"""Tests for named reference slots and automatic batch/video input modes."""

import json
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import AI_Assistant


def image(n=1):
    return torch.zeros((n, 20, 30, 3), dtype=torch.float32)


class AssistantInputTests(unittest.TestCase):
    def setUp(self):
        self.node = AI_Assistant.多模态AI助手节点()
        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=f"reply-{len(self.calls)}")
            )])

        fake = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)), close=lambda: None)
        self.openai = mock.patch.object(AI_Assistant, "OpenAI", return_value=fake)
        self.provider = mock.patch.object(
            AI_Assistant, "resolve_provider_and_model",
            return_value=({"api_key": "synthetic-test", "base_url": "https://openrouter.ai/api/v1"},
                          "test/model"),
        )
        self.openai.start()
        self.provider.start()
        self.addCleanup(self.openai.stop)
        self.addCleanup(self.provider.stop)

    def request(self, **inputs):
        return self.node.处理多模态请求(
            服务商配置="test", 选择模型="test/model", 手动模型="",
            预设系统提示="默认", 系统提示="follow instructions",
            用户输入="compare", 随机度=1, **inputs)

    def test_inputs_and_outputs_have_stable_contract(self):
        optional = self.node.INPUT_TYPES()["optional"]
        self.assertEqual(
            [key for key in optional if key != "最大token"],
            ["image_1", "image_2", "image_3", "image_4", "image_group", "video"],
        )
        self.assertNotIn("输入图像", optional)
        self.assertNotIn("图片处理模式", optional)
        self.assertEqual(self.node.RETURN_NAMES,
                         ("AI回复", "系统提示词", "AI回复列表", "视频分镜列表"))
        self.assertEqual(self.node.OUTPUT_IS_LIST, (False, False, True, True))

    def test_nonconsecutive_reference_slots_keep_names_and_one_request(self):
        result = self.request(image_1=image(), image_3=image())
        self.assertEqual(len(self.calls), 1)
        content = self.calls[0]["messages"][-1]["content"]
        labels = [part["text"] for part in content if part["type"] == "text"]
        self.assertIn("参考图片 image_1：", labels)
        self.assertIn("参考图片 image_3：", labels)
        self.assertNotIn("参考图片 image_2：", labels)
        self.assertLess(labels.index("参考图片 image_1："), labels.index("参考图片 image_3："))
        self.assertEqual(sum(part["type"] == "image_url" for part in content), 2)
        self.assertEqual(result, ("reply-1", "follow instructions", ["reply-1"], []))

    def test_group_batches_are_independent_requests(self):
        result = self.request(image_group=image(3))
        self.assertEqual(len(self.calls), 3)
        for i, call in enumerate(self.calls, start=1):
            parts = call["messages"][-1]["content"]
            self.assertEqual(sum(part["type"] == "image_url" for part in parts), 1)
            self.assertIn(f"参考图片 image_group[{i}]：",
                          [part["text"] for part in parts if part["type"] == "text"])
        self.assertEqual(result[0], "reply-1\n---\nreply-2\n---\nreply-3")
        self.assertEqual(result[2], ["reply-1", "reply-2", "reply-3"])

    def test_ref_group_conflicts_and_video_conflicts(self):
        with self.assertRaisesRegex(ValueError, "二选一"):
            self.request(image_2=image(), image_group=image())
        with self.assertRaisesRegex(ValueError, "不能与 image_group"):
            self.request(image_group=image(), video=object())
        self.assertFalse(self.calls)

    def test_reference_slots_reject_multi_image_batches(self):
        with self.assertRaisesRegex(ValueError, "最多允许 1"):
            self.request(image_4=image(2))
        self.assertFalse(self.calls)
        with self.assertRaisesRegex(ValueError, "最多允许 8"):
            self.request(image_group=image(9))
        self.assertFalse(self.calls)

    def test_video_with_references_is_one_request(self):
        with mock.patch.object(AI_Assistant, "video_to_data_url", return_value="data:video/mp4;base64,AAA") as convert:
            result = self.request(image_4=image(), video=object())
        convert.assert_called_once()
        content = self.calls[0]["messages"][-1]["content"]
        self.assertIn("video_url", [part["type"] for part in content])
        self.assertIn("参考图片 image_4：",
                      [part["text"] for part in content if part["type"] == "text"])
        self.assertEqual(result[2], ["reply-1"])

    def test_crop_preset_accepts_only_image_1(self):
        for inputs in (
            {},
            {"image_2": image()},
            {"image_1": image(), "image_4": image()},
            {"image_group": image()},
            {"image_1": image(), "video": object()},
        ):
            with self.subTest(inputs=tuple(inputs)):
                with self.assertRaisesRegex(ValueError, "只能连接 image_1"):
                    self.node.处理多模态请求(
                        服务商配置="test", 选择模型="test/model", 手动模型="",
                        预设系统提示="区域识别裁剪", 系统提示="",
                        用户输入="find", 随机度=1, **inputs)
        self.assertFalse(self.calls)

    def test_text_only_still_works(self):
        result = self.request()
        self.assertEqual(result[0], "reply-1")
        content = self.calls[0]["messages"][-1]["content"]
        self.assertEqual(len([p for p in content if p["type"] == "image_url"]), 0)


if __name__ == "__main__":
    unittest.main()
