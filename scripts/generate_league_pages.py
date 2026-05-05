#!/usr/bin/env python3
"""
generate_league_pages.py
リーグ別 日本人選手ハブページを自動生成するスクリプト。
出力先:
  leagues/index.html           ← リーグ一覧（日本語）
  leagues/{slug}/index.html    ← 各リーグページ（日本語）
使い方: python3 scripts/generate_league_pages.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON    = REPO_ROOT / "data" / "players.json"
MATCHES_JSON    = REPO_ROOT / "data" / "matches.json"
STANDINGS_JSON  = REPO_ROOT / "data" / "standings.json"
SCORERS_JSON    = REPO_ROOT / "data" / "scorers.json"
BROADCASTERS_JSON = REPO_ROOT / "data" / "broadcasters.json"
PLAYER_STATS_JSON = REPO_ROOT / "data" / "player_stats.json"
OUTPUT_DIR      = REPO_ROOT / "leagues"

GA4_ID    = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL  = "https://football-jp.com"

JST = timezone(timedelta(hours=9))

# ============================
# リーグスラグ定義（日本語名 → slug）
# ============================
LEAGUE_SLUG_MAP = {
    "プレミアリーグ":         "premier-league",
    "チャンピオンシップ":       "championship",
    "ブンデスリーガ":          "bundesliga",
    "2.ブンデスリーガ":         "2-bundesliga",
    "ラ・リーガ":              "la-liga",
    "ラリーガ":               "la-liga",
    "セリエA":                "serie-a",
    "リーグ・アン":            "ligue-1",
    "リーグ・ドゥ":            "ligue-2",
    "エールディビジ":          "eredivisie",
    "プリメイラ・リーガ":       "primeira-liga",
    "ジュピラー・プロ・リーグ":  "jupiler-pro-league",
    "スコティッシュ・プレミアシップ": "scottish-premiership",
    "スーペル・リーグ":         "super-lig",
    "MLS":                    "mls",
    "J1リーグ":               "j1-league",
    "Jリーグ":                "j-league",
}

# リーグ名英語（日本語 → 英語）
LEAGUE_EN_MAP = {
    "プレミアリーグ":         "Premier League",
    "チャンピオンシップ":       "Championship",
    "ブンデスリーガ":          "Bundesliga",
    "2.ブンデスリーガ":         "2. Bundesliga",
    "ラ・リーガ":              "La Liga",
    "ラリーガ":               "La Liga",
    "セリエA":                "Serie A",
    "リーグ・アン":            "Ligue 1",
    "リーグ・ドゥ":            "Ligue 2",
    "エールディビジ":          "Eredivisie",
    "プリメイラ・リーガ":       "Primeira Liga",
    "ジュピラー・プロ・リーグ":  "Jupiler Pro League",
    "スコティッシュ・プレミアシップ": "Scottish Premiership",
    "スーペル・リーグ":         "Süper Lig",
    "MLS":                    "MLS",
    "J1リーグ":               "J1 League",
    "Jリーグ":                "J.League",
}

# リーグ国旗
LEAGUE_FLAG_MAP = {
    "プレミアリーグ":         "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "チャンピオンシップ":       "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "ブンデスリーガ":          "🇩🇪",
    "2.ブンデスリーガ":         "🇩🇪",
    "ラ・リーガ":              "🇪🇸",
    "ラリーガ":               "🇪🇸",
    "セリエA":                "🇮🇹",
    "リーグ・アン":            "🇫🇷",
    "リーグ・ドゥ":            "🇫🇷",
    "エールディビジ":          "🇳🇱",
    "プリメイラ・リーガ":       "🇵🇹",
    "ジュピラー・プロ・リーグ":  "🇧🇪",
    "スコティッシュ・プレミアシップ": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "スーペル・リーグ":         "🇹🇷",
    "MLS":                    "🇺🇸",
    "J1リーグ":               "🇯🇵",
    "Jリーグ":                "🇯🇵",
}

# 表示順（人気リーグ優先）
LEAGUE_DISPLAY_ORDER = [
    "プレミアリーグ",
    "ジュピラー・プロ・リーグ",
    "ブンデスリーガ",
    "チャンピオンシップ",
    "エールディビジ",
    "リーグ・アン",
    "ラ・リーガ",
    "プリメイラ・リーガ",
    "セリエA",
    "リーグ・ドゥ",
    "スコティッシュ・プレミアシップ",
    "スーペル・リーグ",
    "MLS",
    "J1リーグ",
    "Jリーグ",
    "2.ブンデスリーガ",
]


# ============================
# ユーティリティ関数
# ============================
def esc(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def make_slug(name_en: str) -> str:
    """英語名をURLスラグに変換する。"""
    s = name_en.lower()
    s = s.replace("'", "").replace(".", "")
    replacements = {
        "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "é": "e", "è": "e",
        "ê": "e", "ç": "c", "ã": "a", "á": "a", "à": "a", "ó": "o",
        "ô": "o", "ú": "u", "í": "i", "ï": "i", "ō": "o", "ū": "u",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def league_slug(league_ja: str) -> str:
    """リーグ名（日本語）からslugを返す。"""
    return LEAGUE_SLUG_MAP.get(league_ja, make_slug(LEAGUE_EN_MAP.get(league_ja, league_ja)))


def league_en(league_ja: str) -> str:
    """リーグ名（英語）を返す。"""
    return LEAGUE_EN_MAP.get(league_ja, league_ja)


def league_flag(league_ja: str) -> str:
    return LEAGUE_FLAG_MAP.get(league_ja, "")


def make_player_slug(name_en: str) -> str:
    return make_slug(name_en)


def build_unique_player_slugs(players: list) -> dict:
    """選手名(name_en) → slug 辞書（重複対応）"""
    slug_map = {}
    used = {}
    for p in players:
        base = make_slug(p.get("name_en", ""))
        if base not in used:
            used[base] = 1
            slug_map[p.get("name_en", "")] = base
        else:
            used[base] += 1
            # 重複の場合は番号付き (2番目以降)
            slug_map[p.get("name_en", "")] = f"{base}-{used[base]}"
    return slug_map


def get_lastmod_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


# ============================
# broadcaster タグ
# ============================
def load_services() -> dict:
    if not BROADCASTERS_JSON.exists():
        return {}
    with open(BROADCASTERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("services", {})


def bc_brand_class(name: str) -> str:
    n = (name or "").lower()
    if "wowow" in n: return "bc-wowow"
    if "dazn" in n: return "bc-dazn"
    if "lemino" in n: return "bc-lemino"
    if "abema" in n: return "bc-abema"
    if "u-next" in n or "unext" in n: return "bc-unext"
    if "bs10" in n: return "bc-bs10"
    return "bc-default"


def build_utm_url(base_url: str, page_type: str, page_id: str, league: str = "") -> str:
    from urllib.parse import urlencode
    if not base_url:
        return ""
    params = {
        "utm_source": "football-jp",
        "utm_medium": f"{page_type}_page",
        "utm_content": page_id,
    }
    if league:
        params["utm_campaign"] = league
    sep = "&" if "?" in base_url else "?"
    return base_url + sep + urlencode(params)


def build_bc_tag(broadcaster: dict, services: dict, page_type: str, page_id: str, lg: str = "") -> str:
    name = broadcaster.get("name", "")
    svc = services.get(name, {})
    base_url = svc.get("affiliate_url") or svc.get("url") or broadcaster.get("url") or ""
    if not base_url:
        brand_cls = bc_brand_class(name)
        return f'<span class="bc-tag {esc(brand_cls)}">{esc(name)}</span>'
    utm_url = build_utm_url(base_url, page_type, page_id, lg)
    brand_cls = bc_brand_class(name)
    logo_file = svc.get("logo", "")
    logo_html = (
        f'<img class="bc-logo" src="/assets/broadcasters/{esc(logo_file)}" alt="" width="16" height="16">'
        if logo_file else ""
    )
    return (
        f'<a class="bc-tag {esc(brand_cls)}" href="{esc(utm_url)}" '
        f'target="_blank" rel="noopener" '
        f'data-svc="{esc(name)}" data-pagetype="{esc(page_type)}" data-pageid="{esc(page_id)}" '
        f'onclick="trackAffClick(this)">'
        f'{logo_html}{esc(name)}'
        f'</a>'
    )


# ============================
# 共通 HEAD / NAV / FOOTER テンプレート
# ============================
def common_head_ja(title: str, description: str, canonical: str, hreflang_en: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="alternate" hreflang="ja" href="{esc(canonical)}">
  <link rel="alternate" hreflang="en" href="{esc(hreflang_en)}">
  <link rel="alternate" hreflang="x-default" href="{esc(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA4_ID}');
  </script>
  <link rel="icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/logos/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/assets/logos/favicon-48.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
</head>"""


def common_nav_ja(active: str = "leagues") -> str:
    return """<nav class="view-tabs">
    <a class="view-tab" href="/" data-view="schedule">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 7v5l3.5 2"/>
      </svg>
      <span>予定を見る</span>
    </a>
    <a class="view-tab" href="/results/" data-view="results">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M8 12.5l3 3 5-6"/>
      </svg>
      <span>結果を見る</span>
    </a>
    <a class="view-tab" href="/standings/" data-view="ranking">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4 20h16"/>
        <path d="M7 20v-5"/>
        <path d="M12 20v-9"/>
        <path d="M17 20v-13"/>
      </svg>
      <span>順位・ランキング</span>
    </a>
    <a class="view-tab active" href="/leagues/" data-view="leagues">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      <span>リーグ</span>
    </a>
  </nav>"""


def common_footer_ja() -> str:
    return """  <footer>
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">football-data.org</a></p>
    <nav class="footer-nav">
      <a href="/players/">日本人選手一覧</a>
      <a href="/clubs/">クラブ一覧</a>
      <a href="/leagues/">リーグ一覧</a>
    </nav>
    <p>
      <a href="/privacy.html">プライバシーポリシー</a>
      &nbsp;|&nbsp;
      <a href="/en/">🇺🇸 English</a>
    </p>
  </footer>
  <script>
    function trackAffClick(el) {
      if (typeof gtag === 'function') {
        gtag('event', 'aff_click', {
          service: el.dataset.svc,
          page_type: el.dataset.pagetype,
          page_id: el.dataset.pageid
        });
      }
    }
  </script>"""


# ============================
# データ読み込み
# ============================
def load_all_data():
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    with open(MATCHES_JSON, encoding="utf-8") as f:
        matches_raw = json.load(f)
    matches = matches_raw.get("matches", [])

    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_raw = json.load(f)
    standings_comps = standings_raw.get("competitions", {})

    scorers_comps = {}
    if SCORERS_JSON.exists():
        with open(SCORERS_JSON, encoding="utf-8") as f:
            scorers_raw = json.load(f)
        scorers_comps = scorers_raw.get("competitions", {})

    player_stats = {}
    if PLAYER_STATS_JSON.exists():
        with open(PLAYER_STATS_JSON, encoding="utf-8") as f:
            ps_raw = json.load(f)
        player_stats = ps_raw.get("stats", {})

    services = load_services()
    return players, matches, standings_comps, scorers_comps, player_stats, services


# ============================
# 選手データをリーグ別にグループ化
# ============================
def group_players_by_league(players: list) -> dict:
    """league_ja → list of player dict"""
    grouped = defaultdict(list)
    for p in players:
        lg = p.get("league_ja", "")
        if lg:
            grouped[lg].append(p)
    return dict(grouped)


def group_players_by_club(players: list) -> dict:
    """club_en → list of player dict"""
    grouped = defaultdict(list)
    for p in players:
        club = p.get("club_en", "")
        grouped[club].append(p)
    return dict(grouped)


# ============================
# 選手スタッツ取得
# ============================
def get_player_stats_data(player: dict, scorers_comps: dict, player_stats: dict) -> dict:
    """選手の今シーズン成績を返す（ゴール・試合数等）"""
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")

    # まず scorers.json から探す
    if comp_id and comp_id in scorers_comps:
        scorers = scorers_comps[comp_id].get("scorers", [])
        en_parts = name_en.lower().split() if name_en else []
        for s in scorers:
            scorer_name = s.get("player_name", "")
            scorer_parts = scorer_name.lower().split()
            if en_parts and scorer_parts:
                last_en = en_parts[-1]
                last_sc = scorer_parts[-1]
                if last_en == last_sc and (not club_id or s.get("team_id") == club_id):
                    return {
                        "goals": s.get("goals", 0),
                        "assists": s.get("assists", 0),
                        "played": s.get("playedMatches", 0),
                    }

    # player_stats.json (Wikipedia) からフォールバック
    if name_en and name_en in player_stats:
        entry = player_stats[name_en]
        return {
            "goals": entry.get("goals", 0),
            "assists": entry.get("assists", 0),
            "played": entry.get("apps", 0),
        }

    return {}


# ============================
# 試合データをリーグ別・日付別に整理
# ============================
def get_league_matches(matches: list, comp_id: int) -> dict:
    """comp_id に一致する試合を返す。"""
    result = []
    for m in matches:
        if m.get("competition_id") == comp_id and m.get("japanese_players"):
            result.append(m)
    return result


def parse_iso_datetime(dt_str: str):
    """ISO 8601 文字列を datetime に変換する（Python 3.6 対応）。"""
    if not dt_str:
        return None
    try:
        # Python 3.7+ fromisoformat は使えないため手動パース
        # フォーマット: 2026-04-24T01:45:00+09:00
        # タイムゾーン部分を処理
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        # +09:00 形式のタイムゾーンを手動処理
        if "+" in dt_str[10:] or (dt_str[10:].count("-") > 0 and "T" in dt_str):
            # タイムゾーン部分を分離
            idx = dt_str.rfind("+")
            if idx > 10:
                tz_str = dt_str[idx:]
                dt_str_naive = dt_str[:idx]
            else:
                idx = dt_str.rfind("-", 10)
                if idx > 10:
                    tz_str = dt_str[idx:]
                    dt_str_naive = dt_str[:idx]
                else:
                    tz_str = None
                    dt_str_naive = dt_str
            dt = datetime.strptime(dt_str_naive, "%Y-%m-%dT%H:%M:%S")
            if tz_str:
                sign = 1 if tz_str[0] == "+" else -1
                parts = tz_str[1:].split(":")
                h, m_val = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
                offset = timezone(timedelta(hours=sign * h, minutes=sign * m_val))
                dt = dt.replace(tzinfo=offset)
            return dt
        else:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def split_matches_by_date(matches: list):
    """試合を過去2週間の結果と今後2週間の予定に分ける。"""
    now = datetime.now(JST)
    two_weeks_ago = now - timedelta(days=14)
    two_weeks_later = now + timedelta(days=14)

    recent = []
    upcoming = []
    for m in matches:
        kickoff_str = m.get("kickoff_jst", "")
        if not kickoff_str:
            continue
        kickoff = parse_iso_datetime(kickoff_str)
        if kickoff is None:
            continue
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=JST)

        if kickoff >= two_weeks_ago and kickoff <= now and m.get("status") == "FINISHED":
            recent.append(m)
        elif kickoff > now and kickoff <= two_weeks_later:
            upcoming.append(m)

    recent.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    upcoming.sort(key=lambda x: x.get("kickoff_jst", ""))
    return recent, upcoming


def format_kickoff(kickoff_str: str) -> str:
    """kickoff_jst を読みやすい形式に変換する。"""
    if not kickoff_str:
        return ""
    try:
        dt = parse_iso_datetime(kickoff_str)
        if dt is None:
            return kickoff_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.strftime("%m/%d（%a）%H:%M")
    except Exception:
        return kickoff_str


WEEKDAY_JA = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": "土", "Sun": "日"}


def format_kickoff_ja(kickoff_str: str) -> str:
    """kickoff_jst を日本語形式に変換する。"""
    if not kickoff_str:
        return ""
    try:
        dt = parse_iso_datetime(kickoff_str)
        if dt is None:
            return kickoff_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        wd_en = dt.strftime("%a")
        wd_ja = WEEKDAY_JA.get(wd_en, wd_en)
        return dt.strftime(f"%m/%d（{wd_ja}）%H:%M")
    except Exception:
        return kickoff_str


# ============================
# 選手イニシャルアバター
# ============================
def player_initials(name_en: str) -> str:
    parts = name_en.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1 and parts[0]:
        return parts[0][0].upper()
    return "?"


def position_color(position: str) -> str:
    p = (position or "").upper()
    if "GK" in p: return "#f59e0b"
    if "DF" in p: return "#3b82f6"
    if "MF" in p: return "#10b981"
    if "FW" in p: return "#ef4444"
    return "#6b7280"


# ============================
# リーグ順位テーブル生成
# ============================
def build_standings_html(standings_comps: dict, comp_id: int, jp_club_ids: set, max_rows: int = 20) -> str:
    """リーグ順位HTML（日本人選手在籍クラブをハイライト）。"""
    comp_data = standings_comps.get(str(comp_id))
    if not comp_data:
        return ""

    standings_list = comp_data.get("standings", [])
    table = []
    for s in standings_list:
        if s.get("type") == "TOTAL" and s.get("table"):
            table = s["table"]
            break

    if not table:
        return ""

    rows_html = []
    for row in table[:max_rows]:
        pos = row.get("position", "")
        team_id = row.get("team_id")
        team_ja = row.get("team_ja", "")
        crest = row.get("team_crest", "")
        played = row.get("playedGames", "")
        won = row.get("won", "")
        draw = row.get("draw", "")
        lost = row.get("lost", "")
        pts = row.get("points", "")

        is_jp = team_id in jp_club_ids
        row_class = ' class="jp-club-row"' if is_jp else ""
        jp_badge = ' <span class="jp-badge">🇯🇵</span>' if is_jp else ""

        crest_html = ""
        if crest:
            crest_html = f'<img src="{esc(crest)}" alt="" width="18" height="18" style="vertical-align:middle;margin-right:4px;">'

        rows_html.append(
            f'<tr{row_class}>'
            f'<td class="pos-cell">{esc(str(pos))}</td>'
            f'<td class="team-cell">{crest_html}{esc(team_ja)}{jp_badge}</td>'
            f'<td>{esc(str(played))}</td>'
            f'<td>{esc(str(won))}</td>'
            f'<td>{esc(str(draw))}</td>'
            f'<td>{esc(str(lost))}</td>'
            f'<td class="pts-cell"><strong>{esc(str(pts))}</strong></td>'
            f'</tr>'
        )

    if not rows_html:
        return ""

    html = """<section class="league-section">
  <h2 class="section-title">リーグ順位</h2>
  <p class="section-note">🇯🇵マークは日本人選手在籍クラブ</p>
  <div class="table-scroll">
  <table class="standings-table league-standings-table">
    <thead>
      <tr>
        <th>順位</th>
        <th>チーム</th>
        <th>試合</th>
        <th>勝</th>
        <th>分</th>
        <th>敗</th>
        <th>勝点</th>
      </tr>
    </thead>
    <tbody>
"""
    html += "\n".join(rows_html)
    html += """
    </tbody>
  </table>
  </div>
  <p style="text-align:right;margin-top:6px;"><a href="/standings/" class="link-more">全リーグ順位を見る →</a></p>
</section>"""
    return html


# ============================
# 試合カード生成
# ============================
def build_match_card(m: dict, services: dict, league_slug_str: str, is_result: bool) -> str:
    kickoff = format_kickoff_ja(m.get("kickoff_jst", ""))
    home_ja = m.get("home_ja", "")
    away_ja = m.get("away_ja", "")
    home_crest = m.get("home_crest", "")
    away_crest = m.get("away_crest", "")
    score = m.get("score") or {}
    home_score = score.get("home")
    away_score = score.get("away")
    jp_players = m.get("japanese_players", [])
    broadcasters = m.get("broadcasters", [])
    match_id = str(m.get("id", ""))

    # 出場選手バッジ
    jp_names = []
    for jp in jp_players:
        name = jp.get("name_ja", "")
        side = jp.get("side", "")
        if name:
            jp_names.append(f'<span class="jp-player-badge">{esc(name)}</span>')

    jp_html = ""
    if jp_names:
        jp_html = f'<div class="jp-players-row">{"".join(jp_names)}</div>'

    # 配信バッジ
    bc_html = ""
    if broadcasters:
        bc_tags = [build_bc_tag(bc, services, "league", league_slug_str, league_slug_str) for bc in broadcasters]
        bc_html = f'<div class="bc-tags">{"".join(bc_tags)}</div>'

    # スコア表示
    if is_result and home_score is not None and away_score is not None:
        score_html = f'<span class="match-score">{esc(str(home_score))} - {esc(str(away_score))}</span>'
    else:
        score_html = '<span class="match-vs">vs</span>'

    home_crest_html = f'<img src="{esc(home_crest)}" alt="" width="24" height="24" class="match-crest">' if home_crest else ""
    away_crest_html = f'<img src="{esc(away_crest)}" alt="" width="24" height="24" class="match-crest">' if away_crest else ""

    return f"""<div class="match-card">
  <div class="match-header">
    <span class="match-date">{esc(kickoff)}</span>
  </div>
  <div class="match-body">
    <span class="match-team home">{home_crest_html}{esc(home_ja)}</span>
    {score_html}
    <span class="match-team away">{away_crest_html}{esc(away_ja)}</span>
  </div>
  {jp_html}
  {bc_html}
</div>"""


# ============================
# 選手カード生成
# ============================
def build_player_card(player: dict, player_slug: str, stats: dict) -> str:
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    position = player.get("position", "")
    club_ja = player.get("club_ja", "")
    club_en = player.get("club_en", "")
    club_slug = make_slug(club_en) if club_en else ""

    initials = player_initials(name_en)
    pos_color = position_color(position)

    goals = stats.get("goals", "")
    assists = stats.get("assists", "")
    played = stats.get("played", "")

    stats_html = ""
    if played or goals or assists:
        stats_parts = []
        if played:
            stats_parts.append(f'<span class="stat-item">{esc(str(played))}試合</span>')
        if goals:
            stats_parts.append(f'<span class="stat-item stat-goal">{esc(str(goals))}G</span>')
        if assists:
            stats_parts.append(f'<span class="stat-item stat-assist">{esc(str(assists))}A</span>')
        if stats_parts:
            stats_html = f'<div class="player-card-stats">{"".join(stats_parts)}</div>'

    club_link = f'/clubs/{esc(club_slug)}/' if club_slug else "#"

    return f"""<a href="/players/{esc(player_slug)}/" class="player-card-link">
  <div class="player-card">
    <div class="player-avatar" style="background:{esc(pos_color)}">{esc(initials)}</div>
    <div class="player-card-info">
      <div class="player-card-name-ja">{esc(name_ja)}</div>
      <div class="player-card-name-en">{esc(name_en)}</div>
      <div class="player-card-meta">
        <span class="player-pos-tag" style="background:{esc(pos_color)}20;color:{esc(pos_color)}">{esc(position)}</span>
        <a href="{esc(club_link)}" class="player-club-link" onclick="event.stopPropagation()">{esc(club_ja)}</a>
      </div>
      {stats_html}
    </div>
  </div>
</a>"""


# ============================
# リーグ別ページ生成
# ============================
def generate_league_page(
    league_ja: str,
    players: list,
    all_matches: list,
    standings_comps: dict,
    scorers_comps: dict,
    player_stats: dict,
    services: dict,
    all_players: list,
) -> str:
    """1リーグ分のHTMLを返す。"""
    lg_en = league_en(league_ja)
    lg_slug = league_slug(league_ja)
    lg_flag = league_flag(league_ja)
    comp_id = players[0].get("competition_id") if players else None

    # 選手slug（全選手ベースで重複管理）
    slug_map = build_unique_player_slugs(all_players)

    # クラブ別グループ
    clubs_grouped = defaultdict(list)
    jp_club_ids = set()
    for p in players:
        clubs_grouped[p.get("club_en", "")].append(p)
        if p.get("club_id"):
            jp_club_ids.add(p.get("club_id"))

    num_players = len(players)
    num_clubs = len(clubs_grouped)

    canonical = f"{SITE_URL}/leagues/{lg_slug}/"
    en_url = f"{SITE_URL}/en/leagues/{lg_slug}/"
    title = f"{league_ja} の日本人選手 - 試合・配信情報 | football-jp"
    description = (
        f"{league_ja}に在籍する日本人選手{num_players}名（{num_clubs}クラブ）の試合日程・結果・リーグ順位を日本時間でチェック。"
        f"配信情報付き。"
    )

    # Schema.org
    schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "SportsLeague",
        "name": lg_en,
        "url": canonical,
        "sport": "Soccer",
        "location": {
            "@type": "Place",
            "name": lg_en
        }
    }, ensure_ascii=False, indent=2)

    # ============================
    # 試合データ
    # ============================
    if comp_id:
        league_matches = get_league_matches(all_matches, comp_id)
        recent_matches, upcoming_matches = split_matches_by_date(league_matches)
    else:
        recent_matches, upcoming_matches = [], []

    # ============================
    # HTML 組み立て
    # ============================
    html_parts = [common_head_ja(title, description, canonical, en_url)]
    html_parts.append(f'  <script type="application/ld+json">\n{schema}\n  </script>')
    html_parts.append("</head>")
    html_parts.append('<body data-view="leagues">')
    html_parts.append("""  <header>
    <div>
      <h1><a href="/" style="text-decoration:none;color:inherit;"><img src="/assets/logos/logo-header.png" alt="football-jp" class="header-logo"></a> リーグ別 日本人選手</h1>
    </div>
  </header>""")
    html_parts.append(common_nav_ja())

    # ============================
    # ヒーローセクション
    # ============================
    html_parts.append(f"""<div class="league-hero">
  <div class="league-hero-inner">
    <div class="league-flag-big">{lg_flag}</div>
    <div class="league-hero-text">
      <h2 class="league-name-ja">{esc(league_ja)}</h2>
      <p class="league-name-en">{esc(lg_en)}</p>
      <p class="league-summary">在籍日本人選手 <strong>{num_players}名</strong> ／ <strong>{num_clubs}クラブ</strong></p>
    </div>
  </div>
</div>""")

    # ============================
    # 選手一覧（クラブ別グループ）
    # ============================
    html_parts.append('<section class="league-section">')
    html_parts.append('<h2 class="section-title">在籍日本人選手</h2>')

    sorted_clubs = sorted(clubs_grouped.keys())
    for club_en_key in sorted_clubs:
        club_players = clubs_grouped[club_en_key]
        club_ja = club_players[0].get("club_ja", club_en_key)
        club_slug_str = make_slug(club_en_key)
        html_parts.append(f'<div class="club-group">')
        html_parts.append(
            f'<h3 class="club-group-name">'
            f'<a href="/clubs/{esc(club_slug_str)}/" class="club-link">{esc(club_ja)}</a>'
            f'</h3>'
        )
        html_parts.append('<div class="player-cards-grid">')
        for p in club_players:
            p_slug = slug_map.get(p.get("name_en", ""), make_slug(p.get("name_en", "")))
            stats = get_player_stats_data(p, scorers_comps, player_stats)
            html_parts.append(build_player_card(p, p_slug, stats))
        html_parts.append('</div>')
        html_parts.append('</div>')

    html_parts.append('</section>')

    # ============================
    # リーグ順位
    # ============================
    if comp_id:
        standings_html = build_standings_html(standings_comps, comp_id, jp_club_ids)
        if standings_html:
            html_parts.append(standings_html)

    # ============================
    # 直近の試合結果
    # ============================
    if recent_matches:
        html_parts.append('<section class="league-section">')
        html_parts.append('<h2 class="section-title">直近の試合結果（日本人選手出場）</h2>')
        html_parts.append('<div class="match-cards-list">')
        for m in recent_matches[:10]:
            html_parts.append(build_match_card(m, services, lg_slug, is_result=True))
        html_parts.append('</div>')
        html_parts.append(f'<p style="text-align:right;margin-top:8px;"><a href="/results/" class="link-more">すべての試合結果 →</a></p>')
        html_parts.append('</section>')

    # ============================
    # 次節以降の予定
    # ============================
    if upcoming_matches:
        html_parts.append('<section class="league-section">')
        html_parts.append('<h2 class="section-title">次節以降の試合予定</h2>')
        html_parts.append('<div class="match-cards-list">')
        for m in upcoming_matches[:10]:
            html_parts.append(build_match_card(m, services, lg_slug, is_result=False))
        html_parts.append('</div>')
        html_parts.append(f'<p style="text-align:right;margin-top:8px;"><a href="/" class="link-more">全試合スケジュール →</a></p>')
        html_parts.append('</section>')

    # ============================
    # 関連リンク
    # ============================
    html_parts.append('<section class="league-section">')
    html_parts.append('<h2 class="section-title">関連リンク</h2>')
    html_parts.append('<ul class="related-links">')

    # 選手リンク
    seen_slugs = set()
    for p in players:
        p_slug = slug_map.get(p.get("name_en", ""), make_slug(p.get("name_en", "")))
        if p_slug not in seen_slugs:
            seen_slugs.add(p_slug)
            html_parts.append(
                f'<li><a href="/players/{esc(p_slug)}/">{esc(p.get("name_ja",""))} 選手ページ</a></li>'
            )

    # クラブリンク
    seen_clubs = set()
    for club_en_key in sorted_clubs:
        c_slug = make_slug(club_en_key)
        if c_slug not in seen_clubs:
            seen_clubs.add(c_slug)
            club_ja = clubs_grouped[club_en_key][0].get("club_ja", club_en_key)
            html_parts.append(f'<li><a href="/clubs/{esc(c_slug)}/">{esc(club_ja)} クラブページ</a></li>')

    html_parts.append(f'<li><a href="/standings/">リーグ順位一覧</a></li>')
    html_parts.append(f'<li><a href="/leagues/">リーグ一覧に戻る</a></li>')
    html_parts.append('</ul>')
    html_parts.append('</section>')

    html_parts.append(common_footer_ja())
    html_parts.append('</body>')
    html_parts.append('</html>')

    return "\n".join(html_parts)


# ============================
# リーグ一覧ページ生成
# ============================
def generate_league_index(league_groups: dict) -> str:
    """leagues/index.html のHTMLを返す。"""
    canonical = f"{SITE_URL}/leagues/"
    en_url = f"{SITE_URL}/en/leagues/"
    title = "リーグ別 日本人選手一覧 | football-jp"
    description = (
        "プレミアリーグ・ブンデスリーガ・エールディビジ等、海外リーグに在籍する日本人選手をリーグ別に一覧。"
        "試合日程・リーグ順位・配信情報を日本時間でチェック。"
    )

    html_parts = [common_head_ja(title, description, canonical, en_url)]
    html_parts.append("</head>")
    html_parts.append('<body data-view="leagues">')
    html_parts.append("""  <header>
    <div>
      <h1><a href="/" style="text-decoration:none;color:inherit;"><img src="/assets/logos/logo-header.png" alt="football-jp" class="header-logo"></a> リーグ別 日本人選手</h1>
    </div>
  </header>""")
    html_parts.append(common_nav_ja())

    html_parts.append('<div class="league-index-hero">')
    html_parts.append('<h2>リーグ一覧</h2>')
    html_parts.append('<p>海外サッカーリーグに在籍する日本人選手をリーグ別に確認できます。</p>')
    html_parts.append('</div>')

    html_parts.append('<section class="league-index-grid-section">')
    html_parts.append('<div class="league-index-grid">')

    # 表示順に並べる
    ordered_leagues = []
    for lg in LEAGUE_DISPLAY_ORDER:
        if lg in league_groups:
            ordered_leagues.append(lg)
    for lg in league_groups:
        if lg not in ordered_leagues:
            ordered_leagues.append(lg)

    for league_ja in ordered_leagues:
        players = league_groups[league_ja]
        lg_en_name = league_en(league_ja)
        lg_slug_str = league_slug(league_ja)
        lg_flag_str = league_flag(league_ja)
        num_p = len(players)
        clubs = set(p.get("club_en", "") for p in players)
        num_c = len(clubs)

        html_parts.append(f"""<a href="/leagues/{esc(lg_slug_str)}/" class="league-card">
  <div class="league-card-flag">{lg_flag_str}</div>
  <div class="league-card-body">
    <div class="league-card-name-ja">{esc(league_ja)}</div>
    <div class="league-card-name-en">{esc(lg_en_name)}</div>
    <div class="league-card-meta">
      <span class="league-player-count">日本人選手 <strong>{num_p}名</strong></span>
      <span class="league-club-count">{num_c}クラブ</span>
    </div>
  </div>
</a>""")

    html_parts.append('</div>')
    html_parts.append('</section>')

    html_parts.append(common_footer_ja())
    html_parts.append('</body>')
    html_parts.append('</html>')

    return "\n".join(html_parts)


# ============================
# メイン
# ============================
def main():
    print("=== generate_league_pages.py 開始 ===")
    players, matches, standings_comps, scorers_comps, player_stats, services = load_all_data()
    print(f"  選手数: {len(players)}, 試合数: {len(matches)}")

    league_groups = group_players_by_league(players)
    print(f"  リーグ数: {len(league_groups)}")
    for lg, ps in sorted(league_groups.items(), key=lambda x: -len(x[1])):
        print(f"    {lg}: {len(ps)}名")

    generated = 0

    # 各リーグページ生成
    for league_ja, lg_players in league_groups.items():
        lg_slug_str = league_slug(league_ja)
        if not lg_slug_str:
            print(f"  [SKIP] {league_ja}: slug 未定義")
            continue

        out_dir = OUTPUT_DIR / lg_slug_str
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"

        try:
            html = generate_league_page(
                league_ja, lg_players, matches,
                standings_comps, scorers_comps, player_stats, services,
                players  # 全選手（slug重複管理用）
            )
            out_path.write_text(html, encoding="utf-8")
            print(f"  [生成] {out_path}")
            generated += 1
        except Exception as e:
            print(f"  [ERROR] {league_ja}: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()

    # リーグ一覧ページ
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = OUTPUT_DIR / "index.html"
    try:
        html = generate_league_index(league_groups)
        index_path.write_text(html, encoding="utf-8")
        print(f"  [生成] {index_path}")
        generated += 1
    except Exception as e:
        print(f"  [ERROR] リーグ一覧: {e}", file=sys.stderr)

    print(f"=== 完了: {generated} ファイル生成 ===")


if __name__ == "__main__":
    main()
