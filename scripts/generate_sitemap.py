#!/usr/bin/env python3
"""
generate_sitemap.py
sitemap.xml を自動生成するスクリプト。
出力先: {REPO_ROOT}/sitemap.xml
使い方: python3 scripts/generate_sitemap.py
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
PROFILES_JSON = REPO_ROOT / "data" / "wc2026" / "country_profiles.json"
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
OUTPUT_FILE = REPO_ROOT / "sitemap.xml"

BASE_URL = "https://football-jp.com"

# ============================
# slug生成（generate_country_pages.py と同じロジック）
# ============================
SLUG_OVERRIDE = {
    "CUW": "curacao-cuw",  # 念のため残しておく（CUW削除済みだが安全のため）
}


def make_slug(en: str) -> str:
    """英語国名をURLスラグに変換する。"""
    s = en.lower()
    s = s.replace("'", "")
    s = s.replace(".", "")
    s = s.replace("ç", "c").replace("ã", "a").replace("é", "e").replace("ñ", "n")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


# ============================
# URL 定義（固定ページ）
# ============================
STATIC_URLS = [
    # (path, priority, changefreq)
    ("/",                           "1.0", "daily"),
    ("/results/",                   "0.9", "daily"),
    ("/calendar/",                  "0.8", "daily"),
    ("/standings/",                 "0.8", "daily"),
    ("/leagues/",                   "0.8", "weekly"),
    ("/privacy.html",               "0.3", "yearly"),
    ("/worldcup/",                  "0.9", "daily"),
    ("/worldcup/japan.html",        "0.9", "daily"),
    ("/worldcup/groups.html",       "0.7", "weekly"),
    ("/worldcup/bracket.html",      "0.7", "weekly"),
    ("/worldcup/rules.html",        "0.5", "monthly"),
    ("/worldcup/countries.html",    "0.7", "weekly"),
    # English pages (Phase 1)
    ("/en/",                        "0.9", "daily"),
    ("/en/results/",                "0.8", "daily"),
    ("/en/calendar/",               "0.7", "daily"),
    ("/en/standings/",              "0.7", "daily"),
    ("/en/players/",                "0.8", "weekly"),
    ("/en/clubs/",                  "0.7", "weekly"),
    ("/en/leagues/",                "0.7", "weekly"),
]


def get_lastmod_jst() -> str:
    """現在のJST日付を YYYY-MM-DD 形式で返す。"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def build_sitemap() -> str:
    """sitemap.xml の文字列を生成して返す。"""
    lastmod = get_lastmod_jst()

    # country_profiles.json から各国 slug を取得
    with open(PROFILES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    country_urls = []
    for tla, profile in data["profiles"].items():
        en_name = profile.get("en", "")
        slug = SLUG_OVERRIDE.get(tla) or make_slug(en_name)
        path = f"/worldcup/countries/{slug}/"
        country_urls.append((path, "0.6", "weekly"))

    # players.json から選手ページ slug を取得
    player_urls = []
    club_urls = []
    try:
        with open(PLAYERS_JSON, encoding="utf-8") as f:
            players_data = json.load(f)
        players = players_data.get("players", [])

        # 選手slug（重複対応）
        used_slugs = {}
        seen_clubs = {}
        for p in players:
            name_en = p.get("name_en", "")
            base = make_slug(name_en)
            if base not in used_slugs:
                used_slugs[base] = 1
                player_slug = base
            else:
                used_slugs[base] += 1
                player_slug = f"{base}-{used_slugs[base]}"
            player_urls.append((f"/players/{player_slug}/", "0.7", "weekly"))

            # クラブslug（ユニーク）
            club_en = p.get("club_en", "")
            if club_en and club_en not in seen_clubs:
                seen_clubs[club_en] = True
                club_slug = make_slug(club_en)
                club_urls.append((f"/clubs/{club_slug}/", "0.6", "weekly"))
    except Exception as e:
        print(f"[WARN] 選手/クラブデータ読み込みエラー: {e}")

    # 英語版選手・クラブページ
    en_player_urls = [(f"/en{path}", "0.6", "weekly") for path, _, _ in player_urls]
    en_club_urls = [(f"/en{path}", "0.5", "weekly") for path, _, _ in club_urls]

    # リーグページ（leagues/{slug}/ および en/leagues/{slug}/）
    league_urls = []
    try:
        import sys as _sys
        _scripts_dir = str(Path(__file__).parent)
        if _scripts_dir not in _sys.path:
            _sys.path.insert(0, _scripts_dir)
        from generate_league_pages import LEAGUE_SLUG_MAP, group_players_by_league
        league_groups = group_players_by_league(players)
        for league_ja, lg_players in league_groups.items():
            slug = LEAGUE_SLUG_MAP.get(league_ja)
            if slug:
                league_urls.append((f"/leagues/{slug}/", "0.7", "weekly"))
    except Exception as e:
        print(f"[WARN] リーグURLの取得エラー: {e}")

    en_league_urls = [(f"/en{path}", "0.6", "weekly") for path, _, _ in league_urls]

    all_urls = (
        STATIC_URLS
        + sorted(country_urls, key=lambda x: x[0])
        + sorted(player_urls, key=lambda x: x[0])
        + sorted(club_urls, key=lambda x: x[0])
        + sorted(league_urls, key=lambda x: x[0])
        + sorted(en_player_urls, key=lambda x: x[0])
        + sorted(en_club_urls, key=lambda x: x[0])
        + sorted(en_league_urls, key=lambda x: x[0])
    )

    # XML 生成
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for path, priority, changefreq in all_urls:
        loc = f"{BASE_URL}{path}"
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")

    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def validate_xml(xml_str: str) -> bool:
    """XML として parse できるか確認する。"""
    try:
        ET.fromstring(xml_str)
        return True
    except ET.ParseError as e:
        print(f"[ERROR] XML parse エラー: {e}")
        return False


def main():
    xml_str = build_sitemap()

    # 検証
    if not validate_xml(xml_str):
        raise SystemExit(1)

    # URL数カウント
    url_count = xml_str.count("<loc>")
    print(f"URL数: {url_count}")

    # 書き出し
    OUTPUT_FILE.write_text(xml_str, encoding="utf-8")
    print(f"生成完了: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
