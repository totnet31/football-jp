#!/usr/bin/env python3
"""
generate_player_pages_en.py
英語版 日本人選手プロフィールページを自動生成するスクリプト。
出力先: en/players/{slug}/index.html
使い方: python3 scripts/generate_player_pages_en.py
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
PLAYER_VIDEOS_JSON = REPO_ROOT / "data" / "player_videos.json"
OUTPUT_DIR = REPO_ROOT / "en" / "players"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"

# 翻訳辞書をインポート
sys.path.insert(0, str(Path(__file__).parent))
from translation_dict import (
    translate_league, translate_position,
    translate_career_club, translate_birthplace,
    LEAGUE_JA_TO_EN, POSITION_JA_TO_EN
)


# ============================
# slug生成
# ============================
def make_slug(name_en: str) -> str:
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


def make_unique_slugs(players: list) -> dict:
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
# データ読み込み
# ============================
def load_services() -> dict:
    if not BROADCASTERS_JSON.exists():
        return {}
    with open(BROADCASTERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("services", {})


def load_data():
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    with open(MATCHES_JSON, encoding="utf-8") as f:
        matches_raw = json.load(f)
    matches = matches_raw.get("matches", [])
    matches_dict = {str(m["id"]): m for m in matches}

    scorers_comps = {}
    if SCORERS_JSON.exists():
        with open(SCORERS_JSON, encoding="utf-8") as f:
            scorers_raw = json.load(f)
        scorers_comps = scorers_raw.get("competitions", {})

    events = {}
    if MATCH_EVENTS_JSON.exists():
        with open(MATCH_EVENTS_JSON, encoding="utf-8") as f:
            events_raw = json.load(f)
        events = events_raw.get("events", {})

    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_raw = json.load(f)
    standings_comps = standings_raw.get("competitions", {})

    player_stats = {}
    if PLAYER_STATS_JSON.exists():
        with open(PLAYER_STATS_JSON, encoding="utf-8") as f:
            ps_raw = json.load(f)
        player_stats = ps_raw.get("stats", {})
        print(f"  player_stats.json: {len(player_stats)} players")

    player_info = {}
    if PLAYER_INFO_JSON.exists():
        with open(PLAYER_INFO_JSON, encoding="utf-8") as f:
            player_info = json.load(f)
        print(f"  player_info.json: {len(player_info)} players")

    player_videos = {}
    if PLAYER_VIDEOS_JSON.exists():
        try:
            with open(PLAYER_VIDEOS_JSON, encoding="utf-8") as f:
                pv_raw = json.load(f)
            player_videos = pv_raw.get("players", {})
        except Exception:
            pass

    services = load_services()

    return players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info, player_videos


# ============================
# データ取得ヘルパー
# ============================
def get_player_wiki_stats(player: dict, player_stats: dict) -> dict:
    name_en = player.get("name_en", "")
    entry = player_stats.get(name_en)
    if entry:
        return {
            "goals": entry.get("goals", 0),
            "assists": entry.get("assists", 0),
            "penalties": 0,
            "played": entry.get("apps", 0),
        }
    return {}


def get_player_scorer_stats(player: dict, scorers_comps: dict) -> dict:
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")
    if not comp_id or comp_id not in scorers_comps:
        return {}
    comp_data = scorers_comps[comp_id]
    scorers = comp_data.get("scorers", [])
    for s in scorers:
        scorer_name = s.get("player_name", "")
        en_parts = name_en.lower().split()
        scorer_parts = scorer_name.lower().split()
        if en_parts and scorer_parts:
            if en_parts[-1] == scorer_parts[-1]:
                if club_id and s.get("team_id") == club_id:
                    return {
                        "goals": s.get("goals", 0),
                        "assists": s.get("assists", 0),
                        "penalties": s.get("penalties", 0),
                        "played": s.get("playedMatches", 0),
                    }
    return {}


def get_player_goals(player: dict, events: dict, matches_dict: dict) -> list:
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    goal_events = []
    for match_id, evs in events.items():
        for ev in evs:
            if ev.get("type") == "goal" and ev.get("is_japanese"):
                ev_name_ja = ev.get("player_ja", "")
                ev_name_en = ev.get("player_en", "")
                matched = False
                if ev_name_ja and name_ja and ev_name_ja in name_ja:
                    matched = True
                if not matched and ev_name_ja and name_ja and name_ja in ev_name_ja:
                    matched = True
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
                        "home_en": match.get("home_en", match.get("home_ja", "")),
                        "away_en": match.get("away_en", match.get("away_ja", "")),
                        "score": match.get("score", {}),
                        "kickoff_jst": match.get("kickoff_jst", ""),
                        "competition_en": LEAGUE_JA_TO_EN.get(
                            match.get("competition_ja", ""), match.get("competition_ja", "")),
                    })
    goal_events.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return goal_events[:10]


def get_club_matches(player: dict, matches: list) -> list:
    club_id = player.get("club_id")
    if not club_id:
        return []
    club_matches = [m for m in matches if m.get("home_id") == club_id or m.get("away_id") == club_id]
    club_matches.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return club_matches


def get_club_highlights(player: dict, matches: list) -> list:
    club_id = player.get("club_id")
    if not club_id:
        return []
    videos = []
    for m in sorted(matches, key=lambda x: x.get("kickoff_jst", ""), reverse=True):
        if m.get("home_id") != club_id and m.get("away_id") != club_id:
            continue
        for h in m.get("highlights", []):
            vid = h.get("video_id", "")
            if not vid:
                continue
            videos.append({
                "video_id": vid,
                "url": h.get("url", f"https://www.youtube.com/watch?v={vid}"),
                "title": h.get("title", ""),
                "channel": h.get("broadcaster", ""),
                "published": m.get("kickoff_jst", ""),
            })
            if len(videos) >= 10:
                return videos
    return videos


def get_club_standing(player: dict, standings_comps: dict) -> dict:
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")
    if not comp_id or not club_id or comp_id not in standings_comps:
        return {}
    comp_data = standings_comps[comp_id]
    for sg in comp_data.get("standings", []):
        if sg.get("type") == "TOTAL":
            for entry in sg.get("table", []):
                if entry.get("team_id") == club_id:
                    league_ja = comp_data.get("name_ja", "")
                    return {
                        "position": entry.get("position"),
                        "points": entry.get("points"),
                        "played": entry.get("playedGames"),
                        "won": entry.get("won"),
                        "draw": entry.get("draw"),
                        "lost": entry.get("lost"),
                        "goals_for": entry.get("goalsFor"),
                        "goals_against": entry.get("goalsAgainst"),
                        "total_teams": len(sg.get("table", [])),
                        "league_en": translate_league(league_ja),
                    }
    return {}


def get_related_players(player: dict, all_players: list, slug_map: dict) -> list:
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
                "position": translate_position(p.get("position", "")),
                "slug": slug_map.get(i, make_slug(p.get("name_en", ""))),
            })
    return related[:5]


def calc_age(birth_date_str: str) -> str:
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


def foot_en(foot: str) -> str:
    if foot == "right":
        return "Right"
    if foot == "left":
        return "Left"
    if foot == "both":
        return "Both"
    return foot or "—"


# ============================
# HTML生成
# ============================
def build_player_page_en(player: dict, slug: str, scorer_stats: dict,
                         goal_events: list, club_matches: list, standing: dict,
                         wiki_stats: dict = None, services: dict = None,
                         related_players: list = None,
                         player_info: dict = None,
                         highlights: list = None,
                         player_videos: list = None) -> str:
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    position_ja = player.get("position", "")
    position_en = translate_position(position_ja)
    club_ja = player.get("club_ja", "")
    club_en = player.get("club_en", "")
    league_ja = player.get("league_ja", "")
    league_en = translate_league(league_ja)
    note = player.get("note", "")

    title = f"{esc(name_en)} - Stats & Match History | football-jp"
    goals_val = (wiki_stats or scorer_stats or {}).get("goals", 0) if (wiki_stats or scorer_stats) else 0
    played_val = (wiki_stats or scorer_stats or {}).get("played", 0) if (wiki_stats or scorer_stats) else 0
    if goals_val and played_val:
        desc = f"{name_en} ({position_en}, {club_en}) – {goals_val} goals in {played_val} apps this season. Match schedule, stats, and broadcaster info in JST. Japanese overseas player tracker."
    else:
        desc = f"{name_en} ({position_en}) plays for {club_en} in the {league_en}. Match schedule, stats, broadcasters, and career info updated in Japan Standard Time."
    if len(desc) > 160:
        desc = desc[:157] + "..."
    canonical = f"{SITE_URL}/en/players/{slug}/"
    ja_url = f"{SITE_URL}/players/{slug}/"

    # Schema.org Person JSON-LD (English, 強化版)
    schema_person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name_en,
        "alternateName": name_ja,
        "jobTitle": "Footballer",
        "nationality": "JP",
        "memberOf": {
            "@type": "SportsTeam",
            "name": club_en,
            "sport": "Soccer",
            "url": f"{SITE_URL}/en/clubs/{make_slug(club_en)}/"
        },
        "url": canonical,
    }
    schema_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/en/"},
            {"@type": "ListItem", "position": 2, "name": "Players", "item": f"{SITE_URL}/en/players/"},
            {"@type": "ListItem", "position": 3, "name": name_en, "item": canonical},
        ]
    }
    schema_ld = json.dumps(schema_person, ensure_ascii=False, indent=2)
    schema_breadcrumb_ld = json.dumps(schema_breadcrumb, ensure_ascii=False, indent=2)

    # --- Stats section ---
    active_stats = wiki_stats if wiki_stats else scorer_stats
    stats_source_note = ""
    if wiki_stats:
        stats_source_note = '<div class="stats-source">Source: Wikipedia</div>'
    elif scorer_stats:
        stats_source_note = '<div class="stats-source">Source: Football-Data.org</div>'

    stats_html = ""
    if active_stats:
        stats_html = f"""
    <section class="player-section">
      <h3>📊 Season Stats</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Apps</div>
          <div class="stat-value">{esc(str(active_stats.get('played', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Goals</div>
          <div class="stat-value">{esc(str(active_stats.get('goals', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Assists</div>
          <div class="stat-value">{esc(str(active_stats.get('assists', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Pens</div>
          <div class="stat-value">{esc(str(active_stats.get('penalties', '—')))}</div>
        </div>
      </div>
      {stats_source_note}
    </section>"""

    # --- Standings section ---
    standing_html = ""
    if standing:
        pos = standing.get("position", "—")
        pts = standing.get("points", "—")
        total = standing.get("total_teams", "")
        played = standing.get("played", "—")
        won = standing.get("won", "—")
        draw = standing.get("draw", "—")
        lost = standing.get("lost", "—")
        league_disp = standing.get("league_en", league_en)
        standing_html = f"""
    <section class="player-section">
      <h3>🏆 {esc(league_disp)} Current Standings</h3>
      <div class="standing-row">
        <span class="standing-pos">{esc(str(pos))}</span>
        <span class="standing-detail">
          (of {esc(str(total))})&nbsp;&nbsp;{esc(str(played))} played&nbsp;
          {esc(str(won))}W {esc(str(draw))}D {esc(str(lost))}L&nbsp;
          {esc(str(pts))} pts
        </span>
      </div>
    </section>"""

    # --- Matches section ---
    matches_html = ""
    if club_matches:
        match_rows = ""
        for idx, m in enumerate(club_matches):
            kickoff = m.get("kickoff_jst", "")
            status = m.get("status", "")
            home_en_m = m.get("home_en", m.get("home_ja", ""))
            away_en_m = m.get("away_en", m.get("away_ja", ""))
            score = m.get("score", {})
            comp_ja_m = m.get("competition_ja", "")
            comp_en_m = LEAGUE_JA_TO_EN.get(comp_ja_m, comp_ja_m)
            home_id = m.get("home_id")
            club_id = player.get("club_id")
            is_home = home_id == club_id
            extra_cls = " hidden-extra" if idx >= 10 else ""

            date_display = ""
            if kickoff:
                try:
                    import re as _re
                    from datetime import datetime
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', kickoff.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:16], "%Y-%m-%dT%H:%M")
                    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    wd = weekdays[dt.weekday()]
                    date_display = f'<span class="match-date-day">{dt.strftime("%Y/%m/%d")}</span><span class="match-date-time">({wd}) {dt.strftime("%H:%M")}</span>'
                except Exception:
                    if "T" in kickoff:
                        d, t = kickoff.split("T", 1)
                        date_display = f'<span class="match-date-day">{d.replace("-", "/")}</span><span class="match-date-time">{t[:5]}</span>'
                    else:
                        date_display = kickoff[:16]

            if status == "FINISHED" and score:
                home_score = score.get("home", "")
                away_score = score.get("away", "")
                if is_home:
                    score_display = f"{home_score} - {away_score}"
                    opponent = esc(away_en_m)
                    result_class = "win" if home_score > away_score else ("lose" if home_score < away_score else "draw")
                else:
                    score_display = f"{away_score} - {home_score}"
                    opponent = esc(home_en_m)
                    result_class = "win" if away_score > home_score else ("lose" if away_score < home_score else "draw")
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                match_rows += f"""
          <div class="match-row{extra_cls}">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result {result_class}">{esc(score_display)}</div>
            <div class="match-broadcast">—</div>
            <div class="match-comp">{esc(comp_en_m)}</div>
          </div>"""
            else:
                opponent = esc(away_en_m) if is_home else esc(home_en_m)
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                match_rows += f"""
          <div class="match-row scheduled{extra_cls}">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result">—</div>
            <div class="match-broadcast">—</div>
            <div class="match-comp">{esc(comp_en_m)}</div>
          </div>"""

        total_matches = len(club_matches)
        extra_count = max(0, total_matches - 10)
        show_more_btn = ""
        if extra_count > 0:
            show_more_btn = f"""
      <button class="show-more-matches" onclick="toggleMoreMatches(this)" data-count="{extra_count}" data-expanded="false">
        Show more ({extra_count} remaining)
      </button>"""

        matches_html = f"""
    <section class="player-section">
      <h3>📅 Recent Matches</h3>
      <div class="matches-list">
        <div class="match-header">
          <div class="match-date">Date (JST)</div>
          <div class="match-venue">Venue</div>
          <div class="match-opponent">Opponent</div>
          <div class="match-result">Result</div>
          <div class="match-broadcast">Stream</div>
          <div class="match-comp">Competition</div>
        </div>
        {match_rows}
      </div>{show_more_btn}
    </section>"""
    else:
        matches_html = """
    <section class="player-section">
      <h3>📅 Recent Matches</h3>
      <p class="no-data">Match data is being fetched.</p>
    </section>"""

    # --- Goals section ---
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
            home_en_g = g.get("home_en", "")
            away_en_g = g.get("away_en", "")
            minute_raw = g.get("minute_raw", str(g.get("minute", "?")))
            goal_note = g.get("note", "")
            comp_en_g = g.get("competition_en", "")
            if goal_note:
                minute_raw += f" ({goal_note})"
            goal_rows += f"""
          <div class="goal-row">
            <div class="goal-date">{date_display}</div>
            <div class="goal-match">{esc(home_en_g)} vs {esc(away_en_g)}</div>
            <div class="goal-minute">{esc(minute_raw)}'</div>
            <div class="goal-comp">{esc(comp_en_g)}</div>
          </div>"""
        goals_html = f"""
    <section class="player-section">
      <h3>⚽ Recent Goals</h3>
      <div class="goals-list">
        {goal_rows}
      </div>
    </section>"""
    else:
        goals_html = """
    <section class="player-section">
      <h3>⚽ Recent Goals</h3>
      <p class="no-data">No goals recorded this season (or outside tracked range).</p>
    </section>"""

    # --- Player videos section ---
    player_videos_html = ""
    if player_videos:
        pv_cards = ""
        for v in player_videos:
            vid = v.get("video_id", "")
            if not vid:
                continue
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            vurl = v.get("url", f"https://www.youtube.com/watch?v={vid}")
            title_v = v.get("title", "")
            channel = v.get("channel", "")
            pub = v.get("published", "")
            pub_display = ""
            if pub:
                try:
                    from datetime import datetime
                    import re as _re
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', pub.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:10], "%Y-%m-%d")
                    pub_display = dt.strftime("%m/%d")
                except Exception:
                    pub_display = pub[:10]
            meta_parts = []
            if channel:
                meta_parts.append(esc(channel))
            if pub_display:
                meta_parts.append(pub_display)
            official_badge = ""
            if v.get("is_official"):
                official_badge = '<span class="video-official-badge">Official</span>'
            meta_str = " · ".join(meta_parts)
            pv_cards += f"""
        <a href="{esc(vurl)}" target="_blank" rel="noopener" class="video-card video-card-player">
          <div class="video-thumb-wrap">
            <img src="{esc(thumb)}" alt="" loading="lazy">
            {official_badge}
          </div>
          <div class="video-title">{esc(title_v)}</div>
          <div class="video-meta">{meta_str}</div>
        </a>"""
        if pv_cards:
            player_videos_html = f"""
    <section class="player-section">
      <h3>🎬 Season Goals & Highlights</h3>
      <div class="video-grid video-grid-player">
        {pv_cards}
      </div>
    </section>"""

    # --- Highlights section ---
    videos_html = ""
    if highlights:
        video_cards = ""
        for v in highlights:
            vid = v.get("video_id", "")
            if not vid:
                continue
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            url = v.get("url", f"https://www.youtube.com/watch?v={vid}")
            title_v = v.get("title", "")
            channel = v.get("channel", "")
            pub = v.get("published", "")
            pub_display = ""
            if pub:
                try:
                    from datetime import datetime
                    import re as _re
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', pub.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:10], "%Y-%m-%d")
                    pub_display = dt.strftime("%m/%d")
                except Exception:
                    pub_display = pub[:10]
            meta_parts = []
            if channel:
                meta_parts.append(esc(channel))
            if pub_display:
                meta_parts.append(pub_display)
            meta_str = " · ".join(meta_parts)
            video_cards += f"""
        <a href="{esc(url)}" target="_blank" rel="noopener" class="video-card">
          <img src="{esc(thumb)}" alt="" loading="lazy">
          <div class="video-title">{esc(title_v)}</div>
          <div class="video-meta">{meta_str}</div>
        </a>"""
        if video_cards:
            section_title = "Related Highlights" if player_videos else "📺 Match Highlights"
            videos_html = f"""
    <section class="player-section">
      <h3>{section_title}</h3>
      <div class="video-grid">
        {video_cards}
      </div>
    </section>"""

    # --- Profile section ---
    profile_info_html = ""
    if player_info:
        height_cm = player_info.get("height_cm")
        weight_kg = player_info.get("weight_kg")
        birth_date = player_info.get("birth_date")
        birth_place = player_info.get("birth_place", "")
        birth_place_ja = player_info.get("birth_place_ja", "")
        # Prefer English birthplace, fallback to translation
        display_place = birth_place if birth_place else translate_birthplace(birth_place_ja)
        foot = player_info.get("foot")
        wiki_url = player_info.get("wiki_url")

        height_str = f"{height_cm} cm" if height_cm else "—"
        weight_str = f"{weight_kg} kg" if weight_kg else "—"
        age_str = calc_age(birth_date)
        birth_str = f"{esc(birth_date)} (age {age_str})" if birth_date and age_str else esc(birth_date or "—")
        foot_str = foot_en(foot) if foot else "—"
        place_str = esc(display_place) if display_place else "—"

        wiki_link = ""
        if wiki_url:
            wiki_link = f' <a href="{esc(wiki_url)}" target="_blank" rel="noopener" style="font-size:11px;color:#888;">Wikipedia →</a>'

        profile_info_html = f"""
    <section class="player-section">
      <h3>👤 Profile{wiki_link}</h3>
      <table class="profile-table">
        <tr><td class="profile-label">Height / Weight</td><td class="profile-value">{height_str} / {weight_str}</td></tr>
        <tr><td class="profile-label">Date of Birth</td><td class="profile-value">{birth_str}</td></tr>
        <tr><td class="profile-label">Birthplace</td><td class="profile-value">{place_str}</td></tr>
        <tr><td class="profile-label">Foot</td><td class="profile-value">{foot_str}</td></tr>
      </table>
    </section>"""

    # --- Career section ---
    career_html = ""
    if player_info:
        career_en = player_info.get("career", [])
        career_ja = player_info.get("career_ja", [])
        # Prefer English career data; fallback to career_ja with translation
        if career_en:
            career = career_en
        elif career_ja:
            career = [{"years": c.get("years", ""), "club": translate_career_club(c.get("club", ""))}
                      for c in career_ja]
        else:
            career = []

        if career:
            def year_start(item):
                y = item.get("years", "")
                m = re.match(r"^(\d{4})", y.strip())
                return int(m.group(1)) if m else 0

            def is_current(item):
                y = item.get("years", "").strip()
                return y.endswith("–") or y.endswith("-") or y.endswith("—")

            sorted_past = sorted([c for c in career if not is_current(c)], key=year_start, reverse=True)
            current_clubs = [c for c in career if is_current(c)]
            ordered_career = current_clubs + sorted_past

            current_club_badge = ""
            if current_clubs:
                latest = current_clubs[-1]
                current_club_badge = f'<div class="career-current">🟢 Current club: <strong>{esc(latest.get("club", ""))}</strong> ({esc(latest.get("years", ""))})</div>'

            career_rows = ""
            for item in ordered_career:
                years = esc(item.get("years", ""))
                club = esc(item.get("club", ""))
                cur_class = " is-current" if is_current(item) else ""
                career_rows += f'<div class="career-row{cur_class}"><span class="career-years">{years}</span><span class="career-club">{club}</span></div>'
            career_html = f"""
    <section class="player-section">
      <h3>📋 Career</h3>
      {current_club_badge}
      <div class="career-list">
        {career_rows}
      </div>
    </section>"""

    # --- International career section ---
    national_team_html = ""
    if player_info:
        nt_history = player_info.get("national_team_history", [])
        if nt_history:
            nt_rows = ""
            for nt in nt_history:
                team_en = esc(nt.get("team", nt.get("team_ja", "")))
                years = esc(nt.get("years", ""))
                caps = nt.get("caps")
                goals = nt.get("goals")
                if caps is not None and goals is not None:
                    stats_str = f"{caps} caps / {goals} goals"
                elif caps is not None:
                    stats_str = f"{caps} caps"
                else:
                    stats_str = "—"
                nt_rows += f"""
            <div class="nt-row">
              <span class="nt-team">{team_en}</span>
              <span class="nt-years">{years}</span>
              <span class="nt-stats">{esc(stats_str)}</span>
            </div>"""
            national_team_html = f"""
    <section class="player-section">
      <h3>🇯🇵 International Career</h3>
      <div class="national-team-list">
        {nt_rows}
      </div>
    </section>"""

    # --- SNS section ---
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
      <h3>🔗 Social Media & Official Links</h3>
      <div class="sns-links">
        {"".join(sns_items)}
      </div>
    </section>"""

    # --- Related players section ---
    related_html = ""
    if related_players:
        cards_html = ""
        for rp in related_players:
            cards_html += f"""
          <a class="related-player-card" href="/en/players/{esc(rp['slug'])}/">
            <span class="related-player-flag">🇯🇵</span>
            <div class="related-player-info">
              <div class="related-player-name-ja">{esc(rp['name_en'])}</div>
              <div class="related-player-name-en">{esc(rp['name_ja'])}</div>
              <div class="related-player-pos">{esc(rp['position'])}</div>
            </div>
          </a>"""
        related_html = f"""
    <section class="player-section">
      <h3>🏟️ Other Japanese Players at This Club</h3>
      <div class="related-players-grid">
        {cards_html}
      </div>
    </section>"""

    note_html = ""
    if note:
        note_html = f'<div class="player-note">ℹ️ {esc(note)}</div>'

    club_slug = make_slug(club_en)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <link rel="alternate" hreflang="ja" href="{esc(ja_url)}">
  <link rel="alternate" hreflang="en" href="{esc(canonical)}">
  <link rel="alternate" hreflang="x-default" href="{esc(ja_url)}">
  <meta property="og:type" content="profile">
  <meta property="og:url" content="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:site_name" content="{esc(SITE_NAME)}">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "{GA4_ID}");
    gtag("event", "page_view", {{ language: "en" }});
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
    .standing-row {{ font-size: 14px; padding: 8px 0; }}
    .standing-pos {{ font-size: 24px; font-weight: 800; margin-right: 12px; }}
    .standing-detail {{ color: #444; }}
    .matches-list {{ font-size: 13px; }}
    .match-header, .match-row {{
      display: grid;
      grid-template-columns: 110px 30px 1fr 60px 110px 80px;
      gap: 6px;
      padding: 10px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: center;
    }}
    .match-header {{
      font-size: 11px;
      font-weight: 700;
      color: #666;
      background: #f8f9fa;
      align-items: center;
    }}
    .match-row:last-child {{ border-bottom: none; }}
    .match-result {{ font-weight: 700; text-align: center; }}
    .match-result.win {{ color: #1a7a3a; }}
    .match-result.lose {{ color: #c0392b; }}
    .match-result.draw {{ color: #666; }}
    .match-broadcast {{
      display: flex; flex-wrap: wrap; gap: 4px;
      align-items: center; justify-content: center;
    }}
    .match-date-day {{ display: block; font-size: 12px; }}
    .match-date-time {{ display: block; font-size: 11px; color: #555; }}
    .venue-badge {{
      display: inline-block; width: 24px; height: 24px;
      line-height: 24px; text-align: center; border-radius: 4px;
      font-weight: 700; font-size: 12px;
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
    .no-data {{ color: #888; font-size: 13px; padding: 8px 0; margin: 0; }}
    .stats-source {{ font-size: 11px; color: #999; margin-top: 6px; text-align: right; }}
    .player-note {{
      background: #fff8e1; border-left: 3px solid #d4af37;
      padding: 8px 12px; font-size: 12px; margin: 8px 0 0;
    }}
    .related-players-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px;
    }}
    .related-player-card {{
      display: flex; align-items: flex-start; gap: 8px;
      background: #f8f9fa; border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px; padding: 10px 12px;
      text-decoration: none; color: var(--c-text, #111); transition: background 0.15s;
    }}
    .related-player-card:hover {{ background: #eef0f7; }}
    .related-player-flag {{ font-size: 18px; line-height: 1; padding-top: 1px; flex-shrink: 0; }}
    .related-player-name-ja {{ font-size: 13px; font-weight: 700; margin-bottom: 2px; }}
    .related-player-name-en {{ font-size: 10px; color: #666; margin-bottom: 3px; }}
    .related-player-pos {{
      display: inline-block; padding: 1px 5px; font-size: 10px; font-weight: 700;
      background: #e6f0fa; color: #1565c0; border-radius: 3px;
    }}
    .back-link {{
      display: block; padding: 12px 16px; font-size: 13px;
      color: var(--c-text, #111); text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .lang-switch {{
      display: inline-block; margin-left: 12px; font-size: 12px;
      color: #666; text-decoration: none;
    }}
    .lang-switch:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
    .site-footer {{
      padding: 20px 16px; font-size: 12px; color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb); margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
    .profile-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .profile-table tr {{ border-bottom: 1px solid var(--c-border, #e5e7eb); }}
    .profile-table tr:last-child {{ border-bottom: none; }}
    .profile-label {{ width: 120px; padding: 7px 0; color: #666; font-size: 12px; vertical-align: top; }}
    .profile-value {{ padding: 7px 0; font-weight: 600; }}
    .career-list {{ font-size: 13px; }}
    .career-current {{ font-size: 12px; color: #1a7a3a; margin-bottom: 10px; }}
    .career-row {{
      display: flex; gap: 12px; padding: 6px 0;
      border-bottom: 1px solid var(--c-border, #e5e7eb); align-items: baseline;
    }}
    .career-row:last-child {{ border-bottom: none; }}
    .career-years {{ min-width: 90px; color: #888; font-size: 12px; flex-shrink: 0; }}
    .career-club {{ font-weight: 600; }}
    .sns-links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .sns-link {{
      display: inline-block; padding: 6px 14px; border-radius: 4px;
      font-size: 13px; font-weight: 600; text-decoration: none; transition: opacity 0.15s;
    }}
    .sns-link:hover {{ opacity: 0.8; }}
    .sns-twitter {{ background: #000; color: #fff; }}
    .sns-instagram {{ background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); color: #fff; }}
    .sns-official {{ background: #f0f1f5; color: #333; border: 1px solid #ccc; }}
    .match-row.hidden-extra {{ display: none; }}
    .match-row.hidden-extra.shown {{ display: grid; }}
    .show-more-matches {{
      display: block; width: 100%; margin-top: 10px; padding: 10px;
      background: #f0f4ff; border: 1px solid #aac6e8; border-radius: 4px;
      font-size: 13px; font-weight: 600; color: var(--c-accent, #0047ab);
      cursor: pointer; text-align: center; transition: background 0.15s;
    }}
    .show-more-matches:hover {{ background: #dce8ff; }}
    .video-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }}
    .video-card {{
      display: block; text-decoration: none; color: var(--c-text, #111);
      background: #f8f9fa; border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px; overflow: hidden; transition: background 0.15s;
    }}
    .video-card:hover {{ background: #eef0f7; }}
    .video-card img {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }}
    .video-title {{
      font-size: 11px; font-weight: 600; padding: 6px 8px 2px; line-height: 1.4;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }}
    .video-meta {{ font-size: 10px; color: #888; padding: 0 8px 8px; }}
    .video-grid-player {{ grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
    .video-card-player {{ border: 2px solid #aac6e8; }}
    .video-thumb-wrap {{ position: relative; }}
    .video-thumb-wrap img {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }}
    .video-official-badge {{
      position: absolute; top: 6px; left: 6px;
      background: var(--c-accent, #0047ab); color: #fff;
      font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px;
    }}
    .national-team-list {{ font-size: 13px; }}
    .nt-row {{
      display: flex; gap: 12px; padding: 7px 0;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: baseline; flex-wrap: wrap;
    }}
    .nt-row:last-child {{ border-bottom: none; }}
    .nt-team {{ font-weight: 700; min-width: 140px; flex-shrink: 0; }}
    .nt-years {{ color: #888; font-size: 12px; min-width: 70px; flex-shrink: 0; }}
    .nt-stats {{ color: #444; font-size: 12px; }}
    @media (max-width: 600px) {{
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .match-header, .match-row {{
        grid-template-columns: 80px 28px 1fr 45px;
        font-size: 12px;
      }}
      .match-broadcast, .match-comp {{ display: none; }}
      .goal-row {{ grid-template-columns: 45px 1fr 60px; }}
      .goal-comp {{ display: none; }}
      .video-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
  <script type="application/ld+json">
{schema_ld}
  </script>
  <script type="application/ld+json">
{schema_breadcrumb_ld}
  </script>
  <style>
    .breadcrumb {{
      font-size: 12px;
      color: #888;
      padding: 8px 16px;
      background: #f8f9fa;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .breadcrumb a {{ color: #555; text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
  </style>
</head>
<body>

<nav class="breadcrumb" aria-label="Breadcrumb">
  <a href="/en/">Home</a> ›
  <a href="/en/players/">Players</a> ›
  <span aria-current="page">{esc(name_en)}</span>
</nav>

<div class="player-hero">
  <div class="name-block">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
      <h2 style="margin:0;">🇯🇵 {esc(name_en)}</h2>
      <button class="fav-btn" data-slug="{slug}" onclick="fjFavorites.toggle('{slug}'); refreshFavBtn(this);" title="Add to favorites" aria-label="Favorite"><span class="fav-star">☆</span></button>
    </div>
    <p class="name-en">{esc(name_ja)}</p>
    <div class="player-meta">
      <span class="player-meta-tag">⚽ {esc(position_en)}</span>
      <span class="player-meta-tag">🏟️ {esc(club_en)}</span>
      <span class="player-meta-tag">🏆 {esc(league_en)}</span>
    </div>
    {note_html}
    <p style="margin:8px 0 0; font-size:12px; color:#888;">
      🇯🇵 <a href="{esc(ja_url)}" class="lang-switch">日本語ページ</a>
    </p>
  </div>
</div>

<div style="max-width: 860px; margin: 0 auto;">

  {profile_info_html}

  {stats_html}

  {standing_html}

  {matches_html}

  {player_videos_html}

  {videos_html}

  {goals_html}

  {career_html}

  {national_team_html}

  {sns_html}

  {related_html}

  <div class="player-section">
    <h3>🔗 Related Links</h3>
    <p style="font-size:13px; margin: 0;">
      <a href="/en/clubs/{make_slug(club_en)}/" style="color: var(--c-accent, #0047ab);">
        {esc(club_en)} Club Page →
      </a>
    </p>
  </div>

  <footer class="site-footer">
    <p>Data: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football-Data.org</a></p>
    <p class="footer-links">
      <a href="/en/">football-jp (English)</a> |
      <a href="/en/players/">Players</a> |
      <a href="/en/clubs/">Clubs</a> |
      <a href="/privacy.html">Privacy Policy</a> |
      <a href="{esc(ja_url)}">🇯🇵 Japanese</a>
    </p>
  </footer>
</div>

<script>
function toggleMoreMatches(btn) {{
  var list = btn.previousElementSibling;
  list.querySelectorAll('.hidden-extra').forEach(function(r) {{
    r.classList.toggle('shown');
  }});
  if (btn.dataset.expanded === 'true') {{
    btn.textContent = 'Show more (' + btn.dataset.count + ' remaining)';
    btn.dataset.expanded = 'false';
  }} else {{
    btn.textContent = 'Close';
    btn.dataset.expanded = 'true';
  }}
}}
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
<script src="/favorites.js" defer></script>

</body>
</html>
"""


# ============================
# メイン処理
# ============================
def main():
    print("Loading data...")
    players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info, player_videos = load_data()
    print(f"  Players: {len(players)}")
    print(f"  Matches: {len(matches)}")

    slug_map = make_unique_slugs(players)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []

    for i, player in enumerate(players):
        slug = slug_map[i]
        name_en = player.get("name_en", "")
        name_ja = player.get("name_ja", "")

        if not name_en:
            print(f"  [SKIP] No name_en for player {i}: {name_ja}")
            continue

        # Gather data
        wiki_stats = get_player_wiki_stats(player, player_stats)
        scorer_stats = get_player_scorer_stats(player, scorers_comps)
        goal_events = get_player_goals(player, events, matches_dict)
        club_matches = get_club_matches(player, matches)
        standing = get_club_standing(player, standings_comps)
        related = get_related_players(player, players, slug_map)
        highlights = get_club_highlights(player, matches)
        pinfo = player_info.get(name_en, {})
        pvideos_raw = player_videos.get(name_en, {})
        if isinstance(pvideos_raw, dict):
            pvideos = pvideos_raw.get("videos", [])
        elif isinstance(pvideos_raw, list):
            pvideos = pvideos_raw
        else:
            pvideos = []

        html = build_player_page_en(
            player, slug, scorer_stats, goal_events, club_matches, standing,
            wiki_stats=wiki_stats, services=services,
            related_players=related,
            player_info=pinfo if pinfo else None,
            highlights=highlights,
            player_videos=pvideos if pvideos else None,
        )

        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((name_en, slug, size))
        print(f"  ✅ {name_en} ({name_ja}) → /en/players/{slug}/ ({size:,} bytes)")

    print(f"\nTotal: {len(generated)} English player pages generated")
    return len(generated)


if __name__ == "__main__":
    main()
