---
name: carete-character-image
description: NotionのCharacters/Face/Body/Outfit DBを必ず先に参照し、日本人キャラクター画像向けの英語Generation Instructionsと自然言語プロンプトを生成し、必要に応じて画像生成まで実行するSkill。Blog/X/LP/Print用途で、character_id指定の人物画像を一貫フローで作るときに使う。
---

# Carete Character Image

## Overview

このSkillは以下の固定順序で処理する。
1. 入力自然文を正規化JSONへ変換する
2. Notion DBをクエリする
3. Generation Instructions（英語）を固定フレームで生成する
4. 自然言語プロンプト（英語）を固定フレームで生成する
5. 生成前ダブルチェックを実行する
6. ユーザー確認後にのみ画像生成を実行する
7. 出力前ダブルチェックを実行する
8. 画像メタJSONを出力する

Notionの生レスポンスをユーザーへ直接表示しない。

## Workflow

### 1) Normalize Input

入力自然文を次のJSONへ正規化する。

```json
{
  "character_id": "A-ayaka",
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

プロンプト構成は正式な Nano Banana ガイドに合わせ、まず次の5要素をこの順で必ず明示する。
- Subject
- Action
- Location/context
- Composition
- Style

加えて、このSkillでは次の補助要素も必須とする。
- Edit Preservation
- Text Rendering and Localization
- Constraint Notes

`Style` には Creative Director 要素として最低でも Lighting / Camera and Lens / Color Grading or Film Stock / Materiality and Texture を含める。

まず指示書とプロンプトだけを作る:

```bash
python3 scripts/notion_image_pipeline.py \
  --request-json /absolute/path/request.json \
  --output-dir /absolute/path/output
```

ユーザー確認後に画像生成まで進める:

```bash
python3 scripts/notion_image_pipeline.py \
  --request-json /absolute/path/request.json \
  --output-dir /absolute/path/output \
  --confirm-image-generation
```

### 3) Env Vars

Notion参照には `NOTION_API_KEY` を必須とする。
画像生成を有効化する場合は `OPENAI_API_KEY` を必須とする。
フラグ未指定時はプロンプト成果物のみ出力し、`image_status: "awaiting_confirmation"` を返す。

### 4) Output Contract

アシスタント出力順は常に次の通り。
1. 構造化Markdown「Generation Instructions」（英語）
2. 自然言語プロンプト（英語）
3. ダブルチェック結果
4. ユーザー確認
5. 画像生成実行（必要時）
6. 画像出力メタ（JSON）

生成画像ファイル名は以下形式とする。
`<character_id>_<use_case>_<YYYYMMDD-HHmmss>.png`

未確認の実行では `image_status: "awaiting_confirmation"` を返す。

## Subflows

次の3サブフローを1スキル内で運用する。
- Subflow A: `scripts/notion_image_pipeline.py` の Notionクエリ部分（Characters→Face→Body→Outfit）
- Subflow B: 同スクリプトのプロンプト組み立て部分（Generation Instructions + Natural Prompt）
- Subflow C: 同スクリプトの画像生成部分（OpenAI Images API）

## Double Check

### Check 1: Prompt Assembly

画像生成前に以下を必ず確認する。
- `character_id` 検索が `equals` で実行されている
- Face/Body/Outfit が `relation.contains` で取得されている
- 自然言語プロンプトが強い動詞で始まっている
- Generation Instructions に Subject / Action / Location-context / Composition / Style が全てある
- 自然言語プロンプトにも同じ5要素が平文で全てある
- Style が Lighting / Camera and Lens / Color Grading or Film Stock / Materiality and Texture を含んでいる
- Text Rendering and Localization が未指定なら「不要な文字を入れない」旨が明示されている
- Edit Preservation が「何を固定し、何を変えてよいか」を限定している
- Negative統合が適用されている
- 用途別の target_aspect と generation_size の両方が適用されている
- ①と②、および Alt/Caption に日本語が混在していたら失敗している

### Check 2: Output Package

メタJSON出力前に以下を確認する。
- OpenAI Images API の許容サイズだけが使われている
- Alt/Caption が説明的である
- `image_status: "awaiting_confirmation"` のとき画像APIを呼んでいない
- ダブルチェック結果がメタJSONに記録されている
