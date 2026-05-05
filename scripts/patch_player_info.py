#!/usr/bin/env python3
"""
player_info.json の birth_date・height_cm・career を手動補完するスクリプト。

対象: Wikipedia 英語版/日本語版から取得した情報を直接パッチする。
      自動スクリプトで取得に失敗した選手のみを対象とする。

実行: python3 scripts/patch_player_info.py
冪等性: 何度実行しても同じ結果になる（既存データを上書きしない、nullのみ補完）。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 手動補完データ（Wikipedia 日本語版・英語版から確認済み）
# birth_date: YYYY-MM-DD, height_cm: int, career: [{years, club}]
# None のフィールドはスキップ（既存データを保持）
PATCHES = {
    "Takefusa Kubo": {
        "birth_date": "2001-06-04",
        "birth_place": "Asao-ku, Kawasaki, Kanagawa, Japan",
        "birth_place_ja": "神奈川県川崎市",
        "height_cm": 173,
        "wiki_url": "https://en.wikipedia.org/wiki/Takefusa_Kubo",
        "career": [
            {"years": "2010–2011", "club": "Kawasaki Frontale (Youth)"},
            {"years": "2011–2015", "club": "Barcelona (Youth)"},
            {"years": "2015–2019", "club": "FC Tokyo"},
            {"years": "2018", "club": "→ Yokohama F. Marinos (loan)"},
            {"years": "2016–2018", "club": "FC Tokyo U-23"},
            {"years": "2019–2022", "club": "Real Madrid CF"},
            {"years": "2019–2020", "club": "→ RCD Mallorca (loan)"},
            {"years": "2020–2021", "club": "→ Villarreal CF (loan)"},
            {"years": "2021", "club": "→ Getafe CF (loan)"},
            {"years": "2021–2022", "club": "→ RCD Mallorca (loan)"},
            {"years": "2022–", "club": "Real Sociedad"},
        ],
    },
    "Hidemasa Morita": {
        "birth_date": "1995-05-10",
        "birth_place": "Takatsuki, Osaka, Japan",
        "birth_place_ja": "大阪府高槻市",
        "height_cm": 177,
        "wiki_url": "https://en.wikipedia.org/wiki/Hidemasa_Morita",
        "career": [
            {"years": "2018–2020", "club": "Kawasaki Frontale"},
            {"years": "2021–2022", "club": "C.D. Santa Clara"},
            {"years": "2022–", "club": "Sporting CP"},
        ],
    },
    "Issei Sakamoto": {
        "birth_date": "2003-08-26",
        "birth_place": "Kumamoto, Kumamoto, Japan",
        "birth_place_ja": "熊本県熊本市",
        "height_cm": 173,
        "wiki_url": "https://ja.wikipedia.org/wiki/坂本一彩",
        "career": [
            {"years": "2020", "club": "Gamba Osaka U-23"},
            {"years": "2022–2024", "club": "Gamba Osaka"},
            {"years": "2023", "club": "→ Fagiano Okayama (loan)"},
            {"years": "2025–", "club": "KVC Westerlo"},
        ],
    },
    "Riihito Yamamoto": {
        "birth_date": "2001-12-12",
        "birth_place": "Sagamihara, Kanagawa, Japan",
        "birth_place_ja": "神奈川県相模原市",
        "height_cm": 179,
        "wiki_url": "https://ja.wikipedia.org/wiki/山本理仁",
        "career": [
            {"years": "2019–2022", "club": "Tokyo Verdy"},
            {"years": "2022–2023", "club": "Gamba Osaka"},
            {"years": "2023–2024", "club": "→ Sint-Truiden VV (loan)"},
            {"years": "2024–", "club": "Sint-Truiden VV"},
        ],
    },
    "Ko Watanabe": {
        "birth_date": "1997-02-05",
        "birth_place": "Saitama, Japan",
        "birth_place_ja": "埼玉県",
        "height_cm": 186,
        "wiki_url": "https://ja.wikipedia.org/wiki/渡辺剛_(サッカー選手)",
        "career": [
            {"years": "2018–2019", "club": "FC Tokyo U-23"},
            {"years": "2019–2021", "club": "FC Tokyo"},
            {"years": "2022–2023", "club": "KV Kortrijk"},
            {"years": "2023–2025", "club": "KAA Gent"},
            {"years": "2025–", "club": "Feyenoord"},
        ],
    },
    "Daiki Sekine": {
        "birth_date": "2002-08-11",
        "birth_place": "Suruga-ku, Shizuoka, Japan",
        "birth_place_ja": "静岡県静岡市駿河区",
        "height_cm": 187,
        "wiki_url": "https://ja.wikipedia.org/wiki/関根大輝",
        "career": [
            {"years": "2023–2024", "club": "Kashiwa Reysol"},
            {"years": "2025–", "club": "Stade de Reims"},
        ],
    },
    "Itsuki Seko": {
        # birth_date already exists (1997-12-22), only add career
        "birth_date": None,  # skip (already correct)
        "height_cm": 175,
        "wiki_url": "https://ja.wikipedia.org/wiki/瀬古樹",
        "career": [
            {"years": "2020–2021", "club": "Yokohama FC"},
            {"years": "2022–2024", "club": "Kawasaki Frontale"},
            {"years": "2024–", "club": "Stoke City"},
        ],
    },
    "Yoshito Kamishiro": {
        "birth_date": "2007-10-25",
        "birth_place": "Kumamoto, Kumamoto, Japan",
        "birth_place_ja": "熊本県熊本市",
        "height_cm": 181,
        "wiki_url": "https://ja.wikipedia.org/wiki/神代慶人",
        "career": [
            {"years": "2024–2025", "club": "Roasso Kumamoto"},
            {"years": "2026–", "club": "Eintracht Frankfurt"},
        ],
    },
    "Daichi Hara": {
        "birth_date": "1999-05-05",
        "birth_place": "Hino, Tokyo, Japan",
        "birth_place_ja": "東京都日野市",
        "height_cm": 191,
        "wiki_url": "https://ja.wikipedia.org/wiki/原大智_(サッカー選手)",
        "career": [
            {"years": "2018–2020", "club": "FC Tokyo"},
            {"years": "2021", "club": "NK Istra 1961"},
            {"years": "2021–2022", "club": "→ Sint-Truiden VV (loan)"},
            {"years": "2021–2023", "club": "Deportivo Alavés"},
            {"years": "2023", "club": "→ Sint-Truiden VV (loan)"},
            {"years": "2023–2025", "club": "Kyoto Sanga FC"},
            {"years": "2026–", "club": "FC St. Pauli"},
        ],
    },
    # Ryota Onoda: Wikipedia（英語・日本語）にページなし → スキップ
}


def main():
    info_path = DATA / "player_info.json"
    if not info_path.exists():
        print("[ERROR] data/player_info.json が見つかりません", file=sys.stderr)
        sys.exit(1)

    data = json.loads(info_path.read_text(encoding="utf-8"))

    birth_updated = 0
    career_updated = 0
    height_updated = 0
    skipped = 0

    for player_name, patch in PATCHES.items():
        if player_name not in data:
            print(f"  [SKIP] {player_name} は player_info.json に存在しない", file=sys.stderr)
            skipped += 1
            continue

        entry = data[player_name]
        changed = False

        # birth_date
        new_birth = patch.get("birth_date")
        if new_birth is not None:
            old_birth = entry.get("birth_date")
            if old_birth is None:
                entry["birth_date"] = new_birth
                print(f"  [UPDATE] {player_name}: birth_date={new_birth}")
                birth_updated += 1
                changed = True
            else:
                print(f"  [NO CHANGE] {player_name}: birth_date already={old_birth}")

        # height_cm
        new_height = patch.get("height_cm")
        if new_height is not None:
            old_height = entry.get("height_cm")
            if old_height is None:
                entry["height_cm"] = new_height
                print(f"  [UPDATE] {player_name}: height_cm={new_height}")
                height_updated += 1
                changed = True

        # birth_place
        for fld in ("birth_place", "birth_place_ja"):
            new_val = patch.get(fld)
            if new_val and not entry.get(fld):
                entry[fld] = new_val
                changed = True

        # wiki_url (overwrite only if obviously wrong)
        new_wiki = patch.get("wiki_url")
        old_wiki = entry.get("wiki_url", "")
        if new_wiki and old_wiki and "wikipedia.org/wiki/" not in old_wiki:
            entry["wiki_url"] = new_wiki
            changed = True
        elif new_wiki and not old_wiki:
            entry["wiki_url"] = new_wiki
            changed = True

        # career
        new_career = patch.get("career")
        if new_career is not None:
            old_career = entry.get("career") or []
            if not old_career:
                entry["career"] = new_career
                print(f"  [UPDATE] {player_name}: career ({len(new_career)} entries added)")
                career_updated += 1
                changed = True
            else:
                print(f"  [NO CHANGE] {player_name}: career already has {len(old_career)} entries")

        if not changed:
            print(f"  [NO CHANGE] {player_name}: 変更なし")

    # 書き出し
    info_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[OK] player_info.json を更新しました。")
    print(f"  birth_date 補完: {birth_updated} 名")
    print(f"  career 補完: {career_updated} 名")
    print(f"  height_cm 補完: {height_updated} 名")
    print(f"  スキップ(未登録): {skipped} 名")


if __name__ == "__main__":
    main()
