"""Grid image splitting and size-safe feathered merging for AI Chat."""

from __future__ import annotations

import math
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw


TILE_DATA_TYPE = "AI_CHAT_TILE_DATA"
ALIGNMENTS = ["2", "4", "8", "16", "32", "64"]
PREVIEW_MODES = ["网格与外扩", "仅基础网格", "关闭"]


def _image(value, title="图像"):
    if not isinstance(value, torch.Tensor) or value.ndim != 4:
        raise ValueError(f"{title}必须是 ComfyUI IMAGE 张量 [B,H,W,C]。")
    if value.shape[-1] not in (3, 4):
        raise ValueError(f"{title}必须有 3 或 4 个颜色通道。")
    return value


def _grid_edges(length, count):
    # Pixel-accurate partitions cover odd-sized image borders too.
    return [i * length // count for i in range(count + 1)]


def _aligned_crop(left, top, right, bottom, width, height, alignment):
    """Expand to the alignment grid and pad virtual edges when necessary."""
    n = int(alignment)
    x0, y0 = (left // n) * n, (top // n) * n
    virtual_x1 = max(x0 + n, math.ceil(right / n) * n)
    virtual_y1 = max(y0 + n, math.ceil(bottom / n) * n)
    x1, y1 = min(width, virtual_x1), min(height, virtual_y1)
    return {
        "crop_box": [x0, y0, x1 - x0, y1 - y0],
        "aligned_size": [virtual_x1 - x0, virtual_y1 - y0],
        "boundary_pad": [virtual_x1 - x1, virtual_y1 - y1],
    }


def _build_tiles(width, height, rows, cols, expand, alignment):
    xs, ys = _grid_edges(width, cols), _grid_edges(height, rows)
    tiles = []
    for row in range(rows):
        for col in range(cols):
            x0, x1 = xs[col], xs[col + 1]
            y0, y1 = ys[row], ys[row + 1]
            aligned = _aligned_crop(
                max(0, x0 - expand), max(0, y0 - expand),
                min(width, x1 + expand), min(height, y1 + expand),
                width, height, alignment)
            cx, cy, cw, ch = aligned["crop_box"]
            tiles.append({
                "index": row * cols + col, "row": row, "col": col,
                "base_box": [x0, y0, x1 - x0, y1 - y0],
                **aligned,
                "overlap": [x0 - cx, y0 - cy, cx + cw - x1, cy + ch - y1],
            })
    return tiles


def _preview(image, tiles, mode):
    """Draw numbered base grid (cyan) and actual crop boxes (orange)."""
    pixels = image[0, :, :, :3].detach().float().clamp(0, 1).cpu().numpy()
    visual = Image.fromarray(np.round(pixels * 255).astype(np.uint8))
    draw = ImageDraw.Draw(visual)
    thickness = max(1, min(6, round(min(visual.size) / 350)))
    for tile in tiles:
        bx, by, bw, bh = tile["base_box"]
        cx, cy, cw, ch = tile["crop_box"]
        if mode == "网格与外扩":
            draw.rectangle((cx, cy, cx + cw - 1, cy + ch - 1),
                           outline=(255, 160, 34), width=thickness)
        draw.rectangle((bx, by, bx + bw - 1, by + bh - 1),
                       outline=(0, 220, 230), width=thickness)
        label = str(tile["index"] + 1)
        lx, ly = bx + 3, by + 3
        label_bounds = draw.textbbox((lx, ly), label)
        draw.rectangle((label_bounds[0] - 2, label_bounds[1] - 1,
                        label_bounds[2] + 2, label_bounds[3] + 2), fill=(0, 0, 0))
        draw.text((lx, ly), label, fill=(255, 255, 255))
    arr = np.asarray(visual, dtype=np.uint8).copy()
    return (torch.from_numpy(arr).float() / 255.0).unsqueeze(0).to(
        device=image.device, dtype=image.dtype)


def _feather_weights(tile, height, width, feather, device):
    """Only blend in the actual overlapping margins, never source boundaries."""
    left, top, right, bottom = tile["overlap"]
    if feather == 0:
        # Hard partition without averaging overlapping edits.
        bx, by, bw, bh = tile["base_box"]
        cx, cy, _, _ = tile["crop_box"]
        mask = torch.zeros((height, width), dtype=torch.float32, device=device)
        mask[by - cy:by - cy + bh, bx - cx:bx - cx + bw] = 1
        return mask[:, :, None]
    xs = torch.arange(width, device=device, dtype=torch.float32) + 0.5
    ys = torch.arange(height, device=device, dtype=torch.float32) + 0.5
    wx, wy = torch.ones_like(xs), torch.ones_like(ys)
    if left:
        wx = wx * (xs / min(feather, left)).clamp(0, 1)
    if right:
        wx = wx * ((width - xs) / min(feather, right)).clamp(0, 1)
    if top:
        wy = wy * (ys / min(feather, top)).clamp(0, 1)
    if bottom:
        wy = wy * ((height - ys) / min(feather, bottom)).clamp(0, 1)
    return (wy[:, None] * wx[None, :])[:, :, None]


class AIChatTileSplit:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "分块行数": ("INT", {"default": 3, "min": 1, "max": 32}),
            "分块列数": ("INT", {"default": 3, "min": 1, "max": 32}),
            "外扩像素": ("INT", {"default": 64, "min": 0, "max": 2048}),
            "对齐倍数": (ALIGNMENTS, {"default": "8"}),
            "图像预览": (PREVIEW_MODES, {"default": "网格与外扩"}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK", TILE_DATA_TYPE, "INT", "IMAGE")
    RETURN_NAMES = ("分块图像批次", "有效区域遮罩", "分块数据", "分块总数", "分块框预览")
    FUNCTION = "split"
    CATEGORY = "🫧 AI Chat"
    OUTPUT_NODE = True
    DESCRIPTION = "按行列分块并四边外扩；节点内直接显示编号网格和真实裁剪框。"

    def split(self, 原图像, 分块行数=3, 分块列数=3, 外扩像素=64,
              对齐倍数="8", 图像预览="网格与外扩"):
        image = _image(原图像, "原图像")
        batch, height, width, _ = image.shape
        if batch != 1:
            raise ValueError("图像分块只接收一张原图，请先从图像批次选出一张。")
        if (not isinstance(分块行数, int) or not isinstance(分块列数, int)
                or not 1 <= 分块行数 <= height or not 1 <= 分块列数 <= width):
            raise ValueError("分块行列必须为正整数，且不能超过原图宽高。")
        if 分块行数 * 分块列数 > 256:
            raise ValueError("单次最多支持 256 块，请降低行列数。")
        if not isinstance(外扩像素, int) or 外扩像素 < 0:
            raise ValueError("外扩像素必须为非负整数。")
        if str(对齐倍数) not in ALIGNMENTS:
            raise ValueError("对齐倍数只能选择 2、4、8、16、32 或 64。")
        if 图像预览 not in PREVIEW_MODES:
            raise ValueError("未知的图像预览模式。")
        tiles = _build_tiles(width, height, 分块行数, 分块列数,
                             外扩像素, int(对齐倍数))
        canvas_w = max(tile["aligned_size"][0] for tile in tiles)
        canvas_h = max(tile["aligned_size"][1] for tile in tiles)
        patches, masks = [], []
        for tile in tiles:
            x, y, w, h = tile["crop_box"]
            region = image[0, y:y + h, x:x + w].permute(2, 0, 1)
            # Replicate-pad right/bottom to one model-compatible batch size.
            padded = F.pad(region, (0, canvas_w - w, 0, canvas_h - h), mode="replicate")
            patches.append(padded.permute(1, 2, 0))
            valid = torch.zeros((canvas_h, canvas_w),
                                dtype=image.dtype, device=image.device)
            valid[:h, :w] = 1
            masks.append(valid)
        data = {
            "type": "ai_chat_tile_set", "version": 1,
            "original_size": [width, height],
            "rows": 分块行数, "cols": 分块列数,
            "alignment": int(对齐倍数), "expand_px": 外扩像素,
            "canvas_size": [canvas_w, canvas_h],
            "tiles": tiles,
        }
        preview = image if 图像预览 == "关闭" else _preview(image, tiles, 图像预览)
        result = (torch.stack(patches), torch.stack(masks), data, len(tiles), preview)
        if 图像预览 == "关闭":
            return {"result": result}
        # Native ComfyUI preview: image is displayed directly INSIDE this node.
        from nodes import PreviewImage
        visuals = PreviewImage().save_images(preview, "AIChatTilePreview")["ui"]["images"]
        return {"ui": {"images": visuals}, "result": result}


class AIChatTileMerge:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "原图像": ("IMAGE",),
            "编辑后分块批次": ("IMAGE",),
            "分块数据": (TILE_DATA_TYPE,),
            "羽化像素": ("INT", {"default": 32, "min": 0, "max": 2048}),
        }}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("合并图像",)
    FUNCTION = "merge"
    CATEGORY = "🫧 AI Chat"
    DESCRIPTION = "非等比还原编辑块并剔除补边，按原图坐标加权羽化合并。"

    def merge(self, 原图像, 编辑后分块批次, 分块数据, 羽化像素=32):
        image = _image(原图像, "原图像")
        edited = _image(编辑后分块批次, "编辑后分块批次")
        if image.shape[0] != 1:
            raise ValueError("合并节点只接收单张原图。")
        if not isinstance(分块数据, dict) or 分块数据.get("type") != "ai_chat_tile_set":
            raise ValueError("请连接「AI Chat 图像分块」输出的分块数据。")
        _, height, width, _ = image.shape
        if 分块数据.get("original_size") != [width, height]:
            raise ValueError("原图尺寸与分块数据不一致。")
        tiles = 分块数据.get("tiles", [])
        if (edited.shape[0] != len(tiles) or
                len(tiles) != 分块数据.get("rows", 0) * 分块数据.get("cols", 0)):
            raise ValueError("编辑后分块数量和分块数据不匹配，请保持原分块顺序。")
        if not isinstance(羽化像素, int) or 羽化像素 < 0:
            raise ValueError("羽化像素必须为非负整数。")
        canvas_w, canvas_h = 分块数据["canvas_size"]
        if canvas_w <= 0 or canvas_h <= 0:
            raise ValueError("分块画布尺寸无效。")
        accum = torch.zeros((height, width, 3), device=image.device, dtype=torch.float32)
        weights = torch.zeros((height, width, 1), device=image.device, dtype=torch.float32)
        for i, tile in enumerate(tiles):
            if tile.get("index") != i:
                raise ValueError("分块数据的索引顺序无效。")
            x, y, w, h = tile["crop_box"]
            bx, by, bw, bh = tile["base_box"]
            if not (0 <= x < width and 0 <= y < height and
                    0 < w <= canvas_w and 0 < h <= canvas_h and
                    x + w <= width and y + h <= height and
                    x <= bx < bx + bw <= x + w and y <= by < by + bh <= y + h):
                raise ValueError(f"第 {i + 1} 块的位置无效。")
            patch = edited[i, :, :, :3].permute(2, 0, 1).unsqueeze(0).float()
            if patch.shape[2:] != (canvas_h, canvas_w):
                patch = F.interpolate(patch, size=(canvas_h, canvas_w),
                                      mode="bilinear", align_corners=False)
            # Discard all virtual alignment / uniform batch padding.
            region = patch[0, :, :h, :w].permute(1, 2, 0).to(image.device)
            alpha = _feather_weights(tile, h, w, 羽化像素, image.device)
            accum[y:y + h, x:x + w] += region * alpha
            weights[y:y + h, x:x + w] += alpha
        result = image.clone()
        restored = accum / weights.clamp(min=1e-8)
        result[0, :, :, :3] = torch.where(
            weights > 1e-8, restored, image[0, :, :, :3].float()
        ).to(image.dtype).clamp(0, 1)
        return (result,)


NODE_CLASS_MAPPINGS = {"AIChatTileSplit": AIChatTileSplit, "AIChatTileMerge": AIChatTileMerge}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AIChatTileSplit": "图像分块",
    "AIChatTileMerge": "分块合并",
}
