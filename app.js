(function () {
  const scheduleEl = document.getElementById('scheduleView');
  const resultsEl = document.getElementById('resultsView');
  const calendarEl = document.getElementById('calendarView');
  const rankingEl = document.getElementById('rankingView');
  const calGridEl = document.getElementById('calGrid');
  const calMonthLabelEl = document.getElementById('calMonthLabel');
  const calDayDetailEl = document.getElementById('calDayDetail');
  const updatedEl = document.getElementById('updated');
  const periodEl = document.getElementById('period');
  const onlyJpEl = document.getElementById('onlyJp');
  const leagueChecksEl = document.getElementById('leagueChecks');
  const matchFiltersEl = document.getElementById('matchFilters');
  const rankLeagueEl = document.getElementById('rankLeague');
  const standingsContentEl = document.getElementById('standingsContent');
  const scorersContentEl = document.getElementById('scorersContent');
  const viewTabs = document.querySelectorAll('.view-tab');
  const sortBtns = document.querySelectorAll('.sort-btn');

  const WEEKDAY = ['日', '月', '火', '水', '木', '金', '土'];

  let allMatches = [];
  let standingsData = null;
  let scorersData = null;
  let jpPlayerNames = new Set();   // 日本人選手名（ローマ字）の集合（ハイライト用）
  let jpClubIds = new Set();       // 日本人選手が所属するクラブID
  let jpPlayersByClub = new Map(); // クラブID → 選手名(日本語)の配列
  let dataRangeFrom = null;
  let dataRangeTo = null;
  const enabledLeagues = new Set();
  let currentView = localStorage.getItem('view') || 'schedule';
  if (currentView === 'list') currentView = 'schedule';
  let calCursor = null;
  let calSelected = null;
  let currentRankLeague = null;
  let currentSort = 'goals';

  function pad(n) { return String(n).padStart(2, '0'); }

  function dateKey(iso) {
    const d = new Date(iso);
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  }

  function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  }

  function fmtDateHeading(key) {
    const [y, m, d] = key.split('-').map(Number);
    const date = new Date(y, m-1, d);
    return `${y}年${m}月${d}日（${WEEKDAY[date.getDay()]}）`;
  }

  function fmtUpdated(iso) {
    const d = new Date(iso);
    return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fmtDateShort(s) {
    if (!s) return '';
    const [y, m, d] = s.split('-');
    return `${Number(y)}/${Number(m)}/${Number(d)}`;
  }

  function fmtTime(iso) {
    const d = new Date(iso);
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function diffDays(iso) {
    const d = new Date(iso);
    const today = new Date();
    today.setHours(0,0,0,0);
    const matchDay = new Date(d);
    matchDay.setHours(0,0,0,0);
    return Math.round((matchDay - today) / 86400000);
  }

  async function loadAll() {
    try {
      const [m, s, sc, players] = await Promise.all([
        fetchJson('data/matches.json'),
        fetchJson('data/standings.json').catch(() => null),
        fetchJson('data/scorers.json').catch(() => null),
        fetchJson('data/players.json').catch(() => null),
      ]);
      allMatches = m.matches || [];
      standingsData = s;
      scorersData = sc;
      // 実際の試合データの最小・最大日付（JST）から範囲を算出。
      // API側のdate_from/date_toはUTC基準のため時差で1日ズレる試合があるので、
      // 実データから求める方がカレンダーのグレーアウトと整合する。
      if (allMatches.length > 0) {
        const keys = allMatches.map(x => dateKey(x.kickoff_jst));
        keys.sort();
        dataRangeFrom = keys[0];
        dataRangeTo = keys[keys.length - 1];
      } else {
        dataRangeFrom = m.date_from;
        dataRangeTo = m.date_to;
      }
      if (players) {
        for (const p of players.players || []) {
          if (p.name_en) jpPlayerNames.add(p.name_en.toLowerCase());
          if (p.club_id != null) {
            const cid = Number(p.club_id);
            jpClubIds.add(cid);
            if (!jpPlayersByClub.has(cid)) jpPlayersByClub.set(cid, []);
            jpPlayersByClub.get(cid).push(p.name_ja);
          }
        }
      }
      const updated = fmtUpdated(m.updated);
      updatedEl.textContent = `更新: ${updated} / ${m.match_count}試合`;
      periodEl.textContent = `データ期間: ${fmtDateShort(dataRangeFrom)} 〜 ${fmtDateShort(dataRangeTo)}（過去7日 〜 今後14日）`;
      buildLeagueChecks();
      buildRankLeagueOptions();
      initCalCursor();
      switchView(currentView);
    } catch (e) {
      listEl.innerHTML = `<p class="empty">データの読み込みに失敗しました: ${escape(e.message)}<br>scripts/fetch_matches.py を実行してください。</p>`;
    }
  }

  async function fetchJson(path) {
    const res = await fetch(path + '?_=' + Date.now());
    if (!res.ok) throw new Error(`${path} が読み込めません (${res.status})`);
    return res.json();
  }

  function initCalCursor() {
    const now = new Date();
    calCursor = { year: now.getFullYear(), month: now.getMonth() };
    calSelected = todayKey();
  }

  function buildLeagueChecks() {
    const seen = new Map();
    for (const m of allMatches) {
      if (!seen.has(m.competition_id)) {
        seen.set(m.competition_id, { name: m.competition_ja, flag: m.competition_flag || '' });
      }
    }
    leagueChecksEl.innerHTML = '';
    for (const [id, meta] of seen) {
      enabledLeagues.add(id);
      const wrap = document.createElement('label');
      wrap.innerHTML = `<input type="checkbox" data-lg="${id}" checked> ${meta.flag} ${escape(meta.name)}`;
      leagueChecksEl.appendChild(wrap);
    }
    leagueChecksEl.addEventListener('change', e => {
      const t = e.target;
      if (t.dataset && t.dataset.lg) {
        const id = Number(t.dataset.lg);
        if (t.checked) enabledLeagues.add(id);
        else enabledLeagues.delete(id);
        rerender();
      }
    });
  }

  function buildRankLeagueOptions() {
    if (!standingsData) return;
    rankLeagueEl.innerHTML = '';
    // 表示順を固定（CL/欧州大会は末尾、国内リーグはカテゴリ順）
    const order = [39, 40, 140, 78, 135, 61, 88, 2];
    const allIds = Object.keys(standingsData.competitions || {});
    const ids = order
      .filter(n => allIds.includes(String(n)))
      .map(String)
      .concat(allIds.filter(s => !order.map(String).includes(s)));
    for (const id of ids) {
      const meta = standingsData.competitions[id];
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = `${meta.flag || ''} ${meta.name_ja}`;
      rankLeagueEl.appendChild(opt);
    }
    if (ids.length > 0) {
      currentRankLeague = ids[0];
      rankLeagueEl.value = currentRankLeague;
    }
    rankLeagueEl.addEventListener('change', () => {
      currentRankLeague = rankLeagueEl.value;
      renderRanking();
    });
  }

  function filtered() {
    const onlyJp = onlyJpEl.checked;
    return allMatches.filter(m => {
      if (!enabledLeagues.has(m.competition_id)) return false;
      if (onlyJp && (!m.japanese_players || m.japanese_players.length === 0)) return false;
      // 両チームともTBD（CLノックアウト等の未確定試合）はAPI側で名前未確定なので非表示
      if (m.home_ja === '未定' && m.away_ja === '未定') return false;
      return true;
    });
  }

  function switchView(view) {
    currentView = view;
    localStorage.setItem('view', view);
    viewTabs.forEach(t => t.classList.toggle('active', t.dataset.view === view));
    scheduleEl.classList.toggle('hidden', view !== 'schedule');
    resultsEl.classList.toggle('hidden', view !== 'results');
    calendarEl.classList.toggle('hidden', view !== 'calendar');
    rankingEl.classList.toggle('hidden', view !== 'ranking');
    matchFiltersEl.classList.toggle('hidden', view === 'ranking');
    rerender();
  }

  function rerender() {
    if (currentView === 'schedule') renderSchedule();
    else if (currentView === 'results') renderResults();
    else if (currentView === 'calendar') renderCalendar();
    else if (currentView === 'ranking') renderRanking();
  }

  // ===== Schedule view =====
  function renderSchedule() {
    const matches = filtered().filter(m => m.status !== 'FINISHED');
    if (matches.length === 0) {
      scheduleEl.innerHTML = `<p class="empty">予定されている試合はありません。<br>フィルタ条件を変更してください。</p>`;
      return;
    }
    const groups = new Map();
    for (const m of matches) {
      const k = dateKey(m.kickoff_jst);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(m);
    }
    const today = todayKey();
    const html = [];
    for (const [key, ms] of groups) {
      const isToday = key === today;
      html.push(`<h2 class="date-heading${isToday ? ' today' : ''}">${fmtDateHeading(key)}${isToday ? ' ・ 今日' : ''}</h2>`);
      for (const m of ms) html.push(renderMatch(m, isToday));
    }
    scheduleEl.innerHTML = html.join('');
  }

  // ===== Results view =====
  function renderResults() {
    const matches = filtered().filter(m => m.status === 'FINISHED').slice().reverse();
    if (matches.length === 0) {
      resultsEl.innerHTML = `<p class="empty">直近の結果はありません。<br>フィルタ条件を変更してください。</p>`;
      return;
    }
    const groups = new Map();
    for (const m of matches) {
      const k = dateKey(m.kickoff_jst);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(m);
    }
    const today = todayKey();
    const html = [];
    for (const [key, ms] of groups) {
      const isToday = key === today;
      html.push(`<h2 class="date-heading${isToday ? ' today' : ''}">${fmtDateHeading(key)}${isToday ? ' ・ 今日' : ''}</h2>`);
      for (const m of ms) html.push(renderMatch(m, isToday));
    }
    resultsEl.innerHTML = html.join('');
  }

  function renderMatch(m, isToday) {
    const finished = m.status === 'FINISHED';
    const live = m.status === 'IN_PLAY' || m.status === 'PAUSED';
    const time = fmtTime(m.kickoff_jst);
    const dd = diffDays(m.kickoff_jst);

    let timeLabel;
    if (finished) timeLabel = `<small>終了</small>${time}`;
    else if (live) timeLabel = `<small>LIVE</small>${time}`;
    else timeLabel = time + (dd > 0 ? `<small>${dd}日後</small>` : (dd < 0 ? `<small>${-dd}日前</small>` : ''));

    const score = m.score;
    const homeWin = score && score.home > score.away;
    const awayWin = score && score.away > score.home;

    const homeJp = (m.japanese_players || []).filter(p => p.side === 'home');
    const awayJp = (m.japanese_players || []).filter(p => p.side === 'away');

    const teamRow = (name, crest, scoreVal, win, jp) => {
      const jpHtml = jp.length > 0
        ? `<span class="team-jp">🇯🇵 ${jp.map(p => escape(p.name_ja)).join('・')}</span>`
        : '';
      const crestHtml = crest ? `<img class="team-crest" src="${escape(crest)}" alt="" loading="lazy">` : '<span class="team-crest"></span>';
      const scoreHtml = scoreVal != null ? `<span class="team-score">${scoreVal}</span>` : '';
      return `<div class="team-row${win ? ' winner' : ''}">
        ${crestHtml}
        <div class="team-mid">
          <span class="team-name">${escape(name)}</span>
          ${jpHtml}
        </div>
        ${scoreHtml}
      </div>`;
    };

    // タグを2グループに分離（リーグ＋ステージ／放送局）して見やすく
    const primaryTags = [];
    primaryTags.push(`<span class="league-tag cat-league-${m.competition_id}">${m.competition_flag || ''} ${escape(m.competition_ja)}</span>`);
    if (live) primaryTags.push(`<span class="status-tag status-live">LIVE</span>`);
    if (m.stage && m.stage !== 'REGULAR_SEASON') {
      primaryTags.push(`<span class="status-tag">${escape(stageLabel(m.stage))}</span>`);
    }

    const broadcasterTags = [];
    if (m.broadcasters && m.broadcasters.length > 0) {
      for (const b of m.broadcasters) {
        const brandCls = bcBrandClass(b.name);
        if (b.url) {
          broadcasterTags.push(`<a class="bc-tag ${brandCls}" href="${escape(b.url)}" target="_blank" rel="noopener"><span class="bc-play">▶</span>${escape(b.name)}</a>`);
        } else {
          broadcasterTags.push(`<span class="bc-tag ${brandCls}"><span class="bc-play">▶</span>${escape(b.name)}</span>`);
        }
      }
    }

    const cls = ['match'];
    if (isToday) cls.push('today');
    if (finished) cls.push('finished');

    // ハイライト動画リンク（試合終了時のみ・1試合に1ボタン・YouTubeスタイル）
    let highlightCell = '';
    if (finished && Array.isArray(m.highlights) && m.highlights.length > 0) {
      const first = m.highlights.find(h => h.url || h.video_id);
      if (first) {
        const url = first.url || `https://youtu.be/${first.video_id}`;
        highlightCell = `<a class="match-highlight" href="${escape(url)}" target="_blank" rel="noopener" aria-label="ハイライト動画（YouTube）">▶ ハイライト</a>`;
      }
    }

    return `<div class="${cls.join(' ')}">
      <div class="match-top${highlightCell ? ' has-highlight' : ''}">
        <div class="kickoff">${timeLabel}</div>
        <div class="teams">
          ${teamRow(m.home_ja, m.home_crest, score ? score.home : null, homeWin, homeJp)}
          ${teamRow(m.away_ja, m.away_crest, score ? score.away : null, awayWin, awayJp)}
        </div>
        ${highlightCell}
      </div>
      <div class="tags">
        <div class="tags-row primary">${primaryTags.join('')}</div>
        ${broadcasterTags.length ? `<div class="tags-row broadcasters">${broadcasterTags.join('')}</div>` : ''}
      </div>
    </div>`;
  }

  function bcBrandClass(name) {
    const n = String(name || '').toLowerCase();
    if (n.includes('wowow')) return 'bc-wowow';
    if (n.includes('dazn')) return 'bc-dazn';
    if (n.includes('lemino')) return 'bc-lemino';
    if (n.includes('abema')) return 'bc-abema';
    if (n.includes('u-next') || n.includes('unext')) return 'bc-unext';
    if (n.includes('bs10')) return 'bc-bs10';
    return 'bc-default';
  }

  function stageLabel(s) {
    const map = {
      LAST_16: 'ラウンド16',
      QUARTER_FINALS: '準々決勝',
      SEMI_FINALS: '準決勝',
      FINAL: '決勝',
      GROUP_STAGE: 'グループ',
      LEAGUE_STAGE: 'リーグ',
      PLAYOFFS: 'プレーオフ',
    };
    return map[s] || s;
  }

  // ===== Calendar view =====
  function renderCalendar() {
    const { year, month } = calCursor;
    calMonthLabelEl.textContent = `${year}年${month+1}月`;

    const matches = filtered();
    const byDay = new Map();
    for (const m of matches) {
      const k = dateKey(m.kickoff_jst);
      if (!byDay.has(k)) byDay.set(k, []);
      byDay.get(k).push(m);
    }

    const first = new Date(year, month, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(year, month+1, 0).getDate();
    const prevDays = new Date(year, month, 0).getDate();

    const cells = [];
    for (let i = 0; i < 7; i++) {
      const cls = i === 0 ? 'head sun' : (i === 6 ? 'head sat' : 'head');
      cells.push(`<div class="cal-cell ${cls}">${WEEKDAY[i]}</div>`);
    }

    const today = todayKey();
    for (let i = 0; i < 42; i++) {
      const dayNum = i - startDay + 1;
      let cellY = year, cellM = month, cellD;
      let otherMonth = false;
      if (dayNum < 1) {
        cellD = prevDays + dayNum;
        cellM = month - 1;
        if (cellM < 0) { cellM = 11; cellY -= 1; }
        otherMonth = true;
      } else if (dayNum > daysInMonth) {
        cellD = dayNum - daysInMonth;
        cellM = month + 1;
        if (cellM > 11) { cellM = 0; cellY += 1; }
        otherMonth = true;
      } else {
        cellD = dayNum;
      }
      const key = `${cellY}-${pad(cellM+1)}-${pad(cellD)}`;
      const wd = i % 7;
      const ms = byDay.get(key) || [];

      const dots = [...new Set(ms.map(x => x.competition_id))]
        .slice(0, 6)
        .map(id => `<span class="cal-dot" style="background: var(${cssVarForCompetition(id)});"></span>`)
        .join('');

      const outOfRange = dataRangeFrom && dataRangeTo && (key < dataRangeFrom || key > dataRangeTo);

      const cls = ['cal-cell'];
      if (otherMonth) cls.push('other-month');
      if (outOfRange) cls.push('out-of-range');
      if (key === today) cls.push('today');
      if (key === calSelected) cls.push('selected');
      if (wd === 0) cls.push('sun');
      if (wd === 6) cls.push('sat');

      cells.push(`<div class="${cls.join(' ')}" data-key="${key}" data-oor="${outOfRange ? '1' : ''}">
        <span class="cal-date">${cellD}</span>
        <div class="cal-dots">${dots}</div>
        ${ms.length > 0 ? `<span class="cal-count">${ms.length}試合</span>` : ''}
      </div>`);
    }
    calGridEl.innerHTML = cells.join('');

    calGridEl.querySelectorAll('.cal-cell:not(.head)').forEach(el => {
      el.addEventListener('click', () => {
        if (el.dataset.oor === '1') return;  // 期間外はクリック無効
        calSelected = el.dataset.key;
        renderCalendar();
        renderCalendarDayDetail(byDay);
      });
    });

    renderCalendarDayDetail(byDay);
  }

  function cssVarForCompetition(id) {
    const map = { 39:'--pl', 40:'--elc', 140:'--pd', 78:'--bl1', 135:'--sa', 61:'--fl1', 88:'--ded', 2:'--cl' };
    return map[id] || '--text-sub';
  }

  function renderCalendarDayDetail(byDay) {
    const ms = byDay.get(calSelected) || [];
    if (ms.length === 0) {
      calDayDetailEl.innerHTML = `<h3>${fmtDateHeading(calSelected)}</h3><p class="empty">この日の試合はありません。</p>`;
      return;
    }
    const isToday = calSelected === todayKey();
    const html = [`<h3>${fmtDateHeading(calSelected)}（${ms.length}試合）</h3>`];
    for (const m of ms) html.push(renderMatch(m, isToday));
    calDayDetailEl.innerHTML = html.join('');
  }

  // ===== Ranking view =====
  function renderRanking() {
    if (!standingsData || !currentRankLeague) {
      standingsContentEl.innerHTML = '<p class="empty">順位データを読み込めませんでした。</p>';
      scorersContentEl.innerHTML = '';
      return;
    }
    renderStandings();
    renderScorers();
  }

  function zoneClass(competitionId, position, total) {
    // 簡易版：プレミア・ラ・リーガ・ブンデス・セリエA・リーグ・アンの上位がCL圏
    const compId = Number(competitionId);
    if (compId === 39 || compId === 140 || compId === 135 || compId === 61) {
      // 5大リーグ標準: 1-4位CL, 5位EL, 6位ECL, 18-20位降格
      if (position <= 4) return 'zone-cl';
      if (position === 5) return 'zone-uel';
      if (position >= total - 2) return 'zone-relegate';
    } else if (compId === 78) {
      // ブンデス: 1-4位CL, 5位EL, 6位ECL, 17-18位降格 (16位プレーオフ)
      if (position <= 4) return 'zone-cl';
      if (position === 5) return 'zone-uel';
      if (position >= total - 1) return 'zone-relegate';
    } else if (compId === 88) {
      // エールディビジ: 1位CL, 2位CL予選, 3-5位欧州予選, 17-18位降格
      if (position <= 1) return 'zone-cl';
      if (position <= 5) return 'zone-uel';
      if (position >= total - 1) return 'zone-relegate';
    } else if (compId === 40) {
      // チャンピオンシップ: 1-2位昇格, 3-6位プレーオフ, 22-24位降格
      if (position <= 2) return 'zone-cl';
      if (position <= 6) return 'zone-uel';
      if (position >= total - 2) return 'zone-relegate';
    }
    return '';
  }

  function renderStandings() {
    const meta = standingsData.competitions[currentRankLeague];
    if (!meta) { standingsContentEl.innerHTML = ''; return; }

    const html = [];
    for (const s of meta.standings || []) {
      const isTotal = s.type === 'TOTAL';
      if (s.standings && s.standings.length === 0) continue;
      if (s.group) html.push(`<h3 style="margin:8px 0;font-size:14px;">${escape(s.group)}</h3>`);
      else if (!isTotal && s.stage) html.push(`<h3 style="margin:8px 0;font-size:14px;">${escape(stageLabel(s.stage))}</h3>`);

      const total = s.table.length;
      html.push(`<table class="standings-table"><thead><tr>
        <th class="position">#</th>
        <th></th>
        <th>クラブ</th>
        <th>試合</th>
        <th>勝</th>
        <th>分</th>
        <th>負</th>
        <th>得点</th>
        <th>失点</th>
        <th>差</th>
        <th>勝点</th>
      </tr></thead><tbody>`);
      for (const r of s.table) {
        const zoneCls = isTotal ? zoneClass(currentRankLeague, r.position, total) : '';
        const hasJp = jpClubIds.has(Number(r.team_id));
        const jpNames = hasJp ? (jpPlayersByClub.get(Number(r.team_id)) || []).join('・') : '';
        const rowCls = [zoneCls, hasJp ? 'has-jp' : ''].filter(Boolean).join(' ');
        const teamLabel = hasJp
          ? `${escape(r.team_ja)} <span class="team-jp" title="${escape(jpNames)}">🇯🇵</span>`
          : escape(r.team_ja);
        html.push(`<tr class="${rowCls}">
          <td class="position num">${r.position}</td>
          <td>${r.team_crest ? `<img class="row-crest" src="${escape(r.team_crest)}" alt="">` : ''}</td>
          <td class="team-cell">${teamLabel}</td>
          <td class="num">${r.playedGames}</td>
          <td class="num">${r.won}</td>
          <td class="num">${r.draw}</td>
          <td class="num">${r.lost}</td>
          <td class="num">${r.goalsFor}</td>
          <td class="num">${r.goalsAgainst}</td>
          <td class="num">${r.goalDifference > 0 ? '+' : ''}${r.goalDifference}</td>
          <td class="num points">${r.points}</td>
        </tr>`);
      }
      html.push('</tbody></table>');
    }

    // 凡例
    const compId = Number(currentRankLeague);
    if (compId === 40) {
      html.push(`<p class="zone-legend">
        <span><span class="dot" style="background:#1858a8"></span>自動昇格</span>
        <span><span class="dot" style="background:#f5b500"></span>プレーオフ</span>
        <span><span class="dot" style="background:#c8102e"></span>降格</span>
      </p>`);
    } else if ([39, 140, 135, 61, 78, 88].includes(compId)) {
      html.push(`<p class="zone-legend">
        <span><span class="dot" style="background:#1858a8"></span>CL圏</span>
        <span><span class="dot" style="background:#f5b500"></span>EL/ECL圏</span>
        <span><span class="dot" style="background:#c8102e"></span>降格圏</span>
      </p>`);
    }

    standingsContentEl.innerHTML = html.join('');
  }

  function renderScorers() {
    if (!scorersData) { scorersContentEl.innerHTML = ''; return; }
    const meta = scorersData.competitions[currentRankLeague];
    if (!meta) { scorersContentEl.innerHTML = '<p class="empty">この大会の得点ランキングはありません。</p>'; return; }

    const list = [...(meta.scorers || [])].map(s => ({...s, ga: (s.goals || 0) + (s.assists || 0)}));
    list.sort((a, b) => {
      if (currentSort === 'goals') return (b.goals||0) - (a.goals||0) || (b.assists||0) - (a.assists||0);
      if (currentSort === 'assists') return (b.assists||0) - (a.assists||0) || (b.goals||0) - (a.goals||0);
      return b.ga - a.ga || (b.goals||0) - (a.goals||0);
    });

    const html = [`<table class="scorers-table"><thead><tr>
      <th>#</th>
      <th>選手</th>
      <th>クラブ</th>
      <th>G</th>
      <th>A</th>
      <th>G+A</th>
      <th>PK</th>
      <th>試合</th>
    </tr></thead><tbody>`];
    list.forEach((s, i) => {
      const isJp = s.nationality === 'Japan' || jpPlayerNames.has((s.player_name || '').toLowerCase());
      html.push(`<tr class="${isJp ? 'is-jp' : ''}">
        <td class="num">${i+1}</td>
        <td class="player-cell">${isJp ? '🇯🇵 ' : ''}${escape(s.player_name || '')}</td>
        <td class="team-cell">${s.team_crest ? `<img class="row-crest" src="${escape(s.team_crest)}" alt="">` : ''}${escape(s.team_ja || '')}</td>
        <td class="num">${s.goals ?? '-'}</td>
        <td class="num">${s.assists ?? '-'}</td>
        <td class="num">${s.ga || '-'}</td>
        <td class="num">${s.penalties ?? '-'}</td>
        <td class="num">${s.playedMatches ?? '-'}</td>
      </tr>`);
    });
    html.push('</tbody></table>');
    scorersContentEl.innerHTML = html.join('');
  }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // ==== Events ====
  onlyJpEl.addEventListener('change', rerender);
  viewTabs.forEach(t => t.addEventListener('click', () => switchView(t.dataset.view)));
  sortBtns.forEach(b => b.addEventListener('click', () => {
    sortBtns.forEach(x => x.classList.toggle('active', x === b));
    currentSort = b.dataset.sort;
    renderScorers();
  }));

  document.getElementById('calPrev').addEventListener('click', () => {
    calCursor.month -= 1;
    if (calCursor.month < 0) { calCursor.month = 11; calCursor.year -= 1; }
    renderCalendar();
  });
  document.getElementById('calNext').addEventListener('click', () => {
    calCursor.month += 1;
    if (calCursor.month > 11) { calCursor.month = 0; calCursor.year += 1; }
    renderCalendar();
  });
  document.getElementById('calToday').addEventListener('click', () => {
    initCalCursor();
    renderCalendar();
  });

  loadAll();
})();
