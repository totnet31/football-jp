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

// ─── Web Push 送信（VAPID 署名付き + RFC 8291 aes128gcm 暗号化） ──────────
/**
 * Web Push プロトコルに従って Push 通知を送信する
 * VAPID JWT を自前で生成、ペイロードを RFC 8291 (aes128gcm) で暗号化
 *
 * @param {object} subscription - sub.toJSON() の出力（endpoint, keys.auth, keys.p256dh）
 * @param {object} payload - { title: string, body: string, url?: string, badge?: string }
 * @param {object} env - Cloudflare Worker 環境（VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY が必要）
 */
async function sendWebPush(subscription, payload, env) {
  const endpoint = subscription.endpoint;
  const auth = subscription.keys?.auth;
  const p256dh = subscription.keys?.p256dh;

  if (!auth || !p256dh) {
    return { ok: false, error: 'missing subscription keys' };
  }

  const vapidPrivateKeyB64 = env.VAPID_PRIVATE_KEY;
  const vapidPublicKeyB64  = env.VAPID_PUBLIC_KEY;
  const vapidSubject = env.VAPID_SUBJECT || 'mailto:privacy@football-jp.com';

  if (!vapidPrivateKeyB64) {
    return { ok: false, error: 'VAPID_PRIVATE_KEY not configured' };
  }

  try {
    // VAPID JWT 生成
    const jwt = await createVapidJwt(endpoint, vapidSubject, vapidPrivateKeyB64);

    // 公開鍵（Authorization ヘッダの k= に入れる）
    const vapidPublicKeyForHeader = vapidPublicKeyB64
      || 'BOQ4LvD-tUTTYj8E7_L28zVtbio-10Brm8oFzwBlCd2gVlG-wPt_YfOzPdtEJ-wwnN8DUdEoXBJGoUQHkyllvb8';

    // 通知ペイロードを JSON に変換
    const notifPayload = JSON.stringify({
      title: payload.title || '⚽ 今週の注目試合',
      body:  payload.body  || '試合情報をチェック',
      url:   payload.url   || 'https://football-jp.com/',
      badge: payload.badge || '/favicon.ico'
    });

    // RFC 8291 (aes128gcm) でペイロードを暗号化
    const { encryptedBody, salt, serverPublicKeyBytes } = await encryptWebPushPayload(
      notifPayload,
      p256dh,
      auth
    );

    const pushResponse = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `vapid t=${jwt},k=${vapidPublicKeyForHeader}`,
        'Content-Type': 'application/octet-stream',
        'Content-Encoding': 'aes128gcm',
        'TTL': '86400',
        'Urgency': 'normal'
      },
      body: encryptedBody
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

// ─── RFC 8291 / aes128gcm 暗号化実装 ────────────────────────────────────

/**
 * Web Push ペイロードを RFC 8291 (aes128gcm) で暗号化する
 *
 * @param {string} plaintext - 送信するペイロード文字列（JSON）
 * @param {string} clientPublicKeyB64url - subscription.keys.p256dh（base64url）
 * @param {string} authSecretB64url      - subscription.keys.auth（base64url）
 * @returns {{ encryptedBody: Uint8Array, salt: Uint8Array, serverPublicKeyBytes: Uint8Array }}
 */
async function encryptWebPushPayload(plaintext, clientPublicKeyB64url, authSecretB64url) {
  // 1. 乱数 salt（16バイト）を生成
  const salt = crypto.getRandomValues(new Uint8Array(16));

  // 2. エフェメラル鍵ペア（ECDH P-256）を生成
  const serverKeyPair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits']
  );

  // サーバー公開鍵を uncompressed point 形式（65バイト）でエクスポート
  const serverPublicKeyRaw = await crypto.subtle.exportKey('raw', serverKeyPair.publicKey);
  const serverPublicKeyBytes = new Uint8Array(serverPublicKeyRaw);

  // 3. クライアント公開鍵をインポート
  const clientPublicKeyBytes = base64ToUint8(clientPublicKeyB64url);
  const clientPublicKey = await crypto.subtle.importKey(
    'raw',
    clientPublicKeyBytes,
    { name: 'ECDH', namedCurve: 'P-256' },
    false,
    []
  );

  // 4. ECDH 共有秘密（32バイト）を導出
  const sharedSecretBits = await crypto.subtle.deriveBits(
    { name: 'ECDH', public: clientPublicKey },
    serverKeyPair.privateKey,
    256
  );
  const sharedSecret = new Uint8Array(sharedSecretBits);

  // 5. auth secret をデコード
  const authSecret = base64ToUint8(authSecretB64url);

  // 6. HKDF でコンテンツ暗号化鍵（CEK）と nonce を導出
  //    RFC 8291 Section 3.3 に従う
  const { cek, nonce } = await deriveEncryptionKeys(
    sharedSecret,
    authSecret,
    clientPublicKeyBytes,
    serverPublicKeyBytes,
    salt
  );

  // 7. AES-128-GCM でペイロードを暗号化
  //    RFC 8291: plaintext の末尾に \x02 パディングを付けて暗号化
  const encoder = new TextEncoder();
  const plaintextBytes = encoder.encode(plaintext);

  // パディングバイト \x02 を付与（RFC 8188 Section 2 の record padding delimiter）
  const paddedPlaintext = new Uint8Array(plaintextBytes.length + 1);
  paddedPlaintext.set(plaintextBytes);
  paddedPlaintext[plaintextBytes.length] = 0x02;

  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce },
    cek,
    paddedPlaintext
  );

  // 8. RFC 8188 Section 2.1 に従い、ヘッダを構築して結合
  //    header = salt(16) + rs(4, big-endian) + idlen(1) + keyid(65)
  //    rs = record size = ciphertext.length（1レコードのみ）
  const ciphertextBytes = new Uint8Array(ciphertext);
  const rs = ciphertextBytes.byteLength; // record size（パディング含む）

  // RFC 8188: rs フィールドは実際の暗号文サイズを示す（最低 18: 17 + パディング delimiter）
  const rsValue = rs; // ciphertext length（GCM tag 16バイト込み）

  const idLen = serverPublicKeyBytes.length; // 65

  // ヘッダ構造: salt(16) + rs(4) + idlen(1) + server_public_key(65)
  const headerLen = 16 + 4 + 1 + idLen;
  const encryptedBody = new Uint8Array(headerLen + ciphertextBytes.byteLength);

  let offset = 0;

  // salt（16バイト）
  encryptedBody.set(salt, offset);
  offset += 16;

  // rs（4バイト、big-endian）
  const rsView = new DataView(encryptedBody.buffer, offset, 4);
  rsView.setUint32(0, rsValue, false); // big-endian
  offset += 4;

  // idlen（1バイト）
  encryptedBody[offset] = idLen;
  offset += 1;

  // server public key（65バイト）
  encryptedBody.set(serverPublicKeyBytes, offset);
  offset += idLen;

  // ciphertext
  encryptedBody.set(ciphertextBytes, offset);

  return { encryptedBody, salt, serverPublicKeyBytes };
}

/**
 * RFC 8291 Section 3.3 に従い、HKDF で CEK と nonce を導出する
 *
 * @param {Uint8Array} sharedSecret   - ECDH 共有秘密（32バイト）
 * @param {Uint8Array} authSecret     - subscription.keys.auth（16バイト）
 * @param {Uint8Array} clientPubKey   - クライアント公開鍵 raw（65バイト）
 * @param {Uint8Array} serverPubKey   - サーバー公開鍵 raw（65バイト）
 * @param {Uint8Array} salt           - 乱数 salt（16バイト）
 * @returns {{ cek: CryptoKey, nonce: Uint8Array }}
 */
async function deriveEncryptionKeys(sharedSecret, authSecret, clientPubKey, serverPubKey, salt) {
  // HKDF PRK の導出（auth secret を使って共有秘密を強化）
  // RFC 8291 Section 3.3:
  //   PRK_key = HKDF-Extract(auth_secret, ecdh_secret)
  //   key_info = "WebPush: info\x00" || client_pub || server_pub
  //   IKM = HKDF-Expand(PRK_key, key_info, 32)
  const prkKey = await hkdfExtract(authSecret, sharedSecret);

  // key_info の構築
  const keyInfoPrefix = new TextEncoder().encode('WebPush: info\x00');
  const keyInfo = concatUint8Arrays(keyInfoPrefix, clientPubKey, serverPubKey);

  // IKM（Input Keying Material）= HKDF-Expand(PRK_key, key_info, 32)
  const ikm = await hkdfExpand(prkKey, keyInfo, 32);

  // PRK の導出（salt を使って IKM から暗号化用キーを生成）
  // RFC 8291: PRK = HKDF-Extract(salt, IKM)
  const prk = await hkdfExtract(salt, ikm);

  // CEK（Content Encryption Key）= HKDF-Expand(PRK, "Content-Encoding: aes128gcm\x00", 16)
  const cekInfo = new TextEncoder().encode('Content-Encoding: aes128gcm\x00');
  const cekBytes = await hkdfExpand(prk, cekInfo, 16);

  // CEK を AES-GCM キーとしてインポート
  const cek = await crypto.subtle.importKey(
    'raw',
    cekBytes,
    { name: 'AES-GCM' },
    false,
    ['encrypt']
  );

  // Nonce = HKDF-Expand(PRK, "Content-Encoding: nonce\x00", 12)
  const nonceInfo = new TextEncoder().encode('Content-Encoding: nonce\x00');
  const nonce = await hkdfExpand(prk, nonceInfo, 12);

  return { cek, nonce };
}

/**
 * HKDF-Extract: PRK = HMAC-SHA256(salt, IKM)
 * @param {Uint8Array} salt
 * @param {Uint8Array} ikm
 * @returns {Uint8Array} PRK（32バイト）
 */
async function hkdfExtract(salt, ikm) {
  const saltKey = await crypto.subtle.importKey(
    'raw',
    salt,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const prk = await crypto.subtle.sign('HMAC', saltKey, ikm);
  return new Uint8Array(prk);
}

/**
 * HKDF-Expand: OKM = T(1) || T(2) || ... where T(i) = HMAC-SHA256(PRK, T(i-1) || info || i)
 * @param {Uint8Array} prk    - 32バイトの PRK
 * @param {Uint8Array} info   - コンテキスト情報
 * @param {number}     length - 出力バイト数
 * @returns {Uint8Array}
 */
async function hkdfExpand(prk, info, length) {
  const prkKey = await crypto.subtle.importKey(
    'raw',
    prk,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const blocks = Math.ceil(length / 32);
  const okm = new Uint8Array(blocks * 32);
  let prev = new Uint8Array(0);

  for (let i = 1; i <= blocks; i++) {
    const input = concatUint8Arrays(prev, info, new Uint8Array([i]));
    const t = await crypto.subtle.sign('HMAC', prkKey, input);
    prev = new Uint8Array(t);
    okm.set(prev, (i - 1) * 32);
  }

  return okm.slice(0, length);
}

/** 複数の Uint8Array を結合する */
function concatUint8Arrays(...arrays) {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const arr of arrays) {
    result.set(arr, offset);
    offset += arr.length;
  }
  return result;
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
