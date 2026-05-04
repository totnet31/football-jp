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
from typing import Dict, List, Optional
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
    # ref タグ除去（先に行う）
    cell = re.sub(r"<ref[^>]*/?>.*?</ref>", "", cell, flags=re.DOTALL)
    cell = re.sub(r"<ref[^>]*/?>", "", cell)
    # テンプレート除去: {{...}} (ネスト対応)
    for _ in range(5):
        cell = re.sub(r"\{\{[^{}]*\}\}", "", cell)
    # リンク除去: [[Page|Display]] → Display, [[Page]] → Page
    cell = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", cell)
    # HTML タグ除去
    cell = re.sub(r"<[^>]+>", "", cell)
    return cell.strip()


def extract_club_name_from_cell(cell: str) -> str:
    """
    1列目のセル文字列からクラブ名を取り出す。
    例:
      ' align=left|[[Liverpool F.C.|Liverpool]]' → 'Liverpool'
      ' align="left"|[[FC Barcelona|Barcelona]]' → 'Barcelona'
      '[[Arsenal F.C.|Arsenal]]'                 → 'Arsenal'
      'align=left| Liverpool'                    → 'Liverpool'
    """
    raw = cell.strip()
    # 先頭から "key=value|" や "key=\"value\"|" のような属性プレフィックスを除去
    # 例: align=left| / align="left"| / style="..."|
    raw = re.sub(r'^(?:[\w-]+=(?:"[^"]*"|\'[^\']*\'|[^|"\'\s]+)\|)+', "", raw)
    raw = raw.strip().lstrip("|").strip()
    # [[Page|Display]] → Display
    m = re.match(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", raw)
    if m:
        return m.group(1).strip()
    # テンプレート・HTML タグを除去して残りをクラブ名とする
    raw = re.sub(r"\{\{[^{}]*\}\}", "", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return raw.strip()


def find_positions_table(wikitext: str) -> Optional[str]:
    """
    wikitext から「Positions by round」セクション直下の最初の wikitable を返す。
    テーブルのネスト（{| ... |}）を正しく対応してブロックを抽出する。
    """
    # セクション見出しを探す（複数パターン）
    section_patterns = [
        r"==+\s*Positions?\s+by\s+round\s*==+",
        r"==+\s*Round-by-round\s+positions?\s*==+",
        r"==+\s*Positions?\s+by\s+matchday\s*==+",
        r"==+\s*Positions?\s+by\s+gameweek\s*==+",
        r"==+\s*Table\s+by\s+round\s*==+",
        r"==+\s*Standings?\s+by\s+round\s*==+",
    ]

    section_start = -1
    for pat in section_patterns:
        m = re.search(pat, wikitext, re.IGNORECASE)
        if m:
            section_start = m.end()
            break

    if section_start == -1:
        # フォールバック: "Position" を含む見出しを緩く探す
        m = re.search(r"==+\s*(?:Position|Round)[^=]*==+", wikitext, re.IGNORECASE)
        if m:
            section_start = m.end()

    if section_start == -1:
        return None

    # セクション先頭から次の == 見出し（同レベル以上）の前まで
    section_text = wikitext[section_start:]

    # 次の上位見出しで切り詰め（深いサブ見出しは除外）
    next_section = re.search(r"\n==+[^=]", section_text)
    if next_section:
        section_text = section_text[: next_section.start()]

    # section_text 内で最初の {| を探し、ネスト対応でテーブルブロックを抽出
    start = section_text.find("{|")
    if start == -1:
        return None

    depth = 0
    i = start
    while i < len(section_text):
        if section_text[i : i + 2] == "{|":
            depth += 1
            i += 2
        elif section_text[i : i + 2] == "|}":
            depth -= 1
            i += 2
            if depth == 0:
                return section_text[start:i]
        else:
            i += 1

    return None


def parse_positions_table_wikitext(wikitext: str):
    """
    wikitext から「Positions by round」テーブルを探してパースする。
    戻り値: {club_name: [position_round1, position_round2, ...]}
    """
    positions = {}

    table_text = find_positions_table(wikitext)
    if not table_text:
        return {}

    # テーブルを行（|-）で分割
    rows = re.split(r"^\|-", table_text, flags=re.MULTILINE)

    for row in rows:
        stripped = row.strip()
        if not stripped or stripped.startswith("{|") or stripped.startswith("|}") or stripped.startswith("|+"):
            continue

        # ヘッダ行をスキップ（! で始まる行が含まれる）
        if stripped.startswith("!"):
            continue

        # データ行の抽出: 行全体を || または \n| で分割
        # ただし先頭の | を除去してから処理
        if not stripped.startswith("|"):
            continue

        # 先頭の | を除去
        line = stripped[1:]

        # セルを || または \n| で分割
        cells = re.split(r"\|\||\n\s*\|(?!\|)", line)

        if len(cells) < 2:
            continue

        # 1列目: クラブ名
        club_name = extract_club_name_from_cell(cells[0])
        if not club_name or re.match(r"^\d+$", club_name):
            # 数字だけ・空はスキップ
            continue
        # テーブルメタ行（class=, style= で始まる）をスキップ
        if re.match(r"^(?:class|style|width|border)\s*=", club_name, re.IGNORECASE):
            continue

        # 2列目以降: 順位数値
        pos_list = []
        for c in cells[1:]:
            # テーブル終端 |} を含むセル、または } だけのセルはスキップ
            if "|}" in c or c.strip().rstrip("}").strip() == "":
                continue
            val = clean_wiki_cell(c)
            # rowspan/colspan 属性を除去
            val = re.sub(r"rowspan\s*=\s*[\"']?\d+[\"']?\s*\|?", "", val, flags=re.IGNORECASE)
            val = val.strip()
            m = re.match(r"^(\d+)$", val)
            if m:
                pos_list.append(int(m.group(1)))
            else:
                pos_list.append(None)

        if pos_list and any(v is not None for v in pos_list):
            positions[club_name] = pos_list

    return positions


def parse_positions_html(html: str, league_name: str):
    """
    Wikipedia HTML から positions テーブルをパースする。
    wikitext パースが失敗した場合のフォールバック。
    セクション見出し id="Positions_by_round" の直後にある wikitable を探す。
    """
    positions = {}

    # 「Positions by round」に相当する見出し id を持つ span/h2/h3 を探す
    heading_patterns = [
        r'id="Positions_by_round"',
        r'id="Round-by-round_positions"',
        r'id="Positions_by_matchday"',
        r'id="Table_by_round"',
        r'id="Standings_by_round"',
    ]
    section_start = -1
    for pat in heading_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            section_start = m.start()
            break

    if section_start == -1:
        # より緩い検索
        m = re.search(r'id="[^"]*[Pp]osition[^"]*"', html)
        if m:
            section_start = m.start()

    if section_start == -1:
        return {}

    # そこから最初の <table を探す
    table_start = html.find("<table", section_start)
    if table_start == -1:
        return {}

    # 次の </table> を ネスト考慮で探す
    depth = 0
    i = table_start
    table_end = -1
    while i < len(html):
        if html[i:i+6].lower() == "<table":
            depth += 1
            i += 6
        elif html[i:i+8].lower() == "</table>":
            depth -= 1
            i += 8
            if depth == 0:
                table_end = i
                break
        else:
            i += 1

    if table_end == -1:
        return {}

    table_html = html[table_start:table_end]

    # tr → td/th の解析
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
        # タグを除去してテキストのみ取得
        cells_clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if not cells_clean:
            continue

        # ヘッダ行（数字 or Team/Club）はスキップ
        if all(re.match(r"^\d+$", c) or c.lower() in ("team", "club", "pos", "#", "") for c in cells_clean):
            continue

        # データ行: 1列目がクラブ名、残りは順位数値
        if len(cells_clean) >= 2:
            club_name = cells_clean[0]
            # 数字だけのクラブ名はスキップ
            if re.match(r"^\d+$", club_name):
                continue
            pos_values = []
            for c in cells_clean[1:]:
                m = re.match(r"^(\d+)$", c)
                pos_values.append(int(m.group(1)) if m else None)
            if pos_values and club_name and any(v is not None for v in pos_values):
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
