"""Safe image loaders with filename and mask outputs for ComfyUI workflows."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import folder_paths  # type: ignore
except ImportError:  # Unit tests and static inspection outside ComfyUI.
    folder_paths = None

try:
    from .image_utils import (
        MAX_BATCH_PIXELS,
        MAX_IMAGE_PIXELS,
        pil_to_mask,
        pils_to_tensor_batch,
    )
    from .progress_utils import ProgressTracker
except ImportError:  # Direct import in unit tests.
    from image_utils import (
        MAX_BATCH_PIXELS,
        MAX_IMAGE_PIXELS,
        pil_to_mask,
        pils_to_tensor_batch,
    )
    from progress_utils import ProgressTracker


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
FILENAME_FORMATS = ["不含扩展名", "含扩展名", "相对路径"]
SORT_MODES = ["自然排序", "名称倒序", "修改时间升序", "修改时间降序"]
MAX_FOLDER_IMAGES = 256
MAX_DISCOVERED_IMAGES = 100_000
MAX_IMAGE_FILE_BYTES = 100 * 1024 * 1024


def _input_directory() -> Path:
    if folder_paths is None:
        return Path.cwd().resolve()
    return Path(folder_paths.get_input_directory()).resolve()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_supported_image(path: Path) -> bool:
    return path.suffix.casefold() in IMAGE_EXTENSIONS


def _safe_filename_text(path: Path, root: Path, mode: str) -> str:
    if mode == "不含扩展名":
        value = path.stem
    elif mode == "含扩展名":
        value = path.name
    elif mode == "相对路径":
        try:
            value = path.relative_to(root).as_posix()
        except ValueError:
            value = path.name
    else:
        raise ValueError(f"未知文件名格式：{mode}")
    return value.replace("\r", " ").replace("\n", " ")


def _decode_first_frame(path: Path) -> Image.Image:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RuntimeError(f"无法读取图片文件信息：{path.name}：{exc}") from exc
    if size > MAX_IMAGE_FILE_BYTES:
        raise ValueError(f"图片文件超过 100MB 限制：{path.name}")

    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"图片像素数超过限制：{path.name}（{opened.width}×{opened.height}）"
                )
            opened.seek(0)
            normalized = ImageOps.exif_transpose(opened)
            normalized.load()
            return normalized.copy()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(f"无法解码图片：{path.name}：{exc}") from exc


def _load_first_frame(path: Path) -> Image.Image:
    return _decode_first_frame(path).convert("RGB")


def _load_first_frame_with_mask(path: Path):
    decoded = _decode_first_frame(path)
    return decoded.convert("RGB"), pil_to_mask(decoded)


def _list_input_images() -> list[str]:
    if folder_paths is None:
        return []
    root = _input_directory()
    if not root.is_dir():
        return []
    images: list[str] = []
    for current_root, directories, filenames in os.walk(root, followlinks=False):
        directories.sort(key=str.casefold)
        for filename in sorted(filenames, key=str.casefold):
            path = Path(current_root) / filename
            if _is_supported_image(path):
                images.append(path.relative_to(root).as_posix())
            if len(images) >= MAX_DISCOVERED_IMAGES:
                return images
    return images


def _resolve_input_image(image: str) -> Path:
    if folder_paths is None:
        raise RuntimeError("当前不在 ComfyUI 环境中，无法解析 input 图片。")
    if not image or not folder_paths.exists_annotated_filepath(image):
        raise FileNotFoundError(f"找不到输入图片：{image}")
    path = Path(folder_paths.get_annotated_filepath(image)).resolve(strict=True)
    input_root = _input_directory()
    if not _is_inside(path, input_root):
        raise ValueError("单图加载仅允许读取 ComfyUI input 目录中的图片。")
    if not path.is_file() or not _is_supported_image(path):
        raise ValueError(f"不是支持的图片文件：{path.name}")
    try:
        if path.stat().st_size > MAX_IMAGE_FILE_BYTES:
            raise ValueError(f"图片文件超过 100MB 限制：{path.name}")
    except OSError as exc:
        raise RuntimeError(f"无法读取图片文件信息：{path.name}：{exc}") from exc
    return path


def _resolve_folder(folder: str, allow_external: bool) -> tuple[Path, Path]:
    raw = str(folder or "").strip()
    if not raw:
        raise ValueError("文件夹不能为空。")
    if len(raw) > 4096:
        raise ValueError("文件夹路径过长。")
    if not isinstance(allow_external, bool):
        raise ValueError("允许外部路径必须是布尔值。")

    input_root = _input_directory()
    expanded = Path(os.path.expandvars(raw)).expanduser()
    candidate = expanded if expanded.is_absolute() else input_root / expanded
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError(f"找不到文件夹：{raw}") from exc
    if not resolved.is_dir():
        raise NotADirectoryError(f"路径不是文件夹：{resolved}")
    if not allow_external and not _is_inside(resolved, input_root):
        raise ValueError("外部文件夹默认禁用；确认可信后请启用“允许外部路径”。")
    return resolved, input_root


def _natural_key(path: Path, root: Path):
    relative = path.relative_to(root).as_posix().casefold()
    return [
        (1, int(part)) if part.isdigit() else (0, part)
        for part in re.split(r"(\d+)", relative)
    ]


def _discover_images(
    folder: Path,
    include_subfolders: bool,
    allow_external: bool,
    input_root: Path,
) -> list[Path]:
    def iter_paths():
        if include_subfolders:
            for current_root, directories, filenames in os.walk(folder, followlinks=False):
                directories.sort(key=str.casefold)
                for filename in sorted(filenames, key=str.casefold):
                    yield Path(current_root) / filename
        else:
            yield from folder.iterdir()

    candidates: list[Path] = []
    for path in iter_paths():
        if not path.is_file() or not _is_supported_image(path):
            continue
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not allow_external and not _is_inside(resolved, input_root):
            raise ValueError(f"图片通过符号链接指向 input 目录之外：{path.name}")
        candidates.append(path)
        if len(candidates) > MAX_DISCOVERED_IMAGES:
            raise ValueError(f"文件夹图片超过 {MAX_DISCOVERED_IMAGES} 张，拒绝继续扫描。")
    return candidates


def _validate_folder_options(
    load_limit: int,
    start_index: int,
    include_subfolders: bool,
    sort_mode: str,
) -> None:
    if not isinstance(load_limit, int) or isinstance(load_limit, bool) or load_limit < 0:
        raise ValueError("加载上限必须是大于等于 0 的整数。")
    if load_limit > MAX_FOLDER_IMAGES:
        raise ValueError(f"加载上限不能超过 {MAX_FOLDER_IMAGES}。")
    if not isinstance(start_index, int) or isinstance(start_index, bool) or start_index < 0:
        raise ValueError("起始编号必须是大于等于 0 的整数。")
    if start_index > 1_000_000:
        raise ValueError("起始编号不能超过 1000000。")
    if not isinstance(include_subfolders, bool):
        raise ValueError("包含子文件夹必须是布尔值。")
    if sort_mode not in SORT_MODES:
        raise ValueError(f"未知排序方式：{sort_mode}")


def _sort_images(paths: list[Path], root: Path, mode: str) -> list[Path]:
    if mode == "自然排序":
        return sorted(paths, key=lambda path: _natural_key(path, root))
    if mode == "名称倒序":
        return sorted(paths, key=lambda path: _natural_key(path, root), reverse=True)
    if mode == "修改时间升序":
        return sorted(paths, key=lambda path: (path.stat().st_mtime_ns, _natural_key(path, root)))
    if mode == "修改时间降序":
        return sorted(
            paths,
            key=lambda path: (path.stat().st_mtime_ns, _natural_key(path, root)),
            reverse=True,
        )
    raise ValueError(f"未知排序方式：{mode}")


def _select_folder_images(
    folder: str,
    load_limit: int,
    start_index: int,
    include_subfolders: bool,
    allow_external: bool,
    sort_mode: str,
) -> tuple[Path, list[Path]]:
    _validate_folder_options(load_limit, start_index, include_subfolders, sort_mode)

    resolved, input_root = _resolve_folder(folder, allow_external)
    paths = _discover_images(resolved, include_subfolders, allow_external, input_root)
    paths = _sort_images(paths, resolved, sort_mode)
    if not paths:
        raise FileNotFoundError(f"文件夹中没有支持的图片：{resolved}")
    if start_index >= len(paths):
        raise IndexError(f"起始编号 {start_index} 超出图片数量 {len(paths)}。")

    remaining = paths[start_index:]
    selected = remaining[:load_limit] if load_limit > 0 else remaining
    if len(selected) > MAX_FOLDER_IMAGES:
        raise ValueError(
            f"单次最多加载 {MAX_FOLDER_IMAGES} 张图片；请设置加载上限或调整起始编号。"
        )
    return resolved, selected


class AIChatLoadImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": (
                    _list_input_images(),
                    {
                        "image_upload": True,
                        "allow_batch": False,
                        "tooltip": "从 ComfyUI input 目录选择或上传一张图片。",
                    },
                ),
                "文件名格式": (
                    FILENAME_FORMATS,
                    {"default": "不含扩展名", "tooltip": "控制 filename_text 的内容。"},
                ),
            }
        }

    # Keep the existing outputs in place so saved workflows retain their links.
    RETURN_TYPES = ("IMAGE", "STRING", "MASK")
    RETURN_NAMES = ("image", "filename_text", "mask")
    OUTPUT_TOOLTIPS = (
        "加载后的 RGB 图像。",
        "所选图片的文件名文本。",
        "由透明通道生成的遮罩；透明区域为白色，不透明区域为黑色。",
    )
    FUNCTION = "load_image"
    CATEGORY = "🫧 AI Chat/图像加载"
    DESCRIPTION = "从 ComfyUI input 目录上传或选择单张图片，并输出文件名和透明通道遮罩。"
    SEARCH_ALIASES = ["加载图片", "图片文件名", "Load Image"]

    def load_image(self, image, 文件名格式):
        if 文件名格式 not in FILENAME_FORMATS:
            raise ValueError(f"未知文件名格式：{文件名格式}")
        path = _resolve_input_image(image)
        loaded, mask = _load_first_frame_with_mask(path)
        filename = _safe_filename_text(path, _input_directory(), 文件名格式)
        return (pils_to_tensor_batch([loaded], max_images=1), filename, mask)

    @classmethod
    def VALIDATE_INPUTS(cls, image, 文件名格式):
        if 文件名格式 not in FILENAME_FORMATS:
            return f"未知文件名格式：{文件名格式}"
        try:
            _resolve_input_image(image)
        except (OSError, ValueError, RuntimeError, IndexError) as exc:
            return str(exc)
        return True

    @classmethod
    def IS_CHANGED(cls, image, 文件名格式):
        try:
            path = _resolve_input_image(image)
            digest = hashlib.sha256()
            digest.update(文件名格式.encode("utf-8"))
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except (OSError, ValueError, RuntimeError, IndexError):
            return float("nan")


class AIChatLoadImagesFromFolder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "文件夹": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "input 相对路径；外部绝对路径需启用下方开关",
                        "tooltip": "相对路径以 ComfyUI input 目录为基准。",
                    },
                ),
                "加载上限": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_FOLDER_IMAGES,
                        "tooltip": "0 表示加载起始编号之后的全部图片，硬上限 256 张。",
                    },
                ),
                "起始编号": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1_000_000,
                        "tooltip": "从排序结果的第几个文件开始，编号从 0 计算。",
                    },
                ),
                "包含子文件夹": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "递归扫描子目录，不跟随目录符号链接。"},
                ),
                "允许外部路径": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "允许读取 ComfyUI input 目录之外的可信文件夹。",
                    },
                ),
                "排序方式": (SORT_MODES, {"default": "自然排序"}),
                "文件名格式": (FILENAME_FORMATS, {"default": "不含扩展名"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "filename_text")
    OUTPUT_TOOLTIPS = (
        "按顺序组成的 RGB 图像批次；异尺寸图片会居中补边。",
        "与图像批次同顺序、用换行分隔的文件名。",
    )
    FUNCTION = "load_images"
    CATEGORY = "🫧 AI Chat/图像加载"
    DESCRIPTION = "按稳定顺序从文件夹加载图片批次；多个文件名按相同顺序用换行连接。"
    SEARCH_ALIASES = ["加载图片文件夹", "批量加载图片", "Load Images From Folder"]

    def load_images(
        self,
        文件夹,
        加载上限,
        起始编号,
        包含子文件夹,
        允许外部路径,
        排序方式,
        文件名格式,
    ):
        if 文件名格式 not in FILENAME_FORMATS:
            raise ValueError(f"未知文件名格式：{文件名格式}")
        root, paths = _select_folder_images(
            文件夹,
            加载上限,
            起始编号,
            包含子文件夹,
            允许外部路径,
            排序方式,
        )
        progress = ProgressTracker(len(paths))
        images = []
        filenames = []
        max_width = 0
        max_height = 0
        for path in paths:
            image = _load_first_frame(path)
            max_width = max(max_width, image.width)
            max_height = max(max_height, image.height)
            if (len(images) + 1) * max_width * max_height > MAX_BATCH_PIXELS:
                raise ValueError(
                    "图片批次补边后超过总像素限制；请降低加载上限或拆分文件夹。"
                )
            images.append(image)
            filenames.append(_safe_filename_text(path, root, 文件名格式))
            progress.advance()

        batch = pils_to_tensor_batch(
            images,
            max_images=MAX_FOLDER_IMAGES,
            max_batch_pixels=MAX_BATCH_PIXELS,
        )
        return (batch, "\n".join(filenames))

    @classmethod
    def IS_CHANGED(
        cls,
        文件夹,
        加载上限,
        起始编号,
        包含子文件夹,
        允许外部路径,
        排序方式,
        文件名格式,
    ):
        try:
            root, paths = _select_folder_images(
                文件夹,
                加载上限,
                起始编号,
                包含子文件夹,
                允许外部路径,
                排序方式,
            )
            digest = hashlib.sha256()
            digest.update(str(root).encode("utf-8"))
            digest.update(文件名格式.encode("utf-8"))
            for path in paths:
                stat = path.stat()
                digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
            return digest.hexdigest()
        except (OSError, ValueError, RuntimeError, IndexError):
            return float("nan")


NODE_CLASS_MAPPINGS = {
    "AIChatLoadImage": AIChatLoadImage,
    "AIChatLoadImagesFromFolder": AIChatLoadImagesFromFolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AIChatLoadImage": "加载图片",
    "AIChatLoadImagesFromFolder": "加载图片(文件夹)",
}
