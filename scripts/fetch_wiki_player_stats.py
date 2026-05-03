#!/usr/bin/env python3
"""
fetch_wiki_player_stats.py
各クラブの Wikipedia season ページの statistics/squad テーブルから
選手別ゴール数・アシスト数・出場数を抽出する。
出力: data/player_stats.json

使い方: python3 scripts/fetch_wiki_player_stats.py
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

WIKI_API = "https://en.wikipedia.org/w/api.php"


def load_json(name, default=None):
    p = DATA / name
    if not p.exists():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_wikitext(page_title):
    """指定ページのwikitextを取得。リダイレクト追跡。"""
    url = (f"{WIKI_API}?action=parse&page={quote(page_title)}"
           f"&prop=wikitext&format=json&formatversion=2&redirects=1")
    req = Request(url, headers={"User-Agent": "football-jp scraper / 0.1 (saito@tottot.net)"})
    try:
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            return None
        return data.get("parse", {}).get("wikitext", "")
    except (HTTPError, URLError) as e:
        print(f"  [WIKI ERROR] {page_title}: {e}", file=sys.stderr)
        return None


def clean_wiki_cell(cell: str) -> str:
    """wikitextのセルから表示テキストを抽出する。"""
    # [[Link|Display]] → Display
    cell = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', cell)
    # {{template|...}} → 空
    cell = re.sub(r'\{\{[^}]+\}\}', '', cell)
    # HTML タグ除去
    cell = re.sub(r'<[^>]+>', '', cell)
    # ref タグ除去
    cell = re.sub(r'<ref[^/]*/>', '', cell)
    # 残ったパイプ記号・特殊文字除去
    cell = cell.replace('|', '').strip()
    return cell


def normalize_name(name: str) -> str:
    """名前を小文字・空白正規化で比較用に変換する。"""
    return re.sub(r'\s+', ' ', name.strip().lower())


def extract_number(s: str) -> int:
    """文字列から最初の数値を取得。なければ0。"""
    m = re.search(r'\d+', s)
    return int(m.group()) if m else 0


def parse_stats_table(wikitext: str) -> list:
    """
    wikitextから統計テーブルを解析して選手データリストを返す。
    対応フォーマット: wikitable 形式の Statistics/Squad sections
    戻り値: [{"name": str, "apps": int, "goals": int, "assists": int}, ...]
    """
    results = []

    # wikitable ブロックを全部取得（ネストされたテーブルは簡易的に処理）
    table_blocks = re.findall(r'\{\|[^\n]*wikitable[^\n]*\n(.*?)\n\|\}',
                              wikitext, re.DOTALL | re.IGNORECASE)

    for block in table_blocks:
        # ヘッダー行を取得してカラム位置を特定
        header_line = ""
        header_match = re.search(r'^\|-.*?\n((?:!.*?\n)+)', block, re.MULTILINE | re.DOTALL)
        if header_match:
            header_line = header_match.group(1).lower()
        else:
            # !! 区切りのヘッダーも試す
            hm = re.search(r'^!(.*?)$', block, re.MULTILINE)
            if hm:
                header_line = hm.group(1).lower()

        if not header_line:
            continue

        # ヘッダーにAppearances/Goals/Player などが含まれているか確認
        has_goals = any(kw in header_line for kw in ['goal', 'gls', 'goals'])
        has_apps = any(kw in header_line for kw in ['app', 'appearance', 'played', 'pld'])
        has_player = any(kw in header_line for kw in ['player', 'name'])

        if not (has_goals and (has_player or has_apps)):
            continue

        # ヘッダーのカラムインデックスを特定
        # !! または | で区切られたカラム名から位置を推定
        header_cols = re.split(r'!!|\|', header_line)
        header_cols = [c.strip() for c in header_cols if c.strip()]

        player_col = -1
        apps_col = -1
        goals_col = -1
        assists_col = -1

        for idx, h in enumerate(header_cols):
            h_lower = h.lower()
            if any(kw in h_lower for kw in ['player', 'name']) and player_col < 0:
                player_col = idx
            if any(kw in h_lower for kw in ['app', 'appearance', 'played', 'pld']) and apps_col < 0:
                apps_col = idx
            if 'goal' in h_lower or h_lower in ['g', 'gls'] and goals_col < 0:
                goals_col = idx
            if 'assist' in h_lower or h_lower in ['a', 'ast'] and assists_col < 0:
                assists_col = idx

        if player_col < 0 or goals_col < 0:
            continue

        # データ行を解析
        rows = re.split(r'\n\|-', block)
        for row in rows:
            # | で始まるデータセル行
            cells_raw = re.findall(r'^\|([^|!\n][^\n]*)', row, re.MULTILINE)
            if not cells_raw:
                # || 区切りも試す
                line_cells = []
                for line in row.split('\n'):
                    if line.startswith('|') and not line.startswith('|-') and not line.startswith('!'):
                        parts = re.split(r'\|\|', line[1:])
                        line_cells.extend(parts)
                cells_raw = line_cells

            if not cells_raw:
                continue

            # セルの値をクリーニング
            cells = []
            for c in cells_raw:
                # セル属性（style="..." など）がある場合は | より後の値を取る
                if '|' in c:
                    c = c.split('|', 1)[-1]
                cells.append(clean_wiki_cell(c))

            # カラム数が足りない場合はスキップ
            max_col = max(player_col, goals_col)
            if assists_col >= 0:
                max_col = max(max_col, assists_col)
            if apps_col >= 0:
                max_col = max(max_col, apps_col)
            if len(cells) <= max_col:
                continue

            player_name = cells[player_col].strip()
            if not player_name or len(player_name) < 2:
                continue

            goals = extract_number(cells[goals_col]) if goals_col < len(cells) else 0
            apps = extract_number(cells[apps_col]) if apps_col >= 0 and apps_col < len(cells) else 0
            assists = extract_number(cells[assists_col]) if assists_col >= 0 and assists_col < len(cells) else 0

            results.append({
                "name": player_name,
                "apps": apps,
                "goals": goals,
                "assists": assists,
            })

    return results


# クラブ → Wikipedia season ページのマッピング
# "club_en" → Wikipedia page title
CLUB_WIKI_PAGES = {
    "Brighton & Hove Albion": "Brighton & Hove Albion F.C. 2025–26 season",
    "Crystal Palace": "Crystal Palace F.C. 2025–26 season",
    "Liverpool": "Liverpool F.C. 2025–26 season",
    "Leeds": "Leeds United F.C. 2025–26 season",
    "Tottenham": "Tottenham Hotspur F.C. 2025–26 season",
    "Southampton": "Southampton F.C. 2025–26 season",
    "Coventry": "Coventry City F.C. 2025–26 season",
    "Hull City": "Hull City A.F.C. 2025–26 season",
    "Blackburn": "Blackburn Rovers F.C. 2025–26 season",
    "Queens Park Rangers": "Queens Park Rangers F.C. 2025–26 season",
    "Stoke City": "Stoke City F.C. 2025–26 season",
    "Birmingham": "Birmingham City F.C. 2025–26 season",
    "Real Sociedad": "Real Sociedad 2025–26 season",
    "Mallorca": "RCD Mallorca 2025–26 season",
    "Bayern München": "FC Bayern München 2025–26 season",
    "Eintracht Frankfurt": "Eintracht Frankfurt 2025–26 season",
    "SC Freiburg": "Sport-Club Freiburg 2025–26 season",
    "Mainz 05": "1. FSV Mainz 05 2025–26 season",
    "Werder Bremen": "SV Werder Bremen 2025–26 season",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach 2025–26 season",
    "VfL Wolfsburg": "VfL Wolfsburg 2025–26 season",
    "FC Augsburg": "FC Augsburg 2025–26 season",
    "FC St. Pauli": "FC St. Pauli 2025–26 season",
    "TSG Hoffenheim": "TSG 1899 Hoffenheim 2025–26 season",
    "Parma": "Parma Calcio 1913 2025–26 season",
    "Monaco": "AS Monaco FC 2025–26 season",
    "Le Havre": "Le Havre AC 2025–26 season",
    "Ajax": "AFC Ajax 2025–26 season",
    "Feyenoord": "Feyenoord 2025–26 season",
    "AZ Alkmaar": "AZ Alkmaar 2025–26 season",
    "NEC Nijmegen": "NEC Nijmegen 2025–26 season",
    "Sparta Rotterdam": "Sparta Rotterdam 2025–26 season",
    "Sporting CP": "Sporting CP 2025–26 season",
    "Gil Vicente": "Gil Vicente F.C. 2025–26 season",
    "Genk": "K.R.C. Genk 2025–26 season",
    "Royal Antwerp": "Royal Antwerp F.C. 2025–26 season",
    "Gent": "K.A.A. Gent 2025–26 season",
    "Westerlo": "K.V.C. Westerlo 2025–26 season",
    "OH Leuven": "Oud-Heverlee Leuven 2025–26 season",
    "Sint-Truiden": "Sint-Truidense V.V. 2025–26 season",
}


def main():
    print("players.json 読み込み中...")
    players_raw = load_json("players.json", {})
    players = players_raw.get("players", [])
    print(f"  選手数: {len(players)}")

    # 日本人選手の名前セット（小文字正規化）
    jp_names = {}
    for p in players:
        name_en = p.get("name_en", "")
        club_en = p.get("club_en", "")
        if name_en:
            key = normalize_name(name_en)
            jp_names[key] = {
                "name_en": name_en,
                "name_ja": p.get("name_ja", ""),
                "club_en": club_en,
                "club_ja": p.get("club_ja", ""),
            }
            # 姓のみでも登録（マッチング補助）
            parts = name_en.split()
            if len(parts) >= 2:
                last = normalize_name(parts[-1])
                if last not in jp_names:
                    jp_names[last] = jp_names[key]

    print(f"  照合用名前セット: {len(jp_names)} 件")

    # クラブごとにWikipediaページを取得・解析
    stats = {}
    processed_clubs = set()

    # players.json のクラブ一覧からページタイトルを取得
    clubs_in_players = {}
    for p in players:
        club_en = p.get("club_en", "")
        if club_en and club_en not in clubs_in_players:
            clubs_in_players[club_en] = CLUB_WIKI_PAGES.get(club_en)

    total_clubs = len(clubs_in_players)
    print(f"\n対象クラブ数: {total_clubs}")

    for i, (club_en, wiki_title) in enumerate(clubs_in_players.items()):
        if club_en in processed_clubs:
            continue
        processed_clubs.add(club_en)

        if not wiki_title:
            print(f"  [{i+1}/{total_clubs}] {club_en}: Wikipediaページ未登録、スキップ")
            continue

        print(f"  [{i+1}/{total_clubs}] {club_en}: {wiki_title} を取得中...")
        wikitext = fetch_wikitext(wiki_title)

        if not wikitext:
            print(f"    → 取得失敗")
            time.sleep(1)
            continue

        print(f"    → wikitext {len(wikitext):,} chars 取得")

        # テーブル解析
        table_data = parse_stats_table(wikitext)
        print(f"    → テーブルから {len(table_data)} 選手候補")

        # 日本人選手のみフィルタ
        matched_count = 0
        for row in table_data:
            name_raw = row.get("name", "")
            name_norm = normalize_name(name_raw)

            # 完全一致または部分一致
            matched_player = None
            if name_norm in jp_names:
                matched_player = jp_names[name_norm]
            else:
                # 部分マッチング（姓のみ）
                for jp_key, jp_info in jp_names.items():
                    if jp_info.get("club_en") != club_en:
                        continue
                    # 姓でマッチング
                    jp_parts = jp_info["name_en"].lower().split()
                    raw_parts = name_raw.lower().split()
                    if jp_parts and raw_parts:
                        jp_last = jp_parts[-1]
                        raw_last = raw_parts[-1]
                        if jp_last == raw_last:
                            matched_player = jp_info
                            break

            if matched_player:
                name_en = matched_player["name_en"]
                stats[name_en] = {
                    "apps": row.get("apps", 0),
                    "goals": row.get("goals", 0),
                    "assists": row.get("assists", 0),
                    "club": club_en,
                    "club_ja": matched_player.get("club_ja", ""),
                    "name_ja": matched_player.get("name_ja", ""),
                    "source": "wikipedia",
                    "wiki_page": wiki_title,
                }
                matched_count += 1
                print(f"      ✅ {name_en}: {row['apps']} apps / {row['goals']} goals / {row['assists']} assists")

        if matched_count == 0:
            print(f"    → 日本人選手マッチなし")

        time.sleep(1.5)  # Wikipedia API レート制限対応

    # 出力
    output = {
        "updated": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "note": "Wikipediaの各クラブシーズンページから取得。統計テーブルのフォーマットによっては取得できない場合あり。",
        "total_players": len(stats),
        "stats": stats,
    }

    save_json("player_stats.json", output)
    print(f"\n完了！ {len(stats)} 選手分のデータを data/player_stats.json に保存しました。")

    # サマリー表示
    if stats:
        print("\n取得できた選手一覧:")
        for name_en, s in sorted(stats.items(), key=lambda x: x[1].get("goals", 0), reverse=True):
            name_ja = s.get("name_ja", "")
            print(f"  {name_ja:10s} ({name_en:25s}): {s['apps']} apps / {s['goals']} goals / {s['assists']} assists")


if __name__ == "__main__":
    main()
