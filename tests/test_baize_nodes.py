"""Tests for the three imported Baize nodes; no running ComfyUI required."""

import base64
import io
import json
import math
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

from baize_sampler_nodes import BaizeAITKQwen21Sigmas, BaizeViggleTurboSigmas
from baize_pintu_nodes import BaizePintu, _resolve_ref_path


class BaizeSamplerTests(unittest.TestCase):
    def test_aitk_qwen_schedule_matches_original(self):
        latent = {"samples": torch.zeros((1, 64, 32, 40))}
        sigmas, info = BaizeAITKQwen21Sigmas().build(latent, 30)
        self.assertEqual(tuple(sigmas.shape), (31,))
        self.assertAlmostEqual(float(sigmas[0]), 1.0, places=6)
        self.assertAlmostEqual(float(sigmas[-2]), 0.02, places=6)
        self.assertEqual(float(sigmas[-1]), 0.0)
        self.assertTrue(torch.all(sigmas[:-1] >= sigmas[1:]))
        self.assertIn("steps=30", info)
        mu = (32 * 40 - 256) * (0.9 - 0.5) / (8192 - 256) + 0.5
        raw = np.linspace(1.0, 1 / 30, 30, dtype=np.float32)
        shifted = math.exp(mu) / (math.exp(mu) + (1 / raw - 1))
        factor = (1 - shifted[-1]) / 0.98
        expected = np.concatenate((1 - (1 - shifted) / factor, [0])).astype(np.float32)
        self.assertTrue(np.allclose(sigmas.numpy(), expected, atol=1e-7, rtol=0))

    def test_aitk_rejects_non_64_channel_latent(self):
        with self.assertRaisesRegex(ValueError, "64"):
            BaizeAITKQwen21Sigmas().build(
                {"samples": torch.zeros((1, 16, 32, 32))}, 30)

    def test_viggle_student_nodes_and_terminal_zero(self):
        latent = {"samples": torch.zeros((1, 64, 32, 40))}
        sigma, = BaizeViggleTurboSigmas().get_sigmas(
            latent, "1.0, 0.9375, 0.875, 0.75, 0.5, 0.25")
        self.assertEqual(tuple(sigma.shape), (7,))
        self.assertEqual(float(sigma[-1]), 0.0)
        self.assertEqual(float(sigma[0]), 1.0)
        mu = 0.5 + 0.4 * (32 * 40 - 256) / (8192 - 256)
        student = torch.tensor([1.0, 0.9375, 0.875, 0.75, 0.5, 0.25], dtype=torch.float64)
        expected = math.exp(mu) / (math.exp(mu) + (1 / student - 1))
        self.assertTrue(torch.allclose(sigma[:-1], expected.float(), atol=1e-7, rtol=0))

    def test_viggle_rejects_invalid_student_nodes(self):
        for nodes in ("", "NaN", "1,0", "1, 1.1", "abc", "1,-2"):
            with self.subTest(nodes=nodes):
                with self.assertRaisesRegex(ValueError, "nodes"):
                    BaizeViggleTurboSigmas().get_sigmas(
                        {"samples": torch.zeros((1, 64, 24, 24))}, nodes)


class BaizePintuTests(unittest.TestCase):
    def background(self):
        return torch.zeros((1, 24, 32, 3), dtype=torch.float32)

    def product(self):
        product = torch.zeros((1, 8, 8, 4), dtype=torch.float32)
        product[..., 1] = 1
        product[..., 3] = 1
        return product

    def compose(self, **options):
        fields = {
            "background": self.background(),
            "product": self.product(),
            "outline_size": 0,
            "outline_opacity": 50,
            "transform_json": json.dumps({"x": 0.5, "y": 0.5,
                                           "scale": 0.5, "rotation": 0}),
            "locked": False,
            "background_ref": "",
            "product_ref": "",
            "paint_layer": "",
        }
        fields.update(options)
        return BaizePintu().compose(**fields)

    def test_pintu_alpha_mask_and_background_size(self):
        result, mask = self.compose()
        self.assertEqual(tuple(result.shape), (1, 24, 32, 3))
        self.assertEqual(tuple(mask.shape), (1, 24, 32))
        self.assertEqual(float(mask.sum()), 256)
        self.assertTrue(torch.equal(result[0, 4:20, 8:24, 1],
                                    torch.ones((16, 16))))
        self.assertTrue(torch.equal(result[0, 0, 0],
                                    torch.zeros((3,))))

    def test_outline_only_changes_output_not_mask(self):
        image, mask = self.compose()
        outlined, outlined_mask = self.compose(outline_size=3, outline_opacity=100)
        self.assertTrue(torch.equal(mask, outlined_mask))
        self.assertFalse(torch.equal(image, outlined))

    def test_paint_layer_does_not_modify_product_mask(self):
        src = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
        src.putpixel((1, 1), (255, 255, 255, 255))
        encoded = io.BytesIO()
        src.save(encoded, format="PNG")
        layer = "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")
        baseline, mask = self.compose()
        with_paint, paint_mask = self.compose(paint_layer=layer, outline_opacity=100)
        self.assertTrue(torch.equal(mask, paint_mask))
        self.assertFalse(torch.equal(baseline, with_paint))
        self.assertTrue(torch.all(with_paint[0, 1, 1] == 1))

    def test_path_references_cannot_escape_input_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            folder = base / "input"
            folder.mkdir()
            path = folder / "product.png"
            Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(path)
            stub = SimpleNamespace(
                get_input_directory=lambda: str(folder),
                get_output_directory=lambda: str(base / "output"),
                get_temp_directory=lambda: str(base / "temp"))
            with patch.dict(sys.modules, {"folder_paths": stub}):
                self.assertEqual(_resolve_ref_path(
                    json.dumps({"filename": "product.png", "type": "input"})), path)
                with self.assertRaisesRegex(ValueError, "路径"):
                    _resolve_ref_path(json.dumps({
                        "filename": "../outside.png", "type": "input"}))


if __name__ == "__main__":
    unittest.main()
