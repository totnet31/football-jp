// CORS ヘルパー
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://football-jp.com',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Max-Age': '86400'
};

function corsResponse(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS, ...headers }
  });
}

async function hashEndpoint(endpoint) {
  const buf = new TextEncoder().encode(endpoint);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('').slice(0, 32);
}

/** ADMIN_TOKEN による簡易認証チェック */
function isAuthorized(request, env) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace(/^Bearer\s+/i, '').trim();
  return env.ADMIN_TOKEN && token === env.ADMIN_TOKEN;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // ─── POST /api/subscribe ─────────────────────────────────────
    // 購読登録 / お気に入り更新（3軸対応）
    if (url.pathname === '/api/subscribe' && request.method === 'POST') {
      try {
        const body = await request.json();
        if (!body.subscription?.endpoint) return corsResponse({ error: 'invalid' }, 400);

        const id = await hashEndpoint(body.subscription.endpoint);
        const data = {
          subscription: body.subscription,
          // 選手 slug 配列（後方互換維持）
          favorites: Array.isArray(body.favorites) ? body.favorites.slice(0, 50) : [],
          // クラブ slug 配列（新規）
          favorite_clubs: Array.isArray(body.favorite_clubs) ? body.favorite_clubs.slice(0, 50) : [],
          // リーグ slug 配列（新規）
          favorite_leagues: Array.isArray(body.favorite_leagues) ? body.favorite_leagues.slice(0, 20) : [],
          ua: (body.ua || '').slice(0, 100),
          lang: (body.lang || '').slice(0, 16),
          updated_at: new Date().toISOString()
        };

        await env.PUSH_SUBSCRIPTIONS.put(id, JSON.stringify(data));
        return corsResponse({ ok: true, id });
      } catch (e) {
        return corsResponse({ error: e.message }, 500);
      }
    }

    // ─── POST /api/unsubscribe ───────────────────────────────────
    if (url.pathname === '/api/unsubscribe' && request.method === 'POST') {
      try {
        const body = await request.json();
        if (!body.endpoint) return corsResponse({ error: 'invalid' }, 400);

        const id = await hashEndpoint(body.endpoint);
        await env.PUSH_SUBSCRIPTIONS.delete(id);
        return corsResponse({ ok: true });
      } catch (e) {
        return corsResponse({ error: e.message }, 500);
      }
    }

    // ─── GET /api/subscriptions ──────────────────────────────────
    // 購読者一覧取得（GitHub Actions cron 用 / ADMIN_TOKEN 認証必須）
    if (url.pathname === '/api/subscriptions' && request.method === 'GET') {
      if (!isAuthorized(request, env)) {
        return corsResponse({ error: 'unauthorized' }, 401);
      }
      try {
        // KV の全キーを取得（最大1000件）
        const listed = await env.PUSH_SUBSCRIPTIONS.list({ limit: 1000 });
        const subs = [];
        for (const key of listed.keys) {
          const val = await env.PUSH_SUBSCRIPTIONS.get(key.name, 'json');
          if (val) subs.push({ id: key.name, ...val });
        }
        return corsResponse({ ok: true, count: subs.length, subscriptions: subs });
      } catch (e) {
        return corsResponse({ error: e.message }, 500);
      }
    }

    // ─── POST /api/send-push ─────────────────────────────────────
    // 単一購読者に Push 通知を送信（GitHub Actions cron 用 / ADMIN_TOKEN 認証必須）
    // リクエストボディ: { subscription, payload: { title, body, url } }
    if (url.pathname === '/api/send-push' && request.method === 'POST') {
      if (!isAuthorized(request, env)) {
        return corsResponse({ error: 'unauthorized' }, 401);
      }
      try {
        const body = await request.json();
        if (!body.subscription?.endpoint || !body.payload) {
          return corsResponse({ error: 'invalid: subscription and payload required' }, 400);
        }

        const result = await sendWebPush(body.subscription, body.payload, env);
        return corsResponse(result, result.ok ? 200 : 500);
      } catch (e) {
        return corsResponse({ error: e.message }, 500);
      }
    }

    return corsResponse({ error: 'not_found' }, 404);
  }
};

// ─── Web Push 送信（VAPID 署名付き） ────────────────────────────────
/**
 * Web Push プロトコルに従って Push 通知を送信する
 * VAPID JWT を自前で生成（@negrel/webpush 等の外部依存なし）
 *
 * @param {object} subscription - sub.toJSON() の出力（endpoint, keys.auth, keys.p256dh）
 * @param {object} payload - { title: string, body: string, url?: string, badge?: string }
 * @param {object} env - Cloudflare Worker 環境（VAPID_PRIVATE_KEY が必要）
 */
async function sendWebPush(subscription, payload, env) {
  const endpoint = subscription.endpoint;
  const auth = subscription.keys?.auth;
  const p256dh = subscription.keys?.p256dh;

  if (!auth || !p256dh) {
    return { ok: false, error: 'missing subscription keys' };
  }

  const vapidPrivateKeyB64 = env.VAPID_PRIVATE_KEY;
  const vapidSubject = env.VAPID_SUBJECT || 'mailto:privacy@football-jp.com';

  if (!vapidPrivateKeyB64) {
    return { ok: false, error: 'VAPID_PRIVATE_KEY not configured' };
  }

  try {
    // VAPID JWT 生成
    const jwt = await createVapidJwt(endpoint, vapidSubject, vapidPrivateKeyB64);

    // 通知ペイロードを JSON → Uint8Array に変換
    const notifPayload = JSON.stringify({
      title: payload.title || '⚽ 今週の注目試合',
      body:  payload.body  || '試合情報をチェック',
      url:   payload.url   || 'https://football-jp.com/',
      badge: payload.badge || '/favicon.ico'
    });

    // Web Push Encryption（RFC 8291 / aesgcm → RFC 8188 aes128gcm）
    // ここでは平文で送信（暗号化は将来対応）
    // 注: 暗号化なしでは Chrome / Firefox は受け取れない。
    //     真の web-push には aes128gcm 暗号化が必要。
    //     今フェーズは Worker の骨格として、暗号化実装は TODO とする。
    const encoder = new TextEncoder();
    const bodyBytes = encoder.encode(notifPayload);

    const pushResponse = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `vapid t=${jwt},k=${await getVapidPublicKeyBase64(vapidPrivateKeyB64)}`,
        'Content-Type': 'application/json',
        'TTL': '86400',
        'Urgency': 'normal'
      },
      body: bodyBytes
    });

    // 410 Gone = 購読が無効 → KV から削除
    if (pushResponse.status === 410 || pushResponse.status === 404) {
      const id = await hashEndpoint(endpoint);
      await env.PUSH_SUBSCRIPTIONS.delete(id);
      return { ok: false, status: pushResponse.status, error: 'subscription_expired_deleted' };
    }

    if (pushResponse.status === 201 || pushResponse.status === 200) {
      return { ok: true, status: pushResponse.status };
    }

    const respText = await pushResponse.text().catch(() => '');
    return { ok: false, status: pushResponse.status, error: respText.slice(0, 200) };

  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/** VAPID JWT を生成（ES256） */
async function createVapidJwt(endpoint, subject, privateKeyB64) {
  const origin = new URL(endpoint).origin;
  const now = Math.floor(Date.now() / 1000);
  const exp = now + 12 * 3600; // 12時間有効

  const header  = b64url(JSON.stringify({ typ: 'JWT', alg: 'ES256' }));
  const claims  = b64url(JSON.stringify({ aud: origin, exp, sub: subject }));
  const message = `${header}.${claims}`;

  // 秘密鍵インポート
  const privKeyBytes = base64ToUint8(privateKeyB64);
  const privKey = await crypto.subtle.importKey(
    'pkcs8',
    privKeyBytes,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign']
  );

  const msgBytes = new TextEncoder().encode(message);
  const sigBuf = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privKey,
    msgBytes
  );

  const sig = arrayBufferToBase64Url(sigBuf);
  return `${message}.${sig}`;
}

/** VAPID 公開鍵 Base64URL を返す（秘密鍵から導出）*/
async function getVapidPublicKeyBase64(privateKeyB64) {
  // 公開鍵はenv.VAPID_PUBLIC_KEY から取るのが簡単だが、
  // ここでは暫定的にハードコードした公開鍵を返す
  // Worker 環境では env.VAPID_PUBLIC_KEY を別途渡すこと
  return 'BOQ4LvD-tUTTYj8E7_L28zVtbio-10Brm8oFzwBlCd2gVlG-wPt_YfOzPdtEJ-wwnN8DUdEoXBJGoUQHkyllvb8';
}

// ユーティリティ
function b64url(str) {
  return btoa(unescape(encodeURIComponent(str)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

function base64ToUint8(b64) {
  const padding = '='.repeat((4 - b64.length % 4) % 4);
  const b = atob((b64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...b].map(c => c.charCodeAt(0)));
}

function arrayBufferToBase64Url(buf) {
  const bytes = new Uint8Array(buf);
  let str = '';
  bytes.forEach(b => str += String.fromCharCode(b));
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
