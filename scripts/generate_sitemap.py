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
    ("/privacy.html",               "0.3", "yearly"),
    ("/worldcup/",                  "0.9", "daily"),
    ("/worldcup/japan.html",        "0.9", "daily"),
    ("/worldcup/groups.html",       "0.7", "weekly"),
    ("/worldcup/bracket.html",      "0.7", "weekly"),
    ("/worldcup/rules.html",        "0.5", "monthly"),
    ("/worldcup/countries.html",    "0.7", "weekly"),
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

    all_urls = STATIC_URLS + sorted(country_urls, key=lambda x: x[0])

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
