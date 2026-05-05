#!/usr/bin/env python3
"""
fetch_belgium_crests.py
ジュピラー・プロ・リーグ（competition ID 144）の16クラブの
エンブレム画像を Wikipedia から取得し、
assets/club_crests/ に保存して data/standings.json を更新する。

使い方: python3 scripts/fetch_belgium_crests.py
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
STANDINGS_JSON = REPO_ROOT / "data" / "standings.json"
MAPPING_JSON = REPO_ROOT / "data" / "club_crests.json"
OUTPUT_DIR = REPO_ROOT / "assets" / "club_crests"

# Wikipedia API エンドポイント
WIKI_API = "https://en.wikipedia.org/w/api.php"

# チームの英語名 → スラッグ のマッピング
# （data/standings.json の team_en → ローカルファイル名）
SLUG_MAP = {
    "Genk": "genk",
    "Club Brugge": "club-brugge",
    "Union SG": "union-saint-gilloise",
    "Anderlecht": "anderlecht",
    "Antwerp": "royal-antwerp",
    "Gent": "gent",
    "Standard Liège": "standard-liege",
    "Mechelen": "mechelen",
    "Westerlo": "westerlo",
    "Charleroi": "charleroi",
    "OH Leuven": "oh-leuven",
    "Dender EH": "dender",
    "Cercle Brugge": "cercle-brugge",
    "Sint-Truiden": "sint-truiden",
    "Kortrijk": "kortrijk",
    "Beerschot": "beerschot",
}

# チームの英語名 → Wikipedia 記事タイトル のオーバーライド
WIKI_TITLE_OVERRIDES = {
    "Genk": "KRC Genk",
    "Club Brugge": "Club Brugge K.V.",
    "Union SG": "Royale Union Saint-Gilloise",
    "Anderlecht": "R.S.C. Anderlecht",
    "Antwerp": "Royal Antwerp F.C.",
    "Gent": "K.A.A. Gent",
    "Standard Liège": "Standard Liège",
    "Mechelen": "K.V. Mechelen",
    "Westerlo": "K.V.C. Westerlo",
    "Charleroi": "R. Charleroi S.C.",
    "OH Leuven": "Oud-Heverlee Leuven",
    "Dender EH": "F.C. Dender EH",
    "Cercle Brugge": "Cercle Brugge K.S.V.",
    "Sint-Truiden": "Sint-Truidense V.V.",
    "Kortrijk": "K.V. Kortrijk",
    "Beerschot": "Beerschot V.A.",
}

# チームの英語名 → Wikipedia File名 の直接マッピング（調査済み）
WIKI_FILE_OVERRIDES = {
    "Genk": "Logo_KRC_Genk.png",
    "Club Brugge": "Club Brugge KV logo.svg",
    "Union SG": "Royale Union Saint-Gilloise logo.svg",
    "Anderlecht": "R.S.C. Anderlecht.svg",
    "Antwerp": "Royal Antwerp Football Club logo.svg",
    "Gent": "KAA Gent logo.svg",
    "Standard Liège": "Standard Liège logo.svg",
    "Mechelen": "KV Mechelen logo.svg",
    "Westerlo": "K.V.C. Westerlo logo.png",
    "Charleroi": "Royal Charleroi Sporting Club logo.svg",
    "OH Leuven": "OH_LEUVEN.png",
    "Dender EH": "FCVDenderEH.png",
    "Cercle Brugge": "Logo_Cercle_Brugge_2022.png",
    "Sint-Truiden": "K. Sint-Truidense V.V. logo.png",
    "Kortrijk": "KV Kortrijk logo 2016.svg",
    "Beerschot": "Beerschot AC logo.svg",
}


def wikipedia_api(params: dict) -> dict:
    """Wikipedia API を呼び出して JSON を返す。"""
    params["format"] = "json"
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "football-jp-bot/1.0 (https://football-jp.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    Wikipedia API エラー: {e}")
        return {}


def resolve_wiki_image_url(file_name: str) -> str:
    """File:Foo.svg を実際の画像 URL に解決する（imageinfo API）。"""
    if file_name.startswith("File:"):
        file_name = file_name[5:]

    params = {
        "action": "query",
        "titles": f"File:{file_name}",
        "prop": "imageinfo",
        "iiprop": "url",
    }
    data = wikipedia_api(params)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        ii = page.get("imageinfo", [])
        if ii:
            return ii[0].get("url", "")
    return ""


def get_club_logo_from_wikipedia(team_en: str) -> str:
    """
    Wikipedia からクラブロゴ画像 URL を取得する。
    優先順位:
    1. WIKI_FILE_OVERRIDES → imageinfo API で URL 解決
    2. pageimages API でサムネイル取得
    3. wikitext infobox の image フィールド解析
    """
    # 1. 直接 File 名マッピング
    if team_en in WIKI_FILE_OVERRIDES:
        file_name = WIKI_FILE_OVERRIDES[team_en]
        print(f"    既知ファイル名: {file_name}")
        url = resolve_wiki_image_url(file_name)
        if url:
            return url
        print(f"    imageinfo 失敗 → pageimages にフォールバック")

    wiki_title = WIKI_TITLE_OVERRIDES.get(team_en, team_en)

    # 2. pageimages API
    params = {
        "action": "query",
        "titles": wiki_title,
        "prop": "pageimages",
        "pithumbsize": 300,
        "redirects": "1",
    }
    data = wikipedia_api(params)
    pages = data.get("query", {}).get("pages", {})

    for page_id, page in pages.items():
        if page_id == "-1":
            print(f"    ページ未発見: {wiki_title}")
            break
        thumb = page.get("thumbnail", {}).get("source", "")
        if thumb:
            base_url = re.sub(r"(/thumb/.*?)(/\d+px-[^/]+)$", r"\1", thumb)
            if base_url != thumb:
                print(f"    元ファイル URL: {base_url}")
                return base_url
            return thumb

    # 3. wikitext infobox フォールバック
    params2 = {
        "action": "query",
        "titles": wiki_title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "rvsection": "0",
        "redirects": "1",
    }
    data2 = wikipedia_api(params2)
    pages2 = data2.get("query", {}).get("pages", {})

    for page_id, page in pages2.items():
        if page_id == "-1":
            return ""
        revs = page.get("revisions", [])
        if revs:
            content = revs[0].get("slots", {}).get("main", {}).get("*", "")
            patterns = [
                r"\|\s*image\s*=\s*([^\|\[\]\n]+)",
                r"\|\s*(?:logo|badge|crest|emblem)\s*=\s*([^\|\[\]\n]+)",
            ]
            for pattern in patterns:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    img_text = m.group(1).strip()
                    file_match = re.search(r"File:([^\|\]\[\{\}]+)", img_text, re.IGNORECASE)
                    if file_match:
                        file_name = file_match.group(1).strip()
                    else:
                        fn_match = re.search(
                            r"([^\|\[\]\{\}\s]+\.(?:svg|png|jpg|jpeg))",
                            img_text,
                            re.IGNORECASE,
                        )
                        if fn_match:
                            file_name = fn_match.group(1).strip()
                        else:
                            continue
                    if file_name:
                        print(f"    wikitext からファイル名取得: {file_name}")
                        url = resolve_wiki_image_url(file_name)
                        if url:
                            return url
    return ""


def download_image(url: str, dest: Path) -> bool:
    """画像をダウンロードして dest に保存する。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "football-jp-bot/1.0 (https://football-jp.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"    ダウンロードエラー: {e} → {url}")
        return False


def main():
    print("ジュピラー・プロ・リーグ クラブエンブレム取得スクリプト開始")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 既存マッピング読み込み
    if MAPPING_JSON.exists():
        with open(MAPPING_JSON, encoding="utf-8") as f:
            mapping = json.load(f)
    else:
        mapping = {}

    # standings.json 読み込み
    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_data = json.load(f)

    table = standings_data["competitions"]["144"]["standings"][0]["table"]
    print(f"対象チーム数: {len(table)}")

    success_list = []
    failure_list = []

    for entry in table:
        team_en = entry["team_en"]
        team_ja = entry["team_ja"]
        slug = SLUG_MAP.get(team_en)

        if not slug:
            print(f"\n警告: スラッグ未定義 → {team_en}（スキップ）")
            failure_list.append((team_en, "スラッグ未定義"))
            continue

        print(f"\n処理中: {team_ja}（{team_en}）→ {slug}")

        # 既にファイルが存在すればスキップ
        for ext in (".svg", ".png", ".jpg"):
            existing = OUTPUT_DIR / f"{slug}{ext}"
            if existing.exists():
                relative_url = f"/assets/club_crests/{slug}{ext}"
                print(f"  スキップ（既存ファイルあり）: {relative_url}")
                mapping[slug] = relative_url
                # standings.json にも反映
                entry["team_crest"] = relative_url
                success_list.append((team_ja, team_en, relative_url, "既存"))
                break
        else:
            # 新規取得
            img_url = get_club_logo_from_wikipedia(team_en)
            if not img_url:
                print(f"  失敗: Wikipedia から画像 URL を取得できませんでした")
                failure_list.append((team_en, "URL取得失敗"))
                time.sleep(1)
                continue

            print(f"  取得 URL: {img_url}")

            # 拡張子を決定
            url_lower = img_url.lower().split("?")[0]
            if ".svg" in url_lower:
                ext = ".svg"
            elif ".png" in url_lower:
                ext = ".png"
            elif ".jpg" in url_lower or ".jpeg" in url_lower:
                ext = ".jpg"
            else:
                ext = ".png"

            dest_path = OUTPUT_DIR / f"{slug}{ext}"
            relative_url = f"/assets/club_crests/{slug}{ext}"

            if download_image(img_url, dest_path):
                size = dest_path.stat().st_size
                print(f"  保存成功: {dest_path.name} ({size:,} bytes)")
                mapping[slug] = relative_url
                entry["team_crest"] = relative_url
                success_list.append((team_ja, team_en, relative_url, "新規取得"))
            else:
                print(f"  ダウンロード失敗")
                failure_list.append((team_en, "ダウンロード失敗"))

            time.sleep(1.5)

    # マッピング JSON 保存
    with open(MAPPING_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\nマッピング保存: {MAPPING_JSON}")

    # standings.json 更新
    with open(STANDINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(standings_data, f, ensure_ascii=False, indent=2)
    print(f"standings.json 更新: {STANDINGS_JSON}")

    # 結果サマリー
    print("\n" + "=" * 60)
    print(f"完了: {len(success_list)} クラブ成功 / {len(failure_list)} クラブ失敗")

    if success_list:
        print("\n[成功]")
        for team_ja, team_en, url, status in success_list:
            print(f"  {team_ja}（{team_en}）→ {url} [{status}]")

    if failure_list:
        print("\n[失敗]")
        for team_en, reason in failure_list:
            print(f"  {team_en}: {reason}")

    return len(success_list), failure_list


if __name__ == "__main__":
    main()
