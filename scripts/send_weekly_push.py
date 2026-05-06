#!/usr/bin/env python3
"""
PWA Phase 4: 週次 Push 通知送信スクリプト
- 毎週月曜朝7時 JST（GitHub Actions cron: 0 22 * * 0 UTC）に実行
- 購読者のお気に入り（選手/クラブ/リーグ）に合致する今週の試合をフィルタ
- Cloudflare Worker /api/send-push に POST して Web Push 配信

【必要な環境変数】
  ADMIN_TOKEN   - Cloudflare Worker の ADMIN_TOKEN と同じ値
                  GitHub Actions Secret に設定: Settings > Secrets > ADMIN_TOKEN
  WORKER_URL    - （省略可）デフォルト: https://football-jp-push-api.saito-dfe.workers.dev

【実行方法】
  ADMIN_TOKEN=xxx python3 scripts/send_weekly_push.py
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST  = timezone(timedelta(hours=9))

WORKER_URL = os.environ.get("WORKER_URL", "https://football-jp-push-api.saito-dfe.workers.dev")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# 今週の対象期間（月曜朝7時〜日曜23:59 JST）
def get_week_window():
    """今日（月曜）の7:00 JST 〜 今週日曜23:59 JST"""
    now_jst = datetime.now(JST)
    # 月曜=0、日曜=6
    days_until_sunday = 6 - now_jst.weekday()
    week_start = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
    week_end   = (now_jst + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=59, microsecond=0)
    return week_start, week_end


def api_get(path):
    url = WORKER_URL + path
    req = Request(url, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except HTTPError as e:
        print(f"[ERROR] GET {path}: HTTP {e.code}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"[ERROR] GET {path}: {e}", file=sys.stderr)
        return None


def api_post(path, body):
    url = WORKER_URL + path
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    })
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[ERROR] POST {path}: HTTP {e.code} {body_text}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"[ERROR] POST {path}: {e}", file=sys.stderr)
        return None


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def format_kickoff(kickoff_jst: str) -> str:
    """キックオフ日時を「5/8(木) 23:30」形式に変換"""
    try:
        dt = datetime.fromisoformat(kickoff_jst)
        weekday = ["月","火","水","木","金","土","日"][dt.weekday()]
        return f"{dt.month}/{dt.day}({weekday}) {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return kickoff_jst[:10]


def build_notification_for_subscriber(sub_data, matches_this_week):
    """
    購読者のお気に入りに合致する試合を選定し、通知メッセージを生成する

    Args:
        sub_data: {
            subscription: {...},
            favorites: [...],         # 選手 slug 配列
            favorite_clubs: [...],    # クラブ slug 配列（例: ['club-397']）
            favorite_leagues: [...],  # リーグ slug 配列（例: ['league-39']）
        }
        matches_this_week: 今週の SCHEDULED 試合リスト

    Returns:
        (subscription_obj, message_dict) または None（対象なし）
    """
    favorites      = sub_data.get("favorites", [])
    fav_clubs      = sub_data.get("favorite_clubs", [])
    fav_leagues    = sub_data.get("favorite_leagues", [])

    # クラブIDセット（'club-397' → '397'）
    fav_club_ids   = set(slug.replace("club-", "") for slug in fav_clubs)
    # リーグIDセット（'league-39' → 39）
    fav_league_ids = set(int(slug.replace("league-", "")) for slug in fav_leagues if slug.replace("league-", "").isdigit())

    matched_lines = []
    matched_set = set()  # 重複排除

    for m in matches_this_week:
        mid = m.get("id") or f"{m.get('home_en')}-{m.get('away_en')}"
        if mid in matched_set:
            continue

        ko_str    = format_kickoff(m.get("kickoff_jst", ""))
        home_ja   = m.get("home_ja", "")
        away_ja   = m.get("away_ja", "")
        home_id   = str(m.get("home_id") or "")
        away_id   = str(m.get("away_id") or "")
        comp_id   = m.get("competition_id")
        jp_players = m.get("japanese_players", [])

        reason = None

        # 1) お気に入り選手がこの試合に出場予定か
        #    japanese_players は選手名 or slug リスト
        if favorites and jp_players:
            for fav_slug in favorites:
                for jp in jp_players:
                    jp_slug = (jp.get("slug") or jp.get("name_en", "")).lower().replace(" ", "-")
                    jp_name = jp.get("name_ja") or jp.get("name", "")
                    if fav_slug == jp_slug or fav_slug in jp_slug:
                        reason = f"👤 {jp_name}"
                        break
                if reason:
                    break

        # 2) お気に入りクラブ
        if not reason and fav_club_ids:
            if home_id in fav_club_ids:
                reason = f"🏟 {home_ja}"
            elif away_id in fav_club_ids:
                reason = f"🏟 {away_ja}"

        # 3) お気に入りリーグ
        if not reason and fav_league_ids:
            if comp_id in fav_league_ids:
                reason = f"🏆 {m.get('competition_ja', '')}"

        if reason:
            matched_lines.append(f"• {ko_str} {home_ja} vs {away_ja}  ({reason})")
            matched_set.add(mid)

        if len(matched_lines) >= 5:
            break

    if not matched_lines:
        return None

    # 通知本文生成
    lines_text = "\n".join(matched_lines[:5])
    count = len(matched_lines)
    if count > 5:
        lines_text += f"\n… 他{count - 5}試合"

    body_text = lines_text + "\n👉 football-jp.com でチェック！"

    return sub_data["subscription"], {
        "title": f"⚽ 今週の注目試合 ({count}試合)",
        "body":  body_text,
        "url":   "https://football-jp.com/"
    }


def main():
    if not ADMIN_TOKEN:
        print("[ERROR] ADMIN_TOKEN 環境変数が未設定です", file=sys.stderr)
        print("[ERROR] GitHub Actions: Settings > Secrets > ADMIN_TOKEN を設定してください", file=sys.stderr)
        sys.exit(1)

    week_start, week_end = get_week_window()
    print(f"[INFO] 対象期間: {week_start.isoformat()} 〜 {week_end.isoformat()} (JST)")

    # matches.json を読み込んで今週の SCHEDULED 試合を抽出
    matches_data = load_json("matches.json")
    all_matches  = matches_data.get("matches", [])

    matches_this_week = []
    for m in all_matches:
        if m.get("status") not in ("SCHEDULED", "TIMED"):
            continue
        try:
            ko = datetime.fromisoformat(m["kickoff_jst"])
        except Exception:
            continue
        if week_start <= ko <= week_end:
            matches_this_week.append(m)

    # キックオフ順にソート
    matches_this_week.sort(key=lambda m: m.get("kickoff_jst", ""))
    print(f"[INFO] 今週の試合数: {len(matches_this_week)}")

    if not matches_this_week:
        print("[INFO] 今週の試合が0件のため終了")
        return

    # 購読者一覧を取得
    print("[INFO] 購読者一覧を取得中...")
    result = api_get("/api/subscriptions")
    if not result or not result.get("ok"):
        print("[ERROR] 購読者取得に失敗", file=sys.stderr)
        sys.exit(1)

    subscriptions = result.get("subscriptions", [])
    print(f"[INFO] 購読者数: {len(subscriptions)}")

    if not subscriptions:
        print("[INFO] 購読者が0件のため終了")
        return

    # 各購読者に通知を送信
    sent = 0
    skipped = 0
    errors  = 0

    for i, sub_data in enumerate(subscriptions, 1):
        sub_id = sub_data.get("id", f"#{i}")
        build_result = build_notification_for_subscriber(sub_data, matches_this_week)

        if build_result is None:
            skipped += 1
            continue

        subscription_obj, payload = build_result
        print(f"  [{i}/{len(subscriptions)}] {sub_id[:8]}... 送信中: {payload['title'][:40]}")

        resp = api_post("/api/send-push", {
            "subscription": subscription_obj,
            "payload": payload
        })

        if resp and resp.get("ok"):
            sent += 1
        elif resp and resp.get("error") == "subscription_expired_deleted":
            print(f"    → 期限切れ購読を削除")
            skipped += 1
        else:
            errors += 1
            err_msg = (resp or {}).get("error", "不明なエラー")
            print(f"    → エラー: {err_msg}", file=sys.stderr)

    print(f"\n[DONE] 送信: {sent}件 / スキップ: {skipped}件 / エラー: {errors}件")
    if errors > 0:
        sys.exit(1)  # GitHub Actions で失敗扱いにする


if __name__ == "__main__":
    main()
