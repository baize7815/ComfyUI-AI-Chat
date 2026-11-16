"""Independent ComfyUI image preview bridge with native mask-editor support.

Designed around ComfyUI's PreviewImage and mask-editor file conventions. This
module does not import or require ComfyUI-Impact-Pack.
"""

from __future__ import annotations

from collections import OrderedDict
import logging
import os
from pathlib import Path
import threading
import uuid

import numpy as np
from PIL import Image, ImageOps
import torch
import torch.nn.functional as F


_FILE_REFERENCES = OrderedDict()
_NODE_HISTORY = OrderedDict()
_LAST_MASK = OrderedDict()
_LOCK = threading.RLock()
_MAX_ENTRIES = 128
LOGGER = logging.getLogger("AI_Chat")


def _remember(mapping, key, value):
    with _LOCK:
        mapping[key] = value
        mapping.move_to_end(key)
        while len(mapping) > _MAX_ENTRIES:
            mapping.popitem(last=False)


def resolve_path(filename, subfolder, kind, *, require_exists=True):
    """Restrict file references to ComfyUI-managed directories only."""
    import folder_paths

    if kind not in ("input", "output", "temp"):
        raise ValueError("Unsupported image storage type.")
    if not isinstance(filename, str) or not filename or not isinstance(subfolder, str):
        raise ValueError("Invalid image filename.")
    if Path(filename).name != filename or filename in (".", ".."):
        raise ValueError("Image filename must be a single file name.")
    for part in (filename, subfolder):
        if "\x00" in part or "\\" in part:
            raise ValueError("Invalid image path.")
    base = {
        "input": folder_paths.get_input_directory,
        "output": folder_paths.get_output_directory,
        "temp": folder_paths.get_temp_directory,
    }[kind]()
    root = Path(base).resolve()
    if Path(subfolder).is_absolute() or any(x in (".", "..") for x in Path(subfolder).parts):
        raise ValueError("Image subfolder cannot escape the ComfyUI directory.")
    full = (root / subfolder / filename).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        raise ValueError("Image path escapes the managed directory.") from None
    if require_exists and not full.is_file():
        raise FileNotFoundError("Image file is unavailable.")
    return full


def register_file(node_id, item):
    """Return an opaque ID for one immutable, validated preview file."""
    if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
        raise ValueError("Invalid node id.")
    if not isinstance(item, dict):
        raise ValueError("Invalid file reference.")
    filename = item.get("filename")
    subfolder = item.get("subfolder", "")
    kind = item.get("type", "input")
    path = resolve_path(filename, subfolder, kind)
    descriptor = {"filename": filename, "subfolder": subfolder, "type": kind}
    reference = f"$aichat-{node_id}-{uuid.uuid4().hex}"
    _remember(_FILE_REFERENCES, reference, (path, descriptor))
    mask = _file_mask(path)
    if mask is not None:
        _remember(_LAST_MASK, node_id, mask)
    return reference


def lookup_item(reference):
    with _LOCK:
        saved = _FILE_REFERENCES.get(reference)
    if saved is None:
        return None
    path, item = saved
    return dict(item) if path.is_file() else None


def _file_mask(path):
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        if "A" not in image.getbands():
            return None
        alpha = np.asarray(image.getchannel("A"), dtype=np.float32) / 255.0
        return (1.0 - torch.from_numpy(alpha.copy())).unsqueeze(0)


def _load_reference(reference):
    with _LOCK:
        entry = _FILE_REFERENCES.get(reference)
    if entry is None or not entry[0].is_file():
        return None
    path, descriptor = entry
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        if "A" in image.getbands():
            alpha = np.asarray(image.getchannel("A"), dtype=np.float32) / 255.0
            mask = (1.0 - torch.from_numpy(alpha.copy())).unsqueeze(0)
        else:
            mask = None
    return torch.from_numpy(rgb.copy()).unsqueeze(0), mask, dict(descriptor)


def _restore_mask(mask, height, width):
    if mask.shape[1:] == (height, width):
        return mask
    return F.interpolate(mask[:, None].float(), size=(height, width),
                         mode="nearest")[:, 0].clamp(0, 1)


def _rgba_preview(images, mask):
    if mask is None:
        return images
    rgba = torch.cat((images[:, :, :, :3], torch.ones_like(images[:, :, :, :1])), dim=-1)
    resized = _restore_mask(mask, images.shape[1], images.shape[2])
    rgba[:, :, :, 3] = 1.0 - resized.to(device=images.device, dtype=images.dtype)
    return rgba


def _same_images(left, right):
    if not isinstance(left, torch.Tensor) or left.shape != right.shape:
        return False
    return bool(torch.equal(left, right.detach().cpu()))


class AIChatPreviewBridge:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "image": ("STRING", {"default": ""}),
            },
            "optional": {
                "block": ("BOOLEAN", {"default": False,
                                      "label_on": "遮罩为空时阻塞", "label_off": "不阻塞"}),
                "restore_mask": (["never", "always", "if_same_size"],
                                 {"default": "never"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("图像", "遮罩")
    OUTPUT_NODE = True
    FUNCTION = "bridge"
    CATEGORY = "🫧 AI Chat"
    DESCRIPTION = "内嵌预览，使用 ComfyUI 遮罩编辑器绘制并传递遮罩；无需安装 Impact Pack。"

    def bridge(self, images, image, unique_id, block=False, restore_mask="never",
               prompt=None, extra_pnginfo=None):
        import nodes

        if not isinstance(images, torch.Tensor) or images.ndim != 4 or images.shape[-1] < 3:
            raise ValueError("需要有效的 ComfyUI IMAGE 图像。")
        if restore_mask not in ("never", "always", "if_same_size"):
            raise ValueError("无效的遮罩恢复设置。")
        node_id = str(unique_id)
        with _LOCK:
            previous = _NODE_HISTORY.get(node_id)
        fresh = previous is None or not _same_images(previous[0], images)
        if fresh and restore_mask == "never":
            with _LOCK:
                _LAST_MASK.pop(node_id, None)

        # The node preview image from its previous execution is authoritative
        # until the mask editor supplies a newly registered image.
        reference = image
        if not fresh and previous is not None and image == previous[1]:
            reference = previous[2]
        loaded = _load_reference(reference) if not fresh else None
        if loaded is not None:
            pixels, mask, item = loaded
            if mask is None:
                mask = torch.zeros((1, pixels.shape[1], pixels.shape[2]))
            previews = [item]
        else:
            pixels = images
            mask = None
            if restore_mask != "never":
                registered = _load_reference(image) if isinstance(image, str) else None
                if registered is not None:
                    mask = registered[1]
                if mask is None:
                    with _LOCK:
                        mask = _LAST_MASK.get(node_id)
                if mask is not None and restore_mask == "if_same_size" and mask.shape[1:] != images.shape[1:3]:
                    mask = None
            if mask is None:
                mask = torch.zeros((1, images.shape[1], images.shape[2]))
            else:
                mask = _restore_mask(mask, images.shape[1], images.shape[2])
            saved = nodes.PreviewImage().save_images(
                _rgba_preview(images, mask), filename_prefix="AIChatBridge/PB-",
                prompt=prompt, extra_pnginfo=extra_pnginfo)
            previews = saved["ui"]["images"]
            # Save first preview's token for native mask editing after queue.
            item = previews[0]
            reference = register_file(node_id, item)

        if torch.any(mask > 0):
            _remember(_LAST_MASK, node_id, mask.detach().cpu().clone())
        # Never pin upstream GPU image tensors in a long-lived node cache.
        _remember(_NODE_HISTORY, node_id, (images.detach().cpu().clone(), image, reference))
        if block and not bool(torch.any(mask > 0)):
            try:
                from comfy_execution.graph import ExecutionBlocker
            except ImportError:
                LOGGER.warning("[AI Chat] 当前 ComfyUI 版本不支持空遮罩阻塞；将正常输出。")
                outputs = (pixels, mask)
            else:
                outputs = (ExecutionBlocker(None), ExecutionBlocker(None))
        else:
            outputs = (pixels, mask)
        return {"ui": {"images": previews, "source_image": [image]}, "result": outputs}


NODE_CLASS_MAPPINGS = {"AIChatPreviewBridge": AIChatPreviewBridge}
NODE_DISPLAY_NAME_MAPPINGS = {"AIChatPreviewBridge": "桥接预览图像"}
