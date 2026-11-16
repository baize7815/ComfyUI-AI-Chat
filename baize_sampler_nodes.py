"""Two independent sampling schedules from user-supplied node archives.

These implement only the two SIGMAS nodes selected by the user. The upstream
Viggle Turbo LoRA loader is deliberately not imported into AI Chat.
"""

import math

import numpy as np
import torch


class BaizeAITKQwen21Sigmas:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latent": ("LATENT",),
            "steps": ("INT", {"default": 30, "min": 2, "max": 200}),
        }}

    RETURN_TYPES = ("SIGMAS", "STRING")
    RETURN_NAMES = ("sigmas", "schedule_info")
    FUNCTION = "build"
    CATEGORY = "🫧 AI Chat"

    def build(self, latent, steps):
        samples = latent["samples"]
        if samples.ndim != 4 or samples.shape[1] != 64:
            raise ValueError("只适用于 Qwen Image 2.1 的 64 通道图像 latent。")
        if not isinstance(steps, int) or not 2 <= steps <= 200:
            raise ValueError("steps 必须是 2 到 200 的整数。")
        seq_len = samples.shape[-2] * samples.shape[-1]
        mu = (seq_len - 256) * (0.9 - 0.5) / (8192 - 256) + 0.5
        raw = np.linspace(1.0, 1.0 / steps, steps, dtype=np.float32)
        shifted = math.exp(mu) / (math.exp(mu) + (1.0 / raw - 1.0))
        factor = (1.0 - shifted[-1]) / (1.0 - 0.02)
        shifted = 1.0 - (1.0 - shifted) / factor
        sigmas = torch.from_numpy(
            np.concatenate([shifted, np.zeros(1, dtype=np.float32)]).astype(np.float32))
        return (sigmas,
                f"AITK Qwen2.1: steps={steps}; mu={mu:.10f}; last_nonzero=0.02; terminal=0")


class BaizeViggleTurboSigmas:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "latent": ("LATENT", {"tooltip": "传入采样器的 latent 尺寸决定调度偏移。"}),
            "nodes": ("STRING", {
                "default": "1.0, 0.9375, 0.875, 0.75, 0.5, 0.25",
                "tooltip": "未偏移的 student nodes，默认六步；按逗号分隔。",
            }),
        }}

    RETURN_TYPES = ("SIGMAS",)
    FUNCTION = "get_sigmas"
    CATEGORY = "🫧 AI Chat"

    def get_sigmas(self, latent, nodes):
        s = latent["samples"]
        if not isinstance(s, torch.Tensor) or s.ndim != 4:
            raise ValueError("latent 必须包含四维 samples 张量。")
        # Preserve original Viggle Turbo behavior and its ComfyUI spatial
        # downscale metadata convention.
        r = latent.get("downscale_ratio_spacial", 16) / 16
        tokens = round(s.shape[-2] * r) * round(s.shape[-1] * r)
        mu = 0.5 + (0.9 - 0.5) * (tokens - 256) / (8192 - 256)
        try:
            values = [float(x.strip()) for x in nodes.split(",")]
            if not values or not all(0 < value <= 1 for value in values):
                raise ValueError()
        except (ValueError, AttributeError) as exc:
            raise ValueError("nodes 必须是逗号分隔的数字，每个值在 (0, 1] 范围。") from exc
        t = torch.tensor(values, dtype=torch.float64)
        sigmas = math.exp(mu) / (math.exp(mu) + (1 / t - 1))
        return (torch.cat([sigmas, sigmas.new_zeros(1)]).float(),)


NODE_CLASS_MAPPINGS = {
    "BaizeAITKQwen21Sigmas": BaizeAITKQwen21Sigmas,
    "BaizeViggleTurboSigmas": BaizeViggleTurboSigmas,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BaizeAITKQwen21Sigmas": "白泽·AITK Qwen2.1采样时间表",
    "BaizeViggleTurboSigmas": "Qwen-Image-2.1 Viggle Turbo Sigmas",
}
