"""
post_to_x.py - X（旧Twitter）自動投稿スクリプト（雛形）

依存ライブラリ（pip install で導入）:
  - requests          # X API v2 への HTTP リクエスト
  - requests-oauthlib # OAuth 1.0a 認証（投稿時に必須）
  # pip install requests requests-oauthlib

環境変数（GitHub Secrets から読み込む想定）:
  X_API_KEY             : API Key（Consumer Key）
  X_API_SECRET          : API Key Secret（Consumer Secret）
  X_BEARER_TOKEN        : Bearer Token（読み取り用、今回は不使用）
  X_ACCESS_TOKEN        : Access Token
  X_ACCESS_TOKEN_SECRET : Access Token Secret

実装ステータス：雛形（モック）
  - データ読み込み・フォーマットは実装済み
  - API送信部分は関数として用意済み（実際のAPIコールは要キー設定）
  - エラーハンドリング・リトライロジック実装済み

使い方:
  python scripts/post_to_x.py --mode morning   # 朝のスケジュール投稿
  python scripts/post_to_x.py --mode results   # 試合結果投稿
  python scripts/post_to_x.py --mode weekly    # 週次まとめ投稿
  python scripts/post_to_x.py --dry-run        # 実際には送信しない（テスト確認用）
"""

import json
import os
import sys
import time
import argparse
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

# プロジェクトルートを基準にデータパスを解決
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"

# 投稿済み試合IDの記録ファイル
POSTED_MATCHES_FILE = DATA_DIR / "x_posted_matches.json"

# サイトURL（UTMパラメータ付き）
SITE_URL = "https://football-jp.com"

def make_url(path: str = "", campaign: str = "bot_morning", content: str = "schedule") -> str:
    """UTMパラメータ付きURLを生成する"""
    base = SITE_URL + path
    utm = f"?utm_source=twitter&utm_medium=social&utm_campaign={campaign}&utm_content={content}"
    return base + utm

# ---------------------------------------------------------------------------
# X API クライアント
# ---------------------------------------------------------------------------

def get_x_client():
    """
    X API v2 クライアントを返す。
    実装時は requests_oauthlib.OAuth1Session を使う。

    実装手順:
      1. pip install requests requests-oauthlib
      2. GitHub Secrets に5つの環境変数を設定
      3. 以下のコメントアウトを解除して使用
    """
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("[WARN] X API の認証情報が設定されていません。dry-run モードで実行します。")
        return None

    try:
        from requests_oauthlib import OAuth1Session
        client = OAuth1Session(
            client_key=api_key,
            client_secret=api_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
        )
        return client
    except ImportError:
        print("[ERROR] requests-oauthlib がインストールされていません。")
        print("  pip install requests requests-oauthlib")
        return None


def post_tweet(text: str, client=None, dry_run: bool = False) -> bool:
    """
    ツイートを投稿する。

    Args:
        text: 投稿するテキスト（280文字以内）
        client: OAuth1Session クライアント（None の場合は dry-run）
        dry_run: True の場合は実際には投稿しない

    Returns:
        True: 成功 / False: 失敗
    """
    if len(text) > 280:
        print(f"[WARN] テキストが280文字を超えています（{len(text)}文字）。先頭280文字を使用します。")
        text = text[:277] + "..."

    if dry_run or client is None:
        print("[DRY-RUN] 以下のツイートを投稿します（実際には送信しません）:")
        print("-" * 60)
        print(text)
        print("-" * 60)
        return True

    # X API v2 エンドポイント
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}

    # リトライロジック（最大3回）
    for attempt in range(3):
        try:
            response = client.post(url, json=payload)

            if response.status_code == 201:
                tweet_data = response.json()
                tweet_id = tweet_data.get("data", {}).get("id", "unknown")
                print(f"[OK] ツイート投稿成功: https://twitter.com/i/web/status/{tweet_id}")
                return True

            elif response.status_code == 429:
                # レートリミット超過
                wait_time = int(response.headers.get("x-rate-limit-reset", time.time() + 60)) - int(time.time())
                wait_time = max(wait_time, 60)
                print(f"[WARN] レートリミット超過。{wait_time}秒待機します...")
                time.sleep(wait_time)

            else:
                print(f"[ERROR] ツイート投稿失敗 (attempt {attempt+1}/3): HTTP {response.status_code}")
                print(f"  レスポンス: {response.text}")
                if attempt < 2:
                    wait = 30 * (2 ** attempt)
                    print(f"  {wait}秒後にリトライします...")
                    time.sleep(wait)

        except Exception as e:
            print(f"[ERROR] 例外発生 (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(30)

    return False

# ---------------------------------------------------------------------------
# データ読み込みユーティリティ
# ---------------------------------------------------------------------------

def load_matches() -> dict:
    """data/matches.json を読み込む"""
    path = DATA_DIR / "matches.json"
    if not path.exists():
        print(f"[ERROR] ファイルが見つかりません: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_players() -> list:
    """data/players.json を読み込む"""
    path = DATA_DIR / "players.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("players", [])


def load_scorers() -> dict:
    """data/scorers.json を読み込む"""
    path = DATA_DIR / "scorers.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_posted_match_ids() -> set:
    """投稿済み試合IDのセットを返す"""
    if not POSTED_MATCHES_FILE.exists():
        return set()
    with open(POSTED_MATCHES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("posted_ids", []))


def save_posted_match_id(match_id: int):
    """投稿済み試合IDを記録する"""
    existing = load_posted_match_ids()
    existing.add(match_id)
    with open(POSTED_MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump({"posted_ids": sorted(existing)}, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# 投稿テキスト生成
# ---------------------------------------------------------------------------

def format_kickoff_time(kickoff_jst: str) -> str:
    """'2026-05-04T19:00:00+09:00' → '19:00'"""
    try:
        dt = datetime.datetime.fromisoformat(kickoff_jst)
        return dt.strftime("%H:%M")
    except Exception:
        return kickoff_jst[:16]


def get_today_matches(matches_data: dict) -> list:
    """今日（JST）開催予定の試合を返す"""
    today_jst = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=9))).date()
    result = []
    for match in matches_data.get("matches", []):
        try:
            kickoff = datetime.datetime.fromisoformat(match["kickoff_jst"])
            if kickoff.date() == today_jst and match.get("status") in ("SCHEDULED", "TIMED"):
                result.append(match)
        except Exception:
            continue
    return sorted(result, key=lambda m: m["kickoff_jst"])


def get_finished_matches(matches_data: dict, posted_ids: set) -> list:
    """終了済みかつ未投稿の試合を返す"""
    result = []
    for match in matches_data.get("matches", []):
        match_id = match.get("id")
        if match.get("status") == "FINISHED" and match_id not in posted_ids:
            result.append(match)
    return result


def build_morning_schedule_text(matches: list) -> str:
    """朝のスケジュール投稿テキストを生成する"""
    today = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=9)))
    date_str = f"{today.month}月{today.day}日"

    if not matches:
        return (
            f"⚽ 今日（{date_str}）は日本人選手の海外試合はお休みです\n\n"
            "明日以降のスケジュールはこちら👇\n"
            f"{make_url('', 'bot_morning', 'no_match')}\n"
            "#海外サッカー #日本人選手"
        )

    lines = [f"⚽ 今日の日本人選手の試合（{date_str}）\n"]

    # リーグごとにグループ化（最大5試合まで表示）
    shown = 0
    current_competition = None
    for match in matches[:5]:
        comp = match.get("competition_ja", "")
        flag = match.get("competition_flag", "")
        if comp != current_competition:
            lines.append(f"\n{flag} {comp}")
            current_competition = comp

        time_str = format_kickoff_time(match.get("kickoff_jst", ""))
        home = match.get("home_ja", "")
        away = match.get("away_ja", "")
        players = match.get("japanese_players", [])
        broadcasters = match.get("broadcasters", [])

        player_str = "・".join(p.get("name_ja", "") for p in players)
        bc_str = broadcasters[0].get("name", "") if broadcasters else ""

        lines.append(f"{time_str} {home} vs {away}")
        if player_str:
            lines.append(f"└ 🇯🇵 {player_str}" + (f"　📺{bc_str}" if bc_str else ""))
        shown += 1

    if len(matches) > 5:
        lines.append(f"\n他{len(matches)-5}試合...")

    lines.append(f"\n詳細・中継情報 👇")
    lines.append(make_url("", "bot_morning", "schedule"))
    lines.append("#海外サッカー #日本人選手")

    return "\n".join(lines)


def build_result_text(match: dict) -> str:
    """試合結果投稿テキストを生成する"""
    comp_flag = match.get("competition_flag", "")
    comp_ja = match.get("competition_ja", "")
    home = match.get("home_ja", "")
    away = match.get("away_ja", "")
    score = match.get("score", {})
    home_score = score.get("home", "?")
    away_score = score.get("away", "?")
    players = match.get("japanese_players", [])
    player_str = "・".join(p.get("name_ja", "") for p in players)

    # 勝敗判定（日本人選手がいる側）
    jp_sides = set(p.get("side") for p in players)
    result_icon = "📊"
    if "home" in jp_sides and isinstance(home_score, int) and isinstance(away_score, int):
        result_icon = "✅" if home_score > away_score else ("🤝" if home_score == away_score else "❌")
    elif "away" in jp_sides and isinstance(home_score, int) and isinstance(away_score, int):
        result_icon = "✅" if away_score > home_score else ("🤝" if home_score == away_score else "❌")

    lines = [
        f"{result_icon} 試合結果",
        "",
        f"{comp_flag} {comp_ja}",
        f"{home} {home_score}-{away_score} {away}",
        "",
        f"🇯🇵 {player_str} 出場",
        "",
        f"詳細 → {make_url('', 'bot_result', 'result')}",
        f"#{comp_ja.replace('・', '').replace(' ', '')} #海外サッカー",
    ]
    return "\n".join(lines)


def build_weekly_summary_text(matches_data: dict) -> str:
    """週次まとめテキストを生成する"""
    now_jst = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=9)))
    week_ago = now_jst - datetime.timedelta(days=7)

    weekly_matches = []
    for match in matches_data.get("matches", []):
        try:
            kickoff = datetime.datetime.fromisoformat(match["kickoff_jst"])
            if week_ago <= kickoff <= now_jst and match.get("status") == "FINISHED":
                weekly_matches.append(match)
        except Exception:
            continue

    match_count = len(weekly_matches)
    date_from = week_ago.strftime("%-m月%-d日")
    date_to = now_jst.strftime("%-m月%-d日")

    if match_count == 0:
        return (
            f"📊 先週（{date_from}〜{date_to}）は試合がありませんでした\n\n"
            "今週のスケジュールはこちら👇\n"
            f"{make_url('', 'bot_weekly', 'weekly')}\n"
            "#海外サッカー #日本人選手"
        )

    lines = [
        f"📊 先週の日本人選手まとめ",
        f"（{date_from}〜{date_to}）",
        "",
        f"✅ 試合数：{match_count}試合",
        "",
        "今週の試合もチェック 👇",
        make_url("", "bot_weekly", "weekly"),
        "#海外サッカー #日本人選手 #週間まとめ",
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def post_today_schedule(client=None, dry_run: bool = False) -> bool:
    """今日のスケジュールをX に投稿する"""
    print("[INFO] 朝のスケジュール投稿を開始...")
    matches_data = load_matches()
    today_matches = get_today_matches(matches_data)
    print(f"[INFO] 今日の試合数: {len(today_matches)}")

    text = build_morning_schedule_text(today_matches)
    return post_tweet(text, client=client, dry_run=dry_run)


def post_match_results(client=None, dry_run: bool = False) -> bool:
    """直近終了した試合の結果をX に投稿する"""
    print("[INFO] 試合結果投稿を開始...")
    matches_data = load_matches()
    posted_ids = load_posted_match_ids()
    finished = get_finished_matches(matches_data, posted_ids)
    print(f"[INFO] 未投稿の終了試合: {len(finished)}件")

    success_count = 0
    for match in finished:
        text = build_result_text(match)
        ok = post_tweet(text, client=client, dry_run=dry_run)
        if ok:
            if not dry_run:
                save_posted_match_id(match["id"])
            success_count += 1
        # 連続投稿の間隔（レートリミット対策）
        if not dry_run:
            time.sleep(5)

    print(f"[INFO] 試合結果投稿完了: {success_count}/{len(finished)}件成功")
    return success_count > 0 or len(finished) == 0


def post_weekly_summary(client=None, dry_run: bool = False) -> bool:
    """週次まとめをX に投稿する"""
    print("[INFO] 週次まとめ投稿を開始...")
    matches_data = load_matches()
    text = build_weekly_summary_text(matches_data)
    return post_tweet(text, client=client, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="football-jp X投稿bot")
    parser.add_argument(
        "--mode",
        choices=["morning", "results", "weekly"],
        default="morning",
        help="投稿モード（morning: 朝スケジュール / results: 試合結果 / weekly: 週次まとめ）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には投稿しない（テスト確認用）",
    )
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        print("[INFO] DRY-RUN モードで実行します（投稿は行いません）")

    client = get_x_client()

    if args.mode == "morning":
        ok = post_today_schedule(client=client, dry_run=dry_run)
    elif args.mode == "results":
        ok = post_match_results(client=client, dry_run=dry_run)
    elif args.mode == "weekly":
        ok = post_weekly_summary(client=client, dry_run=dry_run)
    else:
        print(f"[ERROR] 未知のモード: {args.mode}")
        sys.exit(1)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
