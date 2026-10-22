#!/usr/bin/env python3
"""
EL（Europa League）と ECL（Conference League）の試合データを
Wikipedia から取得して matches.json に追加するスクリプト。

football-data.org 無料プランでは EL/ECL は提供されないため、
Wikipedia の league phase / knockout phase ページから Football box を抽出
（{{Football box ...}} と {{#invoke:Football box|main ...}} の両方の書き方に対応）。

実装範囲：
- EL 2026-27：リーグフェーズ（第1〜8節）＋ノックアウト（ページができ次第・全ラウンド）
- ECL 2026-27：リーグフェーズ（第1〜6節）＋ノックアウト（ページができ次第・全ラウンド）
- EL/ECL 2025-26：準決勝・決勝（従来どおり）
- 試合終了後はスコアも取り込む

時刻は Wikipedia の決まり（UEFA 発表の中央ヨーロッパ時間＝CET/CEST。現地時刻は括弧書き）
に合わせ、Europe/Paris の夏時間・冬時間で日本時間に直す。

1日3回（7時・12時・18時 JST）の GitHub Actions（fetch.yml）で再実行され、新しいスコアが出たら自動更新する。
取得に失敗したページの試合は、前回のデータをそのまま残す（ページ単位）。
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))
UTC = timezone.utc

WIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "football-jp/1.0 (https://football-jp.com; contact: saito@tottot.net) Python-urllib"

WOWOW_EL = {"name": "WOWOW", "type": "exclusive", "url": "https://droog.tokyo/link.php?i=phejoijtz4o2&m=mhotmxg90s1l", "note": "〜2026-27"}

# sources：取り込むページ。stages=None なら全セクション、リストならその stage だけ。
#   optional=True：ページがまだ無くてもよい（ノックアウトは抽選後にできる）
COMPETITIONS = [
    {
        "id": 3,
        "name_ja": "UEFAヨーロッパリーグ",
        "name_short": "EL",
        "flag": "🇪🇺",
        "sources": [
            {"page": "2025–26 UEFA Europa League knockout phase", "stages": ["SEMI_FINALS", "FINAL"], "legacy": True},
            {"page": "2026–27 UEFA Europa League league phase", "stages": None},
            {"page": "2026–27 UEFA Europa League knockout phase", "stages": None, "optional": True},
        ],
        "broadcasters": [WOWOW_EL],
    },
    {
        "id": 848,
        "name_ja": "UEFAカンファレンスリーグ",
        "name_short": "ECL",
        "flag": "🇪🇺",
        "sources": [
            {"page": "2025–26 UEFA Conference League knockout phase", "stages": ["SEMI_FINALS", "FINAL"], "legacy": True},
            {"page": "2026–27 UEFA Conference League league phase", "stages": None},
            {"page": "2026–27 UEFA Conference League knockout phase", "stages": None, "optional": True},
        ],
        "broadcasters": [
            {"name": "WOWOW", "type": "partial", "url": "https://droog.tokyo/link.php?i=phejoijtz4o2&m=mhotmxg90s1l", "note": "注目試合"},
        ],
    },
]

# Wikipedia のリンク先（記事名）→（日本語名, football-data.org のチームID or None）
# ID は data/clubs.json・matches.json に既にあるものだけ（推測で埋めない）。
# 日本人のいるクラブの日本語名は players.json の club_ja と同じ表記にそろえる（大会ページの突き合わせに使う）。
WIKI_CLUBS = {
    # 2026-27 EL リーグフェーズ 36クラブ（2026-10-21 英語版Wikipediaで確認）
    "AC Milan": ("ミラン", 98),
    "AC Omonia": ("オモニア", None),
    "AC Sparta Prague": ("スパルタ・プラハ", None),
    "AFC Bournemouth": ("ボーンマス", 1044),
    "AZ Alkmaar": ("AZアルクマール", 682),
    "Bayer 04 Leverkusen": ("レバークーゼン", 3),
    "Beşiktaş J.K.": ("ベシクタシュ", None),
    "Celtic F.C.": ("セルティック", None),
    "Crystal Palace F.C.": ("クリスタル・パレス", 354),
    "FC Ararat-Armenia": ("アララト・アルメニア", None),
    "FC Red Bull Salzburg": ("ザルツブルク", None),
    "FC Viktoria Plzeň": ("ヴィクトリア・プルゼニ", None),
    "Ferencvárosi TC": ("フェレンツヴァーロシュ", None),
    "GNK Dinamo Zagreb": ("ディナモ・ザグレブ", None),
    "Hapoel Be'er Sheva F.C.": ("ハポエル・ベエルシェバ", None),
    "Jagiellonia Białystok": ("ヤギエロニア・ビャウィストク", None),
    "Juventus FC": ("ユヴェントス", 109),
    "Lech Poznań": ("レフ・ポズナン", None),
    "Lillestrøm SK": ("リレストレム", None),
    "NEC Nijmegen": ("NEC", 1915),
    "NK Celje": ("ツェリェ", None),
    "OFI Crete F.C.": ("OFIクレタ", None),
    "Olympiacos F.C.": ("オリンピアコス", 654),
    "Olympique Lyonnais": ("リヨン", 523),
    "Olympique de Marseille": ("マルセイユ", 516),
    "PFC Levski Sofia": ("レフスキ・ソフィア", None),
    "RC Celta de Vigo": ("セルタ", 558),
    "RSC Anderlecht": ("アンデルレヒト", None),
    "Real Sociedad": ("レアル・ソシエダ", 92),
    "Royale Union Saint-Gilloise": ("ユニオン・サンジロワーズ", 3929),
    "S.C.U. Torreense": ("トレエンセ", None),
    "S.L. Benfica": ("ベンフィカ", 1903),
    "SK Sturm Graz": ("シュトゥルム・グラーツ", None),
    "Stade Rennais FC": ("レンヌ", 529),
    "Sunderland A.F.C.": ("サンダーランド", 71),
    "TSG 1899 Hoffenheim": ("ホッフェンハイム", 2),
    # 2026-27 ECL リーグフェーズ 36クラブ（2026-10-22 英語版Wikipediaで確認。全6節）
    "AFC Ajax": ("アヤックス", 678),
    "AS Monaco FC": ("モナコ", 548),
    "Aarhus Gymnastikforening": ("AGFオーフス", None),
    "Atalanta BC": ("アタランタ", 102),
    "Brighton & Hove Albion F.C.": ("ブライトン", 397),
    "CS Universitatea Craiova": ("ウニヴェルシタテア・クラヨーヴァ", None),
    "F.C. Copenhagen": ("コペンハーゲン", 1876),
    "FC Iberia 1999": ("イベリア1999", None),
    "FC Kairat": ("カイラト", None),
    "FC Lugano": ("ルガーノ", None),
    "FC Midtjylland": ("ミッティラン", None),
    "FC Nordsjælland": ("ノアシェラン", None),
    "FC Thun": ("トゥーン", None),
    "FC Twente": ("トゥエンテ", 666),
    "FK Borac Banja Luka": ("ボラツ・バニャ・ルカ", None),
    "FK Jablonec": ("ヤブロネツ", None),
    "FK Kauno Žalgiris": ("カウノ・ジャルギリス", None),
    "Getafe CF": ("ヘタフェ", 82),
    "HNK Hajduk Split": ("ハイドゥク・スプリト", None),
    "Heart of Midlothian F.C.": ("ハーツ", None),
    "Inter Club d'Escaldes": ("インテル・クルブ・デスカルデス", None),
    "KAA Gent": ("ヘント", None),
    "KF Egnatia": ("エグナティア", None),
    "Kuopion Palloseura": ("KuPS", None),
    "Lincoln Red Imps F.C.": ("リンカーン・レッドインプス", None),
    "Mjällby AIF": ("ミエルビー", None),
    "PFC CSKA Sofia": ("CSKAソフィア", None),
    "Pafos FC": ("パフォス", None),
    "Panathinaikos F.C.": ("パナシナイコス", None),
    "Red Star Belgrade": ("ツルヴェナ・ズヴェズダ", None),
    "Riga FC": ("リガFC", None),
    "S.C. Braga": ("ブラガ", 5613),
    "SC Freiburg": ("フライブルク", 17),
    "SK Brann": ("ブラン", None),
    "Sint-Truidense VV": ("シント＝トロイデン", None),
    "Trabzonspor": ("トラブゾンスポル", None),
}

# IDのあるクラブは、ほかのページと表記がずれないよう、football-data.org 由来の試合の名前（英語・日本語）を優先して使う
FD_NAMES = {}  # team_id -> (en, ja)。main() で matches.json から作る

CET = ZoneInfo("Europe/Paris")
# スコアが入っていても、キックオフからこの時間が経つまでは「試合中の途中経過」とみなして結果扱いしない
FINISH_AFTER = timedelta(minutes=110)

# stage 表記マップ
STAGE_NORMALIZE = {
    "Knockout phase play-offs": "PLAYOFFS",
    "Knockout round play-offs": "PLAYOFFS",
    "Round of 16": "LAST_16",
    "Quarter-finals": "QUARTER_FINALS",
    "Semi-finals": "SEMI_FINALS",
    "Final": "FINAL",
}


def fetch_wikitext(title, max_retries=4, follow_redirects=True):
    """follow_redirects=False：まだ記事が無く大会ページへ転送されているページを、転送先で読まない"""
    from urllib.parse import quote
    url = f"{WIKI_API}?action=parse&page={quote(title)}&prop=wikitext&format=json&formatversion=2" + ("&redirects=1" if follow_redirects else "")
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


def extract_football_boxes(text):
    """{{Football box ...}} と {{#invoke:Football box|main ...}} の両方を、出てくる順に抜き出す"""
    found = []
    for name in ("Football box", "#invoke:Football box"):
        for start, body in _extract_template_pos(text, name):
            found.append((start, body))
    found.sort()
    # 同じ位置の重複を除く
    out, seen = [], set()
    for start, body in found:
        if start in seen:
            continue
        seen.add(start)
        out.append(body)
    return out


def extract_template(text, name):
    return [b for _, b in _extract_template_pos(text, name)]


def _extract_template_pos(text, name):
    """{{name|...}} を bracket counting で抽出。(開始位置, 中身) のリストで返す"""
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
        out.append((s, text[s+2:j-2]))
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
    """'21:00' / '18:45&nbsp;{{small|(20:45 UTC+4)}}' → '21:00' / '18:45'
    先頭の時刻が UEFA 発表の中央ヨーロッパ時間（CET/CEST）。括弧の中は現地時刻なので使わない。"""
    m = re.match(r"\s*(\d{1,2}):(\d{2})", s or "")
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def to_jst_iso(date_str, time_str):
    """date='2026-10-22', time='21:00'（CET/CEST）→ JST ISO（夏時間・冬時間は Europe/Paris で判定）"""
    if not (date_str and time_str):
        return None
    try:
        local = datetime.fromisoformat(f"{date_str}T{time_str}:00").replace(tzinfo=CET)
        return local.astimezone(JST).isoformat()
    except Exception:
        return None


def parse_score(s):
    """'2–1' / '1−3' / '1–1 (a.e.t.)' → {home, away}"""
    s = re.sub(r"<ref.*?(</ref>|/>)", "", s, flags=re.DOTALL)
    # ダッシュの書き方がページごとに違う（– en dash・— em dash・− マイナス記号。ECL は − を使う）
    s = s.strip().replace("–", "-").replace("—", "-").replace("−", "-")
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)(?:\s|$|&nbsp;|\()", s + " ")
    if m:
        return {"home": int(m.group(1)), "away": int(m.group(2))}
    return None


def parse_team(field):
    """'[[AC Milan|Milan]] {{fbaicon|ITA}}' → ('AC Milan', 'Milan')"""
    m = re.search(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]", field or "")
    if m:
        target = m.group(1).strip()
        return target, (m.group(2) or target).strip()
    name = strip_wiki(field or "")
    return name, name


def resolve_team(target, display, clubs_data):
    """→ (日本語名, チームID or None)"""
    if target in WIKI_CLUBS:
        return WIKI_CLUBS[target]
    for k in (display, target):
        if k in clubs_data:
            return clubs_data[k], None
    return display, None


def jp_players_for(team_id, team_ja, names_en, players_index):
    out = []
    for jp in players_index:
        if team_id is not None and jp.get("club_id") == team_id:
            out.append(jp)
        elif jp.get("club_ja") and jp["club_ja"] == team_ja:
            out.append(jp)
        elif jp.get("club_en") and jp["club_en"] in names_en:
            out.append(jp)
    return out


def parse_match_box(body, stage_key, comp_meta, clubs_data, players_index, matchday=None, now=None):
    """1つの Football box body から Match dict を生成"""
    date_field = parse_box_field(body, "date")
    time_field = parse_box_field(body, "time")
    t1_target, team1 = parse_team(parse_box_field(body, "team1"))
    t2_target, team2 = parse_team(parse_box_field(body, "team2"))
    score_str = parse_box_field(body, "score")

    date = parse_start_date(date_field) or parse_start_date(body)
    time_str = parse_time(time_field) if time_field else None
    kickoff_jst = to_jst_iso(date, time_str)
    if not kickoff_jst or not team1 or not team2:
        return None

    score = parse_score(score_str) if score_str else None
    now = now or datetime.now(JST)
    if score and now < datetime.fromisoformat(kickoff_jst) + FINISH_AFTER:
        # キックオフ直後に入った途中経過は結果として扱わない
        score = None
    status = "FINISHED" if score else "SCHEDULED"

    home_ja, home_id = resolve_team(t1_target, team1, clubs_data)
    away_ja, away_id = resolve_team(t2_target, team2, clubs_data)

    # 日本人選手（players.json の所属クラブと突き合わせ）
    jp_players = []
    for side, tid, tja, names in (("home", home_id, home_ja, (team1, t1_target)),
                                  ("away", away_id, away_ja, (team2, t2_target))):
        for jp in jp_players_for(tid, tja, names, players_index):
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
        "matchday": matchday,
        "home_id": home_id,
        "home_ja": FD_NAMES.get(home_id, (None, home_ja))[1],
        "home_en": FD_NAMES.get(home_id, (team1, None))[0],
        "home_crest": f"https://crests.football-data.org/{home_id}.png" if home_id else None,
        "away_id": away_id,
        "away_ja": FD_NAMES.get(away_id, (None, away_ja))[1],
        "away_en": FD_NAMES.get(away_id, (team2, None))[0],
        "away_crest": f"https://crests.football-data.org/{away_id}.png" if away_id else None,
        "score": score,
        "japanese_players": jp_players,
        "broadcasters": comp_meta["broadcasters"],
        "_source": "wikipedia",
    }


def parse_page(wt, stages, comp, clubs_data, players_index):
    """ページの wikitext から試合を取り出す。
    リーグフェーズ：=== Matchday N === ごと（stage=LEAGUE_STAGE, matchday=N）
    ノックアウト：== Semi-finals == などの見出しごと（STAGE_NORMALIZE）"""
    out = []
    now = datetime.now(JST)
    # 見出しで区切る（== X == と === X === の両方）
    heads = [(m.start(), m.end(), m.group(1), m.group(2).strip())
             for m in re.finditer(r"^(={2,3})\s*([^=\n]+?)\s*\1\s*$", wt, re.MULTILINE)]
    cur_stage = None  # 直前の == 見出し == で決まる段階
    for i, (hs, he, level, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(wt)
        section = wt[he:end]
        md = re.match(r"Matchday\s+(\d+)$", title)
        if len(level) == 2:
            cur_stage = STAGE_NORMALIZE.get(title)
            stage, matchday = cur_stage, None
        elif md:
            stage, matchday = "LEAGUE_STAGE", int(md.group(1))
        else:
            # === Matches === / === First leg === などは親の段階を引き継ぐ
            stage, matchday = cur_stage, None
        if stage is None:
            continue
        if stages is not None and stage not in stages:
            continue
        for body in extract_football_boxes(section):
            m = parse_match_box(body, stage, comp, clubs_data, players_index, matchday=matchday, now=now)
            if m:
                out.append(m)
    return out


def main():
    matches_data = json.loads((DATA / "matches.json").read_text(encoding="utf-8"))
    matches = matches_data.get("matches", [])

    for m in matches:
        if m.get("_source") == "wikipedia":
            continue
        for side in ("home", "away"):
            tid = m.get(f"{side}_id")
            if tid is not None and m.get(f"{side}_en") and m.get(f"{side}_ja"):
                FD_NAMES[tid] = (m[f"{side}_en"], m[f"{side}_ja"])

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
        "Aston Villa": "アストン・ヴィラ",
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
    players_index = [p for p in players_data.get("players", [])
                     if (p.get("club_en") or p.get("club_ja")) and not p.get("second_team")]

    # ページごとに取得。失敗したページの試合は前回データを残す
    fetched = {}  # page -> list[match]（None なら取得失敗・未作成）
    for comp in COMPETITIONS:
        for src in comp["sources"]:
            page = src["page"]
            print(f"[INFO] {comp['name_ja']}: {page}")
            wt = fetch_wikitext(page, follow_redirects=not src.get("optional"))
            if wt and re.match(r"\s*#REDIRECT", wt, re.IGNORECASE):
                wt = ""
            if not wt:
                msg = "まだページが無い" if src.get("optional") else "取得失敗"
                print(f"  [SKIP] {msg}のため既存データ保持")
                fetched[page] = None
                time.sleep(1)
                continue
            got = parse_page(wt, src.get("stages"), comp, clubs_data, players_index)
            for m in got:
                m["_source_page"] = page
            n_fin = sum(1 for m in got if m["status"] == "FINISHED")
            print(f"  → parsed: {len(got)}件（結果あり {n_fin}件 / 日程のみ {len(got) - n_fin}件）")
            fetched[page] = got
            time.sleep(2)  # Wikipedia 思いやりウェイト

    def owner_page(m):
        """既存の試合がどのページ由来か。_source_page が無い古いデータは、その大会の legacy ページ扱い"""
        if m.get("_source_page"):
            return m["_source_page"]
        for comp in COMPETITIONS:
            if isinstance(m.get("id"), str) and m["id"].startswith(comp["name_short"] + "_"):
                for src in comp["sources"]:
                    if src.get("legacy"):
                        return src["page"]
        return None

    # 取得に成功したページの試合だけ入れ替える
    # ただし「Wikipediaが結果未反映で SCHEDULED/no-score だが既存データには FINISHED + score がある」
    # ケースでは既存データを保持する（Wikipedia の更新遅延で確定結果を上書きしないため）
    ok_pages = {pg for pg, got in fetched.items() if got}
    is_uefa2 = lambda m: isinstance(m.get("id"), str) and (m["id"].startswith("EL_") or m["id"].startswith("ECL_"))
    existing_by_id = {m.get("id"): m for m in matches if is_uefa2(m) and owner_page(m) in ok_pages}
    matches = [m for m in matches if not (is_uefa2(m) and owner_page(m) in ok_pages)]
    new_matches = []
    seen_ids = {m.get("id") for m in matches}
    for pg in ok_pages:
        for new_m in fetched[pg]:
            if new_m["id"] in seen_ids:
                continue
            seen_ids.add(new_m["id"])
            old_m = existing_by_id.get(new_m.get("id"))
            if old_m is not None:
                if old_m.get("highlights"):
                    new_m["highlights"] = old_m["highlights"]
                if (old_m.get("status") == "FINISHED" and old_m.get("score")
                        and new_m.get("status") != "FINISHED"):
                    print(f"  [PROTECT] {new_m.get('id')} 既存FINISHED保持 (Wikipedia更新遅延)")
                    new_m["status"] = "FINISHED"
                    new_m["score"] = old_m["score"]
            new_matches.append(new_m)

    matches.extend(new_matches)
    # kickoff順にソート
    matches.sort(key=lambda m: m.get("kickoff_jst", ""))

    # サニティチェック：もし全競技失敗で既存も0件なら警告
    if not new_matches and not any(
        isinstance(m.get("id"), str) and (m["id"].startswith("EL_") or m["id"].startswith("ECL_"))
        for m in matches
    ):
        print("[WARN] EL/ECL 試合が0件です（取得失敗で既存も無し）", file=sys.stderr)

    from utils import fix_finished_status
    fixed = fix_finished_status(matches)
    if fixed:
        print(f"[INFO] status='FINISHED' に補正: {fixed}件")

    # 配信先：全試合を league_guides.json の欄（公式確認済み）で書き直す（2026-10-22。下の WOWOW_EL 等の手書きは使われない）
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from watch_source import apply_to_matches
    n_bc = apply_to_matches(matches)
    print(f"[INFO] 配信先を league_guides.json の欄から書き直し: {n_bc}試合")

    matches_data["matches"] = matches
    matches_data["match_count"] = len(matches)
    matches_data["updated_uefa_secondary"] = datetime.now(JST).isoformat()
    (DATA / "matches.json").write_text(json.dumps(matches_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] EL/ECL 試合データを {len(new_matches)}件 追加（うち日本人所属クラブの試合を表示）")
    for m in new_matches:
        if not m.get("japanese_players"):
            continue
        score_str = f"{m['score']['home']}-{m['score']['away']}" if m.get('score') else 'TBD'
        jp = ', '.join(p['name_ja'] for p in m.get('japanese_players', [])) or '—'
        print(f"  [{m['stage']:12}] {m['kickoff_jst'][:16]} {m['home_ja']} {score_str} {m['away_ja']} (JP: {jp})")


if __name__ == "__main__":
    main()
