# 本体（UNO Q）のソフトの仕分け一覧（2026-11-13、SP-2-4）

`RaceCapture-UNOQ/`と`EcoCapture-Web/`の中身を、「いま動いているもの／公式アプリ用／試験／古い候補」に分けた一覧。
**ファイルは動かしていない。** 公式のRaceCaptureアプリを本体から外すとき（`task_spec_rebuild_breakdown.md` SP-7-3）に、止めるもの・残すものを分ける材料にする。

- 分けた根拠は、リポジトリの中だけ：各フォルダーの`README.md`、入れ方のスクリプト（`install*.sh`・`deploy.sh`・`Dockerfile`）がどのファイルを入れるか、ファイルの冒頭の説明、`v2_firmware_backup_20261110.md`の控えの記録。
- **本体そのものは見ていない。** 本体でどのサービスが有効かは、控えの`inventory.txt`（PCの`Documents\UNOQ_fw_backup\2026-11-10\`）で確かめる（SP-1-4）。下の「要確認」はそのとき見る。

## 1. `RaceCapture-UNOQ/`（81本）

入口は`RaceCapture-UNOQ/README.md`。前半が公式アプリの表示、後半（「EcoCapture DASH」）がいまの車載画面。

### いま動いているもの（残す）

| ファイル | 役割 |
|---|---|
| `ecocapture_dash.py`・`dash_model.py` | 車載画面 EcoCapture DASH（HDMI） |
| `ecocapture-dash.service`・`ecocapture-dash.sudoers`・`install-dash.sh` | DASHの自動起動と入れ方 |
| `incident_monitor.py`・`logger-v2-incident-monitor.service`・`install-incident-mitigation.sh` | 見守り役（急な電源断の記録） |
| `arduino-router-serial-safe.sh`・`arduino-router-serial-wait.conf` | USBの口が無い間、ルーターの直列の口を静かに待たせる |
| `hdmi_display.py`・`xorg.conf`・`racecapture-display.service` | HDMIの画面（Xorg `:2`）。名前は`racecapture-`だがDASHもこの上に出る（要確認：外すときに名前ごと残すか） |
| `display_load_control.py` | 見えていない方の画面のアプリだけを休ませる（`install-dash.sh`も入れる） |
| `test_dash_model.py`・`test_incident_monitor.py`・`test_display_mitigation.py` | 上の試験 |

### 公式アプリ用（SP-7-3で外す候補）

| ファイル | 役割 |
|---|---|
| `rcp_bridge.py`・`logger-v2-rcp.service`・`test_bridge.py` | ロガーの値を公式アプリの形（RCP）に変える |
| `racecapture-app.service`・`launch.sh`・`fastnav.py`・`fit_window.py`・`racecapture-app-control.sudoers` | 公式アプリの起動と表示の調整 |
| `racecapture-vnc.service`・`racecapture-web.service`・`display_transport.sh`・`index.html` | 公式アプリの画面をUSBでPCのブラウザへ出す |
| `racecapture-touch.service`・`touch_launcher.py` | タッチでの公式アプリ／EcoCaptureの切り替え |
| `dash_switch.sh` | DASHと公式アプリの切り替え（公式アプリを外すと役目が無くなる） |
| `configure_app.py`・`configure_display.py`・`configure_hdmi_profile.py`・`configure_oiltemp_dashboard.py`・`configure_sugo_dashboard.py` | 公式アプリのダッシュボードの設定 |
| `install.sh`・`install-hdmi-mitigation.sh` | 公式アプリ一式の入れ方（**`install-dash.sh`は`install.sh`のあとに動かす前提**なので、外すときは画面の土台の分を切り分ける） |
| `Open-RaceCapture.ps1`・`Watch-RaceCapture-USB.ps1`・`Install-USB-Autostart.ps1`・`Configure-OilTemp.ps1` | PC側：USBをつなぐと公式アプリの画面を開く |
| `prefetch_kanto.py`・`test_prefetch_kanto.py` | 公式アプリの地図の先読み |

### 試験・確かめの記録

| ファイル | 役割 |
|---|---|
| `verify_live.py`・`verify_podium_live.py`・`verify_sd_recording.py`・`verify_vehicle_recording.py` | 実機での確かめ（2026-10） |
| `validation-20261004/`（11本）・`vehicle-can-validation-20261004.json`・`boot-communication-validation.json` | 確かめの結果 |
| `boot_communication_check.py`・`test_boot_communication_check.py`・`ecocapture-boot-check.service` | 起動直後の通信の確かめと立て直し（要確認：いま有効か。`EcoCapture-Web`の見守り役と役目が重なる） |
| `maintenance_clear_recordings.py`・`maintenance_sd_inventory.py` | 手で動かす手入れ（記録を消す・SDの中身を確かめる） |

### 古い候補

| ファイル | 役割 |
|---|---|
| `ecocapture_native.cpp`・`ecocapture-native.service`・`capture_x11.cpp`・`input_x11.cpp`・`test_native_controls.cpp`・`test_native_gestures.cpp` | DASHの前の、軽いタッチ画面の試作（C++）。`install.sh`はサービスを置く（要確認：いま無効か） |
| `logger_impl.device-before.h`・`logger_impl.device-candidate.h`・`logger_impl.vehicle-candidate.h`・`decoder.device-trial.h` | STM32のファームの候補の写し。稼働中のファームの正ではない |
| `arduino-router-vehicle.conf`・`router-stop-timeout.conf` | ルーターの追加設定の案。入れ方のスクリプトからは参照されていない（いま本体にあるのは`EcoCapture-Web/ecologger-router.conf`の側。要確認） |

## 2. `EcoCapture-Web/`（197本、うち`vendor/`が112本）

入口は`EcoCapture-Web/README.md`。公式アプリ用のものは無い。

### いま動いているもの（残す）

| ファイル | 役割 |
|---|---|
| `server.py`・`telemetry_bridge.py`・`models.py`・`hardware.py`・`imu_mount.py`・`ncec.py` | EcoCapture本体（STM32の値を読み、記録し、画面とAPIを出す）。Dockerの像に入る |
| `lap.py`・`field.py` | ラップの計算、コースウォーク画面 |
| `podium.py`・`sim7070.py`・`remote_command.py` | LTEでの送信と、ピットからの命令 |
| `video_store.py` | 動画と走行記録の消し方（ドラレコ式） |
| `sd_decode.py`・`sd_storage.py`・`sd_timestamp.py` | シールドのSDカードの読み書き |
| `public_server.py`・`build_public.py`・`public/` | 見るだけのページ |
| `web/` | 設定・ログ管理の画面 |
| `vendor/` | 同梱している外のライブラリ（appdirs・fs・pyfatfs・segno） |
| `Dockerfile`・`deploy.sh`・`.dockerignore` | 像の作り方と入れ方 |
| `device_agent.py`・`ecocapture-admin.service`・`install-device-agent.sh` | root権限の手伝い役 |
| `mcu-supervisor.py`・`ecocapture-mcu-supervisor.service`・`install-mcu-supervisor.sh` | STM32との通信路の見守り役 |
| `ecocapture-mcu-start.service`・`ecocapture-web-start.service`・`install-boot.sh` | 電源ONのときの起動の順番 |
| `ecologger-router.conf`・`install-router.sh` | ルーターの追加設定 |
| `flash-mcu.sh`・`build-mcu.sh`・`setup-root.sh` | STM32への書き込み、新しい基板への引っ越し |
| `Update-UNOQ.ps1`・`Open-EcoCapture-Web.ps1`・`Watch-EcoCapture-USB.ps1`・`Install-USB-Autostart.ps1`・`Uninstall-USB-Autostart.ps1` | PC側：更新と、USBをつなぐと画面を開く |

### 通話（範囲外。`SPEC.md` 10章）

| ファイル | 役割 |
|---|---|
| `voice_agent.py`・`ecocapture-voice.service`・`install-voice-agent.sh`・`wireplumber-ecologger-bluetooth.conf`・`test_voice_agent.py` | ドライバーの音声（要確認：いま有効か。試験の道具は`archive/voice/`へ移した） |
| `install-dash-ap.sh` | 本体のWi-Fiを親機にして車のスマホをつなぐ（エコラン大会の構成。要確認） |

### 試験・確かめの記録

| ファイル | 役割 |
|---|---|
| `test_*.py`（18本。うち`test_voice_agent.py`は通話）・`test_map.cjs` | 試験。`deploy.sh`が像を作るときに通すものと、PCで動かすものがある |
| `verify_live.py`・`mcu_diagnostics.py` | 実機での確かめ・診断 |
| `VERIFICATION.md`・`artifacts/live-verification.json` | 確かめの結果（2026-09） |
| `LTE_PODIUM.md` | LTE送信の準備と試験の記録 |
| `ncec_can_spec.md` | `docs/design/ncec_can_spec.md`の写し（要確認：どちらを正にして、片方を案内だけにするか） |

## 3. 外すとき（SP-7-3）に気を付ける所

- `install-dash.sh`は`install.sh`（公式アプリ一式）のあとに動かす前提。画面の土台（Xorg・HDMI）とDASHだけを入れる形に切り分けてから、公式アプリの分を外す。
- 画面のサービスの名前が`racecapture-display`で、DASHもこの上に出ている。名前を変えると本体の設定・`tools/sugo_setup/dash_check.py`も変わるので、本体に触れるときに合わせる。
- `dash_switch.sh`と`ecocapture-dash.service`は「公式アプリと同時に動かない」決まりを持っている。公式アプリを外したら、この切り替えは要らなくなる。
- 本体の録画のソフトは`tools/unoq_overlay_enc/`にある。置き場所を本体のソフトの並びへ移すかは、本体に触れるとき（SP-7）に決める（SP-2-5）。

## 4. 本体でいま有効なもの（控えの目録から、SP-1-4、2026-11-13）

根拠は、2026-11-10にSUGOを走った形のまま取った控えの`inventory.txt`（systemdの一覧・`docker ps`・Wi-Fiの設定の種類）と`etc.tar.gz`の中のファイル名。**本体そのものにはつないでいない。** 展示用に書き換えたあとの今の本体とは違うことがある。

| サービス | 控えの時点 | 仕分け |
|---|---|---|
| `ecocapture-web-start`・`ecocapture-mcu-start`・`ecocapture-mcu-supervisor`・`ecocapture-admin` | 有効 | 残す（EcoCaptureと見守り役） |
| `ecocapture-dash`・`racecapture-display` | 有効 | 残す（車載画面DASHと、その土台のHDMIの画面） |
| `ecologger-video` | 有効 | 残す（焼き込み録画） |
| `logger-v2-incident-monitor` | 有効 | 残す（急な電源断の記録） |
| `arduino-router`・`arduino-router-serial`（追加設定`ecologger.conf`・`stop-timeout.conf`・`10-wait-for-ttygs0.conf`） | 有効 | 残す |
| `ecocapture-boot-check` | **有効** | 要判断：`ecocapture-mcu-supervisor`と役目が重なる。どちらかに寄せるかはSP-7-3で決める |
| `logger-v2-rcp` | **有効** | 公式アプリ用（値をRCPに変える）。SP-7-3で外す候補 |
| `racecapture-vnc`・`racecapture-web` | **有効** | 公式アプリ用（画面をUSBでPCへ出す）。SP-7-3で外す候補 |
| `racecapture-app`・`racecapture-touch` | 無効（自動では起動しない） | 公式アプリ用。`dash_switch.sh`で切り替えたときだけ動く。SP-7-3で外す候補 |
| `ecocapture-native` | **有効** | 古い候補（DASHの前のタッチ画面の試作）なのに有効のまま。SP-7-3で止める |
| `ecocapture-voice` | 無効 | 通話（範囲外）。止まっている |

Docker（`ecocapture-web:0.2.0`の像から2つ）：

| コンテナ | 出している口 | 中身 |
|---|---|---|
| `ecocapture-web` | 8080（本体の中だけ）、8082（Wi-Fiへ） | EcoCapture本体と設定・ログの画面、コースウォーク画面 |
| `ecocapture-viewer` | 8081（Wi-Fiへ） | 見るだけのページ（`public_server.py`） |

Wi-Fiの設定は、自動でつなぐものが1つ（テザリング）と、自動ではつながないものが1つ（本体を親機にする設定＝`install-dash-ap.sh`の分）。cronは無し。

上の章の「要確認」の答え：

- `ecocapture-boot-check.service`：有効。
- `ecocapture-native.service`：有効（`install.sh`が置いたまま）。
- `router-stop-timeout.conf`：本体に入っている（`arduino-router.service.d/stop-timeout.conf`）。`arduino-router-vehicle.conf`にあたるものは控えに見当たらない。
- `ecocapture-voice.service`：無効。
- `install-dash-ap.sh`の親機の設定：本体に残っているが、自動ではつながない。

**外すとき（SP-7-3）に止める・取り除くものは6つ**：`logger-v2-rcp`・`racecapture-vnc`・`racecapture-web`・`ecocapture-native`と、無効のまま置いてある`racecapture-app`・`racecapture-touch`のユニット。`racecapture-display`は名前に反してDASHの土台なので残す。

