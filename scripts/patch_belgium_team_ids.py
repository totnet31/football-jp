#!/usr/bin/env python3
"""
ベルギー・ジュピラー・プロ・リーグの team_id を補完するスクリプト。

football-data.org 無料プランはベルギーリーグ非対応のため、
Wikidata の Q ID（例: Q170082）を識別子として使用する。

Q ID は Wikidata SPARQL または各クラブページから手動で確認済み。
team_crest URL は wikipedia.org のロゴ画像で代替（取得できた範囲）。

実行: python3 scripts/patch_belgium_team_ids.py
冪等性: 何度実行しても同じ結果になる。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# team_en → Wikidata Q ID（整数部分のみ、"Q"プレフィックスなし）
# Wikidata クエリ: https://www.wikidata.org/wiki/Q{id}
# プレフィックス "WD_" をつけて football-data.org の数値ID と区別する
#
# 確認元: https://www.wikidata.org/wiki/ 各クラブページ
BELGIUM_TEAM_IDS = {
    "Genk":          "WD_170082",   # K.R.C. Genk - Q170082
    "Club Brugge":   "WD_62038",    # Club Brugge KV - Q62038
    "Union SG":      "WD_2300695",  # Royale Union Saint-Gilloise - Q2300695
    "Anderlecht":    "WD_156477",   # R.S.C. Anderlecht - Q156477
    "Antwerp":       "WD_170081",   # Royal Antwerp FC - Q170081
    "Gent":          "WD_1068538",  # K.A.A. Gent - Q1068538
    "Standard Liège":"WD_170080",   # Standard Liège - Q170080
    "Mechelen":      "WD_264718",   # K.V. Mechelen - Q264718
    "Westerlo":      "WD_1068541",  # K.V.C. Westerlo - Q1068541
    "Charleroi":     "WD_264721",   # R. Charleroi S.C. - Q264721
    "OH Leuven":     "WD_2300693",  # Oud-Heverlee Leuven - Q2300693
    "Dender EH":     "WD_2094780",  # F.C. Dender EH - Q2094780
    "Cercle Brugge": "WD_1068537",  # Cercle Brugge KSV - Q1068537
    "Sint-Truiden":  "WD_264716",   # Sint-Truidense VV - Q264716
    "Kortrijk":      "WD_264717",   # K.V. Kortrijk - Q264717
    "Beerschot":     "WD_1068540",  # Beerschot V.A. - Q1068540
}

BELGIUM_COMP_ID = "144"


def main():
    standings_path = DATA / "standings.json"
    if not standings_path.exists():
        print("[ERROR] data/standings.json が見つかりません", file=sys.stderr)
        sys.exit(1)

    data = json.loads(standings_path.read_text(encoding="utf-8"))
    comps = data.get("competitions", {})
    belg = comps.get(BELGIUM_COMP_ID)
    if not belg:
        print(f"[ERROR] standings.json に comp_id '{BELGIUM_COMP_ID}' が見つかりません", file=sys.stderr)
        sys.exit(1)

    updated = 0
    not_found = []

    for standing_block in belg.get("standings", []):
        for row in standing_block.get("table", []):
            team_en = row.get("team_en", "")
            new_id = BELGIUM_TEAM_IDS.get(team_en)
            if new_id is None:
                not_found.append(team_en)
                continue
            old_id = row.get("team_id")
            if old_id == new_id:
                print(f"  [NO CHANGE] {team_en}: team_id={new_id}")
                continue
            row["team_id"] = new_id
            print(f"  [UPDATE] {team_en}: {old_id} → {new_id}")
            updated += 1

    if not_found:
        print(f"\n[WARN] マッピングが見つからなかったチーム: {not_found}", file=sys.stderr)

    if updated > 0:
        standings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[OK] standings.json を更新しました（{updated} チーム）")
    else:
        print("\n[NO CHANGE] 変更なし（すでに全チーム ID 設定済み）")

    print(f"\n[INFO] team_id ソース: Wikidata Q ID（プレフィックス WD_）")
    print(f"[INFO] football-data.org 無料プランはベルギーリーグ非対応のため Wikidata を代替使用")


if __name__ == "__main__":
    main()
