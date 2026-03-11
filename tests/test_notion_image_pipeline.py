import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "skills" / "create-character-image" / "scripts" / "notion_image_pipeline.py"
MOCK_REQUEST_PATH = PROJECT_ROOT / "skills" / "create-character-image" / "scripts" / "mock_request.json"
MOCK_PROFILES_PATH = PROJECT_ROOT / "skills" / "create-character-image" / "scripts" / "mock_profiles.json"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("notion_image_pipeline", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pipeline = load_pipeline_module()


class NotionImagePipelineTests(unittest.TestCase):
    def test_resolution_map_uses_supported_openai_sizes(self):
        for use_case in pipeline.RESOLUTION_MAP:
            resolution = pipeline.validate_resolution_config(use_case)
            self.assertIn(resolution["generation_size_px"], pipeline.SUPPORTED_IMAGE_SIZES)

    def test_natural_prompt_is_plain_text(self):
        req = pipeline.load_request_json(MOCK_REQUEST_PATH)
        bundle = pipeline.load_mock_bundle(MOCK_PROFILES_PATH)
        tone_name = pipeline.DEFAULT_TONE_BY_USE_CASE[req["use_case"]]
        _, extra = pipeline.compose_generation_instructions(req, bundle, tone_name)
        prompt = pipeline.build_natural_prompt(
            req=req,
            bundle=bundle,
            tone_name=tone_name,
            preset=pipeline.choose_preset(req["use_case"]),
            resolution=extra["resolution"],
            negative=extra["negative"],
        )

        self.assertIn("Create a photorealistic professional photograph", prompt)
        self.assertNotIn("# ", prompt)
        self.assertNotIn("##", prompt)
        self.assertNotIn("**", prompt)
        pipeline.validate_english_only_fields({"Natural prompt": prompt})

    def test_validate_english_only_fields_rejects_japanese(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                pipeline.validate_english_only_fields({"Natural prompt": "これは日本語です"})

    def test_main_defaults_to_awaiting_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            argv = [
                "--request-json",
                str(MOCK_REQUEST_PATH),
                "--mock-data",
                str(MOCK_PROFILES_PATH),
                "--output-dir",
                tmp_dir,
            ]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                pipeline.main(argv)

            meta = json.loads((Path(tmp_dir) / "image_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["image_status"], "awaiting_confirmation")
            self.assertIsNone(meta["file_path"])
            self.assertTrue((Path(tmp_dir) / "generation_instructions.md").exists())
            self.assertTrue((Path(tmp_dir) / "natural_prompt.txt").exists())

    def test_main_generates_image_when_confirmed(self):
        captured = {}

        def fake_generate_image(openai_api_key, model, prompt, size_px, output_path):
            captured["openai_api_key"] = openai_api_key
            captured["model"] = model
            captured["prompt"] = prompt
            captured["size_px"] = size_px
            output_path.write_bytes(b"fake-image")
            return {"revised_prompt": "revised", "source_url": None}

        with tempfile.TemporaryDirectory() as tmp_dir:
            argv = [
                "--request-json",
                str(MOCK_REQUEST_PATH),
                "--mock-data",
                str(MOCK_PROFILES_PATH),
                "--output-dir",
                tmp_dir,
                "--confirm-image-generation",
            ]
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
                with mock.patch.object(pipeline, "generate_image", side_effect=fake_generate_image):
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        pipeline.main(argv)

            meta = json.loads((Path(tmp_dir) / "image_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["image_status"], "generated")
            self.assertIn(captured["size_px"], pipeline.SUPPORTED_IMAGE_SIZES)
            self.assertEqual(captured["openai_api_key"], "test-key")
            self.assertTrue(Path(meta["file_path"]).exists())


if __name__ == "__main__":
    unittest.main()
