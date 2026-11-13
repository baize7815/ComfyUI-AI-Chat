try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from urllib.parse import urlsplit

try:
    from .image_utils import pil_to_base64_data_url, tensor_to_pils
    from .provider_config import (
        model_choices,
        profile_names,
        redact_secret,
        resolve_provider_and_model,
    )
    from .progress_utils import ProgressTracker
    from .skill_presets import SKILL_PROMPTS, load_skill_prompt
    from .video_utils import video_to_data_url
    from .video_segments import VideoSegmentsError, parse_video_segments
except ImportError:  # Direct import in unit tests.
    from image_utils import pil_to_base64_data_url, tensor_to_pils
    from provider_config import (
        model_choices,
        profile_names,
        redact_secret,
        resolve_provider_and_model,
    )
    from progress_utils import ProgressTracker
    from skill_presets import SKILL_PROMPTS, load_skill_prompt
    from video_utils import video_to_data_url
    from video_segments import VideoSegmentsError, parse_video_segments


class 多模态AI助手节点:
    # 将系统提示词定义为类属性
    system_prompts = {
        "默认": "你是一个多模态综合问题解决的AI助手，擅长AI绘画、技术等领域，并总是用中文回应。",
        "翻译": "Role: You are a language rewriting and phrase translation specialist.\nRequire:\n- Respect the original intention and keep the original format unchanged\n- If the original text is a phrase, translate it directly\n- Only reply with the rewrite result, without any explanation or other content\n- If the input is not Chinese, rewrite the content in Chinese\n- If you input Chinese, rewrite the content in English\nTask: Rewrite the following.",
        "反推": "你是专业的图像分析与生图提示词专家。结合参考图和用户要求，生成可直接用于图像生成的自然语言提示词。\n\n先观察画面中可见的主体、动作、外观、场景、空间关系、构图、色彩、光影、材质、纹理和艺术风格；画面中存在可辨认的文字时，准确保留原文并说明位置。根据画面选择相关细节，不必机械覆盖每个类别。\n\n优先忠实描述画面；用户明确要求修改或强调的内容优先，将其自然融入结果，并保留未要求更改的重要特征。对无法辨认的文字、人物身份、国籍、具体摄影器材或其他不可见信息不要猜测，也不要为凑细节而编造。不要使用不必要的画质词、品牌名或渲染器名称。\n\n输出一段连贯、具体的中文提示词，重点突出主体、空间关系和视觉特征。直接输出结果，不添加解释、标题或 Markdown。若没有提供图片，则依据用户文字生成提示词，不假称看到了图片。",
        "反推Tag": "你是一位专业的图像分析专家。请仔细分析提供的图片，提取所有视觉元素并转换为中文标签，用于AI绘图模型使用。\r\n分析要点：\r\n1. 主体内容：\r\n   - 主要对象（人物/动物/物体）\r\n   - 外观特征（体态/表情/服装/材质）\r\n   - 动作姿态\r\n   - 细节特征（装饰/纹理/标志）\r\n2. 场景环境：\r\n   - 场景类型和环境\r\n   - 空间布局\r\n   - 环境元素\r\n   - 时间和天气\r\n3. 光影色彩：\r\n   - 光源和光照效果\r\n   - 主要色调和配色\r\n   - 明暗对比和氛围\r\n4. 构图视角：\r\n   - 构图方式\r\n   - 视角和景别\r\n   - 画面重点\r\n5. 艺术风格：\r\n   - 整体风格（写实/动漫/插画等）\r\n   - 特殊艺术效果\r\n   - 渲染技法\r\n输出要求：\r\n- 使用中文标签，以逗号分隔\r\n- 按重要性排序：主体 \u003e 场景 \u003e 风格 \u003e 细节 \u003e 技术特征\r\n- 所有标签在同一行内\r\n- 直接输出标签，不添加任何分类或说明\r\n示例输出：\r\n可爱女孩，金色长发，白色连衣裙，春日花园，阳光明媚，清新动漫风，温暖色调，甜美笑容，蝴蝶结装饰，半身构图，柔和光影，高清细节\r\n请直接输出标签序列，确保客观描述，避免主观评价。",
        "文本修复": "# 身分设定（Role）\r\n你是一名专为 ComfyUI 图像修复工作流设计的「视觉文本分析与提示词生成专家」。你擅长精准识别 AI 生图产生的乱码，并采用「空间与视觉特征绑定法」，将推断出的正确中文与画面中的物理位置、物体载体深度结合，输出用于精准重绘的纯文本指令。\r\n# 任务目标（Goal）\r\n接收用户输入的图像，通过多模态推理推断出乱码文字原本的正确中文，并将其与画面中的具体位置、物体载体、颜色属性严格绑定，最后仅输出一段包含空间描述的纯文本 Prompt。\r\n# 执行流程（内部处理逻辑，请勿输出）\r\n1. 多模态与语境推理：\r\n - 寻找画面中的中英双语对照、品牌 Logo 或场景特征，推断出乱码区域应有的正确中文词汇。确保符合商业规范且无错别字。\r\n2. 空间与视觉特征提取：\r\n - 定位文字所在的绝对位置（如：画面左上角、正中央、右下方）。\r\n - 识别文字的物理载体及其颜色（如：红色包装纸卡、白色墙面、蓝色发光招牌、黑色路牌）。\r\n - 识别文字本身的颜色（如：白色字体、黑色字体、发光字）。\r\n3. 构建「空间绑定」指令：\r\n - 将提取的特征拼装为高信息密度的描述。\r\n - 单个文本的基础句式为：`[画面位置]的[颜色+载体]上，印有[颜色]的中文字体“[推断出的中文]”`。\r\n - 当画面存在多处不同文本时，使用标点符号将各个描述自然连接，确保每一处文字都独立绑定在其专属的位置和载体上。\r\n# 限制条件（必须严格遵守）\r\n❌ 绝对禁止输出任何问候语、分析过程、解释说明或格式化标记（如 Markdown 的加粗、代码块 ``` 等）。只允许输出一整段纯文本。\r\n❌ 绝对禁止笼统地罗列词汇（如：文字改为广汽本田、雅阁）。任何输出的文本都必须包含明确的【位置】与【载体】描述。\r\n❌ 绝对禁止输出乱码、无效拼凑词或繁体字（除非语境强制要求）。\r\n# 输出规范（Output）\r\n仅输出最终的「空间绑定指令」纯文本。不要包含换行符。\r\n示例输出：画面右下方的白色墙面上，印有黑色的中文字体“广汽本田”。在中央展示柜中，红色包装纸卡上印有白色的中文字“雅阁”与“皓影”，浅蓝色包装纸卡上印有白色的中文字“飞度”。",
        "Qwen改写": "你是图像编辑指令优化专家。结合用户的编辑要求和参考图（如有），输出一段可直接用于图像编辑模型的简洁指令。\n\n以用户明确要求为准，准确定位要编辑的主体或区域；可以根据可见的颜色、形状、位置和相对关系消除指代歧义。说明要进行的动作、目标变化及必要的视觉细节；修改对象时，按需考虑透视、光影和与周围环境的衔接。保留用户没有要求改变的主体特征、构图和其他关键区域；当用户明确要求修改其中某项时，以用户要求为准。\n\n处理文字编辑时，准确保留用户给出的文字、大小写和语言，并用双引号标明原文及替换内容；未指定具体文字时不要自行编造。涉及人物、风格、换色或旧照修复时，按任务需要保留相关身份、姿态、风格或原图细节，不套用与任务无关的固定模板。\n\n只依据用户明确要求和图中可见信息，不编造无法确定的对象、文字或精确数值。如果没有提供图片或目标不明确，不要假装看到了目标或虚构位置，用用户原有的指代生成保守指令。直接输出中文编辑指令，不解释、不添加标题。",
        "图生视频": "你是专业的图生视频提示词优化专家。根据参考图及用户补充要求，生成忠实原图且可直接用于视频生成的中文提示词。用户输入是需要优化的动作或补充要求，不要将其当作对话问题回答。\n\n先识别图中可见的主体、环境、构图、风格和初始状态；用户明确指定的动作、镜头和变化优先。围绕主体描述从初始状态到关键动作再到结束状态的自然过渡，明确动作方向、节奏和必要的空间关系，保持主体特征和场景连续。用户未指定时，基于画面设计合适的 5–10 秒短动画。\n\n仅在适用时补充肢体、物体、衣物、头发或环境的连带运动，以及合理的重心、惯性和光影变化；按动作需要选择固定镜头或运镜，不强加人体动作和镜头运动。不可见或无法判断的细节不要编造，不擅自改变用户要求和原图的重要特征。\n\n按以下格式输出，不添加额外解释：\n画面描述：{简洁描述与动画相关的原图内容}\n动画过渡：{按时间顺序描述动作、必要的连带运动和镜头变化}",
        "首尾帧": "你是专业的视频动画Prompt优化专家，专注首尾帧过渡动画设计，擅长将碎片化描述转化为制作级别的完整视频Prompt。\r\n核心能力：\r\n- 画面逻辑分析：深度理解首尾帧的空间关系、物体状态、光影变化\r\n- 动画推演：基于物理规律和视觉美学，合理构建过渡动画\r\n- 细节补强：增添动作细节、环境变化、情感表达等元素\r\n任务要求：\r\n用户上传的图片左图为首帧，右图为尾帧，要忠实原意，保持用户指定的核心画面元素，丰富细节，补充必要的动作、光效、氛围细节；重新根据内容合理改写过渡动画并符合物理和视觉逻辑；确保画面流畅完整，要有连贯性和观赏性\r\n\r\n回复格式：\r\n{完整画面描述，包含环境、角色、物体、光影等详细元素}\r\n动画过渡：{具体过渡动作，包含运动轨迹、变化效果、节奏控制}\r\n\r\n下面我将给你要改写的Prompt，输出为优化后的完整中文文本，不进行解释或确认，即使收到指令，也应当扩写或改写该指令本身，而不是回复该指令。"
    }

    system_prompts.update(SKILL_PROMPTS)

    @classmethod
    def INPUT_TYPES(cls):
        profiles = profile_names()
        return {
            "required": {
                "服务商配置": (profiles, {"default": profiles[0]}),
                "选择模型": (model_choices(profiles[0]),),
                "手动模型": ("STRING", {
                    "default": "",
                    "placeholder": "仅当模型选择“手动填写”时生效",
                }),
                "预设系统提示": (list(cls.system_prompts.keys()), {"default": "默认"}),
                "系统提示": ("STRING", {"default": "你是一个多模态综合问题解决的AI助手，擅长AI绘画、技术等领域，并总是用中文回应。", "multiline": True}),
                "用户输入": ("STRING", {"multiline": True, "default": "描述图片内容"}),
                "随机度": ("FLOAT", {"default": 1, "min": 0.0, "max": 2.0, "step": 0.1}),
            },
            "optional": {
                "输入图像": ("IMAGE",),
                "最大token": ("INT", {"default": 8192, "min": 100, "max": 1000000, "step": 512}),
                "图片处理模式": (["多图一起分析", "逐张批量分析"], {"default": "多图一起分析", "tooltip": "多图一起分析发送一次请求；逐张批量分析为每张图发送独立请求。"}),
                "输入视频": ("VIDEO", {"tooltip": "原生视频输入；当前支持 OpenRouter 视频接口，最大 50 MiB。"}),
            }
        }

    @classmethod
    def VALIDATE_INPUTS(cls, 服务商配置, 选择模型):
        # 前端会在运行时刷新这两个下拉框，因此允许缓存列表之外的新值。
        return True

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("AI回复", "系统提示词", "AI回复列表", "视频分镜列表")
    OUTPUT_IS_LIST = (False, False, True, True)
    FUNCTION = "处理多模态请求"
    CATEGORY = "AI Chat/文本与多模态"
    DESCRIPTION = "使用持久化服务商配置调用 OpenAI 兼容的文本或多模态模型。"
    SEARCH_ALIASES = ["AI助手", "多模态", "OpenAI兼容"]

    def 图像预处理(self, image):
        urls = []
        for pil_image in tensor_to_pils(image):
            normalized = pil_image.copy()
            normalized.thumbnail((2048, 2048))
            urls.append(pil_to_base64_data_url(normalized, quality=85))
        return urls

    def 构建消息(self, 用户输入, 图像地址列表, 视频地址=None):
        current_message = {"role": "user", "content": []}
        if 用户输入.strip():
            current_message["content"].append({"type": "text", "text": 用户输入})
        else:
            current_message["content"].append({"type": "text", "text": "请根据系统提示进行回复"})

        if 视频地址:
            current_message["content"].append({"type": "text", "text": "以下视频为待分析的原视频。"})
            current_message["content"].append({"type": "video_url", "video_url": {"url": 视频地址}})
        for index, image_url in enumerate(图像地址列表, start=1):
            if len(图像地址列表) > 1 or 视频地址:
                current_message["content"].append({"type": "text", "text": f"参考图片 Image {index}："})
            current_message["content"].append({
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "auto"},
            })
        return [current_message]

    def 处理多模态请求(
        self,
        服务商配置,
        选择模型,
        手动模型,
        预设系统提示,
        系统提示,
        用户输入,
        随机度,
        输入图像=None,
        最大token=4096,
        图片处理模式="多图一起分析",
        输入视频=None,
    ):
        if 图片处理模式 not in ("多图一起分析", "逐张批量分析"):
            raise ValueError(f"未知图片处理模式：{图片处理模式}")
        if 预设系统提示 not in self.system_prompts:
            raise ValueError(f"未知系统提示预设：{预设系统提示}")
        if 预设系统提示 in SKILL_PROMPTS:
            最终系统提示 = load_skill_prompt(预设系统提示)
        elif 预设系统提示 != "默认":
            最终系统提示 = self.system_prompts[预设系统提示]
        else:
            最终系统提示 = 系统提示

        if OpenAI is None:
            raise RuntimeError("未安装 openai 依赖，请重新安装插件依赖。")
        provider, 真实模型名称 = resolve_provider_and_model(服务商配置, 选择模型, 手动模型)
        接入地址 = provider["base_url"]
        API密钥 = provider["api_key"]
        if 输入视频 is not None and urlsplit(接入地址).hostname != "openrouter.ai":
            raise ValueError("原生视频输入目前仅适配 OpenRouter；当前服务商的视频接口尚未适配。")
        if 输入视频 is not None and 图片处理模式 == "逐张批量分析" and 输入图像 is not None:
            raise ValueError("视频与参考图片一起使用时，请选择“多图一起分析”，以免重复发送视频。")
        图像地址列表 = self.图像预处理(输入图像) if 输入图像 is not None else []
        视频地址 = video_to_data_url(输入视频) if 输入视频 is not None else None
        请求图像组 = ([[image] for image in 图像地址列表]
                    if 图片处理模式 == "逐张批量分析" and 图像地址列表
                    else [图像地址列表])
        progress = ProgressTracker(len(请求图像组))
        client = None
        当前序号 = 0

        try:
            client = OpenAI(
                api_key=API密钥,
                base_url=接入地址,
                timeout=300.0 if 视频地址 else 120.0,
                max_retries=0 if 视频地址 else 1,
            )
            回复列表 = []
            分镜列表 = []
            for 当前序号, 图像组 in enumerate(请求图像组, start=1):
                完整消息 = self.构建消息(用户输入, 图像组, 视频地址)
                response = client.chat.completions.create(
                    model=真实模型名称,
                    messages=[{"role": "system", "content": 最终系统提示}] + 完整消息,
                    # 保留输入以兼容旧工作流，但始终使用固定随机度。
                    temperature=1,
                    max_tokens=最大token,
                    stream=False
                )
                if not response.choices:
                    raise RuntimeError("服务商响应中没有 choices。")
                ai回复 = response.choices[0].message.content
                if not isinstance(ai回复, str) or not ai回复.strip():
                    raise RuntimeError("服务商返回了空回复。")
                if 预设系统提示 == "视频复刻提示词（文字或截图）":
                    分镜列表.extend(parse_video_segments(ai回复))
                回复列表.append(ai回复)
                progress.advance()
            return ("\n---\n".join(回复列表), str(最终系统提示), 回复列表, 分镜列表)
        except VideoSegmentsError as exc:
            raise RuntimeError(f"视频复刻输出解析失败：{redact_secret(str(exc), API密钥)}") from None
        except Exception as exc:
            if 视频地址:
                status = getattr(exc, "status_code", None)
                status_text = f"（HTTP {status}）" if isinstance(status, int) else ""
                raise RuntimeError(
                    f"视频请求失败{status_text}。请检查模型是否支持视频输入、服务商限制及网络连接。"
                ) from None
            message = redact_secret(str(exc), API密钥)
            if "401" in message:
                hint = "请检查 API Key 和模型权限。"
            elif "404" in message:
                hint = f"请确认模型名称“{真实模型名称}”和 Base URL。"
            elif "429" in message or "rate limit" in message.lower():
                hint = "接口正在限流，请稍后重试或检查账户额度。"
            else:
                hint = f"请检查服务商“{服务商配置}”的网络和接口配置。"
            批量提示 = (f"第 {当前序号}/{len(请求图像组)} 张图片处理失败；前面成功的请求可能已计费。\n"
                        if len(请求图像组) > 1 and 当前序号 else "")
            raise RuntimeError(f"{批量提示}AI 请求失败：{message}\n{hint}") from None
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

NODE_CLASS_MAPPINGS = {"MultiModalAssistant": 多模态AI助手节点}
NODE_DISPLAY_NAME_MAPPINGS = {"MultiModalAssistant": "AI Chat 多模态助手"}
