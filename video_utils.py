"""Serialize a ComfyUI VIDEO for native video input without extracting frames."""

import base64
import io


MAX_VIDEO_BYTES = 50 * 1024 * 1024


class _LimitedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_VIDEO_BYTES:
            raise ValueError("视频导出超过 50 MiB 限制，请先压缩或裁剪视频。")
        return super().write(data)


def video_to_data_url(video):
    save_to = getattr(video, "save_to", None)
    if not callable(save_to):
        raise ValueError("视频输入需要连接 ComfyUI 原生 VIDEO 类型；图片帧批次不能作为原生视频上传。")
    try:
        with _LimitedBuffer() as buffer:
            # Export the VIDEO object itself so upstream trims/crops are respected.
            # ComfyUI handles its video and audio streams when writing MP4.
            save_to(buffer, format="mp4")
            data = buffer.getvalue()
    except Exception as exc:
        raise ValueError(f"无法导出视频：{exc}") from exc
    if not data:
        raise ValueError("导出的视频为空。")
    return "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")
