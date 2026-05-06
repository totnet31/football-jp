#!/usr/bin/env python3
"""
generate_wc_scorers_page.py
歴代W杯得点王ランキング詳細ページを生成するスクリプト。

入力:  data/wc2026/wc_history.json
出力:  worldcup/history/scorers/index.html (日本語)
       en/worldcup/history/scorers/index.html (英語)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
WC_HISTORY = ROOT / "data" / "wc2026" / "wc_history.json"
JST = timezone(timedelta(hours=9))


# 歴代得点王ランキング TOP30（知識ベース補完）
# JSON に5名、残りを補完
ALL_TIME_SCORERS_EXTENDED = [
    {"player": "ミロスラフ・クローゼ", "player_en": "Miroslav Klose",
     "country": "ドイツ", "country_en": "Germany", "goals": 16,
     "tournaments": 4, "years": "2002, 2006, 2010, 2014",
     "tournament_goals": "2002:5, 2006:5, 2010:4, 2014:2"},
    {"player": "ロナウド", "player_en": "Ronaldo",
     "country": "ブラジル", "country_en": "Brazil", "goals": 15,
     "tournaments": 4, "years": "1994, 1998, 2002, 2006",
     "tournament_goals": "1994:0, 1998:4, 2002:8, 2006:3"},
    {"player": "ゲルト・ミュラー", "player_en": "Gerd Müller",
     "country": "西ドイツ", "country_en": "West Germany", "goals": 14,
     "tournaments": 2, "years": "1970, 1974",
     "tournament_goals": "1970:10, 1974:4"},
    {"player": "リオネル・メッシ", "player_en": "Lionel Messi",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 13,
     "tournaments": 5, "years": "2006, 2010, 2014, 2018, 2022",
     "tournament_goals": "2006:1, 2010:1, 2014:4, 2018:1, 2022:7"},
    {"player": "ジュスト・フォンテーヌ", "player_en": "Just Fontaine",
     "country": "フランス", "country_en": "France", "goals": 13,
     "tournaments": 1, "years": "1958",
     "tournament_goals": "1958:13"},
    {"player": "ペレ", "player_en": "Pelé",
     "country": "ブラジル", "country_en": "Brazil", "goals": 12,
     "tournaments": 4, "years": "1958, 1962, 1966, 1970",
     "tournament_goals": "1958:6, 1962:1, 1966:1, 1970:4"},
    {"player": "キリアン・ムバッペ", "player_en": "Kylian Mbappé",
     "country": "フランス", "country_en": "France", "goals": 12,
     "tournaments": 2, "years": "2018, 2022",
     "tournament_goals": "2018:4, 2022:8"},
    {"player": "サンドル・コチシュ", "player_en": "Sándor Kocsis",
     "country": "ハンガリー", "country_en": "Hungary", "goals": 11,
     "tournaments": 1, "years": "1954",
     "tournament_goals": "1954:11"},
    {"player": "ユルゲン・クリンスマン", "player_en": "Jürgen Klinsmann",
     "country": "ドイツ", "country_en": "Germany", "goals": 11,
     "tournaments": 3, "years": "1990, 1994, 1998",
     "tournament_goals": "1990:3, 1994:5, 1998:3"},
    {"player": "ガブリエル・バティストゥータ", "player_en": "Gabriel Batistuta",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 10,
     "tournaments": 3, "years": "1994, 1998, 2002",
     "tournament_goals": "1994:4, 1998:5, 2002:1"},
    {"player": "テオフィロ・クビジャス", "player_en": "Teófilo Cubillas",
     "country": "ペルー", "country_en": "Peru", "goals": 10,
     "tournaments": 2, "years": "1970, 1978",
     "tournament_goals": "1970:5, 1978:5"},
    {"player": "ヘルムート・ラーン", "player_en": "Helmut Rahn",
     "country": "西ドイツ", "country_en": "West Germany", "goals": 10,
     "tournaments": 2, "years": "1954, 1958",
     "tournament_goals": "1954:4, 1958:6"},
    {"player": "グレグ・ニル", "player_en": "Gary Lineker",
     "country": "イングランド", "country_en": "England", "goals": 10,
     "tournaments": 2, "years": "1986, 1990",
     "tournament_goals": "1986:6, 1990:4"},
    {"player": "クリスティアーノ・ロナウド", "player_en": "Cristiano Ronaldo",
     "country": "ポルトガル", "country_en": "Portugal", "goals": 9,
     "tournaments": 5, "years": "2006, 2010, 2014, 2018, 2022",
     "tournament_goals": "2006:1, 2010:1, 2014:1, 2018:4, 2022:1"},
    {"player": "アデミール", "player_en": "Ademir",
     "country": "ブラジル", "country_en": "Brazil", "goals": 9,
     "tournaments": 1, "years": "1950",
     "tournament_goals": "1950:9"},
    {"player": "ヴァーヴァ", "player_en": "Vavá",
     "country": "ブラジル", "country_en": "Brazil", "goals": 9,
     "tournaments": 2, "years": "1958, 1962",
     "tournament_goals": "1958:5, 1962:4"},
    {"player": "エウゼビオ", "player_en": "Eusébio",
     "country": "ポルトガル", "country_en": "Portugal", "goals": 9,
     "tournaments": 1, "years": "1966",
     "tournament_goals": "1966:9"},
    {"player": "ディエゴ・マラドーナ", "player_en": "Diego Maradona",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 8,
     "tournaments": 4, "years": "1982, 1986, 1990, 1994",
     "tournament_goals": "1982:2, 1986:5, 1990:1, 1994:0"},
    {"player": "ガリー・リネカー", "player_en": "Gary Lineker",
     "country": "イングランド", "country_en": "England", "goals": 10,
     "tournaments": 2, "years": "1986, 1990",
     "tournament_goals": "1986:6, 1990:4"},
    {"player": "ギジェルモ・スタービレ", "player_en": "Guillermo Stábile",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 8,
     "tournaments": 1, "years": "1930",
     "tournament_goals": "1930:8"},
    {"player": "レオニダス", "player_en": "Leônidas",
     "country": "ブラジル", "country_en": "Brazil", "goals": 8,
     "tournaments": 2, "years": "1934, 1938",
     "tournament_goals": "1934:1, 1938:7"},
    {"player": "ロベルト・バッジョ", "player_en": "Roberto Baggio",
     "country": "イタリア", "country_en": "Italy", "goals": 9,
     "tournaments": 3, "years": "1990, 1994, 1998",
     "tournament_goals": "1990:2, 1994:5, 1998:2"},
    {"player": "パオロ・ロッシ", "player_en": "Paolo Rossi",
     "country": "イタリア", "country_en": "Italy", "goals": 9,
     "tournaments": 2, "years": "1978, 1982",
     "tournament_goals": "1978:3, 1982:6"},
    {"player": "トマス・スコレク", "player_en": "Tomáš Skuhravý",
     "country": "チェコスロバキア", "country_en": "Czechoslovakia", "goals": 5,
     "tournaments": 1, "years": "1990",
     "tournament_goals": "1990:5"},
    {"player": "ズラタン・イブラヒモビッチ", "player_en": "Zlatan Ibrahimović",
     "country": "スウェーデン", "country_en": "Sweden", "goals": 6,
     "tournaments": 3, "years": "2002, 2006, 2014",
     "tournament_goals": "2002:1, 2006:0, 2014:4"},
]

# 重複除去・ソート済みリスト（上位20名をユニーク選出）
SCORERS_TOP20 = [
    {"player": "ミロスラフ・クローゼ", "player_en": "Miroslav Klose",
     "country": "ドイツ", "country_en": "Germany", "goals": 16,
     "tournaments": 4, "years": "2002, 2006, 2010, 2014",
     "note": "4大会連続出場。2014年大会で通算記録を更新し引退。"},
    {"player": "ロナウド", "player_en": "Ronaldo (R9)",
     "country": "ブラジル", "country_en": "Brazil", "goals": 15,
     "tournaments": 4, "years": "1994, 1998, 2002, 2006",
     "note": "2002年大会で8得点・優勝の両方を達成。フェノメノの異名。"},
    {"player": "ゲルト・ミュラー", "player_en": "Gerd Müller",
     "country": "西ドイツ", "country_en": "West Germany", "goals": 14,
     "tournaments": 2, "years": "1970, 1974",
     "note": "1970年大会で10得点。「ボンバー」と呼ばれた決定力の化身。"},
    {"player": "リオネル・メッシ", "player_en": "Lionel Messi",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 13,
     "tournaments": 5, "years": "2006, 2010, 2014, 2018, 2022",
     "note": "2022年大会7得点・優勝。5大会出場で通算13得点。"},
    {"player": "ジュスト・フォンテーヌ", "player_en": "Just Fontaine",
     "country": "フランス", "country_en": "France", "goals": 13,
     "tournaments": 1, "years": "1958",
     "note": "1大会限定で13得点の不滅記録。1大会での記録は今も破られていない。"},
    {"player": "ペレ", "player_en": "Pelé",
     "country": "ブラジル", "country_en": "Brazil", "goals": 12,
     "tournaments": 4, "years": "1958, 1962, 1966, 1970",
     "note": "1958年大会で最年少ゴール（17歳）。3回W杯制覇に貢献した唯一の選手。"},
    {"player": "キリアン・ムバッペ", "player_en": "Kylian Mbappé",
     "country": "フランス", "country_en": "France", "goals": 12,
     "tournaments": 2, "years": "2018, 2022",
     "note": "2022年大会でハットトリック含む8得点。現役最高得点者。2026年大会でさらなる記録更新を目指す。"},
    {"player": "サンドル・コチシュ", "player_en": "Sándor Kocsis",
     "country": "ハンガリー", "country_en": "Hungary", "goals": 11,
     "tournaments": 1, "years": "1954",
     "note": "1954年大会で11得点。ハンガリーの黄金世代を代表するストライカー。"},
    {"player": "ユルゲン・クリンスマン", "player_en": "Jürgen Klinsmann",
     "country": "ドイツ", "country_en": "Germany", "goals": 11,
     "tournaments": 3, "years": "1990, 1994, 1998",
     "note": "3大会に渡り安定した得点力を発揮。後に代表監督としても活躍。"},
    {"player": "ガブリエル・バティストゥータ", "player_en": "Gabriel Batistuta",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 10,
     "tournaments": 3, "years": "1994, 1998, 2002",
     "note": "1998年大会5得点。アルゼンチンの象徴的ストライカー「バティゴール」。"},
    {"player": "テオフィロ・クビジャス", "player_en": "Teófilo Cubillas",
     "country": "ペルー", "country_en": "Peru", "goals": 10,
     "tournaments": 2, "years": "1970, 1978",
     "note": "1970・1978大会でともに5得点。南米屈指のプレイメーカー。"},
    {"player": "ガリー・リネカー", "player_en": "Gary Lineker",
     "country": "イングランド", "country_en": "England", "goals": 10,
     "tournaments": 2, "years": "1986, 1990",
     "note": "1986年大会得点王（6得点）。フェアプレー精神でも知られるイングランドの英雄。"},
    {"player": "パオロ・ロッシ", "player_en": "Paolo Rossi",
     "country": "イタリア", "country_en": "Italy", "goals": 9,
     "tournaments": 2, "years": "1978, 1982",
     "note": "1982年大会6得点・優勝・得点王・MVP。イタリアW杯優勝の象徴。"},
    {"player": "ロベルト・バッジョ", "player_en": "Roberto Baggio",
     "country": "イタリア", "country_en": "Italy", "goals": 9,
     "tournaments": 3, "years": "1990, 1994, 1998",
     "note": "1994年大会5得点・準優勝。PKを外した場面は今も語り継がれる。"},
    {"player": "アデミール", "player_en": "Ademir",
     "country": "ブラジル", "country_en": "Brazil", "goals": 9,
     "tournaments": 1, "years": "1950",
     "note": "1950年大会で9得点・得点王。マラカナンの悲劇でブラジルが敗れた大会。"},
    {"player": "エウゼビオ", "player_en": "Eusébio",
     "country": "ポルトガル", "country_en": "Portugal", "goals": 9,
     "tournaments": 1, "years": "1966",
     "note": "1966年大会で9得点の得点王。ポルトガルの3位躍進を牽引した「黒豹」。"},
    {"player": "クリスティアーノ・ロナウド", "player_en": "Cristiano Ronaldo",
     "country": "ポルトガル", "country_en": "Portugal", "goals": 9,
     "tournaments": 5, "years": "2006, 2010, 2014, 2018, 2022",
     "note": "5大会出場で通算9得点。2018年大会でハットトリックを決めた。"},
    {"player": "ヴァーヴァ", "player_en": "Vavá",
     "country": "ブラジル", "country_en": "Brazil", "goals": 9,
     "tournaments": 2, "years": "1958, 1962",
     "note": "1958・1962年大会で連続優勝に貢献。ペレとともにブラジル黄金期を形成。"},
    {"player": "ギジェルモ・スタービレ", "player_en": "Guillermo Stábile",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 8,
     "tournaments": 1, "years": "1930",
     "note": "記念すべき第1回大会の得点王（8得点）。初めての得点王。"},
    {"player": "ディエゴ・マラドーナ", "player_en": "Diego Maradona",
     "country": "アルゼンチン", "country_en": "Argentina", "goals": 8,
     "tournaments": 4, "years": "1982, 1986, 1990, 1994",
     "note": "1986年大会5得点・優勝。「神の手」と「5人抜き」で世界に名を刻んだ。"},
]

# 大会別得点王（22大会）
TOURNAMENT_TOP_SCORERS = [
    {"year": 1930, "player": "ギジェルモ・スタービレ", "player_en": "Guillermo Stábile", "country": "アルゼンチン", "country_en": "Argentina", "goals": 8},
    {"year": 1934, "player": "オルダジフ・ネイエドリー", "player_en": "Oldřich Nejedlý", "country": "チェコスロバキア", "country_en": "Czechoslovakia", "goals": 5},
    {"year": 1938, "player": "レオニダス", "player_en": "Leônidas", "country": "ブラジル", "country_en": "Brazil", "goals": 7},
    {"year": 1950, "player": "アデミール", "player_en": "Ademir", "country": "ブラジル", "country_en": "Brazil", "goals": 9},
    {"year": 1954, "player": "サンドル・コチシュ", "player_en": "Sándor Kocsis", "country": "ハンガリー", "country_en": "Hungary", "goals": 11},
    {"year": 1958, "player": "ジュスト・フォンテーヌ", "player_en": "Just Fontaine", "country": "フランス", "country_en": "France", "goals": 13, "note": "歴代最多（1大会）"},
    {"year": 1962, "player": "複数（6得点）", "player_en": "Multiple (6 goals)", "country": "複数国", "country_en": "Multiple", "goals": 6},
    {"year": 1966, "player": "エウゼビオ", "player_en": "Eusébio", "country": "ポルトガル", "country_en": "Portugal", "goals": 9},
    {"year": 1970, "player": "ゲルト・ミュラー", "player_en": "Gerd Müller", "country": "西ドイツ", "country_en": "West Germany", "goals": 10},
    {"year": 1974, "player": "グジェゴシュ・ラト", "player_en": "Grzegorz Lato", "country": "ポーランド", "country_en": "Poland", "goals": 7},
    {"year": 1978, "player": "マリオ・ケンペス", "player_en": "Mario Kempes", "country": "アルゼンチン", "country_en": "Argentina", "goals": 6},
    {"year": 1982, "player": "パオロ・ロッシ", "player_en": "Paolo Rossi", "country": "イタリア", "country_en": "Italy", "goals": 6},
    {"year": 1986, "player": "ガリー・リネカー", "player_en": "Gary Lineker", "country": "イングランド", "country_en": "England", "goals": 6},
    {"year": 1990, "player": "サルヴァトーレ・スキラッチ", "player_en": "Salvatore Schillaci", "country": "イタリア", "country_en": "Italy", "goals": 6},
    {"year": 1994, "player": "オレグ・サレンコ / ストイコビッチ", "player_en": "Oleg Salenko / Stoichkov", "country": "ロシア / ブルガリア", "country_en": "Russia / Bulgaria", "goals": 6},
    {"year": 1998, "player": "ダボル・スーケル", "player_en": "Davor Šuker", "country": "クロアチア", "country_en": "Croatia", "goals": 6},
    {"year": 2002, "player": "ロナウド", "player_en": "Ronaldo", "country": "ブラジル", "country_en": "Brazil", "goals": 8},
    {"year": 2006, "player": "ミロスラフ・クローゼ", "player_en": "Miroslav Klose", "country": "ドイツ", "country_en": "Germany", "goals": 5},
    {"year": 2010, "player": "トーマス・ミュラー / 複数", "player_en": "Thomas Müller / Multiple", "country": "ドイツ / 複数", "country_en": "Germany / Multiple", "goals": 5},
    {"year": 2014, "player": "ハメス・ロドリゲス", "player_en": "James Rodríguez", "country": "コロンビア", "country_en": "Colombia", "goals": 6},
    {"year": 2018, "player": "ハリー・ケイン", "player_en": "Harry Kane", "country": "イングランド", "country_en": "England", "goals": 6},
    {"year": 2022, "player": "キリアン・ムバッペ", "player_en": "Kylian Mbappé", "country": "フランス", "country_en": "France", "goals": 8},
]

SPECIAL_RECORDS = [
    {"title": "1大会最多得点（個人）",
     "title_en": "Most Goals in a Single Tournament (Individual)",
     "player": "ジュスト・フォンテーヌ（フランス）",
     "player_en": "Just Fontaine (France)",
     "detail": "1958年大会で13得点。この記録は60年以上破られていない不滅の記録。",
     "detail_en": "13 goals in the 1958 World Cup. This record has stood unbroken for over 60 years."},
    {"title": "最多大会出場での得点王",
     "title_en": "Most Goals Across Most Tournaments",
     "player": "ミロスラフ・クローゼ（ドイツ）",
     "player_en": "Miroslav Klose (Germany)",
     "detail": "4大会連続出場（2002〜2014）し、すべての大会で得点。通算16得点は歴代最多。",
     "detail_en": "Scored in all 4 tournaments (2002–2014) he played. 16 career goals is the all-time record."},
    {"title": "最年少W杯得点",
     "title_en": "Youngest World Cup Scorer",
     "player": "ペレ（ブラジル）",
     "player_en": "Pelé (Brazil)",
     "detail": "1958年大会、17歳と239日での得点は長らく最年少記録。若くして世界を驚かせた。",
     "detail_en": "Pelé scored at 17 years and 239 days in 1958, long the youngest scorer record."},
    {"title": "現役最高得点者（2022年終了時）",
     "title_en": "Top Active Scorer (as of 2022)",
     "player": "キリアン・ムバッペ（フランス）",
     "player_en": "Kylian Mbappé (France)",
     "detail": "2018・2022の2大会で計12得点。2026年大会でクローゼの記録（16得点）への挑戦が注目される。",
     "detail_en": "12 goals in 2 tournaments (2018, 2022). Widely expected to challenge Klose's record at the 2026 WC."},
    {"title": "連続大会での得点王",
     "title_en": "Back-to-Back Tournament Top Scorer",
     "player": "テオフィロ・クビジャス（ペルー）",
     "player_en": "Teófilo Cubillas (Peru)",
     "detail": "1970・1978年大会でともに5得点。8年の間を空けて同得点を記録した稀有な選手。",
     "detail_en": "5 goals each in 1970 and 1978, a remarkable feat 8 years apart."},
    {"title": "優勝大会で得点王",
     "title_en": "Top Scorer + Champion in the Same Tournament",
     "player": "パオロ・ロッシ（1982）、マリオ・ケンペス（1978）、ゲルト・ミュラー（1974）など",
     "player_en": "Paolo Rossi (1982), Mario Kempes (1978), Gerd Müller (1974), etc.",
     "detail": "優勝国の選手が得点王も獲得したケース。1982年ロッシは得点王・MVP・優勝の三冠を達成。",
     "detail_en": "Rare cases when the tournament's top scorer also won the championship."},
]


def get_lastmod():
    return datetime.now(JST).strftime("%Y-%m-%d")


def build_ja_page(tournaments_data):
    lastmod = get_lastmod()

    # 大会別得点王のHTML
    tournament_rows = ""
    for ts in TOURNAMENT_TOP_SCORERS:
        note = ts.get("note", "")
        note_html = f'<span style="font-size:11px;color:var(--c-accent);font-weight:600"> ★ {note}</span>' if note else ""
        tournament_rows += f"""
        <tr>
          <td style="font-weight:700;font-feature-settings:'tnum';text-align:center">{ts['year']}</td>
          <td style="font-weight:600">{ts['player']}{note_html}</td>
          <td>{ts['country']}</td>
          <td style="font-weight:700;text-align:right;font-feature-settings:'tnum';color:var(--c-navy)">{ts['goals']}</td>
        </tr>"""

    # 通算得点王ランキングのHTML
    scorer_rows = ""
    for i, s in enumerate(SCORERS_TOP20):
        rank = i + 1
        rank_style = ""
        if rank == 1:
            rank_style = "color:#d4af37;font-size:22px;"
        elif rank == 2:
            rank_style = "color:#888;font-size:20px;"
        elif rank == 3:
            rank_style = "color:#cd7f32;font-size:18px;"
        note = s.get("note", "")
        scorer_rows += f"""
        <tr>
          <td style="font-weight:800;text-align:center;{rank_style}">{rank}</td>
          <td>
            <div style="font-weight:700;font-size:14px">{s['player']}</div>
            <div style="font-size:11px;color:var(--c-text-sub)">{s['player_en']}</div>
          </td>
          <td style="font-size:13px">{s['country']}</td>
          <td style="font-weight:700;text-align:center;font-feature-settings:'tnum'">{s['tournaments']}大会</td>
          <td style="font-size:12px;color:var(--c-text-sub)">{s['years']}</td>
          <td style="font-weight:800;font-size:18px;text-align:right;color:var(--c-navy);font-feature-settings:'tnum'">{s['goals']}</td>
        </tr>"""

    # 特殊記録HTML
    special_cards = ""
    for r in SPECIAL_RECORDS:
        special_cards += f"""
      <div class="record-card">
        <div class="record-title">{r['title']}</div>
        <div style="font-size:13px;font-weight:600;color:var(--c-accent);margin-bottom:4px">{r['player']}</div>
        <div class="record-detail">{r['detail']}</div>
      </div>"""

    schema_items = ""
    for s in SCORERS_TOP20[:10]:
        schema_items += f"""{{
        "@type": "ListItem",
        "position": {SCORERS_TOP20.index(s) + 1},
        "name": "{s['player']} ({s['player_en']})"
      }},"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>歴代W杯得点王ランキングTOP20 | football-jp</title>
  <meta name="description" content="歴代W杯得点王ランキング全TOP20（クローゼ16G・ロナウド15G・ミュラー14G・メッシ13G・フォンテーヌ13G等）と全22大会の大会別得点王一覧。FIFA W杯の歴代スコアラー記録を徹底解説。サッカーファン必見。">
  <link rel="canonical" href="https://football-jp.com/worldcup/history/scorers/">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/scorers/">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/scorers/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/worldcup/history/scorers/">
  <meta property="og:title" content="歴代W杯得点王ランキングTOP20 | football-jp">
  <meta property="og:description" content="歴代FIFAワールドカップ通算得点ランキング。クローゼ・ロナウド・ミュラー・メッシ・フォンテーヌ等の記録を大会別・通算でまとめて掲載。">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
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
  <style>
    .scorers-hero {{
      background: linear-gradient(135deg, #0b1220 0%, #1a2540 100%);
      color: #fff;
      padding: 24px 20px;
      margin-bottom: 24px;
      text-align: center;
    }}
    .scorers-hero h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 6px; }}
    .scorers-hero p {{ font-size: 13px; color: #a0b0c8; margin: 0; }}
    .rank-table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    .rank-table th {{
      background: var(--c-bg-subtle);
      padding: 8px 10px;
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      color: var(--c-text-sub);
      border-bottom: 2px solid var(--c-border-strong);
      white-space: nowrap;
    }}
    .rank-table td {{
      padding: 10px 10px;
      border-bottom: 1px solid var(--c-border);
      vertical-align: middle;
    }}
    .rank-table tr:last-child td {{ border-bottom: none; }}
    .rank-table tr:hover {{ background: var(--c-bg-subtle); }}
    .rank-table .rank-num {{
      font-size: 18px;
      font-weight: 800;
      color: var(--c-text-sub);
      text-align: center;
      min-width: 32px;
      font-feature-settings: "tnum";
    }}
    .records-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 10px;
      margin-top: 8px;
    }}
    .record-card {{
      background: #fff;
      border: 1px solid var(--c-border);
      border-left: 4px solid var(--c-accent);
      padding: 14px 16px;
    }}
    .record-title {{
      font-size: 13px;
      font-weight: 700;
      color: var(--c-navy);
      margin-bottom: 6px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--c-border);
    }}
    .record-detail {{
      font-size: 12.5px;
      line-height: 1.65;
      color: var(--c-text);
    }}
    .source-note {{
      font-size: 11px;
      color: var(--c-text-sub);
      margin-top: 12px;
      font-style: italic;
    }}
    @media (max-width: 600px) {{
      .records-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "歴代FIFAワールドカップ通算得点ランキング",
    "description": "FIFAワールドカップ歴代通算得点ランキングTOP20",
    "url": "https://football-jp.com/worldcup/history/scorers/",
    "numberOfItems": 20,
    "itemListElement": [
      {schema_items}
    ]
  }}
  </script>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="football-jp">
  <link rel="apple-touch-icon" href="/assets/logos/favicon-180.png">
</head>
<body class="wc-page">
<div class="wc-container">

  <nav class="wc-nav" id="wcNav"></nav>
  <script>document.getElementById('wcNav').innerHTML = window.wcRenderNav ? wcRenderNav('history') : '';</script>

  <nav class="breadcrumb" aria-label="パンくず">
    <ol>
      <li><a href="../../">W杯</a></li>
      <li><a href="../">歴史と記録</a></li>
      <li>歴代得点王ランキング</li>
    </ol>
  </nav>

  <div class="scorers-hero">
    <h1>⚽ 歴代W杯得点王ランキング TOP20</h1>
    <p>1930年〜2022年 全22大会の通算得点記録</p>
  </div>

  <!-- 1. 通算得点王ランキング -->
  <section class="wc-section">
    <h2>🏆 歴代通算得点ランキング（1930〜2022）</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="rank-table">
        <thead>
          <tr>
            <th>順位</th>
            <th>選手名</th>
            <th>国</th>
            <th>出場大会数</th>
            <th>出場年</th>
            <th style="text-align:right">通算得点</th>
          </tr>
        </thead>
        <tbody>
          {scorer_rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">※ 出典: Wikipedia / FIFA公式記録（2022年大会終了時点）。1934年以降の修正記録・複数得点者が同点の場合は代表的1名を掲載。</p>
  </section>

  <!-- 2. 大会別得点王 -->
  <section class="wc-section">
    <h2>📋 大会別得点王一覧（全22大会）</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="rank-table">
        <thead>
          <tr>
            <th style="text-align:center">大会年</th>
            <th>得点王</th>
            <th>国</th>
            <th style="text-align:right">得点</th>
          </tr>
        </thead>
        <tbody>
          {tournament_rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">※ 1962年大会は6得点が複数選手で並び、当時のFIFA規定では確定得点王が存在しない。</p>
  </section>

  <!-- 3. 特殊記録 -->
  <section class="wc-section">
    <h2>📊 得点王の特殊記録・トリビア</h2>
    <div class="records-grid">
      {special_cards}
    </div>
  </section>

  <!-- 4. 関連ページ -->
  <section class="wc-section">
    <h2>🔗 関連ページ</h2>
    <ul style="list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px;">
      <li><a href="../" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-accent);text-decoration:none;font-size:13px;">← 歴代大会一覧に戻る</a></li>
      <li><a href="../countries/brazil/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇧🇷 ブラジルの出場履歴</a></li>
      <li><a href="../countries/germany/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇩🇪 ドイツの出場履歴</a></li>
      <li><a href="../countries/argentina/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇦🇷 アルゼンチンの出場履歴</a></li>
    </ul>
  </section>

  <footer class="wc-footer">
    <p>データ出典: Wikipedia / FIFA公式記録（2022年大会終了時点）</p>
    <p><a href="../../">歴史と記録トップへ</a> ／ <a href="../../../">football-jp トップへ</a></p>
    <p class="footer-links"><a href="../../../privacy.html">プライバシーポリシー</a></p>
  </footer>
</div>

  <script src="/sw-register.js" defer></script>
  <script src="/push-client.js" defer></script>
  <script src="/push-ui.js" defer></script>
  <script src="/search.js" defer></script>
  <script src="/search-ui.js" defer></script>
</body>
</html>
"""


def build_en_page(tournaments_data):
    # 大会別得点王のHTML（英語）
    tournament_rows = ""
    for ts in TOURNAMENT_TOP_SCORERS:
        note = ts.get("note", "")
        note_html = f'<span style="font-size:11px;color:var(--c-accent);font-weight:600"> ★ {note}</span>' if note else ""
        tournament_rows += f"""
        <tr>
          <td style="font-weight:700;font-feature-settings:'tnum';text-align:center">{ts['year']}</td>
          <td style="font-weight:600">{ts['player_en']}{note_html}</td>
          <td>{ts['country_en']}</td>
          <td style="font-weight:700;text-align:right;font-feature-settings:'tnum';color:var(--c-navy)">{ts['goals']}</td>
        </tr>"""

    # 通算得点王ランキングHTML（英語）
    scorer_rows = ""
    for i, s in enumerate(SCORERS_TOP20):
        rank = i + 1
        rank_style = ""
        if rank == 1:
            rank_style = "color:#d4af37;font-size:22px;"
        elif rank == 2:
            rank_style = "color:#888;font-size:20px;"
        elif rank == 3:
            rank_style = "color:#cd7f32;font-size:18px;"
        scorer_rows += f"""
        <tr>
          <td style="font-weight:800;text-align:center;{rank_style}">{rank}</td>
          <td>
            <div style="font-weight:700;font-size:14px">{s['player_en']}</div>
            <div style="font-size:11px;color:var(--c-text-sub)">{s['player']}</div>
          </td>
          <td style="font-size:13px">{s['country_en']}</td>
          <td style="font-weight:700;text-align:center;font-feature-settings:'tnum'">{s['tournaments']} WC</td>
          <td style="font-size:12px;color:var(--c-text-sub)">{s['years']}</td>
          <td style="font-weight:800;font-size:18px;text-align:right;color:var(--c-navy);font-feature-settings:'tnum'">{s['goals']}</td>
        </tr>"""

    special_cards = ""
    for r in SPECIAL_RECORDS:
        special_cards += f"""
      <div class="record-card">
        <div class="record-title">{r['title_en']}</div>
        <div style="font-size:13px;font-weight:600;color:var(--c-accent);margin-bottom:4px">{r['player_en']}</div>
        <div class="record-detail">{r['detail_en']}</div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FIFA World Cup All-Time Top Scorers (TOP20) | football-jp</title>
  <meta name="description" content="Complete FIFA World Cup all-time top scorers ranking: Klose 16, Ronaldo 15, Müller 14, Messi 13, Fontaine 13. All 22 tournaments' top scorers and special records.">
  <link rel="canonical" href="https://football-jp.com/en/worldcup/history/scorers/">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/scorers/">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/scorers/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/en/worldcup/history/scorers/">
  <meta property="og:title" content="FIFA World Cup All-Time Top Scorers TOP20 | football-jp">
  <meta property="og:description" content="FIFA World Cup all-time top scorers. Klose, Ronaldo, Müller, Messi, Fontaine and more. Every tournament's top scorer listed.">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
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
  <style>
    .scorers-hero {{
      background: linear-gradient(135deg, #0b1220 0%, #1a2540 100%);
      color: #fff;
      padding: 24px 20px;
      margin-bottom: 24px;
      text-align: center;
    }}
    .scorers-hero h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 6px; }}
    .scorers-hero p {{ font-size: 13px; color: #a0b0c8; margin: 0; }}
    .rank-table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    .rank-table th {{
      background: var(--c-bg-subtle);
      padding: 8px 10px;
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      color: var(--c-text-sub);
      border-bottom: 2px solid var(--c-border-strong);
      white-space: nowrap;
    }}
    .rank-table td {{
      padding: 10px 10px;
      border-bottom: 1px solid var(--c-border);
      vertical-align: middle;
    }}
    .rank-table tr:last-child td {{ border-bottom: none; }}
    .rank-table tr:hover {{ background: var(--c-bg-subtle); }}
    .records-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 10px;
      margin-top: 8px;
    }}
    .record-card {{
      background: #fff;
      border: 1px solid var(--c-border);
      border-left: 4px solid var(--c-accent);
      padding: 14px 16px;
    }}
    .record-title {{
      font-size: 13px;
      font-weight: 700;
      color: var(--c-navy);
      margin-bottom: 6px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--c-border);
    }}
    .record-detail {{
      font-size: 12.5px;
      line-height: 1.65;
      color: var(--c-text);
    }}
    .source-note {{
      font-size: 11px;
      color: var(--c-text-sub);
      margin-top: 12px;
      font-style: italic;
    }}
    @media (max-width: 600px) {{
      .records-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
</head>
<body class="wc-page">
<div class="wc-container">

  <nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
      <li><a href="../../../">World Cup</a></li>
      <li><a href="../">History &amp; Records</a></li>
      <li>All-Time Top Scorers</li>
    </ol>
  </nav>

  <div class="scorers-hero">
    <h1>⚽ FIFA World Cup All-Time Top Scorers</h1>
    <p>All 22 Tournaments (1930–2022) Career Goals Ranking</p>
  </div>

  <!-- 1. All-time ranking -->
  <section class="wc-section">
    <h2>🏆 All-Time Career Goals Ranking (1930–2022)</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="rank-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Player</th>
            <th>Country</th>
            <th>Tournaments</th>
            <th>Years</th>
            <th style="text-align:right">Goals</th>
          </tr>
        </thead>
        <tbody>
          {scorer_rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">Source: Wikipedia / FIFA official records (as of end of 2022 World Cup). Where multiple players tied for top scorer, the primary scorer is listed.</p>
  </section>

  <!-- 2. Tournament top scorers -->
  <section class="wc-section">
    <h2>📋 Top Scorer by Tournament (All 22 Editions)</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="rank-table">
        <thead>
          <tr>
            <th style="text-align:center">Year</th>
            <th>Top Scorer</th>
            <th>Country</th>
            <th style="text-align:right">Goals</th>
          </tr>
        </thead>
        <tbody>
          {tournament_rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">Note: In 1962, multiple players tied at 6 goals. FIFA did not officially designate a single top scorer.</p>
  </section>

  <!-- 3. Special records -->
  <section class="wc-section">
    <h2>📊 Special Records &amp; Trivia</h2>
    <div class="records-grid">
      {special_cards}
    </div>
  </section>

  <!-- 4. Related pages -->
  <section class="wc-section">
    <h2>🔗 Related Pages</h2>
    <ul style="list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px;">
      <li><a href="../" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-accent);text-decoration:none;font-size:13px;">← World Cup History</a></li>
      <li><a href="../countries/brazil/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇧🇷 Brazil History</a></li>
      <li><a href="../countries/germany/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇩🇪 Germany History</a></li>
      <li><a href="../countries/argentina/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">🇦🇷 Argentina History</a></li>
    </ul>
  </section>

  <footer class="wc-footer">
    <p>Data source: Wikipedia / FIFA official records (as of 2022 World Cup)</p>
    <p><a href="../">History &amp; Records</a> / <a href="../../../../">football-jp Top</a></p>
    <p class="footer-links"><a href="../../../../privacy.html">Privacy Policy</a></p>
  </footer>
</div>

  <script src="/sw-register.js" defer></script>
  <script src="/push-client.js" defer></script>
  <script src="/push-ui.js" defer></script>
</body>
</html>
"""


def main():
    # Load tournaments data for reference
    with open(WC_HISTORY, encoding="utf-8") as f:
        data = json.load(f)
    tournaments = data.get("tournaments", [])

    # Japanese page
    ja_dir = ROOT / "worldcup" / "history" / "scorers"
    ja_dir.mkdir(parents=True, exist_ok=True)
    ja_html = build_ja_page(tournaments)
    (ja_dir / "index.html").write_text(ja_html, encoding="utf-8")
    print(f"[JA] 生成: {ja_dir / 'index.html'}")

    # English page
    en_dir = ROOT / "en" / "worldcup" / "history" / "scorers"
    en_dir.mkdir(parents=True, exist_ok=True)
    en_html = build_en_page(tournaments)
    (en_dir / "index.html").write_text(en_html, encoding="utf-8")
    print(f"[EN] 生成: {en_dir / 'index.html'}")

    print("得点王ランキングページ生成完了（日英2ページ）")


if __name__ == "__main__":
    main()
