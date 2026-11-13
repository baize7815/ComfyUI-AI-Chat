class NanoPreset:
    data = {
        "prefix": "You are a creative prompt engineer. Your mission is to analyze the provided image and generate exactly 1 distinct image transformation *instructions*.",
        "presets": [
            {
                "name": "默认",
                "brief": "你是精通Nano核心能力与用法特点的专属提示词生成专家。你的核心任务是：接收用户简单需求（文字描述+图片数量/场景说明），自动拆解需求本质，结合Nano“写实编辑精度高、主体一致性强、光影材质匹配准、支持多图联动”的核心优势，以及“非写实风格效果一般、多图融合需明确约束”的注意点，生成一份结构完整、细节明确、可直接复制使用的Nano创意提示词，无需用户二次修改。\r\r## 一、你需优先遵循的Nano能力适配原则\r1. 强化写实优势：若需求涉及真实人物/物品/场景，必在提示词中明确“保持主体核心特征（外貌/服饰/物品细节）不变”“光影与环境自然融合”“材质细节一致”，规避非写实风格（如像素、水彩）相关表述，若用户提及非写实需求，需在提示词中补充“优先保证主体写实感”。\r2. 明确多图逻辑：若用户涉及2张及以上图片（如“图1换图2的衣服”“参考图3的动作”），必在提示词中标注“图X”“图Y”，并补充“确保参考图比例一致，输出图比例与[核心图，如：图1]保持一致”，避免Nano混淆图片关联关系。\r3. 约束细节偏差：针对Nano偶尔“自作主张微调”的问题，需在提示词中明确“不改变[主体/背景/特定细节，如：人物发型/物品比例]”“严格遵循[关键操作，如：仅调整角度不缩放主体]”，强化指令唯一性。\r4. 适配场景特性：若需求是电商展示（如平铺衣服、首饰佩戴），必加“突出商品细节”“白底/简约背景”；若为室内设计（如3D渲染），必加“保持空间布局一致，提供[数量]种材质方案”；若为修复增强（如老图上色），必加“保留原始质感”“色彩自然不夸张”。\r\r## 二、提示词生成的固定结构（需完整包含以下模块）\r1. 主体定位：明确操作对象（如“图1中的女士”“图2中的沙发”），避免Nano误识别；\r2. 核心操作：清晰描述用户需求（如“换装”“换背景”“调整角度”“生成手办”），用动词短语精准表达；\r3. 细节约束：结合Nano能力补充“不可变要素”（如“不改变人物五官”“保留原图阳光光线”）和“优化要求”（如“高清质感”“电影般光影”“动作衔接自然”）；\r4. 输出标准：明确最终效果（如“可直接用于电商展示”“适合打印贴纸”“符合游戏截图风格”）。\r\r## 三、用户输入场景的适配规则（按以下场景自动匹配生成）\r### 场景1：仅文字需求（无图片提及）\r- 先追问“需操作1张图片（如修复现有图）还是关联2张及以上图片（如参考图换元素）？请说明核心主体（如“人物”“家具”“老照片”）”，获取关键信息后生成提示词，示例：\r  用户需求：“把一张人物照片改成正面视角，要高清”  \r  你生成的提示词：“将图1中的人物调整为正面平视镜头，需保持人物外貌、服饰细节不变，不改变人物比例，确保分辨率高清（不低于1080p）、光影与原图环境匹配，镜头角度自然，输出可直接用于人像展示。”\r\r### 场景2：1张图片+文字需求\r- 自动标注“图1”为操作对象，重点补充“与原图匹配”的细节，示例：\r  用户需求：“图1是黑白老照片，想上色并修复划痕”  \r  你生成的提示词：“对图1的黑白老照片进行2项操作：①修复照片中的划痕、破损部分至完好无损；②为照片自然上色（肤色偏暖、衣物色彩符合时代质感），需保留老照片的复古质感，不夸张色彩饱和度，输出高清细节（修复痕迹不可见），适合打印纪念。”\r\r### 场景3：2张及以上图片+文字需求\r- 用“图X”“图Y”明确图片分工（如“图1是主体，图2是参考元素”），必加“比例一致”“元素融合”约束，示例：\r  用户需求：“图1是女孩，图2是裙子，想让女孩穿图2的裙子，背景换成海边”  \r  你生成的提示词：“给图1中的女孩换上图2的裙子（确保裙子与女孩身形贴合，不改变女孩发型、五官细节），同时将图1的背景替换为海边（保留原图的自然光方向，海边需有沙滩、浅海元素，不遮挡人物），输出需满足：裙子材质细节清晰、背景与人物自然融合、整体为高清写实摄影风格，可直接用于穿搭分享。”\r\r## 四、禁用与规避\r1. 不使用模糊表述（如“好看一点”“高级风格”），需转化为具体可执行的描述（如“增强对比度、提升色彩饱和度”“Vogue杂志海报质感”）；\r2. 不生成超过3条核心操作的提示词（避免Nano上下文过载），若用户需求复杂（如“换装+换背景+调角度”），需拆分为“分步骤生成，每次仅执行1项操作”的提示词；\r3. 若用户需求超出Nano能力（如“把照片转成像素画”），需在提示词中补充“优先保证主体轮廓准确，风格效果以写实为基础微调”，同时在提示词后附加“Nano非写实风格效果一般，建议重点关注主体细节”的友好提醒。\r\r请你严格按照以上规则，接收我的简单需求后，直接输出可复制的Nano提示词，无需额外解释。"
            },
            {
                "name": "照片增强",
                "brief": "This photo is very boring and plain. Enhance it!Increase the contrast, boost the colors, and improve the lighting to make it richer, crop and delete details that affect the composition"
            },
            {
                "name": "人像精修",
                "brief": "Repair skin blemishes and smooth the skin texture"
            },
            {
                "name": "老照片修复",
                "brief": "Enhance the resolution of this [old photo] and add the appropriate texture details, reinterpreting it with [modern photo]"
            },
            {
                "name": "平铺展示",
                "brief": "A flat lay photograph showing all the [prompt] involved in the photo."
            },
            {
                "name": "跨图穿戴",
                "brief": "The character in Figure 2 is wearing the [prompt] from Figure.Do not change the details of other parts of Figure 2"
            },
            {
                "name": "贴纸生成",
                "brief": "Help me turn the character into a white outline cartoon sticker similar to Figure 2. The character needs to be transformed into a cartoon style, and add a funny short phrase describing Figure 1."
            },
            {
                "name": "风格转换",
                "brief": "将[主体/场景]转换为[目标风格，如：高精度手办/等轴测三维图/3D渲染室内设计图]，（补充特征：手办需PVC材质+金属漆细节/三维图需简约可爱/渲染图提供3种材质方案），输出需（细节精致/专业摄影灯光展示/风格统一）。  "
            },
            {
                "name": "背景替换",
                "brief": "将[图X中的背景]替换为[新背景，如：天坛/西湖/现代写字楼天台夜景]，（或：将[图X中的A物品]替换为[图Y中的B物品]），需保证[主体]不变，新背景/物品与主体自然融合，突出主体/保留原图光线方向，呈现（逼真摄影感/电影般质感/光影过渡柔和/材质细节一致）。 "
            },
            {
                "name": "角度与姿势调整",
                "brief": "将[图X中的主体]调整为[具体角度/姿势，如：正面平视镜头/纯侧面转向左/高角度俯视/模仿图Y的动作]，需保持[主体核心特征，如：外貌/服饰/物体细节]不变，（补充要求：镜头自然/氛围感强/完整展示环境），确保（光影匹配原图/分辨率与清晰度一致/动作衔接自然）。 "
            },
            {
                "name": "逼真手办",
                "brief": "Please convert this photo into a highly detailed character model. Place in front of the model a delicate, colorful box featuring the printed image of the person from the photo. Behind the box, show a computer screen actively displaying the Blender modeling process. In front of the box, position the completed character model based on the provided photo, with the PVC texture clearly and realistically rendered. Set the entire scene in a bright, stylish indoor environment resembling a toy collector’s or hobbyist’s room—full of refined details, vibrant décor, and playful atmosphere. Ensure the lighting is crisp and luminous, highlighting both the model and its packaging."
            },
            {
                "name": "IP角色延展",
                "brief": "请根据图1中IP○角色形象生成符合其形象的IP场景图，保持角色特征,颜色和画风不变,有趣可爱，有故事性"
            },
            {
                "name": "IP表情延展",
                "brief": "请根据图1中IP角色形象生成符合其形象的表情包,要在同一张画面中,生成9个表情,"
            },
            {
                "name": "3d建模",
                "brief": "Use the provided photo as reference.Generate a high-fidelity 3D model in the look of a [3D-printed model] Preserve the object massing and key texture details, lightly stylized for a game. Render with realistic,physically-based lighting and shadows. Show a 45° top-down (isometric) view to emphasize depth. Define materials clearly,so it reads as a high-quality,game-engine-ready render: Pure white background."
            },
            {
                "name": "IP角色banner",
                "brief": "请根据图1中IP角色形象生成符合其形象的海报,一个奇幻森林场景,整体氛围神秘又温馨,色彩以深绿色的森林背景为主,搭配暖黄色的发光蘑菇和角色身上的橙黄色调,形成鲜明的冷暖对比,采用中景偏特写的镜头,将角色置于画面右侧,它蹲坐在一个发光的蘑菇上,左手抬起指向画面左上方,背景是茂密的森林,高大的树木林立,地面覆盖着绿色的苔藓和零星的小蘑菇,光感主要来自角色脚下的发光蘑菇,发出柔和的暖黄色光芒,照亮了角色的面部和周围的苔藓,森林中漂浮着许多黄色的光点,如同萤火虫般增添了梦幻感,整体光效柔和且具有层次感,营造出夜晚森林中温暖治愈的氛围."
            },
        ],
        "suffix": "Your response must consist of concise instruction ready for the image editing AI. Do not add any conversational text, explanations, or deviations; only the instructions."
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": ([preset["name"] for preset in cls.data.get("presets", [])], {
                    "default": "默认",
                    "height": 100,
                    "step": 1
                }),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("提示词",)
    FUNCTION = "get_preset"
    CATEGORY = "AI Chat/提示词预设"
    DESCRIPTION = "输出适用于 Nano 图像编辑的提示词预设。"

    @classmethod
    def get_brief_by_name(cls, name):
        for preset in cls.data.get("presets", []):
            if preset["name"] == name:
                return preset["brief"]
        return None

    def get_preset(cls, preset):
        brief_text = cls.get_brief_by_name(preset)
        if brief_text is None:
            raise ValueError(f"未知 Nano 预设：{preset}")
        brief = "The Brief:" + brief_text
        fullString = cls.data.get("prefix")+'\n'+brief+'\n'+cls.data.get("suffix")
        return (fullString,)

NODE_CLASS_MAPPINGS = {
    "NanoPreset": NanoPreset,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoPreset": "Nano 提示词预设",
}
