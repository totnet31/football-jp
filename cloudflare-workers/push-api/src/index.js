// CORS ヘルパー
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://football-jp.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // POST /api/subscribe
    if (url.pathname === '/api/subscribe' && request.method === 'POST') {
      try {
        const body = await request.json();
        if (!body.subscription?.endpoint) return corsResponse({ error: 'invalid' }, 400);

        const id = await hashEndpoint(body.subscription.endpoint);
        const data = {
          subscription: body.subscription,
          favorites: Array.isArray(body.favorites) ? body.favorites.slice(0, 50) : [],
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

    // POST /api/unsubscribe
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

    return corsResponse({ error: 'not_found' }, 404);
  }
};
