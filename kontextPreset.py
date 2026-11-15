class kontextPreset:
    data = {
        "prefix": "You are a creative prompt engineer. Your mission is to analyze the provided image and generate exactly 1 distinct image transformation *instructions*.",
        "presets": [
            # --- 所有预设均已按照官方指南进行重写和升级 ---
            {
                "name": "默认",
                "brief": "Please rewrite the following simple description into a prompt suitable for the kontext model based on the given rules.Language: Use EnglishThe rules are as follows:\n```\n## Flux Kontext Prompting Techniques\n### 1. Basic Modifications\n- Be simple & direct:\"Change the car color to red\"\n- Preserve style:\"Change to daytime while maintaining the same style of the painting\"\n\n### 2. Style Transfers\nPrinciples:\n- Name the style explicitly:\"Transform to Bauhaus art style\"\n- Describe the characteristics:\"Transform to oil painting with visible brushstrokes, thick paint texture\"\n- Keep the composition:\"Change to Bauhaus style while maintaining the original composition\"\n\n### 3. Character Consistency\nFramework:\n- Be specific:\"The woman with short black hair\"\n- Preserve features:\"while maintaining the same facial features, hairstyle, and expression\"\n- Edit in steps: change background first, then action\n\n### 4. Text Editing\n- Use quotation marks:\"Replace 'joy' with 'BFL'\"\n- Keep formatting:\"Replace text while maintaining the same font style\"\n\n## Troubleshooting Common Issues\n### Character changes too drastically\n❌ Wrong:\"Transform the person into a Viking\"\n✅ Correct:\"Change the clothes to be a viking warrior while preserving facial features\"\n\n### Composition position shifts\n❌ Wrong:\"Put him on a beach\"\n✅ Correct:\"Change the background to a beach while keeping the person in the exact same position, scale, and pose\"\n\n### Style not applied accurately\n❌ Wrong:\"Make it a sketch\"\n✅ Correct:\"Convert to pencil sketch with natural graphite lines, cross-hatching, and visible paper texture\"\n\n## Core Principles\n1. Be Specific – use exact descriptions, avoid vague words\n2. Edit in Steps – break complex edits into simple steps\n3. Explicitly Preserve – state what should stay unchanged\n4. Verb Choice – use 'change', 'replace', not 'transform'\n\n## Best-Practice Templates\n- Object modification:\"Change [object] to [new state], keep [content to preserve] unchanged\"\n- Style transfer:\"Transform to [specific style], while maintaining [composition/character/other] unchanged\"\n- Background swap:\"Change the background to [new background], keep the subject in the exact same position and pose\"\n- Text edit:\"Replace [original text] with [new text], maintain the same font style\"\n\nRemember: The more specific, the better. Kontext excels at understanding detailed instructions and maintaining consistency.```"
            },
            {
                "name": "情境深度融合",
                "brief": "The provided image is a composite with a head and body from drastically different contexts (lighting, style, condition). Your mission is to generate instructions for a complete narrative and physical transformation of the head to flawlessly match the body and scene. The instructions must guide the AI to: 1. **Cinematic Re-Lighting**: Describe in vivid detail the scene's light sources (color, direction, hardness) and how this light should sculpt the head's features with new, appropriate shadows and highlights. 2. **Contextual Storytelling**: Instruct to add physical evidence of the scene's story onto the head, such as grime from a battle, sweat from exertion, or rain droplets from a storm. 3. **Color Grading Unification**: Detail how to apply the scene's specific color grade (e.g., cool desaturated tones, warm golden hour hues) to the head. 4. **Asset & Hair Adaptation**: Command the modification or removal of out-of-place elements (like clean jewelry in a gritty scene) and the restyling of the hair to fit the environment (e.g., messy, windblown, wet). 5. **Flawless Final Integration**: As the final step, describe the process of blending the neckline to be completely invisible, ensuring a uniform film grain and texture across the entire person."
            },
            {
                "name": "无痕融合",
                "brief": "This image is a composite with minor inconsistencies between the head and body. Your task is to generate instructions for a subtle but master-level integration. Focus on creating a photorealistic and utterly convincing final image. The instructions should detail: 1. **Micro-Lighting Adjustment**: Fine-tune the lighting and shadows around the neck and jawline to create a perfect match. 2. **Skin Tone & Texture Unification**: Describe the process of unifying the skin tones for a seamless look, and more importantly, harmonizing the micro-textures like pores, fine hairs, and film grain across the blended area. 3. **Edge Blending Perfection**: Detail how to create an invisible transition at the neckline, making it appear as if it was never separate."
            },
            {
                "name": "移除万物",
                "brief": "Remove {{主体}} completely from the image. Provide different levels of removal of related elements (supports, structures, similar items..etc)."
            },
            {
                "name": "移除水印",
                "brief": "Describe the task of removing all text from the image as a meticulous restoration project. 'Carefully and seamlessly remove all text, logos, and lettering from the image. The goal is to reconstruct the underlying surfaces and textures so perfectly that there is no hint that text ever existed there.'"
            },
            {
                "name": "产品精修",
                "brief": "Make the picture high-definition, the smooth surface of the {{主体}} without any scratches or stains, and the light and shadow become studio lights, very sharp light and shadows, the overall texture reaches the style of product photography, and the text and overall composition must be kept clear and visible and unchanged."
            },
            {
                "name": "工作室产品摄影",
                "brief": "Re-imagine this image as a high-end commercial product photograph for a luxury catalog. Describe a clean, professional setting. The instruction should specify: 1. **Studio Lighting**: Detail a sophisticated lighting setup (e.g., three-point lighting with a softbox key light, a rim light for separation, and a fill light to soften shadows). 2. **Composition**: Describe a clean, minimalist composition on a seamless background or in a luxury lifestyle setting. 3. **Product Focus**: Emphasize capturing crisp details, perfect textures, and an aspirational mood."
            },
            {
                "name": "产品摄影",
                "brief": "Turn this image into the style of a professional product photo. Describe a variety of scenes (simple packshot or the item being used), so that it could show different aspects of the item in a highly professional catalog. Suggest a variety of scenes, light settings and camera angles/framings, zoom levels, etc. Suggest at least 1 scenario of how the item is used."
            },
            {
                "name": "重新布光",
                "brief": "Completely transform the mood and story of the image by proposing a new, cinematic lighting scheme. Describe a specific lighting style linked to a genre or mood. For example: 'Relight the scene with Film Noir aesthetics: hard, single-source key light creating deep shadows and high contrast,' or 'Relight with the warmth of a magical Golden Hour: soft, golden light from a low angle, wrapping around the subject and creating long, gentle shadows.'"
            },
            {
                "name": "材质置换",
                "brief": "Re-imagine the main subject as a masterfully crafted sculpture made from an unexpected material, keeping their pose intact. Describe the new material's properties in detail. For example: 'Transform the subject into a statue carved from a single piece of dark, polished obsidian. Describe its glossy, reflective surface, how it catches the light, and the subtle, natural imperfections within the stone.'"
            },
            {
                "name": "移动镜头",
                "brief": "Propose a dramatic and purposeful camera movement that reveals a new perspective or emotion in the scene. Instead of a simple change, describe the *type* of shot and its *narrative purpose*. For example, 'Change to a dramatic low-angle shot from the ground, making the subject appear heroic and monumental against the sky,' or 'Switch to a dizzying Dutch angle shot, tilting the horizon to create a sense of unease and disorientation'."
            },
            {
                "name": "画面缩放",
                "brief": "Describe a specific zoom action that serves a narrative purpose. Propose either: 1. **A dramatic 'push-in' (zoom in)**: 'Slowly push in on the subject's eyes to reveal a subtle, hidden emotion.' or 2. **A revealing 'pull-out' (zoom out)**: 'Pull the camera back to reveal a surprising or vast new element in the environment that re-contextualizes the subject's situation.'"
            },
            {
                "name": "图像上色",
                "brief": "Describe a specific artistic style for colorizing a black and white image. Go beyond simple colorization. For example: 'Colorize this image with the vibrant, high-contrast, and slightly surreal palette of the Technicolor films from the 1950s,' or 'Apply a muted, melancholic color palette with desaturated blues and earthy tones, reminiscent of a modern independent film.'"
            },
            {
                "name": "电影海报",
                "brief": "Transform the image into a compelling movie poster for a specific, imagined film genre. Describe the full poster concept: 1. **Genre & Title**: Invent a movie title and genre (e.g., Sci-Fi Thriller: 'ECHOES OF TOMORROW'). 2. **Visual Style**: Describe how to treat the image (e.g., 'apply a gritty, high-contrast filter'). 3. **Typography & Text**: Instruct to add a stylized title, a dramatic tagline (e.g., 'The future is listening.'), and other elements like actor names and release date."
            },
            {
                "name": "艺术风格模仿",
                "brief": "Repaint the entire image in the unmistakable style of a famous art movement. Be descriptive and evocative. For example: 'Transform the image into a Post-Impressionist painting in the style of Van Gogh, using thick, swirling brushstrokes (impasto), vibrant, emotional colors, and a dynamic sense of energy and movement in every element.'"
            },
            {
                "name": "微缩世界",
                "brief": "Convert the entire scene into a charming and highly detailed miniature model world, as if viewed through a tilt-shift lens. Describe the visual effects needed: 'Apply a very shallow depth of field to blur the top and bottom of the image, making the scene look tiny. Sharpen the details and boost the color saturation to enhance the artificial, toy-like appearance of all subjects and objects.'"
            },
            {
                "name": "蓝图视角",
                "brief": "Convert the image into a detailed and aesthetically pleasing technical blueprint. Describe the visual transformation: 'Change the background to a classic cyanotype-blue. Redraw the main subject and key objects using clean, white, schematic outlines. Overlay the image with fictional measurement lines, annotations, and technical callouts to complete the architectural drawing effect.'"
            },
            {
                "name": "添加倒影",
                "brief": "Introduce a new, reflective surface into the scene to create a more dynamic and compelling composition. Describe the placement and quality of the reflection. For example: 'After a rain shower, the street is now covered in a thin layer of water, creating a stunning, mirror-like reflection of the subject and the moody, illuminated sky above. The reflection should be slightly distorted by ripples in the water.'"
            },
            {
                "name": "像素艺术",
                "brief": "Deconstruct the image into the charming, retro aesthetic of 16-bit era pixel art. Describe the technical and artistic constraints: 'Reduce the entire image to a limited color palette of 64 colors. Redraw all shapes and subjects with sharp, aliased pixel edges. Use dithering patterns to create gradients and shading, capturing the authentic look and feel of a classic Super Nintendo game.'"
            },
            {
                "name": "铅笔手绘",
                "brief": "You are a master of pencil sketching. Write prompt words to transform the picture into a pencil sketch style based on the image content. The description needs to be precise and detailed, and avoid describing content unrelated to the task."
            }
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
    CATEGORY = "🫧 AI Chat/提示词预设"
    DESCRIPTION = "输出适用于 Flux Kontext 的图像编辑提示词预设。"

    @classmethod
    def get_brief_by_name(cls, name):
        for preset in cls.data.get("presets", []):
            if preset["name"] == name:
                return preset["brief"]
        return None

    def get_preset(cls, preset):
        brief_text = cls.get_brief_by_name(preset)
        if brief_text is None:
            raise ValueError(f"未知 Kontext 预设：{preset}")
        brief = "The Brief:" + brief_text
        fullString = cls.data.get("prefix")+'\n'+brief+'\n'+cls.data.get("suffix")
        return (fullString,)

NODE_CLASS_MAPPINGS = {
    "kontextPreset": kontextPreset,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "kontextPreset": "Kontext 提示词预设",
}
