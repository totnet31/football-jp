#!/usr/bin/env python3
"""
検索インデックスJSONを生成するスクリプト。
全選手・クラブ・リーグ・W杯国を data/search_index.json (日本語) と
data/search_index_en.json (英語) に出力する。
冪等で、既存データを壊さない。
"""

import json
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ----- リーグID → en名 マッピング -----
LEAGUE_EN = {
    "39":  "Premier League",
    "40":  "Championship",
    "140": "La Liga",
    "78":  "Bundesliga",
    "135": "Serie A",
    "61":  "Ligue 1",
    "88":  "Eredivisie",
    "94":  "Primeira Liga",
    "2":   "UEFA Champions League",
    "144": "Jupiler Pro League",
    "62":  "Ligue 2",
}

# リーグIDとURLスラグのマッピング
LEAGUE_SLUG = {
    "39":  "premier-league",
    "40":  "championship",
    "140": "la-liga",
    "78":  "bundesliga",
    "135": "serie-a",
    "61":  "ligue-1",
    "88":  "eredivisie",
    "94":  "primeira-liga",
    "2":   None,   # CLはリーグページなし
    "144": "jupiler-pro-league",
    "62":  "ligue-2",
}

def slugify(text):
    """英語名からURLスラグを生成"""
    s = text.lower()
    s = re.sub(r"[&/']", "", s)
    s = re.sub(r"[\s\-]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def country_slug(en_name):
    """W杯国名からURLスラグへ変換。実際のディレクトリ名と一致させる"""
    special = {
        "South Africa": "south-africa",
        "South Korea": "south-korea",
        "United States": "united-states",
        "Bosnia-Herzegovina": "bosnia-herzegovina",
        "Cape Verde Islands": "cape-verde-islands",
        "Congo DR": "congo-dr",
        "Ivory Coast": "ivory-coast",
        "New Zealand": "new-zealand",
    }
    if en_name in special:
        return special[en_name]
    return slugify(en_name)

def get_player_slug(name_en):
    """英語名からプレイヤースラグを生成"""
    return slugify(name_en)

def build_items():
    items_ja = []
    items_en = []

    # ---- 1. 選手 ----
    players_path = os.path.join(DATA, "players.json")
    players_data = json.load(open(players_path, encoding="utf-8"))
    players = players_data.get("players", [])

    for p in players:
        name_ja = p.get("name_ja", "")
        name_en = p.get("name_en", "")
        position = p.get("position", "")
        club_ja = p.get("club_ja", "")
        club_en = p.get("club_en", "")
        league_ja = p.get("league_ja", "")
        comp_id = str(p.get("competition_id", ""))

        slug = get_player_slug(name_en)
        url = f"/players/{slug}/"

        # プレイヤーページが実際に存在するか確認
        player_dir = os.path.join(ROOT, "players", slug)
        if not os.path.isdir(player_dir):
            # フォールバック: players一覧ページへ
            url = "/players/"

        subtitle_ja = f"{position} / {club_ja}" if position else club_ja
        subtitle_en = f"{position} / {club_en}" if position else club_en
        league_en = LEAGUE_EN.get(comp_id, league_ja)

        items_ja.append({
            "type": "player",
            "id": slug,
            "name_ja": name_ja,
            "name_en": name_en,
            "subtitle": subtitle_ja,
            "url": url,
        })
        items_en.append({
            "type": "player",
            "id": slug,
            "name_ja": name_ja,
            "name_en": name_en,
            "subtitle": subtitle_en,
            "url": url,
        })

    # ---- 2. クラブ ----
    # クラブディレクトリから一覧を取得
    clubs_dir = os.path.join(ROOT, "clubs")
    club_dirs = sorted(d for d in os.listdir(clubs_dir) if os.path.isdir(os.path.join(clubs_dir, d)))

    # players.jsonからclub_id → club情報 マッピングを構築
    club_info_by_slug = {}
    for p in players:
        club_slug = slugify(p.get("club_en", ""))
        if club_slug and club_slug not in club_info_by_slug:
            comp_id = str(p.get("competition_id", ""))
            club_info_by_slug[club_slug] = {
                "ja": p.get("club_ja", ""),
                "en": p.get("club_en", ""),
                "league_ja": p.get("league_ja", ""),
                "league_en": LEAGUE_EN.get(comp_id, p.get("league_ja", "")),
            }

    # 特殊なスラグのマッピング（slugifyで一致しないケース）
    CLUB_SLUG_OVERRIDE = {
        "az-alkmaar": {"ja": "AZアルクマール", "en": "AZ Alkmaar", "league_ja": "エールディビジ", "league_en": "Eredivisie"},
        "oh-leuven": {"ja": "OHルーヴェン", "en": "OH Leuven", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "nec-nijmegen": {"ja": "NEC", "en": "NEC Nijmegen", "league_ja": "エールディビジ", "league_en": "Eredivisie"},
        "fc-augsburg": {"ja": "アウクスブルク", "en": "FC Augsburg", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "fc-st-pauli": {"ja": "ザンクトパウリ", "en": "FC St. Pauli", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "tsg-hoffenheim": {"ja": "ホッフェンハイム", "en": "TSG Hoffenheim", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "sc-freiburg": {"ja": "フライブルク", "en": "SC Freiburg", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "vfl-wolfsburg": {"ja": "ヴォルフスブルク", "en": "VfL Wolfsburg", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "mainz-05": {"ja": "マインツ", "en": "Mainz 05", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "borussia-monchengladbach": {"ja": "ボルシアMG", "en": "Borussia Mönchengladbach", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "eintracht-frankfurt": {"ja": "フランクフルト", "en": "Eintracht Frankfurt", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "sparta-rotterdam": {"ja": "スパルタ・ロッテルダム", "en": "Sparta Rotterdam", "league_ja": "エールディビジ", "league_en": "Eredivisie"},
        "stade-de-reims": {"ja": "スタッド・ドゥ・ランス", "en": "Stade de Reims", "league_ja": "リーグ・アン", "league_en": "Ligue 1"},
        "le-havre": {"ja": "ル・アーブル", "en": "Le Havre", "league_ja": "リーグ・アン", "league_en": "Ligue 1"},
        "sporting-cp": {"ja": "スポルティング", "en": "Sporting CP", "league_ja": "プリメイラ・リーガ", "league_en": "Primeira Liga"},
        "gil-vicente": {"ja": "ジル・ヴィセンテ", "en": "Gil Vicente", "league_ja": "プリメイラ・リーガ", "league_en": "Primeira Liga"},
        "sint-truiden": {"ja": "シント＝トロイデン", "en": "Sint-Truiden", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "royal-antwerp": {"ja": "アントワープ", "en": "Royal Antwerp", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "westerlo": {"ja": "ウェステルロー", "en": "Westerlo", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "genk": {"ja": "ヘンク", "en": "Genk", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "gent": {"ja": "ヘント", "en": "Gent", "league_ja": "ジュピラー・プロ・リーグ", "league_en": "Jupiler Pro League"},
        "queens-park-rangers": {"ja": "QPR", "en": "Queens Park Rangers", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "stoke-city": {"ja": "ストーク・シティ", "en": "Stoke City", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "hull-city": {"ja": "ハル・シティ", "en": "Hull City", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "brighton-hove-albion": {"ja": "ブライトン", "en": "Brighton & Hove Albion", "league_ja": "プレミアリーグ", "league_en": "Premier League"},
        "crystal-palace": {"ja": "クリスタル・パレス", "en": "Crystal Palace", "league_ja": "プレミアリーグ", "league_en": "Premier League"},
        "real-sociedad": {"ja": "レアル・ソシエダ", "en": "Real Sociedad", "league_ja": "ラ・リーガ", "league_en": "La Liga"},
        "ajax": {"ja": "アヤックス", "en": "Ajax", "league_ja": "エールディビジ", "league_en": "Eredivisie"},
        "feyenoord": {"ja": "フェイエノールト", "en": "Feyenoord", "league_ja": "エールディビジ", "league_en": "Eredivisie"},
        "monaco": {"ja": "モナコ", "en": "Monaco", "league_ja": "リーグ・アン", "league_en": "Ligue 1"},
        "parma": {"ja": "パルマ", "en": "Parma", "league_ja": "セリエA", "league_en": "Serie A"},
        "mallorca": {"ja": "マジョルカ", "en": "Mallorca", "league_ja": "ラ・リーガ", "league_en": "La Liga"},
        "tottenham": {"ja": "トッテナム", "en": "Tottenham", "league_ja": "プレミアリーグ", "league_en": "Premier League"},
        "liverpool": {"ja": "リバプール", "en": "Liverpool", "league_ja": "プレミアリーグ", "league_en": "Premier League"},
        "leeds": {"ja": "リーズ・ユナイテッド", "en": "Leeds", "league_ja": "プレミアリーグ", "league_en": "Premier League"},
        "southampton": {"ja": "サウサンプトン", "en": "Southampton", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "coventry": {"ja": "コヴェントリー", "en": "Coventry", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "blackburn": {"ja": "ブラックバーン", "en": "Blackburn", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "birmingham": {"ja": "バーミンガム", "en": "Birmingham", "league_ja": "チャンピオンシップ", "league_en": "Championship"},
        "werder-bremen": {"ja": "ブレーメン", "en": "Werder Bremen", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
        "bayern-munchen": {"ja": "バイエルン・ミュンヘン", "en": "Bayern München", "league_ja": "ブンデスリーガ", "league_en": "Bundesliga"},
    }

    for club_slug in club_dirs:
        info = CLUB_SLUG_OVERRIDE.get(club_slug) or club_info_by_slug.get(club_slug)
        if not info:
            # HTMLから取得を試みる
            idx_path = os.path.join(clubs_dir, club_slug, "index.html")
            if os.path.exists(idx_path):
                content = open(idx_path, encoding="utf-8").read()
                import re as re2
                m = re2.search(r'<title>(.+?)（(.+?)）', content)
                if m:
                    info = {
                        "ja": m.group(1).strip(),
                        "en": m.group(2).strip(),
                        "league_ja": "",
                        "league_en": "",
                    }

        if not info:
            # 最低限スラグから生成
            info = {
                "ja": club_slug.replace("-", " ").title(),
                "en": club_slug.replace("-", " ").title(),
                "league_ja": "",
                "league_en": "",
            }

        url = f"/clubs/{club_slug}/"
        items_ja.append({
            "type": "club",
            "id": club_slug,
            "name_ja": info["ja"],
            "name_en": info["en"],
            "subtitle": info["league_ja"],
            "url": url,
        })
        items_en.append({
            "type": "club",
            "id": club_slug,
            "name_ja": info["ja"],
            "name_en": info["en"],
            "subtitle": info["league_en"],
            "url": url,
        })

    # ---- 3. リーグ ----
    LEAGUES = [
        {"id": "premier-league",    "ja": "プレミアリーグ",         "en": "Premier League",        "country_ja": "イングランド", "country_en": "England"},
        {"id": "championship",      "ja": "チャンピオンシップ",     "en": "Championship",          "country_ja": "イングランド", "country_en": "England"},
        {"id": "la-liga",           "ja": "ラ・リーガ",             "en": "La Liga",               "country_ja": "スペイン",     "country_en": "Spain"},
        {"id": "bundesliga",        "ja": "ブンデスリーガ",         "en": "Bundesliga",            "country_ja": "ドイツ",       "country_en": "Germany"},
        {"id": "serie-a",           "ja": "セリエA",                "en": "Serie A",               "country_ja": "イタリア",     "country_en": "Italy"},
        {"id": "ligue-1",           "ja": "リーグ・アン",           "en": "Ligue 1",               "country_ja": "フランス",     "country_en": "France"},
        {"id": "eredivisie",        "ja": "エールディビジ",         "en": "Eredivisie",            "country_ja": "オランダ",     "country_en": "Netherlands"},
        {"id": "primeira-liga",     "ja": "プリメイラ・リーガ",     "en": "Primeira Liga",         "country_ja": "ポルトガル",   "country_en": "Portugal"},
        {"id": "jupiler-pro-league","ja": "ジュピラー・プロ・リーグ","en": "Jupiler Pro League",    "country_ja": "ベルギー",     "country_en": "Belgium"},
        {"id": "ligue-2",           "ja": "リーグ2",                "en": "Ligue 2",               "country_ja": "フランス",     "country_en": "France"},
    ]
    for lg in LEAGUES:
        league_dir = os.path.join(ROOT, "leagues", lg["id"])
        if not os.path.isdir(league_dir):
            continue
        url = f"/leagues/{lg['id']}/"
        items_ja.append({
            "type": "league",
            "id": lg["id"],
            "name_ja": lg["ja"],
            "name_en": lg["en"],
            "subtitle": lg["country_ja"],
            "url": url,
        })
        items_en.append({
            "type": "league",
            "id": lg["id"],
            "name_ja": lg["ja"],
            "name_en": lg["en"],
            "subtitle": lg["country_en"],
            "url": url,
        })

    # ---- 4. W杯国 ----
    cp_path = os.path.join(DATA, "wc2026", "country_profiles.json")
    cp_data = json.load(open(cp_path, encoding="utf-8"))
    profiles = cp_data.get("profiles", {})

    for code, p in profiles.items():
        ja_name = p.get("ja", "")
        en_name = p.get("en", "")
        flag = p.get("flag", "")
        group = p.get("group", "")
        slug = country_slug(en_name)

        # ページが存在するか確認
        country_dir = os.path.join(ROOT, "worldcup", "countries", slug)
        if not os.path.isdir(country_dir):
            url = "/worldcup/countries/"
        else:
            url = f"/worldcup/countries/{slug}/"

        subtitle_ja = f"{flag} グループ{group}" if group else flag
        subtitle_en = f"{flag} Group {group}" if group else flag

        items_ja.append({
            "type": "country",
            "id": slug,
            "name_ja": ja_name,
            "name_en": en_name,
            "subtitle": subtitle_ja,
            "url": url,
        })
        items_en.append({
            "type": "country",
            "id": slug,
            "name_ja": ja_name,
            "name_en": en_name,
            "subtitle": subtitle_en,
            "url": url,
        })

    return items_ja, items_en

def main():
    today = date.today().isoformat()
    items_ja, items_en = build_items()

    out_ja = {
        "items": items_ja,
        "_updated": today,
        "_count": len(items_ja),
    }
    out_en = {
        "items": items_en,
        "_updated": today,
        "_count": len(items_en),
    }

    out_ja_path = os.path.join(DATA, "search_index.json")
    out_en_path = os.path.join(DATA, "search_index_en.json")

    with open(out_ja_path, "w", encoding="utf-8") as f:
        json.dump(out_ja, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {out_ja_path}  ({len(items_ja)} items)")

    with open(out_en_path, "w", encoding="utf-8") as f:
        json.dump(out_en, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {out_en_path}  ({len(items_en)} items)")

    print(f"\n内訳: 選手={sum(1 for i in items_ja if i['type']=='player')}, "
          f"クラブ={sum(1 for i in items_ja if i['type']=='club')}, "
          f"リーグ={sum(1 for i in items_ja if i['type']=='league')}, "
          f"国={sum(1 for i in items_ja if i['type']=='country')}")

if __name__ == "__main__":
    main()
