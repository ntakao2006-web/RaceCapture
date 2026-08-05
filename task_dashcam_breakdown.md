# ダッシュカム型リアルタイム映像配信システム サブタスク分解

> `DASHCAM_STREAMING_RESEARCH.md`（調査記録）7章「次のステップ」を受けての実作業ログ。
> ARCHITECTURE.mdの本編ロードマップ（Phase0〜5）とは独立した派生検討のため、
> タスクIDは`X-Y-Z`ではなく`DC-N`で採番する（8章のタスク分解ルールに準拠した運用）。
> 完了したタスクはこのファイル内でチェックし、区切りがついたら結論だけ
> `DASHCAM_STREAMING_RESEARCH.md`へ転記する。

---

## DC-1: 検証機（AMD PC）へのUbuntu Server導入・リモート操作環境構築 ※完了
- [x] DC-1-1: 手元で余っていたAMD PC（AMD A4 PRO-7300B APU with Radeon HD Graphics／メモリ8GB DDR3／SSD128GB、Windows 10プリインストール済み）を検証機として選定 ※Windows 10は完全消去してUbuntu専用機にする方針で合意
- [x] DC-1-2: Ubuntu Server 24.04.4 LTSのインストールUSBを作成 ※作業端末（AMD PCとは別のPC）にUSBメモリを挿し、PowerShellから直接操作して作成。管理者権限が必要な`Clear-Disk`/`Initialize-Disk`はツール実行環境が非管理者だったためユーザーに管理者PowerShellで実行してもらい、`Initialize-Disk`が「already initialized」エラーを出したためGPT変換はせずMBRのまま`Remove-Partition`→`New-Partition`→`Format-Volume(FAT32)`する方式に変更。ISOはSHA256チェックサム一致を確認済み(`E907D92E...138433`)
- [x] DC-1-3: 作成したUSBでAMD PCを起動しインストール実施 ※UEFIブートメニューでUSBを選択しGRUBまでは到達したが、`Try or Install Ubuntu Server`選択直後にWindowsへフォールバックする問題が発生。原因は**AMD-Vi(IOMMU)がAHCI(SATA)コントローラのDMAを弾くIO_PAGE_FAULT**（古いAMDマザーボードのBIOS/IVRSテーブル不備によるカーネルパニック→自動リブート）。GRUB編集画面(`e`キー)でカーネル起動行に`amd_iommu=off`を追記して回避しインストール完了。ディスクは128GB全体を使用（LVM、暗号化なし）、ホスト名`dashcam-test`、ユーザー名`ntakao`、OpenSSHサーバーを有効化してインストール
- [x] DC-1-4: インストール後の初回起動でも同じAMD-Vi問題が再発することを確認 ※`amd_iommu=off`はインストーラー起動時の一時パラメータでインストール後の起動設定には引き継がれないため。GRUB編集で再度`amd_iommu=off`を追記して起動し、SSH経由で`/etc/default/grub`の`GRUB_CMDLINE_LINUX_DEFAULT`に恒久設定→`update-grub`で解消。以降は再起動だけで正常に起動することを確認済み
- [x] DC-1-5: Claude Codeから直接リモート操作できる環境を構築 ※SSH鍵認証（ed25519、ユーザーが自分の端末でパスワード認証ログイン→公開鍵を`~/.ssh/authorized_keys`へ追記する一手間のみ実施）、パスワードなしsudo（`/etc/sudoers.d/ntakao-nopasswd`、`chmod 0440`必須）を設定し、以降sudoを含む全操作をSSH経由で実行できる状態にした
  - SSH秘密鍵は`C:\Users\ntaka\.ssh\amdpc_dashcam_ed25519`（Gitリポジトリの外、このPC上の永続的な場所）に保存済み。次のチャットでもこのファイルを`-i`オプションで指定すればそのまま接続できる（例: `ssh -i "C:/Users/ntaka/.ssh/amdpc_dashcam_ed25519" ntakao@<IPアドレス>`）。**このファイルは絶対にRaceCaptureリポジトリ内にコピー・移動しないこと**（コミット→自動push対象になり秘密鍵が漏洩するため）
  - ⚠️ IPアドレスが変わっていた場合や、AMD PC自体を再セットアップした場合は、この鍵の公開鍵(`amdpc_dashcam_ed25519.pub`)が`~/.ssh/authorized_keys`に残っているか要確認
  - ⚠️ IPアドレスはDHCP割当（確認時点で`192.168.68.55`）のため、次回接続時は変わっている可能性がある。変わっていた場合はルーターのDHCPクライアント一覧かAMD PC側のコンソールで再確認が必要

## DC-2: 物理モニターへの表示 ※保留（車載本番接続時に再検討）
- [x] DC-2-1: 物理モニター(iiyama ProLite X2382HS)への表示を試みたが、`DP-1`（DP→D-Sub変換アダプター経由）・`VGA-1`（D-Sub直結）いずれの接続でもBIOS/HPロゴまでは表示されるがUbuntu起動直後に信号が消える症状が発生。`video=`強制モード指定・`drm.edid_firmware=`によるEDID偽装を試したが解決せず、アダプターまたはケーブル自体の相性問題の可能性が高いと判断し、これ以上の深追いは中止
  - 結論：**この検証機でのソフトウェア的な原因究明はここで打ち切り、SSH中心の運用で進める**。車載本番でディスプレイ接続が必要になった時点で、別のケーブル・アダプター（またはそもそも別の小型機材）で改めて解決する
  - 起動オプションはクリーンアップ済み（`amd_iommu=off`のみ残し、`video=`/`drm.edid_firmware=`は削除済み）

---

## DC-3: VAAPI/VCEハードウェアエンコード対応確認 ※完了
- [x] DC-3-1: `mesa-va-drivers`（AMD GPU向けVAAPIドライバ）と`vainfo`をインストールする ※`sudo apt-get install -y mesa-va-drivers vainfo`で導入
- [x] DC-3-2: `vainfo`を実行し、このAPU(AMD A4 PRO-7300B、Richland世代、GPU: Radeon HD 8470D)がVCE(ハードウェアエンコーダ)のプロファイルを認識するか確認する ※**確認できた**。ドライバは`r600_drv_video.so`（Mesa Gallium、DRM 2.50.0 / kernel 6.8.0-136-generic）。`VAEntrypointEncSlice`（エンコード）が`VAProfileH264ConstrainedBaseline`/`Main`/`High`/`High10`の4プロファイルで利用可能と判明し、VCEによるH.264ハードウェアエンコードが使える見込み
  - ハマりどころ：ヘッドレスサーバーのため`vainfo`をデフォルト実行すると`error: can't connect to X server!`で失敗する。`vainfo --display drm --device /dev/dri/renderD128`と明示的にDRMモードを指定する必要がある
  - ハマりどころ：`ntakao`ユーザーが`/dev/dri/renderD128`の所有グループ`render`（および`card0`の`video`）に未所属で`Failed to open the given device!`となった。`sudo usermod -aG video,render ntakao`で恒久的に追加し、以降はsudoなしで`vainfo`が実行できることを確認済み（再ログイン後のSSHセッションで反映）

## DC-4: racecapture_streaming_install.shのAMD向け実行検証 ※完了
- [x] DC-4-1: AutosportLabs公式リポジトリから`racecapture_streaming_install.sh`を取得し内容を再確認する ※公式wiki(https://wiki.autosportlabs.com/Video_plus_data_streaming_with_racecapture)記載の`curl -sL bit.ly/3RL9Yoj | bash`のリダイレクト先を`curl -sIL`で確認したところ実体は`https://github.com/autosportlabs/racecapture_video_data_livestreaming`リポジトリの`racecapture_streaming_install.sh`(96行)と判明。内容は①`apt-get`で依存パッケージ導入、②podium.live APIから最新の`race_capture`/`video-streamer`のdebパッケージを取得し`dpkg -i`、③USB udevルール・グループ追加、④`~/Desktop/video-config.ini`雛形生成、⑤ratpoison(タイル型WM)による自動起動・キオスクセッション化、の5段構成
- [x] DC-4-2: スクリプト内のIntel専用パッケージをAMD向けに調整する ※検証機(dashcam-test)上のコピー`~/racecapture_setup/racecapture_streaming_install_amd.sh`で以下を変更。**①`intel-media-va-driver-non-free`→`mesa-va-drivers vainfo`**(DC-3で確認済みのAMD VCE用VAAPIドライバに読み替え)。加えて、Ubuntu 24.04(noble)環境特有の非互換が2点見つかり合わせて修正：**②`libegl1-mesa`→`libegl1`**(24.04ではパッケージ名変更、旧名は存在せず`apt-get install`全体が失敗しリスト内の他パッケージも道連れで入らなくなっていた)、**③`gconf2`を削除**(24.04には存在しないGNOME2時代の設定パッケージ、racecapture/video-streamerの依存関係には無関係と確認済み)
- [x] DC-4-3: 調整したスクリプトを実行し、`race_capture`・`video-streamer`の各プロセスが起動するか確認する ※`racecapture`(2.18.0)・`video-streamer`(0.4.0)とも`dpkg -l`で`ii`(正常インストール)まで到達。プロセス起動確認はヘッドレスサーバーのため`Xvfb`(仮想ディスプレイ)上で実施：
  - **race_capture**：起動はするが`No matching FB config found`で即終了(exit 102)。`glxinfo`ではXvfb上でも`llvmpipe`ソフトウェアレンダラでGLXは機能していることを確認済みのため、Kivy(SDL2 x11バックエンド)が要求する特定のFBConfig(深度/ステンシル構成)にXvfbの疑似GLXが対応していないテスト環境固有の制約と判断。**これは物理ディスプレイ+実GPU(Radeon HD 8470D、DRM直結)接続時には再発しない可能性が高く、DC-2で保留中の物理モニター接続問題の解消と合わせて実ディスプレイ上で再確認が必要**
  - **video-streamer**：`--help`等の引数は無く即座に`video-config.ini`(初回導入時は`~/Desktop/`ディレクトリが無く生成に失敗していたため手動作成)を読んで動作する仕様と判明。ローカル録画設定のみで起動したところ、GStreamerの`file_h264_enc`エレメント作成に失敗して終了(exit 0、クラッシュではなく正常なエラーハンドリング)。原因切り分けの過程で以下が判明：
    - `gst-inspect-1.0`(診断コマンド)・GStreamerの`vaapi`プラグイン本体がいずれもインストールされておらず、元のインストールスクリプトのパッケージリストにも含まれていなかった(**`gstreamer1.0-vaapi`・`gstreamer1.0-tools`を追加導入する必要がある**、AMD/Intel問わず本来必要な項目だった可能性)。追加後`gst-inspect-1.0 vaapi`で`vaapih264enc`(VA-API H264エンコーダー)を含む7エレメントが登録されることを確認
    - それでも`file_h264_enc`作成には失敗。`/dev/video*`が存在せず(`ls`で確認)、USBカメラ未接続がキャプチャパイプライン構築失敗の直接原因と判断。**これはDC-5(実機/USBカメラ接続)待ちの想定内の制約**であり、video-streamer自体はプロセスとして正常に起動しログも適切に出力することを確認できた

## DC-5: 実機接続検証 ※DC-5-1完了、DC-5-2は途中で新たな課題を発見し中断中
- [x] DC-5-1: RaceCapture実機・USBカメラをAMD PCへ接続する ※購入済みのRaceCapture実機がまだ無いため、Phase1本開発ファームウェア(`firmware/src/main.cpp`、RCP応答・ダミーテレメトリ送信まで実装済み)を予備のESP32-C3へ書き込み、「実機」代わりとしてAMD PC(dashcam-test)へUSB接続する方式を採用（ユーザー判断）。COM12でビルド・書き込み・シリアルログ確認後、AMD PCへ物理接続。SSH側で`/dev/ttyACM0`(Espressif USB JTAG/serial, VID 303a:1001)として認識、`ntakao`ユーザーは`dialout`グループ所属済みでsudoなしアクセス可能、実際にテレメトリーログがシリアル経由で流れてくることを確認済み。USBカメラ(BUFFALO BSWHD06M)も`/dev/video0`/`/dev/video1`として認識済み(DC-4以前から接続済み)
- [ ] DC-5-2: ダッシュ表示・映像へのデータ焼き込みが実際に動作するか確認する ※**video-streamer側は根本原因を特定・解消できたが、race_capture(ダッシュGUI)側で新たな未解決課題が見つかり中断中**。詳細は次の2項目
  - ✅ **video-streamerのVAAPI初期化失敗を解消**：DC-4-3で確認した`file_h264_enc`エレメント作成失敗の真因は、USBカメラ未接続ではなく（カメラは今回接続済みでも同じ失敗が再現した）、`video-streamer`にバンドルされた2022年当時の古い`libstdc++.so.6`/`libva*.so.2`が、Ubuntu 24.04環境のMesa VAAPIドライバ(`r600_drv_video.so`が要求する`GLIBCXX_3.4.32`や、システムの新しいlibva ABI)と非互換だったことが原因と判明。`LD_PRELOAD=/usr/lib/x86_64-linux-gnu/{libstdc++.so.6,libva.so.2,libva-drm.so.2,libva-x11.so.2}`でシステム側の新しいライブラリを優先させることで解消し、`file_h264_enc`の作成に初めて成功、パイプライン(`telemetry-vid-pipeline`)が実際に起動することを確認した
  - ⚠️ **新発見：video-streamerの映像取り込み方式が判明し、race_capture(ダッシュGUI)の実描画が必須と確定**。video-streamerの映像ソースはUSBカメラ(V4L2)を直接GStreamerで合成しているのではなく、`ximagesrc`（X11画面キャプチャ）で**race_captureアプリのダッシュ画面の描画結果を丸ごとキャプチャする**方式だった。そのため「データ焼き込み」を機能させるには、race_captureアプリのGUIが実際にX11セッション上で描画されている状態が構造的に必須（ヘッドレスでは`Could not open X display for reading`で失敗し続ける）
  - ⚠️ **race_capture(Kivy/SDL2アプリ)がX11セッション上で`No matching FB config found`により起動失敗、原因未特定のまま中断**。DC-4-3では「Xvfb(ソフトウェアレンダラ)特有の問題」という仮説だったが、今回**実GPU(Radeon HD 8470D、Mesaのradeonクラシックドライバ、DRI2/r600)を使った本物のXorgセッションでも全く同じエラーが再現**し、この仮説は否定された。検証手順：`xserver-xorg-core`/`xserver-xorg-video-ati`/`xinit`を新規導入し、`sudo X :1`で物理モニター非接続のままXorgを起動（カーネル起動オプションに残っていた`drm.edid_firmware=VGA-1:edid/1920x1080.bin`のおかげでVGA-1が「connected」として扱われ、EDID偽装だけでXサーバー自体は起動できた。これはDC-2で試して「解消せず」と記録した方法だが、物理モニターに映すことは諦めても**Xサーバーを起動させるためのEDID偽装としては機能していた**という新しい理解）。`glxinfo`で`direct rendering: Yes`・`OpenGL 4.5`・528件のGLXFBConfigs（depth24/stencil8/RGBA8888/ダブルバッファ付きの標準的な組み合わせを含む）を確認し、GLX自体は正常に機能しているにもかかわらず、`race_capture`実行時は変わらず`No matching FB config found`で終了(exit 102)。`SDL_VIDEO_X11_FORCE_EGL=1`環境変数、`~/.kivy/config.ini`の`multisamples`を2→0に変更、のいずれも効果なし。`strace`で見る限りGLXライブラリ自体は正常にロードされている。原因はKivy 2.3.1同梱のSDL2(2.30.7、`Kivy.libs/libSDL2-2-d9872e50.0.so.0.3000.7`)とこの古い世代のMesa `radeon`クラシックDDX/glamorスタックとの間のFBConfig選択ロジックの非互換と推測されるが、未特定
  - **重要な認識の訂正**：DC-2（物理モニター接続問題）と今回のrace_capture FBConfigクラッシュは**別々の問題**と判明した。ヘッドレス（モニター非接続）でも本物のXorg+GLXは起動できることを確認したため、**DC-2の物理モニター/ケーブル問題を仮に解決できたとしても、race_captureのFBConfigクラッシュ自体は別途解決が必要**（両方解決して初めてダッシュ表示が成立する）
  - ✅ **原因をさらに特定：Kivy固有の問題ではなく、SDL2自体がこのGPU/ドライバ組み合わせでGLX visualを見つけられていないと判明**。Kivyの起動ログの2行目`Provider: x11(['window_sdl2'] ignored)`は、実際にはSDL2ではなく**Kivy独自のネイティブX11ウィンドウ実装(`kivy/core/window/window_x11_core.c`)が選ばれ、SDL2側が無視されていた**ことを示すログだったと判明（Web調査でソースコードを確認）。このネイティブ実装は`glXChooseFBConfig`でRGBA8888/depth≥16/stencil≥8/ダブルバッファのFBConfigを検索した後、さらに`XRenderFindVisualFormat`でalpha対応のXRenderフォーマットと一致するものだけに絞り込む処理があり、**一致しなければフォールバックなしで即座に`fatalError("No matching FB config found")`**という実装（`glXChooseFBConfig`自体は候補を返していても、この二次フィルタで全滅していた可能性が高い）。そこで`KIVY_WINDOW=sdl2`環境変数でSDL2プロバイダを強制したところ、**Kivy独自コードの問題ではなく、SDL2自体が`RuntimeError: Couldn't find matching GLX visual`で同様に失敗する**ことを確認した
  - ✅ **さらに切り分けを進め、システム側のGLXスタック自体は正常に機能していることを確定させた**。`xdpyinfo`でdepth 32のTrueColor X Visual（compositing用のARGB visual）が実在すること、`glxinfo`の全528件のGLXFBConfigsの中にKivyの要求(RGBA8888/depth≥16/stencil≥8/ダブルバッファ)に完全一致するdepth 32の設定(`0x2a2`等)が存在することを確認。念のためPython3のctypesで`glXChooseFBConfig`をKivyと全く同じ属性で直接呼び出すテストを行ったところ、**18件のFBConfigがマッチし、`glXGetVisualFromFBConfig`でのVisual取得にも成功**した。つまりシステムのGLX/Mesa/Xサーバー自体には問題がなく、race_capture固有の何らかの問題である
  - ⚠️ **race_captureがバンドルしている古い`libX11.so.6`/`libXrender.so.1`が原因という仮説を試したが効果なし**。`video-streamer`で有効だった手法(`LD_PRELOAD`でシステム側の新しいライブラリを優先)をrace_captureにも適用したが、Kivyネイティブ実装・SDL2強制のいずれでも症状は変化しなかった。`LD_LIBRARY_PATH`をシステムパス優先に変更しても同様に無効だった。**PyInstallerでバンドルされたバイナリは`$ORIGIN`相対のRPATHや絶対パス指定の`dlopen`でバンドル済みライブラリを直接読み込んでいる可能性が高く、`LD_PRELOAD`/`LD_LIBRARY_PATH`のような外部からの環境変数介入では回避できない**と推測される（GL/GLXライブラリ自体はシステムパスから正しくロードされていることをstraceで確認済みのため、X11/XRender側の何らかの古いバンドル版特有の非互換が濃厚だが、これ以上はgdb等でのソースレベルデバッグかrace_capture自体のソースからの再ビルドが必要と判断し、一旦調査を打ち切った）
  - 作業ログ：`/tmp/rc_test*.log`・`/tmp/vs_test.log`・`/tmp/glx_test.py`（AMD PC上、次回接続時に参照可能。恒久保存はしていない）

---

## DC-6: Intel実機(EliteDesk 800 G3系)での再検証 ※ハードウェア入れ替え・準備中
DC-5-2でAMD機(A4 PRO-7300B, Mesaのclassic `radeon`ドライバ)固有の環境問題である可能性が高いと
判断したため、AutosportLabs公式の推奨・動作確認済み実機に近い**HP EliteDesk 800 G3系（Intel
Core i5 第7世代、メモリ24GB、SSDは今回のAMD機で使っていたものを流用しOSは新規インストール）**
での再検証に切り替える。

- [x] DC-6-1: EliteDeskへUbuntu Server 24.04 LTSを新規インストール（DC-1と同様の手順。SSDは
      リセットされる想定） ※完了
  - ⚠️ 流用予定のSSDには当初AMD機のUbuntu環境（`amd_iommu=off`のGRUB設定、DC-5-2のVGA-1向け
    EDID偽装、`mesa-va-drivers`・`xserver-xorg-video-ati`等AMD向けパッケージ）が残っていたが、
    新規インストールで上書き済み
  - ハマりどころ：EliteDesk本体でBIOS/POST画面が出ず再起動ループのように見える症状が発生したが、
    原因はSSDやOS側ではなくディスプレイ接続だった。この機種（HP EliteDesk 800 G3、Mini型では
    なく通常サイズ＝SFF/Tower系）は背面に**DisplayPort×2 + VGA×1が標準搭載**（Mini型は
    DisplayPortのみでHDMI非搭載という別構成のため要注意）。VGA接続に切り替えて解消
  - USBインストーラー自体はDC-1-2で作成したものをそのまま使い回した（アーキ非依存、AMD向けの
    変更はUSBには含まれていない。DC-1-3のGRUB編集`amd_iommu=off`はIntel機では不要で、実際に
    編集なしで正常インストールできた）
  - インストール完了、ホスト名`dashcam-test`（旧AMD機と同名だが別実機、IP`192.168.68.62`）・
    ユーザー名`ntakao`・OpenSSHサーバー有効化で構成
- [x] DC-6-2: SSH接続・パスワードなしsudoなど、DC-1-5相当のリモート操作環境を再構築 ※完了
  - 新規インストールのため旧SSH鍵の`authorized_keys`登録は引き継がれておらず、再設定が必要
    だった。作業PCとEliteDeskが別ネットワークに接続されていて最初SSH疎通できなかったが、
    ネットワーク再接続で解消（`192.168.68.x`セグメントに合わせる）
  - 既存の秘密鍵(`C:\Users\ntaka\.ssh\amdpc_dashcam_ed25519`)はそのまま継続使用。公開鍵を
    パスワード認証SSH経由で`~/.ssh/authorized_keys`へ追記、`/etc/sudoers.d/ntakao-nopasswd`も
    再設定し、鍵認証・パスワードなしsudoとも動作確認済み
- [x] DC-6-3: `racecapture_streaming_install_intel.sh`（本リポジトリに保存済み。DC-5-2の
      調査を踏まえ、公式スクリプトからUbuntu 24.04向けの3点だけを修正したIntel版。詳細は
      ファイル冒頭のコメント参照）を実行し、`racecapture`・`video-streamer`のインストールを
      確認 ※完了
  - ✅ スクリプト内容を確認済み：DC-4-2でAMD機向けに`intel-media-va-driver-non-free`→
    `mesa-va-drivers`と読み替えていた箇所は、本ファイルでは公式スクリプト通り
    `intel-media-va-driver-non-free`のまま維持されている（Intel機向けなので読み替え不要で正しい）。
    CPUベンダーに関係ないUbuntu 24.04固有の3修正（`libegl1-mesa`→`libegl1`、`gconf2`削除、
    `gstreamer1.0-vaapi`/`gstreamer1.0-tools`追加）のみが反映されており、修正漏れなし
  - リモート(SSH)からスクリプトを転送・実行。`dpkg -l`で`racecapture`(2.18.0)・
    `video-streamer`(0.4.0)とも`ii`(正常インストール)を確認
  - ✅ `vainfo --display drm --device /dev/dri/renderD128`で`iHD_drv_video.so`(Intel iHD
    driver、VA-API 1.20)がロードされ、H.264(Main/High/ConstrainedBaseline)の
    `VAEntrypointEncSlice`(エンコード)が確認できた（システムレベルでのVAAPI動作確認）
  - ⚠️ **【DC-6-4での訂正】上記はシステムレベルの`vainfo`確認であり、実際には`video-streamer`
    自体は依然`LD_PRELOAD`が必要だった**（詳細はDC-6-4参照）。「Intel機ではLD_PRELOAD不要」は
    誤った予測だったため撤回する
  - ハマりどころ（DC-4-3と同じ既知の問題、再発）：スクリプト末尾で`~/Desktop`が存在せず
    `video-config.ini`生成に失敗(exit 2の原因)、および`/var/lib/AccountsService/users/ntakao`
    unmatched不在で`sed`が失敗。いずれも非致命的で`racecapture`/`video-streamer`のインストール
    自体には影響なし。`mkdir -p ~/Desktop`で手動対処済み（AccountsService側はキオスク自動起動を
    設定する際に改めて対応）
- [x] DC-6-4: USBカメラ・ESP32-C3（DC-5-1のESP32実機、または新規に同じ手順で書き込んだもの）を
      接続し、DC-5-2で確認した`video-streamer`のVAAPI動作（`file_h264_enc`エレメント作成）を
      再確認 ※完了
  - USBカメラ(BUFFALO BSWHD06M→`/dev/video0`/`/dev/video1`)・ESP32-C3(→`/dev/ttyACM0`,
    Espressif USB JTAG/serial)とも`lsusb`・デバイスファイルで正常認識。ESP32-C3からのRCP
    テレメトリー出力もDC-5-1同様に確認できた（開発中ファームウェアのデバッグログとJSON RCP
    メッセージが同一シリアル上に混在するのは既知の仕様、新たな問題ではない）
  - ⚠️ **予想は外れ、Intel機でも`video-streamer`単体では`LD_PRELOAD`なしだと`file_h264_enc`
    作成に失敗した**：`libva error: dlopen of .../iHD_drv_video.so failed:
    /opt/video-streamer/libstdc++.so.6: version 'GLIBCXX_3.4.32' not found (required by
    /lib/x86_64-linux-gnu/libigdgmm.so.12)`。つまりDC-5-2で見つかった問題は**AMD固有ではなく、
    video-streamerにバンドルされた2022年当時の古い`libstdc++.so.6`が、Ubuntu 24.04の新しい
    Mesa/Intelドライバ側ライブラリと衝突するという、ベンダー非依存の汎用的な非互換**だった
  - ✅ DC-5-2と同じ`LD_PRELOAD=/usr/lib/x86_64-linux-gnu/{libstdc++.so.6,libva.so.2,
    libva-drm.so.2,libva-x11.so.2}`を適用したところ`va_openDriver() returns 0`で解消し、
    VAAPI初期化に成功。その後は想定通り`ximagesrc`が`Could not open X display for reading`
    で失敗（race_captureのGUI描画＝X11セッションが必須という、DC-5-2で判明した仕様通りで
    新たな問題ではない）
- [x] DC-6-5: `race_capture`アプリの起動を確認し、DC-5-2で発生した`No matching FB config found`
      / `Couldn't find matching GLX visual`が再発しないか検証 ※完了
  - `xserver-xorg-core`・`xserver-xorg-video-intel`は`racecapture_streaming_install_intel.sh`
    導入時の依存関係で既にインストール済みだった。`xinit`のみ追加導入し、`sudo X :1`で物理
    モニター非接続のままXorgを起動（DC-5-2と同様、EDID偽装なしでも起動できた）
  - `glxinfo`で`direct rendering: Yes`・`OpenGL 4.6`・Mesa Intel UHD Graphics 630(CFL GT2)・
    GLXFBConfigs 992件、`xdpyinfo`でdepth 32のTrueColor Visual多数（`0x6d`等）を確認。
    システムのGLX/Mesa/Xサーバー自体はAMD機同様に正常機能している
  - 🔴 **確定：`No matching FB config found`(exit 102)がIntel機（Mesa `iris`系ドライバ、
    AMD機とは全く異なるGPUベンダー・ドライバスタック）でも完全に再現した**。depth32 Visual・
    十分な数のGLXFBConfigsが存在するにもかかわらず失敗することもAMD機と同一の症状。これにより
    DC-6全体の目的だった「AMD機固有の環境問題か、race_capture配布バイナリ自体の一般的な
    非互換か」の切り分けが完了し、**後者（race_capture配布バイナリ自体がUbuntu 24.04世代の
    Mesa/Xorg/XRenderスタックと一般的に非互換）と確定**。DC-5-2で推測した「Kivyネイティブ
    実装/SDL2の内部的な二次フィルタ(`XRenderFindVisualFormat`)がGPUベンダーを問わず失敗する」
    という仮説を強く支持する結果。これ以上の解決にはrace_capture自体のソースからの再ビルド、
    または旧バージョンのUbuntu/Mesaへのダウングレードが必要と判断し、実機切り替えによる
    切り分け調査はここで完了とする
- [ ] DC-6-6: ダッシュ表示・映像へのデータ焼き込みが実際に動作するか最終確認（DC-5-2の元々の目的）
  - DC-6-5の結果により、現状の配布バイナリのままでは本タスクの達成は困難と判明。着手には
    前提となる対応方針（race_captureの再ビルド／別バージョン入手／Ubuntuダウングレード等）の
    決定が必要なため保留

---

*次のチャットでは「DC-6から進めて」のように指定すれば、このファイルとリポジトリ直下の
`racecapture_streaming_install_intel.sh`を参照して作業を再開できる。*
