# football-jp Push API (Cloudflare Worker)

## デプロイ手順（Phase 4 対応版）

### 1. Cloudflare Workers にログイン
```bash
npx wrangler login
```

### 2. Worker Secrets を設定（4つ）

```bash
cd cloudflare-workers/push-api

# VAPID秘密鍵（.env.local の VAPID_PRIVATE_KEY の値を貼る）
npx wrangler secret put VAPID_PRIVATE_KEY

# VAPID公開鍵
npx wrangler secret put VAPID_PUBLIC_KEY

# VAPID subject
npx wrangler secret put VAPID_SUBJECT
# 入力値: mailto:privacy@football-jp.com

# 管理APIトークン（週次Push cron 認証用）
# 適当な乱数文字列を生成して設定する（例: openssl rand -hex 32）
npx wrangler secret put ADMIN_TOKEN
# 生成コマンド例: openssl rand -hex 32
```

### 3. GitHub Secrets に同じ ADMIN_TOKEN を登録
GitHubリポジトリの Settings > Secrets and variables > Actions > New repository secret
- Name: `ADMIN_TOKEN`
- Value: 上記と同じ値

### 4. デプロイ
```bash
cd cloudflare-workers/push-api
npx wrangler deploy
```

### 5. 動作確認（購読者一覧取得）
```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  https://football-jp-push-api.saito-dfe.workers.dev/api/subscriptions
```

---

## エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---------|------|------|------|
| POST | /api/subscribe | なし | 購読登録・お気に入り更新（3軸対応） |
| POST | /api/unsubscribe | なし | 購読解除 |
| GET  | /api/subscriptions | ADMIN_TOKEN | 購読者一覧取得（cron用） |
| POST | /api/send-push | ADMIN_TOKEN | 単一購読者にPush送信（cron用） |

## 動作確認（購読登録テスト）

```bash
curl -X POST https://football-jp-push-api.saito-dfe.workers.dev/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "subscription": {"endpoint":"https://example.com/test","keys":{}},
    "favorites": ["mitoma"],
    "favorite_clubs": ["club-397"],
    "favorite_leagues": ["league-39"]
  }'
```

## ⚠️ 注意事項

- `ADMIN_TOKEN` が未設定の場合、`/api/subscriptions` と `/api/send-push` は 401 を返す
- Web Push の暗号化（aes128gcm）は現在 TODO。実際の配信には暗号化実装が必要
- 購読者が410エラーを返した場合、KVから自動削除される
