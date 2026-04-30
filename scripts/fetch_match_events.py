#!/usr/bin/env python3
"""
Phase 1: 日本人選手の得点・アシスト取得スクリプト
- API-Football v3 (free 100 req/日) を使用
- finished matches で japanese_players が存在するものだけ対象
- 既取得試合はキャッシュでスキップ
- 出力: data/match_events.json
"""
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENV_FILE = ROOT / ".env"

JST = timezone(timedelta(hours=9))
LIMIT_PER_RUN = 40  # 1回の実行で消費するAPI calls上限（100/日に余裕）


def load_env():
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("API_FOOTBALL_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("API_FOOTBALL_KEY not found in .env")


def load_json(name, default=None):
    p = DATA / name
    if not p.exists():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


_call_count = 0


def api_get(path, params, key):
    global _call_count
    _call_count += 1
    url = f"https://v3.football.api-sports.io/{path}?{urlencode(params)}"
    req = Request(url, headers={"x-apisports-key": key})
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except (HTTPError, URLError) as e:
        print(f"  [API ERROR] {path} {params}: {e}", file=sys.stderr)
        return None


def normalize_team(name):
    if not name:
        return ""
    s = re.sub(r"\b(FC|F\.C\.|CF|SC|AC|FK|AS|BK|RC|AFC|CFC)\b", "", name, flags=re.IGNORECASE)
    s = re.sub(r"\W+", " ", s).strip().lower()
    return s


def normalize_player(name):
    if not name:
        return ""
    return re.sub(r"\W+", " ", name).strip().lower()


def find_fixture_id(jp_match, key, fixture_cache):
    """football-data match.id → API-Football fixture.id を解決"""
    cache_key = str(jp_match["id"])
    if cache_key in fixture_cache:
        return fixture_cache[cache_key]

    kickoff = datetime.fromisoformat(jp_match["kickoff_jst"])
    utc_date = kickoff.astimezone(timezone.utc).strftime("%Y-%m-%d")
    season = kickoff.year if kickoff.month >= 7 else kickoff.year - 1
    league_id = jp_match["competition_id"]

    data = api_get("fixtures", {
        "league": league_id,
        "season": season,
        "date": utc_date,
    }, key)
    if not data or not data.get("response"):
        fixture_cache[cache_key] = None
        return None

    home_norm = normalize_team(jp_match.get("home_en") or jp_match.get("home_ja"))
    away_norm = normalize_team(jp_match.get("away_en") or jp_match.get("away_ja"))

    for fx in data["response"]:
        h = normalize_team(fx["teams"]["home"]["name"])
        a = normalize_team(fx["teams"]["away"]["name"])
        if (home_norm and (home_norm in h or h in home_norm)) and \
           (away_norm and (away_norm in a or a in away_norm)):
            fid = fx["fixture"]["id"]
            fixture_cache[cache_key] = fid
            return fid

    fixture_cache[cache_key] = None
    return None


def fetch_events(fixture_id, key):
    data = api_get("fixtures/events", {"fixture": fixture_id}, key)
    if not data:
        return []
    return data.get("response", [])


def build_jp_name_lookup(players_data):
    """name_en正規化 → name_ja のマップ"""
    out = {}
    for p in players_data.get("players", []):
        nen = normalize_player(p.get("name_en", ""))
        if nen:
            out[nen] = p.get("name_ja", p.get("name_en"))
    return out


def extract_jp_events(events, jp_lookup):
    """eventsから日本人選手の goal/assist を抽出"""
    out = []
    for ev in events:
        if ev.get("type") != "Goal":
            continue
        # スコアラー本人
        scorer_name = (ev.get("player") or {}).get("name", "")
        scorer_norm = normalize_player(scorer_name)
        if scorer_norm in jp_lookup:
            out.append({
                "type": "goal",
                "player_ja": jp_lookup[scorer_norm],
                "player_en": scorer_name,
                "minute": ev.get("time", {}).get("elapsed"),
                "extra": ev.get("time", {}).get("extra"),
                "team_name": (ev.get("team") or {}).get("name"),
                "detail": ev.get("detail"),  # "Normal Goal" / "Penalty" / "Own Goal" 等
            })
        # アシスト
        assist_name = (ev.get("assist") or {}).get("name", "")
        assist_norm = normalize_player(assist_name)
        if assist_norm in jp_lookup:
            out.append({
                "type": "assist",
                "player_ja": jp_lookup[assist_norm],
                "player_en": assist_name,
                "minute": ev.get("time", {}).get("elapsed"),
                "extra": ev.get("time", {}).get("extra"),
                "team_name": (ev.get("team") or {}).get("name"),
                "detail": ev.get("detail"),
            })
    return out


def main():
    key = load_env()
    matches_data = load_json("matches.json")
    players_data = load_json("players.json")
    events_store = load_json("match_events.json", default={
        "updated": "",
        "fixture_id_map": {},
        "events": {},
    })

    fixture_cache = events_store.setdefault("fixture_id_map", {})
    events_map = events_store.setdefault("events", {})

    jp_lookup = build_jp_name_lookup(players_data)
    print(f"[INFO] 日本人選手 {len(jp_lookup)} 名 ロード")

    # 対象: FINISHED ＋ japanese_players が存在 ＋ 未処理
    targets = []
    for m in matches_data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        if not m.get("japanese_players"):
            continue
        if str(m["id"]) in events_map:
            continue
        targets.append(m)

    # 古い順に処理（まずは過去から）
    targets.sort(key=lambda m: m["kickoff_jst"])
    print(f"[INFO] 対象試合（未処理）: {len(targets)}件")

    processed = 0
    for m in targets:
        if _call_count >= LIMIT_PER_RUN:
            print(f"[INFO] API call上限 ({LIMIT_PER_RUN}) 到達、終了")
            break

        fid = find_fixture_id(m, key, fixture_cache)
        if not fid:
            print(f"  [SKIP] fixture not found: {m['id']} {m.get('home_en')} vs {m.get('away_en')}")
            events_map[str(m["id"])] = []  # 見つからなかった旨を記録
            continue

        events = fetch_events(fid, key)
        jp_events = extract_jp_events(events, jp_lookup)
        events_map[str(m["id"])] = jp_events
        processed += 1
        if jp_events:
            names = ", ".join(f"{e['player_ja']}({e['type']}{e['minute']}')" for e in jp_events)
            print(f"  ⚽ {m['home_ja']} vs {m['away_ja']} → {names}")
        else:
            print(f"  ─ {m['home_ja']} vs {m['away_ja']} → 日本人ゴール/アシストなし")

    events_store["updated"] = datetime.now(JST).isoformat()
    save_json("match_events.json", events_store)
    print(f"\n[DONE] 処理 {processed}件 / API calls {_call_count}回 / 累計 {len(events_map)}試合")


if __name__ == "__main__":
    main()
