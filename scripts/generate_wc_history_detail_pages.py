#!/usr/bin/env python3
"""
generate_wc_history_detail_pages.py
W杯詳細ページ（日本出場7大会）を生成するスクリプト。

入力:  data/wc2026/wc_history_detail/{year}.json
出力:  worldcup/history/{year}/index.html (日本語)
       en/worldcup/history/{year}/index.html (英語)
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "wc2026" / "wc_history_detail"

TARGET_YEARS = [1998, 2002, 2006, 2010, 2014, 2018, 2022]
JST = timezone(timedelta(hours=9))

# wc_history.jsonからのメタ情報
WC_EXTRA = {
    1998: {
        "champion": "フランス", "runner_up": "ブラジル", "third": "クロアチア",
        "final_score": "3-0",
        "top_scorer": "ダボル・スーケル", "top_scorer_country": "クロアチア", "top_scorer_goals": 6,
        "teams": 32, "matches": 64, "total_goals": 171,
        "japan_result": "GS敗退", "highlight": "初出場。3戦全敗。アルゼンチン・クロアチア・ジャマイカ組。",
        "period_ja": "1998年6月10日〜7月12日",
        "champion_en": "France", "runner_up_en": "Brazil",
        "mvp": "Ronaldo", "mvp_ja": "ロナウド",
    },
    2002: {
        "champion": "ブラジル", "runner_up": "ドイツ", "third": "トルコ",
        "final_score": "2-0",
        "top_scorer": "ロナウド", "top_scorer_country": "ブラジル", "top_scorer_goals": 8,
        "teams": 32, "matches": 64, "total_goals": 161,
        "japan_result": "ベスト16",
        "highlight": "日韓共催。日本初のベスト16。グループH首位通過、トルコに0-1敗退。",
        "period_ja": "2002年5月31日〜6月30日",
        "champion_en": "Brazil", "runner_up_en": "Germany",
        "mvp": "Oliver Kahn", "mvp_ja": "オリバー・カーン",
    },
    2006: {
        "champion": "イタリア", "runner_up": "フランス", "third": "ドイツ",
        "final_score": "1-1（PK 5-3）",
        "top_scorer": "ミロスラフ・クローゼ", "top_scorer_country": "ドイツ", "top_scorer_goals": 5,
        "teams": 32, "matches": 64, "total_goals": 147,
        "japan_result": "GS敗退",
        "highlight": "ジーコ監督。グループF（オーストラリア・クロアチア・ブラジル）。1分2敗で敗退。",
        "period_ja": "2006年6月9日〜7月9日",
        "champion_en": "Italy", "runner_up_en": "France",
        "mvp": "Zinedine Zidane", "mvp_ja": "ジネディーヌ・ジダン",
    },
    2010: {
        "champion": "スペイン", "runner_up": "オランダ", "third": "ドイツ",
        "final_score": "1-0",
        "top_scorer": "トーマス・ミュラー / ダビド・ビジャ / スナイデル / フォルラン（同点）",
        "top_scorer_country": "ドイツ / スペイン / オランダ / ウルグアイ", "top_scorer_goals": 5,
        "teams": 32, "matches": 64, "total_goals": 145,
        "japan_result": "ベスト16",
        "highlight": "岡田監督。グループE首位通過。PK戦でパラグアイに敗退（0-0、PK3-5）。",
        "period_ja": "2010年6月11日〜7月11日",
        "champion_en": "Spain", "runner_up_en": "Netherlands",
        "mvp": "Diego Forlán", "mvp_ja": "ディエゴ・フォルラン",
    },
    2014: {
        "champion": "ドイツ", "runner_up": "アルゼンチン", "third": "オランダ",
        "final_score": "1-0（延長）",
        "top_scorer": "ハメス・ロドリゲス", "top_scorer_country": "コロンビア", "top_scorer_goals": 6,
        "teams": 32, "matches": 64, "total_goals": 171,
        "japan_result": "GS敗退",
        "highlight": "ザッケローニ監督。グループC（コートジボワール・ギリシャ・コロンビア）。1分2敗。",
        "period_ja": "2014年6月12日〜7月13日",
        "champion_en": "Germany", "runner_up_en": "Argentina",
        "mvp": "Lionel Messi", "mvp_ja": "リオネル・メッシ",
    },
    2018: {
        "champion": "フランス", "runner_up": "クロアチア", "third": "ベルギー",
        "final_score": "4-2",
        "top_scorer": "ハリー・ケイン", "top_scorer_country": "イングランド", "top_scorer_goals": 6,
        "teams": 32, "matches": 64, "total_goals": 169,
        "japan_result": "ベスト16",
        "highlight": "西野監督。グループH2位通過。ベルギーに2-3逆転負け（ロストフの悲劇）。",
        "period_ja": "2018年6月14日〜7月15日",
        "champion_en": "France", "runner_up_en": "Croatia",
        "mvp": "Luka Modrić", "mvp_ja": "ルカ・モドリッチ",
    },
    2022: {
        "champion": "アルゼンチン", "runner_up": "フランス", "third": "クロアチア",
        "final_score": "3-3（PK 4-2）",
        "top_scorer": "キリアン・ムバッペ", "top_scorer_country": "フランス", "top_scorer_goals": 8,
        "teams": 32, "matches": 64, "total_goals": 172,
        "japan_result": "ベスト16",
        "highlight": "森保監督。ドイツ・スペインを逆転撃破。クロアチアにPK負け（1-1、PK1-3）。",
        "period_ja": "2022年11月20日〜12月18日",
        "champion_en": "Argentina", "runner_up_en": "France",
        "mvp": "Lionel Messi", "mvp_ja": "リオネル・メッシ",
    },
}

STAGE_JA = {
    "GS-1": "グループステージ 第1節",
    "GS-2": "グループステージ 第2節",
    "GS-3": "グループステージ 第3節",
    "R16": "ベスト16",
    "QF": "準々決勝",
    "SF": "準決勝",
    "F": "決勝",
}

STAGE_EN = {
    "GS-1": "Group Stage MD1",
    "GS-2": "Group Stage MD2",
    "GS-3": "Group Stage MD3",
    "R16": "Round of 16",
    "QF": "Quarter-final",
    "SF": "Semi-final",
    "F": "Final",
}


def esc(s):
    """HTMLエスケープ。"""
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def score_html(home_score, away_score, pk_score=None):
    """スコア表示HTML。"""
    if home_score is None or away_score is None:
        return '<span class="score-na">-</span>'
    result = f'<span class="score">{home_score}–{away_score}</span>'
    if pk_score:
        result += f' <span class="score-pk">(PK {pk_score})</span>'
    return result


def japan_match_card_ja(match):
    """日本戦カードのHTML（日本語版）。"""
    home_ja = match.get("home_ja", match.get("home_en", ""))
    away_ja = match.get("away_ja", match.get("away_en", ""))
    is_japan_home = match.get("home_en") == "Japan"
    stage_label = STAGE_JA.get(match.get("stage", ""), match.get("stage", ""))
    score_display = score_html(match.get("home_score"), match.get("away_score"), match.get("pk_score"))
    date_str = match.get("date", "")

    # 勝敗判定
    hs = match.get("home_score")
    as_ = match.get("away_score")
    if hs is not None and as_ is not None:
        if match.get("pk_score"):
            # PKの場合は引き分け
            result_class = "draw"
            result_label = "PK負け" if is_japan_home else "PK負け"
            if match.get("pk_score"):
                pk_parts = match["pk_score"].split("-")
                if len(pk_parts) == 2:
                    japan_pk = int(pk_parts[0]) if is_japan_home else int(pk_parts[1])
                    opp_pk = int(pk_parts[1]) if is_japan_home else int(pk_parts[0])
                    result_label = "PK勝利" if japan_pk > opp_pk else "PK負け"
        else:
            japan_score = hs if is_japan_home else as_
            opp_score = as_ if is_japan_home else hs
            if japan_score > opp_score:
                result_class, result_label = "win", "勝利"
            elif japan_score < opp_score:
                result_class, result_label = "loss", "敗戦"
            else:
                result_class, result_label = "draw", "引き分け"
    else:
        result_class, result_label = "na", ""

    scorers_html = ""
    if match.get("japan_scorers"):
        scorers_html = '<div class="match-scorers">⚽ ' + " / ".join(esc(s) for s in match["japan_scorers"]) + "</div>"

    note_html = ""
    if match.get("note"):
        note_html = f'<div class="match-note">{esc(match["note"])}</div>'

    return f"""<div class="japan-match-card {result_class}">
  <div class="match-meta">
    <span class="match-date">{esc(date_str)}</span>
    <span class="match-stage">{esc(stage_label)}</span>
    <span class="result-badge {result_class}">{result_label}</span>
  </div>
  <div class="match-teams">
    <span class="team {'japan' if is_japan_home else ''}">{esc(home_ja)}</span>
    <span class="match-score">{score_display}</span>
    <span class="team {'japan' if not is_japan_home else ''}">{esc(away_ja)}</span>
  </div>
  {scorers_html}
  {note_html}
</div>"""


def group_table_html_ja(group):
    """グループ順位表のHTML（日本語版）。"""
    rows_html = ""
    for row in group.get("table", []):
        pos = row.get("position", "")
        team_ja = row.get("team_ja", row.get("team_en", ""))
        played = row.get("played", "")
        won = row.get("won", "")
        drawn = row.get("drawn", "")
        lost = row.get("lost", "")
        gf = row.get("goals_for", "")
        ga = row.get("goals_against", "")
        gd = (gf - ga) if (isinstance(gf, int) and isinstance(ga, int)) else ""
        pts = row.get("points", "")
        is_japan = row.get("team_en") == "Japan"
        row_class = ' class="japan-row"' if is_japan else ""
        rows_html += f"""<tr{row_class}>
      <td class="pos">{pos}</td>
      <td class="team-name">{esc(team_ja)}</td>
      <td>{played}</td><td>{won}</td><td>{drawn}</td><td>{lost}</td>
      <td>{gf}</td><td>{ga}</td><td>{gd}</td>
      <td class="pts">{pts}</td>
    </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="10" class="no-data">データ取得中</td></tr>'

    matches_html = ""
    for m in group.get("matches", []):
        home_ja = m.get("home_ja", m.get("home_en", ""))
        away_ja = m.get("away_ja", m.get("away_en", ""))
        is_japan_match = (m.get("home_en") == "Japan" or m.get("away_en") == "Japan")
        row_class = ' class="japan-match"' if is_japan_match else ""
        sc = score_html(m.get("home_score"), m.get("away_score"))
        matches_html += f"""<tr{row_class}>
      <td class="match-date-cell">{esc(m.get('date',''))}</td>
      <td class="team-home">{esc(home_ja)}</td>
      <td class="match-score-cell">{sc}</td>
      <td class="team-away">{esc(away_ja)}</td>
    </tr>"""

    return f"""<div class="group-section" id="group-{group['group_id']}">
  <h3 class="group-title">{esc(group.get('name_ja',''))}</h3>
  <div class="table-wrap">
    <table class="group-table">
      <thead>
        <tr><th>位</th><th>チーム</th><th>試</th><th>勝</th><th>分</th><th>敗</th><th>得</th><th>失</th><th>差</th><th>点</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="table-wrap" style="margin-top:12px;">
    <table class="matches-table">
      <thead>
        <tr><th>日付</th><th colspan="3">試合</th></tr>
      </thead>
      <tbody>{matches_html}</tbody>
    </table>
  </div>
</div>"""


def knockout_section_html_ja(knockout):
    """決勝トーナメントのHTML（日本語版）。"""
    def render_match(m, label=""):
        if not m:
            return ""
        home_ja = m.get("home_ja", m.get("home_en", ""))
        away_ja = m.get("away_ja", m.get("away_en", ""))
        sc = score_html(m.get("home_score"), m.get("away_score"), m.get("pk_score"))
        is_japan = m.get("home_en") == "Japan" or m.get("away_en") == "Japan"
        row_class = ' class="japan-match"' if is_japan else ""
        return f"""<tr{row_class}>
      <td class="match-date-cell">{esc(m.get('date',''))}</td>
      <td class="team-home">{esc(home_ja)}</td>
      <td class="match-score-cell">{sc}</td>
      <td class="team-away">{esc(away_ja)}</td>
    </tr>"""

    sections = []
    round_labels = [
        ("round_of_16", "ベスト16"),
        ("quarter_finals", "準々決勝"),
        ("semi_finals", "準決勝"),
        ("third_place", "3位決定戦"),
        ("final", "決勝"),
    ]

    for key, label in round_labels:
        data = knockout.get(key)
        if not data:
            continue
        if isinstance(data, list):
            rows = "".join(render_match(m) for m in data if m)
        else:
            rows = render_match(data)

        if not rows:
            continue

        sections.append(f"""<div class="knockout-round" id="ko-{key}">
  <h3 class="round-title">{label}</h3>
  <div class="table-wrap">
    <table class="matches-table">
      <thead><tr><th>日付</th><th colspan="3">試合</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>""")

    return "\n".join(sections)


def generate_html_ja(year, data, extra):
    """日本語版HTMLを生成。"""
    host = extra.get("host", data.get("host", ""))
    period = extra.get("period_ja", "")
    japan_result = extra.get("japan_result", "")
    champion = extra.get("champion", "")
    runner_up = extra.get("runner_up", "")
    final_score = extra.get("final_score", "")
    top_scorer = extra.get("top_scorer", "")
    top_scorer_country = extra.get("top_scorer_country", "")
    top_scorer_goals = extra.get("top_scorer_goals", "")
    highlight = extra.get("highlight", "")
    mvp_ja = extra.get("mvp_ja", "")
    japan_group = data.get("japan_group", "")

    # 日本戦ハイライト
    japan_matches = data.get("japan_matches", [])
    japan_matches_html = "\n".join(japan_match_card_ja(m) for m in japan_matches)

    # グループステージ
    groups_html = "\n".join(group_table_html_ja(g) for g in data.get("groups", []))
    if not groups_html:
        groups_html = '<p class="no-data">グループデータを取得中です。</p>'

    # 決勝トーナメント
    ko_html = knockout_section_html_ja(data.get("knockout", {}))
    if not ko_html:
        ko_html = '<p class="no-data">決勝トーナメントデータを取得中です。</p>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{year} FIFAワールドカップ 全試合・グループ・日本戦 | football-jp</title>
  <meta name="description" content="{year}年FIFAワールドカップ（開催国：{esc(host)}）の全グループ順位表・決勝トーナメント・日本代表全試合スコアを掲載。日本は{esc(japan_result)}。">
  <link rel="canonical" href="https://football-jp.com/worldcup/history/{year}/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/worldcup/history/{year}/">
  <meta property="og:title" content="{year} FIFAワールドカップ | football-jp">
  <meta property="og:description" content="{year}年W杯全データ。開催国：{esc(host)}。優勝：{esc(champion)}。日本：{esc(japan_result)}。">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/{year}/">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/{year}/">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-39G8CVXRW0"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "G-39G8CVXRW0");
  </script>
  <link rel="stylesheet" href="../../style.css">
  <link rel="stylesheet" href="../../worldcup-history-detail.css">
  <script src="../../wc-nav.js" defer></script>
</head>
<body class="wc-page">
<div class="wc-container">

  <!-- ナビ -->
  <nav class="wc-nav" id="wcNav"></nav>
  <script>document.getElementById('wcNav').innerHTML = window.wcRenderNav ? wcRenderNav('history') : '';</script>

  <!-- パンくずリスト -->
  <nav class="breadcrumb" aria-label="パンくず">
    <ol>
      <li><a href="../../">W杯</a></li>
      <li><a href="../../history.html">歴代W杯</a></li>
      <li aria-current="page">{year}</li>
    </ol>
  </nav>

  <!-- ヘッダー -->
  <header class="wc-detail-header">
    <div class="wc-detail-year">{year}</div>
    <h1 class="wc-detail-title">FIFA ワールドカップ {year}</h1>
    <div class="wc-detail-meta">
      <span class="meta-item">開催国：{esc(host)}</span>
      <span class="meta-item">期間：{esc(period)}</span>
      <span class="meta-item">出場：{extra.get('teams', 32)}カ国</span>
      <span class="meta-item">総試合：{extra.get('matches', 64)}</span>
      <span class="meta-item">総ゴール：{extra.get('total_goals', '')}</span>
    </div>
    <div class="wc-detail-results">
      <div class="result-item champion">🏆 優勝：{esc(champion)}</div>
      <div class="result-item">準優勝：{esc(runner_up)}</div>
      <div class="result-item">決勝スコア：{esc(final_score)}</div>
      <div class="result-item">得点王：{esc(top_scorer)}（{esc(top_scorer_country)}）{top_scorer_goals}点</div>
      {'<div class="result-item">MVP：' + esc(mvp_ja) + '</div>' if mvp_ja else ''}
    </div>
    <div class="japan-badge-header">
      <span class="japan-icon">🇯🇵</span>
      <span class="japan-result-text">日本代表：{esc(japan_result)} （グループ{esc(japan_group)}）</span>
    </div>
    <p class="wc-highlight">{esc(highlight)}</p>
    <div class="lang-switch">
      <a href="../../../en/worldcup/history/{year}/" class="lang-btn">🌐 English</a>
    </div>
  </header>

  <!-- TOC -->
  <nav class="page-toc">
    <a href="#japan-matches">日本戦</a>
    <a href="#group-stage">グループステージ</a>
    <a href="#knockout">決勝トーナメント</a>
    <a href="#records">記録</a>
  </nav>

  <!-- 1. 日本戦ハイライト -->
  <section id="japan-matches" class="wc-section">
    <h2 class="section-title">🇯🇵 日本代表 全試合</h2>
    <div class="japan-matches-grid">
      {japan_matches_html if japan_matches_html else '<p class="no-data">日本代表試合データなし。</p>'}
    </div>
  </section>

  <!-- 2. グループステージ -->
  <section id="group-stage" class="wc-section">
    <h2 class="section-title">グループステージ</h2>
    <div class="groups-container">
      {groups_html}
    </div>
  </section>

  <!-- 3. 決勝トーナメント -->
  <section id="knockout" class="wc-section">
    <h2 class="section-title">決勝トーナメント</h2>
    <div class="knockout-container">
      {ko_html}
    </div>
  </section>

  <!-- 4. 記録 -->
  <section id="records" class="wc-section">
    <h2 class="section-title">大会記録</h2>
    <div class="records-grid">
      <div class="record-item"><span class="rec-label">優勝</span><span class="rec-value">{esc(champion)}</span></div>
      <div class="record-item"><span class="rec-label">準優勝</span><span class="rec-value">{esc(runner_up)}</span></div>
      <div class="record-item"><span class="rec-label">3位</span><span class="rec-value">{esc(extra.get('third',''))}</span></div>
      <div class="record-item"><span class="rec-label">決勝スコア</span><span class="rec-value">{esc(final_score)}</span></div>
      <div class="record-item"><span class="rec-label">得点王</span><span class="rec-value">{esc(top_scorer)}（{top_scorer_goals}点）</span></div>
      {'<div class="record-item"><span class="rec-label">MVP</span><span class="rec-value">' + esc(mvp_ja) + '</span></div>' if mvp_ja else ''}
      <div class="record-item"><span class="rec-label">出場国数</span><span class="rec-value">{extra.get('teams', 32)}カ国</span></div>
      <div class="record-item"><span class="rec-label">総試合数</span><span class="rec-value">{extra.get('matches', 64)}試合</span></div>
      <div class="record-item"><span class="rec-label">総ゴール数</span><span class="rec-value">{extra.get('total_goals', '')}点</span></div>
      <div class="record-item"><span class="rec-label">日本成績</span><span class="rec-value">{esc(japan_result)}</span></div>
    </div>
  </section>

  <!-- ナビゲーション -->
  <nav class="year-nav">
    <a href="../" class="year-nav-btn">← 歴代W杯一覧</a>
    <div class="year-nav-years">
      {''.join(f'<a href="../{y}/" class="year-link{"active" if y == year else ""}">{y}</a>' for y in [1998,2002,2006,2010,2014,2018,2022])}
    </div>
  </nav>

  <footer class="wc-footer">
    <p>データ出典: Wikipedia / FIFA 公式記録</p>
    <p><a href="../../history.html">歴代W杯一覧へ戻る</a> / <a href="../../">W杯トップへ</a> / <a href="../../../">football-jp トップへ</a></p>
    <p class="footer-links"><a href="../../../privacy.html">プライバシーポリシー</a></p>
  </footer>
</div>
<script>
  // ナビ遅延初期化（wc-nav.js読み込み後）
  document.addEventListener('DOMContentLoaded', function() {{
    const nav = document.getElementById('wcNav');
    if (nav && typeof wcRenderNav === 'function') {{
      nav.innerHTML = wcRenderNav('history');
    }}
  }});
</script>
</body>
</html>"""


def generate_html_en(year, data, extra):
    """英語版HTMLを生成。"""
    host_en = extra.get("host_en", data.get("host_en", ""))
    japan_result = extra.get("japan_result", "")
    champion_en = extra.get("champion_en", "")
    runner_up_en = extra.get("runner_up_en", "")
    final_score = extra.get("final_score", "")
    top_scorer = extra.get("top_scorer", "")
    top_scorer_country = extra.get("top_scorer_country", "")
    top_scorer_goals = extra.get("top_scorer_goals", "")
    highlight = extra.get("highlight", "")
    mvp = extra.get("mvp", "")
    japan_group = data.get("japan_group", "")
    third = extra.get("third", "")

    # Japan matches (English)
    def japan_match_card_en(match):
        home_en = match.get("home_en", "")
        away_en = match.get("away_en", "")
        is_japan_home = home_en == "Japan"
        stage = STAGE_EN.get(match.get("stage", ""), match.get("stage", ""))
        sc = score_html(match.get("home_score"), match.get("away_score"), match.get("pk_score"))
        hs = match.get("home_score")
        as_ = match.get("away_score")
        if match.get("pk_score"):
            result_class = "draw"
            pk_parts = match["pk_score"].split("-")
            if len(pk_parts) == 2:
                j_pk = int(pk_parts[0]) if is_japan_home else int(pk_parts[1])
                o_pk = int(pk_parts[1]) if is_japan_home else int(pk_parts[0])
                result_label = "Win (PK)" if j_pk > o_pk else "Defeat (PK)"
            else:
                result_label = "Draw (PK)"
        elif hs is not None and as_ is not None:
            j = hs if is_japan_home else as_
            o = as_ if is_japan_home else hs
            if j > o:
                result_class, result_label = "win", "Win"
            elif j < o:
                result_class, result_label = "loss", "Defeat"
            else:
                result_class, result_label = "draw", "Draw"
        else:
            result_class, result_label = "na", ""

        scorers_html = ""
        if match.get("japan_scorers"):
            scorers_html = '<div class="match-scorers">⚽ ' + " / ".join(esc(s) for s in match["japan_scorers"]) + "</div>"
        note_html = f'<div class="match-note">{esc(match["note"])}</div>' if match.get("note") else ""

        return f"""<div class="japan-match-card {result_class}">
  <div class="match-meta">
    <span class="match-date">{esc(match.get('date',''))}</span>
    <span class="match-stage">{esc(stage)}</span>
    <span class="result-badge {result_class}">{result_label}</span>
  </div>
  <div class="match-teams">
    <span class="team {'japan' if is_japan_home else ''}">{esc(home_en)}</span>
    <span class="match-score">{sc}</span>
    <span class="team {'japan' if not is_japan_home else ''}">{esc(away_en)}</span>
  </div>
  {scorers_html}
  {note_html}
</div>"""

    japan_matches = data.get("japan_matches", [])
    japan_matches_html = "\n".join(japan_match_card_en(m) for m in japan_matches)

    # Group tables (English)
    def group_table_html_en(group):
        rows_html = ""
        for row in group.get("table", []):
            team_en = row.get("team_en", "")
            is_japan = team_en == "Japan"
            row_class = ' class="japan-row"' if is_japan else ""
            gf = row.get("goals_for", "")
            ga = row.get("goals_against", "")
            gd = (gf - ga) if (isinstance(gf, int) and isinstance(ga, int)) else ""
            rows_html += f"""<tr{row_class}>
        <td class="pos">{row.get('position','')}</td>
        <td class="team-name">{esc(team_en)}</td>
        <td>{row.get('played','')}</td><td>{row.get('won','')}</td>
        <td>{row.get('drawn','')}</td><td>{row.get('lost','')}</td>
        <td>{gf}</td><td>{ga}</td><td>{gd}</td>
        <td class="pts">{row.get('points','')}</td>
        </tr>"""
        if not rows_html:
            rows_html = '<tr><td colspan="10" class="no-data">Data loading</td></tr>'

        matches_html = ""
        for m in group.get("matches", []):
            is_japan_m = m.get("home_en") == "Japan" or m.get("away_en") == "Japan"
            row_class = ' class="japan-match"' if is_japan_m else ""
            sc = score_html(m.get("home_score"), m.get("away_score"))
            matches_html += f"""<tr{row_class}>
        <td class="match-date-cell">{esc(m.get('date',''))}</td>
        <td class="team-home">{esc(m.get('home_en',''))}</td>
        <td class="match-score-cell">{sc}</td>
        <td class="team-away">{esc(m.get('away_en',''))}</td>
        </tr>"""

        return f"""<div class="group-section" id="group-{group['group_id']}">
  <h3 class="group-title">Group {group['group_id']}</h3>
  <div class="table-wrap">
    <table class="group-table">
      <thead><tr><th>Pos</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="table-wrap" style="margin-top:12px;">
    <table class="matches-table">
      <thead><tr><th>Date</th><th colspan="3">Match</th></tr></thead>
      <tbody>{matches_html}</tbody>
    </table>
  </div>
</div>"""

    groups_html = "\n".join(group_table_html_en(g) for g in data.get("groups", []))
    if not groups_html:
        groups_html = '<p class="no-data">Group data loading.</p>'

    # Knockout (English)
    def ko_section_html_en(knockout):
        def render_match(m, label=""):
            if not m:
                return ""
            home_en = m.get("home_en", "")
            away_en = m.get("away_en", "")
            sc = score_html(m.get("home_score"), m.get("away_score"), m.get("pk_score"))
            is_japan = home_en == "Japan" or away_en == "Japan"
            row_class = ' class="japan-match"' if is_japan else ""
            return f"""<tr{row_class}>
      <td class="match-date-cell">{esc(m.get('date',''))}</td>
      <td class="team-home">{esc(home_en)}</td>
      <td class="match-score-cell">{sc}</td>
      <td class="team-away">{esc(away_en)}</td>
      </tr>"""

        sections = []
        round_labels_en = [
            ("round_of_16", "Round of 16"),
            ("quarter_finals", "Quarter-finals"),
            ("semi_finals", "Semi-finals"),
            ("third_place", "Third-place play-off"),
            ("final", "Final"),
        ]
        for key, label in round_labels_en:
            d = knockout.get(key)
            if not d:
                continue
            rows = "".join(render_match(m) for m in d if m) if isinstance(d, list) else render_match(d)
            if not rows:
                continue
            sections.append(f"""<div class="knockout-round" id="ko-{key}">
  <h3 class="round-title">{label}</h3>
  <div class="table-wrap">
    <table class="matches-table">
      <thead><tr><th>Date</th><th colspan="3">Match</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>""")
        return "\n".join(sections)

    ko_html = ko_section_html_en(data.get("knockout", {}))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{year} FIFA World Cup – All Groups, Results & Japan | football-jp</title>
  <meta name="description" content="Complete {year} FIFA World Cup data: all group tables, knockout results, and Japan national team matches. Host: {esc(host_en)}. Champion: {esc(champion_en)}.">
  <link rel="canonical" href="https://football-jp.com/en/worldcup/history/{year}/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/en/worldcup/history/{year}/">
  <meta property="og:title" content="{year} FIFA World Cup | football-jp">
  <meta property="og:description" content="{year} World Cup complete data. Host: {esc(host_en)}. Winner: {esc(champion_en)}. Japan: {esc(japan_result)}.">
  <meta property="og:locale" content="en_US">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/{year}/">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/{year}/">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-39G8CVXRW0"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "G-39G8CVXRW0");
  </script>
  <link rel="stylesheet" href="../../../../worldcup/style.css">
  <link rel="stylesheet" href="../../../../worldcup-history-detail.css">
</head>
<body class="wc-page">
<div class="wc-container">

  <!-- Breadcrumb -->
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
      <li><a href="../../../../en/">Home</a></li>
      <li><a href="../../../../worldcup/history.html">World Cup History</a></li>
      <li aria-current="page">{year}</li>
    </ol>
  </nav>

  <!-- Header -->
  <header class="wc-detail-header">
    <div class="wc-detail-year">{year}</div>
    <h1 class="wc-detail-title">FIFA World Cup {year}</h1>
    <div class="wc-detail-meta">
      <span class="meta-item">Host: {esc(host_en)}</span>
      <span class="meta-item">Teams: {extra.get('teams', 32)}</span>
      <span class="meta-item">Matches: {extra.get('matches', 64)}</span>
      <span class="meta-item">Goals: {extra.get('total_goals', '')}</span>
    </div>
    <div class="wc-detail-results">
      <div class="result-item champion">🏆 Champion: {esc(champion_en)}</div>
      <div class="result-item">Runner-up: {esc(runner_up_en)}</div>
      <div class="result-item">3rd place: {esc(third)}</div>
      <div class="result-item">Final score: {esc(final_score)}</div>
      <div class="result-item">Top scorer: {esc(top_scorer)} ({esc(top_scorer_country)}) {top_scorer_goals} goals</div>
      {'<div class="result-item">MVP: ' + esc(mvp) + '</div>' if mvp else ''}
    </div>
    <div class="japan-badge-header">
      <span class="japan-icon">🇯🇵</span>
      <span class="japan-result-text">Japan: {esc(japan_result)} (Group {esc(japan_group)})</span>
    </div>
    <div class="lang-switch">
      <a href="../../../../worldcup/history/{year}/" class="lang-btn">🌐 日本語</a>
    </div>
  </header>

  <!-- TOC -->
  <nav class="page-toc">
    <a href="#japan-matches">Japan Matches</a>
    <a href="#group-stage">Group Stage</a>
    <a href="#knockout">Knockout</a>
    <a href="#records">Records</a>
  </nav>

  <!-- Japan Matches -->
  <section id="japan-matches" class="wc-section">
    <h2 class="section-title">🇯🇵 Japan Matches</h2>
    <div class="japan-matches-grid">
      {japan_matches_html if japan_matches_html else '<p class="no-data">No Japan match data.</p>'}
    </div>
  </section>

  <!-- Group Stage -->
  <section id="group-stage" class="wc-section">
    <h2 class="section-title">Group Stage</h2>
    <div class="groups-container">
      {groups_html}
    </div>
  </section>

  <!-- Knockout -->
  <section id="knockout" class="wc-section">
    <h2 class="section-title">Knockout Stage</h2>
    <div class="knockout-container">
      {ko_html if ko_html else '<p class="no-data">Knockout data loading.</p>'}
    </div>
  </section>

  <!-- Records -->
  <section id="records" class="wc-section">
    <h2 class="section-title">Tournament Records</h2>
    <div class="records-grid">
      <div class="record-item"><span class="rec-label">Champion</span><span class="rec-value">{esc(champion_en)}</span></div>
      <div class="record-item"><span class="rec-label">Runner-up</span><span class="rec-value">{esc(runner_up_en)}</span></div>
      <div class="record-item"><span class="rec-label">3rd Place</span><span class="rec-value">{esc(third)}</span></div>
      <div class="record-item"><span class="rec-label">Final Score</span><span class="rec-value">{esc(final_score)}</span></div>
      <div class="record-item"><span class="rec-label">Top Scorer</span><span class="rec-value">{esc(top_scorer)} ({top_scorer_goals})</span></div>
      {'<div class="record-item"><span class="rec-label">MVP</span><span class="rec-value">' + esc(mvp) + '</span></div>' if mvp else ''}
      <div class="record-item"><span class="rec-label">Teams</span><span class="rec-value">{extra.get('teams', 32)}</span></div>
      <div class="record-item"><span class="rec-label">Matches</span><span class="rec-value">{extra.get('matches', 64)}</span></div>
      <div class="record-item"><span class="rec-label">Goals</span><span class="rec-value">{extra.get('total_goals', '')}</span></div>
      <div class="record-item"><span class="rec-label">Japan Result</span><span class="rec-value">{esc(japan_result)}</span></div>
    </div>
  </section>

  <!-- Year Nav -->
  <nav class="year-nav">
    <a href="../../../../worldcup/history.html" class="year-nav-btn">← All World Cups</a>
    <div class="year-nav-years">
      {''.join(f'<a href="../{y}/" class="year-link{"active" if y == year else ""}">{y}</a>' for y in [1998,2002,2006,2010,2014,2018,2022])}
    </div>
  </nav>

  <footer class="wc-footer">
    <p>Data source: Wikipedia / FIFA official records</p>
    <p><a href="../../../../worldcup/history.html">Back to History</a> / <a href="../../../../">football-jp Top</a></p>
    <p><a href="../../../../privacy.html">Privacy Policy</a></p>
  </footer>
</div>
</body>
</html>"""


def main():
    print(f"[INFO] W杯詳細ページ生成開始")
    ja_count = 0
    en_count = 0

    for year in TARGET_YEARS:
        json_path = DATA / f"{year}.json"
        if not json_path.exists():
            print(f"[WARN] {year}.json が見つかりません。スキップ。")
            continue

        data = json.loads(json_path.read_text(encoding="utf-8"))
        extra = WC_EXTRA.get(year, {})

        # 日本語版
        ja_dir = ROOT / "worldcup" / "history" / str(year)
        ja_dir.mkdir(parents=True, exist_ok=True)
        ja_html = generate_html_ja(year, data, extra)
        (ja_dir / "index.html").write_text(ja_html, encoding="utf-8")
        print(f"[JA] {ja_dir}/index.html")
        ja_count += 1

        # 英語版
        en_dir = ROOT / "en" / "worldcup" / "history" / str(year)
        en_dir.mkdir(parents=True, exist_ok=True)
        en_html = generate_html_en(year, data, extra)
        (en_dir / "index.html").write_text(en_html, encoding="utf-8")
        print(f"[EN] {en_dir}/index.html")
        en_count += 1

    print(f"\n[DONE] 日本語: {ja_count}ページ / 英語: {en_count}ページ 生成完了")


if __name__ == "__main__":
    main()
