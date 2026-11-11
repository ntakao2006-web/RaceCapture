# Ver.2（UNO Q）のファームの控え（2026-11-10）と戻し方

展示会に向けてVer.2のファームを書き換えたり、まったく別のファームを入れたりする前に、
**SUGO（11/8）を走った形のまま**の本体を丸ごと控えた。展示が終わったらこの資料で元へ戻す。

- 取った日時：2026-11-10 15:36〜15:50（JST）、USBのadb（本体のシリアル`2954148814`）
- 取ったときの本体：起動から約5時間、EcoCaptureは受信100Hz・記録中、STM32のリセット0回。
  読み出しの前後でこの状態は変わっていない（STM32は止めずに読んだ。書き込み・リセットはしていない）

> **2026-11-11追記**：この控えのあと、ロガーのファームをSDの目次の不具合を直した版（`~/ecologger_v2_sdfix_20261111.bin`、7066c1b7…）へ書き換えた。違いは`sd_logger.h`だけ（直す前は本体の`~/sd_logger.h.pre-sdfix-20261111`）。SUGOを走った形（`ecologger_v2_gnss10hz_20261109.bin`、e3501ec7…）へ戻すと、その不具合も戻る。展示のあとで元へ戻すときは、ロガーは直した版を書くこと

## 1. 控えの置き場

| 場所 | パス |
|---|---|
| PC | `Documents\UNOQ_fw_backup\2026-11-10\` |
| NAS | `Z:\general\RaceCapture\unoq_fw_backup\2026-11-10\`（PCと同じ中身。SHA-256で照合済み） |

どちらにも`SHA256SUMS.txt`（全ファイルのハッシュ）と`README.txt`（この資料への案内）がある。
**リポジトリには入れていない**（公開リポジトリで、Linux側の控えに合言葉・SIMの設定・sshの鍵が入っているため）。

## 2. 中身

### STM32（`stm32\`）

| ファイル | 中身 | SHA-256（先頭） |
|---|---|---|
| `flash_full_2MB.bin` | フラッシュ全体（0x08000000〜、2MiB）を読み出したもの。2回読んで同じ値 | `ae07eb5e…` |
| `zephyr_core_restore.hex` | 上のうち土台のZephyr（0x08000000〜0x0803A000）だけを、番地付きのHEXにしたもの。戻す用 | `61d943c4…` |
| `sketch_0x80F0000_64KiB.bin` | 上のうちロガーのファームの領域（0x080F0000〜、64KiB）そのまま | `b1be6c9f…` |
| `ecologger_v2_gnss10hz_20261109.bin` | **今動いているロガーのファーム**（11/9に書き込んだGNSSの解を全部渡す版、59,844バイト）。戻すときはこれを書く | `e3501ec7…` |
| `ecologger_v2_sdfull_20261107.bin`ほか2つ | その前の版（11/7のSD満杯対策、10/9の監視つき・CAN2のACK） | |

確かめたこと：

- フラッシュの0x080F0000からの59,844バイトは`ecologger_v2_gnss10hz_20261109.bin`と**1バイトも違わない**（残りは全部0xFF）。
  ファームのソース（`logger_impl.h`・`sd_logger.h`ほか`.h`と`.ino`）は、本体の`~/ecologger_v2/`とリポジトリの`firmware/ecologger_v2/`で同じ。
  組み立て用の`build.sh`は本体に10/9の版が残っていて、今の像はそれで作ったもの（リポジトリの`build.sh`は新しい版で、まだ本体で使っていない）。本体の`build.sh`も下のLinux側の控えに入っている
- 中身があるのは0x08000000〜0x0803A000（Zephyr）と0x080F0000〜0x080FF000（ロガー）だけで、ほかは空（0xFF）
- **土台のZephyrは、本体の`~/.arduino15`に入っているコア0.52.0のファイルとも、10/21に交換する前の基板とも違う版**（中に`v4.2.0-22-g2c23b6e2571b`の文字がある。0.52.0のファイルは`v4.2.0-31-g8e71141c1b0a`）。
  つまり**今の土台の正確な写しはこの控えだけ**。展示でArduino App Labなどが土台まで書き換えたら、2章のHEXで戻す
- オプションバイト：`FLASH_OPTR=0x1FEFF8AA`（読み出し保護はLevel 0、TrustZoneは無効）、`NSBOOTADD0R=0x0800007F`、`NSBOOTADD1R=0x0BF9007F`、`SECBOOTADD0R=0`

### Linux側（`linux\`）

| ファイル | 中身 |
|---|---|
| `home_arduino.tar.gz`（約740MB） | `/home/arduino`まるごと。**ただし走行記録（`ecocapture-v2-data/logs`）・動画（同`video`）・古い控え（`ecocapture-source-backups`）・`.cache`は除いた**。EcoCapture-Web（`private/`の合言葉・Podiumの設定を含む）・`ecocapture-v2-data`の設定（`config.json`・`lap.json`・`imu_mount.json`・地図）・録画の設定（`ecologger-video/`）・RaceCapture-UNOQ・ファームのソースと組み立て環境（`ecologger_v2*`・`ecologger_v2_libraries`・`.arduino15`のコア0.52.0一式）・RaceCaptureアプリの設定（`.config`・`.kivy`）・`.ssh` |
| `opt.tar.gz`（約180MB） | `/opt`のうち、`ecocapture-admin`・`ecocapture-voice`・`ecologger-video`（録画プログラム）・`logger-v2-racecapture`（DASH・RCP変換）・`openocd`・`racecapture`（公式アプリ） |
| `etc.tar.gz` | `/etc/systemd/system`（サービス一式と`arduino-router`の追加設定`ecologger.conf`・`stop-timeout.conf`）、`/etc/sudoers.d`のうち読めたもの（`ecocapture-dash`はroot専用で読めず。中身はリポジトリの`RaceCapture-UNOQ/ecocapture-dash.sudoers`）、`os-release`・`fstab`・`hostname` |
| `docker_ecocapture-web_0.2.0.tar.gz`（約280MB） | 今動いているEcoCaptureのDocker像（`ecocapture-web:0.2.0`、ID `037afde1d63a…`）。`docker load`で戻る |
| `inventory.txt` | 本体の構成の記録：OS（Debian 13）、Arduino App CLI 0.7.0、コア`arduino:zephyr 0.52.0`、サービスの有効/無効、Dockerの起動のしかた（つないでいるフォルダー・ポート）、Wi-Fiの接続名、入っているパッケージと版 |

控えていないもの：走行記録と動画（4.7GB。ファームではないので。回収は`Collect-Logs.cmd`）、Wi-Fiのパスワード（root専用）、ほかの古いDocker像。
センサーハブのPICのファームはこの控えに入っていない（11/3のv8書き込みの記録は`outputs/sensorhub_20261103_v8_flash/`）。

## 3. 展示用のファームを入れるときの注意

- **先にロガー用のサービスを止める**。止めないと、EcoCaptureが「STM32とつながらない」と判断して、監視役（`ecocapture-mcu-supervisor`）が約30秒ごとに`flash-mcu.sh --recover`でSTM32をリセットし続ける。
  止めるもの：`ecocapture-mcu-supervisor`・`ecocapture-web`（Docker）。起動のたびにSTM32をリセットする`ecocapture-mcu-start`も、展示のファームの動きに合わなければ無効にする。
  DASH・録画・RCP変換もEcoCaptureの値を読むので、画面に出るものを変えたいなら合わせて止める（rootの操作はDocker経由。`flash-mcu.sh`の`host_sh`と同じ形）
- ロガーの領域（64KiB）だけに書くなら、今までどおり`EcoCapture-Web/flash-mcu.sh`が使える（ルーターを止めてから書くので、Linux側のUARTが固まらない）。
  ただし最後にEcoCaptureを起こすので、そのあとで上のサービスを止める
- Arduino App Labから書くと、`~/.arduino15`のコアの版や土台のZephyrまで変わることがある。戻すときは4-2の手順で土台から戻す
- `arduino-burn-bootloader.service`（初回だけ土台を書く）は、`~/.local/share/arduino-app-cli/bootloader_burned.flag`がある限り動かない。この印を消さない

## 4. 戻し方

### 4-1. ロガーのファームだけ戻す（土台は変わっていないとき）

1. PCから本体へ像を送る：`adb -s 2954148814 push stm32\ecologger_v2_gnss10hz_20261109.bin /home/arduino/`
2. 本体で`sh ~/EcoCapture-Web/flash-mcu.sh ~/ecologger_v2_gnss10hz_20261109.bin`（約20秒）
3. 止めたサービスを起こす：`systemctl enable --now ecocapture-mcu-supervisor`（無効にしたなら`ecocapture-mcu-start`も`enable`）
4. 5章で確かめる

### 4-2. 土台のZephyrから戻す（App Labなどで土台まで変わったとき）

`flash-mcu.sh`はロガーの領域しか書かないので、同じ順番を手で行う（**この手順はまだ実機で通していない**）。

1. `stm32\zephyr_core_restore.hex`と`ecologger_v2_gnss10hz_20261109.bin`を本体の`~/`へ送る
2. `docker stop ecocapture-web`、rootで`systemctl stop ecocapture-mcu-supervisor arduino-router`（ルーターが止まったことを`systemctl is-active`で確かめる。**止まっていなければ先へ進まない**）
3. `/opt/openocd/bin/arduino-flash.sh ~/zephyr_core_restore.hex ~/ecologger_v2_gnss10hz_20261109.bin`
   （土台をHEXの番地へ、ロガーを0x080F0000へ書く。OpenOCDはHEXを中身で見分ける）
4. rootで`sh /home/arduino/EcoCapture-Web/install-router.sh --no-start && systemctl start arduino-router`（展示のときに`arduino-router-serial`も止めたなら起こす）
5. 3秒待ってから、STM32をリセット：`/opt/openocd/bin/openocd -d1 -s /opt/openocd -f /opt/openocd/openocd_gpiod.cfg -c "reset_config srst_only srst_push_pull; init; reset run; shutdown"`
6. `docker start ecocapture-web`、rootで`systemctl start ecocapture-mcu-supervisor`
7. 5章で確かめる

### 4-3. Linux側を戻す（展示でLinux側も変えたとき）

- 変えたところだけ戻すのが基本。控えの中のファイルを取り出して上書きする（例：`tar -xzf home_arduino.tar.gz ./EcoCapture-Web/server.py`）
- EcoCaptureの像：`gunzip -c docker_ecocapture-web_0.2.0.tar.gz | docker load`のあと、`EcoCapture-Web/deploy.sh`の形で起動し直す（つなぐフォルダー・ポートは`inventory.txt`）
- `/opt`と`/etc/systemd/system`はrootで`opt.tar.gz`・`etc.tar.gz`から戻し、`systemctl daemon-reload`。サービスの有効/無効は`inventory.txt`の一覧に合わせる
- まるごと作り直すときは`EcoCapture-Web/setup-root.sh`（10/21の基板交換で使った手順）のあと、上の控えで設定を戻す

## 5. 戻せたかの確かめ方

- STM32を止めずに読み出して照合する（これは本体のふだんの動きを乱さない。11/10に確かめた）：
  `openocd -d1 -s /opt/openocd -f /opt/openocd/openocd_gpiod.cfg -c "init; dump_image /tmp/now.bin 0x08000000 0x200000; shutdown"`
  - 0x080F0000からの59,844バイトのSHA-256が`e3501ec78b58e4c48180819b91a769c19c4e39d2a094eb61e3f7b75e974e9da0`
  - 土台（先頭0x3A000バイト）が`flash_full_2MB.bin`の同じ範囲と同じ
  - 展示のファームがほかの領域に書いていなければ、全体のSHA-256も`ae07eb5ebbd5cc568c6db7a9c480f7b0df304dc920e61ccaae377ab80245f3df`になる
- EcoCaptureの`/api/status`で`connected: true`・`receive_hz`が約100・`mcu_resets`が増えない・記録の`rows`が増える
