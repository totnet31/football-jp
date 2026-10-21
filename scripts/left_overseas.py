#!/usr/bin/env python3
"""
left_overseas.py
海外クラブを離れて日本に戻った選手（players.json の left_overseas）の選手ページを
「残す」ための共通処理。generate_player_pages.py / generate_player_pages_en.py から使う。
- ページは前の所属（海外）のデータで作り、試合予定・順位は出さない
- 先頭に「現在はJリーグ（◯◯）に所属」の一文を出し、見出しの所属・説明文・構造化データを今の所属に直す
"""
import html as _html
import json
import re
from pathlib import Path

PLAYERS_JSON = Path(__file__).resolve().parent.parent / "data" / "players.json"


def load_left() -> list:
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        return json.load(f).get("left_overseas", []) or []


def _e(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def banner_text(entry: dict, lang: str = "ja") -> str:
    if lang == "en":
        return entry.get("left_note_en", "")
    return (f"現在はJリーグ（{entry.get('current_league_ja', '')}・{entry.get('current_club_ja', '')}）に所属しています。"
            f"{entry.get('left_note', '')}。このページの成績は{entry.get('club_ja', '')}時代のものです。")


def adjust_html(page: str, entry: dict, lang: str = "ja") -> str:
    """作り手が出したHTMLを、今の所属が分かる形に直す。"""
    if lang == "en":
        old_tag = f'🏟️ {_e(entry.get("club_en"))}</span>'
        new_tag = f'🏟️ {_e(entry.get("current_club_en"))}</span>'
        new_lg = f'🏆 {_e(entry.get("current_league_en"))}</span>'
        desc = (f'{entry.get("name_en", "")} now plays for {entry.get("current_club_en", "")} '
                f'({entry.get("current_league_en", "")}). Profile and stats from his time at {entry.get("club_en", "")}.')
        team_name = entry.get("current_club_en", "")
    else:
        old_tag = f'🏟️ {_e(entry.get("club_ja"))}（{_e(entry.get("club_en"))}）</span>'
        new_tag = f'🏟️ {_e(entry.get("current_club_ja"))}（{_e(entry.get("current_club_en"))}）</span>'
        new_lg = f'🏆 {_e(entry.get("current_league_ja"))}</span>'
        desc = (f'{entry.get("name_ja", "")}は現在Jリーグ（{entry.get("current_club_ja", "")}）に所属。'
                f'{entry.get("left_note", "")}。{entry.get("club_ja", "")}時代の成績とプロフィール。')
        team_name = entry.get("current_club_ja", "")
    page = page.replace(old_tag, new_tag, 1)
    page = page.replace('<p class="no-data">試合データを取得中です。</p>',
                        '<p class="no-data">Jリーグの試合は、このサイトでは載せていません。</p>', 1)
    page = page.replace('<p class="no-data">Match data is being fetched.</p>',
                        '<p class="no-data">J.League matches are not covered on this site.</p>', 1)
    page = re.sub(r'🏆 [^<]*</span>', new_lg, page, count=1)
    page = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + _e(desc) + m.group(2), page, count=1)
    page = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + _e(desc) + m.group(2), page, count=1)

    def fix_ld(m):
        try:
            data = json.loads(m.group(2))
        except ValueError:
            return m.group(0)
        if isinstance(data, dict) and data.get("@type") == "Person":
            data["memberOf"] = {"@type": "SportsTeam", "name": team_name, "sport": "Soccer"}
            return m.group(1) + json.dumps(data, ensure_ascii=False, indent=2) + m.group(3)
        return m.group(0)
    page = re.sub(r'(<script type="application/ld\+json">\s*)(.*?)(\s*</script>)', fix_ld, page, flags=re.S)
    return page
