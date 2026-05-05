#!/usr/bin/env python3
"""
ベルギー・ジュピラー・プロ・リーグ（2024-25）の順位データを
Wikipedia の Sports table wikitext からパースして
data/standings.json の competitions["144"] に追記するスクリプト。

football-data.org 無料プランはベルギーリーグ非対応のため Wikipedia を代替ソース使用。

実行: python3 scripts/fetch_belgium_standings.py
"""

import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "football-jp/1.0 (https://football-jp.com; contact: saito@tottot.net) Python-urllib"

# ベルギー1部 comp_id（competitions.json と一致）
BELGIUM_COMP_ID = "144"

# 2024-25シーズンのWikipediaページタイトル
WIKI_PAGE = "2024\u201325 Belgian Pro League"

# チーム略称 → 日本語名マッピング
TEAM_NAME_JA = {
    "Genk": "ヘンク",
    "Club Brugge": "クラブ・ブルッヘ",
    "Union SG": "ユニオン・サン＝ジロワーズ",
    "Anderlecht": "アンデルレヒト",
    "Antwerp": "ロイヤル・アントワープ",
    "Beerschot": "ベースホット",
    "Cercle Brugge": "セルクル・ブルッヘ",
    "Charleroi": "スポルティン・シャルルロワ",
    "Dender EH": "デンデルEH",
    "Gent": "KAAヘント",
    "Kortrijk": "コルトレイク",
    "Mechelen": "メヘレン",
    "OH Leuven": "OHルーヴェン",
    "Sint-Truiden": "シント＝トロイデンVV",
    "Standard Liège": "スタンダール・リエージュ",
    "Westerlo": "ウェステルロ",
}


def fetch_wikitext(page_title, max_retries=4):
    """指定ページのwikitextを取得（リダイレクト追跡・リトライ付き）。"""
    url = (
        f"{WIKI_API}?action=parse&page={quote(page_title)}"
        f"&prop=wikitext&format=json&formatversion=2&redirects=1"
    )
    for attempt in range(max_retries):
        req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            if "error" in data:
                print(f"[ERROR] Wikipedia API エラー: {data['error']}", file=sys.stderr)
                return None
            return data.get("parse", {}).get("wikitext", "")
        except HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 2)
                print(
                    f"  [WARN] HTTP 429 リトライ {attempt+1}/{max_retries}、{wait}秒待機",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            print(f"  [ERROR] HTTP {e.code}: {e}", file=sys.stderr)
            return None
        except URLError as e:
            print(f"  [ERROR] URL エラー: {e}", file=sys.stderr)
            return None
    return None


def parse_sports_table(wikitext):
    """
    {{#invoke:Sports table|main|...}} テンプレートから順位データをパース。

    Sports table は以下の形式でデータを持つ：
      |team_order = GNK, CLU, USG, ...  (順位順のチーム略称リスト)
      |win_GNK=21 |draw_GNK=5 |loss_GNK=4 |gf_GNK=55 |ga_GNK=33
      |name_GNK=[[K.R.C. Genk|Genk]]  (表示名)
    """
    # 最初のSports tableブロックを切り出す
    start = wikitext.find("{{#invoke:Sports table")
    if start < 0:
        print("[ERROR] Sports table テンプレートが見つかりません", file=sys.stderr)
        return None

    # 対応する }} を探す（ネスト考慮）
    depth = 0
    end = start
    i = start
    while i < len(wikitext):
        if wikitext[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i : i + 2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                end = i
                break
        else:
            i += 1

    block = wikitext[start:end]

    # team_order からチーム略称リスト（順位順）を取得
    order_m = re.search(r"\|team_order\s*=\s*([^\n|]+)", block)
    if not order_m:
        print("[ERROR] team_order が見つかりません", file=sys.stderr)
        return None
    team_order = [t.strip() for t in order_m.group(1).split(",")]
    print(f"[INFO] チーム順番: {team_order}")

    # 各チームの表示名を取得（wikilink から表示名を抽出）
    name_map = {}
    for m in re.finditer(r"\|name_([A-Z0-9]+)\s*=\s*(.+?)(?:\n|$)", block):
        code = m.group(1).strip()
        raw = m.group(2).strip()
        # [[Link|Display]] または [[Link]] を処理
        link_m = re.search(r"\[\[(?:[^\]|]+\|)?([^\]|]+)\]\]", raw)
        if link_m:
            display = link_m.group(1).strip()
        else:
            display = re.sub(r"\[\[|\]\]", "", raw).strip()
        name_map[code] = display

    # 各チームの成績を取得
    stats = {}
    for code in team_order:
        w_m = re.search(rf"\|win_{code}\s*=\s*(\d+)", block)
        d_m = re.search(rf"\|draw_{code}\s*=\s*(\d+)", block)
        l_m = re.search(rf"\|loss_{code}\s*=\s*(\d+)", block)
        gf_m = re.search(rf"\|gf_{code}\s*=\s*(\d+)", block)
        ga_m = re.search(rf"\|ga_{code}\s*=\s*(\d+)", block)

        if not all([w_m, d_m, l_m, gf_m, ga_m]):
            print(f"  [WARN] {code} の成績データが不完全、スキップ", file=sys.stderr)
            continue

        won = int(w_m.group(1))
        draw = int(d_m.group(1))
        lost = int(l_m.group(1))
        gf = int(gf_m.group(1))
        ga = int(ga_m.group(1))
        played = won + draw + lost
        points = won * 3 + draw
        gd = gf - ga

        display_name = name_map.get(code, code)
        name_ja = TEAM_NAME_JA.get(display_name, display_name)

        stats[code] = {
            "display_name": display_name,
            "name_ja": name_ja,
            "won": won,
            "draw": draw,
            "lost": lost,
            "gf": gf,
            "ga": ga,
            "played": played,
            "points": points,
            "gd": gd,
        }

    # team_order の順に並べてテーブルを構築
    table = []
    position = 1
    for code in team_order:
        if code not in stats:
            continue
        s = stats[code]
        table.append(
            {
                "position": position,
                "team_id": None,  # Wikipedia データにはIDなし
                "team_en": s["display_name"],
                "team_ja": s["name_ja"],
                "team_crest": None,
                "playedGames": s["played"],
                "won": s["won"],
                "draw": s["draw"],
                "lost": s["lost"],
                "points": s["points"],
                "goalsFor": s["gf"],
                "goalsAgainst": s["ga"],
                "goalDifference": s["gd"],
                "form": None,
            }
        )
        position += 1

    return table


def load_standings():
    """既存の standings.json を読み込む。存在しない場合は空構造を返す。"""
    path = DATA / "standings.json"
    if not path.exists():
        return {"updated": None, "competitions": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] standings.json の読み込み失敗: {e}", file=sys.stderr)
        return {"updated": None, "competitions": {}}


def save_standings(data):
    """standings.json を書き出す。"""
    path = DATA / "standings.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {path} に書き出しました。")


def main():
    print(f"[INFO] Wikipedia からベルギー1部リーグ順位データを取得します...")
    print(f"[INFO] ページ: {WIKI_PAGE}")

    wikitext = fetch_wikitext(WIKI_PAGE)
    if not wikitext:
        print("[ERROR] wikitext の取得に失敗しました。終了します。", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] wikitext 取得完了（{len(wikitext)}文字）")

    table = parse_sports_table(wikitext)
    if not table:
        print("[ERROR] 順位テーブルのパースに失敗しました。終了します。", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] {len(table)}チームの順位データをパース完了")
    print("  上位3チーム:")
    for row in table[:3]:
        print(
            f"    {row['position']}位 {row['team_ja']} ({row['team_en']})"
            f" {row['playedGames']}試合 {row['won']}勝{row['draw']}分{row['lost']}敗"
            f" {row['points']}pt GD{row['goalDifference']:+d}"
        )

    # 既存 standings.json に追記（上書き）
    standings = load_standings()
    standings["competitions"][BELGIUM_COMP_ID] = {
        "name_ja": "ジュピラー・プロ・リーグ",
        "flag": "🇧🇪",
        "category": "league",
        "season_start": "2024-08-02",
        "season_end": "2025-05-18",
        "source": f"https://en.wikipedia.org/wiki/{WIKI_PAGE.replace(' ', '_')}",
        "standings": [
            {
                "type": "TOTAL",
                "group": None,
                "stage": "REGULAR_SEASON",
                "table": table,
            }
        ],
    }

    # updated タイムスタンプを更新
    standings["updated"] = datetime.now(JST).isoformat()

    save_standings(standings)
    print(f"[OK] standings.json の competitions['{BELGIUM_COMP_ID}'] を更新しました。")


if __name__ == "__main__":
    main()
