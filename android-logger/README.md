# EcoLogger（Androidアプリ）

エコラン大会でVer.2ロガーを積まない車（スマホ組）用。Android端末の内蔵GNSS・IMUを0.1秒ごとの行にそろえ、
**端末内にCSVで記録**しながら、Ver.2ロガーと同じ形式で`ecorun-logger-server`へ送る（`task_ecorun_20261024_breakdown.md` ER-11）。
画面を消しても常駐通知を出して動き続ける。音声は入っていない（大会では同じスマホでDiscordの通話を並行して使う）。

## 使い方

画面は**横向きのドライバー用**。左に速度を大きく、右に「周回（何周目／規定周回）」「残り時間（規定時間まで）」
「今の周（経過と、規定時間に間に合う目標ペース）」「前回ラップ（均等ペースに対する貯金）」、上に記録・GNSS・送信・電池の状態。
記録中は画面が点いたままになり、ロック画面の上にも出る。

1. 「設定」で、車の名前、主・予備サーバーのURL（`wss://<ホスト>/ws/audio/<room>`、roomは車ごと）、規定周回数・規定時間を入れて保存。「点検」で電池の最適化を外す
2. 「● 記録を始める」→ 位置情報（正確な位置）と通知を許可する
3. ライン：コースウォークで記録を始めてから、ライン上に立って「現在地にする」（または地図で調べた「緯度, 経度」を入れる）。向きは最初の通過で自動に決まる
4. 本番の前に「ラップをリセット」
5. 走り終えたら「■ 長押しで停止」（触れただけでは止まらない）

- 記録ファイル：端末の`Download/EcoLogger/EL_<車の名前>_<日時>.csv`（USBでPCにつなぐと見える。アプリを消しても残る）
- 通信が切れている間も記録は続く。送信は「今」の値だけで、切れていた間の分を後から送り直すことはしない
- 主サーバーにつながらない・切れたら、間を空けずに予備へ移る。予備へ移った後は、予備が切れるまで主へは戻らない（Ver.2ロガーと同じ）
- ラップ判定はVer.2ロガー（`EcoCapture-Web/lap.py`）と同じ（スタート・コントロール・ゴールの3本、規定周回の前はゴールを無視、線から幅以上離れるまで次を数えない）。
  違いは、スマホの測位が毎秒約1回なので、1.5秒以内の測位どうしを続きとして扱うこと。ラップの状態は端末に保存され、アプリを開き直しても続く

## 送る値

`podium.meta`のチャンネル名・単位・桁数は`EcoCapture-Web/podium.py`に合わせてある（`Latitude`・`Longitude`・`GPSSpeed`・`Utc`など）。

- `Utc`：GNSSの時刻（端末の時計は使わない）。1Hzの測位の間の行は、測位からの経過時間を足して進める
- `GPSFix`：3＝高度つきの測位、2＝高度なし、0＝3秒以上測位が無い
- `GPSSats`：測位に使っている衛星の数
- `AccelX/Y/Z`（m/s²、重力を含む）・`GyroX/Y/Z`（°/s）：**端末自身の軸**（画面を正面に見て、右がX、上がY、画面から手前がZ）の0.1秒間の平均。車への固定の向きを決めておくこと

ラインを設定するとラップの値（`LapCount`・`CurrentLap`・`LapTime`・`BestLap`・`ElapsedTime`・`RaceTime`・`LapsLeft`、時間は分）も送る。CSVは上の値に、測位の精度`Accuracy`（m）を足したもの。

## ビルド

Android Studio（同梱のJDK）とAndroid SDK（platform 36・build-tools 36）が必要。`local.properties`の`sdk.dir`はPCごとに書く（Git管理外）。

```bash
cd android-logger && JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew testDebugUnitTest assembleDebug
```

APKは`app/build/outputs/apk/debug/app-debug.apk`。端末へは`adb install -r`で入れる。
