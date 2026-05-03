#!/usr/bin/env python3
"""
fetch_player_videos.py
各日本人選手のシーズンゴール集・まとめ動画を YouTube Data API で取得する。

クオータ消費見積もり:
  - search.list: 100 units/call
  - 68選手 × 1 call = 6,800 units（1日クオータ 10,000 の 68%）
  - 既存 fetch_youtube_highlights.py (300 units) との合計 = 7,100 units
  ⚠️  実行前に残りクオータを確認すること

出力: data/player_videos.json
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENV_FILE = ROOT / ".env"
JST = timezone(timedelta(hours=9))

PLAYERS_JSON = DATA / "players.json"
OUTPUT_JSON = DATA / "player_videos.json"

# 公式チャンネルIDリスト（優先度順）
OFFICIAL_CHANNELS = {
    "UCyeDNNizMGbVsn_8Ttc3FIw": "DAZN Japan",
    "UCMjvvElkdLRTgcTKklAUkSw": "U-NEXT Football",
    "UCJQj2lbG_3w8UrncJd7JZXw": "WOWOW",
    "UCa5_OsB-mZCxJSIW5u1eV1w": "ABEMA Sports",
    "UCRc-TxAh1OoSUMTMFhHAeRA": "ABEMA",
}

# 検索クエリテンプレート（選手名 + シーズン）
QUERY_TEMPLATES = [
    "{name_en} goals 2025-26",
    "{name_en} highlights 2025-26",
    "{name_en} season goals 2025",
]

_call_count = 0


def load_env() -> dict:
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def load_players() -> list:
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("players", [])


def yt_search(query: str, key: str, max_results: int = 10):
    """YouTube search.list API を呼ぶ（100 units/call）"""
    global _call_count
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "relevance",
        "maxResults": str(max_results),
        "relevanceLanguage": "ja",
        "key": key,
    }
    url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
    _call_count += 1
    try:
        with urlopen(url, timeout=20) as r:
            return json.loads(r.read())
    except (HTTPError, URLError) as e:
        print(f"  [YT ERROR] query={query!r}: {e}", file=sys.stderr)
        return None


def score_video(item: dict) -> int:
    """公式チャンネルなら高スコア、そうでなければ 0"""
    channel_id = item.get("snippet", {}).get("channelId", "")
    if channel_id in OFFICIAL_CHANNELS:
        return 10
    # チャンネル名でも判定（補助）
    channel_title = (item.get("snippet", {}).get("channelTitle") or "").lower()
    for kw in ("dazn", "u-next", "unext", "wowow", "abema"):
        if kw in channel_title:
            return 5
    return 1


def fetch_player_videos(name_en: str, key: str, max_results: int = 5) -> list:
    """選手名で検索して最大3本の動画情報を返す"""
    videos = []
    seen_ids = set()

    # 最初のクエリで検索（クオータ節約のため1クエリのみ）
    query = f"{name_en} goals 2025-26"
    data = yt_search(query, key, max_results=max_results)
    if not data:
        return []

    items = data.get("items", [])
    # スコアでソート
    items.sort(key=score_video, reverse=True)

    for item in items:
        vid = item.get("id", {}).get("videoId", "")
        if not vid or vid in seen_ids:
            continue
        seen_ids.add(vid)
        s = item.get("snippet", {})
        channel_id = s.get("channelId", "")
        channel_name = OFFICIAL_CHANNELS.get(channel_id, s.get("channelTitle", ""))
        published = s.get("publishedAt", "")[:10]
        videos.append({
            "video_id": vid,
            "title": s.get("title", ""),
            "channel": channel_name,
            "channel_id": channel_id,
            "is_official": channel_id in OFFICIAL_CHANNELS,
            "published": published,
            "url": f"https://youtube.com/watch?v={vid}",
        })
        if len(videos) >= 3:
            break

    return videos


def main():
    # ── クオータ消費見積もりログ ──────────────────────────────
    print("=" * 60)
    print("[QUOTA ESTIMATE] fetch_player_videos.py")
    print("  - search.list: 100 units/call")
    print("  - 68選手 × 1 call = 6,800 units")
    print("  - fetch_youtube_highlights.py との合計 ≒ 7,100 units")
    print("  - 1日クオータ 10,000 の約 71%")
    print("=" * 60)

    env = load_env()
    key = env.get("YOUTUBE_API_KEY")
    if not key:
        print("[ERROR] YOUTUBE_API_KEY が設定されていません（.env または環境変数）", file=sys.stderr)
        sys.exit(1)

    players = load_players()
    print(f"[INFO] 選手数: {len(players)} 名")

    # 既存データを読み込んでキャッシュとして使用
    existing: dict = {}
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, encoding="utf-8") as f:
                raw = json.load(f)
            existing = raw.get("players", {})
            print(f"[INFO] 既存データ: {len(existing)} 選手分をキャッシュとして読み込み")
        except Exception:
            pass

    result = {}
    skipped = 0
    fetched = 0
    errors = 0

    for i, player in enumerate(players):
        name_en = player.get("name_en", "")
        if not name_en:
            continue

        # キャッシュが新鮮（7日以内）であればスキップしてクオータ節約
        cached = existing.get(name_en, {})
        if cached:
            cached_date_str = cached.get("fetched_at", "")
            if cached_date_str:
                try:
                    cached_dt = datetime.fromisoformat(cached_date_str)
                    if (datetime.now(JST) - cached_dt).days < 7:
                        result[name_en] = cached
                        skipped += 1
                        continue
                except Exception:
                    pass

        print(f"[{i+1:02d}/{len(players)}] {name_en} ... ", end="", flush=True)
        try:
            videos = fetch_player_videos(name_en, key)
            result[name_en] = {
                "videos": videos,
                "fetched_at": datetime.now(JST).isoformat(),
            }
            fetched += 1
            official_count = sum(1 for v in videos if v.get("is_official"))
            print(f"  {len(videos)} 本取得（公式: {official_count} 本）")
        except Exception as e:
            print(f"  [ERROR] {e}", file=sys.stderr)
            result[name_en] = {"videos": [], "fetched_at": datetime.now(JST).isoformat()}
            errors += 1

    # 保存
    output = {
        "updated": datetime.now(JST).isoformat(),
        "total_players": len(result),
        "api_calls": _call_count,
        "units_used": _call_count * 100,
        "players": result,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] 選手別動画取得完了")
    print(f"  新規取得: {fetched} 名 / キャッシュ利用: {skipped} 名 / エラー: {errors} 名")
    print(f"  API calls: {_call_count} / 消費ユニット: {_call_count * 100} units")
    print(f"  残量目安: {10000 - _call_count * 100} units")
    print(f"  保存先: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
