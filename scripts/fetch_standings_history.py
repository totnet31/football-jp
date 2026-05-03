#!/usr/bin/env python3
"""
fetch_standings_history.py
Wikipedia の各リーグ season ページから「節ごとの順位」を取得する。

対象リーグ:
  - 39: Premier League   → 2025–26 Premier League
  - 140: La Liga         → 2025–26 La Liga
  - 78: Bundesliga       → 2025–26 Bundesliga
  - 135: Serie A         → 2025–26 Serie A
  - 61: Ligue 1          → 2025–26 Ligue 1
  - 88: Eredivisie       → 2025–26 Eredivisie
  - 94: Primeira Liga    → 2025–26 Primeira Liga

出力: data/standings_history.json
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT_JSON = DATA / "standings_history.json"
JST = timezone(timedelta(hours=9))

# リーグID → Wikipedia 記事タイトル
LEAGUE_CONFIGS = {
    "39": {
        "name": "Premier League",
        "name_ja": "プレミアリーグ",
        "wiki_title": "2025–26_Premier_League",
        "matchdays": 38,
    },
    "140": {
        "name": "La Liga",
        "name_ja": "ラ・リーガ",
        "wiki_title": "2025–26_La_Liga",
        "matchdays": 38,
    },
    "78": {
        "name": "Bundesliga",
        "name_ja": "ブンデスリーガ",
        "wiki_title": "2025–26_Bundesliga",
        "matchdays": 34,
    },
    "135": {
        "name": "Serie A",
        "name_ja": "セリエA",
        "wiki_title": "2025–26_Serie_A",
        "matchdays": 38,
    },
    "61": {
        "name": "Ligue 1",
        "name_ja": "リーグ・アン",
        "wiki_title": "2025–26_Ligue_1",
        "matchdays": 34,
    },
    "88": {
        "name": "Eredivisie",
        "name_ja": "エールディビジ",
        "wiki_title": "2025–26_Eredivisie",
        "matchdays": 34,
    },
    "94": {
        "name": "Primeira Liga",
        "name_ja": "プリメイラ・リーガ",
        "wiki_title": "2025–26_Primeira_Liga",
        "matchdays": 34,
    },
}

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "football-jp/1.0 (https://football-jp.com; bot)"}


def fetch_wikipedia_wikitext(title: str):
    """Wikipedia の記事の wikitext を取得する"""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    url = WIKIPEDIA_API + "?" + urlencode(params)
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        revisions = page.get("revisions", [])
        if not revisions:
            return None
        return revisions[0].get("slots", {}).get("main", {}).get("content", "")
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        print(f"  [WIKI ERROR] {title}: {e}", file=sys.stderr)
        return None


def fetch_wikipedia_html(title: str):
    """Wikipedia の記事の HTML を取得する（パース補助用）"""
    url = f"https://en.wikipedia.org/wiki/{quote(title)}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        print(f"  [WIKI HTML ERROR] {title}: {e}", file=sys.stderr)
        return None


def clean_wiki_cell(cell: str) -> str:
    """wikitext セルの余分な記法を除去して数値文字列を返す"""
    # テンプレート除去: {{...}}
    cell = re.sub(r"\{\{[^}]*\}\}", "", cell)
    # リンク除去: [[...]]
    cell = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", cell)
    # HTML タグ除去
    cell = re.sub(r"<[^>]+>", "", cell)
    # ref タグ除去
    cell = re.sub(r"<ref[^>]*>.*?</ref>", "", cell, flags=re.DOTALL)
    return cell.strip()


def parse_positions_table_wikitext(wikitext: str):
    """
    wikitext から「Positions by round」または「positions」表を探してパースする。
    戻り値: {club_name: [position_round1, position_round2, ...]}
    """
    positions = {}

    # 「positions by round」「position by matchday」などのセクションを探す
    # 典型的な構造:
    # {| class="wikitable"
    # ! Team !! 1 !! 2 !! 3 ...
    # |-
    # | Liverpool || 1 || 2 || 1 ...
    # |}

    # まず "positions" 関連のテーブルを探す
    # wikitext 全体からテーブルブロックを抽出
    table_pattern = re.compile(
        r"(?:Positions? by (?:round|matchday|gameweek)|round-by-round)"
        r".*?(\{\|.*?\|\})",
        re.IGNORECASE | re.DOTALL
    )

    match = table_pattern.search(wikitext)
    if not match:
        # より広い検索: 「position」という見出しの後のテーブル
        alt_pattern = re.compile(
            r"==+\s*(?:Positions?|Table by round|Standings? by round)\s*==+"
            r".*?(\{\|.*?\|\})",
            re.IGNORECASE | re.DOTALL
        )
        match = alt_pattern.search(wikitext)

    if not match:
        return {}

    table_text = match.group(1)
    rows = re.split(r"\|-", table_text)

    header_cols = []
    for row in rows:
        stripped = row.strip()
        if not stripped:
            continue

        # ヘッダ行 (! で始まる)
        if stripped.startswith("!"):
            cols = re.split(r"\!\!|\n!", stripped)
            header_cols = [clean_wiki_cell(c) for c in cols]
            continue

        # データ行 (| で始まる)
        if stripped.startswith("|") and not stripped.startswith("|}") and not stripped.startswith("|+"):
            cols = re.split(r"\|\||\n\|", stripped)
            if not cols:
                continue
            club_raw = clean_wiki_cell(cols[0])
            club_raw = club_raw.lstrip("|").strip()
            if not club_raw or club_raw.startswith("{"):
                continue
            # 数字の列のみ抽出
            pos_list = []
            for c in cols[1:]:
                val = clean_wiki_cell(c)
                # 数値のみ
                m = re.match(r"^(\d+)$", val)
                if m:
                    pos_list.append(int(m.group(1)))
                else:
                    pos_list.append(None)
            if pos_list:
                positions[club_raw] = pos_list

    return positions


def parse_positions_html(html: str, league_name: str):
    """
    Wikipedia HTML から positions テーブルをパースする。
    wikitext パースが失敗した場合のフォールバック。
    """
    positions = {}

    # <table> タグで囲まれた部分を探す
    # 「Positions by round」見出しの直後のテーブルを優先
    pos_section = re.search(
        r"[Pp]ositions?\s+by\s+(?:round|matchday|gameweek|week)"
        r"(.*?)</table>",
        html,
        re.DOTALL
    )
    if not pos_section:
        return {}

    table_html = pos_section.group(1)

    # tr → td/th の解析
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    header_count = 0
    for row in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
        cells_clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if not cells_clean:
            continue

        # ヘッダ行（数字だけで構成されているか確認）
        if all(re.match(r"^\d+$", c) or c in ("Team", "Club", "") for c in cells_clean):
            header_count += 1
            continue

        # データ行
        if len(cells_clean) >= 2:
            club_name = cells_clean[0]
            pos_values = []
            for c in cells_clean[1:]:
                m = re.match(r"^(\d+)$", c)
                pos_values.append(int(m.group(1)) if m else None)
            if pos_values and club_name:
                positions[club_name] = pos_values

    return positions


def normalize_club_name(raw: str) -> str:
    """クラブ名の余分な記法・注記を除去して正規化する"""
    # wikitext の残渣を除去
    name = re.sub(r"\(.*?\)", "", raw).strip()
    name = re.sub(r"\[.*?\]", "", name).strip()
    name = re.sub(r"''+", "", name).strip()
    return name


def get_current_matchday(positions):
    """最後に全クラブがデータを持っている節番号を返す"""
    if not positions:
        return 0
    min_len = min(
        sum(1 for v in vals if v is not None)
        for vals in positions.values()
        if vals
    )
    return min_len


def fetch_league_standings_history(league_id: str, config: dict):
    """1リーグ分の節別順位を取得してパースする"""
    wiki_title = config["wiki_title"]
    print(f"  [{config['name']}] Wikipedia: {wiki_title}")

    # wikitext を試みる
    wikitext = fetch_wikipedia_wikitext(wiki_title)
    positions = {}

    if wikitext:
        positions = parse_positions_table_wikitext(wikitext)

    # wikitext パースが失敗したら HTML フォールバック
    if not positions:
        print(f"    wikitext パース失敗 → HTML フォールバック試行")
        html = fetch_wikipedia_html(wiki_title)
        if html:
            positions = parse_positions_html(html, config["name"])

    if not positions:
        print(f"    [WARN] {config['name']}: 順位データ取得失敗", file=sys.stderr)
        return None

    # クラブ名正規化
    normalized = {}
    for raw_name, vals in positions.items():
        clean = normalize_club_name(raw_name)
        if clean:
            normalized[clean] = vals

    current_matchday = get_current_matchday(normalized)
    print(f"    取得成功: {len(normalized)} クラブ × {current_matchday} 節分")

    return {
        "name": config["name"],
        "name_ja": config["name_ja"],
        "matchdays": config["matchdays"],
        "current_matchday": current_matchday,
        "positions": normalized,
    }


def main():
    print("=" * 60)
    print("[INFO] fetch_standings_history.py 開始")
    print("  Wikipedia から各リーグの節別順位を取得します")
    print("  対象: PL / La Liga / Bundesliga / Serie A / Ligue 1 / Eredivisie / Primeira Liga")
    print("=" * 60)

    # 既存データをロード（差分更新用）
    existing: dict = {}
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, encoding="utf-8") as f:
                raw = json.load(f)
            existing = raw.get("competitions", {})
            print(f"[INFO] 既存データ: {len(existing)} リーグ分をロード")
        except Exception:
            pass

    result_comps: dict = {}
    success = 0
    fail = 0

    for league_id, config in LEAGUE_CONFIGS.items():
        try:
            data = fetch_league_standings_history(league_id, config)
            if data:
                result_comps[league_id] = data
                success += 1
            else:
                # 既存データがあれば保持
                if league_id in existing:
                    result_comps[league_id] = existing[league_id]
                    print(f"    [{config['name']}] 既存データを保持")
                fail += 1
            # Wikipedia への連続アクセスを抑制
            time.sleep(1.5)
        except Exception as e:
            print(f"  [ERROR] {config['name']}: {e}", file=sys.stderr)
            if league_id in existing:
                result_comps[league_id] = existing[league_id]
            fail += 1

    # 保存
    output = {
        "updated": datetime.now(JST).isoformat(),
        "competitions": result_comps,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] 節別順位取得完了")
    print(f"  成功: {success} リーグ / 失敗: {fail} リーグ")
    print(f"  保存先: {OUTPUT_JSON}")

    # サンプル出力
    for lid, comp_data in result_comps.items():
        name = comp_data.get("name", lid)
        current_md = comp_data.get("current_matchday", 0)
        clubs = list(comp_data.get("positions", {}).keys())[:3]
        print(f"\n  [{name}] 第{current_md}節まで / クラブ例: {', '.join(clubs)}")


if __name__ == "__main__":
    main()
