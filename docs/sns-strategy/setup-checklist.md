# アカウント開設・API設定手順

---

## 開設前準備チェックリスト

### ビジュアル素材
- [ ] アカウントアイコン（400×400px推奨・JPG/PNG）
  - サイトのfavicon.ico または ロゴを流用可
  - サッカーボール＋日本国旗をモチーフにしたシンプルなアイコンが理想
- [ ] カバー画像（1500×500px推奨）
  - 例：「日本人海外サッカー選手情報」とサイトURL表示
  - カラー：サイトのメインカラーに揃える
- [ ] プロフィール文の確定 → [x-bot-design.md](./x-bot-design.md) の案2を推奨
- [ ] ピン留めツイートの内容確定 → 同上

### アカウント情報
- [ ] メールアドレス（Xアカウント専用のものを推奨）
  - 例：football-jp-sns@gmail.com 等を新規作成
- [ ] 電話番号（SMS認証必須）
- [ ] アカウント名（@ハンドル）の決定 → `@football_jp_info` を推奨

---

## X アカウント開設手順

1. https://x.com にアクセス
2. 「アカウント作成」をクリック
3. 名前・メール・生年月日を入力
4. SMS認証コードを入力
5. パスワード設定
6. アカウント名（@ハンドル）を設定 → `football_jp_info` 等
7. プロフィール写真・カバー画像をアップロード
8. プロフィール文を設定（[x-bot-design.md](./x-bot-design.md) 参照）
9. ウェブサイトURL欄に `https://football-jp.com` を入力
10. 最初のツイート（ピン留め用）を投稿してピン留め設定

---

## X Developer Portal でのアプリ登録

### 前提
- Xアカウントが作成済みであること
- 電話番号認証が完了していること

### 手順

1. https://developer.x.com にアクセス
2. 右上「Sign in」で先ほど作成したXアカウントでログイン
3. 「Developer Portal」に入る
4. 「Apply for access」または「Get started」をクリック
5. **Use case 選択：**
   - "Automated bot that posts content" を選択
   - 用途の説明（英語）：
     ```
     I am running a website (football-jp.com) that provides information about 
     Japanese football players playing in overseas leagues. I want to build a bot 
     that automatically posts match schedules and results from my own data to 
     promote the website. All posts will be original content generated from my 
     data files. I will not scrape or repost content from other sources.
     ```
6. 「Developer agreement」に同意
7. 承認後（即時 or 数日かかる場合あり）、ダッシュボードに進む

### アプリ作成

1. Developer Portal の「Projects & Apps」→「New Project」
2. プロジェクト名：`football-jp-bot`
3. 用途説明：上記と同じ内容
4. 「New App」→ アプリ名：`football-jp-x-bot`
5. 作成後、「Keys and tokens」タブへ

### APIキー・トークン取得

| 取得するもの | 場所 | 環境変数名 |
|-------------|------|-----------|
| API Key | Consumer Keys > API Key | `X_API_KEY` |
| API Key Secret | Consumer Keys > API Key Secret | `X_API_SECRET` |
| Bearer Token | Authentication Tokens > Bearer Token | `X_BEARER_TOKEN` |
| Access Token | Authentication Tokens > Access Token | `X_ACCESS_TOKEN` |
| Access Token Secret | Authentication Tokens > Access Token Secret | `X_ACCESS_TOKEN_SECRET` |

**重要：** Access Token は「Read and Write」権限で生成すること（デフォルトはRead only）

---

## GitHub Secrets 設定

### 設定場所
GitHubリポジトリ → Settings → Secrets and variables → Actions → 「New repository secret」

### 追加するSecrets

| Secret名 | 値 |
|---------|-----|
| `X_API_KEY` | Developer Portalで取得したAPI Key |
| `X_API_SECRET` | API Key Secret |
| `X_BEARER_TOKEN` | Bearer Token |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |

### 確認方法
```yaml
# ワークフロー内での参照例
env:
  X_API_KEY: ${{ secrets.X_API_KEY }}
```

---

## 動作確認チェックリスト

- [ ] Xアカウントが開設できた
- [ ] プロフィール・アイコン・カバー画像が設定できた
- [ ] ピン留めツイートを投稿した
- [ ] Developer Portal でアプリが承認された
- [ ] 5つのAPIキー・トークンを取得した
- [ ] GitHub Secrets に5つ全て設定した
- [ ] `scripts/post_to_x.py` をローカルで手動テスト実行した
- [ ] GitHub Actions の `x-post.yml` を有効化（`if: false` を削除）した
- [ ] 最初の自動投稿が正常に実行された

---

## よくあるつまずきポイント

| 問題 | 原因 | 対処法 |
|------|------|--------|
| Access Token が Read only になっている | アプリの権限設定が Read になっている | App Settings > User authentication settings で「Read and Write」に変更後、再生成 |
| 401 Unauthorized エラー | トークンが間違っている or 権限不足 | GitHub Secrets の値を再確認・再設定 |
| 403 Forbidden エラー | 無料プランの制限超過 or アカウント凍結 | 月間投稿数を確認。制限超過なら翌月まで待つ |
| 429 Too Many Requests | レートリミット超過 | スクリプトのリトライ間隔を確認。投稿間隔を空ける |

---

*最終更新：2026-05-04*
