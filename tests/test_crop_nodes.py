"""Lightweight, local tests; does not require a running ComfyUI server."""

import json
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from crop_nodes import AIChatCropFromJSON, AIChatCropFromMask, AIChatPasteCrop
import AI_Assistant


def zeros(height=13, width=17, batch=1):
    return torch.zeros((batch, height, width, 3), dtype=torch.float32)


def mask_crop(image, mask, align="8", edges=0):
    return AIChatCropFromMask().crop(
        image, mask, 0.01, align, edges, edges, edges, edges)


def json_crop(image, value, align="8", edges=0):
    return AIChatCropFromJSON().crop(
        image, json.dumps(value), 0, align,
        edges, edges, edges, edges, False)


class CropNodesTest(unittest.TestCase):
    def test_scaled_reference_coordinates(self):
        image = zeros(1125, 2001)
        _, crop_mask, data = json_crop(image, {
            "image_width": 1920, "image_height": 1080,
            "regions": [{"bbox": [42, 29, 225, 92]}],
        })
        self.assertEqual(data["boxes"][0]["x"], 40)
        self.assertEqual(data["boxes"][0]["y"], 24)
        self.assertEqual(data["boxes"][0]["width"], 200)
        self.assertEqual(data["boxes"][0]["height"], 72)
        self.assertEqual(tuple(crop_mask.shape), (1, 72, 200))

    def test_odd_image_edge_crop_and_exact_roundtrip(self):
        image = torch.arange(13 * 17 * 3, dtype=torch.float32).reshape(1, 13, 17, 3) / 1000
        mask = torch.zeros((1, 13, 17))
        mask[0, 11:13, 16] = 1
        crop, rectangle, metadata = mask_crop(image, mask)
        box = metadata["boxes"][0]
        self.assertEqual((box["x"], box["y"]), (16, 8))
        self.assertEqual((box["width"], box["height"]), (1, 5))
        self.assertEqual((box["pad_right"], box["pad_bottom"]), (7, 3))
        self.assertEqual(tuple(crop.shape), (1, 8, 8, 3))
        self.assertEqual(float(rectangle.sum()), 5.0)
        restored = AIChatPasteCrop().paste(image, crop, metadata, 0)[0]
        self.assertTrue(torch.equal(image, restored))

    def test_manual_mask_returns_full_rectangle(self):
        image = zeros()
        mask = torch.zeros((1, 13, 17))
        mask[0, 3, 5] = 1
        mask[0, 4, 6] = 1
        crop, rectangle, data = mask_crop(image, mask, align="2")
        self.assertEqual((data["boxes"][0]["x"], data["boxes"][0]["y"]), (4, 2))
        self.assertEqual(float(rectangle.sum()), float(data["boxes"][0]["width"] * data["boxes"][0]["height"]))
        self.assertGreater(float(rectangle.sum()), float(mask.sum()))
        self.assertEqual(tuple(crop.shape[1:3]), tuple(rectangle.shape[1:]))

    def test_paste_resizes_only_region(self):
        image = zeros(25, 25)
        crop, _, metadata = json_crop(image, {
            "image_width": 25, "image_height": 25,
            "regions": [{"bbox": [10, 10, 14, 14]}],
        })
        edited = torch.ones((1, 16, 20, 3))
        pasted = AIChatPasteCrop().paste(image, edited, metadata, 0)[0]
        box = metadata["boxes"][0]
        x, y, w, h = (box[k] for k in ("x", "y", "width", "height"))
        self.assertTrue(torch.equal(pasted[0, y:y+h, x:x+w], torch.ones((h, w, 3))))
        self.assertTrue(torch.equal(pasted[0, :, 24, :], image[0, :, 24, :]))
        self.assertTrue(torch.equal(pasted[0, 24, :, :], image[0, 24, :, :]))

    def test_multi_image_mask_batch(self):
        image = zeros(batch=2)
        masks = torch.zeros((2, 13, 17))
        masks[0, 1:3, 2:4] = 1
        masks[1, 10:13, 15:17] = 1
        cropped, cropped_masks, data = mask_crop(image, masks)
        self.assertEqual(cropped.shape[0], 2)
        self.assertEqual(cropped_masks.shape[0], 2)
        self.assertNotEqual(data["boxes"][0]["x"], data["boxes"][1]["x"])
        self.assertEqual(tuple(cropped.shape[1:3]), tuple(cropped_masks.shape[1:]))
        self.assertTrue(torch.equal(image, AIChatPasteCrop().paste(image, cropped, data, 0)[0]))

    def test_reject_aspect_mismatch_and_empty_mask(self):
        with self.assertRaisesRegex(ValueError, "宽高比"):
            json_crop(zeros(), {"image_width": 100, "image_height": 100,
                                "regions": [{"bbox": [1, 1, 5, 5]}]})
        with self.assertRaisesRegex(ValueError, "为空"):
            mask_crop(zeros(), torch.zeros((1, 13, 17)))

    def test_assistant_uses_real_outgoing_image_size(self):
        node = AI_Assistant.多模态AI助手节点()
        image = zeros(320, 2560)
        captured = {}

        def fake_create(**kwargs):
            captured["messages"] = kwargs["messages"]
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps({
                    "image_width": 123, "image_height": 456,
                    "regions": [{"label": "logo", "bbox": [10, 10, 100, 80]}],
                })))])

        fake = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
            close=lambda: None,
        )
        with mock.patch.object(AI_Assistant, "OpenAI", return_value=fake), mock.patch.object(
            AI_Assistant, "resolve_provider_and_model",
            return_value=({"api_key": "test", "base_url": "https://example.com/v1"}, "fake"),
        ):
            result = node.处理多模态请求(
                服务商配置="test", 选择模型="fake", 手动模型="",
                预设系统提示="区域识别裁剪", 系统提示="",
                用户输入="寻找 logo", 随机度=1, 输入图像=image,
            )
        data = json.loads(result[0])
        self.assertEqual((data["image_width"], data["image_height"]), (2048, 256))
        user_message = captured["messages"][-1]["content"]
        self.assertIn("2048", user_message[0]["text"])
        self.assertIn("256", user_message[0]["text"])
        self.assertEqual(data["regions"][0]["bbox"], [10.0, 10.0, 100.0, 80.0])


if __name__ == "__main__":
    unittest.main()
