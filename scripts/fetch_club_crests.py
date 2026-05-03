#!/usr/bin/env python3
"""
fetch_club_crests.py
Wikipedia からクラブエンブレムを取得するスクリプト。
対象: football-data.org 無料プランで crest が提供されない Tier2/Tier3 リーグのクラブ
出力: assets/club_crests/{slug}.png / .svg
     data/club_crests.json  (slug -> 相対URLのマッピング)

使い方: python3 scripts/fetch_club_crests.py
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
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
MATCHES_JSON = REPO_ROOT / "data" / "matches.json"
OUTPUT_DIR = REPO_ROOT / "assets" / "club_crests"
MAPPING_JSON = REPO_ROOT / "data" / "club_crests.json"

# Wikipedia API エンドポイント
WIKI_API = "https://en.wikipedia.org/w/api.php"

# クラブ名 → Wikipedia 記事タイトル のオーバーライドマップ
# Wikipedia の記事タイトルと club_en が一致しない場合に使う
WIKI_TITLE_OVERRIDES = {
    "Stade de Reims": "Stade de Reims",
    "Genk": "KRC Genk",
    "Royal Antwerp": "Royal Antwerp F.C.",
    "Gent": "K.A.A. Gent",
    "Westerlo": "K.V.C. Westerlo",
    "OH Leuven": "Oud-Heverlee Leuven",
    "Sint-Truiden": "Sint-Truidense V.V.",
}

# クラブ名 → Wikipedia File名 の直接マッピング（infobox 調査済み）
# pageimages API でサムネイルが取れない場合にこちらを使う
WIKI_FILE_OVERRIDES = {
    "Stade de Reims": "Stade de Reims logo.svg",
    "Genk": "Logo_KRC_Genk.png",
    "Royal Antwerp": "Royal Antwerp Football Club logo.svg",
    "Gent": "KAA Gent logo.svg",
    "Westerlo": "K.V.C. Westerlo logo.png",
    "OH Leuven": "OH_LEUVEN.png",
    "Sint-Truiden": "K. Sint-Truidense V.V. logo.png",
}

# クラブのリーグ情報（Tier2/Tier3 判定用）
TIER2_TIER3_LEAGUES = {
    "リーグ・ドゥ",
    "ジュピラー・プロ・リーグ",
}


def make_slug(name_en: str) -> str:
    """英語名をURLスラグに変換する（generate_club_pages.pyと同じロジック）。"""
    s = name_en.lower()
    s = s.replace("'", "").replace(".", "")
    replacements = {
        "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "é": "e", "è": "e",
        "ê": "e", "ç": "c", "ã": "a", "á": "a", "à": "a", "ó": "o",
        "ô": "o", "ú": "u", "í": "i", "ï": "i", "ō": "o", "ū": "u",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def get_target_clubs() -> list:
    """
    対象クラブ（Tier2/3 で crest が取得できていないクラブ）を返す。
    players.json のリーグ情報で絞り込む。
    """
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    # matches.json から既存 crest を収集（club_en をキーにした辞書）
    existing_crests = {}
    if MATCHES_JSON.exists():
        with open(MATCHES_JSON, encoding="utf-8") as f:
            matches_raw = json.load(f)
        for m in matches_raw.get("matches", []):
            for side in ("home", "away"):
                cid = m.get(f"{side}_id")
                cen = m.get(f"{side}_en", "")
                crest = m.get(f"{side}_crest", "")
                if cid and cen and crest:
                    existing_crests[cen] = crest

    # club_id が None または crest が無いクラブを Tier2/3 から抽出
    seen: dict[str, dict] = {}
    for p in players:
        league = p.get("league_ja", "")
        if league not in TIER2_TIER3_LEAGUES:
            continue
        club_en = p.get("club_en", "")
        club_ja = p.get("club_ja", "")
        if not club_en or club_en in seen:
            continue
        # 既に crest がある場合はスキップ
        if club_en in existing_crests:
            print(f"  スキップ（既存 crest あり）: {club_en}")
            continue
        seen[club_en] = {
            "club_en": club_en,
            "club_ja": club_ja,
            "league_ja": league,
            "slug": make_slug(club_en),
        }

    return list(seen.values())


def wikipedia_api(params: dict) -> dict:
    """Wikipedia API を呼び出して JSON を返す。"""
    params["format"] = "json"
    params["action"] = params.get("action", "query")
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "football-jp-bot/1.0 (https://football-jp.com)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    Wikipedia API エラー: {e}")
        return {}


def resolve_wiki_image_url(file_name: str) -> str:
    """
    Wikipedia の File:Foo.svg などを実際の画像 URL に解決する。
    MediaWiki の imageinfo API を使用。
    """
    # 先頭の "File:" を除去
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


def get_club_logo_from_wikipedia(club_en: str) -> str:
    """
    Wikipedia のクラブページから logo/crest 画像 URL を取得する。
    戻り値: 画像の直接 URL（空文字列は失敗）

    優先順位:
    1. WIKI_FILE_OVERRIDES に直接 File 名がある場合 → imageinfo API で URL 解決
    2. pageimages API でサムネイルが取れる場合 → thumb URL から元ファイル URL を構築
    3. wikitext の infobox から image フィールドを探す
    """
    # 1. 直接 File 名マッピングが存在する場合（最も信頼性が高い）
    if club_en in WIKI_FILE_OVERRIDES:
        file_name = WIKI_FILE_OVERRIDES[club_en]
        print(f"    既知ファイル名使用: {file_name}")
        url = resolve_wiki_image_url(file_name)
        if url:
            return url
        print(f"    imageinfo API 失敗、pageimages にフォールバック")

    # Wikipedia 記事タイトルを決定（オーバーライド優先）
    wiki_title = WIKI_TITLE_OVERRIDES.get(club_en, club_en)

    # 2. pageimages API でサムネイル取得を試みる
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
            print(f"    ページが見つかりません: {wiki_title}")
            break

        thumb = page.get("thumbnail", {}).get("source", "")
        if thumb:
            # thumb URL から元ファイルの URL を構築
            # 例: https://...thumb/X/XX/File.svg/300px-File.svg.png → https://.../X/XX/File.svg
            base_url = re.sub(r"(/thumb/.*?)(/\d+px-[^/]+)$", r"\1", thumb)
            if base_url != thumb:
                print(f"    元ファイル URL: {base_url}")
                return base_url
            return thumb

    # 3. wikitext の infobox から image フィールドを探す（フォールバック）
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
                        # ファイル名だけの場合（.svg/.png/.jpg で終わる文字列）
                        fn_match = re.search(r"([^\|\[\]\{\}\s]+\.(?:svg|png|jpg|jpeg))", img_text, re.IGNORECASE)
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
    req = urllib.request.Request(url, headers={
        "User-Agent": "football-jp-bot/1.0 (https://football-jp.com)"
    })
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
    print("クラブエンブレム取得スクリプト開始")
    print("=" * 50)

    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 既存マッピング読み込み
    if MAPPING_JSON.exists():
        with open(MAPPING_JSON, encoding="utf-8") as f:
            mapping = json.load(f)
    else:
        mapping = {}

    # 対象クラブ取得
    target_clubs = get_target_clubs()
    print(f"\n対象クラブ数: {len(target_clubs)}")

    success_list = []
    failure_list = []

    for club in target_clubs:
        club_en = club["club_en"]
        club_ja = club["club_ja"]
        slug = club["slug"]
        league = club["league_ja"]

        print(f"\n処理中: {club_ja}（{club_en}）[{league}]")

        # 既にマッピングに存在かつファイルも存在すればスキップ
        if slug in mapping:
            local_path = REPO_ROOT / mapping[slug].lstrip("/")
            if local_path.exists():
                print(f"  スキップ（マッピング済み + ファイル存在）: {mapping[slug]}")
                success_list.append((club_ja, club_en, mapping[slug]))
                continue

        # Wikipedia から URL 取得
        img_url = get_club_logo_from_wikipedia(club_en)
        if not img_url:
            print(f"  失敗: Wikipedia から画像 URL を取得できませんでした")
            failure_list.append(club_en)
            time.sleep(1)
            continue

        print(f"  取得 URL: {img_url}")

        # 拡張子を決定（SVG の場合は PNG で保存先を設定）
        url_lower = img_url.lower()
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

        # ダウンロード
        if download_image(img_url, dest_path):
            size = dest_path.stat().st_size
            print(f"  保存成功: {dest_path} ({size:,} bytes)")
            mapping[slug] = relative_url
            success_list.append((club_ja, club_en, relative_url))
        else:
            print(f"  ダウンロード失敗")
            failure_list.append(club_en)

        # Wikipedia への過剰アクセスを避けるため少し待機
        time.sleep(1.5)

    # マッピング JSON 保存
    with open(MAPPING_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\nマッピング保存: {MAPPING_JSON}")

    # 結果サマリー
    print("\n" + "=" * 50)
    print(f"完了: {len(success_list)} クラブ成功 / {len(failure_list)} クラブ失敗")

    if success_list:
        print("\n[成功]")
        for club_ja, club_en, url in success_list:
            print(f"  {club_ja}（{club_en}）→ {url}")

    if failure_list:
        print("\n[失敗]")
        for club_en in failure_list:
            print(f"  {club_en}")

    return len(success_list), failure_list


if __name__ == "__main__":
    main()
