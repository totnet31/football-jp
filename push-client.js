// Push通知購読クライアント
// 使い方：window.fjPush.subscribe(['mitoma', 'kubo']) / window.fjPush.unsubscribe()

const VAPID_PUBLIC_KEY = 'BOQ4LvD-tUTTYj8E7_L28zVtbio-10Brm8oFzwBlCd2gVlG-wPt_YfOzPdtEJ-wwnN8DUdEoXBJGoUQHkyllvb8';
const API_BASE = 'https://football-jp-push-api.saito-dfe.workers.dev'; // Cloudflare Workers（2026-05-07 デプロイ）
const STORAGE_KEY = 'fjPushFavorites';
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

  async subscribe(favoriteSlugs = []) {
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
        ua: navigator.userAgent.slice(0, 100),
        lang: navigator.language
      })
    });

    if (!res.ok) throw new Error('登録APIでエラー: ' + res.status);

    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
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
    localStorage.removeItem(SUB_KEY);
    return true;
  },

  getFavorites() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch { return []; }
  },

  isSubscribed() {
    return localStorage.getItem(SUB_KEY) === '1';
  },

  async updateFavorites(favoriteSlugs) {
    if (!this.isSubscribed()) {
      // 未購読なら何もしない（通知も送られないので）
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
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
          ua: navigator.userAgent.slice(0, 100),
          lang: navigator.language
        })
      });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteSlugs));
  }
};
