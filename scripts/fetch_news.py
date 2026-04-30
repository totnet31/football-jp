#!/usr/bin/env python3
"""
日本人選手 ニュース集約
- 複数の日本サッカーメディアRSSから記事を取得
- 日本人選手67名のうち1名以上の名前/苗字がタイトル/概要に含まれるものをフィルタ
- 出力: data/news.json （直近100件・重複排除・新しい順）
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"

# RSSソース（ニュース性高い順）
SOURCES = [
    {"name": "サッカーキング", "url": "https://www.soccer-king.jp/feed"},
    {"name": "Football Channel", "url": "https://www.footballchannel.jp/feed/"},
    {"name": "Footballista", "url": "https://www.footballista.jp/feed"},
    {"name": "THE WORLD", "url": "https://www.theworldmagazine.jp/feed"},
    {"name": "ゲキサカ", "url": "https://web.gekisaka.jp/feed"},
    {"name": "Football Zone", "url": "https://www.football-zone.net/feed"},
    {"name": "Number Web (サッカー)", "url": "https://number.bunshun.jp/list/feed?genre=soccer"},
]

# 低品質タイトルパターン（試合記録/写真ギャラリーのみは除外）
LOW_QUALITY_PATTERNS = [
    r"^.+vs.+\s*試合記録\s*$",
    r"^.+vs.+\s*$",  # 単なる "AvsB" だけ
    r"試合記録$",
    r"^【写真ギャラリー】",
    r"^【写真特集】",
    r"\(\d+枚\)$",  # "(N枚)" で終わる写真ギャラリー
    r"^写真[一覧]?[:：]",
]


def fetch(url):
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def parse_rss(xml, source_name):
    items_raw = re.findall(r"<item[^>]*>(.*?)</item>", xml, re.DOTALL)
    out = []
    for raw in items_raw:
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.DOTALL)
        link_m = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", raw, re.DOTALL)
        if not link_m:
            link_m = re.search(r"<guid[^>]*>(.*?)</guid>", raw)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", raw)
        desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", raw, re.DOTALL)
        title = (title_m.group(1) if title_m else "").strip()
        title = re.sub(r"<[^>]+>", "", title)
        link = (link_m.group(1) if link_m else "").strip()
        desc = re.sub(r"<[^>]+>", "", (desc_m.group(1) if desc_m else "")).strip()
        # pubDate → ISO
        pub_iso = None
        if pub_m:
            try:
                dt = parsedate_to_datetime(pub_m.group(1).strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                pub_iso = dt.astimezone(JST).isoformat()
            except Exception:
                pass
        if not title or not link:
            continue
        out.append({
            "title": title,
            "link": link,
            "published": pub_iso,
            "description": desc[:200],
            "source": source_name,
        })
    return out


# 追加：playersに無いが、海外でプレーする日本人選手（ニュース捕捉用）
EXTRA_OVERSEAS_PLAYERS = [
    "旗手怜央", "中村敬斗", "鈴木優磨", "前田大然", "古橋亨梧",
    "西川潤", "鈴木武蔵", "伊東純也", "森下龍矢", "湊谷凌",
    "南野拓実", "冨安健洋", "板倉滉", "守田英正", "鎌田大地",
    "上田綺世", "町田浩樹", "佐野海舟", "佐野航大", "藤田譲瑠チマ",
    "遠藤渓太", "原口元気", "鎌田大地", "三好康児", "守田英正",
]


def build_player_keywords(players_data):
    """各選手の検索キーワード（名前・苗字）"""
    out = []
    seen = set()
    for p in players_data.get("players", []):
        name_ja = p.get("name_ja", "").strip()
        if not name_ja or name_ja in seen:
            continue
        seen.add(name_ja)
        last_name = name_ja.split()[0] if " " in name_ja else (name_ja.split("　")[0] if "　" in name_ja else name_ja[:2] if len(name_ja) >= 2 else name_ja)
        full = name_ja.replace(" ", "").replace("　", "")
        out.append({"name_ja": name_ja, "full_no_space": full, "last_name": last_name})
    # 追加分も足す
    for name_ja in EXTRA_OVERSEAS_PLAYERS:
        if name_ja in seen:
            continue
        seen.add(name_ja)
        last_name = name_ja[:2] if len(name_ja) >= 2 else name_ja
        out.append({"name_ja": name_ja, "full_no_space": name_ja, "last_name": last_name})
    return out


# J-League関連ワード（誤検出除外）
JLEAGUE_EXCLUDE = [
    "Jリーグ", "J1リーグ", "J2リーグ", "J3リーグ", "J1", "J2", "J3",
    "FC町田", "町田ゼルビア", "FC東京", "横浜FM", "横浜マリノス", "鹿島アントラーズ",
    "浦和レッズ", "川崎フロンターレ", "ガンバ大阪", "セレッソ大阪", "サンフレッチェ広島",
    "ヴィッセル神戸", "名古屋グランパス", "アビスパ福岡", "ジュビロ磐田", "サガン鳥栖",
    "アルビレックス新潟", "湘南ベルマーレ", "京都サンガ", "柏レイソル", "清水エスパルス",
    "WEリーグ", "なでしこリーグ", "天皇杯", "ルヴァンカップ",
]

# 海外サッカー文脈キーワード
OVERSEAS_CONTEXT = [
    "プレミア", "ラ・リーガ", "セリエA", "ブンデス", "リーグ・アン", "リーグアン",
    "エールディビジ", "プリメイラ", "チャンピオンズリーグ", "ヨーロッパリーグ",
    "ELC", "UCL", "UEL", "海外", "欧州", "イングランド", "スペイン", "ドイツ",
    "イタリア", "フランス", "オランダ", "ポルトガル", "ベルギー",
    # クラブ名（よく出る）
    "リヴァプール", "リバプール", "アーセナル", "チェルシー", "マンチェスター",
    "ブライトン", "トッテナム", "レアル・ソシエダ", "レアル・マドリード", "バルセロナ",
    "アトレティコ", "バイエルン", "ドルトムント", "ミラン", "ユヴェントス", "ナポリ",
    "PSG", "リヨン", "モナコ", "アヤックス", "フェイエノールト", "PSV",
    "スポルティング", "ポルト", "ベンフィカ",
]


def is_low_quality(title):
    """単なる試合記録・写真ギャラリーは除外"""
    for pat in LOW_QUALITY_PATTERNS:
        if re.search(pat, title):
            return True
    return False


def article_matches(title, desc, players):
    """フルネーム or 苗字+海外文脈 にマッチするものを採用。J-League記事は除外"""
    text = f"{title} {desc}"
    # J-League記事は除外
    if any(k in text for k in JLEAGUE_EXCLUDE):
        return []
    # 低品質タイトル（試合記録のみ等）は除外
    if is_low_quality(title):
        return []
    matched_players = []
    for p in players:
        # フルネーム一致は強マッチ
        if p["full_no_space"] in text:
            matched_players.append(p["name_ja"])
            continue
        # 苗字 + 海外文脈ワード があれば採用
        if p["last_name"] in text and any(k in text for k in OVERSEAS_CONTEXT):
            matched_players.append(p["name_ja"])
    return matched_players


def main():
    players_data = json.loads((DATA / "players.json").read_text(encoding="utf-8"))
    players = build_player_keywords(players_data)
    print(f"[INFO] 日本人選手: {len(players)} 名")

    all_items = []
    for src in SOURCES:
        print(f"[INFO] {src['name']}: 取得中...")
        xml = fetch(src["url"])
        if not xml:
            continue
        items = parse_rss(xml, src["name"])
        print(f"  → {len(items)} 件")
        all_items.extend(items)
        time.sleep(0.5)

    # 日本人選手フィルタ
    filtered = []
    for item in all_items:
        matched = article_matches(item["title"], item["description"], players)
        if matched:
            item["matched_players"] = matched
            filtered.append(item)

    # 既存ニュースを読み込み（蓄積モード）
    existing_path = DATA / "news.json"
    existing_items = []
    if existing_path.exists():
        try:
            existing_data = json.loads(existing_path.read_text(encoding="utf-8"))
            existing_items = existing_data.get("items", [])
        except Exception:
            pass

    # 既存と新規をマージ（重複排除：linkベース）
    seen = set()
    uniq = []
    for it in filtered + existing_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        uniq.append(it)

    # 新しい順にソート＋直近100件保持（過去30日分まで）
    uniq.sort(key=lambda x: x.get("published") or "", reverse=True)
    uniq = uniq[:100]
    cutoff = (datetime.now(JST) - timedelta(days=30)).isoformat()
    uniq = [it for it in uniq if (it.get("published") or "") >= cutoff or len(uniq) < 30]

    out = {
        "updated": datetime.now(JST).isoformat(),
        "sources": [s["name"] for s in SOURCES],
        "count": len(uniq),
        "items": uniq,
    }
    (DATA / "news.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] 日本人選手記事: {len(uniq)} 件保存")
    for it in uniq[:5]:
        print(f"  - [{(it.get('published') or '')[:10]}] {it['title'][:60]} ({it['source']})")


if __name__ == "__main__":
    main()
