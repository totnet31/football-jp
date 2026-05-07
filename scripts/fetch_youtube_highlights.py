#!/usr/bin/env python3
"""
Phase 2: YouTube Data API でハイライト動画を自動取得
- 対象チャンネル（公式5チャンネル）:
  - DAZN Japan: @DAZNJapan
  - U-NEXT Football: @UNEXT_football
  - WOWOW サッカー: @wowowsoccer
  - DAZN Football (英語版): UCSZ21xyG8w_33KriMM69IxQ
  - DAZN Fußball (ドイツ語版・ブンデス): UClBFnQJMlinWDCvfSXj60CA
- 各チャンネルの最新アップロードをまとめて取得（search.list × 5 = 500ユニット/日）
- finished matches の title 内チーム名と照合してマッチング
- 出力: data/matches.json の各 match.highlights[] 更新

【0件になる主な原因】
1. GitHub Actions で YOUTUBE_API_KEY secret が未設定の場合はスキップされる
2. publishedAfter のタイムゾーン処理（UTC基準で正常）
3. チャンネルが動画を非公開にした場合
"""
import json
import os
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

# 対象チャンネル（公式・日本語 + 英語/ドイツ語補完）
CHANNELS = [
    {"name": "DAZN", "handle": "@DAZNJapan", "id": "UCoFLB_Gw_AoxUuuzKjXrc_Q"},
    {"name": "U-NEXT", "handle": "@UNEXT_football", "id": "UCMjvvElkdLRTgcTKklAUkSw"},
    {"name": "WOWOW", "handle": "@wowowsoccer", "id": "UCJQj2lbG_3w8UrncJd7JZXw"},
    {"name": "DAZN Football", "handle": "@DAZNFootball", "id": "UCSZ21xyG8w_33KriMM69IxQ"},
    {"name": "DAZN Fussball", "handle": "@DAZNFussball", "id": "UClBFnQJMlinWDCvfSXj60CA"},
]

# UEFAクラブ大会（UCL/UEL/UECL）はWOWOWの独占放映なので、ハイライト動画もWOWOWチャンネルからのみ取得する
# 他チャンネル（DAZN等）が同タイトルで動画を出していても採用しない
UEFA_CLUB_COMPETITION_IDS = {2, 3, 848}  # UCL / UEL / UECL
UEFA_EXCLUSIVE_CHANNEL = "WOWOW"

# Wikipedia の英語チーム名 → 日本語の代表的な検索キーワード
TEAM_KEYWORDS = {
    # プレミア
    "Liverpool": ["リヴァプール", "リバプール", "Liverpool"],
    "Manchester City": ["マンチェスター・シティ", "マンC", "Man City"],
    "Manchester United": ["マンチェスター・ユナイテッド", "マンU", "Man Utd"],
    "Arsenal": ["アーセナル", "Arsenal"],
    "Chelsea": ["チェルシー", "Chelsea"],
    "Tottenham": ["トッテナム", "Tottenham", "Spurs"],
    "Crystal Palace": ["クリスタル・パレス", "Crystal Palace"],
    "Brighton & Hove Albion": ["ブライトン", "Brighton"],
    "Newcastle": ["ニューカッスル", "Newcastle"],
    "Aston Villa": ["アストン・ビラ", "Aston Villa"],
    "West Ham": ["ウェストハム", "West Ham"],
    "Wolverhampton": ["ウルブス", "ウルバーハンプトン", "Wolves"],
    "Everton": ["エヴァートン", "エバートン", "Everton"],
    "Nottingham Forest": ["ノッティンガム", "Forest"],
    "Fulham": ["フラム", "Fulham"],
    "Brentford": ["ブレントフォード", "Brentford"],
    "Bournemouth": ["ボーンマス", "Bournemouth"],
    "Southampton": ["サウサンプトン", "Southampton"],
    "Leeds": ["リーズ", "Leeds"],
    # La Liga
    "Real Madrid": ["レアル・マドリード", "レアル・マドリー", "Real Madrid"],
    "FC Barcelona": ["バルセロナ", "Barcelona"],
    "Atlético Madrid": ["アトレティコ・マドリード", "アトレティコ・マドリー", "Atletico"],
    "Real Sociedad": ["レアル・ソシエダ", "Real Sociedad"],
    "Athletic Club": ["アスレティック・ビルバオ", "ビルバオ", "Athletic"],
    "Sevilla": ["セビージャ", "セビリア", "Sevilla"],
    "Villarreal": ["ビジャレアル", "Villarreal"],
    "Valencia": ["バレンシア", "Valencia"],
    "Real Betis": ["レアル・ベティス", "ベティス", "Betis"],
    "Mallorca": ["マジョルカ", "Mallorca"],
    "Getafe": ["ヘタフェ", "Getafe"],
    "Espanyol": ["エスパニョール", "Espanyol"],
    "Rayo Vallecano": ["ラージョ・バジェカーノ", "Rayo"],
    "Girona": ["ジローナ", "Girona"],
    "Levante": ["レバンテ", "Levante"],
    "Alavés": ["アラベス", "Alaves"],
    "Real Oviedo": ["レアル・オビエド", "Oviedo"],
    "Celta de Vigo": ["セルタ", "Celta"],
    "Osasuna": ["オサスナ", "Osasuna"],
    # Serie A
    "Juventus": ["ユヴェントス", "ユベントス", "Juventus"],
    "Inter": ["インテル", "Inter Milan"],
    "AC Milan": ["ACミラン", "AC Milan"],
    "Napoli": ["ナポリ", "Napoli"],
    "Roma": ["ローマ", "Roma"],
    "Lazio": ["ラツィオ", "Lazio"],
    "Atalanta": ["アタランタ", "Atalanta"],
    "Fiorentina": ["フィオレンティーナ", "Fiorentina"],
    "Bologna": ["ボローニャ", "Bologna"],
    "Parma": ["パルマ", "Parma"],
    "AC Pisa": ["ピサ", "Pisa"],
    "Sassuolo": ["サッスオーロ", "Sassuolo"],
    "Torino": ["トリノ", "Torino"],
    "Cremonese": ["クレモネーゼ", "Cremonese"],
    # Bundesliga
    "Bayern": ["バイエルン", "バイエルン・ミュンヘン", "Bayern"],
    "Borussia Dortmund": ["ドルトムント", "Dortmund"],
    "Borussia Mönchengladbach": ["ボルシアMG", "メンヒェングラートバッハ", "Borussia M"],
    "Bayer Leverkusen": ["レバークーゼン", "Leverkusen"],
    "RB Leipzig": ["RBライプツィヒ", "ライプツィヒ", "Leipzig"],
    "Eintracht Frankfurt": ["フランクフルト", "Frankfurt"],
    "VfB Stuttgart": ["シュトゥットガルト", "Stuttgart"],
    "Werder Bremen": ["ブレーメン", "Bremen"],
    "VfL Wolfsburg": ["ヴォルフスブルク", "Wolfsburg"],
    "FC Augsburg": ["アウクスブルク", "Augsburg"],
    "Mainz 05": ["マインツ", "Mainz"],
    "TSG Hoffenheim": ["ホッフェンハイム", "Hoffenheim"],
    "1. FC Köln": ["ケルン", "Köln", "Koln"],
    "SC Freiburg": ["フライブルク", "Freiburg"],
    "1. FC Heidenheim": ["ハイデンハイム", "Heidenheim"],
    "FC St. Pauli": ["ザンクト・パウリ", "St. Pauli"],
    "Hamburger SV": ["ハンブルガー", "ハンブルク", "Hamburg"],
    "Union Berlin": ["ウニオン・ベルリン", "Union Berlin"],
    # Ligue 1
    "Paris Saint-Germain": ["PSG", "パリ・サンジェルマン", "Paris"],
    "Marseille": ["マルセイユ", "Marseille"],
    "Lyon": ["リヨン", "Lyon"],
    "Monaco": ["モナコ", "Monaco"],
    "Lille": ["リール", "Lille"],
    "Rennes": ["レンヌ", "Rennes"],
    "Strasbourg": ["ストラスブール", "Strasbourg"],
    "Nice": ["ニース", "Nice"],
    "Nantes": ["ナント", "Nantes"],
    "Le Havre": ["ル・アーヴル", "Le Havre"],
    "Brest": ["ブレスト", "Brest"],
    "Lens": ["ランス", "Lens"],
    "FC Metz": ["メス", "Metz"],
    "Toulouse": ["トゥールーズ", "Toulouse"],
    "Auxerre": ["オセール", "Auxerre"],
    "Lorient": ["ロリアン", "Lorient"],
    "Angers": ["アンジェ", "Angers"],
    # Eredivisie
    "Ajax": ["アヤックス", "Ajax"],
    "Feyenoord": ["フェイエノールト", "Feyenoord"],
    "PSV": ["PSV"],
    "AZ": ["AZ", "AZアルクマール"],
    "Twente": ["トゥエンテ", "Twente"],
    # Primeira Liga
    "Sporting CP": ["スポルティング", "Sporting"],
    "FC Porto": ["ポルト", "Porto"],
    "Benfica": ["ベンフィカ", "Benfica"],
    "Braga": ["ブラガ", "Braga"],
    "Gil Vicente": ["ジル・ヴィセンテ", "Gil Vicente"],
}


def load_env():
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save_json(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


_call_count = 0


def yt_search_channel(channel_id, key, max_results=50, published_after=None):
    """指定チャンネルの最新アップロードを取得"""
    global _call_count
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "order": "date",
        "maxResults": str(max_results),
        "key": key,
    }
    if published_after:
        params["publishedAfter"] = published_after
    url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
    _call_count += 1
    try:
        with urlopen(url, timeout=20) as r:
            return json.loads(r.read())
    except (HTTPError, URLError) as e:
        print(f"  [YT ERROR] channel {channel_id}: {e}", file=sys.stderr)
        return None


def team_keywords(team_en):
    """team_en から検索キーワードのリストを取得（日本語表記含む）"""
    if not team_en:
        return []
    if team_en in TEAM_KEYWORDS:
        return TEAM_KEYWORDS[team_en]
    # フォールバック：英語名そのまま、+ 主要トークン
    out = [team_en]
    tokens = [w for w in re.split(r"\W+", team_en) if len(w) >= 4]
    out.extend(tokens)
    return out


def title_match(title, home_en, away_en):
    """両チームの代表ワードがタイトルに含まれているか"""
    if not title:
        return False
    t = title.lower()
    home_kws = [k.lower() for k in team_keywords(home_en)]
    away_kws = [k.lower() for k in team_keywords(away_en)]
    home_hit = any(k in t for k in home_kws if k)
    away_hit = any(k in t for k in away_kws if k)
    return home_hit and away_hit


def main():
    env = load_env()
    key = env.get("YOUTUBE_API_KEY")
    if not key:
        print("[ERROR] YOUTUBE_API_KEY が .env にありません", file=sys.stderr)
        print("[ERROR] GitHub Actions の場合: Settings > Secrets > YOUTUBE_API_KEY を登録してください", file=sys.stderr)
        sys.exit(1)

    # publishedAfter: 過去14日間（UTC基準）
    now_utc = datetime.now(timezone.utc)
    after = (now_utc - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[INFO] 取得範囲: {after} 〜 {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')} (UTC)")

    matches_data = load_json("matches.json")
    matches = matches_data.get("matches", [])

    # 既存の sample でない非公式ハイライトをクリア（過去のテスト残骸）
    all_channel_names = [c["name"].lower() for c in CHANNELS]
    cleared = 0
    for m in matches:
        if not m.get("highlights"):
            continue
        keep = []
        for h in m["highlights"]:
            if h.get("is_sample"):
                keep.append(h)
                continue
            ch = (h.get("broadcaster") or "").lower()
            if any(cn in ch for cn in all_channel_names):
                keep.append(h)
            else:
                cleared += 1
        m["highlights"] = keep
    if cleared > 0:
        print(f"[INFO] 公式チャンネル外のハイライトを {cleared}件 削除")

    # 各チャンネルから最新50件取得（過去2週間に絞る）
    all_videos = []
    channel_counts = {}
    for ch in CHANNELS:
        print(f"[INFO] {ch['name']} ({ch['handle']}) の最新動画取得中...")
        data = yt_search_channel(ch["id"], key, max_results=50, published_after=after)
        if data is None:
            print(f"  → {ch['name']}: APIエラー（スキップ）", file=sys.stderr)
            channel_counts[ch["name"]] = 0
            continue
        if "error" in data:
            err = data["error"]
            print(f"  → {ch['name']}: APIエラー code={err.get('code')} {err.get('message','')}", file=sys.stderr)
            channel_counts[ch["name"]] = 0
            continue
        items = data.get("items") or []
        count_before = len(all_videos)
        for it in items:
            s = it.get("snippet") or {}
            vid = it.get("id", {}).get("videoId")
            if not vid:
                continue
            all_videos.append({
                "video_id": vid,
                "title": s.get("title", ""),
                "channel_name": ch["name"],
                "channel_id": ch["id"],
                "published_at": s.get("publishedAt", ""),
            })
        count = len(all_videos) - count_before
        channel_counts[ch["name"]] = count
        print(f"  → {ch['name']}: {count}本 取得")
        if count == 0 and items:
            print(f"  [WARN] items={len(items)}件あるが videoId が取れなかった（resourceId 形式の可能性）")

    print(f"[INFO] 取得動画 累計 {len(all_videos)}本 / API calls: {_call_count}")
    print(f"[INFO] チャンネル別: {channel_counts}")

    # finished matches に対して動画照合
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    print(f"[INFO] 照合対象（FINISHED）: {len(finished)}試合")
    found = 0
    skipped_has_hl = 0
    for m in finished:
        # 既に公式ハイライトある場合はスキップ
        existing = m.get("highlights") or []
        has_real = any(h.get("video_id") and not h.get("is_sample") for h in existing)
        if has_real:
            skipped_has_hl += 1
            continue
        # 試合日 ±1日〜+5日のビデオから絞り込み
        try:
            ko = datetime.fromisoformat(m["kickoff_jst"]).astimezone(timezone.utc)
        except Exception:
            continue
        win_start = ko - timedelta(days=1)
        win_end = ko + timedelta(days=5)
        # UEFA独占大会は WOWOW チャンネルからのみ採用
        is_uefa_exclusive = m.get("competition_id") in UEFA_CLUB_COMPETITION_IDS
        candidates = []
        for v in all_videos:
            try:
                pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            if not (win_start <= pub <= win_end):
                continue
            if is_uefa_exclusive and v["channel_name"] != UEFA_EXCLUSIVE_CHANNEL:
                continue
            if title_match(v["title"], m.get("home_en"), m.get("away_en")):
                candidates.append(v)
        if not candidates:
            continue
        # 公開日が試合に最も近いものを採用
        candidates.sort(key=lambda v: abs((datetime.fromisoformat(v["published_at"].replace("Z","+00:00")) - ko).total_seconds()))
        best = candidates[0]
        new_h = {
            "broadcaster": best["channel_name"],
            "video_id": best["video_id"],
            "url": f"https://youtu.be/{best['video_id']}",
            "title": best["title"],
            "yt_published": best["published_at"][:10],
        }
        # 上書き（サンプル除去・既存の公式ハイライトは新しいものに更新）
        m["highlights"] = [new_h]
        print(f"  ⚽ {m['kickoff_jst'][:10]} {m['home_ja']} vs {m['away_ja']} → [{best['channel_name']}] {best['title'][:60]}")
        found += 1

    print(f"[INFO] スキップ（既存ハイライトあり）: {skipped_has_hl}試合")
    matches_data["updated_yt_highlights"] = datetime.now(JST).isoformat()
    save_json("matches.json", matches_data)
    used_units = _call_count * 100
    print(f"\n[DONE] ハイライト発見: {found}件 / API calls: {_call_count} / 使用ユニット: {used_units} / 残量目安: {10000 - used_units}ユニット")


if __name__ == "__main__":
    main()
