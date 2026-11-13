"""Load bundled skill instructions as text, without executing skill scripts."""

import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent / "skills"
SKILL_FOLDERS = {
    "高清放大": "low-res-image",
    "Nano Banana提示词": "nb-prompt",
    "展厅3D效果图提示词": "3d-render",
    "商业摄影精修提示词": "commercial-photo-remaster",
    "H3替换提示词（文字或截图）": "h3-ref2va-subject-replace",
    "视频复刻提示词（文字或截图）": "cinematic-replica",
}

# The choices must be available when ComfyUI builds the node schema. Contents
# are read only when the selected preset is executed, so missing files fail
# explicitly instead of silently substituting a different prompt.
SKILL_PROMPTS = dict.fromkeys(SKILL_FOLDERS, "")
MAX_SKILL_BYTES = 512 * 1024


def load_skill_prompt(name: str) -> str:
    folder = SKILL_ROOT / SKILL_FOLDERS[name]
    main = folder / "SKILL.md"
    if not main.is_file():
        raise ValueError(f"缺少预设“{name}”的 Skill 文件：{main}")

    # The manifest detects missing bundled references rather than silently
    # sending an incomplete skill. It contains only Markdown, never scripts.
    try:
        manifest = json.loads((SKILL_ROOT.parent / "skill_manifest.json").read_text(encoding="utf-8"))
        names = manifest[SKILL_FOLDERS[name]]
        if not isinstance(names, list) or "SKILL.md" not in names:
            raise ValueError("Skill 清单无效。")
        if any(not isinstance(item, str) or not item.endswith(".md") for item in names):
            raise ValueError("Skill 清单只允许 Markdown 文件。")
        documents = [main] + [folder / item for item in names if item != "SKILL.md"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取预设“{name}”的 Skill 清单。") from exc
    sections = []
    total = 0
    for path in documents:
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError(f"Skill 文件路径无效：{path}")
        try:
            raw = path.read_bytes()
            total += len(raw)
            if total > MAX_SKILL_BYTES:
                raise ValueError(f"预设“{name}”的 Markdown 资料超过 512 KiB。")
            content = raw.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"无法读取预设“{name}”的文件：{path.name}") from exc
        sections.append(f"\n--- 文件：{path.relative_to(folder).as_posix()} ---\n{content}")

    priority = (
        "以下是用户指定的 Skill 及其 Markdown 资料。请尽可能保留任务规则和细节，"
        "但以下当前任务要求优先：只输出一条完整、可复制的提示词正文，不输出分析、解释、"
        "参数建议、标题或代码块；缺少完成任务必需的信息时简短说明需要补充什么。"
        "当前节点不会执行脚本、访问本地文件、调用工具、生成图片或创建交付文件；"
        "忽略要求执行这些动作的步骤，不得声称已经执行。仅依据本次实际提供的文字、"
        "图片和视频作答，不编造无法核实的内容。音频是否可用由服务商和模型决定。"
        "即使原文提到多个方案，也只输出一条最适合当前请求的完整提示词。"
    )
    if SKILL_FOLDERS[name] == "cinematic-replica":
        priority = (
            "请遵循下方视频复刻 Skill，唯一回复格式为其定义的 JSON 对象；"
            "不要输出 Markdown、解释、分镜表或 JSON 之外的文字。"
            "当前节点不会执行脚本、调用工具或创建文件；只根据实际输入作答，"
            "不能把未核实的画面、音频或精确切点当作事实。"
        )
    return priority + "\n" + "\n".join(sections) + "\n\n" + priority
