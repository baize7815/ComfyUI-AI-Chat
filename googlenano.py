from __future__ import annotations

import base64
import io
import json
from typing import Any

import requests
from PIL import Image

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from .image_utils import (
        MAX_IMAGE_COUNT,
        MAX_IMAGE_PIXELS,
        pil_to_base64_data_url,
        pils_to_tensor_batch,
        tensor_to_pils,
    )
    from .provider_config import model_choices, profile_names, redact_secret, resolve_provider_and_model
    from .progress_utils import ProgressTracker
except ImportError:  # Direct import in unit tests.
    from image_utils import (
        MAX_IMAGE_COUNT,
        MAX_IMAGE_PIXELS,
        pil_to_base64_data_url,
        pils_to_tensor_batch,
        tensor_to_pils,
    )
    from provider_config import model_choices, profile_names, redact_secret, resolve_provider_and_model
    from progress_utils import ProgressTracker


MAX_DECODED_IMAGE_BYTES = 50 * 1024 * 1024
MAX_ENCODED_IMAGE_CHARS = (MAX_DECODED_IMAGE_BYTES * 4 // 3) + 8
MAX_IMAGE_RESPONSE_BYTES = 100 * 1024 * 1024
API_MODES = [
    "OpenRouter Images (/images)",
    "OpenAI Images (/images/generations)",
    "Chat Completions",
]


def _decode_base64_image(value: str) -> Image.Image:
    encoded = value.split("base64,", 1)[1] if "base64," in value else value
    if len(encoded) > MAX_ENCODED_IMAGE_CHARS:
        raise ValueError("接口返回的单张图片超过 50MB 限制。")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("接口返回了无效的 Base64 图片。") from exc
    if len(raw) > MAX_DECODED_IMAGE_BYTES:
        raise ValueError("接口返回的单张图片超过 50MB 限制。")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError(f"接口返回的图像像素数超过限制：{image.width}×{image.height}。")
        image.load()
        return image.convert("RGB")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("接口返回的数据不是有效图像。") from exc


def _response_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        dumped = response.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _decode_generated_images(response: Any, api_mode: str) -> list[Image.Image]:
    body = _response_dict(response)
    encoded_images: list[str] = []

    if api_mode != "Chat Completions":
        for item in body.get("data", []) if isinstance(body.get("data"), list) else []:
            if not isinstance(item, dict):
                continue
            value = item.get("b64_json") or item.get("url")
            if isinstance(value, str) and ("base64," in value or not value.startswith(("http://", "https://"))):
                encoded_images.append(value)
    else:
        choices = body.get("choices", [])
        message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        images = message.get("images", []) if isinstance(message, dict) else []
        for item in images if isinstance(images, list) else []:
            if not isinstance(item, dict):
                continue
            image_url = item.get("image_url", {})
            value = image_url.get("url") if isinstance(image_url, dict) else None
            if isinstance(value, str) and (
                "base64," in value or not value.startswith(("http://", "https://"))
            ):
                encoded_images.append(value)

    if not encoded_images:
        raise RuntimeError(f"{api_mode} 响应中没有 Base64 图片数据。")
    return [_decode_base64_image(value) for value in encoded_images[:MAX_IMAGE_COUNT]]


class GoogleNanoNode:
    """通过可配置的 OpenAI 兼容服务生成或编辑图像。"""

    CATEGORY = "AI Chat/图像生成"
    FUNCTION = "generate"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("图像", "状态")
    OUTPUT_NODE = False
    DESCRIPTION = "通过 Images API 或 Chat Completions 调用可配置的图像生成服务。"
    SEARCH_ALIASES = ["Nano Banana", "Google Nano", "图片生成"]

    @classmethod
    def INPUT_TYPES(cls):
        profiles = profile_names()
        return {
            "required": {
                "服务商配置": (profiles, {"default": profiles[0]}),
                "选择模型": (model_choices(profiles[0]),),
                "手动模型": (
                    "STRING",
                    {"default": "", "placeholder": "仅当模型选择“手动填写”时生效"},
                ),
                "API模式": (API_MODES, {"default": "OpenRouter Images (/images)"}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, 服务商配置, 选择模型):
        return True

    @staticmethod
    def _collect_references(*inputs) -> list[Image.Image]:
        references: list[Image.Image] = []
        for image in inputs:
            if image is not None:
                references.extend(tensor_to_pils(image, max_images=MAX_IMAGE_COUNT))
            if len(references) > MAX_IMAGE_COUNT:
                raise ValueError(f"单次最多允许 {MAX_IMAGE_COUNT} 张参考图。")
        return references

    @staticmethod
    def _generate_images_api(client, model: str, prompt: str, references: list[Image.Image]):
        request = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
        }
        if references:
            request["extra_body"] = {
                "input_references": [
                    {"type": "image_url", "image_url": {"url": pil_to_base64_data_url(image)}}
                    for image in references
                ]
            }
        return client.images.generate(
            **request,
        )

    @staticmethod
    def _generate_openrouter_images(provider, model: str, prompt: str, references: list[Image.Image]):
        url = provider["base_url"].rstrip("/") + "/images"
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
        }
        if references:
            payload["input_references"] = [
                {"type": "image_url", "image_url": {"url": pil_to_base64_data_url(image)}}
                for image in references
            ]
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(10, 180),
            stream=True,
        )
        try:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_IMAGE_RESPONSE_BYTES:
                        raise RuntimeError("图片接口响应超过 100MB 限制。")
                except ValueError:
                    pass
            buffer = io.BytesIO()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buffer.write(chunk)
                if buffer.tell() > MAX_IMAGE_RESPONSE_BYTES:
                    raise RuntimeError("图片接口响应超过 100MB 限制。")
            response_text = buffer.getvalue().decode(response.encoding or "utf-8", errors="replace")
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code}：{response_text[:20_000]}")
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError("OpenRouter Images API 返回了无效 JSON。") from exc
        finally:
            response.close()

    @staticmethod
    def _generate_chat(client, model: str, prompt: str, references: list[Image.Image]):
        content = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": pil_to_base64_data_url(image)}}
            for image in references
        )
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            extra_body={"modalities": ["image", "text"]},
        )

    def generate(
        self,
        服务商配置,
        选择模型,
        手动模型,
        API模式,
        prompt,
        image1=None,
        image2=None,
        image3=None,
        image4=None,
    ):
        prompt_text = str(prompt).strip()
        if not prompt_text:
            raise ValueError("提示词不能为空。")
        references = self._collect_references(image1, image2, image3, image4)
        provider, model = resolve_provider_and_model(服务商配置, 选择模型, 手动模型)
        progress = ProgressTracker(3)

        try:
            progress.advance()
            if API模式 == "OpenRouter Images (/images)":
                response = self._generate_openrouter_images(provider, model, prompt_text, references)
            elif API模式 == "OpenAI Images (/images/generations)":
                if OpenAI is None:
                    raise RuntimeError("未安装 openai 依赖，请重新安装插件依赖。")
                client = OpenAI(
                    base_url=provider["base_url"],
                    api_key=provider["api_key"],
                    timeout=180.0,
                    max_retries=0,
                )
                try:
                    response = self._generate_images_api(client, model, prompt_text, references)
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass
            elif API模式 == "Chat Completions":
                if OpenAI is None:
                    raise RuntimeError("未安装 openai 依赖，请重新安装插件依赖。")
                client = OpenAI(
                    base_url=provider["base_url"],
                    api_key=provider["api_key"],
                    timeout=180.0,
                    max_retries=0,
                )
                try:
                    response = self._generate_chat(client, model, prompt_text, references)
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass
            else:
                raise ValueError(f"未知 API 模式：{API模式}")
            progress.advance()
            images = _decode_generated_images(response, API模式)
        except Exception as exc:
            safe_message = redact_secret(str(exc), provider.get("api_key"))
            raise RuntimeError(
                f"图片生成失败：{safe_message}\n请检查服务商、模型和 API 模式是否匹配。"
            ) from None

        progress.advance()
        return (pils_to_tensor_batch(images), f"已通过 {model} 生成 {len(images)} 张图片。")


NODE_CLASS_MAPPINGS = {"GoogleNanoNode": GoogleNanoNode}
NODE_DISPLAY_NAME_MAPPINGS = {"GoogleNanoNode": "AI Chat 通用图片生成"}
