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

  // 言語判定（/en/ パスなら英語表示モード）
  const IS_EN = document.documentElement.lang === 'en' || location.pathname.startsWith('/en/');
  const COMP_EN = {
    'プレミアリーグ': 'Premier League',
    'チャンピオンシップ': 'Championship',
    'ラ・リーガ': 'La Liga',
    'セリエA': 'Serie A',
    'ブンデスリーガ': 'Bundesliga',
    'リーグ・アン': 'Ligue 1',
    'エールディビジ': 'Eredivisie',
    'プリメイラ・リーガ': 'Primeira Liga',
    'UEFAチャンピオンズリーグ': 'UEFA Champions League',
    'UEFAヨーロッパリーグ': 'UEFA Europa League',
    'UEFAカンファレンスリーグ': 'UEFA Conference League',
    'キリンチャレンジカップ': 'Kirin Challenge Cup',
    'ジュピラー・プロ・リーグ': 'Jupiler Pro League',
    'リーグ・ドゥ': 'Ligue 2',
    'ブンデスリーガ2部': '2. Bundesliga',
  };
  const WEEKDAY_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const WEEKDAY = IS_EN ? WEEKDAY_EN : ['日', '月', '火', '水', '木', '金', '土'];
  // 結果待ち：開始から何時間すぎても TIMED/SCHEDULED なら「結果待ち」にするか（isResultPending 参照）
  const RESULT_PENDING_HOURS = 3;
  const RESULT_PENDING_LABEL = IS_EN ? 'Result pending' : '結果待ち';
  // 表示文言の日英切り替え（英語ページでは en を出す）
  const L = (ja, en) => (IS_EN ? en : ja);

  let allMatches = [];
  let standingsData = null;
  let scorersData = null;
  let matchEvents = {};  // match_id (string) → [{type:'goal', player_ja, minute, side}]
  let jpPlayerNames = new Set();   // 日本人選手名（ローマ字）の集合（ハイライト用）
  let jpClubIds = new Set();       // 日本人選手が所属するクラブID
  let jpPlayersByClub = new Map(); // クラブID → 選手名(日本語)の配列
  let jpPlayerSlugMap = new Map(); // name_ja → slug（選手ページリンク用）
  let jpPlayerEnMap = new Map(); // name_ja → name_en（英語表示用・苗字のみ）
  let dataRangeFrom = null;
  let dataRangeTo = null;
  const enabledLeagues = new Set();
  // ビューはURL（=ページ）で決まる。body[data-view] を優先、無ければレガシーlocalStorageを参照
  let currentView = document.body.dataset.view || localStorage.getItem('view') || 'schedule';
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
    if (IS_EN) {
      return `${y}/${String(m).padStart(2,'0')}/${String(d).padStart(2,'0')} (${WEEKDAY[date.getDay()]})`;
    }
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
      const [m, s, sc, players, evts, news] = await Promise.all([
        fetchJson('/data/matches.json'),
        fetchJson('/data/standings.json').catch(() => null),
        fetchJson('/data/scorers.json').catch(() => null),
        fetchJson('/data/players.json').catch(() => null),
        fetchJson('/data/match_events.json').catch(() => null),
        fetchJson('/data/news.json').catch(() => null),
      ]);
      // 配信先は matches.json の broadcasters（scripts/watch_source.py が league_guides.json の欄から入れたもの）だけを使う。
      // 報酬リンクは各配信の affiliate_url があるときだけ（サービス名で一律に付けない・2026-10-22）
      renderNews(news);
      allMatches = m.matches || [];
      normalizeUnplayedFinished(allMatches);
      // 英語モード時：表示用フィールドを英語に切替（_ja を _en で上書き）
      if (IS_EN) {
        for (const x of allMatches) {
          if (x.home_en) x.home_ja = x.home_en;
          if (x.away_en) x.away_ja = x.away_en;
          if (x.competition_ja && COMP_EN[x.competition_ja]) {
            x.competition_ja = COMP_EN[x.competition_ja];
          }
        }
      }
      standingsData = s;
      scorersData = sc;
      matchEvents = (evts && evts.events) ? evts.events : {};
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
        // slug生成（Python側の make_slug と同じロジック）
        const makeSlug = (nameEn) => {
          let s = (nameEn || '').toLowerCase()
            .replace(/'/g, '').replace(/\./g, '');
          const rep = {'ä':'a','ö':'o','ü':'u','ñ':'n','é':'e','è':'e','ê':'e','ç':'c','ã':'a','á':'a','à':'a','ó':'o','ô':'o','ú':'u','í':'i','ï':'i','ō':'o','ū':'u'};
          for (const [k, v] of Object.entries(rep)) s = s.split(k).join(v);
          return s.replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        };
        const usedSlugs = {};
        for (const p of players.players || []) {
          if (p.name_en) jpPlayerNames.add(p.name_en.toLowerCase());
          if (p.club_id != null) {
            const cid = Number(p.club_id);
            jpClubIds.add(cid);
            if (!jpPlayersByClub.has(cid)) jpPlayersByClub.set(cid, []);
            jpPlayersByClub.get(cid).push(p.name_ja);
          }
          // slug → name_ja マッピング（重複時は -2 付与）
          if (p.name_en && p.name_ja) {
            const base = makeSlug(p.name_en);
            if (!usedSlugs[base]) {
              usedSlugs[base] = 1;
              jpPlayerSlugMap.set(p.name_ja, base);
            } else {
              usedSlugs[base]++;
              jpPlayerSlugMap.set(p.name_ja, `${base}-${usedSlugs[base]}`);
            }
            // name_ja → name_en（苗字のみ、英語badge用）
            const parts = (p.name_en || '').trim().split(/\s+/);
            const lastName = parts.length > 1 ? parts[parts.length - 1] : (parts[0] || p.name_en);
            jpPlayerEnMap.set(p.name_ja, lastName);
          }
        }
      }
      const updated = fmtUpdated(m.updated);
      if (IS_EN) {
        updatedEl.textContent = `Updated: ${updated} / ${m.match_count} matches`;
        periodEl.textContent = `Data period: ${fmtDateShort(dataRangeFrom)} - ${fmtDateShort(dataRangeTo)}`;
      } else {
        updatedEl.textContent = `更新: ${updated} / ${m.match_count}試合`;
        periodEl.textContent = `データ期間: ${fmtDateShort(dataRangeFrom)} 〜 ${fmtDateShort(dataRangeTo)}`;
      }
      buildLeagueChecks();
      buildRankLeagueOptions();
      initCalCursor();
      switchView(currentView);
      // Schema.org SportsEvent 注入
      injectSchemaForView();
    } catch (e) {
      listEl.innerHTML = `<p class="empty">${L('データの読み込みに失敗しました', 'Failed to load data')}: ${escape(e.message)}${L('<br>scripts/fetch_matches.py を実行してください。', '')}</p>`;
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
      const leagueName = (IS_EN && COMP_EN[meta.name_ja]) ? COMP_EN[meta.name_ja] : meta.name_ja;
      opt.textContent = `${meta.flag || ''} ${leagueName}`;
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
    // タブはURL遷移するため、このページで使うビューを表示するだけ
    currentView = view;
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

  // ===== お気に入り選手セクション =====
  function renderFavSection() {
    const favSectionId = 'favMatchesSection';
    let favEl = document.getElementById(favSectionId);
    const favs = (window.fjFavorites ? window.fjFavorites.list() : []);

    if (favs.length === 0) {
      if (favEl) favEl.remove();
      return;
    }

    // お気に入り選手のname_jaを収集
    const favNames = new Set();
    for (const [nameJa, slug] of jpPlayerSlugMap.entries()) {
      if (favs.includes(slug)) favNames.add(nameJa);
    }

    // お気に入り選手が出場する試合をフィルタ（未終了・直近結果）
    const now = new Date();
    const cutoff = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000); // 3日前まで
    const favMatches = allMatches.filter(m => {
      if (!enabledLeagues.has(m.competition_id)) return false;
      if (m.home_ja === '未定' && m.away_ja === '未定') return false;
      const kickoff = new Date(m.kickoff_jst);
      if ((isFinished(m) || isResultPending(m)) && kickoff < cutoff) return false;
      const jp = m.japanese_players || [];
      return jp.some(p => {
        const raw = String(p.name_ja || '').trim();
        const clean = raw.replace(/（[^）]*）/g, '').trim();
        return favNames.has(raw) || favNames.has(clean);
      });
    });

    if (favMatches.length === 0) {
      if (favEl) favEl.remove();
      return;
    }

    // セクションをスケジュールビューの直前に挿入
    if (!favEl) {
      favEl = document.createElement('div');
      favEl.id = favSectionId;
      favEl.className = 'fav-section';
      scheduleEl.parentNode.insertBefore(favEl, scheduleEl);
    }

    const title = IS_EN ? '⭐ Favorite Players\' Matches' : '⭐ お気に入り選手の試合';
    const today = todayKey();
    const groups = new Map();
    for (const m of favMatches) {
      const k = dateKey(m.kickoff_jst);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(m);
    }
    const html = [`<h2>${title}</h2>`];
    for (const [key, ms] of groups) {
      const isToday = key === today;
      html.push(`<h2 class="date-heading${isToday ? ' today' : ''}" style="font-size:14px;">${fmtDateHeading(key)}${isToday ? (IS_EN ? ' · Today' : ' ・ 今日') : ''}</h2>`);
      for (const m of ms) html.push(renderMatch(m, isToday));
    }
    favEl.innerHTML = html.join('');
  }

  // ===== Schedule view =====
  function renderSchedule() {
    renderFavSection();
    const matches = filtered().filter(m => {
      if (isFinished(m)) return false;  // 終了試合（スコア入り含む）を除外
      if (isResultPending(m)) return false;  // 開始から3時間すぎても予定のまま＝結果待ち（結果側へ）
      return ['SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED'].includes(m.status);
    });
    if (matches.length === 0) {
      scheduleEl.innerHTML = `<p class="empty">${L('予定されている試合はありません。<br>フィルタ条件を変更してください。', 'No upcoming matches.<br>Try changing the filters.')}</p>`;
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
      html.push(`<h2 class="date-heading${isToday ? ' today' : ''}">${fmtDateHeading(key)}${isToday ? (IS_EN ? ' · Today' : ' ・ 今日') : ''}</h2>`);
      for (const m of ms) html.push(renderMatch(m, isToday));
    }
    scheduleEl.innerHTML = html.join('');
  }

  // ===== Results view =====
  function renderResults() {
    const matches = filtered().filter(m => isFinished(m) || isResultPending(m)).slice().reverse();
    if (matches.length === 0) {
      resultsEl.innerHTML = `<p class="empty">${L('直近の結果はありません。<br>フィルタ条件を変更してください。', 'No recent results.<br>Try changing the filters.')}</p>`;
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
      html.push(`<h2 class="date-heading${isToday ? ' today' : ''}">${fmtDateHeading(key)}${isToday ? (IS_EN ? ' · Today' : ' ・ 今日') : ''}</h2>`);
      for (const m of ms) html.push(renderMatch(m, isToday));
    }
    resultsEl.innerHTML = html.join('');
  }

  function renderMatch(m, isToday) {
    const finished = isFinished(m);
    const pending = isResultPending(m);
    const live = m.status === 'IN_PLAY' || m.status === 'PAUSED';
    const time = fmtTime(m.kickoff_jst);
    const dd = diffDays(m.kickoff_jst);

    let timeLabel;
    if (finished) timeLabel = `<small>${L('終了', 'FT')}</small>${time}`;
    else if (live) timeLabel = `<small>LIVE</small>${time}`;
    else if (pending) timeLabel = `<small>${RESULT_PENDING_LABEL}</small>${time}`;
    else timeLabel = time + (dd > 0 ? `<small>${L(`${dd}日後`, `in ${dd}d`)}</small>` : (dd < 0 ? `<small>${L(`${-dd}日前`, `${-dd}d ago`)}</small>` : ''));

    // 結果待ちの試合にはスコアを出さない
    const score = pending ? null : m.score;
    const homeWin = score && score.home > score.away;
    const awayWin = score && score.away > score.home;

    const homeJp = (m.japanese_players || []).filter(p => p.side === 'home');
    const awayJp = (m.japanese_players || []).filter(p => p.side === 'away');

    // 日本人選手のイベント有無（カードでは「あった」ことだけ示す）
    const events = matchEvents[String(m.id)] || [];
    const homeJpGoals = events.filter(e => e.type === 'goal' && e.side === 'home' && e.is_japanese);
    const awayJpGoals = events.filter(e => e.type === 'goal' && e.side === 'away' && e.is_japanese);
    const homeJpAssists = events.filter(e => e.type === 'assist' && e.side === 'home' && e.is_japanese);
    const awayJpAssists = events.filter(e => e.type === 'assist' && e.side === 'away' && e.is_japanese);
    const cornerBadge = (hasG, hasA) => {
      if (!hasG && !hasA) return '';
      const label = (hasG ? 'G' : '') + (hasA ? 'A' : '');
      return `<span class="jp-corner" title="${IS_EN ? `Japanese player ${hasG ? 'goal':''}${hasG && hasA ? '/':''}${hasA ? 'assist':''} (tap for details)` : `日本人選手の${hasG ? 'ゴール':''}${hasG && hasA ? '/':''}${hasA ? 'アシスト':''}（タップで詳細）`}">🇯🇵 <strong>${label}</strong></span>`;
    };
    const homeCorner = cornerBadge(homeJpGoals.length > 0, homeJpAssists.length > 0);
    const awayCorner = cornerBadge(awayJpGoals.length > 0, awayJpAssists.length > 0);

    const teamRow = (name, crest, scoreVal, win, jp) => {
      // 日本人選手名：簡略化（3人以上は最初2人 + 残り人数を表示・(レンタル)等の補足は除去）
      let jpHtml = '';
      if (jp.length > 0) {
        const cleaned = jp.map(p => {
          const raw = String(p.name_ja || '').trim();
          const nameJa = raw.replace(/（[^）]*）/g, '').trim();
          // 英語モード：苗字のみ（jpPlayerEnMap から取得）
          const nameEn = jpPlayerEnMap.get(raw) || jpPlayerEnMap.get(nameJa) || '';
          const display = IS_EN && nameEn ? nameEn : nameJa;
          return { nameJa, raw, display };
        }).filter(p => p.nameJa);
        // 選手名をリンク化（slotがあれば /players/{slug}/ へ）
        const playerHref = IS_EN ? (slug) => `/en/players/${slug}/` : (slug) => `/players/${slug}/`;
        const makePlayerLink = (display, raw) => {
          const slug = jpPlayerSlugMap.get(raw) || jpPlayerSlugMap.get(display);
          if (slug) {
            return `<a class="jp-player-link" href="${playerHref(escape(slug))}" onclick="event.stopPropagation()" style="color:inherit;text-decoration:underline dotted;">${escape(display)}</a>`;
          }
          return escape(display);
        };
        const sep = IS_EN ? ', ' : '・';
        let label;
        if (cleaned.length <= 2) {
          label = cleaned.map(p => makePlayerLink(p.display, p.raw)).join(sep);
        } else {
          label = `${makePlayerLink(cleaned[0].display, cleaned[0].raw)}${sep}${makePlayerLink(cleaned[1].display, cleaned[1].raw)} +${cleaned.length - 2}`;
        }
        const tip = cleaned.map(p => p.display).join(sep);
        jpHtml = `<span class="team-jp" title="${escape(tip)}">🇯🇵 ${label}</span>`;
      }
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
    if (pending) primaryTags.push(`<span class="status-tag status-pending">${RESULT_PENDING_LABEL}</span>`);
    if (m.stage && m.stage !== 'REGULAR_SEASON') {
      primaryTags.push(`<span class="status-tag">${escape(stageLabel(m.stage))}</span>`);
    }

    const broadcasterTags = broadcasterTagList(m, !finished, true);

    const cls = ['match'];
    if (isToday) cls.push('today');
    if (finished) cls.push('finished');
    if (pending) cls.push('result-pending');
    if (homeCorner || awayCorner) cls.push('has-jp-corner');
    // 終了試合は詳細モーダル可（イベント無しでも空状態で表示）
    const hasDetails = finished;
    if (hasDetails) cls.push('clickable');

    // ハイライト動画リンク（試合終了時のみ・1試合1ボタン・PC表示用）
    // ※モバイルではカード上に表示せず、モーダル内に集約
    let highlightCell = '<span class="match-highlight-placeholder" aria-hidden="true"></span>';
    if (finished && Array.isArray(m.highlights) && m.highlights.length > 0) {
      const first = m.highlights.find(h => h.url || h.video_id);
      if (first) {
        const url = first.url || `https://youtu.be/${first.video_id}`;
        // YouTube公式アイコン風 SVG（赤角丸 + 白▶）
        const ytIcon = `<svg class="yt-icon" viewBox="0 0 28 20" aria-hidden="true"><rect width="28" height="20" rx="5" fill="#ff0000"/><path d="M11 6 L11 14 L18 10 Z" fill="#ffffff"/></svg>`;
        highlightCell = `<a class="match-highlight" href="${escape(url)}" target="_blank" rel="noopener" aria-label="${L('ハイライト動画（YouTube）', 'Highlights (YouTube)')}" title="${L('ハイライト動画', 'Highlights')}"><span class="icon-only">${ytIcon}</span><span class="label-text">▶ ${L('ハイライト', 'Highlights')}</span></a>`;
      }
    }

    return `<div class="${cls.join(' ')}"${hasDetails ? ` data-match-id="${m.id}"` : ''}>
      ${homeCorner ? `<div class="jp-corner-wrap left">${homeCorner}</div>` : ''}
      ${awayCorner ? `<div class="jp-corner-wrap right">${awayCorner}</div>` : ''}
      <div class="match-top has-highlight">
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

  // 配信のタグ（試合カード・試合の詳しい窓で共通）。
  // b.affiliate_url があるときだけ報酬リンク（rel=sponsored）。無ければ公式ページへのふつうのリンク。
  // 配信が空（league_guides.json に欄が無い大会）で、まだ終わっていない試合は「確認中」。
  function broadcasterTagList(m, showUnconfirmed, lazy) {
    // source が league_guides のものだけ（古い 4/29 時点の配信が残ったデータは出さない＝確認中）
    const list = (Array.isArray(m.broadcasters) ? m.broadcasters : []).filter(b => b && b.source === 'league_guides');
    const tags = [];
    for (const b of list) {
      if (!b || !b.name) continue;
      const brandCls = bcBrandClass(b.name);
      const logoFile = bcLogoFile(b.name);
      const logoHtml = logoFile
        ? `<img class="bc-logo" src="/assets/broadcasters/${logoFile}" alt="" width="16" height="16"${lazy ? ' loading="lazy"' : ''}>`
        : `<span class="bc-play">▶</span>`;
      const title = b.label ? ` title="${escape(b.label)}"` : '';
      const linkUrl = b.affiliate_url || b.url;
      const rel = b.affiliate_url ? 'sponsored nofollow noopener' : 'nofollow noopener';
      if (linkUrl) {
        tags.push(`<a class="bc-tag ${brandCls}" href="${escape(linkUrl)}" target="_blank" rel="${rel}"${title}>${logoHtml}${escape(b.name)}</a>`);
      } else {
        tags.push(`<span class="bc-tag ${brandCls}"${title}>${logoHtml}${escape(b.name)}</span>`);
      }
    }
    if (!tags.length && showUnconfirmed) {
      tags.push(`<span class="bc-unconfirmed">${L('配信：確認中', 'Broadcast: TBC')}</span>`);
    }
    return tags;
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

  function bcLogoFile(name) {
    const n = String(name || '').toLowerCase();
    if (n.includes('wowow')) return 'wowow.png';
    if (n.includes('dazn')) return 'dazn.png';
    if (n.includes('lemino')) return 'lemino.png';
    if (n.includes('abema')) return 'abema.png';
    if (n.includes('u-next') || n.includes('unext')) return 'unext.png';
    if (n.includes('bs10')) return 'bs10.png';
    return null;
  }

  function stageLabel(s) {
    const map = IS_EN ? {
      LAST_16: 'Round of 16',
      QUARTER_FINALS: 'Quarter-finals',
      SEMI_FINALS: 'Semi-finals',
      FINAL: 'Final',
      GROUP_STAGE: 'Group stage',
      LEAGUE_STAGE: 'League phase',
      PLAYOFFS: 'Play-offs',
    } : {
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
    calMonthLabelEl.textContent = IS_EN ? `${year}/${pad(month+1)}` : `${year}年${month+1}月`;

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
        ${ms.length > 0 ? `<span class="cal-count">${ms.length}${L('試合', IS_EN && ms.length === 1 ? ' match' : ' matches')}</span>` : ''}
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
      calDayDetailEl.innerHTML = `<h3>${fmtDateHeading(calSelected)}</h3><p class="empty">${L('この日の試合はありません。', 'No matches on this day.')}</p>`;
      return;
    }
    const isToday = calSelected === todayKey();
    const html = [`<h3>${fmtDateHeading(calSelected)}${L(`（${ms.length}試合）`, ` (${ms.length} ${ms.length === 1 ? 'match' : 'matches'})`)}</h3>`];
    for (const m of ms) html.push(renderMatch(m, isToday));
    calDayDetailEl.innerHTML = html.join('');
  }

  // ===== Ranking view =====
  function renderRanking() {
    if (!standingsData || !currentRankLeague) {
      standingsContentEl.innerHTML = `<p class="empty">${L('順位データを読み込めませんでした。', 'Could not load standings.')}</p>`;
      scorersContentEl.innerHTML = '';
      return;
    }
    renderStandings();
    renderScorers();
  }

  function zoneClass(competitionId, position, total) {
    // 簡易版：プレミア・ラ・リーガ・ブンデス・セリエA・リーグ・アンの上位がCL圏
    const compId = Number(competitionId);
    if (compId === 39) {
      // プレミア2025-26最終: アストン・ヴィラのEL優勝でCL枠が5に拡大。
      // 1-5位CL, 6-8位EL/ECL, 18-20位降格
      if (position <= 5) return 'zone-cl';
      if (position <= 8) return 'zone-uel';
      if (position >= total - 2) return 'zone-relegate';
    } else if (compId === 140 || compId === 135 || compId === 61) {
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
        <th>${L('クラブ', 'Club')}</th>
        <th>${L('試合', 'P')}</th>
        <th>${L('勝', 'W')}</th>
        <th>${L('分', 'D')}</th>
        <th>${L('負', 'L')}</th>
        <th>${L('得点', 'GF')}</th>
        <th>${L('失点', 'GA')}</th>
        <th>${L('差', 'GD')}</th>
        <th>${L('勝点', 'Pts')}</th>
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
        <span><span class="dot" style="background:#1858a8"></span>${L('自動昇格', 'Promotion')}</span>
        <span><span class="dot" style="background:#f5b500"></span>${L('プレーオフ', 'Play-offs')}</span>
        <span><span class="dot" style="background:#c8102e"></span>${L('降格', 'Relegation')}</span>
      </p>`);
    } else if ([39, 140, 135, 61, 78, 88].includes(compId)) {
      html.push(`<p class="zone-legend">
        <span><span class="dot" style="background:#1858a8"></span>${L('CL圏', 'UCL')}</span>
        <span><span class="dot" style="background:#f5b500"></span>${L('EL/ECL圏', 'UEL/UECL')}</span>
        <span><span class="dot" style="background:#c8102e"></span>${L('降格圏', 'Relegation')}</span>
      </p>`);
    }

    standingsContentEl.innerHTML = html.join('');
  }

  function renderScorers() {
    if (!scorersData) { scorersContentEl.innerHTML = ''; return; }
    const meta = scorersData.competitions[currentRankLeague];
    if (!meta) { scorersContentEl.innerHTML = `<p class="empty">${L('この大会の得点ランキングはありません。', 'No scorer rankings for this competition.')}</p>`; return; }

    const list = [...(meta.scorers || [])].map(s => ({...s, ga: (s.goals || 0) + (s.assists || 0)}));
    list.sort((a, b) => {
      if (currentSort === 'goals') return (b.goals||0) - (a.goals||0) || (b.assists||0) - (a.assists||0);
      if (currentSort === 'assists') return (b.assists||0) - (a.assists||0) || (b.goals||0) - (a.goals||0);
      return b.ga - a.ga || (b.goals||0) - (a.goals||0);
    });

    const html = [`<table class="scorers-table"><thead><tr>
      <th>#</th>
      <th>${L('選手', 'Player')}</th>
      <th>${L('クラブ', 'Club')}</th>
      <th>G</th>
      <th>A</th>
      <th>G+A</th>
      <th>PK</th>
      <th>${L('試合', 'MP')}</th>
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

  // 試合が終了したかどうかの判定
  // status === 'FINISHED' を基本とするが、スコアが入っている場合も終了扱い（データ反映漏れ対策）
  function isFinished(m) {
    if (!m) return false;
    if (m.status === 'FINISHED') return true;
    // status が SCHEDULED 等でも、スコアが入っていれば終了とみなす
    if (m.score && (
        (m.score.home !== null && m.score.home !== undefined) ||
        (m.score.away !== null && m.score.away !== undefined)
    )) return true;
    return false;
  }

  // 開始前なのに「終了」の試合を予定に戻す（取り寄せ元が未来の試合を FINISHED 0-0 で返すことがある）
  // 開始時刻がまだ来ていないのに status が FINISHED、またはスコア入りの試合は、
  // 表示上だけ TIMED・スコア無しとして扱う（データは書き換えない。生成スクリプトの utils.fix_unplayed_finished と同じ判定）
  function normalizeUnplayedFinished(list) {
    const now = Date.now();
    for (const m of list) {
      if (!m || !isFinished(m)) continue;
      const ko = new Date(m.kickoff_jst).getTime();
      if (isNaN(ko) || ko <= now) continue;
      m.status = 'TIMED';
      if (m.score) m.score = Object.assign({}, m.score, { home: null, away: null });
    }
  }

  // 結果待ちの判定（取り寄せ元が結果を入れてこない試合への対策）
  // 開始時刻から RESULT_PENDING_HOURS 時間すぎても status が TIMED/SCHEDULED のままの試合は
  // 「予定」から外し、「結果待ち」として結果側に出す（スコアは作らない）
  function isResultPending(m) {
    if (!m || isFinished(m)) return false;
    if (m.status !== 'TIMED' && m.status !== 'SCHEDULED') return false;
    const ko = new Date(m.kickoff_jst).getTime();
    if (isNaN(ko)) return false;
    return Date.now() - ko >= RESULT_PENDING_HOURS * 60 * 60 * 1000;
  }

  // ==== Events ====
  onlyJpEl.addEventListener('change', rerender);
  // タブは <a> 要素で各ページにナビゲートする（クリックハンドラ不要）
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

  // ===== 試合詳細モーダル =====
  document.body.addEventListener('click', (e) => {
    // バッジ・リンクなどのクリックは透過
    if (e.target.closest('a')) return;
    const card = e.target.closest('.match.clickable');
    if (!card) return;
    const mid = card.getAttribute('data-match-id');
    if (!mid) return;
    openMatchModal(mid);
  });

  function openMatchModal(matchId) {
    const m = allMatches.find(x => String(x.id) === String(matchId));
    if (!m) return;
    const events = matchEvents[String(matchId)] || [];
    const score = m.score || { home: '—', away: '—' };

    const goalLine = (e) => {
      const cls = e.is_japanese ? 'modal-goal jp' : 'modal-goal';
      const minStr = e.minute_raw && e.minute_raw.includes('+') ? `${e.minute}'` : `${e.minute}'`;
      const noteStr = e.note ? ` (${e.note})` : '';
      const flag = e.is_japanese ? '🇯🇵 ' : '';
      return `<li class="${cls}">⚽ ${flag}${escape(e.player_ja)} <span class="modal-min">${minStr}${noteStr}</span></li>`;
    };
    const homeGoals = events.filter(e => e.type === 'goal' && e.side === 'home').sort((a,b) => a.minute - b.minute);
    const awayGoals = events.filter(e => e.type === 'goal' && e.side === 'away').sort((a,b) => a.minute - b.minute);

    const bcs = broadcasterTagList(m, m.status !== 'FINISHED', false).join('');

    const highlights = (m.highlights || []).filter(h => h.url || h.video_id);
    const highlightHtml = highlights.length
      ? highlights.map(h => {
          const url = h.url || `https://youtu.be/${h.video_id}`;
          return `<a class="match-highlight" href="${escape(url)}" target="_blank" rel="noopener">▶ ${escape(h.title || L('ハイライト動画', 'Highlights'))}</a>`;
        }).join('')
      : '';

    const overlay = document.createElement('div');
    overlay.className = 'match-modal-overlay';
    overlay.innerHTML = `
      <div class="match-modal" role="dialog" aria-modal="true">
        <button class="match-modal-close" aria-label="${L('閉じる', 'Close')}">×</button>
        <div class="modal-comp">
          <span class="league-tag cat-league-${m.competition_id}">${m.competition_flag || ''} ${escape(m.competition_ja)}</span>
          ${m.matchday ? `<span class="status-tag">${L(`第${m.matchday}節`, `Matchday ${m.matchday}`)}</span>` : ''}
          ${m.stage && m.stage !== 'REGULAR_SEASON' ? `<span class="status-tag">${escape(stageLabel(m.stage))}</span>` : ''}
        </div>
        <div class="modal-score">
          <div class="modal-team">
            ${m.home_crest ? `<img src="${escape(m.home_crest)}" alt="" class="modal-crest">` : ''}
            <div class="modal-name">${escape(m.home_ja)}</div>
          </div>
          <div class="modal-result">${score.home != null ? score.home : '—'} - ${score.away != null ? score.away : '—'}</div>
          <div class="modal-team">
            ${m.away_crest ? `<img src="${escape(m.away_crest)}" alt="" class="modal-crest">` : ''}
            <div class="modal-name">${escape(m.away_ja)}</div>
          </div>
        </div>
        <div class="modal-meta">${escape(fmtKickoff(m.kickoff_jst))}</div>
        <div class="modal-section">
          <h3>${L('得点者', 'Scorers')}</h3>
          ${(homeGoals.length || awayGoals.length) ? `
            <div class="modal-goals">
              <div class="modal-goals-side">
                <div class="modal-goals-title">${escape(m.home_ja)}</div>
                <ul class="modal-goal-list">${homeGoals.map(goalLine).join('') || '<li class="modal-goal-empty">—</li>'}</ul>
              </div>
              <div class="modal-goals-side">
                <div class="modal-goals-title">${escape(m.away_ja)}</div>
                <ul class="modal-goal-list">${awayGoals.map(goalLine).join('') || '<li class="modal-goal-empty">—</li>'}</ul>
              </div>
            </div>
          ` : `
            <div class="modal-goal-empty">${L('得点者データはまだ取得できていません。', 'Scorer data is not available yet.')}</div>
          `}
        </div>
        ${highlightHtml ? `
          <div class="modal-section">
            <h3>${L('ハイライト動画', 'Highlights')}</h3>
            <div class="modal-highlights">${highlightHtml}</div>
          </div>
        ` : ''}
        ${bcs ? `
          <div class="modal-section">
            <h3>${L('放送・配信', 'Where to watch')}</h3>
            <div class="tags-row broadcasters">${bcs}</div>
          </div>
        ` : ''}
        <div class="modal-source">${L('出典: Wikipedia 各クラブ2025-26シーズンページ／ハイライトはYouTube公式チャンネル', 'Source: Wikipedia club 2025-26 season pages / highlights from official YouTube channels')}</div>
      </div>
    `;
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';
    const close = () => {
      overlay.remove();
      document.body.style.overflow = '';
    };
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });
    overlay.querySelector('.match-modal-close').addEventListener('click', close);
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') {
        close();
        document.removeEventListener('keydown', esc);
      }
    });
  }

  function fmtKickoff(iso) {
    const d = new Date(iso);
    if (IS_EN) return `Kick-off ${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())} (${WEEKDAY[d.getDay()]}) ${pad(d.getHours())}:${pad(d.getMinutes())} JST`;
    return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())}（${WEEKDAY[d.getDay()]}）${pad(d.getHours())}:${pad(d.getMinutes())} キックオフ`;
  }

  // ===== SportsEvent Schema.org JSON-LD 注入 =====
  // 大会の公式サイトURL（organizer.url 用）
  const COMPETITION_URLS = {
    39: 'https://www.premierleague.com',
    40: 'https://www.efl.com/clubs-and-competitions/sky-bet-championship',
    140: 'https://www.laliga.com',
    135: 'https://www.legaseriea.it',
    78: 'https://www.bundesliga.com',
    61: 'https://www.ligue1.com',
    88: 'https://eredivisie.nl',
    94: 'https://www.ligaportugal.pt',
    2: 'https://www.uefa.com/uefachampionsleague',
    3: 'https://www.uefa.com/uefaeuropaleague',
    848: 'https://www.uefa.com/uefaeuropaconferenceleague'
  };

  function injectMatchSchema(matches) {
    // 既存スキーマ（同じid）があれば削除して二重注入防止
    const old = document.getElementById('matchSchema');
    if (old) old.remove();
    if (!matches || !matches.length) return;

    const data = matches.map(m => {
      const finished = isFinished(m);
      // 試合終了予定時刻 = キックオフ + 105分（90分 + 15分ハーフタイム）
      const start = new Date(m.kickoff_jst);
      const end = new Date(start.getTime() + 105 * 60 * 1000);
      const endIso = end.toISOString().replace('Z', '+09:00').replace(/\.\d{3}/, '');
      // ローカルJSTのISO形式に揃える
      const tz = '+09:00';
      const pad2 = n => String(n).padStart(2, '0');
      const endJst = `${end.getFullYear()}-${pad2(end.getMonth()+1)}-${pad2(end.getDate())}T${pad2(end.getHours())}:${pad2(end.getMinutes())}:00${tz}`;

      const event = {
        '@context': 'https://schema.org',
        '@type': 'SportsEvent',
        'name': `${m.home_ja} vs ${m.away_ja}`,
        'description': `${m.competition_ja}：${m.home_ja} vs ${m.away_ja}（${start.getFullYear()}年${start.getMonth()+1}月${start.getDate()}日 ${pad2(start.getHours())}:${pad2(start.getMinutes())} JSTキックオフ）`,
        'startDate': m.kickoff_jst,
        'endDate': endJst,
        'sport': 'Football',
        'location': {
          '@type': 'Place',
          'name': `${m.home_ja} ホームスタジアム`,
          'address': {
            '@type': 'PostalAddress',
            'addressCountry': m.competition_flag || ''
          }
        },
        'homeTeam': {
          '@type': 'SportsTeam',
          'name': m.home_ja,
          'sport': 'Football'
        },
        'awayTeam': {
          '@type': 'SportsTeam',
          'name': m.away_ja,
          'sport': 'Football'
        },
        'performer': [
          { '@type': 'SportsTeam', 'name': m.home_ja },
          { '@type': 'SportsTeam', 'name': m.away_ja }
        ],
        'organizer': {
          '@type': 'SportsOrganization',
          'name': m.competition_ja,
          'url': COMPETITION_URLS[m.competition_id] || 'https://football-jp.com/'
        },
        'eventStatus': finished
          ? 'https://schema.org/EventCompleted'
          : 'https://schema.org/EventScheduled'
      };
      // 画像（ホームチームのクレスト）— あれば付加
      if (m.home_crest) {
        event.image = m.home_crest;
      }
      return event;
    });

    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'matchSchema';
    script.textContent = JSON.stringify(data);
    document.head.appendChild(script);
  }

  function injectSchemaForView() {
    const now = new Date();
    let schemaMatches = [];

    if (currentView === 'schedule') {
      // 予定試合（未終了）の先頭10件
      schemaMatches = filtered()
        .filter(m => !isFinished(m) && !isResultPending(m) && ['SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED'].includes(m.status))
        .slice(0, 10);
    } else if (currentView === 'results') {
      // 終了済み試合の最新10件（降順で先頭10件）
      schemaMatches = filtered()
        .filter(m => isFinished(m))
        .slice()
        .reverse()
        .slice(0, 10);
    } else if (currentView === 'calendar') {
      // 当月の試合（最大10件）
      const y = now.getFullYear();
      const mo = now.getMonth();
      schemaMatches = filtered()
        .filter(m => {
          const d = new Date(m.kickoff_jst);
          return d.getFullYear() === y && d.getMonth() === mo;
        })
        .slice(0, 10);
    }
    // ranking ビューは試合なし → 空配列でスキーマなし
    injectMatchSchema(schemaMatches);
  }

  function renderNews(newsData) {
    const section = document.getElementById('newsSection');
    const list = document.getElementById('newsList');
    const count = document.getElementById('newsCount');
    if (!section || !list || !newsData || !Array.isArray(newsData.items) || newsData.items.length === 0) {
      return;
    }
    const items = newsData.items.slice(0, 10);
    const INITIAL = 3;
    const renderItem = it => {
      const dateStr = it.published ? it.published.slice(0, 10) : '';
      const players = (it.matched_players || []).slice(0, 3).join('・');
      return `<a href="${escape(it.link)}" target="_blank" rel="noopener" class="news-item">
        <div class="news-meta">
          <span class="news-date">${escape(dateStr)}</span>
          <span class="news-source">${escape(it.source || '')}</span>
          ${players ? `<span class="news-players">🇯🇵 ${escape(players)}</span>` : ''}
        </div>
        <div class="news-title">${escape(it.title)}</div>
      </a>`;
    };
    const visibleHtml = items.slice(0, INITIAL).map(renderItem).join('');
    const hiddenHtml  = items.slice(INITIAL).map(renderItem).join('');
    list.innerHTML = visibleHtml
      + (hiddenHtml ? `<div class="news-more-items" hidden>${hiddenHtml}</div>
          <button class="news-more-btn" onclick="
            this.previousElementSibling.hidden=false;
            this.remove();
          ">${L(`残り${items.length - INITIAL}件を見る`, `Show ${items.length - INITIAL} more`)} ▼</button>` : '');
    if (count) count.textContent = `(${items.length})`;
    section.hidden = false;
  }

  loadAll();
})();
