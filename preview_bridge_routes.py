"""HTTP registry for AI Chat's native ComfyUI mask editor preview bridge."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

try:
    from .preview_bridge_nodes import lookup_item, register_file
except ImportError:
    from preview_bridge_nodes import lookup_item, register_file

_REGISTERED = False


def register_routes():
    global _REGISTERED
    if _REGISTERED:
        return True
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return False

    routes = PromptServer.instance.routes

    @routes.post("/ai_chat/preview_bridge/register")
    async def register(request):
        origin = request.headers.get("Origin", "").strip()
        if origin and urlsplit(origin).netloc.casefold() != request.host.casefold():
            return web.json_response({"error": "Cross-site registrations are not allowed."}, status=403)
        if request.content_length and request.content_length > 2048:
            return web.json_response({"error": "Request too large."}, status=413)
        try:
            payload = await request.content.read(2049)
            if len(payload) > 2048:
                return web.json_response({"error": "Request too large."}, status=413)
            body = json.loads(payload.decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object.")
            reference = register_file(str(body.get("node_id", "")), body.get("image"))
        except (ValueError, TypeError, UnicodeDecodeError, OSError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({"id": reference})

    @routes.get("/ai_chat/preview_bridge/lookup")
    async def lookup(request):
        reference = request.query.get("id", "")
        descriptor = lookup_item(reference)
        if descriptor is None:
            return web.json_response({"error": "Preview reference not found."}, status=404)
        return web.json_response(descriptor)

    _REGISTERED = True
    return True
