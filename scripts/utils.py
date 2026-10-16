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


# 開始から何時間すぎても TIMED/SCHEDULED のままなら「結果待ち」とみなすか
# （サイト表示の app.js の RESULT_PENDING_HOURS と同じ値にそろえる）
RESULT_PENDING_HOURS = 3


def is_result_pending(m, now=None):
    """開始時刻から RESULT_PENDING_HOURS 時間すぎても status が TIMED/SCHEDULED のままの試合か。

    取り寄せ元が結果を入れてこない試合を「予定」に出し続けないための判定。
    スコアが入っている試合は終了扱いなので対象外（スコアは作らない）。
    """
    from datetime import datetime, timedelta, timezone
    if not isinstance(m, dict):
        return False
    if m.get('status') not in ('TIMED', 'SCHEDULED'):
        return False
    score = m.get('score')
    if isinstance(score, dict) and (score.get('home') is not None or score.get('away') is not None):
        return False
    ko_str = m.get('kickoff_jst') or ''
    try:
        ko = datetime.fromisoformat(ko_str.replace('Z', '+00:00'))
    except Exception:
        return False
    jst = timezone(timedelta(hours=9))
    if ko.tzinfo is None:
        ko = ko.replace(tzinfo=jst)
    if now is None:
        now = datetime.now(jst)
    return now - ko >= timedelta(hours=RESULT_PENDING_HOURS)
