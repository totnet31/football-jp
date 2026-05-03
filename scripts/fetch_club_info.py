#!/usr/bin/env python3
"""
fetch_club_info.py
Wikipedia のクラブ infobox から基本情報（創設年・スタジアム・監督等）を取得して
data/club_info.json に保存するスクリプト。

使い方: python3 scripts/fetch_club_info.py
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
OUTPUT_JSON = REPO_ROOT / "data" / "club_info.json"

# Wikipedia API エンドポイント
WIKI_API = "https://en.wikipedia.org/w/api.php"

# クラブ名 → Wikipedia 記事タイトル のマッピング
# Wikipedia 上でのクラブ公式記事名に合わせる
CLUB_WIKI_TITLES = {
    "Liverpool": "Liverpool F.C.",
    "Brighton & Hove Albion": "Brighton & Hove Albion F.C.",
    "Tottenham": "Tottenham Hotspur F.C.",
    "Crystal Palace": "Crystal Palace F.C.",
    "Southampton": "Southampton F.C.",
    "Bayern München": "FC Bayern Munich",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "FC Augsburg": "FC Augsburg",
    "FC St. Pauli": "FC St. Pauli",
    "Mainz 05": "1. FSV Mainz 05",
    "SC Freiburg": "Sport-Club Freiburg",
    "TSG Hoffenheim": "TSG 1899 Hoffenheim",
    "VfL Wolfsburg": "VfL Wolfsburg",
    "Werder Bremen": "SV Werder Bremen",
    "Real Sociedad": "Real Sociedad",
    "Mallorca": "RCD Mallorca",
    "Ajax": "AFC Ajax",
    "AZ Alkmaar": "AZ Alkmaar",
    "Feyenoord": "Feyenoord",
    "NEC Nijmegen": "NEC Nijmegen",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "Sporting CP": "Sporting CP",
    "Gil Vicente": "Gil Vicente F.C.",
    "Monaco": "AS Monaco FC",
    "Le Havre": "Le Havre AC",
    "Stade de Reims": "Stade de Reims",
    "Genk": "K.R.C. Genk",
    "Gent": "K.A.A. Gent",
    "OH Leuven": "Oud-Heverlee Leuven",
    "Royal Antwerp": "Royal Antwerp F.C.",
    "Sint-Truiden": "Sint-Truidense V.V.",
    "Westerlo": "K.V.C. Westerlo",
    "Parma": "Parma Calcio 1913",
    "Birmingham": "Birmingham City F.C.",
    "Blackburn": "Blackburn Rovers F.C.",
    "Coventry": "Coventry City F.C.",
    "Hull City": "Hull City A.F.C.",
    "Leeds": "Leeds United F.C.",
    "Queens Park Rangers": "Queens Park Rangers F.C.",
    "Stoke City": "Stoke City F.C.",
}


def fetch_wikipedia_infobox(wiki_title: str) -> dict:
    """Wikipedia API から infobox テキストを取得してパースする。"""
    params = {
        "action": "query",
        "titles": wiki_title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "football-jp/1.0 (https://football-jp.com; contact@football-jp.com)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    [ERROR] {wiki_title}: {e}")
        return {}

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return {}

    content = pages[0].get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
    if not content:
        return {}

    return parse_infobox(content)


def clean_wiki_value(val: str) -> str:
    """Wikitext の余分なマークアップを除去する。"""
    if not val:
        return ""
    # [[...]] リンク → テキストのみ
    val = re.sub(r'\[\[(?:[^\|\]]*\|)?([^\]]+)\]\]', r'\1', val)
    # {{...}} テンプレート除去（簡易）
    val = re.sub(r'\{\{[^}]*\}\}', '', val)
    # <ref>...</ref> 除去
    val = re.sub(r'<ref[^>]*>.*?</ref>', '', val, flags=re.DOTALL)
    val = re.sub(r'<ref[^/]*/>', '', val)
    # HTML タグ除去
    val = re.sub(r'<[^>]+>', '', val)
    # 余分な記号除去
    val = val.replace("'", "").replace('"', "").strip()
    # 複数スペース → 単一
    val = re.sub(r'\s+', ' ', val).strip()
    return val


def parse_infobox(content: str) -> dict:
    """Wikitext から infobox フィールドを抽出する。"""
    result = {}

    # infobox ブロック抽出（{{Infobox football club ... }}）
    infobox_match = re.search(r'\{\{[Ii]nfobox\s+(?:football|soccer)[^}]*?club', content)
    if not infobox_match:
        # より広いマッチ
        infobox_match = re.search(r'\{\{[Ii]nfobox', content)

    # フィールドを行単位でパース
    field_pattern = re.compile(r'^\s*\|\s*(\w+)\s*=\s*(.+?)(?=^\s*\||\Z)', re.MULTILINE | re.DOTALL)

    for match in field_pattern.finditer(content):
        key = match.group(1).strip().lower()
        val = match.group(2).strip()

        if key == "founded" or key == "year_formed":
            result["founded"] = clean_wiki_value(val)[:20]
        elif key == "city":
            result["city"] = clean_wiki_value(val)[:60]
        elif key == "country":
            result["country"] = clean_wiki_value(val)[:60]
        elif key in ("ground", "stadium"):
            v = clean_wiki_value(val)
            if v and len(v) < 100:
                result["stadium"] = v[:80]
        elif key == "capacity":
            v = clean_wiki_value(val)
            # 数字とカンマのみ抽出
            m = re.search(r'[\d,]+', v)
            if m:
                result["capacity"] = m.group(0)
        elif key == "website":
            v = clean_wiki_value(val)
            if "http" in v:
                m = re.search(r'https?://[^\s\|\]]+', val)
                if m:
                    result["website"] = m.group(0).rstrip('/')
            elif v and "." in v:
                result["website"] = "https://" + v
        elif key in ("manager", "head_coach"):
            result["manager"] = clean_wiki_value(val)[:80]
        elif key in ("chairman", "owner", "president"):
            if "chairman" not in result:
                result["chairman"] = clean_wiki_value(val)[:80]

    return result


def load_clubs() -> list:
    """players.json からクラブ一覧を返す。"""
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    players = data.get("players", [])
    seen = set()
    clubs = []
    for p in players:
        club_en = p.get("club_en", "")
        if club_en and club_en not in seen:
            seen.add(club_en)
            clubs.append({
                "club_en": club_en,
                "club_ja": p.get("club_ja", club_en),
            })
    return clubs


def main():
    # 既存データ読み込み（増分更新のため）
    existing = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"  既存データ: {len(existing)} クラブ")

    clubs = load_clubs()
    print(f"  対象クラブ数: {len(clubs)}")

    results = dict(existing)
    success = 0
    skipped = 0
    failed = 0

    for club in clubs:
        club_en = club["club_en"]

        # すでに取得済みの場合はスキップ（force_refresh したい場合はコメントアウト）
        if club_en in results and results[club_en].get("founded"):
            skipped += 1
            continue

        wiki_title = CLUB_WIKI_TITLES.get(club_en, f"{club_en} F.C.")
        print(f"  {club_en} → Wikipedia: {wiki_title}")

        info = fetch_wikipedia_infobox(wiki_title)
        if info:
            info["wiki_url"] = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(wiki_title)}"
            info["club_ja"] = club.get("club_ja", club_en)
            results[club_en] = info
            fields = ", ".join(k for k in info if k not in ("wiki_url", "club_ja"))
            print(f"    ✅ 取得成功: {fields}")
            success += 1
        else:
            print(f"    ⚠️ 取得失敗（データなし）")
            failed += 1
            results[club_en] = {"club_ja": club.get("club_ja", club_en), "wiki_url": ""}

        # Wikipedia API レート制限対応（1秒待機）
        time.sleep(1.0)

    # 保存
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n完了！ 成功:{success} スキップ:{skipped} 失敗:{failed}")
    print(f"  → {OUTPUT_JSON}")
    return results


if __name__ == "__main__":
    main()
