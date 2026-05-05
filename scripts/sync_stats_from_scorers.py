#!/usr/bin/env python3
"""
scorers.json の日本人選手データを player_stats.json に補完するスクリプト。
- 既存エントリは上書きしない（既存値を尊重）
- players.json から name_ja と club_ja を照合
- source: "scorers.json" を付与
"""

import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    scorers_path = os.path.join(ROOT, 'data', 'scorers.json')
    player_stats_path = os.path.join(ROOT, 'data', 'player_stats.json')
    players_path = os.path.join(ROOT, 'data', 'players.json')

    scorers_data = json.load(open(scorers_path, encoding='utf-8'))
    player_stats_data = json.load(open(player_stats_path, encoding='utf-8'))
    players_raw = json.load(open(players_path, encoding='utf-8'))

    # players.json の構造に応じてリストを取得
    if isinstance(players_raw, dict) and 'players' in players_raw:
        players_list = players_raw['players']
    elif isinstance(players_raw, list):
        players_list = players_raw
    else:
        players_list = []

    # name_en → name_ja / club_ja のマップを構築
    en_to_ja = {}
    en_to_club_ja = {}
    for p in players_list:
        if not isinstance(p, dict):
            continue
        name_en = p.get('name_en')
        if not name_en:
            continue
        en_to_ja[name_en] = p.get('name_ja', '')
        # current_club_ja がなければ club_ja を使用
        en_to_club_ja[name_en] = (
            p.get('current_club_ja') or
            p.get('club_ja') or
            p.get('current_club') or
            ''
        )

    stats = player_stats_data.get('stats', {})
    added = []

    # scorers の日本人選手を走査
    for cid, comp in scorers_data.get('competitions', {}).items():
        comp_name = comp.get('competition_name', f'comp_{cid}')
        for s in comp.get('scorers', []):
            if s.get('nationality') != 'Japan':
                continue
            name = s.get('player_name')
            if not name:
                continue
            if name in stats:
                print(f"  SKIP (already exists): {name}")
                continue

            # 補完データを構築
            goals = s.get('goals', 0) or 0
            assists = s.get('assists', 0) or 0
            played = s.get('playedMatches', 0) or 0
            team_ja = s.get('team_ja', '')

            entry = {
                'apps': played,
                'goals': goals,
                'assists': assists,
                'total_apps': played,   # リーグ戦のみ（scorers経由）
                'total_goals': goals,
                'club': team_ja,
                'club_ja': en_to_club_ja.get(name, team_ja),
                'name_ja': en_to_ja.get(name, ''),
                'source': 'scorers.json',
                'competition_id': int(cid),
                'competition_name': comp_name,
                'note': 'リーグ戦のみ（scorers経由）',
            }
            stats[name] = entry
            added.append(name)
            print(f"  ADD: {name} ({en_to_ja.get(name, '')}) — {goals}G {assists}A {played}試合 [{comp_name}]")

    # 書き戻し
    player_stats_data['stats'] = stats
    player_stats_data['total_players'] = len(stats)
    player_stats_data['updated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+09:00')

    with open(player_stats_path, 'w', encoding='utf-8') as f:
        json.dump(player_stats_data, f, ensure_ascii=False, indent=2)

    print(f"\nDone.")
    print(f"  Added players : {len(added)}")
    print(f"  Total players in stats: {len(stats)}")
    if added:
        print(f"  Added: {', '.join(added)}")


if __name__ == '__main__':
    main()
