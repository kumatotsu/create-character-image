#!/usr/bin/env python3
"""
Notion-driven character image pipeline.

Flow:
1) Load normalized request JSON
2) Query Notion databases (or load mock pages)
3) Build Generation Instructions (English markdown)
4) Build natural language prompt (English text)
5) Optionally generate image via OpenAI Images API
6) Emit image metadata JSON
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request


NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

DATABASE_IDS = {
    "characters": "25fcbab97adf81d48605f9db9446161d",
    "face_profiles": "25fcbab97adf81f7b82ffe93661cc35a",
    "body_profiles": "25fcbab97adf81c3b106fa97c0b9014d",
    "outfit_profiles": "25fcbab97adf813e8c96d96ebb59cb43",
}

PHOTO_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "default-photographic",
        "label": "Default Photographic",
        "use_cases": ["X", "Blog", "LP", "Print"],
        "photo_keywords": (
            "photorealistic, professional photography, sharp focus, "
            "detailed skin texture"
        ),
        "color_temp_K": 5200,
        "exposure_ev": 0.3,
        "ISO_range": "100-400",
        "aperture": "f/2.8",
        "shutter_speed": "1/125s",
        "focal_length_eq": "35mm",
        "subject_occupancy": 0.6,
        "composition_rules": ["Rule of thirds"],
        "palette": "Natural palette",
    },
    {
        "id": "soft-studio",
        "label": "Soft Studio (LP)",
        "use_cases": ["LP"],
        "scene_suggestion": "Indoor, white seamless background, frontal composition",
        "photo_keywords": (
            "ultra realistic photo, professional studio lighting, "
            "softbox lighting, high detail"
        ),
        "color_temp_K": 5600,
        "exposure_ev": 0.0,
        "ISO_range": "100-200",
        "aperture": "f/5.6-f/8",
        "shutter_speed": "1/160s",
        "focal_length_eq": "50mm",
        "subject_occupancy": 0.65,
        "composition_rules": ["Centered", "Rule of thirds"],
        "palette": "Soft neutral palette",
    },
    {
        "id": "outdoor-golden-hour",
        "label": "Outdoor Golden Hour (Blog/X)",
        "use_cases": ["Blog", "X"],
        "scene_suggestion": "Outdoor, warm sunset light, soft backlight",
        "photo_keywords": (
            "candid street photography, moment-in-time photo, beautiful lighting, "
            "lens flare, detailed, sharp"
        ),
        "color_temp_K": 4800,
        "exposure_ev": 0.3,
        "ISO_range": "200-400",
        "aperture": "f/2.8-f/4",
        "shutter_speed": "1/200s",
        "focal_length_eq": "35mm",
        "subject_occupancy": 0.55,
        "composition_rules": ["Rule of thirds"],
        "palette": "Warm golden palette",
    },
]

SUPPORTED_IMAGE_SIZES = {"1024x1024", "1536x1024", "1024x1536"}

RESOLUTION_MAP = {
    "X": {
        "target_aspect": "1:1",
        "generation_size_px": "1024x1024",
        "delivery_format": "png",
        "colorspace": "sRGB",
        "framing_notes": "Keep the subject centered for square delivery.",
    },
    "Blog": {
        "target_aspect": "16:9",
        "generation_size_px": "1536x1024",
        "delivery_format": "png",
        "colorspace": "sRGB",
        "framing_notes": "Leave safe margins above and below the subject for a downstream 16:9 crop.",
    },
    "LP": {
        "target_aspect": "4:3",
        "generation_size_px": "1536x1024",
        "delivery_format": "png",
        "colorspace": "sRGB",
        "framing_notes": "Keep hands and key outfit details within a centered 4:3 safe area.",
    },
    "Print": {
        "target_aspect": "A4",
        "generation_size_px": "1024x1536",
        "delivery_format": "png",
        "colorspace": "sRGB",
        "framing_notes": "Compose vertically with extra headroom for an A4 portrait crop.",
    },
}

NEGATIVE_POLICY = {
    "forbidden_words": ["cleavage", "exposure", "fetishistic", "see-through"],
    "negative_prompt_boilerplate": [
        "portrait",
        "illustration",
        "artwork",
        "painting",
        "cgi",
        "3d",
        "unnatural hair color",
        "heavy makeup",
        "eccentric outfit",
        "short hair",
        "anime style",
    ],
}

TONE_PRESETS = {
    "neutral": {"description": "Natural and neutral expression"},
    "soft": {"description": "Soft and gentle tone"},
    "energetic": {"description": "Bright and energetic tone"},
}

DEFAULT_TONE_BY_USE_CASE = {
    "Blog": "soft",
    "X": "energetic",
    "LP": "energetic",
    "Print": "neutral",
}

REQ_KEYS = {"character_id", "use_case"}


@dataclass
class ProfileBundle:
    character_page: Dict[str, Any]
    face_page: Dict[str, Any]
    body_page: Dict[str, Any]
    outfit_page: Dict[str, Any]


def fail(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def http_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        fail(f"HTTP {exc.code} {url}: {err_body}")
    except error.URLError as exc:
        fail(f"Request failed for {url}: {exc}")
    return {}


def rich_text_to_str(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    items = prop.get("rich_text") or []
    parts: List[str] = []
    for item in items:
        plain = item.get("plain_text")
        if plain:
            parts.append(str(plain).strip())
    return " ".join([p for p in parts if p]).strip()


def title_to_str(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    items = prop.get("title") or []
    parts: List[str] = []
    for item in items:
        plain = item.get("plain_text")
        if plain:
            parts.append(str(plain).strip())
    return " ".join([p for p in parts if p]).strip()


def select_to_str(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    sel = prop.get("select")
    if isinstance(sel, dict):
        return str(sel.get("name") or "").strip()
    return ""


def multi_select_to_list(prop: Optional[Dict[str, Any]]) -> List[str]:
    if not prop:
        return []
    values = prop.get("multi_select") or []
    out: List[str] = []
    for item in values:
        name = str(item.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def number_to_str(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    value = prop.get("number")
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


def relation_ids(prop: Optional[Dict[str, Any]]) -> List[str]:
    if not prop:
        return []
    rel = prop.get("relation") or []
    out: List[str] = []
    for item in rel:
        page_id = str(item.get("id") or "").strip()
        if page_id:
            out.append(page_id)
    return out


def extract_skin_tone(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    as_select = select_to_str(prop)
    if as_select:
        return as_select
    return rich_text_to_str(prop)


def contains_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text))


def validate_english_only_fields(fields: Dict[str, str]) -> None:
    violations = [label for label, text in fields.items() if contains_japanese(text)]
    if violations:
        fail(
            "The following fields must be English-only: "
            + ", ".join(sorted(violations))
        )


def merge_negative_constraints(body_neg: str, outfit_neg: str) -> Dict[str, Any]:
    return {
        "forbidden_words": NEGATIVE_POLICY["forbidden_words"],
        "style_exclusions": NEGATIVE_POLICY["negative_prompt_boilerplate"],
        "body_constraints": body_neg.strip(),
        "outfit_constraints": outfit_neg.strip(),
    }


def build_negative_line(negative: Dict[str, Any]) -> str:
    parts: List[str] = []
    fw = negative.get("forbidden_words") or []
    sx = negative.get("style_exclusions") or []
    body_c = negative.get("body_constraints") or ""
    outfit_c = negative.get("outfit_constraints") or ""
    if fw:
        parts.append("forbidden words: " + ", ".join(fw))
    if sx:
        parts.append("style exclusions: " + ", ".join(sx))
    if body_c:
        parts.append("body constraints: " + body_c)
    if outfit_c:
        parts.append("outfit constraints: " + outfit_c)
    return " | ".join(parts)


def join_non_empty(parts: List[str], sep: str = ", ") -> str:
    return sep.join([part for part in parts if part])


def sentence_fragment(text: str, fallback: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    return cleaned.rstrip(".!?")


def validate_resolution_config(use_case: str) -> Dict[str, Any]:
    resolution = RESOLUTION_MAP[use_case]
    size_px = resolution["generation_size_px"]
    if size_px not in SUPPORTED_IMAGE_SIZES:
        fail(f"Unsupported OpenAI image size configured for {use_case}: {size_px}")
    return resolution


def choose_preset(use_case: str) -> Dict[str, Any]:
    preferred: Dict[str, str] = {"LP": "soft-studio", "Blog": "outdoor-golden-hour", "X": "outdoor-golden-hour"}
    preferred_id = preferred.get(use_case)
    if preferred_id:
        for preset in PHOTO_PRESETS:
            if preset["id"] == preferred_id:
                return preset
    for preset in PHOTO_PRESETS:
        if use_case in preset["use_cases"]:
            return preset
    return PHOTO_PRESETS[0]


def notion_headers(notion_api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def query_database(
    notion_api_key: str,
    database_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{NOTION_BASE_URL}/databases/{database_id}/query"
    return http_json("POST", url, notion_headers(notion_api_key), payload)


def query_character_page(notion_api_key: str, character_id: str) -> Dict[str, Any]:
    payload = {
        "filter": {
            "property": "character_id",
            "rich_text": {"equals": character_id},
        },
        "sorts": [
            {"property": "updated_at", "direction": "descending"},
            {"timestamp": "last_edited_time", "direction": "descending"},
        ],
        "page_size": 1,
    }
    result = query_database(notion_api_key, DATABASE_IDS["characters"], payload)
    rows = result.get("results") or []
    if not rows:
        fail(f"Character not found by character_id equals: {character_id}")
    return rows[0]


def query_related_profile(
    notion_api_key: str,
    database_id: str,
    char_page_id: str,
) -> Dict[str, Any]:
    payload = {
        "filter": {
            "property": "character",
            "relation": {"contains": char_page_id},
        },
        "sorts": [
            {"property": "updated_at", "direction": "descending"},
            {"timestamp": "last_edited_time", "direction": "descending"},
        ],
        "page_size": 1,
    }
    result = query_database(notion_api_key, database_id, payload)
    rows = result.get("results") or []
    if rows:
        return rows[0]

    fail(f"Related profile not found in database {database_id} for character page {char_page_id}")
    return {}


def load_request_json(request_json_path: Path) -> Dict[str, Any]:
    if not request_json_path.exists():
        fail(f"request json not found: {request_json_path}")
    payload = json.loads(request_json_path.read_text(encoding="utf-8"))
    missing = [k for k in REQ_KEYS if not payload.get(k)]
    if missing:
        fail(f"request json is missing required keys: {', '.join(missing)}")
    use_case = payload.get("use_case")
    if use_case not in RESOLUTION_MAP:
        fail("use_case must be one of X, Blog, LP, Print")
    return payload


def load_mock_bundle(mock_data_path: Path) -> ProfileBundle:
    if not mock_data_path.exists():
        fail(f"mock data not found: {mock_data_path}")
    raw = json.loads(mock_data_path.read_text(encoding="utf-8"))
    required = ["character_page", "face_page", "body_page", "outfit_page"]
    for key in required:
        if key not in raw:
            fail(f"mock data must include: {', '.join(required)}")
    return ProfileBundle(
        character_page=raw["character_page"],
        face_page=raw["face_page"],
        body_page=raw["body_page"],
        outfit_page=raw["outfit_page"],
    )


def fetch_profiles(
    notion_api_key: Optional[str],
    req: Dict[str, Any],
    mock_data_path: Optional[Path] = None,
) -> ProfileBundle:
    if mock_data_path:
        return load_mock_bundle(mock_data_path)
    if not notion_api_key:
        fail("NOTION_API_KEY is required unless --mock-data is provided")

    character_page = query_character_page(notion_api_key, req["character_id"])
    char_page_id = character_page.get("id")
    if not char_page_id:
        fail("character page has no id")
    face_page = query_related_profile(
        notion_api_key,
        DATABASE_IDS["face_profiles"],
        char_page_id,
    )
    body_page = query_related_profile(
        notion_api_key,
        DATABASE_IDS["body_profiles"],
        char_page_id,
    )
    outfit_page = query_related_profile(
        notion_api_key,
        DATABASE_IDS["outfit_profiles"],
        char_page_id,
    )
    return ProfileBundle(
        character_page=character_page,
        face_page=face_page,
        body_page=body_page,
        outfit_page=outfit_page,
    )


def compose_generation_instructions(
    req: Dict[str, Any],
    bundle: ProfileBundle,
    tone_name: str,
) -> Tuple[str, Dict[str, Any]]:
    preset = choose_preset(req["use_case"])
    resolution = validate_resolution_config(req["use_case"])

    c_props = bundle.character_page.get("properties", {})
    f_props = bundle.face_page.get("properties", {})
    b_props = bundle.body_page.get("properties", {})
    o_props = bundle.outfit_page.get("properties", {})

    age = number_to_str(c_props.get("age")) or "N/A"
    nationality = select_to_str(c_props.get("nationality")) or rich_text_to_str(c_props.get("nationality")) or "Japanese"
    scene = str(req.get("scene") or "").strip() or "N/A"
    expression = str(req.get("expression") or "").strip() or "N/A"
    angle = str(req.get("angle") or "").strip() or "N/A"
    gaze = str(req.get("gaze") or "").strip() or "N/A"
    extra_constraints = str(req.get("extra_constraints") or "").strip() or "N/A"

    body_negative = rich_text_to_str(b_props.get("negative_constraints"))
    outfit_negative = rich_text_to_str(o_props.get("negative_constraints"))
    negative = merge_negative_constraints(body_negative, outfit_negative)

    md = f"""# Generation Instructions

## Meta Information
- **Character ID**: {req["character_id"]}
- **Nationality**: {nationality}
- **Age**: {age}
- **Purpose**: {req["use_case"]}

## Scene
- **Situation**: {scene}
- **Expression**: {expression}
- **Angle**: {angle}
- **Gaze**: {gaze}
- **Other Constraints**: {extra_constraints}

## Tone
- **Name**: {tone_name}
- **Description**: {TONE_PRESETS[tone_name]["description"]}

## Facial Description
- **Bangs**: {rich_text_to_str(f_props.get("bangs")) or "N/A"}
- **Eyebrows**: {rich_text_to_str(f_props.get("eyebrows")) or "N/A"}
- **Eyes**: {rich_text_to_str(f_props.get("eyes")) or "N/A"}
- **Nose**: {rich_text_to_str(f_props.get("nose")) or "N/A"}
- **Mouth**: {rich_text_to_str(f_props.get("mouth")) or "N/A"}
- **Jawline**: {select_to_str(f_props.get("jawline")) or "N/A"}
- **Hairstyle**: {select_to_str(f_props.get("hair_style")) or "N/A"}
- **Hair Color**: {select_to_str(f_props.get("hair_color")) or "N/A"}
- **Skin Tone**: {extract_skin_tone(f_props.get("skin_tone")) or "N/A"}
- **Golden Ratio**: {rich_text_to_str(f_props.get("golden_ratio")) or "N/A"}

## Body Description
- **Height**: {number_to_str(b_props.get("height_cm")) or "N/A"} cm
- **Height Tolerance**: {number_to_str(b_props.get("height_tolerance")) or "N/A"} cm
- **Body Type**: {select_to_str(b_props.get("body_type")) or "N/A"}
- **Bust Size**: {select_to_str(b_props.get("bust_size")) or "N/A"}
- **Proportions Notes**: {rich_text_to_str(b_props.get("proportions_notes")) or "N/A"}
- **Default Age Range**: {select_to_str(b_props.get("default_age_range")) or "N/A"}

## Clothing
- **Style Theme**: {select_to_str(o_props.get("style_theme")) or "N/A"}
- **Garments**: {", ".join(multi_select_to_list(o_props.get("garments"))) or "N/A"}
- **Color Palette**: {", ".join(multi_select_to_list(o_props.get("color_palette"))) or "N/A"}
- **Accessories**: {", ".join(multi_select_to_list(o_props.get("accessories"))) or "N/A"}
- **Modesty Level**: {select_to_str(o_props.get("modesty_level")) or "N/A"}

## Shooting Conditions
- **Atmosphere**: {preset["photo_keywords"]}
- **Camera**:
  - **focal_length**: {preset["focal_length_eq"]}
  - **aperture**: {preset["aperture"]}
  - **shutter_speed**: {preset["shutter_speed"]}
- **Lighting**:
  - **color_temp**: {preset["color_temp_K"]}
  - **exposure**: {preset["exposure_ev"]}
  - **ISO**: {preset["ISO_range"]}
- **Composition**:
  - **rules**: {", ".join(preset["composition_rules"])}
  - **subject_occupancy**: {preset["subject_occupancy"]}
- **Color**:
  - **palette**: {preset["palette"]}
- **Output**:
  - **target_aspect**: {resolution["target_aspect"]}
  - **generation_size**: {resolution["generation_size_px"]}
  - **format**: {resolution["delivery_format"]}
  - **colorspace**: {resolution["colorspace"]}
  - **framing_notes**: {resolution["framing_notes"]}

## Prohibited Actions
- **General forbidden words**: {", ".join(negative["forbidden_words"])}
- **General style exclusions**: {", ".join(negative["style_exclusions"])}
- **Body-specific constraints**: {negative["body_constraints"] or "N/A"}
- **Outfit-specific constraints**: {negative["outfit_constraints"] or "N/A"}
"""
    extra = {
        "preset_id": preset["id"],
        "resolution": resolution,
        "negative": negative,
    }
    return md.strip() + "\n", extra


def build_natural_prompt(
    req: Dict[str, Any],
    bundle: ProfileBundle,
    tone_name: str,
    preset: Dict[str, Any],
    resolution: Dict[str, Any],
    negative: Dict[str, Any],
) -> str:
    c_props = bundle.character_page.get("properties", {})
    f_props = bundle.face_page.get("properties", {})
    b_props = bundle.body_page.get("properties", {})
    o_props = bundle.outfit_page.get("properties", {})

    age = number_to_str(c_props.get("age")) or "adult"
    nationality = (
        select_to_str(c_props.get("nationality"))
        or rich_text_to_str(c_props.get("nationality"))
        or "Japanese"
    )
    garments = join_non_empty(multi_select_to_list(o_props.get("garments")))
    colors = join_non_empty(multi_select_to_list(o_props.get("color_palette")))
    accessories = join_non_empty(multi_select_to_list(o_props.get("accessories")))
    scene = sentence_fragment(
        str(req.get("scene") or ""),
        "a clean, context-appropriate setting",
    )
    expression = sentence_fragment(
        str(req.get("expression") or ""),
        TONE_PRESETS[tone_name]["description"],
    )
    angle = str(req.get("angle") or "").strip() or "eye-level"
    gaze = str(req.get("gaze") or "").strip() or "toward camera"
    extra_constraints = str(req.get("extra_constraints") or "").strip()
    tone_description = (
        TONE_PRESETS[tone_name]["description"]
        .lower()
        .replace(" tone", "")
        .replace(" expression", "")
    )

    prompt_parts = [
        (
            f"Create a photorealistic professional photograph of {req['character_id']}, "
            f"a {nationality} adult subject whose apparent age is around {age}, for {req['use_case']} use."
        ),
        (
            f"Facial features include {rich_text_to_str(f_props.get('bangs')) or 'natural bangs'}, "
            f"{rich_text_to_str(f_props.get('eyes')) or 'natural eyes'}, "
            f"{select_to_str(f_props.get('hair_style')) or 'a natural hairstyle'}, and "
            f"{select_to_str(f_props.get('hair_color')) or 'a natural hair color'}."
        ),
        (
            f"Body presentation should read as {select_to_str(b_props.get('body_type')) or 'balanced'} "
            f"with proportions described as {rich_text_to_str(b_props.get('proportions_notes')) or 'natural and believable'}."
        ),
        (
            f"Style the outfit as {select_to_str(o_props.get('style_theme')) or 'clean casual'}"
            + (f", featuring {garments}" if garments else "")
            + (f", in {colors}" if colors else "")
            + (f", with {accessories}" if accessories else "")
            + "."
        ),
        f"Set the scene as follows: {scene}.",
        f"Her expression should convey {expression}.",
        f"Frame the shot from {angle}, with the subject gazing {gaze}.",
        (
            f"Use {preset['photo_keywords']}, {preset['focal_length_eq']} framing, {preset['aperture']} aperture, "
            f"{preset['shutter_speed']} shutter speed, {preset['ISO_range']} ISO, and {preset['palette']} color treatment."
        ),
        (
            f"The overall tone should feel {tone_description}, "
            f"and the composition must respect this delivery plan: {resolution['target_aspect']} output, "
            f"{resolution['generation_size_px']} generation canvas, {resolution['framing_notes']}"
        ),
        f"Avoid the following elements: {build_negative_line(negative).rstrip('. ')}.",
    ]
    if extra_constraints:
        prompt_parts.append(f"Additional constraints: {extra_constraints}.")
    return " ".join(prompt_parts).strip() + "\n"


def resolve_image_generation_mode(
    skip_image: bool,
    confirm_image_generation: bool,
    openai_api_key: Optional[str],
) -> str:
    if skip_image:
        return "skipped"
    if not confirm_image_generation:
        return "awaiting_confirmation"
    if not openai_api_key:
        fail("OPENAI_API_KEY is required when image generation is confirmed")
    return "generated"


def openai_headers(openai_api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }


def generate_image(
    openai_api_key: str,
    model: str,
    prompt: str,
    size_px: str,
    output_path: Path,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size_px,
    }
    resp = http_json(
        "POST",
        "https://api.openai.com/v1/images/generations",
        openai_headers(openai_api_key),
        payload,
    )
    data = resp.get("data") or []
    if not data:
        fail("image generation response has no data")
    first = data[0]
    b64 = first.get("b64_json")
    image_url = first.get("url")
    revised_prompt = first.get("revised_prompt")
    if b64:
        raw = base64.b64decode(b64)
        output_path.write_bytes(raw)
    elif image_url:
        req = request.Request(url=image_url, method="GET")
        with request.urlopen(req, timeout=60) as r:
            output_path.write_bytes(r.read())
    else:
        fail("image data has neither b64_json nor url")
    return {
        "revised_prompt": revised_prompt,
        "source_url": image_url,
    }


def save_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_alt_caption(character_id: str, use_case: str, scene: str) -> Tuple[str, str]:
    short_scene = (scene or "a candid scene").strip()
    alt = f"{character_id} for {use_case}: {short_scene}"
    caption = (
        f"{character_id} in a photorealistic {use_case} scene. "
        f"Context: {short_scene}"
    )
    return alt, caption


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Notion character image pipeline.")
    parser.add_argument("--request-json", required=True, help="Path to normalized request JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for outputs")
    parser.add_argument("--mock-data", help="Path to local mock profile bundle JSON")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--skip-image", action="store_true", help="Skip image generation")
    mode_group.add_argument(
        "--confirm-image-generation",
        action="store_true",
        help="Explicitly confirm that image generation should be executed.",
    )
    parser.add_argument("--tone", choices=["neutral", "soft", "energetic"], help="Override tone preset")
    parser.add_argument("--image-model", default="gpt-image-1", help="OpenAI image model")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    req = load_request_json(Path(args.request_json))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    notion_api_key = os.getenv("NOTION_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    mock_path = Path(args.mock_data) if args.mock_data else None

    bundle = fetch_profiles(notion_api_key, req, mock_path)
    tone_name = args.tone or DEFAULT_TONE_BY_USE_CASE[req["use_case"]]
    generation_instructions, extra = compose_generation_instructions(req, bundle, tone_name)
    natural_prompt = build_natural_prompt(
        req=req,
        bundle=bundle,
        tone_name=tone_name,
        preset=choose_preset(req["use_case"]),
        resolution=extra["resolution"],
        negative=extra["negative"],
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f'{req["character_id"]}_{req["use_case"]}_{timestamp}.png'
    image_path = out_dir / file_name

    gi_path = out_dir / "generation_instructions.md"
    prompt_path = out_dir / "natural_prompt.txt"
    meta_path = out_dir / "image_meta.json"

    save_text(gi_path, generation_instructions)
    save_text(prompt_path, natural_prompt)

    image_result: Dict[str, Any] = {}
    image_status = resolve_image_generation_mode(
        skip_image=args.skip_image,
        confirm_image_generation=args.confirm_image_generation,
        openai_api_key=openai_api_key,
    )
    if image_status == "generated":
        image_result = generate_image(
            openai_api_key=openai_api_key,
            model=args.image_model,
            prompt=natural_prompt,
            size_px=extra["resolution"]["generation_size_px"],
            output_path=image_path,
        )

    alt, caption = build_alt_caption(req["character_id"], req["use_case"], str(req.get("scene") or ""))
    validate_english_only_fields(
        {
            "Generation Instructions": generation_instructions,
            "Natural prompt": natural_prompt,
            "Alt text": alt,
            "Caption": caption,
        }
    )

    meta = {
        "character_id": req["character_id"],
        "use_case": req["use_case"],
        "timestamp": timestamp,
        "file_name": file_name,
        "image_status": image_status,
        "file_path": str(image_path) if image_status == "generated" else None,
        "generation_instructions_path": str(gi_path),
        "natural_prompt_path": str(prompt_path),
        "preset_id": extra["preset_id"],
        "resolution": extra["resolution"],
        "tone": tone_name,
        "alt": alt,
        "caption": caption,
        "negative": extra["negative"],
        "warnings": [],
        "image_provider": "openai-images-api" if image_status == "generated" else None,
        "image_provider_details": image_result,
    }
    save_text(meta_path, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    print("```markdown")
    print(generation_instructions.rstrip())
    print("```")
    print()
    print("```text")
    print(natural_prompt.rstrip())
    print("```")
    print()
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
