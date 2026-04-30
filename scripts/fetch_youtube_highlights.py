#!/usr/bin/env python3
"""
Phase 2: YouTube Data API でハイライト動画を自動取得
- 対象チャンネル（公式3チャンネルのみ）:
  - DAZN Japan: @DAZNJapan
  - U-NEXT Football: @UNEXT_football
  - WOWOW サッカー: @wowowsoccer
- 各チャンネルの最新アップロードをまとめて取得（search.list × 3 = 300ユニット/日）
- finished matches の title 内チーム名と照合してマッチング
- 出力: data/matches.json の各 match.highlights[] 更新
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

# 対象3チャンネル（公式・日本語）
CHANNELS = [
    {"name": "DAZN", "handle": "@DAZNJapan", "id": "UCyeDNNizMGbVsn_8Ttc3FIw"},
    {"name": "U-NEXT", "handle": "@UNEXT_football", "id": "UCMjvvElkdLRTgcTKklAUkSw"},
    {"name": "WOWOW", "handle": "@wowowsoccer", "id": "UCJQj2lbG_3w8UrncJd7JZXw"},
]

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
        sys.exit(1)

    matches_data = load_json("matches.json")
    matches = matches_data.get("matches", [])

    # 既存の sample でない非公式ハイライトをクリア（過去のテスト残骸）
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
            if any(c["name"].lower() in ch for c in CHANNELS):
                keep.append(h)
            else:
                cleared += 1
        m["highlights"] = keep
    if cleared > 0:
        print(f"[INFO] 公式チャンネル外のハイライトを {cleared}件 削除")

    # 各チャンネルから最新50件取得（過去2週間に絞る）
    after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_videos = []
    for ch in CHANNELS:
        print(f"[INFO] {ch['name']} の最新動画取得...")
        data = yt_search_channel(ch["id"], key, max_results=50, published_after=after)
        if not data or not data.get("items"):
            continue
        for it in data["items"]:
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
        print(f"  → {ch['name']}: {len([v for v in all_videos if v['channel_id']==ch['id']])}本")

    print(f"[INFO] 取得動画 累計 {len(all_videos)}本 / API calls: {_call_count}")

    # finished matches に対して動画照合
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    found = 0
    for m in finished:
        # 既に公式ハイライトある場合はスキップ
        existing = m.get("highlights") or []
        has_real = any(h.get("video_id") and not h.get("is_sample") for h in existing)
        if has_real:
            continue
        # 試合日 ±3日のビデオから絞り込み
        try:
            ko = datetime.fromisoformat(m["kickoff_jst"]).astimezone(timezone.utc)
        except Exception:
            continue
        win_start = ko - timedelta(days=1)
        win_end = ko + timedelta(days=5)
        candidates = []
        for v in all_videos:
            try:
                pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            if not (win_start <= pub <= win_end):
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
        m["highlights"] = [new_h] + [h for h in (m.get("highlights") or []) if h.get("is_sample") and h.get("broadcaster") not in [c["name"] for c in CHANNELS]]
        # 上書き（サンプル除去）
        m["highlights"] = [new_h]
        print(f"  ⚽ {m['kickoff_jst'][:10]} {m['home_ja']} vs {m['away_ja']} → [{best['channel_name']}] {best['title'][:60]}")
        found += 1

    matches_data["updated_yt_highlights"] = datetime.now(JST).isoformat()
    save_json("matches.json", matches_data)
    print(f"\n[DONE] ハイライト発見: {found}件 / API calls: {_call_count} / 残量目安: {10000 - _call_count*100}ユニット")


if __name__ == "__main__":
    main()
