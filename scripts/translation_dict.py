#!/usr/bin/env python3
"""
translation_dict.py
日本語→英語の共通翻訳辞書。
generate_player_pages_en.py / generate_club_pages_en.py から共通利用。
"""

# ============================
# リーグ名
# ============================
LEAGUE_JA_TO_EN = {
    "プレミアリーグ": "Premier League",
    "チャンピオンシップ": "Championship",
    "ブンデスリーガ": "Bundesliga",
    "2.ブンデスリーガ": "2. Bundesliga",
    "ラ・リーガ": "La Liga",
    "ラリーガ": "La Liga",
    "セリエA": "Serie A",
    "リーグ・アン": "Ligue 1",
    "リーグ・ドゥ": "Ligue 2",
    "エールディビジ": "Eredivisie",
    "プリメイラ・リーガ": "Primeira Liga",
    "ジュピラー・プロ・リーグ": "Jupiler Pro League",
    "スコティッシュ・プレミアシップ": "Scottish Premiership",
    "スーペル・リーグ": "Super Lig",
    "MLS": "MLS",
    "Jリーグ": "J.League",
    "J1リーグ": "J1 League",
}

# ============================
# ポジション
# ============================
POSITION_JA_TO_EN = {
    "GK": "Goalkeeper",
    "DF": "Defender",
    "MF": "Midfielder",
    "FW": "Forward",
    "DF/MF": "Defender/Midfielder",
    "MF/FW": "Midfielder/Forward",
    "FW/MF": "Forward/Midfielder",
    "DF/FW": "Defender/Forward",
    "MF/DF": "Midfielder/Defender",
    "FW/DF": "Forward/Defender",
}

POSITION_ABBR_EN = {
    "GK": "GK",
    "DF": "DF",
    "MF": "MF",
    "FW": "FW",
}

# ============================
# セクションタイトル
# ============================
SECTION_TITLES = {
    "基本情報": "Profile",
    "プロフィール": "Profile",
    "キャリア": "Career",
    "直近の試合": "Recent Matches",
    "直近10試合": "Recent 10 Matches",
    "直近のゴール": "Recent Goals",
    "代表履歴": "International Career",
    "関連動画": "Related Videos",
    "関連ニュース": "Latest News",
    "今シーズン成績": "Season Stats",
    "順位": "Standings",
    "現在順位": "Current Standings",
    "所属日本人選手": "Japanese Players",
    "対戦相手別成績": "Records vs Opponents",
    "関連ハイライト動画": "Match Highlights",
    "シーズンゴール集・まとめ動画": "Season Goals & Highlights",
    "同クラブの日本人選手": "Other Japanese Players at This Club",
    "SNS・公式リンク": "Social Media & Official Links",
    "クラブ基本情報": "Club Info",
    "順位推移": "League Position History",
    "クラブ関連ニュース": "Club News",
}

# ============================
# 統計ヘッダー
# ============================
STATS_HEADERS = {
    "試合数": "Apps",
    "出場試合": "Apps",
    "ゴール": "Goals",
    "アシスト": "Assists",
    "PK": "Pens",
    "日時": "Date",
    "日時（JST）": "Date (JST)",
    "場所": "Venue",
    "対戦相手": "Opponent",
    "結果": "Result",
    "配信": "Stream",
    "大会": "Competition",
    "試合": "Match",
    "分": "min",
    "得点": "Goals",
    "失点": "Against",
    "試合数": "Played",
    "勝": "W",
    "分": "D",
    "負": "L",
}

# ============================
# プロフィールラベル
# ============================
PROFILE_LABELS = {
    "身長 / 体重": "Height / Weight",
    "生年月日": "Date of Birth",
    "出身地": "Birthplace",
    "利き足": "Foot",
    "右": "Right",
    "左": "Left",
    "両足": "Both",
    "歳": " years old",
    "位": "",  # 順位の"位"は除去
    "pt": "pts",
    "試合": "matches",
    "勝": "W",
    "分": "D",
    "敗": "L",
}

# ============================
# クラブ情報ラベル
# ============================
CLUB_INFO_LABELS = {
    "創設年": "Founded",
    "本拠地": "Location",
    "スタジアム": "Stadium",
    "収容人数": "Capacity",
    "監督": "Manager",
    "会長": "Chairman",
    "公式サイト": "Official Website",
}

# ============================
# 国名（よく使われるもの）
# ============================
COUNTRY_JA_TO_EN = {
    "日本": "Japan",
    "イングランド": "England",
    "スペイン": "Spain",
    "ドイツ": "Germany",
    "フランス": "France",
    "イタリア": "Italy",
    "オランダ": "Netherlands",
    "ポルトガル": "Portugal",
    "ベルギー": "Belgium",
    "スコットランド": "Scotland",
    "トルコ": "Turkey",
    "アメリカ": "United States",
    "ブラジル": "Brazil",
    "アルゼンチン": "Argentina",
    "韓国": "South Korea",
    "中国": "China",
    "オーストラリア": "Australia",
    "神奈川県": "Kanagawa, Japan",
    "東京都": "Tokyo, Japan",
    "大阪府": "Osaka, Japan",
    "愛知県": "Aichi, Japan",
    "兵庫県": "Hyogo, Japan",
    "静岡県": "Shizuoka, Japan",
    "埼玉県": "Saitama, Japan",
    "千葉県": "Chiba, Japan",
    "北海道": "Hokkaido, Japan",
    "福岡県": "Fukuoka, Japan",
    "広島県": "Hiroshima, Japan",
    "宮城県": "Miyagi, Japan",
    "京都府": "Kyoto, Japan",
}

# ============================
# ヘルパー関数
# ============================
def translate_league(league_ja: str) -> str:
    """リーグ名を英語に変換する。"""
    return LEAGUE_JA_TO_EN.get(league_ja, league_ja)


def translate_position(position: str) -> str:
    """ポジションを英語に変換する。完全一致→部分変換の順で試みる。"""
    if not position:
        return position
    if position in POSITION_JA_TO_EN:
        return POSITION_JA_TO_EN[position]
    # 複合ポジションの場合（例: DF/MF は辞書にない組み合わせ）
    parts = position.split("/")
    en_parts = [POSITION_ABBR_EN.get(p.strip(), p.strip()) for p in parts]
    return "/".join(en_parts)


def translate_career_club(club_ja: str) -> str:
    """キャリアのクラブ名（日本語）を英語に変換。
    player_info.json の career フィールド（英語）を優先するため、
    このメソッドは career_ja フォールバック時に使用。
    """
    # 特定の変換ルール
    conversions = {
        "湘南ベルマーレ": "Shonan Bellmare",
        "浦和レッズ": "Urawa Red Diamonds",
        "鹿島アントラーズ": "Kashima Antlers",
        "ガンバ大阪": "Gamba Osaka",
        "セレッソ大阪": "Cerezo Osaka",
        "横浜F・マリノス": "Yokohama F. Marinos",
        "川崎フロンターレ": "Kawasaki Frontale",
        "名古屋グランパス": "Nagoya Grampus",
        "サンフレッチェ広島": "Sanfrecce Hiroshima",
        "ヴィッセル神戸": "Vissel Kobe",
        "FC東京": "FC Tokyo",
        "柏レイソル": "Kashiwa Reysol",
        "清水エスパルス": "Shimizu S-Pulse",
        "大宮アルディージャ": "Omiya Ardija",
        "ジュビロ磐田": "Júbilo Iwata",
        "アルビレックス新潟": "Albirex Niigata",
        "モンテディオ山形": "Montedio Yamagata",
        "コンサドーレ札幌": "Consadole Sapporo",
        "ベガルタ仙台": "Vegalta Sendai",
        "シント＝トロイデン": "Sint-Truiden",
        "シュトゥットガルト": "VfB Stuttgart",
        "リヴァプール": "Liverpool",
        "マンチェスター・シティ": "Manchester City",
        "マンチェスター・ユナイテッド": "Manchester United",
        "アーセナル": "Arsenal",
        "チェルシー": "Chelsea",
        "トッテナム": "Tottenham Hotspur",
    }
    # → がある場合（ローン表記）
    if club_ja.startswith("→"):
        inner = club_ja[1:].strip()
        inner_en = conversions.get(inner, inner)
        if "(loan)" in inner_en or "loan" in inner_en.lower():
            return f"→ {inner_en}"
        return f"→ {inner_en} (loan)"
    return conversions.get(club_ja, club_ja)


def translate_birthplace(birthplace: str) -> str:
    """出身地を英語に変換する。
    player_info.json の birth_place フィールド（英語）があれば不要。
    """
    if not birthplace:
        return ""
    # 英語の文字が多い場合はそのまま返す
    ascii_ratio = sum(1 for c in birthplace if ord(c) < 128) / max(len(birthplace), 1)
    if ascii_ratio > 0.5:
        return birthplace
    # 辞書で変換
    for ja, en in COUNTRY_JA_TO_EN.items():
        if ja in birthplace:
            return en
    return birthplace  # 変換できなければそのまま


def get_competition_en(comp_ja: str, comp_en_map: dict = None) -> str:
    """大会名（日本語）を英語に変換する。"""
    if comp_en_map and comp_ja in comp_en_map:
        return comp_en_map[comp_ja]
    return LEAGUE_JA_TO_EN.get(comp_ja, comp_ja)
