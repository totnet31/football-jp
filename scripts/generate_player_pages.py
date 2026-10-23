#!/usr/bin/env python3
"""
generate_player_pages.py
日本人選手プロフィールページを自動生成するスクリプト。
出力先: players/{slug}/index.html
使い方: python3 scripts/generate_player_pages.py
"""

from utils import is_result_pending, fix_unplayed_finished, openligadb_matches_for_names
from second_team import is_second_team, page_player, adjust_html as adjust_second_team
import json
import os
import re
import sys
from pathlib import Path

# ============================
# パス設定
# ============================
REPO_ROOT = Path(__file__).parent.parent
PLAYERS_JSON = REPO_ROOT / "data" / "players.json"
MATCHES_JSON = REPO_ROOT / "data" / "matches.json"
SCORERS_JSON = REPO_ROOT / "data" / "scorers.json"
MATCH_EVENTS_JSON = REPO_ROOT / "data" / "match_events.json"
STANDINGS_JSON = REPO_ROOT / "data" / "standings.json"
PLAYER_STATS_JSON = REPO_ROOT / "data" / "player_stats.json"
PLAYER_INFO_JSON = REPO_ROOT / "data" / "player_info.json"
BROADCASTERS_JSON = REPO_ROOT / "data" / "broadcasters.json"
PLAYER_VIDEOS_JSON = REPO_ROOT / "data" / "player_videos.json"
OUTPUT_DIR = REPO_ROOT / "players"

GA4_ID = "G-39G8CVXRW0"
SITE_NAME = "football-jp"
SITE_URL = "https://football-jp.com"


# 選手ページの説明文に出す人数（main() で players.json の数を入れる）
TOTAL_PLAYERS = 0


# ============================
# broadcaster サービスマップ
# ============================

def load_services() -> dict:
    """broadcasters.json の services セクションを返す。"""
    if not BROADCASTERS_JSON.exists():
        return {}
    with open(BROADCASTERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("services", {})


def bc_brand_class(name: str) -> str:
    """サービス名 → CSS クラス名変換。"""
    n = (name or "").lower()
    if "wowow" in n:
        return "bc-wowow"
    if "dazn" in n:
        return "bc-dazn"
    if "lemino" in n:
        return "bc-lemino"
    if "abema" in n:
        return "bc-abema"
    if "u-next" in n or "unext" in n:
        return "bc-unext"
    if "bs10" in n:
        return "bc-bs10"
    return "bc-default"


def build_utm_url(base_url: str, page_type: str, page_id: str, league: str = "") -> str:
    """UTMパラメータ付きURLを返す。"""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    if not base_url:
        return ""
    params = {
        "utm_source": "football-jp",
        "utm_medium": f"{page_type}_page",
        "utm_content": page_id,
    }
    if league:
        params["utm_campaign"] = league
    sep = "&" if "?" in base_url else "?"
    return base_url + sep + urlencode(params)


def build_bc_tag(broadcaster: dict, services: dict, page_type: str, page_id: str, league: str = "") -> str:
    """配信サービス bc-tag HTML を生成する。"""
    name = broadcaster.get("name", "")
    svc = services.get(name, {})
    # affiliate_url があればそれを、なければ url を使用
    base_url = svc.get("affiliate_url") or svc.get("url") or broadcaster.get("url") or ""
    if not base_url:
        # url が無い場合はテキストのみ
        brand_cls = bc_brand_class(name)
        return f'<span class="bc-tag {esc(brand_cls)}">{esc(name)}</span>'

    utm_url = build_utm_url(base_url, page_type, page_id, league)
    brand_cls = bc_brand_class(name)
    logo_file = svc.get("logo", "")
    logo_html = ""
    if logo_file:
        logo_html = f'<img class="bc-logo" src="/assets/broadcasters/{esc(logo_file)}" alt="" width="16" height="16">'

    return (
        f'<a class="bc-tag {esc(brand_cls)}" href="{esc(utm_url)}" '
        f'target="_blank" rel="noopener" '
        f'data-svc="{esc(name)}" data-pagetype="{esc(page_type)}" data-pageid="{esc(page_id)}" '
        f'onclick="trackAffClick(this)">'
        f'{logo_html}{esc(name)}'
        f'</a>'
    )


# ============================
# 「次の試合・どこで見れる」欄（2026-10-22 追加）
# 配信先は league_guides.json の「どこで見られる？」欄（公式ページで確かめた分だけ）から出す。
# 欄が無い大会・リーグ（ブンデスリーガ2部・リーグ・ドゥ・代表戦など）は「配信先は確認中」とし、推測で書かない。
# 成果報酬リンクは、欄の url_service が broadcasters.json の services で affiliate_url を持つときだけ付く。
# 次の試合は作るたびに matches.json から選び直す（1日3回の自動更新で古くならない。日付は手で書かない）。
# ============================
LEAGUE_GUIDES_JSON = REPO_ROOT / "data" / "league_guides.json"
NEXT_WATCH_SHOW = 2      # 最初に見せる試合の数
NEXT_WATCH_SPARE = 1     # 作ったあとに試合が終わったとき用の控え（画面の中で入れ替える）
_WD_JA = ["月", "火", "水", "木", "金", "土", "日"]

# ============================
# 「今季成績・次の試合・どこで見れるか」型の試し（2026-10-23・strategy_20261023/plan.md 案1）
# ここに入れた slug の日本語ページだけ、title・説明文・見出しをこの型にし、
# 上のほうに「今季の成績」「次の試合」「どこで見れる？」を並べる。ほかの選手は今までどおり。
# 効果を見てから人を増やす（slug を足すだけで効く）。
# ============================
TITLE_TRIAL_SLUGS = {"takefusa-kubo"}
PLAYER_STATS_CUR_JSON = REPO_ROOT / "data" / "player_stats_2026-27.json"  # 2026-27（今季）の数字
CUR_STATS_MAX_AGE_DAYS = 14  # 「○日時点」がこれより古ければ出さない（リーグページと同じ）


def load_cur_stats() -> dict:
    if not PLAYER_STATS_CUR_JSON.exists():
        return {}
    with open(PLAYER_STATS_CUR_JSON, encoding="utf-8") as f:
        return json.load(f).get("stats", {})


def get_cur_season_stats(player: dict, cur_stats: dict):
    """今季（2026-27）の数字。Wikipedia の as_of が新しいものだけ。無ければ None（推測で埋めない）。"""
    from datetime import datetime, timezone, timedelta
    e = cur_stats.get(player.get("name_en", ""))
    if not e or not e.get("as_of"):
        return None
    jst = timezone(timedelta(hours=9))
    try:
        as_of = datetime.strptime(e["as_of"], "%Y-%m-%d").replace(tzinfo=jst)
    except ValueError:
        return None
    if (datetime.now(jst) - as_of).days > CUR_STATS_MAX_AGE_DAYS:
        return None
    return {"apps": e.get("apps"), "goals": e.get("goals"),
            "total_apps": e.get("total_apps"), "total_goals": e.get("total_goals"),
            "as_of": as_of, "wiki_page": e.get("wiki_page", ""),
            "src": "Wikipedia（選手ページ）" if e.get("source") == "wikipedia_player_page" else "Wikipedia（クラブの今季ページ）"}


def build_cur_stats_section(player: dict, cur: dict) -> str:
    name_ja = player.get("name_ja", "")
    league_ja = player.get("league_ja", "")
    if not cur:
        return f"""
    <section class="player-section pt-stats" id="season-stats">
      <h3>📊 {esc(name_ja)}の今季（2026-27）成績</h3>
      <p class="no-data">今季の出場・得点の数字は、まだこのサイトに入っていません。</p>
    </section>"""
    def v(x):
        return "—" if x is None else str(x)
    wiki = ""
    if cur.get("wiki_page"):
        wiki = f' <a href="https://en.wikipedia.org/wiki/{esc(cur["wiki_page"].replace(" ", "_"))}" target="_blank" rel="noopener">→</a>'
    return f"""
    <section class="player-section pt-stats" id="season-stats">
      <h3>📊 {esc(name_ja)}の今季（2026-27）成績</h3>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-label">{esc(league_ja)} 出場</div><div class="stat-value">{esc(v(cur.get("apps")))}</div></div>
        <div class="stat-card"><div class="stat-label">{esc(league_ja)} ゴール</div><div class="stat-value">{esc(v(cur.get("goals")))}</div></div>
        <div class="stat-card"><div class="stat-label">全大会 出場</div><div class="stat-value">{esc(v(cur.get("total_apps")))}</div></div>
        <div class="stat-card"><div class="stat-label">全大会 ゴール</div><div class="stat-value">{esc(v(cur.get("total_goals")))}</div></div>
      </div>
      <div class="stats-source">{cur["as_of"].month}月{cur["as_of"].day}日の試合まで・出典：{esc(cur["src"])}{wiki}（全大会＝リーグ戦・国内カップ・欧州の大会の合計）</div>
    </section>"""


def build_where_section(player: dict, slug: str, upcoming: list, guides: dict, bc_services: dict) -> tuple:
    """「どこで見れる？」欄（大会ごと）。返り値：(html, [(大会名, [配信名...])...])"""
    name_ja = player.get("name_ja", "")
    seen, blocks, summary = set(), [], []
    comps = [(m.get("competition_id"), m.get("competition_ja", "")) for _, m in upcoming]
    comps.insert(0, (player.get("competition_id"), player.get("league_ja", "")))
    for cid, cja in comps:
        if not cja or cja in seen:
            continue
        seen.add(cja)
        watch = find_watch_guide(guides, cid, cja)
        if watch.get("services"):
            svc_html, _ = _watch_services_html(watch, bc_services, slug)
            summary.append((cja, [sv.get("name", "") for sv in watch["services"]]))
        else:
            svc_html = _unconfirmed_html()
        blocks.append(f'<div class="nw-card nw-card-league"><div class="nw-watch-h">{esc(cja)}</div>{svc_html}</div>')
    html = f"""
    <section class="player-section nw-section" id="where-to-watch">
      <h3>📺 {esc(name_ja)}の試合はどこで見れる？</h3>
      <div class="nw-cards">{"".join(blocks)}</div>
      <p class="nw-note">今季このサイトに日程が入っている大会ごとの案内です。配信先・料金は各サービスの公式ページで確かめた日付つきで載せています。その試合を必ず中継するとは限りません。</p>
    </section>"""
    return html, summary


# 取り出し方は scripts/watch_source.py に共通化（クラブ・リーグページ・matches.json と同じ。2026-10-22）
from watch_source import load_league_guides, find_watch_guide, build_watch_cell, affiliate_for  # noqa: E402


def _parse_ko(kickoff: str):
    from datetime import datetime, timezone, timedelta
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
    return dt.astimezone(timezone(timedelta(hours=9)))


def get_upcoming_matches(club_matches: list, now=None) -> list:
    """まだ終わっていない試合（始まって2時間以内のものを含む）を古い順に。"""
    from datetime import datetime, timezone, timedelta
    now = now or datetime.now(timezone(timedelta(hours=9)))
    out = []
    for m in club_matches:
        if m.get("status") == "FINISHED":
            continue
        dt = _parse_ko(m.get("kickoff_jst", ""))
        if dt is None or dt < now - timedelta(hours=2):
            continue
        out.append((dt, m))
    out.sort(key=lambda x: x[0])
    return out


def _jp_side(m: dict, name_ja: str):
    """試合の japanese_players に選手の名前があれば、その side（"home"/"away"）を返す。無ければ None。"""
    for jp in m.get("japanese_players") or []:
        if jp.get("name_ja") == name_ja:
            return jp.get("side")
    return None


def get_next_watch_matches(player: dict, matches: list, club_matches: list) -> list:
    """「次の試合」欄の候補の試合。
    クラブ番号（club_id）がある選手は、これまでどおりクラブの全試合から選ぶ。
    クラブ番号が無い選手（ベルギー1部・ブンデス2部など、football-data.org に無いクラブ）は、
    試合データの「出場する日本人選手」（japanese_players）に名前が入っている試合から選ぶ
    （EL・ECL の試合は fetch_uefa_secondary.py がクラブ名で選手を付けている。1日3回の自動更新で付け直される）。2026-10-22"""
    if player.get("club_id"):
        return club_matches
    name_ja = player.get("name_ja", "")
    if not name_ja:
        return []
    return [m for m in matches if _jp_side(m, name_ja) in ("home", "away")]


def _watch_services_html(watch: dict, bc_services: dict, slug: str) -> tuple:
    """配信先のカード。返り値：(html, 報酬リンクが付いたか)"""
    has_aff = False
    rows = []
    for sv in watch.get("services") or []:
        name = sv.get("name", "")
        href = sv.get("url", "")
        rel = "nofollow noopener"
        aff = affiliate_for(sv, bc_services)
        if aff:
            href, rel = aff, "sponsored nofollow noopener"
            has_aff = True
        link = ""
        if href:
            link = (f'<a class="nw-link" href="{esc(href)}" target="_blank" rel="{rel}" '
                    f'data-svc="{esc(name)}" data-pagetype="player_next_watch" data-pageid="{esc(slug)}" '
                    f'onclick="trackAffClick(this)">{esc(name)}の公式ページへ</a>')
        detail = ""
        if sv.get("scope"):
            detail += f'<p class="nw-scope">{esc(sv["scope"])}</p>'
        if sv.get("price"):
            detail += f'<p class="nw-price">料金：{esc(sv["price"])}</p>'
        if sv.get("checked"):
            detail += f'<p class="nw-src">公式ページで確認：{esc(sv["checked"])}</p>'
        rows.append(f'<div class="nw-svc"><div class="nw-svc-name">{esc(name)}</div>{detail}{link}</div>')
    more = watch.get("more_link")
    if more and more.get("href"):
        rows.append(f'<p class="nw-more"><a href="{esc(more["href"])}">{esc(more.get("text", "見る方法"))} →</a></p>')
    return "".join(rows), has_aff


def build_table_watch_cell(guides: dict, bc_services: dict, competition_id, competition_ja: str, slug: str) -> tuple:
    """「直近の試合」表の配信の列（2026-10-22）。上の「次の試合・どこで見れる」欄と同じ
    league_guides.json の欄から出す（共通の取り出し方：scripts/watch_source.py）。
    返り値：(html, 報酬リンクの数)"""
    return build_watch_cell(guides, bc_services, competition_id, competition_ja, "player_table", slug)


TABLE_WATCH_STATS = {"affiliate_links": 0, "unconfirmed_rows": 0}


def _unconfirmed_html() -> str:
    return ('<p class="nw-unconfirmed">配信先は確認中です（日本の配信サービスの公式ページで確かめられた分だけを載せています）。</p>')


def build_next_watch_section(player: dict, slug: str, upcoming: list, guides: dict, bc_services: dict,
                             compact: bool = False) -> tuple:
    """選手ページ上部の「次の試合・どこで見れる」欄。
    返り値：(html, 情報) 情報＝{"has_match", "unconfirmed", "affiliate"}"""
    name_ja = player.get("name_ja", "")
    club_id = player.get("club_id")
    info = {"has_match": False, "unconfirmed": False, "affiliate": False}
    cards = []
    for i, (dt, m) in enumerate(upcoming[:NEXT_WATCH_SHOW + NEXT_WATCH_SPARE]):
        if club_id:
            is_home = m.get("home_id") == club_id
        else:
            is_home = _jp_side(m, name_ja) == "home"
        opp = m.get("away_ja", "") if is_home else m.get("home_ja", "")
        venue = "ホーム" if is_home else "アウェイ"
        comp = m.get("competition_ja", "")
        when = f'{dt.month}月{dt.day}日（{_WD_JA[dt.weekday()]}）{dt.strftime("%H:%M")}'
        watch = find_watch_guide(guides, m.get("competition_id"), comp)
        if watch.get("services"):
            svc_html, aff = _watch_services_html(watch, bc_services, slug)
        else:
            svc_html, aff = _unconfirmed_html(), False
        if compact:
            # 試しの型：配信先は下の「どこで見れる？」欄にまとめ、ここは名前だけ
            names = "・".join(sv.get("name", "") for sv in watch.get("services") or [])
            svc_html = (f'<p class="nw-scope">{esc(names)}（<a href="#where-to-watch">くわしくは下へ</a>）</p>'
                        if names else _unconfirmed_html())
        visible = i < NEXT_WATCH_SHOW
        if visible:
            info["has_match"] = True
            if not watch.get("services"):
                info["unconfirmed"] = True
            if aff:
                info["affiliate"] = True
        label = "次の試合" if i == 0 else "その次の試合"
        cards.append(
            f'<div class="nw-card{"" if visible else " nw-spare"}" data-ko="{esc(dt.isoformat())}">'
            f'<div class="nw-label"><span class="nw-label-text">{label}</span><span class="nw-when-rel"></span></div>'
            f'<div class="nw-when">{esc(when)}<span class="nw-jst">（日本時間）</span></div>'
            f'<div class="nw-match">vs {esc(opp)}<span class="nw-venue">{venue}</span></div>'
            f'<div class="nw-comp">{esc(comp)}</div>'
            f'<div class="nw-watch-h">日本で見られるところ</div>'
            f'{svc_html}'
            f'</div>'
        )

    league_ja = player.get("league_ja", "")
    if not cards:
        # 次の試合が無い（オフ・日程未発表・このサイトにリーグの日程が無い）
        if club_id:
            msg = "次の試合の日程は、まだこのサイトに入っていません。日程が出たら、1日3回の自動更新でここに載ります。"
        else:
            msg = f"{league_ja}の試合日程は、まだこのサイトに載せていません。"
        watch = find_watch_guide(guides, None, league_ja)
        if watch.get("services"):
            svc_html, aff = _watch_services_html(watch, bc_services, slug)
            info["affiliate"] = aff
        else:
            svc_html = _unconfirmed_html()
            info["unconfirmed"] = True
        body = (f'<p class="nw-none">{esc(msg)}</p>'
                f'<div class="nw-card nw-card-league"><div class="nw-watch-h">{esc(league_ja)}を日本で見られるところ</div>{svc_html}</div>')
    else:
        body = "".join(cards) + '<p class="nw-none nw-none-js" hidden>次の試合の日程は、まだこのサイトに入っていません。日程が出たら、1日3回の自動更新でここに載ります。</p>'

    note = "" if not cards else '<p class="nw-note">リーグ戦と欧州の大会（CL・EL・ECL）の日程から出しています。国内のカップ戦などは入っていないことがあります。配信先は大会ごとの案内で、その試合を必ず中継するとは限りません。</p>'
    html = f"""
    <section class="player-section nw-section" id="next-watch">
      <h3>{"📅" if compact else "📺"} {esc(name_ja)}の次の試合{"（日本時間）" if compact else "・どこで見れる"}</h3>
      <div class="nw-cards">{body}</div>
      {note}
    </section>"""
    return html, info


NEXT_WATCH_CSS = """
    .nw-section { background: #f5f8ff; }
    .nw-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
    .nw-card { background: #fff; border: 1px solid var(--c-border, #e5e7eb); border-radius: 8px; padding: 12px 14px; min-width: 0; overflow-wrap: anywhere; }
    .nw-spare { display: none; }
    .nw-label { font-size: 12px; font-weight: 700; color: var(--c-accent, #0047ab); display: flex; gap: 8px; align-items: center; }
    .nw-when-rel { background: #0047ab; color: #fff; border-radius: 10px; padding: 0 8px; font-size: 11px; }
    .nw-when-rel:empty { display: none; }
    .nw-when { font-size: 18px; font-weight: 700; margin-top: 4px; }
    .nw-jst { font-size: 11px; font-weight: 400; color: #666; margin-left: 2px; }
    .nw-match { font-size: 15px; font-weight: 700; margin-top: 2px; }
    .nw-venue { font-size: 11px; font-weight: 400; color: #666; margin-left: 6px; }
    .nw-comp { font-size: 12px; color: #555; margin-top: 2px; }
    .nw-watch-h { font-size: 12px; font-weight: 700; margin: 10px 0 6px; padding-top: 8px; border-top: 1px dashed var(--c-border, #e5e7eb); }
    .nw-card-league .nw-watch-h { border-top: none; padding-top: 0; margin-top: 0; }
    .nw-svc { margin-bottom: 10px; }
    .nw-svc-name { font-weight: 700; font-size: 14px; }
    .nw-scope, .nw-price { font-size: 12px; color: #444; margin: 2px 0; line-height: 1.5; }
    .nw-src { font-size: 11px; color: #888; margin: 2px 0; }
    .nw-link { display: inline-block; margin-top: 4px; padding: 6px 12px; border-radius: 6px; background: var(--c-accent, #0047ab); color: #fff; font-size: 13px; font-weight: 700; text-decoration: none; }
    .nw-more { font-size: 13px; margin: 6px 0 0; }
    .nw-more a { color: var(--c-accent, #0047ab); }
    .nw-unconfirmed { font-size: 13px; color: #555; margin: 0; }
    .nw-none { font-size: 13px; color: #444; margin: 0 0 10px; }
    .nw-note { font-size: 11px; color: #888; margin: 10px 0 0; line-height: 1.5; }
"""

NEXT_WATCH_JS = """
(function() {
  var sec = document.getElementById('next-watch');
  if (!sec) return;
  var now = Date.now();
  var cards = Array.prototype.slice.call(sec.querySelectorAll('.nw-card[data-ko]'));
  var shown = 0;
  cards.forEach(function(c) {
    var ko = Date.parse(c.getAttribute('data-ko'));
    if (isNaN(ko)) return;
    if (now > ko + 2 * 3600 * 1000) { c.style.display = 'none'; return; }
    if (shown >= {show}) { c.style.display = 'none'; return; }
    c.style.display = 'block';
    var lt = c.querySelector('.nw-label-text');
    if (lt) lt.textContent = shown === 0 ? '次の試合' : 'その次の試合';
    shown++;
    var rel = c.querySelector('.nw-when-rel');
    if (!rel) return;
    if (now >= ko) { rel.textContent = '試合中'; return; }
    var j = function(t) { var d = new Date(t + 9 * 3600 * 1000); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()); };
    var days = Math.round((j(ko) - j(now)) / 86400000);
    rel.textContent = days === 0 ? '今日' : (days === 1 ? '明日' : 'あと' + days + '日');
  });
  if (cards.length && shown === 0) {
    var n = sec.querySelector('.nw-none-js');
    if (n) n.hidden = false;
  }
})();
""".replace("{show}", str(NEXT_WATCH_SHOW))


# ============================
# slug生成
# ============================
def make_slug(name_en: str) -> str:
    """英語名をURLスラグに変換する。"""
    s = name_en.lower()
    s = s.replace("'", "").replace(".", "")
    # 特殊文字をASCII化
    replacements = {
        "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "é": "e", "è": "e",
        "ê": "e", "ç": "c", "ã": "a", "á": "a", "à": "a", "ó": "o",
        "ô": "o", "ú": "u", "í": "i", "ï": "i", "ō": "o", "ū": "u",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def make_unique_slugs(players: list) -> dict:
    """選手リストからユニークなslug辞書を生成する。index→slug"""
    slug_map = {}
    used = {}
    for i, p in enumerate(players):
        base = make_slug(p.get("name_en", f"player-{i}"))
        if base not in used:
            used[base] = 1
            slug_map[i] = base
        else:
            used[base] += 1
            slug_map[i] = f"{base}-{used[base]}"
    return slug_map


# ============================
# HTML エスケープ
# ============================
def esc(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ============================
# データ前処理
# ============================
def load_data():
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players_raw = json.load(f)
    players = players_raw.get("players", [])

    with open(MATCHES_JSON, encoding="utf-8") as f:
        matches_raw = json.load(f)
    matches = matches_raw.get("matches", [])
    fix_unplayed_finished(matches)  # 開始前なのに「終了」になっている試合は予定に戻す（データは書き換えない）
    # match_id → match 辞書
    matches_dict = {str(m["id"]): m for m in matches}

    with open(SCORERS_JSON, encoding="utf-8") as f:
        scorers_raw = json.load(f)
    scorers_comps = scorers_raw.get("competitions", {})

    with open(MATCH_EVENTS_JSON, encoding="utf-8") as f:
        events_raw = json.load(f)
    events = events_raw.get("events", {})  # match_id(str) → list of events

    with open(STANDINGS_JSON, encoding="utf-8") as f:
        standings_raw = json.load(f)
    standings_comps = standings_raw.get("competitions", {})

    # player_stats.json（Wikipedia統計、任意）
    player_stats = {}
    if PLAYER_STATS_JSON.exists():
        with open(PLAYER_STATS_JSON, encoding="utf-8") as f:
            ps_raw = json.load(f)
        player_stats = ps_raw.get("stats", {})
        print(f"  player_stats.json: {len(player_stats)} 選手分")

    # player_info.json（身長・体重・キャリア等、任意）
    player_info = {}
    if PLAYER_INFO_JSON.exists():
        with open(PLAYER_INFO_JSON, encoding="utf-8") as f:
            player_info = json.load(f)
        print(f"  player_info.json: {len(player_info)} 選手分")

    # player_videos.json（選手別ゴール集動画、任意）
    player_videos = {}
    if PLAYER_VIDEOS_JSON.exists():
        try:
            with open(PLAYER_VIDEOS_JSON, encoding="utf-8") as f:
                pv_raw = json.load(f)
            player_videos = pv_raw.get("players", {})
            print(f"  player_videos.json: {len(player_videos)} 選手分")
        except Exception:
            pass

    services = load_services()
    print(f"  サービス数: {len(services)}")

    return players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info, player_videos


def get_player_wiki_stats(player: dict, player_stats: dict) -> dict:
    """player_stats.json（Wikipediaソース）から選手統計を取得する。"""
    name_en = player.get("name_en", "")
    if not name_en:
        return {}
    entry = player_stats.get(name_en)
    if entry:
        return {
            "goals": entry.get("goals", 0),
            "assists": entry.get("assists", 0),
            "penalties": 0,
            "played": entry.get("apps", 0),
            "source": "wikipedia",
        }
    return {}


def get_player_scorer_stats(player: dict, scorers_comps: dict) -> dict:
    """選手のスコアラー統計を取得する。"""
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")
    name_ja = player.get("name_ja", "")

    if not comp_id or comp_id not in scorers_comps:
        return {}

    comp_data = scorers_comps[comp_id]
    scorers = comp_data.get("scorers", [])

    # 名前の一部マッチング（player_nameがfull nameの一部として含まれるか）
    for s in scorers:
        scorer_name = s.get("player_name", "")
        # 名前の一部でマッチング
        en_parts = name_en.lower().split()
        scorer_parts = scorer_name.lower().split()
        # 姓でマッチング（最後の単語）
        if en_parts and scorer_parts:
            last_name_en = en_parts[-1]
            last_name_scorer = scorer_parts[-1]
            if last_name_en == last_name_scorer:
                # チームIDも確認
                if club_id and s.get("team_id") == club_id:
                    return {
                        "goals": s.get("goals", 0),
                        "assists": s.get("assists", 0),
                        "penalties": s.get("penalties", 0),
                        "played": s.get("playedMatches", 0),
                    }

    return {}


def get_player_goals(player: dict, events: dict, matches_dict: dict, known_ja: set = None) -> list:
    """選手のゴールイベントリストを取得する（最大10件）。
    known_ja：追いかけている日本人選手の和名の一覧。記録の和名がこの中の誰かなら、その名前と一致するときだけ
    数える（苗字が同じ選手のゴールを取り違えないため。2026-10-23）"""
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    known_ja = known_ja or set()

    goal_events = []
    for match_id, evs in events.items():
        for ev in evs:
            if ev.get("type") == "goal" and ev.get("is_japanese"):
                ev_name_ja = ev.get("player_ja", "")
                ev_name_en = ev.get("player_en", "")
                if ev_name_ja in known_ja:
                    matched = ev_name_ja == name_ja
                    if matched:
                        match = matches_dict.get(match_id, {})
                        goal_events.append({
                            "match_id": match_id, "minute": ev.get("minute"),
                            "minute_raw": ev.get("minute_raw", ""), "note": ev.get("note", ""),
                            "home_ja": match.get("home_ja", ""), "away_ja": match.get("away_ja", ""),
                            "score": match.get("score", {}), "kickoff_jst": match.get("kickoff_jst", ""),
                            "competition_ja": match.get("competition_ja", ""), "side": ev.get("side", ""),
                        })
                    continue
                # 名前マッチング（名前の一部）
                matched = False
                if ev_name_ja and name_ja and ev_name_ja in name_ja:
                    matched = True
                if not matched and ev_name_ja and name_ja and name_ja in ev_name_ja:
                    matched = True
                # フルネームの姓でマッチング
                if not matched and ev_name_en and name_en:
                    en_last = name_en.split()[-1].lower() if name_en.split() else ""
                    ev_last = ev_name_en.split()[-1].lower() if ev_name_en.split() else ""
                    if en_last and ev_last and en_last == ev_last:
                        matched = True

                if matched:
                    match = matches_dict.get(match_id, {})
                    goal_events.append({
                        "match_id": match_id,
                        "minute": ev.get("minute"),
                        "minute_raw": ev.get("minute_raw", ""),
                        "note": ev.get("note", ""),
                        "home_ja": match.get("home_ja", ""),
                        "away_ja": match.get("away_ja", ""),
                        "score": match.get("score", {}),
                        "kickoff_jst": match.get("kickoff_jst", ""),
                        "competition_ja": match.get("competition_ja", ""),
                        "side": ev.get("side", ""),
                    })

    # kickoff_jst でソート（新しい順）
    goal_events.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return goal_events[:10]


def get_club_matches(player: dict, matches: list) -> list:
    """選手所属クラブの全試合を取得する（新しい順）。"""
    club_id = player.get("club_id")
    if not club_id:
        # クラブ番号の無いブンデス2部の選手は、OpenLigaDB の試合を名前で選ぶ（2026-10-22）
        return [m for m, _side in openligadb_matches_for_names([player.get("name_ja")], matches)]

    club_matches = [
        m for m in matches
        if m.get("home_id") == club_id or m.get("away_id") == club_id
    ]
    # kickoff_jst でソート（新しい順）
    club_matches.sort(key=lambda x: x.get("kickoff_jst", ""), reverse=True)
    return club_matches


def get_club_highlights(player: dict, matches: list) -> list:
    """選手所属クラブの試合に紐付いたYouTube動画を最大10本返す（新しい順）。"""
    club_id = player.get("club_id")
    if not club_id:
        return []

    videos = []
    for m in sorted(matches, key=lambda x: x.get("kickoff_jst", ""), reverse=True):
        if m.get("home_id") != club_id and m.get("away_id") != club_id:
            continue
        for h in m.get("highlights", []):
            vid = h.get("video_id", "")
            if not vid:
                continue
            videos.append({
                "video_id": vid,
                "url": h.get("url", f"https://www.youtube.com/watch?v={vid}"),
                "title": h.get("title", ""),
                "channel": h.get("broadcaster", ""),
                "published": m.get("kickoff_jst", ""),
            })
            if len(videos) >= 10:
                return videos
    return videos


def get_club_standing(player: dict, standings_comps: dict) -> dict:
    """選手所属クラブのリーグ順位を取得する。"""
    comp_id = str(player.get("competition_id", ""))
    club_id = player.get("club_id")

    if not comp_id or not club_id or comp_id not in standings_comps:
        return {}

    comp_data = standings_comps[comp_id]
    for standing_group in comp_data.get("standings", []):
        if standing_group.get("type") == "TOTAL":
            for entry in standing_group.get("table", []):
                if entry.get("team_id") == club_id:
                    return {
                        "position": entry.get("position"),
                        "points": entry.get("points"),
                        "played": entry.get("playedGames"),
                        "won": entry.get("won"),
                        "draw": entry.get("draw"),
                        "lost": entry.get("lost"),
                        "goals_for": entry.get("goalsFor"),
                        "goals_against": entry.get("goalsAgainst"),
                        "total_teams": len(standing_group.get("table", [])),
                        "league_ja": comp_data.get("name_ja", ""),
                    }
    return {}


# ============================
# 個別ページHTML生成
# ============================
def get_related_players(player: dict, all_players: list, slug_map: dict) -> list:
    """同じ club_id の他の日本人選手を最大5名返す。"""
    club_id = player.get("club_id")
    name_en = player.get("name_en", "")
    if not club_id:
        return []
    related = []
    for i, p in enumerate(all_players):
        if p.get("club_id") == club_id and p.get("name_en") != name_en:
            related.append({
                "name_ja": p.get("name_ja", ""),
                "name_en": p.get("name_en", ""),
                "position": p.get("position", ""),
                "slug": slug_map.get(i, make_slug(p.get("name_en", ""))),
            })
    return related[:5]


def calc_age(birth_date_str: str) -> str:
    """生年月日文字列（YYYY-MM-DD）から年齢を計算する。"""
    if not birth_date_str:
        return ""
    try:
        from datetime import date
        y, m, d = birth_date_str.split("-")
        bd = date(int(y), int(m), int(d))
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return str(age)
    except Exception:
        return ""


def foot_ja(foot: str) -> str:
    """利き足を日本語に変換する。"""
    if foot == "right":
        return "右"
    if foot == "left":
        return "左"
    if foot == "both":
        return "両足"
    return foot or ""


TRIAL_CSS = """
    .pt-h1 { margin: 0; font-size: 1.5em; line-height: 1.3; }
    .pt-h1-sub { display: block; font-size: 0.6em; font-weight: 700; color: #444; margin-top: 4px; }
"""


def build_player_page(player: dict, slug: str, scorer_stats: dict,
                      goal_events: list, club_matches: list, standing: dict,
                      wiki_stats: dict = None, services: dict = None,
                      related_players: list = None,
                      player_info: dict = None,
                      highlights: list = None,
                      player_videos: list = None,
                      next_watch_html: str = "",
                      guides: dict = None,
                      trial: dict = None) -> str:
    if guides is None:
        guides = load_league_guides()
    name_ja = player.get("name_ja", "")
    name_en = player.get("name_en", "")
    position = player.get("position", "")
    club_ja = player.get("club_ja", "")
    club_en = player.get("club_en", "")
    league_ja = player.get("league_ja", "")
    note = player.get("note", "")

    title = f"{esc(name_ja)}（{esc(name_en)}）プロフィール｜football-jp"
    if trial:
        title = f"{name_ja}の今季成績・次の試合・どこで見れるか【2026-27】｜football-jp"

    # メタdesc生成（100-160字）
    goals_val = (wiki_stats or scorer_stats or {}).get("goals", 0) if (wiki_stats or scorer_stats) else 0
    played_val = (wiki_stats or scorer_stats or {}).get("played", 0) if (wiki_stats or scorer_stats) else 0
    if goals_val and played_val:
        season_word = "2025-26シーズン" if wiki_stats else "今シーズン"
        desc_raw = f"{name_ja}（{position}・{club_ja}）の試合スケジュール・最新成績・配信局情報を日本時間で確認。{season_word}{goals_val}ゴール・{played_val}試合出場。{league_ja}で活躍する日本人海外組の最新データ。三笘薫・久保建英ら{TOTAL_PLAYERS}名をまとめてチェックできる国内最速データベース。"
    else:
        desc_raw = f"{name_ja}（{position}・{club_ja}）の試合スケジュール・最新成績・配信局情報を日本時間でチェック。{league_ja}在籍の日本人海外組。三笘薫・久保建英ら全{TOTAL_PLAYERS}名の最新データをfootball-jpで一括確認。配信局・次の試合日程も掲載。"
    # 文字数調整（160字以内）
    if len(desc_raw) > 160:
        desc_raw = desc_raw[:157] + "…"
    desc = desc_raw
    if trial:
        cur = trial.get("cur")
        parts = [f"{name_ja}（{club_ja}）の2026-27シーズンの成績"]
        if cur:
            parts.append(f"（{league_ja}{cur.get('apps')}試合{cur.get('goals')}ゴール・全大会{cur.get('total_apps')}試合{cur.get('total_goals')}ゴール、{cur['as_of'].month}月{cur['as_of'].day}日時点）")
        parts.append("、次の試合の日本時間、どこで見れるか")
        if trial.get("where"):
            parts.append("（" + "／".join(f"{c}：{'・'.join(n)}" for c, n in trial["where"]) + "）")
        parts.append("をまとめています。")
        desc = "".join(parts)
        if len(desc) > 160:
            desc = desc[:157] + "…"

    canonical = f"{SITE_URL}/players/{slug}/"

    # Schema.org Person JSON-LD（強化版）
    schema_person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name_ja,
        "alternateName": name_en,
        "jobTitle": "Footballer",
        "nationality": "JP",
        "memberOf": {
            "@type": "SportsTeam",
            "name": club_ja,
            "alternateName": club_en,
            "sport": "Soccer",
            "url": f"{SITE_URL}/clubs/{make_slug(club_en)}/"
        },
        "url": canonical,
    }
    # BreadcrumbList
    schema_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "選手", "item": f"{SITE_URL}/players/"},
            {"@type": "ListItem", "position": 3, "name": name_ja, "item": canonical},
        ]
    }
    schema_ld = json.dumps(schema_person, ensure_ascii=False, indent=2)
    schema_breadcrumb_ld = json.dumps(schema_breadcrumb, ensure_ascii=False, indent=2)

    # --- 統計セクション ---
    # wiki_stats を優先、なければ scorer_stats (football-data API top50) を使用
    active_stats = wiki_stats if wiki_stats else scorer_stats
    stats_source_note = ""
    if wiki_stats:
        stats_source_note = '<div class="stats-source">出典: Wikipedia</div>'
    elif scorer_stats:
        stats_source_note = '<div class="stats-source">出典: Football-Data.org</div>'

    stats_html = ""
    if active_stats:
        stats_html = f"""
    <section class="player-section">
      <h3>📊 {"2025-26シーズン成績（リーグ戦）" if wiki_stats else "今シーズン（2026-27）成績"}</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">出場試合</div>
          <div class="stat-value">{esc(str(active_stats.get('played', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ゴール</div>
          <div class="stat-value">{esc(str(active_stats.get('goals', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">アシスト</div>
          <div class="stat-value">{esc(str(active_stats.get('assists', '—')))}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">PK</div>
          <div class="stat-value">{esc(str(active_stats.get('penalties', '—')))}</div>
        </div>
      </div>
      {stats_source_note}
    </section>"""

    # --- 順位セクション ---
    standing_html = ""
    if standing:
        pos = standing.get("position", "—")
        pts = standing.get("points", "—")
        total = standing.get("total_teams", "")
        played = standing.get("played", "—")
        won = standing.get("won", "—")
        draw = standing.get("draw", "—")
        lost = standing.get("lost", "—")
        league = standing.get("league_ja", league_ja)
        standing_html = f"""
    <section class="player-section">
      <h3>🏆 {esc(league)} 現在順位</h3>
      <div class="standing-row">
        <span class="standing-pos">{esc(str(pos))}位</span>
        <span class="standing-detail">（{esc(str(total))}チーム中）　{esc(str(played))}試合　{esc(str(won))}勝{esc(str(draw))}分{esc(str(lost))}敗　{esc(str(pts))}pt</span>
      </div>
    </section>"""

    # --- 直近の試合セクション ---
    matches_html = ""
    if club_matches:
        match_rows = ""
        for idx, m in enumerate(club_matches):
            kickoff = m.get("kickoff_jst", "")
            status = m.get("status", "")
            home_ja = m.get("home_ja", "")
            away_ja = m.get("away_ja", "")
            score = m.get("score", {})
            comp_ja = m.get("competition_ja", "")
            home_id = m.get("home_id")
            away_id = m.get("away_id")
            club_id = player.get("club_id")
            if club_id:
                is_home = home_id == club_id
            else:
                # クラブ番号の無い選手（ブンデス2部）は、試合データの日本人選手の側で決める
                is_home = _jp_side(m, player.get("name_ja", "")) == "home"
            extra_cls = " hidden-extra" if idx >= 10 else ""

            # 日時表示（yyyy/mm/dd 改行 (曜) HH:MM JST）
            date_display = ""
            if kickoff:
                try:
                    import re as _re
                    from datetime import datetime
                    # タイムゾーン部分（+09:00 や Z）を除去してローカル日時として扱う
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', kickoff.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:16], "%Y-%m-%dT%H:%M")
                    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
                    wd = weekdays[dt.weekday()]
                    date_display = f'<span class="match-date-day">{dt.strftime("%Y/%m/%d")}</span><span class="match-date-time">（{wd}）{dt.strftime("%H:%M")}</span>'
                except Exception:
                    # フォールバック：ISO文字列を最低限分割
                    if "T" in kickoff:
                        d, t = kickoff.split("T", 1)
                        # yyyy-mm-dd → yyyy/mm/dd
                        d_fmt = d.replace("-", "/")
                        date_display = f'<span class="match-date-day">{d_fmt}</span><span class="match-date-time">{t[:5]}</span>'
                    else:
                        date_display = kickoff[:16]

            # スコア表示
            if status == "FINISHED" and score:
                home_score = score.get("home", "")
                away_score = score.get("away", "")
                if is_home:
                    score_display = f"{home_score} - {away_score}"
                    opponent = esc(away_ja)
                    result_class = "win" if home_score > away_score else ("lose" if home_score < away_score else "draw")
                else:
                    score_display = f"{away_score} - {home_score}"
                    opponent = esc(home_ja)
                    result_class = "win" if away_score > home_score else ("lose" if away_score < home_score else "draw")
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                match_rows += f"""
          <div class="match-row{extra_cls}">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result {result_class}">{esc(score_display)}</div>
            <div class="match-broadcast">—</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""
            else:
                if is_home:
                    opponent = esc(away_ja)
                else:
                    opponent = esc(home_ja)
                venue_cls = "venue-home" if is_home else "venue-away"
                venue_label = "H" if is_home else "A"
                # 配信は上の「次の試合・どこで見れる」欄と同じ情報源（league_guides.json）から
                bc_tags, _n_aff = build_table_watch_cell(guides, services or {}, m.get("competition_id"), comp_ja, slug)
                TABLE_WATCH_STATS["affiliate_links"] += _n_aff
                TABLE_WATCH_STATS["unconfirmed_rows"] += 1 if "bc-unconfirmed" in bc_tags else 0
                _pending = is_result_pending(m)  # 開始から3時間すぎても予定のまま＝結果待ち
                match_rows += f"""
          <div class="match-row {'result-pending' if _pending else 'scheduled'}{extra_cls}">
            <div class="match-date">{date_display}</div>
            <div class="match-venue"><span class="venue-badge {venue_cls}">{venue_label}</span></div>
            <div class="match-opponent">vs {opponent}</div>
            <div class="match-result{' pending' if _pending else ''}">{'結果待ち' if _pending else '—'}</div>
            <div class="match-broadcast">{bc_tags if bc_tags else "—"}</div>
            <div class="match-comp">{esc(comp_ja)}</div>
          </div>"""

        total_matches = len(club_matches)
        extra_count = max(0, total_matches - 10)
        show_more_btn = ""
        if extra_count > 0:
            show_more_btn = f"""
      <button class="show-more-matches" onclick="toggleMoreMatches(this)" data-count="{extra_count}" data-expanded="false">
        もっと見る（残り {extra_count} 試合）
      </button>"""

        matches_html = f"""
    <section class="player-section">
      <h3>📅 直近の試合</h3>
      <div class="matches-list">
        <div class="match-header">
          <div class="match-date">日時（JST）</div>
          <div class="match-venue">場所</div>
          <div class="match-opponent">対戦相手</div>
          <div class="match-result">結果</div>
          <div class="match-broadcast">配信</div>
          <div class="match-comp">大会</div>
        </div>
        {match_rows}
      </div>{show_more_btn}
    </section>"""
    else:
        matches_html = """
    <section class="player-section">
      <h3>📅 直近の試合</h3>
      <p class="no-data">試合データを取得中です。</p>
    </section>"""

    # --- ゴールセクション ---
    goals_html = ""
    if goal_events:
        goal_rows = ""
        for g in goal_events:
            kickoff = g.get("kickoff_jst", "")
            date_display = ""
            if kickoff:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(kickoff)
                    date_display = dt.strftime("%m/%d")
                except Exception:
                    date_display = kickoff[:10]

            home_ja_g = g.get("home_ja", "")
            away_ja_g = g.get("away_ja", "")
            minute_raw = g.get("minute_raw", str(g.get("minute", "?")))
            goal_note = g.get("note", "")
            comp_ja_g = g.get("competition_ja", "")
            if goal_note:
                minute_raw += f" ({goal_note})"
            goal_rows += f"""
          <div class="goal-row">
            <div class="goal-date">{date_display}</div>
            <div class="goal-match">{esc(home_ja_g)} vs {esc(away_ja_g)}</div>
            <div class="goal-minute">{esc(minute_raw)}分</div>
            <div class="goal-comp">{esc(comp_ja_g)}</div>
          </div>"""
        goals_html = f"""
    <section class="player-section">
      <h3>⚽ 直近のゴール</h3>
      <div class="goals-list">
        {goal_rows}
      </div>
    </section>"""
    else:
        goals_html = """
    <section class="player-section">
      <h3>⚽ 直近のゴール</h3>
      <p class="no-data">今シーズンまだゴールなし（または取得範囲外）。</p>
    </section>"""

    # --- 選手別ゴール集動画セクション（優先） ---
    player_videos_html = ""
    if player_videos:
        pv_cards = ""
        for v in player_videos:
            vid = v.get("video_id", "")
            if not vid:
                continue
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            vurl = v.get("url", f"https://www.youtube.com/watch?v={vid}")
            title_v = v.get("title", "")
            channel = v.get("channel", "")
            pub = v.get("published", "")
            pub_display = ""
            if pub:
                try:
                    from datetime import datetime
                    import re as _re
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', pub.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:10], "%Y-%m-%d")
                    pub_display = dt.strftime("%m/%d")
                except Exception:
                    pub_display = pub[:10]
            meta_parts = []
            if channel:
                meta_parts.append(esc(channel))
            if pub_display:
                meta_parts.append(pub_display)
            # 公式チャンネルバッジ
            official_badge = ""
            if v.get("is_official"):
                official_badge = '<span class="video-official-badge">公式</span>'
            meta_str = " · ".join(meta_parts)
            pv_cards += f"""
        <a href="{esc(vurl)}" target="_blank" rel="noopener" class="video-card video-card-player">
          <div class="video-thumb-wrap">
            <img src="{esc(thumb)}" alt="" loading="lazy">
            {official_badge}
          </div>
          <div class="video-title">{esc(title_v)}</div>
          <div class="video-meta">{meta_str}</div>
        </a>"""
        if pv_cards:
            player_videos_html = f"""
    <section class="player-section">
      <h3>🎬 シーズンゴール集・まとめ動画</h3>
      <div class="video-grid video-grid-player">
        {pv_cards}
      </div>
    </section>"""

    # --- 関連ハイライト動画セクション（試合単位・下に表示） ---
    videos_html = ""
    if highlights:
        video_cards = ""
        for v in highlights:
            vid = v.get("video_id", "")
            if not vid:
                continue
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            url = v.get("url", f"https://www.youtube.com/watch?v={vid}")
            title_v = v.get("title", "")
            channel = v.get("channel", "")
            pub = v.get("published", "")
            pub_display = ""
            if pub:
                try:
                    from datetime import datetime
                    import re as _re
                    ko_str = _re.sub(r'[+-]\d{2}:\d{2}$', '', pub.replace("Z", ""))
                    dt = datetime.strptime(ko_str[:10], "%Y-%m-%d")
                    pub_display = dt.strftime("%m/%d")
                except Exception:
                    pub_display = pub[:10]
            meta_parts = []
            if channel:
                meta_parts.append(esc(channel))
            if pub_display:
                meta_parts.append(pub_display)
            meta_str = " · ".join(meta_parts)
            video_cards += f"""
        <a href="{esc(url)}" target="_blank" rel="noopener" class="video-card">
          <img src="{esc(thumb)}" alt="" loading="lazy">
          <div class="video-title">{esc(title_v)}</div>
          <div class="video-meta">{meta_str}</div>
        </a>"""
        if video_cards:
            # 選手別動画がある場合は「他のハイライト動画」として表示
            section_title = "他のハイライト動画" if player_videos else "📺 関連ハイライト動画"
            section_icon = "📺"
            videos_html = f"""
    <section class="player-section">
      <h3>{section_icon} {section_title}</h3>
      <div class="video-grid">
        {video_cards}
      </div>
    </section>"""

    # --- プロフィール情報セクション（身長・体重・年齢・利き足）---
    profile_info_html = ""
    if player_info:
        height_cm = player_info.get("height_cm")
        weight_kg = player_info.get("weight_kg")
        birth_date = player_info.get("birth_date")
        # 出身地：_ja フィールドがあれば優先
        birth_place_ja = player_info.get("birth_place_ja", "")
        birth_place = player_info.get("birth_place", "")
        display_place = birth_place_ja if birth_place_ja else birth_place
        foot = player_info.get("foot")
        wiki_url = player_info.get("wiki_url")

        height_str = f"{height_cm}cm" if height_cm else "—"
        weight_str = f"{weight_kg}kg" if weight_kg else "—"
        age_str = calc_age(birth_date)
        birth_str = f"{esc(birth_date)}（{age_str}歳）" if birth_date and age_str else esc(birth_date or "—")
        foot_str = foot_ja(foot) if foot else "—"
        place_str = esc(display_place) if display_place else "—"

        wiki_link = ""
        if wiki_url:
            wiki_link = f' <a href="{esc(wiki_url)}" target="_blank" rel="noopener" style="font-size:11px;color:#888;">Wikipedia →</a>'

        profile_info_html = f"""
    <section class="player-section">
      <h3>👤 プロフィール{wiki_link}</h3>
      <table class="profile-table">
        <tr><td class="profile-label">身長 / 体重</td><td class="profile-value">{height_str} / {weight_str}</td></tr>
        <tr><td class="profile-label">生年月日</td><td class="profile-value">{birth_str}</td></tr>
        <tr><td class="profile-label">出身地</td><td class="profile-value">{place_str}</td></tr>
        <tr><td class="profile-label">利き足</td><td class="profile-value">{foot_str}</td></tr>
      </table>
    </section>"""

    # --- キャリアセクション ---
    career_html = ""
    if player_info:
        # career_ja があれば優先、なければ career（英語）にフォールバック
        career_ja = player_info.get("career_ja", [])
        career_en = player_info.get("career", [])
        career = career_ja if career_ja else career_en
        if career:
            # 並び順を整理：開始年でソート → 現在所属クラブ（years が "–" で終わるもの）を末尾に
            def year_start(item):
                y = item.get("years", "")
                m = re.match(r"^(\d{4})", y.strip())
                return int(m.group(1)) if m else 0

            def is_current(item):
                y = item.get("years", "").strip()
                return y.endswith("–") or y.endswith("-") or y.endswith("—")

            sorted_past = sorted([c for c in career if not is_current(c)], key=year_start, reverse=True)
            current_clubs = [c for c in career if is_current(c)]
            # 新しい順：現在所属 → 過去（新→古）
            ordered_career = current_clubs + sorted_past

            # 現在所属クラブを示すバッジ
            current_club_badge = ""
            if current_clubs:
                latest = current_clubs[-1]
                current_club_badge = f'<div class="career-current">🟢 現在所属：<strong>{esc(latest.get("club", ""))}</strong>（{esc(latest.get("years", ""))}）</div>'

            career_rows = ""
            for item in ordered_career:
                years = esc(item.get("years", ""))
                club = esc(item.get("club", ""))
                cur_class = " is-current" if is_current(item) else ""
                career_rows += f'<div class="career-row{cur_class}"><span class="career-years">{years}</span><span class="career-club">{club}</span></div>'
            career_html = f"""
    <section class="player-section">
      <h3>📋 キャリア</h3>
      {current_club_badge}
      <div class="career-list">
        {career_rows}
      </div>
    </section>"""

    # --- 代表履歴セクション ---
    national_team_html = ""
    if player_info:
        nt_history = player_info.get("national_team_history", [])
        if nt_history:
            nt_rows = ""
            for nt in nt_history:
                team_ja = esc(nt.get("team_ja", nt.get("team", "")))
                years = esc(nt.get("years", ""))
                caps = nt.get("caps")
                goals = nt.get("goals")
                if caps is not None and goals is not None:
                    stats_str = f"{caps}試合 / {goals}ゴール"
                elif caps is not None:
                    stats_str = f"{caps}試合"
                else:
                    stats_str = "—"
                nt_rows += f"""
            <div class="nt-row">
              <span class="nt-team">{team_ja}</span>
              <span class="nt-years">{years}</span>
              <span class="nt-stats">{esc(stats_str)}</span>
            </div>"""
            national_team_html = f"""
    <section class="player-section">
      <h3>🇯🇵 代表履歴</h3>
      <div class="national-team-list">
        {nt_rows}
      </div>
    </section>"""

    # --- SNSセクション ---
    sns_html = ""
    if player_info:
        twitter = player_info.get("twitter")
        instagram = player_info.get("instagram")
        official_url = player_info.get("official_url")
        sns_items = []
        if twitter:
            handle = twitter.lstrip("@")
            sns_items.append(f'<a class="sns-link sns-twitter" href="https://x.com/{esc(handle)}" target="_blank" rel="noopener">𝕏 {esc(twitter)}</a>')
        if instagram:
            sns_items.append(f'<a class="sns-link sns-instagram" href="https://www.instagram.com/{esc(instagram)}/" target="_blank" rel="noopener">📷 @{esc(instagram)}</a>')
        if official_url:
            domain = official_url.replace("https://", "").replace("http://", "").split("/")[0]
            sns_items.append(f'<a class="sns-link sns-official" href="{esc(official_url)}" target="_blank" rel="noopener">🌐 {esc(domain)}</a>')
        if sns_items:
            sns_html = f"""
    <section class="player-section">
      <h3>🔗 SNS・公式リンク</h3>
      <div class="sns-links">
        {"".join(sns_items)}
      </div>
    </section>"""

    # --- 関連選手セクション（同クラブ他日本人）---
    related_html = ""
    if related_players:
        cards_html = ""
        for rp in related_players:
            cards_html += f"""
          <a class="related-player-card" href="/players/{esc(rp['slug'])}/">
            <span class="related-player-flag">🇯🇵</span>
            <div class="related-player-info">
              <div class="related-player-name-ja">{esc(rp['name_ja'])}</div>
              <div class="related-player-name-en">{esc(rp['name_en'])}</div>
              <div class="related-player-pos">{esc(rp['position'])}</div>
            </div>
          </a>"""
        related_html = f"""
    <section class="player-section">
      <h3>🏟️ 同クラブの日本人選手</h3>
      <div class="related-players-grid">
        {cards_html}
      </div>
    </section>"""

    # note がある場合
    note_html = ""
    if note:
        note_html = f'<div class="player-note">ℹ️ {esc(note)}</div>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="profile">
  <meta property="og:url" content="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:site_name" content="{esc(SITE_NAME)}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">
{schema_ld}
  </script>
  <script type="application/ld+json">
{schema_breadcrumb_ld}
  </script>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "{GA4_ID}");
  </script>
  <link rel="icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/logos/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/assets/logos/favicon-48.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <style>
    .breadcrumb {{
      font-size: 12px;
      color: #888;
      padding: 8px 16px;
      background: #f8f9fa;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .breadcrumb a {{ color: #555; text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
    .breadcrumb span {{ color: #333; }}
    .player-hero {{
      background: #ffffff;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 18px;
      margin-bottom: 18px;
    }}
    .player-hero .name-block h2 {{
      margin: 0 0 4px;
      font-size: 26px;
      font-weight: 800;
    }}
    .player-hero .name-en {{
      font-size: 13px;
      color: #666;
      margin: 0 0 8px;
    }}
    .player-hero .player-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .player-meta-tag {{
      display: inline-block;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 600;
      background: #f0f1f5;
      border-radius: 3px;
    }}
    .player-section {{
      background: #fff;
      padding: 18px 16px;
      margin-bottom: 1px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .player-section h3 {{
      margin: 0 0 14px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding-left: 10px;
      border-left: 4px solid var(--c-accent, #0047ab);
      color: var(--c-text, #111);
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      border: 1px solid var(--c-border, #e5e7eb);
    }}
    .stat-card {{
      background: #fff;
      border-right: 1px solid var(--c-border, #e5e7eb);
      padding: 12px 14px;
      text-align: center;
    }}
    .stat-card:last-child {{ border-right: none; }}
    .stat-label {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .stat-value {{ font-size: 22px; font-weight: 800; color: var(--c-text, #111); }}
    .standing-row {{
      font-size: 14px;
      padding: 8px 0;
    }}
    .standing-pos {{
      font-size: 24px;
      font-weight: 800;
      margin-right: 12px;
    }}
    .standing-detail {{ color: #444; }}
    .matches-list {{
      font-size: 13px;
    }}
    .match-header, .match-row {{
      display: grid;
      grid-template-columns: 110px 30px 1fr 60px 110px 80px;
      gap: 6px;
      padding: 10px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: center;
    }}
    .match-header {{
      font-size: 11px;
      font-weight: 700;
      color: #666;
      background: #f8f9fa;
      align-items: center;
    }}
    .match-row:last-child {{ border-bottom: none; }}
    .match-result {{
      font-weight: 700;
      text-align: center;
    }}
    .match-result.win {{ color: #1a7a3a; }}
    .match-result.lose {{ color: #c0392b; }}
    .match-result.draw {{ color: #666; }}
    .match-result.pending {{ color: #8a6100; font-size: 12px; font-weight: 600; }}
    .match-broadcast {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      align-items: center;
      justify-content: center;
    }}
    .bc-unconfirmed {{ font-size: 11px; color: #888; }}
    .match-date-day {{ display: block; font-size: 12px; }}
    .match-date-time {{ display: block; font-size: 11px; color: #555; }}
    .venue-badge {{
      display: inline-block;
      width: 24px;
      height: 24px;
      line-height: 24px;
      text-align: center;
      border-radius: 4px;
      font-weight: 700;
      font-size: 12px;
    }}
    .venue-away {{ background: #fee; color: #c9302c; border: 1px solid #f5b7b1; }}
    .venue-home {{ background: #e7f0ff; color: #1e6cba; border: 1px solid #aac6e8; }}
    .match-comp {{ font-size: 11px; color: #666; }}
    .goals-list {{ font-size: 13px; }}
    .goal-row {{
      display: grid;
      grid-template-columns: 50px 1fr 70px 100px;
      gap: 8px;
      padding: 8px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: center;
    }}
    .goal-row:last-child {{ border-bottom: none; }}
    .goal-date {{ font-size: 11px; color: #666; }}
    .goal-minute {{ font-weight: 700; text-align: center; color: #1a7a3a; }}
    .goal-comp {{ font-size: 11px; color: #666; }}
    .no-data {{
      color: #888;
      font-size: 13px;
      padding: 8px 0;
      margin: 0;
    }}
    .stats-source {{
      font-size: 11px;
      color: #999;
      margin-top: 6px;
      text-align: right;
    }}
    .player-note {{
      background: #fff8e1;
      border-left: 3px solid #d4af37;
      padding: 8px 12px;
      font-size: 12px;
      margin: 8px 0 0;
    }}
    .related-players-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 8px;
    }}
    .related-player-card {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px;
      padding: 10px 12px;
      text-decoration: none;
      color: var(--c-text, #111);
      transition: background 0.15s;
    }}
    .related-player-card:hover {{ background: #eef0f7; }}
    .related-player-flag {{ font-size: 18px; line-height: 1; padding-top: 1px; flex-shrink: 0; }}
    .related-player-name-ja {{ font-size: 13px; font-weight: 700; margin-bottom: 2px; }}
    .related-player-name-en {{ font-size: 10px; color: #666; margin-bottom: 3px; }}
    .related-player-pos {{
      display: inline-block;
      padding: 1px 5px;
      font-size: 10px;
      font-weight: 700;
      background: #e6f0fa;
      color: #1565c0;
      border-radius: 3px;
    }}
    .back-link {{
      display: block;
      padding: 12px 16px;
      font-size: 13px;
      color: var(--c-text, #111);
      text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .site-footer {{
      padding: 20px 16px;
      font-size: 12px;
      color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb);
      margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
    .profile-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .profile-table tr {{
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .profile-table tr:last-child {{ border-bottom: none; }}
    .profile-label {{
      width: 100px;
      padding: 7px 0;
      color: #666;
      font-size: 12px;
      vertical-align: top;
    }}
    .profile-value {{
      padding: 7px 0;
      font-weight: 600;
    }}
    .career-list {{
      font-size: 13px;
    }}
    .career-row {{
      display: flex;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: baseline;
    }}
    .career-row:last-child {{ border-bottom: none; }}
    .career-years {{
      min-width: 90px;
      color: #888;
      font-size: 12px;
      flex-shrink: 0;
    }}
    .career-club {{
      font-weight: 600;
    }}
    .sns-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .sns-link {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      transition: opacity 0.15s;
    }}
    .sns-link:hover {{ opacity: 0.8; }}
    .sns-twitter {{ background: #000; color: #fff; }}
    .sns-instagram {{ background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); color: #fff; }}
    .sns-official {{ background: #f0f1f5; color: #333; border: 1px solid #ccc; }}
    .match-row.hidden-extra {{ display: none; }}
    .match-row.hidden-extra.shown {{ display: grid; }}
    .show-more-matches {{
      display: block;
      width: 100%;
      margin-top: 10px;
      padding: 10px;
      background: #f0f4ff;
      border: 1px solid #aac6e8;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      color: var(--c-accent, #0047ab);
      cursor: pointer;
      text-align: center;
      transition: background 0.15s;
    }}
    .show-more-matches:hover {{ background: #dce8ff; }}
    .video-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 12px;
    }}
    .video-card {{
      display: block;
      text-decoration: none;
      color: var(--c-text, #111);
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px;
      overflow: hidden;
      transition: background 0.15s;
    }}
    .video-card:hover {{ background: #eef0f7; }}
    .video-card img {{
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      display: block;
    }}
    .video-title {{
      font-size: 11px;
      font-weight: 600;
      padding: 6px 8px 2px;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .video-meta {{
      font-size: 10px;
      color: #888;
      padding: 0 8px 8px;
    }}
    .video-grid-player {{ grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
    .video-card-player {{ border: 2px solid #aac6e8; }}
    .video-thumb-wrap {{ position: relative; }}
    .video-thumb-wrap img {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }}
    .video-official-badge {{
      position: absolute;
      top: 6px;
      left: 6px;
      background: var(--c-accent, #0047ab);
      color: #fff;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
    }}
    .national-team-list {{
      font-size: 13px;
    }}
    .nt-row {{
      display: flex;
      gap: 12px;
      padding: 7px 0;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      align-items: baseline;
      flex-wrap: wrap;
    }}
    .nt-row:last-child {{ border-bottom: none; }}
    .nt-team {{
      font-weight: 700;
      min-width: 140px;
      flex-shrink: 0;
    }}
    .nt-years {{
      color: #888;
      font-size: 12px;
      min-width: 70px;
      flex-shrink: 0;
    }}
    .nt-stats {{
      color: #444;
      font-size: 12px;
    }}
    .wc-history {{
      margin-top: 10px;
      font-size: 13px;
      color: #555;
      padding: 6px 10px;
      background: #fffbe6;
      border-left: 3px solid #d4af37;
      border-radius: 2px;
    }}
{NEXT_WATCH_CSS if next_watch_html else ""}{TRIAL_CSS if trial else ""}    @media (max-width: 600px) {{
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .match-header, .match-row {{
        grid-template-columns: 80px 28px 1fr 45px;
        font-size: 12px;
      }}
      .match-broadcast, .match-comp {{ display: none; }}
      .goal-row {{ grid-template-columns: 45px 1fr 60px; }}
      .goal-comp {{ display: none; }}
      .video-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
  <script type="application/ld+json">
{schema_ld}
  </script>
</head>
<body>

<nav class="breadcrumb" aria-label="パンくずリスト">
  <a href="/">ホーム</a> ›
  <a href="/players/">選手</a> ›
  <span aria-current="page">{esc(name_ja)}</span>
</nav>

<div class="player-hero">
  <div class="name-block">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
      {f'<h1 class="pt-h1">🇯🇵 {esc(name_ja)}<span class="pt-h1-sub">の今季成績・次の試合・どこで見れるか</span></h1>' if trial else f'<h2 style="margin:0;">🇯🇵 {esc(name_ja)}</h2>'}
      <button class="fav-btn" data-slug="{slug}" onclick="fjFavorites.toggle('{slug}'); refreshFavBtn(this);" title="お気に入りに追加" aria-label="お気に入り"><span class="fav-star">☆</span></button>
    </div>
    <p class="name-en">{esc(name_en)}</p>
    <div class="player-meta">
      <span class="player-meta-tag">⚽ {esc(position)}</span>
      <span class="player-meta-tag">🏟️ {esc(club_ja)}（{esc(club_en)}）</span>
      <span class="player-meta-tag">🏆 {esc(league_ja)}</span>
    </div>
    {note_html}
  </div>
</div>

<div style="max-width: 860px; margin: 0 auto;">

  {(trial["stats_html"] + next_watch_html + trial["where_html"]) if trial else next_watch_html}{profile_info_html}

  {"" if trial else stats_html}

  {standing_html}

  {matches_html}

  {player_videos_html}

  {videos_html}

  {goals_html}

  {career_html}

  {national_team_html}

  {sns_html}

  {related_html}

  <div class="player-section">
    <h3>🔗 関連リンク</h3>
    <p style="font-size:13px; margin: 0;">
      <a href="/clubs/{make_slug(club_en)}/" style="color: var(--c-accent, #0047ab);">
        {esc(club_ja)} クラブページ →
      </a>
    </p>
  </div>

  <footer class="site-footer">
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football-Data.org</a></p>
    <p class="oldb-credit">ブンデスリーガ2部の日程・結果: <a href="https://www.openligadb.de/" target="_blank" rel="noopener">OpenLigaDB</a>（www.openligadb.de）、<a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener">ODbL 1.0</a> で提供</p>
    <p class="footer-links">
      <a href="/">football-jp トップへ</a> |
      <a href="/players/">選手一覧</a> |
      <a href="/clubs/">クラブ一覧</a> |
      <a href="/privacy">プライバシーポリシー</a>
    </p>
  </footer>
</div>

<script>
{NEXT_WATCH_JS if next_watch_html else ""}function toggleMoreMatches(btn) {{
  var list = btn.previousElementSibling;
  list.querySelectorAll('.hidden-extra').forEach(function(r) {{
    r.classList.toggle('shown');
  }});
  if (btn.dataset.expanded === 'true') {{
    btn.textContent = '\u3082\u3063\u3068\u898b\u308b\uff08\u6b8b\u308a ' + btn.dataset.count + ' \u8a66\u5408\uff09';
    btn.dataset.expanded = 'false';
  }} else {{
    btn.textContent = '\u9589\u3058\u308b';
    btn.dataset.expanded = 'true';
  }}
}}
function trackAffClick(el) {{
  if (typeof gtag === 'function') {{
    gtag('event', 'affiliate_click', {{
      service: el.dataset.svc,
      page_type: el.dataset.pagetype,
      page_id: el.dataset.pageid,
      destination: el.href
    }});
  }}
}}
</script>
<script src="/favorites.js" defer></script>

</body>
</html>
"""


# 手書きの4ページにある案内リンク「日本人選手一覧（◯名）」。数は players.json から出す（2026-10-21 まで 68名 の手書きだった）
STATIC_COUNT_PAGES = ["index.html", "calendar/index.html", "results/index.html", "standings/index.html"]
_COUNT_LINK_RE = re.compile(r"日本人選手一覧（\d+名）")


def update_static_player_count_links(n: int) -> None:
    for rel in STATIC_COUNT_PAGES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text = _COUNT_LINK_RE.sub(f"日本人選手一覧（{n}名）", text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"  ✅ /{rel} の選手数リンク → {n}名")


# ============================
# 一覧ページHTML生成
# ============================
def build_players_index(players: list, slug_map: dict) -> str:
    """選手一覧ページ（/players/index.html）を生成する。"""
    n = len(players)  # 人数は players.json の数から出す（2026-10-21 まで「68名」と手書きだった）
    title = f"日本人サッカー選手 一覧 海外組{n}名｜football-jp"
    desc = f"三笘薫・久保建英・遠藤航など海外組{n}名の日本人選手一覧。プレミアリーグ・ブンデスリーガ・ラ・リーガ等の試合スケジュール・成績・配信情報を日本時間で確認。"
    canonical = f"{SITE_URL}/players/"

    # ポジション正規化（GK/DF/MF/FW の4分類）
    def pos_category(pos: str) -> str:
        p = pos.upper()
        if "GK" in p:
            return "GK"
        if p.startswith("DF") or p.endswith("DF"):
            return "DF"
        if p.startswith("FW") or p.endswith("FW"):
            return "FW"
        if "MF" in p:
            return "MF"
        return "他"

    # リーグ別にグループ化
    LEAGUE_ORDER = [
        "プレミアリーグ", "チャンピオンシップ",
        "ブンデスリーガ", "ラ・リーガ",
        "セリエA", "リーグ・アン", "リーグ・ドゥ",
        "エールディビジ", "プリメイラ・リーガ", "ジュピラー・プロ・リーグ",
    ]
    groups: dict = {}
    for i, p in enumerate(players):
        league = p.get("league_ja", "その他")
        if league not in groups:
            groups[league] = []
        groups[league].append((i, p))

    # リーグ順でソート
    sorted_leagues = sorted(
        groups.keys(),
        key=lambda l: LEAGUE_ORDER.index(l) if l in LEAGUE_ORDER else 99
    )

    sections_html = ""
    for league in sorted_leagues:
        league_players = groups[league]
        cards_html = ""
        for i, p in league_players:
            slug = slug_map[i]
            pos_cat = pos_category(p.get("position", ""))
            cards_html += f"""
        <div class="player-card-fav-wrap" data-pos="{esc(pos_cat)}" data-slug="{esc(slug)}">
          <a class="player-card" href="/players/{esc(slug)}/"
             data-pos="{esc(pos_cat)}" style="flex:1;">
            <span class="player-card-flag">🇯🇵</span>
            <div class="player-card-body">
              <div class="player-card-name-ja">{esc(p.get('name_ja',''))}</div>
              <div class="player-card-name-en">{esc(p.get('name_en',''))}</div>
              <div class="player-card-meta">
                <span class="pos-badge pos-{esc(pos_cat.lower())}">{esc(pos_cat)}</span>
                <span class="club-name">{esc(p.get('club_ja',''))}</span>
              </div>
            </div>
          </a>
          <button class="fav-btn" data-slug="{esc(slug)}" onclick="fjFavorites.toggle('{esc(slug)}'); refreshFavBtn(this); applyFavFilter();" title="お気に入りに追加" aria-label="お気に入り"><span class="fav-star">☆</span></button>
        </div>"""

        sections_html += f"""
      <section class="league-section">
        <h2 class="league-heading">{esc(league)}</h2>
        <div class="player-grid">
          {cards_html}
        </div>
      </section>"""

    # Schema.org ItemList（事前生成）
    item_list_elements = [
        {"@type": "ListItem", "position": i + 1, "name": p.get("name_ja", ""),
         "url": f"{SITE_URL}/players/{slug_map.get(i, '')}/"}
        for i, p in enumerate(players[:20])
    ]
    schema_itemlist = json.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "日本人サッカー選手一覧",
        "description": f"海外リーグで活躍する日本人選手{len(players)}名の一覧",
        "url": f"{SITE_URL}/players/",
        "itemListElement": item_list_elements
    }, ensure_ascii=False, indent=2)
    schema_breadcrumb_index = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "選手一覧", "item": f"{SITE_URL}/players/"}
        ]
    }, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:site_name" content="{esc(SITE_NAME)}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">
{schema_itemlist}
  </script>
  <script type="application/ld+json">
{schema_breadcrumb_index}
  </script>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "{GA4_ID}");
  </script>
  <link rel="icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/logos/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/logos/favicon-180.png">
  <link rel="stylesheet" href="/style.css">
  <style>
    .breadcrumb {{
      font-size: 12px;
      color: #888;
      padding: 8px 16px;
      background: #f8f9fa;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .breadcrumb a {{ color: #555; text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--c-accent, #0047ab); text-decoration: underline; }}
    .index-hero {{
      background: #fff;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      padding: 20px 16px 16px;
      margin-bottom: 0;
    }}
    .index-hero h1 {{
      margin: 0 0 6px;
      font-size: 22px;
      font-weight: 800;
    }}
    .index-hero p {{
      margin: 0;
      font-size: 13px;
      color: #555;
    }}
    .filter-bar {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      padding: 10px 16px;
      background: #f8f9fa;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .filter-btn {{
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid #ccc;
      border-radius: 4px;
      background: #fff;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--c-accent, #0047ab);
      color: #fff;
      border-color: var(--c-accent, #0047ab);
    }}
    .league-section {{
      padding: 14px 16px 4px;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
      background: #fff;
      margin-bottom: 1px;
    }}
    .league-section.hidden {{ display: none; }}
    .league-heading {{
      font-size: 13px;
      font-weight: 700;
      color: #444;
      margin: 0 0 10px;
      padding-left: 8px;
      border-left: 3px solid var(--c-accent, #0047ab);
    }}
    .player-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }}
    .player-card {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: #f8f9fa;
      border: 1px solid var(--c-border, #e5e7eb);
      border-radius: 4px;
      padding: 10px 12px;
      text-decoration: none;
      color: var(--c-text, #111);
      transition: background 0.15s;
    }}
    .player-card:hover {{ background: #eef0f7; }}
    .player-card.hidden {{ display: none; }}
    .player-card-flag {{ font-size: 18px; line-height: 1; padding-top: 1px; }}
    .player-card-name-ja {{ font-size: 14px; font-weight: 700; margin-bottom: 2px; }}
    .player-card-name-en {{ font-size: 11px; color: #666; margin-bottom: 4px; }}
    .player-card-meta {{ display: flex; align-items: center; gap: 6px; }}
    .pos-badge {{
      display: inline-block;
      padding: 1px 5px;
      font-size: 10px;
      font-weight: 700;
      border-radius: 3px;
      background: #e6f0fa;
      color: #1565c0;
    }}
    .pos-gk {{ background: #fff3e0; color: #e65100; }}
    .pos-df {{ background: #e8f5e9; color: #2e7d32; }}
    .pos-mf {{ background: #e6f0fa; color: #1565c0; }}
    .pos-fw {{ background: #fce4ec; color: #c62828; }}
    .club-name {{ font-size: 11px; color: #555; }}
    .back-link {{
      display: block;
      padding: 12px 16px;
      font-size: 13px;
      color: var(--c-text, #111);
      text-decoration: none;
      border-bottom: 1px solid var(--c-border, #e5e7eb);
    }}
    .site-footer {{
      padding: 20px 16px;
      font-size: 12px;
      color: #666;
      border-top: 1px solid var(--c-border, #e5e7eb);
      margin-top: 20px;
    }}
    .site-footer a {{ color: #666; }}
  </style>
</head>
<body>

<nav class="breadcrumb" aria-label="パンくずリスト">
  <a href="/">ホーム</a> ›
  <span aria-current="page">選手一覧</span>
</nav>

<div class="index-hero">
  <h1>🇯🇵 日本人選手 一覧</h1>
  <p>海外リーグで活躍する日本人選手 {len(players)} 名</p>
</div>

<div class="filter-bar" id="filterBar">
  <button class="filter-btn active" data-filter="all" onclick="filterPlayers('all', this)">すべて</button>
  <button class="filter-btn" data-filter="GK" onclick="filterPlayers('GK', this)">GK</button>
  <button class="filter-btn" data-filter="DF" onclick="filterPlayers('DF', this)">DF</button>
  <button class="filter-btn" data-filter="MF" onclick="filterPlayers('MF', this)">MF</button>
  <button class="filter-btn" data-filter="FW" onclick="filterPlayers('FW', this)">FW</button>
  <label class="fav-filter-label" style="font-size:12px;font-weight:600;display:flex;align-items:center;gap:4px;cursor:pointer;margin-left:4px;">
    <input type="checkbox" id="onlyFav" onchange="applyFavFilter()">
    ⭐ お気に入りのみ
  </label>
</div>

<div style="max-width: 900px; margin: 0 auto;">
  {sections_html}

  <footer class="site-footer">
    <p>データ提供: <a href="https://www.football-data.org/" target="_blank" rel="noopener">Football-Data.org</a></p>
    <p class="footer-links">
      <a href="/">football-jp トップへ</a> |
      <a href="/clubs/">クラブ一覧（41）</a> |
      <a href="/privacy">プライバシーポリシー</a>
    </p>
  </footer>
</div>

<script>
var _currentPosFilter = 'all';

function filterPlayers(pos, btn) {{
  _currentPosFilter = pos;
  // ボタン状態更新
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFavFilter();
}}

function applyFavFilter() {{
  var onlyFav = document.getElementById('onlyFav') && document.getElementById('onlyFav').checked;
  var favs = (window.fjFavorites ? window.fjFavorites.list() : []);

  document.querySelectorAll('.player-card-fav-wrap').forEach(wrap => {{
    var pos = wrap.dataset.pos;
    var slug = wrap.dataset.slug;
    var posOk = (_currentPosFilter === 'all' || pos === _currentPosFilter);
    var favOk = !onlyFav || favs.includes(slug);
    wrap.classList.toggle('hidden', !(posOk && favOk));
  }});

  // 全ラップ非表示のセクションを隠す
  document.querySelectorAll('.league-section').forEach(sec => {{
    const visible = [...sec.querySelectorAll('.player-card-fav-wrap')].some(c => !c.classList.contains('hidden'));
    sec.classList.toggle('hidden', !visible);
  }});
}}

// お気に入り変更時に一覧を再フィルタ
document.addEventListener('fj-favorites-changed', function() {{
  applyFavFilter();
}});
</script>
<script>
function trackAffClick(el) {{
  if (typeof gtag === 'function') {{
    gtag('event', 'affiliate_click', {{
      service: el.dataset.svc,
      page_type: el.dataset.pagetype,
      page_id: el.dataset.pageid,
      destination: el.href
    }});
  }}
}}
</script>
<script src="/favorites.js" defer></script>

</body>
</html>
"""


# ============================
# メイン処理
# ============================
def main():
    print(f"データ読み込み中...")
    players, matches, matches_dict, scorers_comps, events, standings_comps, player_stats, services, player_info, player_videos_data = load_data()
    print(f"  選手数: {len(players)}")
    print(f"  試合数: {len(matches)}")
    global TOTAL_PLAYERS
    TOTAL_PLAYERS = len(players)  # 選手ページの説明文の「全◯名」に使う

    # slug生成
    slug_map = make_unique_slugs(players)

    generated = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    guides = load_league_guides()
    cur_stats = load_cur_stats()
    nw_counts = {"pages": 0, "has_match": 0, "no_match": 0, "unconfirmed": [], "affiliate": []}

    for i, player in enumerate(players):
        slug = slug_map[i]
        name_ja = player.get("name_ja", "")
        name_en = player.get("name_en", "")

        # 統計データ取得
        wiki_stats = get_player_wiki_stats(player, player_stats)
        scorer_stats = get_player_scorer_stats(player, scorers_comps)
        goal_events = get_player_goals(player, events, matches_dict,
                                       known_ja={q.get("name_ja") for q in players if q.get("name_ja")})
        club_matches = get_club_matches(player, matches)
        standing = get_club_standing(player, standings_comps)
        if is_second_team(player):
            # セカンドチームの選手には、トップチームの試合・順位を出さない
            goal_events, club_matches, standing = [], [], {}
        related_players = get_related_players(player, players, slug_map)
        pinfo = player_info.get(name_en)
        highlights = [] if is_second_team(player) else get_club_highlights(player, matches)
        # 選手別ゴール集動画（player_videos.json）
        pv_entry = player_videos_data.get(name_en, {})
        player_vids = pv_entry.get("videos", []) if pv_entry else []

        # 次の試合・どこで見れる（セカンドチームの選手は、トップチームの試合を出さないので欄も出さない）
        next_watch_html = ""
        trial = None
        if not is_second_team(player):
            upcoming = get_upcoming_matches(get_next_watch_matches(player, matches, club_matches))
            is_trial = slug in TITLE_TRIAL_SLUGS
            next_watch_html, nw_info = build_next_watch_section(
                player, slug, upcoming, guides, services, compact=is_trial)
            if is_trial:
                cur = get_cur_season_stats(player, cur_stats)
                where_html, where = build_where_section(player, slug, upcoming, guides, services)
                trial = {"cur": cur, "where": where, "where_html": where_html,
                         "stats_html": build_cur_stats_section(player, cur)}
                print(f"  🧪 試しの型（今季成績・次の試合・どこで見れるか）: {name_ja} /players/{slug}/")
            nw_counts["pages"] += 1
            nw_counts["has_match" if nw_info["has_match"] else "no_match"] += 1
            if nw_info["unconfirmed"]:
                nw_counts["unconfirmed"].append(name_ja)
            if nw_info["affiliate"]:
                nw_counts["affiliate"].append(name_ja)

        # HTMLページ生成
        html = build_player_page(page_player(player, "ja"), slug, scorer_stats, goal_events, club_matches, standing,
                                 wiki_stats=wiki_stats, services=services,
                                 related_players=related_players,
                                 player_info=pinfo,
                                 highlights=highlights,
                                 player_videos=player_vids if player_vids else None,
                                 next_watch_html=next_watch_html,
                                 guides=guides, trial=trial)
        if is_second_team(player):
            html = adjust_second_team(html, player, "ja")

        # 出力
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        size = out_path.stat().st_size
        generated.append((name_ja, name_en, slug, size))
        print(f"  ✅ {name_ja} ({name_en}) → /players/{slug}/ ({size:,} bytes)")

    # 日本に戻った選手（left_overseas）のページも残す（一覧・サイトマップには入れない）
    from left_overseas import load_left, adjust_html, banner_text
    left = load_left()
    if left:
        left_slugs = make_unique_slugs(players + left)
        for j, entry in enumerate(left):
            slug = left_slugs[len(players) + j]
            p = dict(entry, note=banner_text(entry, "ja"))
            html = build_player_page(p, slug, get_player_scorer_stats(p, scorers_comps), [], [], {},
                                     wiki_stats=get_player_wiki_stats(p, player_stats), services=services,
                                     related_players=[], player_info=player_info.get(p.get("name_en")),
                                     highlights=[], player_videos=None)
            html = adjust_html(html, entry, "ja")
            out_dir = OUTPUT_DIR / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(html, encoding="utf-8")
            print(f"  ✅ {p.get('name_ja')}（日本に復帰）→ /players/{slug}/")

    print(f"\n合計 {len(generated)} 選手ページ生成完了")
    print(f"  次の試合・どこで見れる欄: {nw_counts['pages']}ページ（次の試合あり {nw_counts['has_match']}・なし {nw_counts['no_match']}）")
    print(f"  配信先「確認中」を含む: {len(nw_counts['unconfirmed'])}人 {'・'.join(nw_counts['unconfirmed'])}")
    print(f"  報酬リンクが付く: {len(nw_counts['affiliate'])}人 {'・'.join(nw_counts['affiliate'])}")
    print(f"  直近の試合の表（配信の列）: 報酬リンク {TABLE_WATCH_STATS['affiliate_links']}本・確認中 {TABLE_WATCH_STATS['unconfirmed_rows']}行")

    # slug一覧
    print("\n生成済みslug一覧:")
    for name_ja, name_en, slug, size in generated:
        print(f"  {name_ja:12s} → /players/{slug}/")

    # 一覧ページ生成
    print("\n一覧ページ生成中...")
    index_html = build_players_index(players, slug_map)
    index_path = OUTPUT_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"  ✅ /players/index.html → {index_path.stat().st_size:,} bytes")

    # 手書きページ（トップ・カレンダー・結果・順位）の案内リンク「日本人選手一覧（◯名）」を人数に合わせる
    update_static_player_count_links(len(players))

    print("\n完了！")
    return slug_map


if __name__ == "__main__":
    main()
