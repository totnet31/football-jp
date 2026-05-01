#!/usr/bin/env python3
"""
データ更新後のスモークテスト
develop ブランチにpush後、main マージ前に実行する整合性チェック。

失敗時は exit 1 を返す。GitHub Actions が main マージをスキップ。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

errors = []
warnings = []


def fail(msg):
    errors.append(msg)
    print(f"  [FAIL] {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg):
    print(f"  [OK] {msg}")


def check_matches():
    print("\n[1] matches.json")
    path = DATA / "matches.json"
    if not path.exists():
        fail("matches.json が存在しない")
        return
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"JSON文法エラー: {e}")
        return
    matches = m.get("matches", [])
    n = len(matches)
    if n < 100:
        fail(f"試合数が異常に少ない: {n}件（>=100期待）")
    else:
        ok(f"試合数: {n}件")

    # 必須フィールドチェック
    REQUIRED = ["id", "kickoff_jst", "home_ja", "away_ja", "competition_id", "competition_ja"]
    missing_count = 0
    for x in matches[:10]:  # 先頭10件サンプル
        for k in REQUIRED:
            if k not in x or x.get(k) in (None, ""):
                missing_count += 1
                if missing_count <= 3:
                    fail(f"必須フィールド欠損 id={x.get('id')} field={k}")
    if missing_count == 0:
        ok("必須フィールド整合（先頭10件サンプル）")

    # 主要リーグの存在チェック
    EXPECTED_LEAGUES = {
        39: "プレミアリーグ",
        140: "ラ・リーガ",
        135: "セリエA",
        78: "ブンデスリーガ",
        61: "リーグ・アン",
        88: "エールディビジ",
    }
    league_counts = {}
    for x in matches:
        cid = x.get("competition_id")
        league_counts[cid] = league_counts.get(cid, 0) + 1
    for cid, name in EXPECTED_LEAGUES.items():
        cnt = league_counts.get(cid, 0)
        if cnt == 0:
            fail(f"主要リーグ {name} (id={cid}) の試合が0件")
        else:
            ok(f"{name}: {cnt}件")

    # EL/ECLは決勝直前に減るので0件警告のみ
    ucl_count = league_counts.get(2, 0)
    el_count = league_counts.get(3, 0)
    ecl_count = league_counts.get(848, 0)
    if ucl_count + el_count + ecl_count == 0:
        warn("UCL/EL/ECL 全体で0件（シーズン終盤の場合は正常）")
    else:
        ok(f"UEFA系: UCL {ucl_count} / EL {el_count} / ECL {ecl_count}件")


def check_standings():
    print("\n[2] standings.json")
    path = DATA / "standings.json"
    if not path.exists():
        fail("standings.json が存在しない")
        return
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"JSON文法エラー: {e}")
        return
    leagues = s.get("competitions") or s.get("standings") or {}
    if not leagues:
        fail("順位データが空")
    else:
        ok(f"順位データ: {len(leagues)}リーグ")


def check_scorers():
    print("\n[3] scorers.json")
    path = DATA / "scorers.json"
    if not path.exists():
        fail("scorers.json が存在しない")
        return
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"JSON文法エラー: {e}")
        return
    leagues = s.get("competitions") or s.get("scorers") or {}
    if not leagues:
        warn("得点者データが空")
    else:
        ok(f"得点者データ: {len(leagues)}リーグ")


def check_players():
    print("\n[4] players.json")
    path = DATA / "players.json"
    if not path.exists():
        fail("players.json が存在しない")
        return
    try:
        p = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"JSON文法エラー: {e}")
        return
    players = p.get("players", [])
    if len(players) < 30:
        fail(f"日本人選手数が異常に少ない: {len(players)}人（>=30期待）")
    else:
        ok(f"日本人選手: {len(players)}人")


def check_wc2026():
    print("\n[5] wc2026/")
    wc = DATA / "wc2026"
    if not wc.exists():
        warn("wc2026 ディレクトリが存在しない")
        return
    for fn in ("matches.json", "standings.json"):
        p = wc / fn
        if not p.exists():
            warn(f"wc2026/{fn} が存在しない")
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
            ok(f"wc2026/{fn}: 文法OK")
        except json.JSONDecodeError as e:
            fail(f"wc2026/{fn} JSON文法エラー: {e}")


def main():
    print("=== football-jp データ整合性スモークテスト ===")
    check_matches()
    check_standings()
    check_scorers()
    check_players()
    check_wc2026()
    print()
    print(f"=== 結果: ERRORS={len(errors)} / WARNINGS={len(warnings)} ===")
    if errors:
        print("\n[FAILED] 以下のエラーで main へのマージを中止します:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("[PASSED] 全てのチェック合格")
    sys.exit(0)


if __name__ == "__main__":
    main()
