# football-jp Push API (Cloudflare Worker)

## デプロイ手順

1. Cloudflare Workers と Pages に対して wrangler ログイン：
   `npx wrangler login`

2. VAPID秘密鍵を Secret として設定：
   `npx wrangler secret put VAPID_PRIVATE_KEY`
   （Phase 3 で配信時に必要、Phase 2 では不要）

3. デプロイ：
   `cd cloudflare-workers/push-api && npx wrangler deploy`

4. デプロイ後の URL（例：`https://football-jp-push-api.xxx.workers.dev`）を、
   フロント `push-client.js` の `API_BASE` 定数に反映する。
   または独自ドメイン `push.football-jp.com` を Cloudflare ダッシュボードで割り当て。

## 動作確認

```bash
curl -X POST https://[YOUR_WORKER_URL]/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"subscription":{"endpoint":"https://example.com/test","keys":{}},"favorites":["test"]}'
```
