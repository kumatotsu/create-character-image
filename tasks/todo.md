# Task Plan

- [x] Review the current skill contract, script behavior, and validation gaps.
- [x] Update the pipeline to require explicit confirmation before image generation.
- [x] Replace unsupported image sizes with valid `gpt-image-1` sizes while preserving use-case intent in metadata.
- [x] Generate a real plain-text natural prompt instead of duplicating markdown instructions.
- [x] Enforce English-only output as a hard validation step.
- [x] Remove the silent fallback that bypasses the mandatory `relation.contains` query flow.
- [x] Add regression tests for image-size constraints, confirmation gating, natural prompt format, and English-only enforcement.
- [x] Update skill/docs/agent metadata so the documented workflow matches the implementation.
- [x] Run mock execution, unit tests, and syntax checks.

# Review

- The pipeline now returns `image_status: "awaiting_confirmation"` unless `--confirm-image-generation` is explicitly passed.
- Resolution metadata now separates target delivery framing from the actual OpenAI generation size, and every generation size is validated against the supported `gpt-image-1` set.
- The natural prompt is now generated as plain English prose instead of reusing markdown instructions.
- English-only validation now fails fast for generation instructions, natural prompt, alt text, and caption.
- The mandatory `relation.contains` query flow is now enforced without a direct page-fetch fallback.
- Regression coverage was added in `tests/test_notion_image_pipeline.py`.
- Verification passed with `python3 -m unittest tests.test_notion_image_pipeline`, `python3 skills/create-character-image/scripts/notion_image_pipeline.py --request-json skills/create-character-image/scripts/mock_request.json --mock-data skills/create-character-image/scripts/mock_profiles.json --output-dir /tmp/create-character-image-review`, and `PYTHONPYCACHEPREFIX=/tmp/python-pyc-cache python3 -m py_compile skills/create-character-image/scripts/notion_image_pipeline.py tests/test_notion_image_pipeline.py`.
