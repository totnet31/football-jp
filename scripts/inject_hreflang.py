#!/usr/bin/env python3
"""
inject_hreflang.py
日本語版の選手・クラブページに hreflang タグを注入するスクリプト。
canonical タグの直後に挿入する。
既に hreflang が存在する場合はスキップ（冪等）。
使い方: python3 scripts/inject_hreflang.py
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SITE_URL = "https://football-jp.com"


def inject_hreflang_to_file(path: Path, ja_url: str, en_url: str) -> bool:
    """
    ファイルを読み込んで hreflang を注入する。
    変更があった場合は True を返す。
    """
    content = path.read_text(encoding="utf-8")

    # 既に hreflang がある場合はスキップ
    if 'hreflang' in content:
        return False

    hreflang_tags = (
        f'  <link rel="alternate" hreflang="ja" href="{ja_url}">\n'
        f'  <link rel="alternate" hreflang="en" href="{en_url}">\n'
        f'  <link rel="alternate" hreflang="x-default" href="{ja_url}">\n'
    )

    # canonical タグの直後に挿入
    canonical_pattern = re.compile(r'(<link rel="canonical"[^>]+>)\n')
    if canonical_pattern.search(content):
        new_content = canonical_pattern.sub(r'\1\n' + hreflang_tags, content, count=1)
        path.write_text(new_content, encoding="utf-8")
        return True

    return False


def main():
    injected_players = 0
    injected_clubs = 0

    # --- 選手ページ ---
    players_dir = REPO_ROOT / "players"
    for slug_dir in sorted(players_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        index_html = slug_dir / "index.html"
        if not index_html.exists():
            continue
        slug = slug_dir.name
        ja_url = f"{SITE_URL}/players/{slug}/"
        en_url = f"{SITE_URL}/en/players/{slug}/"
        changed = inject_hreflang_to_file(index_html, ja_url, en_url)
        if changed:
            injected_players += 1
            print(f"  ✅ [player] /players/{slug}/")

    # --- クラブページ ---
    clubs_dir = REPO_ROOT / "clubs"
    for slug_dir in sorted(clubs_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        index_html = slug_dir / "index.html"
        if not index_html.exists():
            continue
        slug = slug_dir.name
        ja_url = f"{SITE_URL}/clubs/{slug}/"
        en_url = f"{SITE_URL}/en/clubs/{slug}/"
        changed = inject_hreflang_to_file(index_html, ja_url, en_url)
        if changed:
            injected_clubs += 1
            print(f"  ✅ [club] /clubs/{slug}/")

    print(f"\nhreflang 注入完了: 選手 {injected_players} ページ、クラブ {injected_clubs} ページ")
    return injected_players, injected_clubs


if __name__ == "__main__":
    main()
