#!/usr/bin/env python3
"""
ハイライト動画 ブラウザスクレイプ版（YouTube API クオータ切れ時の代替）
- DAZN/U-NEXT/WOWOW の各チャンネルの /videos ページを直接取得
- ytInitialData JSON を抽出 → videoRenderer から video_id+title を取得
- finished matches とタイトル照合 → matches.json に反映
"""
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

# 「アップロード再生リスト」URL（最新100動画取得可能。channel_idのUCをUUに置換）
CHANNELS = [
    {"name": "DAZN",   "url": "https://www.youtube.com/playlist?list=UUoFLB_Gw_AoxUuuzKjXrc_Q"},
    {"name": "U-NEXT", "url": "https://www.youtube.com/playlist?list=UUMjvvElkdLRTgcTKklAUkSw"},
    {"name": "WOWOW",  "url": "https://www.youtube.com/playlist?list=UUJQj2lbG_3w8UrncJd7JZXw"},
    {"name": "ABEMA",  "url": "https://www.youtube.com/playlist?list=UUVjvtweGM-Kak2D53AvfNOA"},
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
ACCEPT_LANG = "ja,en-US;q=0.9,en;q=0.8"

# 試合英語チーム名 → 日本語照合キーワード
TEAM_KEYWORDS = {
    "Liverpool": ["リヴァプール", "リバプール"],
    "Manchester City": ["マンチェスター・シティ", "マンチェスターC", "マンC"],
    "Man City": ["マンチェスター・シティ", "マンC"],
    "Manchester United": ["マンチェスター・ユナイテッド", "マンU"],
    "Man United": ["マンチェスター・ユナイテッド", "マンU"],
    "Arsenal": ["アーセナル"],
    "Chelsea": ["チェルシー"],
    "Tottenham": ["トッテナム"],
    "Crystal Palace": ["クリスタル・パレス", "クリスタルパレス"],
    "Brighton & Hove Albion": ["ブライトン"],
    "Newcastle": ["ニューカッスル"],
    "Aston Villa": ["アストン・ビラ", "アストンビラ"],
    "West Ham": ["ウェストハム"],
    "Wolverhampton": ["ウルブス", "ウルバーハンプトン", "ウォルバーハンプトン"],
    "Everton": ["エヴァートン", "エバートン"],
    "Nottingham Forest": ["ノッティンガム"],
    "Nottingham": ["ノッティンガム"],
    "Fulham": ["フラム"],
    "Brentford": ["ブレントフォード"],
    "Bournemouth": ["ボーンマス"],
    "Leeds": ["リーズ"],
    "Burnley": ["バーンリー"],
    # Championship
    "Southampton": ["サウサンプトン"],
    "Ipswich": ["イプスウィッチ"],
    "Ipswich Town": ["イプスウィッチ"],
    "Birmingham": ["バーミンガム"],
    "Bristol City": ["ブリストル・シティ", "ブリストルシティ"],
    "Coventry": ["コヴェントリー"],
    "Hull City": ["ハル・シティ", "ハルシティ"],
    "Charlton": ["チャールトン"],
    "Blackburn": ["ブラックバーン"],
    "Queens Park Rangers": ["QPR"],
    "Derby County": ["ダービー"],
    "Stoke City": ["ストーク"],
    "Portsmouth": ["ポーツマス"],
    "Norwich": ["ノリッジ"],
    "Swansea": ["スウォンジー"],
    "Watford": ["ワトフォード"],
    "Middlesbrough": ["ミドルズブラ"],
    "Millwall": ["ミルウォール"],
    "Leicester": ["レスター"],
    "Sunderland": ["サンダーランド"],
    "WBA": ["WBA", "ウェスト・ブロムウィッチ"],
    "Sheffield United": ["シェフィールド・ユナイテッド"],
    "Sheffield Utd": ["シェフィールド・ユナイテッド"],
    "Sheffield Wednesday": ["シェフィールド・ウェンズデー"],
    "Sheffield Wed": ["シェフィールド・ウェンズデー"],
    "Preston": ["プレストン"],
    "Preston NE": ["プレストン"],
    "Oxford": ["オックスフォード"],
    "Oxford United": ["オックスフォード"],
    "Wrexham": ["レクサム"],
    "WBA": ["WBA", "ウェスト・ブロムウィッチ"],
    "West Brom": ["WBA", "ウェスト・ブロムウィッチ"],
    "Stoke": ["ストーク"],
    "Stoke City": ["ストーク"],
    # La Liga
    "Real Madrid": ["レアル・マドリード", "レアル・マドリー", "マドリー"],
    "FC Barcelona": ["バルセロナ"],
    "Barça": ["バルセロナ"],
    "Atlético Madrid": ["アトレティコ・マドリード", "アトレティコ・マドリー", "アトレティコ"],
    "Atleti": ["アトレティコ・マドリード", "アトレティコ・マドリー", "アトレティコ"],
    "Real Sociedad": ["レアル・ソシエダ"],
    "Athletic Club": ["アスレティック・ビルバオ", "ビルバオ"],
    "Athletic": ["アスレティック・ビルバオ", "ビルバオ"],
    "Sevilla": ["セビージャ", "セビリア"],
    "Sevilla FC": ["セビージャ", "セビリア"],
    "Villarreal": ["ビジャレアル"],
    "Valencia": ["バレンシア"],
    "Real Betis": ["レアル・ベティス", "ベティス"],
    "Mallorca": ["マジョルカ"],
    "Getafe": ["ヘタフェ"],
    "Espanyol": ["エスパニョール"],
    "Rayo Vallecano": ["ラージョ・バジェカーノ"],
    "Girona": ["ジローナ"],
    "Levante": ["レバンテ"],
    "Alavés": ["アラベス"],
    "Real Oviedo": ["レアル・オビエド", "オビエド"],
    "Celta de Vigo": ["セルタ"],
    "Celta": ["セルタ"],
    "Osasuna": ["オサスナ"],
    "Elche": ["エルチェ"],
    # Serie A
    "Juventus": ["ユヴェントス", "ユベントス"],
    "Inter": ["インテル"],
    "AC Milan": ["ACミラン", "ミラン"],
    "Milan": ["ACミラン", "ミラン"],
    "Napoli": ["ナポリ"],
    "Roma": ["ローマ"],
    "Lazio": ["ラツィオ"],
    "Atalanta": ["アタランタ"],
    "Fiorentina": ["フィオレンティーナ"],
    "Bologna": ["ボローニャ"],
    "Parma": ["パルマ"],
    "AC Pisa": ["ピサ"],
    "Sassuolo": ["サッスオーロ"],
    "Torino": ["トリノ"],
    "Cremonese": ["クレモネーゼ"],
    "Lecce": ["レッチェ"],
    "Genoa": ["ジェノア"],
    "Cagliari": ["カリアリ"],
    "Verona": ["ヴェローナ"],
    "Como 1907": ["コモ"],
    "Udinese": ["ウディネーゼ"],
    # Bundesliga
    "Bayern": ["バイエルン"],
    "Borussia Dortmund": ["ドルトムント"],
    "Dortmund": ["ドルトムント"],
    "Borussia Mönchengladbach": ["ボルシアMG", "メンヒェングラートバッハ", "MG"],
    "M'gladbach": ["ボルシアMG", "メンヒェングラートバッハ"],
    "Bayer Leverkusen": ["レバークーゼン"],
    "Leverkusen": ["レバークーゼン"],
    "Freiburg": ["フライブルク"],
    "Mainz": ["マインツ"],
    "Augsburg": ["アウクスブルク"],
    "St. Pauli": ["ザンクト・パウリ"],
    "Heidenheim": ["ハイデンハイム"],
    "Wolfsburg": ["ヴォルフスブルク"],
    "Werder": ["ブレーメン"],
    "Bremen": ["ブレーメン"],
    "Stuttgart": ["シュトゥットガルト"],
    "HSV": ["ハンブルガー"],
    "Hoffenheim": ["ホッフェンハイム"],
    "RB Leipzig": ["RBライプツィヒ", "ライプツィヒ"],
    "Eintracht Frankfurt": ["フランクフルト"],
    "VfB Stuttgart": ["シュトゥットガルト"],
    "Werder Bremen": ["ブレーメン"],
    "VfL Wolfsburg": ["ヴォルフスブルク"],
    "FC Augsburg": ["アウクスブルク"],
    "Mainz 05": ["マインツ"],
    "TSG Hoffenheim": ["ホッフェンハイム"],
    "1. FC Köln": ["ケルン"],
    "SC Freiburg": ["フライブルク"],
    "1. FC Heidenheim": ["ハイデンハイム"],
    "FC St. Pauli": ["ザンクト・パウリ", "ザンクトパウリ"],
    "Hamburger SV": ["ハンブルガー", "ハンブルク"],
    "Union Berlin": ["ウニオン・ベルリン", "ウニオン"],
    # Ligue 1
    "PSG": ["PSG", "パリ・サンジェルマン", "パリSG"],
    "Marseille": ["マルセイユ"],
    "Lyon": ["リヨン"],
    "Olympique Lyon": ["リヨン"],
    "Monaco": ["モナコ"],
    "Lille": ["リール"],
    "Rennes": ["レンヌ"],
    "Stade Rennais": ["レンヌ"],
    "Strasbourg": ["ストラスブール"],
    "Nice": ["ニース"],
    "Nantes": ["ナント"],
    "Le Havre": ["ル・アーヴル", "ルアーヴル"],
    "Brest": ["ブレスト"],
    "Lens": ["ランス"],
    "RC Lens": ["ランス"],
    "FC Metz": ["メス"],
    "Toulouse": ["トゥールーズ", "トゥールズ"],
    "Auxerre": ["オセール"],
    "Lorient": ["ロリアン"],
    "Angers SCO": ["アンジェ"],
    "Paris FC": ["パリFC"],
    # Eredivisie
    "Ajax": ["アヤックス"],
    "Feyenoord": ["フェイエノールト"],
    "PSV": ["PSV"],
    "AZ": ["AZ", "AZアルクマール", "アルクマール"],
    "Twente": ["トゥエンテ"],
    "NAC Breda": ["NACブレダ"],
    "Heracles": ["ヘラクレス"],
    "Volendam": ["フォレンダム"],
    "Heerenveen": ["ヘーレンフェーン"],
    "Fortuna Sittard": ["フォルトゥナ・シッタート"],
    "Sittard": ["フォルトゥナ・シッタート"],
    "PEC Zwolle": ["ズヴォレ"],
    "Zwolle": ["ズヴォレ"],
    "NEC": ["NEC"],
    "Excelsior": ["エクセルシオール"],
    "Utrecht": ["ユトレヒト"],
    "Sparta Rotterdam": ["スパルタ・ロッテルダム"],
    "Groningen": ["フローニンゲン"],
    "Go Ahead": ["ゴー・アヘッド"],
    # Primeira
    "Sporting CP": ["スポルティング"],
    "FC Porto": ["ポルト"],
    "Porto": ["ポルト"],
    "Benfica": ["ベンフィカ"],
    "SL Benfica": ["ベンフィカ"],
    "Braga": ["ブラガ"],
    "Gil Vicente": ["ジル・ヴィセンテ"],
    "Casa Pia": ["カーザ・ピア"],
    "Tondela": ["トンデラ"],
    "AVS": ["AVS"],
    "Alverca": ["アルヴェルカ"],
    "Arouca": ["アロウカ"],
    "Estoril": ["エストリル"],
    "Estoril Praia": ["エストリル"],
    "Famalicão": ["ファマリカン"],
    "Vitória": ["ヴィトーリア"],
    "Vitória SC": ["ヴィトーリア"],
    "Rio Ave": ["リオアヴェ"],
    "Santa Clara": ["サンタクララ"],
    "Estrela Amadora": ["アマドーラ"],
    "Amadora": ["アマドーラ"],
    "Nacional": ["ナシオナル"],
    "CD Nacional": ["ナシオナル"],
    "Moreirense": ["モレイレンセ"],
}


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": ACCEPT_LANG})
    try:
        with urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def extract_videos(html):
    if not html:
        return []
    m = re.search(r"var ytInitialData = ({.+?});</script>", html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    out = []

    def walk(obj):
        if isinstance(obj, dict):
            vid = obj.get("videoId")
            title_obj = obj.get("title")
            if vid and isinstance(title_obj, dict):
                runs = title_obj.get("runs") or []
                if runs and isinstance(runs[0], dict) and runs[0].get("text"):
                    out.append({"video_id": vid, "title": runs[0]["text"]})
                    return
                st = title_obj.get("simpleText")
                if st:
                    out.append({"video_id": vid, "title": st})
                    return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    seen = set()
    uniq = []
    for x in out:
        if x["video_id"] in seen:
            continue
        seen.add(x["video_id"])
        uniq.append(x)
    return uniq


def team_kws(team_en):
    if not team_en:
        return []
    if team_en in TEAM_KEYWORDS:
        return TEAM_KEYWORDS[team_en]
    return [team_en]


def title_match(title, home_en, away_en):
    if not title:
        return False
    t = title
    home_hit = any(k in t for k in team_kws(home_en))
    away_hit = any(k in t for k in team_kws(away_en))
    return home_hit and away_hit


def main():
    matches_path = DATA / "matches.json"
    matches_data = json.loads(matches_path.read_text(encoding="utf-8"))
    matches = matches_data.get("matches", [])

    # 全チャンネル取得
    all_videos = []
    for ch in CHANNELS:
        print(f"[INFO] {ch['name']} 取得中: {ch['url']}")
        html = fetch(ch["url"])
        vids = extract_videos(html)
        print(f"  → {len(vids)}本")
        for v in vids:
            v["channel_name"] = ch["name"]
            all_videos.append(v)

    print(f"[INFO] 合計動画: {len(all_videos)}本")

    # 既存ハイライトクリア（公式4チャンネル外）
    APPROVED = {"DAZN", "U-NEXT", "WOWOW", "ABEMA"}
    cleared = 0
    for m in matches:
        if not m.get("highlights"):
            continue
        keep = []
        for h in m["highlights"]:
            bc = (h.get("broadcaster") or "").upper()
            if any(a in bc for a in APPROVED):
                keep.append(h)
            else:
                cleared += 1
        m["highlights"] = keep
    if cleared:
        print(f"[INFO] 公式外ハイライト {cleared}件 をクリア")

    # finished matches に対して照合
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    found = 0
    for m in finished:
        existing = m.get("highlights") or []
        if any(h.get("video_id") for h in existing):
            continue
        for v in all_videos:
            if title_match(v["title"], m.get("home_en"), m.get("away_en")):
                m["highlights"] = [{
                    "broadcaster": v["channel_name"],
                    "video_id": v["video_id"],
                    "url": f"https://youtu.be/{v['video_id']}",
                    "title": v["title"],
                }]
                print(f"  ⚽ {m['kickoff_jst'][:10]} {m['home_ja']} vs {m['away_ja']} → [{v['channel_name']}] {v['title'][:60]}")
                found += 1
                break

    matches_data["updated_yt_highlights_scrape"] = datetime.now(JST).isoformat()
    matches_path.write_text(json.dumps(matches_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] ハイライト追加: {found}件 / 試合データ {len(finished)}件中")


if __name__ == "__main__":
    main()
