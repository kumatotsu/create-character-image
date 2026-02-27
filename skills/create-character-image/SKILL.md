---
name: carete-character-image
description: NotionのCharacters/Face/Body/Outfit DBを必ず先に参照し、日本人キャラクター画像向けの英語Generation Instructionsと自然言語プロンプトを生成し、必要に応じて画像生成まで実行するSkill。Blog/X/LP/Print用途で、character_id指定の人物画像を一貫フローで作るときに使う。
---

# Carete Character Image

## Overview

このSkillは以下の固定順序で処理する。
1. 入力自然文を正規化JSONへ変換する
2. Notion DBをクエリする
3. Generation Instructions（英語）を生成する
4. 自然言語プロンプト（英語）を生成する
5. 必要に応じて画像生成を実行する
6. 画像メタJSONを出力する

Notionの生レスポンスをユーザーへ直接表示しない。

## Workflow

### 1) Normalize Input

入力自然文を次のJSONへ正規化する。

```json
{
  "character_id": "A-あやか",
  "use_case": "Blog",
  "scene": "Waiting in front of a stylish variety shop and noticing the viewer.",
  "expression": "She smiles happily as if saying, Found you.",
  "angle": "Eye-level, medium distance",
  "gaze": "Toward camera",
  "extra_constraints": "Subject distance: medium, chest emphasis: 2"
}
```

必須:
- `character_id`
- `use_case` (`X` / `Blog` / `LP` / `Print`)

### 2) Execute Pipeline

参照仕様:
- 生成ポリシー: `references/generation-policy.md`
- Notion OpenAPI: `references/notion-openapi-2025-09-01.yaml`

実行コマンド:

```bash
python3 scripts/notion_image_pipeline.py \
  --request-json /absolute/path/request.json \
  --output-dir /absolute/path/output
```

画像生成をスキップして指示書だけ作る:

```bash
python3 scripts/notion_image_pipeline.py \
  --request-json /absolute/path/request.json \
  --output-dir /absolute/path/output \
  --skip-image
```

### 3) Env Vars

Notion参照には `NOTION_API_KEY` を必須とする。
画像生成を有効化する場合は `OPENAI_API_KEY` を必須とする。

### 4) Output Contract

アシスタント出力順は常に次の通り。
1. 構造化Markdown「Generation Instructions」（英語）
2. 自然言語プロンプト（英語）
3. 画像生成実行（必要時）
4. 画像出力メタ（JSON）

生成画像ファイル名は以下形式とする。
`<character_id>_<use_case>_<YYYYMMDD-HHmmss>.png`

## Subflows

次の3サブフローを1スキル内で運用する。
- Subflow A: `scripts/notion_image_pipeline.py` の Notionクエリ部分（Characters→Face→Body→Outfit）
- Subflow B: 同スクリプトのプロンプト組み立て部分（Generation Instructions + Natural Prompt）
- Subflow C: 同スクリプトの画像生成部分（OpenAI Images API）

## Self Check

出力前に以下を確認する。
- Characters検索が `character_id` の `equals` で実行されている
- Face/Body/Outfitが relation.contains で取得されている
- Negative統合が適用されている
- 用途別解像度マップが適用されている
- ①と②に日本語が混在していない
- Alt/Captionが説明的である
