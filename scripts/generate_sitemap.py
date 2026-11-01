#!/usr/bin/env python3
"""
generate_sitemap.py
sitemap.xml を自動生成するスクリプト。
出力先: {REPO_ROOT}/sitemap.xml
使い方: python3 scripts/generate_sitemap.py
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = REPO_ROOT / "sitemap.xml"
COLUMN_DIR = REPO_ROOT / "column"

BASE_URL = "https://football-jp.com"

def get_lastmod_jst() -> str:
    """現在のJST日付を YYYY-MM-DD 形式で返す。"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


# ============================
# 検索に出すページだけを載せる（2026-11-01 AdSense「有用性の低いコンテンツ」対応）
# _headers で noindex にしている区分（players / clubs / leagues / standings / results /
# calendar / en / worldcup）は sitemap に載せない。noindex を外した区分ができたら
# ここに足すこと。
# ============================
INDEXABLE_STATIC_URLS = [
    # (path, priority, changefreq)
    ("/",         "1.0", "daily"),
    ("/column/",  "0.8", "weekly"),
    ("/about",    "0.3", "yearly"),
    ("/privacy",  "0.3", "yearly"),
    ("/contact",  "0.3", "yearly"),
]


def build_sitemap() -> str:
    """sitemap.xml の文字列を生成して返す（検索に出すページだけ）。"""
    lastmod = get_lastmod_jst()

    # column/ 配下を動的スキャン
    column_urls = []
    if COLUMN_DIR.exists():
        for d in sorted(COLUMN_DIR.iterdir()):
            if d.is_dir() and (d / "index.html").exists():
                column_urls.append((f"/column/{d.name}/", "0.7", "weekly"))

    all_urls = INDEXABLE_STATIC_URLS + column_urls

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
