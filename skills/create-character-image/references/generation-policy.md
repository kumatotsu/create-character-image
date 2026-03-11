# Generation Policy (2026-03-11)

## Output Order

Always output in this order:
1. Structured markdown `Generation Instructions` (English)
2. Natural language prompt (English plain text)
3. User confirmation for image generation
4. Image generation execution
5. Image metadata (JSON)

If confirmation has not been given yet, emit the prompt artifacts, return `image_status: "awaiting_confirmation"` in metadata, and do not call the image API.

## Prompt Framework

Follow the official Nano Banana text-to-image formula first:

`[Subject] + [Action] + [Location/context] + [Composition] + [Style]`

Implementation rules for this skill:
- Start the natural prompt with a strong image-generation verb such as `Generate`.
- `Subject` must identify the character and stable appearance traits first.
- `Action` must describe the visible action or expression in observable language.
- `Location/context` must describe the environment concretely.
- `Composition` must specify framing, distance, angle, gaze, and safe-area expectations.
- `Style` must include Creative Director controls: lighting, camera/lens/focus, color grading or film stock, and materiality/texture.

Supporting directives required by this skill:
- `Edit Preservation`: lock identity traits and state exactly what may change.
- `Text Rendering and Localization`: either quote exact text requirements or explicitly forbid accidental text.
- `Constraint Notes`: include physical and wardrobe facts from Notion, use-case output constraints, and merged negative policy.

Rules derived from the official guide:
- Use explicit categories instead of keyword piles.
- Prefer concrete positive wording over vague negatives.
- If text must appear in the image, quote the exact string and name the font/design intent.
- If no text is required, say that no accidental signage, logos, or overlays should appear.
- Treat edits as tightly scoped changes; preserve everything else unless the request explicitly changes it.
- Keep aspect ratio explicit in the prompt and in metadata.
- Do not ask for multiple variants in a single request path; run separate requests instead.

## Input Normalization Schema

```json
{
  "character_id": "<required: character_id in Characters DB>",
  "use_case": "<required: X | Blog | LP | Print>",
  "scene": "<optional>",
  "expression": "<optional>",
  "angle": "<optional>",
  "gaze": "<optional>",
  "extra_constraints": "<optional>"
}
```

## Notion Database IDs

- Characters: `25fcbab97adf81d48605f9db9446161d`
- Face Profiles: `25fcbab97adf81f7b82ffe93661cc35a`
- Body Profiles: `25fcbab97adf81c3b106fa97c0b9014d`
- Outfit Profiles: `25fcbab97adf813e8c96d96ebb59cb43`

## Mandatory Query Flow

1. Characters query with `character_id` `equals`
2. Face Profiles query with `character` relation `contains CHAR_PAGE_ID`
3. Body Profiles query with `character` relation `contains CHAR_PAGE_ID`
4. Outfit Profiles query with `character` relation `contains CHAR_PAGE_ID`
5. Apply presets, negative policy, and tone presets

## Photo Presets

```yaml
- id: "default-photographic"
  use_cases: ["X", "Blog", "LP", "Print"]
  photo_keywords: "photorealistic, professional photography, sharp focus, detailed skin texture"
  color_temp_K: 5200
  exposure_ev: 0.3
  ISO_range: "100-400"
  aperture: "f/2.8"
  shutter_speed: "1/125s"
  focal_length_eq: "35mm"
  subject_occupancy: 0.6
  composition_rules: ["Rule of thirds"]
  palette: "Natural palette"

- id: "soft-studio"
  use_cases: ["LP"]
  photo_keywords: "ultra realistic photo, professional studio lighting, softbox lighting, high detail"
  color_temp_K: 5600
  exposure_ev: 0.0
  ISO_range: "100-200"
  aperture: "f/5.6-f/8"
  shutter_speed: "1/160s"
  focal_length_eq: "50mm"
  subject_occupancy: 0.65
  composition_rules: ["Centered", "Rule of thirds"]
  palette: "Soft neutral palette"

- id: "outdoor-golden-hour"
  use_cases: ["Blog", "X"]
  photo_keywords: "candid street photography, moment-in-time photo, beautiful lighting, lens flare, detailed, sharp"
  color_temp_K: 4800
  exposure_ev: 0.3
  ISO_range: "200-400"
  aperture: "f/2.8-f/4"
  shutter_speed: "1/200s"
  focal_length_eq: "35mm"
  subject_occupancy: 0.55
  composition_rules: ["Rule of thirds"]
  palette: "Warm golden palette"
```

## Resolution Map

```yaml
X:
  target_aspect: "1:1"
  generation_size_px: "1024x1024"
  delivery_format: "png"
  colorspace: "sRGB"
  framing_notes: "Keep the subject centered for square delivery."
Blog:
  target_aspect: "16:9"
  generation_size_px: "1536x1024"
  delivery_format: "png"
  colorspace: "sRGB"
  framing_notes: "Leave safe margins above and below the subject for a downstream 16:9 crop."
LP:
  target_aspect: "4:3"
  generation_size_px: "1536x1024"
  delivery_format: "png"
  colorspace: "sRGB"
  framing_notes: "Keep hands and key outfit details within a centered 4:3 safe area."
Print:
  target_aspect: "A4"
  generation_size_px: "1024x1536"
  delivery_format: "png"
  colorspace: "sRGB"
  framing_notes: "Compose vertically with extra headroom for an A4 portrait crop."
```

Use only OpenAI-supported generation sizes for `gpt-image-1`: `1024x1024`, `1536x1024`, `1024x1536`.

## Negative Policy and Tone

```yaml
Negative_policy:
  forbidden_words: ["cleavage", "exposure", "fetishistic", "see-through"]
  negative_prompt_boilerplate: ["portrait", "illustration", "artwork", "painting", "cgi", "3d", "unnatural hair color", "heavy makeup", "eccentric outfit", "short hair", "anime style"]
tone_presets:
  - name: neutral
    usage: ["all"]
  - name: soft
    usage: ["Blog"]
  - name: energetic
    usage: ["X", "LP"]
```

## Double Check

### Check 1: Prompt Assembly

Verify before image generation:
1. Do not output raw Notion API response.
2. Ensure `character_id` is queried with `equals`.
3. Ensure Face/Body/Outfit are all reflected in outputs.
4. Ensure the core formula sections `Subject`, `Action`, `Location/context`, `Composition`, and `Style` are present in both outputs.
5. Ensure the natural prompt starts with a strong image-generation verb.
6. Ensure `Style` includes lighting, camera/lens/focus, color grading or film stock, and materiality/texture.
7. Ensure `Edit Preservation` explicitly states what is locked and what may vary.
8. Ensure `Text Rendering and Localization` either quotes exact text or forbids accidental text.
9. Ensure negative policy integration is complete.
10. Ensure tone selection is suitable.
11. Ensure use-case resolution map uses OpenAI-supported generation sizes.
12. Ensure Generation Instructions and natural prompt are fully in English and fail fast if Japanese text is detected.

### Check 2: Output Package

Verify before final completion:
1. Ensure image file name format is `<character_id>_<use_case>_<YYYYMMDD-HHmmss>.png`.
2. Ensure Alt/Caption are descriptive.
3. Ensure Alt/Caption are fully in English and fail fast if Japanese text is detected.
4. Ensure `image_status: "awaiting_confirmation"` skips the image API.
5. Ensure the double-check results are recorded in metadata.
