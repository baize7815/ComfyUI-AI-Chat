"""ComfyUI entry point for the AI Chat node pack."""

from __future__ import annotations

import importlib
import logging


LOGGER = logging.getLogger("AI_Chat")
WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _load_node_module(module_name: str) -> None:
    try:
        module = importlib.import_module(f".{module_name}", __name__)
    except Exception:
        LOGGER.exception("[AI Chat] 节点模块加载失败：%s", module_name)
        return
    NODE_CLASS_MAPPINGS.update(getattr(module, "NODE_CLASS_MAPPINGS", {}))
    NODE_DISPLAY_NAME_MAPPINGS.update(getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {}))


for _module_name in (
    "AI_Assistant",
    "kontextPreset",
    "NanoPreset",
    "text_replace_node",
    "expression_node",
    "googlenano",
    "image_loader_nodes",
    "crop_nodes",
    "tile_nodes",
    "preview_bridge_nodes",
):
    _load_node_module(_module_name)

try:
    from .api_routes import register_routes

    register_routes()
except Exception:
    LOGGER.exception("[AI Chat] 服务商配置接口注册失败；节点仍可加载。")

try:
    from .preview_bridge_routes import register_routes as register_preview_bridge_routes

    register_preview_bridge_routes()
except Exception:
    LOGGER.exception("[AI Chat] 桥接预览路由注册失败；其他节点仍可加载。")


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print(f"[AI Chat] 已加载 {len(NODE_CLASS_MAPPINGS)} 个节点。")
