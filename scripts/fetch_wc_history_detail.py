#!/usr/bin/env python3.13
"""
fetch_wc_history_detail.py
日本代表出場7大会（1998/2002/2006/2010/2014/2018/2022）の
WikipediaのグループページからW杯詳細データを取得してJSONに保存する。

出力: data/wc2026/wc_history_detail/{year}.json
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "wc2026" / "wc_history_detail"
DATA.mkdir(parents=True, exist_ok=True)

WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "football-jp scraper / 0.2 (saito@tottot.net)"
JST = timezone(timedelta(hours=9))

TARGET_YEARS = [
    1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966,
    1970, 1974, 1978, 1982, 1986, 1990, 1994,
    1998, 2002, 2006, 2010, 2014, 2018, 2022,
]

# 大会フォーマット区分
# "standard"   : 1994以降の32→16チーム標準ノックアウト
# "gs1990"     : 1990（24チーム・GS A-F）
# "gs2nd_1982" : 1982/1986（1次GS + 2次GS + ノックアウト）
# "round2_1974": 1974/1978（1次GS + 2次GS + 決勝・3位）
# "pool_1950"  : 1950（グループ + 最終ラウンドリーグ）
# "early"      : 1930-1938（トーナメント・小規模）
WC_FORMAT = {
    1930: "early", 1934: "early", 1938: "early",
    1950: "pool_1950",
    1954: "early_ko", 1958: "early_ko", 1962: "early_ko", 1966: "early_ko",
    1970: "early_ko",
    1974: "round2_1974", 1978: "round2_1974",
    1982: "gs2nd_1982", 1986: "gs2nd_1986",
    1990: "gs1990",
    1994: "standard",
    1998: "standard", 2002: "standard", 2006: "standard",
    2010: "standard", 2014: "standard", 2018: "standard", 2022: "standard",
}

# グループ数マッピング（各大会のグループ数）
WC_GROUPS = {
    1930: ["1", "2", "3", "4"],
    1934: [],  # トーナメント方式
    1938: [],  # トーナメント方式
    1950: ["1", "2", "3", "4"],
    1954: ["1", "2", "3", "4"],
    1958: ["1", "2", "3", "4"],
    1962: ["1", "2", "3", "4"],
    1966: ["1", "2", "3", "4"],
    1970: ["1", "2", "3", "4"],
    1974: ["1", "2", "3", "4"],
    1978: ["1", "2", "3", "4"],
    1982: list("ABCDEF"),
    1986: list("ABCDEF"),
    1990: list("ABCDEF"),
    1994: list("ABCD") + ["E", "F"],
    1998: list("ABCDEFGH"),
    2002: list("ABCDEFGH"),
    2006: list("ABCDEFGH"),
    2010: list("ABCDEFGH"),
    2014: list("ABCDEFGH"),
    2018: list("ABCDEFGH"),
    2022: list("ABCDEFGH"),
}

# 大会基本情報
WC_META = {
    1930: {"host": "ウルグアイ", "host_en": "Uruguay", "japan_group": None},
    1934: {"host": "イタリア", "host_en": "Italy", "japan_group": None},
    1938: {"host": "フランス", "host_en": "France", "japan_group": None},
    1950: {"host": "ブラジル", "host_en": "Brazil", "japan_group": None},
    1954: {"host": "スイス", "host_en": "Switzerland", "japan_group": None},
    1958: {"host": "スウェーデン", "host_en": "Sweden", "japan_group": None},
    1962: {"host": "チリ", "host_en": "Chile", "japan_group": None},
    1966: {"host": "イングランド", "host_en": "England", "japan_group": None},
    1970: {"host": "メキシコ", "host_en": "Mexico", "japan_group": None},
    1974: {"host": "西ドイツ", "host_en": "West Germany", "japan_group": None},
    1978: {"host": "アルゼンチン", "host_en": "Argentina", "japan_group": None},
    1982: {"host": "スペイン", "host_en": "Spain", "japan_group": None},
    1986: {"host": "メキシコ", "host_en": "Mexico", "japan_group": None},
    1990: {"host": "イタリア", "host_en": "Italy", "japan_group": None},
    1994: {"host": "アメリカ", "host_en": "United States", "japan_group": None},
    1998: {"host": "フランス", "host_en": "France", "japan_group": "H"},
    2002: {"host": "日本・韓国", "host_en": "Japan / South Korea", "japan_group": "H"},
    2006: {"host": "ドイツ", "host_en": "Germany", "japan_group": "F"},
    2010: {"host": "南アフリカ", "host_en": "South Africa", "japan_group": "E"},
    2014: {"host": "ブラジル", "host_en": "Brazil", "japan_group": "C"},
    2018: {"host": "ロシア", "host_en": "Russia", "japan_group": "H"},
    2022: {"host": "カタール", "host_en": "Qatar", "japan_group": "E"},
}

# FIFA 3文字コード → 英語国名（主要国）
FIFA_CODE_TO_EN = {
    "JPN": "Japan", "GER": "Germany", "ESP": "Spain",
    "ARG": "Argentina", "FRA": "France", "BRA": "Brazil",
    "NED": "Netherlands", "ENG": "England", "ITA": "Italy",
    "CRO": "Croatia", "POR": "Portugal", "BEL": "Belgium",
    "URU": "Uruguay", "POL": "Poland", "MEX": "Mexico",
    "USA": "United States", "KOR": "South Korea",
    "AUS": "Australia", "SAU": "Saudi Arabia", "IRN": "Iran",
    "ECU": "Ecuador", "SEN": "Senegal", "GHA": "Ghana",
    "MAR": "Morocco", "CMR": "Cameroon", "TUN": "Tunisia",
    "NGA": "Nigeria", "CIV": "Ivory Coast", "DEN": "Denmark",
    "SWE": "Sweden", "SUI": "Switzerland", "CZE": "Czech Republic",
    "SVK": "Slovakia", "RUS": "Russia", "UKR": "Ukraine",
    "TUR": "Turkey", "GRE": "Greece", "SRB": "Serbia",
    "SVN": "Slovenia", "PAR": "Paraguay", "COL": "Colombia",
    "CHI": "Chile", "CRC": "Costa Rica", "HON": "Honduras",
    "PAN": "Panama", "JAM": "Jamaica", "TRI": "Trinidad and Tobago",
    "CAN": "Canada", "ALG": "Algeria", "EGY": "Egypt",
    "RSA": "South Africa", "TOG": "Togo", "ANG": "Angola",
    "NZL": "New Zealand", "PRK": "North Korea", "IRQ": "Iraq",
    "QAT": "Qatar", "BIH": "Bosnia and Herzegovina",
    "HUN": "Hungary", "ROU": "Romania", "BUL": "Bulgaria",
    "NOR": "Norway", "SCO": "Scotland", "WAL": "Wales",
    "AUT": "Austria", "FIN": "Finland", "ISL": "Iceland",
    "LUX": "Luxembourg", "MDA": "Moldova", "GEO": "Georgia",
    "ARM": "Armenia", "AZE": "Azerbaijan", "KOS": "Kosovo",
    "MKD": "North Macedonia", "UZB": "Uzbekistan",
    "ARE": "United Arab Emirates", "PER": "Peru",
    "BOL": "Bolivia", "VEN": "Venezuela",
    "CUB": "Cuba", "HAI": "Haiti", "SLV": "El Salvador",
    "GUA": "Guatemala", "ZAM": "Zambia", "ZIM": "Zimbabwe",
    "LBA": "Libya", "SUD": "Sudan", "ETH": "Ethiopia",
    "KEN": "Kenya", "TAN": "Tanzania", "UGA": "Uganda",
    "MOZ": "Mozambique", "MAD": "Madagascar", "MLI": "Mali",
    "BFA": "Burkina Faso", "GUI": "Guinea", "BEN": "Benin",
    "NER": "Niger", "CHA": "Chad", "SOM": "Somalia",
    "RWA": "Rwanda", "BDI": "Burundi", "SLE": "Sierra Leone",
    "LBR": "Liberia", "GAM": "Gambia", "GNB": "Guinea-Bissau",
    "CPV": "Cape Verde", "IDN": "Indonesia", "THA": "Thailand",
    "VIE": "Vietnam", "MYA": "Myanmar", "PHI": "Philippines",
    "MAS": "Malaysia", "SGP": "Singapore", "CHN": "China",
    "MGL": "Mongolia", "KAZ": "Kazakhstan", "KGZ": "Kyrgyzstan",
    "TJK": "Tajikistan", "TKM": "Turkmenistan", "AFG": "Afghanistan",
    "PAK": "Pakistan", "IND": "India", "SRI": "Sri Lanka",
    "NEP": "Nepal", "BAN": "Bangladesh", "JOR": "Jordan",
    "LIB": "Lebanon", "SYR": "Syria", "OMA": "Oman",
    "KUW": "Kuwait", "BHR": "Bahrain", "YEM": "Yemen",
    "PLE": "Palestine", "ISR": "Israel", "CYP": "Cyprus",
    "FIJ": "Fiji", "PNG": "Papua New Guinea",
    "SOL": "Solomon Islands", "VAN": "Vanuatu",
    "SAM": "Samoa", "TGA": "Tonga", "TAH": "Tahiti",
    "CUR": "Curaçao", "SLO": "Slovenia",
    "MON": "Morocco", "DRC": "DR Congo",
}

# 英語→日本語チーム名変換辞書
TEAM_JA = {
    "Japan": "日本",
    "Germany": "ドイツ",
    "Spain": "スペイン",
    "Argentina": "アルゼンチン",
    "France": "フランス",
    "Brazil": "ブラジル",
    "Netherlands": "オランダ",
    "England": "イングランド",
    "Italy": "イタリア",
    "Croatia": "クロアチア",
    "Portugal": "ポルトガル",
    "Belgium": "ベルギー",
    "Uruguay": "ウルグアイ",
    "Poland": "ポーランド",
    "Mexico": "メキシコ",
    "United States": "アメリカ合衆国",
    "South Korea": "韓国",
    "Korea Republic": "韓国",
    "Australia": "オーストラリア",
    "Saudi Arabia": "サウジアラビア",
    "Iran": "イラン",
    "Ecuador": "エクアドル",
    "Senegal": "セネガル",
    "Ghana": "ガーナ",
    "Morocco": "モロッコ",
    "Cameroon": "カメルーン",
    "Tunisia": "チュニジア",
    "Nigeria": "ナイジェリア",
    "Ivory Coast": "コートジボワール",
    "Côte d'Ivoire": "コートジボワール",
    "Denmark": "デンマーク",
    "Sweden": "スウェーデン",
    "Switzerland": "スイス",
    "Czech Republic": "チェコ",
    "Slovakia": "スロバキア",
    "Russia": "ロシア",
    "Ukraine": "ウクライナ",
    "Turkey": "トルコ",
    "Greece": "ギリシャ",
    "Serbia": "セルビア",
    "Slovenia": "スロベニア",
    "Paraguay": "パラグアイ",
    "Colombia": "コロンビア",
    "Chile": "チリ",
    "Costa Rica": "コスタリカ",
    "Honduras": "ホンジュラス",
    "Panama": "パナマ",
    "Jamaica": "ジャマイカ",
    "Trinidad and Tobago": "トリニダード・トバゴ",
    "Canada": "カナダ",
    "Algeria": "アルジェリア",
    "Egypt": "エジプト",
    "South Africa": "南アフリカ",
    "Togo": "トーゴ",
    "Angola": "アンゴラ",
    "New Zealand": "ニュージーランド",
    "North Korea": "北朝鮮",
    "Iraq": "イラク",
    "Qatar": "カタール",
    "Bosnia and Herzegovina": "ボスニア・ヘルツェゴビナ",
    "Hungary": "ハンガリー",
    "Romania": "ルーマニア",
    "Bulgaria": "ブルガリア",
    "Norway": "ノルウェー",
    "Scotland": "スコットランド",
    "Wales": "ウェールズ",
    "Austria": "オーストリア",
    "Finland": "フィンランド",
    "Iceland": "アイスランド",
    "Cyprus": "キプロス",
    "Turkey": "トルコ",
    "Belarus": "ベラルーシ",
    "Albania": "アルバニア",
    "North Macedonia": "北マケドニア",
    "United Arab Emirates": "アラブ首長国連邦",
    "Peru": "ペルー",
    "Bolivia": "ボリビア",
    "Venezuela": "ベネズエラ",
    "Cuba": "キューバ",
    "Haiti": "ハイチ",
    "El Salvador": "エルサルバドル",
    "Guatemala": "グアテマラ",
    "DR Congo": "コンゴ民主共和国",
    "Curaçao": "キュラソー",
    "Cape Verde": "カーボベルデ",
    "China": "中国",
    "Indonesia": "インドネシア",
    "Thailand": "タイ",
    "Vietnam": "ベトナム",
    "Philippines": "フィリピン",
    "Malaysia": "マレーシア",
    "Singapore": "シンガポール",
    "Kazakhstan": "カザフスタン",
    "Uzbekistan": "ウズベキスタン",
    "Jordan": "ヨルダン",
    "Lebanon": "レバノン",
    "Syria": "シリア",
    "Oman": "オマーン",
    "Kuwait": "クウェート",
    "Bahrain": "バーレーン",
    "Yemen": "イエメン",
    "Palestine": "パレスチナ",
    "Israel": "イスラエル",
    "Fiji": "フィジー",
    "Tahiti": "タヒチ",
    "Turkey": "トルコ",
    "Bosnia-Herzegovina": "ボスニア・ヘルツェゴビナ",
}

# 日本代表出場試合の詳細（検証済みハードコードデータ）
JAPAN_MATCHES_HARDCODED = {
    1998: [
        {"date": "1998-06-14", "stage": "GS-1", "home_en": "Argentina", "away_en": "Japan", "home_score": 1, "away_score": 0, "japan_scorers": []},
        {"date": "1998-06-20", "stage": "GS-2", "home_en": "Japan", "away_en": "Croatia", "home_score": 0, "away_score": 1, "japan_scorers": []},
        {"date": "1998-06-26", "stage": "GS-3", "home_en": "Japan", "away_en": "Jamaica", "home_score": 1, "away_score": 2, "japan_scorers": ["中山雅史 74'"]},
    ],
    2002: [
        {"date": "2002-06-04", "stage": "GS-1", "home_en": "Japan", "away_en": "Belgium", "home_score": 2, "away_score": 2, "japan_scorers": ["鈴木隆行 59'", "稲本潤一 67'"]},
        {"date": "2002-06-09", "stage": "GS-2", "home_en": "Japan", "away_en": "Russia", "home_score": 1, "away_score": 0, "japan_scorers": ["稲本潤一 51'"]},
        {"date": "2002-06-14", "stage": "GS-3", "home_en": "Japan", "away_en": "Tunisia", "home_score": 2, "away_score": 0, "japan_scorers": ["森島寛晃 48'", "中田浩二 75'"]},
        {"date": "2002-06-18", "stage": "R16", "home_en": "Japan", "away_en": "Turkey", "home_score": 0, "away_score": 1, "japan_scorers": []},
    ],
    2006: [
        {"date": "2006-06-12", "stage": "GS-1", "home_en": "Australia", "away_en": "Japan", "home_score": 3, "away_score": 1, "japan_scorers": ["中村俊輔 26'"]},
        {"date": "2006-06-18", "stage": "GS-2", "home_en": "Japan", "away_en": "Croatia", "home_score": 0, "away_score": 0, "japan_scorers": []},
        {"date": "2006-06-22", "stage": "GS-3", "home_en": "Brazil", "away_en": "Japan", "home_score": 4, "away_score": 1, "japan_scorers": ["玉田圭司 34'"]},
    ],
    2010: [
        {"date": "2010-06-14", "stage": "GS-1", "home_en": "Japan", "away_en": "Cameroon", "home_score": 1, "away_score": 0, "japan_scorers": ["本田圭佑 39'"]},
        {"date": "2010-06-19", "stage": "GS-2", "home_en": "Netherlands", "away_en": "Japan", "home_score": 1, "away_score": 0, "japan_scorers": []},
        {"date": "2010-06-24", "stage": "GS-3", "home_en": "Japan", "away_en": "Denmark", "home_score": 3, "away_score": 1, "japan_scorers": ["本田圭佑 17'(FK)", "遠藤保仁 30'(FK)", "岡崎慎司 87'"]},
        {"date": "2010-06-29", "stage": "R16", "home_en": "Paraguay", "away_en": "Japan", "home_score": 0, "away_score": 0, "pk_score": "5-3", "japan_scorers": [], "note": "PK戦でパラグアイが勝利"},
    ],
    2014: [
        {"date": "2014-06-14", "stage": "GS-1", "home_en": "Japan", "away_en": "Ivory Coast", "home_score": 1, "away_score": 2, "japan_scorers": ["本田圭佑 16'"]},
        {"date": "2014-06-19", "stage": "GS-2", "home_en": "Japan", "away_en": "Greece", "home_score": 0, "away_score": 0, "japan_scorers": []},
        {"date": "2014-06-24", "stage": "GS-3", "home_en": "Colombia", "away_en": "Japan", "home_score": 4, "away_score": 1, "japan_scorers": ["岡崎慎司 45+1'"]},
    ],
    2018: [
        {"date": "2018-06-19", "stage": "GS-1", "home_en": "Japan", "away_en": "Colombia", "home_score": 2, "away_score": 1, "japan_scorers": ["香川真司 6'(PK)", "大迫勇也 73'"]},
        {"date": "2018-06-24", "stage": "GS-2", "home_en": "Senegal", "away_en": "Japan", "home_score": 2, "away_score": 2, "japan_scorers": ["乾貴士 34'", "本田圭佑 78'"]},
        {"date": "2018-06-28", "stage": "GS-3", "home_en": "Japan", "away_en": "Poland", "home_score": 0, "away_score": 1, "japan_scorers": []},
        {"date": "2018-07-02", "stage": "R16", "home_en": "Belgium", "away_en": "Japan", "home_score": 3, "away_score": 2, "japan_scorers": ["原口元気 48'", "乾貴士 52'"], "note": "ロストフの悲劇。2-0から逆転負け"},
    ],
    2022: [
        {"date": "2022-11-23", "stage": "GS-1", "home_en": "Germany", "away_en": "Japan", "home_score": 1, "away_score": 2, "japan_scorers": ["堂安律 75'", "浅野拓磨 83'"]},
        {"date": "2022-11-27", "stage": "GS-2", "home_en": "Japan", "away_en": "Costa Rica", "home_score": 0, "away_score": 1, "japan_scorers": []},
        {"date": "2022-12-01", "stage": "GS-3", "home_en": "Spain", "away_en": "Japan", "home_score": 1, "away_score": 2, "japan_scorers": ["堂安律 48'", "田中碧 51'"]},
        {"date": "2022-12-05", "stage": "R16", "home_en": "Japan", "away_en": "Croatia", "home_score": 1, "away_score": 1, "pk_score": "1-3", "japan_scorers": ["前田大然 43'"], "note": "PK戦でクロアチアが勝利"},
    ],
}

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def fetch_wikitext(page_title, retries=3):
    """WikipediaのAPIからページのwikitextを取得（リトライあり）。"""
    url = (f"{WIKI_API}?action=parse&page={quote(page_title)}"
           f"&prop=wikitext&format=json&formatversion=2&redirects=1")
    req = Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            if "error" in data:
                return None
            return data.get("parse", {}).get("wikitext", "")
        except (HTTPError, URLError) as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def fifa_code_to_en(code):
    """FIFA 3文字コードを英語国名に変換。"""
    return FIFA_CODE_TO_EN.get(code.upper(), code)


def to_ja(team_en):
    """英語チーム名→日本語変換。辞書にない場合は英語のまま返す。"""
    return TEAM_JA.get(team_en, team_en)


def parse_date_str(s):
    """各種形式の日付文字列を YYYY-MM-DD に変換。"""
    if not s:
        return None
    # {{Start date|YYYY|M|D}}
    m = re.search(r"\{\{[Ss]tart\s*date\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s.strip())
    if m:
        return s.strip()[:10]
    # DD Month YYYY
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s.strip())
    if m:
        day, mon, year = int(m.group(1)), m.group(2), int(m.group(3))
        if mon in MONTH_MAP:
            return f"{year:04d}-{MONTH_MAP[mon]:02d}-{day:02d}"
    return None


def strip_wiki_markup(s):
    """ウィキマークアップを除去してプレーンテキスト化。"""
    if not s:
        return ""
    s = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    return s.strip()


def extract_team_from_fb_template(field_value):
    """
    {{#invoke:Football box|...}} や {{fb|QAT}} 等のテンプレートから
    チーム名を抽出する。
    """
    # {{#invoke:flagg|main|...|QAT}} 形式
    m = re.search(r"\|\s*([A-Z]{2,3})\s*\}\}", field_value)
    if m:
        code = m.group(1)
        return fifa_code_to_en(code)

    # {{fb|QAT}} 形式
    m = re.search(r"\{\{fb(?:-rt|-xl|-sm)?\|([A-Z]{2,3})\}\}", field_value)
    if m:
        return fifa_code_to_en(m.group(1))

    # {{fb-rt|BRA}} 形式
    m = re.search(r"\{\{fb-rt\|([A-Z]{2,3})\}\}", field_value)
    if m:
        return fifa_code_to_en(m.group(1))

    # {{flagicon|Country}} Country 形式
    m = re.search(r"\{\{[Ff]lagicon\|([^}]+)\}\}\s*([^\n|{]+)", field_value)
    if m:
        return strip_wiki_markup(m.group(2)).strip()

    # プレーンテキスト（wikiリンクを除去）
    return strip_wiki_markup(field_value).strip()


def extract_score_from_template(score_field):
    """
    {{score link|...|2–1}} や 2–1 などからスコアを抽出する。
    """
    # {{score link|...|X–Y}} 形式
    m = re.search(r"\{\{score[ _]link\|[^|]+\|(\d+)[–\-](\d+)\}\}", score_field)
    if m:
        return int(m.group(1)), int(m.group(2))

    # X–Y (em dash or hyphen)
    m = re.search(r"(\d+)\s*[–\-]\s*(\d+)", score_field)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None


def parse_football_box_field(box_text, field):
    """football box テンプレートから特定フィールドの値を抽出。"""
    pat = rf"^\s*\|\s*{re.escape(field)}\s*=(.*?)(?=\n\s*\||\n\s*\}}\}})"
    m = re.search(pat, box_text, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract_scorers_from_goals_text(goals_text):
    """goals1/goals2 テキストからスコアラー情報を抽出。"""
    scorers = []
    for line in goals_text.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        line = line[1:].strip()
        # プレーヤー名を取得（ウィキリンクまたはプレーンテキスト）
        player_m = re.match(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]", line)
        if player_m:
            name = (player_m.group(2) or player_m.group(1)).strip()
        else:
            plain_m = re.match(r"([A-Za-zÀ-ÖØ-öø-ÿĀ-ž\s'\-\.]+?)(?=\s*\{\{|\s+\d+[''])", line)
            if plain_m:
                name = plain_m.group(1).strip()
            else:
                continue
        # ゴール時間を取得
        for goal_m in re.finditer(r"\{\{goal[^}]*\|([^}]+)\}\}", line):
            tokens = goal_m.group(1).split("|")
            for tok in tokens:
                tok = tok.strip()
                if re.match(r"^\d+\+?\d*$", tok):
                    scorers.append({"player": name, "minute": tok})
    return scorers


def parse_group_boxes(wikitext):
    """
    グループページのwikitextから {{Football box}} / {{#invoke:Football box|main}} を全て取得。
    team1/team2 の FIFA コードをチーム名に変換する。
    """
    results = []

    # パターン1: {{Football box\n|date=...\n|team1=...}}
    pattern1 = r"\{\{Football box\s*\n(.*?)\n\}\}"
    # パターン2: {{#invoke:Football box|main|section=...\n|date=...\n|team1=...}}
    pattern2 = r"\{\{#invoke:Football box\|main[^}]*?\n(.*?)\n\}\}"

    for pat in [pattern1, pattern2]:
        for m in re.finditer(pat, wikitext, re.DOTALL):
            box = m.group(1)

            date_raw = parse_football_box_field(box, "date")
            date = parse_date_str(date_raw)
            if not date:
                continue

            team1_raw = parse_football_box_field(box, "team1")
            team2_raw = parse_football_box_field(box, "team2")
            score_raw = parse_football_box_field(box, "score")
            goals1 = parse_football_box_field(box, "goals1")
            goals2 = parse_football_box_field(box, "goals2")

            team1_en = extract_team_from_fb_template(team1_raw) if team1_raw else ""
            team2_en = extract_team_from_fb_template(team2_raw) if team2_raw else ""
            score = extract_score_from_template(score_raw)

            home_score = score[0] if score else None
            away_score = score[1] if score else None

            # スコアラー情報
            match_scorers = []
            if goals1:
                for s in extract_scorers_from_goals_text(goals1):
                    match_scorers.append({"player": s["player"], "team": team1_en, "minute": s["minute"]})
            if goals2:
                for s in extract_scorers_from_goals_text(goals2):
                    match_scorers.append({"player": s["player"], "team": team2_en, "minute": s["minute"]})

            results.append({
                "date": date,
                "home_en": team1_en,
                "home_ja": to_ja(team1_en),
                "away_en": team2_en,
                "away_ja": to_ja(team2_en),
                "home_score": home_score,
                "away_score": away_score,
                "scorers": match_scorers,
            })

    return results


def parse_group_standings(wikitext):
    """
    Sports table テンプレートからグループ順位表を抽出。
    |team1=BRA|team2=NOR... |win_BRA=2 |draw_BRA=0... 形式。
    """
    # スポーツテーブルを探す
    table_pattern = r"\{\{#invoke:Sports table\|main(.*?)\}\}"
    m = re.search(table_pattern, wikitext, re.DOTALL)
    if not m:
        return []

    table_text = m.group(1)

    # team_order または team1, team2... からチームコード順序を取得
    order_m = re.search(r"\|team_order\s*=\s*([^\n|]+)", table_text)
    if order_m:
        codes = [c.strip() for c in order_m.group(1).split(",")]
    else:
        # team1=, team2=... を順番に取得
        codes = re.findall(r"\|team(\d+)\s*=\s*([A-Z]{2,3})", table_text)
        if codes:
            codes = [c[1] for c in sorted(codes, key=lambda x: int(x[0]))]
        else:
            return []

    rows = []
    for i, code in enumerate(codes):
        code = code.strip()
        if not code:
            continue
        win = int(re.search(rf"\|win_{code}\s*=\s*(\d+)", table_text).group(1)) if re.search(rf"\|win_{code}\s*=\s*(\d+)", table_text) else 0
        draw = int(re.search(rf"\|draw_{code}\s*=\s*(\d+)", table_text).group(1)) if re.search(rf"\|draw_{code}\s*=\s*(\d+)", table_text) else 0
        loss = int(re.search(rf"\|loss_{code}\s*=\s*(\d+)", table_text).group(1)) if re.search(rf"\|loss_{code}\s*=\s*(\d+)", table_text) else 0
        gf = int(re.search(rf"\|gf_{code}\s*=\s*(\d+)", table_text).group(1)) if re.search(rf"\|gf_{code}\s*=\s*(\d+)", table_text) else 0
        ga = int(re.search(rf"\|ga_{code}\s*=\s*(\d+)", table_text).group(1)) if re.search(rf"\|ga_{code}\s*=\s*(\d+)", table_text) else 0

        played = win + draw + loss
        pts = win * 3 + draw
        team_en = fifa_code_to_en(code)

        rows.append({
            "position": i + 1,
            "team_en": team_en,
            "team_ja": to_ja(team_en),
            "played": played,
            "won": win,
            "drawn": draw,
            "lost": loss,
            "goals_for": gf,
            "goals_against": ga,
            "points": pts,
        })

    return rows


def parse_external_group_tables_template(template_wikitext, group_id):
    """
    {{YYYY FIFA World Cup group tables}} テンプレートのwikitextから
    特定グループの順位表を抽出する（2022年等の特殊対応）。
    """
    # |Group X= セクションを取得
    pat = rf"\|Group {group_id}=(.*?)(?=\|Group [A-H]=|\Z)"
    m = re.search(pat, template_wikitext, re.DOTALL)
    if not m:
        return []
    return parse_group_standings(m.group(1))


def fetch_group_data(year, group_id):
    """特定の年・グループのデータをWikipediaから取得。"""
    # 1930-1970年は "Group N" (数字)、1974以降はアルファベット
    if str(group_id).isdigit():
        page_title = f"{year}_FIFA_World_Cup_Group_{group_id}"
    else:
        page_title = f"{year}_FIFA_World_Cup_Group_{group_id}"

    wikitext = fetch_wikitext(page_title)
    if not wikitext:
        # 古い大会の別ページタイトル試行
        alt_titles = [
            f"{year}_FIFA_World_Cup_group_{group_id}",
            f"{year}_FIFA_World_Cup_groups",
        ]
        for alt in alt_titles:
            wikitext = fetch_wikitext(alt)
            if wikitext:
                break
        if not wikitext:
            return None

    table = parse_group_standings(wikitext)

    # テーブルが取れなかった場合は外部テンプレートページから取得
    if not table:
        template_title = f"Template:{year}_FIFA_World_Cup_group_tables"
        tmpl_wt = fetch_wikitext(template_title)
        if tmpl_wt:
            table = parse_external_group_tables_template(tmpl_wt, group_id)
            time.sleep(0.5)

    matches = parse_group_boxes(wikitext)

    # グループ名（数字の場合も対応）
    if str(group_id).isdigit():
        name_ja = f"グループ{group_id}"
    else:
        name_ja = f"グループ{group_id}"

    return {
        "group_id": str(group_id),
        "name_ja": name_ja,
        "table": table,
        "matches": matches,
    }


def fetch_1950_final_round():
    """1950年の最終ラウンドリーグ戦データを取得。"""
    page_title = "1950_FIFA_World_Cup_Final_Round"
    wikitext = fetch_wikitext(page_title)
    if not wikitext:
        return None

    table = parse_group_standings(wikitext)
    matches = parse_group_boxes(wikitext)

    return {
        "group_id": "final_round",
        "name_ja": "最終ラウンド（リーグ戦）",
        "table": table,
        "matches": matches,
    }


def fetch_second_group_stage(year, group_ids):
    """1974/1978/1982/1986の2次グループステージデータを取得。"""
    groups = []
    for gid in group_ids:
        page_title = f"{year}_FIFA_World_Cup_second_group_stage"
        wikitext = fetch_wikitext(page_title)
        if not wikitext:
            alt_titles = [
                f"{year}_FIFA_World_Cup_second_round",
                f"{year}_FIFA_World_Cup_Second_round",
                f"{year}_FIFA_World_Cup_second_group_stage_Group_{gid}",
            ]
            for alt in alt_titles:
                wikitext = fetch_wikitext(alt)
                if wikitext:
                    break
        if not wikitext:
            continue

        # ページ内の特定グループ部分を取り出す
        matches = parse_group_boxes(wikitext)
        table = parse_group_standings(wikitext)

        groups.append({
            "group_id": f"2nd_{gid}",
            "name_ja": f"2次グループ{gid}",
            "table": table,
            "matches": matches,
        })
        time.sleep(0.5)
        break  # 同一ページなので1回で十分

    return groups


def parse_knockout_boxes(wikitext, section_names):
    """決勝トーナメントのセクションから試合データを抽出。"""
    for section_name in section_names:
        # == から ==== まで全パターンを試す
        patterns = [
            rf"==\s*{re.escape(section_name)}\s*==(?!=)",
            rf"===\s*{re.escape(section_name)}\s*===(?!=)",
            rf"====\s*{re.escape(section_name)}\s*====(?!=)",
        ]
        section_start = -1
        for pat in patterns:
            m = re.search(pat, wikitext, re.IGNORECASE)
            if m:
                section_start = m.start()
                break
        if section_start < 0:
            continue

        # セクション終端（同レベル以上のヘッダーまで）
        next_m = re.search(r"^==+[^=]", wikitext[section_start+5:], re.MULTILINE)
        if next_m:
            section_text = wikitext[section_start:section_start+5+next_m.start()]
        else:
            section_text = wikitext[section_start:section_start+30000]

        matches = parse_group_boxes(section_text)
        if matches:
            return matches

    return []


def fetch_knockout_data(year):
    """決勝トーナメントデータを取得。"""
    page_title = f"{year}_FIFA_World_Cup_knockout_stage"
    wikitext = fetch_wikitext(page_title)
    if not wikitext:
        # 古い大会用フォールバック
        alt_titles = [
            f"{year}_FIFA_World_Cup_Final",
            f"{year}_FIFA_World_Cup",
        ]
        for alt in alt_titles:
            wikitext = fetch_wikitext(alt)
            if wikitext:
                break
        if not wikitext:
            return {}

    time.sleep(0.5)

    # 大会年代により試合ラウンド名が異なる
    if year <= 1938:
        round_sections = {
            "quarter_finals": ["Quarter-finals", "Quarter finals", "Quarterfinal", "First round"],
            "semi_finals": ["Semi-finals", "Semi finals", "Semifinal"],
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match", "Third place"],
            "final": ["Final"],
        }
    elif year == 1950:
        # 1950は決勝ラウンドリーグ戦（finalなし）
        return {}
    elif year in [1954, 1958, 1962, 1966, 1970]:
        round_sections = {
            "quarter_finals": ["Quarter-finals", "Quarter finals", "Quarterfinal"],
            "semi_finals": ["Semi-finals", "Semi finals", "Semifinal"],
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match", "Third place"],
            "final": ["Final"],
        }
    elif year in [1974, 1978]:
        # 2次グループ制のため、ここでは決勝・3位決定戦のみ
        round_sections = {
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match"],
            "final": ["Final"],
        }
    elif year in [1982, 1986]:
        # 1982/1986: 2次GS + 準決勝・決勝
        round_sections = {
            "semi_finals": ["Semi-finals", "Semi finals", "Semifinal"],
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match"],
            "final": ["Final"],
        }
    elif year == 1990:
        round_sections = {
            "round_of_16": ["Round of 16", "Second round", "Round of sixteen"],
            "quarter_finals": ["Quarter-finals", "Quarter finals", "Quarterfinals"],
            "semi_finals": ["Semi-finals", "Semi finals", "Semifinals"],
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match"],
            "final": ["Final"],
        }
    else:
        round_sections = {
            "round_of_16": ["Round of 16", "Second round", "Round of sixteen"],
            "quarter_finals": ["Quarter-finals", "Quarter finals", "Quarterfinals"],
            "semi_finals": ["Semi-finals", "Semi finals", "Semifinals"],
            "third_place": ["Third-place play-off", "Third place play-off", "Third place match"],
            "final": ["Final"],
        }

    knockout = {}
    for round_key, section_names in round_sections.items():
        matches = parse_knockout_boxes(wikitext, section_names)
        if round_key == "final":
            knockout[round_key] = matches[0] if matches else {}
        else:
            knockout[round_key] = matches

    return knockout


def fetch_year_data(year):
    """特定の年のW杯詳細データを取得してdictで返す。"""
    print(f"\n[{year}] データ取得開始")
    meta = WC_META.get(year, {})
    fmt = WC_FORMAT.get(year, "standard")
    group_ids = WC_GROUPS.get(year, list("ABCDEFGH"))
    groups = []

    # グループステージ取得
    for gid in group_ids:
        print(f"  [GS-{gid}] グループ{gid}を取得中...")
        try:
            group_data = fetch_group_data(year, gid)
            if group_data:
                groups.append(group_data)
                m_count = len(group_data.get("matches", []))
                t_count = len(group_data.get("table", []))
                print(f"  [GS-{gid}] OK: テーブル{t_count}チーム / {m_count}試合")
            else:
                print(f"  [GS-{gid}] 取得失敗")
        except Exception as e:
            print(f"  [GS-{gid}] エラー: {e}")
        time.sleep(1.0)

    # 1950年の最終ラウンドリーグ戦
    final_round_data = None
    if fmt == "pool_1950":
        print(f"  [1950FR] 最終ラウンドを取得中...")
        try:
            final_round_data = fetch_1950_final_round()
            if final_round_data:
                print(f"  [1950FR] OK: {len(final_round_data.get('matches',[]))}試合")
        except Exception as e:
            print(f"  [1950FR] エラー: {e}")
        time.sleep(1.0)

    print(f"  [KO] 決勝トーナメントを取得中...")
    try:
        knockout = fetch_knockout_data(year)
    except Exception as e:
        print(f"  [KO] エラー: {e}")
        knockout = {}
    print(f"  [KO] 完了")
    time.sleep(1.0)

    # 日本代表試合データ
    japan_matches_raw = JAPAN_MATCHES_HARDCODED.get(year, [])
    japan_matches = []
    for m in japan_matches_raw:
        entry = {
            "date": m["date"],
            "stage": m["stage"],
            "home_en": m["home_en"],
            "home_ja": to_ja(m["home_en"]),
            "away_en": m["away_en"],
            "away_ja": to_ja(m["away_en"]),
            "home_score": m["home_score"],
            "away_score": m["away_score"],
            "japan_scorers": m.get("japan_scorers", []),
        }
        if m.get("pk_score"):
            entry["pk_score"] = m["pk_score"]
        if m.get("note"):
            entry["note"] = m["note"]
        japan_matches.append(entry)

    result = {
        "year": year,
        "host": meta.get("host", ""),
        "host_en": meta.get("host_en", ""),
        "japan_group": meta.get("japan_group"),
        "format": fmt,
        "groups": groups,
        "knockout": knockout,
        "japan_matches": japan_matches,
        "_source": "Wikipedia",
        "_updated": datetime.now(JST).strftime("%Y-%m-%d"),
    }

    # 1950年の最終ラウンドを追加
    if final_round_data:
        result["final_round"] = final_round_data

    return result


def main():
    print(f"[INFO] W杯詳細データ取得開始（対象: {TARGET_YEARS}）")
    total_groups = 0
    total_matches = 0
    success_years = []

    for year in TARGET_YEARS:
        output_path = DATA / f"{year}.json"

        # 既存データ確認（グループ試合があれば再利用）
        if output_path.exists():
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            gs_total = sum(len(g.get("matches", [])) for g in existing.get("groups", []))
            if gs_total > 10:
                print(f"[SKIP] {year}: 既存データあり（{len(existing.get('groups',[]))}グループ / {gs_total}試合）")
                total_groups += len(existing.get("groups", []))
                total_matches += gs_total
                success_years.append(year)
                continue

        data = fetch_year_data(year)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[SAVED] {output_path}")

        g_count = len(data["groups"])
        m_count = sum(len(g.get("matches", [])) for g in data["groups"])
        total_groups += g_count
        total_matches += m_count
        success_years.append(year)

        time.sleep(2.0)

    print(f"\n[DONE] 完了: {len(success_years)}/{len(TARGET_YEARS)} 大会")
    print(f"  グループ数: {total_groups}")
    print(f"  GS試合数: {total_matches}")
    print(f"  成功大会: {success_years}")


if __name__ == "__main__":
    main()
