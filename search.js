/**
 * search.js — 横断検索エンジン
 * - 検索インデックスを初回のみfetch（キャッシュ）
 * - インクリメンタル検索 debounce 150ms
 * - Cmd+K / Ctrl+K でモーダル開閉
 * - ESCで閉じる
 * - localStorage で検索履歴（直近5件）
 */

(function () {
  'use strict';

  // ---- 定数 ----
  const INDEX_URL_JA = '/data/search_index.json';
  const INDEX_URL_EN = '/data/search_index_en.json';
  const HISTORY_KEY = 'fjSearchHistory';
  const MAX_HISTORY = 5;
  const MAX_RESULTS = 15;
  const DEBOUNCE_MS = 150;

  // 英語版かどうかを判定
  const isEnglish = document.documentElement.lang === 'en' ||
                    location.pathname.startsWith('/en/');
  const INDEX_URL = isEnglish ? INDEX_URL_EN : INDEX_URL_JA;

  // ---- 状態 ----
  let indexData = null;   // 検索インデックス（ロード後にキャッシュ）
  let loading = false;

  // ---- 検索インデックス読み込み ----
  async function loadIndex() {
    if (indexData) return indexData;
    if (loading) {
      // 読み込み中は待機
      await new Promise(resolve => {
        const check = setInterval(() => {
          if (!loading) { clearInterval(check); resolve(); }
        }, 50);
      });
      return indexData;
    }
    loading = true;
    try {
      const res = await fetch(INDEX_URL, { cache: 'default' });
      const data = await res.json();
      indexData = data.items || [];
    } catch (e) {
      indexData = [];
    }
    loading = false;
    return indexData;
  }

  // ---- ひらがな⇔カタカナ正規化 ----
  function normalize(text) {
    if (!text) return '';
    return text
      .toLowerCase()
      // カタカナ→ひらがな
      .replace(/[\u30A1-\u30F6]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60))
      // 全角英数→半角
      .replace(/[Ａ-Ｚａ-ｚ０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
      .trim();
  }

  // ---- 検索ロジック ----
  function search(query, items) {
    if (!query) return [];
    const q = normalize(query);
    if (!q) return [];

    const results = [];

    for (const item of items) {
      const nameJa = normalize(item.name_ja || '');
      const nameEn = normalize(item.name_en || '');
      const subtitle = normalize(item.subtitle || '');

      // マッチング
      const inJa = nameJa.includes(q);
      const inEn = nameEn.includes(q);
      const inSub = subtitle.includes(q);

      if (!inJa && !inEn && !inSub) continue;

      // スコアリング（先頭一致を優先）
      let score = 0;
      if (nameJa === q || nameEn === q) score += 100;
      if (nameJa.startsWith(q) || nameEn.startsWith(q)) score += 50;
      if (inJa || inEn) score += 20;
      if (inSub) score += 5;

      results.push({ item, score });
    }

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, MAX_RESULTS).map(r => r.item);
  }

  // ---- 検索履歴 ----
  function getHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    } catch {
      return [];
    }
  }

  function addHistory(query) {
    if (!query.trim()) return;
    let hist = getHistory().filter(h => h !== query);
    hist.unshift(query);
    hist = hist.slice(0, MAX_HISTORY);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(hist));
    } catch {}
  }

  // ---- 公開API ----
  window.fjSearch = {
    loadIndex,
    search,
    getHistory,
    addHistory,
    normalize,
    isEnglish,
    MAX_RESULTS,
  };

  // ---- Cmd+K / Ctrl+K ショートカット ----
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (typeof window.openSearchModal === 'function') {
        window.openSearchModal();
      }
    }
    if (e.key === 'Escape') {
      const modal = document.getElementById('fjSearchModal');
      if (modal) modal.remove();
    }
  });

})();
