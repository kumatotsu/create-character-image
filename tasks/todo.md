# Task Plan

- [x] Review `tasks/lessons.md`, the current image-generation skill contract, and the current pipeline behavior.
- [x] Confirm the publicly available `nanobanana2` prompt guidance from primary Google sources and extract only rules relevant to this skill.
- [x] Update the skill spec and bundled policy so prompt construction explicitly follows the guide's structure, ambiguity controls, and editing rules.
- [x] Add a strict double-check workflow that validates prompt completeness before generation and validates output metadata after prompt assembly.
- [x] Update the pipeline implementation so the generated instructions and natural prompt encode the new rules mechanically.
- [x] Add or update regression tests for the new prompt structure and double-check gates.
- [x] Run mock execution, unit tests, and syntax checks.

# Review

- Rebased the skill contract, bundled generation policy, and agent metadata on the official Nano Banana guide at `https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana?hl=en`.
- Reworked the prompt workflow around the official text-to-image formula `[Subject] + [Action] + [Location/context] + [Composition] + [Style]`, and kept `Edit Preservation`, `Text Rendering and Localization`, and `Constraint Notes` as supporting directives required by this skill.
- Added a strict double-check flow in the pipeline. `prompt_assembly` now fails if the official formula sections, strong generation verb, creative-director style controls, edit-preservation clause, text-rendering clause, negative integration, or English-only contract is missing. `output_package` now fails if naming, descriptive alt/caption, confirmation gating, or metadata recording is broken.
- Reworked the generated Markdown instructions and plain-text prompt so the official Nano Banana structure is mechanically enforced by code instead of relying on operator discipline.
- Added regression coverage for the new framework and double-check gates in `tests/test_notion_image_pipeline.py`.
- Verification passed with `PYTHONPYCACHEPREFIX=/tmp/python-pyc-cache python3 -m py_compile skills/create-character-image/scripts/notion_image_pipeline.py tests/test_notion_image_pipeline.py`, `python3 -m unittest tests.test_notion_image_pipeline`, and `python3 skills/create-character-image/scripts/notion_image_pipeline.py --request-json skills/create-character-image/scripts/mock_request.json --mock-data skills/create-character-image/scripts/mock_profiles.json --output-dir /tmp/create-character-image-nanobanana-official`.
