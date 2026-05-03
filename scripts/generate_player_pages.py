#!/usr/bin/env python3
"""
generate_player_pages.py
日本人選手プロフィールページを自動生成するスクリプト。
出力先: players/{slug}/index.html
使い方: python3 scripts/generate_player_pages.py
"""

import json
import os
import re
import sys
from pathlib import Path

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
MATCHES_JSON = REPO_ROOT / "data" / "matches.json"
SCORERS_JSON = REPO_ROOT / "data" / "scorers.json"
MATCH_EVENTS_JSON = REPO_ROOT / "data" / "match_events.json"
STANDINGS_JSON = REPO_ROOT / "data" / "standings.json"
PLAYER_STATS_JSON = REPO_ROOT / "data" / "player_stats.json"
PLAYER_INFO_JSON = REPO_ROOT / "data" / "player_info.json"
BROADCASTERS_JSON = REPO_ROOT / "data" / "broadcasters.json"
OUTPUT_DIR = REPO_ROOT / "players"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"


# ============================
# broadcaster サービスマップ
# ============================
def load_services() -> dict:
    """broadcasters.json の services セクションを返す。"""
    if not BROADCASTERS_JSON.exists():
        return {}
    with open(BROADCASTERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("services", {})


def bc_brand_class(name: str) -> str:
    """サービス名 → CSS クラス名変換。"""
    n = (name or "").lower()
    if "wowow" in n:
        return "bc-wowow"
    if "dazn" in n:
        return "bc-dazn"
    if "lemino" in n:
        return "bc-lemino"
    if "abema" in n:
        return "bc-abema"
    if "u-next" in n or "unext" in n:
        return "bc-unext"
    if "bs10" in n:
        return "bc-bs10"
    return "bc-default"


def build_utm_url(base_url: str, page_type: str, page_id: str, league: str = "") -> str:
    """UTMパラメータ付きURLを返す。"""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
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


def build_bc_tag(broadcaster: dict, services: dict, page_type: str, page_id: str, league: str = "") -> str:
    """配信サービス bc-tag HTML を生成する。"""
    name = broadcaster.get("name", "")
    svc = services.get(name, {})
    # affiliate_url があればそれを、なければ url を使用
    base_url = svc.get("affiliate_url") or svc.get("url") or broadcaster.get("url") or ""
    if not base_url:
        # url が無い場合はテキストのみ
        brand_cls = bc_brand_class(name)
        return f'<span class="bc-tag {esc(brand_cls)}">{esc(name)}</span>'

    utm_url = build_utm_url(base_url, page_type, page_id, league)
    brand_cls = bc_brand_class(name)
    logo_file = svc.get("logo", "")
    logo_html = ""
    if logo_file:
        logo_html = f'<img class="bc-logo" src="/assets/broadcasters/{esc(logo_file)}" alt="" width="16" height="16">'

    return (
        f'<a class="bc-tag {esc(brand_cls)}" href="{esc(utm_url)}" '
        f'target="_blank" rel="noopener" '
        f'data-svc="{esc(name)}" data-pagetype="{esc(page_type)}" data-pageid="{esc(page_id)}" '
        f'onclick="trackAffClick(this)">'
        f'{logo_html}{esc(name)}'
        f'</a>'
    )


# ============================
# slug生成
# ============================
def make_slug(name_en: str) -> str:
    """英語名をURLスラグに変換する。"""
    s = name_en.lower()
    s = s.replace("'", "").replace(".", "")
    # 特殊文字をASCII化
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


def make_unique_slugs(players: list) -> dict:
    """選手リストからユニークなslug辞書を生成する。index→slug"""
    slug_map = {}
    used = {}
    for i, p in enumerate(players):
        base = make_slug(p.get("name_en", f"player-{i}"))
        if base not in used:
            used[base] = 1
            slug_map[i] = base
        else:
            used[base] += 1
            slug_map[i] = f"{base}-{used[base]}"
    return slug_map


# ============================
# HTML エスケープ
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


# ============================
# データ前処理
# ============================
def load_data():
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    with open(MATCHES_JSON, encoding="utf-8") as f:
        matches_raw = json.load(f)
    matches = matches_raw.get("matches", [])
    # match_id → match 辞書
    matches_dict = {str(m["id"]): m for m in matches}

    with open(SCORERS_JSON, encoding="utf-8") as f:
        scorers_raw = json.load(f)
    scorers_comps = scorers_raw.get("competitions", {})

    with open(MATCH_EVENTS_JSON, encoding="utf-8") as f:
        events_raw = json.load(f)
    events = events_raw.get("events", {})  # match_id(str) → list of events

    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_raw = json.load(f)
    standings_comps = standings_raw.get("competitions", {})

    # player_stats.json（Wikipedia統計、任意）
    player_stats = {}
    if PLAYER_STATS_JSON.exists():
        with open(PLAYER_STATS_JSON, encoding="utf-8") as f:
            ps_raw = json.load(f)
        player_stats = ps_raw.get("stats", {})
        print(f"  player_stats.json: {len(player_stats)} 選手分")

    # player_info.json（身長・体重・キャリア等、任意）
    player_info = {}
    if PLAYER_INFO_JSON.exists():
        with open(PLAYER_INFO_JSON, encoding="utf-8") as f:
            player_info = json.load(f)
        print(f"  player_info.json: {len(player_info)} 選手分")

    services = load_services()
    print(f"  サービス数: {len(services)}")

    return players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info


def get_player_wiki_stats(player: dict, player_stats: dict) -> dict:
    """player_stats.json（Wikipediaソース）から選手統計を取得する。"""
    name_en = player.get("name_en", "")
    if not name_en:
        return {}
    entry = player_stats.get(name_en)
    if entry:
        return {
            "goals": entry.get("goals", 0),
            "assists": entry.get("assists", 0),
            "penalties": 0,
            "played": entry.get("apps", 0),
            "source": "wikipedia",
        }
    return {}


def get_player_scorer_stats(player: dict, scorers_comps: dict) -> dict:
    """選手のスコアラー統計を取得する。"""
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")
    name_ja = player.get("name_ja", "")

    if not comp_id or comp_id not in scorers_comps:
        return {}

    comp_data = scorers_comps[comp_id]
    scorers = comp_data.get("scorers", [])

    # 名前の一部マッチング（player_nameがfull nameの一部として含まれるか）
    for s in scorers:
        scorer_name = s.get("player_name", "")
        # 名前の一部でマッチング
        en_parts = name_en.lower().split()
        scorer_parts = scorer_name.lower().split()
        # 姓でマッチング（最後の単語）
        if en_parts and scorer_parts:
            last_name_en = en_parts[-1]
            last_name_scorer = scorer_parts[-1]
            if last_name_en == last_name_scorer:
                # チームIDも確認
                if club_id and s.get("team_id") == club_id:
                    return {
                        "goals": s.get("goals", 0),
                        "assists": s.get("assists", 0),
                        "penalties": s.get("penalties", 0),
                        "played": s.get("playedMatches", 0),
                    }

    return {}


def get_player_goals(player: dict, events: dict, matches_dict: dict) -> list:
    """選手のゴールイベントリストを取得する（最大10件）。"""
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")

    goal_events = []
    for match_id, evs in events.items():
        for ev in evs:
            if ev.get("type") == "goal" and ev.get("is_japanese"):
                ev_name_ja = ev.get("player_ja", "")
                ev_name_en = ev.get("player_en", "")
                # 名前マッチング（名前の一部）
                matched = False
                if ev_name_ja and name_ja and ev_name_ja in name_ja:
                    matched = True
                if not matched and ev_name_ja and name_ja and name_ja in ev_name_ja:
                    matched = True
                # フルネームの姓でマッチング
                if not matched and ev_name_en and name_en:
                    en_last = name_en.split()[-1].lower() if name_en.split() else ""
                    ev_last = ev_name_en.split()[-1].lower() if ev_name_en.split() else ""
                    if en_last and ev_last and en_last == ev_last:
                        matched = True

                if matched:
                    match = matches_dict.get(match_id, {})
                    goal_events.append({
                        "match_id": match_id,
                        "minute": ev.get("minute"),
                        "minute_raw": ev.get("minute_raw", ""),
                        "note": ev.get("note", ""),
                        "home_ja": match.get("home_ja", ""),
                        "away_ja": match.get("away_ja", ""),
                        "score": match.get("score", {}),
                        "kickoff_jst": match.get("kickoff_jst", ""),
                        "competition_ja": match.get("competition_ja", ""),
                        "side": ev.get("side", ""),
                    })

    # kickoff_jst でソート（新しい順）
    goal_events.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return goal_events[:10]


def get_club_matches(player: dict, matches: list) -> list:
    """選手所属クラブの直近試合を取得する（最大10件）。"""
    club_id = player.get("club_id")
    if not club_id:
        return []

    club_matches = [
        m for m in matches
        if m.get("home_id") == club_id or m.get("away_id") == club_id
    ]
    # kickoff_jst でソート（新しい順）
    club_matches.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return club_matches[:10]


def get_club_standing(player: dict, standings_comps: dict) -> dict:
    """選手所属クラブのリーグ順位を取得する。"""
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")

    if not comp_id or not club_id or comp_id not in standings_comps:
        return {}

    comp_data = standings_comps[comp_id]
    for standing_group in comp_data.get("standings", []):
        if standing_group.get("type") == "TOTAL":
            for entry in standing_group.get("table", []):
                if entry.get("team_id") == club_id:
                    return {
                        "position": entry.get("position"),
                        "points": entry.get("points"),
                        "played": entry.get("playedGames"),
                        "won": entry.get("won"),
                        "draw": entry.get("draw"),
                        "lost": entry.get("lost"),
                        "goals_for": entry.get("goalsFor"),
                        "goals_against": entry.get("goalsAgainst"),
                        "total_teams": len(standing_group.get("table", [])),
                        "league_ja": comp_data.get("name_ja", ""),
                    }
    return {}


# ============================
# 個別ページHTML生成
# ============================
def get_related_players(player: dict, all_players: list, slug_map: dict) -> list:
    """同じ club_id の他の日本人選手を最大5名返す。"""
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")
    if not club_id:
        return []
    related = []
    for i, p in enumerate(all_players):
        if p.get("club_id") == club_id and p.get("name_en") != name_en:
            related.append({
                "name_ja": p.get("name_ja", ""),
                "name_en": p.get("name_en", ""),
                "position": p.get("position", ""),
                "slug": slug_map.get(i, make_slug(p.get("name_en", ""))),
            })
    return related[:5]


def calc_age(birth_date_str: str) -> str:
    """生年月日文字列（YYYY-MM-DD）から年齢を計算する。"""
    if not birth_date_str:
        return ""
    try:
        from datetime import date
        y, m, d = birth_date_str.split("-")
        bd = date(int(y), int(m), int(d))
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return str(age)
    except Exception:
        return ""


def foot_ja(foot: str) -> str:
    """利き足を日本語に変換する。"""
    if foot == "right":
        return "右"
    if foot == "left":
        return "左"
    if foot == "both":
        return "両足"
    return foot or ""


def build_player_page(player: dict, slug: str, scorer_stats: dict,
                      goal_events: list, club_matches: list, standing: dict,
                      wiki_stats: dict = None, services: dict = None,
                      related_players: list = None,
                      player_info: dict = None) -> str:
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    position = player.get("position", "")
    club_ja = player.get("club_ja", "")
    club_en = player.get("club_en", "")
    league_ja = player.get("league_ja", "")
    note = player.get("note", "")

    title = f"{esc(name_ja)}（{esc(name_en)}）プロフィール｜football-jp"
    desc = f"{esc(name_ja)}選手の{esc(club_ja)}での試合・ゴール・統計を日本時間で。"
    canonical = f"{SITE_URL}/players/{slug}/"

    # Schema.org Person JSON-LD
    schema_person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name_ja,
        "alternateName": name_en,
        "jobTitle": position,
        "affiliation": {
            "@type": "SportsTeam",
            "name": club_ja,
            "sport": "Football"
        },
        "url": canonical,
        "nationality": {
            "@type": "Country",
            "name": "Japan"
        }
    }
    schema_ld = json.dumps(schema_person, ensure_ascii=False, indent=2)

    # --- 統計セクション ---
    # wiki_stats を優先、なければ scorer_stats (football-data API top50) を使用
    active_stats = wiki_stats if wiki_stats else scorer_stats
    stats_source_note = ""
    if wiki_stats:
        stats_source_note = '<div class="stats-source">出典: Wikipedia</div>'
    elif scorer_stats:
        stats_source_note = '<div class="stats-source">出典: Football-Data.org</div>'

    stats_html = ""
    if active_stats:
        stats_html = f"""
    <section class="player-section">
      <h3>📊 今シーズン成績</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">出場試合</div>
          <div class="stat-value">{esc(str(active_stats.get('played', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ゴール</div>
          <div class="stat-value">{esc(str(active_stats.get('goals', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">アシスト</div>
          <div class="stat-value">{esc(str(active_stats.get('assists', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">PK</div>
          <div class="stat-value">{esc(str(active_stats.get('penalties', '—')))}</div>
        </div>
      </div>
      {stats_source_note}
    </section>"""

    # --- 順位セクション ---
    standing_html = ""
    if standing:
        pos = standing.get("position", "—")
        pts = standing.get("points", "—")
        total = standing.get("total_teams", "")
        played = standing.get("played", "—")
        won = standing.get("won", "—")
        draw = standing.get("draw", "—")
        lost = standing.get("lost", "—")
        league = standing.get("league_ja", league_ja)
        standing_html = f"""
    <section class="player-section">
      <h3>🏆 {esc(league)} 現在順位</h3>
      <div class="standing-row">
        <span class="standing-pos">{esc(str(pos))}位</span>
        <span class="standing-detail">（{esc(str(total))}チーム中）　{esc(str(played))}試合　{esc(str(won))}勝{esc(str(draw))}分{esc(str(lost))}敗　{esc(str(pts))}pt</span>
      </div>
    </section>"""

    # --- 直近の試合セクション ---
    matches_html = ""
    if club_matches:
        match_rows = ""
        for m in club_matches:
            kickoff = m.get("kickoff_jst", "")
            status = m.get("status", "")
            home_ja = m.get("home_ja", "")
            away_ja = m.get("away_ja", "")
            score = m.get("score", {})
            comp_ja = m.get("competition_ja", "")
            home_id = m.get("home_id")
            away_id = m.get("away_id")
            club_id = player.get("club_id")
            is_home = home_id == club_id

            # 日時表示（yyyy/mm/dd 改行 (曜) HH:MM JST）
            date_display = ""
            if kickoff:
                try:
                    import re as _re
                    from datetime import datetime
                    # タイムゾーン部分（+09:00 や Z）を除去してローカル日時として扱う
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', kickoff.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:16], "%Y-%m-%dT%H:%M")
                    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
                    wd = weekdays[dt.weekday()]
                    date_display = f'<span class="match-date-day">{dt.strftime("%Y/%m/%d")}</span><span class="match-date-time">（{wd}）{dt.strftime("%H:%M")}</span>'
                except Exception:
                    # フォールバック：ISO文字列を最低限分割
                    if "T" in kickoff:
                        d, t = kickoff.split("T", 1)
                        # yyyy-mm-dd → yyyy/mm/dd
                        d_fmt = d.replace("-", "/")
                        date_display = f'<span class="match-date-day">{d_fmt}</span><span class="match-date-time">{t[:5]}</span>'
                    else:
                        date_display = kickoff[:16]

            # スコア表示
            if status == "FINISHED" and score:
                home_score = score.get("home", "")
                away_score = score.get("away", "")
                if is_home:
                    score_display = f"{home_score} - {away_score}"
                    opponent = esc(away_ja)
                    result_class = "win" if home_score > away_score else ("lose" if home_score < away_score else "draw")
                else:
                    score_display = f"{away_score} - {home_score}"
                    opponent = esc(home_ja)
                    result_class = "win" if away_score > home_score else ("lose" if away_score < home_score else "draw")
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                match_rows += f"""
          <div class="match-row">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result {result_class}">{esc(score_display)}</div>
            <div class="match-broadcast">—</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""
            else:
                if is_home:
                    opponent = esc(away_ja)
                else:
                    opponent = esc(home_ja)
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                broadcasters_list = m.get("broadcasters", [])
                league_ja_m = m.get("competition_ja", player.get("league_ja", ""))
                bc_tags = ""
                if broadcasters_list and services is not None:
                    tags = [build_bc_tag(b, services, "player", slug, league_ja_m)
                            for b in broadcasters_list[:2] if b.get("name")]
                    bc_tags = " ".join(tags)
                elif broadcasters_list:
                    bc_names = [b.get("name", "") for b in broadcasters_list[:2] if b.get("name")]
                    bc_tags = esc(" / ".join(bc_names))
                match_rows += f"""
          <div class="match-row scheduled">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result">—</div>
            <div class="match-broadcast">{bc_tags if bc_tags else "—"}</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""

        matches_html = f"""
    <section class="player-section">
      <h3>📅 直近の試合（最大10試合）</h3>
      <div class="matches-list">
        <div class="match-header">
          <div class="match-date">日時（JST）</div>
          <div class="match-venue">場所</div>
          <div class="match-opponent">対戦相手</div>
          <div class="match-result">結果</div>
          <div class="match-broadcast">配信</div>
          <div class="match-comp">大会</div>
        </div>
        {match_rows}
      </div>
    </section>"""
    else:
        matches_html = """
    <section class="player-section">
      <h3>📅 直近の試合</h3>
      <p class="no-data">試合データを取得中です。</p>
    </section>"""

    # --- ゴールセクション ---
    goals_html = ""
    if goal_events:
        goal_rows = ""
        for g in goal_events:
            kickoff = g.get("kickoff_jst", "")
            date_display = ""
            if kickoff:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(kickoff)
                    date_display = dt.strftime("%m/%d")
                except Exception:
                    date_display = kickoff[:10]

            home_ja_g = g.get("home_ja", "")
            away_ja_g = g.get("away_ja", "")
            minute_raw = g.get("minute_raw", str(g.get("minute", "?")))
            goal_note = g.get("note", "")
            comp_ja_g = g.get("competition_ja", "")
            if goal_note:
                minute_raw += f" ({goal_note})"
            goal_rows += f"""
          <div class="goal-row">
            <div class="goal-date">{date_display}</div>
            <div class="goal-match">{esc(home_ja_g)} vs {esc(away_ja_g)}</div>
            <div class="goal-minute">{esc(minute_raw)}分</div>
            <div class="goal-comp">{esc(comp_ja_g)}</div>
          </div>"""
        goals_html = f"""
    <section class="player-section">
      <h3>⚽ 直近のゴール</h3>
      <div class="goals-list">
        {goal_rows}
      </div>
    </section>"""
    else:
        goals_html = """
    <section class="player-section">
      <h3>⚽ 直近のゴール</h3>
      <p class="no-data">今シーズンまだゴールなし（または取得範囲外）。</p>
    </section>"""

    # --- プロフィール情報セクション（身長・体重・年齢・利き足）---
    profile_info_html = ""
    if player_info:
        height_cm = player_info.get("height_cm")
        weight_kg = player_info.get("weight_kg")
        birth_date = player_info.get("birth_date")
        # 出身地：_ja フィールドがあれば優先
        birth_place_ja = player_info.get("birth_place_ja", "")
        birth_place = player_info.get("birth_place", "")
        display_place = birth_place_ja if birth_place_ja else birth_place
        foot = player_info.get("foot")
        wiki_url = player_info.get("wiki_url")

        height_str = f"{height_cm}cm" if height_cm else "—"
        weight_str = f"{weight_kg}kg" if weight_kg else "—"
        age_str = calc_age(birth_date)
        birth_str = f"{esc(birth_date)}（{age_str}歳）" if birth_date and age_str else esc(birth_date or "—")
        foot_str = foot_ja(foot) if foot else "—"
        place_str = esc(display_place) if display_place else "—"

        wiki_link = ""
        if wiki_url:
            wiki_link = f' <a href="{esc(wiki_url)}" target="_blank" rel="noopener" style="font-size:11px;color:#888;">Wikipedia →</a>'

        profile_info_html = f"""
    <section class="player-section">
      <h3>👤 プロフィール{wiki_link}</h3>
      <table class="profile-table">
        <tr><td class="profile-label">身長 / 体重</td><td class="profile-value">{height_str} / {weight_str}</td></tr>
        <tr><td class="profile-label">生年月日</td><td class="profile-value">{birth_str}</td></tr>
        <tr><td class="profile-label">出身地</td><td class="profile-value">{place_str}</td></tr>
        <tr><td class="profile-label">利き足</td><td class="profile-value">{foot_str}</td></tr>
      </table>
    </section>"""

    # --- キャリアセクション ---
    career_html = ""
    if player_info:
        # career_ja があれば優先、なければ career（英語）にフォールバック
        career_ja = player_info.get("career_ja", [])
        career_en = player_info.get("career", [])
        career = career_ja if career_ja else career_en
        if career:
            career_rows = ""
            for item in career:
                years = esc(item.get("years", ""))
                club = esc(item.get("club", ""))
                career_rows += f'<div class="career-row"><span class="career-years">{years}</span><span class="career-club">{club}</span></div>'
            career_html = f"""
    <section class="player-section">
      <h3>📋 キャリア</h3>
      <div class="career-list">
        {career_rows}
      </div>
    </section>"""

    # --- SNSセクション ---
    sns_html = ""
    if player_info:
        twitter = player_info.get("twitter")
        instagram = player_info.get("instagram")
        official_url = player_info.get("official_url")
        sns_items = []
        if twitter:
            handle = twitter.lstrip("@")
            sns_items.append(f'<a class="sns-link sns-twitter" href="https://x.com/{esc(handle)}" target="_blank" rel="noopener">𝕏 {esc(twitter)}</a>')
        if instagram:
            sns_items.append(f'<a class="sns-link sns-instagram" href="https://www.instagram.com/{esc(instagram)}/" target="_blank" rel="noopener">📷 @{esc(instagram)}</a>')
        if official_url:
            domain = official_url.replace("https://", "").replace("http://", "").split("/")[0]
            sns_items.append(f'<a class="sns-link sns-official" href="{esc(official_url)}" target="_blank" rel="noopener">🌐 {esc(domain)}</a>')
        if sns_items:
            sns_html = f"""
    <section class="player-section">
      <h3>🔗 SNS・公式リンク</h3>
      <div class="sns-links">
        {"".join(sns_items)}
      </div>
    </section>"""

    # --- 関連選手セクション（同クラブ他日本人）---
    related_html = ""
    if related_players:
        cards_html = ""
        for rp in related_players:
            cards_html += f"""
          <a class="related-player-card" href="/players/{esc(rp['slug'])}/">
            <span class="related-player-flag">🇯🇵</span>
            <div class="related-player-info">
              <div class="related-player-name-ja">{esc(rp['name_ja'])}</div>
              <div class="related-player-name-en">{esc(rp['name_en'])}</div>
              <div class="related-player-pos">{esc(rp['position'])}</div>
            </div>
          </a>"""
        related_html = f"""
    <section class="player-section">
      <h3>🏟️ 同クラブの日本人選手</h3>
      <div class="related-players-grid">
        {cards_html}
      </div>
    </section>"""

    # note がある場合
    note_html = ""
    if note:
        note_html = f'<div class="player-note">ℹ️ {esc(note)}</div>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="profile">
  <meta property="og:url" content="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:site_name" content="{esc(SITE_NAME)}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "{GA4_ID}");
  </script>
  <link rel="icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/logos/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/assets/logos/favicon-48.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <style>
    .player-hero {{
      background: #ffffff;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 18px;
      margin-bottom: 18px;
    }}
    .player-hero .name-block h2 {{
      margin: 0 0 4px;
      font-size: 26px;
      font-weight: 800;
    }}
    .player-hero .name-en {{
      font-size: 13px;
      color: #666;
      margin: 0 0 8px;
    }}
    .player-hero .player-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .player-meta-tag {{
      display: inline-block;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 600;
      background: #f0f1f5;
      border-radius: 3px;
    }}
    .player-section {{
      background: #fff;
      padding: 18px 16px;
      margin-bottom: 1px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .player-section h3 {{
      margin: 0 0 14px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding-left: 10px;
      border-left: 4px solid var(--c-accent, #0047ab);
      color: var(--c-text, #111);
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      border: 1px solid var(--c-border, #e5e7eb);
    }}
    .stat-card {{
      background: #fff;
      border-right: 1px solid var(--c-border, #e5e7eb);
      padding: 12px 14px;
      text-align: center;
    }}
    .stat-card:last-child {{ border-right: none; }}
    .stat-label {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .stat-value {{ font-size: 22px; font-weight: 800; color: var(--c-text, #111); }}
    .standing-row {{
      font-size: 14px;
      padding: 8px 0;
    }}
    .standing-pos {{
      font-size: 24px;
      font-weight: 800;
      margin-right: 12px;
    }}
    .standing-detail {{ color: #444; }}
    .matches-list {{
      font-size: 13px;
    }}
    .match-header, .match-row {{
      display: grid;
      grid-template-columns: 110px 30px 1fr 60px 110px 80px;
      gap: 6px;
      padding: 8px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: start;
    }}
    .match-header {{
      font-size: 11px;
      font-weight: 700;
      color: #666;
      background: #f8f9fa;
      align-items: center;
    }}
    .match-row:last-child {{ border-bottom: none; }}
    .match-result {{
      font-weight: 700;
      text-align: center;
    }}
    .match-result.win {{ color: #1a7a3a; }}
    .match-result.lose {{ color: #c0392b; }}
    .match-result.draw {{ color: #666; }}
    .match-broadcast {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      align-items: flex-start;
    }}
    .match-date-day {{ display: block; font-size: 12px; }}
    .match-date-time {{ display: block; font-size: 11px; color: #555; }}
    .venue-badge {{
      display: inline-block;
      width: 24px;
      height: 24px;
      line-height: 24px;
      text-align: center;
      border-radius: 4px;
      font-weight: 700;
      font-size: 12px;
    }}
    .venue-away {{ background: #fee; color: #c9302c; border: 1px solid #f5b7b1; }}
    .venue-home {{ background: #e7f0ff; color: #1e6cba; border: 1px solid #aac6e8; }}
    .match-comp {{ font-size: 11px; color: #666; }}
    .goals-list {{ font-size: 13px; }}
    .goal-row {{
      display: grid;
      grid-template-columns: 50px 1fr 70px 100px;
      gap: 8px;
      padding: 8px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: center;
    }}
    .goal-row:last-child {{ border-bottom: none; }}
    .goal-date {{ font-size: 11px; color: #666; }}
    .goal-minute {{ font-weight: 700; text-align: center; color: #1a7a3a; }}
    .goal-comp {{ font-size: 11px; color: #666; }}
    .no-data {{
      color: #888;
      font-size: 13px;
      padding: 8px 0;
      margin: 0;
    }}
    .stats-source {{
      font-size: 11px;
      color: #999;
      margin-top: 6px;
      text-align: right;
    }}
    .player-note {{
      background: #fff8e1;
      border-left: 3px solid #d4af37;
      padding: 8px 12px;
      font-size: 12px;
      margin: 8px 0 0;
    }}
    .related-players-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 8px;
    }}
    .related-player-card {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px;
      padding: 10px 12px;
      text-decoration: none;
      color: var(--c-text, #111);
      transition: background 0.15s;
    }}
    .related-player-card:hover {{ background: #eef0f7; }}
    .related-player-flag {{ font-size: 18px; line-height: 1; padding-top: 1px; flex-shrink: 0; }}
    .related-player-name-ja {{ font-size: 13px; font-weight: 700; margin-bottom: 2px; }}
    .related-player-name-en {{ font-size: 10px; color: #666; margin-bottom: 3px; }}
    .related-player-pos {{
      display: inline-block;
      padding: 1px 5px;
      font-size: 10px;
      font-weight: 700;
      background: #e6f0fa;
      color: #1565c0;
      border-radius: 3px;
    }}
    .back-link {{
      display: block;
      padding: 12px 16px;
      font-size: 13px;
      color: var(--c-text, #111);
      text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .site-footer {{
      padding: 20px 16px;
      font-size: 12px;
      color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb);
      margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
    .profile-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .profile-table tr {{
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .profile-table tr:last-child {{ border-bottom: none; }}
    .profile-label {{
      width: 100px;
      padding: 7px 0;
      color: #666;
      font-size: 12px;
      vertical-align: top;
    }}
    .profile-value {{
      padding: 7px 0;
      font-weight: 600;
    }}
    .career-list {{
      font-size: 13px;
    }}
    .career-row {{
      display: flex;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: baseline;
    }}
    .career-row:last-child {{ border-bottom: none; }}
    .career-years {{
      min-width: 90px;
      color: #888;
      font-size: 12px;
      flex-shrink: 0;
    }}
    .career-club {{
      font-weight: 600;
    }}
    .sns-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .sns-link {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      transition: opacity 0.15s;
    }}
    .sns-link:hover {{ opacity: 0.8; }}
    .sns-twitter {{ background: #000; color: #fff; }}
    .sns-instagram {{ background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); color: #fff; }}
    .sns-official {{ background: #f0f1f5; color: #333; border: 1px solid #ccc; }}
    @media (max-width: 600px) {{
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .match-header, .match-row {{
        grid-template-columns: 80px 28px 1fr 45px;
        font-size: 12px;
      }}
      .match-broadcast, .match-comp {{ display: none; }}
      .goal-row {{ grid-template-columns: 45px 1fr 60px; }}
      .goal-comp {{ display: none; }}
    }}
  </style>
  <script type="application/ld+json">
{schema_ld}
  </script>
</head>
<body>

<a class="back-link" href="/">← football-jp トップへ</a>

<div class="player-hero">
  <div class="name-block">
    <h2>🇯🇵 {esc(name_ja)}</h2>
    <p class="name-en">{esc(name_en)}</p>
    <div class="player-meta">
      <span class="player-meta-tag">⚽ {esc(position)}</span>
      <span class="player-meta-tag">🏟️ {esc(club_ja)}（{esc(club_en)}）</span>
      <span class="player-meta-tag">🏆 {esc(league_ja)}</span>
    </div>
    {note_html}
  </div>
</div>

<div style="max-width: 860px; margin: 0 auto;">

  {profile_info_html}

  {stats_html}

  {standing_html}

  {matches_html}

  {goals_html}

  {career_html}

  {sns_html}

  {related_html}

  <div class="player-section">
    <h3>🔗 関連リンク</h3>
    <p style="font-size:13px; margin: 0;">
      <a href="/clubs/{make_slug(club_en)}/" style="color: var(--c-accent, #0047ab);">
        {esc(club_ja)} クラブページ →
      </a>
    </p>
  </div>

  <footer class="site-footer">
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football-Data.org</a></p>
    <p class="footer-links">
      <a href="/">football-jp トップへ</a> |
      <a href="/players/">選手一覧</a> |
      <a href="/clubs/">クラブ一覧</a> |
      <a href="/privacy.html">プライバシーポリシー</a>
    </p>
  </footer>
</div>

<script>
function trackAffClick(el) {{
  if (typeof gtag === 'function') {{
    gtag('event', 'affiliate_click', {{
      service: el.dataset.svc,
      page_type: el.dataset.pagetype,
      page_id: el.dataset.pageid,
      destination: el.href
    }});
  }}
}}
</script>

</body>
</html>
"""


# ============================
# 一覧ページHTML生成
# ============================
def build_players_index(players: list, slug_map: dict) -> str:
    """選手一覧ページ（/players/index.html）を生成する。"""
    title = "日本人サッカー選手 一覧 海外組68名｜football-jp"
    desc = "プレミア・ラ・リーガ・ブンデス等で活躍する日本人選手68名の一覧。各選手のプロフィール・統計・最近の試合へ。"
    canonical = f"{SITE_URL}/players/"

    # ポジション正規化（GK/DF/MF/FW の4分類）
    def pos_category(pos: str) -> str:
        p = pos.upper()
        if "GK" in p:
            return "GK"
        if p.startswith("DF") or p.endswith("DF"):
            return "DF"
        if p.startswith("FW") or p.endswith("FW"):
            return "FW"
        if "MF" in p:
            return "MF"
        return "他"

    # リーグ別にグループ化
    LEAGUE_ORDER = [
        "プレミアリーグ", "チャンピオンシップ",
        "ブンデスリーガ", "ラ・リーガ",
        "セリエA", "リーグ・アン", "リーグ・ドゥ",
        "エールディビジ", "プリメイラ・リーガ", "ジュピラー・プロ・リーグ",
    ]
    groups: dict = {}
    for i, p in enumerate(players):
        league = p.get("league_ja", "その他")
        if league not in groups:
            groups[league] = []
        groups[league].append((i, p))

    # リーグ順でソート
    sorted_leagues = sorted(
        groups.keys(),
        key=lambda l: LEAGUE_ORDER.index(l) if l in LEAGUE_ORDER else 99
    )

    sections_html = ""
    for league in sorted_leagues:
        league_players = groups[league]
        cards_html = ""
        for i, p in league_players:
            slug = slug_map[i]
            pos_cat = pos_category(p.get("position", ""))
            cards_html += f"""
        <a class="player-card" href="/players/{esc(slug)}/"
           data-pos="{esc(pos_cat)}">
          <span class="player-card-flag">🇯🇵</span>
          <div class="player-card-body">
            <div class="player-card-name-ja">{esc(p.get('name_ja',''))}</div>
            <div class="player-card-name-en">{esc(p.get('name_en',''))}</div>
            <div class="player-card-meta">
              <span class="pos-badge pos-{esc(pos_cat.lower())}">{esc(pos_cat)}</span>
              <span class="club-name">{esc(p.get('club_ja',''))}</span>
            </div>
          </div>
        </a>"""

        sections_html += f"""
      <section class="league-section">
        <h2 class="league-heading">{esc(league)}</h2>
        <div class="player-grid">
          {cards_html}
        </div>
      </section>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:site_name" content="{esc(SITE_NAME)}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "{GA4_ID}");
  </script>
  <link rel="icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <style>
    .index-hero {{
      background: #fff;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 16px;
      margin-bottom: 0;
    }}
    .index-hero h1 {{
      margin: 0 0 6px;
      font-size: 22px;
      font-weight: 800;
    }}
    .index-hero p {{
      margin: 0;
      font-size: 13px;
      color: #555;
    }}
    .filter-bar {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      padding: 10px 16px;
      background: #f8f9fa;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .filter-btn {{
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid #ccc;
      border-radius: 4px;
      background: #fff;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--c-accent, #0047ab);
      color: #fff;
      border-color: var(--c-accent, #0047ab);
    }}
    .league-section {{
      padding: 14px 16px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      background: #fff;
      margin-bottom: 1px;
    }}
    .league-section.hidden {{ display: none; }}
    .league-heading {{
      font-size: 13px;
      font-weight: 700;
      color: #444;
      margin: 0 0 10px;
      padding-left: 8px;
      border-left: 3px solid var(--c-accent, #0047ab);
    }}
    .player-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }}
    .player-card {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px;
      padding: 10px 12px;
      text-decoration: none;
      color: var(--c-text, #111);
      transition: background 0.15s;
    }}
    .player-card:hover {{ background: #eef0f7; }}
    .player-card.hidden {{ display: none; }}
    .player-card-flag {{ font-size: 18px; line-height: 1; padding-top: 1px; }}
    .player-card-name-ja {{ font-size: 14px; font-weight: 700; margin-bottom: 2px; }}
    .player-card-name-en {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .player-card-meta {{ display: flex; align-items: center; gap: 6px; }}
    .pos-badge {{
      display: inline-block;
      padding: 1px 5px;
      font-size: 10px;
      font-weight: 700;
      border-radius: 3px;
      background: #e6f0fa;
      color: #1565c0;
    }}
    .pos-gk {{ background: #fff3e0; color: #e65100; }}
    .pos-df {{ background: #e8f5e9; color: #2e7d32; }}
    .pos-mf {{ background: #e6f0fa; color: #1565c0; }}
    .pos-fw {{ background: #fce4ec; color: #c62828; }}
    .club-name {{ font-size: 11px; color: #555; }}
    .back-link {{
      display: block;
      padding: 12px 16px;
      font-size: 13px;
      color: var(--c-text, #111);
      text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .site-footer {{
      padding: 20px 16px;
      font-size: 12px;
      color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb);
      margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
  </style>
</head>
<body>

<a class="back-link" href="/">← football-jp トップへ</a>

<div class="index-hero">
  <h1>🇯🇵 日本人選手 一覧</h1>
  <p>海外リーグで活躍する日本人選手 {len(players)} 名</p>
</div>

<div class="filter-bar" id="filterBar">
  <button class="filter-btn active" data-filter="all" onclick="filterPlayers('all', this)">すべて</button>
  <button class="filter-btn" data-filter="GK" onclick="filterPlayers('GK', this)">GK</button>
  <button class="filter-btn" data-filter="DF" onclick="filterPlayers('DF', this)">DF</button>
  <button class="filter-btn" data-filter="MF" onclick="filterPlayers('MF', this)">MF</button>
  <button class="filter-btn" data-filter="FW" onclick="filterPlayers('FW', this)">FW</button>
</div>

<div style="max-width: 900px; margin: 0 auto;">
  {sections_html}

  <footer class="site-footer">
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football-Data.org</a></p>
    <p class="footer-links">
      <a href="/">football-jp トップへ</a> |
      <a href="/clubs/">クラブ一覧（41）</a> |
      <a href="/privacy.html">プライバシーポリシー</a>
    </p>
  </footer>
</div>

<script>
function filterPlayers(pos, btn) {{
  // ボタン状態更新
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  // カード表示切替
  document.querySelectorAll('.player-card').forEach(card => {{
    if (pos === 'all' || card.dataset.pos === pos) {{
      card.classList.remove('hidden');
    }} else {{
      card.classList.add('hidden');
    }}
  }});

  // 全カード非表示のセクションを隠す
  document.querySelectorAll('.league-section').forEach(sec => {{
    const visible = [...sec.querySelectorAll('.player-card')].some(c => !c.classList.contains('hidden'));
    sec.classList.toggle('hidden', !visible);
  }});
}}
</script>
<script>
function trackAffClick(el) {{
  if (typeof gtag === 'function') {{
    gtag('event', 'affiliate_click', {{
      service: el.dataset.svc,
      page_type: el.dataset.pagetype,
      page_id: el.dataset.pageid,
      destination: el.href
    }});
  }}
}}
</script>

</body>
</html>
"""


# ============================
# メイン処理
# ============================
def main():
    print(f"データ読み込み中...")
    players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info = load_data()
    print(f"  選手数: {len(players)}")
    print(f"  試合数: {len(matches)}")

    # slug生成
    slug_map = make_unique_slugs(players)

    generated = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, player in enumerate(players):
        slug = slug_map[i]
        name_ja = player.get("name_ja", "")
        name_en = player.get("name_en", "")

        # 統計データ取得
        wiki_stats = get_player_wiki_stats(player, player_stats)
        scorer_stats = get_player_scorer_stats(player, scorers_comps)
        goal_events = get_player_goals(player, events, matches_dict)
        club_matches = get_club_matches(player, matches)
        standing = get_club_standing(player, standings_comps)
        related_players = get_related_players(player, players, slug_map)
        pinfo = player_info.get(name_en)

        # HTMLページ生成
        html = build_player_page(player, slug, scorer_stats, goal_events, club_matches, standing,
                                 wiki_stats=wiki_stats, services=services,
                                 related_players=related_players,
                                 player_info=pinfo)

        # 出力
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((name_ja, name_en, slug, size))
        print(f"  ✅ {name_ja} ({name_en}) → /players/{slug}/ ({size:,} bytes)")

    print(f"\n合計 {len(generated)} 選手ページ生成完了")

    # slug一覧
    print("\n生成済みslug一覧:")
    for name_ja, name_en, slug, size in generated:
        print(f"  {name_ja:12s} → /players/{slug}/")

    # 一覧ページ生成
    print("\n一覧ページ生成中...")
    index_html = build_players_index(players, slug_map)
    index_path = OUTPUT_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"  ✅ /players/index.html → {index_path.stat().st_size:,} bytes")

    print("\n完了！")
    return slug_map


if __name__ == "__main__":
    main()
