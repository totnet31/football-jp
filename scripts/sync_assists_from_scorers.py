#!/usr/bin/env python3
"""
scorers.json から日本人選手のアシスト数を取得し、
player_stats.json の assists フィールドを上書きするスクリプト。

実行: python3 scripts/sync_assists_from_scorers.py

冪等性: 何度実行しても同じ結果になる。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main():
    # --- scorers.json 読み込み ---
    scorers_path = DATA / "scorers.json"
    if not scorers_path.exists():
        print("[ERROR] data/scorers.json が見つかりません", file=sys.stderr)
        sys.exit(1)
    scorers_data = json.loads(scorers_path.read_text(encoding="utf-8"))

    # --- player_stats.json 読み込み ---
    stats_path = DATA / "player_stats.json"
    if not stats_path.exists():
        print("[ERROR] data/player_stats.json が見つかりません", file=sys.stderr)
        sys.exit(1)
    stats_data = json.loads(stats_path.read_text(encoding="utf-8"))

    # --- scorers.json から日本人選手のアシスト数を集計 ---
    # scorers.json 構造:
    #   { "competitions": { "78": { "scorers": [ { "player_name": "Ritsu Doan", "nationality": "Japan", "assists": 4, ... } ] } } }
    # player_name ベースで集計する
    assist_map: dict[str, int] = {}

    comps = scorers_data.get("competitions", {})
    for comp_id, comp_data in comps.items():
        scorers = comp_data.get("scorers", [])
        for entry in scorers:
            nationality = entry.get("nationality", "")
            if nationality != "Japan":
                continue
            player_name = entry.get("player_name")
            if not player_name:
                continue
            assists = entry.get("assists")
            if assists is None:
                continue
            # 同一選手が複数リーグに出る場合は合算（ただし実態は1リーグ）
            assist_map[player_name] = assist_map.get(player_name, 0) + assists

    print(f"[INFO] scorers.json から日本人選手アシスト集計: {len(assist_map)} 名")
    for name, a in sorted(assist_map.items(), key=lambda x: -x[1]):
        print(f"  {name}: {a} アシスト")

    # --- player_stats.json の stats に反映 ---
    stats = stats_data.get("stats", {})
    updated = 0
    skipped = 0

    for player_name, assists_new in assist_map.items():
        if player_name not in stats:
            print(f"  [SKIP] {player_name} は player_stats.json に存在しない", file=sys.stderr)
            skipped += 1
            continue

        old_assists = stats[player_name].get("assists", 0)
        if old_assists == assists_new:
            print(f"  [NO CHANGE] {player_name}: assists={old_assists} (変更なし)")
            continue

        stats[player_name]["assists"] = assists_new
        print(f"  [UPDATE] {player_name}: {old_assists} → {assists_new}")
        updated += 1

    stats_data["stats"] = stats

    # --- 書き出し ---
    stats_path.write_text(
        json.dumps(stats_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[OK] player_stats.json を更新しました。")
    print(f"  更新: {updated} 名 / スキップ(未登録): {skipped} 名")


if __name__ == "__main__":
    main()
