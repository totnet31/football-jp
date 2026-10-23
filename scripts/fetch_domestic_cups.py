#!/usr/bin/env python3
"""
国内カップ戦（日本人が所属するクラブの試合だけ）を英語版 Wikipedia の大会ページから取り、
data/matches.json（日程・結果）と data/match_events.json（得点者）に足すスクリプト（2026-10-23）。

football-data.org の無料プランには国内カップ戦が無いため、EL・ECL（fetch_uefa_secondary.py）と
同じく Wikipedia の {{Football box collapsible}} を読む。数字（日時・スコア・得点者・得点時間）は
ページに書かれているものだけを使い、推測で埋めない。

取れる大会（2026-10-23 に英語版 Wikipedia で確認）
  - カラバオカップ（EFLカップ）  2026–27 EFL Cup
  - FAカップ                    2026–27 FA Cup（プレミア・チャンピオンシップのクラブは1月の3回戦から。ページに載り次第入る）
  - DFBポカール                 2026–27 DFB-Pokal
  - コパ・デル・レイ（国王杯）   2026–27 Copa del Rey
  - コッパ・イタリア             2026–27 Coppa Italia
  - KNVBベーカー                2026–27 KNVB Cup（得点者が書かれていない試合が多い）
  - ベルギーカップ               2026–27 Belgian Cup
  - クープ・ドゥ・フランス       2026–27 Coupe de France（2026-10-23 時点でページが無い。できたら入る）
取れない大会
  - タッサ・デ・ポルトゥガル（ページが表の形で、試合ごとの記録の枠が無い）
  - スコットランドの2つのカップ（日本人の所属クラブが無い）

時刻：ページの時刻は開催国の現地時刻（イングランド＝英国時間、ほか＝中央ヨーロッパ時間）。
大会ごとのタイムゾーンで夏時間・冬時間を判定して日本時間に直す。時刻が未定の試合は入れない。

取得に失敗したページの試合は、前回のデータをそのまま残す（ページ単位）。
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_uefa_secondary import (  # noqa: E402
    fetch_wikitext, extract_football_boxes, parse_box_field, parse_start_date, parse_time,
    parse_score, parse_team, strip_wiki,
)
from fetch_wiki_events import (  # noqa: E402
    parse_box_field as _ev_field, parse_goals_block, parse_minute, parse_date, build_jp_lookup, normalize_team, _ascii_fold,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))
ID_PREFIX = "CUP_"
CATEGORY = "domestic_cup"


def current_season(now=None):
    now = now or datetime.now(JST)
    y = now.year if now.month >= 7 else now.year - 1
    return f"{y}–{(y + 1) % 100:02d}"


SEASON = current_season()

# competition_id は data/competitions.json と同じ番号（api-football の大会番号にそろえてある）
CUPS = [
    {"id": 48, "short": "EFL", "page": f"{SEASON} EFL Cup", "tz": "Europe/London"},
    {"id": 45, "short": "FAC", "page": f"{SEASON} FA Cup", "tz": "Europe/London"},
    {"id": 81, "short": "DFB", "page": f"{SEASON} DFB-Pokal", "tz": "Europe/Berlin"},
    {"id": 143, "short": "CDR", "page": f"{SEASON} Copa del Rey", "tz": "Europe/Madrid"},
    {"id": 137, "short": "CIT", "page": f"{SEASON} Coppa Italia", "tz": "Europe/Rome"},
    {"id": 90, "short": "KNVB", "page": f"{SEASON} KNVB Cup", "tz": "Europe/Amsterdam"},
    {"id": 147, "short": "BEL", "page": f"{SEASON} Belgian Cup", "tz": "Europe/Brussels"},
    {"id": 66, "short": "CDF", "page": f"{SEASON} Coupe de France", "tz": "Europe/Paris", "optional": True},
]

# Wikipedia のリンク先（記事名）→ players.json の club_en。日本人が所属するクラブだけ（2026-10-23 確認）。
# ここに無いクラブも、名前を整えて club_en と完全に同じなら拾う（移籍で所属クラブが増えたとき用）。
WIKI_JP_CLUBS = {
    # イングランド
    "Aston Villa F.C.": "Aston Villa",
    "Birmingham City F.C.": "Birmingham",
    "Blackburn Rovers F.C.": "Blackburn",
    "Bolton Wanderers F.C.": "Bolton",
    "Brighton & Hove Albion F.C.": "Brighton & Hove Albion",
    "Bristol City F.C.": "Bristol City",
    "Burnley F.C.": "Burnley",
    "Coventry City F.C.": "Coventry",
    "Crystal Palace F.C.": "Crystal Palace",
    "Hull City A.F.C.": "Hull City",
    "Ipswich Town F.C.": "Ipswich Town",
    "Leeds United F.C.": "Leeds",
    "Liverpool F.C.": "Liverpool",
    "Queens Park Rangers F.C.": "Queens Park Rangers",
    "Southampton F.C.": "Southampton",
    # ドイツ
    "1. FSV Mainz 05": "Mainz 05",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "FC Bayern Munich": "Bayern München",
    "FC Schalke 04": "FC Schalke 04",
    "FC St. Pauli": "FC St. Pauli",
    "Holstein Kiel": "Holstein Kiel",
    "Karlsruher SC": "Karlsruher SC",
    "SC Freiburg": "SC Freiburg",
    "SV Darmstadt 98": "Darmstadt 98",
    "TSG 1899 Hoffenheim": "TSG Hoffenheim",
    "VfL Wolfsburg": "VfL Wolfsburg",
    # スペイン・イタリア
    "Valencia CF": "Valencia CF",
    "Real Sociedad": "Real Sociedad",
    "Cagliari Calcio": "Cagliari",
    # オランダ
    "Sparta Rotterdam": "Sparta Rotterdam",
    "AZ Alkmaar": "AZ Alkmaar",
    "PSV Eindhoven": "PSV Eindhoven",
    "Feyenoord": "Feyenoord",
    # ベルギー
    "KRC Genk": "Genk",
    "KV Kortrijk": "KV Kortrijk",
    "KVC Westerlo": "Westerlo",
    "Royal Antwerp FC": "Royal Antwerp",
    "Royale Union Saint-Gilloise": "Royale Union Saint-Gilloise",
    "Sint-Truidense VV": "Sint-Truiden",
    "Oud-Heverlee Leuven": "OH Leuven",
    # フランス
    "AS Monaco FC": "Monaco",
    "Olympique Lyonnais": "Olympique Lyonnais",
    "Lille OSC": "LOSC Lille",
    "Le Havre AC": "Le Havre",
}

# スコアが入っていても、キックオフからこの時間が経つまでは途中経過とみなす（延長・PK戦を見込んで長め）
FINISH_AFTER = timedelta(minutes=150)

ROUND_RE = re.compile(r"(round|final|play-?off|quarter|semi|section|group|leg|stage)", re.IGNORECASE)
GENERIC = {"matches", "knockout phase", "final stage", "first stage", "summary", "draw", "draw and seeding"}


def fold_norm(s):
    return _ascii_fold(normalize_team(s or ""))


# football-data.org の短い呼び名（Man United・Tottenham など）と Wikipedia の正式名をつなぐ
_SUFFIXES = ("hotspur", "united", "city", "albion", "wanderers", "rovers", "athletic", "town", "county")


def name_variants(name):
    n = fold_norm(name)
    out = [n]
    if n.startswith("manchester "):
        out.append("man " + n[len("manchester "):])
    for suf in _SUFFIXES:
        if n.endswith(" " + suf) and n.count(" ") >= 1:
            out.append(n[: -len(suf) - 1])
    out.append(n.replace("united", "utd"))
    return out


def strip_team_extra(field):
    """'[[Lincoln City F.C.|Lincoln City]] (2)' の (2)・太字を除いた上で parse_team"""
    f = re.sub(r"'''", "", field or "")
    target, display = parse_team(f)
    display = re.sub(r"\s*\(\d+\)\s*$", "", display).strip()
    target = re.sub(r"\s*\(\d+\)\s*$", "", target).strip()
    return target, display


def section_stages(wt):
    """wikitext を見出しで区切り、(本文, 段階名) を返す"""
    heads = [(m.start(), m.end(), len(m.group(1)), m.group(2).strip())
             for m in re.finditer(r"^(={2,4})\s*([^=\n]+?)\s*\1\s*$", wt, re.MULTILINE)]
    cur = {}
    out = []
    for i, (hs, he, level, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(wt)
        cur[level] = title
        for lv in list(cur):
            if lv > level:
                del cur[lv]
        parts = [cur[lv] for lv in sorted(cur) if cur[lv].lower() not in GENERIC and ROUND_RE.search(cur[lv])]
        stage = " / ".join(parts) or None
        out.append((wt[he:end], stage))
    return out


def to_jst(date, time_str, tz):
    try:
        local = datetime.fromisoformat(f"{date}T{time_str}:00").replace(tzinfo=ZoneInfo(tz))
        return local.astimezone(JST).isoformat()
    except Exception:
        return None


def main():
    matches_data = json.loads((DATA / "matches.json").read_text(encoding="utf-8"))
    matches = matches_data.get("matches", [])
    players = json.loads((DATA / "players.json").read_text(encoding="utf-8")).get("players", [])
    comps = {c["id"]: c for c in json.loads((DATA / "competitions.json").read_text(encoding="utf-8"))["competitions"]}
    events_store = json.loads((DATA / "match_events.json").read_text(encoding="utf-8")) if (DATA / "match_events.json").exists() else {"events": {}}
    events_map = events_store.setdefault("events", {})

    active = [p for p in players if not p.get("second_team") and p.get("club_en")]
    by_club_en = {}
    for p in active:
        by_club_en.setdefault(p["club_en"], []).append(p)
    club_norm = {fold_norm(c): c for c in by_club_en}

    # ほかの大会の試合から、クラブ名（英語）→（ID, 英語名, 日本語名）を作る（相手クラブの日本語名に使う）
    name_index, id_names = {}, {}
    for m in matches:
        if str(m.get("id", "")).startswith(ID_PREFIX):
            continue
        for side in ("home", "away"):
            en, ja, tid = m.get(f"{side}_en"), m.get(f"{side}_ja"), m.get(f"{side}_id")
            if not en or not ja or ja == en or ja == "未定":
                continue
            name_index.setdefault(fold_norm(en), (tid, en, ja))
            if tid is not None and m.get("_source") != "wikipedia":
                id_names[tid] = (en, ja)

    jp_full = build_jp_lookup(players, with_last=False)

    def jp_club_of(target, display):
        ce = WIKI_JP_CLUBS.get(target)
        if ce and ce in by_club_en:
            return ce
        for k in (target, display):
            ce = club_norm.get(fold_norm(k))
            if ce:
                return ce
        return None

    def team_info(target, display):
        """→ (id, 英語名, 日本語名, 日本人選手のリスト)"""
        ce = jp_club_of(target, display)
        if ce:
            ps = by_club_en[ce]
            tid = next((p.get("club_id") for p in ps if p.get("club_id")), None)
            en, ja = id_names.get(tid, (ce, ps[0].get("club_ja") or ce))
            return tid, en, ja, ps
        for k in (target, display):
            for v in name_variants(k):
                hit = name_index.get(v)
                if hit:
                    return hit[0], hit[1], hit[2], []
        return None, display, display, []

    now = datetime.now(JST)
    fetched = {}
    for cup in CUPS:
        meta = comps.get(cup["id"])
        if not meta:
            print(f"[WARN] competitions.json に id={cup['id']} が無いため飛ばします", file=sys.stderr)
            continue
        print(f"[INFO] {meta['name_ja']}: {cup['page']}")
        wt = fetch_wikitext(cup["page"], follow_redirects=False)
        if wt and re.match(r"\s*#REDIRECT", wt, re.IGNORECASE):
            wt = ""
        if not wt:
            print(f"  [SKIP] {'まだページが無い' if cup.get('optional') else '取得失敗'}ため前回データを保持")
            fetched[cup["id"]] = None
            time.sleep(1)
            continue
        got, no_time = [], 0
        for section, stage in section_stages(wt):
            for body in extract_football_boxes(section):
                t1_target, team1 = strip_team_extra(parse_box_field(body, "team1"))
                t2_target, team2 = strip_team_extra(parse_box_field(body, "team2"))
                if not team1 or not team2:
                    continue
                c1, c2 = jp_club_of(t1_target, team1), jp_club_of(t2_target, team2)
                if not (c1 or c2):
                    continue
                date_field = parse_box_field(body, "date")
                date = parse_start_date(date_field) or parse_date(strip_wiki(date_field) if "{{" not in date_field else date_field)
                time_str = parse_time(parse_box_field(body, "time"))
                if not date or not time_str:
                    no_time += 1
                    continue
                kickoff = to_jst(date, time_str, cup["tz"])
                if not kickoff:
                    continue
                score_raw = parse_box_field(body, "score")
                score = parse_score(score_raw) if score_raw else None
                if score and now < datetime.fromisoformat(kickoff) + FINISH_AFTER:
                    score = None
                h_id, h_en, h_ja, h_ps = team_info(t1_target, team1)
                a_id, a_en, a_ja, a_ps = team_info(t2_target, team2)
                jp = [{"name_ja": p["name_ja"], "position": p.get("position", ""), "side": "home"} for p in h_ps]
                jp += [{"name_ja": p["name_ja"], "position": p.get("position", ""), "side": "away"} for p in a_ps]
                mid = (f"{ID_PREFIX}{cup['short']}_{date}_"
                       f"{re.sub(r'[^a-zA-Z]', '', _ascii_fold(team1))[:6]}_{re.sub(r'[^a-zA-Z]', '', _ascii_fold(team2))[:6]}")
                m = {
                    "id": mid,
                    "competition_id": cup["id"],
                    "competition_ja": meta["name_ja"],
                    "competition_category": CATEGORY,
                    "competition_flag": meta.get("flag", ""),
                    "kickoff_jst": kickoff,
                    "status": "FINISHED" if score else "SCHEDULED",
                    "stage": stage,
                    "matchday": None,
                    "home_id": h_id, "home_ja": h_ja, "home_en": h_en,
                    "home_crest": f"https://crests.football-data.org/{h_id}.png" if h_id else None,
                    "away_id": a_id, "away_ja": a_ja, "away_en": a_en,
                    "away_crest": f"https://crests.football-data.org/{a_id}.png" if a_id else None,
                    "score": score,
                    "japanese_players": jp,
                    "broadcasters": [],
                    "_source": "wikipedia",
                    "_source_page": cup["page"],
                }
                pen = parse_score(parse_box_field(body, "penaltyscore")) if score else None
                if pen:
                    m["penalties"] = pen
                if score and re.search(r"^\s*yes", parse_box_field(body, "aet"), re.I) or "a.e.t" in (score_raw or ""):
                    m["extra_time"] = True

                # 得点者（ページに書かれている分だけ）。日本人はフルネーム→苗字（この試合の日本人の中で1人に決まるとき）で照合
                evs = []
                if score:
                    local_last = {}
                    for p in h_ps + a_ps:
                        if p.get("name_en"):
                            local_last.setdefault(_ascii_fold(p["name_en"].split()[-1]).lower(), set()).add(p["name_ja"])
                    for side, field in (("home", "goals1"), ("away", "goals2")):
                        # 得点の欄は「*」の行をまたぐので、fetch_wiki_events と同じ読み方をする
                        for entry in parse_goals_block(_ev_field(body + "\n}}", field)):
                            ja = None
                            for c in (entry.get("wiki_target") or "", entry.get("display", "")):
                                for key in (c, c.lower(), _ascii_fold(c), _ascii_fold(c).lower()):
                                    if c and key in jp_full:
                                        ja = jp_full[key]
                                        break
                                if ja:
                                    break
                            if not ja:
                                for c in (entry.get("wiki_target") or "", entry.get("display", "")):
                                    w = re.sub(r"\s*\(.*?\)", "", c).split()
                                    hit = local_last.get(_ascii_fold(w[-1]).lower()) if w else None
                                    if hit and len(hit) == 1:
                                        ja = next(iter(hit))
                                        break
                            for g in entry["goals"]:
                                minute = parse_minute(g["minute_raw"])
                                if minute is None:
                                    continue
                                evs.append({"type": "goal", "player_ja": ja or entry["display"], "player_en": entry["display"],
                                            "is_japanese": ja is not None, "minute": minute,
                                            "minute_raw": g["minute_raw"], "note": g["note"], "side": side})
                m["_events"] = evs
                got.append(m)
        n_fin = sum(1 for m in got if m["status"] == "FINISHED")
        print(f"  → 日本人所属クラブの試合 {len(got)}件（結果あり {n_fin}・日程のみ {len(got) - n_fin}）"
              + (f"・時刻未定で入れなかった試合 {no_time}件" if no_time else ""))
        fetched[cup["id"]] = got
        time.sleep(2)

    ok_ids = {cid for cid, got in fetched.items() if got is not None}
    old = {m["id"]: m for m in matches if str(m.get("id", "")).startswith(ID_PREFIX)}
    matches = [m for m in matches if not (str(m.get("id", "")).startswith(ID_PREFIX) and m.get("competition_id") in ok_ids)]
    seen = {m["id"] for m in matches}
    added, n_goal_jp = [], 0
    for cid in ok_ids:
        for m in fetched[cid]:
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            evs = m.pop("_events")
            prev = old.get(m["id"])
            if prev:
                if prev.get("highlights"):
                    m["highlights"] = prev["highlights"]
                if prev.get("status") == "FINISHED" and prev.get("score") and m["status"] != "FINISHED":
                    m["status"], m["score"] = "FINISHED", prev["score"]  # Wikipedia の更新遅れで結果を消さない
            if m["status"] == "FINISHED" and (evs or str(m["id"]) not in events_map):
                events_map[str(m["id"])] = evs
            n_goal_jp += sum(1 for e in events_map.get(str(m["id"]), []) if e.get("is_japanese"))
            added.append(m)
    matches.extend(added)
    matches.sort(key=lambda m: m.get("kickoff_jst", ""))

    from watch_source import apply_to_matches
    apply_to_matches(matches)

    matches_data["matches"] = matches
    matches_data["match_count"] = len(matches)
    matches_data["updated_domestic_cups"] = datetime.now(JST).isoformat()
    (DATA / "matches.json").write_text(json.dumps(matches_data, ensure_ascii=False, indent=2), encoding="utf-8")
    events_store["updated"] = datetime.now(JST).isoformat()
    (DATA / "match_events.json").write_text(json.dumps(events_store, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[DONE] 国内カップ戦：日本人所属クラブの試合 {len(added)}件（日本人のゴール {n_goal_jp}点）")
    for m in sorted(added, key=lambda x: x["kickoff_jst"]):
        sc = f"{m['score']['home']}-{m['score']['away']}" if m.get("score") else "vs"
        gl = [f"{e['player_ja']}{e['minute_raw']}'" for e in events_map.get(str(m["id"]), []) if e.get("is_japanese")]
        print(f"  {m['kickoff_jst'][:16]} {m['competition_ja']:<12} {m['home_ja']} {sc} {m['away_ja']}"
              + (f"  ⚽ {', '.join(gl)}" if gl else ""))


if __name__ == "__main__":
    main()
