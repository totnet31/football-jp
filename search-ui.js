/**
 * search-ui.js — 検索UIモーダル
 * push-ui.js と同じデザイン言語で実装。
 * search.js が先に読み込まれている必要がある。
 */

(function () {
  'use strict';

  const isEn = window.fjSearch && window.fjSearch.isEnglish;

  const T = {
    title:     isEn ? '🔍 Search' : '🔍 検索',
    placeholder: isEn ? 'Player, club, league, country...' : '選手・クラブ・リーグ・国を検索...',
    noResult:  isEn ? 'No results found.' : '該当する選手・クラブ・国が見つかりません',
    loading:   isEn ? 'Loading...' : '読み込み中...',
    history:   isEn ? 'Recent searches' : '最近の検索',
    shortcut:  isEn ? 'Cmd+K / Ctrl+K' : 'Cmd+K / Ctrl+K',
    typeLabels: {
      player:  isEn ? '👤 Player'  : '👤 選手',
      club:    isEn ? '⚽ Club'    : '⚽ クラブ',
      league:  isEn ? '📋 League'  : '📋 リーグ',
      country: isEn ? '🏆 Country' : '🏆 国',
    },
  };

  function getTypeIcon(type) {
    return { player:'👤', club:'⚽', league:'📋', country:'🏆' }[type] || '🔎';
  }

  function renderItem(item, query) {
    const icon = getTypeIcon(item.type);
    const typeLabel = T.typeLabels[item.type] || item.type;
    // ハイライト（シンプルに部分一致を太字化）
    const displayName = item.name_ja || item.name_en;
    return `
      <a href="${item.url}" class="fjSearch-item" data-query="${escHtml(query)}" data-name="${escHtml(displayName)}">
        <span class="fjSearch-icon">${icon}</span>
        <span class="fjSearch-info">
          <span class="fjSearch-name">${escHtml(displayName)}</span>
          <span class="fjSearch-meta">
            <span class="fjSearch-type">${typeLabel}</span>
            ${item.subtitle ? `<span class="fjSearch-sub"> · ${escHtml(item.subtitle)}</span>` : ''}
          </span>
        </span>
      </a>`;
  }

  function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  let debounceTimer = null;

  async function openSearchModal() {
    // 既存モーダルがあれば削除
    document.getElementById('fjSearchModal')?.remove();

    const modal = document.createElement('div');
    modal.id = 'fjSearchModal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', T.title);
    modal.className = 'fjSearch-overlay';

    modal.innerHTML = `
      <div class="fjSearch-box">
        <div class="fjSearch-header">
          <h2 class="fjSearch-title">${T.title}</h2>
          <button class="fjSearch-close" aria-label="閉じる">×</button>
        </div>
        <div class="fjSearch-input-wrap">
          <input
            type="search"
            id="fjSearchInput"
            class="fjSearch-input"
            placeholder="${T.placeholder}"
            autocomplete="off"
            autocorrect="off"
            spellcheck="false"
          >
        </div>
        <div id="fjSearchResults" class="fjSearch-results"></div>
        <div class="fjSearch-footer">
          <span>${T.shortcut}</span>
          <span style="color:#64748b">· ESC で閉じる</span>
        </div>
      </div>`;

    document.body.appendChild(modal);

    const input = document.getElementById('fjSearchInput');
    const resultsEl = document.getElementById('fjSearchResults');

    // 閉じる
    modal.querySelector('.fjSearch-close').onclick = () => modal.remove();
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

    // 結果クリック → 履歴保存
    resultsEl.addEventListener('click', e => {
      const a = e.target.closest('.fjSearch-item');
      if (a && a.dataset.query) {
        window.fjSearch.addHistory(a.dataset.query);
      }
    });

    // 履歴表示関数
    function showHistory() {
      const hist = window.fjSearch.getHistory();
      if (hist.length === 0) {
        resultsEl.innerHTML = '';
        return;
      }
      let html = `<div class="fjSearch-section-label">${T.history}</div>`;
      hist.forEach(h => {
        html += `<button class="fjSearch-history-item" data-q="${escHtml(h)}">🕐 ${escHtml(h)}</button>`;
      });
      resultsEl.innerHTML = html;
      resultsEl.querySelectorAll('.fjSearch-history-item').forEach(btn => {
        btn.onclick = () => {
          input.value = btn.dataset.q;
          runSearch(btn.dataset.q);
        };
      });
    }

    // 検索実行
    async function runSearch(query) {
      const q = query.trim();
      if (!q) {
        showHistory();
        return;
      }
      resultsEl.innerHTML = `<div class="fjSearch-loading">${T.loading}</div>`;
      const items = await window.fjSearch.loadIndex();
      const results = window.fjSearch.search(q, items);

      if (results.length === 0) {
        resultsEl.innerHTML = `<div class="fjSearch-no-result">${T.noResult}</div>`;
        return;
      }
      resultsEl.innerHTML = results.map(item => renderItem(item, q)).join('');
    }

    // デバウンス付き入力イベント
    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (!q) { showHistory(); return; }
      debounceTimer = setTimeout(() => runSearch(q), 150);
    });

    // ESC
    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') { modal.remove(); }
    });

    // 初期表示：履歴
    showHistory();

    // オートフォーカス
    requestAnimationFrame(() => input.focus());

    // インデックスをプリロード（ユーザーが入力する前に取得を開始）
    window.fjSearch.loadIndex();
  }

  window.openSearchModal = openSearchModal;

})();
