#!/usr/bin/env python3
"""
generate_league_pages_en.py
リーグ別 日本人選手ハブページ（英語版）を自動生成するスクリプト。
出力先:
  en/leagues/index.html           ← リーグ一覧（英語）
  en/leagues/{slug}/index.html    ← 各リーグページ（英語）
使い方: python3 scripts/generate_league_pages_en.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# 日本語版と共通モジュールを流用
_scripts_dir = Path(__file__).parent
sys.path.insert(0, str(_scripts_dir))
from generate_league_pages import (
    REPO_ROOT, PLAYERS_JSON, MATCHES_JSON, STANDINGS_JSON, SCORERS_JSON,
    BROADCASTERS_JSON, PLAYER_STATS_JSON, GA4_ID, SITE_NAME, SITE_URL, JST,
    LEAGUE_DISPLAY_ORDER,
    esc, make_slug, league_slug, league_en, league_flag,
    build_unique_player_slugs, get_lastmod_jst,
    load_services, bc_brand_class, build_utm_url, build_bc_tag,
    load_all_data, group_players_by_league, group_players_by_club,
    get_player_stats_data, get_league_matches, split_matches_by_date,
    format_kickoff_ja, player_initials, position_color,
    build_standings_html, build_match_card,
)

OUTPUT_DIR = REPO_ROOT / "en" / "leagues"


# ============================
# 共通 HEAD / NAV / FOOTER（英語版）
# ============================
def common_head_en(title: str, description: str, canonical: str, hreflang_ja: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="alternate" hreflang="ja" href="{esc(hreflang_ja)}">
  <link rel="alternate" hreflang="en" href="{esc(canonical)}">
  <link rel="alternate" hreflang="x-default" href="{esc(hreflang_ja)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA4_ID}');
    gtag('event', 'page_view', {{ language: 'en' }});
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


def common_nav_en() -> str:
    return """<nav class="view-tabs">
    <a class="view-tab" href="/en/" data-view="schedule">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 7v5l3.5 2"/>
      </svg>
      <span>Schedule</span>
    </a>
    <a class="view-tab" href="/en/results/" data-view="results">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M8 12.5l3 3 5-6"/>
      </svg>
      <span>Results</span>
    </a>
    <a class="view-tab" href="/en/standings/" data-view="ranking">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4 20h16"/>
        <path d="M7 20v-5"/>
        <path d="M12 20v-9"/>
        <path d="M17 20v-13"/>
      </svg>
      <span>Standings</span>
    </a>
    <a class="view-tab active" href="/en/leagues/" data-view="leagues">
      <svg class="vt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      <span>Leagues</span>
    </a>
  </nav>"""


def common_footer_en() -> str:
    return """  <footer>
    <p>Data: <a href="https://www.football-data.org/" target="_blank" rel="noopener">football-data.org</a></p>
    <nav class="footer-nav">
      <a href="/en/players/">Players</a>
      <a href="/en/clubs/">Clubs</a>
      <a href="/en/leagues/">Leagues</a>
    </nav>
    <p>
      <a href="/privacy.html">Privacy Policy</a>
      &nbsp;|&nbsp;
      <a href="/">🇯🇵 日本語</a>
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
# 選手カード（英語版）
# ============================
def build_player_card_en(player: dict, player_slug: str, stats: dict) -> str:
    name_en = player.get("name_en", "")
    position = player.get("position", "")
    club_en = player.get("club_en", "")
    club_slug_str = make_slug(club_en) if club_en else ""

    initials = player_initials(name_en)
    pos_color = position_color(position)

    goals = stats.get("goals", "")
    assists = stats.get("assists", "")
    played = stats.get("played", "")

    stats_parts = []
    if played:
        stats_parts.append(f'<span class="stat-item">{esc(str(played))} apps</span>')
    if goals:
        stats_parts.append(f'<span class="stat-item stat-goal">{esc(str(goals))}G</span>')
    if assists:
        stats_parts.append(f'<span class="stat-item stat-assist">{esc(str(assists))}A</span>')
    stats_html = f'<div class="player-card-stats">{"".join(stats_parts)}</div>' if stats_parts else ""

    club_link = f'/en/clubs/{esc(club_slug_str)}/' if club_slug_str else "#"

    return f"""<a href="/en/players/{esc(player_slug)}/" class="player-card-link">
  <div class="player-card">
    <div class="player-avatar" style="background:{esc(pos_color)}">{esc(initials)}</div>
    <div class="player-card-info">
      <div class="player-card-name-ja">{esc(name_en)}</div>
      <div class="player-card-meta">
        <span class="player-pos-tag" style="background:{esc(pos_color)}20;color:{esc(pos_color)}">{esc(position)}</span>
        <a href="{esc(club_link)}" class="player-club-link" onclick="event.stopPropagation()">{esc(club_en)}</a>
      </div>
      {stats_html}
    </div>
  </div>
</a>"""


# ============================
# 順位テーブル（英語版）
# ============================
def build_standings_html_en(standings_comps: dict, comp_id: int, jp_club_ids: set, max_rows: int = 20) -> str:
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
        team_en = row.get("team_en", row.get("team_ja", ""))
        crest = row.get("team_crest", "")
        played = row.get("playedGames", "")
        won = row.get("won", "")
        draw = row.get("draw", "")
        lost = row.get("lost", "")
        pts = row.get("points", "")

        is_jp = team_id in jp_club_ids
        row_class = ' class="jp-club-row"' if is_jp else ""
        jp_badge = ' <span class="jp-badge">🇯🇵</span>' if is_jp else ""
        crest_html = f'<img src="{esc(crest)}" alt="" width="18" height="18" style="vertical-align:middle;margin-right:4px;">' if crest else ""

        rows_html.append(
            f'<tr{row_class}>'
            f'<td class="pos-cell">{esc(str(pos))}</td>'
            f'<td class="team-cell">{crest_html}{esc(team_en)}{jp_badge}</td>'
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
  <h2 class="section-title">League Standings</h2>
  <p class="section-note">🇯🇵 = Japanese player(s) at this club</p>
  <div class="table-scroll">
  <table class="standings-table league-standings-table">
    <thead>
      <tr>
        <th>Pos</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>Pts</th>
      </tr>
    </thead>
    <tbody>
"""
    html += "\n".join(rows_html)
    html += """
    </tbody>
  </table>
  </div>
  <p style="text-align:right;margin-top:6px;"><a href="/en/standings/" class="link-more">All Standings →</a></p>
</section>"""
    return html


# ============================
# 試合カード（英語版）
# ============================
def build_match_card_en(m: dict, services: dict, league_slug_str: str, is_result: bool) -> str:
    from generate_league_pages import format_kickoff_ja
    kickoff = format_kickoff_ja(m.get("kickoff_jst", ""))
    home_en = m.get("home_en", m.get("home_ja", ""))
    away_en = m.get("away_en", m.get("away_ja", ""))
    home_crest = m.get("home_crest", "")
    away_crest = m.get("away_crest", "")
    score = m.get("score") or {}
    home_score = score.get("home")
    away_score = score.get("away")
    jp_players = m.get("japanese_players", [])
    broadcasters = m.get("broadcasters", [])

    jp_names = [
        f'<span class="jp-player-badge">{esc(jp.get("name_ja",""))}</span>'
        for jp in jp_players if jp.get("name_ja")
    ]
    jp_html = f'<div class="jp-players-row">{"".join(jp_names)}</div>' if jp_names else ""

    bc_tags = [build_bc_tag(bc, services, "league", league_slug_str, league_slug_str) for bc in broadcasters]
    bc_html = f'<div class="bc-tags">{"".join(bc_tags)}</div>' if bc_tags else ""

    if is_result and home_score is not None and away_score is not None:
        score_html = f'<span class="match-score">{esc(str(home_score))} - {esc(str(away_score))}</span>'
    else:
        score_html = '<span class="match-vs">vs</span>'

    home_crest_html = f'<img src="{esc(home_crest)}" alt="" width="24" height="24" class="match-crest">' if home_crest else ""
    away_crest_html = f'<img src="{esc(away_crest)}" alt="" width="24" height="24" class="match-crest">' if away_crest else ""

    return f"""<div class="match-card">
  <div class="match-header">
    <span class="match-date">{esc(kickoff)} JST</span>
  </div>
  <div class="match-body">
    <span class="match-team home">{home_crest_html}{esc(home_en)}</span>
    {score_html}
    <span class="match-team away">{away_crest_html}{esc(away_en)}</span>
  </div>
  {jp_html}
  {bc_html}
</div>"""


# ============================
# リーグ別ページ（英語版）
# ============================
def generate_league_page_en(
    league_ja: str,
    players: list,
    all_matches: list,
    standings_comps: dict,
    scorers_comps: dict,
    player_stats: dict,
    services: dict,
    all_players: list,
) -> str:
    lg_en_name = league_en(league_ja)
    lg_slug_str = league_slug(league_ja)
    lg_flag_str = league_flag(league_ja)
    comp_id = players[0].get("competition_id") if players else None

    slug_map = build_unique_player_slugs(all_players)

    clubs_grouped = defaultdict(list)
    jp_club_ids = set()
    for p in players:
        clubs_grouped[p.get("club_en", "")].append(p)
        if p.get("club_id"):
            jp_club_ids.add(p.get("club_id"))

    num_players = len(players)
    num_clubs = len(clubs_grouped)

    canonical = f"{SITE_URL}/en/leagues/{lg_slug_str}/"
    ja_url = f"{SITE_URL}/leagues/{lg_slug_str}/"
    title = f"Japanese Players in {lg_en_name} - Stats & Match Schedule | football-jp"
    description = (
        f"All {num_players} Japanese players across {num_clubs} clubs in the {lg_en_name}. "
        f"Check match schedule, results, standings and streaming info in JST."
    )

    schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "SportsLeague",
        "name": lg_en_name,
        "url": canonical,
        "sport": "Soccer",
    }, ensure_ascii=False, indent=2)

    if comp_id:
        league_matches = get_league_matches(all_matches, comp_id)
        recent_matches, upcoming_matches = split_matches_by_date(league_matches)
    else:
        recent_matches, upcoming_matches = [], []

    html_parts = [common_head_en(title, description, canonical, ja_url)]
    html_parts.append(f'  <script type="application/ld+json">\n{schema}\n  </script>')
    html_parts.append("</head>")
    html_parts.append('<body data-view="leagues">')
    html_parts.append("""  <header>
    <div>
      <h1><a href="/en/" style="text-decoration:none;color:inherit;"><img src="/assets/logos/logo-header.png" alt="football-jp" class="header-logo"></a> Japanese Players by League</h1>
    </div>
  </header>""")
    html_parts.append(common_nav_en())

    html_parts.append(f"""<div class="league-hero">
  <div class="league-hero-inner">
    <div class="league-flag-big">{lg_flag_str}</div>
    <div class="league-hero-text">
      <h2 class="league-name-ja">{esc(lg_en_name)}</h2>
      <p class="league-summary">Japanese Players: <strong>{num_players}</strong> across <strong>{num_clubs} clubs</strong></p>
    </div>
  </div>
</div>""")

    # 選手一覧
    html_parts.append('<section class="league-section">')
    html_parts.append('<h2 class="section-title">Japanese Players</h2>')

    for club_en_key in sorted(clubs_grouped.keys()):
        club_players = clubs_grouped[club_en_key]
        c_slug = make_slug(club_en_key)
        html_parts.append(f'<div class="club-group">')
        html_parts.append(
            f'<h3 class="club-group-name">'
            f'<a href="/en/clubs/{esc(c_slug)}/" class="club-link">{esc(club_en_key)}</a>'
            f'</h3>'
        )
        html_parts.append('<div class="player-cards-grid">')
        for p in club_players:
            p_slug = slug_map.get(p.get("name_en", ""), make_slug(p.get("name_en", "")))
            stats = get_player_stats_data(p, scorers_comps, player_stats)
            html_parts.append(build_player_card_en(p, p_slug, stats))
        html_parts.append('</div></div>')

    html_parts.append('</section>')

    # 順位
    if comp_id:
        st_html = build_standings_html_en(standings_comps, comp_id, jp_club_ids)
        if st_html:
            html_parts.append(st_html)

    # 直近結果
    if recent_matches:
        html_parts.append('<section class="league-section">')
        html_parts.append('<h2 class="section-title">Recent Results (Japanese Players)</h2>')
        html_parts.append('<div class="match-cards-list">')
        for m in recent_matches[:10]:
            html_parts.append(build_match_card_en(m, services, lg_slug_str, is_result=True))
        html_parts.append('</div>')
        html_parts.append(f'<p style="text-align:right;margin-top:8px;"><a href="/en/results/" class="link-more">All Results →</a></p>')
        html_parts.append('</section>')

    # 次節予定
    if upcoming_matches:
        html_parts.append('<section class="league-section">')
        html_parts.append('<h2 class="section-title">Upcoming Fixtures</h2>')
        html_parts.append('<div class="match-cards-list">')
        for m in upcoming_matches[:10]:
            html_parts.append(build_match_card_en(m, services, lg_slug_str, is_result=False))
        html_parts.append('</div>')
        html_parts.append(f'<p style="text-align:right;margin-top:8px;"><a href="/en/" class="link-more">Full Schedule →</a></p>')
        html_parts.append('</section>')

    # 関連リンク
    html_parts.append('<section class="league-section">')
    html_parts.append('<h2 class="section-title">Related Links</h2>')
    html_parts.append('<ul class="related-links">')

    seen_slugs = set()
    for p in players:
        p_slug = slug_map.get(p.get("name_en", ""), make_slug(p.get("name_en", "")))
        if p_slug not in seen_slugs:
            seen_slugs.add(p_slug)
            html_parts.append(f'<li><a href="/en/players/{esc(p_slug)}/">{esc(p.get("name_en",""))} — Player Profile</a></li>')

    seen_clubs = set()
    for club_en_key in sorted(clubs_grouped.keys()):
        c_slug = make_slug(club_en_key)
        if c_slug not in seen_clubs:
            seen_clubs.add(c_slug)
            html_parts.append(f'<li><a href="/en/clubs/{esc(c_slug)}/">{esc(club_en_key)} — Club Page</a></li>')

    html_parts.append('<li><a href="/en/standings/">Standings</a></li>')
    html_parts.append('<li><a href="/en/leagues/">All Leagues</a></li>')
    html_parts.append(f'<li><a href="/leagues/{esc(lg_slug_str)}/">日本語版</a></li>')
    html_parts.append('</ul>')
    html_parts.append('</section>')

    html_parts.append(common_footer_en())
    html_parts.append('</body>')
    html_parts.append('</html>')

    return "\n".join(html_parts)


# ============================
# リーグ一覧ページ（英語版）
# ============================
def generate_league_index_en(league_groups: dict) -> str:
    canonical = f"{SITE_URL}/en/leagues/"
    ja_url = f"{SITE_URL}/leagues/"
    title = "Japanese Players by League | football-jp"
    description = (
        "Find all Japanese players competing in top European leagues — Premier League, Bundesliga, Eredivisie, and more. "
        "Match schedule, standings, and streaming info in JST."
    )

    html_parts = [common_head_en(title, description, canonical, ja_url)]
    html_parts.append("</head>")
    html_parts.append('<body data-view="leagues">')
    html_parts.append("""  <header>
    <div>
      <h1><a href="/en/" style="text-decoration:none;color:inherit;"><img src="/assets/logos/logo-header.png" alt="football-jp" class="header-logo"></a> Japanese Players by League</h1>
    </div>
  </header>""")
    html_parts.append(common_nav_en())

    html_parts.append('<div class="league-index-hero">')
    html_parts.append('<h2>Leagues</h2>')
    html_parts.append('<p>Browse Japanese players competing in top football leagues worldwide.</p>')
    html_parts.append('</div>')

    html_parts.append('<section class="league-index-grid-section">')
    html_parts.append('<div class="league-index-grid">')

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

        html_parts.append(f"""<a href="/en/leagues/{esc(lg_slug_str)}/" class="league-card">
  <div class="league-card-flag">{lg_flag_str}</div>
  <div class="league-card-body">
    <div class="league-card-name-ja">{esc(lg_en_name)}</div>
    <div class="league-card-meta">
      <span class="league-player-count">Japanese Players: <strong>{num_p}</strong></span>
      <span class="league-club-count">{num_c} clubs</span>
    </div>
  </div>
</a>""")

    html_parts.append('</div></section>')
    html_parts.append(common_footer_en())
    html_parts.append('</body></html>')

    return "\n".join(html_parts)


# ============================
# メイン
# ============================
def main():
    print("=== generate_league_pages_en.py 開始 ===")
    players, matches, standings_comps, scorers_comps, player_stats, services = load_all_data()

    league_groups = group_players_by_league(players)
    print(f"  リーグ数: {len(league_groups)}")

    generated = 0

    for league_ja, lg_players in league_groups.items():
        lg_slug_str = league_slug(league_ja)
        if not lg_slug_str:
            continue

        out_dir = OUTPUT_DIR / lg_slug_str
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"

        try:
            html = generate_league_page_en(
                league_ja, lg_players, matches,
                standings_comps, scorers_comps, player_stats, services, players
            )
            out_path.write_text(html, encoding="utf-8")
            print(f"  [生成] {out_path}")
            generated += 1
        except Exception as e:
            print(f"  [ERROR] {league_ja}: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = OUTPUT_DIR / "index.html"
    try:
        html = generate_league_index_en(league_groups)
        index_path.write_text(html, encoding="utf-8")
        print(f"  [生成] {index_path}")
        generated += 1
    except Exception as e:
        print(f"  [ERROR] リーグ一覧（英語）: {e}", file=sys.stderr)

    print(f"=== 完了: {generated} ファイル生成 ===")


if __name__ == "__main__":
    main()
