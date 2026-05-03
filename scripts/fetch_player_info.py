#!/usr/bin/env python3
"""
fetch_player_info.py
Wikipedia 英語版 infobox から選手プロフィール情報を取得する。
Wikipedia 日本語版が存在する場合は日本語版を優先して取得し、
_ja サフィックス付きフィールドに日本語情報を追加する。
入力: data/players.json
出力: data/player_info.json
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict

REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
OUTPUT_JSON = REPO_ROOT / "data" / "player_info.json"

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_JA_API = "https://ja.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "football-jp/1.0 (https://football-jp.com; contact@football-jp.com)"}

# ========== 翻訳辞書 ==========

COUNTRY_TRANSLATIONS = {
    "Japan": "日本",
    "England": "イングランド",
    "Germany": "ドイツ",
    "Spain": "スペイン",
    "Italy": "イタリア",
    "France": "フランス",
    "Netherlands": "オランダ",
    "Portugal": "ポルトガル",
    "Scotland": "スコットランド",
    "Belgium": "ベルギー",
    "Brazil": "ブラジル",
    "Argentina": "アルゼンチン",
    "United States": "アメリカ",
    "Australia": "オーストラリア",
    "South Korea": "韓国",
    "China": "中国",
    "Sweden": "スウェーデン",
    "Denmark": "デンマーク",
    "Norway": "ノルウェー",
    "Switzerland": "スイス",
    "Austria": "オーストリア",
    "Turkey": "トルコ",
    "Russia": "ロシア",
    "Poland": "ポーランド",
    "Croatia": "クロアチア",
    "Serbia": "セルビア",
    "Ukraine": "ウクライナ",
    "Greece": "ギリシャ",
    "Czech Republic": "チェコ",
    "Slovakia": "スロバキア",
    "Hungary": "ハンガリー",
    "Romania": "ルーマニア",
    "Ireland": "アイルランド",
    "Wales": "ウェールズ",
    "Northern Ireland": "北アイルランド",
}

PREFECTURE_TRANSLATIONS = {
    "Tokyo": "東京都",
    "Osaka": "大阪府",
    "Kanagawa": "神奈川県",
    "Aichi": "愛知県",
    "Saitama": "埼玉県",
    "Chiba": "千葉県",
    "Hyōgo": "兵庫県",
    "Hyogo": "兵庫県",
    "Fukuoka": "福岡県",
    "Shizuoka": "静岡県",
    "Ibaraki": "茨城県",
    "Hiroshima": "広島県",
    "Miyagi": "宮城県",
    "Hokkaido": "北海道",
    "Kyoto": "京都府",
    "Nara": "奈良県",
    "Ōsaka": "大阪府",
    "Ōita": "大分県",
    "Oita": "大分県",
    "Gunma": "群馬県",
    "Tochigi": "栃木県",
    "Nagano": "長野県",
    "Niigata": "新潟県",
    "Okayama": "岡山県",
    "Kumamoto": "熊本県",
    "Kagoshima": "鹿児島県",
    "Nagasaki": "長崎県",
    "Okinawa": "沖縄県",
    "Mie": "三重県",
    "Saga": "佐賀県",
    "Miyazaki": "宮崎県",
    "Yamaguchi": "山口県",
    "Ehime": "愛媛県",
    "Kochi": "高知県",
    "Tokushima": "徳島県",
    "Kagawa": "香川県",
    "Shimane": "島根県",
    "Tottori": "鳥取県",
    "Yamagata": "山形県",
    "Akita": "秋田県",
    "Iwate": "岩手県",
    "Aomori": "青森県",
    "Fukushima": "福島県",
    "Fukui": "福井県",
    "Ishikawa": "石川県",
    "Toyama": "富山県",
    "Gifu": "岐阜県",
    "Shiga": "滋賀県",
    "Wakayama": "和歌山県",
    "Yamanashi": "山梨県",
    "Gumma": "群馬県",
    # 市名（独立した値として使われる場合）はここに書かない
    # city_pref_map で対応
}

# クラブ名翻訳（英語 → 日本語）
CLUB_TRANSLATIONS = {
    # プレミアリーグ
    "Brighton & Hove Albion": "ブライトン",
    "Brighton": "ブライトン",
    "Liverpool": "リバプール",
    "Chelsea": "チェルシー",
    "Arsenal": "アーセナル",
    "Manchester United": "マンチェスター・ユナイテッド",
    "Manchester City": "マンチェスター・シティ",
    "Tottenham Hotspur": "トッテナム",
    "Tottenham": "トッテナム",
    "Crystal Palace": "クリスタル・パレス",
    "Southampton": "サウサンプトン",
    "Brentford": "ブレントフォード",
    "West Ham United": "ウェストハム",
    "Everton": "エバートン",
    "Fulham": "フルアム",
    "Newcastle United": "ニューカッスル",
    "Aston Villa": "アストン・ヴィラ",
    "Leicester City": "レスター・シティ",
    "Wolverhampton Wanderers": "ウォルバーハンプトン",
    "Nottingham Forest": "ノッティンガム・フォレスト",
    "Leeds United": "リーズ・ユナイテッド",
    "Leeds": "リーズ・ユナイテッド",
    "Stoke City": "ストーク・シティ",
    "Blackburn Rovers": "ブラックバーン",
    "Blackburn": "ブラックバーン",
    "Birmingham City": "バーミンガム",
    "Birmingham": "バーミンガム",
    "Coventry City": "コヴェントリー",
    "Coventry": "コヴェントリー",
    "Hull City": "ハル・シティ",
    "Queens Park Rangers": "QPR",
    # ブンデスリーガ
    "Bayern Munich": "バイエルン・ミュンヘン",
    "Bayern München": "バイエルン・ミュンヘン",
    "Borussia Dortmund": "ドルトムント",
    "Bayer Leverkusen": "レバークーゼン",
    "RB Leipzig": "ライプツィヒ",
    "Eintracht Frankfurt": "フランクフルト",
    "SC Freiburg": "フライブルク",
    "Borussia Mönchengladbach": "ボルシアMG",
    "VfL Wolfsburg": "ヴォルフスブルク",
    "VfB Stuttgart": "シュトゥットガルト",
    "TSG Hoffenheim": "ホッフェンハイム",
    "Mainz 05": "マインツ",
    "Mainz": "マインツ",
    "FC Augsburg": "アウクスブルク",
    "Werder Bremen": "ブレーメン",
    "Werder Bremen II": "ブレーメンII",
    "Holstein Kiel": "ホルシュタイン・キール",
    "FC St. Pauli": "ザンクト・パウリ",
    "VfL Bochum": "ボーフム",
    "Fortuna Düsseldorf": "デュッセルドルフ",
    "Hannover 96": "ハノーファー96",
    "Schalke 04": "シャルケ04",
    "Arminia Bielefeld": "ビーレフェルト",
    "Hamburger SV": "ハンブルガーSV",
    # ラ・リーガ
    "Real Madrid": "レアル・マドリード",
    "Barcelona": "バルセロナ",
    "Atletico Madrid": "アトレティコ・マドリード",
    "Sevilla": "セビージャ",
    "Valencia": "バレンシア",
    "Villarreal": "ビジャレアル",
    "Real Sociedad": "レアル・ソシエダ",
    "Mallorca": "マジョルカ",
    "Getafe": "ヘタフェ",
    "Celta Vigo": "セルタ",
    "Athletic Club": "アスレティック・クラブ",
    "Betis": "ベティス",
    "Göztepe": "ギョズテペ",
    # セリエA
    "Juventus": "ユベントス",
    "Inter Milan": "インテル",
    "AC Milan": "ACミラン",
    "Napoli": "ナポリ",
    "Roma": "ローマ",
    "Lazio": "ラツィオ",
    "Fiorentina": "フィオレンティーナ",
    "Atalanta": "アタランタ",
    "Bologna": "ボローニャ",
    "Parma": "パルマ",
    # リーグアン
    "Paris Saint-Germain": "パリSG",
    "PSG": "パリSG",
    "Monaco": "ASモナコ",
    "Lyon": "リヨン",
    "Marseille": "マルセイユ",
    "Lille": "リール",
    "Strasbourg": "ストラスブール",
    "Strasbourg II": "ストラスブールII",
    "Stade de Reims": "スタッド・ランス",
    "Le Havre": "ル・アーヴル",
    # エールディビジ / オランダ
    "Ajax": "アヤックス",
    "Feyenoord": "フェイエノールト",
    "PSV": "PSVアイントホーフェン",
    "AZ Alkmaar": "AZアルクマール",
    "AZ": "AZアルクマール",
    "NEC Nijmegen": "NECナイメヘン",
    "Sparta Rotterdam": "スパルタ・ロッテルダム",
    "Groningen": "フローニンゲン",
    "FC Groningen": "フローニンゲン",
    "Twente": "トウェンテ",
    "Vitesse": "ビタッセ",
    "FC Volendam": "フォーレンダム",
    "Jong AZ": "ヨングAZ",
    # ポルトガル
    "Sporting CP": "スポルティングCP",
    "Benfica": "ベンフィカ",
    "Benfica B": "ベンフィカB",
    "Porto": "ポルト",
    "Gil Vicente": "ジル・ヴィセンテ",
    "Santa Clara": "サンタ・クララ",
    # ベルギー
    "Anderlecht": "アンデルレヒト",
    "Club Brugge": "クラブ・ブルージュ",
    "Genk": "ゲンク",
    "Gent": "ヘント",
    "Sint-Truiden": "シント＝トロイデン",
    "STVV": "シント＝トロイデン",
    "Royal Antwerp": "アントワープ",
    "Antwerp": "アントワープ",
    "Westerlo": "ウェステルロー",
    "OH Leuven": "OHルーヴェン",
    "Cercle Brugge": "セルクル・ブルージュ",
    "KV Oostende": "KVオーステンデ",
    "RSCA Futures": "アンデルレヒトII",
    "Jong Genk": "ヨングヘンク",
    # スコットランド
    "Celtic": "セルティック",
    "Rangers": "レンジャーズ",
    # その他欧州
    "Djurgårdens IF": "ユールゴーデン",
    "Grasshopper": "グラスホッパー",
    "Slavia Prague": "スラヴィア・プラハ",
    "Legia Warsaw": "レギア・ワルシャワ",
    "Brøndby": "ブレンドビー",
    "Juniors OÖ": "ユニオン・ヴェルス",
    # Jリーグ
    "Kawasaki Frontale": "川崎フロンターレ",
    "Urawa Red Diamonds": "浦和レッズ",
    "Gamba Osaka": "ガンバ大阪",
    "Gamba Osaka U23": "ガンバ大阪U-23",
    "Vissel Kobe": "ヴィッセル神戸",
    "FC Tokyo": "FC東京",
    "FC Tokyo U-23": "FC東京U-23",
    "Yokohama F. Marinos": "横浜F・マリノス",
    "Yokohama FC": "横浜FC",
    "Cerezo Osaka": "セレッソ大阪",
    "Cerezo Osaka U-23": "セレッソ大阪U-23",
    "Shonan Bellmare": "湘南ベルマーレ",
    "Sanfrecce Hiroshima": "サンフレッチェ広島",
    "Shimizu S-Pulse": "清水エスパルス",
    "Nagoya Grampus": "名古屋グランパス",
    "Ventforet Kofu": "ヴァンフォーレ甲府",
    "Sagan Tosu": "サガン鳥栖",
    "Avispa Fukuoka": "アビスパ福岡",
    "Vegalta Sendai": "ベガルタ仙台",
    "Albirex Niigata": "アルビレックス新潟",
    "Tokushima Vortis": "徳島ヴォルティス",
    "Tokyo Verdy": "東京ヴェルディ",
    "Tochigi SC": "栃木SC",
    "Giravanz Kitakyushu": "ギラヴァンツ北九州",
    "V-Varen Nagasaki": "V・ファーレン長崎",
    "Mito HollyHock": "水戸ホーリーホック",
    "Fagiano Okayama": "ファジアーノ岡山",
    "FC Ryukyu": "FC琉球",
    "FC Imabari": "FC今治",
    "Oita Trinita": "大分トリニータ",
    "Iwate Grulla Morioka": "いわてグルージャ盛岡",
    # 大学
    "Tsukuba University": "筑波大学",
    "Union SG": "ユニオンSG",
    # ローン先（→ 付き）
    "→ Union SG": "→ ユニオンSG",
    "→ AZ": "→ AZアルクマール",
    "→ Arminia Bielefeld": "→ ビーレフェルト",
    "→ Borussia Mönchengladbach": "→ ボルシアMG",
    "→ Bristol City": "→ ブリストル・シティ",
    "→ Celtic": "→ セルティック",
    "→ FC Groningen": "→ フローニンゲン",
    "→ FC Volendam": "→ フォーレンダム",
    "→ Fortuna Düsseldorf": "→ デュッセルドルフ",
    "→ Genk": "→ ゲンク",
    "→ Gent": "→ ヘント",
    "→ Getafe": "→ ヘタフェ",
    "→ Gil Vicente": "→ ジル・ヴィセンテ",
    "→ Giravanz Kitakyushu": "→ ギラヴァンツ北九州",
    "→ Groningen": "→ フローニンゲン",
    "→ Göztepe": "→ ギョズテペ",
    "→ Hannover 96": "→ ハノーファー96",
    "→ Hull City": "→ ハル・シティ",
    "→ Iwate Grulla Morioka": "→ いわてグルージャ盛岡",
    "→ J. League U-22": "→ Jリーグ U-22",
    "→ J.League U-22": "→ Jリーグ U-22",
    "→ Jong AZ": "→ ヨングAZ",
    "→ Jong Genk": "→ ヨングヘンク",
    "→ Juniors OÖ": "→ ユニオン・ヴェルス",
    "→ KV Oostende": "→ KVオーステンデ",
    "→ Legia Warsaw": "→ レギア・ワルシャワ",
    "→ Mainz 05": "→ マインツ",
    "→ Mallorca": "→ マジョルカ",
    "→ Mito HollyHock": "→ 水戸ホーリーホック",
    "→ NEC Nijmegen": "→ NECナイメヘン",
    "→ Nagoya Grampus": "→ 名古屋グランパス",
    "→ Oita Trinita": "→ 大分トリニータ",
    "→ Queens Park Rangers": "→ QPR",
    "→ RSCA Futures": "→ アンデルレヒトII",
    "→ Schalke 04": "→ シャルケ04",
    "→ Sint-Truiden": "→ シント＝トロイデン",
    "→ Southampton": "→ サウサンプトン",
    "→ Sparta Rotterdam": "→ スパルタ・ロッテルダム",
    "→ Strasbourg": "→ ストラスブール",
    "→ Strasbourg II": "→ ストラスブールII",
    "→ Twente": "→ トウェンテ",
    "→ Union SG": "→ ユニオンSG",
    "→ Vegalta Sendai": "→ ベガルタ仙台",
    "→ VfB Stuttgart": "→ シュトゥットガルト",
    "→ VfB Stuttgart II": "→ シュトゥットガルトII",
    "→ Villarreal": "→ ビジャレアル",
    "→ Werder Bremen": "→ ブレーメン",
    "→ Yokohama F. Marinos": "→ 横浜F・マリノス",
}


def build_club_translations_from_players():
    # type: () -> dict
    """players.json の club_en → club_ja マッピングを動的生成する。"""
    mapping = {}
    try:
        with open(PLAYERS_JSON, encoding="utf-8") as f:
            players_raw = json.load(f)
        for p in players_raw.get("players", []):
            en = p.get("club_en", "")
            ja = p.get("club_ja", "")
            if en and ja:
                mapping[en] = ja
    except Exception:
        pass
    return mapping


def wiki_api_get(params, base_url=None):
    # type: (dict, str) -> dict
    """Wikipedia API GET リクエスト。"""
    params["format"] = "json"
    api_url = (base_url or WIKI_API) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(api_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_wiki_title(name_en):
    # type: (str) -> Optional[str]
    """選手名でWikipedia記事タイトルを検索する。"""
    data = wiki_api_get({
        "action": "query",
        "list": "search",
        "srsearch": "{} footballer".format(name_en),
        "srlimit": 3,
    })
    results = data.get("query", {}).get("search", [])
    if results:
        return results[0]["title"]
    # フォールバック: footballer なしで再検索
    data2 = wiki_api_get({
        "action": "query",
        "list": "search",
        "srsearch": name_en,
        "srlimit": 3,
    })
    results2 = data2.get("query", {}).get("search", [])
    if results2:
        return results2[0]["title"]
    return None


def get_infobox_wikitext(title):
    # type: (str) -> str
    """Wikipedia記事のwikitextを取得する。"""
    data = wiki_api_get({
        "action": "query",
        "prop": "revisions",
        "titles": title,
        "rvprop": "content",
        "rvslots": "main",
        "rvlimit": 1,
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        revs = page.get("revisions", [])
        if revs:
            return revs[0].get("slots", {}).get("main", {}).get("*", "")
    return ""


def parse_height_cm(raw):
    # type: (str) -> Optional[int]
    """
    身長テンプレートをcmに変換する。
    例: {{height|m=1.78}} → 178
        {{height|ft=5|in=10}} → 178
        {{convert|178|cm|...}} → 178
        単純に数値のみの場合も対応
    """
    if not raw:
        return None

    # {{height|m=1.XX}} or {{height|cm=XXX}}
    m = re.search(r'\{\{\s*[Hh]eight\s*\|[^}]*?cm\s*=\s*(\d+)', raw)
    if m:
        return int(m.group(1))

    m = re.search(r'\{\{\s*[Hh]eight\s*\|[^}]*?m\s*=\s*([0-9.]+)', raw)
    if m:
        try:
            return int(round(float(m.group(1)) * 100))
        except ValueError:
            pass

    # ft/in 変換
    m = re.search(r'\{\{\s*[Hh]eight\s*\|[^}]*?ft\s*=\s*(\d+)[^}]*in\s*=\s*(\d+)', raw)
    if m:
        ft, inch = int(m.group(1)), int(m.group(2))
        return int(round((ft * 12 + inch) * 2.54))

    # {{convert|178|cm|...}}
    m = re.search(r'\{\{\s*convert\s*\|\s*(\d+)\s*\|\s*cm', raw)
    if m:
        return int(m.group(1))

    # 数値 cm のみ
    m = re.search(r'(\d{3})\s*cm', raw)
    if m:
        return int(m.group(1))

    # 小数メートル
    m = re.search(r'([12]\.\d{2})\s*m', raw)
    if m:
        try:
            return int(round(float(m.group(1)) * 100))
        except ValueError:
            pass

    # 数値のみ(150-220の範囲)
    m = re.search(r'\b(1[5-9]\d|2[012]\d)\b', raw)
    if m:
        return int(m.group(1))

    return None


def parse_weight_kg(raw):
    # type: (str) -> Optional[int]
    """体重テンプレートをkgに変換する。"""
    if not raw:
        return None

    # {{weight|kg=XX}} or {{weight|XX|kg}}
    m = re.search(r'\{\{\s*[Ww]eight\s*\|[^}]*?kg\s*=\s*(\d+)', raw)
    if m:
        return int(m.group(1))

    m = re.search(r'\{\{\s*[Ww]eight\s*\|\s*(\d+)\s*\|\s*kg', raw)
    if m:
        return int(m.group(1))

    # {{convert|XX|kg|...}}
    m = re.search(r'\{\{\s*convert\s*\|\s*(\d+)\s*\|\s*kg', raw)
    if m:
        return int(m.group(1))

    # 数値 kg
    m = re.search(r'(\d{2,3})\s*kg', raw)
    if m:
        val = int(m.group(1))
        if 40 <= val <= 150:
            return val

    return None


def parse_birth_date(raw):
    # type: (str) -> Optional[str]
    """
    生年月日を YYYY-MM-DD に変換する。
    例: {{birth date|1997|5|20}} → 1997-05-20
        {{birth date and age|1997|5|20}} → 1997-05-20
    """
    if not raw:
        return None

    m = re.search(r'\{\{\s*birth[_ ]date(?:\s+and\s+age)?\s*(?:df=[yn]\s*)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})', raw, re.IGNORECASE)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return "{}-{:02d}-{:02d}".format(y, mo, d)

    # ISO日付
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', raw)
    if m:
        return m.group(0)

    return None


def _strip_templates(text):
    """ネスト・複数行を含むWikipediaテンプレート {{...}} を bracket counting で除去。"""
    if not text or '{{' not in text:
        return text
    out = []
    i = 0
    depth = 0
    n = len(text)
    while i < n:
        if text[i:i+2] == '{{':
            depth += 1
            i += 2
        elif text[i:i+2] == '}}':
            depth = max(0, depth - 1)
            i += 2
        elif depth > 0:
            i += 1
        else:
            out.append(text[i])
            i += 1
    cleaned = ''.join(out)
    # 未閉じ {{ がある場合（途中まで残ってる）は除去
    cleaned = re.sub(r'\{\{[^{}]*$', '', cleaned, flags=re.DOTALL)
    return cleaned


def clean_wiki_text(text):
    # type: (str) -> str
    """wikitextから余計な記法を除去して平文にする。"""
    if not text:
        return ""
    # <ref>...</ref> 除去（複数行対応）
    text = re.sub(r'<ref[^>]*?>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'<ref[^/]*?/>', '', text)
    # {{template|...}} 除去（ネスト・複数行対応）
    text = _strip_templates(text)
    # [[Link|Text]] → Text
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
    # ''bold'' or '''bold'''
    text = re.sub(r"'{2,3}", '', text)
    # HTMLタグ除去
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip().rstrip('|').strip()


def extract_infobox(wikitext):
    # type: (str) -> dict
    """
    Infobox football biography テンプレートのフィールドを辞書として抽出する。
    ネストされたテンプレートも考慮したシンプルなパーサ。
    """
    fields = {}
    if not wikitext:
        return fields

    # infobox の開始位置を探す
    start_pattern = re.compile(r'\{\{\s*[Ii]nfobox\s+football\s+biograph', re.IGNORECASE)
    m = start_pattern.search(wikitext)
    if not m:
        start_pattern2 = re.compile(r'\{\{\s*[Ii]nfobox\s+soccer\s+biograph', re.IGNORECASE)
        m = start_pattern2.search(wikitext)
    if not m:
        return fields

    start = m.start()
    # テンプレートの終端を探す（ブラケットの深さで判定）
    depth = 0
    end = start
    for i, ch in enumerate(wikitext[start:], start):
        if wikitext[i:i+2] == '{{':
            depth += 1
        elif wikitext[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                end = i + 2
                break

    infobox_text = wikitext[start:end]

    # フィールドを抽出: | key = value
    lines = infobox_text.split('\n')
    current_key = None
    current_val = []

    for line in lines:
        field_match = re.match(r'\|\s*(\w+)\s*=\s*(.*)', line)
        if field_match:
            if current_key:
                fields[current_key] = '\n'.join(current_val).strip()
            current_key = field_match.group(1).strip()
            current_val = [field_match.group(2)]
        elif current_key:
            current_val.append(line)

    if current_key:
        fields[current_key] = '\n'.join(current_val).strip()

    return fields


NATIONAL_TEAM_TRANSLATIONS = {
    "Japan": {"ja": "日本代表（A代表）", "level": "A"},
    "Japan U-23": {"ja": "U-23日本代表", "level": "U-23"},
    "Japan U-22": {"ja": "U-22日本代表", "level": "U-22"},
    "Japan U-21": {"ja": "U-21日本代表", "level": "U-21"},
    "Japan U-20": {"ja": "U-20日本代表", "level": "U-20"},
    "Japan U-19": {"ja": "U-19日本代表", "level": "U-19"},
    "Japan U-18": {"ja": "U-18日本代表", "level": "U-18"},
    "Japan U-17": {"ja": "U-17日本代表", "level": "U-17"},
    "Japan U-16": {"ja": "U-16日本代表", "level": "U-16"},
    "Japan U-15": {"ja": "U-15日本代表", "level": "U-15"},
}


def parse_national_team_history(wikitext):
    # type: (str) -> list
    """
    infobox の nationalteam/nationalyears/nationalcaps/nationalgoals フィールドから
    代表履歴を抽出する。
    """
    history = []
    if not wikitext:
        return history

    fields = extract_infobox(wikitext)

    for i in range(1, 11):
        team_key = "nationalteam{}".format(i)
        years_key = "nationalyears{}".format(i)
        caps_key = "nationalcaps{}".format(i)
        goals_key = "nationalgoals{}".format(i)

        team_raw = fields.get(team_key, "")
        if not team_raw:
            break

        team_clean = clean_wiki_text(team_raw).strip()
        years_clean = clean_wiki_text(fields.get(years_key, "")).strip()
        caps_raw = clean_wiki_text(fields.get(caps_key, "")).strip()
        goals_raw = clean_wiki_text(fields.get(goals_key, "")).strip()

        # Japan 系のチームのみ対象
        if "Japan" not in team_clean:
            continue

        # caps/goals を数値に変換
        try:
            caps = int(re.sub(r'[^\d]', '', caps_raw)) if caps_raw and re.sub(r'[^\d]', '', caps_raw) else None
        except ValueError:
            caps = None
        try:
            goals = int(re.sub(r'[^\d]', '', goals_raw)) if goals_raw and re.sub(r'[^\d]', '', goals_raw) else None
        except ValueError:
            goals = None

        # team_ja 変換
        team_info = NATIONAL_TEAM_TRANSLATIONS.get(team_clean, {})
        team_ja = team_info.get("ja", team_clean)

        entry = {
            "team": team_clean,
            "team_ja": team_ja,
            "years": years_clean,
        }
        if caps is not None:
            entry["caps"] = caps
        if goals is not None:
            entry["goals"] = goals

        history.append(entry)

    return history


def parse_career(wikitext):
    # type: (str) -> list
    """
    infobox の clubs / youthclubs セクションからキャリアを抽出する。
    """
    career = []
    if not wikitext:
        return career

    fields = extract_infobox(wikitext)

    # youth clubs を先に追加
    for i in range(1, 15):
        year_key = "youthyears{}".format(i)
        club_key = "youthclubs{}".format(i)
        years = fields.get(year_key, "")
        club = fields.get(club_key, "")
        if not club:
            break
        years_clean = clean_wiki_text(years).strip()
        club_clean = clean_wiki_text(club).strip()
        if club_clean:
            career.append({"years": years_clean or "?", "club": club_clean + " (Youth)"})

    # clubs1–clubs20 から抽出
    for i in range(1, 25):
        year_key = "years{}".format(i)
        club_key = "clubs{}".format(i)
        years = fields.get(year_key, "")
        club = fields.get(club_key, "")
        if not club:
            break
        years_clean = clean_wiki_text(years).strip()
        club_clean = clean_wiki_text(club).strip()
        if club_clean:
            career.append({"years": years_clean or "?", "club": club_clean})

    return career


def parse_foot(raw):
    # type: (str) -> Optional[str]
    """利き足を right/left/both に正規化する。"""
    if not raw:
        return None
    r = raw.lower()
    if "both" in r or "either" in r:
        return "both"
    if "left" in r:
        return "left"
    if "right" in r:
        return "right"
    return None


def extract_social_links(wikitext):
    # type: (str) -> dict
    """
    wikitext から SNS リンクを抽出する。
    主に {{Twitter}} {{Instagram}} テンプレートや外部リンクセクションから。
    """
    links = {"twitter": None, "instagram": None, "official_url": None}
    if not wikitext:
        return links

    # {{Twitter|username}} or {{Twitter|username|name}}
    m = re.search(r'\{\{\s*[Tt]witter\s*\|\s*([^|}\s]+)', wikitext)
    if m:
        links["twitter"] = "@" + m.group(1).lstrip("@")

    # {{Instagram|username}}
    m = re.search(r'\{\{\s*[Ii]nstagram\s*\|\s*([^|}\s]+)', wikitext)
    if m:
        links["instagram"] = m.group(1).lstrip("@")

    # [https://www.instagram.com/username ...]
    m = re.search(r'https?://(?:www\.)?instagram\.com/([\w.]+)/?', wikitext)
    if m and not links["instagram"]:
        links["instagram"] = m.group(1)

    # [https://twitter.com/username ...] or x.com
    m = re.search(r'https?://(?:www\.)?(?:twitter|x)\.com/([\w]+)/?', wikitext)
    if m and not links["twitter"]:
        handle = m.group(1)
        if handle.lower() not in ("intent", "search", "hashtag", "share"):
            links["twitter"] = "@" + handle

    # 公式サイト: 外部リンクセクションの最初の URL
    ext_links_m = re.search(r'==\s*External links?\s*==(.+?)(?:==|\Z)', wikitext, re.DOTALL | re.IGNORECASE)
    if ext_links_m:
        ext_section = ext_links_m.group(1)
        m = re.search(r'\[https?://([\w./-]+)', ext_section)
        if m:
            links["official_url"] = "https://" + m.group(1)

    return links


def translate_club_name(club_en, club_translations):
    # type: (str, dict) -> str
    """クラブ名を英語→日本語に変換する。辞書にない場合は英語のまま返す。"""
    if not club_en:
        return club_en

    # まず完全一致（→付きも含む）
    if club_en in club_translations:
        return club_translations[club_en]

    # (Youth) / (loan) などのサフィックスを分離（スペースなしで結合）
    suffix_match = re.match(r'^(.*?)\s*(\([^)]+\))$', club_en)
    if suffix_match:
        base = suffix_match.group(1).strip()
        suffix = suffix_match.group(2)
    else:
        base = club_en
        suffix = ""

    # ベースクラブ名で変換 + サフィックス再付与
    if base in club_translations:
        ja_base = club_translations[base]
        # サフィックスの日本語化（スペースなし）
        suffix_ja = suffix.replace("(loan)", "（ローン）").replace("(Youth)", "（ユース）")
        return ja_base + suffix_ja

    # → 付きローン記法の処理: "→ ClubName (loan)"
    if club_en.startswith("→ "):
        raw_club = club_en[2:].strip()
        # (loan)除去してベースクラブ名取得
        loan_match = re.match(r'^(.*?)\s*(\(loan\))?$', raw_club)
        raw_base = loan_match.group(1).strip() if loan_match else raw_club
        if raw_base in club_translations:
            return "→ " + club_translations[raw_base]
        # 辞書にある "→ X" キーがあれば使用
        arrow_key = "→ " + raw_base
        if arrow_key in club_translations:
            return club_translations[arrow_key]

    return club_en


def translate_birth_place(en_str):
    # type: (str) -> Optional[str]
    """出身地を英語→日本語に変換する。"""
    if not en_str:
        return None

    parts = [p.strip() for p in en_str.split(',')]

    # 日本出身の場合
    if "Japan" in en_str:
        if len(parts) >= 3:
            # 例: "Hita, Ōita, Japan" → city=Hita, pref=Ōita
            # 例: "Asao-ku, Kawasaki, Kanagawa, Japan" → parts[0]=Asao-ku, parts[1]=Kawasaki, parts[2]=Kanagawa
            # 例: "Totsuka-ku, Yokohama, Japan" → city=Totsuka-ku, mid=Yokohama
            # 最後が Japan なので parts[-1]="Japan", parts[-2]=都道府県 or 市
            pref_candidate = parts[-2]
            pref_ja = PREFECTURE_TRANSLATIONS.get(pref_candidate)
            if pref_ja:
                # 都道府県が確認できた場合
                return "{}（日本）".format(pref_ja)
            else:
                # parts[-2]が市名の場合（例: Yokohama, Kawasaki）
                # その場合 parts[-3]が都道府県の可能性
                if len(parts) >= 4:
                    pref2 = parts[-3]
                    pref2_ja = PREFECTURE_TRANSLATIONS.get(pref2)
                    if pref2_ja:
                        return "{}（日本）".format(pref2_ja)
                # 市名が都道府県辞書にある場合（例: Yokohama→神奈川県横浜市）
                city_pref_map = {
                    "Yokohama": "神奈川県横浜市",
                    "Kawasaki": "神奈川県川崎市",
                    "Osaka": "大阪府",
                    "Kyoto": "京都府",
                    "Sapporo": "北海道札幌市",
                    "Fukuoka": "福岡県福岡市",
                    "Nagoya": "愛知県名古屋市",
                    "Kobe": "兵庫県神戸市",
                    "Hiroshima": "広島県広島市",
                    "Sendai": "宮城県仙台市",
                    "Saitama": "埼玉県さいたま市",
                    "Chiba": "千葉県千葉市",
                }
                city_ja = city_pref_map.get(pref_candidate)
                if city_ja:
                    return "{}（日本）".format(city_ja)
                return "{}（日本）".format(pref_candidate)
        elif len(parts) == 2:
            pref_or_city, _country = parts[0], parts[1]
            pref_ja = PREFECTURE_TRANSLATIONS.get(pref_or_city)
            if pref_ja:
                return "{}（日本）".format(pref_ja)
            return "{}（日本）".format(pref_or_city)
        elif len(parts) == 1:
            return "日本"

    # 海外の場合：最後の部分が国名
    if parts:
        country = parts[-1]
        country_ja = COUNTRY_TRANSLATIONS.get(country)
        if country_ja and len(parts) >= 2:
            city_or_region = parts[0]
            return "{}（{}）".format(city_or_region, country_ja)
        elif country_ja:
            return country_ja

    return en_str


def get_ja_wiki_infobox(name_ja):
    # type: (str) -> str
    """Wikipedia日本語版から選手のwikitextを取得する。取得できない場合は空文字を返す。"""
    if not name_ja:
        return ""
    try:
        data = wiki_api_get({
            "action": "query",
            "prop": "revisions",
            "titles": name_ja,
            "rvprop": "content",
            "rvslots": "main",
            "rvlimit": 1,
        }, base_url=WIKI_JA_API)
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            # ページが存在しない場合 page_id が -1
            if page.get("pageid", -1) == -1:
                return ""
            revs = page.get("revisions", [])
            if revs:
                return revs[0].get("slots", {}).get("main", {}).get("*", "")
    except Exception as e:
        print("    JA Wiki error: {}".format(e))
    return ""


def extract_ja_birth_place(ja_wikitext):
    # type: (str) -> Optional[str]
    """日本語Wikipedia wikitextから出身地を抽出する。"""
    if not ja_wikitext:
        return None

    # |出身地 = や |生誕地 = を探す
    # 行末まで貪欲にキャプチャ → bracket counting でテンプレ除去
    for key in ["出身地", "生誕地", "出生地", "birth_place", "birthplace"]:
        m = re.search(r'\|\s*{}\s*=\s*([^\n]*)'.format(key), ja_wikitext)
        if m:
            val = clean_wiki_text(m.group(1))
            if val:
                return val
    return None


def extract_ja_career(ja_wikitext):
    # type: (str) -> list
    """日本語Wikipedia wikitextからキャリア情報を抽出する。"""
    career = []
    if not ja_wikitext:
        return career

    # 日本語版infoboxからクラブ情報を抽出
    # |クラブ1 = や |年1 = など
    # 行末まで貪欲にキャプチャ → bracket counting でテンプレ除去
    for i in range(1, 25):
        year_keys = ["年{}".format(i), "clb_years{}".format(i)]
        club_keys = ["クラブ{}".format(i), "clb{}".format(i)]

        years = ""
        club = ""

        for yk in year_keys:
            m = re.search(r'\|\s*{}\s*=\s*([^\n]*)'.format(yk), ja_wikitext)
            if m:
                years = clean_wiki_text(m.group(1))
                break

        for ck in club_keys:
            m = re.search(r'\|\s*{}\s*=\s*([^\n]*)'.format(ck), ja_wikitext)
            if m:
                club = clean_wiki_text(m.group(1))
                break

        if club:
            career.append({"years": years or "?", "club": club})
        else:
            break

    return career


def fetch_player_info(name_en, name_ja="", club_translations=None):
    # type: (str, str, dict) -> dict
    """1選手分の情報を取得して辞書で返す。"""
    if club_translations is None:
        club_translations = {}

    info = {
        "wiki_url": None,
        "height_cm": None,
        "weight_kg": None,
        "birth_date": None,
        "birth_place": None,
        "birth_place_ja": None,
        "foot": None,
        "career": [],
        "career_ja": [],
        "national_team_history": [],
        "twitter": None,
        "instagram": None,
        "official_url": None,
    }

    # 記事タイトルを検索
    title = search_wiki_title(name_en)
    if not title:
        print("    → Wikipedia記事が見つかりません: {}".format(name_en))
        return info

    info["wiki_url"] = "https://en.wikipedia.org/wiki/{}".format(
        urllib.parse.quote(title.replace(' ', '_'))
    )
    print("    → {}".format(title))

    # wikitext 取得
    wikitext = get_infobox_wikitext(title)
    if not wikitext:
        return info

    fields = extract_infobox(wikitext)

    # 身長
    height_raw = fields.get("height", "")
    info["height_cm"] = parse_height_cm(height_raw)

    # 体重
    weight_raw = fields.get("weight", "")
    info["weight_kg"] = parse_weight_kg(weight_raw)

    # 生年月日
    birth_raw = fields.get("birth_date", "")
    info["birth_date"] = parse_birth_date(birth_raw)

    # 出身地（英語版）
    birth_place_raw = fields.get("birth_place", "")
    birth_place_en = clean_wiki_text(birth_place_raw)
    info["birth_place"] = birth_place_en

    # 利き足
    foot_raw = fields.get("foot", "")
    info["foot"] = parse_foot(foot_raw)

    # キャリア（英語版）
    info["career"] = parse_career(wikitext)

    # 代表履歴
    info["national_team_history"] = parse_national_team_history(wikitext)

    # SNS
    social = extract_social_links(wikitext)
    info["twitter"] = social["twitter"]
    info["instagram"] = social["instagram"]
    info["official_url"] = social["official_url"]

    # ====== 日本語化処理 ======

    # Step 1: Wikipedia日本語版から取得を試みる
    ja_birth_place = None
    ja_career = []
    if name_ja:
        print("    → JA Wiki 取得試行: {}".format(name_ja))
        ja_wikitext = get_ja_wiki_infobox(name_ja)
        if ja_wikitext:
            print("    → JA Wiki 取得成功")
            ja_birth_place = extract_ja_birth_place(ja_wikitext)
            ja_career = extract_ja_career(ja_wikitext)
        else:
            print("    → JA Wiki 記事なし（辞書変換にフォールバック）")

    # Step 2: 出身地の日本語化
    if ja_birth_place:
        info["birth_place_ja"] = ja_birth_place
    else:
        # 辞書ベース変換
        info["birth_place_ja"] = translate_birth_place(birth_place_en)

    # Step 3: キャリアの日本語化
    if ja_career:
        info["career_ja"] = ja_career
    else:
        # 辞書ベースでクラブ名を翻訳
        career_ja = []
        for item in info["career"]:
            club_en_raw = item.get("club", "")
            club_ja = translate_club_name(club_en_raw, club_translations)
            career_ja.append({"years": item.get("years", ""), "club": club_ja})
        info["career_ja"] = career_ja

    return info


def main():
    # 既存データ読み込み（差分更新用）
    existing = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existing = json.load(f)

    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    print("選手数: {}".format(len(players)))

    # players.json から club_en→club_ja マッピングを動的生成
    dynamic_clubs = build_club_translations_from_players()
    # 静的辞書に動的生成分をマージ（静的辞書を優先）
    merged_clubs = dict(dynamic_clubs)
    merged_clubs.update(CLUB_TRANSLATIONS)

    result = {}
    success = 0
    fail = 0
    ja_success = 0

    empty_template = {
        "wiki_url": None,
        "height_cm": None,
        "weight_kg": None,
        "birth_date": None,
        "birth_place": None,
        "birth_place_ja": None,
        "foot": None,
        "career": [],
        "career_ja": [],
        "national_team_history": [],
        "twitter": None,
        "instagram": None,
        "official_url": None,
    }

    for i, player in enumerate(players):
        name_en = player.get("name_en", "")
        name_ja = player.get("name_ja", "")
        print("[{}/{}] {} ({})".format(i + 1, len(players), name_ja, name_en))

        try:
            info = fetch_player_info(name_en, name_ja=name_ja, club_translations=merged_clubs)
            result[name_en] = info
            if info.get("height_cm") or info.get("birth_date") or info.get("career"):
                success += 1
            else:
                fail += 1
            if info.get("birth_place_ja"):
                ja_success += 1
        except Exception as e:
            print("    Error: {}".format(e))
            old = existing.get(name_en, {})
            # 既存データがあれば _ja フィールドだけ追記試行
            fallback = dict(empty_template)
            fallback.update(old)
            if not fallback.get("birth_place_ja") and old.get("birth_place"):
                fallback["birth_place_ja"] = translate_birth_place(old["birth_place"])
            if not fallback.get("career_ja") and old.get("career"):
                fallback["career_ja"] = [
                    {"years": c.get("years", ""), "club": translate_club_name(c.get("club", ""), merged_clubs)}
                    for c in old["career"]
                ]
            result[name_en] = fallback
            fail += 1

        # Wikipedia API への負荷軽減
        time.sleep(0.5)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n完了: 取得成功 {}/{} 選手".format(success, len(players)))
    print("日本語化成功（出身地）: {}/{} 選手".format(ja_success, len(players)))
    print("保存先: {}".format(OUTPUT_JSON))


if __name__ == "__main__":
    main()
