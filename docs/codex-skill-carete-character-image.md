# codex-skill-carete-character-image

更新日: 2026-02-27

## 目的

- Notion DBを必ず先に参照し、キャラクター画像生成の手順を再利用可能なSkillへ分離する
- 入力正規化から画像メタ出力までを一連で運用できるようにする

## 重要な前提

- スキル名はユーザー指定を優先して `carete-character-image` とした
- Characters / Face / Body / Outfit の4DB参照を必須フローとする
- 画像生成API実行は `OPENAI_API_KEY` がある場合のみ有効化する

## 設計判断

1. 1スキル内に3サブフローを定義した

- Subflow A: Notionクエリ
- Subflow B: Generation Instructions/Natural Prompt生成
- Subflow C: 画像生成とメタ出力

2. 実行ロジックを `scripts/notion_image_pipeline.py` へ集約した

- `--skip-image` でプロンプト生成のみ実行できる
- `--mock-data` でNotion接続なしのテストを可能にした

3. 仕様の重い情報を `references/` へ分離した

- `references/generation-policy.md`
- `references/notion-openapi-2025-09-01.yaml`

## 検証メモ

- 実行テスト:
  - `python3 skills/carete-character-image/scripts/notion_image_pipeline.py --request-json skills/carete-character-image/scripts/mock_request.json --mock-data skills/carete-character-image/scripts/mock_profiles.json --output-dir /tmp/carete-character-image-test --skip-image`
  - Generation Instructions / Natural Prompt / meta JSON を生成できることを確認
- 構文チェック:
  - `PYTHONPYCACHEPREFIX=/tmp/python-pyc-cache python3 -m py_compile skills/carete-character-image/scripts/notion_image_pipeline.py`
  - 成功
- `quick_validate.py`:
  - `yaml` モジュール不足で実行不可（`ModuleNotFoundError: No module named 'yaml'`）

## 配置

- ワークスペース: `skills/carete-character-image`
- ユーザー領域へコピー済み: `/Users/totsu00/.codex/skills/carete-character-image`
