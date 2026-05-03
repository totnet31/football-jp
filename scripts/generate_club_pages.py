#!/usr/bin/env python3
"""
generate_club_pages.py
日本人選手が所属するクラブの別ページを自動生成するスクリプト。
出力先: clubs/{slug}/index.html
使い方: python3 scripts/generate_club_pages.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
MATCHES_JSON = REPO_ROOT / "data" / "matches.json"
STANDINGS_JSON = REPO_ROOT / "data" / "standings.json"
OUTPUT_DIR = REPO_ROOT / "clubs"

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
    replacements = {
        "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "é": "e", "è": "e",
        "ê": "e", "ç": "c", "ã": "a", "á": "a", "à": "a", "ó": "o",
        "ô": "o", "ú": "u", "í": "i", "ï": "i", "ō": "o", "ū": "u",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    # & などを除去してハイフン区切り
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
# データ前処理
# ============================
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

    return players, matches, standings_comps


def build_clubs(players: list) -> dict:
    """players.json からクラブ別の情報を集約する。
    戻り値: {club_en: {club_ja, club_en, club_id, league_ja, competition_id, players: []}}
    """
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
                "competition_id": p.get("competition_id"),
                "players": [],
            }
        # 同クラブに複数選手いる場合
        clubs[club_en]["players"].append({
            "name_ja": p.get("name_ja", ""),
            "name_en": p.get("name_en", ""),
            "position": p.get("position", ""),
            "note": p.get("note", ""),
        })
    return clubs


def get_club_standing(club_info: dict, standings_comps: dict) -> dict:
    """クラブのリーグ順位を取得する。"""
    comp_id = str(club_info.get("competition_id") or "")
    club_id = club_info.get("club_id")

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


def get_club_recent_matches(club_info: dict, matches: list) -> list:
    """クラブの直近試合を取得する（最大10件）。"""
    club_id = club_info.get("club_id")
    if not club_id:
        return []

    club_matches = [
        m for m in matches
        if m.get("home_id") == club_id or m.get("away_id") == club_id
    ]
    club_matches.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return club_matches[:10]


def get_club_crest(club_info: dict, matches: list) -> str:
    """matches.json からクラブ紋章URLを取得する。"""
    club_id = club_info.get("club_id")
    if not club_id:
        return ""
    for m in matches:
        if m.get("home_id") == club_id and m.get("home_crest"):
            return m["home_crest"]
        if m.get("away_id") == club_id and m.get("away_crest"):
            return m["away_crest"]
    return ""


# ============================
# 選手slug生成（player_pagesと同じロジック）
# ============================
def get_player_slugs(players: list) -> dict:
    """name_en → slug の辞書を返す。重複時は -2 を付与。"""
    slug_map = {}
    used = {}
    for p in players:
        name_en = p.get("name_en", "")
        base = make_slug(name_en)
        if base not in used:
            used[base] = 1
            slug_map[name_en] = base
        else:
            # 重複があれば -2 を付与（generate_player_pages.py と同じ順序依存）
            # 既に登録済みの場合はスキップ（最初に見つかったものを保持）
            if name_en not in slug_map:
                used[base] += 1
                slug_map[name_en] = f"{base}-{used[base]}"
    return slug_map


# ============================
# 個別クラブページHTML生成
# ============================
def build_club_page(club_info: dict, slug: str, standing: dict,
                    recent_matches: list, crest_url: str,
                    player_slug_map: dict) -> str:
    club_ja = club_info.get("club_ja", "")
    club_en = club_info.get("club_en", "")
    league_ja = club_info.get("league_ja", "")
    players = club_info.get("players", [])

    title = f"{esc(club_ja)}（{esc(club_en)}）｜日本人選手・試合・順位｜football-jp"
    desc = f"{esc(club_ja)}に所属する日本人選手の試合日程・リーグ順位を日本時間で。"
    canonical = f"{SITE_URL}/clubs/{slug}/"

    # Schema.org SportsTeam JSON-LD
    schema_team = {
        "@context": "https://schema.org",
        "@type": "SportsTeam",
        "name": club_ja,
        "alternateName": club_en,
        "sport": "Football",
        "url": canonical,
    }
    if league_ja:
        schema_team["memberOf"] = {
            "@type": "SportsOrganization",
            "name": league_ja
        }
    if crest_url:
        schema_team["image"] = crest_url
    schema_ld = json.dumps(schema_team, ensure_ascii=False, indent=2)

    # --- 紋章 ---
    crest_html = ""
    if crest_url:
        crest_html = f'<img src="{esc(crest_url)}" alt="{esc(club_en)} crest" class="club-crest" width="64" height="64" loading="lazy">'
    else:
        crest_html = '<span style="font-size:48px;">🏟️</span>'

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
        gf = standing.get("goals_for", "—")
        ga = standing.get("goals_against", "—")
        league = standing.get("league_ja", league_ja)
        standing_html = f"""
    <section class="club-section">
      <h3>🏆 {esc(league)} 現在順位</h3>
      <div class="standing-row">
        <span class="standing-pos">{esc(str(pos))}位</span>
        <span class="standing-detail">
          （{esc(str(total))}チーム中）　{esc(str(played))}試合
          {esc(str(won))}勝{esc(str(draw))}分{esc(str(lost))}敗
          得失点 {esc(str(gf))}-{esc(str(ga))}
          <strong>{esc(str(pts))}pt</strong>
        </span>
      </div>
    </section>"""
    else:
        standing_html = f"""
    <section class="club-section">
      <h3>🏆 {esc(league_ja)} 順位</h3>
      <p class="no-data">順位データ取得外のリーグです（例：ベルギー・リーグ・ドゥ）。</p>
    </section>"""

    # --- 日本人選手セクション ---
    player_cards = ""
    for pl in players:
        name_en_pl = pl.get("name_en", "")
        pl_slug = player_slug_map.get(name_en_pl, make_slug(name_en_pl))
        note_pl = pl.get("note", "")
        note_html = f'<div class="player-note-small">{esc(note_pl)}</div>' if note_pl else ""
        player_cards += f"""
        <a class="player-link-card" href="/players/{esc(pl_slug)}/">
          <div class="player-name-ja">{esc(pl.get('name_ja', ''))}</div>
          <div class="player-name-en">{esc(name_en_pl)}</div>
          <div class="player-pos">{esc(pl.get('position', ''))}</div>
          {note_html}
        </a>"""

    players_html = f"""
    <section class="club-section">
      <h3>🇯🇵 所属日本人選手（{len(players)}名）</h3>
      <div class="players-grid">
        {player_cards}
      </div>
    </section>"""

    # --- 直近の試合セクション ---
    matches_html = ""
    if recent_matches:
        match_rows = ""
        for m in recent_matches:
            kickoff = m.get("kickoff_jst", "")
            status = m.get("status", "")
            home_ja = m.get("home_ja", "")
            away_ja = m.get("away_ja", "")
            score = m.get("score", {})
            comp_ja = m.get("competition_ja", "")
            home_id = m.get("home_id")
            club_id = club_info.get("club_id")
            is_home = home_id == club_id

            date_display = ""
            if kickoff:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(kickoff)
                    date_display = dt.strftime("%m/%d(%a) %H:%M JST")
                except Exception:
                    date_display = kickoff[:16]

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
            <div class="match-score {result_class}">{esc(score_display)}</div>
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
            <div class="match-score">{esc(bc_str) if bc_str else "—"}</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""

        matches_html = f"""
    <section class="club-section">
      <h3>📅 直近の試合（最大10試合）</h3>
      <div class="matches-list">
        <div class="match-header">
          <div class="match-date">日時（JST）</div>
          <div class="match-opponent">対戦相手</div>
          <div class="match-score">スコア/配信</div>
          <div class="match-comp">大会</div>
        </div>
        {match_rows}
      </div>
    </section>"""
    else:
        matches_html = """
    <section class="club-section">
      <h3>📅 直近の試合</h3>
      <p class="no-data">試合データを取得中です。</p>
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
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/logos/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/assets/logos/favicon-48.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <style>
    .club-hero {{
      background: #ffffff;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 18px;
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .club-crest {{
      width: 64px;
      height: 64px;
      object-fit: contain;
      flex-shrink: 0;
    }}
    .club-name-block h2 {{
      margin: 0 0 4px;
      font-size: 24px;
      font-weight: 800;
    }}
    .club-name-en {{
      font-size: 13px;
      color: #666;
      margin: 0 0 4px;
    }}
    .club-league-tag {{
      display: inline-block;
      padding: 2px 8px;
      font-size: 11px;
      background: #f0f1f5;
      border-radius: 3px;
    }}
    .club-section {{
      background: #fff;
      padding: 18px 16px;
      margin-bottom: 1px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .club-section h3 {{
      margin: 0 0 14px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding-left: 10px;
      border-left: 4px solid var(--c-accent, #0047ab);
      color: var(--c-text, #111);
    }}
    .standing-row {{ font-size: 14px; padding: 8px 0; }}
    .standing-pos {{ font-size: 24px; font-weight: 800; margin-right: 12px; }}
    .standing-detail {{ color: #444; }}
    .players-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 8px;
    }}
    .player-link-card {{
      display: block;
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      padding: 12px 14px;
      text-decoration: none;
      color: var(--c-text, #111);
      border-radius: 4px;
      transition: background 0.15s;
    }}
    .player-link-card:hover {{ background: #eef0f7; }}
    .player-name-ja {{ font-size: 15px; font-weight: 700; margin-bottom: 2px; }}
    .player-name-en {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .player-pos {{
      display: inline-block;
      padding: 1px 6px;
      font-size: 11px;
      font-weight: 700;
      background: #e6f0fa;
      color: #1565c0;
      border-radius: 3px;
    }}
    .player-note-small {{ font-size: 11px; color: #888; margin-top: 4px; }}
    .matches-list {{ font-size: 13px; }}
    .match-header, .match-row {{
      display: grid;
      grid-template-columns: 160px 1fr 80px 100px;
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
    .match-score {{ font-weight: 700; text-align: center; }}
    .match-score.win {{ color: #1a7a3a; }}
    .match-score.lose {{ color: #c0392b; }}
    .match-score.draw {{ color: #666; }}
    .match-row.scheduled .match-score {{
      font-size: 11px;
      font-weight: normal;
      color: #666;
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
    .no-data {{ color: #888; font-size: 13px; padding: 8px 0; margin: 0; }}
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
      .match-header, .match-row {{
        grid-template-columns: 120px 1fr 60px;
        font-size: 12px;
      }}
      .match-comp {{ display: none; }}
    }}
  </style>
  <script type="application/ld+json">
{schema_ld}
  </script>
</head>
<body>

<a class="back-link" href="/">← football-jp トップへ</a>

<div class="club-hero">
  <div class="crest-wrapper">
    {crest_html}
  </div>
  <div class="club-name-block">
    <h2>{esc(club_ja)}</h2>
    <p class="club-name-en">{esc(club_en)}</p>
    <span class="club-league-tag">🏆 {esc(league_ja)}</span>
  </div>
</div>

<div style="max-width: 860px; margin: 0 auto;">

  {standing_html}

  {players_html}

  {matches_html}

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
    players, matches, standings_comps = load_data()
    print(f"  選手数: {len(players)}")
    print(f"  試合数: {len(matches)}")

    # クラブ集約
    clubs = build_clubs(players)
    print(f"  対象クラブ数: {len(clubs)}")

    # 選手slug辞書（クラブページからのリンク用）
    player_slug_map = get_player_slugs(players)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []

    for club_en, club_info in clubs.items():
        slug = make_slug(club_en)
        club_ja = club_info.get("club_ja", club_en)

        # データ取得
        standing = get_club_standing(club_info, standings_comps)
        recent_matches = get_club_recent_matches(club_info, matches)
        crest_url = get_club_crest(club_info, matches)

        # HTMLページ生成
        html = build_club_page(club_info, slug, standing, recent_matches, crest_url, player_slug_map)

        # 出力
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((club_ja, club_en, slug, size))
        print(f"  ✅ {club_ja} ({club_en}) → /clubs/{slug}/ ({size:,} bytes)")

    print(f"\n合計 {len(generated)} クラブページ生成完了")

    print("\n生成済みslug一覧:")
    for club_ja, club_en, slug, size in generated:
        print(f"  {club_ja:20s} → /clubs/{slug}/")

    print("\n完了！")
    return {c_en: make_slug(c_en) for c_en in clubs.keys()}


if __name__ == "__main__":
    main()
