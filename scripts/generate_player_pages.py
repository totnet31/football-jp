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
OUTPUT_DIR = REPO_ROOT / "players"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"


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

    return players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats


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
def build_player_page(player: dict, slug: str, scorer_stats: dict,
                      goal_events: list, club_matches: list, standing: dict,
                      wiki_stats: dict = None) -> str:
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

            # 日時表示
            date_display = ""
            if kickoff:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(kickoff)
                    date_display = dt.strftime("%m/%d(%a) %H:%M JST")
                except Exception:
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
                home_away = "H" if is_home else "A"
                match_rows += f"""
          <div class="match-row">
            <div class="match-date">{esc(date_display)}</div>
            <div class="match-opponent"><span class="home-away">{home_away}</span> vs {opponent}</div>
            <div class="match-result {result_class}">{esc(score_display)}</div>
            <div class="match-broadcast">—</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""
            else:
                if is_home:
                    opponent = esc(away_ja)
                else:
                    opponent = esc(home_ja)
                home_away = "H" if is_home else "A"
                broadcasters = m.get("broadcasters", [])
                bc_str = ""
                if broadcasters:
                    bc_names = [b.get("name", "") for b in broadcasters[:2] if b.get("name")]
                    bc_str = " / ".join(bc_names)
                match_rows += f"""
          <div class="match-row scheduled">
            <div class="match-date">{esc(date_display)}</div>
            <div class="match-opponent"><span class="home-away">{home_away}</span> vs {opponent}</div>
            <div class="match-result">—</div>
            <div class="match-broadcast">{esc(bc_str) if bc_str else "—"}</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""

        matches_html = f"""
    <section class="player-section">
      <h3>📅 直近の試合（最大10試合）</h3>
      <div class="matches-list">
        <div class="match-header">
          <div class="match-date">日時（JST）</div>
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
            <div class="goal-date">{esc(date_display)}</div>
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
      grid-template-columns: 150px 1fr 70px 80px 100px;
      gap: 8px;
      padding: 8px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: center;
    }}
    .match-header {{
      font-size: 11px;
      font-weight: 700;
      color: #666;
      background: #f8f9fa;
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
      font-size: 11px;
      color: #555;
      text-align: center;
    }}
    .home-away {{
      display: inline-block;
      padding: 1px 5px;
      font-size: 10px;
      font-weight: 700;
      background: #f0f0f0;
      border-radius: 2px;
      margin-right: 4px;
    }}
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
    @media (max-width: 600px) {{
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .match-header, .match-row {{
        grid-template-columns: 110px 1fr 55px 55px;
        font-size: 12px;
      }}
      .match-comp {{ display: none; }}
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

  {stats_html}

  {standing_html}

  {matches_html}

  {goals_html}

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
    <p><a href="/">football-jp トップへ</a> ／ <a href="/privacy.html">プライバシーポリシー</a></p>
  </footer>
</div>

</body>
</html>
"""


# ============================
# メイン処理
# ============================
def main():
    print(f"データ読み込み中...")
    players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats = load_data()
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

        # HTMLページ生成
        html = build_player_page(player, slug, scorer_stats, goal_events, club_matches, standing,
                                 wiki_stats=wiki_stats)

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

    print("\n完了！")
    return slug_map


if __name__ == "__main__":
    main()
