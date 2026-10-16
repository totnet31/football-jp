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


def fix_unplayed_finished(matches, now=None):
    """開始時刻がまだ来ていないのに「終了（FINISHED）」やスコア入りになっている試合を、予定の試合に戻す。

    取り寄せ元が未来の試合を FINISHED 0-0 で返してくることがある（2026-10 ラ・リーガ
    レバンテ対アスレティック・ビルバオ 10/22）。そのまま出すと「終了 0-0」と表示されるため、
    ページを作るときだけ status を TIMED に、スコアを空にして扱う（data/ のファイルは書き換えない）。
    サイト表示の app.js の normalizeUnplayedFinished と同じ判定。
    戻した件数を返す。
    """
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    if now is None:
        now = datetime.now(jst)
    fixed = 0
    for m in matches or []:
        if not isinstance(m, dict):
            continue
        score = m.get('score')
        has_score = isinstance(score, dict) and (score.get('home') is not None or score.get('away') is not None)
        if m.get('status') != 'FINISHED' and not has_score:
            continue
        try:
            ko = datetime.fromisoformat((m.get('kickoff_jst') or '').replace('Z', '+00:00'))
        except Exception:
            continue
        if ko.tzinfo is None:
            ko = ko.replace(tzinfo=jst)
        if ko <= now:
            continue
        m['status'] = 'TIMED'
        if isinstance(score, dict):
            m['score'] = {**score, 'home': None, 'away': None}
        fixed += 1
    return fixed
