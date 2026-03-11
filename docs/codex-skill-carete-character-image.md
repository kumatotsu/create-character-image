# codex-skill-carete-character-image

更新日: 2026-03-07

## 目的

- Notion DBを必ず先に参照し、キャラクター画像生成の手順を再利用可能なSkillへ分離する
- 入力正規化から画像メタ出力までを一連で運用できるようにする

## 重要な前提

- スキル名はユーザー指定を優先して `carete-character-image` とした
- 実ディレクトリ名は `skills/create-character-image` だが、呼び出し名は互換性のため `carete-character-image` を維持する
- Characters / Face / Body / Outfit の4DB参照を必須フローとする
- 画像生成API実行はユーザー確認後かつ `OPENAI_API_KEY` がある場合のみ有効化する

## 設計判断

1. 1スキル内に3サブフローを定義した

- Subflow A: Notionクエリ
- Subflow B: Generation Instructions/Natural Prompt生成
- Subflow C: 画像生成とメタ出力

2. 実行ロジックを `scripts/notion_image_pipeline.py` へ集約した

- デフォルト実行でプロンプト生成のみ行い、`image_status: awaiting_confirmation` を返す
- `--confirm-image-generation` を付けたときだけ画像生成を実行する
- `--mock-data` でNotion接続なしのテストを可能にした
- OpenAI Images API の許容サイズに合わせ、用途ごとに target_aspect と generation_size を分離した

3. 仕様の重い情報を `references/` へ分離した

- `references/generation-policy.md`
- `references/notion-openapi-2025-09-01.yaml`

## 検証メモ

- 実行テスト:
  - `python3 skills/create-character-image/scripts/notion_image_pipeline.py --request-json skills/create-character-image/scripts/mock_request.json --mock-data skills/create-character-image/scripts/mock_profiles.json --output-dir /tmp/create-character-image-test`
  - `image_status: awaiting_confirmation` で Generation Instructions / Natural Prompt / meta JSON を生成できることを確認
- 構文チェック:
  - `PYTHONPYCACHEPREFIX=/tmp/python-pyc-cache python3 -m py_compile skills/create-character-image/scripts/notion_image_pipeline.py`
  - 成功
- テスト:
  - `python3 -m unittest tests.test_notion_image_pipeline`
  - サイズ制約、確認フロー、自然言語プロンプト、英語-only バリデーションを確認

## 配置

- ワークスペース: `skills/create-character-image`
- ユーザー領域の呼び出し名: `/Users/totsu00/.codex/skills/carete-character-image`
