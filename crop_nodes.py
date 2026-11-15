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
        if index < 0:
            raise ValueError("未找到 JSON 对象，请让 AI 只输出 JSON。") from None
        try:
            value, _ = json.JSONDecoder().raw_decode(content[index:])
        except json.JSONDecodeError as exc:
            raise ValueError(f"裁剪 JSON 无法解析：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("裁剪 JSON 必须是对象。")
    return value


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
    return torch.stack(crops), torch.stack(cropped_masks), data


_MARGINS = {
    "左侧扩展像素": ("INT", {"default": 16, "min": -4096, "max": 4096}),
    "顶部扩展像素": ("INT", {"default": 16, "min": -4096, "max": 4096}),
    "右侧扩展像素": ("INT", {"default": 16, "min": -4096, "max": 4096}),
    "底部扩展像素": ("INT", {"default": 16, "min": -4096, "max": 4096}),
}
_OUTPUT_TYPES = ("IMAGE", "MASK", CROP_TYPE)
_OUTPUT_NAMES = ("裁剪图像", "矩形遮罩", "裁剪数据")


class AIChatCropFromJSON:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "AI裁剪JSON": ("STRING", {"multiline": True, "forceInput": False}),
            "区域序号": ("INT", {"default": 0, "min": 0, "max": 999}),
            "对齐倍数": (ALIGNMENTS, {"default": "8"}),
            **_MARGINS,
            "允许宽高比不同": ("BOOLEAN", {"default": False}),
        }}

    RETURN_TYPES, RETURN_NAMES = _OUTPUT_TYPES, _OUTPUT_NAMES
    FUNCTION = "crop"
    CATEGORY = "AI Chat/局部裁剪"
    DESCRIPTION = "AI JSON 坐标按参考分辨率换算到 ComfyUI 原图，自动对齐和安全补边。"

    def crop(self, 原图像, AI裁剪JSON, 区域序号, 对齐倍数, 左侧扩展像素,
             顶部扩展像素, 右侧扩展像素, 底部扩展像素, 允许宽高比不同):
        image = _image(原图像)
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
        x1, y1, x2, y2 = _xyxy(boxes[区域序号])
        sx, sy = w / src_w, h / src_h
        rect = _align_box(
            math.floor(x1 * sx) - 左侧扩展像素,
            math.floor(y1 * sy) - 顶部扩展像素,
            math.ceil(x2 * sx) + 右侧扩展像素,
            math.ceil(y2 * sy) + 底部扩展像素,
            w, h, 对齐倍数)
        return _crop_batch(image, [rect] * image.shape[0], 对齐倍数,
                           reference=(src_w, src_h))


class AIChatCropFromMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "手绘遮罩": ("MASK",),
            "遮罩阈值": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0, "step": 0.01}),
            "对齐倍数": (ALIGNMENTS, {"default": "8"}),
            **_MARGINS,
        }}

    RETURN_TYPES, RETURN_NAMES = _OUTPUT_TYPES, _OUTPUT_NAMES
    FUNCTION = "crop"
    CATEGORY = "AI Chat/局部裁剪"
    DESCRIPTION = "手绘遮罩只用于定位，自动转成矩形裁剪和矩形遮罩。"

    def crop(self, 原图像, 手绘遮罩, 遮罩阈值, 对齐倍数, 左侧扩展像素,
             顶部扩展像素, 右侧扩展像素, 底部扩展像素):
        image = _image(原图像)
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
            boxes.append(_align_box(x1 - 左侧扩展像素, y1 - 顶部扩展像素,
                                    x2 + 右侧扩展像素, y2 + 底部扩展像素,
                                    w, h, 对齐倍数))
        return _crop_batch(image, boxes, 对齐倍数)


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
    FUNCTION = "paste"
    CATEGORY = "AI Chat/局部裁剪"
    DESCRIPTION = "根据真实 BBOX 回贴；仅缩放图块，不缩放原图，自动剔除对齐补边。"

    def paste(self, 原图像, 编辑后图像, 裁剪数据, 边缘羽化像素):
        original = _image(原图像)
        edited = _image(编辑后图像, "编辑后图像")
        if not isinstance(裁剪数据, dict) or 裁剪数据.get("version") != 1:
            raise ValueError("需要连接本插件生成的裁剪数据，不能直接传入 AI JSON。")
        count, h, w, _ = original.shape
        if edited.shape[0] != count or len(裁剪数据.get("boxes", [])) != count:
            raise ValueError("原图、编辑图和裁剪数据的批次数量不一致。")
        if (裁剪数据.get("original_width"), 裁剪数据.get("original_height")) != (w, h):
            raise ValueError("原图尺寸与裁剪数据不一致，不能安全回贴。")
        bw, bh = 裁剪数据["batch_width"], 裁剪数据["batch_height"]
        result = original.clone()
        for i, box in enumerate(裁剪数据["boxes"]):
            x, y, sw, sh = (int(box[k]) for k in ("x", "y", "width", "height"))
            if not (0 <= x < w and 0 <= y < h and 0 < sw <= bw and 0 < sh <= bh
                    and x + sw <= w and y + sh <= h):
                raise ValueError("回贴 BBOX 超出原图边界。")
            # Align the *whole* edited patch to the padded crop canvas first.
            # Its padded right/bottom pixels are then deliberately discarded.
            patch = _resize(edited[i], bh, bw)
            patch = patch[:sh, :sw, :3].to(device=result.device, dtype=result.dtype)
            alpha = _soft_rectangle(sh, sw, 边缘羽化像素, result.device, result.dtype)
            target = result[i, y:y + sh, x:x + sw, :3]
            target.copy_(target * (1 - alpha[..., None]) + patch * alpha[..., None])
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
