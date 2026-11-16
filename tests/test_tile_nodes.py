"""Regression tests for AI Chat grid split / merge and inline previews."""

import copy
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tile_nodes import AIChatTileSplit, AIChatTileMerge


def split(image, rows=3, cols=3, expand=6, align="8", mode="关闭"):
    return AIChatTileSplit().split(image, rows, cols, expand, align, mode)["result"]


class TilesTest(unittest.TestCase):
    def test_odd_size_full_coverage_and_roundtrip(self):
        torch.manual_seed(6)
        source = torch.rand((1, 37, 43, 3), dtype=torch.float32)
        for expand, feather in ((0, 0), (0, 12), (7, 0), (7, 6), (7, 60)):
            with self.subTest(expand=expand, feather=feather):
                batch, masks, meta, total, preview = split(source, 3, 3, expand)
                self.assertEqual(total, 9)
                self.assertEqual(tuple(preview.shape), tuple(source.shape))
                self.assertEqual(batch.shape[0], 9)
                self.assertEqual(tuple(masks.shape), tuple(batch.shape[:3]))
                self.assertEqual(batch.shape[1] % 8, 0)
                self.assertEqual(batch.shape[2] % 8, 0)
                self.assertEqual(sum(item["base_box"][2] * item["base_box"][3]
                                     for item in meta["tiles"]), 37 * 43)
                output = AIChatTileMerge().merge(source, batch, meta, feather)[0]
                self.assertEqual(tuple(output.shape), tuple(source.shape))
                self.assertTrue(torch.allclose(output, source, atol=2e-6, rtol=0))

    def test_real_source_and_virtual_pad_are_separate(self):
        source = torch.arange(13 * 17 * 3, dtype=torch.float32).reshape(1, 13, 17, 3) / 700
        batch, masks, meta, _, _ = split(source, 3, 3, 2, "8")
        self.assertEqual(meta["original_size"], [17, 13])
        self.assertEqual(batch.shape[1] % 8, 0)
        self.assertEqual(batch.shape[2] % 8, 0)
        for i, tile in enumerate(meta["tiles"]):
            x, y, w, h = tile["crop_box"]
            self.assertTrue(torch.equal(batch[i, :h, :w], source[0, y:y+h, x:x+w]))
            self.assertTrue(torch.all(masks[i, :h, :w] == 1))
            self.assertTrue(torch.all(masks[i, h:, :] == 0))
            self.assertTrue(torch.all(masks[i, :, w:] == 0))
        restored = AIChatTileMerge().merge(source, batch, meta, 4)[0]
        self.assertTrue(torch.allclose(restored, source, atol=2e-6, rtol=0))

    def test_rescaled_edited_tiles_restore_original_dimensions(self):
        source = torch.zeros((1, 39, 51, 3))
        batch, _, data, total, _ = split(source, 3, 3, 5)
        # The model may output a completely different, non-proportional size.
        edited = torch.ones((total, 61, 37, 3), dtype=torch.float32)
        result = AIChatTileMerge().merge(source, edited, data, 12)[0]
        self.assertEqual(tuple(result.shape), (1, 39, 51, 3))
        self.assertTrue(torch.allclose(result, torch.ones_like(result), atol=1e-6))

    def test_3x3_realistic_odd_resolution(self):
        source = torch.zeros((1, 1125, 2001, 3))
        batch, _, meta, total, _ = split(source, 3, 3, 64, "8")
        self.assertEqual(total, 9)
        self.assertEqual([tile["base_box"][2] for tile in meta["tiles"][:3]],
                         [667, 667, 667])
        self.assertEqual([tile["base_box"][3] for tile in meta["tiles"][::3]],
                         [375, 375, 375])
        self.assertEqual(batch.shape[1] % 8, 0)
        self.assertEqual(batch.shape[2] % 8, 0)
        self.assertTrue(any(t["boundary_pad"][0] > 0 for t in meta["tiles"]))
        restored = AIChatTileMerge().merge(source, batch, meta, 32)[0]
        self.assertEqual(tuple(restored.shape), (1, 1125, 2001, 3))
        self.assertEqual(float(restored.abs().max()), 0.0)

    def test_alpha_preserved_and_no_feather_hard_assignment(self):
        source = torch.zeros((1, 21, 23, 4))
        source[..., 3] = 0.75
        batch, _, meta, total, _ = split(source, 2, 2, 5)
        edited = torch.stack([torch.full_like(batch[0], 0.1 * (i + 1))
                              for i in range(total)])
        restored = AIChatTileMerge().merge(source, edited, meta, 0)[0]
        self.assertTrue(torch.allclose(restored[..., 3], source[..., 3]))
        for i, tile in enumerate(meta["tiles"]):
            x, y, w, h = tile["base_box"]
            expected = torch.full_like(restored[0, y:y+h, x:x+w, :3], 0.1 * (i+1))
            self.assertTrue(torch.allclose(restored[0, y:y+h, x:x+w, :3],
                                            expected, atol=1e-6))

    def test_in_node_preview_three_modes(self):
        source = torch.zeros((1, 35, 49, 3))
        seen = []

        class Preview:
            def save_images(self, images, prefix, **kwargs):
                seen.append((images.clone(), prefix))
                return {"ui": {"images": [{"filename": "preview.png", "type": "temp"}]}}

        with mock.patch.dict(sys.modules, {"nodes": SimpleNamespace(PreviewImage=Preview)}):
            displayed = AIChatTileSplit().split(source, 3, 3, 5, "8", "网格与外扩")
            self.assertEqual(len(displayed["ui"]["images"]), 1)
            self.assertEqual(tuple(seen[0][0].shape), tuple(source.shape))
            self.assertEqual(len(displayed["result"][2]["tiles"]), 9)
            self.assertFalse(torch.equal(seen[0][0], source))
            grid = AIChatTileSplit().split(source, 3, 3, 5, "8", "仅基础网格")
            self.assertFalse(torch.equal(grid["result"][4], displayed["result"][4]))
            closed = AIChatTileSplit().split(source, 3, 3, 5, "8", "关闭")
            self.assertNotIn("ui", closed)
        self.assertEqual(len(seen), 2)

    def test_bad_counts_coordinates_and_inputs_rejected(self):
        source = torch.zeros((1, 19, 31, 3))
        batch, _, data, _, _ = split(source)
        merger = AIChatTileMerge()
        with self.assertRaisesRegex(ValueError, "数量"):
            merger.merge(source, batch[:-1], data, 8)
        with self.assertRaisesRegex(ValueError, "尺寸"):
            merger.merge(torch.zeros((1, 18, 31, 3)), batch, data, 8)
        broken = copy.deepcopy(data)
        broken["tiles"][0]["crop_box"][0] = -5
        with self.assertRaisesRegex(ValueError, "位置"):
            merger.merge(source, batch, broken, 8)
        with self.assertRaisesRegex(ValueError, "不能超过"):
            split(source, rows=20)
        with self.assertRaisesRegex(ValueError, "只能选择"):
            split(source, align="0")
        with self.assertRaisesRegex(ValueError, "一张"):
            split(source.expand(2, -1, -1, -1))


if __name__ == "__main__":
    unittest.main()
