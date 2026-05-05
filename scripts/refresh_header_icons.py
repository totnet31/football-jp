#!/usr/bin/env python3
"""
ヘッダーアイコンを絵文字からSVGに一括置換するスクリプト。
- 🔍 検索ボタン（class="fjSearchBtn"）→ class="fjHeaderBtn" + SVGアイコン
- 🔔 通知ボタン（onclick="openPushModal()"）→ class="fjHeaderBtn" + SVGアイコン
- 既存のインラインstyleは削除（CSSクラスに集約）
- 英語版(/en/)は title/aria-label を英語に
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEARCH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" '
    'stroke-width="1.8" stroke="currentColor" width="20" height="20" aria-hidden="true">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />'
    '</svg>'
)

BELL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" '
    'stroke-width="1.8" stroke="currentColor" width="20" height="20" aria-hidden="true">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75'
    'a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0'
    'm5.714 0a3 3 0 1 1-5.714 0" />'
    '</svg>'
)

SKIP_FILES = {
    os.path.join(ROOT, "assets", "logos", "preview.html"),
}


def is_en_file(filepath):
    rel = filepath.replace(ROOT, '')
    return '/en/' in rel


def replace_search_button(content, is_en):
    """
    class="fjSearchBtn" の検索ボタンを SVG 版に置換。
    絵文字 🔍 を SVG に変換し、class を fjHeaderBtn に変更。
    """
    title = 'Search (Cmd+K)' if is_en else '検索 (Cmd+K)'
    aria = 'Search' if is_en else '検索'

    new_btn = (
        f'<button class="fjHeaderBtn" onclick="openSearchModal()" '
        f'title="{title}" aria-label="{aria}">{SEARCH_SVG}</button>'
    )

    # パターン: <button class="fjSearchBtn" ...>🔍</button>
    # class の前後に他の属性があっても対応できるよう柔軟に
    pattern = re.compile(
        r'<button\s+[^>]*class="fjSearchBtn"[^>]*>\s*🔍\s*</button>',
        re.DOTALL
    )
    new_content, count = pattern.subn(new_btn, content)
    return new_content, count


def replace_push_button(content, is_en):
    """
    onclick="openPushModal()" の通知ボタンを SVG 版に置換。
    絵文字 🔔 を SVG に変換し、class を fjHeaderBtn に変更。
    インラインstyle は削除。
    """
    title = 'Notifications' if is_en else '通知設定'
    aria = 'Notifications' if is_en else '通知設定'

    new_btn = (
        f'<button class="fjHeaderBtn" onclick="openPushModal()" '
        f'title="{title}" aria-label="{aria}">{BELL_SVG}</button>'
    )

    # パターン: onclick="openPushModal()" を含むボタン（style属性あり・なし両方対応）
    pattern = re.compile(
        r'<button\s+[^>]*onclick="openPushModal\(\)"[^>]*>\s*🔔\s*</button>',
        re.DOTALL
    )
    new_content, count = pattern.subn(new_btn, content)
    return new_content, count


def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    is_en = is_en_file(path)

    content, search_count = replace_search_button(content, is_en)
    content, push_count = replace_push_button(content, is_en)

    total_replaced = search_count + push_count
    if total_replaced > 0 and content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return search_count, push_count
    return 0, 0


def find_html_files(root):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != 'node_modules']
        for fname in filenames:
            if fname.endswith('.html'):
                result.append(os.path.join(dirpath, fname))
    return sorted(result)


def main():
    html_files = find_html_files(ROOT)
    total_search = 0
    total_push = 0
    updated_files = 0
    skipped_files = 0

    for path in html_files:
        if path in SKIP_FILES:
            skipped_files += 1
            continue

        sc, pc = process_file(path)
        if sc + pc > 0:
            rel = os.path.relpath(path, ROOT)
            print(f"  OK: {rel} (search={sc}, push={pc})")
            total_search += sc
            total_push += pc
            updated_files += 1
        else:
            skipped_files += 1

    print(f"\nDone.")
    print(f"  Updated files : {updated_files}")
    print(f"  Skipped files : {skipped_files}")
    print(f"  Search btns replaced : {total_search}")
    print(f"  Push btns replaced   : {total_push}")


if __name__ == '__main__':
    main()
