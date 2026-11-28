# 本番の構成と、古い実験（2026-11-27）

## 本番（毎日動いているもの）

- リポジトリ: このリポジトリ（asaroyoon1004-star/sns-auto）の main
- 実行: `.github/workflows/daily.yml`（07:00 / 12:00 / 20:00 JST）→ `python -m sns.pipeline daily`
- 台本: Claude がその場で1本生成（`sns/scriptgen.py`）→ 失敗時は Claude 製の在庫 `data/stock/scripts.json` → それも空なら旧シード `data/seed/scripts.json`
- 在庫の補充: `.github/workflows/stock.yml`（毎週月曜 04:30 JST と手動）。補充後に1本サンプルを作り、ffprobe の長さをログに出す（アップロードはしない）
- 動画: Python 描画（`sns/render.py` + `sns/design_scene.py`）。デザインは sb と wh の A/B
- 分析: `.github/workflows/weekly.yml`（毎日 05:00 JST）→ `data/report.md`
- 投稿先: YouTube（公開）。TikTok は inbox（下書き）モードで、公開投稿はしていない

## 本番では使っていないもの（削除候補。消すかどうかは Asaro さんが判断）

| 場所 | 中身 | 状態 |
|---|---|---|
| `finance-shorts/`（このリポジトリ） | Remotion 版のデザイン | 本番のワークフローから呼ばれていない |
| `config.json` の `video.styles.v4` と design v1/v2/v3/v3b/v4 の分岐 | 旧デザイン | 本番は sb / wh のみ。`sns/design_v3.py` は sb / wh の描画にも使われているので消さない |
| `data/seed/scripts.json` | 手書きの旧台本 70 本 | 2026-11-27 から最後の予備だけ |
| プロジェクトファイル `sns-auto/`, `sns-auto.zip` | 10月11日時点のリポジトリの古いコピー | GitHub の main が正。コピーは更新されていない |
| プロジェクトファイル `remotion/`, `remotion-pipeline/`, `skills/finance-short-animation/` | Remotion の試作とスキル | 本番に未接続 |
| プロジェクトファイル `overhaul/`, `visual-opt/`, `research/design_*` | 10月のデザイン比較の素材 | 結果は sb 採用で決着済み |
| プロジェクトファイル `samples/`（11/18 の cr / wh / sample） | デザイン試作の動画 | cr は不採用。wh は本番の A/B に入った |
| `config.json` の `affiliates` | 紹介リンクの枠 | URL が全部空。リンクを取るまで動画に出ない |

## 続けている A/B（安いので残す）

- `experiment: hook`（言い切り vs 疑問）: 台本の型を変えるだけでコストは無い。各15本で判定
- `video.design_arms: sb / wh`: 描画の切り替えだけ。各15本で判定
- 2026-11-27 の 25〜30秒化は全動画に入るので、上の2つの比較は 11/27 以降の動画どうしで見ること
