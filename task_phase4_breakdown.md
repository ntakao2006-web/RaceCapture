# Phase 4 サブタスク分解（車載電源・保護回路の組込み & 筐体化）

> ARCHITECTURE.md「5. 開発ロードマップ」のPhase 4（4-1〜4-4）は粒度が粗いため、
> 実作業はこのファイルの単位（1チャット=1タスク）で進める。
> 完了したタスクはこのファイル内でチェックし、Phase全体が終わったらARCHITECTURE.mdへ
> 結論だけ転記してarchive/へ移動する運用（8章のルールに準拠）。

---

## 4-1〜4-3: 車載電源保護回路・CANバス終端・PCB化 ※保留

電気・回路系は友人へ一任済み（`hardware_interface_spec.md`参照）。友人側の設計・製作が進み、
実基板や確定仕様が揃った段階で改めて分解する。現時点ではサブタスク化しない。

---

## 4-4: ケース格納、Raspberry Pi車載ダッシュボードの固定

### 4-4-1: Raspberry Pi 4B/3BへのRaceCapture Appインストール ※完了
- [x] 4-4-1-1: Raspberry Pi 4Bへの初期セットアップ・RaceCapture App(v2.18.0)インストール → 完了。SSH公開鍵認証・NOPASSWD sudo設定、trixie向けパッケージ名差異（`libegl1-mesa`→`libegl1`）対応した非対話インストールスクリプトを使用。HDMIディスプレイ未接続のため起動確認は次回持ち越し（詳細は`ARCHITECTURE.md`4章参照）。
- [x] 4-4-1-2: Raspberry Pi 3B（`rc-dash-3b`）への同様のセットアップ・インストール → 完了。HDMIモニタ接続済み環境で起動確認まで実施。

### 4-4-2: 画面表示問題（黒画面）のデバッグ・解決 ※大幅改善したが未完了、次回続き
**現象**：`race_capture`プロセスはクラッシュせず安定動作（USB通信・DB・RCPAPI等は正常）しているが、
実際のディスプレイ出力はほぼ真っ黒。通知（Snackbar）だけは表示される。FBモード・X11モードいずれでも再現。

**これまでに確認・除外した原因**：
- ✅ 電源のアンダーボルテージ → スマホ用急速充電器(QC3.0)からPD/QC非対応の5V/2.1A固定出力充電器に交換し、`vcgencmd get_throttled`で通常時は解消を確認（ただし後述の通り高負荷時は再発）
- ✅ `libstdc++`のGLIBCXXバージョン不整合（trixie環境でのMesaドライバロード失敗）→ バンドル版`libstdc++.so.6`をシステム版へのシンボリックリンクに置換して解消
- ✅ DRM/KMS側の出力設定 → `crtc active=1`、コネクタ接続、プレーンへのフレームバッファ割り当てまですべて正常と確認済み（`/sys/kernel/debug/dri/0/state`で確認）
- △ `racecapture.kv`が`_internal`配下に存在しない → dpkgパッケージ・v2.16.1/v2.18.0いずれにも存在しないため、バージョン間のリグレッションではなく元々の仕様の可能性が高い（直接の原因ではなさそう）
- 🔴 **前回セッションの前提の誤りを訂正**：調査候補として挙げていた`reference/RaceCapture_App`（`ryandoherty`フォーク、Kivy 1.9系・`__version__="1.5.3"`）は、実機にインストールされているv2.18.0とは**別物**と判明。実機の`/opt/racecapture/_internal`を直接調査したところ`kivymd`（1.0.2）がバンドルされており、実際のUIはKivyMDベース。フォーク版ソースはUI描画ロジックの参考にはならない（RCPプロトコル仕様の参考としては引き続き有効、5-1-2の用途通り）。

**今回のセッションで新たに特定・修正した2つの実バグ（実機で描画が大幅改善することを確認済み）**：
1. **`~/.config/racecapture/prefs.json`の`general_prefs.preferences.full_screen_mode`が`0`（無効）のままだった**：アプリ自身のプリファレンス（純正アプリのPreferences画面にある「Full Screen Mode」トグルに相当）で、ウィンドウマネージャの無い素のKMS/DRM環境で非フルスクリーンモードのまま起動していた。あわせて`~/.config/racecapture/install_settings.cfg`の`RESOLUTION=800x480`（純正7インチタッチパネル向けのデフォルト値、このPiに繋がっているのは実際には1920x1080の一般HDMIモニタ）も整合していなかった。`full_screen_mode`を`1`に修正し、`~/.kivy/config.ini`の`[graphics]`セクション（`fullscreen`/`width`/`height`）も実モニタ解像度(1920x1080、`/sys/class/drm/card0-HDMI-A-1/modes`のEDID先頭＝preferredモードで確認済み)に合わせて修正した。
2. **`~/.kivy/config.ini`の`[graphics]`セクション`multisamples = 2`（アンチエイリアシング）が、Pi 3Bのレガシー世代GPU（VC4 V3D、`OpenGL renderer <VC4 V3D 2.1>`、GL 2.1相当のMesaドライバ）でまともに機能していなかった**：`multisamples = 0`に変更したところ、それまで全画面`RGBA(0,0,0,0)`（完全な透過）だった描画が、背景の単色矩形（`RGBA(18,18,18,255)`、ツールバー相当と見られる領域）についてはきちんと不透明で描画されるようになった。MSAA未対応/バグのあるレガシーGPUドライバでKivy(SDL2/EGL)のマルチサンプリングを要求すると、描画コマンドがサイレントに失われる（例外・エラーログなし）という典型的な既知パターンに合致する。

**上記2点を修正した状態でのDRM直接キャプチャ（`ffmpeg -f kmsgrab`）による確認結果**：
- 修正前：全画面のほぼ100%が`RGBA(0,0,0,0)`（完全透過）で、画面最下部24行のみ市松状の`(18,18,18,255)`ピクセルが存在（電源再投入・複数回の再現で完全に同一パターン、静的な要素と判明）
- 修正後（クリーンな自動起動フロー、tty1オートログイン経由での確認）：画面上部（ツールバー相当、高さ約24%）・画面最下部の両方に不透明な`(18,18,18,255)`の背景矩形が描画されるようになった。**ただし背景矩形以外の色は依然として一切存在しない**（`RGBA(0,0,0,0)`と`(18,18,18,255)`の2色のみ、フルHD画面全体をサンプリングして確認）。**つまり文字（ラベル）・アイコンの類は、背景が正しく描画されるようになった領域内でも依然として完全に非表示のまま**。これが次回に残る本丸の課題。
- MSAA無効化の効果が無い状態（`multisamples=2`のまま`full_screen_mode`だけ`1`にした場合）では、実解像度が意図せず1024x768へ変わり（EDID上の実際のpreferredモードは1920x1080のはずだが、アプリ内部で別途width/height設定の上書きが起きている可能性を示唆）、その状態では画面全体が完全に`RGBA(0,0,0,0)`（背景矩形すら描画されない、直前の食い違うテスト結果）になった。この「実解像度がアプリ側の何らかのロジックで上書きされる」現象自体は未解明。
- `KIVY_TEXT=pil`環境変数（Kivyのテキストレンダリングプロバイダをsdl2_ttfからPILへ切り替える定番の切り分け手段）を試したが、改善せず、むしろ背景矩形すら描画されない状態に悪化した。この手は筋が悪いと判断し、以後は試さない方針。
- 🔴 **重要な反例（ユーザーが物理モニタを直接撮影して発見）**：MSAA無効化の効果を確認していた最中、`ffmpeg -f kmsgrab`の単発スクリーンショットでは検出できなかったが、**物理モニタ上には実際に「Error reading configuration. Check your connection」という文字が読める状態で表示されていた**（ESP32側との通信不安定時に出る`alertPopup`系のダイアログと推測、`SampleMetaException`等のRCPAPIエラーと符合）。これは上記「文字・アイコンは一切描画されない」という結論を修正する必要があることを示す：**少なくともこの種のポップアップ/ダイアログでは文字が正常に描画されている**。単発のkmsgrabキャプチャは表示タイミングを取りこぼしていた可能性が高く（ポップアップは一時的にしか出ない）、次回は「1〜2秒間隔での連続キャプチャ」など時間方向の取りこぼし対策が必要。また、Popup（モーダルダイアログ）とScreen本体（Home/Dashboard等）とで描画経路・ウィジェットツリーが異なる可能性があり、**「メイン画面のコンテンツ領域だけが描画されない」という、より狭い範囲の問題である可能性**が新たに浮上した。

**電源アンダーボルテージについての重要な追加発見・暫定対応**：
調査中、`dmesg`で`hwmon1: Undervoltage detected!`が**現在進行形で10〜90秒間隔で頻発**しており、`[drm] Resetting GPU.`（GPUリセット）も実際に発生していることを確認した。「4-4-1完了後に5V/2.1A固定電源へ交換して通常時は解消済み」という従来の認識は誤りで、**ESP32実機を接続した通常運用（race_capture単体、X11/VNCなどの追加負荷なし）だけでも再発する**状態だった。暫定対応として`/boot/firmware/config.txt`にCPUクロックの制限(`arm_freq=800`、定格1.2GHz→800MHz)とBluetooth無効化(`dtoverlay=disable-bt`)を追記し、適用後60秒間の監視でアンダーボルテージ・GPUリセットが1件も発生しないことを確認した。**ただし、この電源問題の有無に関わらず上記の画面描画バグ（背景色は再現、透過/MSAA関連）は完全に同一のパターンで再現したため、電源問題と画面描画バグは無関係と判明**（当初「電源が原因で描画が壊れているのでは」という仮説を立てたが、これは誤りだった）。電源問題そのものは実車搭載前に要対応の別課題として残る：**5V/2.5A以上（できれば純正Raspberry Pi電源）への交換が本来の対策**、CPUクロック制限はあくまで暫定的な消費電力削減策。

**未解決・次回の調査候補（優先度順）**：
0. **最優先：連続キャプチャでポップアップ表示中の状態を捉え、上記の反例を掘り下げる**：`ffmpeg -f kmsgrab`を1〜2秒間隔で複数枚（例：15〜20枚）連続キャプチャし、文字が表示される瞬間（Popup/alertPopup表示中）を確実に捕捉する。捕捉できれば、①その時のツールバー・Home画面等メイン領域に文字/アイコンが出ているか（出ていなければ「Popupだけ別経路で正常」という仮説が濃厚）、②Popup自体のフォント・描画設定がメイン画面の各種Labelと何か違うか、を比較できる。ユーザーが物理モニタで実際に文字を目視できているため、次回はキャプチャ手法の見直しから着手するのが最も効率的。
1. **文字・アイコンが一切描画されない件の原因調査**：背景矩形の描画（Colorインストラクション+Rectangle）は直ったが、Label/MDIconの類（フォントアトラスのテクスチャサンプリングを伴う描画）がHome画面等では引き続き非表示に見える（上記0の通り、Popupでは表示されている可能性が高いため「一切」ではなく「特定の画面/ウィジェットのみ」の問題に絞られつつある）。`~/.kivy/config.ini`の`log_level`を`debug`にして`~/.kivy/logs/`の詳細ログを取得し、フォント/テクスチャ関連のエラー・警告が出ていないか確認するのが次の一手。
2. **実解像度がアプリ内部で上書きされる現象の解明**：`full_screen_mode=1`だけ設定し`multisamples`が2のままだった際、`~/.kivy/config.ini`で明示的に指定した1920x1080が反映されず1024x768（EDIDのpreferredモードではない値）で起動した事象があった。アプリ内部（PyInstallerでバンドルされ`.py`ソースが直接読めないため詳細不明）が独自に`Config.set('graphics','width'/'height', ...)`のような上書きを行っている可能性がある。
3. **実機バイナリの逆コンパイルという選択肢**：本プロジェクトでは過去に公式アプリ(Windows版)を`pyinstxtractor-ng` + `pydisasm`(xdis)で逆コンパイルしてプロトコル仕様を解析した実績がある（`HANDOFF.md`参照）。今回のRaspberry Pi版(`/opt/racecapture/race_capture`、ARM64 ELF・PyInstaller onedir)も同様の手法で逆コンパイルできれば、上記1・2の原因を推測ではなく実際のPythonソースから直接特定できる可能性が高い。時間はかかるが最も確実な次の一手候補。
4. KivyMD側の既知issue（背景色/canvas色指定が反映されないバグ報告が複数バージョンで存在）との関連を、実際のソース（逆コンパイルできれば）と突き合わせて確認する。

**実機（`rc-dash-3b`）に加えた変更点（次回セッション用の記録、いずれも変更前バックアップを同ディレクトリに`.bak_*`として保存済み）**：
- `~/.config/racecapture/prefs.json`：`general_prefs.preferences.full_screen_mode`を`0`→`1`
- `~/.kivy/config.ini`の`[graphics]`：`fullscreen`を`0`→`1`、`width`を`800`→`1920`、`height`を`600`→`1080`、`multisamples`を`2`→`0`
- `/boot/firmware/config.txt`：末尾に`arm_freq=800`（定格1.2GHzから暫定的に降格）・`dtoverlay=disable-bt`を追記（電源アンダーボルテージの暫定緩和策、上記参照）
- いずれも再起動後も維持される設定ファイルへの変更のため、次回セッションでも当該修正は引き継がれた状態から再開できる

**今回のセッション（4-4-2続き）で得た新知見**：

**1. 連続kmsgrabキャプチャ（1.5秒間隔×15枚）による確認結果**：
ESP32実機を接続しGPS/telemetryが正常に流れている「完全に正常な稼働状態」下でも、全フレームとも背景色2色（`RGBA(0,0,0,0)`と`(18,18,18,255)`）のみで、メイン画面（Home/Dashboard）のコンテンツは一切描画されていないことを確認した。つまりこの問題はESP32との通信状態（接続待ち/エラー/正常受信）に関わらず再現する、UI描画そのものの問題である。

**2. デバッグログ（`~/.kivy/config.ini`の`log_level=debug`）を有効化して調査**：
`~/racecapture.log`にフォント/テクスチャ関連の明示的なエラー・警告は一切出力されていなかった（`grep -i "font\|texture\|label\|glyph"`では通常のリソースパス登録ログのみ）。Text providerは`sdl2`（sdl2_ttf）。唯一の`[ERROR]`は`RaceCaptureApp:Error reading configuration: ('Timeout waiting for %s', 'canCfg')`（ESP32との再接続シーケンス中に発生、`toast()`で通知）のみで、これ以外に例外・Tracebackは通信断・再接続系統のもの2件のみ（描画系ではない）。

**3. 実機バイナリの逆コンパイルを実施（`pyinstxtractor-ng` + `xdis`のpydisasm、Windows版で過去実績のある手法をARM64 Linux版に適用）**：
- `rc-dash-3b`上にvenvを作成し`pip install pyinstxtractor-ng xdis`（インターネット疎通確認済み）、`/opt/racecapture/race_capture`（onedir、ARM64 ELF）から`pyinstxtractor-ng`でPYZアーカイブを展開。PYZ内に2606個の`.pyc`（Python 3.11向け）を確認。作業一式は`~/decompile_4-4-2/`に保存済み（`race_capture_extracted/`が展開結果、`main_disasm.txt`/`digitalgauge_disasm.txt`が逆アセンブル結果）。
- **ユーザーが実機目視した「Error reading configuration. Check your connection」のテキストは、`main.py`の`on_read_config_error`メソッド（逆アセンブル済み）から、実は**Popup（モーダルダイアログ）ではなく`kivymd.toast.toast()`（`kivymd/toast/kivytoast/kivytoast.py`、`Toast`クラスは`BaseDialog`＝`ModalView`系のサブクラス）で表示されていることが判明**。これはScreenManager配下の通常のScreen/Widgetツリーとは完全に別の、Window直下に追加されるオーバーレイ描画経路であり、「toastでは文字が見えるのにHome画面本体では見えない」という一見矛盾する目視結果を説明する。前回セッションで立てた「Popupとメイン画面で描画経路が違うのでは」という仮説の対象が、正確には「toast」だったと訂正。
- **最有力の新仮説**：ダッシュボードの数値ゲージ表示を担う`autosportlabs/uix/gauge/digitalgauge.py`の`DigitalGaugeElement`ウィジェット（`.kv`定義を`main_disasm.txt`より復元済み、`ScaledCompactLabel`で数値・チャンネル名・単位を表示）が、`StencilPush`/`StencilUse`/`StencilPop`（Kivyのcanvasクリッピング命令、OpenGLのstencilバッファを使用）でラベル群をクリッピングしている（`digitalgauge_disasm.txt`の1398〜1580行あたり）。Web検索により、**Raspberry PiのレガシーVC4/MesaドライバがOpenGL stencilバッファを正しくサポートせず`stencil buffer support missing, expect rendering errors`という既知の警告が出るケースがある**ことを確認した（[Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=254395)、[kivy/kivy#5511](https://github.com/kivy/kivy/issues/5511)）。stencilバッファが無効/0ビットの状態でStencilPush→StencilUseが実行されると、後続の描画命令（Label/MDIconのテクスチャ付き矩形）がクリップ領域外と判定されて完全に非表示になる、という典型的な故障パターンに合致する。背景の単色矩形（`SmoothRoundedRectangle`、Stencil命令を伴わない）は正常に描画され、Stencilクリッピングの内側にあるLabel群だけが非表示という今回の症状と矛盾なく整合する。
- 検証のため`MESA_DEBUG=1 LIBGL_DEBUG=verbose`環境変数を付けて再起動してみたが（ログは`~/racecapture_mesadebug.log`）、`Mesa: error: GL_INVALID_ENUM in glGetIntegerv(pname=GL_MAJOR_VERSION)`という別のエラーは出力されたものの、stencil関連の明示的な警告は出力されなかった（Kivy側のPython実装(`kivy/core/window/window_sdl2.pyc`)にも`kivy/config.pyc`のデフォルト設定にも`stencil`という文字列自体が存在せず、SDL_GL_SetAttribute等のstencilサイズ要求はCython実装(`.so`、今回は未解析)側にあると推測される）。stencilバッファの実際のビット数を直接確認するには、EGL/GLコンテキストを直接照会する検証スクリプトの作成、または`.so`レベルの追加調査が必要。

**実機（`rc-dash-3b`）に今回のセッションで加えた追加の変更点**：
- `~/.kivy/config.ini`：`log_level`を`info`→`debug`に変更（次回セッションでも有効なまま。ログが増えるため、調査が一段落したら`info`に戻すことを検討）
- `~/decompile_4-4-2/`：逆コンパイル作業一式（venv、展開済みPYZ、逆アセンブル結果）を保存。次回セッションもここから再開できる
- `~/capture_4-4-2/`：連続kmsgrabキャプチャの結果（15枚、全て背景2色のみ）を保存
- `~/racecapture.log` / `~/racecapture_mesadebug.log`：デバッグログ・Mesa詳細ログを保存

**未解決・次回の調査候補（優先度順、更新）**：
0. **最優先：stencilバッファ仮説の検証**。①EGL/GBM経由で実際に選択されているEGLConfigの`EGL_STENCIL_SIZE`を照会する小さなPython/ctypesスクリプトを書いて実測する、②Kivyの`window_sdl2`のCython実装（`.so`）を`objdump`等で調べてstencilサイズ要求箇所を特定する、③試しにOSやMesa側でstencilバッファを強制する設定（`MESA_GLES_VERSION_OVERRIDE`、EGL関連の環境変数等）がないか調べる。
1. 上記で確定困難な場合、`racecapture/views/dashboard/dashboardview.py`側で`DigitalGaugeElement`以外の一般的な`MDLabel`（Stencilを使わない箇所、例えばツールバーのタイトル等）が表示されているかどうかを別途連続キャプチャで確認し、「Stencil配下のLabelだけが非表示」なのか「全てのLabelが非表示」なのかを切り分ける（現状は判別できていない）。
2. 実解像度がアプリ内部で上書きされる現象（1024x768に固定される件）は今回未着手。逆コンパイル済みソース（`~/decompile_4-4-2/race_capture_extracted/`）から`Config.set('graphics', ...)`のような呼び出し箇所を探索する。
3. KivyMD側の既知issue（背景色/canvas色指定が反映されないバグ報告）との関連は、逆コンパイル済みソースと突き合わせてまだ未実施。

### 4-4-3: X11+VNCでの目視調査時の電源負荷問題 ※記録のみ・要注意
`Xorg` + `x11vnc` + `race_capture`を同時稼働させた状態で、`throttled=0x50005`（アンダーボルテージ再発）が発生し、
システムウォッチドッグ（1分タイムアウト）による強制リブートが発生した。改善後の電源（PD/QC非対応 5V/2.1A固定出力）でも、
この複合負荷には耐えられないことが判明。次回X11+VNCでの調査を行う場合は、より高出力な電源（5V/3A程度）を先に用意するか、
あるいはX11+VNCを使わない別の調査手法（ソースコード読解等）を優先する。

### 4-4-4: 筐体格納・固定 ※未着手
4-4-2の画面表示問題解決後に着手。
