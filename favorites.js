// お気に入り選手管理（localStorage 永続化）
// push-client.js と同じキー fjPushFavorites を使用
window.fjFavorites = {
  KEY: 'fjPushFavorites',

  list() {
    try {
      return JSON.parse(localStorage.getItem(this.KEY) || '[]');
    } catch { return []; }
  },

  has(slug) {
    return this.list().includes(slug);
  },

  toggle(slug) {
    const favs = this.list();
    const idx = favs.indexOf(slug);
    if (idx >= 0) {
      favs.splice(idx, 1);
    } else {
      favs.push(slug);
    }
    localStorage.setItem(this.KEY, JSON.stringify(favs));

    // push-client が購読中ならサーバ側も更新
    if (window.fjPush && typeof window.fjPush.updateFavorites === 'function') {
      window.fjPush.updateFavorites(favs).catch(function() {});
    }

    // UIに通知
    var added = favs.includes(slug);
    document.dispatchEvent(new CustomEvent('fj-favorites-changed', {
      detail: { favorites: favs, slug: slug, added: added }
    }));
    return added;
  },

  add(slug) {
    if (!this.has(slug)) this.toggle(slug);
  },

  remove(slug) {
    if (this.has(slug)) this.toggle(slug);
  },

  clear() {
    localStorage.removeItem(this.KEY);
    document.dispatchEvent(new CustomEvent('fj-favorites-changed', {
      detail: { favorites: [] }
    }));
  }
};

// ⭐ ボタンの状態を更新するグローバル関数
function refreshFavBtn(btn) {
  var slug = btn.dataset.slug;
  if (!slug) return;
  var active = window.fjFavorites.has(slug);
  btn.classList.toggle('active', active);
  var star = btn.querySelector('.fav-star');
  if (star) star.textContent = active ? '⭐' : '☆';
  btn.title = active ? 'お気に入りから外す' : 'お気に入りに追加';
}

// ページ読み込み時にすべての ⭐ ボタンの初期状態を反映
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.fav-btn').forEach(function(btn) {
    refreshFavBtn(btn);
  });
});

// お気に入り変更イベント時にページ内のボタンを一括更新
document.addEventListener('fj-favorites-changed', function(e) {
  document.querySelectorAll('.fav-btn').forEach(function(btn) {
    refreshFavBtn(btn);
  });
});
