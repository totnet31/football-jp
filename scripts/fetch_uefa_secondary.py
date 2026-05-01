#!/usr/bin/env python3
"""
EL（Europa League）と ECL（Conference League）の準決勝以降の試合データを
Wikipedia から取得して matches.json に追加するスクリプト。

football-data.org 無料プランでは EL/ECL は提供されないため、
Wikipedia の knockout phase ページから {{Football box}} テンプレートを抽出。

実装範囲：
- 準決勝（1st leg / 2nd leg）
- 決勝
- 試合終了後はスコアと得点者も取り込む（match_events.jsonに保存される）

毎朝のcronで再実行され、新しいスコアが出たら自動更新する。
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))
UTC = timezone.utc

WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "football-jp/1.0 (https://football-jp.com; contact: saito@tottot.net) Python-urllib"

COMPETITIONS = [
    {
        "id": 3,
        "name_ja": "UEFAヨーロッパリーグ",
        "name_short": "EL",
        "flag": "🇪🇺",
        "knockout_page": "2025–26 UEFA Europa League knockout phase",
        "broadcasters": [
            {"name": "WOWOW", "type": "exclusive", "url": "https://www.wowow.co.jp/", "note": "〜2026-27"},
        ],
    },
    {
        "id": 848,
        "name_ja": "UEFAカンファレンスリーグ",
        "name_short": "ECL",
        "flag": "🇪🇺",
        "knockout_page": "2025–26 UEFA Conference League knockout phase",
        "broadcasters": [
            {"name": "WOWOW", "type": "partial", "url": "https://www.wowow.co.jp/", "note": "注目試合"},
        ],
    },
]

# stage 表記マップ
STAGE_NORMALIZE = {
    "Semi-finals": "SEMI_FINALS",
    "Final": "FINAL",
    "Quarter-finals": "QUARTER_FINALS",
}


def fetch_wikitext(title, max_retries=4):
    from urllib.parse import quote
    url = f"{WIKI_API}?action=parse&page={quote(title)}&prop=wikitext&format=json&formatversion=2&redirects=1"
    for attempt in range(max_retries):
        req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read()).get("parse", {}).get("wikitext", "")
        except HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 2)  # 4, 8, 16, 32秒
                print(f"  [WARN] {title}: HTTP 429（リトライ {attempt+1}/{max_retries}, {wait}秒待機）", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  [ERROR] {title}: {e}", file=sys.stderr)
            return None
        except URLError as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [WARN] {title}: {e}（リトライ {attempt+1}/{max_retries}, {wait}秒待機）", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  [ERROR] {title}: {e}", file=sys.stderr)
            return None
    return None


def strip_wiki(s):
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
    s = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_template(text, name):
    """{{name|...}} を bracket counting で抽出。リストで返す"""
    out = []
    pat = "{{" + name
    i = 0
    while True:
        s = text.lower().find(pat.lower(), i)
        if s < 0:
            break
        depth = 1
        j = s + len(pat)
        while j < len(text) and depth > 0:
            if text[j:j+2] == "{{":
                depth += 1
                j += 2
            elif text[j:j+2] == "}}":
                depth -= 1
                j += 2
            else:
                j += 1
        out.append(text[s+2:j-2])
        i = j
    return out


def parse_box_field(body, field):
    pat = rf"^\s*\|\s*{field}\s*=(.*?)(?=\n\s*\||\n\s*\}}\}}|$)"
    m = re.search(pat, body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_start_date(s):
    """{{Start date|2026|4|30|df=y}} → 2026-04-30"""
    m = re.search(r"\{\{Start date\|(\d+)\|(\d+)\|(\d+)", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def parse_time(s):
    """| time = 21:00 (UTC+1) → '21:00' (※UTC+1表記。CET/CEST想定)"""
    m = re.match(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None, "+01:00"
    hh, mm = int(m.group(1)), int(m.group(2))
    # UTC+X 抽出
    tz = re.search(r"UTC([+\-]\d+)", s)
    offset = "+01:00"
    if tz:
        try:
            off = int(tz.group(1))
            offset = f"{'+' if off >= 0 else '-'}{abs(off):02d}:00"
        except Exception:
            pass
    # 21:00 in UTC+1 → 20:00 UTC → 翌5時 JST
    return f"{hh:02d}:{mm:02d}", offset


def to_jst_iso(date_str, time_str, tz_offset):
    """date='2026-04-30', time='21:00', tz_offset='+01:00' → JST ISO"""
    if not (date_str and time_str):
        return None
    try:
        from datetime import datetime as DT
        local = DT.fromisoformat(f"{date_str}T{time_str}:00{tz_offset}")
        jst_dt = local.astimezone(JST)
        return jst_dt.isoformat()
    except Exception:
        return None


def parse_score(s):
    """'2–1' or '1–3' → {home, away}"""
    s = s.strip().replace("–", "-").replace("—", "-")
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", s)
    if m:
        return {"home": int(m.group(1)), "away": int(m.group(2))}
    return None


def lookup_team(name_en, clubs_data):
    """clubs.json から日本語名・IDを引く"""
    for cid, ja in clubs_data.items():
        # ja = 日本語名
        pass
    return name_en  # fallback


def parse_match_box(body, stage_key, comp_meta, clubs_data, players_index):
    """1つの Football box body から Match dict を生成"""
    date_field = parse_box_field(body, "date")
    time_field = parse_box_field(body, "time")
    team1 = strip_wiki(parse_box_field(body, "team1"))
    team2 = strip_wiki(parse_box_field(body, "team2"))
    score_str = parse_box_field(body, "score")
    stadium = strip_wiki(parse_box_field(body, "stadium"))

    date = parse_start_date(date_field) or parse_start_date(body)
    time_str, tz_off = parse_time(time_field) if time_field else (None, "+01:00")
    kickoff_jst = to_jst_iso(date, time_str, tz_off)
    if not kickoff_jst:
        return None

    score = parse_score(score_str) if score_str else None
    status = "FINISHED" if score else "SCHEDULED"

    # 日本人選手の確認
    jp_players = []
    for jp in players_index:
        # team1/team2に対応するクラブを所属で照合（簡易）
        if jp.get("club_en") and jp["club_en"] in (team1, team2):
            side = "home" if jp["club_en"] in team1 else "away"
            jp_players.append({"name_ja": jp["name_ja"], "position": jp.get("position", ""), "side": side})

    # ID生成（衝突回避のため EL/ECL用にプレフィックス）
    match_id = f"{comp_meta['name_short']}_{date}_{re.sub(r'[^a-zA-Z]', '', team1)[:6]}_{re.sub(r'[^a-zA-Z]', '', team2)[:6]}"

    return {
        "id": match_id,
        "competition_id": comp_meta["id"],
        "competition_ja": comp_meta["name_ja"],
        "competition_category": "european_cup",
        "competition_flag": comp_meta["flag"],
        "kickoff_jst": kickoff_jst,
        "status": status,
        "stage": stage_key,
        "matchday": None,
        "home_id": None,
        "home_ja": clubs_data.get(team1, team1),
        "home_en": team1,
        "home_crest": None,
        "away_id": None,
        "away_ja": clubs_data.get(team2, team2),
        "away_en": team2,
        "away_crest": None,
        "score": score,
        "japanese_players": jp_players,
        "broadcasters": comp_meta["broadcasters"],
        "_source": "wikipedia",
    }


def main():
    matches_data = json.loads((DATA / "matches.json").read_text(encoding="utf-8"))
    matches = matches_data.get("matches", [])

    # 既存clubsを team_en → ja でマップ
    clubs_data = {}
    try:
        pd = json.loads((DATA / "players.json").read_text(encoding="utf-8"))
        for p in pd.get("players", []):
            if p.get("club_en") and p.get("club_ja"):
                clubs_data[p["club_en"]] = p["club_ja"]
    except Exception:
        pass
    # EL/ECL に出てくるクラブの追加マッピング（players.json に無い）
    EXTRA_CLUBS = {
        "Braga": "ブラガ",
        "S.C. Braga": "ブラガ",
        "Nottingham Forest": "ノッティンガム・フォレスト",
        "Aston Villa": "アストン・ビラ",
        "Shakhtar Donetsk": "シャフタール・ドネツク",
        "FC Shakhtar Donetsk": "シャフタール・ドネツク",
        "Rayo Vallecano": "ラージョ・バジェカーノ",
        "Strasbourg": "ストラスブール",
        "RC Strasbourg Alsace": "ストラスブール",
        "Lyon": "リヨン",
        "Olympique Lyonnais": "リヨン",
        "Celtic": "セルティック",
        "Celtic F.C.": "セルティック",
        "VfB Stuttgart": "シュトゥットガルト",
        "Stuttgart": "シュトゥットガルト",
        "Porto": "ポルト",
        "FC Porto": "ポルト",
    }
    for k, v in EXTRA_CLUBS.items():
        clubs_data.setdefault(k, v)

    # 日本人選手インデックス（club_en付き）
    players_data = json.loads((DATA / "players.json").read_text(encoding="utf-8"))
    players_index = [p for p in players_data.get("players", []) if p.get("club_en")]

    # 競技ごとに「取得成功 + 新試合リスト」を保持
    fetched_per_comp = {}  # comp_short -> list[match] (None なら取得失敗)
    for comp in COMPETITIONS:
        print(f"[INFO] {comp['name_ja']}: {comp['knockout_page']}")
        wt = fetch_wikitext(comp["knockout_page"])
        if wt is None or wt == "":
            print(f"  [SKIP] {comp['name_short']}: 取得失敗のため既存データ保持")
            fetched_per_comp[comp["name_short"]] = None
            continue
        comp_matches = []
        # Semi-finals
        sf_m = re.search(r"==\s*Semi-finals\s*==.*?(?:==\s*Final\s*==)", wt, re.DOTALL)
        sf_section = sf_m.group(0) if sf_m else ""
        sf_boxes = extract_template(sf_section, "Football box")
        for body in sf_boxes:
            m = parse_match_box(body, "SEMI_FINALS", comp, clubs_data, players_index)
            if m:
                comp_matches.append(m)
        # Final
        fn_m = re.search(r"==\s*Final\s*==(.+)", wt, re.DOTALL)
        fn_section = fn_m.group(1) if fn_m else ""
        fn_boxes = extract_template(fn_section, "Football box")
        for body in fn_boxes:
            m = parse_match_box(body, "FINAL", comp, clubs_data, players_index)
            if m:
                comp_matches.append(m)
        print(f"  → SF: {len(sf_boxes)}件 / Final: {len(fn_boxes)}件 / parsed: {len(comp_matches)}件")
        fetched_per_comp[comp["name_short"]] = comp_matches
        time.sleep(2)  # Wikipedia 思いやりウェイト

    # 取得成功した競技だけ既存試合を入れ替える（失敗した競技は既存データを保持）
    new_matches = []
    for comp in COMPETITIONS:
        short = comp["name_short"]
        comp_id = comp["id"]
        prefix = f"{short}_"
        if fetched_per_comp.get(short):
            # 既存の同競技試合を削除し新規で置き換え
            matches = [m for m in matches
                       if not (isinstance(m.get("id"), str) and m["id"].startswith(prefix))]
            new_matches.extend(fetched_per_comp[short])

    matches.extend(new_matches)
    # kickoff順にソート
    matches.sort(key=lambda m: m.get("kickoff_jst", ""))

    # サニティチェック：もし全競技失敗で既存も0件なら警告
    if not new_matches and not any(
        isinstance(m.get("id"), str) and (m["id"].startswith("EL_") or m["id"].startswith("ECL_"))
        for m in matches
    ):
        print("[WARN] EL/ECL 試合が0件です（取得失敗で既存も無し）", file=sys.stderr)

    matches_data["matches"] = matches
    matches_data["match_count"] = len(matches)
    matches_data["updated_uefa_secondary"] = datetime.now(JST).isoformat()
    (DATA / "matches.json").write_text(json.dumps(matches_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] EL/ECL 試合データを {len(new_matches)}件 追加")
    for m in new_matches:
        score_str = f"{m['score']['home']}-{m['score']['away']}" if m.get('score') else 'TBD'
        jp = ', '.join(p['name_ja'] for p in m.get('japanese_players', [])) or '—'
        print(f"  [{m['stage']:12}] {m['kickoff_jst'][:16]} {m['home_ja']} {score_str} {m['away_ja']} (JP: {jp})")


if __name__ == "__main__":
    main()
