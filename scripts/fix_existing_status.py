"""
既存 data/matches.json の status 補正スクリプト（一度限り実行用）

スコアが入っているのに status=SCHEDULED 等になっている試合を
status='FINISHED' に補正して上書き保存する。
"""
import json
import sys
from pathlib import Path

# スクリプトのディレクトリを基準にプロジェクトルートを特定
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"

sys.path.insert(0, str(SCRIPT_DIR))
from utils import fix_finished_status


def main():
    matches_path = DATA_DIR / "matches.json"
    if not matches_path.exists():
        print(f"[ERROR] {matches_path} が見つかりません")
        sys.exit(1)

    d = json.loads(matches_path.read_text(encoding="utf-8"))
    matches = d.get("matches", [])
    print(f"[INFO] 読み込み: {len(matches)}試合")

    fixed = fix_finished_status(matches)
    print(f"[INFO] 補正件数: {fixed}件")

    if fixed > 0:
        # 補正した試合を確認表示
        for m in matches:
            if m.get("status") == "FINISHED":
                score = m.get("score", {})
                if score and (score.get("home") is not None or score.get("away") is not None):
                    pass  # 正常な FINISHED
        d["matches"] = matches
        d["match_count"] = len(matches)
        matches_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {matches_path} を上書き保存しました。")
    else:
        print("[INFO] 補正対象なし。ファイルは変更しませんでした。")


if __name__ == "__main__":
    main()
