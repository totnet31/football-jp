"""
football-jp 共通ユーティリティ関数
"""


def fix_finished_status(matches):
    """過去キックオフ + スコア入り → status='FINISHED' に補正

    データ提供元（football-data.org / Wikipedia 等）が status を正しく更新しない
    ケースをカバー。
    """
    fixed_count = 0
    for m in matches:
        if not isinstance(m, dict):
            continue
        if m.get('status') == 'FINISHED':
            continue
        score = m.get('score')
        if not isinstance(score, dict):
            continue
        home_score = score.get('home')
        away_score = score.get('away')
        if home_score is None and away_score is None:
            continue
        # スコアが入っていれば終了扱い
        m['status'] = 'FINISHED'
        fixed_count += 1
    return fixed_count
