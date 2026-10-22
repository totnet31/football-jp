#!/usr/bin/env python3
"""
ブンデスリーガ2部（2. Bundesliga）の今季の日程と結果を OpenLigaDB から取り、
data/matches.json に足すスクリプト（2026-10-22）。

football-data.org の無料枠に2部が無いため、別の取り先を使う。
  取り先：https://api.openligadb.de/getmatchdata/bl2/<シーズン開始年>（鍵なし・無料）
  データの決まり：ODbL 1.0。サイトでは「Daten von OpenLigaDB（www.openligadb.de）、ODbL 1.0」を
                 フッターに出す（選手・リーグ・トップ／結果／カレンダー）。
  使い方の決まり（https://www.openligadb.de/nutzungsbedingungen 2026-08-28 版）：
    - 試合中でなければ1日に数回で足りる → 1日3回の自動更新で、1回につき1リクエストだけ
    - 名前と連絡先の入った User-Agent を付ける
    - 429・5xx は間をあけて（倍々に）やり直す。すぐに連打しない
    - 落ちていることがある前提で、前回のデータを残す
    - チームのロゴの URL（teamIconUrl）は他所の画像なので使わない

入れる試合：日本人選手（data/players.json の所属クラブ名）が出るクラブの試合だけ。
  - id は "BL2_<OpenLigaDB の matchID>"（football-data.org の数字の id とぶつからない）
  - 日本人選手の名前は、選手のクラブ名（club_ja / club_en）で付ける。
    ブンデス2部のクラブには football-data.org の番号が無いので、選手ページは名前で次の試合を選ぶ
    （generate_player_pages.py の get_next_watch_matches）
  - 配信先は watch_source.apply_to_matches（league_guides.json に欄が無い＝「確認中」）

失敗したとき（OpenLigaDB が落ちている・形が変わった・0件）は、matches.json を書き換えずに終わる
（前回の2部の試合がそのまま残る）。終わりのコードは常に 0 で、自動更新全体を止めない。

実行: python3 scripts/fetch_openligadb.py
"""

import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = ZoneInfo("Asia/Tokyo")

API_BASE = "https://api.openligadb.de"
LEAGUE_SHORTCUT = "bl2"
ID_PREFIX = "BL2_"
SOURCE_TAG = "openligadb"
USER_AGENT = "football-jp/1.0 (+https://football-jp.com/; https://football-jp.com/contact.html)"
MAX_TRIES = 4          # 1回目＋やり直し3回
BACKOFF_FIRST = 10     # 秒。10 → 20 → 40
MIN_MATCHES = 100      # 1シーズン306試合。これより少なければ形がおかしいとみなして使わない

COMP = {
    "id": 79,
    "name_ja": "ブンデスリーガ2部",
    "flag": "🇩🇪",
    "category": "league",
}

# OpenLigaDB のチーム名 → (日本語, 英語)。日本語は既存の表記（players.json・clubs.json・fetch_player_info.py）にそろえる
TEAM_NAMES = {
    "VfL Wolfsburg": ("ヴォルフスブルク", "VfL Wolfsburg"),
    "FC St. Pauli": ("ザンクト・パウリ", "FC St. Pauli"),
    "Holstein Kiel": ("ホルシュタイン・キール", "Holstein Kiel"),
    "Karlsruher SC": ("カールスルーエ", "Karlsruher SC"),
    "SV Darmstadt 98": ("ダルムシュタット", "Darmstadt 98"),
    "1. FC Heidenheim 1846": ("ハイデンハイム", "1. FC Heidenheim"),
    "VfL Bochum": ("ボーフム", "VfL Bochum"),
    "Hannover 96": ("ハノーファー96", "Hannover 96"),
    "DSC Arminia Bielefeld": ("ビーレフェルト", "Arminia Bielefeld"),
    "Hertha BSC": ("ヘルタ・ベルリン", "Hertha BSC"),
    "1. FC Kaiserslautern": ("カイザースラウテルン", "1. FC Kaiserslautern"),
    "1. FC Magdeburg": ("マクデブルク", "1. FC Magdeburg"),
    "1. FC Nürnberg": ("ニュルンベルク", "1. FC Nürnberg"),
    "Dynamo Dresden": ("ディナモ・ドレスデン", "Dynamo Dresden"),
    "Eintracht Braunschweig": ("ブラウンシュヴァイク", "Eintracht Braunschweig"),
    "Energie Cottbus": ("コットブス", "Energie Cottbus"),
    "SpVgg Greuther Fürth": ("グロイター・フュルト", "Greuther Fürth"),
    "VfL Osnabrück": ("オスナブリュック", "VfL Osnabrück"),
    # 入れ替わりで来そうなクラブ
    "Fortuna Düsseldorf": ("デュッセルドルフ", "Fortuna Düsseldorf"),
    "FC Schalke 04": ("シャルケ04", "FC Schalke 04"),
    "Hamburger SV": ("ハンブルガーSV", "Hamburger SV"),
    "1. FC Köln": ("ケルン", "1. FC Köln"),
    "SC Paderborn 07": ("パーダーボルン", "SC Paderborn 07"),
    "SSV Ulm 1846": ("ウルム", "SSV Ulm 1846"),
    "SSV Jahn Regensburg": ("レーゲンスブルク", "Jahn Regensburg"),
    "SV Elversberg": ("エルファースベルク", "SV Elversberg"),
    "Preußen Münster": ("プロイセン・ミュンスター", "Preußen Münster"),
}

# 選手の club_en と OpenLigaDB のチーム名の言い方が違うもの
CLUB_EN_ALIASES = {
    "Darmstadt 98": "SV Darmstadt 98",
    "Arminia Bielefeld": "DSC Arminia Bielefeld",
    "1. FC Heidenheim": "1. FC Heidenheim 1846",
    "Greuther Fürth": "SpVgg Greuther Fürth",
}


def season_start_year(now: datetime) -> int:
    """7月から新しいシーズン（2026-10 → 2026 = 2026/27）"""
    return now.year if now.month >= 7 else now.year - 1


def fetch_json(url: str):
    """取れなければ None。429・5xx・通信の失敗は 10→20→40 秒あけてやり直す。"""
    wait = BACKOFF_FIRST
    for i in range(1, MAX_TRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            retry = e.code == 429 or e.code >= 500
            print(f"[WARN] HTTP {e.code}（{i}/{MAX_TRIES}回目）{url}", file=sys.stderr)
            if not retry:
                return None
        except Exception as e:
            print(f"[WARN] 取得失敗（{i}/{MAX_TRIES}回目）{url}: {e}", file=sys.stderr)
        if i < MAX_TRIES:
            time.sleep(wait + random.uniform(0, 3))
            wait *= 2
    return None


def team_names(team: dict) -> tuple:
    name = (team or {}).get("teamName") or ""
    ja, en = TEAM_NAMES.get(name, (None, None))
    if not ja:
        print(f"[WARN] 日本語名が無いチーム: {name}（英語名のまま出す。TEAM_NAMES に足してください）", file=sys.stderr)
        ja, en = name or "未定", name
    return name, ja, en


def build_player_index(players: list) -> dict:
    """OpenLigaDB のチーム名 / 日本語のクラブ名 → 選手の一覧（セカンドチームの選手は除く）"""
    by_key = {}
    for p in players:
        if p.get("second_team"):
            continue
        keys = set()
        if p.get("club_ja"):
            keys.add(("ja", p["club_ja"]))
        if p.get("club_en"):
            keys.add(("en", p["club_en"]))
            keys.add(("en", CLUB_EN_ALIASES.get(p["club_en"], p["club_en"])))
        for k in keys:
            by_key.setdefault(k, []).append(p)
    return by_key


def jp_players_for(oldb_name: str, ja: str, en: str, idx: dict) -> list:
    seen, out = set(), []
    for k in (("en", oldb_name), ("en", en), ("ja", ja)):
        for p in idx.get(k, []):
            if p["name_ja"] in seen:
                continue
            seen.add(p["name_ja"])
            out.append(p)
    return out


def final_score(m: dict):
    """「Endergebnis」（resultTypeID 2）。無ければ resultOrderID がいちばん大きいもの。"""
    res = m.get("matchResults") or []
    if not res:
        return None
    end = [r for r in res if r.get("resultTypeID") == 2] or sorted(res, key=lambda r: r.get("resultOrderID") or 0)[-1:]
    r = end[0]
    if r.get("pointsTeam1") is None or r.get("pointsTeam2") is None:
        return None
    return {"home": r["pointsTeam1"], "away": r["pointsTeam2"]}


def to_jst(utc_str: str) -> str:
    if utc_str.endswith("Z"):
        utc_str = utc_str[:-1] + "+00:00"
    return datetime.fromisoformat(utc_str).astimezone(JST).isoformat()


def transform(m: dict, idx: dict):
    if not m.get("matchDateTimeUTC") or not m.get("matchID"):
        return None
    h_name, home_ja, home_en = team_names(m.get("team1"))
    a_name, away_ja, away_en = team_names(m.get("team2"))
    jp = []
    for side, n, ja, en in (("home", h_name, home_ja, home_en), ("away", a_name, away_ja, away_en)):
        for p in jp_players_for(n, ja, en, idx):
            jp.append({"name_ja": p["name_ja"], "position": p.get("position", ""), "side": side})
    if not jp:
        return None  # 日本人選手のいない試合は入れない
    finished = bool(m.get("matchIsFinished"))
    score = final_score(m) if finished else None
    group = m.get("group") or {}
    return {
        "id": f"{ID_PREFIX}{m['matchID']}",
        "competition_id": COMP["id"],
        "competition_ja": COMP["name_ja"],
        "competition_category": COMP["category"],
        "competition_flag": COMP["flag"],
        "kickoff_jst": to_jst(m["matchDateTimeUTC"]),
        "status": "FINISHED" if (finished and score) else "SCHEDULED",
        "stage": "REGULAR_SEASON",
        "matchday": group.get("groupOrderID"),
        "home_id": None,
        "home_ja": home_ja,
        "home_en": home_en,
        "home_crest": None,  # teamIconUrl は他所の画像なので使わない（OpenLigaDB の決まり）
        "away_id": None,
        "away_ja": away_ja,
        "away_en": away_en,
        "away_crest": None,
        "score": score,
        "japanese_players": jp,
        "broadcasters": [],  # 下で watch_source.apply_to_matches が入れる（欄が無い＝確認中）
        "_source": SOURCE_TAG,
    }


def main() -> int:
    now = datetime.now(JST)
    season = season_start_year(now)
    url = f"{API_BASE}/getmatchdata/{LEAGUE_SHORTCUT}/{season}"

    out_path = DATA / "matches.json"
    try:
        matches_data = json.loads(out_path.read_text(encoding="utf-8"))
        players = json.loads((DATA / "players.json").read_text(encoding="utf-8")).get("players", [])
    except Exception as e:
        print(f"[WARN] matches.json / players.json を読めないため何もしません: {e}", file=sys.stderr)
        return 0

    time.sleep(random.uniform(0, 5))  # ちょうどの時刻に集中させない（OpenLigaDB のお願い）
    print(f"[INFO] ブンデスリーガ2部 {season}/{str(season + 1)[2:]} を取得: {url}")
    raw = fetch_json(url)
    if not isinstance(raw, list) or len(raw) < MIN_MATCHES:
        n = len(raw) if isinstance(raw, list) else "取得失敗"
        print(f"[WARN] OpenLigaDB から使えるデータが取れませんでした（{n}）。前回のデータを残します。", file=sys.stderr)
        return 0
    if any((x.get("leagueShortcut") or "").lower() != LEAGUE_SHORTCUT for x in raw[:20]):
        print("[WARN] 返ってきたデータの大会が bl2 ではありません。前回のデータを残します。", file=sys.stderr)
        return 0

    idx = build_player_index(players)
    new = []
    for m in raw:
        t = transform(m, idx)
        if t:
            new.append(t)
    n_fin = sum(1 for x in new if x["status"] == "FINISHED")
    print(f"[INFO] シーズン {len(raw)}試合のうち、日本人選手のいるクラブの試合 {len(new)}件（結果あり {n_fin}件 / 日程のみ {len(new) - n_fin}件）")
    if not new:
        print("[WARN] 日本人選手のいる試合が0件。前回のデータを残します。", file=sys.stderr)
        return 0

    matches = matches_data.get("matches", [])
    is_ours = lambda m: isinstance(m.get("id"), str) and m["id"].startswith(ID_PREFIX)
    old_by_id = {m["id"]: m for m in matches if is_ours(m)}
    kept = [m for m in matches if not is_ours(m)]
    for m in new:
        old = old_by_id.get(m["id"])
        if not old:
            continue
        if old.get("highlights"):
            m["highlights"] = old["highlights"]
        # 一度入った結果が、取り先の都合で消えたときは前回の結果を残す
        if old.get("status") == "FINISHED" and old.get("score") and m["status"] != "FINISHED":
            print(f"  [PROTECT] {m['id']} 前回の結果を残します")
            m["status"], m["score"] = "FINISHED", old["score"]

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from utils import fix_finished_status
    from watch_source import apply_to_matches
    fix_finished_status(new)
    apply_to_matches(new)

    all_matches = kept + new
    all_matches.sort(key=lambda m: m.get("kickoff_jst", ""))
    matches_data["matches"] = all_matches
    matches_data["match_count"] = len(all_matches)
    matches_data["updated_openligadb"] = now.isoformat()
    out_path.write_text(json.dumps(matches_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] ブンデスリーガ2部 {len(new)}試合を入れました（前回 {len(old_by_id)}件と入れ替え）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 思わぬ失敗でも自動更新全体は止めない
        print(f"[WARN] fetch_openligadb.py が途中で止まりました。前回のデータを残します: {e}", file=sys.stderr)
        sys.exit(0)
