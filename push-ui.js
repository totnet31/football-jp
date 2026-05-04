// シンプルなモーダル：お気に入り選手選択 + 購読/解除
async function openPushModal() {
  // 既存モーダルがあれば削除
  document.getElementById('fjPushModal')?.remove();

  // 選手リスト取得（data/players.json から名前と slug）
  let players = [];
  try {
    const playersRes = await fetch('/data/players.json');
    if (playersRes.ok) {
      const raw = await playersRes.json();
      // players.json はトップレベルが配列
      players = Array.isArray(raw) ? raw : (raw.players || []);
    }
  } catch (e) {
    // フォールバック：選手リスト取得失敗時は空欄
    players = [];
  }

  const fav = window.fjPush.getFavorites();
  const subscribed = window.fjPush.isSubscribed();

  const modal = document.createElement('div');
  modal.id = 'fjPushModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px;';

  const iosWarning = (window.fjPush.isIOS() && !window.fjPush.isStandalone())
    ? '<br><strong style="color:#fbbf24;">⚠️ iPhoneでは「ホーム画面に追加」してから利用ください</strong>'
    : '';

  const playerItems = players.map(p => {
    const slug = p.slug || (p.name_en || '').toLowerCase().replace(/\s+/g, '-');
    const checked = fav.includes(slug) ? 'checked' : '';
    const label = p.name_ja || p.name || slug;
    return `<label style="display:flex;align-items:center;gap:6px;padding:6px;background:#1e293b;border-radius:6px;font-size:13px;cursor:pointer;">
      <input type="checkbox" data-slug="${slug}" ${checked} style="margin:0;">
      ${label}
    </label>`;
  }).join('');

  const unsubBtn = subscribed
    ? '<button id="fjPushUnsub" style="background:#7f1d1d;color:#fee2e2;border:none;border-radius:6px;padding:10px 14px;cursor:pointer;font-size:14px;">通知を停止</button>'
    : '';
  const saveLabel = subscribed ? '保存' : '通知を有効にする';

  modal.innerHTML = `
    <div style="background:#0b1220;border:1px solid #334155;border-radius:12px;padding:20px;max-width:480px;width:100%;max-height:80vh;overflow:auto;color:#e2e8f0;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h2 style="margin:0;font-size:18px;">🔔 通知設定</h2>
        <button id="fjPushClose" style="background:none;border:none;color:#94a3b8;font-size:22px;cursor:pointer;">×</button>
      </div>
      <p style="color:#94a3b8;font-size:13px;margin:0 0 12px;">
        毎週月曜朝7時に「お気に入り選手の今週の試合予定」をお届けします。${iosWarning}
      </p>
      <div style="margin:8px 0 12px;">
        <strong style="font-size:14px;">お気に入り選手を選択：</strong>
        <div id="fjPlayersGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px;margin-top:8px;max-height:280px;overflow-y:auto;padding:4px;">
          ${playerItems || '<p style="color:#64748b;font-size:13px;">選手データを読み込めませんでした</p>'}
        </div>
        <p style="font-size:11px;color:#64748b;margin:4px 0 0;">※ 選手未選択の場合、通知は送られません</p>
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
        ${unsubBtn}
        <button id="fjPushSave" style="background:#22c55e;color:#0b1220;border:none;border-radius:6px;padding:10px 14px;cursor:pointer;font-size:14px;font-weight:bold;">${saveLabel}</button>
      </div>
      <div id="fjPushMsg" style="margin-top:12px;font-size:13px;color:#94a3b8;"></div>
    </div>
  `;
  document.body.appendChild(modal);

  document.getElementById('fjPushClose').onclick = () => modal.remove();
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  const msg = document.getElementById('fjPushMsg');

  document.getElementById('fjPushSave').onclick = async () => {
    const checks = modal.querySelectorAll('input[type="checkbox"]:checked');
    const favs = Array.from(checks).map(c => c.dataset.slug);
    msg.textContent = '処理中...';
    msg.style.color = '#94a3b8';
    try {
      if (subscribed) {
        await window.fjPush.updateFavorites(favs);
        msg.textContent = '✅ 保存しました';
        msg.style.color = '#22c55e';
      } else {
        await window.fjPush.subscribe(favs);
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
