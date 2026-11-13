"""Shared, validated image conversion helpers for ComfyUI IMAGE batches."""

from __future__ import annotations

import base64
import io
from typing import Iterable

import numpy as np
import torch
from PIL import Image


MAX_IMAGE_COUNT = 8
MAX_IMAGE_PIXELS = 40_000_000
MAX_BATCH_PIXELS = 40_000_000


def _validate_pil(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("图像尺寸必须大于 0。")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"图像像素数超过限制：{width}×{height}。")
    return image.convert("RGB") if image.mode != "RGB" else image


def tensor_to_pils(image, max_images: int = MAX_IMAGE_COUNT) -> list[Image.Image]:
    if isinstance(image, dict) and "images" in image:
        image = image["images"]
    if not isinstance(image, torch.Tensor):
        raise TypeError("IMAGE 输入应为 torch.Tensor 或包含 images 键的字典。")
    if image.ndim == 3:
        image = image.unsqueeze(0)
    if image.ndim != 4 or image.shape[-1] not in (3, 4):
        raise ValueError("IMAGE 张量必须是 [B,H,W,3] 或 [B,H,W,4]。")
    if image.shape[0] <= 0:
        raise ValueError("IMAGE 批次不能为空。")
    if image.shape[0] > max_images:
        raise ValueError(f"单次最多允许 {max_images} 张输入图像。")
    height, width = int(image.shape[1]), int(image.shape[2])
    if height * width > MAX_IMAGE_PIXELS:
        raise ValueError(f"图像像素数超过限制：{width}×{height}。")
    if int(image.shape[0]) * height * width > MAX_BATCH_PIXELS:
        raise ValueError("输入图像批次总像素数超过限制。")

    array = (image[..., :3].detach().clamp(0, 1).cpu().numpy() * 255.0).round().astype(np.uint8)
    return [_validate_pil(Image.fromarray(item, mode="RGB")) for item in array]


def pils_to_tensor_batch(
    images: Iterable[Image.Image],
    max_images: int | None = None,
    max_batch_pixels: int | None = None,
) -> torch.Tensor:
    if max_images is None:
        max_images = MAX_IMAGE_COUNT
    if max_batch_pixels is None:
        max_batch_pixels = MAX_BATCH_PIXELS
    source_images = list(images)
    if not source_images:
        raise ValueError("没有可输出的图像。")
    if len(source_images) > max_images:
        raise ValueError(f"单次最多允许输出 {max_images} 张图像。")

    for image in source_images:
        width, height = image.size
        if width <= 0 or height <= 0:
            raise ValueError("图像尺寸必须大于 0。")
        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError(f"图像像素数超过限制：{width}×{height}。")
    max_width = max(image.width for image in source_images)
    max_height = max(image.height for image in source_images)
    if len(source_images) * max_width * max_height > max_batch_pixels:
        raise ValueError("输出图像批次补边后的总像素数超过限制。")
    pils = [_validate_pil(image) for image in source_images]
    arrays = []
    for image in pils:
        if image.size != (max_width, max_height):
            canvas = Image.new("RGB", (max_width, max_height), (0, 0, 0))
            offset = ((max_width - image.width) // 2, (max_height - image.height) // 2)
            canvas.paste(image, offset)
            image = canvas
        arrays.append(np.asarray(image, dtype=np.float32) / 255.0)
    return torch.from_numpy(np.stack(arrays, axis=0))


def pil_to_mask(image: Image.Image) -> torch.Tensor:
    """Convert PIL transparency to a ComfyUI MASK tensor."""
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("图像尺寸必须大于 0。")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"图像像素数超过限制：{width}×{height}。")

    if "A" in image.getbands():
        alpha = image.getchannel("A")
    elif "transparency" in image.info:
        # Palette images can carry transparency without exposing an A band.
        alpha = image.convert("RGBA").getchannel("A")
    else:
        return torch.zeros((1, height, width), dtype=torch.float32)

    alpha_array = np.array(alpha, dtype=np.float32, copy=True) / 255.0
    return torch.from_numpy(1.0 - alpha_array).unsqueeze(0)


def pil_to_base64_data_url(
    image: Image.Image,
    image_format: str = "JPEG",
    quality: int = 85,
) -> str:
    normalized = _validate_pil(image)
    buffer = io.BytesIO()
    normalized.save(buffer, format=image_format, quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    mime_subtype = "jpeg" if image_format.upper() == "JPEG" else image_format.lower()
    return f"data:image/{mime_subtype};base64,{encoded}"
