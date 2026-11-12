# ラップ判定の調査：RaceCapture・RaceChrono と Ver.2（`lap.py`）の比較（ER-2-4）

> 2026-10-14作成。ER-2-5（判定の改善）の根拠にする。
> RaceCapture のファームは **GPLv3** なので、コードは持ち込まず考え方だけ取り込んだ。
> RaceChrono は非公開のため、公式FAQとフォーラムの記述からわかる範囲だけ書いている。

## 調べたもの

- RaceCapture：`autosportlabs/RaceCapture-Pro_firmware` の master（`src/lap_stats/lap_stats.c`、`src/gps/geoTrigger.c`、`src/gps/geoCircle.c`、`include/logger/loggerConfig.h`）
- RaceChrono：公式FAQ「Start/Finishの幅を広げられるか」、公式フォーラムの「ラインを2回通過」「一方通行コース」等のスレッド。**判定アルゴリズム（サンプル間の補間方法など）の公式の説明は見つからなかった**

## 比較表

| 項目 | RaceCapture（ファーム） | RaceChrono | Ver.2 `lap.py`（ER-2-5適用後） |
|---|---|---|---|
| ラインの形 | **円**（中心点＋半径）。線ではない | **線**（トラップ）。地図上で置いて回転させる | 向きが決まっていれば**線**、未定なら**円** |
| 大きさ | 半径 既定0.0001°≒**11m**（設定範囲 約1〜111m） | 幅 既定**50m**（FAQでは50〜75mが普通） | 幅 既定30m（円のときは半径＝幅/2） |
| 通過方向 | **見ない** | **一方向が既定**。双方向にもできるが非推奨 | 一方向。向きは画面で指定でき、空欄なら最初の通過時のGNSS進行方向で決める |
| 通過時刻の決め方 | 円に**入った最初の点**の時刻。GNSSが10Hz未満なら点を10Hz相当に補間してから判定 | 公開情報なし | 線なら**前後2点を線形補間した横切り時刻**。円なら**最接近点**の時刻 |
| 誤検出の防ぎ方 | ①通過後、半径の**2倍の円から一度出る**まで次を受け付けない ②前回の通過から**100m以上走っている**（速度×時間で積算、1km/h未満は数えない） | 一方向判定。ユーザーからは最短ラップ時間の設定要望があった（実装有無は不明） | ①**通過後、ラインから幅以上離れるまで次を受け付けない**（今回追加） ②最短ラップ（既定10秒） ③測位精度25m超・1秒超の欠測では判定しない |
| 最短ラップ時間 | なし（10秒の定数は定義だけで未使用） | 不明 | あり（既定**60秒→10秒**へ変更） |
| 長い中断 | 記載なし | 記載なし | 最長ラップ（既定3600秒）を超えたら数えずに計測だけやり直す |

## 考え方として取り込んだもの・取り込まなかったもの

- **取り込んだ：通過後の再アーム（RaceCapture の geo trigger）**。止まったままラインの上でGNSSが揺れると、
  一方向判定でも「前→後ろ→前」で何度も横切る。最短ラップだけで防ぐと、その値を周回時間に合わせて
  決めなければならず、60秒のような根拠のない値になっていた。再アームがあれば最短ラップは小さくてよい
- **取り込んだ：最短ラップを短く（10秒）**。再アームがあるので、作手（約30秒）でも安全側
- **取り込んだ：一方向を既定にし、向きを手で指定できるようにする（RaceChrono）**。
  今までは「最初の通過時の進行方向」を学習するだけで、学習が外れたら直す手段が「ラインを登録し直す」しかなかった
- **取り込まなかった：走行距離100mの条件**。再アーム（幅以上離れる）でほぼ同じ効果があり、
  距離の積算はGNSS速度の質に左右される。必要になれば追加する
- **取り込まなかった：円の「入った最初の点」で時刻を取る方式**。進入角で時刻がずれる。
  Ver.2は線の補間を主にしており、こちらの方が正確

## 残る懸念（実機で確認すること）

- 線＋向きの判定は**まだ実機で通していない**（ER-2-3は歩行で円判定のみ）。自転車か車で一度確認したい
- 幅の既定30mは RaceChrono の50mより狭い。もてぎのようにコース幅が広い会場では50m程度にした方が取りこぼしにくい
- もてぎロードコースのコントロールライン付近をオーバルで通過したときPodium側でどう扱われるか（ER-1-5）は別問題

## 出典

- RaceCapture-Pro firmware（GPLv3）：https://github.com/autosportlabs/RaceCapture-Pro_firmware
- RaceChrono FAQ「Can I make the Start/Finish line wider, so all of my laps will register?」：https://racechrono.com/article/faq/can-i-make-the-start-finish-line-wider-so-all-of-my-laps-will-register
- RaceChrono フォーラム「Crossing Finish line twice」：https://racechrono.com/forum/discussion/358/crossing-finish-line-twice
- RaceChrono フォーラム「Onway track - no circuit」：https://racechrono.com/forum/discussion/198/onway-track-no-circuit
