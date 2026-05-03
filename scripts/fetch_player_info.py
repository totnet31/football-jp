#!/usr/bin/env python3
"""
fetch_player_info.py
Wikipedia 英語版 infobox から選手プロフィール情報を取得する。
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
HEADERS = {"User-Agent": "football-jp/1.0 (https://football-jp.com; contact@football-jp.com)"}


def wiki_api_get(params):
    # type: (dict) -> dict
    """Wikipedia API GET リクエスト。"""
    params["format"] = "json"
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
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


def clean_wiki_text(text):
    # type: (str) -> str
    """wikitextから余計な記法を除去して平文にする。"""
    if not text:
        return ""
    # [[Link|Text]] → Text
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
    # {{template|...}} の単純除去（ネスト非対応）
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    # ''bold'' or '''bold'''
    text = re.sub(r"'{2,3}", '', text)
    # HTMLタグ除去
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


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


def fetch_player_info(name_en):
    # type: (str) -> dict
    """1選手分の情報を取得して辞書で返す。"""
    info = {
        "wiki_url": None,
        "height_cm": None,
        "weight_kg": None,
        "birth_date": None,
        "birth_place": None,
        "foot": None,
        "career": [],
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

    # 出身地
    birth_place_raw = fields.get("birth_place", "")
    info["birth_place"] = clean_wiki_text(birth_place_raw)

    # 利き足
    foot_raw = fields.get("foot", "")
    info["foot"] = parse_foot(foot_raw)

    # キャリア
    info["career"] = parse_career(wikitext)

    # SNS
    social = extract_social_links(wikitext)
    info["twitter"] = social["twitter"]
    info["instagram"] = social["instagram"]
    info["official_url"] = social["official_url"]

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

    result = {}
    success = 0
    fail = 0

    for i, player in enumerate(players):
        name_en = player.get("name_en", "")
        name_ja = player.get("name_ja", "")
        print("[{}/{}] {} ({})".format(i + 1, len(players), name_ja, name_en))

        try:
            info = fetch_player_info(name_en)
            result[name_en] = info
            if info.get("height_cm") or info.get("birth_date") or info.get("career"):
                success += 1
            else:
                fail += 1
        except Exception as e:
            print("    Error: {}".format(e))
            result[name_en] = existing.get(name_en, {
                "wiki_url": None,
                "height_cm": None,
                "weight_kg": None,
                "birth_date": None,
                "birth_place": None,
                "foot": None,
                "career": [],
                "twitter": None,
                "instagram": None,
                "official_url": None,
            })
            fail += 1

        # Wikipedia API への負荷軽減
        time.sleep(0.5)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n完了: 取得成功 {}/{} 選手".format(success, len(players)))
    print("保存先: {}".format(OUTPUT_JSON))


if __name__ == "__main__":
    main()
