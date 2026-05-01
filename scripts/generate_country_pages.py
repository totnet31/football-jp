#!/usr/bin/env python3
"""
generate_country_pages.py
W杯2026 出場国別静的HTMLページを自動生成するスクリプト。
出力先: worldcup/countries/{slug}/index.html
使い方: python3 scripts/generate_country_pages.py
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
PROFILES_JSON = REPO_ROOT / "data" / "wc2026" / "country_profiles.json"
OUTPUT_DIR = REPO_ROOT / "worldcup" / "countries"
REDIRECTS_FILE = REPO_ROOT / "_redirects"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"


# ============================
# slug生成
# ============================
def make_slug(en: str) -> str:
    """英語国名をURLスラグに変換する。"""
    s = en.lower()
    s = s.replace("'", "")
    s = s.replace(".", "")
    # ç → c などの特殊文字をASCII化
    s = s.replace("ç", "c").replace("ã", "a").replace("é", "e").replace("ñ", "n")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


# TLA→slug の重複を解消するための上書きマッピング
# (同じenを持つ重複エントリがある場合はTLAで識別)
SLUG_OVERRIDE = {
    "CUW": "curacao-cuw",  # CURと重複するため識別子付きに
}


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
# 個別ページHTML生成
# ============================
def build_page(tla: str, p: dict, slug: str) -> str:
    ja = p.get("ja", tla)
    en = p.get("en", tla)
    flag = p.get("flag", "")
    group = p.get("group", "?")
    detailed = bool(p.get("detailed", False))

    # --- SEO meta ---
    summary_raw = p.get("summary", "")
    if summary_raw:
        desc = summary_raw[:150]
    else:
        desc = f"{ja}代表のW杯2026プロフィール。FIFAランク・過去成績・注目選手・日本との関係性。"

    title = f"{ja} 代表プロフィール｜W杯2026｜{SITE_NAME}"
    canonical = f"{SITE_URL}/worldcup/countries/{slug}/"
    og_desc = esc(desc)
    og_title = esc(title)
    og_url = canonical

    # key_players は JSON-LD 生成でも使うため先に取得
    key_players = p.get("key_players", [])

    # --- SportsTeam JSON-LD ---
    schema_obj = {
        "@context": "https://schema.org",
        "@type": "SportsTeam",
        "name": f"{ja} 代表",
        "alternateName": f"{en} national football team",
        "sport": "Football",
        "url": canonical,
        "memberOf": {
            "@type": "SportsOrganization",
            "name": "FIFA"
        }
    }
    # key_players が1件以上あれば athlete を追加（最大5名、nullフィールドは除外）
    valid_players = []
    for pl in key_players[:5]:
        name = pl.get("name") or ""
        position = pl.get("position") or ""
        club = pl.get("club") or ""
        if not name or not position or not club:
            continue
        valid_players.append({
            "@type": "Person",
            "name": name,
            "jobTitle": position,
            "affiliation": {
                "@type": "SportsTeam",
                "name": club
            }
        })
    if valid_players:
        schema_obj["athlete"] = valid_players
    sports_team_ld = json.dumps(schema_obj, ensure_ascii=False, indent=2)

    # --- info-grid values ---
    fifa_rank = p.get("fifa_rank")
    if fifa_rank:
        fifa_str = esc(str(fifa_rank) + "位")
    else:
        fifa_max = p.get("fifa_max_rank")
        fifa_str = esc(f"最高{fifa_max}位") if fifa_max else "—"

    wc_appearances = p.get("wc_appearances")
    wc_str = esc(str(wc_appearances) + "回") if wc_appearances else "—"

    manager = p.get("manager") or p.get("manager_en") or "—"
    captain = p.get("captain") or p.get("captain_en") or ""

    # --- sections HTML ---
    sections_html = ""

    # info-grid (常に表示)
    captain_card = ""
    if captain:
        captain_card = f'<div class="info-card"><div class="label">キャプテン</div><div class="value" style="font-size:13px;">{esc(captain)}</div></div>'

    info_grid = f"""
    <div class="info-grid">
      <div class="info-card"><div class="label">FIFAランク</div><div class="value">{fifa_str}</div></div>
      <div class="info-card"><div class="label">W杯出場回数</div><div class="value">{wc_str}</div></div>
      <div class="info-card"><div class="label">監督</div><div class="value" style="font-size:13px;">{esc(manager)}</div></div>
      {captain_card}
    </div>"""

    if detailed and summary_raw:
        expectations = p.get("expectations", "")
        exp_html = f'<p><strong>期待値：</strong>{esc(expectations)}</p>' if expectations else ""
        sections_html += f"""
    <section class="country-section">
      <h3>📋 サマリー</h3>
      <p>{esc(summary_raw)}</p>
      {exp_html}
    </section>"""

    # best_result
    best_result = p.get("best_result", "")
    sections_html += f"""
    <section class="country-section">
      <h3>🏆 過去W杯成績</h3>
      <p>{esc(best_result) if best_result else '—'}</p>
    </section>"""

    # japan_relation
    japan_relation = p.get("japan_relation", "")
    if japan_relation:
        sections_html += f"""
    <section class="country-section">
      <h3>🇯🇵 日本との関係性</h3>
      <p>{esc(japan_relation)}</p>
    </section>"""

    # key_players (key_players は上部で取得済み)
    if key_players:
        player_cards = ""
        for pl in key_players:
            player_cards += f"""
        <div class="player-card">
          <div class="name">{esc(pl.get('name', ''))}</div>
          <div class="meta">{esc(pl.get('position', ''))} ｜ {esc(pl.get('club', ''))}</div>
          <div class="note">{esc(pl.get('note', ''))}</div>
        </div>"""
        sections_html += f"""
    <section class="country-section">
      <h3>⭐ 注目選手</h3>
      {player_cards}
    </section>"""

    # stub-warning (detailed=False の国)
    stub_html = ""
    if not detailed:
        stub_html = """
    <div class="stub-warning">
      ⏳ この国の詳細プロフィールは<strong>準備中</strong>です（順次拡充）。<br>
      現時点では基本情報のみ表示しています。
    </div>"""
        # stub でも japan_relation があれば表示
        if japan_relation:
            stub_html += f"""
    <section class="country-section">
      <h3>🇯🇵 日本との関係性</h3>
      <p>{esc(japan_relation)}</p>
    </section>"""

    # detailed=True でも summary が無い場合 = auto_filled stub
    if detailed and not summary_raw and not key_players:
        stub_html = """
    <div class="stub-warning">
      ⏳ この国の詳細プロフィールは<strong>準備中</strong>です（順次拡充）。<br>
      現時点では基本情報のみ表示しています。
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{og_desc}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{og_url}">
  <meta property="og:title" content="{og_title}">
  <meta property="og:description" content="{og_desc}">
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
  <link rel="stylesheet" href="/worldcup/style.css">
  <style>
    .country-hero {{
      background: #ffffff;
      border-bottom: 1px solid var(--c-border);
      padding: 20px 0 18px;
      margin-bottom: 18px;
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 16px;
    }}
    .country-hero .flag {{ font-size: 56px; line-height: 1; }}
    .country-hero .name-block h2 {{
      margin: 0;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: 0.01em;
    }}
    .country-hero .en {{
      font-size: 12px;
      color: var(--c-text-sub);
      letter-spacing: 0.06em;
      margin-top: 2px;
    }}
    .country-hero .group-tag {{
      display: inline-block;
      padding: 3px 10px;
      font-size: 11px;
      font-weight: 700;
      color: var(--c-accent);
      border: 1px solid var(--c-accent);
      letter-spacing: 0.04em;
    }}
    .info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 0;
      margin-bottom: 22px;
      border: 1px solid var(--c-border);
    }}
    .info-card {{
      background: #fff;
      border-right: 1px solid var(--c-border);
      padding: 12px 14px;
      text-align: left;
    }}
    .info-card:last-child {{ border-right: none; }}
    .info-card .label {{ font-size: 11px; color: var(--c-text-sub); margin-bottom: 4px; letter-spacing: 0.04em; }}
    .info-card .value {{ font-size: 17px; font-weight: 800; color: var(--c-text); font-feature-settings: "tnum"; }}
    .country-section {{
      background: #fff;
      padding: 18px 0;
      margin-bottom: 0;
      border-bottom: 1px solid var(--c-border);
    }}
    .country-section:last-child {{ border-bottom: none; }}
    .country-section h3 {{
      margin: 0 0 14px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding-left: 10px;
      border-left: 4px solid var(--c-accent);
      color: var(--c-text);
    }}
    .country-section p {{ margin: 0 0 8px; line-height: 1.7; font-size: 13px; }}
    .player-card {{
      background: #fff;
      border: 1px solid var(--c-border);
      padding: 12px 14px;
      margin-bottom: 6px;
    }}
    .player-card .name {{ font-size: 14px; font-weight: 700; }}
    .player-card .meta {{ font-size: 12px; color: var(--c-text-sub); margin: 2px 0 6px; }}
    .player-card .note {{ font-size: 13px; }}
    .stub-warning {{
      background: #fff;
      border: 1px solid var(--c-border);
      border-left: 3px solid #d4af37;
      padding: 12px 14px;
      font-size: 13px;
      line-height: 1.7;
      margin-bottom: 16px;
    }}
    .matches-list {{ margin-top: 10px; }}
    .squad-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 4px;
    }}
    .squad-table th {{
      background: #f0f1f5;
      color: var(--c-text);
      font-weight: 600;
      font-size: 11px;
      padding: 8px 6px;
      text-align: left;
      border-bottom: 2px solid var(--c-text);
    }}
    .squad-table td {{
      padding: 8px 6px;
      border-bottom: 1px solid var(--c-border);
      font-size: 12px;
    }}
    .squad-table td.num {{ text-align: right; font-feature-settings: "tnum"; }}
    .squad-table tr:hover {{ background: var(--c-bg-subtle); }}
    .squad-table .pos-tag {{
      display: inline-block;
      padding: 1px 6px;
      font-size: 10px;
      font-weight: 700;
      color: var(--c-text);
      border: 1px solid var(--c-border-strong);
      background: #fff;
      letter-spacing: 0.02em;
      border-radius: 3px;
    }}
    .pos-tag.GK {{ color: #b8770a; background: #fff8e1; border-color: #f0c860; }}
    .pos-tag.DF {{ color: #1565c0; background: #e6f0fa; border-color: #90c1e6; }}
    .pos-tag.MF {{ color: #2d7a4d; background: #e6f4ec; border-color: #a0cfb4; }}
    .pos-tag.FW {{ color: #c1304a; background: #fff0f0; border-color: #f4c0c0; }}
    .squad-table tr.first-of-pos td {{ border-top: 2px solid var(--c-border-strong); }}
    .squad-disclaimer {{
      background: #fff8ed;
      border-left: 3px solid #d4af37;
      padding: 8px 12px;
      margin: 10px 0;
      font-size: 12px;
      line-height: 1.6;
    }}
    .club-name {{ font-weight: 600; }}
    .club-country {{ display: block; font-size: 10px; color: var(--c-text-sub); margin-top: 1px; }}
    @media (max-width: 600px) {{
      .squad-table {{ display: block; font-size: 12px; }}
      .squad-table thead {{ display: none; }}
      .squad-table tbody {{ display: block; }}
      .squad-table tr {{
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 4px 10px;
        padding: 10px 12px;
        border: 1px solid var(--c-border);
        border-radius: 4px;
        margin-bottom: 6px;
        align-items: start;
      }}
      .squad-table td {{ display: block; padding: 0; border: none; }}
      .squad-table td.col-no {{ grid-column: 1; grid-row: 1; font-weight:700; font-size: 14px; align-self: center; min-width: 26px; text-align: center; color: var(--c-text-sub); }}
      .squad-table td.col-pos {{ grid-column: 1; grid-row: 2; align-self: center; }}
      .squad-table td.col-name {{ grid-column: 2; grid-row: 1 / span 2; }}
      .squad-table td.col-club {{ grid-column: 1 / span 3; grid-row: 3; font-size: 11px; padding-top: 4px; border-top: 1px dashed var(--c-border); margin-top: 4px; }}
      .squad-table td.col-dob {{ grid-column: 3; grid-row: 1; text-align: right; font-size: 11px; }}
      .squad-table td.col-h, .squad-table td.col-w {{ display: none !important; }}
      .squad-table td.col-hw {{
        display: block !important;
        grid-column: 3; grid-row: 2; text-align: right; font-size: 11px;
        font-feature-settings: "tnum";
      }}
      .club-country {{ display: inline; margin-left: 6px; }}
    }}
  </style>
  <script type="application/ld+json">
{sports_team_ld}
  </script>
  <script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "football-jp",
  "alternateName": "海外サッカー 日本人選手 試合スケジュール",
  "url": "https://football-jp.com/",
  "inLanguage": "ja-JP",
  "publisher": {{
    "@type": "Organization",
    "name": "football-jp",
    "url": "https://football-jp.com/"
  }}
}}
  </script>
</head>
<body class="wc-page">

<header class="wc-header">
  <a href="/worldcup/" class="wc-back-link">⚽ W杯2026特集トップへ</a>
  <h1>{esc(flag)} {esc(ja)}</h1>
  <p class="wc-tagline">{esc(en)}（Group {esc(group)}）</p>
</header>

<div class="wc-container">

  <nav class="wc-nav" id="wcNav"></nav>
  <script src="/worldcup/wc-nav.js"></script>
  <script>document.getElementById('wcNav').innerHTML = wcRenderNav('countries');</script>

  <!-- 静的コンテンツ（SEO用） -->
  <div class="country-hero">
    <div class="flag">{esc(flag)}</div>
    <div class="name-block">
      <h2>{esc(ja)}</h2>
      <div class="en">{esc(en)}</div>
    </div>
    <span class="group-tag">Group {esc(group)}</span>
  </div>

  {info_grid}

  {stub_html}

  {sections_html}

  <!-- 動的コンテンツ（試合・スカッド） -->
  <div id="dynamic-content"></div>

  <p style="margin-top: 20px;">
    <a href="/worldcup/countries.html" style="color:var(--c-text); font-size: 13px;">← 48か国一覧に戻る</a>
  </p>

  <footer class="wc-footer">
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football data provided by the Football-Data.org API</a></p>
    <p>このページは2026 FIFA W杯の期間限定特集です／<a href="/">football-jp トップへ</a></p>
    <p class="footer-links"><a href="/privacy.html">プライバシーポリシー</a></p>
  </footer>
</div>

<script>
const TLA = {json.dumps(tla)};

(async () => {{
  const [matchesRes, squadsRes] = await Promise.all([
    fetch('/data/wc2026/matches.json'),
    fetch('/data/wc2026/squads.json').catch(() => null),
  ]);
  const matches = (await matchesRes.json()).matches || [];
  const squadsData = squadsRes ? await squadsRes.json().catch(() => null) : null;
  const squad = squadsData ? squadsData[TLA] : null;

  const teamMatches = matches.filter(m => m.home_tla === TLA || m.away_tla === TLA)
    .sort((a, b) => a.kickoff_jst.localeCompare(b.kickoff_jst));

  let html = '';

  if (teamMatches.length > 0) {{
    html += `
      <section class="country-section">
        <h3>📅 {esc(ja)}の試合（グループステージ）</h3>
        <div class="matches-list">${{teamMatches.map(m => renderMatchSummary(m, TLA)).join('')}}</div>
      </section>
    `;
  }}

  if (squad && squad.players && squad.players.length > 0) {{
    const players = squad.players.slice().sort((a, b) => {{
      const posOrder = {{ GK: 0, DF: 1, MF: 2, FW: 3 }};
      const pa = posOrder[a.pos] ?? 9;
      const pb = posOrder[b.pos] ?? 9;
      if (pa !== pb) return pa - pb;
      return (a.no || 0) - (b.no || 0);
    }});
    const ageAt = (dob) => {{
      try {{
        const d = new Date(dob);
        const ref = new Date('2026-06-11');
        let age = ref.getFullYear() - d.getFullYear();
        const m = ref.getMonth() - d.getMonth();
        if (m < 0 || (m === 0 && ref.getDate() < d.getDate())) age--;
        return age;
      }} catch {{ return ''; }}
    }};
    const splitClub = (club) => {{
      if (!club) return {{ name: '—', country: '' }};
      const m = club.match(/^(.+?)\\s*\\((.+?)\\)\\s*$/);
      if (m) return {{ name: m[1].trim(), country: m[2].trim() }};
      return {{ name: club.trim(), country: '' }};
    }};
    let prevPos = null;
    const rows = players.map(pl => {{
      const c = splitClub(pl.club);
      const ageStr = ageAt(pl.dob);
      const isFirst = pl.pos !== prevPos;
      prevPos = pl.pos;
      return `<tr class="${{isFirst ? 'first-of-pos' : ''}} pos-${{pl.pos}}">
        <td class="num col-no">${{pl.no || '—'}}</td>
        <td class="col-pos"><span class="pos-tag ${{pl.pos}}">${{pl.pos || '—'}}</span></td>
        <td class="col-name"><strong>${{escapeHtml(pl.name_ja)}}</strong><br><span style="font-size:10px;color:var(--c-text-sub);">${{escapeHtml(pl.name_en)}}</span></td>
        <td class="col-club"><span class="club-name">${{escapeHtml(c.name)}}</span>${{c.country ? `<span class="club-country">${{escapeHtml(c.country)}}</span>` : ''}}</td>
        <td class="num col-dob">${{pl.dob ? pl.dob.replace(/-/g, '/') : '—'}}<br><span style="font-size:10px;color:var(--c-text-sub);">${{ageStr ? ageStr+'歳' : ''}}</span></td>
        <td class="num col-h hide-on-mobile">${{pl.height_cm ? pl.height_cm + 'cm' : '—'}}</td>
        <td class="num col-w hide-on-mobile">${{pl.weight_kg ? pl.weight_kg + 'kg' : '—'}}</td>
        <td class="num col-hw show-on-mobile" style="display:none;">${{pl.height_cm ? pl.height_cm + 'cm' : '—'}}/${{pl.weight_kg ? pl.weight_kg + 'kg' : '—'}}</td>
      </tr>`;
    }}).join('');
    html += `
      <section class="country-section">
        <h3>👥 {esc(ja)}代表 全選手プロフィール(${{players.length}}名）</h3>
        <div class="squad-disclaimer">
          ⚠️ ${{escapeHtml(squad.as_of || '参考データ')}}を表示中。
          2026年最終スカッドは6/1のFIFA発表後に更新します。
          <span style="display:block; margin-top:4px; font-size:11px; color:var(--c-text-sub);">出典: ${{escapeHtml(squadsData._source || 'unknown')}}</span>
        </div>
        <table class="squad-table">
          <thead>
            <tr><th>#</th><th>Pos</th><th>選手名</th><th>所属クラブ</th><th>生年月日</th><th>身長</th><th>体重</th></tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>
      </section>
    `;
  }} else if (squad === null || (squad && (!squad.players || squad.players.length === 0))) {{
    html += `
      <section class="country-section">
        <h3>👥 {esc(ja)}代表 全選手プロフィール</h3>
        <div class="squad-disclaimer">
          ⏳ 全選手プロフィールは準備中です。<br>
          5/11の予備リスト（35〜55名）または6/1の最終スカッド（23〜26名）発表後に表示予定。
        </div>
      </section>
    `;
  }}

  document.getElementById('dynamic-content').innerHTML = html;
}})();

function renderMatchSummary(m, currentTla) {{
  const ko = new Date(m.kickoff_jst);
  const dateStr = ko.toLocaleDateString('ja-JP', {{ month: 'numeric', day: 'numeric', weekday: 'short' }});
  const timeStr = ko.toLocaleTimeString('ja-JP', {{ hour: '2-digit', minute: '2-digit' }});
  const homeIsCurrent = m.home_tla === currentTla;
  const oppFlag = homeIsCurrent ? m.away_flag : m.home_flag;
  const oppName = homeIsCurrent ? m.away_ja : m.home_ja;
  const score = m.score;
  let scoreStr = '—';
  if (score) {{
    scoreStr = homeIsCurrent ? `${{score.home}} - ${{score.away}}` : `${{score.away}} - ${{score.home}}`;
  }}
  return `
    <div class="player-card" style="display:grid; grid-template-columns: 80px 1fr auto; gap:12px; align-items:center;">
      <div style="font-size:11px; color:var(--c-text-sub);">${{dateStr}}<br>${{timeStr}} JST</div>
      <div>vs <strong>${{oppFlag}} ${{escapeHtml(oppName)}}</strong></div>
      <div style="font-size:14px; font-weight:700;">${{scoreStr}}</div>
    </div>
  `;
}}

function escapeHtml(s) {{
  return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}
</script>

</body>
</html>
"""


# ============================
# _redirects 追記内容生成
# ============================
def build_redirect_lines(slug_map: dict) -> list:
    lines = []
    for tla, slug in sorted(slug_map.items()):
        lines.append(f"/worldcup/country.html?tla={tla}  /worldcup/countries/{slug}/  301")
    return lines


# ============================
# メイン処理
# ============================
def main():
    print(f"📖 プロフィールJSON読み込み中: {PROFILES_JSON}")
    with open(PROFILES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    profiles = data.get("profiles", {})
    print(f"   {len(profiles)}か国のデータを検出")

    slug_map = {}
    generated = []

    for tla, p in profiles.items():
        en = p.get("en", tla)
        if tla in SLUG_OVERRIDE:
            slug = SLUG_OVERRIDE[tla]
        else:
            slug = make_slug(en)
        slug_map[tla] = slug

        # 出力ディレクトリ作成
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"

        html = build_page(tla, p, slug)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((tla, slug, size))
        print(f"   ✅ {tla} → {slug}/  ({size:,} bytes)")

    print(f"\n📊 合計 {len(generated)} ページ生成完了")
    total_size = sum(s for _, _, s in generated)
    avg_size = total_size // len(generated) if generated else 0
    print(f"   平均ファイルサイズ: {avg_size:,} bytes")

    # _redirects 更新
    print(f"\n📝 _redirects 更新中: {REDIRECTS_FILE}")
    with open(REDIRECTS_FILE, encoding="utf-8") as f:
        existing = f.read()

    redirect_lines = build_redirect_lines(slug_map)
    marker = "\n# [自動生成] /worldcup/country.html?tla=XXX → 静的ページ 301リダイレクト\n"

    # 既存の自動生成ブロックを削除してから追記
    if marker in existing:
        existing = existing[: existing.index(marker)]

    new_content = existing.rstrip() + "\n" + marker + "\n".join(redirect_lines) + "\n"
    with open(REDIRECTS_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"   {len(redirect_lines)} 行の301リダイレクトを追記")

    # slug一覧を出力
    print("\n🗂️  生成済みslug一覧:")
    for tla, slug, size in sorted(generated, key=lambda x: x[1]):
        print(f"   {tla:5s} → /worldcup/countries/{slug}/")

    print("\n✨ 完了！")
    return slug_map


if __name__ == "__main__":
    main()
