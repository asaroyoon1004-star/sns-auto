# 初回セットアップ手順（1〜4）

審査待ちがあるのは TikTok だけなので、**3 の TikTok 開発者アプリの申請を最初に出し、待っている間に 1・2・4 を進める**のが一番早い順番です。

以下、`<ユーザー名>` はあなたの GitHub ユーザー名に置き換えてください。

---

## 0. 事前準備（パソコンに Python を入れる）

2 と 3 の最後に、認証用の小さなプログラムを自分のパソコンで1回だけ動かします。

1. https://www.python.org/downloads/ から Python 3.12 以降をインストール
   - Windows はインストール画面の最初で「Add python.exe to PATH」に必ずチェック
2. ダウンロードした `sns-auto.zip` をデスクトップなどに展開
3. ターミナル（Windows は「PowerShell」、Mac は「ターミナル」）を開き、展開したフォルダに移動して、必要な部品を入れる

```bash
cd ~/Desktop/sns-auto          # Windows: cd $HOME\Desktop\sns-auto
pip install requests
```

---

## 1. GitHub（毎日の自動実行と、リンク集・規約ページの置き場所）

**リポジトリは「公開（Public）」をおすすめします。** 理由は2つあります。GitHub Pages（リンク集と、TikTok 審査に必須の利用規約・プライバシーポリシーのページ）は、非公開リポジトリだと有料プランが必要です。そして、API キーなどの秘密情報はリポジトリではなく暗号化された「Secrets」に入れるので、公開しても漏れません。公開されるのは台本とプログラムだけです。

### 1-1. アカウントとリポジトリを作る
1. https://github.com/signup でアカウント作成（メール認証まで）
2. 右上の「＋」→「New repository」
3. Repository name に `sns-auto`、**Public** を選択、他は何もチェックせず「Create repository」

### 1-2. ファイルをアップロードする
1. 作ったリポジトリの画面で「uploading an existing file」のリンクを押す
2. 展開した `sns-auto` フォルダの**中身すべて**（`sns` `data` `docs` `.github` などのフォルダと、`config.json` などのファイル）をドラッグ＆ドロップ
   - `.github` は隠しフォルダです。Mac の Finder は `Command + Shift + .` で表示、Windows はエクスプローラーの「表示」→「隠しファイル」にチェック
   - アップロード後、一覧に `.github` フォルダがあることを必ず確認（ないと自動実行が動きません）
3. 下の「Commit changes」を押す

### 1-3. 自動実行がファイルを書き込めるようにする
1. リポジトリの「Settings」→ 左メニュー「Actions」→「General」
2. 一番下の「Workflow permissions」で **Read and write permissions** を選んで「Save」

### 1-4. GitHub Pages を公開する
1. 「Settings」→ 左メニュー「Pages」
2. Source を「Deploy from a branch」、Branch を `main`、フォルダを `/docs` にして「Save」
3. 1〜2分後、次の3つのURLが開けることを確認
   - リンク集： `https://<ユーザー名>.github.io/sns-auto/`
   - 利用規約： `https://<ユーザー名>.github.io/sns-auto/terms.html`
   - プライバシーポリシー： `https://<ユーザー名>.github.io/sns-auto/privacy.html`

### 1-5. Secrets の入れ方（2〜4 で出てくる値を入れる場所）
「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で、名前と値を1つずつ登録します。登録する名前は次の7つです。

| 名前 | どこで手に入るか |
|---|---|
| `YT_CLIENT_ID` `YT_CLIENT_SECRET` `YT_REFRESH_TOKEN` | 2 |
| `TIKTOK_CLIENT_KEY` `TIKTOK_CLIENT_SECRET` `TIKTOK_REFRESH_TOKEN` | 3 |
| `ANTHROPIC_API_KEY` | 4 |

### 1-6. 動作確認
「Actions」タブ →「daily-shorts」→「Run workflow」。緑のチェックが付けば成功で、作られた動画は実行結果の画面下「Artifacts」からダウンロードできます。認証情報が未登録のうちは、動画を作るだけで投稿はしません。

---

## 2. YouTube

### 2-1. チャンネルを作る
1. 投稿専用の Google アカウントを作るのがおすすめ（https://accounts.google.com/signup）
2. https://www.youtube.com にそのアカウントでログイン → 右上のアイコン →「チャンネルを作成」
3. 名前は `1分でわかるお金の話`、ハンドルは `@okane_1min` など空いているもの

### 2-2. YouTube Data API を有効にする
1. https://console.cloud.google.com に同じアカウントでログイン（初回は利用規約に同意）
2. 上部のプロジェクト選択 →「新しいプロジェクト」→ 名前 `sns-auto` →「作成」
3. 左メニュー「APIとサービス」→「ライブラリ」→ `YouTube Data API v3` を検索 →「有効にする」

### 2-3. OAuth の設定（ログイン許可の画面を作る）
1. 「APIとサービス」→「OAuth 同意画面」（表示が「Google Auth Platform」の場合も同じ場所）→「開始」
2. アプリ名 `sns-auto`、サポートメールは自分のアドレス → 対象は **外部** → 連絡先も自分のアドレス → 作成
3. 「対象」（または「公開ステータス」）で **「アプリを公開」→ 本番環境** にする
   - **ここが重要です。** 「テスト」のままだと、取得した許可が7日で切れて投稿が止まります
   - 公開しても、使うのは自分だけなので Google の審査は不要です
4. 「クライアント」→「クライアントを作成」→ アプリケーションの種類 **デスクトップアプリ** → 作成
5. 表示された **クライアント ID** と **クライアント シークレット** を控える

### 2-4. リフレッシュトークンを取る（0 で準備したパソコンで実行）

Mac：
```bash
export YT_CLIENT_ID="控えたクライアントID"
export YT_CLIENT_SECRET="控えたシークレット"
python -m sns.auth_youtube
```
Windows（PowerShell）：
```powershell
$env:YT_CLIENT_ID="控えたクライアントID"
$env:YT_CLIENT_SECRET="控えたシークレット"
python -m sns.auth_youtube
```

1. 表示されたURLをブラウザで開き、2-1 のアカウントを選ぶ
2. 「Google はこのアプリを確認していません」と出たら「詳細」→「sns-auto（安全ではないページ）に移動」→ 許可（自分で作ったアプリなので問題ありません）
3. ブラウザが「このサイトにアクセスできません」になりますが正常です。**アドレスバーのURL全体**をコピーして、ターミナルに貼り付けて Enter
4. `YT_REFRESH_TOKEN = ...` と表示された値を控える
5. 1-5 の手順で `YT_CLIENT_ID` `YT_CLIENT_SECRET` `YT_REFRESH_TOKEN` を登録

---

## 3. TikTok

### 3-1. 投稿用アカウントを作る
1. スマホに TikTok アプリを入れ、新しいアカウントを作成（18歳以上の生年月日で）
2. **個人アカウントのまま**にする（ビジネスアカウントにすると、TikTok Shop のアフィリエイトとクリエイター報酬が使えません）
3. 名前・アイコン・自己紹介を設定（例：「毎日1分でお金に強くなる｜節約・制度・詐欺対策」）

### 3-2. 開発者アプリを作る
1. https://developers.tiktok.com →「Log in」→ 3-1 のアカウントでログインし、開発者登録
2. 右上のプロフィール →「Manage apps」→「Connect an app」（所有者は個人でOK）
3. App details を入力
   - App icon：1024×1024 の画像（`docs/icon.png` を用意してあります）
   - App name：`sns-auto`
   - Category：Utilities などに近いもの
   - Description：`Personal tool that uploads my own short videos to my own TikTok account and reads their view counts.`
   - Terms of Service URL：`https://<ユーザー名>.github.io/sns-auto/terms.html`
   - Privacy Policy URL：`https://<ユーザー名>.github.io/sns-auto/privacy.html`
   - Platforms：**Web** にチェックし、Website URL に `https://<ユーザー名>.github.io/sns-auto/`
4. 「Add products」で **Login Kit** と **Content Posting API** を追加
   - Login Kit の Redirect URI に `https://<ユーザー名>.github.io/sns-auto/`
   - Content Posting API の **Direct Post** をオン（審査後の完全自動投稿用）
5. Scopes で `user.info.basic` `user.info.stats` `video.upload` `video.publish` `video.list` を追加

### 3-3. URLの所有確認
1. アプリ画面上部の「URL properties」→ Production になっていることを確認 →「Verify properties」
2. 「URL prefix」を選び `https://<ユーザー名>.github.io/sns-auto/` を入力
3. 署名ファイル（`tiktok〇〇〇.txt`）をダウンロード
4. GitHub のリポジトリで `docs` フォルダを開き「Add file」→「Upload files」でそのファイルを入れて Commit
5. 1〜2分待って TikTok の画面で「Verify」

### 3-4. 審査に出す
1. 「App review」に、各機能の説明を英語で書く（例：`Login Kit: I log in with my own account. video.upload / video.publish: upload videos I made to my own account. video.list / user.info.stats: read my own view and follower counts for weekly reports.`）
2. デモ動画が必須です。2-4 や 3-5 で認証して、投稿されるまでをスマホやパソコンで画面録画したもの（50MB以内）を添付
3. 「Submit for review」

審査中でも、アプリ画面上部を **Sandbox** に切り替え、Sandbox 設定で自分のアカウントをテストユーザーに追加すれば、次の 3-5 と下書き投稿を試せます（Sandbox 中は Client key と secret が Sandbox 用のものになる点に注意）。

### 3-5. リフレッシュトークンを取る
アプリ画面の「Client key」と「Client secret」を控えて、パソコンで実行します。

Mac：
```bash
export TIKTOK_CLIENT_KEY="Client key"
export TIKTOK_CLIENT_SECRET="Client secret"
export TIKTOK_REDIRECT="https://<ユーザー名>.github.io/sns-auto/"
python -m sns.auth_tiktok
```
Windows は 2-4 と同じく `$env:名前="値"` の形で3つ設定してから `python -m sns.auth_tiktok`。

1. 表示されたURLを開き、3-1 のアカウントで許可
2. リンク集のページに戻ってきたら、**アドレスバーのURL全体**（`?code=...` を含む）をコピーしてターミナルに貼り付け
3. `TIKTOK_REFRESH_TOKEN = ...` を控え、1-5 の手順で3つ登録

### 3-6. 審査が通る前と後
- **通る前**：動画は TikTok アプリの「受信箱（下書き）」に届きます。アプリの通知から開いて投稿ボタンを押すだけです（キャプションは README の通り自動で作られます）
- **通った後**：`config.json` の `"mode": "inbox"` を `"mode": "direct"` に書き換えて保存すると、完全自動で公開投稿されます
- リフレッシュトークンは約1年で期限が切れます。実行結果に「new refresh token」の通知が出たら 3-5 をやり直してください

---

## 4. Anthropic API キー（毎回新しい台本を作るため）

1. https://console.anthropic.com でアカウント作成（メール認証と電話番号認証）
2. 左メニュー「Billing」（または「Plans & Billing」）でクレジットカードを登録し、前払いでクレジットを購入（最初は 5〜10 ドルで十分）
   - 目安：台本1本あたり数円〜十数円、1日3本で月 数百円〜1,500円程度
   - 使いすぎ防止に、同じ画面で月の利用上限（Spend limit）を設定しておくと安心です
3. 「API Keys」→「Create Key」→ 名前 `sns-auto` → 作成
4. 表示されたキー（`sk-ant-...`）を**その場でコピー**（あとから再表示できません）
5. 1-5 の手順で `ANTHROPIC_API_KEY` として登録

キーを登録しなくても、用意済みの30本の台本で約10日分は回ります。

---

## 全部終わったら

「Actions」→「daily-shorts」→「Run workflow」をもう一度実行し、YouTube Studio と TikTok の受信箱に動画が届けば完了です。以降は毎日 7時・12時・20時に自動で投稿されます。
