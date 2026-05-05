#!/usr/bin/env python3
"""
generate_club_pages_en.py
英語版クラブページを自動生成するスクリプト。
出力先: en/clubs/{slug}/index.html
使い方: python3 scripts/generate_club_pages_en.py
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
STANDINGS_JSON = REPO_ROOT / "data" / "standings.json"
BROADCASTERS_JSON = REPO_ROOT / "data" / "broadcasters.json"
CLUB_CRESTS_JSON = REPO_ROOT / "data" / "club_crests.json"
NEWS_JSON = REPO_ROOT / "data" / "news.json"
CLUB_INFO_JSON = REPO_ROOT / "data" / "club_info.json"
STANDINGS_HISTORY_JSON = REPO_ROOT / "data" / "standings_history.json"
OUTPUT_DIR = REPO_ROOT / "en" / "clubs"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"

sys.path.insert(0, str(Path(__file__).parent))
from translation_dict import (
    translate_league, translate_position,
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


def load_local_crests() -> dict:
    if not CLUB_CRESTS_JSON.exists():
        return {}
    with open(CLUB_CRESTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_data():
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    with open(MATCHES_JSON, encoding="utf-8") as f:
        matches_raw = json.load(f)
    matches = matches_raw.get("matches", [])

    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_raw = json.load(f)
    standings_comps = standings_raw.get("competitions", {})

    services = load_services()
    local_crests = load_local_crests()

    news_items = []
    if NEWS_JSON.exists():
        with open(NEWS_JSON, encoding="utf-8") as f:
            news_raw = json.load(f)
        news_items = news_raw.get("items", [])

    club_info_data = {}
    if CLUB_INFO_JSON.exists():
        with open(CLUB_INFO_JSON, encoding="utf-8") as f:
            club_info_data = json.load(f)

    standings_history = {}
    if STANDINGS_HISTORY_JSON.exists():
        try:
            with open(STANDINGS_HISTORY_JSON, encoding="utf-8") as f:
                sh_raw = json.load(f)
            standings_history = sh_raw.get("competitions", {})
        except Exception:
            pass

    return players, matches, standings_comps, services, local_crests, news_items, club_info_data, standings_history


def build_clubs(players: list) -> dict:
    clubs = {}
    for p in players:
        club_en = p.get("club_en", "")
        if not club_en:
            continue
        if club_en not in clubs:
            clubs[club_en] = {
                "club_ja": p.get("club_ja", club_en),
                "club_en": club_en,
                "club_id": p.get("club_id"),
                "league_ja": p.get("league_ja", ""),
                "league_en": translate_league(p.get("league_ja", "")),
                "competition_id": p.get("competition_id"),
                "players": [],
            }
        clubs[club_en]["players"].append({
            "name_ja": p.get("name_ja", ""),
            "name_en": p.get("name_en", ""),
            "position": p.get("position", ""),
            "position_en": translate_position(p.get("position", "")),
            "note": p.get("note", ""),
        })
    return clubs


def get_player_slugs(players: list) -> dict:
    slug_map = {}
    used = {}
    for p in players:
        name_en = p.get("name_en", "")
        base = make_slug(name_en)
        if base not in used:
            used[base] = 1
            slug_map[name_en] = base
        else:
            if name_en not in slug_map:
                used[base] += 1
                slug_map[name_en] = f"{base}-{used[base]}"
    return slug_map


def get_club_standing(club_info: dict, standings_comps: dict) -> dict:
    comp_id = str(club_info.get("competition_id") or "")
    club_id = club_info.get("club_id")
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


def get_club_recent_matches(club_info: dict, matches: list) -> list:
    club_id = club_info.get("club_id")
    if not club_id:
        return []
    club_matches = [m for m in matches if m.get("home_id") == club_id or m.get("away_id") == club_id]
    club_matches.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return club_matches


def get_club_crest(club_info: dict, matches: list, local_crests: dict = None) -> str:
    club_id = club_info.get("club_id")
    if club_id:
        for m in matches:
            if m.get("home_id") == club_id and m.get("home_crest"):
                return m["home_crest"]
            if m.get("away_id") == club_id and m.get("away_crest"):
                return m["away_crest"]
    if local_crests is not None:
        club_en = club_info.get("club_en", "")
        slug = make_slug(club_en)
        local_url = local_crests.get(slug, "")
        if local_url:
            return local_url
    return ""


def get_club_highlights(club_info: dict, matches: list) -> list:
    club_id = club_info.get("club_id")
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


def get_club_news(club_info: dict, news_items: list) -> list:
    club_en = club_info.get("club_en", "")
    matched = []
    for item in news_items:
        title = item.get("title", "")
        desc = item.get("description", "")
        text = title + " " + desc
        if club_en and club_en.lower() in text.lower():
            matched.append(item)
    matched.sort(key=lambda x: x.get("published", ""), reverse=True)
    seen = set()
    unique = []
    for item in matched:
        key = item.get("link", item.get("title", ""))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:5]


def get_opponent_records(club_info: dict, matches: list) -> list:
    club_id = club_info.get("club_id")
    if not club_id:
        return []
    records = {}
    for m in matches:
        home_id = m.get("home_id")
        away_id = m.get("away_id")
        status = m.get("status", "")
        score = m.get("score", {})
        if status != "FINISHED" or not score:
            continue
        home_score = score.get("home")
        away_score = score.get("away")
        if home_score is None or away_score is None:
            continue
        if home_id == club_id:
            opponent = m.get("away_en", m.get("away_ja", ""))
            gf, ga = home_score, away_score
        elif away_id == club_id:
            opponent = m.get("home_en", m.get("home_ja", ""))
            gf, ga = away_score, home_score
        else:
            continue
        if not opponent:
            continue
        if opponent not in records:
            records[opponent] = {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
        r = records[opponent]
        if gf > ga:
            r["w"] += 1
        elif gf < ga:
            r["l"] += 1
        else:
            r["d"] += 1
        r["gf"] += gf
        r["ga"] += ga
    sorted_records = sorted(
        records.items(),
        key=lambda x: x[1]["w"] + x[1]["d"] + x[1]["l"],
        reverse=True
    )
    return sorted_records[:10]


def get_club_positions_history(club_info: dict, standings_history: dict):
    comp_id = str(club_info.get("competition_id") or "")
    club_en = club_info.get("club_en", "")
    if not comp_id or comp_id not in standings_history:
        return None
    comp_data = standings_history[comp_id]
    positions_map = comp_data.get("positions", {})
    matched_positions = None
    matched_club = None
    for name, vals in positions_map.items():
        if name == club_en:
            matched_positions = vals
            matched_club = name
            break
    if not matched_positions:
        club_en_lower = club_en.lower()
        for name, vals in positions_map.items():
            name_lower = name.lower()
            if (club_en_lower in name_lower or name_lower in club_en_lower) and len(name) >= 4:
                matched_positions = vals
                matched_club = name
                break
    if not matched_positions:
        return None
    league_ja = comp_data.get("name_ja", "")
    return {
        "positions": matched_positions,
        "matched_club": matched_club,
        "league_name_en": translate_league(league_ja),
        "current_matchday": comp_data.get("current_matchday", 0),
        "total_matchdays": comp_data.get("matchdays", 38),
    }


# ============================
# HTML生成
# ============================
def build_club_page_en(club_info: dict, slug: str, standing: dict,
                       recent_matches: list, crest_url: str,
                       player_slug_map: dict, services: dict = None,
                       club_news: list = None, opponent_records: list = None,
                       club_info_extra: dict = None,
                       highlights: list = None,
                       standings_history_data: dict = None) -> str:
    club_ja = club_info.get("club_ja", "")
    club_en = club_info.get("club_en", "")
    league_ja = club_info.get("league_ja", "")
    league_en = club_info.get("league_en", translate_league(league_ja))
    players = club_info.get("players", [])

    title = f"{esc(club_en)} - Japanese Players, Fixtures & Standings | football-jp"
    desc = (f"{esc(club_en)} ({esc(league_en)}) Japanese players, fixtures, and league standings "
            f"in Japan Standard Time.")
    canonical = f"{SITE_URL}/en/clubs/{slug}/"
    ja_url = f"{SITE_URL}/clubs/{slug}/"

    schema_team = {
        "@context": "https://schema.org",
        "@type": "SportsTeam",
        "name": club_en,
        "alternateName": club_ja,
        "sport": "Football",
        "url": canonical,
    }
    if league_en:
        schema_team["memberOf"] = {"@type": "SportsOrganization", "name": league_en}
    if crest_url:
        schema_team["image"] = crest_url
    schema_ld = json.dumps(schema_team, ensure_ascii=False, indent=2)

    # --- Crest ---
    crest_html = ""
    if crest_url:
        crest_html = f'<img src="{esc(crest_url)}" alt="{esc(club_en)} crest" class="club-crest" width="64" height="64" loading="lazy">'
    else:
        crest_html = '<span style="font-size:48px;">🏟️</span>'

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
        gf = standing.get("goals_for", "—")
        ga = standing.get("goals_against", "—")
        league_disp = standing.get("league_en", league_en)
        standing_html = f"""
    <section class="club-section">
      <h3>🏆 {esc(league_disp)} Current Standings</h3>
      <div class="standing-row">
        <span class="standing-pos">{esc(str(pos))}</span>
        <span class="standing-detail">
          (of {esc(str(total))})&nbsp;&nbsp;{esc(str(played))} played&nbsp;
          {esc(str(won))}W {esc(str(draw))}D {esc(str(lost))}L&nbsp;
          {esc(str(gf))}-{esc(str(ga))} GD&nbsp;
          <strong>{esc(str(pts))} pts</strong>
        </span>
      </div>
    </section>"""
    else:
        standing_html = f"""
    <section class="club-section">
      <h3>🏆 {esc(league_en)} Standings</h3>
      <p class="no-data">Standings data not available for this league.</p>
    </section>"""

    # --- Japanese players section ---
    player_cards = ""
    for pl in players:
        name_en_pl = pl.get("name_en", "")
        name_ja_pl = pl.get("name_ja", "")
        pl_slug = player_slug_map.get(name_en_pl, make_slug(name_en_pl))
        pos_en = pl.get("position_en", translate_position(pl.get("position", "")))
        note_pl = pl.get("note", "")
        note_html = f'<div class="player-note-small">{esc(note_pl)}</div>' if note_pl else ""
        player_cards += f"""
        <a class="player-link-card" href="/en/players/{esc(pl_slug)}/">
          <div class="player-name-ja">{esc(name_en_pl)}</div>
          <div class="player-name-en">{esc(name_ja_pl)}</div>
          <div class="player-pos">{esc(pos_en)}</div>
          {note_html}
        </a>"""

    players_html = f"""
    <section class="club-section">
      <h3>🇯🇵 Japanese Players ({len(players)})</h3>
      <div class="players-grid">
        {player_cards}
      </div>
    </section>"""

    # --- Matches section ---
    matches_html = ""
    if recent_matches:
        match_rows = ""
        for idx, m in enumerate(recent_matches):
            kickoff = m.get("kickoff_jst", "")
            status = m.get("status", "")
            home_en_m = m.get("home_en", m.get("home_ja", ""))
            away_en_m = m.get("away_en", m.get("away_ja", ""))
            score = m.get("score", {})
            comp_ja_m = m.get("competition_ja", "")
            comp_en_m = LEAGUE_JA_TO_EN.get(comp_ja_m, comp_ja_m)
            home_id = m.get("home_id")
            club_id = club_info.get("club_id")
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

        total_matches = len(recent_matches)
        extra_count = max(0, total_matches - 10)
        show_more_btn = ""
        if extra_count > 0:
            show_more_btn = f"""
      <button class="show-more-matches" onclick="toggleMoreMatches(this)" data-count="{extra_count}" data-expanded="false">
        Show more ({extra_count} remaining)
      </button>"""

        matches_html = f"""
    <section class="club-section">
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
    <section class="club-section">
      <h3>📅 Recent Matches</h3>
      <p class="no-data">Match data is being fetched.</p>
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
            videos_html = f"""
    <section class="club-section">
      <h3>📺 Match Highlights</h3>
      <div class="video-grid">
        {video_cards}
      </div>
    </section>"""

    # --- Club info section ---
    club_basic_html = ""
    if club_info_extra:
        rows = ""
        if club_info_extra.get("founded"):
            rows += f'<tr><th>Founded</th><td>{esc(club_info_extra["founded"])}</td></tr>'
        if club_info_extra.get("city") or club_info_extra.get("country"):
            city = club_info_extra.get("city", "")
            country = club_info_extra.get("country", "")
            loc = ", ".join(filter(None, [city, country]))
            rows += f'<tr><th>Location</th><td>{esc(loc)}</td></tr>'
        if club_info_extra.get("stadium"):
            rows += f'<tr><th>Stadium</th><td>{esc(club_info_extra["stadium"])}</td></tr>'
        if club_info_extra.get("capacity"):
            rows += f'<tr><th>Capacity</th><td>{esc(club_info_extra["capacity"])}</td></tr>'
        if club_info_extra.get("manager"):
            rows += f'<tr><th>Manager</th><td>{esc(club_info_extra["manager"])}</td></tr>'
        if club_info_extra.get("chairman"):
            rows += f'<tr><th>Chairman</th><td>{esc(club_info_extra["chairman"])}</td></tr>'
        if club_info_extra.get("website"):
            rows += f'<tr><th>Website</th><td><a href="{esc(club_info_extra["website"])}" target="_blank" rel="noopener">{esc(club_info_extra["website"])}</a></td></tr>'
        if rows:
            club_basic_html = f"""
    <section class="club-section">
      <h3>ℹ️ Club Info</h3>
      <table class="club-info-table">
        {rows}
      </table>
    </section>"""

    # --- News section ---
    news_html = ""
    if club_news:
        news_rows = ""
        for item in club_news:
            title_n = item.get("title", "")
            link_n = item.get("link", "#")
            pub = item.get("published", "")
            source = item.get("source", "")
            pub_display = ""
            if pub:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(pub)
                    pub_display = dt.strftime("%m/%d")
                except Exception:
                    pub_display = pub[:10]
            news_rows += f"""
          <div class="news-row">
            <div class="news-date">{esc(pub_display)}</div>
            <div class="news-title"><a href="{esc(link_n)}" target="_blank" rel="noopener">{esc(title_n)}</a></div>
            <div class="news-source">{esc(source)}</div>
          </div>"""
        news_html = f"""
    <section class="club-section">
      <h3>📰 Latest News</h3>
      <div class="news-list">
        {news_rows}
      </div>
    </section>"""

    # --- Standings chart section ---
    standings_chart_html = ""
    if standings_history_data:
        pos_list = standings_history_data.get("positions", [])
        current_md = standings_history_data.get("current_matchday", 0)
        league_name_en = standings_history_data.get("league_name_en", league_en)
        valid_pos = [p for p in pos_list[:current_md] if p is not None]
        if valid_pos:
            labels = list(range(1, len(valid_pos) + 1))
            labels_json = json.dumps(labels)
            data_json = json.dumps(valid_pos)
            max_pos = max(valid_pos) + 1
            y_max = max(max_pos, 21)
            canvas_id = f"standings-chart-{slug}"
            standings_chart_html = f"""
    <section class="club-section">
      <h3>📈 League Position History (2025-26)</h3>
      <p class="chart-subtitle">Matchday 1–{len(valid_pos)} ({esc(league_name_en)})</p>
      <div class="standings-chart-container">
        <canvas id="{canvas_id}" width="600" height="300"></canvas>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
      <script>
      (function() {{
        var ctx = document.getElementById('{canvas_id}');
        if (!ctx) return;
        new Chart(ctx, {{
          type: 'line',
          data: {{
            labels: {labels_json},
            datasets: [{{
              label: '{esc(club_en)}',
              data: {data_json},
              borderColor: '#0047ab',
              backgroundColor: 'rgba(0,71,171,0.08)',
              borderWidth: 2,
              pointRadius: 3,
              pointHoverRadius: 6,
              pointBackgroundColor: '#0047ab',
              tension: 0.1,
              fill: false,
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: true,
            plugins: {{
              legend: {{ display: false }},
              tooltip: {{
                callbacks: {{
                  title: function(items) {{ return 'MD ' + items[0].label; }},
                  label: function(item) {{ return item.dataset.label + ': ' + item.parsed.y + (item.parsed.y === 1 ? 'st' : item.parsed.y === 2 ? 'nd' : item.parsed.y === 3 ? 'rd' : 'th'); }}
                }}
              }}
            }},
            scales: {{
              x: {{
                title: {{ display: true, text: 'Matchday', font: {{ size: 11 }} }},
                ticks: {{ font: {{ size: 10 }} }}
              }},
              y: {{
                reverse: true,
                min: 1,
                max: {y_max},
                ticks: {{
                  stepSize: 1,
                  font: {{ size: 10 }},
                  callback: function(v) {{ return v + (v === 1 ? 'st' : v === 2 ? 'nd' : v === 3 ? 'rd' : 'th'); }}
                }},
                title: {{ display: true, text: 'Position', font: {{ size: 11 }} }},
                grid: {{ color: 'rgba(0,0,0,0.06)' }}
              }}
            }}
          }}
        }});
      }})();
      </script>
    </section>"""

    # --- Opponent records section ---
    opponent_html = ""
    if opponent_records:
        opp_rows = ""
        for opp_name, rec in opponent_records:
            total = rec["w"] + rec["d"] + rec["l"]
            gf = rec["gf"]
            ga = rec["ga"]
            wdl = f'{rec["w"]}W {rec["d"]}D {rec["l"]}L'
            goals = f'{gf} GF - {ga} GA'
            opp_rows += f"""
          <div class="opp-row">
            <div class="opp-name">{esc(opp_name)}</div>
            <div class="opp-total">{esc(str(total))} played</div>
            <div class="opp-wdl">{esc(wdl)}</div>
            <div class="opp-goals">{esc(goals)}</div>
          </div>"""
        opponent_html = f"""
    <section class="club-section">
      <h3>📊 Records vs Opponents (Top {len(opponent_records)})</h3>
      <div class="opponent-records">
        <div class="opp-header">
          <div class="opp-name">Opponent</div>
          <div class="opp-total">Played</div>
          <div class="opp-wdl">Record</div>
          <div class="opp-goals">Goals</div>
        </div>
        {opp_rows}
      </div>
    </section>"""

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
  <meta property="og:type" content="website">
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
    .club-hero {{
      background: #ffffff; border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 18px; margin-bottom: 18px;
      display: flex; align-items: center; gap: 16px;
    }}
    .club-crest {{ width: 64px; height: 64px; object-fit: contain; flex-shrink: 0; }}
    .club-name-block h2 {{ margin: 0 0 4px; font-size: 24px; font-weight: 800; }}
    .club-name-en {{ font-size: 13px; color: #666; margin: 0 0 4px; }}
    .club-league-tag {{
      display: inline-block; padding: 2px 8px; font-size: 11px;
      background: #f0f1f5; border-radius: 3px;
    }}
    .lang-switch {{
      display: inline-block; margin-left: 8px; font-size: 12px;
      color: #666; text-decoration: none;
    }}
    .lang-switch:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
    .club-section {{
      background: #fff; padding: 18px 16px; margin-bottom: 1px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .club-section h3 {{
      margin: 0 0 14px; font-size: 14px; font-weight: 700;
      letter-spacing: 0.06em; padding-left: 10px;
      border-left: 4px solid var(--c-accent, #0047ab); color: var(--c-text, #111);
    }}
    .standing-row {{ font-size: 14px; padding: 8px 0; }}
    .standing-pos {{ font-size: 24px; font-weight: 800; margin-right: 12px; }}
    .standing-detail {{ color: #444; }}
    .players-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px;
    }}
    .player-link-card {{
      display: block; background: #f8f9fa; border: 1px solid var(--c-border, #e5e7eb);
      padding: 12px 14px; text-decoration: none; color: var(--c-text, #111);
      border-radius: 4px; transition: background 0.15s;
    }}
    .player-link-card:hover {{ background: #eef0f7; }}
    .player-name-ja {{ font-size: 15px; font-weight: 700; margin-bottom: 2px; }}
    .player-name-en {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .player-pos {{
      display: inline-block; padding: 1px 6px; font-size: 11px; font-weight: 700;
      background: #e6f0fa; color: #1565c0; border-radius: 3px;
    }}
    .player-note-small {{ font-size: 11px; color: #888; margin-top: 4px; }}
    .matches-list {{ font-size: 13px; }}
    .match-header, .match-row {{
      display: grid;
      grid-template-columns: 110px 30px 1fr 60px 110px 80px;
      gap: 6px; padding: 10px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb); align-items: center;
    }}
    .match-header {{
      font-size: 11px; font-weight: 700; color: #666; background: #f8f9fa;
    }}
    .match-row:last-child {{ border-bottom: none; }}
    .match-result {{ font-weight: 700; text-align: center; }}
    .match-result.win {{ color: #1a7a3a; }}
    .match-result.lose {{ color: #c0392b; }}
    .match-result.draw {{ color: #666; }}
    .match-broadcast {{ display: flex; flex-wrap: wrap; gap: 4px; align-items: center; justify-content: center; }}
    .match-date-day {{ display: block; font-size: 12px; }}
    .match-date-time {{ display: block; font-size: 11px; color: #555; }}
    .venue-badge {{
      display: inline-block; width: 24px; height: 24px; line-height: 24px;
      text-align: center; border-radius: 4px; font-weight: 700; font-size: 12px;
    }}
    .venue-away {{ background: #fee; color: #c9302c; border: 1px solid #f5b7b1; }}
    .venue-home {{ background: #e7f0ff; color: #1e6cba; border: 1px solid #aac6e8; }}
    .match-comp {{ font-size: 11px; color: #666; }}
    .no-data {{ color: #888; font-size: 13px; padding: 8px 0; margin: 0; }}
    .chart-subtitle {{ font-size: 12px; color: #888; margin: -8px 0 10px; }}
    .standings-chart-container {{ position: relative; width: 100%; max-width: 640px; }}
    .club-info-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .club-info-table th {{
      width: 120px; text-align: left; padding: 7px 8px; color: #555;
      font-weight: 600; border-bottom: 1px solid var(--c-border, #e5e7eb); background: #f8f9fa;
    }}
    .club-info-table td {{ padding: 7px 8px; border-bottom: 1px solid var(--c-border, #e5e7eb); }}
    .club-info-table tr:last-child th, .club-info-table tr:last-child td {{ border-bottom: none; }}
    .club-info-table a {{ color: var(--c-accent, #0047ab); word-break: break-all; }}
    .news-list {{ font-size: 13px; }}
    .news-row {{
      display: grid; grid-template-columns: 45px 1fr 70px; gap: 8px;
      padding: 8px 4px; border-bottom: 1px solid var(--c-border, #e5e7eb); align-items: start;
    }}
    .news-row:last-child {{ border-bottom: none; }}
    .news-date {{ font-size: 11px; color: #888; padding-top: 2px; }}
    .news-title a {{ color: var(--c-text, #111); text-decoration: none; }}
    .news-title a:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
    .news-source {{ font-size: 11px; color: #888; text-align: right; }}
    .opponent-records {{ font-size: 13px; }}
    .opp-header, .opp-row {{
      display: grid; grid-template-columns: 1fr 80px 110px 100px; gap: 6px;
      padding: 8px 4px; border-bottom: 1px solid var(--c-border, #e5e7eb); align-items: center;
    }}
    .opp-header {{ font-size: 11px; font-weight: 700; color: #666; background: #f8f9fa; }}
    .opp-row:last-child {{ border-bottom: none; }}
    .opp-total {{ text-align: center; color: #555; }}
    .opp-wdl {{ font-weight: 600; }}
    .opp-goals {{ color: #555; }}
    .back-link {{
      display: block; padding: 12px 16px; font-size: 13px;
      color: var(--c-text, #111); text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .site-footer {{
      padding: 20px 16px; font-size: 12px; color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb); margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
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
    @media (max-width: 600px) {{
      .match-header, .match-row {{ grid-template-columns: 80px 28px 1fr 45px; font-size: 12px; }}
      .match-broadcast, .match-comp {{ display: none; }}
      .video-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
  <script type="application/ld+json">
{schema_ld}
  </script>
</head>
<body>

<a class="back-link" href="/en/">← football-jp (English)</a>

<div class="club-hero">
  <div class="crest-wrapper">
    {crest_html}
  </div>
  <div class="club-name-block">
    <h2>{esc(club_en)}</h2>
    <p class="club-name-en">{esc(club_ja)}</p>
    <span class="club-league-tag">🏆 {esc(league_en)}</span>
    <br>
    <a href="{esc(ja_url)}" class="lang-switch">🇯🇵 日本語ページ</a>
  </div>
</div>

<div style="max-width: 860px; margin: 0 auto;">

  {club_basic_html}

  {standing_html}

  {standings_chart_html}

  {players_html}

  {matches_html}

  {videos_html}

  {opponent_html}

  {news_html}

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
</script>

</body>
</html>
"""


# ============================
# メイン処理
# ============================
def main():
    print("Loading data...")
    players, matches, standings_comps, services, local_crests, news_items, club_info_data, standings_history = load_data()
    print(f"  Players: {len(players)}")
    print(f"  Matches: {len(matches)}")
    print(f"  Local crests: {len(local_crests)}")

    clubs = build_clubs(players)
    print(f"  Clubs: {len(clubs)}")

    player_slug_map = get_player_slugs(players)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []

    for club_en, club_info in clubs.items():
        slug = make_slug(club_en)

        standing = get_club_standing(club_info, standings_comps)
        recent_matches = get_club_recent_matches(club_info, matches)
        crest_url = get_club_crest(club_info, matches, local_crests)
        club_news = get_club_news(club_info, news_items)
        opponent_records = get_opponent_records(club_info, matches)
        extra_info = club_info_data.get(club_en, {})
        highlights = get_club_highlights(club_info, matches)
        sh_data = get_club_positions_history(club_info, standings_history)

        html = build_club_page_en(
            club_info, slug, standing, recent_matches, crest_url, player_slug_map,
            services=services, club_news=club_news,
            opponent_records=opponent_records,
            club_info_extra=extra_info if extra_info else None,
            highlights=highlights,
            standings_history_data=sh_data,
        )

        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((club_en, slug, size))
        print(f"  ✅ {club_en} → /en/clubs/{slug}/ ({size:,} bytes)")

    print(f"\nTotal: {len(generated)} English club pages generated")
    return len(generated)


if __name__ == "__main__":
    main()
