try:
    import regex as regex_engine
except ImportError:  # Keep the node importable and fail safely only when regex mode is used.
    regex_engine = None


MAX_INPUT_LENGTH = 1_000_000
MAX_OUTPUT_LENGTH = 5_000_000
MAX_RULE_TEXT_LENGTH = 1_000_000
MAX_RULE_COUNT = 100
MAX_PATTERN_LENGTH = 4_000
MAX_REPLACEMENT_LENGTH = 100_000

class 文本正则替换节点:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "替换规则": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "每行一条：查找内容|||替换内容",
                }),
                "替换模式": (["默认", "正则替换"], {"default": "默认"}),
            },
            "optional": {
                "输入文本": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("输出文本",)
    FUNCTION = "文本替换处理"
    CATEGORY = "AI Chat/文本工具"
    DESCRIPTION = "按每行“查找|||替换”规则执行普通或带超时保护的正则替换。"

    def 文本替换处理(self, 替换规则, 替换模式, 输入文本=None):
        # 如果没有输入文本，直接返回空字符串
        if not 输入文本:
            return ("",)

        # 如果没有替换规则，直接返回原始文本
        if not 替换规则:
            return (输入文本,)

        if len(输入文本) > MAX_INPUT_LENGTH:
            raise ValueError(f"输入文本不能超过 {MAX_INPUT_LENGTH} 个字符。")
        if len(替换规则) > MAX_RULE_TEXT_LENGTH:
            raise ValueError(f"替换规则总长度不能超过 {MAX_RULE_TEXT_LENGTH} 个字符。")
        if 替换模式 == "正则替换" and regex_engine is None:
            raise RuntimeError("未安装 regex 依赖，不能安全执行正则替换。")

        # 分割替换规则为多行
        规则行列表 = 替换规则.strip().split('\n')
        if len(规则行列表) > MAX_RULE_COUNT:
            raise ValueError(f"替换规则不能超过 {MAX_RULE_COUNT} 条。")

        已解析规则 = []
        for 行号, 规则行 in enumerate(规则行列表, start=1):
            if not 规则行.strip():
                continue
            if "|||" not in 规则行:
                raise ValueError(f"第 {行号} 行缺少分隔符 |||。")
            查找内容, 替换内容 = 规则行.split("|||", 1)
            if len(查找内容) > MAX_PATTERN_LENGTH:
                raise ValueError(f"第 {行号} 行查找内容过长。")
            if len(替换内容) > MAX_REPLACEMENT_LENGTH:
                raise ValueError(f"第 {行号} 行替换内容过长。")
            if 替换模式 == "正则替换":
                try:
                    查找内容 = regex_engine.compile(查找内容)
                except Exception as exc:
                    raise ValueError(f"第 {行号} 行正则表达式无效：{exc}") from exc
            已解析规则.append((查找内容, 替换内容, 行号))

        # 处理每一行替换规则
        结果文本 = 输入文本
        for 查找内容, 替换内容, 行号 in 已解析规则:
            try:
                if 替换模式 == "正则替换":
                    replacement_total = 0

                    def bounded_replacement(match):
                        nonlocal replacement_total
                        expanded = match.expand(替换内容)
                        replacement_total += len(expanded)
                        if len(结果文本) + replacement_total > MAX_OUTPUT_LENGTH:
                            raise ValueError(f"第 {行号} 行替换后的文本预计过大。")
                        return expanded

                    结果文本 = 查找内容.sub(
                        bounded_replacement,
                        结果文本,
                        timeout=1.0,
                    )
                else:
                    occurrences = 结果文本.count(查找内容) if 查找内容 else len(结果文本) + 1
                    projected_length = len(结果文本) + occurrences * (
                        len(替换内容) - len(查找内容)
                    )
                    if projected_length > MAX_OUTPUT_LENGTH:
                        raise ValueError(f"第 {行号} 行替换后的文本预计过大。")
                    结果文本 = 结果文本.replace(查找内容, 替换内容)
            except TimeoutError as exc:
                raise ValueError(f"第 {行号} 行正则执行超时，请简化表达式。") from exc
            except Exception as exc:
                raise ValueError(f"第 {行号} 行替换失败：{exc}") from exc
            if len(结果文本) > MAX_OUTPUT_LENGTH:
                raise ValueError(f"第 {行号} 行替换后的文本超过大小限制。")

        return (结果文本,)

NODE_CLASS_MAPPINGS = {"TextReplaceNode": 文本正则替换节点}
NODE_DISPLAY_NAME_MAPPINGS = {"TextReplaceNode": "文本正则替换"}
