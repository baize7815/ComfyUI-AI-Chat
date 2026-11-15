"""AI Chat local crops with coordinate-safe round-trip pasting."""

from __future__ import annotations

import json
import math
import re

import torch
import torch.nn.functional as F


CROP_TYPE = "AI_CHAT_CROP_DATA"
ALIGNMENTS = ["2", "4", "8", "16", "32", "64"]


def _image(value, label="图像"):
    if not isinstance(value, torch.Tensor):
        raise ValueError(f"{label}必须是 IMAGE 张量。")
    if value.ndim == 3:
        value = value.unsqueeze(0)
    if value.ndim != 4 or value.shape[-1] not in (3, 4):
        raise ValueError(f"{label}格式须为 [B,H,W,3/4]。")
    return value


def _mask(value, batch):
    if not isinstance(value, torch.Tensor):
        raise ValueError("遮罩必须是 MASK 张量。")
    if value.ndim == 2:
        value = value.unsqueeze(0)
    if value.ndim != 3:
        raise ValueError("MASK 格式须为 [B,H,W]。")
    if value.shape[0] == 1 and batch > 1:
        value = value.expand(batch, -1, -1)
    if value.shape[0] != batch:
        raise ValueError("遮罩批次须与图像匹配。")
    return value


def _finite(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field}必须是有限数字。")
    return float(value)


def _read_json(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("AI 裁剪 JSON 不能为空。")
    content = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.I)
    if fenced:
        content = fenced.group(1)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        index = content.find("{")
        if index >= 0:
            try:
                value, _ = json.JSONDecoder().raw_decode(content[index:])
            except json.JSONDecodeError:
                value = _extract_bbox_by_regex(content)
        else:
            value = _extract_bbox_by_regex(content)
    if not isinstance(value, dict):
        raise ValueError("裁剪 JSON 必须是对象。")
    return value


def _extract_bbox_by_regex(text):
    """Conservative fallback for prose containing explicitly labelled bbox arrays.

    Never treat an arbitrary list of four numbers as a location.
    Dimensions are optional here because the AI Chat preset stamps actual ones.
    """
    number = r"-?\d+(?:\.\d+)?"
    coordinate_pattern = re.compile(
        rf'(?:\b(?:bbox|bounding_box)\b|裁剪坐标|区域坐标)\s*["\']?\s*[:：=]\s*'
        rf'\[\s*({number})\s*,\s*({number})\s*,\s*({number})\s*,\s*({number})\s*\]',
        re.I,
    )
    matches = coordinate_pattern.findall(text)
    if not matches:
        raise ValueError("没有检测到有效的 JSON 或标注的 bbox 坐标，请检查 AI 输出。")
    data = {"regions": [{"bbox": [float(x) for x in values]} for values in matches]}
    width = re.search(r'["\']?(?:image_width|source_width|图像宽度|图片宽度)["\']?\s*[:：=]\s*(\d+)', text, re.I)
    height = re.search(r'["\']?(?:image_height|source_height|图像高度|图片高度)["\']?\s*[:：=]\s*(\d+)', text, re.I)
    if width and height:
        data["image_width"] = int(width.group(1))
        data["image_height"] = int(height.group(1))
    else:
        resolution = re.search(r'(?:图片尺寸|图像尺寸|分辨率)\s*[:：=]\s*(\d+)\s*[×xX*]\s*(\d+)', text)
        if resolution:
            data["image_width"], data["image_height"] = map(int, resolution.groups())
    return data


def _source_size(data):
    for item in (data, data.get("image_size"), data.get("source_size"),
                 data.get("original_size")):
        if not isinstance(item, dict):
            continue
        w = next((item[k] for k in ("image_width", "source_width", "original_width", "width") if k in item), None)
        h = next((item[k] for k in ("image_height", "source_height", "original_height", "height") if k in item), None)
        if w is not None and h is not None:
            w, h = _finite(w, "参考宽度"), _finite(h, "参考高度")
            if w <= 0 or h <= 0:
                raise ValueError("参考宽高必须大于 0。")
            return w, h
    raise ValueError("JSON 必须提供 image_width、image_height（或 image_size）。")


def _xyxy(region):
    if isinstance(region, dict):
        if "bbox" in region:
            return _xyxy(region["bbox"])
        for keys in (("x1", "y1", "x2", "y2"), ("left", "top", "right", "bottom")):
            if all(k in region for k in keys):
                region = [region[k] for k in keys]
                break
        else:
            if all(k in region for k in ("x", "y", "width", "height")):
                x, y = _finite(region["x"], "x"), _finite(region["y"], "y")
                region = [x, y, x + _finite(region["width"], "width"),
                          y + _finite(region["height"], "height")]
            else:
                raise ValueError("区域应包含 bbox:[x1,y1,x2,y2] 或 x/y/width/height。")
    if not isinstance(region, (tuple, list)) or len(region) != 4:
        raise ValueError("bbox 应为四个数字。")
    x1, y1, x2, y2 = [_finite(v, "bbox 坐标") for v in region]
    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox 必须满足 x1<x2、y1<y2。")
    return x1, y1, x2, y2


def _align_box(x1, y1, x2, y2, width, height, multiple):
    """Cover desired half-open xyxy using aligned top-left/virtual bottom-right.

    A source whose width/height is odd cannot always provide an entirely
    aligned in-bounds BBOX; pad the crop *outside* the source instead.
    """
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    if x1 >= x2 or y1 >= y2:
        raise ValueError("裁剪区域越界或扩边后为空。")
    n = int(multiple)
    left = (math.floor(x1) // n) * n
    top = (math.floor(y1) // n) * n
    right_virtual = max(left + n, math.ceil(x2 / n) * n)
    bottom_virtual = max(top + n, math.ceil(y2 / n) * n)
    right, bottom = min(width, right_virtual), min(height, bottom_virtual)
    return {
        "x": left, "y": top, "width": right - left, "height": bottom - top,
        "pad_right": right_virtual - right, "pad_bottom": bottom_virtual - bottom,
        "crop_width": right_virtual - left, "crop_height": bottom_virtual - top,
    }


def _crop_batch(image, boxes, multiple, reference=None):
    count, height, width, _ = image.shape
    if len(boxes) != count:
        raise ValueError("裁剪框与图像批次数量不匹配。")
    # All tensors in one ComfyUI IMAGE batch must have the same size.
    out_w = max(b["crop_width"] for b in boxes)
    out_h = max(b["crop_height"] for b in boxes)
    crops, cropped_masks = [], []
    for i, b in enumerate(boxes):
        x, y, w, h = (b[k] for k in ("x", "y", "width", "height"))
        tile = image[i, y:y+h, x:x+w].permute(2, 0, 1)
        tile = F.pad(tile, (0, out_w - w, 0, out_h - h), mode="replicate")
        crops.append(tile.permute(1, 2, 0))
        selected = torch.ones((h, w), dtype=image.dtype, device=image.device)
        cropped_masks.append(F.pad(selected, (0, out_w - w, 0, out_h - h)))
    data = {
        "version": 1, "coordinate_system": "xyxy_half_open",
        "original_width": width, "original_height": height,
        "alignment": int(multiple), "batch_width": out_w, "batch_height": out_h,
        "boxes": [dict(b) for b in boxes],
    }
    if reference is not None:
        data["ai_reference_width"], data["ai_reference_height"] = reference
    return torch.stack(crops), torch.stack(cropped_masks), data, _crop_preview(image, boxes)


def _crop_preview(image, boxes):
    """Render the real crop rectangle on the full-size original image."""
    preview = image.clone()
    _, height, width, _ = preview.shape
    thickness = max(1, min(6, round(min(height, width) / 400)))
    red = preview.new_tensor((1.0, 0.12, 0.12))
    for i, box in enumerate(boxes):
        x, y, w, h = (box[key] for key in ("x", "y", "width", "height"))
        t = min(thickness, w, h)
        x2, y2 = x + w, y + h
        preview[i, y:y + t, x:x2, :3] = red
        preview[i, y2 - t:y2, x:x2, :3] = red
        preview[i, y:y2, x:x + t, :3] = red
        preview[i, y:y2, x2 - t:x2, :3] = red
    return preview


_EXPANSION = {"裁剪扩展像素": ("INT", {"default": 16, "min": 0, "max": 4096})}
_OUTPUT_TYPES = ("IMAGE", "MASK", CROP_TYPE, "IMAGE")
_OUTPUT_NAMES = ("裁剪图像", "矩形遮罩", "裁剪数据", "裁剪框预览")
_PREVIEW_MODES = ["裁剪结果", "原图标框", "关闭"]


def _validate_alignment(value):
    if str(value) not in ALIGNMENTS:
        raise ValueError("对齐倍数无效，请从 2/4/8/16/32/64 选择；旧工作流建议重建节点。")
    return str(value)


def _emit_crops(image, indexed_boxes, alignment, preview_mode, reference=None):
    """Return one list item per independent crop with matching metadata."""
    if not indexed_boxes:
        raise ValueError("没有可以裁剪的区域。")
    if preview_mode not in _PREVIEW_MODES:
        raise ValueError("图像预览选项无效。")
    crops, masks, records, previews = [], [], [], []
    for source_idx, box in indexed_boxes:
        crop, mask, record, preview = _crop_batch(
            image[source_idx:source_idx + 1], [box], alignment, reference=reference)
        record["source_batch_index"] = source_idx
        record["source_batch_count"] = image.shape[0]
        crops.append(crop)
        masks.append(mask)
        records.append(record)
        previews.append(preview)
    outputs = (crops, masks, records, previews)
    if preview_mode == "关闭":
        return {"result": outputs}
    # Same built-in ComfyUI preview mechanism as Easy-Use, without an extra node.
    from nodes import PreviewImage
    presenter = PreviewImage()
    images = []
    for thumbnail in (crops if preview_mode == "裁剪结果" else previews):
        images.extend(presenter.save_images(thumbnail, "AIChatCropPreview")["ui"]["images"])
    return {"ui": {"images": images}, "result": outputs}


class AIChatCropFromJSON:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "AI裁剪JSON": ("STRING", {"forceInput": True}),
            "区域序号": ("INT", {"default": 0, "min": -1, "max": 999, "tooltip": "-1：全部区域；0 起按序号选择单个区域。"}),
            "对齐倍数": (ALIGNMENTS, {"default": "8"}),
            **_EXPANSION,
            "允许宽高比不同": ("BOOLEAN", {"default": False}),
            "图像预览": (_PREVIEW_MODES, {"default": "裁剪结果"}),
        }}

    RETURN_TYPES, RETURN_NAMES = _OUTPUT_TYPES, _OUTPUT_NAMES
    OUTPUT_IS_LIST = (True, True, True, True)
    OUTPUT_NODE = True
    FUNCTION = "crop"
    CATEGORY = "🫧 AI Chat"
    DESCRIPTION = "AI JSON 坐标按参考分辨率换算到 ComfyUI 原图，自动对齐和安全补边。"

    def crop(self, 原图像, AI裁剪JSON, 区域序号, 对齐倍数, 裁剪扩展像素,
             允许宽高比不同, 图像预览="裁剪结果"):
        image = _image(原图像)
        alignment = _validate_alignment(对齐倍数)
        if isinstance(区域序号, bool) or not isinstance(区域序号, int) or 区域序号 < -1:
            raise ValueError("区域序号必须是整数（-1 为全部、0 起选择单区域）。旧节点出现 NaN 时请重建节点。")
        obj = _read_json(AI裁剪JSON)
        src_w, src_h = _source_size(obj)
        boxes = obj.get("regions", obj.get("boxes", obj.get("bboxes")))
        if boxes is None:
            boxes = [obj]
        if not isinstance(boxes, list) or not boxes:
            raise ValueError("regions 应为非空列表。")
        if 区域序号 >= len(boxes):
            raise ValueError(f"区域序号越界：共有 {len(boxes)} 个区域。")
        _, h, w, _ = image.shape
        if not 允许宽高比不同 and abs((w / h) / (src_w / src_h) - 1) > 0.02:
            raise ValueError("AI 参考图与 ComfyUI 原图宽高比相差超过 2%；请核对尺寸。")
        sx, sy = w / src_w, h / src_h
        selected = range(len(boxes)) if 区域序号 == -1 else (区域序号,)
        indexed_boxes = []
        for region_index in selected:
            x1, y1, x2, y2 = _xyxy(boxes[region_index])
            rect = _align_box(
                math.floor(x1 * sx) - 裁剪扩展像素,
                math.floor(y1 * sy) - 裁剪扩展像素,
                math.ceil(x2 * sx) + 裁剪扩展像素,
                math.ceil(y2 * sy) + 裁剪扩展像素,
                w, h, alignment)
            for image_index in range(image.shape[0]):
                indexed_boxes.append((image_index, rect))
        return _emit_crops(image, indexed_boxes, alignment, 图像预览,
                           reference=(src_w, src_h))


class AIChatCropFromMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "手绘遮罩": ("MASK",),
            "遮罩阈值": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0, "step": 0.01}),
            "对齐倍数": (ALIGNMENTS, {"default": "8"}),
            **_EXPANSION,
            "图像预览": (_PREVIEW_MODES, {"default": "裁剪结果"}),
        }}

    RETURN_TYPES, RETURN_NAMES = _OUTPUT_TYPES, _OUTPUT_NAMES
    OUTPUT_IS_LIST = (True, True, True, True)
    OUTPUT_NODE = True
    FUNCTION = "crop"
    CATEGORY = "🫧 AI Chat"
    DESCRIPTION = "手绘遮罩只用于定位，自动转成矩形裁剪和矩形遮罩。"

    def crop(self, 原图像, 手绘遮罩, 遮罩阈值, 对齐倍数, 裁剪扩展像素,
             图像预览="裁剪结果"):
        image = _image(原图像)
        alignment = _validate_alignment(对齐倍数)
        mask = _mask(手绘遮罩, image.shape[0])
        _, h, w, _ = image.shape
        if tuple(mask.shape[1:]) != (h, w):
            raise ValueError("手绘遮罩宽高必须与原图一致。")
        boxes = []
        for item in mask:
            active = torch.nonzero(torch.isfinite(item) & (item > 遮罩阈值), as_tuple=False)
            if active.numel() == 0:
                raise ValueError("手绘遮罩为空，无法裁剪。")
            y1, x1 = active.min(dim=0).values.tolist()
            y2, x2 = (active.max(dim=0).values + 1).tolist()
            boxes.append(_align_box(x1 - 裁剪扩展像素, y1 - 裁剪扩展像素,
                                    x2 + 裁剪扩展像素, y2 + 裁剪扩展像素,
                                    w, h, alignment))
        return _emit_crops(image, list(enumerate(boxes)), alignment, 图像预览)


def _resize(tile, height, width):
    if tuple(tile.shape[:2]) == (height, width):
        return tile
    output = F.interpolate(tile.permute(2, 0, 1).unsqueeze(0).float(),
                           size=(height, width), mode="bilinear", align_corners=False)
    return output[0].permute(1, 2, 0).to(dtype=tile.dtype)


def _soft_rectangle(h, w, feather, device, dtype):
    if feather == 0:
        return torch.ones((h, w), device=device, dtype=dtype)
    ys = torch.arange(h, device=device, dtype=torch.float32) + 0.5
    xs = torch.arange(w, device=device, dtype=torch.float32) + 0.5
    dy = torch.minimum(ys, h - ys)
    dx = torch.minimum(xs, w - xs)
    return (torch.minimum(dy[:, None], dx[None, :]) / feather).clamp(0, 1).to(dtype)


class AIChatPasteCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "编辑后图像": ("IMAGE",),
            "裁剪数据": (CROP_TYPE,),
            "边缘羽化像素": ("INT", {"default": 8, "min": 0, "max": 1024}),
        }}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("合并图像",)
    INPUT_IS_LIST = True
    FUNCTION = "paste"
    CATEGORY = "🫧 AI Chat"
    DESCRIPTION = "根据真实 BBOX 回贴；仅缩放图块，不缩放原图，自动剔除对齐补边。"

    def paste(self, 原图像, 编辑后图像, 裁剪数据, 边缘羽化像素):
        # INPUT_IS_LIST gathers items from the automatically mapped crop branch.
        originals = 原图像 if isinstance(原图像, list) else [原图像]
        edits = 编辑后图像 if isinstance(编辑后图像, list) else [编辑后图像]
        records = 裁剪数据 if isinstance(裁剪数据, list) else [裁剪数据]
        feather_values = 边缘羽化像素 if isinstance(边缘羽化像素, list) else [边缘羽化像素]
        if len(originals) != 1 or not feather_values:
            raise ValueError("原图像必须是单个 IMAGE 输入；不能用多路原图列表混合回贴。")
        original = _image(originals[0])
        if len(edits) != len(records) or not edits:
            raise ValueError("编辑结果数量与裁剪数据不一致，请确保每个区域都编辑成功且没有改变顺序。")
        feather = int(feather_values[0])
        if feather < 0:
            raise ValueError("边缘羽化不能为负数。")
        count, h, w, _ = original.shape
        result = original.clone()
        for item_index, (edited_item, record) in enumerate(zip(edits, records)):
            if not isinstance(record, dict) or record.get("version") != 1:
                raise ValueError("请连接裁剪节点输出的裁剪数据，不要直接连接 AI JSON。")
            if (record.get("original_width"), record.get("original_height")) != (w, h):
                raise ValueError("裁剪数据原图尺寸与当前原图不一致，不能回贴。")
            edited = _image(edited_item, "编辑后图像")
            boxes = record.get("boxes", [])
            # Compatibility: older metadata may describe an image batch.
            source_index = record.get("source_batch_index")
            if source_index is None and len(boxes) == count and edited.shape[0] == count:
                indices = range(count)
            elif len(boxes) == 1 and edited.shape[0] == 1:
                source_index = 0 if source_index is None else source_index
                if not isinstance(source_index, int) or not 0 <= source_index < count:
                    raise ValueError("裁剪数据源图片序号无效。")
                indices = (source_index,)
            else:
                raise ValueError(f"第 {item_index + 1} 组裁剪数据与编辑图像批次不匹配。")
            bw, bh = record["batch_width"], record["batch_height"]
            for patch_index, original_index in enumerate(indices):
                box = boxes[patch_index] if len(boxes) > 1 else boxes[0]
                x, y, sw, sh = (int(box[k]) for k in ("x", "y", "width", "height"))
                if not (0 <= x < w and 0 <= y < h and 0 < sw <= bw and 0 < sh <= bh
                        and x + sw <= w and y + sh <= h):
                    raise ValueError("回贴 BBOX 超出原图边界。")
                # Non-uniform scaling to padded canvas; discard padding.
                patch = _resize(edited[patch_index], bh, bw)
                patch = patch[:sh, :sw, :3].to(device=result.device, dtype=result.dtype)
                alpha = _soft_rectangle(sh, sw, feather, result.device, result.dtype)
                target = result[original_index, y:y + sh, x:x + sw, :3]
                target.copy_(target * (1 - alpha[..., None]) + patch * alpha[..., None])
        # Multiple/overlapping regions are composited in regions-array order.
        return (result,)


NODE_CLASS_MAPPINGS = {
    "AIChatCropFromJSON": AIChatCropFromJSON,
    "AIChatCropFromMask": AIChatCropFromMask,
    "AIChatPasteCrop": AIChatPasteCrop,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AIChatCropFromJSON": "AI Chat JSON区域裁剪",
    "AIChatCropFromMask": "AI Chat 手绘遮罩裁剪",
    "AIChatPasteCrop": "AI Chat 局部图像回贴",
}
