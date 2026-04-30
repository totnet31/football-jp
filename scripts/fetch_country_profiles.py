#!/usr/bin/env python3
"""
W杯出場48か国のプロフィールをWikipediaから自動取得
- 入力: data/wc2026/countries.json（48か国マスタ）
- 出力: data/wc2026/country_profiles.json（既存をマージ）
- 取得項目: coach（監督）, captain（キャプテン）, wc_appearances, best_result, fifa_rank
- 既存detailedプロフィールは上書きしない（保護）
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
DATA = ROOT / "data" / "wc2026"
JST = timezone(timedelta(hours=9))

WIKI_API = "https://en.wikipedia.org/w/api.php"

# TLA → Wikipedia ページ名（標準形式： "{Country} national football team"）
PAGE_OVERRIDES = {
    "USA": "United States men's national soccer team",
    "KOR": "South Korea national football team",
    "PRK": "North Korea national football team",
    "RSA": "South Africa national football team",
    "CZE": "Czech Republic national football team",
    "BIH": "Bosnia and Herzegovina national football team",
    "CIV": "Ivory Coast national football team",
    "CPV": "Cape Verde national football team",
    "COD": "DR Congo national football team",
    "CUW": "Curaçao national football team",
    "JPN": "Japan national football team",
    "NED": "Netherlands national football team",
    "SWE": "Sweden national football team",
    "TUN": "Tunisia national football team",
    "MEX": "Mexico national football team",
    "CAN": "Canada men's national soccer team",
    "ENG": "England national football team",
    "ESP": "Spain national football team",
    "FRA": "France national football team",
    "GER": "Germany national football team",
    "POR": "Portugal national football team",
    "ITA": "Italy national football team",
    "BRA": "Brazil national football team",
    "ARG": "Argentina national football team",
    "URU": "Uruguay national football team",
    "PAR": "Paraguay national football team",
    "AUS": "Australia men's national soccer team",
    "NZL": "New Zealand men's national football team",
    "MAR": "Morocco national football team",
    "EGY": "Egypt national football team",
    "GHA": "Ghana national football team",
    "SEN": "Senegal national football team",
    "ALG": "Algeria national football team",
    "IRN": "Iran national football team",
    "IRQ": "Iraq national football team",
    "JOR": "Jordan national football team",
    "KSA": "Saudi Arabia national football team",
    "QAT": "Qatar national football team",
    "UZB": "Uzbekistan national football team",
    "PAN": "Panama national football team",
    "HAI": "Haiti national football team",
    "SUI": "Switzerland national football team",
    "BEL": "Belgium national football team",
    "AUT": "Austria national football team",
    "NOR": "Norway national football team",
    "CRO": "Croatia national football team",
    "SCO": "Scotland national football team",
    "TUR": "Turkey national football team",
    "ECU": "Ecuador national football team",
    "COL": "Colombia national football team",
}


def fetch_wikitext(title):
    url = (f"{WIKI_API}?action=parse&page={quote(title)}"
           f"&prop=wikitext&format=json&formatversion=2&redirects=1")
    req = Request(url, headers={"User-Agent": "football-jp/0.1 (saito@tottot.net)"})
    try:
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            return None
        return data.get("parse", {}).get("wikitext", "")
    except (HTTPError, URLError) as e:
        print(f"  [WIKI ERROR] {title}: {e}", file=sys.stderr)
        return None


def parse_infobox_field(box, field):
    pat = rf"^\s*\|\s*{field}\s*=\s*(.*?)(?=\n\s*\||\n\s*\}}\}})"
    m = re.search(pat, box, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def strip_wiki(s):
    if not s:
        return ""
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
    s = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref[^/]*/>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


# 順位（Wikipedia英語表記）→ 日本語＋数値スコア（小さいほど好成績）
RESULT_RANK = {
    "Champions": ("優勝", 1),
    "Winners": ("優勝", 1),
    "Runners-up": ("準優勝", 2),
    "Third place": ("3位", 3),
    "Fourth place": ("4位", 4),
    "Semi-finals": ("ベスト4", 4),
    "Quarter-finals": ("ベスト8", 8),
    "Round of 16": ("ベスト16", 16),
    "Round of 32": ("ベスト32", 32),
    "Group stage": ("グループステージ", 32),
    "First round": ("グループステージ", 32),
    "Second round": ("ベスト16", 16),
}


def parse_wc_record(wt, country_en=None):
    """FIFA World Cup の最初のテーブルから Total 行を取得（transclusion対応）"""
    m = re.search(r"\n(=+) ?FIFA World Cup ?\1", wt)
    if not m:
        return {"appearances": None, "best_result": None}
    i = m.end()
    level = len(m.group(1))
    next_same = re.search(rf"\n={{{level}}}(?!=)[^=]", wt[i:])
    section_end = i + (next_same.start() if next_same else len(wt[i:]))
    section_text = wt[i:section_end]

    # transclusion検出: {{#section-h:Page|Section}} → 専用ページを取得
    transclusion = re.search(r"\{\{#section-h:([^|]+)\|", section_text)
    if transclusion:
        sub_title = transclusion.group(1).strip()
        sub_wt = fetch_wikitext(sub_title)
        if sub_wt:
            ts = sub_wt.find("{|")
            te = sub_wt.find("\n|}", ts) if ts >= 0 else -1
            if ts >= 0 and te >= 0:
                section = sub_wt[ts:te + 3]
                result = _extract_total(section)
                if result.get("appearances"):
                    return result

    # {{main|Page}} 参照があれば、同じページからTotalを試みる
    main_link = re.search(r"\{\{main\|([^|}]+)\}\}", section_text)
    if main_link:
        sub_title = main_link.group(1).strip()
        sub_wt = fetch_wikitext(sub_title)
        if sub_wt:
            ts = sub_wt.find("{|")
            te = sub_wt.find("\n|}", ts) if ts >= 0 else -1
            if ts >= 0 and te >= 0:
                section = sub_wt[ts:te + 3]
                result = _extract_total(section)
                if result.get("appearances"):
                    return result

    table_start = wt.find("{|", i, section_end)
    if table_start < 0:
        return {"appearances": None, "best_result": None}
    table_end = wt.find("\n|}", table_start, section_end)
    if table_end < 0:
        return {"appearances": None, "best_result": None}
    section = wt[table_start:table_end + 3]
    return _extract_total(section)


def _extract_total(section):

    # Total 行を見つける。書式バリエーション:
    # 1) シングルライン: "!Total: 18/23!!Quarter-finals!!..."
    # 2) マルチライン: "!Total\n!{{Tooltip|Runners-up|Highest finish}}\n!{{Tooltip|9/22|...}}"
    # 3) Tooltip埋込: "!Total||{{Tooltip|Quarter-finals|Highest finish}}||..."
    appearances = None
    best_label = None
    # "Total" 出現位置から後ろ ~800 文字を total 行として扱う
    tm = re.search(r"^![\!\|\s]*Total\b", section, re.MULTILINE)
    if tm:
        chunk = section[tm.start():tm.start() + 1500]
        # マルチラインTotal: 次の '|-' または '|}' まで
        end_chunk = re.search(r"\n\|[-\}]", chunk)
        if end_chunk:
            chunk = chunk[:end_chunk.start()]

        # 出場回数: "X/Y" パターン（plain or tooltip内）
        ams = list(re.finditer(r"(\d+)\s*/\s*\d+", chunk))
        # ただし得失点比などのX/Y形式と区別するため、Tooltipに "Number of tournaments" や "qualified" が含まれるものを優先
        for am in ams:
            ctx = chunk[max(0, am.start()-80):am.start()+50]
            if "tournaments" in ctx.lower() or "qualified" in ctx.lower():
                appearances = int(am.group(1))
                break
        if appearances is None and ams:
            # フォールバック：最初の数字/数字
            appearances = int(ams[0].group(1))

        # 最高成績: Highest finish 周辺・Tooltip内のラベル探索
        # Tooltipの第1引数が最高成績ラベル
        tooltip_first = re.search(r"\{\{Tooltip\|([^|}]+)\|Highest finish\}\}", chunk)
        if tooltip_first:
            best_text = tooltip_first.group(1).strip()
            for label, (ja, sc) in RESULT_RANK.items():
                if label.lower() == best_text.lower():
                    best_label = ja
                    break
            if best_label is None:
                best_label = best_text  # 不明ラベルはそのまま
        else:
            # ラベル直書き
            for label, (ja, sc) in RESULT_RANK.items():
                if re.search(rf"\b{re.escape(label)}\b", chunk):
                    best_label = ja
                    break

    return {"appearances": appearances, "best_result": best_label}


def extract_profile(wt):
    if not wt:
        return None
    m = re.search(r"\{\{Infobox national football team(.*?)\n\}\}", wt, re.DOTALL)
    if not m:
        return None
    box = m.group(1)
    coach = strip_wiki(parse_infobox_field(box, "Coach") or parse_infobox_field(box, "Manager"))
    captain = strip_wiki(parse_infobox_field(box, "Captain"))
    fifa_max = strip_wiki(parse_infobox_field(box, "FIFA max"))
    wc = parse_wc_record(wt)
    return {
        "manager_en": coach or None,
        "captain_en": captain or None,
        "fifa_max_rank": fifa_max or None,
        "wc_appearances": wc["appearances"],
        "best_result": wc["best_result"],
    }


def main():
    # 引数：対象グループ（例: 'A' で Group A のみ。指定なしで全48か国）
    target_group = sys.argv[1].upper() if len(sys.argv) > 1 else None

    profiles_path = DATA / "country_profiles.json"
    countries = json.loads((DATA / "countries.json").read_text(encoding="utf-8"))
    profiles = json.loads(profiles_path.read_text(encoding="utf-8")) if profiles_path.exists() else {"profiles": {}}
    pmap = profiles.setdefault("profiles", {})

    targets = []
    cs = countries.get("countries", {})
    items = cs.values() if isinstance(cs, dict) else cs
    for c in items:
        tla = c.get("tla")
        group = c.get("group")
        if target_group and group != target_group:
            continue
        # 既存detailed（手動分）はスキップ。auto_filledは更新可
        existing = pmap.get(tla, {})
        if existing.get("detailed") and not existing.get("auto_filled"):
            continue
        targets.append(c)

    print(f"[INFO] 対象: {len(targets)}か国")

    for c in targets:
        tla = c["tla"]
        title = PAGE_OVERRIDES.get(tla) or f"{c.get('en')} national football team"
        print(f"  [{tla}] {title}")
        wt = fetch_wikitext(title)
        prof = extract_profile(wt)
        if not prof:
            print(f"    ⚠️ 取得失敗")
            continue
        # 既存をベースに上書き（detailed=true手動分は除外済み）
        existing = pmap.get(tla, {})
        merged = {**existing, **prof,
                  "ja": existing.get("ja") or c.get("ja"),
                  "en": existing.get("en") or c.get("en"),
                  "flag": existing.get("flag") or c.get("flag"),
                  "group": existing.get("group") or c.get("group"),
                  "auto_filled": True,
                  "detailed": True,
                  "source_wiki": title}
        pmap[tla] = merged
        print(f"    ✓ 監督={prof['manager_en']} / W杯出場={prof['wc_appearances']}回 / 最高={prof['best_result']}")
        time.sleep(0.5)

    profiles["updated"] = datetime.now(JST).isoformat()
    profiles_path.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] 書き込み完了: {profiles_path}")


if __name__ == "__main__":
    main()
