#!/usr/bin/env python3
"""
second_team.py
トップチームではなくセカンドチームでプレー中の選手（players.json の second_team）の選手ページを、
今のプレー先が分かる形に直す共通処理。generate_player_pages.py / generate_player_pages_en.py から使う。
- 見出しの所属・リーグを、セカンドチーム名と「ドイツ4部」などのリーグ名にする
- 説明文・構造化データの所属名も同じにする
- トップチームの試合予定・順位は出さない（作り手側で空にして呼ぶ）
"""
import html as _html
import json
import re


def _e(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def is_second_team(player: dict) -> bool:
    return bool(player.get("second_team"))


def page_player(player: dict, lang: str = "ja") -> dict:
    """ページを作るときに渡す選手データ（英語ページはメモを英語に差し替える）。"""
    st = player.get("second_team") or {}
    if lang == "en":
        return dict(player, note=st.get("note_en", ""))
    return dict(player)


def adjust_html(page: str, player: dict, lang: str = "ja") -> str:
    st = player.get("second_team") or {}
    if not st:
        return page
    if lang == "en":
        old_tag = f'🏟️ {_e(player.get("club_en"))}</span>'
        new_tag = f'🏟️ {_e(st.get("team_en"))}</span>'
        new_lg = f'🏆 {_e(st.get("league_en"))}</span>'
        desc = (f'{player.get("name_en", "")} plays for {st.get("team_en", "")}, the second team of '
                f'{st.get("parent_en") or player.get("club_en", "")}, in the {st.get("league_en", "")} — not in the Bundesliga. '
                f'Profile and stats.')
        team_name, alt_name = st.get("team_en", ""), st.get("team_ja", "")
        no_match = '<p class="no-data">Second-team (4th tier) matches are not covered on this site.</p>'
        page = page.replace('<p class="no-data">Match data is being fetched.</p>', no_match)
    else:
        old_tag = f'🏟️ {_e(player.get("club_ja"))}（{_e(player.get("club_en"))}）</span>'
        new_tag = f'🏟️ {_e(st.get("team_ja"))}（{_e(st.get("team_en"))}）</span>'
        new_lg = f'🏆 {_e(st.get("league_ja"))}</span>'
        desc = (f'{player.get("name_ja", "")}（{player.get("position", "")}）は、'
                f'{st.get("parent_ja") or player.get("club_ja", "")}のセカンドチーム「{st.get("team_ja", "")}」でプレー。'
                f'リーグは{st.get("league_ja", "")}で、ブンデスリーガ（1部）ではありません。プロフィールと成績。')
        team_name, alt_name = st.get("team_ja", ""), st.get("team_en", "")
        no_match = '<p class="no-data">セカンドチーム（4部）の試合は、このサイトでは載せていません。</p>'
        page = page.replace('<p class="no-data">試合データを取得中です。</p>', no_match)
    page = page.replace(old_tag, new_tag, 1)
    page = re.sub(r'🏆 [^<]*</span>', lambda m: new_lg, page, count=1)
    for prop in ('name="description"', 'property="og:description"', 'name="twitter:description"'):
        page = re.sub(r'(<meta ' + re.escape(prop) + r' content=")[^"]*(")',
                      lambda m: m.group(1) + _e(desc) + m.group(2), page, count=1)

    def fix_ld(m):
        try:
            data = json.loads(m.group(2))
        except ValueError:
            return m.group(0)
        if isinstance(data, dict) and data.get("@type") == "Person" and isinstance(data.get("memberOf"), dict):
            data["memberOf"]["name"] = team_name
            data["memberOf"]["alternateName"] = alt_name
            return m.group(1) + json.dumps(data, ensure_ascii=False, indent=2) + m.group(3)
        return m.group(0)
    page = re.sub(r'(<script type="application/ld\+json">\s*)(.*?)(\s*</script>)', fix_ld, page, flags=re.S)
    return page
