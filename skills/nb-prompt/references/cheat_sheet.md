# Nano Banana Pro Vocabulary & Parameter Cheat Sheet

Quick vocabulary lookups for composing precise prompts aligned with Nano Banana Pro's visual semantic space.

## 1. Medium & Style Vocabulary (Always Declare First)

| Category | Recommended Terms | Cross-Contamination Ban |
| :--- | :--- | :--- |
| **Photography** | cinematic photograph, editorial fashion portrait, documentary street shot, macro close-up, tilt-shift, Kodak Portra 400, Fujifilm Pro 400H, 35mm / 85mm f/1.8 | Never use brush strokes, vector lines, or cel-shading. |
| **2D Illustration & Anime** | flat-vector illustration, wet-on-wet watercolor, crisp ink linework, cel-shaded anime frame, thick impasto oil painting, gouache storybook, woodcut print | **Ban** camera lenses (`85mm`), aperture (`f/1.4`), skin pores, and photorealistic bokeh. |
| **Digital & 3D Render** | isometric 3D diorama, Unreal Engine 5 render, Octane Render, Blender Cycles, claymation miniature, stylized PBR character model | Specify shader channels (subsurface scattering, anisotropic metal, micro-roughness). |
| **Graphic Design & UI** | Swiss grid poster, editorial magazine spread, minimalist brand identity sheet, infographic layout, high-contrast typographic cover | Specify negative space ratio, grid alignment, and exact typography hierarchy. |

## 2. Materials & Physical Textures (Noun + Materiality)

Always pair objects with concrete surface materiality rather than bare nouns or vague words like "high quality":

- **Metals**: brushed stainless steel, anodized matte aluminum, tarnished antique brass, hammered copper, cast iron with subtle patina, specular chrome.
- **Glass & Liquids**: frosted borosilicate glass, fluted ribbed glass, leaded crystal with caustic refraction, fine condensation droplets, glossy ceramic glaze.
- **Fabrics & Wearables**: coarse unbleached linen, heavy ribbed cotton knit, distressed selvedge denim, supple grained lambskin leather, sheer silk organza, houndstooth wool tweed.
- **Surfaces & Architecture**: weathered teak wood grain, board-formed exposed concrete, honed travertine marble, wet cobblestone with specular puddles, warm terracotta tiles.
- **Paper & Print**: matte cotton rag paper with visible fiber, high-gloss UV-coated cardstock, translucent vellum overlay, aged parchment with deckled edges.

## 3. Spatial & Positional Phrases (For "Walk the Frame")

When composing complex scenes, posters, or multi-region layouts, distribute 8 to 12 positional anchors across all quadrants so objects do not cluster solely in the center:

```text
[in the upper-left corner]   [spanning across the top band]   [in the upper-right corner]
[along the far left edge]    [centered in the midground]      [along the far right edge]
[in the lower-left foreground] [across the lower third base]  [tucked into the lower-right corner]
```

- **Depth & Relative Placement**: `in the immediate foreground`, `receding softly into the background`, `directly in front of`, `partially occluded behind`, `angled diagonally toward the viewer`, `flanking both sides of`.
- **Two Traversal Modes**:
  - **Single-Subject Frame (Portrait / Product Close-up)**: Walk from background drop-off -> subject pose & placement -> head/face expression -> garment/surface materiality -> held props -> edge environment.
  - **Multi-Region Frame (Poster / UI / Infographic / Wide Scene)**: Walk systematically by zone:
    1. Base background surface & color palette.
    2. Top band (header bar, main title, sky/ceiling).
    3. Main body from left -> center -> right.
    4. Bottom band (footer, base row, foreground ground plane).

## 4. Lighting & Color Descriptors

Give lighting its own dedicated clause specifying source, direction, quality, and shadow behavior:

- **Natural Light**: soft diffused overcast daylight through a left window, harsh midday sunlight casting crisp short shadows, warm golden-hour rim light from a low angle, cool blue twilight ambient glow.
- **Studio & Interior**: three-point studio lighting with a large diffused key softbox, sharp rim light separating the hair and shoulders from the dark backdrop, warm tungsten pendant glow, single dramatic chiaroscuro spotlight.
- **Atmospheric**: volumetric sunbeams (god rays) slicing through morning mist, neon magenta and cyan spill reflecting off damp pavement, warm flickering candlelight illuminating one side of the face.
- **Color Modifiers**: Never use bare color names (`blue`, `red`, `white`). Pair every color with a tone/material modifier (`deep navy`, `muted sage olive`, `warm alabaster cream`, `burnt terracotta`, `dusty rose`, `charcoal slate`) and optionally anchor key brand colors with `#HEX` codes.

## 5. Native Aspect Ratio & Scenario Matrix

Keep aspect ratios in the parameter recommendation section (never write pixel dimensions like `1920x1080` inside the English prose):

| Target Scenario | Recommended Ratio | Notes |
| :--- | :--- | :--- |
| Standard Landscape / Photography / Group Shot | `3:2` | Classic horizontal framing |
| Standard Portrait / Poster / Fashion Editorial | `2:3` | Classic vertical framing |
| Xiaohongshu / Social Portrait / Editorial Card | `3:4` | Balanced vertical social feed ratio |
| Tablet / Classic Frame / Presentation Card | `4:3` | Balanced horizontal frame |
| Square Avatar / Icon / Album Cover / 2x2 Grid | `1:1` | Centered symmetrical compositions |
| Desktop Wallpaper / Video Thumbnail / Slide | `16:9` | Wide horizontal framing |
| Mobile Wallpaper / Reels / Stories / Tall Banner | `9:16` | Full vertical mobile screen |
| Cinematic Widescreen / Ultra-Wide Scene | `21:9` | Anamorphic film look |
