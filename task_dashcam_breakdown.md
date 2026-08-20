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

## DC-5: 実機接続検証 ※DC-5-1完了、DC-5-2はAMD機+Ubuntu24.04では中断のままだが、DC-6-6-7(Intel機+Ubuntu22.04)で元々の目的自体は達成された
- [x] DC-5-1: RaceCapture実機・USBカメラをAMD PCへ接続する ※購入済みのRaceCapture実機がまだ無いため、Phase1本開発ファームウェア(`firmware/src/main.cpp`、RCP応答・ダミーテレメトリ送信まで実装済み)を予備のESP32-C3へ書き込み、「実機」代わりとしてAMD PC(dashcam-test)へUSB接続する方式を採用（ユーザー判断）。COM12でビルド・書き込み・シリアルログ確認後、AMD PCへ物理接続。SSH側で`/dev/ttyACM0`(Espressif USB JTAG/serial, VID 303a:1001)として認識、`ntakao`ユーザーは`dialout`グループ所属済みでsudoなしアクセス可能、実際にテレメトリーログがシリアル経由で流れてくることを確認済み。USBカメラ(BUFFALO BSWHD06M)も`/dev/video0`/`/dev/video1`として認識済み(DC-4以前から接続済み)
- [ ] DC-5-2: ダッシュ表示・映像へのデータ焼き込みが実際に動作するか確認する ※**video-streamer側は根本原因を特定・解消できたが、race_capture(ダッシュGUI)側で新たな未解決課題が見つかり中断中**。詳細は次の2項目
  - 🎉 **後日談**：本項目自体(AMD機+Ubuntu24.04環境)はFBConfig問題未解決のまま中断しているが、「ダッシュ表示・映像へのデータ焼き込みが実際に動作するか」という**元々の目的自体は、DC-6（Intel機+Ubuntu22.04ダウングレード）のDC-6-6-7で最終的に達成された**。詳細はDC-6-6-7参照
  - ✅ **video-streamerのVAAPI初期化失敗を解消**：DC-4-3で確認した`file_h264_enc`エレメント作成失敗の真因は、USBカメラ未接続ではなく（カメラは今回接続済みでも同じ失敗が再現した）、`video-streamer`にバンドルされた2022年当時の古い`libstdc++.so.6`/`libva*.so.2`が、Ubuntu 24.04環境のMesa VAAPIドライバ(`r600_drv_video.so`が要求する`GLIBCXX_3.4.32`や、システムの新しいlibva ABI)と非互換だったことが原因と判明。`LD_PRELOAD=/usr/lib/x86_64-linux-gnu/{libstdc++.so.6,libva.so.2,libva-drm.so.2,libva-x11.so.2}`でシステム側の新しいライブラリを優先させることで解消し、`file_h264_enc`の作成に初めて成功、パイプライン(`telemetry-vid-pipeline`)が実際に起動することを確認した
  - ⚠️ **新発見：video-streamerの映像取り込み方式が判明し、race_capture(ダッシュGUI)の実描画が必須と確定**。video-streamerの映像ソースはUSBカメラ(V4L2)を直接GStreamerで合成しているのではなく、`ximagesrc`（X11画面キャプチャ）で**race_captureアプリのダッシュ画面の描画結果を丸ごとキャプチャする**方式だった。そのため「データ焼き込み」を機能させるには、race_captureアプリのGUIが実際にX11セッション上で描画されている状態が構造的に必須（ヘッドレスでは`Could not open X display for reading`で失敗し続ける）
  - ⚠️ **race_capture(Kivy/SDL2アプリ)がX11セッション上で`No matching FB config found`により起動失敗、原因未特定のまま中断**。DC-4-3では「Xvfb(ソフトウェアレンダラ)特有の問題」という仮説だったが、今回**実GPU(Radeon HD 8470D、Mesaのradeonクラシックドライバ、DRI2/r600)を使った本物のXorgセッションでも全く同じエラーが再現**し、この仮説は否定された。検証手順：`xserver-xorg-core`/`xserver-xorg-video-ati`/`xinit`を新規導入し、`sudo X :1`で物理モニター非接続のままXorgを起動（カーネル起動オプションに残っていた`drm.edid_firmware=VGA-1:edid/1920x1080.bin`のおかげでVGA-1が「connected」として扱われ、EDID偽装だけでXサーバー自体は起動できた。これはDC-2で試して「解消せず」と記録した方法だが、物理モニターに映すことは諦めても**Xサーバーを起動させるためのEDID偽装としては機能していた**という新しい理解）。`glxinfo`で`direct rendering: Yes`・`OpenGL 4.5`・528件のGLXFBConfigs（depth24/stencil8/RGBA8888/ダブルバッファ付きの標準的な組み合わせを含む）を確認し、GLX自体は正常に機能しているにもかかわらず、`race_capture`実行時は変わらず`No matching FB config found`で終了(exit 102)。`SDL_VIDEO_X11_FORCE_EGL=1`環境変数、`~/.kivy/config.ini`の`multisamples`を2→0に変更、のいずれも効果なし。`strace`で見る限りGLXライブラリ自体は正常にロードされている。原因はKivy 2.3.1同梱のSDL2(2.30.7、`Kivy.libs/libSDL2-2-d9872e50.0.so.0.3000.7`)とこの古い世代のMesa `radeon`クラシックDDX/glamorスタックとの間のFBConfig選択ロジックの非互換と推測されるが、未特定
  - **重要な認識の訂正**：DC-2（物理モニター接続問題）と今回のrace_capture FBConfigクラッシュは**別々の問題**と判明した。ヘッドレス（モニター非接続）でも本物のXorg+GLXは起動できることを確認したため、**DC-2の物理モニター/ケーブル問題を仮に解決できたとしても、race_captureのFBConfigクラッシュ自体は別途解決が必要**（両方解決して初めてダッシュ表示が成立する）
  - ✅ **原因をさらに特定：Kivy固有の問題ではなく、SDL2自体がこのGPU/ドライバ組み合わせでGLX visualを見つけられていないと判明**。Kivyの起動ログの2行目`Provider: x11(['window_sdl2'] ignored)`は、実際にはSDL2ではなく**Kivy独自のネイティブX11ウィンドウ実装(`kivy/core/window/window_x11_core.c`)が選ばれ、SDL2側が無視されていた**ことを示すログだったと判明（Web調査でソースコードを確認）。このネイティブ実装は`glXChooseFBConfig`でRGBA8888/depth≥16/stencil≥8/ダブルバッファのFBConfigを検索した後、さらに`XRenderFindVisualFormat`でalpha対応のXRenderフォーマットと一致するものだけに絞り込む処理があり、**一致しなければフォールバックなしで即座に`fatalError("No matching FB config found")`**という実装（`glXChooseFBConfig`自体は候補を返していても、この二次フィルタで全滅していた可能性が高い）。そこで`KIVY_WINDOW=sdl2`環境変数でSDL2プロバイダを強制したところ、**Kivy独自コードの問題ではなく、SDL2自体が`RuntimeError: Couldn't find matching GLX visual`で同様に失敗する**ことを確認した
  - ✅ **さらに切り分けを進め、システム側のGLXスタック自体は正常に機能していることを確定させた**。`xdpyinfo`でdepth 32のTrueColor X Visual（compositing用のARGB visual）が実在すること、`glxinfo`の全528件のGLXFBConfigsの中にKivyの要求(RGBA8888/depth≥16/stencil≥8/ダブルバッファ)に完全一致するdepth 32の設定(`0x2a2`等)が存在することを確認。念のためPython3のctypesで`glXChooseFBConfig`をKivyと全く同じ属性で直接呼び出すテストを行ったところ、**18件のFBConfigがマッチし、`glXGetVisualFromFBConfig`でのVisual取得にも成功**した。つまりシステムのGLX/Mesa/Xサーバー自体には問題がなく、race_capture固有の何らかの問題である
  - ⚠️ **race_captureがバンドルしている古い`libX11.so.6`/`libXrender.so.1`が原因という仮説を試したが効果なし**。`video-streamer`で有効だった手法(`LD_PRELOAD`でシステム側の新しいライブラリを優先)をrace_captureにも適用したが、Kivyネイティブ実装・SDL2強制のいずれでも症状は変化しなかった。`LD_LIBRARY_PATH`をシステムパス優先に変更しても同様に無効だった。**PyInstallerでバンドルされたバイナリは`$ORIGIN`相対のRPATHや絶対パス指定の`dlopen`でバンドル済みライブラリを直接読み込んでいる可能性が高く、`LD_PRELOAD`/`LD_LIBRARY_PATH`のような外部からの環境変数介入では回避できない**と推測される（GL/GLXライブラリ自体はシステムパスから正しくロードされていることをstraceで確認済みのため、X11/XRender側の何らかの古いバンドル版特有の非互換が濃厚だが、これ以上はgdb等でのソースレベルデバッグかrace_capture自体のソースからの再ビルドが必要と判断し、一旦調査を打ち切った）
  - 作業ログ：`/tmp/rc_test*.log`・`/tmp/vs_test.log`・`/tmp/glx_test.py`（AMD PC上、次回接続時に参照可能。恒久保存はしていない）

---

## DC-6: Intel実機(EliteDesk 800 G3系)での再検証 ※完了。Ubuntu 22.04ダウングレードによりダッシュ表示+映像データ焼き込みの動作を実証
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
  - ⚠️ DC-1-5と同じ注意点：IPアドレス`192.168.68.62`はDHCP割当のため、EliteDesk再起動後は
    変わっている可能性がある（変わっていればEliteDesk側コンソールか`ip a`で再確認）。また、
    Claude Codeを動かす作業PCがEliteDeskと同じ`192.168.68.x`のLANに接続されていないと
    そもそも到達できない（今回まさに発生した問題）。次回接続できない場合はまずこの2点と
    EliteDesk本体の電源状態を確認する
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
- [x] DC-6-6: ダッシュ表示・映像へのデータ焼き込みが実際に動作するか最終確認（DC-5-2の元々の目的） ※完了、達成
  - DC-6-5の結果により、現状の配布バイナリのままでは本タスクの達成は困難と判明。対応方針は
    ユーザー判断で**「EliteDeskをUbuntu 22.04 LTSへダウングレードし、race_capture配布バイナリが
    動作実績を持つ世代のMesa/Xorgへ戻す」**に決定（他候補：ソース再ビルド／旧バージョン入手／
    映像焼き込み自体を諦める、は不採用）。以下のサブタスクに分解して進める
  - [x] DC-6-6-1: Ubuntu Server 22.04 LTS（最新ポイントリリース22.04.5）のインストールUSBを作成 ※完了
    - `ubuntu-22.04.5-live-server-amd64.iso`をUbuntu公式(releases.ubuntu.com)から取得し
      SHA256チェックサム一致を確認済み(`9bc6028870...aa98b0`)。USBメモリはDC-1-2で使用したもの
      を再利用（ディスク1、ELECOM MF-MSU2B、31GB、MBR）
    - ハマりどころ：`Remove-Partition`実行直後、Windowsが未フォーマットボリュームを検知して
      自動的にGUIのフォーマットダイアログをポップアップさせ、それを使おうとすると
      「Windowsはフォーマットを完了できませんでした」で失敗する事象が発生。GUIダイアログは
      キャンセルし、`New-Partition -UseMaximumSize -IsActive -AssignDriveLetter | Format-Volume
      -FileSystem FAT32`をコマンド経由で実行することで解消（USBの抜き差しを挟んでもディスク
      番号は1のまま変化なし）
    - ISO中身は`Mount-DiskImage`→`robocopy`→`Dismount-DiskImage`でUSBへ展開。DC-1-2と同様、
      dd的なraw書き込みではなくFAT32へのファイル展開方式（Ubuntu ServerのISOサイズは
      約2GBのためFAT32の単一ファイル4GB制限には抵触しない）
  - [x] DC-6-6-2: EliteDeskへUbuntu 22.04 LTSを新規インストール（DC-6-1相当の手順） ※完了
    - VGA接続・ディスク全体(LVM、暗号化なし)・ホスト名`dashcam-test`・ユーザー名`ntakao`・
      OpenSSHサーバー有効化、いずれもDC-6-1と同じ設定でインストール完了。
      Ubuntu 22.04.5 LTS(jammy)であることを確認済み
  - [x] DC-6-6-3: SSH接続・パスワードなしsudoの再構築（DC-6-2相当の手順） ※完了
    - IPアドレスは前回(DC-6-1〜DC-6-5時点)と同じ`192.168.68.62`のまま変わらず
    - 新規インストールのためSSHホストキーが変わり`known_hosts`が警告を出したため
      `ssh-keygen -R`で古いエントリを削除して解消（想定内の事象）
    - 公開鍵`authorized_keys`への追記・パスワードなしsudo設定(`/etc/sudoers.d/ntakao-nopasswd`)
      とも、ユーザー自身が作業PC側のPowerShellから`ssh`/`ssh -t`でパスワード認証ログインする形で
      実施（Claude Code側でユーザーのログインパスワードを扱わない運用とした）。鍵認証・
      パスワードなしsudoとも動作確認済み
  - [x] DC-6-6-4: `racecapture_streaming_install_intel.sh`を実行し、`racecapture`・
        `video-streamer`のインストールを再確認（DC-6-3相当の手順） ※完了
    - `~/Desktop`は事前に`mkdir -p`しておいたため、DC-6-3で発生した`video-config.ini`生成失敗
      (exit 2)は今回発生せず。`/var/lib/AccountsService/users/ntakao`不在によるsed失敗のみ
      再発したが、これはDC-6-3同様に非致命的（キオスク自動起動設定の一部のみ影響、
      racecapture/video-streamer本体のインストールには無関係）
    - `dpkg -l`で`racecapture`(2.18.0)・`video-streamer`(0.4.0)とも`ii`(正常インストール)を
      確認済み
  - [x] DC-6-6-5: USBカメラ・ESP32-C3を接続し、`video-streamer`のVAAPI動作
        （`file_h264_enc`エレメント作成、`LD_PRELOAD`要否含む）を再確認（DC-6-4相当の手順） ※完了
    - USBカメラ(BUFFALO BSWHD06M→`/dev/video0`)・ESP32-C3(→`/dev/ttyACM0`)とも、EliteDesk本体への
      OS再インストールをまたいで接続されたままだったため物理再接続は不要だった
    - `vainfo`パッケージ自体は`racecapture_streaming_install_intel.sh`の対象外で未導入だったため
      追加導入（`intel-media-va-driver-non-free`/`gstreamer1.0-vaapi`/`gstreamer1.0-tools`は
      スクリプトにより導入済み）。`vainfo --display drm --device /dev/dri/renderD128`で
      `iHD_drv_video.so`(Intel iHD driver, VA-API 1.14)ロード・H.264 EncSlice等を確認
    - `video-streamer`本体（`/opt/video-streamer/video-streamer`）をDC-6-4と同じ
      `LD_PRELOAD=.../{libstdc++.so.6,libva.so.2,libva-drm.so.2,libva-x11.so.2}`付きで起動した
      ところ、`va_openDriver() returns 0`でVAAPI初期化に成功（GLIBCXXバージョン不整合エラーは
      再発せず）。**Ubuntu 22.04環境でも同じ`LD_PRELOAD`回避策が有効であることを確認**
    - その後`Could not open X display for reading`で失敗するのはDC-5-2/DC-6-4で判明済みの
      仕様通り（race_captureのGUI描画＝X11セッションが必須なため、単体起動では想定内のエラー）
  - [x] DC-6-6-6: `race_capture`アプリを起動し、`No matching FB config found`が
        Ubuntu 22.04世代のMesa/Xorgでも再発するか検証（DC-6-5相当の手順。ここでOKなら
        ダウングレード方針の有効性が実証される） ※完了
    - DC-6-6-5と同様`sudo X :1`で物理モニター非接続のままXorgを起動（`xinit`パッケージは
      未導入だが`/usr/bin/X`は`xserver-xorg-core`に同梱済みで起動可能）。`glxinfo`で
      `direct rendering: Yes`・OpenGL 4.6・Mesa 23.2.1(Intel UHD Graphics 630)・
      GLXFBConfigs 1176件を確認
    - 🎉 **確定：`DISPLAY=:1 /opt/racecapture/race_capture`を実行したところ、DC-5-2/DC-6-5で
      発生していた`No matching FB config found`/`Couldn't find matching GLX visual`は
      **再発せず**、`[INFO] [GL] NPOT texture support is available`でGLウィンドウ生成に成功、
      `[INFO] [Base] Start application main loop`でメインループへ到達した。これにより
      **「Ubuntu 22.04 LTSへのダウングレードでrace_capture配布バイナリのFBConfigクラッシュが
      解消する」というDC-6全体の方針の有効性が実証された**
    - 初回起動時は`FileNotFoundError: .../.config/racecapture`（設定ディレクトリ未作成）で
      即終了したが、これはFBConfig問題とは無関係の別問題。`mkdir -p ~/.config/racecapture`で
      解消し、以降はESP32-C3(`/dev/ttyACM0`)への接続試行・データストア初期化・セッション記録
      開始まで進み、20秒のタイムアウトで正常終了（`exiting mainloop and closing`）するまで
      安定して動作し続けた
    - なお`xsel`/`xclip`未導入によるクリップボード機能の警告が出ているが、これも動作の
      本質には影響しない軽微な問題（クリップボード機能が使えないだけ）
  - [x] DC-6-6-7: 上記が解消した場合、ダッシュ表示＋`ximagesrc`経由の映像データ焼き込みが
        実際に一連の流れとして動作するか最終確認（DC-5-2/DC-6全体の元々の目的の達成確認） ※完了、達成
    - DC-6-6-6で起動したままのXorg(`:1`)上で、`race_capture --size=1920x1080`をバックグラウンド
      永続起動（`nohup`）。続けて`video-streamer`を`start-video-streamer.sh -w 1`（DC-6-6-5と
      同じ`LD_PRELOAD`付き、`DISPLAY=:1`）で起動したところ、`ximagesrc`の
      `Could not open X display for reading`は再発せず、race_captureのウィンドウを正しく
      画面キャプチャできていることを確認
    - ⚠️ 新たな軽微な問題を発見・解消：オーディオキャプチャが`Recording open error on device
      'hw:1,0': No such file or directory`で失敗しパイプラインが再起動ループしていた。原因は
      `racecapture_streaming_install_intel.sh`が`ntakao`ユーザーを`audio`グループに追加して
      おらず、USBカメラ内蔵マイク(`/dev/snd/pcmC1D0c`、`root:audio`権限)にアクセスできな
      かったこと。`sudo adduser ntakao audio`で解消したため、**インストールスクリプト自体に
      `audio`グループ追加を追記**（`racecapture_streaming_install_intel.sh`）し、今後の
      再インストールでも同じ問題が起きないようにした
    - オーディオ問題解消後、パイプラインは`READY→PAUSED→PLAYING`まで正常に到達。唯一残る
      エラーは`video-config.ini`の`streaming_url`がインストール時のダミー値
      (`rtmp://a.rtmp.youtube.com/live2/<streaming key>`)のままのため`Could not connect to
      RTMP stream`で失敗する点のみ（未設定の配信キーが原因の想定内のエラーで、ローカル録画側
      には影響しない別経路と判明）
    - 🎉 **確定：`~/Videos/<timestamp>/video_*.mp4`に実際にmp4動画ファイルが生成され続けている
      ことを確認**（1ファイルあたり約8万バイト、`file`コマンドで正常なISO Media/MP4と確認）。
      `gst-launch-1.0`で1本のmp4から静止フレームを抽出しダウンロードして目視確認したところ、
      **race_captureのGUI画面（ようこそ画面、ESP32-C3デバイス名・緑の接続ステータスドット
      表示込み）がそのまま録画データとして焼き込まれていることを画像で確認できた**。これにより
      「ダッシュ表示＋映像データ焼き込み」というDC-5-2/DC-6全体の元々の目的が
      **Intel機(EliteDesk 800 G3)+Ubuntu 22.04 LTS環境で最終的に達成された**
    - なお実際のYouTube等へのライブ配信(RTMP)自体は今回未検証（ダミーURLのまま）。配信機能を
      使う場合は実際の配信キーを`video-config.ini`の`streaming_url`に設定すれば動作する見込み
      だが、これは車載本番導入時に別途確認が必要
    - 検証終了後、確認用に起動していた`race_capture`・`video-streamer`・Xorg(`:1`)は停止し、
      検証中に大量生成されたテスト録画ファイル(`~/Videos`配下、100件超の短い断片)は削除して
      クリーンアップ済み

---

## DC-7: 車載本番導入に向けた残タスク ※DC-7-1・DC-7-2完了、DC-7-3〜4は未着手
- [x] DC-7-1: ratpoisonによるキオスク自動起動（電源投入だけで`race_capture`+`video-streamer`が
      無人で起動するか）を検証 ※完了、達成
  - `racecapture_streaming_install_intel.sh`が用意する`.ratpoisonrc`（race_capture/
    video-streamer自動起動）・`/usr/share/xsessions/racecapture.desktop`（ratpoisonセッション
    定義）に加え、以下2点が不足していたため追加設定した：
    1. **GDM3の自動ログイン設定が未設定**：`/etc/gdm3/custom.conf`の`AutomaticLoginEnable`/
       `AutomaticLogin`はコメントアウトされたままだった（ユーザー承認を得た上で有効化）。
       これがないとログイン画面で止まり、AccountsServiceのSession設定だけでは自動起動しない
    2. **AccountsServiceのユーザー設定ファイルが未生成**：DC-6-3で判明済みの通り
       `/var/lib/AccountsService/users/$USER`が新規インストール直後は存在せず、公式スクリプトの
       `sed`コマンドが失敗する（非致命的だが放置されていた）。`sudo tee`で直接生成する方式に
       修正し、`Session=racecapture`/`XSession=racecapture`を設定
    - 🎉 **上記2点を設定してリブートしたところ、電源投入→GDM自動ログイン→ratpoisonセッション
      →`race_capture`+`video-streamer`の自動起動が完全に無人で成功することを確認**
      （`ps aux`でプロセス起動を確認、`gst-launch-1.0`のライブスクリーンショットでrace_capture
      のウェルカム画面がクリーンに表示されていることも視覚的に確認）
    - ⚠️ 新たな軽微な問題を発見・解消：初回起動時のみ、GNOME keyringの「Choose password for
      new keyring」ダイアログが表示された。原因はrace_captureが認証情報保存にsecretstorage/
      D-Bus Secret Serviceを使っており、自動ログイン(パスワードなし)ではキーリング自動アンロック
      用のパスワードが得られないため。`xdotool`を導入し、パスワード欄を空のままEnter
      （→確認ダイアログ「Store passwords unencrypted?」も空パスワードのままEnter）で解消。
      **2回目のリブートで検証したところ、このダイアログは再発せず**（一度空パスワードの
      「Default」キーリングを作成すれば以降は自動アンロックされる）、`race_capture`の
      ウェルカム画面がクリーンに表示され続けることを確認した。video-streamer側もPLAYING状態に
      到達し、mp4動画ファイルが継続生成されることを確認
    - 上記2つの恒久対応（GDM自動ログイン設定・AccountsServiceファイル生成方式の修正）は
      `racecapture_streaming_install_intel.sh`に反映済み。ただしkeyring初期化は対話的操作
      （xdotoolでのGUI操作）が必要なため自動化しておらず、スクリプル末尾に手順を注記するに留めた
    - 検証終了後、確認用に起動していた`race_capture`・`video-streamer`は停止し、検証中に生成
      されたテスト録画ファイルは削除してクリーンアップ済み。GDM/Xorg/ratpoisonセッション自体は
      稼働させたまま（次回電源を入れ直せば同じ動作をするため、あえてログアウトはしていない）
  - ⚠️ **追記(ユーザーによる実機モニター+マウス接続確認で発覚)**：物理モニター＋マウスを
    接続して実際にrace_captureのボタンをクリックしようとしたところ、**カーソルは表示・移動する
    がクリックが反応しない**という問題が発生。切り分け調査の結果：
    1. `xinput list`でマウスの認識状況を確認したところ、当初USB接続が不安定で物理マウス自体が
       Xに認識されていなかった（`Virtual core pointer`のみで実デバイスがスレーブとして
       存在しない状態）。USBハブ経由で再接続したところ`Logitech USB Laser Mouse`が正しく
       スレーブポインタとして認識された
    2. `xinput test <id>`でマウスの生イベントをリアルタイム監視したところ、移動(`motion`)・
       左右クリック(`button press 1`/`3`)とも**Xサーバーレベルでは正常に検出されていた**
       （＝マウス〜カーネル〜Xサーバーの入力経路自体は問題なし）
    3. `xwininfo -root -tree`でウィンドウツリーを確認したが、RaceCaptureウィンドウ
       (`0xe00008`)に重なる怪しいオーバーレイウィンドウは`IsUnMapped`（非表示）であり
       クリックを奪う原因ではなかった
    4. `ratpoison -c windows`で`0*RaceCapture`（`*`はフォーカスありを示す）を確認でき、
       ウィンドウフォーカス自体は正しくRaceCaptureに当たっていた
    5. race_captureプロセスを一度再起動したところクリックが反応するようになった
    - 🎉 **再度リブートし、本来のキオスク自動起動フロー（電源投入→GDM自動ログイン→ratpoison→
      race_capture自動起動）経由で改めて検証したところ、`ratpoison -c windows`のフォーカスも
      正常、実際のマウスクリックも正常に反応することをユーザーに確認してもらえた**。これにより
      車載本番で想定される「電源投入→自動起動」というフロー自体に問題はなく、今回の不具合は
      **主にマウスのUSB接続不安定（ハブ経由の接触不良等）が原因だった可能性が高い**と判断
    - 車載本番導入時の留意点として記録：もし同様に「カーソルは動くがクリックが効かない」
      症状が再発した場合は、(a)`xinput list`で物理マウスがスレーブポインタとして認識されて
      いるか、(b)`xinput test <id>`でクリックイベントがXサーバーに届いているか、
      (c)`ratpoison -c windows`でRaceCaptureウィンドウにフォーカス(`*`)が当たっているか、
      の順に切り分けるとよい
- [x] DC-7-2: 実際のRTMPライブ配信（YouTube等）が動作するか検証 ※方針(b)ローカルRTMPサーバーで完了、重大な副次バグを発見・解消
  - `video-config.ini`の`streaming_url`はインストール時のダミー値のまま。DC-6-6-7/DC-7-1の
    どちらの検証でもRTMP出力自体は`Could not connect to RTMP stream`で失敗し続けている
    （ローカル録画には影響しない別経路と判明済み）
  - 🔴🎉 **重大発見・解消：video-streamerのRTMP接続失敗リトライで、ログファイルが際限なく肥大化し
    ディスクを使い果たす問題**。DC-7-1のキオスク自動起動テスト後、`streaming_url`がダミー値の
    まま約2時間放置していたところ、`video-streamer`が数秒おきにRTMP接続失敗→パイプライン
    再構築のリトライを繰り返し、単一のログファイル(`~/logs/video-streamer_*.log`)が**45GBまで
    肥大化し、ディスク(57GB)を100%使い果たしていた**ことが判明（`df -h`で発覚）。車載本番で
    配信設定をせずに長時間・数日運用した場合、同じ理屈でディスクフルとなりローカル録画も
    停止し、システムが不安定になりうる重大なリスクと判断
    - 対応：`video-streamer`プロセスを停止し45GBのログファイルを削除してディスクを復旧
      （19%使用まで回復）。恒久対策として`/etc/logrotate.d/racecapture-dashcam`
      （`~/logs/*.log`を50MBごと・2世代までローテーション、`su`ディレクティブで所有者権限
      指定）と`/etc/cron.d/racecapture-dashcam-logrotate`（1分間隔でlogrotate実行、通常の
      1日1回では今回のペース(2時間で45GB)に対応できないため高頻度化）を実機に設定し、
      dry-run(`logrotate -v`)で正常動作を確認済み
    - `racecapture_streaming_install_intel.sh`にも同じlogrotate/cron設定を追加し、今後の
      再インストールでも自動的にディスクフル対策が組み込まれるようにした
  - ユーザーと相談の上、方針(b)（ローカルRTMPサーバーでの疎通確認、配信キー不要）で実施
  - `nginx`+`libnginx-mod-rtmp`（Ubuntu 22.04リポジトリから導入可能と確認済み）を一時的に
    導入し、`nginx.conf`末尾に最小構成の`rtmp { server { listen 1935; application live
    { live on; record off; } } }`を追記。`nginx -t`で構文OK、`systemctl restart nginx`
    （初回`start`ではポート1935がリッスンされず、`restart`が必要だった点に注意）で
    ポート1935が正常にリッスンされることを確認
  - `video-config.ini`の`streaming_url`を一時的に`rtmp://127.0.0.1/live/dc7test`へ変更
    （変更前に`.bak`でバックアップ）し、`video-streamer`を起動したところ、DC-6-6-7/DC-7-1で
    見られた`Could not connect to RTMP stream`エラーは**発生せず**、パイプラインが
    `READY→PAUSED→PLAYING`のまま継続動作。`ss -tn`で`127.0.0.1:1935`への
    **ESTABLISHED接続を確認**し、video-streamerが実際にRTMPストリームを送信し続けている
    ことを実証した
  - 🎉 **確定：RTMP出力パイプライン自体は正常に機能する**。これまでの失敗は単に
    `streaming_url`がダミー値（存在しない配信サーバー）だったことが原因であり、
    video-streamer側のRTMP実装自体には問題がないことが判明した
  - 検証後、`video-config.ini`を元のダミー値に復元、`nginx`は停止・`purge`でアンインストール、
    テスト録画ファイルも削除してクリーンアップ済み
  - 実際のYouTube Live等への本番配信自体（配信キーを使った疎通確認）は未実施のまま
    （ユーザーが配信キーを用意した際に別途確認）
- [ ] DC-7-3: 軽量な車載向け機材（市販小型N100ミニPC/SBC/Mini-ITX裸基板等）でも、今回EliteDesk
      (Intel Core i5, Mesa iris系)で確立した「Ubuntu 22.04 LTS＋本インストールスクリプト」方針が
      通用するか検証 ※未着手、新規ハードウェアの入手が前提
  - EliteDesk自体は約1.2kgと車載搭載には重量面で不利なため、軽量機材での再現性確認が必要
  - 候補機材がUbuntu 24.04専用（22.04非対応）でないかの事前確認も必要
  - DASHCAM_STREAMING_RESEARCH.md 5章の候補一覧（N100ミニPC/UP 7000/ODROID-H4/
    Mini-ITX裸基板等）を参照
- [ ] DC-7-4: 車載電源の保護回路との統合 ※未着手、ハードウェア領域につき友人と要相談
  - ARCHITECTURE.md Phase 4で計画済みの車載電源保護回路（本体RaceCapture/ESP32側）とは別に、
    ダッシュカムPC側の電源設計（イグニッション連動シャットダウン等、走行中の急な電源断で
    ファイルシステムが壊れないようにする対策を含む）の検討が必要

---

## DC-8: ライブテレメトリー配信（podium.live）の動作確認 ※完了（ユーザーによる事前検証）
- [x] DC-8-1: スマートフォン版RaceCaptureアプリの「Send Telemetry」機能を使い、PC版
      PodiumLiveでリアルタイムにモニターできることを確認 ※本チャット上での作業ではなく、
      ユーザーが別途スマートフォンアプリで動作確認済み。DC-5/DC-6で確認できた
      「ローカルでのダッシュ表示・映像データ焼き込み」（`race_capture`+`video-streamer`の
      連携）とは独立した経路（`race_capture`アプリ単体のクラウド中継機能）であり、
      RCPプロトコル→podium.liveクラウド中継→PodiumLive監視、という一連の流れが
      実機で機能することは**この時点ですでに実証済み**とみなしてよい。DC-9以降で
      Raspberry Pi/ROCK 5B上で改めて検証する場合も、このpodium.live側の仕組み自体を
      疑う必要はなく、`race_capture`アプリが各ボード上で正常に動作するかどうかの
      確認に専念してよい

---

## DC-9: ROCK 5B（Rockchip RK3588、ARM）移行の検討・計画 ※検討完了、実機検証は未着手
DC-7-3（軽量な車載向け機材での再検証）の代替候補として、x86の軽量SBC
（LattePanda等）とARM系SBC（Rockchip RK3588搭載機）を比較検討した結果、
**コスト面で明確に有利なRadxa ROCK 5Bへの移行**を検討・決定した。判断の詳細な経緯・
比較・トレードオフ、および電源回路設計に関わる仕様は、友人（電源回路設計担当）への
共有レポートとして`DASHCAM_ROCK5B_REPORT.md`にまとめてある（本タスクの補足資料と
兼用）。

> ⚠️ **2026-08-15追記・最優先事項**：「配信用ダッシュ」と「走行中表示用ダッシュ」を
> 分離する構想の実現可否が、DC-9-1-b〜d（race_captureアプリの2インスタンス同時起動＋
> 別出力＋別レイアウト検証、シリアル共有用fan-outブリッジデーモンの試作、CPU/GPU負荷実測）
> にかかっていることが判明した。ROCK 5B・Raspberry Pi・EliteDesk問わず、何か具体的な
> 作業（GPU描画確認・エンコーダ自作等）に着手する前に、まずDC-9-1-b〜dを最優先で
> 確認すること。背景・調査結果は`DASHCAM_STREAMING_RESEARCH.md`8章参照。

- [ ] 🔴 **DC-9-1: 【最優先】手元のRaspberry Pi単体で、自作ESP32ファームウェア＋`race_capture`
      アプリの接続・動作を確認する（外部モニター使用、追加購入なしで着手可能）**
      ⚠️ **ROCK 5B・Raspberry Pi問わず、何か具体的な作業に着手する前に必ずこのタスクの
      (b)〜(d)を最優先で確認すること**（2026-08-15、ユーザーからの強い指示）。詳細な調査結果・
      背景は`DASHCAM_STREAMING_RESEARCH.md`8章参照。
      🔵 **(b)〜(d)はEliteDesk（x86、DC-6-6-7で動作実績あり、次回学校からの帰宅後に検証予定）
      でも先行して着手できる**。Kivy/pyserialの挙動に依存する部分（マルチプロセス化・
      ブリッジデーモンの設計）はアーキテクチャ非依存。ただし(d)のCPU/GPU負荷の絶対値は
      Intel UHD 630とMali G610で特性が異なるためROCK 5Bへ転用不可、ロジック検証と
      割り切ること。EliteDesk側の注意点は(b)末尾を参照

      > 📋 **次回（2026-08-18以降）EliteDeskで再開する際の作業手順（上から順に）**：
      > 1. `dashcam-test.local`へSSH接続（鍵`~/.ssh/amdpc_dashcam_ed25519`、ユーザー`ntakao`、
      >    `DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority`）、`ps aux`で現状確認
      >    （race_captureは実ポート直結・1インスタンスのみの状態で残しているはず）
      > 2. **(b)の検証**：2つ目のXorgプロセスを別出力（DP-3）向けに起動し、1GPUで2つの
      >    Xorgプロセスが共存できるか確認する（DRMマスター競合の懸念、未検証）。競合が
      >    起きて共存できない場合は、Xorg1プロセス＋Zaphodモード（`:0.0`/`:0.1`の独立
      >    スクリーン）に切り替えて再検証する
      > 3. **(c)の改修**：`serial_fanout_bridge.py`を、ブリッジ自体が唯一のRCPクライアント
      >    として`getStatus`等を定期ポーリング送信し、応答を全consumerへブロードキャストする
      >    設計に書き換える。各インスタンスが仮想ポートへ書き込んでくる自分自身のポーリング
      >    コマンドは実ポートへは転送せず握りつぶす。改修後、2インスタンスがそれぞれ正常に
      >    データを受信できるか実機確認する
      > 4. 検証後は必ず実機を元の直結構成（ブリッジ停止、race_capture実ポート直結・
      >    1インスタンス）に戻してからセッションを終える
  - [ ] DC-9-1-a: 基本動作確認（ESP32ファームウェアとrace_captureアプリ1インスタンスの
        接続・ダッシュ表示）
  - [ ] 🔴 DC-9-1-b: **【最重要確認事項】race_captureアプリを2プロセス同時起動し、それぞれ
        別出力（別モニタ/別ディスプレイ）・別ゲージレイアウトで動作させられるか検証する**。
        「配信用ダッシュ」と「走行中表示用ダッシュ」を分離できるかどうかの構想全体を
        左右する生命線。確認すべき点（`DASHCAM_STREAMING_RESEARCH.md`8.3節に詳細）：
        1. Kivyアプリの複数プロセス起動自体は可能（Kivyの既知の制約、1プロセス1ウィンドウ）。
           `DISPLAY`環境変数や`Config`のウィンドウ位置設定で別出力に配置できるか
        2. race_captureのゲージレイアウト設定ファイルの保存先を2インスタンスで分離できるか
           （`KIVY_HOME`環境変数、または独自設定パス`~/.config/racecapture`の指定手段）
        3. 🔵 【訂正】race_captureのソースコードは**このリポジトリの`reference/RaceCapture_App`
           にgit submoduleとして既にクローン済み**（実体は`ryandoherty/RaceCapture_App`
           フォーク、公式`autosportlabs/RaceCapture_App`は非公開化済みだがこちらは現役）。
           詰まった場合はソースを読んで確認・改造できる。`main.py`の`-p`/`--port`引数で
           シリアルポートを明示指定可能、`user_data_dir`は`KIVY_HOME`環境変数で分離できる
           見込みも実装から確認済み。詳細は`DASHCAM_STREAMING_RESEARCH.md`8.3節参照
        - ⚠️ **EliteDeskでの実施時の注意点**：背面に**DisplayPort×2ポート標準搭載**
          （DC-6-1で判明済み）なので2系統独立出力の検証環境として使えるが、DC-2で
          「DP→D-Sub変換アダプター・VGA直結いずれもUbuntu起動直後に信号が消える」問題が
          未解決のまま保留中。物理モニター表示にこだわらなければ、DC-6-6-6/DC-6-6-7と
          同様に物理モニター非接続のままEDID偽装でXサーバーを2つ（`:1`/`:2`等）起動する
          方式で動作確認自体は可能な見込み
        - 🔴 **【2026-08-17追記】EliteDesk実機検証でratpoisonのタイル配置により単純な位置
          指定は機能しないと判明**：Kivy `config.ini`の`position=custom`設定は無視され、
          2インスタンス目も1インスタンス目と同じ座標`(0,0)`に重なって表示された。
          🔵 **【同日中に方針を再訂正】最終的に採用する方式は「Xvfb+VNC」ではなく
          「ダミーHDMIプラグ（EDID偽装）＋出力ごとに別Xサーバー」に確定**：
          ROCK 5B本番機はWi-Fi/Bluetoothモジュール非搭載（追加購入が必要）なため、
          無線VNC前提のXvfb+x11vnc案は本番運用に不向きと判断。代わりに、
          ①走行中表示用インスタンスは実出力（例:HDMI-1）＋Xサーバー#1(`:0`)、
          ②配信用インスタンスは別出力（例:HDMI-2）＋Xサーバー#2(`:1`)、という
          **出力ごとに独立したXサーバーを割り当てる構成**にする。HDMI-2には普段
          ダミープラグ（EDID偽装アダプタ）を挿しておき、GPUに「モニター接続中」と
          誤認させて常時レンダリングを継続させる（`video-streamer`の`ximagesrc`
          キャプチャは物理モニターの有無に関係なく機能する）。ゲージレイアウトを
          編集したい時はダミープラグを実モニター（＋USBマウス/キーボード）に
          差し替えるだけで、アプリの再起動もネットワーク接続も不要にその場で
          操作できる。ユーザーが用意した持ち運び可能なポータブルディスプレイを
          この用途に使う想定。副次効果として、**出力ごとに別Xサーバーなので
          ratpoisonのタイル配置問題（1つのWMが複数出力を跨いで管理する構成に
          起因）自体が発生しなくなる**（各Xサーバーは自分の担当する1出力に
          1インスタンスしか扱わないため、ウィンドウ配置ロジックが本質的に不要）。
          EDID偽装によるXサーバー起動自体はDC-6-6-6/DC-6-6-7で実績あり。
          詳細は`DASHCAM_STREAMING_RESEARCH.md`8.3.5節参照
          - 🔵 **【2026-08-17追記・要検証】「race_captureプロセス自体を1つにまとめて表示だけ
            分割する」案はユーザーから提案されたが、Kivyの「1プロセス=1ウィンドウ」制約
            （フレームワークレベル、8.3節既出）により実現不可と判断し不採用。またPythonの
            GILにより1プロセス化はむしろマルチコア活用の妨げになる（2プロセスに分けて
            `taskset`で別コアに固定する方がRK3588のようなマルチコアARMチップには適する）
            という整理をした。GPU描画負荷自体は「プロセス数」ではなく「独立レイアウト数×
            解像度」で決まるため、2プロセス化によるGPU負荷増は無いという理解。ただし
            **2つの独立したXorgプロセスが1GPUで共存できるか（DRMマスター競合の懸念）は
            未検証**なので、次回EliteDeskで最初に確認すること。もしDRM競合で共存できない
            場合は、Xorgプロセスは1つのまま「Zaphodモード」（`xorg.conf`で`:0.0`/`:0.1`の
            独立スクリーンを定義する昔ながらのマルチヘッド構成）に切り替える。この場合も
            GPU負荷・ratpoison問題回避の効果は変わらない
  - [ ] 🔴 DC-9-1-c: **ESP32実機とのUSBシリアル接続を2インスタンスで共有するための
        fan-outブリッジデーモンを試作・検証する**。`reference/RaceCapture_App`のソース確認
        （`SerialConnection.open()`）により、`pyserial`の素朴な`serial.Serial()`呼び出しの
        みでOSレベル排他ロック（`TIOCEXCL`等）が一切なく、常時ストリーム読み取りループを
        回す設計と判明。2インスタンス同時接続でメッセージが分断・破損する可能性が高いと
        実装レベルで裏付けられた。
        - 🔴 **【訂正】単純な`socat`によるポート複製では解決しない**：`socat`の標準的な
          複製構成（`TCP-LISTEN,fork`等）は「1つのソースのデータを複数の購読者で奪い合う」
          形になり、シリアル直結と同じ分断問題が起きることが追加調査で判明した
        - ✅ **正しい設計方針：GPSデバイス用デーモン`gpsd`と同じfan-out方式を自作する**。
          ①専用のブリッジプロセス（Python数十行程度の規模）がESP32実機のシリアルポートを
          唯一読み取り、②受信した行を複数の仮想シリアルポート（`socat PTY,link=/dev/ttyV0`
          等で作成）へ複製して書き込み、③各race_captureインスタンスは`--port /dev/ttyV0`
          `--port /dev/ttyV1`のように別々の仮想ポートを読む。書き込み方向（race_capture→
          実機のコマンド送信）は今回の用途（表示のみ）では基本的に発生しない想定のため、
          まずは読み取り方向のfan-outのみ試作すればよい
        - 🔴 **【2026-08-17訂正】読み取り専用fan-outでは機能しないことがEliteDesk実機検証で
          判明**：`serial_fanout_bridge.py`（リポジトリ直下、プロトタイプ実装済み）で
          検証したところ、仮想ポート経由の受信が0バイトだった。原因はRCPプロトコルが
          race_capture側から約1Hzで`getStatus`等をポーリング送信し、ESP32が応答する
          pull型だったため（`HANDOFF.md`参照）。読み取り専用ブリッジでは誰もコマンドを
          送らずESP32が沈黙する。**正しい設計：ブリッジ自体が唯一のRCPクライアントとして
          定期ポーリングを送信し、応答を全consumerへブロードキャストする。各インスタンスが
          仮想ポートへ書き込んでくる自分自身のポーリングコマンドは実ポートへ転送せず
          握りつぶす**（実ポートへの書き込みをブリッジ1箇所に一元化）。次回はこの設計で
          `serial_fanout_bridge.py`を改修するところから再開する。
          なお、比較実験としてブリッジなしで2インスタンス同時直結を試したところ、
          2インスタンス目だけでなく本番側（1インスタンス目）にも`SampleMetaException`
          多発・`sqlite3.IntegrityError`によるセッション記録DB破損が波及することを確認し、
          fan-outブリッジが必須であることも実証された。詳細は
          `DASHCAM_STREAMING_RESEARCH.md`8.3.5節参照
  - [ ] 🔴 DC-9-1-d: **2インスタンス＋エンコード＋配信を同時実行した際のCPU/GPU負荷を実測
        する**。`DASHCAM_ROCK5B_SOFTWARE_HURDLES.md`4章のスペック検討は1インスタンス前提
        だったため、2インスタンス化での追加負荷が未検討のまま残っている。確認すべき点
        （`DASHCAM_STREAMING_RESEARCH.md`8.3(g)に詳細）：
        1. メモリ使用量（1インスタンス2GB未満の実績から、2インスタンスでも4GB未満の
           見込みだが実測で確認）
        2. CPUシングルコア負荷：`taskset`/cgroupsで2インスタンスをそれぞれ別のA76コアに
           固定した場合の効果（ROCK 5Bは4×A76＋4×A55のbig.LITTLE構成）
        3. 🔴 **最大の未知数**：Mali G610（Panfrost/Panthorドライバ）で2つの独立した
           EGL/OpenGLコンテキストを同時描画した際の実効性能。1インスタンスでの描画自体が
           未検証（DC-9-3）のため、実測以外に確認する方法がない
        4. 体感フレームレート・`mpstat -P ALL`でのコア別使用率
        - 対応策候補（負荷が厳しかった場合）：解像度/フレームレート低減、CPUガバナー
          `performance`固定、表示用ダッシュのレイアウトを配信用より軽量にする
- [x] DC-9-2: ROCK 5Bを購入する（USB PD対応電源、冷却ファン付きヒートシンク、
      eMMCモジュール16GB（OS起動用）、microSD（動画保存用・振動対策の物理固定を検討）を
      同時手配すること。M.2 NVMe SSDは消費電力・発熱の懸念から今回は見送り。
      詳細仕様は`DASHCAM_ROCK5B_REPORT.md`4章参照） ※完了。2026-08-13、本体8GBモデル・
      eMMCモジュールを注文（USB PD対応電源・冷却ファン付きヒートシンク・microSDも
      同時注文済み）。到着後の作業手順は`DASHCAM_ROCK5B_SETUP_GUIDE.md`にまとめた
- [x] DC-9-3: ROCK 5B上で`race_capture`アプリがMali GPU（Mali G610）上で正常に描画・
      起動できるか確認する（DC-5/DC-6で発生した`No matching FB config found`級の
      問題が再発しないか、が最大の技術的未知数） → 完了（2026-08-20、`task_phase4_breakdown.md`
      4-4-5-6として実施）。x86ルートのFBConfigクラッシュ（GLX/OpenGLデスクトップ経路）は
      再発せず、事前の仮説通りEGL/OpenGL ES系のレンダリング経路（Panfrostドライバ、
      Radxa製rk3588-bookwormリポジトリ由来）で正常動作した。ただし起動直後はGDM/Xorgとの
      DRMマスター競合で`Could not queue pageflip: -22`が多発する現象があり、GDM完全停止
      （`systemctl disable gdm`＋`multi-user.target`化）が解決に必須と判明。reboot後の
      コンソール自動ログイン→FBモード自動起動でpageflipエラーなしの安定動作を確認済み。
      さらに4-4-5-7-1にてESP32-C3実機とのRCP通信・セッション記録（ラップ集計継続）まで確認済み。
      詳細は`task_phase4_breakdown.md`4-4-5-6・4-4-5-7-1参照
- [ ] DC-9-4: `video-streamer`相当の機能（画面キャプチャ＋RKMPPハードウェアエンコード＋
      ローカルmp4保存）を、ffmpeg-rockchip（`nyanmisaka/ffmpeg-rockchip`）ベースで自作し、
      動作確認する（公式`video-streamer`はクローズドバイナリでVAAPI専用のため移植不可、
      同等機能の自作が必須。DC-9-3の完了が前提条件） ※以下へ分解済み（2026-08-20）。
      x86機での先行調査（DC-4/DC-5）時点では`video-streamer`はX11の`ximagesrc`で
      race_captureのダッシュ画面をキャプチャする方式だったが、ROCK 5Bは4-4-5-6で
      X11/GDMを止めFBモード（DRM/KMS直接描画）で動かす方針を既に確定・実装済みのため、
      「画面キャプチャの手段そのものが未確定」という、他の全サブタスクの設計を左右する
      調査事項が新たに生じている。このため画面キャプチャ方式の調査・選定
      （DC-9-4-1）を最優先・最初に置く。
  - [x] 🔴 DC-9-4-1: **【最優先】FBモード環境での画面キャプチャ方式を調査・選定する** → 完了
        （2026-08-20）。**`ffmpeg`標準の`kmsgrab`入力デバイスを採用に決定**。ROCK 5B実機
        （`rock-5b`、race_capture稼働中）でDebian標準の`ffmpeg`(7:5.1.9)をapt導入し、
        `sudo ffmpeg -f kmsgrab -device /dev/dri/card0 -i - -frames:v 1 -vf
        hwdownload,format=bgra -f image2 out.png`を実行したところ、race_captureの
        FBモード描画（1280x800、plane 57、DRMフォーマット`AR24`）を`drm_prime`フレーム
        として正しく取得できることを実機で確認した。取得したPNGを目視確認し、Speed/RPM/
        LapCount等のダッシュ画面が実際にキャプチャされていることも確認済み。
        - 検証中に判明した候補技術の比較：
          1. **kmsgrab（採用）**：`drm_prime`（DRMバッファのGEMハンドル）としてゼロコピー
             取得できるため、`hwmap`経由でRKMPPハードウェアエンコーダへそのまま渡せる
             見込みが高い（DC-9-4-3で検証）。ffmpeg標準機能で`ffmpeg-rockchip`にも
             当然含まれる。要件：root権限（CAP_SYS_ADMIN）でのプロセス実行が必須
             （非rootでは`No handle set on framebuffer`で失敗することを実機で確認済み）。
             DC-9-4-4（起動フローへの統合）で、録画プロセスをroot権限で動かす設計に
             する必要がある
          2. **DRM Writeback connector**：ROCK 5B実機に`card0-Writeback-1`が実在する
             ことを`/sys/class/drm/`で確認し、RK3588のkernel 6.1でwritebackが
             サポートされていることも実証できたが、既存ツール（ffmpeg/GStreamer）に
             標準対応する要素がなく、libdrmの低レベルAPIを直接叩く自作が必要。
             kmsgrabで目的を達成できたため今回は不採用（将来kmsgrabで問題が出た場合の
             代替候補として記録に残す）
          3. **`/dev/fb0`(fbdev)の定期読み出し**：DRMのfbdev互換レイヤーとして存在は
             確認した（1280x800、32bpp）が、CPUコピー主体でGPU/DRMバッファのゼロコピー
             恩恵がなく性能面でkmsgrabに劣るため不採用
          4. **v4l2loopbackへの書き込み**：単独の一次キャプチャ手段ではなく中間層。
             ffmpegがkmsgrab→hwmap→rkmppを直接パイプライン化できる見込みのため
             中間デバイスは不要と判断し不採用
          5. **race_capture本体を改造しGLテクスチャを`appsrc`経由でエンコーダへ渡す方式**：
             kmsgrabで目的を達成できたため、規模の大きいこの方式は不採用
        - ⚠️ 軽微な既知事項：キャプチャしたPNGにマウスカーソルの矢印が写り込んでいた
          （`-c graphics:show_cursor:0`でrace_capture側は非表示設定にしているにも
          関わらず）。原因未調査だが録画の可否には影響しない軽微な問題のため、
          気になる場合はDC-9-4-3以降で別途対応する
        - 検証で作成したテストファイル（`/tmp/kmstest.png`）は実機上・ローカルとも
          削除済み。apt導入した`ffmpeg`(Debian標準版)はDC-9-4-2で`ffmpeg-rockchip`へ
          置き換える前提のため実機に残したままにしている
  - [ ] DC-9-4-2: **RKMPPハードウェアエンコーダ単体の動作確認**。ffmpeg-rockchip
        （`nyanmisaka/ffmpeg-rockchip`）をROCK 5B上でビルドまたは導入し、適当な
        テスト映像（ダミー入力でよい）からH.264/H.265へのハードウェアエンコードが
        単体で動作することを確認する。DC-9-4-1とは独立して並行着手可能
  - [ ] DC-9-4-3: **キャプチャ→RKMPPエンコード→mp4保存の最小パイプラインを試作・
        動作確認する**。DC-9-4-1で選定した方式とDC-9-4-2で動作確認したエンコーダを
        つなぎ、最小構成（race_capture本体は未連動でよい）でmp4ファイルへの
        保存まで一気通貫で動くことを確認する
  - [ ] DC-9-4-4: **race_capture本体の起動フロー（`run_racecapture_rpi.sh`／FBモード
        自動起動）へ統合し、常駐化する**。race_capture起動と連動した録画プロセスの
        自動起動・停止、ログ・エラー時の扱いを整理する
  - [ ] DC-9-4-5: **実機での録画動作を検証する**（`task_phase4_breakdown.md`
        4-4-5-7-2に対応）。USBカメラ・ESP32-C3接続、race_captureでのダッシュ表示・
        RCP通信中に実際に録画が正常に行われるか、ファイルサイズ・フレームレート・
        CPU/GPU負荷（DC-9-1-dの負荷実測とも関連）を確認する
- [ ] DC-9-5: ある程度動作確認できた段階で、USBドングル型LTEモデム（データ専用SIM契約）を
      購入し、YouTube配信・セルラー通信を検証する（ローカルRTMPサーバーでの疎通確認を
      先に済ませ、最後にセルラー経由の実配信を確認する順序を想定）
- [ ] DC-9-6: 動作確認が取れた段階で、車載用モニター等の周辺機器を購入する
- [ ] DC-9-7: 友人によるロガー本体（電源保護回路含む、2026年9月中旬完成予定）の完成を
      待たず、検証用のESP32-C3代替機のまま実車に持ち込み、2週間程度の実運用テストを
      実施する（真夏〜初秋の高温環境は、連続エンコード時の熱設計・スロットリング挙動を
      検証する上で好条件と判断）

---

## DC-10: 2台目車両向け構成の検討（ROCK 4 SE、動画配信なし） ※検討中、未購入
ロードスター以外にもう1台、動画配信機能が不要な車両があり、そちらにはROCK 5Bとは
別の安価なボードを充てる方向で検討中。**両者の用途の違いを明確に区別しておく**：

- **ROCK 5B（Rockchip RK3588）**：ロードスター向け。`race_capture`（ダッシュ表示）＋
  `video-streamer`相当（画面キャプチャ＋RKMPPハードウェアエンコード＋ローカルmp4保存＋
  YouTube等へのライブ配信）**込みのフル構成**。DC-9で検討・計画中
- **ROCK 4 SE（Rockchip RK3399-T、4GBメモリ）**：2台目車両向け。動画配信・録画機能は
  不要で、`race_capture`によるダッシュ表示＋podium.live経由の**ライブテレメトリー配信の
  みの軽量構成**。カメラ接続なし、ハードウェアエンコード不要。USB-C PD（9-20V）対応かつ
  Raspberry Pi 4クラスの性能・安価（¥9,988、国内ショップ）という条件で選定した
  （購入先：https://shop.iothonpo.com/product/rock-4se/ )

- [ ] DC-10-1: ROCK 5B側でDC-9-3（`race_capture`アプリのMali GPU描画確認）が完了したら、
      その結果・回避策（Ubuntu バージョン、Panfrostドライバの明示的な有効化設定など）を
      記録した上でROCK 4 SEでも同様の確認を行う（Mali世代・SoC世代が異なる（G610/Valhall
      系 vs T860/Midgard系）ため、ROCK 5Bで解決してもそのまま通用するとは限らない点に注意。
      詳細な理由は本チャットの検討記録を参照）
- [ ] DC-10-2: ROCK 4 SEを購入する（USB-C PD対応電源を別途手配。詳細な周辺機材リストは
      DC-9-2のROCK 5B分と同様に検討する）
- [ ] DC-10-3: ライブテレメトリー配信（podium.live経由）のみの軽量構成での動作確認
      （DC-8で実証済みの経路をROCK 4 SE上で再確認）

---

*次のチャットでは「DC-9から進めて」のように指定すれば、このファイルと
`DASHCAM_ROCK5B_REPORT.md`（ROCK 5B移行の背景・仕様まとめ）を参照して作業を再開できる。
DC-7-3/DC-7-4（x86ルートでの軽量化・電源保護回路統合）はROCK 5B移行の検討によって
優先度を下げた状態。DC-8（ライブテレメトリー）はユーザー確認済みのため追加作業不要。
実際のYouTube Live等への本番RTMP配信（配信キーを使った疎通確認）はDC-7-2で
x86ルートでは未実施のまま残っているが、これもDC-9-5でROCK 5Bルートとして
改めて検証する想定。*
