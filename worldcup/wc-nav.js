// W杯特集ページ 共通ナビゲーション（細線SVGアイコン付き）
(function() {
  const ICONS = {
    home: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z"/></svg>',
    jp: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="1"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/></svg>',
    groups: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h16"/><path d="M7 20v-5"/><path d="M12 20v-9"/><path d="M17 20v-13"/></svg>',
    trophy: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5v1.5a2.5 2.5 0 0 0 2.5 2.5"/><path d="M16 6h3v1.5a2.5 2.5 0 0 1-2.5 2.5"/><path d="M12 13v3"/><path d="M9 19h6l-1-3h-4z"/></svg>',
    globe: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18"/><path d="M12 3a14 14 0 0 0 0 18"/></svg>',
    scroll: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M16 4v3h3"/><path d="M8 11h8M8 14h8M8 17h5"/></svg>',
    history: '<svg class="wc-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3v6h6"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 3"/><path d="M12 7v5l3 3"/></svg>'
  };

  const ITEMS = [
    { href: './',              icon: 'home',   label: 'トップ',         key: 'home' },
    { href: './japan.html',    icon: 'jp',     label: '日本代表',        key: 'japan' },
    { href: './groups.html',   icon: 'groups', label: 'グループ順位',     key: 'groups' },
    { href: './bracket.html',  icon: 'trophy', label: 'トーナメント',    key: 'bracket' },
    { href: './countries.html',icon: 'globe',  label: '48か国',          key: 'countries' },
    { href: './rules.html',    icon: 'scroll', label: 'ルール',          key: 'rules' },
    { href: './history.html',  icon: 'history',label: '歴代の歴史',       key: 'history' }
  ];

  window.wcRenderNav = function(activeKey) {
    return ITEMS.map(it => {
      const cls = it.key === activeKey ? ' class="active"' : '';
      return `<a href="${it.href}"${cls}>${ICONS[it.icon]}<span>${it.label}</span></a>`;
    }).join('');
  };
})();
