# Generation Policy (2025-09-12)

## Output Order

Always output in this order:
1. Structured markdown `Generation Instructions` (English)
2. Natural language prompt (English plain text)
3. User confirmation for image generation
4. Image generation execution
5. Image metadata (JSON)

If confirmation has not been given yet, emit the prompt artifacts, return `image_status: "awaiting_confirmation"` in metadata, and do not call the image API.

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

## Self Check

1. Do not output raw Notion API response.
2. Ensure `character_id` is queried with `equals`.
3. Ensure Face/Body/Outfit are all reflected in outputs.
4. Ensure negative policy integration is complete.
5. Ensure tone selection is suitable.
6. Ensure use-case resolution map uses OpenAI-supported generation sizes.
7. Ensure image file name format is `<character_id>_<use_case>_<YYYYMMDD-HHmmss>.png`.
8. Ensure Alt/Caption are descriptive.
9. Ensure Generation Instructions, natural prompt, alt text, and caption are fully in English and fail fast if Japanese text is detected.
