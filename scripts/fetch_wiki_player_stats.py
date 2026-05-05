#!/usr/bin/env python3
"""
fetch_wiki_player_stats.py
各クラブの Wikipedia season ページの statistics/squad テーブルから
選手別ゴール数・アシスト数・出場数を抽出する。
出力: data/player_stats.json

使い方: python3 scripts/fetch_wiki_player_stats.py

対応フォーマット（2025-26シーズン）:
  1. {{Efs player}} テンプレート形式（Brighton, Liverpool, Crystal Palace, Ajax, Bayern等）
  2. wikitable + flagicon 縦型形式（Leeds, Tottenham等）
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "football-jp scraper / 0.2 (saito@tottot.net)"


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
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            print(f"  [WIKI ERROR] {page_title}: {data['error'].get('info', '')}", file=sys.stderr)
            return None
        return data.get("parse", {}).get("wikitext", "")
    except (HTTPError, URLError) as e:
        print(f"  [WIKI ERROR] {page_title}: {e}", file=sys.stderr)
        return None


def clean_wiki_link(text: str) -> str:
    """[[Link|Display]] → Display、{{template}} → '' を除去して表示名を返す。"""
    # [[Link|Display]] → Display
    text = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', text)
    # {{template|...}} → 空
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    # HTML タグ除去
    text = re.sub(r'<[^>]+>', '', text)
    # ref タグ除去
    text = re.sub(r'<ref[^/]*/>', '', text)
    return text.strip()


def normalize_name(name: str) -> str:
    """名前を小文字・空白正規化して比較用に変換する。
    Unicode長音符（ō→o, ū→u等）をASCIIに正規化してから比較する。"""
    # NFKD正規化でアクセント記号を分解し、結合文字を除去
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', ascii_name.strip().lower())


def parse_apps(s: str) -> int:
    """'17+6' や '17(6)' → 先発+途中出場の合計を返す。'-' や '' は 0。"""
    s = s.strip()
    # 太字記法除去
    s = s.replace("'''", "")
    if not s or s in ('-', '—', '–'):
        return 0
    # X+Y 形式
    m = re.match(r'(\d+)\+(\d+)', s)
    if m:
        return int(m.group(1)) + int(m.group(2))
    # X(Y) 形式（先発X, 途中Y）
    m2 = re.match(r'(\d+)\((\d+)\)', s)
    if m2:
        return int(m2.group(1)) + int(m2.group(2))
    m3 = re.search(r'\d+', s)
    return int(m3.group()) if m3 else 0


def parse_goals(s: str) -> int:
    """'3' → 3、'-' や '' は 0。"""
    s = s.strip()
    if not s or s in ('-', '—', '–'):
        return 0
    m = re.search(r'\d+', s)
    return int(m.group()) if m else 0


# ─────────────────────────────────────────────
# フォーマット1: {{Efs player}} テンプレート形式
# ─────────────────────────────────────────────
def parse_efs_format(wikitext: str) -> list:
    """
    {{Efs start|League1|League2|...}} と {{Efs player |no=X|pos=XX|nat=JPN|name=[[Name]]|apps1|goals1|...}}
    を解析して選手データリストを返す。
    戻り値: [{"name": str, "league_apps": int, "league_goals": int,
               "total_apps": int, "total_goals": int, "format": "efs"}, ...]
    """
    results = []

    # Efs start で大会順を確認（最初の大会がリーグ戦）
    efs_start_match = re.search(r'\{\{Efs start\|([^\}]+)\}\}', wikitext)
    if not efs_start_match:
        return results

    competitions = [c.strip() for c in efs_start_match.group(1).split('|')]
    num_competitions = len(competitions)

    # {{Efs player |...}} を全取得
    efs_entries = re.findall(r'\{\{Efs player\s*\|([^\}]+)\}\}', wikitext)
    if not efs_entries:
        return results

    for entry in efs_entries:
        # [[Link|Display]] の内部パイプを一時的に別文字に置換してから | 分割する
        # 例: [[Hiroki Ito (footballer, born 1999)|Hiroki Ito]] → パイプ保護
        protected = re.sub(r'\[\[([^\]]*?)\|([^\]]*?)\]\]',
                           lambda m: '[[' + m.group(1) + '\x00' + m.group(2) + ']]',
                           entry)
        parts = [p.strip().replace('\x00', '|') for p in protected.split('|')]

        # 名前を取得
        name_raw = ""
        for p in parts:
            if p.startswith('name='):
                name_raw = p[5:].strip()
                break

        if not name_raw:
            continue

        name_clean = clean_wiki_link(name_raw)

        # 数値データを抽出（no=, pos=, nat=, name= を除いたもの）
        values = []
        for p in parts:
            if '=' not in p:
                values.append(p)

        # Efs player フォーマット: 大会ごとに [apps, goals] のペア
        # 最終2つが Total apps, Total goals
        league_apps = parse_apps(values[0]) if len(values) > 0 else 0
        league_goals = parse_goals(values[1]) if len(values) > 1 else 0

        # Total（最後の2値）を取得
        # len(values) > 2*num_competitions のとき最後の2値がTotal列
        # len(values) == 2*num_competitions のときはTotal列なし → 全大会の合計を計算
        total_apps = 0
        total_goals = 0
        if len(values) > 2 * num_competitions:
            total_apps = parse_apps(values[-2])
            total_goals = parse_goals(values[-1])
        else:
            # Total列なし: 全大会の合計を手動計算
            for i in range(0, len(values) - 1, 2):
                total_apps += parse_apps(values[i])
                total_goals += parse_goals(values[i + 1])

        results.append({
            "name": name_clean,
            "league_apps": league_apps,
            "league_goals": league_goals,
            "total_apps": total_apps,
            "total_goals": total_goals,
            "format": "efs",
        })

    return results


# ─────────────────────────────────────────────
# フォーマット2: wikitable + flagicon 縦型形式
# ─────────────────────────────────────────────
def _get_wikitable_section(wikitext: str) -> str:
    """Statistics/Appearances セクションのテキストを返す。"""
    patterns = [
        r'={3,4}\s*Appearances and goals\s*={3,4}(.*?)(?===|\Z)',
        r'={3,4}\s*Appearances\s*={3,4}(.*?)(?===|\Z)',
        r'==\s*Statistics\s*==(.*?)(?===|\Z)',
        r'==\s*Squad statistics\s*==(.*?)(?===|\Z)',
    ]
    for pat in patterns:
        m = re.search(pat, wikitext, re.DOTALL)
        if m:
            return m.group(1)
    return ""


def _parse_header_cols(table_body: str):
    """
    テーブルのヘッダー行を解析して (has_goals: bool, col_labels: list) を返す。
    rowspan/colspan に対応した簡易版。
    """
    header_lines = [l for l in table_body.split('\n') if l.startswith('!')]
    col_labels = []
    for line in header_lines:
        parts = re.split(r'!!', line.lstrip('!'))
        for part in parts:
            part = part.strip()
            cs_m = re.search(r'colspan="?(\d+)"?', part)
            cs = int(cs_m.group(1)) if cs_m else 1
            # ラベルを抽出: | より後ろの表示テキスト
            label_part = part
            if '|' in label_part:
                label_part = label_part.split('|', 1)[-1]
            label = re.sub(r'\{\{[^}]*\}\}', '', label_part)
            label = re.sub(r'\[\[[^\]]*\]\]', '', label)
            label = re.sub(r'<[^>]+>', '', label).strip().lower()
            col_labels.extend([label] * cs)

    has_goals = any('goal' in h or h in ('gls', 'g') for h in col_labels)
    return has_goals, col_labels


def _expand_sortname(text: str) -> str:
    """{{sortname|First|Last}} → 'First Last' に展開する。"""
    return re.sub(r'\{\{sortname\|([^|]+)\|([^|}]+)(?:\|[^}]*)?\}\}',
                  lambda m: m.group(1).strip() + ' ' + m.group(2).strip(),
                  text, flags=re.IGNORECASE)


def _flatten_cells(row: str) -> list:
    """ウィキテキストの行（|-区切り）からセル値リストを返す。"""
    lines = row.split('\n')
    cell_lines = [l for l in lines if l.startswith('|')
                  and not l.startswith('|-') and not l.startswith('!')]
    cells = []
    for line in cell_lines:
        # {{sortname}} を展開
        line = _expand_sortname(line)
        if '||' in line:
            parts = re.split(r'\|\|', line[1:])
        else:
            parts = [line[1:]]
        for p in parts:
            if '|' in p:
                p = p.split('|', 1)[-1]
            cells.append(p.strip())
    return cells


def parse_wikitable_format(wikitext: str) -> list:
    """
    wikitableの縦型形式を解析する。Leeds/Tottenham/Coventry等で使われる。
    - Apps+Goalsペア型（Leeds, Tottenham）
    - Appsのみ型（Coventry: ゴール列なし）
    の両方に対応。
    """
    results = []

    section_text = _get_wikitable_section(wikitext)
    if not section_text:
        return results

    table_match = re.search(r'\{\|[^\n]*wikitable[^\n]*\n(.*?)\n\|\}', section_text, re.DOTALL)
    if not table_match:
        return results

    table_body = table_match.group(1)
    has_goals, col_labels = _parse_header_cols(table_body)

    # 行ごとに解析
    rows = re.split(r'\n\|-', table_body)
    for row in rows:
        cells = _flatten_cells(row)
        if not cells:
            continue

        # 選手名を特定（[[リンク]]またはsortname展開後の平文）
        player_name = ""
        player_cell_idx = -1
        for i, c in enumerate(cells):
            # [[Link|Display]] 形式
            link_m = re.search(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', c)
            if link_m:
                candidate = link_m.group(2) or link_m.group(1)
                candidate = candidate.strip()
                if len(candidate) >= 3 and not re.match(r'^\d+$', candidate):
                    player_name = candidate
                    player_cell_idx = i
                    break
            # sortname展開後の平文（例: "Takuma Ominami"）
            # flagiconの次のセルに平文の名前がある場合
            if not link_m and i > 0 and 'flagicon' in cells[i - 1]:
                # 前のセルがflagiconなら、このセルが名前の可能性
                c_clean = c.strip()
                if (len(c_clean) >= 3 and not re.match(r'^\d', c_clean)
                        and not c_clean.startswith('{{') and not c_clean.startswith('align=')):
                    player_name = c_clean
                    player_cell_idx = i
                    break
            # align=left|Name の形式の平文
            if not link_m and re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', c.strip()):
                candidate = c.strip()
                if len(candidate) >= 3 and not re.match(r'^\d', candidate):
                    player_name = candidate
                    player_cell_idx = i
                    break

        if not player_name:
            continue

        # 数値セルを収集（選手名セル以降）
        raw_values = []
        for c in cells[player_cell_idx + 1:]:
            c_clean = c.strip()
            if re.match(r"^\d+(\+\d+)?$", c_clean) or re.match(r"^\d+\(\d+\)$", c_clean) or re.match(r"^'''\d+'''$", c_clean) or c_clean in ('-', '—', '–', ''):
                raw_values.append(c_clean if c_clean else '0')

        if not raw_values:
            continue

        if has_goals:
            # Apps+Goalsペア型: [LeagueApps, LeagueGoals, CupApps, CupGoals, ..., TotalApps, TotalGoals, Yellow, Red]
            league_apps = parse_apps(raw_values[0])
            league_goals = parse_goals(raw_values[1]) if len(raw_values) > 1 else 0

            # TotalはX+Y形式の最後のもの（またはその前のペア）
            # X+Y形式インデックスを全取得
            apps_idx_list = [i for i, v in enumerate(raw_values) if re.match(r'^\d+\+\d+$', v)]

            if apps_idx_list:
                # X+Y形式の最後がTotal Apps
                last_apps_i = apps_idx_list[-1]
                total_apps = parse_apps(raw_values[last_apps_i])
                total_goals = parse_goals(raw_values[last_apps_i + 1]) if last_apps_i + 1 < len(raw_values) else 0
                # Total Goalsは次のセル。ただし次もX+Y形式なら規律列のため直前を採用
                if last_apps_i + 1 < len(raw_values) and re.match(r'^\d+\+\d+$', raw_values[last_apps_i + 1]):
                    # 最後から2番目のX+Yがtrue Total
                    if len(apps_idx_list) >= 2:
                        prev_i = apps_idx_list[-2]
                        total_apps = parse_apps(raw_values[prev_i])
                        total_goals = parse_goals(raw_values[prev_i + 1]) if prev_i + 1 < len(raw_values) else 0
                    else:
                        total_apps = league_apps
                        total_goals = league_goals
            else:
                # 全て純数値: 最大Appsのペアを取得
                best_apps = league_apps
                best_goals = league_goals
                for i in range(0, len(raw_values) - 1, 2):
                    a = parse_apps(raw_values[i])
                    g = parse_goals(raw_values[i + 1])
                    if a > best_apps:
                        best_apps = a
                        best_goals = g
                total_apps = best_apps
                total_goals = best_goals
        else:
            # Appsのみ型（Coventry等): [LeagueApps, CupApps, ..., TotalApps]
            # 最後の値がTotalApps、最初の値がLeagueApps
            league_apps = parse_apps(raw_values[0])
            league_goals = 0  # このテーブルにはGoals列がない
            # 最大値がTotal（通常最後の値）
            total_apps = max(parse_apps(v) for v in raw_values) if raw_values else league_apps
            total_goals = 0

        results.append({
            "name": clean_wiki_link(player_name),
            "league_apps": league_apps,
            "league_goals": league_goals,
            "total_apps": total_apps,
            "total_goals": total_goals,
            "format": "wikitable",
        })

    return results


def parse_player_stats(wikitext: str, club_en: str) -> list:
    """
    wikitextからフォーマットを自動判別して選手データを抽出する。
    フォーマット1（Efs player）を優先し、なければフォーマット2を試みる。
    """
    # フォーマット1を試みる
    results = parse_efs_format(wikitext)
    if results:
        print(f"    → Efsテンプレート形式で {len(results)} 選手取得")
        return results

    # フォーマット2を試みる
    results = parse_wikitable_format(wikitext)
    if results:
        print(f"    → wikitable形式で {len(results)} 選手取得")
        return results

    print(f"    → [警告] どちらのフォーマットでも取得できませんでした", file=sys.stderr)
    return []


# クラブ → Wikipedia season ページのマッピング（2025-26シーズン）
CLUB_WIKI_PAGES = {
    "Brighton & Hove Albion": "2025–26 Brighton & Hove Albion F.C. season",
    "Crystal Palace": "2025–26 Crystal Palace F.C. season",
    "Liverpool": "2025–26 Liverpool F.C. season",
    "Leeds": "2025–26 Leeds United F.C. season",
    "Tottenham": "2025–26 Tottenham Hotspur F.C. season",
    "Southampton": "2025–26 Southampton F.C. season",
    "Coventry": "2025–26 Coventry City F.C. season",
    "Hull City": "2025–26 Hull City A.F.C. season",
    "Blackburn": "2025–26 Blackburn Rovers F.C. season",
    "Queens Park Rangers": "2025–26 Queens Park Rangers F.C. season",
    "Stoke City": "2025–26 Stoke City F.C. season",
    "Birmingham": "2025–26 Birmingham City F.C. season",
    "Real Sociedad": "2025–26 Real Sociedad season",
    "Mallorca": "2025–26 RCD Mallorca season",
    "Bayern München": "2025–26 FC Bayern Munich season",  # 修正: München → Munich
    "Eintracht Frankfurt": "2025–26 Eintracht Frankfurt season",
    "SC Freiburg": "2025–26 SC Freiburg season",
    "Mainz 05": "2025–26 1. FSV Mainz 05 season",
    "Werder Bremen": "2025–26 SV Werder Bremen season",
    "Borussia Mönchengladbach": "2025–26 Borussia Mönchengladbach season",
    "VfL Wolfsburg": "2025–26 VfL Wolfsburg season",
    "FC Augsburg": "2025–26 FC Augsburg season",
    "FC St. Pauli": "2025–26 FC St. Pauli season",
    "TSG Hoffenheim": "2025–26 TSG 1899 Hoffenheim season",
    "Parma": "2025–26 Parma Calcio 1913 season",
    "Monaco": "2025–26 AS Monaco FC season",
    "Le Havre": "2025–26 Le Havre AC season",
    "Ajax": "2025–26 AFC Ajax season",
    "Feyenoord": "2025–26 Feyenoord season",
    "AZ Alkmaar": "2025–26 AZ Alkmaar season",
    "NEC Nijmegen": "2025–26 NEC Nijmegen season",
    "Sparta Rotterdam": "2025–26 Sparta Rotterdam season",
    "Sporting CP": "2025–26 Sporting CP season",
    "Gil Vicente": "2025–26 Gil Vicente F.C. season",
    "Genk": "2025–26 KRC Genk season",
    "Royal Antwerp": "2025–26 Royal Antwerp F.C. season",
    "Gent": "2025–26 K.A.A. Gent season",
    "Westerlo": "2025–26 K.V.C. Westerlo season",
    "OH Leuven": "2025–26 Oud-Heverlee Leuven season",
    "Sint-Truiden": "2025–26 Sint-Truidense V.V. season",
}


def main():
    print("players.json 読み込み中...")
    players_raw = load_json("players.json", {})
    players = players_raw.get("players", [])
    print(f"  選手数: {len(players)}")

    # 既存のstatsを読み込んで保持（取得失敗時のフォールバック用）
    existing_stats = {}
    existing_raw = load_json("player_stats.json", {})
    if isinstance(existing_raw, dict):
        existing_stats = existing_raw.get("stats", {})
    print(f"  既存データ: {len(existing_stats)} 選手")

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

        print(f"  [{i+1}/{total_clubs}] {club_en}: {wiki_title}")
        wikitext = fetch_wikitext(wiki_title)

        if not wikitext:
            print(f"    → 取得失敗、既存データを保持")
            # 既存データを保持
            for name_en, existing in existing_stats.items():
                if existing.get("club") == club_en and name_en not in stats:
                    stats[name_en] = existing
                    stats[name_en]["source"] = "wikipedia_cached"
            time.sleep(1)
            continue

        print(f"    → {len(wikitext):,} chars 取得")

        # テーブル解析（フォーマット自動判別）
        table_data = parse_player_stats(wikitext, club_en)

        # 日本人選手のみフィルタ＆マッチング
        matched_count = 0
        for row in table_data:
            name_raw = row.get("name", "")
            name_norm = normalize_name(name_raw)

            matched_player = None
            # 完全一致（クラブチェック付き）
            if name_norm in jp_names:
                candidate = jp_names[name_norm]
                if candidate.get("club_en") == club_en:
                    matched_player = candidate
                # クラブ違いの場合はスキップ（移籍元クラブのページに名前が出ることがあるため）
            if matched_player is None:
                # 部分マッチング（同クラブの選手の姓でマッチ）
                for jp_key, jp_info in jp_names.items():
                    if jp_info.get("club_en") != club_en:
                        continue
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
                league_apps = row.get("league_apps", 0)
                league_goals = row.get("league_goals", 0)
                total_apps = row.get("total_apps", 0)
                total_goals = row.get("total_goals", 0)

                stats[name_en] = {
                    "apps": league_apps,
                    "goals": league_goals,
                    "assists": 0,  # Assistsは別テーブルのため0固定
                    "total_apps": total_apps,
                    "total_goals": total_goals,
                    "club": club_en,
                    "club_ja": matched_player.get("club_ja", ""),
                    "name_ja": matched_player.get("name_ja", ""),
                    "source": "wikipedia",
                    "wiki_page": wiki_title,
                    "wiki_format": row.get("format", "unknown"),
                }
                matched_count += 1
                print(f"      ✅ {name_en} ({matched_player.get('name_ja', '')}): "
                      f"League {league_apps}試合/{league_goals}G  "
                      f"Total {total_apps}試合/{total_goals}G")

        if matched_count == 0:
            print(f"    → 日本人選手マッチなし（{len(table_data)}選手取得済み）")
            # 既存データを保持
            for name_en, existing in existing_stats.items():
                if existing.get("club") == club_en and name_en not in stats:
                    stats[name_en] = existing
                    stats[name_en]["source"] = "wikipedia_cached"

        time.sleep(1.5)  # Wikipedia API レート制限対応

    # 取得できなかった選手は既存データで補完
    for p in players:
        name_en = p.get("name_en", "")
        if name_en and name_en not in stats and name_en in existing_stats:
            stats[name_en] = existing_stats[name_en]
            stats[name_en]["source"] = "wikipedia_cached"

    # 出力
    output = {
        "updated": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "note": ("Wikipediaの各クラブシーズンページから取得。"
                 "Efsテンプレート形式とwikitable形式の両方に対応。"
                 "league_apps/league_goalsがリーグ戦、total_apps/total_goalsが全大会合計。"),
        "total_players": len(stats),
        "stats": stats,
    }

    save_json("player_stats.json", output)
    print(f"\n完了！ {len(stats)} 選手分のデータを data/player_stats.json に保存しました。")

    # サマリー表示
    if stats:
        print("\n取得できた選手一覧（リーグゴール数順）:")
        for name_en, s in sorted(stats.items(), key=lambda x: x[1].get("goals", 0), reverse=True):
            name_ja = s.get("name_ja", "")
            src = s.get("source", "")
            cached = " [cached]" if src == "wikipedia_cached" else ""
            print(f"  {name_ja:10s} ({name_en:25s}): "
                  f"L {s['apps']}試合/{s['goals']}G  "
                  f"T {s.get('total_apps', 0)}試合/{s.get('total_goals', 0)}G{cached}")


if __name__ == "__main__":
    main()
