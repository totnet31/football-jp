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
        "Hull City": ["Hull City A.F.C.", "Hull City"],
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
        "Leeds": ["Leeds United F.C.", "Leeds United"],
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
    """日付文字列 → 'YYYY-MM-DD'

    対応形式:
      '16 August 2025'            → '2025-08-16'
      '{{Start date|2025|7|6|...}}' → '2025-07-06'
      '{{dts|format=dmy|2025|8|23}}' → '2025-08-23' （wikitable用、_parse_dts と同じ）
    """
    s = s.strip()
    # {{Start date|YYYY|M|D|...}} 形式
    m = re.search(r"\{\{[Ss]tart\s*date\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # {{dts|...|YYYY|M|D}} 形式
    m = re.search(r"\{\{dts[^}]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 'DD Month YYYY' プレーンテキスト形式
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if not m:
        return None
    day, mon_name, year = int(m.group(1)), m.group(2), int(m.group(3))
    if mon_name not in MONTH_MAP:
        return None
    return f"{year:04d}-{MONTH_MAP[mon_name]:02d}-{day:02d}"


def strip_wiki_link(s):
    """[[Real Name|Display]] → 'Display'、[[Name]] → 'Name'、{{fbaicon|GER}} などのテンプレート除去"""
    # {{flagicon|...}} {{fbaicon|...}} などのインラインテンプレート除去
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
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
        # {{goal|MIN}} 〜 {{goal|MIN|MIN|...}} 〜 {{goal|MIN|note|MIN|...}} を抽出
        # 全パイプ区切りのトークンを取得し、数値（"45+3"含む）はゴール、それ以外（pen.等）は直前のゴールの注記
        goals = []
        for gm in re.finditer(r"\{\{goal\s*\|([^}]+)\}\}", rest):
            tokens_raw = gm.group(1)
            # || は単独 | と等価扱い
            tokens = [t.strip() for t in re.split(r"\|+", tokens_raw) if t.strip() != ""]
            current_note = ""
            for tok in tokens:
                if re.match(r"^\d+\s*\+?\s*\d*$", tok):
                    goals.append({"minute_raw": tok, "note": current_note.lower()})
                    current_note = ""
                else:
                    current_note = tok
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


def has_match_data(wt):
    """wikitextが試合データ（ゴール情報）を含むか判定"""
    if not wt:
        return False
    wt_lower = wt.lower()
    # 既存テンプレ（football box collapsible / football box）
    if "football box collapsible" in wt_lower:
        return True
    if "{{football box" in wt_lower:
        return True
    # Fb rs / football box small 系
    if "{{fb rs" in wt_lower:
        return True
    if "{{football box small" in wt_lower:
        return True
    # 通常 wikitable で試合結果がある場合
    # "scorers" 列ヘッダーが含まれていれば採用
    if "wikitable" in wt_lower and "scorer" in wt_lower:
        return True
    return False


def _normalize_header(h):
    """wikitableヘッダーセルを正規化して小文字の純テキストに"""
    # scope="col"| や class="..."| などを除去
    if "|" in h:
        h = h.split("|")[-1]
    # {{...}} テンプレートを除去
    h = re.sub(r"\{\{[^}]+\}\}", "", h)
    # <br/> を空白に
    h = re.sub(r"<br\s*/?>", " ", h, flags=re.IGNORECASE)
    return h.strip().lower()


def _parse_dts(s):
    """{{dts|format=dmy|2025|8|23}} → '2025-08-23'"""
    m = re.search(r"\{\{dts[^}]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _parse_date_cell(s):
    """wikitableの日付セルをパース（dts形式 or プレーンテキスト）"""
    return _parse_dts(s) or parse_date(strip_wiki_link(s))


def _parse_scorers_cell(cell_text):
    """Scorersセルから [(wiki_target, display, minute_raw, note)] を抽出

    対応形式:
      [[Jay Stansfield|Stansfield]] 55'
      [[Paik Seung-ho|Paik]] 40'
      Amoura 42'
      [[Stansfield]] 90' (pen.)
      [[Stansfield]] 90' pen., [[Dykes]] 90+8'
    """
    out = []
    pattern = (
        r"(?:"
        r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]"   # [[wiki|display]] or [[wiki]]
        r"|([A-ZÁÉÍÓÚÀÈÌÒÙÄÖÜ\u00C0-\u024F][A-Za-záéíóúàèìòùÀ-ÖØ-öø-ÿĀ-ž'\.\-]{1,30}"
        r"(?:\s+[A-Za-záéíóúàèìòùÀ-ÖØ-öø-ÿĀ-ž'\.\-]{1,30}){0,3}?)"  # plain text name
        r")"
        r"\s+(\d{1,3}(?:\+\d+)?)['\u2019]"   # MIN'
    )
    for m in re.finditer(pattern, cell_text):
        wiki_target = m.group(1)
        display = m.group(2) or m.group(1) or m.group(3)
        minute_raw = m.group(4)
        if not (display and minute_raw):
            continue
        # pen./og チェック（直後の括弧内）
        rest = cell_text[m.end():]
        note_m = re.match(r"\s*\(?\s*([^,\)]{0,25}?(?:pen|og)[^,\)]{0,25}?)\s*\)?", rest, re.IGNORECASE)
        note = note_m.group(1).strip().lower() if note_m else ""
        out.append({
            "wiki_target": wiki_target,
            "display": display.strip(),
            "minute_raw": minute_raw,
            "note": note,
        })
    return out


def parse_wikitable_matches(wikitext, club_en):
    """wikitable形式の試合結果テーブルをパースしてboxes互換形式で返す

    wikitableは「クラブ視点」で Opponent/Venue/Scorers が1列にまとまっている。
    boxes 互換形式に変換する際は:
      - team1 = club_en（このクラブ）
      - team2 = opponent
      - goals1/goals2 は両方空にして、scorers に全ゴール情報を格納
      ただし find_match() が team1/team2 で照合するので venue (H/A) を使って
      team1/team2 を適切に設定する。
    """
    out = []
    # match details を含む wikitable を対象（Scorers列が必須）
    for table_m in re.finditer(r"\{\|[^\n]*wikitable(.*?)\n\|\}", wikitext, re.DOTALL):
        table_text = table_m.group(0)

        # ヘッダー行を特定（!で始まる行）
        # Birmingham式: !scope=col|Date\n!scope=col|...（1列1行）
        # Bundesliga式: !Round!!Date!!Time!!... （||区切り1行）
        single_headers = re.findall(r"^!([^!\n]+)", table_text, re.MULTILINE)
        inline_header = re.search(r"^!(.+)", table_text, re.MULTILINE)
        if inline_header and "!!" in inline_header.group(1):
            raw_headers = re.split(r"!!", inline_header.group(1))
        else:
            raw_headers = single_headers

        if not raw_headers:
            continue

        norm_headers = [_normalize_header(h) for h in raw_headers]

        # 必要列のインデックスを特定
        scorers_col = date_col = opponent_col = venue_col = None
        for i, h in enumerate(norm_headers):
            if "scorer" in h:
                scorers_col = i
            elif h == "date":
                date_col = i
            elif "opponent" in h:
                opponent_col = i
            elif h == "venue":
                venue_col = i

        # Scorers・Date・Opponent がないテーブルはスキップ
        if scorers_col is None or date_col is None or opponent_col is None:
            continue

        # データ行: |- の直後に続く | で始まる行（次の |- か |} まで）
        # 各データ行は通常1行に全セルが || で区切られて入っている
        for row_m in re.finditer(r"\|-[^\n]*\n(\|[^\n]+)", table_text):
            row_text = row_m.group(1).strip()
            # || で分割（先頭の | を除去）
            cells = re.split(r"\|\|", row_text)
            cells[0] = re.sub(r"^\|", "", cells[0]).strip()
            cells = [c.strip() for c in cells]

            max_col = max(c for c in [scorers_col, date_col, opponent_col, venue_col] if c is not None)
            if len(cells) <= max_col:
                continue

            date = _parse_date_cell(cells[date_col])
            if not date:
                continue

            opponent = strip_wiki_link(cells[opponent_col])
            venue_raw = strip_wiki_link(cells[venue_col]).strip().lower() if venue_col is not None else "h"

            # H/Away に基づいてチーム順を決定
            # venue が "h", "home", St Andrew's (H) 等 → club が team1（ホーム）
            is_home = ("home" in venue_raw or venue_raw == "h" or
                       (venue_raw.endswith("(h)")) or
                       re.search(r"\bh\b", venue_raw) is not None)

            if is_home:
                team1, team2 = club_en, opponent
                goals1_raw = goals2_raw = []  # wikitableは分離不可
            else:
                team1, team2 = opponent, club_en
                goals1_raw = goals2_raw = []

            scorers = _parse_scorers_cell(cells[scorers_col])
            # goals1/goals2 の代わりに scorers を team1/team2 どちら側かわからないため
            # 両方に全員を入れる（find_match後に日本人選手照合で絞る）
            # ただしside情報は "unknown" とする
            scorer_entries = [{
                "wiki_target": s["wiki_target"],
                "display": s["display"],
                "goals": [{"minute_raw": s["minute_raw"], "note": s["note"]}],
            } for s in scorers]

            out.append({
                "date": date,
                "team1": team1,
                "team2": team2,
                "score": "",
                "round": "",
                "goals1": scorer_entries,  # wikitableは両チーム混在→goals1に全員
                "goals2": [],
                "_wikitable": True,        # wikitable由来フラグ
            })
    return out


def parse_match_boxes(wikitext):
    """{{football box collapsible}} と {{football box}} 両方を抽出"""
    # collapsible版（メイン）
    boxes = re.findall(r"\{\{[Ff]ootball box collapsible(.*?)\n\}\}", wikitext, re.DOTALL)
    # 非collapsible版
    boxes += re.findall(r"\{\{[Ff]ootball box\b(?! collapsible)(.*?)\n\}\}", wikitext, re.DOTALL)
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


def parse_all_matches(wikitext, club_en):
    """football box collapsible / wikitable の両方から試合データを統合して返す"""
    boxes = parse_match_boxes(wikitext)
    wikitable_boxes = parse_wikitable_matches(wikitext, club_en)
    # 重複排除：同じ date+team1+team2 のものは football box collapsible 優先
    existing_keys = {(b["date"], b["team1"], b["team2"]) for b in boxes}
    for wb in wikitable_boxes:
        key = (wb["date"], wb["team1"], wb["team2"])
        if key not in existing_keys:
            boxes.append(wb)
            existing_keys.add(key)
    return boxes


def normalize_team(name):
    if not name:
        return ""
    s = re.sub(r"\b(F\.?C\.?|CF|SC|AC|FK|AS|BK|RC|AFC|CFC|VfL|VfB|FSV|TSG|Borussia|VV|RKC)\b",
               "", name, flags=re.IGNORECASE)
    s = re.sub(r"\W+", " ", s).strip().lower()
    return s


def _ascii_fold(s):
    """Unicode の発音符号つき文字をASCII近似に変換（例: ō→o, ā→a）"""
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def build_jp_lookup(players):
    """name_en + wiki_target_guess → name_ja のマップ

    Unicode正規化バリアントも登録（例: 'Dōan' → 'Doan' → '堂安律'）
    """
    out = {}
    for p in players:
        nen = p.get("name_en")
        nja = p.get("name_ja")
        if not (nen and nja):
            continue
        for key in [nen, nen.lower(), _ascii_fold(nen), _ascii_fold(nen).lower()]:
            out.setdefault(key, nja)
        # 苗字（最後の単語）も登録
        last = nen.split()[-1]
        for key in [last, last.lower(), _ascii_fold(last), _ascii_fold(last).lower()]:
            out.setdefault(key, nja)
    return out


# matches.json のクラブ名略称 → Wikipedia での正式名の一部（normalize_team後）への展開
_TEAM_ALIASES = {
    "hsv": ["hamburger", "hamburger sv"],
    "m gladbach": ["monchengladbach", "m gladbach", "gladbach"],
    "brighton hove": ["brighton", "brighton hove albion"],
    "brighton": ["brighton", "brighton hove albion"],
    "man city": ["manchester city", "man city"],
    "man united": ["manchester united", "man united"],
    "qpr": ["queens park rangers", "qpr"],
    "rb leipzig": ["leipzig", "rb leipzig"],
    "go ahead": ["go ahead eagles", "go ahead"],
    "nac": ["nac breda", "nac"],
    "1 fc koln": ["cologne", "koln", "1 koln"],
    "ac pisa": ["pisa"],
    "sc freiburg": ["freiburg", "sc freiburg"],
}


def _team_variants(normalized_name):
    """normalize_team 済みのチーム名からマッチ候補リストを返す（_ascii_fold 済み）"""
    n = _ascii_fold(normalized_name)
    variants = {n}
    for key, alts in _TEAM_ALIASES.items():
        if n == key or n.startswith(key) or key in n:
            variants.update(alts)
            break
    # ASCII fold のみのバリアント
    variants.add(_ascii_fold(n))
    return variants


def _teams_match(a_norm, b_norm):
    """normalize_team 済みの2つのチーム名が同一チームかを判定"""
    if not a_norm or not b_norm:
        return False
    # ASCII fold
    a_ascii = _ascii_fold(a_norm)
    b_ascii = _ascii_fold(b_norm)
    # substring matching（どちらかが他方に含まれる）
    if a_ascii in b_ascii or b_ascii in a_ascii:
        return True
    # エイリアスで展開して照合
    a_variants = _team_variants(a_ascii)
    b_variants = _team_variants(b_ascii)
    for av in a_variants:
        for bv in b_variants:
            if av and bv and (av in bv or bv in av):
                return True
    return False


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
    if _teams_match(h, t1) and _teams_match(a, t2):
        return True
    if _teams_match(h, t2) and _teams_match(a, t1):
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
    # boxes が更新されたクラブの club_id セット（events_map の再計算に使う）
    refreshed_club_ids = set()

    for cid, info in by_club.items():
        cen = info["name_en"]
        # キャッシュチェック: boxes が空でなければ再利用
        cached = pages_cache.get(str(cid), {})
        if cached.get("boxes"):
            boxes = cached["boxes"]
            print(f"  [CACHE] {cen}: {len(boxes)}試合")
            boxes_per_club[cid] = boxes
            continue
        # boxes が空（title=None または boxes=[] でSKIP/失敗済み）の場合は再取得を試みる
        # ページタイトル候補を順に試す
        wt = None
        used_title = None
        for title in candidate_pages(cen, cid):
            wt = fetch_wikitext(title)
            if wt and has_match_data(wt):
                used_title = title
                break
            time.sleep(0.4)
        # フォールバック：opensearch
        if not used_title:
            found_title = search_season_page(cen)
            if found_title:
                wt2 = fetch_wikitext(found_title)
                if wt2 and has_match_data(wt2):
                    wt = wt2
                    used_title = found_title
        if not wt or not used_title:
            print(f"  [SKIP] {cen}: シーズンページ見つからず")
            pages_cache[str(cid)] = {"title": None, "boxes": []}
            continue
        boxes = parse_all_matches(wt, cen)
        if boxes:
            # 新規取得または再取得成功 → events_map の再計算が必要
            refreshed_club_ids.add(cid)
        pages_cache[str(cid)] = {"title": used_title, "boxes": boxes}
        boxes_per_club[cid] = boxes
        print(f"  [WIKI] {cen} ({used_title}): {len(boxes)}試合")
        time.sleep(0.5)

    # 再取得したクラブに関連する events_map エントリを削除して再計算させる
    if refreshed_club_ids:
        # 各試合の JP 選手のクラブが refreshed_club_ids に含まれる場合は events_map から削除
        cleared = 0
        for m in finished_jp:
            mid = str(m["id"])
            if mid not in events_map:
                continue
            jp_clubs = set()
            for p in players:
                for jp in m.get("japanese_players", []):
                    if p.get("name_ja") == jp.get("name_ja") and p.get("club_id"):
                        jp_clubs.add(p["club_id"])
            if jp_clubs & refreshed_club_ids:
                del events_map[mid]
                cleared += 1
        if cleared:
            print(f"  [REFRESH] {cleared}試合のキャッシュをクリア（再計算対象）")

    # 各 finished_jp 試合に対して、関連クラブの boxes から日本人ゴール抽出
    found = 0
    for m in finished_jp:
        mid = str(m["id"])
        # ゴールデータが確認できた試合はスキップ（空 [] はマッチング失敗の可能性があるため再計算）
        if events_map.get(mid):
            continue  # キャッシュ済み（ゴールデータあり）
        # この試合のJP選手のクラブ群
        jp_clubs = set()
        for p in players:
            for jp in m.get("japanese_players", []):
                if p.get("name_ja") == jp.get("name_ja") and p.get("club_id"):
                    jp_clubs.add(p["club_id"])
        # それらクラブのboxesから日付+対戦相手で照合
        events = []
        matched = False
        for cid in jp_clubs:
            if matched:
                break
            for box in boxes_per_club.get(cid, []):
                if not find_match(m, box):
                    continue
                matched = True
                is_wikitable = box.get("_wikitable", False)

                if is_wikitable:
                    # wikitableはgoals1に全ゴール情報が混在（side不明）
                    side_pairs = [("unknown", box["goals1"])]
                else:
                    # football box collapsible: team1=home相当
                    h_norm = normalize_team(m.get("home_en"))
                    t1_norm = normalize_team(box["team1"])
                    home_is_team1 = (h_norm in t1_norm or t1_norm in h_norm) if (h_norm and t1_norm) else True
                    side_pairs = [
                        ("home" if home_is_team1 else "away", box["goals1"]),
                        ("away" if home_is_team1 else "home", box["goals2"]),
                    ]

                # 各 goals ブロックから全得点を保存（日本人にはフラグ付与）
                for side, gblock in side_pairs:
                    for entry in gblock:
                        candidates = [entry.get("display", ""), entry.get("wiki_target") or ""]
                        ja = None
                        for c in candidates:
                            if not c:
                                continue
                            # 通常照合 + ASCII折りたたみ照合（ō→o 等のアクセント対応）
                            for key in [c, c.lower(), _ascii_fold(c), _ascii_fold(c).lower()]:
                                if key in jp_lookup:
                                    ja = jp_lookup[key]
                                    break
                            if ja:
                                break
                            # 苗字のみ照合
                            last = c.split()[-1]
                            for key in [last, last.lower(), _ascii_fold(last), _ascii_fold(last).lower()]:
                                if key in jp_lookup:
                                    ja = jp_lookup[key]
                                    break
                            if ja:
                                break
                        for g in entry["goals"]:
                            minute = parse_minute(g["minute_raw"])
                            if minute is None:
                                continue
                            events.append({
                                "type": "goal",
                                "player_ja": ja or entry["display"],
                                "player_en": entry["display"],
                                "is_japanese": ja is not None,
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
