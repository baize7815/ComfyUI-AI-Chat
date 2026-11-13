# Nano Banana Pro Image Editing & Multi-Image Fusion Rules

Follow these advanced rules whenever the user provides or references one or more input images for local editing, attribute modification, outpainting, or multi-image composition.

## 1. Attribute Disentanglement at Full Strength (属性解耦与防泄漏黄金法则)

Edit **only** the exact attribute(s) the user named at full, unmistakable strength, while holding all untargeted content at strict input fidelity.

### The "Name Without Repainting" Rule (只点名类别，绝不具体描写保留区外观)
- **Why**: To a native multimodal generation model, a detailed visual description of an untouched area reads like an instruction to regenerate it from scratch. The more concretely you describe the appearance of something you want to keep (e.g., `"keep her wavy chestnut hair, subtle smile, and the oak table behind her"`), the more likely the model will repaint and drift those features (Leakage).
- **How to Write**:
  - **Describe concretely ONLY what changes**: Give rich material, color, and lighting detail exclusively for the newly added or modified target.
  - **Lock untouched areas by category and role**: Use a single blanket preservation clause that names untouched elements by high-level category (`"while keeping the subject's facial identity, pose, existing lighting direction, and background environment completely unchanged"`).
  - **Identity Lock via Reference Pointer**: When preserving a person's face or a product's exact design from an input image, point directly to the image (`"strictly preserving the exact facial features, bone structure, and expression of the person in Image 1"`) rather than describing their eyes, nose, or face shape in words.

## 2. Operation Mode Templates

### Mode A: Visual Cue / Red-Box / Mask / Coordinate Local Edit
When the user wants to edit a specific region marked by a bounding box, scribble, mask, or coordinates:
- **Opening Template**:
  `Edit the uploaded image: Modify ONLY the region inside the red bounding box (or at normalized coordinates [ymin, xmin, ymax, xmax]) by replacing/adding [detailed target description with materiality and lighting integration]. Completely remove the red annotation box/lines so no border artifacts remain, and keep the subject's identity, surrounding objects, and background outside the marked region 100% unchanged.`

### Mode B: Single-Image Attribute / Outfit / Background Edit
When modifying clothing, material, weather, or background on a single image without visual boxes:
- **Opening Template**:
  `Edit the uploaded image: Replace [target item/background] with [detailed new item/environment, texture, and realistic contact shadows/reflections], while keeping [high-level category list: e.g., the person's facial identity, hairstyle, body posture, and foreground props] completely unchanged.`

### Mode C: Multi-Image Fusion & Character/Product Consistency (N >= 2)
Always index every input image explicitly (`Image 1`, `Image 2`, `Image 3`) and assign each image's exact role (Base Canvas vs. Identity/Material Source):
- **Scene Compositing (Putting Object/Person from Image 2 into Image 1)**:
  `Using Image 1 as the base scene canvas and Image 2 as the [subject/product] reference, place the [object/person] from Image 2 into [specific spatial position in Image 1]. Preserve the exact [facial identity / product silhouette, logo, and surface texture] from Image 2, adjust its scale, perspective, and cast shadows to match the ambient lighting of Image 1, and keep the rest of Image 1 unchanged.`
- **New Scene Generation from Multiple Identity Sources (e.g., Group Photo / New Shoot)**:
  `Using Image 1 and Image 2 strictly as identity references, create a new [medium & shot scale] scene showing the person from Image 1 on the left and the person from Image 2 on the right [doing action in environment]. Preserve each person's exact facial features and hairstyle from their respective reference image...`

### Mode D: Outpainting (扩图与画幅延伸)
When extending the canvas outward:
- Explicitly state `Outpaint and extend the uploaded image [left / right / upward / downward / on all sides] to a [target aspect ratio, e.g., 16:9 / 9:16] frame.`
- Describe what newly revealed architectural, environmental, or bodily elements seamlessly continue across the boundary while locking the original center frame unchanged.

## 3. In-Image Text Editing & Language Priority

When an edit adds, translates, or replaces visible text inside the image:
1. **Exact String in Quotes**: Always wrap the literal target characters in straight double quotes (`"..."`). Never summarize or abbreviate text that is meant to be legible.
2. **Typography & Surface Matching**: Specify that the new text matches the perspective warp, surface texture (e.g., embossed gold foil, neon tube, weathered paint), font weight, and color of the original signage unless instructed otherwise.
3. **Language Consistency**:
   - Follow the user's explicit target text or language instruction first.
   - If the user asks to add a title/label without specifying the language, match the dominant language already present inside the input image.
   - Keep quoted text strings monolingual (do not mix Chinese and English inside quotes unless explicitly requested).
