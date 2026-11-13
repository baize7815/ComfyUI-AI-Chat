"""ComfyUI HTTP routes used by the provider profile manager."""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlsplit

try:
    from .provider_config import (
        PROVIDER_STORE,
        ProviderConfigError,
        ProviderNotFoundError,
        ProviderValidationError,
    )
except ImportError:
    from provider_config import (
        PROVIDER_STORE,
        ProviderConfigError,
        ProviderNotFoundError,
        ProviderValidationError,
    )


LOGGER = logging.getLogger("AI_Chat")
MAX_REQUEST_BYTES = 32 * 1024
_ROUTES_REGISTERED = False


async def _read_json(request):
    origin = request.headers.get("Origin", "").strip()
    if origin and urlsplit(origin).netloc.casefold() != request.host.casefold():
        raise ProviderValidationError("已拒绝跨站配置请求。")
    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        raise ProviderValidationError("请求内容过大。")
    try:
        chunks = []
        total = 0
        async for chunk in request.content.iter_chunked(8192):
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise ProviderValidationError("请求内容过大。")
            chunks.append(chunk)
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except ProviderValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderValidationError("请求必须是有效 JSON。") from exc
    if not isinstance(payload, dict):
        raise ProviderValidationError("请求 JSON 必须是对象。")
    return payload


def register_routes() -> bool:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return True

    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return False

    routes = PromptServer.instance.routes

    @routes.get("/ai_chat/profiles")
    async def list_profiles(_request):
        try:
            return web.json_response({"profiles": PROVIDER_STORE.list_profiles()})
        except ProviderConfigError as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/ai_chat/profiles")
    async def save_profile(request):
        try:
            payload = await _read_json(request)
            profile = await asyncio.to_thread(PROVIDER_STORE.upsert_profile, payload)
            return web.json_response({"profile": profile})
        except ProviderValidationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except ProviderConfigError as exc:
            LOGGER.exception("Failed to save AI Chat provider profile")
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/ai_chat/profiles/delete")
    async def delete_profile(request):
        try:
            payload = await _read_json(request)
            name = str(payload.get("name", ""))
            await asyncio.to_thread(PROVIDER_STORE.delete_profile, name)
            return web.json_response({"deleted": name})
        except ProviderNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except ProviderValidationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except ProviderConfigError as exc:
            LOGGER.exception("Failed to delete AI Chat provider profile")
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/ai_chat/models/refresh")
    async def refresh_models(request):
        try:
            payload = await _read_json(request)
            name = str(payload.get("name", ""))
            models = await asyncio.to_thread(PROVIDER_STORE.refresh_models, name)
            return web.json_response({"models": models})
        except ProviderNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except ProviderValidationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except ProviderConfigError as exc:
            return web.json_response({"error": str(exc)}, status=502)

    @routes.post("/ai_chat/profiles/clear-key")
    async def clear_profile_key(request):
        try:
            payload = await _read_json(request)
            profile = await asyncio.to_thread(PROVIDER_STORE.clear_api_key, str(payload.get("name", "")))
            return web.json_response({"profile": profile})
        except ProviderNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except ProviderValidationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except ProviderConfigError as exc:
            LOGGER.exception("Failed to clear AI Chat provider key")
            return web.json_response({"error": str(exc)}, status=500)

    _ROUTES_REGISTERED = True
    return True
