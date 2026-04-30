#!/usr/bin/env python3
"""
worldcdb.com から各国代表スカッドを取得して data/wc2026/squads.json を更新
- URL形式: https://worldcdb.com/{slug}.htm
- 行構造:
  - 1セル行 GK/DF/MF/FW = ポジション切替
  - 4セル行 = 選手データ（名前｜クラブ｜DOB(YY.M.D)｜身長/体重）
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
DATA = ROOT / "data" / "wc2026"
JST = timezone(timedelta(hours=9))

# TLA → worldcdb URL slug
URL_SLUGS = {
    "JPN": "japan",
    "MEX": "mexico",
    "RSA": "southafrica",
    "KOR": "korea",
    "CZE": "czech",
    "BIH": "bih",
    "CAN": "canada",
    "QAT": "qatar",
    "SUI": "switzerland",
    "BRA": "brazil",
    "MAR": "morocco",
    "HAI": "haiti",
    "SCO": "scotland",
    "TUR": "turkey",
    "USA": "usa",
    "PAR": "paraguay",
    "AUS": "australia",
    "GER": "germany",
    "CUW": "curacao",
    "CIV": "ivorycoast",
    "ECU": "ecuador",
    "JPN": "japan",
    "NED": "netherlands",
    "SWE": "sweden",
    "TUN": "tunisia",
    "BEL": "belgium",
    "EGY": "egypt",
    "IRN": "iran",
    "NZL": "newzealand",
    "ESP": "spain",
    "CPV": "capeverde",
    "KSA": "saudiarabia",
    "URU": "uruguay",
    "IRQ": "iraq",
    "FRA": "france",
    "SEN": "senegal",
    "NOR": "norway",
    "ARG": "argentina",
    "ALG": "algeria",
    "AUT": "austria",
    "JOR": "jordan",
    "COD": "drcongo",
    "POR": "portugal",
    "UZB": "uzbekistan",
    "COL": "colombia",
    "ENG": "england",
    "CRO": "croatia",
    "GHA": "ghana",
    "PAN": "panama",
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    try:
        with urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def parse_dob(s):
    """'85.7.13' → '1985-07-13'、'00.2.25' → '2000-02-25'"""
    m = re.match(r"(\d{2})\.(\d{1,2})\.(\d{1,2})", s.strip())
    if not m:
        return None
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy if yy < 30 else 1900 + yy
    return f"{year:04d}-{mm:02d}-{dd:02d}"


def parse_player_row(cells):
    """
    cells[0] = 'ギジェルモ・オチョア (Guillermo OCHOA)' （改行・スペース可）
    cells[1] = 'AELリマソル (キプロス)' or 'グアダラハラ・チバス'
    cells[2] = '85.7.13'
    cells[3] = '185/76'
    """
    if len(cells) < 4:
        return None
    raw_name = strip_tags(cells[0])
    # Split: '〇〇 (NAME_EN)'
    nm = re.match(r"(.+?)\s*\(([^)]+)\)", raw_name)
    if nm:
        name_ja = nm.group(1).strip()
        name_en = nm.group(2).strip()
    else:
        name_ja = raw_name
        name_en = None
    club = strip_tags(cells[1])
    dob = parse_dob(strip_tags(cells[2]))
    hw = strip_tags(cells[3])
    height = weight = None
    hwm = re.match(r"(\d+)\s*/\s*(\d+)", hw)
    if hwm:
        height = int(hwm.group(1))
        weight = int(hwm.group(2))
    return {
        "name_ja": name_ja,
        "name_en": name_en,
        "club": club,
        "dob": dob,
        "height_cm": height,
        "weight_kg": weight,
    }


def parse_squad_page(html):
    """ページHTMLから ポジション別 selectedプレーヤー配列を返す"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    current_pos = None
    players = []
    no_counter = 1
    as_of = None
    # ヘッダー行から「2026/3/19発表」等
    title_m = re.search(r"代表メンバー\s*[\(（]([\d/年月日]+)発表", html)
    if title_m:
        as_of = title_m.group(1).strip()
    for r in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
        if not cells:
            continue
        if len(cells) == 1:
            text = strip_tags(cells[0])
            if text in ("GK", "DF", "MF", "FW"):
                current_pos = text
                continue
        # プレーヤー行
        if current_pos and len(cells) >= 4:
            p = parse_player_row(cells)
            if p:
                p["no"] = None
                p["pos"] = current_pos
                players.append(p)
    return {"players": players, "as_of": as_of}


def main():
    target_group = sys.argv[1].upper() if len(sys.argv) > 1 else None
    countries = json.loads((DATA / "countries.json").read_text(encoding="utf-8"))
    squads_path = DATA / "squads.json"
    squads = json.loads(squads_path.read_text(encoding="utf-8")) if squads_path.exists() else {}
    cs = countries.get("countries", {})
    items = cs.values() if isinstance(cs, dict) else cs

    for c in items:
        tla = c["tla"]
        group = c.get("group")
        if target_group and group != target_group:
            continue
        if tla in squads and squads[tla].get("players"):
            print(f"  [{tla}] 既に取得済（players={len(squads[tla]['players'])}）→ スキップ")
            continue
        slug = URL_SLUGS.get(tla)
        if not slug:
            print(f"  [{tla}] URLスラッグ未定義→スキップ")
            continue
        url = f"https://worldcdb.com/{slug}.htm"
        print(f"  [{tla}] {url}")
        html = fetch(url)
        if not html:
            continue
        data = parse_squad_page(html)
        if not data["players"]:
            print(f"    ⚠️ 0人取得（HTMLパース失敗の可能性）")
            continue
        squads[tla] = {
            "tla": tla,
            "ja": c.get("ja"),
            "flag": c.get("flag"),
            "as_of": data["as_of"],
            "source": url,
            "players": data["players"],
        }
        print(f"    ✓ {len(data['players'])}名取得（as_of: {data['as_of']}）")
        time.sleep(0.5)

    squads["_updated"] = datetime.now(JST).isoformat()
    squads["_source"] = "worldcdb.com"
    squads["_note"] = "各国直近代表メンバー。2026最終スカッドは6/1のFIFA発表後に更新"
    squads_path.write_text(json.dumps(squads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] 書き込み完了: {squads_path}")


if __name__ == "__main__":
    main()
