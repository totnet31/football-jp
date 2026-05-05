#!/usr/bin/env python3
"""
generate_wc_country_history_pages.py
W杯国別出場履歴ページを生成するスクリプト。

入力:  data/wc2026/wc_history.json
       data/wc2026/wc_history_detail/{year}.json
出力:  worldcup/history/countries/{slug}/index.html (日本語)
       en/worldcup/history/countries/{slug}/index.html (英語)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
WC_HISTORY = ROOT / "data" / "wc2026" / "wc_history.json"
WC_DETAIL_DIR = ROOT / "data" / "wc2026" / "wc_history_detail"
JST = timezone(timedelta(hours=9))

# 対象国の定義
COUNTRIES = [
    {
        "slug": "brazil",
        "name_ja": "ブラジル",
        "name_en": "Brazil",
        "flag": "🇧🇷",
        "appearances": 22,
        "titles": 5,
        "title_years": [1958, 1962, 1970, 1994, 2002],
        "runner_up": 2,
        "runner_up_years": [1950, 1998],
        "third_place": 2,
        "best_result_ja": "優勝5回（最多）",
        "best_result_en": "5-time Champion (most ever)",
        "description_ja": "唯一の全大会出場国。ペレ・ロナウド・ネイマールを擁し、W杯最多5回優勝を誇る「王国」。",
        "description_en": "The only nation to appear in every World Cup. Five-time champions featuring Pelé, Ronaldo, and Neymar.",
        "legends": [
            {"name": "ペレ", "name_en": "Pelé", "years": "1958–1970", "goals": 12, "note": "3度の優勝。W杯最年少ゴール（17歳）。"},
            {"name": "ロナウド", "name_en": "Ronaldo (R9)", "years": "1994–2006", "goals": 15, "note": "歴代2位の通算15得点。2002年大会MVP。"},
            {"name": "ジーコ", "name_en": "Zico", "years": "1978–1986", "goals": 5, "note": "82年大会の悲劇も含め3大会出場。「白いペレ」。"},
            {"name": "ロマーリオ", "name_en": "Romário", "years": "1990–1994", "goals": 5, "note": "1994年優勝時の主砲。大会MVP。"},
        ],
        "japan_matches": [
            {"year": 2006, "stage": "GS", "score": "1-4", "result": "負け", "note": "2006年大会GS"},
        ],
    },
    {
        "slug": "germany",
        "name_ja": "ドイツ（西ドイツ含む）",
        "name_en": "Germany (incl. West Germany)",
        "flag": "🇩🇪",
        "appearances": 20,
        "titles": 4,
        "title_years": [1954, 1974, 1990, 2014],
        "runner_up": 4,
        "runner_up_years": [1966, 1982, 1986, 2002],
        "third_place": 4,
        "best_result_ja": "優勝4回",
        "best_result_en": "4-time Champion",
        "description_ja": "一貫してW杯で上位に進出する強豪。西ドイツ時代を含め4回優勝・4回準優勝。ゲルト・ミュラー・クローゼら歴代得点王を輩出。",
        "description_en": "Perennial contenders. Four-time champions including West Germany era. Home of all-time top scorer Miroslav Klose.",
        "legends": [
            {"name": "ゲルト・ミュラー", "name_en": "Gerd Müller", "years": "1970–1974", "goals": 14, "note": "歴代3位の14得点。「ボンバー」の異名。"},
            {"name": "ミロスラフ・クローゼ", "name_en": "Miroslav Klose", "years": "2002–2014", "goals": 16, "note": "歴代最多16得点。4大会連続出場。"},
            {"name": "フランツ・ベッケンバウアー", "name_en": "Franz Beckenbauer", "years": "1966–1974", "goals": 5, "note": "選手・監督の両方でW杯制覇した唯一の人物。"},
            {"name": "ロタール・マテウス", "name_en": "Lothar Matthäus", "years": "1982–1998", "goals": 6, "note": "5大会出場の歴代最多出場記録（当時）。"},
        ],
        "japan_matches": [
            {"year": 2022, "stage": "GS", "score": "2-1", "result": "日本の勝ち", "note": "カタール大会、歴史的番狂わせ"},
        ],
    },
    {
        "slug": "italy",
        "name_ja": "イタリア",
        "name_en": "Italy",
        "flag": "🇮🇹",
        "appearances": 18,
        "titles": 4,
        "title_years": [1934, 1938, 1982, 2006],
        "runner_up": 2,
        "runner_up_years": [1970, 1994],
        "third_place": 1,
        "best_result_ja": "優勝4回",
        "best_result_en": "4-time Champion",
        "description_ja": "イタリアは堅守速攻「カテナチオ」で知られる欧州の雄。1934・1938年の連覇、1982・2006年の優勝で歴代4勝を誇る。",
        "description_en": "Italian football powerhouse known for 'Catenaccio' defense. Four-time World Cup winners across eight decades.",
        "legends": [
            {"name": "パオロ・ロッシ", "name_en": "Paolo Rossi", "years": "1978–1982", "goals": 9, "note": "1982年大会で6得点・MVP・優勝の三冠達成。"},
            {"name": "ロベルト・バッジョ", "name_en": "Roberto Baggio", "years": "1990–1998", "goals": 9, "note": "1994年大会のPK失敗は今も語り継がれる悲劇。"},
            {"name": "ジャンニ・リベラ", "name_en": "Gianni Rivera", "years": "1962–1974", "goals": 3, "note": "イタリアを代表するファンタジスタ。"},
            {"name": "ファビオ・カンナバーロ", "name_en": "Fabio Cannavaro", "years": "1998–2010", "goals": 0, "note": "2006年大会キャプテン。同年バロンドール受賞。"},
        ],
        "japan_matches": [],
    },
    {
        "slug": "argentina",
        "name_ja": "アルゼンチン",
        "name_en": "Argentina",
        "flag": "🇦🇷",
        "appearances": 18,
        "titles": 3,
        "title_years": [1978, 1986, 2022],
        "runner_up": 3,
        "runner_up_years": [1930, 1990, 2014],
        "third_place": 0,
        "best_result_ja": "優勝3回",
        "best_result_en": "3-time Champion",
        "description_ja": "マラドーナ・メッシという2人の世界最高選手を擁し3度のW杯制覇。2022年カタール大会でメッシがついに悲願の頂点に立った。",
        "description_en": "Home of Maradona and Messi — arguably the two greatest players ever. Won in 1978, 1986, and 2022.",
        "legends": [
            {"name": "ディエゴ・マラドーナ", "name_en": "Diego Maradona", "years": "1982–1994", "goals": 8, "note": "1986年大会MVP・優勝。「神の手」と「5人抜き」は伝説。"},
            {"name": "リオネル・メッシ", "name_en": "Lionel Messi", "years": "2006–2022", "goals": 13, "note": "5大会出場・通算13得点。2022年大会MVP・優勝でレジェンド完成。"},
            {"name": "マリオ・ケンペス", "name_en": "Mario Kempes", "years": "1974–1982", "goals": 6, "note": "1978年大会得点王・優勝。開催国アルゼンチンのヒーロー。"},
            {"name": "ガブリエル・バティストゥータ", "name_en": "Gabriel Batistuta", "years": "1994–2002", "goals": 10, "note": "「バティゴール」。3大会10得点で歴代トップ10に入る。"},
        ],
        "japan_matches": [
            {"year": 1998, "stage": "GS", "score": "0-1", "result": "負け", "note": "日本初のW杯での対戦"},
        ],
    },
    {
        "slug": "france",
        "name_ja": "フランス",
        "name_en": "France",
        "flag": "🇫🇷",
        "appearances": 16,
        "titles": 2,
        "title_years": [1998, 2018],
        "runner_up": 1,
        "runner_up_years": [2022],
        "third_place": 2,
        "best_result_ja": "優勝2回",
        "best_result_en": "2-time Champion",
        "description_ja": "1998年の自国開催優勝でW杯の表舞台に。その後ムバッペ率いる2018年優勝・2022年準優勝で現代サッカーの頂点に君臨。",
        "description_en": "Won in 1998 (hosts) and 2018, and were runners-up in 2022. Kylian Mbappé leads a new golden generation.",
        "legends": [
            {"name": "ジュスト・フォンテーヌ", "name_en": "Just Fontaine", "years": "1958", "goals": 13, "note": "1大会13得点の不滅記録保持者。1大会のみ出場。"},
            {"name": "ジネディーヌ・ジダン", "name_en": "Zinedine Zidane", "years": "1998–2006", "goals": 5, "note": "1998年決勝2G・優勝。2006年決勝退場も記憶に残る。"},
            {"name": "キリアン・ムバッペ", "name_en": "Kylian Mbappé", "years": "2018–", "goals": 12, "note": "2018・2022年大会で12得点。クローゼ記録への挑戦が期待される。"},
            {"name": "ティエリ・アンリ", "name_en": "Thierry Henry", "years": "1998–2010", "goals": 6, "note": "1998年優勝メンバー。フランスの象徴的ストライカー。"},
        ],
        "japan_matches": [],
    },
    {
        "slug": "uruguay",
        "name_ja": "ウルグアイ",
        "name_en": "Uruguay",
        "flag": "🇺🇾",
        "appearances": 14,
        "titles": 2,
        "title_years": [1930, 1950],
        "runner_up": 0,
        "runner_up_years": [],
        "third_place": 0,
        "best_result_ja": "優勝2回（第1・2回大会）",
        "best_result_en": "2-time Champion (1st & 2nd editions)",
        "description_ja": "第1回大会（1930）・第4回大会（1950）の優勝国。南米の小国ながら「マラカナンの奇跡」でブラジルを破った伝説を持つ。",
        "description_en": "Winners of the inaugural 1930 and 1950 tournaments. Famous for the 'Maracanazo' upset victory over host Brazil in 1950.",
        "legends": [
            {"name": "アルカンタラ", "name_en": "José Leandro Andrade", "years": "1930", "goals": 0, "note": "1930年初代王者の守備の要。"},
            {"name": "フアン・スキアフィーノ", "name_en": "Juan Schiaffino", "years": "1950–1954", "goals": 4, "note": "1950年決勝の同点弾。マラカナンの奇跡の主役。"},
            {"name": "ルイス・スアレス", "name_en": "Luis Suárez", "years": "2010–2022", "goals": 7, "note": "4大会出場。2010年大会ハンドで物議を醸した。"},
            {"name": "エディンソン・カバーニ", "name_en": "Edinson Cavani", "years": "2010–2022", "goals": 5, "note": "4大会出場のウルグアイの点取り屋。"},
        ],
        "japan_matches": [],
    },
    {
        "slug": "england",
        "name_ja": "イングランド",
        "name_en": "England",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "appearances": 16,
        "titles": 1,
        "title_years": [1966],
        "runner_up": 0,
        "runner_up_years": [],
        "third_place": 1,
        "best_result_ja": "優勝1回（1966年・自国開催）",
        "best_result_en": "1-time Champion (1966, as hosts)",
        "description_ja": "サッカー発祥の国。自国開催の1966年大会でのみ優勝。「サッカーが帰ってきた」と呼ばれた歴史的優勝も、以降は準決勝が最高成績。",
        "description_en": "The birthplace of football. Won only once, in 1966 on home soil. Perennial contenders yet to replicate that glory.",
        "legends": [
            {"name": "ガリー・リネカー", "name_en": "Gary Lineker", "years": "1986–1990", "goals": 10, "note": "2大会合計10得点。1986年大会得点王。"},
            {"name": "ボビー・チャールトン", "name_en": "Bobby Charlton", "years": "1958–1970", "goals": 5, "note": "1966年優勝の主力。イングランドの国民的英雄。"},
            {"name": "ハリー・ケイン", "name_en": "Harry Kane", "years": "2018–", "goals": 8, "note": "2018年大会得点王（6得点）。現役世代の主砲。"},
            {"name": "マイケル・オーウェン", "name_en": "Michael Owen", "years": "1998–2006", "goals": 2, "note": "1998年大会で爆発的デビューを飾った若きストライカー。"},
        ],
        "japan_matches": [],
    },
    {
        "slug": "spain",
        "name_ja": "スペイン",
        "name_en": "Spain",
        "flag": "🇪🇸",
        "appearances": 16,
        "titles": 1,
        "title_years": [2010],
        "runner_up": 0,
        "runner_up_years": [],
        "third_place": 0,
        "best_result_ja": "優勝1回（2010年）",
        "best_result_en": "1-time Champion (2010)",
        "description_ja": "「ティキタカ」の代名詞。2010年南アフリカ大会でW杯初優勝。欧州選手権3連覇も達成した黄金世代を誇る。",
        "description_en": "Masters of 'tiki-taka' possession football. First and only World Cup title in 2010, part of a historic golden generation.",
        "legends": [
            {"name": "ダビド・ビジャ", "name_en": "David Villa", "years": "2006–2014", "goals": 9, "note": "スペイン代表の歴代最多得点者。2010年大会得点王。"},
            {"name": "シャビ", "name_en": "Xavi", "years": "2002–2014", "goals": 0, "note": "ティキタカの司令塔。2010年大会優勝の中核。"},
            {"name": "アンドレス・イニエスタ", "name_en": "Andrés Iniesta", "years": "2006–2014", "goals": 1, "note": "2010年決勝の決勝ゴール。W杯MVP受賞。"},
            {"name": "ラウール", "name_en": "Raúl", "years": "1998–2006", "goals": 4, "note": "スペインの1990〜2000年代を代表するストライカー。"},
        ],
        "japan_matches": [
            {"year": 2022, "stage": "GS", "score": "2-1", "result": "日本の勝ち", "note": "カタール大会、歴史的番狂わせ"},
        ],
    },
    {
        "slug": "japan",
        "name_ja": "日本",
        "name_en": "Japan",
        "flag": "🇯🇵",
        "appearances": 7,
        "titles": 0,
        "title_years": [],
        "runner_up": 0,
        "runner_up_years": [],
        "third_place": 0,
        "best_result_ja": "ベスト16（4回: 2002, 2010, 2018, 2022）",
        "best_result_en": "Round of 16 (4 times: 2002, 2010, 2018, 2022)",
        "description_ja": "1998年フランス大会から7大会連続出場。2002年自国開催でベスト16。2022年カタール大会ではドイツ・スペインを撃破し話題に。2026年大会はグループFに入る。",
        "description_en": "Seven consecutive World Cup appearances since 1998. Upset Germany and Spain at Qatar 2022. In Group F for the 2026 edition.",
        "legends": [
            {"name": "中田英寿", "name_en": "Hidetoshi Nakata", "years": "1998–2006", "goals": 2, "note": "セリエAで活躍した日本サッカーの顔。3大会出場。"},
            {"name": "三浦知良", "name_en": "Kazuyoshi Miura", "years": "1998（落選）", "goals": 0, "note": "代表の象徴も1998年直前に落選。W杯は出場なし。"},
            {"name": "本田圭佑", "name_en": "Keisuke Honda", "years": "2010–2018", "goals": 4, "note": "3大会出場。2010・2018年大会でゴールを記録。"},
            {"name": "岡崎慎司", "name_en": "Shinji Okazaki", "years": "2010–2018", "goals": 3, "note": "3大会出場。チームのためのプレーで知られる献身的FW。"},
        ],
        "japan_matches": [],  # 自国なので対戦相手視点は不要
    },
    {
        "slug": "netherlands",
        "name_ja": "オランダ",
        "name_en": "Netherlands",
        "flag": "🇳🇱",
        "appearances": 11,
        "titles": 0,
        "title_years": [],
        "runner_up": 3,
        "runner_up_years": [1974, 1978, 2010],
        "third_place": 2,
        "best_result_ja": "準優勝3回（優勝なし）",
        "best_result_en": "3-time Runner-up (never won)",
        "description_ja": "1974・1978・2010年の3度の準優勝を誇るが、いまだ優勝はない。ヨハン・クライフの「トータルフットボール」は世界中に影響を与えた。",
        "description_en": "Three-time runners-up (1974, 1978, 2010) but never champions. Johan Cruyff's 'Total Football' revolutionized the game worldwide.",
        "legends": [
            {"name": "ヨハン・クライフ", "name_en": "Johan Cruyff", "years": "1974", "goals": 3, "note": "「クライフターン」の発明者。トータルフットボールの体現者。"},
            {"name": "ロベルト・レンセンブリンク", "name_en": "Rob Rensenbrink", "years": "1974–1978", "goals": 7, "note": "1978年大会でポストに当たったシュートが準優勝の象徴。"},
            {"name": "ルート・ファン・ニステルローイ", "name_en": "Ruud van Nistelrooy", "years": "1998–2006", "goals": 1, "note": "欧州で活躍した点取り屋。代表での成績は伸び悩む。"},
            {"name": "ウェスレイ・スナイデル", "name_en": "Wesley Sneijder", "years": "2006–2014", "goals": 6, "note": "2010年大会準優勝の主力。バロンドール最終候補にも入った。"},
        ],
        "japan_matches": [],
    },
]

# 全22大会の年一覧
ALL_YEARS = [
    1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966,
    1970, 1974, 1978, 1982, 1986, 1990, 1994,
    1998, 2002, 2006, 2010, 2014, 2018, 2022,
]

# 各国の出場年・成績マップ（知識ベース）
COUNTRY_RESULTS = {
    "brazil": {
        1930: {"result_ja": "準決勝", "result_en": "Semifinals"},
        1934: {"result_ja": "1回戦", "result_en": "1st Round"},
        1938: {"result_ja": "3位", "result_en": "3rd Place"},
        1950: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1954: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1958: {"result_ja": "優勝", "result_en": "Champion"},
        1962: {"result_ja": "優勝", "result_en": "Champion"},
        1966: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1970: {"result_ja": "優勝", "result_en": "Champion"},
        1974: {"result_ja": "4位", "result_en": "4th Place"},
        1978: {"result_ja": "3位", "result_en": "3rd Place"},
        1982: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1986: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1990: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1994: {"result_ja": "優勝", "result_en": "Champion"},
        1998: {"result_ja": "準優勝", "result_en": "Runner-up"},
        2002: {"result_ja": "優勝", "result_en": "Champion"},
        2006: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2010: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2014: {"result_ja": "4位", "result_en": "4th Place"},
        2018: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2022: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
    },
    "germany": {
        1930: None,  # 不出場
        1934: {"result_ja": "3位", "result_en": "3rd Place"},
        1938: {"result_ja": "1回戦", "result_en": "1st Round"},
        1950: None,  # 出場停止
        1954: {"result_ja": "優勝", "result_en": "Champion"},
        1958: {"result_ja": "4位", "result_en": "4th Place"},
        1962: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1966: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1970: {"result_ja": "3位", "result_en": "3rd Place"},
        1974: {"result_ja": "優勝", "result_en": "Champion"},
        1978: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1982: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1986: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1990: {"result_ja": "優勝", "result_en": "Champion"},
        1994: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1998: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2002: {"result_ja": "準優勝", "result_en": "Runner-up"},
        2006: {"result_ja": "3位", "result_en": "3rd Place"},
        2010: {"result_ja": "3位", "result_en": "3rd Place"},
        2014: {"result_ja": "優勝", "result_en": "Champion"},
        2018: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2022: {"result_ja": "GS敗退", "result_en": "Group Stage"},
    },
    "italy": {
        1930: None,
        1934: {"result_ja": "優勝", "result_en": "Champion"},
        1938: {"result_ja": "優勝", "result_en": "Champion"},
        1950: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1954: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1958: None,  # 予選敗退
        1962: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1966: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1970: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1974: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1978: {"result_ja": "4位", "result_en": "4th Place"},
        1982: {"result_ja": "優勝", "result_en": "Champion"},
        1986: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1990: {"result_ja": "3位", "result_en": "3rd Place"},
        1994: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1998: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2002: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2006: {"result_ja": "優勝", "result_en": "Champion"},
        2010: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2014: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2018: None,  # 予選敗退
        2022: None,  # 予選敗退
    },
    "argentina": {
        1930: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1934: {"result_ja": "1回戦", "result_en": "1st Round"},
        1938: None,
        1950: None,
        1954: None,
        1958: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1962: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1966: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1970: None,
        1974: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1978: {"result_ja": "優勝", "result_en": "Champion"},
        1982: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1986: {"result_ja": "優勝", "result_en": "Champion"},
        1990: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1994: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1998: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2002: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2006: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2010: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2014: {"result_ja": "準優勝", "result_en": "Runner-up"},
        2018: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2022: {"result_ja": "優勝", "result_en": "Champion"},
    },
    "france": {
        1930: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1934: {"result_ja": "1回戦", "result_en": "1st Round"},
        1938: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1950: None,
        1954: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1958: {"result_ja": "3位", "result_en": "3rd Place"},
        1962: None,
        1966: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1970: None,
        1974: None,
        1978: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1982: {"result_ja": "4位", "result_en": "4th Place"},
        1986: {"result_ja": "3位", "result_en": "3rd Place"},
        1990: None,
        1994: None,
        1998: {"result_ja": "優勝", "result_en": "Champion"},
        2002: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2006: {"result_ja": "準優勝", "result_en": "Runner-up"},
        2010: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2014: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2018: {"result_ja": "優勝", "result_en": "Champion"},
        2022: {"result_ja": "準優勝", "result_en": "Runner-up"},
    },
    "uruguay": {
        1930: {"result_ja": "優勝", "result_en": "Champion"},
        1934: None,
        1938: None,
        1950: {"result_ja": "優勝", "result_en": "Champion"},
        1954: {"result_ja": "4位", "result_en": "4th Place"},
        1958: None,
        1962: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1966: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1970: {"result_ja": "4位", "result_en": "4th Place"},
        1974: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1978: None,
        1982: None,
        1986: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1990: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1994: None,
        1998: None,
        2002: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2006: None,
        2010: {"result_ja": "4位", "result_en": "4th Place"},
        2014: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2018: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2022: {"result_ja": "GS敗退", "result_en": "Group Stage"},
    },
    "england": {
        1930: None,
        1934: None,
        1938: None,
        1950: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1954: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1958: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1962: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1966: {"result_ja": "優勝", "result_en": "Champion"},
        1970: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1974: None,
        1978: None,
        1982: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1986: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1990: {"result_ja": "4位", "result_en": "4th Place"},
        1994: None,
        1998: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2002: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2006: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2010: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2014: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2018: {"result_ja": "4位", "result_en": "4th Place"},
        2022: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
    },
    "spain": {
        1930: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1934: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1938: None,
        1950: {"result_ja": "4位", "result_en": "4th Place"},
        1954: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1958: None,
        1962: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1966: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1970: None,
        1974: None,
        1978: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        1982: {"result_ja": "2次グループL", "result_en": "2nd Round"},
        1986: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1990: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1994: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1998: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2002: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        2006: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2010: {"result_ja": "優勝", "result_en": "Champion"},
        2014: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2018: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2022: {"result_ja": "ベスト16", "result_en": "Round of 16"},
    },
    "japan": {
        1930: None, 1934: None, 1938: None, 1950: None,
        1954: None, 1958: None, 1962: None, 1966: None,
        1970: None, 1974: None, 1978: None, 1982: None,
        1986: None, 1990: None, 1994: None,
        1998: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2002: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2006: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2010: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2014: {"result_ja": "GS敗退", "result_en": "Group Stage"},
        2018: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2022: {"result_ja": "ベスト16", "result_en": "Round of 16"},
    },
    "netherlands": {
        1930: None, 1934: {"result_ja": "1回戦", "result_en": "1st Round"},
        1938: {"result_ja": "1回戦", "result_en": "1st Round"},
        1950: None, 1954: None, 1958: None, 1962: None, 1966: None,
        1970: None,
        1974: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1978: {"result_ja": "準優勝", "result_en": "Runner-up"},
        1982: None, 1986: None,
        1990: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        1994: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
        1998: {"result_ja": "4位", "result_en": "4th Place"},
        2002: None,
        2006: {"result_ja": "ベスト16", "result_en": "Round of 16"},
        2010: {"result_ja": "準優勝", "result_en": "Runner-up"},
        2014: {"result_ja": "3位", "result_en": "3rd Place"},
        2018: None,
        2022: {"result_ja": "準々決勝", "result_en": "Quarter-finals"},
    },
}

# ホスト国情報
HOST_COUNTRY = {
    1930: "Uruguay", 1934: "Italy", 1938: "France", 1950: "Brazil",
    1954: "Switzerland", 1958: "Sweden", 1962: "Chile", 1966: "England",
    1970: "Mexico", 1974: "West Germany", 1978: "Argentina", 1982: "Spain",
    1986: "Mexico", 1990: "Italy", 1994: "USA", 1998: "France",
    2002: "Japan/Korea", 2006: "Germany", 2010: "South Africa",
    2014: "Brazil", 2018: "Russia", 2022: "Qatar",
}
HOST_COUNTRY_JA = {
    1930: "ウルグアイ", 1934: "イタリア", 1938: "フランス", 1950: "ブラジル",
    1954: "スイス", 1958: "スウェーデン", 1962: "チリ", 1966: "イングランド",
    1970: "メキシコ", 1974: "西ドイツ", 1978: "アルゼンチン", 1982: "スペイン",
    1986: "メキシコ", 1990: "イタリア", 1994: "アメリカ合衆国", 1998: "フランス",
    2002: "日本・韓国", 2006: "ドイツ", 2010: "南アフリカ",
    2014: "ブラジル", 2018: "ロシア", 2022: "カタール",
}


def result_class(result_ja):
    if result_ja is None:
        return "not-qualified"
    if "優勝" in result_ja:
        return "champion"
    if "準優勝" in result_ja:
        return "runner-up"
    if "3位" in result_ja:
        return "third"
    if "4位" in result_ja:
        return "fourth"
    if "準々決勝" in result_ja or "ベスト8" in result_ja:
        return "quarter"
    if "準決勝" in result_ja or "ベスト4" in result_ja:
        return "semi"
    if "ベスト16" in result_ja or "16" in result_ja:
        return "r16"
    if "GS" in result_ja or "グループ" in result_ja or "1回戦" in result_ja:
        return "gs"
    return "participated"


STYLE_BLOCK = """
    .country-hero {
      background: linear-gradient(135deg, #0b1220 0%, #1a2540 100%);
      color: #fff;
      padding: 24px 20px;
      margin-bottom: 24px;
    }
    .country-hero-flag { font-size: 40px; margin-bottom: 8px; }
    .country-hero h1 { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
    .country-hero-sub { font-size: 13px; color: #a0b0c8; margin: 0 0 12px; }
    .country-stats {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 12px;
    }
    .stat-box {
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.2);
      padding: 8px 14px;
      text-align: center;
      min-width: 80px;
    }
    .stat-box-num {
      font-size: 22px;
      font-weight: 800;
      display: block;
    }
    .stat-box-label {
      font-size: 11px;
      color: #a0b0c8;
    }
    .result-table { width: 100%; border-collapse: collapse; background: #fff; }
    .result-table th {
      background: var(--c-bg-subtle);
      padding: 8px 10px;
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      color: var(--c-text-sub);
      border-bottom: 2px solid var(--c-border-strong);
      white-space: nowrap;
    }
    .result-table td {
      padding: 8px 10px;
      border-bottom: 1px solid var(--c-border);
      font-size: 12.5px;
      vertical-align: middle;
    }
    .result-table tr:last-child td { border-bottom: none; }
    .result-badge {
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border: 1px solid;
    }
    .result-badge.champion { background: #fff8e1; color: #7a5c00; border-color: #d4af37; }
    .result-badge.runner-up { background: #f5f5f5; color: #444; border-color: #888; }
    .result-badge.third { background: #fdf3e7; color: #7a4400; border-color: #cd7f32; }
    .result-badge.fourth { background: #f5f5f5; color: #555; border-color: #bbb; }
    .result-badge.semi { background: #e8f4fd; color: #1565c0; border-color: #90caf9; }
    .result-badge.quarter { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
    .result-badge.r16 { background: #f3e5f5; color: #6a1b9a; border-color: #ce93d8; }
    .result-badge.gs { background: #f5f5f5; color: #666; border-color: #ccc; }
    .result-badge.not-qualified { background: #fafafa; color: #bbb; border-color: #e0e0e0; font-style: italic; }
    .legend-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 8px;
      margin-top: 8px;
    }
    .legend-card {
      background: #fff;
      border: 1px solid var(--c-border);
      padding: 12px 14px;
    }
    .legend-name { font-size: 14px; font-weight: 700; margin-bottom: 2px; }
    .legend-meta { font-size: 11px; color: var(--c-text-sub); margin-bottom: 4px; }
    .legend-note { font-size: 12px; color: var(--c-text); line-height: 1.5; }
    .source-note {
      font-size: 11px;
      color: var(--c-text-sub);
      margin-top: 12px;
      font-style: italic;
    }
    @media (max-width: 600px) {
      .legend-grid { grid-template-columns: 1fr; }
      .country-stats { gap: 8px; }
    }
"""


def build_country_ja(country, wc_history_tournaments):
    slug = country["slug"]
    results = COUNTRY_RESULTS.get(slug, {})

    # 出場大会一覧HTML
    rows = ""
    for year in ALL_YEARS:
        r = results.get(year)
        host_ja = HOST_COUNTRY_JA.get(year, "")
        if r is None:
            badge = '<span class="result-badge not-qualified">不出場</span>'
            rows += f"""
        <tr style="opacity:0.5">
          <td style="font-weight:700;font-feature-settings:'tnum'">{year}</td>
          <td style="font-size:12px;color:var(--c-text-sub)">{host_ja}</td>
          <td>{badge}</td>
        </tr>"""
        else:
            cls = result_class(r["result_ja"])
            badge = f'<span class="result-badge {cls}">{r["result_ja"]}</span>'
            rows += f"""
        <tr>
          <td style="font-weight:700;font-feature-settings:'tnum'">{year}</td>
          <td style="font-size:12px">{host_ja}</td>
          <td>{badge}</td>
        </tr>"""

    # レジェンドHTML
    legend_cards = ""
    for l in country.get("legends", []):
        legend_cards += f"""
      <div class="legend-card">
        <div class="legend-name">{l['name']}</div>
        <div class="legend-meta">{l['name_en']} / {l['years']} / W杯{l['goals']}得点</div>
        <div class="legend-note">{l['note']}</div>
      </div>"""

    # 日本との対戦
    japan_matches_html = ""
    jm = country.get("japan_matches", [])
    if jm:
        japan_matches_html = """
  <section class="wc-section">
    <h2>🇯🇵 日本との対戦履歴</h2>
    <div style="overflow-x:auto">
      <table class="result-table">
        <thead><tr><th>大会年</th><th>ステージ</th><th>スコア</th><th>結果</th><th>備考</th></tr></thead>
        <tbody>"""
        for m in jm:
            japan_matches_html += f"""
          <tr>
            <td>{m['year']}</td>
            <td>{m['stage']}</td>
            <td style="font-weight:700">{m['score']}</td>
            <td>{m['result']}</td>
            <td style="font-size:12px;color:var(--c-text-sub)">{m.get('note','')}</td>
          </tr>"""
        japan_matches_html += """
        </tbody>
      </table>
    </div>
  </section>"""

    title_years_str = "、".join(str(y) for y in country.get("title_years", []))
    runner_up_years_str = "、".join(str(y) for y in country.get("runner_up_years", []))

    depth = "../../"  # worldcup/history/countries/{slug}/index.html

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{country['name_ja']} W杯出場履歴 | football-jp</title>
  <meta name="description" content="{country['name_ja']}のFIFAワールドカップ全出場履歴。出場{country['appearances']}回・{country['best_result_ja']}。歴代の成績・伝説の選手を一覧で確認。">
  <link rel="canonical" href="https://football-jp.com/worldcup/history/countries/{slug}/">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/countries/{slug}/">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/countries/{slug}/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/worldcup/history/countries/{slug}/">
  <meta property="og:title" content="{country['name_ja']} W杯出場履歴 | football-jp">
  <meta property="og:description" content="{country['name_ja']}のW杯全出場履歴。{country['best_result_ja']}。">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-39G8CVXRW0"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "G-39G8CVXRW0");
  </script>
  <link rel="stylesheet" href="{depth}style.css">
  <link rel="stylesheet" href="{depth}worldcup-history-detail.css">
  <script src="{depth}wc-nav.js" defer></script>
  <style>{STYLE_BLOCK}</style>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="football-jp">
  <link rel="apple-touch-icon" href="/assets/logos/favicon-180.png">
</head>
<body class="wc-page">
<div class="wc-container">

  <nav class="wc-nav" id="wcNav"></nav>
  <script>document.getElementById('wcNav').innerHTML = window.wcRenderNav ? wcRenderNav('history') : '';</script>

  <nav class="breadcrumb" aria-label="パンくず">
    <ol>
      <li><a href="{depth}">W杯</a></li>
      <li><a href="../../../">歴史と記録</a></li>
      <li>国別出場履歴</li>
      <li>{country['name_ja']}</li>
    </ol>
  </nav>

  <div class="country-hero">
    <div class="country-hero-flag">{country['flag']}</div>
    <h1>{country['name_ja']} W杯出場履歴</h1>
    <p class="country-hero-sub">{country['description_ja']}</p>
    <div class="country-stats">
      <div class="stat-box">
        <span class="stat-box-num">{country['appearances']}</span>
        <span class="stat-box-label">出場回数</span>
      </div>
      <div class="stat-box">
        <span class="stat-box-num">{country['titles']}</span>
        <span class="stat-box-label">優勝回数</span>
      </div>
      <div class="stat-box">
        <span class="stat-box-num">{country['runner_up']}</span>
        <span class="stat-box-label">準優勝回数</span>
      </div>
      <div class="stat-box" style="flex:1;min-width:120px;text-align:left;">
        <span class="stat-box-num" style="font-size:14px">{country['best_result_ja']}</span>
        <span class="stat-box-label">最高成績</span>
      </div>
    </div>
    {"<p style='margin-top:10px;font-size:12px;color:#a0b0c8'>優勝: " + title_years_str + "年</p>" if title_years_str else ""}
    {"<p style='font-size:12px;color:#a0b0c8'>準優勝: " + runner_up_years_str + "年</p>" if runner_up_years_str else ""}
  </div>

  <!-- 全大会一覧 -->
  <section class="wc-section">
    <h2>📋 歴代出場大会一覧（1930〜2022）</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="result-table">
        <thead>
          <tr>
            <th>大会年</th>
            <th>開催国</th>
            <th>成績</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">※ 不出場は予選敗退・棄権・除外等を含む。出典: Wikipedia / FIFA（2022年大会終了時点）。</p>
  </section>

  <!-- レジェンド -->
  <section class="wc-section">
    <h2>⭐ 代表的な選手（レジェンド）</h2>
    <div class="legend-grid">
      {legend_cards}
    </div>
  </section>

  {japan_matches_html}

  <!-- 関連ページ -->
  <section class="wc-section">
    <h2>🔗 関連ページ</h2>
    <ul style="list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px;">
      <li><a href="../../../" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-accent);text-decoration:none;font-size:13px;">← 歴史と記録一覧</a></li>
      <li><a href="../../scorers/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">⚽ 歴代得点王ランキング</a></li>
    </ul>
  </section>

  <footer class="wc-footer">
    <p>データ出典: Wikipedia / FIFA公式記録（2022年大会終了時点）</p>
    <p><a href="../../../">歴史と記録トップへ</a> ／ <a href="{depth}../">football-jp トップへ</a></p>
    <p class="footer-links"><a href="{depth}../privacy.html">プライバシーポリシー</a></p>
  </footer>
</div>

  <script src="/sw-register.js" defer></script>
  <script src="/push-client.js" defer></script>
  <script src="/push-ui.js" defer></script>
  <script src="/search.js" defer></script>
  <script src="/search-ui.js" defer></script>
</body>
</html>
"""


def build_country_en(country, wc_history_tournaments):
    slug = country["slug"]
    results = COUNTRY_RESULTS.get(slug, {})

    rows = ""
    for year in ALL_YEARS:
        r = results.get(year)
        host_en = HOST_COUNTRY.get(year, "")
        if r is None:
            badge = '<span class="result-badge not-qualified">Did not qualify</span>'
            rows += f"""
        <tr style="opacity:0.5">
          <td style="font-weight:700;font-feature-settings:'tnum'">{year}</td>
          <td style="font-size:12px;color:var(--c-text-sub)">{host_en}</td>
          <td>{badge}</td>
        </tr>"""
        else:
            cls = result_class(r["result_ja"])
            badge = f'<span class="result-badge {cls}">{r["result_en"]}</span>'
            rows += f"""
        <tr>
          <td style="font-weight:700;font-feature-settings:'tnum'">{year}</td>
          <td style="font-size:12px">{host_en}</td>
          <td>{badge}</td>
        </tr>"""

    legend_cards = ""
    for l in country.get("legends", []):
        legend_cards += f"""
      <div class="legend-card">
        <div class="legend-name">{l['name_en']}</div>
        <div class="legend-meta">{l['name']} / {l['years']} / {l['goals']} WC Goals</div>
        <div class="legend-note">{l['note']}</div>
      </div>"""

    japan_matches_html = ""
    jm = country.get("japan_matches", [])
    if jm:
        japan_matches_html = """
  <section class="wc-section">
    <h2>🇯🇵 Matches vs Japan</h2>
    <div style="overflow-x:auto">
      <table class="result-table">
        <thead><tr><th>Year</th><th>Stage</th><th>Score</th><th>Result</th><th>Note</th></tr></thead>
        <tbody>"""
        for m in jm:
            japan_matches_html += f"""
          <tr>
            <td>{m['year']}</td>
            <td>{m['stage']}</td>
            <td style="font-weight:700">{m['score']}</td>
            <td>{m['result']}</td>
            <td style="font-size:12px;color:var(--c-text-sub)">{m.get('note','')}</td>
          </tr>"""
        japan_matches_html += """
        </tbody>
      </table>
    </div>
  </section>"""

    title_years_str = ", ".join(str(y) for y in country.get("title_years", []))
    runner_up_years_str = ", ".join(str(y) for y in country.get("runner_up_years", []))

    depth_en = "../../../../worldcup/"  # en/worldcup/history/countries/{slug}/

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{country['name_en']} FIFA World Cup History | football-jp</title>
  <meta name="description" content="{country['name_en']}'s FIFA World Cup history: {country['appearances']} appearances, {country['best_result_en']}. Full tournament results and legendary players.">
  <link rel="canonical" href="https://football-jp.com/en/worldcup/history/countries/{slug}/">
  <link rel="alternate" hreflang="en" href="https://football-jp.com/en/worldcup/history/countries/{slug}/">
  <link rel="alternate" hreflang="ja" href="https://football-jp.com/worldcup/history/countries/{slug}/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://football-jp.com/en/worldcup/history/countries/{slug}/">
  <meta property="og:title" content="{country['name_en']} World Cup History | football-jp">
  <meta property="og:description" content="{country['name_en']} World Cup history. {country['best_result_en']}.">
  <meta property="og:site_name" content="football-jp">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-39G8CVXRW0"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag("js", new Date());
    gtag("config", "G-39G8CVXRW0");
  </script>
  <link rel="stylesheet" href="{depth_en}style.css">
  <link rel="stylesheet" href="{depth_en}../worldcup-history-detail.css">
  <style>{STYLE_BLOCK}</style>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0b1220">
</head>
<body class="wc-page">
<div class="wc-container">

  <nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
      <li><a href="../../../">World Cup</a></li>
      <li><a href="../../">History &amp; Records</a></li>
      <li>Country History</li>
      <li>{country['name_en']}</li>
    </ol>
  </nav>

  <div class="country-hero">
    <div class="country-hero-flag">{country['flag']}</div>
    <h1>{country['name_en']} – World Cup History</h1>
    <p class="country-hero-sub">{country['description_en']}</p>
    <div class="country-stats">
      <div class="stat-box">
        <span class="stat-box-num">{country['appearances']}</span>
        <span class="stat-box-label">Appearances</span>
      </div>
      <div class="stat-box">
        <span class="stat-box-num">{country['titles']}</span>
        <span class="stat-box-label">Titles</span>
      </div>
      <div class="stat-box">
        <span class="stat-box-num">{country['runner_up']}</span>
        <span class="stat-box-label">Runner-up</span>
      </div>
      <div class="stat-box" style="flex:1;min-width:120px;text-align:left;">
        <span class="stat-box-num" style="font-size:14px">{country['best_result_en']}</span>
        <span class="stat-box-label">Best Result</span>
      </div>
    </div>
    {"<p style='margin-top:10px;font-size:12px;color:#a0b0c8'>Champions: " + title_years_str + "</p>" if title_years_str else ""}
    {"<p style='font-size:12px;color:#a0b0c8'>Runners-up: " + runner_up_years_str + "</p>" if runner_up_years_str else ""}
  </div>

  <!-- Tournament history table -->
  <section class="wc-section">
    <h2>📋 Tournament History (1930–2022)</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <table class="result-table">
        <thead>
          <tr>
            <th>Year</th>
            <th>Host</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
    <p class="source-note">Source: Wikipedia / FIFA official records (as of 2022 World Cup). "Did not qualify" includes withdrawal, suspension, and failure to qualify.</p>
  </section>

  <!-- Legends -->
  <section class="wc-section">
    <h2>⭐ Legendary Players</h2>
    <div class="legend-grid">
      {legend_cards}
    </div>
  </section>

  {japan_matches_html}

  <!-- Related -->
  <section class="wc-section">
    <h2>🔗 Related Pages</h2>
    <ul style="list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px;">
      <li><a href="../../" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-accent);text-decoration:none;font-size:13px;">← History &amp; Records</a></li>
      <li><a href="../../scorers/" style="display:inline-block;padding:8px 14px;background:#fff;border:1px solid var(--c-border);color:var(--c-text);text-decoration:none;font-size:13px;">⚽ All-Time Top Scorers</a></li>
    </ul>
  </section>

  <footer class="wc-footer">
    <p>Data source: Wikipedia / FIFA official records (as of 2022 World Cup)</p>
    <p><a href="../../">History &amp; Records</a> / <a href="../../../../../">football-jp Top</a></p>
    <p class="footer-links"><a href="../../../../../privacy.html">Privacy Policy</a></p>
  </footer>
</div>

  <script src="/sw-register.js" defer></script>
  <script src="/push-client.js" defer></script>
  <script src="/push-ui.js" defer></script>
</body>
</html>
"""


def main():
    with open(WC_HISTORY, encoding="utf-8") as f:
        data = json.load(f)
    tournaments = data.get("tournaments", [])

    ja_count = 0
    en_count = 0

    for country in COUNTRIES:
        slug = country["slug"]

        # Japanese
        ja_dir = ROOT / "worldcup" / "history" / "countries" / slug
        ja_dir.mkdir(parents=True, exist_ok=True)
        ja_html = build_country_ja(country, tournaments)
        (ja_dir / "index.html").write_text(ja_html, encoding="utf-8")
        print(f"[JA] 生成: {ja_dir / 'index.html'}")
        ja_count += 1

        # English
        en_dir = ROOT / "en" / "worldcup" / "history" / "countries" / slug
        en_dir.mkdir(parents=True, exist_ok=True)
        en_html = build_country_en(country, tournaments)
        (en_dir / "index.html").write_text(en_html, encoding="utf-8")
        print(f"[EN] 生成: {en_dir / 'index.html'}")
        en_count += 1

    print(f"\n国別ページ生成完了: 日本語 {ja_count}ページ / 英語 {en_count}ページ（合計 {ja_count + en_count}ページ）")
    print(f"対象国: {[c['slug'] for c in COUNTRIES]}")


if __name__ == "__main__":
    main()
