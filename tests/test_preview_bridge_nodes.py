"""Preview bridge round-trip checks with ComfyUI service stubs."""

import asyncio
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import preview_bridge_nodes as bridge
import preview_bridge_routes as bridge_routes


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.roots = {}
        for kind in ("input", "output", "temp"):
            self.roots[kind] = root / kind
            self.roots[kind].mkdir()
        folder_paths = SimpleNamespace(
            get_input_directory=lambda: str(self.roots["input"]),
            get_output_directory=lambda: str(self.roots["output"]),
            get_temp_directory=lambda: str(self.roots["temp"]),
        )
        self.folders = patch.dict(sys.modules, {"folder_paths": folder_paths})
        self.folders.start()
        self.addCleanup(self.folders.stop)

        class PreviewImage:
            def save_images(preview, imgs, filename_prefix, prompt=None, extra_pnginfo=None):
                folder = self.roots["temp"] / "AIChatBridge"
                folder.mkdir(parents=True, exist_ok=True)
                items = []
                for frame in imgs:
                    filename = f"preview-{len(list(folder.iterdir()))}.png"
                    pixels = (frame.detach().cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                    Image.fromarray(pixels).save(folder / filename)
                    items.append({"filename": filename, "subfolder": "AIChatBridge", "type": "temp"})
                return {"ui": {"images": items}}
        self.fake_nodes = patch.dict(sys.modules, {"nodes": SimpleNamespace(PreviewImage=PreviewImage)})
        self.fake_nodes.start()
        self.addCleanup(self.fake_nodes.stop)
        bridge._FILE_REFERENCES.clear()
        bridge._NODE_HISTORY.clear()
        bridge._LAST_MASK.clear()

    def test_image_preview_initial_and_mask_editor_round_trip(self):
        images = torch.zeros((1, 9, 13, 3), dtype=torch.float32)
        images[..., 0] = 1
        node = bridge.AIChatPreviewBridge()
        first = node.bridge(images, "$aichat-55-0", unique_id="55")
        self.assertEqual(first["result"][0].shape, (1, 9, 13, 3))
        self.assertEqual(first["result"][1].shape, (1, 9, 13))
        self.assertEqual(first["result"][1].sum().item(), 0)
        self.assertEqual(first["ui"]["images"][0]["type"], "temp")
        image_path = self.roots["input"] / "clipspace"
        image_path.mkdir()
        alpha_image = np.full((9, 13, 4), [255, 0, 0, 255], dtype=np.uint8)
        alpha_image[2:5, 6:11, 3] = 0
        Image.fromarray(alpha_image, "RGBA").save(image_path / "edited.png")
        token = bridge.register_file("55", {"filename": "edited.png", "subfolder": "clipspace", "type": "input"})
        self.assertTrue(token.startswith("$aichat-55-"))
        self.assertEqual(bridge.lookup_item(token)["filename"], "edited.png")

        second = node.bridge(images, token, unique_id="55")
        edited, mask = second["result"]
        self.assertEqual(tuple(edited.shape), (1, 9, 13, 3))
        self.assertEqual(tuple(mask.shape), (1, 9, 13))
        self.assertEqual(mask.sum().item(), 15.0)
        self.assertEqual(mask[0, 2, 6].item(), 1.0)
        self.assertEqual(mask[0, 1, 6].item(), 0.0)

    def test_mask_recovery_after_new_upstream_image(self):
        node = bridge.AIChatPreviewBridge()
        initial = torch.zeros((1, 8, 8, 3))
        node.bridge(initial, "$aichat-6-0", unique_id="6")
        masked = self.roots["input"] / "mask.png"
        pixels = np.full((8, 8, 4), 255, dtype=np.uint8)
        pixels[1:4, 2:7, 3] = 0
        Image.fromarray(pixels, "RGBA").save(masked)
        token = bridge.register_file("6", {"filename": "mask.png", "subfolder": "", "type": "input"})
        node.bridge(initial, token, unique_id="6")
        changed = torch.ones((1, 16, 16, 3))
        restored = node.bridge(changed, token, unique_id="6", restore_mask="always")
        self.assertEqual(restored["result"][1].shape, (1, 16, 16))
        self.assertGreater(restored["result"][1].sum().item(), 0)
        self.assertTrue(torch.equal(restored["result"][0], changed))
        no_restore = node.bridge(torch.zeros((1, 16, 16, 3)), token,
                                 unique_id="6", restore_mask="if_same_size")
        self.assertEqual(no_restore["result"][1].sum().item(), 0)

    def test_registration_rejects_paths_outside_comfyui(self):
        (self.roots["input"] / "ok.png").write_bytes(b"ok")
        self.assertEqual(bridge.resolve_path("ok.png", "", "input"),
                         self.roots["input"] / "ok.png")
        for filename, subfolder, kind in (
            ("../outside.png", "", "input"),
            ("ok.png", "../../", "input"),
            ("ok.png", "../output", "input"),
            ("C:/outside.png", "", "input"),
            ("ok.png", "", "unknown"),
        ):
            with self.subTest(filename=filename, subfolder=subfolder, kind=kind):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    bridge.resolve_path(filename, subfolder, kind)
        outside = pathlib.Path(self.tmp.name) / "outside.png"
        outside.write_bytes(b"bad")
        try:
            (self.roots["input"] / "escaped.png").symlink_to(outside)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            bridge.resolve_path("escaped.png", "", "input")

    def test_recovery_falls_back_when_file_was_deleted(self):
        images = torch.zeros((1, 8, 8, 3))
        node = bridge.AIChatPreviewBridge()
        first = node.bridge(images, "$aichat-77-0", unique_id="77")
        item = first["ui"]["images"][0]
        (self.roots["temp"] / item["subfolder"] / item["filename"]).unlink()
        second = node.bridge(images, "$aichat-77-0", unique_id="77")
        self.assertEqual(second["result"][1].sum().item(), 0)
        self.assertEqual(len(second["ui"]["images"]), 1)

    def test_http_registry_and_traversal_rejection(self):
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer

        example = self.roots["input"] / "photo.png"
        Image.new("RGB", (4, 3), (255, 0, 0)).save(example)
        routes = web.RouteTableDef()
        fake_server = SimpleNamespace(PromptServer=SimpleNamespace(
            instance=SimpleNamespace(routes=routes)))
        previous = bridge_routes._REGISTERED
        bridge_routes._REGISTERED = False
        self.addCleanup(setattr, bridge_routes, "_REGISTERED", previous)
        with patch.dict(sys.modules, {"server": fake_server}):
            self.assertTrue(bridge_routes.register_routes())
        app = web.Application()
        app.add_routes(routes)

        async def request_check():
            async with TestClient(TestServer(app)) as client:
                content = {"node_id": "987", "image": {
                    "filename": "photo.png", "subfolder": "", "type": "input"}}
                response = await client.post("/ai_chat/preview_bridge/register", json=content)
                self.assertEqual(response.status, 200)
                reference = (await response.json())["id"]
                lookup = await client.get("/ai_chat/preview_bridge/lookup", params={"id": reference})
                self.assertEqual((await lookup.json())["filename"], "photo.png")

                content["image"]["subfolder"] = "../"
                invalid = await client.post("/ai_chat/preview_bridge/register", json=content)
                self.assertEqual(invalid.status, 400)
                too_large = await client.post("/ai_chat/preview_bridge/register",
                                              data="A" * 2050)
                self.assertEqual(too_large.status, 413)

        asyncio.run(request_check())


if __name__ == "__main__":
    unittest.main()
