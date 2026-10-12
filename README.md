# sns-auto：お金ショート自動化パイプライン

台本 → AI音声 → 縦型動画 → YouTube／TikTok投稿 → 再生データ分析 → 次の台本に反映、までを自動で回す。
戦略と数値計画は [PLAN.md](PLAN.md)。

## 仕組み

| 段階 | ファイル | 中身 |
|---|---|---|
| 台本 | `sns/scriptgen.py` | `ANTHROPIC_API_KEY` があれば Claude が毎回新しい台本を書く（重複回避、伸びたフックを参考にする）。なければ `data/seed/scripts.json` の30本を順に使う |
| 音声 | `sns/tts.py` | edge-tts（自然な女性ナレーション）。使えない環境ではオフラインの OpenJTalk に自動で切り替え |
| 動画 | `sns/render.py` | 1080×1920、1文1画面で音声と同期。数字を黄色で強調、進捗バー、PR表記。成長期は20〜45秒、収益期は61秒以上 |
| 投稿 | `sns/upload_youtube.py` `sns/upload_tiktok.py` | YouTube Data API（合成メディア申告つき）、TikTok Content Posting API（AI生成ラベルつき） |
| 分析 | `sns/analytics.py` | 再生・いいね・コメント・シェアを集計し、カテゴリの出現率を自動で調整。フォロワー1万人で収益期へ自動切り替え |
| リンク集 | `sns/landing.py` | `config.json` のアフィリエイトURLから `docs/index.html` を生成（GitHub Pages でプロフィールリンクにする） |
| 定期実行 | `.github/workflows/` | 毎日 7時・12時・20時に1本ずつ作って投稿。毎週月曜に分析とリンク集の更新 |

## 手元で動かす

```bash
sudo apt-get install -y ffmpeg fonts-noto-cjk   # mac: brew install ffmpeg
pip install -r requirements.txt
python -m sns.pipeline make --count 3     # data/queue/ に動画を3本作る（投稿はしない）
python -m sns.pipeline daily              # 作って投稿（認証情報があれば）
python -m sns.pipeline analyze            # 集計・学習・週次レポート（data/report.md）
python -m sns.pipeline landing            # リンク集ページを再生成
python -m sns.revenue_model --all         # 収益シミュレーション
```

## 初回セットアップ（本人の操作が必要な部分）

画面ごとの詳しい手順は [SETUP_GUIDE.md](SETUP_GUIDE.md)。

1. **GitHub**：このフォルダを公開リポジトリとして置き、Settings → Pages で `main` ブランチの `/docs` を公開（秘密情報は Secrets に入れるので公開しても漏れない）。
2. **YouTube**：チャンネル作成 → Google Cloud で YouTube Data API v3 を有効化、OAuth クライアント（デスクトップアプリ）作成 → `python -m sns.auth_youtube` でリフレッシュトークン取得。
3. **TikTok**：アカウント作成（個人アカウント） → developers.tiktok.com でアプリ作成、Content Posting API を追加 → `python -m sns.auth_tiktok`。審査前は「下書き（inbox）」に届くのでアプリで投稿ボタンを押す。審査通過後は `config.json` の `tiktok.mode` を `direct` にすると完全自動。
4. **Anthropic**：API キーを発行（台本を毎回新規生成するため。なくても seed の30本で回る）。
5. **GitHub Secrets** に登録：`ANTHROPIC_API_KEY` `YT_CLIENT_ID` `YT_CLIENT_SECRET` `YT_REFRESH_TOKEN` `TIKTOK_CLIENT_KEY` `TIKTOK_CLIENT_SECRET` `TIKTOK_REFRESH_TOKEN`
6. **ASP**：A8.net などに登録し、`config.json` の `affiliates` 6件に提携後のURLを貼る。各SNSのプロフィールに GitHub Pages のURLを設定。

## 調整ポイント

- 投稿本数：ワークフローの cron 行を増減。1回で複数本なら `posts_per_run`
- 声：`tts.edge_voice`（例 `ja-JP-KeitaNeural` で男性）、速さ `tts.edge_rate`
- 色・カテゴリ：`config.json` の `categories`
- BGM：`data/bgm/` に著作権フリーの mp3 を置くと小さく自動で混ぜる
