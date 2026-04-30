#!/usr/bin/env python3
"""
FIFA W杯 2026 データ取得スクリプト
football-data.org の WC エンドポイントから試合・順位・得点ランキングを取得し、
data/wc2026/ 配下にJSONを書き出す。

使い方: python3 scripts/fetch_wc.py
依存: data/wc2026/countries.json （48か国マスタ）
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
DATA = ROOT / "data" / "wc2026"
JST = ZoneInfo("Asia/Tokyo")
RATE_SLEEP = 7  # 10req/分制限対策（余裕を持たせる）
API_BASE = "https://api.football-data.org/v4"
COMP_CODE = "WC"


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


def fetch(url, token):
    req = urllib.request.Request(url, headers={"X-Auth-Token": token, "User-Agent": "wc2026-jp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code} {url}: {e.read().decode('utf-8', errors='ignore')[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] {e} {url}", file=sys.stderr)
        return None


def to_jst(utc_str):
    if utc_str.endswith("Z"):
        utc_str = utc_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(utc_str)
    return dt.astimezone(JST).isoformat()


def transform_match(m, countries):
    """football-data.org の試合データ → wc2026形式に変換"""
    home_team = m.get("homeTeam", {}) or {}
    away_team = m.get("awayTeam", {}) or {}
    home_id = home_team.get("id")
    away_id = away_team.get("id")

    def country_info(team_id, fallback_name):
        """team_id から countries.json で日本語名・国旗を引く"""
        if team_id and str(team_id) in countries:
            c = countries[str(team_id)]
            return c.get("ja") or fallback_name, c.get("flag", ""), c.get("tla", ""), c.get("group", "")
        return fallback_name or "未定", "", "", ""

    home_ja, home_flag, home_tla, home_group = country_info(home_id, home_team.get("name"))
    away_ja, away_flag, away_tla, away_group = country_info(away_id, away_team.get("name"))

    score = None
    full = (m.get("score") or {}).get("fullTime") or {}
    if full.get("home") is not None and full.get("away") is not None:
        score = {"home": full["home"], "away": full["away"]}

    return {
        "id": m.get("id"),
        "kickoff_jst": to_jst(m.get("utcDate")),
        "status": m.get("status"),
        "stage": m.get("stage"),
        "group": m.get("group"),
        "matchday": m.get("matchday"),
        "home_id": home_id,
        "home_ja": home_ja,
        "home_en": home_team.get("name"),
        "home_flag": home_flag,
        "home_tla": home_tla,
        "home_crest": home_team.get("crest"),
        "away_id": away_id,
        "away_ja": away_ja,
        "away_en": away_team.get("name"),
        "away_flag": away_flag,
        "away_tla": away_tla,
        "away_crest": away_team.get("crest"),
        "score": score,
        "venue": m.get("venue"),  # football-data.orgがnull返すが将来補完
    }


def main():
    token = load_env()

    countries_path = DATA / "countries.json"
    if not countries_path.exists():
        print(f"[ERROR] {countries_path} が見つかりません。先に48か国マスタを作成してください。", file=sys.stderr)
        sys.exit(1)
    countries = json.loads(countries_path.read_text(encoding="utf-8"))["countries"]

    DATA.mkdir(parents=True, exist_ok=True)

    # ===== 1. matches =====
    print("[INFO] 全試合を取得中...")
    data = fetch(f"{API_BASE}/competitions/{COMP_CODE}/matches", token)
    if not data or "matches" not in data:
        print("[ERROR] matches取得失敗", file=sys.stderr)
        sys.exit(1)

    raw_matches = data["matches"]
    transformed = [transform_match(m, countries) for m in raw_matches]
    transformed.sort(key=lambda m: m["kickoff_jst"])

    # 既存matches.jsonがあれば、null返却された試合を前回データから補完（football-jpと同じパターン）
    matches_path = DATA / "matches.json"
    if matches_path.exists():
        try:
            old = json.loads(matches_path.read_text(encoding="utf-8"))
            old_by_id = {m["id"]: m for m in old.get("matches", [])}
            preserved = 0
            for m in transformed:
                old_m = old_by_id.get(m["id"])
                if not old_m:
                    continue
                if m["home_id"] is None and old_m.get("home_id"):
                    for k in ("home_id", "home_ja", "home_en", "home_flag", "home_tla", "home_crest"):
                        m[k] = old_m.get(k)
                    preserved += 1
                if m["away_id"] is None and old_m.get("away_id"):
                    for k in ("away_id", "away_ja", "away_en", "away_flag", "away_tla", "away_crest"):
                        m[k] = old_m.get(k)
                    preserved += 1
            if preserved:
                print(f"[INFO] APIがnull返却した {preserved}件 を前回データから補完しました。")
        except Exception as e:
            print(f"[WARN] 既存data補完エラー: {e}")

    matches_out = {
        "updated": datetime.now(JST).isoformat(),
        "competition": "FIFA World Cup 2026",
        "match_count": len(transformed),
        "matches": transformed,
    }
    matches_path.write_text(json.dumps(matches_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(transformed)}試合 → {matches_path}")

    # ===== 2. standings =====
    time.sleep(RATE_SLEEP)
    print("[INFO] グループ順位を取得中...")
    data = fetch(f"{API_BASE}/competitions/{COMP_CODE}/standings", token)
    if data and "standings" in data:
        groups = []
        for g in data["standings"]:
            if g.get("type") != "TOTAL":
                continue
            grp_label = (g.get("group") or "").replace("Group ", "")
            table = []
            for r in g.get("table", []):
                team = r.get("team", {}) or {}
                tid = team.get("id")
                cinfo = countries.get(str(tid), {}) if tid else {}
                table.append({
                    "position": r.get("position"),
                    "team_id": tid,
                    "team_ja": cinfo.get("ja") or team.get("name"),
                    "team_flag": cinfo.get("flag", ""),
                    "team_tla": cinfo.get("tla", ""),
                    "playedGames": r.get("playedGames"),
                    "won": r.get("won"),
                    "draw": r.get("draw"),
                    "lost": r.get("lost"),
                    "points": r.get("points"),
                    "goalsFor": r.get("goalsFor"),
                    "goalsAgainst": r.get("goalsAgainst"),
                    "goalDifference": r.get("goalDifference"),
                })
            groups.append({"group": grp_label, "table": table})
        standings_out = {
            "updated": datetime.now(JST).isoformat(),
            "season_start": data.get("season", {}).get("startDate"),
            "season_end": data.get("season", {}).get("endDate"),
            "groups": groups,
        }
        out_path = DATA / "standings.json"
        out_path.write_text(json.dumps(standings_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {len(groups)}グループ → {out_path}")
    else:
        print("[WARN] standings取得失敗")

    # ===== 3. scorers（大会開幕前は空） =====
    time.sleep(RATE_SLEEP)
    print("[INFO] 得点ランキングを取得中...")
    data = fetch(f"{API_BASE}/competitions/{COMP_CODE}/scorers?limit=50", token)
    if data is not None:
        scorers = []
        for s in (data.get("scorers") or []):
            player = s.get("player", {}) or {}
            team = s.get("team", {}) or {}
            tid = team.get("id")
            cinfo = countries.get(str(tid), {}) if tid else {}
            scorers.append({
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "nationality": player.get("nationality"),
                "team_id": tid,
                "team_ja": cinfo.get("ja") or team.get("name"),
                "team_flag": cinfo.get("flag", ""),
                "goals": s.get("goals"),
                "assists": s.get("assists"),
                "playedMatches": s.get("playedMatches"),
            })
        scorers_out = {"updated": datetime.now(JST).isoformat(), "scorers": scorers}
        out_path = DATA / "scorers.json"
        out_path.write_text(json.dumps(scorers_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {len(scorers)}名 → {out_path}")
    else:
        print("[WARN] scorers取得失敗")

    print("\n[DONE] W杯2026データ更新完了")


if __name__ == "__main__":
    main()
