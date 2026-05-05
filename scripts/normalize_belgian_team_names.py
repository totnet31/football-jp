#!/usr/bin/env python3
"""
ベルギー・クラブ名の表記揺れを統一するスクリプト。

対象ファイル:
  - data/players.json   (club_ja フィールド)
  - data/standings.json (team_ja フィールド)

正規化基準（Wikipedia 日本語版タイトルを優先）:
  - Genk        → "ヘンク"
  - Antwerp     → "ロイヤル・アントワープ"
  - Gent        → "ヘント"
  - Westerlo    → "ウェステルロー"
  - Sint-Truiden → "シント＝トロイデン"

実行: python3 scripts/normalize_belgian_team_names.py
冪等性: 何度実行しても同じ結果になる。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# club_en → 正規化された日本語名
NORMALIZE_MAP = {
    # players.json の club_en → 正規 club_ja
    "Genk": "ヘンク",
    "Royal Antwerp": "ロイヤル・アントワープ",
    "Gent": "ヘント",
    "Westerlo": "ウェステルロー",
    "Sint-Truiden": "シント＝トロイデン",
}

# standings.json の team_en → 正規 team_ja
STANDINGS_NORMALIZE = {
    "Genk": "ヘンク",
    "Antwerp": "ロイヤル・アントワープ",
    "Gent": "ヘント",
    "Westerlo": "ウェステルロー",
    "Sint-Truiden": "シント＝トロイデン",
}


def normalize_players(players_path: Path) -> int:
    """players.json の Belgian クラブ名を正規化。変更件数を返す。"""
    data = json.loads(players_path.read_text(encoding="utf-8"))
    players = data.get("players", [])

    updated = 0
    changes = []
    for p in players:
        if p.get("league_ja") != "ジュピラー・プロ・リーグ":
            continue
        club_en = p.get("club_en", "")
        correct_ja = NORMALIZE_MAP.get(club_en)
        if correct_ja is None:
            continue
        old_ja = p.get("club_ja")
        if old_ja == correct_ja:
            continue
        p["club_ja"] = correct_ja
        changes.append(f"  {p.get('name_en')}: '{old_ja}' → '{correct_ja}'")
        updated += 1

    if updated > 0:
        players_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[OK] players.json を更新しました（{updated} 件）")
        for c in changes:
            print(c)
    else:
        print("[NO CHANGE] players.json: 変更なし（すでに統一済み）")

    return updated


def normalize_standings(standings_path: Path) -> int:
    """standings.json のベルギーリーグ team_ja を正規化。変更件数を返す。"""
    data = json.loads(standings_path.read_text(encoding="utf-8"))
    comps = data.get("competitions", {})
    belg = comps.get("144")
    if not belg:
        print("[WARN] standings.json に comp_id '144' が見つかりません", file=sys.stderr)
        return 0

    updated = 0
    changes = []
    for standing_block in belg.get("standings", []):
        for row in standing_block.get("table", []):
            team_en = row.get("team_en", "")
            correct_ja = STANDINGS_NORMALIZE.get(team_en)
            if correct_ja is None:
                continue
            old_ja = row.get("team_ja")
            if old_ja == correct_ja:
                continue
            row["team_ja"] = correct_ja
            changes.append(f"  {team_en}: '{old_ja}' → '{correct_ja}'")
            updated += 1

    if updated > 0:
        standings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[OK] standings.json を更新しました（{updated} 件）")
        for c in changes:
            print(c)
    else:
        print("[NO CHANGE] standings.json: 変更なし（すでに統一済み）")

    return updated


def main():
    players_path = DATA / "players.json"
    standings_path = DATA / "standings.json"

    print("=== ベルギー・クラブ名 正規化 ===")
    print()

    total = 0

    if not players_path.exists():
        print("[ERROR] data/players.json が見つかりません", file=sys.stderr)
    else:
        total += normalize_players(players_path)

    print()

    if not standings_path.exists():
        print("[ERROR] data/standings.json が見つかりません", file=sys.stderr)
    else:
        total += normalize_standings(standings_path)

    print()
    print(f"[DONE] 合計 {total} 件の表記を更新しました。")

    # 統一後の確認表示
    print()
    print("=== 統一後の確認 ===")
    if players_path.exists():
        p_data = json.loads(players_path.read_text(encoding="utf-8"))
        print("players.json (ベルギー選手 club_ja):")
        seen = set()
        for p in p_data.get("players", []):
            if p.get("league_ja") == "ジュピラー・プロ・リーグ":
                key = (p.get("club_en"), p.get("club_ja"))
                if key not in seen:
                    print(f"  {p.get('club_en')} → {p.get('club_ja')}")
                    seen.add(key)

    if standings_path.exists():
        s_data = json.loads(standings_path.read_text(encoding="utf-8"))
        belg = s_data.get("competitions", {}).get("144", {})
        print("standings.json (ベルギー standings team_ja):")
        for st in belg.get("standings", []):
            for row in st.get("table", []):
                print(f"  {row.get('team_en')} → {row.get('team_ja')}")
            break


if __name__ == "__main__":
    main()
