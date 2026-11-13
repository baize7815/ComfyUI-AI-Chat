"""Parse the video replication preset's JSON into ComfyUI string-list items."""

import json
import re


class VideoSegmentsError(ValueError):
    pass


def parse_video_segments(text):
    raw = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise VideoSegmentsError("视频复刻结果不是有效 JSON；请检查模型输出或提高最大 token。") from exc
    if not isinstance(data, dict):
        raise VideoSegmentsError("视频复刻 JSON 必须是对象。")
    if isinstance(data.get("error"), str) and data["error"].strip():
        raise VideoSegmentsError("视频复刻所需信息不足：" + data["error"].strip()[:1000])
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise VideoSegmentsError("视频复刻 JSON 缺少非空的 segments 列表。")
    results = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise VideoSegmentsError(f"第 {index} 段不是有效对象。")
        prompt = segment.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise VideoSegmentsError(f"第 {index} 段缺少提示词。")
        results.append(prompt.strip())
    return results
