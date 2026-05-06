// Push通知設定モーダル（3タブ式：選手 / クラブ / リーグ）
async function openPushModal() {
  // 既存モーダルがあれば削除
  document.getElementById('fjPushModal')?.remove();

  // 選手・クラブ・リーグのデータを並列取得
  let players = [], clubs = {}, standings = {};
  try {
    const [playersRes, clubsRes, standingsRes] = await Promise.all([
      fetch('/data/players.json'),
      fetch('/data/clubs.json'),
      fetch('/data/standings.json')
    ]);
    if (playersRes.ok) {
      const raw = await playersRes.json();
      players = Array.isArray(raw) ? raw : (raw.players || []);
    }
    if (clubsRes.ok) {
      const raw = await clubsRes.json();
      clubs = raw.clubs || {};
    }
    if (standingsRes.ok) {
      const raw = await standingsRes.json();
      standings = raw.competitions || {};
    }
  } catch (e) {
    // フォールバック：データ取得失敗時は空
  }

  const favPlayers  = window.fjPush.getFavorites();
  const favClubs    = window.fjPush.getFavoriteClubs();
  const favLeagues  = window.fjPush.getFavoriteLeagues();
  const subscribed  = window.fjPush.isSubscribed();

  // モーダル作成
  const modal = document.createElement('div');
  modal.id = 'fjPushModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px;';

  const iosWarning = (window.fjPush.isIOS() && !window.fjPush.isStandalone())
    ? '<br><strong style="color:#fbbf24;">⚠️ iPhoneでは「ホーム画面に追加」してから利用ください</strong>'
    : '';

  // ---- 選手タブのコンテンツ ----
  const playerItems = players.map(p => {
    const slug = p.slug || (p.name_en || '').toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '');
    const checked = favPlayers.includes(slug) ? 'checked' : '';
    const label = p.name_ja || p.name || slug;
    const sub = p.club_ja ? `<span style="color:#64748b;font-size:11px;">${p.club_ja}</span>` : '';
    return `<label style="display:flex;align-items:center;gap:6px;padding:6px;background:#1e293b;border-radius:6px;font-size:13px;cursor:pointer;">
      <input type="checkbox" data-tab="player" data-slug="${slug}" ${checked} style="margin:0;flex-shrink:0;">
      <span style="display:flex;flex-direction:column;gap:1px;">${label}${sub}</span>
    </label>`;
  }).join('');

  // ---- クラブタブのコンテンツ ----
  // 日本人選手のいるクラブを先頭に表示
  const jpClubIds = new Set(players.map(p => String(p.club_id || '')));
  // クラブID→slug変換（英語名から生成）
  // clubs.json は { "57": "アーセナル", ... } 形式なのでslugはID文字列をキーとして使う
  const clubEntries = Object.entries(clubs);
  // 日本人選手クラブ→その他の順にソート
  clubEntries.sort((a, b) => {
    const aJp = jpClubIds.has(a[0]) ? 0 : 1;
    const bJp = jpClubIds.has(b[0]) ? 0 : 1;
    return aJp - bJp;
  });

  const clubItems = clubEntries.map(([id, name_ja]) => {
    const slug = `club-${id}`;
    const checked = favClubs.includes(slug) ? 'checked' : '';
    const hasJp = jpClubIds.has(id) ? '⭐ ' : '';
    return `<label style="display:flex;align-items:center;gap:6px;padding:6px;background:#1e293b;border-radius:6px;font-size:13px;cursor:pointer;">
      <input type="checkbox" data-tab="club" data-slug="${slug}" ${checked} style="margin:0;flex-shrink:0;">
      <span>${hasJp}${name_ja}</span>
    </label>`;
  }).join('');

  // ---- リーグタブのコンテンツ ----
  // リーグ表示順（主要リーグ優先）
  const LEAGUE_ORDER = ['39', '140', '78', '135', '61', '88', '94', '2', '40', '144'];
  const sortedLeagues = Object.entries(standings).sort((a, b) => {
    const ai = LEAGUE_ORDER.indexOf(a[0]);
    const bi = LEAGUE_ORDER.indexOf(b[0]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  const leagueItems = sortedLeagues.map(([id, comp]) => {
    const slug = `league-${id}`;
    const checked = favLeagues.includes(slug) ? 'checked' : '';
    const flag = comp.flag || '';
    const name = comp.name_ja || `League ${id}`;
    return `<label style="display:flex;align-items:center;gap:6px;padding:8px;background:#1e293b;border-radius:6px;font-size:13px;cursor:pointer;">
      <input type="checkbox" data-tab="league" data-slug="${slug}" ${checked} style="margin:0;flex-shrink:0;">
      <span>${flag} ${name}</span>
    </label>`;
  }).join('');

  const unsubBtn = subscribed
    ? '<button id="fjPushUnsub" style="background:#7f1d1d;color:#fee2e2;border:none;border-radius:6px;padding:10px 14px;cursor:pointer;font-size:14px;">通知を停止</button>'
    : '';
  const saveLabel = subscribed ? '保存' : '通知を有効にする';

  modal.innerHTML = `
    <div style="background:#0b1220;border:1px solid #334155;border-radius:12px;padding:20px;max-width:500px;width:100%;max-height:85vh;overflow:auto;color:#e2e8f0;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <h2 style="margin:0;font-size:18px;">🔔 通知設定</h2>
        <button id="fjPushClose" style="background:none;border:none;color:#94a3b8;font-size:22px;cursor:pointer;">×</button>
      </div>
      <p style="color:#94a3b8;font-size:12px;margin:0 0 12px;">
        毎週月曜朝7時に今週の試合予定をお届けします。${iosWarning}
      </p>

      <!-- タブナビ -->
      <div id="fjPushTabs" style="display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:8px;">
        <button data-tab="player" class="fj-tab-btn fj-tab-active" style="flex:1;padding:7px;border:none;border-radius:6px;cursor:pointer;font-size:13px;background:#1e40af;color:#fff;">👤 選手</button>
        <button data-tab="club"   class="fj-tab-btn" style="flex:1;padding:7px;border:none;border-radius:6px;cursor:pointer;font-size:13px;background:#1e293b;color:#94a3b8;">🏟 クラブ</button>
        <button data-tab="league" class="fj-tab-btn" style="flex:1;padding:7px;border:none;border-radius:6px;cursor:pointer;font-size:13px;background:#1e293b;color:#94a3b8;">🏆 リーグ</button>
      </div>

      <!-- タブパネル -->
      <div id="fjTab-player" class="fj-tab-panel" style="display:block;">
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:5px;max-height:300px;overflow-y:auto;padding:2px;">
          ${playerItems || '<p style="color:#64748b;font-size:13px;">選手データを読み込めませんでした</p>'}
        </div>
        <p style="font-size:11px;color:#64748b;margin:6px 0 0;">⭐なし = 選手未選択時は通知なし</p>
      </div>

      <div id="fjTab-club" class="fj-tab-panel" style="display:none;">
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:5px;max-height:300px;overflow-y:auto;padding:2px;">
          ${clubItems || '<p style="color:#64748b;font-size:13px;">クラブデータを読み込めませんでした</p>'}
        </div>
        <p style="font-size:11px;color:#64748b;margin:6px 0 0;">⭐ = 日本人選手在籍クラブ</p>
      </div>

      <div id="fjTab-league" class="fj-tab-panel" style="display:none;">
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:5px;max-height:300px;overflow-y:auto;padding:2px;">
          ${leagueItems || '<p style="color:#64748b;font-size:13px;">リーグデータを読み込めませんでした</p>'}
        </div>
      </div>

      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
        ${unsubBtn}
        <button id="fjPushSave" style="background:#22c55e;color:#0b1220;border:none;border-radius:6px;padding:10px 14px;cursor:pointer;font-size:14px;font-weight:bold;">${saveLabel}</button>
      </div>
      <div id="fjPushMsg" style="margin-top:12px;font-size:13px;color:#94a3b8;"></div>
    </div>
  `;
  document.body.appendChild(modal);

  // タブ切替
  modal.querySelectorAll('.fj-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = btn.dataset.tab;
      modal.querySelectorAll('.fj-tab-btn').forEach(b => {
        b.style.background = '#1e293b';
        b.style.color = '#94a3b8';
        b.classList.remove('fj-tab-active');
      });
      btn.style.background = '#1e40af';
      btn.style.color = '#fff';
      btn.classList.add('fj-tab-active');
      modal.querySelectorAll('.fj-tab-panel').forEach(p => p.style.display = 'none');
      document.getElementById(`fjTab-${t}`).style.display = 'block';
    });
  });

  document.getElementById('fjPushClose').onclick = () => modal.remove();
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  const msg = document.getElementById('fjPushMsg');

  document.getElementById('fjPushSave').onclick = async () => {
    const getChecked = (tab) =>
      Array.from(modal.querySelectorAll(`input[data-tab="${tab}"]:checked`)).map(c => c.dataset.slug);

    const favs        = getChecked('player');
    const favClubsNew  = getChecked('club');
    const favLeaguesNew = getChecked('league');

    msg.textContent = '処理中...';
    msg.style.color = '#94a3b8';
    try {
      if (subscribed) {
        await window.fjPush.updateFavorites(favs, favClubsNew, favLeaguesNew);
        msg.textContent = '✅ 保存しました';
        msg.style.color = '#22c55e';
      } else {
        await window.fjPush.subscribe(favs, favClubsNew, favLeaguesNew);
        msg.textContent = '✅ 通知を有効にしました';
        msg.style.color = '#22c55e';
      }
      setTimeout(() => modal.remove(), 1500);
    } catch (e) {
      msg.textContent = '❌ ' + e.message;
      msg.style.color = '#ef4444';
    }
  };

  if (subscribed) {
    document.getElementById('fjPushUnsub').onclick = async () => {
      msg.textContent = '解除中...';
      try {
        await window.fjPush.unsubscribe();
        msg.textContent = '✅ 通知を停止しました';
        msg.style.color = '#22c55e';
        setTimeout(() => modal.remove(), 1500);
      } catch (e) {
        msg.textContent = '❌ ' + e.message;
        msg.style.color = '#ef4444';
      }
    };
  }
}

window.openPushModal = openPushModal;
