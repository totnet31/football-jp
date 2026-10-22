#!/usr/bin/env python3
"""
配信先（どこで見れる）の共通の取り出し方（2026-10-22）。

配信先は data/league_guides.json の leagues・watch_only・competitions の「watch」欄
（2026-10-21〜22 に日本の配信サービスの公式ページで確かめた分）だけから出す。
古い data/broadcasters.json の「broadcasters」（2026-04-29 時点・大会IDごと）は使わない。
欄が無いリーグ・大会は「確認中」（推測で書かない）。

成果報酬リンクは、欄の url_service が broadcasters.json の services で affiliate_url を持つときだけ付く。
ただし ABEMA の無料中継と「ABEMA de DAZN」には、ABEMAプレミアムの報酬リンクを付けない（念のための止め）。

使う所：
  - 選手ページ・クラブページ・リーグページ（日本語・英語）の試合の配信の列
  - scripts/fetch_matches.py・scripts/fetch_uefa_secondary.py が data/matches.json に書く "broadcasters"
    （app.js の試合カード・試合の詳しい窓はこれを表示するだけ）

直接実行すると、いまの data/matches.json の全試合の "broadcasters" をこの取り出し方で書き直す：
  python3 scripts/watch_source.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEAGUE_GUIDES_JSON = REPO_ROOT / "data" / "league_guides.json"
BROADCASTERS_JSON = REPO_ROOT / "data" / "broadcasters.json"
MATCHES_JSON = REPO_ROOT / "data" / "matches.json"

SOURCE_TAG = "league_guides"


def _esc(text) -> str:
    if text is None:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def bc_brand_class(name: str) -> str:
    n = (name or "").lower()
    for key, cls in (("wowow", "bc-wowow"), ("dazn", "bc-dazn"), ("lemino", "bc-lemino"),
                     ("abema", "bc-abema"), ("u-next", "bc-unext"), ("unext", "bc-unext"),
                     ("bs10", "bc-bs10")):
        if key in n:
            return cls
    return "bc-default"


def load_league_guides() -> dict:
    if not LEAGUE_GUIDES_JSON.exists():
        return {}
    with open(LEAGUE_GUIDES_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_bc_services() -> dict:
    """broadcasters.json の services（ロゴ・affiliate_url）。古い broadcasters の欄は使わない。"""
    if not BROADCASTERS_JSON.exists():
        return {}
    with open(BROADCASTERS_JSON, encoding="utf-8") as f:
        return json.load(f).get("services", {})


def _league_slug_of(name_ja: str) -> str:
    try:
        from generate_league_pages import league_slug
        return league_slug(name_ja)
    except Exception:
        return ""


def find_watch_guide(guides: dict, competition_id=None, competition_ja: str = "") -> dict:
    """大会 → league_guides.json の watch（無ければ {}）。
    大会（CL・EL・ECL）は competition_id で、リーグはリーグ名（日本語）→ slug で引く。"""
    if not guides:
        return {}
    for cfg in (guides.get("competitions") or {}).values():
        if competition_id is not None and cfg.get("competition_id") == competition_id:
            return cfg.get("watch") or {}
    slug = _league_slug_of(competition_ja) if competition_ja else ""
    if not slug:
        return {}
    g = (guides.get("leagues") or {}).get(slug) or (guides.get("watch_only") or {}).get(slug) or {}
    return g.get("watch") or {}


def service_short(name: str) -> str:
    """「ABEMA（無料の生中継）」→「ABEMA」、「U-NEXT サッカーパック」→「U-NEXT」"""
    return (name or "").split("（")[0].split(" ")[0].strip() or (name or "")


def affiliate_for(sv: dict, bc_services: dict):
    """欄の1行 → 報酬リンク（付けないときは None）。"""
    us = sv.get("url_service")
    if not us:
        return None
    name = sv.get("name", "")
    # ABEMA の無料中継・ABEMA de DAZN に ABEMAプレミアムの報酬リンクは付けない
    if us == "ABEMA" and ("無料" in name or "de DAZN" in name or "free" in name.lower()):
        return None
    return (bc_services.get(us) or {}).get("affiliate_url") or None


def match_watch_services(guides: dict, bc_services: dict, competition_id=None, competition_ja: str = "") -> list:
    """試合の配信先の一覧。[{name, label, url, affiliate_url?, source}]（欄が無ければ []＝確認中）"""
    watch = find_watch_guide(guides, competition_id, competition_ja)
    out = []
    for sv in watch.get("services") or []:
        label = sv.get("name", "")
        item = {"name": service_short(label), "label": label, "url": sv.get("url", ""), "source": SOURCE_TAG}
        aff = affiliate_for(sv, bc_services)
        if aff:
            item["affiliate_url"] = aff
        out.append(item)
    return out


def build_watch_cell(guides: dict, bc_services: dict, competition_id, competition_ja: str,
                     page_type: str, page_id: str, unconfirmed_label: str = "確認中") -> tuple:
    """試合の配信の列のHTML。返り値：(html, 報酬リンクの数)。欄が無ければ「確認中」。"""
    svcs = match_watch_services(guides, bc_services, competition_id, competition_ja)
    if not svcs:
        return f'<span class="bc-unconfirmed">{_esc(unconfirmed_label)}</span>', 0
    n_aff = 0
    tags = []
    for sv in svcs:
        short, label = sv["name"], sv["label"]
        brand_cls = bc_brand_class(short)
        logo_file = (bc_services.get(short) or {}).get("logo", "")
        logo_html = (f'<img class="bc-logo" src="/assets/broadcasters/{_esc(logo_file)}" alt="" width="16" height="16">'
                     if logo_file else "")
        href, rel = sv.get("url", ""), "nofollow noopener"
        if sv.get("affiliate_url"):
            href, rel = sv["affiliate_url"], "sponsored nofollow noopener"
            n_aff += 1
        if href:
            tags.append(f'<a class="bc-tag {_esc(brand_cls)}" href="{_esc(href)}" target="_blank" rel="{rel}" '
                        f'title="{_esc(label)}" data-svc="{_esc(short)}" data-pagetype="{_esc(page_type)}" data-pageid="{_esc(page_id)}" '
                        f'onclick="trackAffClick(this)">{logo_html}{_esc(short)}</a>')
        else:
            tags.append(f'<span class="bc-tag {_esc(brand_cls)}" title="{_esc(label)}">{logo_html}{_esc(short)}</span>')
    return " ".join(tags), n_aff


def apply_to_matches(matches: list, guides: dict = None, bc_services: dict = None) -> int:
    """matches.json の全試合の "broadcasters" を、この取り出し方で書き直す（過去分も含めて）。
    返り値：書き直した試合の数。"""
    guides = load_league_guides() if guides is None else guides
    bc_services = load_bc_services() if bc_services is None else bc_services
    cache = {}
    n = 0
    for m in matches:
        key = (m.get("competition_id"), m.get("competition_ja", ""))
        if key not in cache:
            cache[key] = match_watch_services(guides, bc_services, *key)
        new = [dict(x) for x in cache[key]]
        if m.get("broadcasters") != new:
            n += 1
        m["broadcasters"] = new
    return n


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    data = json.loads(MATCHES_JSON.read_text(encoding="utf-8"))
    changed = apply_to_matches(data.get("matches", []))
    MATCHES_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] matches.json の配信を league_guides.json から書き直し：{changed}試合")
