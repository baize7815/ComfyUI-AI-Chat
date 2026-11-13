---
name: low-res-image
description: "Analyze a low-resolution or blurry image and write one tailored English restoration prompt."
---
# Upscale Low-Res Image

Analyze user-uploaded low-resolution or blurry images by evaluating information retention and medium type, output one matched English restoration prompt for image-to-image models (such as Nano Banana).

## When to Use

- The user uploads a low-resolution, pixelated, compressed, or blurry image and asks to upscale, restore, or enhance it into high definition.
- The user asks for an image-to-image (or Nano Banana) HD restoration reverse prompt and parameter recommendations.
- The user needs one professional English enhancement prompt based on the uploaded reference image.

## Workflow

### Step 1: Inspect and Classify the Image

Evaluate the uploaded image across two dimensions before constructing the prompt:

1. **Information Retention Check**:

   - **Condition 1 (Base Information Intact)**: Although resolution is low, the subject edges, facial features, text outlines, and core materials remain distinguishable without requiring AI guesswork.
   - **Condition 2 (Base Information Lost)**: The image is severely blurred, facial features are melted into color blocks, limb details are missing, or text and signage are illegible, requiring semantic reconstruction.

2. **Medium Type Check (For Condition 1)**:

   - Classify the original image into one of three categories: **Photography (实拍照片)**, **2D Illustration & Anime (2D插画/二次元/水彩)**, or **3D & CG Render (3D与CG渲染)**.

### Step 2: Build the English Restoration Prompt

Select and assemble the English prompt strictly based on the classification from Step 1:

#### For Condition 1: Base Information Intact

Lock the composition and subject content strictly without adding new objects, and apply the material enhancement template matching the medium:

- **Photography (实拍照片)**:

  ```text
  Enhance the image while strictly preserving the subject's identity, layout, and background. Do not alter the geometry. Keep the exact same background. Improve clarity while retaining the original lighting and photographic character. Enhance real physical textures (skin pores, fabric threads, natural reflections) - NO plastic skin, NO AI smoothing. 4K resolution, highly detailed photorealism.
  ```

- **2D Illustration & Anime (2D插画/二次元/水彩)**:

  ```text
  Upscale and enhance the illustration while strictly preserving the original line art, character design, composition, and background. Do not convert to 3D or photorealism. Maintain the original artistic style (e.g., anime, watercolor, flat color). Enhance the brushstrokes, color blending, and linework clarity. Remove any pixelation or jpeg artifacts. 4K, masterpiece, official art, high-quality rendering.
  ```

- **3D & CG Render (3D与CG渲染)**:

  ```text
  Enhance the 3D render while strictly keeping the exact geometry, character models, and background. Do not convert to real-life photo. Improve the physically based rendering (PBR) materials. Improve visible material textures and edge clarity while preserving the original rendering style and lighting.
  ```

#### For Condition 2: Base Information Lost

Anchor the scene semantics first through reverse description, then append the structural reconstruction directives:

```text
[Scene Description]: <Write an accurate English description of the subject, pose, attire, props, and background environment inferred from the blurry image>
[Detail Reconstruction]: Based on the description, conservatively reconstruct missing details from the highly blurred base image without presenting uncertain identity or text as recovered facts. Fix any anatomical distortion. Reconstruct crisp textures and environmental lighting that make sense for the scene description. High quality, masterpiece, 8k resolution, intricate details.
```

### Step 3: Output

Return exactly one complete English restoration prompt as plain text, without analysis, parameters, code fences, headings, explanations, or claims that an image was generated. The input is provided by the node; do not call an image generation tool.

## Gotchas

- **Cross-Medium Style Drift**: Never apply photorealistic skin pore or camera prompts to 2D anime/illustrations or 3D renders, as doing so destroys the original 2D linework or CG aesthetic.
- **Unwanted Content Hallucination in Condition 1**: When base features are intact, do not invent new background elements or alter the subject's pose or expression.
- **Missing Scene Description in Condition 2**: Never leave the `[Scene Description]` placeholder generic; always write a concrete English description of the specific uploaded image before appending `[Detail Reconstruction]`.
- **Image Reference**: Write the restoration prompt for the supplied image; do not claim the image has already been enhanced.
