# ROCK 5Bでrace_captureアプリを起動するための準備手順（DC-9-3向け）

> `task_dashcam_breakdown.md`のDC-9-3（Mali GPU上での`race_capture`アプリ動作確認）に着手する際の
> 実務手順書。x86ルート（DC-1〜DC-8、`HP EliteDesk`/`AMD PC`）で得た知見のうち転用できるもの・
> できないものを整理し、ROCK 5B固有の追加調査（Radxa公式ドキュメント・GitHub・AutosportLabs公式wiki）
> を踏まえてまとめた。背景・トレードオフは`DASHCAM_ROCK5B_REPORT.md`・`DASHCAM_ROCK5B_SOFTWARE_HURDLES.md`
> を参照。

作成日：2026-08-13、同日OSインストール手順（1章）を公式ドキュメント再調査のうえ全面改訂
（Web調査ベース、ROCK 5B実機未着手のため机上調査段階の内容を含む）

---

## 0. 最初に押さえておくべき重要な仮説（x86ルートとの決定的な違い）

x86ルート（DC-5/DC-6）で`race_capture`アプリがクラッシュした`No matching FB config found`は、
Kivy/SDL2がX11の**デスクトップOpenGL（GLX）**を要求し、その二次フィルタ
（`XRenderFindVisualFormat`）で全滅していたことが濃厚な原因だった（詳細は`task_dashcam_breakdown.md`
DC-5参照）。

今回の調査で、AutosportLabs公式の**Raspberry Pi向けインストーラー**は、x86向けとは別の配布物・
別の依存パッケージ構成であることが判明した。

- Raspberry Pi版の依存パッケージ：`mesa-utils libgles2 libegl1-mesa libegl-mesa0 mtdev-tools`
  （出典：[RaceCapture on Raspberry Pi - Autosport Labs](https://wiki.autosportlabs.com/RaceCapture_on_Raspberry_Pi)）
- これは**EGL/OpenGL ES系**のパッケージ構成であり、x86版が使っていたGLX（デスクトップOpenGL、
  Xサーバー必須）とは異なるレンダリング経路を使っている可能性が高い
- 一方、ROCK 5B（Radxa OS/Debian 12 Bookworm）のデフォルトGPUドライバは**Panfrost/Panthor**
  （オープンソース）で、これは表向き「OpenGL ES: ✔、OpenGL(デスクトップ): ✔、OpenCL: ✘、
  Vulkan: ✘」という特性を持つ
  （出典：[Switch GPU driver | Radxa Docs](https://docs.radxa.com/en/rock5/rock5c/radxa-os/mali-gpu)）

**つまり「x86版バイナリでのGLXクラッシュ」と「ROCK 5B上でRaspberry Pi版バイナリ（EGL/GLESベース）
を動かす」は、そもそも別のレンダリング経路を通る可能性があり、x86ルートの`No matching FB config
found`問題がそのまま再発するとは限らない**、というのが現時点の新しい見立て。ただしこれは
Web調査からの推測であり、実機での検証（DC-9-3）で確認するまでは仮説の域を出ない。

**推奨**：DC-9-1（手元のRaspberry Piでの先行検証）をROCK 5B購入後・到着前にやっておくと、
「Raspberry Pi版バイナリがEGL/GLESベースで問題なく動くか」を先に切り分けられ、ROCK 5B側で
問題が起きた際に「ROCK 5B/Mali固有の問題か、Raspberry Pi版バイナリ自体の問題か」の判別が
容易になる。まだの場合は本手順と並行、または先行して着手することを推奨。

---

## 1. OSイメージの準備・eMMCへの書き込み

### 1.1 イメージの選定

Radxa公式ビルド（[radxa-build/rock-5b releases](https://github.com/radxa-build/rock-5b/releases)、
[ダウンロードページ](https://docs.radxa.com/en/rock5/rock5b/download)）は、現時点で
**Debian 12 Bookworm + KDEデスクトップ**版（`rock-5b_bookworm_kde_b5.output.img.xz`、Kernel 6.1）
が主要な配布形態（Bullseye版も別途あるが、race_captureのRaspberry Pi版インストーラーが
要求する「Debian 12 (bookworm) 64bit」に合わせ、**Bookworm版を選ぶこと**）。より軽量な
XFCE版・CLI版が用意されているかは到着時に改めてダウンロードページで確認すること（x86ルートでは
キオスク自動起動のためratpoison等の軽量WMに後から切り替えた実績があるので、KDE版で入手しても
DC-9-3以降の作業に支障はない）。

- 入手後、SHA256等のチェックサムをリリースページ記載値と照合すること（x86ルートDC-1-2/DC-6-6-1
  で毎回実施している習慣を踏襲）
- イメージは`.img.xz`形式で配布されているため、書き込み前に7-Zip等で解凍が必要
  （balenaEtcherが直接`.xz`を扱える場合もあるが、公式ドキュメントは「解凍してから」と明記）

### 1.2 書き込み方式（⚠️ メモリに記録していた従来方針からの訂正）

過去のチャットで「microSDから起動して`dd`でeMMCに書き込む」方式に決定済みと記録していたが、
今回Radxa公式ドキュメント・フォーラムを調べ直したところ、**この方式には確立された手順が
存在せず、実運用上の問題が報告されている**ことが判明した。訂正する。

- ⚠️ **問題点**：ROCK 5Bは**eMMCモジュールが装着されていると優先的にそちらから起動する**
  仕様のため、eMMCを挿したままmicroSDから起動させることができない（Radxa公式フォーラム
  [Is it possible to flash the eMMC from SD memory card boot](https://forum.radxa.com/t/is-it-possible-to-flash-the-emmc-from-sd-memory-card-boot/19007)
  で議論されているが、確実な回避策・具体的な成功コマンド例は示されないまま「別の方法を
  推奨する」という結論で終わっている）
- Radxa公式ドキュメントが実際に案内しているのは、次の2方式のいずれか

**方式A：eMMCモジュールを取り外し、USBリーダー経由でPCから直接書き込む（公式の主推奨）**

1. 必要なもの：**eMMC USBリーダー（別売りアダプタ）**、Windows PC、balenaEtcher
2. ROCK 5B基板からeMMCモジュールを取り外し、USBリーダーに挿してPCへ接続
3. balenaEtcherで「Flash from file」→解凍済みイメージを選択→「Select target」で
   **対象デバイスを慎重に確認**（誤って別のドライブを選ぶとそちらのデータが消える）→「Flash!」
4. 書き込み完了後、eMMCモジュールをROCK 5B基板へ戻す
   （出典：[Install the system on the eMMC Module | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/getting-started/install-os/boot-from-emmc)）
5. ⚠️ 今回の購入品リストに「eMMC USBリーダー」が含まれているか要確認（DC-9-2時点では
   本体・eMMC・電源・冷却ファン・microSDの手配は確認済みだが、USBリーダーについては
   別途確認が必要。無ければ方式Bを使う）

**方式B：ROCK 5B本体をMaskromモードにし、USB Type-C接続でRKDevTool（Windows）から直接書き込む**

USBリーダーを別途用意しなくても、ROCK 5B本体とPCをUSBケーブル1本で繋ぐだけで完結する方式。
Windows環境（PowerShell運用）のこのプロジェクトとは相性が良い。

1. 必要なもの：**RKDevTool**（Windows用ツール、Radxaダウンロードページから入手）、
   **USB Type-A to Type-Cケーブル（データ通信対応品。充電専用ケーブルは不可）**、
   対応するローダーファイル（loader.bin相当、イメージと同じダウンロードページに同梱の想定）
2. ROCK 5Bの電源を切り、（可能なら）microSD・NVMe等の他のブートメディアを外した状態にする
3. 基板上の**Maskromボタン（ラベル25、位置は到着後に基板シルクを確認）を押しながら**、
   USB Type-CケーブルでPCと接続し、接続後にボタンを離す
4. Windows側でRKDevToolを起動。左下に`Found One MASKROM Device`と表示されれば認識成功
   （USBドライバが必要な場合はRKDevTool付属のドライバをインストール）
5. RKDevToolで対応するLoaderファイルを選択→システムイメージファイルを選択→
   保存先メディアとして`eMMC`を選択→`Write by Address`にチェック→`RUN`ボタンで書き込み実行
6. 完了後、USBケーブルを外して電源を入れ直すと、eMMCから自動的に起動する
   （出典：[USB Flashing | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/low-level-dev/install-os/rkdevtool-emmc)、
   [Entering Maskrom Mode | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/low-level-dev/install-os/rkdevtool_maskrom)）

**方式選択の目安**：eMMC USBリーダーが手元にあれば方式A（GUIのみで完結し失敗しにくい）、
無ければ方式B（データ通信対応USBケーブルさえあれば追加ハードウェア不要）。到着後、
まず購入品にUSBリーダーが含まれているか確認してから方式を決めること。

### 1.3 microSDの用途について（訂正の補足）

eMMCへの書き込み自体にはmicroSDからの起動は使わない（1.2参照）。ただし今回のストレージ構成
（`DASHCAM_ROCK5B_REPORT.md`4.3節・メモリ記載の決定事項）では、microSDは**OS起動用ではなく
動画保存用**として使う想定のため、購入したmicroSDカードはeMMCでのOS起動が確認できた後、
録画データ保存用ストレージとしてマウントする（振動によるスロット脱落対策の物理固定は
別途検討）。この用途分担自体は変更なし。

### 1.4 初期セットアップ

初回起動後のデフォルトログイン情報は`radxa`/`radxa`（Radxa公式Debianイメージ共通）。まず
これでログインし、パスワード変更後、x86ルートDC-1-5/DC-6-2と同様の手順で以下を構築する。

- SSH鍵登録（ed25519、パスワード認証で一度ログイン→`~/.ssh/authorized_keys`へ公開鍵追記）
  ※既存の`amdpc_dashcam_ed25519`鍵を流用するか、ROCK 5B専用に新規鍵を作るかは到着時に判断
- パスワードなしsudo（`/etc/sudoers.d/ntakao-nopasswd`、`chmod 0440`）
- ホスト名・ユーザー名は`dashcam-test`系との混同を避けるため`rock5b-dashcam`等の別名を推奨
- IPアドレスはDHCP割当想定。ルーターのDHCPクライアント一覧かROCK 5B本体コンソールで確認

---

## 2. GPUドライバの確認

### 2.1 現在のドライバを確認

```bash
lsmod | grep -E 'panfrost|panthor|mali'
```

デフォルトはPanfrost/Panthor（オープンソース）のはず。

### 2.2 EGL/GLESの動作確認（x86ルートの`glxinfo`に相当）

x86ルートではGLX中心（`glxinfo`）で確認していたが、ROCK 5B/Raspberry Pi版はEGL/GLES中心の
可能性が高いため、確認コマンドも変わる：

```bash
sudo apt-get install -y mesa-utils libgles2 libegl1-mesa libegl-mesa0
es2_info      # OpenGL ESのコンテキスト情報（mesa-utils付属）
eglinfo       # EGL構成の一覧（mesa-utils or libegl1-mesa-devパッケージに含まれる場合あり）
```

`No matching FB config found`はGLX（X11+デスクトップOpenGL）特有のエラーメッセージなので、
EGLベースであればこのエラー文言自体は出ないはず。**もし同種のクラッシュが起きた場合、
エラーメッセージの文言が変わっている可能性が高いので、x86ルートの知見をそのまま検索キーワードに
使わず、実際に出力されたエラーメッセージで都度調査すること**。

### 2.3 Mali（プロプライエタリ）への切り替えは基本的に不要という判断

Mali切り替えが有効なのはOpenCL/Vulkan/8K HDMIが必要な場合。今回の用途（1080p30のダッシュ表示＋
録画）ではPanfrost（デフォルト）のままで問題ない見込み。もしPanfrost側でOpenGL ES関連の
クラッシュが解消しない場合の切り分け先として、Mali切り替え手順を記録しておく：

1. `/etc/apt/preferences.d/mali`でRockchip版xorg-xserverを優先するpin設定を作成
2. `apt-get install libmali-*`（該当バリアントはSoC世代で異なる、ROCK 5B=RK3588向けを選択）
3. `rsetup`からMali GPU Overlayを有効化
4. `/etc/modprobe.d/panfrost.conf`の`blacklist panfrost`をコメント解除
5. `echo "LIBGL_KOPPER_DISABLE=true" | sudo tee -a /etc/environment`

（出典：[Switch GPU driver | Radxa Docs](https://docs.radxa.com/en/rock5/rock5c/radxa-os/mali-gpu)。
Mali切り替えはOpenGL(デスクトップ)を失う代わりにOpenCL/Vulkan/8K HDMIを得るトレードオフのため、
race_captureがEGL/GLESベースなら効果は薄い可能性が高い点に注意）

---

## 3. race_captureアプリのインストール

### 3.1 事前確認（実行前に必ずスクリプト内容を読む）

x86ルートDC-4-1で行ったのと同じ姿勢で、実行前に必ずインストーラーの中身を確認する。

- Raspberry Pi向け公式インストーラーは短縮URL（`bit.ly/3yTbPyZ`）経由で配布されている
  （出典：[RaceCapture on Raspberry Pi - Autosport Labs](https://wiki.autosportlabs.com/RaceCapture_on_Raspberry_Pi)）。
  `curl -sIL bit.ly/3yTbPyZ`でリダイレクト先の実体（GitHubリポジトリ内のスクリプトパス）を
  確認してから、スクリプト本文を読むこと
- **要確認ポイント**：スクリプト内にRaspberry Pi固有のハードウェア判定
  （`/proc/device-tree/model`のチェックや`vcgencmd`呼び出し等）が含まれていないか。
  含まれている場合、ROCK 5B上ではスクリプトが早期に弾かれる可能性があるため、該当箇所を
  スキップするかローカルコピーを編集して実行する必要がある（AMD機向けにIntel専用パッケージを
  読み替えたDC-4-2と同じ要領）
- 要件表記に「Raspberry Pi, Bullseye 64bit」（旧バージョン記事）と「Debian 12 (bookworm) 64bit」
  （新しいバージョン、v2.9.0以降の記事）の両方の記述が見つかっており、要求バージョンが
  記事によって揺れている。ROCK 5B側のOSがBookworm系であれば、最新版のrace_captureアプリを
  使う前提で要件を満たしている可能性が高い

### 3.2 依存パッケージ・権限設定

```bash
sudo apt install mesa-utils libgles2 libegl1-mesa libegl-mesa0 mtdev-tools
sudo adduser $USER render
sudo adduser $USER video
sudo adduser $USER input
sudo adduser $USER dialout
```

（x86ルートDC-3-2で`video`/`render`グループ追加が必要だった経験、DC-6-6-7で`audio`グループ
追加が後から必要になった経験を踏まえ、`arecord -l`等でオーディオデバイスも確認し、必要なら
`adduser $USER audio`も追加しておくとよい）

### 3.3 インストール実行・配置

公式手順通りであれば、`/opt/racecapture`配下に展開され、`/opt/racecapture/run_racecapture_rpi.sh`
で起動する構成（x86版の`/opt/racecapture/race_capture`と配置は似ているが、起動スクリプト名が
異なる点に注意）。

---

## 4. 動作確認

### 4.1 ディスプレイ確保

x86ルートと同様、ヘッドレスで確認する場合は仮想ディスプレイ（`Xvfb`）または実Xorgセッション
（`sudo X :1`）が必要になる可能性がある。ただしEGLベースであれば、X11を介さず直接
DRM/KMS（フレームバッファ直描画）で起動できる可能性もあり、その場合はXorg起動自体が
不要になるかもしれない。まずは物理モニターを外部接続した状態での確認を優先し、
ヘッドレス確認はその後の補助手段とする（DC-9段階では外部モニター使用が前提として
すでに合意済み、`DASHCAM_ROCK5B_REPORT.md`5章参照）。

### 4.2 起動確認

```bash
DISPLAY=:1 /opt/racecapture/run_racecapture_rpi.sh
```

`[INFO] [GL] ...`や`[INFO] [Base] Start application main loop`に相当するログが出て、
ウェルカム画面（またはダッシュ画面）が表示されればGPU描画のハードルはクリア。
x86ルートDC-6-6-6と同様、初回起動時に`~/.config/racecapture`ディレクトリ不足で
即終了する可能性があるため、`FileNotFoundError`系のエラーが出た場合は
`mkdir -p ~/.config/racecapture`で解消できないか試す。

### 4.3 ESP32-C3（RaceCapture実機代わり）接続確認

DC-5-1と同じ要領で、Phase1本開発ファームウェアを書き込んだESP32-C3をROCK 5BへUSB接続し、
`/dev/ttyACM0`（Espressif USB JTAG/serial, VID `303a:1001`）として認識されること、
`dialout`グループ経由でsudoなしアクセスできることを確認する。race_captureアプリ側で
デバイス名・接続ステータス（緑ドット）が表示されればテレメトリー疎通も含めて成功。

---

## 5. このタスク（DC-9-3）のスコープ外・後続タスク

- `video-streamer`相当の自作（RKMPPベース）はDC-9-4で別途対応。本手順は`race_capture`
  アプリ単体の起動・GPU描画確認までが範囲
- キオスク自動起動（電源投入だけでの無人起動）はDC-9-3クリア後に改めて検討
  （x86ルートDC-7-1の知見はGDM3自動ログイン等OS共通部分は転用できる見込みだが、
  ratpoison設定ファイル等race_capture起動コマンド部分はRaspberry Pi版の起動スクリプト名
  （`run_racecapture_rpi.sh`）に合わせて書き換えが必要）

---

## トラブルシュート時の基本方針

1. x86ルートのエラーメッセージ・原因をそのまま当てはめず、まず実際に出たエラーメッセージで
   都度調査し直すこと（レンダリング経路が異なるため、同じ症状に見えても原因が違う可能性がある）
2. GPUベンダー非依存の問題か、ROCK 5B/Mali固有の問題かを切り分けるため、DC-9-1
   （Raspberry Pi単体での動作確認）の結果と突き合わせること
3. 詰まった場合の最終手段：`race_capture`はオープンソース
   （[autosportlabs/RaceCapture_App](https://github.com/autosportlabs/RaceCapture_App)）
   なので、ソースからのビルドという逃げ道が残っている
   （`DASHCAM_ROCK5B_SOFTWARE_HURDLES.md`3章参照）

---

## 出典

- [Switch GPU driver | Radxa Docs](https://docs.radxa.com/en/rock5/rock5c/radxa-os/mali-gpu)
- [Panthor open-source driver achieves OpenGL ES 3.1 conformance - CNX Software](https://www.cnx-software.com/2024/07/18/panthor-open-source-driver-achieves-opengl-es-3-1-conformance-with-arm-mali-g610-gpu-rk3588-soc/)
- [RaceCapture on Raspberry Pi - Autosport Labs](https://wiki.autosportlabs.com/RaceCapture_on_Raspberry_Pi)
- [RaceCapture app 2.9.0 with improved video support, plus a better Raspberry Pi installer – Autosport Labs](https://www.autosportlabs.com/racecapture-app-2-9-0-with-improved-video-support-plus-a-better-raspberry-pi-installer/)
- [Releases · radxa-build/rock-5b](https://github.com/radxa-build/rock-5b/releases)
- [Summary of resource downloads | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/download)
- [Install the system on the eMMC Module | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/getting-started/install-os/boot-from-emmc)
- [Install the system on the MicroSD card | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/getting-started/install-os/boot_from_sd_card)
- [USB Flashing (RKDevTool/eMMC) | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/low-level-dev/install-os/rkdevtool-emmc)
- [Entering Maskrom Mode | Radxa Docs](https://docs.radxa.com/en/rock5/rock5b/low-level-dev/install-os/rkdevtool_maskrom)
- [Is it possible to flash the eMMC from SD memory card boot - Radxa Community](https://forum.radxa.com/t/is-it-possible-to-flash-the-emmc-from-sd-memory-card-boot/19007)
- [Rock5/install/eMMC - Radxa Wiki（旧版、参考）](https://wiki.radxa.com/Rock5/install/eMMC)
