#!/usr/bin/env python3
"""ENGスカッドを Wikipedia の Current squad から取得（worldcdbに無いため）"""
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "wc2026"
JST = timezone(timedelta(hours=9))


def fetch_wikitext(title):
    url = f"https://en.wikipedia.org/w/api.php?action=parse&page={title}&prop=wikitext&format=json&formatversion=2&redirects=1"
    req = Request(url, headers={"User-Agent": "football-jp/0.1"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("parse", {}).get("wikitext", "")


def extract_templates(text, name):
    out = []
    i = 0
    pat = "{{" + name
    while True:
        s = text.find(pat, i)
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


def parse_player(body):
    no = re.search(r"\|\s*no\s*=\s*(\d+)", body)
    pos = re.search(r"\|\s*pos\s*=\s*([A-Z]+)", body)
    name = re.search(r"\|\s*name\s*=\s*\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", body)
    bd = re.search(r"Birth date and age\|(\d+)\|(\d+)\|(\d+)", body)
    caps = re.search(r"\|\s*caps\s*=\s*(\d+)", body)
    goals = re.search(r"\|\s*goals\s*=\s*(\d+)", body)
    club = re.search(r"\|\s*club\s*=\s*\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", body)
    name_en = (name.group(2) or name.group(1)) if name else None
    return {
        "no": int(no.group(1)) if no else None,
        "pos": pos.group(1) if pos else None,
        "name_ja": name_en,  # 日本語名は別途付与（暫定で英名）
        "name_en": name_en,
        "club": (club.group(2) or club.group(1)) if club else None,
        "dob": f"{bd.group(1)}-{int(bd.group(2)):02d}-{int(bd.group(3)):02d}" if bd else None,
        "height_cm": None,
        "weight_kg": None,
        "caps": int(caps.group(1)) if caps else None,
        "goals": int(goals.group(1)) if goals else None,
    }


def main():
    wt = fetch_wikitext("England_national_football_team")
    i = wt.find("==Current squad==")
    nh = re.search(r"\n==[^=]", wt[i+4:])
    end = i + 4 + (nh.start() if nh else 0)
    sec = wt[i:end]
    # 'nat fs g player' のみを取る（Recent call-up は除外）
    bodies = extract_templates(sec, "nat fs g player")
    players = [parse_player(b) for b in bodies]
    print(f"取得: {len(players)}名")

    squads_path = DATA / "squads.json"
    sq = json.loads(squads_path.read_text(encoding="utf-8"))
    sq["ENG"] = {
        "tla": "ENG",
        "ja": "イングランド",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "as_of": "2026-03-31（Wikipedia情報）",
        "source": "https://en.wikipedia.org/wiki/England_national_football_team",
        "_note": "worldcdb.com に無いため Wikipedia から自動取得。日本語名は暫定で英名表示。身長体重なし。",
        "players": players,
    }
    sq["_updated"] = datetime.now(JST).isoformat()
    squads_path.write_text(json.dumps(sq, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✓ ENG スカッドを書き込み")


if __name__ == "__main__":
    main()
