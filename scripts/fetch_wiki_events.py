#!/usr/bin/env python3
"""
Phase 1B: Wikipediaスクレイプで日本人選手の得点を抽出
- 入力: data/players.json（67名）／data/matches.json（finished試合）／data/clubs.json
- 出力: data/match_events.json（match_id → goals[]）
- 仕組み:
  1. 各クラブの「2025–26 Club season」Wikipediaページを取得
  2. {{football box collapsible}} テンプレートを正規表現でパース
  3. goals1/goals2 から *[[player wiki|display]] {{goal|MIN}} を抽出
  4. football-dataの試合IDと date+対戦相手 で照合
  5. 日本人選手のゴールのみ保存（players.json の name_en・wiki_link で照合）
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

WIKI_API = "https://en.wikipedia.org/w/api.php"

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def load_json(name, default=None):
    p = DATA / name
    if not p.exists():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_wikitext(page_title):
    """指定ページのwikitextを取得。リダイレクト追跡。"""
    url = (f"{WIKI_API}?action=parse&page={quote(page_title)}"
           f"&prop=wikitext&format=json&formatversion=2&redirects=1")
    req = Request(url, headers={"User-Agent": "football-jp scraper / 0.1 (saito@tottot.net)"})
    try:
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            return None
        return data.get("parse", {}).get("wikitext", "")
    except (HTTPError, URLError) as e:
        print(f"  [WIKI ERROR] {page_title}: {e}", file=sys.stderr)
        return None


def candidate_pages(club_en, club_id):
    """クラブの2025-26シーズンページタイトル候補"""
    base = club_en.strip()
    cands = [
        f"2025–26 {base} season",
        f"2025–26 {base} F.C. season",
        f"2025–26 {base} FC season",
    ]
    # 既知のクラブ別エイリアス
    aliases = {
        "Bayern München": ["FC Bayern Munich", "Bayern Munich"],
        "Borussia Mönchengladbach": ["Borussia Mönchengladbach"],
        "TSG Hoffenheim": ["TSG 1899 Hoffenheim", "1899 Hoffenheim"],
        "Tottenham": ["Tottenham Hotspur"],
        "Mainz 05": ["1. FSV Mainz 05"],
        "Werder Bremen": ["SV Werder Bremen", "Werder Bremen"],
        "FC Augsburg": ["FC Augsburg"],
        "Mallorca": ["RCD Mallorca"],
        "Birmingham": ["Birmingham City"],
        "Coventry": ["Coventry City"],
        "Hull City": ["Hull City"],
        "Blackburn": ["Blackburn Rovers"],
        "Eintracht Frankfurt": ["Eintracht Frankfurt"],
        "SC Freiburg": ["SC Freiburg"],
        "VfL Wolfsburg": ["VfL Wolfsburg"],
        "FC St. Pauli": ["FC St. Pauli"],
        "Parma": ["Parma Calcio 1913"],
        "Monaco": ["AS Monaco FC", "AS Monaco"],
        "Le Havre": ["Le Havre AC"],
        "Ajax": ["AFC Ajax"],
        "NEC Nijmegen": ["NEC Nijmegen"],
        "Sparta Rotterdam": ["Sparta Rotterdam"],
        "Gil Vicente": ["Gil Vicente F.C."],
    }
    for alt in aliases.get(base, []):
        cands.extend([
            f"2025–26 {alt} season",
            f"2025–26 {alt} F.C. season",
            f"2025–26 {alt} FC season",
        ])
    seen = set()
    out = []
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def search_season_page(club_en):
    """Wikipedia 検索APIで '2025-26 {club} season' を探す"""
    q = f"2025–26 {club_en} season"
    url = (f"{WIKI_API}?action=opensearch&search={quote(q)}"
           f"&limit=5&namespace=0&format=json")
    req = Request(url, headers={"User-Agent": "football-jp/0.1"})
    try:
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        # opensearchの応答: [query, [titles], [descs], [urls]]
        if isinstance(data, list) and len(data) > 1:
            for t in data[1]:
                if "2025" in t and "season" in t.lower():
                    return t
    except (HTTPError, URLError):
        pass
    return None


def parse_date(s):
    """'16 August 2025' → 'YYYY-MM-DD'"""
    s = s.strip()
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if not m:
        return None
    day, mon_name, year = int(m.group(1)), m.group(2), int(m.group(3))
    if mon_name not in MONTH_MAP:
        return None
    return f"{year:04d}-{MONTH_MAP[mon_name]:02d}-{day:02d}"


def strip_wiki_link(s):
    """[[Real Name|Display]] → 'Display'、[[Name]] → 'Name'、その他はそのまま"""
    s = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    return s.strip()


def extract_link_target(s):
    """[[Wiki Target|...]] から 'Wiki Target' を取得"""
    m = re.search(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]", s)
    return m.group(1).strip() if m else None


def parse_box_field(box_text, field):
    """| field = ... を抽出（次の改行+パイプで開始されるフィールドまで）"""
    # 値内部に [[A|B]] の `|` が含まれるので、`\n` 直後の `|` だけを区切りとみなす
    pat = rf"^\s*\|\s*{field}\s*=(.*?)(?=\n\s*\||\n\s*\}}\}})"
    m = re.search(pat, box_text, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def parse_goals_block(text):
    """goals1/goals2 の中身から [(wiki_target_or_name, [minutes])] を抽出"""
    # 各行（'*[[Wiki|Display]] {{goal|MIN[|...]}}, {{goal|...}}'）
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        line = line[1:].strip()
        # プレーヤー名（ウィキリンク or プレーン）
        link_target = extract_link_target(line)
        display_name = None
        m = re.match(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]", line)
        if m:
            display_name = (m.group(2) or m.group(1)).strip()
            rest = line[m.end():]
        else:
            # プレーンテキスト
            mp = re.match(r"([A-Za-zÀ-ÖØ-öø-ÿĀ-ž'\.\-\s]+?)(?=\s*\{\{)", line)
            if mp:
                display_name = mp.group(1).strip()
                rest = line[mp.end():]
            else:
                continue
        # {{goal|MIN}} もしくは {{goal|MIN|pen.}} 等を抽出（複数あり）
        goals = []
        for gm in re.finditer(r"\{\{goal\s*\|\s*([^\}\|]+?)(?:\s*\|\s*([^\}]+?))?\s*\}\}", rest):
            mins_str = gm.group(1).strip()
            note = gm.group(2).strip().lower() if gm.group(2) else ""
            # 複数分の連結 (例: '2||20||31||45' は4ゴール) も考慮
            for part in mins_str.split("||"):
                part = part.strip()
                if not part:
                    continue
                goals.append({"minute_raw": part, "note": note})
        if display_name and goals:
            out.append({
                "wiki_target": link_target,
                "display": display_name,
                "goals": goals,
            })
    return out


def parse_minute(raw):
    """'45+3' → 48 / '90+1' → 91 / '35' → 35 / 'pen.' などの文字列だけは捨てる"""
    raw = raw.strip()
    m = re.match(r"(\d+)\s*\+?\s*(\d+)?", raw)
    if not m:
        return None
    base = int(m.group(1))
    extra = int(m.group(2)) if m.group(2) else 0
    return base + extra


def parse_match_boxes(wikitext):
    """{{football box collapsible}} 群を抽出。リスト返却"""
    boxes = re.findall(r"\{\{[Ff]ootball box collapsible(.*?)\n\}\}", wikitext, re.DOTALL)
    out = []
    for b in boxes:
        date_raw = parse_box_field(b, "date")
        date = parse_date(date_raw) if date_raw else None
        if not date:
            continue
        team1 = strip_wiki_link(parse_box_field(b, "team1"))
        team2 = strip_wiki_link(parse_box_field(b, "team2"))
        score = parse_box_field(b, "score")
        round_ = parse_box_field(b, "round")
        goals1_text = parse_box_field(b, "goals1")
        goals2_text = parse_box_field(b, "goals2")
        out.append({
            "date": date,
            "team1": team1,
            "team2": team2,
            "score": score,
            "round": round_,
            "goals1": parse_goals_block(goals1_text),
            "goals2": parse_goals_block(goals2_text),
        })
    return out


def normalize_team(name):
    if not name:
        return ""
    s = re.sub(r"\b(F\.?C\.?|CF|SC|AC|FK|AS|BK|RC|AFC|CFC|VfL|VfB|FSV|TSG|Borussia|VV|RKC)\b",
               "", name, flags=re.IGNORECASE)
    s = re.sub(r"\W+", " ", s).strip().lower()
    return s


def build_jp_lookup(players):
    """name_en + wiki_target_guess → name_ja のマップ"""
    out = {}
    for p in players:
        nen = p.get("name_en")
        nja = p.get("name_ja")
        if not (nen and nja):
            continue
        # 完全一致用：苗字（最後の単語）も登録
        out[nen.lower()] = nja
        last = nen.split()[-1].lower() if nen else ""
        if last:
            out.setdefault(last, nja)
        # wiki targetの推測 (e.g., "Kaoru Mitoma" → "Kaoru Mitoma")
        out.setdefault(nen, nja)
    return out


def find_match(jp_match, wiki_box):
    """jp_match と wiki_box の date+対戦相手 を比較"""
    if jp_match["kickoff_jst"][:10] != wiki_box["date"]:
        # 時差で1日ズレるケースがあるので±1日まで許容
        try:
            jd = datetime.fromisoformat(jp_match["kickoff_jst"]).date()
            wd = datetime.strptime(wiki_box["date"], "%Y-%m-%d").date()
            if abs((jd - wd).days) > 1:
                return False
        except Exception:
            return False
    h = normalize_team(jp_match.get("home_en"))
    a = normalize_team(jp_match.get("away_en"))
    t1 = normalize_team(wiki_box["team1"])
    t2 = normalize_team(wiki_box["team2"])
    if (h and t1 and (h in t1 or t1 in h) and a and t2 and (a in t2 or t2 in a)):
        return True
    if (h and t2 and (h in t2 or t2 in h) and a and t1 and (a in t1 or t1 in a)):
        return True
    return False


def main():
    matches = load_json("matches.json").get("matches", [])
    players = load_json("players.json").get("players", [])
    events_store = load_json("match_events.json", default={
        "updated": "",
        "wikipedia_pages": {},
        "events": {},
    })
    pages_cache = events_store.setdefault("wikipedia_pages", {})
    events_map = events_store.setdefault("events", {})

    jp_lookup = build_jp_lookup(players)
    print(f"[INFO] 日本人選手 {len([p for p in players if p.get('name_en')])} 名 ロード")

    # 対象クラブを抽出（japanese_players が含まれる finished 試合のクラブ）
    finished_jp = [m for m in matches
                   if m.get("status") == "FINISHED" and m.get("japanese_players")]
    print(f"[INFO] 対象 FINISHED 試合: {len(finished_jp)}件")

    # クラブ別 → このクラブのシーズンページから日本人ゴール抽出
    by_club = {}
    for p in players:
        cid = p.get("club_id")
        cen = p.get("club_en")
        if not (cid and cen):
            continue
        by_club.setdefault(cid, {"name_en": cen, "players": []})
        by_club[cid]["players"].append(p)
    print(f"[INFO] 対象クラブ: {len(by_club)}")

    boxes_per_club = {}
    for cid, info in by_club.items():
        cen = info["name_en"]
        # キャッシュチェック
        if str(cid) in pages_cache and pages_cache[str(cid)].get("boxes"):
            boxes = pages_cache[str(cid)]["boxes"]
            print(f"  [CACHE] {cen}: {len(boxes)}試合")
            boxes_per_club[cid] = boxes
            continue
        # ページタイトル候補を順に試す
        wt = None
        used_title = None
        for title in candidate_pages(cen, cid):
            wt = fetch_wikitext(title)
            if wt and "football box collapsible" in wt.lower():
                used_title = title
                break
            time.sleep(0.4)
        # フォールバック：opensearch
        if not used_title:
            found = search_season_page(cen)
            if found:
                wt2 = fetch_wikitext(found)
                if wt2 and "football box collapsible" in wt2.lower():
                    wt = wt2
                    used_title = found
        if not wt or not used_title:
            print(f"  [SKIP] {cen}: シーズンページ見つからず")
            pages_cache[str(cid)] = {"title": None, "boxes": []}
            continue
        boxes = parse_match_boxes(wt)
        pages_cache[str(cid)] = {"title": used_title, "boxes": boxes}
        boxes_per_club[cid] = boxes
        print(f"  [WIKI] {cen} ({used_title}): {len(boxes)}試合")
        time.sleep(0.5)

    # 各 finished_jp 試合に対して、関連クラブの boxes から日本人ゴール抽出
    found = 0
    for m in finished_jp:
        mid = str(m["id"])
        if mid in events_map:
            continue  # キャッシュ済み
        # この試合のJP選手のクラブ群
        jp_clubs = set()
        for p in players:
            for jp in m.get("japanese_players", []):
                if p.get("name_ja") == jp.get("name_ja") and p.get("club_id"):
                    jp_clubs.add(p["club_id"])
        # それらクラブのboxesから日付+対戦相手で照合
        events = []
        for cid in jp_clubs:
            for box in boxes_per_club.get(cid, []):
                if not find_match(m, box):
                    continue
                # team1 = home相当 と仮定
                h_norm = normalize_team(m.get("home_en"))
                t1_norm = normalize_team(box["team1"])
                home_is_team1 = (h_norm in t1_norm or t1_norm in h_norm) if (h_norm and t1_norm) else True
                # 各 goals ブロックから日本人選手をフィルタ
                for side, gblock in [
                    ("home" if home_is_team1 else "away", box["goals1"]),
                    ("away" if home_is_team1 else "home", box["goals2"]),
                ]:
                    for entry in gblock:
                        # 名前マッチ（display, wiki_target, last）
                        candidates = [entry.get("display", ""), entry.get("wiki_target") or ""]
                        ja = None
                        for c in candidates:
                            if not c:
                                continue
                            if c.lower() in jp_lookup:
                                ja = jp_lookup[c.lower()]
                                break
                            if c in jp_lookup:
                                ja = jp_lookup[c]
                                break
                            last = c.split()[-1].lower() if c else ""
                            if last and last in jp_lookup:
                                ja = jp_lookup[last]
                                break
                        if not ja:
                            continue
                        for g in entry["goals"]:
                            minute = parse_minute(g["minute_raw"])
                            if minute is None:
                                continue
                            events.append({
                                "type": "goal",
                                "player_ja": ja,
                                "player_en": entry["display"],
                                "minute": minute,
                                "minute_raw": g["minute_raw"],
                                "note": g["note"],
                                "side": side,
                            })
                break  # マッチ1試合のみ
        events_map[mid] = events
        if events:
            found += 1
            names = ", ".join(f"{e['player_ja']}{e['minute']}'" for e in events)
            print(f"  ⚽ {m['kickoff_jst'][:10]} {m['home_ja']} vs {m['away_ja']} → {names}")

    events_store["updated"] = datetime.now(JST).isoformat()
    save_json("match_events.json", events_store)
    print(f"\n[DONE] 日本人ゴール検出: {found}試合 / 累計記録: {len(events_map)}試合")


if __name__ == "__main__":
    main()
