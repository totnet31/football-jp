#!/usr/bin/env python3
"""
PWA meta tags, Service Worker registration, and Search injection script.
Injects PWA meta into <head> and SW/push/search scripts before </body>.
Also adds 🔍 search button next to the existing 🔔 notification button.
Skips files that already have manifest link.
Skips assets/logos/preview.html (not a real page).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PWA_META = """\
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="football-jp">
  <link rel="apple-touch-icon" href="/assets/logos/favicon-180.png">"""

SW_SCRIPT = '  <script src="/sw-register.js" defer></script>'

PUSH_SCRIPTS = """\
  <script src="/push-client.js" defer></script>
  <script src="/push-ui.js" defer></script>"""

SEARCH_SCRIPTS = """\
  <script src="/search.js" defer></script>
  <script src="/search-ui.js" defer></script>"""

SKIP_FILES = {
    os.path.join(ROOT, "assets", "logos", "preview.html"),
}

def find_html_files(root):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip node_modules, .git etc
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != 'node_modules']
        for fname in filenames:
            if fname.endswith('.html'):
                result.append(os.path.join(dirpath, fname))
    return sorted(result)

def inject_search_button(content, filepath):
    """
    🔔ボタンの隣に🔍ボタンを追加する。
    英語版かどうかでaria-labelを切り替える。
    既にfjSearchBtnがあればスキップ。
    """
    if 'fjSearchBtn' in content or 'openSearchModal' in content:
        return content, False

    is_en = '/en/' in filepath.replace(ROOT, '')

    search_btn_ja = '<button class="fjSearchBtn" onclick="openSearchModal()" title="検索 (Cmd+K)" aria-label="検索">🔍</button>'
    search_btn_en = '<button class="fjSearchBtn" onclick="openSearchModal()" title="Search (Cmd+K)" aria-label="Search">🔍</button>'
    search_btn = search_btn_en if is_en else search_btn_ja

    # 🔔通知ボタンを見つけてその隣（前）に追加
    # パターン1: onclick="openPushModal()" を含むボタン
    # 🔍を🔔の前に置く（視覚的に左）
    push_btn_pattern = re.compile(
        r'(<button[^>]+onclick="openPushModal\(\)"[^>]*>🔔</button>)',
        re.DOTALL
    )
    m = push_btn_pattern.search(content)
    if m:
        new_content = content[:m.start()] + search_btn + '\n      ' + m.group(0) + content[m.end():]
        return new_content, True

    # パターン2: ヘッダー内に追加（フォールバック：</header>の直前）
    if '</header>' in content:
        # ヘッダーに通知ボタンがないページへのフォールバックは実施しない
        # （デザインが壊れる可能性があるため）
        pass

    return content, False

def inject_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    modified = False

    # Check if manifest already present
    has_manifest = 'rel="manifest"' in content or "rel='manifest'" in content

    # Inject PWA meta into <head> if not present
    if not has_manifest:
        if '</head>' in content:
            content = content.replace('</head>', PWA_META + '\n</head>', 1)
            modified = True

    # Check if SW register script already present
    has_sw = '/sw-register.js' in content

    if not has_sw:
        if '</body>' in content:
            content = content.replace('</body>', SW_SCRIPT + '\n</body>', 1)
            modified = True

    # Check if push scripts already present
    has_push = '/push-client.js' in content

    if not has_push:
        if '</body>' in content:
            content = content.replace('</body>', PUSH_SCRIPTS + '\n</body>', 1)
            modified = True

    # Check if search scripts already present
    has_search = '/search.js' in content

    if not has_search:
        if '</body>' in content:
            content = content.replace('</body>', SEARCH_SCRIPTS + '\n</body>', 1)
            modified = True

    # Inject 🔍 search button next to 🔔
    content, btn_modified = inject_search_button(content, path)
    if btn_modified:
        modified = True

    if modified:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    html_files = find_html_files(ROOT)
    processed = 0
    skipped = 0
    for path in html_files:
        if path in SKIP_FILES:
            print(f"  SKIP (excluded): {os.path.relpath(path, ROOT)}")
            skipped += 1
            continue
        result = inject_file(path)
        if result:
            print(f"  OK: {os.path.relpath(path, ROOT)}")
            processed += 1
        else:
            print(f"  SKIP (already up-to-date): {os.path.relpath(path, ROOT)}")
            skipped += 1

    print(f"\nDone. Updated: {processed}, Skipped: {skipped}, Total: {len(html_files)}")

if __name__ == '__main__':
    main()
