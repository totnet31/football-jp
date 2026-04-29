#!/usr/bin/env python3
"""
football-data.org から対象大会の試合データを取得し、
data/matches.json に整形して書き出すスクリプト。

実行: python3 scripts/fetch_matches.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    print("Python 3.9以上が必要です。", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = ZoneInfo("Asia/Tokyo")

PAST_DAYS = 7
FUTURE_DAYS = 14
RATE_SLEEP = 7  # 秒。10req/分制限対策（やや余裕を持たせる）
API_BASE = "https://api.football-data.org/v4"
SCORERS_LIMIT = 50  # 得点ランキング取得人数


def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"[ERROR] .env が見つかりません: {env_path}", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    token = env.get("FOOTBALL_DATA_TOKEN")
    if not token:
        print("[ERROR] .env に FOOTBALL_DATA_TOKEN が設定されていません。", file=sys.stderr)
        sys.exit(1)
    return token


def load_json(name):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url, token):
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[WARN] HTTP {e.code} for {url}: {body[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[WARN] fetch失敗 {url}: {e}", file=sys.stderr)
        return None


def build_player_index(players_data):
    """club_id ごとに選手リストをまとめる辞書を作る。"""
    idx = {}
    for p in players_data["players"]:
        cid = p.get("club_id")
        if cid is None:
            continue
        idx.setdefault(int(cid), []).append({
            "name_ja": p["name_ja"],
            "position": p.get("position", ""),
        })
    return idx


def to_jst(utc_str):
    """ISO8601 UTC文字列をJSTのISO8601文字列に変換。"""
    if utc_str.endswith("Z"):
        utc_str = utc_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(utc_str)
    return dt.astimezone(JST).isoformat()


def transform_match(m, comp_meta, clubs, player_idx, broadcasters):
    home_id = m["homeTeam"]["id"]
    away_id = m["awayTeam"]["id"]
    home_name_api = m["homeTeam"].get("shortName") or m["homeTeam"].get("name") or ""
    away_name_api = m["awayTeam"].get("shortName") or m["awayTeam"].get("name") or ""
    # チーム未確定の場合（CLの未来枠など）は「未定」と表記
    home_ja = clubs.get(str(home_id)) or home_name_api or "未定"
    away_ja = clubs.get(str(away_id)) or away_name_api or "未定"

    jp_players = []
    for p in player_idx.get(home_id, []):
        jp_players.append({"name_ja": p["name_ja"], "position": p["position"], "side": "home"})
    for p in player_idx.get(away_id, []):
        jp_players.append({"name_ja": p["name_ja"], "position": p["position"], "side": "away"})

    score = None
    full = m.get("score", {}).get("fullTime") or {}
    if full.get("home") is not None and full.get("away") is not None:
        score = {"home": full["home"], "away": full["away"]}

    return {
        "id": m["id"],
        "competition_id": comp_meta["id"],
        "competition_ja": comp_meta["name_ja"],
        "competition_category": comp_meta.get("category"),
        "competition_flag": comp_meta.get("flag", ""),
        "kickoff_jst": to_jst(m["utcDate"]),
        "status": m.get("status"),
        "stage": m.get("stage"),
        "matchday": m.get("matchday"),
        "home_id": home_id,
        "home_ja": home_ja,
        "home_en": home_name_api,
        "home_crest": m["homeTeam"].get("crest"),
        "away_id": away_id,
        "away_ja": away_ja,
        "away_en": away_name_api,
        "away_crest": m["awayTeam"].get("crest"),
        "score": score,
        "japanese_players": jp_players,
        "broadcasters": broadcasters.get(str(comp_meta["id"]), []),
    }


def main():
    token = load_env()
    competitions = load_json("competitions.json")
    players = load_json("players.json")
    clubs_data = load_json("clubs.json")
    broadcasters_data = load_json("broadcasters.json")

    clubs = clubs_data["clubs"]
    broadcasters = broadcasters_data["broadcasters"]
    player_idx = build_player_index(players)

    today = datetime.now(JST).date()
    date_from = (today - timedelta(days=PAST_DAYS)).isoformat()
    date_to = (today + timedelta(days=FUTURE_DAYS)).isoformat()

    targets = [c for c in competitions["competitions"] if c.get("covered")]
    print(f"[INFO] 対象大会: {len(targets)}件 / 期間: {date_from} 〜 {date_to}")

    all_matches = []
    for i, comp in enumerate(targets):
        url = f"{API_BASE}/competitions/{comp['fd_code']}/matches?dateFrom={date_from}&dateTo={date_to}"
        print(f"[{i+1}/{len(targets)}] {comp['name_ja']} ({comp['fd_code']}) を取得中...")
        data = fetch(url, token)
        if data and "matches" in data:
            for m in data["matches"]:
                all_matches.append(transform_match(m, comp, clubs, player_idx, broadcasters))
            print(f"    -> {len(data['matches'])}試合")
        else:
            print(f"    -> 取得失敗または0件")
        if i < len(targets) - 1:
            time.sleep(RATE_SLEEP)

    all_matches.sort(key=lambda m: m["kickoff_jst"])

    # 既存matches.jsonがあれば、TBD（home_id=None）の試合は過去の確定済みデータを保持する。
    # football-data.org の無料プランでは、CL等のノックアウトラウンドの対戦カードが
    # APIから後日になって null で返ってくるケースがある（2026-04-29で実測）。
    out_path = DATA / "matches.json"
    if out_path.exists():
        try:
            old_data = json.loads(out_path.read_text(encoding="utf-8"))
            old_by_id = {m["id"]: m for m in old_data.get("matches", [])}
            preserved = 0
            for m in all_matches:
                old = old_by_id.get(m["id"])
                if not old:
                    continue
                # home/away それぞれ独立に判定（片方だけTBDのケースもありうる）
                if m["home_id"] is None and old.get("home_id"):
                    for k in ("home_id", "home_ja", "home_en", "home_crest"):
                        m[k] = old.get(k)
                    # JP playersも再ハイドレート（home側）
                    home_jp_existing = [p for p in m["japanese_players"] if p["side"] == "home"]
                    if not home_jp_existing:
                        for p in player_idx.get(m["home_id"], []):
                            m["japanese_players"].append({"name_ja": p["name_ja"], "position": p["position"], "side": "home"})
                    preserved += 1
                if m["away_id"] is None and old.get("away_id"):
                    for k in ("away_id", "away_ja", "away_en", "away_crest"):
                        m[k] = old.get(k)
                    away_jp_existing = [p for p in m["japanese_players"] if p["side"] == "away"]
                    if not away_jp_existing:
                        for p in player_idx.get(m["away_id"], []):
                            m["japanese_players"].append({"name_ja": p["name_ja"], "position": p["position"], "side": "away"})
                    preserved += 1
            if preserved:
                print(f"[INFO] APIがnull返却した {preserved}件 のチーム情報を、前回データから補完しました。")
        except Exception as e:
            print(f"[WARN] 既存データの参照に失敗: {e}")

    output = {
        "updated": datetime.now(JST).isoformat(),
        "date_from": date_from,
        "date_to": date_to,
        "match_count": len(all_matches),
        "matches": all_matches,
    }

    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(all_matches)}試合を {out_path} に書き出しました。")

    # ===== 順位データ取得 =====
    print()
    print("[INFO] 順位データを取得します...")
    standings_out = {"updated": datetime.now(JST).isoformat(), "competitions": {}}
    for i, comp in enumerate(targets):
        time.sleep(RATE_SLEEP)
        url = f"{API_BASE}/competitions/{comp['fd_code']}/standings"
        print(f"[{i+1}/{len(targets)}] {comp['name_ja']} の順位を取得中...")
        data = fetch(url, token)
        if not data or "standings" not in data:
            print("    -> 取得失敗")
            continue
        standings_out["competitions"][str(comp["id"])] = {
            "name_ja": comp["name_ja"],
            "flag": comp.get("flag", ""),
            "category": comp.get("category"),
            "season_start": data.get("season", {}).get("startDate"),
            "season_end": data.get("season", {}).get("endDate"),
            "standings": [
                {
                    "type": s.get("type"),
                    "group": s.get("group"),
                    "stage": s.get("stage"),
                    "table": [
                        {
                            "position": r["position"],
                            "team_id": r["team"]["id"],
                            "team_ja": clubs.get(str(r["team"]["id"])) or r["team"].get("shortName") or r["team"].get("name"),
                            "team_crest": r["team"].get("crest"),
                            "playedGames": r["playedGames"],
                            "won": r["won"],
                            "draw": r["draw"],
                            "lost": r["lost"],
                            "points": r["points"],
                            "goalsFor": r["goalsFor"],
                            "goalsAgainst": r["goalsAgainst"],
                            "goalDifference": r["goalDifference"],
                            "form": r.get("form"),
                        } for r in s.get("table", [])
                    ]
                } for s in data.get("standings", [])
            ],
        }
        print(f"    -> OK")
    out_path = DATA / "standings.json"
    out_path.write_text(json.dumps(standings_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 順位データを {out_path} に書き出しました。")

    # ===== 得点ランキング取得 =====
    print()
    print("[INFO] 得点ランキングを取得します...")
    scorers_out = {"updated": datetime.now(JST).isoformat(), "competitions": {}}
    for i, comp in enumerate(targets):
        time.sleep(RATE_SLEEP)
        url = f"{API_BASE}/competitions/{comp['fd_code']}/scorers?limit={SCORERS_LIMIT}"
        print(f"[{i+1}/{len(targets)}] {comp['name_ja']} の得点ランキングを取得中...")
        data = fetch(url, token)
        if not data or "scorers" not in data:
            print("    -> 取得失敗")
            continue
        scorers_out["competitions"][str(comp["id"])] = {
            "name_ja": comp["name_ja"],
            "flag": comp.get("flag", ""),
            "scorers": [
                {
                    "player_id": s["player"]["id"],
                    "player_name": s["player"]["name"],
                    "nationality": s["player"].get("nationality"),
                    "team_id": s["team"]["id"],
                    "team_ja": clubs.get(str(s["team"]["id"])) or s["team"].get("shortName") or s["team"].get("name"),
                    "team_crest": s["team"].get("crest"),
                    "goals": s.get("goals"),
                    "assists": s.get("assists"),
                    "penalties": s.get("penalties"),
                    "playedMatches": s.get("playedMatches"),
                } for s in data.get("scorers", [])
            ],
        }
        print(f"    -> {len(data['scorers'])}名")
    out_path = DATA / "scorers.json"
    out_path.write_text(json.dumps(scorers_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 得点ランキングを {out_path} に書き出しました。")


if __name__ == "__main__":
    main()
