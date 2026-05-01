# football-jp

海外サッカー日本人選手の試合スケジュール・W杯2026特集サイト

🌐 **本番URL：** https://football-jp.com/
🏆 **W杯2026特集：** https://football-jp.com/worldcup/

## 主な機能

### 海外サッカー（メインページ）
- プレミア / ラ・リーガ / セリエA / ブンデス / リーグ1 / エールディビジ / プリメイラリーガ / チャンピオンズリーグ / ヨーロッパリーグ
- 日本人選手の出場試合をハイライト（🇯🇵バッジ）
- 試合結果＋日本人選手の得点を🇯🇵Gコーナーバッジで表示
- 試合カードクリックで詳細モーダル（全得点者・配信局・YouTube公式ハイライト）
- カレンダー・順位表・得点ランキング

### W杯2026 特集（/worldcup/）
- 48か国全プロフィール（FIFAランク・監督・W杯成績）
- 各国スカッド（生年月日・身長・体重）
- グループ12組×4チームの順位表
- 決勝トーナメント表（クラシック横長ブラケット）
- 日本代表の進出経路
- 大会ルール・会場情報

## データソース

| ソース | 用途 |
|---|---|
| football-data.org | 試合スケジュール・スコア（全リーグ） |
| Wikipedia | 国別プロフィール、スカッド、日本人選手の得点抽出 |
| worldcdb.com | 各国代表スカッド（身長・体重・生年月日） |
| YouTube公式チャンネル | ハイライト動画（DAZN / U-NEXT / WOWOW / ABEMA） |

## 自動更新

毎朝7時JSTにGitHub Actions cronが実行：
1. `scripts/fetch_matches.py` — 試合データ更新（football-data.org）
2. `scripts/fetch_wc.py` — W杯2026データ更新
3. `scripts/fetch_wiki_events.py` — Wikipedia 日本人選手の得点抽出
4. `scripts/scrape_youtube_highlights.py` — YouTube公式ハイライト自動取得

## ホスティング・デプロイフロー

- **Cloudflare Pages**でホスティング
- カスタムドメイン: `football-jp.com` / `www.football-jp.com`（apex に301リダイレクト）

### ブランチ運用
- `main` → **本番環境**（https://football-jp.com/）にデプロイ
- `develop` → **ステージング環境**（https://develop.football-jp.pages.dev/）にデプロイ
- その他の任意ブランチ → 各ブランチ専用のプレビューURL

### 推奨ワークフロー
1. `develop` ブランチで作業 → push
2. プレビューURL（`https://develop.football-jp.pages.dev/`）で動作確認
3. OK なら `main` にマージ → 本番反映

## ライセンス・出典

- データ提供: [Football data provided by the Football-Data.org API](https://www.football-data.org/)
- ハイライト動画: 各放送局公式YouTubeチャンネルへのリンクのみ提供
- ブラケット構造: Wikipedia "2026 FIFA World Cup knockout stage"
