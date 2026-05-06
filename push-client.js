// Push通知購読クライアント（3軸対応：選手/クラブ/リーグ）
// 使い方：window.fjPush.subscribe(['mitoma'], ['club-397'], ['league-39'])

const VAPID_PUBLIC_KEY = 'BOQ4LvD-tUTTYj8E7_L28zVtbio-10Brm8oFzwBlCd2gVlG-wPt_YfOzPdtEJ-wwnN8DUdEoXBJGoUQHkyllvb8';
const API_BASE = 'https://football-jp-push-api.saito-dfe.workers.dev'; // Cloudflare Workers（2026-05-07 デプロイ）
const STORAGE_KEY         = 'fjPushFavorites';       // 選手 slug 配列（後方互換維持）
const STORAGE_KEY_CLUBS   = 'fjPushFavoriteClubs';   // クラブ slug 配列（新規）
const STORAGE_KEY_LEAGUES = 'fjPushFavoriteLeagues'; // リーグ slug 配列（新規）
const SUB_KEY = 'fjPushSubscribed';

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

window.fjPush = {
  isSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  },

  isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  },

  isIOS() {
    return /iP(hone|od|ad)/.test(navigator.platform) ||
      (/Mac/.test(navigator.platform) && navigator.maxTouchPoints > 1);
  },

  async getPermission() {
    if (!this.isSupported()) return 'unsupported';
    return Notification.permission;
  },

  // 選手お気に入り取得（後方互換）
  getFavorites() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch { return []; }
  },

  // クラブお気に入り取得
  getFavoriteClubs() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY_CLUBS) || '[]');
    } catch { return []; }
  },

  // リーグお気に入り取得
  getFavoriteLeagues() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY_LEAGUES) || '[]');
    } catch { return []; }
  },

  isSubscribed() {
    return localStorage.getItem(SUB_KEY) === '1';
  },

  /**
   * Push購読を開始（または更新）
   * @param {string[]} favoriteSlugs - 選手slug配列
   * @param {string[]} favoriteClubs - クラブslug配列（例: ['club-397']）
   * @param {string[]} favoriteLeagues - リーグslug配列（例: ['league-39']）
   */
  async subscribe(favoriteSlugs = [], favoriteClubs = [], favoriteLeagues = []) {
    if (!this.isSupported()) throw new Error('このブラウザは通知に対応していません');
    if (this.isIOS() && !this.isStandalone()) throw new Error('iPhoneでは「ホーム画面に追加」してから設定してください');

    const perm = await Notification.requestPermission();
    if (perm !== 'granted') throw new Error('通知が許可されませんでした');

    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
      });
    }

    const res = await fetch(API_BASE + '/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subscription: sub.toJSON(),
        favorites: favoriteSlugs,
        favorite_clubs: favoriteClubs,
        favorite_leagues: favoriteLeagues,
        ua: navigator.userAgent.slice(0, 100),
        lang: navigator.language
      })
    });

    if (!res.ok) throw new Error('登録APIでエラー: ' + res.status);

    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
    localStorage.setItem(STORAGE_KEY_CLUBS, JSON.stringify(favoriteClubs));
    localStorage.setItem(STORAGE_KEY_LEAGUES, JSON.stringify(favoriteLeagues));
    localStorage.setItem(SUB_KEY, '1');
    return true;
  },

  async unsubscribe() {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await fetch(API_BASE + '/api/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: sub.endpoint })
      }).catch(() => {});
      await sub.unsubscribe();
    }
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(STORAGE_KEY_CLUBS);
    localStorage.removeItem(STORAGE_KEY_LEAGUES);
    localStorage.removeItem(SUB_KEY);
    return true;
  },

  /**
   * お気に入り（3軸）を更新
   * @param {string[]} favoriteSlugs - 選手slug配列
   * @param {string[]} favoriteClubs - クラブslug配列
   * @param {string[]} favoriteLeagues - リーグslug配列
   */
  async updateFavorites(favoriteSlugs, favoriteClubs = [], favoriteLeagues = []) {
    if (!this.isSubscribed()) {
      // 未購読なら localStorage だけ更新（通知は送られない）
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
      localStorage.setItem(STORAGE_KEY_CLUBS, JSON.stringify(favoriteClubs));
      localStorage.setItem(STORAGE_KEY_LEAGUES, JSON.stringify(favoriteLeagues));
      return;
    }
    // 購読中ならサーバ側のお気に入りも更新（再subscribeで実現）
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await fetch(API_BASE + '/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subscription: sub.toJSON(),
          favorites: favoriteSlugs,
          favorite_clubs: favoriteClubs,
          favorite_leagues: favoriteLeagues,
          ua: navigator.userAgent.slice(0, 100),
          lang: navigator.language
        })
      });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
    localStorage.setItem(STORAGE_KEY_CLUBS, JSON.stringify(favoriteClubs));
    localStorage.setItem(STORAGE_KEY_LEAGUES, JSON.stringify(favoriteLeagues));
  }
};
