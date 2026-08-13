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

### 4-4-2: 画面表示問題（黒画面）のデバッグ・解決 ※大幅改善したが未完了、次回続き（第5回セッションで根本原因を実証・ワークアラウンドも最小アプリでは実証済み、実機への適用のみ未達）
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

**stencilバッファ仮説の追加検証（`mesa-utils`の`eglinfo`が実機に導入済みと判明、これを使用）**：
`sudo EGL_PLATFORM=drm eglinfo`（結果は`/tmp/eglinfo_full.txt`、実機に保存済み）でGBMプラットフォームのEGL Configuration一覧を取得したところ、**このPi（Mesa 26.2.0、trixie backports）のVC4ドライバは実際にはstencil=8bitのConfigを複数提供している**ことを確認した（例：`0x03`, `0x06`, `0x09`, `0x0c`, `0x0f`, `0x12`。`0x06`はMSAA(ms=4)とstencil=8の両立configも存在）。これは「Web検索で見つけたRaspberry Pi Forums/kivy#5511の"stencil buffer support missing"という既知issue」が**現在のMesaバージョンでは解消済みの可能性がある**ことを意味し、当初の「ドライバがstencilを全くサポートしていない」という仮説はやや単純化しすぎだったと訂正する必要がある。
真の焦点は「ドライバがstencilを提供できるか」ではなく、**「KivyのSDL2ウィンドウ生成時に、実際にstencil対応のConfigが選択され使われているか」**に絞られる。これを直接確認するため`EGL_LOG_LEVEL=debug`環境変数を付けて再起動してみたが、`~/racecapture_egldebug.log`にはConfig選択に関するログ出力は得られなかった（Mesa側のEGL実装がこの環境変数によるConfig選択ログを出さない、またはKivyのSDL2部分でリダイレクトされていない可能性）。

**未解決・次回の調査候補（優先度順、更新）**：
0. ~~最優先：Kivy(SDL2)ウィンドウが実際に選択したEGL Configのstencilサイズを特定する~~ → **今回のセッションで実施・解決（下記参照）。stencil仮説は完全に否定された。**
1. 上記で確定困難な場合、`racecapture/views/dashboard/dashboardview.py`側で`DigitalGaugeElement`以外の一般的な`MDLabel`（Stencilを使わない箇所、例えばツールバーのタイトル等）が表示されているかどうかを別途連続キャプチャで確認し、「Stencil配下のLabelだけが非表示」なのか「全てのLabelが非表示」なのかを切り分ける（現状は判別できていない）。→ **これも今回のセッションで判明：Stencilを使わないツールバーのLabelも含め、GPU上には正しく描画されているのに画面には一切出ない、という、より根深い問題であることが確定した（下記参照）。**
2. 実解像度がアプリ内部で上書きされる現象（1024x768に固定される件）は今回未着手。逆コンパイル済みソース（`~/decompile_4-4-2/race_capture_extracted/`）から`Config.set('graphics', ...)`のような呼び出し箇所を探索する。
3. KivyMD側の既知issue（背景色/canvas色指定が反映されないバグ報告）との関連は、逆コンパイル済みソースと突き合わせてまだ未実施。

---

**今回のセッション（4-4-2続き・第3回）で得た決定的な新知見：stencil仮説を完全否定し、問題の所在をアプリ内部からEGL/KMS境界へ移した**：

**接続情報の補記（次回用）**：`rc-dash-3b`へのSSH秘密鍵は`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`（`ntakao@rc-dash-3b.local`、mDNS名で到達可能、IPアドレス固定不要）。今回のセッション開始時、前回セッションの`EGL_LOG_LEVEL=debug`検証用に起動されたままだった`race_capture`（`~/racecapture_egldebug.log`向け起動）が58分間放置されて残っていたため停止した。**次回セッション開始時は必ず`ps aux | grep race_capture`で放置プロセスがないか確認すること。**

**1. `gdb`によるライブプロセスへの直接介入という新しい調査手法を確立**：
`sudo apt-get install -y libegl1-mesa-dev libgles2-mesa-dev`でEGLヘッダーを導入した上で、当初は`LD_PRELOAD`/`LD_LIBRARY_PATH`によるEGL関数フック（`eglChooseConfig`等をラップする共有ライブラリ、ソース一式`/tmp/egl_hook.c`）を試みたが、SDL2が`dlopen`で読み込む実体を完全に置き換える方式は、未実装のEGL関数が芋づる式に必要になり(`No matching FB config found`で起動失敗)、実用的でないと判断し断念した。
代わりに、**稼働中の`race_capture`プロセスに`sudo gdb -p <PID>`でアタッチし、Python C API（`PyGILState_Ensure()`→`PyRun_SimpleString("exec(open('/tmp/script.py').read())")`→`PyGILState_Release()`）を`call`コマンドで直接呼び出すことで、アプリを再起動せずにライブのPythonインタプリタ内で任意のコードを実行する**手法を確立した。これにより：
- まず`thread apply all p (void*)eglGetCurrentContext()`で9スレッド中どれがGLコンテキストをcurrentにしているか特定（Thread 1、メインスレッドのみ非ゼロ）。
- そのスレッド上で`glGetIntegerv(GL_STENCIL_BITS, ...)`等を直接呼び出し、**このPiの実際に使用中のGLコンテキストは`GL_STENCIL_BITS=8`（有効）、`GL_DEPTH_BITS=24`、RGBA8888、`GL_SAMPLES=0`、`glGetError()=0`（エラーなし）であることを実測で確定**。前回セッションで最有力とされていた「stencilバッファが機能していない」という仮説は、**推測ではなく実測で完全に否定された**。
- ⚠️ **重要な注意点（次回のためのハマりどころ）**：`eglQuerySurface`等の出力引数に誤って`(int*)0`（NULLポインタ）を渡したところ、`race_capture`プロセスがgdbの`call`実行中にSIGSEGVでクラッシュした。**`gdb call`で関数を呼ぶ際、出力引数には必ず`(void*)malloc(N)`で確保した有効なポインタを渡すこと。ライブの実プロセスに対して行う操作のため、雑なテストコードがそのままプロセスを落とす**。クラッシュ後は`cd /opt/racecapture && nohup ./run_racecapture_rpi.sh -w 1 -- ... &`で通常のwatchdog付き起動に復旧させ、実機は正常稼働状態に戻して今回のセッションを終えている。

**2. Python C API注入により、ウィジェットツリー・canvas命令・実テクスチャの中身を直接検証、いずれも正常と判明**：
- `kivy.app.App.get_running_app()`経由でアプリのウィジェットツリー全体を再帰的にダンプ。`AppMainFrame`（1920x1080、opacity=1.0）配下、`NavigationDrawer`（閉状態のためx=-230の画面外、これは仕様通り正常）、`ToolbarView`、`ScreenManager > SetupView`（起動直後は設定未了のためSetupViewが表示されている）と、ツリー構造・各ウィジェットの`text`/`color`/`opacity`/`size`/`pos`はすべて一見して正常な値だった（例：`Label text='EXIT' color=[1,1,1,1] opacity=1.0`、`MDIcon color=[0.0,1.0,0.0,1.0]`等）。Python/Kivyのプロパティレベルには異常なし。
- ツールバーの`ProgressLabel`（"RaceCapture/Pro MK3 (esp32-c3 proto fw) esp32-c3-proto-build"）のcanvas命令を直接ダンプしたところ、実際のテキスト描画に使われる`Rectangle`命令（`pos=(1558.0, 1050.0) size=(250.0, 19.0)`、画面内に収まる座標、`Color rgba=[1.0,1.0,1.0,1.0]`＝不透明白、`texture`は250x19のRGBAテクスチャ）が完全に正しい状態で存在することを確認。StencilPush/StencilUse等の命令も別途あるが、これはKivyMDのリップルエフェクト用（幅0の矩形、通常時は無効）であり、本題の文字描画とは別系統と判明。
- **このテクスチャの実体（`texture.pixels`、実際にGPUからglReadPixels相当で読み戻される250x19=19000バイトのRGBAデータ）を`texture.save()`でPNGファイルへ書き出し、目視確認したところ、`"RaceCapture/Pr...32-c3-proto-build"`という完全に判読可能な文字がアンチエイリアス付きで正しくレンダリングされていた**（非ゼロバイト数15126/19000）。フォントレンダリング（sdl2_ttf）・テクスチャアップロードは完全に正常に機能している。

**3. 🔴🎉 最大の発見：Kivy自身の`Window.screenshot()`（実際のGPUからのglReadPixels）は文字・アイコンを完璧に描画しているが、`ffmpeg kmsgrab`（DRM/KMSの実スキャンアウトバッファを直接読む方式）や物理モニタは背景色2色のみしか見せない、という決定的な乖離を実測で確認**：
- `from kivy.core.window import Window; Window.screenshot('/tmp/kivy_window_screenshot.png')`をgdb経由で呼び出し（実際には`kivy_window_screenshot0001.png`として保存される仕様）、得られた1920x1080のPNGを解析したところ、**465種類ものユニークな色**が存在し、ツールバーの文字列「RaceCapture/Pr...32-c3-proto-build」が完全に判読可能な形で描画され、さらに状態アイコン（緑の円、黄色のターゲットアイコン、緑の雲アイコン）も正しい色で表示されていた。文字のアンチエイリアシングによる中間階調グレー（1〜239の多数の濃淡）も確認でき、**フォント・アイコン描画パイプラインはGPU上で完全に正常に機能している**ことが実測で確定した。
- 一方、**同じタイミング帯で`ffmpeg -f kmsgrab`により物理ディスプレイの実スキャンアウトバッファを直接キャプチャすると、これまでの全セッションと同様、`RGBA(0,0,0,0)`（透過）と`RGBA(18,18,18,255)`（背景色）の2色のみしか存在しない**（8フレーム連続バーストキャプチャでも全フレーム同じ結果）。ただし背景色矩形の面積（11520〜840044ピクセルの範囲で変動）はフレームごとに変化しており、**表示バッファ自体は継続的に更新されている（完全に静止した古いバッファではない）ことも確認**。つまり「一度も更新されない」のではなく「更新はされ続けているが、文字・アイコン相当のピクセルだけが一度も乗ってこない」という状態。
- `Window.canvas`（アプリ全体のルートcanvas）を再帰的にダンプし、プロセス内の全オブジェクトを`gc.get_objects()`で走査して`kivy.graphics.fbo.Fbo`インスタンスの有無を確認したところ、**Fboインスタンスはプロセス内に一つも存在しなかった**（0件）。これにより「オフスクリーンFBOで一旦描画してから最終スクリーンへblitする」という仮想解像度スケーリング層のような仕組みは存在しないことが確定し、その方向の仮説は排除できる。
- **結論・新しい最有力仮説**：この乖離パターン（GPU/Kivyが認識している描画内容は完全に正しいが、実際にKMSでスキャンアウトされる＝物理的に画面に映る内容とは食い違う）は、**アプリ側（race_capture本体・Kivy・KivyMD・フォント・stencil等）の問題では一切なく、`eglSwapBuffers`からGBMバッファの確保・DRM/KMSのページフリップに至る、SDL2のKMSDRMバックエンド〜Mesa VC4ドライバ間のどこかにある**と強く示唆される。これまでの全調査対象（4-4-2でこれまで検証してきたstencil、フォント、multisamples、full_screen_mode等）は的外れではなかった（実際に改善もしたが）ものの、**核心的な残課題は全く別のレイヤーにあった**という大きな方向転換。

**未解決・次回の最優先調査候補（更新）**：
0. ~~EGLサーフェスのダブルバッファリング設定を確認する~~ → **今回のセッションで実施・判明（下記参照）**。
1. ~~`/sys/kernel/debug/dri/0/state`を連続して複数回ダンプし、fb_idの変化を確認する~~ → **今回のセッションで実施・判明（下記参照）**。
2. **最小限のKivyアプリ（`Label`一つだけを表示するだけのシンプルなスクリプト）を同じRaspberry Pi・同じKMSDRM/Mesa VC4環境で動かし、同じ「文字だけ消える」症状が再現するか確認する**。再現すれば、race_capture固有ではなく環境（SDL2 KMSDRM＋Mesa VC4 26.2.0）側の一般的な不具合と確定でき、Kivy/SDL2側のissueトラッカーでの既知問題の有無を調べる方向に絞れる。再現しなければ、race_capture側の何らかの特殊なOpenGL呼び出しパターン（例えば非標準のバッファクリア方法、あるいは`RenderContext`の使い方）に原因を絞り込める。**現時点で未着手・次回の最優先候補はこれ一本に絞られた**（下記参照）。
3. SDL2のKMSDRMバックエンドが利用するGBMサーフェスのバッファ数（`gbm_surface_create`のフラグ、ダブル/トリプルバッファ）を、`strace`等でシステムコールレベルから確認する。

---

**今回のセッション（4-4-2続き・第4回）で得た知見：EGL/DRM設定は「正常」、2つのワークアラウンド候補はいずれも効果なし**：

**1. EGLサーフェスのバッファリング設定は標準的で、それ自体に異常はなかった**：
`eglQuerySurface`を（今度は`malloc`で確保した安全なポインタで）照会したところ、`EGL_RENDER_BUFFER=EGL_BACK_BUFFER`・`EGL_SWAP_BEHAVIOR=EGL_BUFFER_DESTROYED`・サーフェスサイズ1920x1080という、GLESドライバとしてはごく標準的な設定だった。この設定自体に異常は無い。

**2. `/sys/kernel/debug/dri/0/state`の連続ダンプにより、DRM側は正常に3枚のバッファをローテーションしながらページフリップし続けていることを確認**：
`plane[86]`（`crtc=pixelvalve-2`にバインドされている実際のスキャンアウトプレーン）の`fb`値を0.5秒間隔で5回サンプリングしたところ、`674, 674, 675, 672, 674`と、**`672`・`674`・`675`の3つの異なるフレームバッファIDが循環していることを確認**。つまりトリプルバッファリングが行われており、ページフリップ機構自体は正常に機能し続けている（フリップが止まっている、あるいは常に同じバッファに固定されている、という状態ではない）。

**3. 2つのワークアラウンド候補を試したが、いずれも症状を改善しなかった（重要な否定的所見）**：
- **`SDL_VIDEO_DOUBLE_BUFFER=0`環境変数**（`libSDL2-2-87637523.0.so.0.3000.7`の文字列解析で存在を確認したヒント）を設定して`race_capture`を再起動したが、`/sys/kernel/debug/dri/0/state`で確認する限りバッファ数は変わらず（引き続き672/674/675の3枚がローテーション）、kmsgrabキャプチャも従来通り2色（透過+背景色）のみだった。**このヒントはKMSDRM＋OpenGL/EGLの経路には効果がないと判明**（SDLのソフトウェアフレームバッファ経路向けのヒントで、Kivyが使うGLコンテキスト経由の描画には影響しないと推測される）。
- **`Window.canvas.ask_update()`を`Clock.schedule_interval(fn, 0)`で毎フレーム強制的に呼び出す**（gdb経由のPython注入で実施）ワークアラウンドも試したが、注入後にkmsgrabで3フレーム連続キャプチャしても依然として2色のみで、**文字は一切復活しなかった**。「Kivyがdirtyフラグに基づいて再描画をスキップしている」という単純な仮説だけでは説明がつかない、より根深い問題であることが示唆される（`ask_update()`はCanvasに再描画をリクエストするだけで、実際の再描画トリガーの仕組みはこれだけでは不十分な可能性がある）。

**今回のセッションのまとめ**：stencil仮説の完全否定、Kivy内部描画の正常性の実証（Window.screenshot()で文字・アイコン完璧に表示）、DRM側のページフリップが正常に機能し続けていることの確認、という大きな前進があった一方、2つの簡易ワークアラウンド候補はいずれも空振りに終わり、**根本原因の特定にはさらに踏み込んだ調査（優先度2の「最小Kivyアプリでの再現実験」、または`window_sdl2`のCython実装(`.so`)をobjdump等でのフレームループ処理自体の解析）が必要**という状態で次回に持ち越す。

**4. 最小限のKivyアプリでの再現実験を試みたが、race_captureとは異なるパターンの不具合が出て決定的な結論には至らなかった（次回への引き継ぎ事項）**：
apt経由で`python3-kivy`（v2.3.1-1+b1、race_captureがバンドルするKivyと同系統のバージョン）を導入し、`Label`一つと単色背景`Rectangle`だけを描画する最小限のアプリ（`BoxLayout`+`Color`+`Rectangle`を`canvas.before`に設置、全画面1920x1080、`multisamples=0`）を作成して実行した（race_captureは一時停止してDRMマスター権を空けてから実行）。
- **結果はrace_captureとは異なるパターンだった**：`ffmpeg kmsgrab`では完全な透過`(0,0,0,0)`のみ（race_captureのように背景色すら出ない）、`Window.screenshot()`によるKivy自身のGPU読み戻しでも**不透明な黒`(0,0,0,255)`一色のみ**（Kivyのデフォルトクリアカラーそのもので、こちらも背景矩形・文字とも一切描画された形跡がない）。
- ウィジェットツリー・canvas命令を同様にgdb経由でダンプしたところ、`root`（1920x1080）・`Label`（1920x1080、`text`正しく設定）・`canvas.before`の`Color rgba=[0.0706,0.0706,0.0706,1.0]`＋`Rectangle pos=(0,0) size=(1920,1080)`と、**Python/canvas命令レベルでは完全に正しい状態**であることを確認した（race_capture同様、Python側は無罪）。にもかかわらずKivy自身の読み戻しでも何も描画されていなかった。
- **これはrace_captureの症状（背景だけは常に正しく出る）とは異なる新しいパターンであり、「race_captureとは別の要因（このミニマルスクリプト固有の初期化タイミング、または`python3-kivy`パッケージ版とrace_capture同梱版のビルド設定差）が別途作用している」可能性がある**。今回は数秒待ってから2回スクリーンショットを試したがいずれも同じ結果で、単純な「初回フレーム未描画」というタイミング問題だけでは説明しづらい。
- **追試（タイミング懸念を排除）**：「まだ最初のフレームが描画されていないだけでは」という懸念を排除するため、`App.on_start()`内で`Clock.schedule_once(take_shot, 3.0)`により**アプリ自身の正規のイベントループ上で3秒間（数百フレーム相当）実際にレンダリングさせてから`Window.screenshot()`を呼ぶ**よう改良して再実行したが、**結果は完全に同一（バイト数まで一致する不透明黒一色）だった**。これによりタイミング問題という可能性は排除され、**この最小アプリはKivy自身の内部読み戻しにおいてすら、実行中ずっと背景矩形・文字を一度も描画できていない、という真正の不具合を抱えていることが確定した**。
- **結論**：この最小アプリの不具合はrace_capture本体の症状（Kivy内部読み戻しでは正しく描画される、KMS実スキャンアウトでのみ消える）とは**明確に異なるパターン**であり、そのままでは「race_capture固有かAPT/KMSDRM環境固有か」の切り分けには使えなかった。おそらく、apt版`python3-kivy`（システムSDL2 2.30.x系にリンク）とrace_capture同梱版Kivy（バンドルされた独自のSDL2 2.30.7）のビルド設定・依存ライブラリの何らかの違いが、このミニマルスクリプト側に別の非互換を生んでいると推測される。次回この方向で再挑戦する場合は、①`canvas.before`ではなく素の`canvas`を使う、②`Color`/`Rectangle`を`kv`言語ファイル経由で定義する（race_captureの実際の描画パターンに近づける）、③`python3-kivy`ではなくrace_capture同梱のSDL2/Mesaライブラリを`LD_LIBRARY_PATH`で優先させた上でapt版Kivyを動かす、といった条件の近似化が必要。
- テストスクリプトは`/tmp/minimal_kivy_test.py`として実機に保存済み（次回セッションでも参照・改造可能）。

**実機（`rc-dash-3b`）の状態**：セッション終了時点で、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み。今回の調査で作成した一時ファイル（`/tmp/egl_hook.c`、`/tmp/egllib/`、`/tmp/introspect*.py`、`/tmp/gdb_*.txt`、各種キャプチャ画像、`/tmp/minimal_kivy_test.py`等）は`/tmp`配下のため次回リブートで自然に消える想定で、明示的なクリーンアップはしていない。なお`python3-kivy`（v2.3.1-1+b1）とEGL/GLES開発ヘッダー（`libegl1-mesa-dev`・`libgles2-mesa-dev`）は今回のセッションでシステムに恒久導入済み（次回セッションでも再インストール不要）。

---

**今回のセッション（4-4-2続き・第5回）で得た決定的な知見：根本原因を実証レベルで特定、実機への適用は次回へ持ち越し**：

**接続情報の補記**：`rc-dash-3b`へのSSH接続は今回のセッション中に何度か（`kill`/`pkill`実行直後を中心に）瞬断が発生した（原因未特定、Pi 3Bの負荷起因の可能性）。再接続すれば問題なく復帰するため、単発の切断は無視して再接続すればよい。

**1. 🔴🎉 最大の成果：最小限のKivyアプリで、race_capture本体と同じ「GPU内部読み戻しは正しいがKMS実スキャンアウトには乗らない」現象を初めて再現させ、原因をSDL2バージョンにまで絞り込んだ**：
- apt版`python3-kivy`（システムSDL2 2.32.4使用）に、race_capture同梱の`libSDL2-2-87637523.0.so.0.3000.7`（SDL2 2.30.7）を`LD_LIBRARY_PATH`経由のシンボリックリンクで読み込ませたところ（`/tmp/sdl2_swap/libSDL2-2.0.so.0`として配置）、**最小アプリのKivy内部読み戻し（`Window.screenshot()`）が、システムSDL2使用時の「完全な黒一色」から「背景+白文字が正しく描画された237色」へと劇的に改善した**。一方`ffmpeg kmsgrab`による実スキャンアウトは3フレーム連続で完全透過(0,0,0,0)一色のまま。
- **これにより「GPU内部描画は正しいのにKMS実画面には乗らない」というrace_capture本体の症状パターンが、race_capture固有のアプリコードとは無関係に、race_capture同梱のSDL2 2.30.7というライブラリバージョン自体（Mesa VC4 KMSDRMバックエンドとの組み合わせ）に起因することが実証された**。なお背景矩形すら出ないという点は本家race_captureの症状（背景は出る）とは差異があるが、「内部読み戻し正常・KMS実スキャンアウト異常」という核心的な乖離パターンの再現に初めて成功した意義は大きい。
- ハマりどころ：SDL2_ttf/SDL2_image/SDL2_mixerまで同梱版に一括スワップすると、フォントレンダリングのText Providerが`sdl2`から`pil`へ意図せずフォールバックし（過去セッションで「筋が悪い」と結論済みの条件と汚染される）、コアの`libSDL2`のみをスワップする必要がある。

**2. 🔴🎉 根本原因を特定：Kivyの「変化がなければ再描画をスキップする」最適化と、このGPU/ドライバの「バッファ内容がスワップ間で保持されない（`EGL_SWAP_BEHAVIOR=EGL_BUFFER_DESTROYED`、3枚のバッファをローテーション）」という制約が組み合わさり、静的なLabel/文字の描画コマンドが一部の物理バッファにしか乗らない、という構造的な不具合と判明**：
- 最小アプリ（SDL2コアスワップ状態）で、`Clock.schedule_interval(fn, 0)`により**毎フレーム、背景`Rectangle`のsize・`Color`のalphaを微小値(1e-6/0.0001)で往復させ、かつ`Label.texture_update()`を呼ぶ**ことで、Kivyの「変化なし判定」を強制的に迂回させたところ、**`ffmpeg kmsgrab`による3連続フレームすべてで、背景・白文字とも完璧に描画されるようになった（239色、内部読み戻しの238色とほぼ一致、白文字ピクセル数10559 vs 10559で完全一致）**。これにより「毎フレーム強制再描画すれば直る」という仮説が実証された。
- 念のため「単に時間が経てば直るのでは（タイミングの問題）」という対抗仮説も検証：注入なしの新規起動race_captureを20秒以上放置してからkmsgrabしたが、依然として2色のまま変化なし。**「時間経過だけでは直らない」ことも確認済み**で、上記の「強制再描画」仮説の方が優位に支持される。

**3. ⚠️ ただし、上記の「強制再描画」ワークアラウンドを実際のrace_capture本体（gdb Python注入）へ適用する試みは、3段階の手法いずれも効果が無かった（次回への重要な引き継ぎ課題）**：
- 手法1：`app.root.opacity`を毎フレーム微小往復 → 効果なし（2色のまま）。過去セッションで否定済みの`ask_update()`系と同じ弱い無効化経路を辿っていると推測。
- 手法2：ウィジェットツリー全体を再帰的に走査し、`texture_update()`と`canvas.ask_update()`を全ウィジェットに毎フレーム適用 → 効果なし（2色のまま）。
- 手法3：ウィジェットツリー全体の`canvas_before`/`canvas`/`canvas_after`配下の`Color`/`Rectangle`インストラクションを再帰的に収集し（実測3359個のColor・2439個のRectangleに到達）、毎フレーム直接プロパティを微小変化させる、最小アプリで効果があったのと全く同じ手法 → **それでも効果なし（2色のまま）**。
- **この「最小アプリでは効くが実機race_captureでは効かない」という乖離自体が重要な新情報**。考えられる要因（次回調査候補）：①5798個ものインストラクションを無制限フレームレート(`interval=0`)で毎フレーム触ることによる過負荷でレンダーループ自体が実質的に停止/フレームが完走していない可能性、②ScreenManager配下で現在非表示のScreenのインストラクションまで一緒に触っても意味がなく、実際に描画対象となる「現在表示中のScreenのみ」に絞り込めていない可能性（`app.root`からの再帰走査が現在アクティブなScreen配下だけを辿れているか要検証）、③KivyMD独自ウィジェット（MDLabel等）が内部でFBOやRenderContext経由の別経路を使っており、素の`Color`/`Rectangle`プロパティ変更だけでは実際のGL描画コマンド再発行につながっていない可能性。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/sdl2_swap/libSDL2-2.0.so.0`：race_capture同梱SDL2コアライブラリへのシンボリックリンク（次回もそのまま再利用可）
- `/tmp/minimal_kivy_test.py`（既存、前回セッションから）、`/tmp/minimal_kivy_forcedirty.py`（新規、強制再描画版）：いずれも保存済み
- `/tmp/inject_forceredraw.py`・`/tmp/inject_forceredraw2.py`・`/tmp/inject_forceredraw3.py`：race_captureへのgdb注入用スクリプト3種（いずれも効果なしと確認済みだが、次回の改良のベースとして保存）
- `ffmpeg -f kmsgrab`のコマンド構文が今回のOS/ffmpegバージョン更新（`7.1.5`）で変化していたため更新：**`-pix_fmt bgr0`直接指定は`Impossible to convert`で失敗するようになった。正しくは`-vf 'hwdownload,format=bgra' -update 1 -frames:v 1 out.png`**（`-update 1`が無いと単一ファイル名では書き込み拒否されるようになった点も新しい変更点）。以後のkmsgrabキャプチャはこの新構文を使うこと。
- セッション終了時点で`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み（注入は一切残っていない、クリーンな状態）

**次回の最優先調査候補（優先度順）**：
0. **手法3（Color/Rectangleインストラクション直接摂動）を、対象を「現在アクティブなScreenの子孫のみ」に絞り込み、かつ`interval=0`ではなく`interval=1/30`程度に抑えた軽量版で再試行する**。過負荷仮説とScreenManager非表示分岐の仮説を同時に切り分けられる。
1. 上記で改良しても効かない場合、`gdb`でPythonレベルの計測（`Clock`のフレームカウンタを注入前後で比較する等）により、注入したコールバックが実際に毎フレーム呼ばれているか、そもそも実行頻度が期待通りかを直接確認する。
2. KivyMDの`MDLabel`/`MDIcon`が内部で`RenderContext`や独自の`InstructionGroup`をどう使っているか、逆コンパイル済みソース（`~/decompile_4-4-2/`）を突き合わせて確認する。
3. 恒久対策としては、gdbによる実行時注入よりも「起動直後に一度だけ全ウィジェットへ`texture_update()`を強制した上で、Kivyの`Config`にある再描画関連の設定（`graphics`セクション、または環境変数）で本質的に無効化できないか」を探る方が現実的な可能性がある。

---

**今回のセッション（4-4-2続き・第6回）で得た知見：force-redraw系ワークアラウンドの絞り込み版も空振り、代わりにgdb注入運用上の重大な安全知見を獲得**：

**1. 手法3（Color/Rectangleインストラクション直接摂動）を「現在アクティブなScreenの子孫のみ」に絞り込み、`interval=0`ではなく`interval=1/30`に抑えた軽量版（前回セッションの優先候補0）を試したが、効果なし（`ffmpeg kmsgrab`は3フレームとも従来通り2色のみ）**：
- race_capture再起動直後のため対象は`Screen name='setup'`（ESP32未接続時のセットアップ画面）、Color 1087個・Rectangle 793個を毎フレーム摂動。
- **別途、単純な心拍コールバック（`Clock.schedule_interval`で1秒ごとに`/tmp/heartbeat.log`へ追記するだけの注入）を仕込み、約26秒間・26回、ほぼ正確に1.0〜1.06秒間隔で発火し続けることを実測で確認した**。これにより「gdb注入したコールバックが実は呼ばれていない／早期に例外で止まっている」という可能性を排除できた（前回セッションの次回調査候補1で挙げていた懸念点への回答）。Clockは確実に動き続けているにもかかわらずKMS実スキャンアウトには一切反映されないため、**「force-redraw系ワークアラウンド」の方向性は、これまでに試した全バリエーション（`ask_update()`単体、`opacity`往復、全ウィジェット走査＋`interval=0`、今回のScreen限定＋`interval=1/30`）が出揃った時点で、事実上手詰まりと判断する**。次回セッションはこの方向を打ち切り、優先候補2（KivyMDのRenderContext/FBO経路の調査）または`window_sdl2`の`.so`解析など、別のレイヤーへ転換することを推奨。

**2. 🔴⚠️ 重大な運用上の新知見：gdbのinfcall（`call`コマンド）によるPython C API呼び出しが、他スレッドを停止させたままGIL解放待ちで永久デッドロックする事例を実際に踏んだ（次回以降、必ず回避策を使うこと）**：
- 過去セッション（第3〜5回）と全く同じ`PyGILState_Ensure()`→`PyRun_SimpleString(...)`→`PyGILState_Release()`のgdb注入パターンを実行したところ、今回は`call`が10分以上応答なく完全にハングした。`race_capture`プロセスの全10スレッドがCPU時間の増加を完全に停止し（`ps`のTIME列が数十秒間1ミリ秒も進まない）、真正のデッドロック状態に陥っていることを確認した。
- **原因と推測**：gdbのinfcall（`call`コマンド）はデフォルトで対象スレッド以外を停止させたまま呼び出しスレッドだけを実行する（scheduler-locking）。このとき呼び出しスレッドが`PyGILState_Ensure()`内でGILを取得しようとしてブロックし、かつ実際のGIL保持スレッドが停止させられたままだと、GILが永久に解放されず`call`自体が返ってこない。過去セッションで同じ手法が3回成功していたのは、たまたま呼び出しタイミングでGILが空いていた（幸運だった）だけと考えられる。
- **対処（今回確立・以後必須）**：gdbコマンドファイルの`call`実行前に`set scheduler-locking off`を追加することで、infcall中も他スレッドの実行を許可し、GIL保持スレッドが自然に解放できるようにする。この修正を入れた再試行では即座に（数秒以内に）正常復帰し、以後2回の注入（本セッション内）とも問題なく完了した。**次回以降、この種のgdb Python注入を行う際は`set scheduler-locking off`を必ず`call`の前に入れること。**
- **デッドロック発生時の復旧手順（今回の実地対応、次回の参考用）**：①ハングしたgdbプロセス自体を`sudo kill -9`しても、race_capture側のデッドロックは解消しない（ptrace detach後もフリーズしたスレッドは既にfutex待ちに入っているため）。②`race_capture`プロセス自体を`sudo kill -9`する必要がある。③**このとき`run_racecapture_rpi.sh -w 1`の watchdog は既に稼働中であれば、子プロセスの死亡を検知して自動的に新しい`race_capture`を再起動することを実地で確認した**（手動での再起動コマンド発行は不要かつ危険——後述）。
- **⚠️ 自己反省・二重起動インシデント**：上記の自動復旧を知らずに手動で`nohup ./run_racecapture_rpi.sh -w 1 ...`を追加実行してしまい、既存のwatchdog（自動復旧済み）と合わせて**race_captureが二重起動する事故を起こした**（DRM/シリアルポートの奪い合いのリスクあり）。すぐに気付いて重複プロセスをkillし単一プロセスの状態に復旧させたが、**次回以降、race_captureが死んだ場合はまず`ps -ef | grep race_capture`でwatchdog（`run_racecapture_rpi.sh -w 1`）が既に自動再起動したかを確認してから対応すること。自動復旧を待たずに手動再起動コマンドを重ねて打たないこと。**

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：単一の`race_capture`プロセス（既存watchdog経由、`Screen name='setup'`、ESP32未接続状態）が正常稼働中。今回注入したコールバック（force-redraw・心拍とも）はプロセスの再起動により消滅済み（永続化なし）。`/tmp/inject_*`・`/tmp/heartbeat.log`・`/tmp/kmscap4/`等の一時ファイルは`/tmp`配下のため次回リブートで自然に消える想定。

**次回の最優先調査候補（優先度順、更新）**：
0. ~~手法3を現在アクティブなScreenのみ・軽量版で再試行~~ → **今回のセッションで実施・効果なしと確定。force-redraw系ワークアラウンドはこの時点で打ち切り。**
1. KivyMDの`MDLabel`/`MDIcon`が内部で`RenderContext`や独自の`InstructionGroup`（FBO等）をどう使っているか、逆コンパイル済みソース（`~/decompile_4-4-2/`）を突き合わせて確認する（過去セッションから持ち越しの候補、force-redraw系が手詰まりになった今、優先度が上がった）。
2. `window_sdl2`のCython実装（`.so`）を`objdump`等でフレームループ・バッファスワップ処理自体を解析し、KMSDRMバックエンドとの相互作用を直接調べる。
3. ESP32を接続してScreenを`setup`から実際のダッシュボード（Home等）へ進めた状態で、同じ調査（心拍ログでのClock動作確認、kmsgrabキャプチャ等）を行う（今回はESP32未接続でセットアップ画面のみの調査だった点に注意）。

---

---

**今回のセッション（4-4-2続き・第7回）で得た知見：KivyMD側のRenderContext/FBO仮説を完全否定、SDL2コアライブラリのみの差し替えでは実機は直らないことを実証**：

**実機状態の確認（セッション開始時）**：`rc-dash-3b`にSSH接続し`ps -ef`で確認したところ、放置プロセス（gdb等）は無く、`race_capture`（watchdog経由、`run_racecapture_rpi.sh -w 1`）が正常稼働中だった。前回セッション末尾の注意書き通りのクリーンな状態から開始できた。

**1. 🔴 前回セッションの優先候補1（KivyMDのRenderContext/FBO経路調査）を実施・完全否定**：
逆コンパイル済み`~/decompile_4-4-2/race_capture_extracted/PYZ.pyz_extracted/kivymd/`配下の全`.pyc`（99ファイル）を、`xdis`の`load_module()`でコードオブジェクトとして読み込み、`co_names`を再帰的に走査して`RenderContext`・`Fbo`・`InstructionGroup`・`StencilPush`・`StencilUse`・`texture_update`の出現を横断検索した（スクリプトは`/tmp/scan_kivymd.py`、実機に保存済み）。結果、**`RenderContext`・`Fbo`・`InstructionGroup`はkivymd全体で一件も参照されていない**ことを確認した。唯一のStencil系参照は`kivymd/uix/behaviors/ripple_behavior.pyc`（`StencilPush`/`StencilUse`、既に前々回セッションで「リップルエフェクト用、通常時は幅0で無効」と確認済みのもの）のみ。**「KivyMD独自ウィジェットがFBOやRenderContext経由の別描画経路を使っているのでは」という仮説は、実装上そもそもそのAPIを一切使っていないことが確定し、完全に否定された**。

**2. 🔴 SDL2コアライブラリのみをシステム版（2.32.4）に差し替える実験を実機`race_capture`本体に対して実施したが、症状は改善しなかった（重要な新しい否定的所見）**：
- 前回セッションで確立した「race_capture同梱のSDL2 2.30.7を最小Kivyアプリに移植すると同じ症状を再現できる」という知見の**逆方向**（＝実機race_captureに新しいSDL2 2.32.4を与えたら直るのでは）を検証した。
- `readelf -d`で`_window_sdl2.cpython-311-*.so`の依存関係を確認したところ、`RPATH=$ORIGIN/../../../Kivy.libs`（旧形式RPATH）が設定されており、**`LD_LIBRARY_PATH`より優先されるため環境変数での差し替えは効かない**ことが判明。そのため`/opt/racecapture/_internal/Kivy.libs/libSDL2-2-87637523.0.so.0.3000.7`（バンドル版、要求されるファイル名そのもの）を直接操作する必要があった。
- 元ファイルを`.bak_4-4-2`としてバックアップした上で、同名ファイルをシステム版`/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0`（2.32.4）へのシンボリックリンクに置き換え、`race_capture`を再起動（watchdog経由で自動復旧、PIDのみ変わる）。ログにエラーは一切出ず、Text providerも`sdl2`のまま維持され、ESP32との通信・GPS/テレメトリ受信も正常に継続した（＝SDL2コアの差し替え自体はクラッシュなく機能した）。
- しかし`ffmpeg kmsgrab`による3連続キャプチャは、**従来と全く同じ`RGBA(0,0,0,0)`と`(18,18,18,255)`の2色のみ**で、文字・アイコンは依然として一切表示されなかった。ESP32接続済み・GPS/テレメトリ正常受信という「完全に正常な稼働状態」下での結果である点も前回までと同条件。
- 検証後、直ちに`.bak_4-4-2`から元のバンドル版ファイルへ復元し（MD5ハッシュ一致で復元を確認済み：`60689a9cef510e5b73ff3fba29bd3869`）、`race_capture`を再起動して正常稼働状態（エラー無し、GPS/テレメトリ正常）に戻したことを確認済み。実機に恒久的な変更は残っていない。
- **考察**：前回セッションで示された「SDL2 2.30.7を新しいアプリに移植すると症状を再現する」という結果と、今回の「SDL2 2.32.4を旧アプリ(race_capture)に移植しても直らない」という結果は非対称であり、**SDL2コアライブラリのバージョン単体が唯一の原因因子ではない**ことを示唆する。可能性としては、①SDL2_ttf/image/mixer（今回は差し替えていないバンドル版2.30.x系のまま）がコアと何らかの形で密結合しており、コアだけ新しくしても意味がない、②前回の「再現実験」で見えた症状はrace_capture本体の症状と表面上似ているだけの別原因（apt版Kivyとの組み合わせ固有の何か）だった、③そもそもSDL2バージョンではなく、race_capture固有のビルドオプション・GLコンテキスト生成パラメータ（EGL Config選択時の具体的な属性リスト等）に真因がある、等が考えられる。いずれも次回の要検証事項。

**今回のセッションの意義**：2つの有力仮説（KivyMD RenderContext/FBO、SDL2コア差し替えのみでの修正）をいずれも実測で否定できたことで、**「アプリ側のPython/Kivyレベルの問題」という方向性そのものへの疑念が強まった**。前々回までに確定している「Kivy内部のGPU読み戻し(`Window.screenshot()`)は完全に正常、KMS実スキャンアウトのみ異常」という乖離の核心原因は、依然としてSDL2のKMSDRMバックエンド〜Mesa VC4ドライバ間のどこかにあると考えられるが、単純な「ライブラリバージョンを上げる」対処では解決しないことが分かった。

**次回の最優先調査候補（優先度順、更新）**：
0. **SDL2 2.30.7のオープンソース（KMSDRMバックエンド, `src/video/kmsdrm/`）を実機外（Web調査）で直接読み、2.30系→2.32系の間でKMSDRM関連の修正がchangelog上に無いか確認する**。今回コア単体差し替えでは直らなかったため、変更点を正確に特定した上で該当パッチのみを適用する、より的を絞ったアプローチに切り替える。
1. 上記0と並行し、`window_sdl2`のCython実装(`.so`)を`objdump`でフレームループ・`eglSwapBuffers`呼び出し周辺を解析する（既存の優先候補、未着手のまま持ち越し）。
2. SDL2_ttf/image/mixerも含めた「バンドル版一式をまるごとシステム版に統一」する差し替え（今回はコアのみだった）を試す。ただしKivyMDのフォントレンダリングがPILへフォールバックしないよう、システム版のバージョン差異に注意（過去セッションでフォールバックが起きた前例あり）。
3. race_capture起動時のログ（`log_level=debug`のまま）で、EGL Config選択時の実際の属性リスト（`SDL_GL_SetAttribute`相当のログ、または`strace`での`eglChooseConfig`呼び出し引数）を直接確認し、最小アプリ側の設定と具体的に何が違うかを突き合わせる。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`race_capture`は元のバンドル版SDL2で正常稼働中（watchdog経由、エラーなし、GPS/テレメトリ正常）。今回のセッションで加えた実機ファイル変更は`libSDL2-2-87637523.0.so.0.3000.7.bak_4-4-2`（バックアップファイル、削除せず残置——次回同様の検証をする際に再利用可）のみで、動作に影響する変更は残っていない。`/tmp/scan_kivymd.py`（KivyMD横断検索スクリプト）・`/tmp/kmscap_sdl2swap/`（差し替え時のキャプチャ結果）も実機に保存済み。

---

**今回のセッション（4-4-2続き・第8回）で得た知見：`eglChooseConfig`はそもそも呼ばれていないと判明、そして最有力の新仮説──`race_capture`同梱の独自「WindowPatch」がリサイズの度に描画を無効化する仕組みを発見**：

**接続情報の補記**：`rc-dash-3b`へのSSH接続（`ntakao@rc-dash-3b.local`、鍵は`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`）は今回も正常。セッション開始時、放置プロセスはなく`race_capture`はwatchdog経由でクリーンに稼働中だった。

**1. LD_PRELOADによるEGL関数フック（v1）は失敗、原因はSDL2がdlopen+dlsym(handle,...)で直接シンボル解決していること**：
Web調査（SDL公式コミット履歴）で、`SDL_VIDEO_DOUBLE_BUFFER`ヒントをKMSDRMバックエンドで実際に有効化するコミット(`5ab1151`、2024-07-18)は、実機バンドル版SDL2 2.30.7のリリース日(2024-09-01、GitHub API`release-2.30.7`タグで確認)より前で、**既にバンドル版に含まれていたと判明**。これにより前回セッション(第4回)で「`SDL_VIDEO_DOUBLE_BUFFER=0`が効かなかった」のはヒント自体の不備ではないと分かった。
続けて、`eglChooseConfig`/`eglCreateWindowSurface`/`eglSwapBuffers`をログ出力する素朴なLD_PRELOADフック(`egl_interpose.c`、単純にシンボルを再定義するだけの非侵襲的な手法)を作成・コンパイルし、稼働中の`race_capture`を安全に停止→`LD_PRELOAD`付きで15秒間だけ手動起動→watchdogで自動復旧、という手順（gdb注入より低リスク）で試したが、**ログファイルが一切生成されず、フックは一度も呼ばれなかった**。原因を調査した結果、**SDL2はEGL関数を通常のリンク（PLT経由）ではなく`dlopen("libEGL...")`＋`dlsym(handle, "eglChooseConfig")`のように特定ハンドル指定で解決しており、この方式はグローバルシンボルテーブルを経由しないため`LD_PRELOAD`による通常のシンボル差し替えでは横取りできない**ことが判明した（video-streamerの`libstdc++`/`libva`差し替えが効いたのとは対照的な結果）。

**2. `dlsym()`自体をフックする改良版(v2)で横取りに成功、そして重要な発見：`eglChooseConfig`は実際には一度も呼ばれていなかった**：
`dlsym()`を横取りし、呼び出し名が`eglChooseConfig`/`eglCreateWindowSurface`/`eglSwapBuffers`の場合だけ自前のロギングラッパーを返す（それ以外は本来の`dlsym`結果をそのまま返す）方式の`egl_interpose2.c`を作成。`dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.2.5")`で無限再帰を回避。同じ「安全な停止→15秒稼働→watchdog自動復旧」手順で実機`race_capture`に適用したところ、今度は正常にフックが機能し(`/tmp/egl_interpose2.log`)、以下が判明した：
- `eglChooseConfig`はシンボルとしてフックはされた（`dlsym()`で名前解決はされている）が、**実行された形跡（ログ）が一切無い**。つまりKivy/SDL2はconfig選択に`eglChooseConfig`を使っておらず、`eglGetConfigs`＋`eglGetConfigAttrib`による手動フィルタリング、または既知のconfig IDを直接指定する等の別経路を使っていると推測される（未確認、次回調査候補）。
- `eglCreateWindowSurface`が**同一のウィンドウハンドルに対して2回呼ばれ**、2回とも同じサーフェスポインタが返っていることを確認：1回目はプロセス起動直後（`config_id=3、RGBA=8/8/8/8、depth=24、stencil=8、samples=0`——過去セッションでgdb実測した値と完全に一致）、**2回目はその約14秒後**。この「起動から一定時間後にEGLサーフェスが再作成されるイベントが実在する」という事実を、ログという確たる証拠で初めて捉えた。
- `eglSwapBuffers`は2回目の`eglCreateWindowSurface`直後に1回だけ呼ばれたところで15秒のタイムアウトに達した（テスト時間が短すぎて継続動作は未確認）。

**3. 🔴🎉 最有力の新仮説を発見：`race_capture`にバンドルされている独自の「WindowPatch」(`autosportlabs/monkey_patches/window.py`)が、ウィンドウリサイズの度に`Window.on_draw`/`Window.update_viewport`を一時的に何もしないラムダへ差し替える仕組みだと判明**：
起動ログ(`race_capture_egltest2.log`)に`[DEBUG] [WindowPatch] Applied window resize patch`という、これまでのセッションで見落としていたログ行を発見。逆コンパイル済みソース(`~/decompile_4-4-2/`、前回までのセッションの成果物で今回も再利用可能だった)から該当モジュール`autosportlabs/monkey_patches/window.pyc`を`pydisasm`で逆アセンブルし、ロジックを完全に復元した。要約すると（疑似コード）：
```python
_original_on_draw = Window.on_draw
_original_update_viewport = Window.update_viewport

def _restore_drawing(*args):
    Window.on_draw = _original_on_draw
    Window.update_viewport = _original_update_viewport
    _original_update_viewport()
    _original_on_draw()

_restore_drawing_trigger = Clock.create_trigger(_restore_drawing, 0.25)  # デバウンス

def _on_resize(instance, width, height):
    Window.clear()
    Window.flip()
    Window.on_draw = lambda *_: None          # ← 描画を無効化
    Window.update_viewport = lambda *_: None  # ← ビューポート更新も無効化
    _restore_drawing_trigger.cancel()
    _restore_drawing_trigger()                # 0.25秒後方に再スケジュール

Window.bind(on_resize=_on_resize)
```
つまり**リサイズイベントが起きるたびに、`on_draw`/`update_viewport`を0.25秒間（かつ、その間に新たなリサイズが来るたびに0.25秒延長され続ける）まるごと無効化し、リサイズが収まってから1回だけ強制再描画して元に戻す**という設計。おそらくKivy側の「リサイズ中にGL関連クラッシュが起きる」既知問題への対策として実装されたものと推測される。

**4. この発見が、これまでの全セッションの観測結果を矛盾なく統一的に説明できる可能性が高いことに気づいた（未検証・次回最優先）**：
- DC-4以来ずっと「背景色（`(18,18,18,255)`の単色矩形）だけは常に正しく描画されるが、文字・アイコンは一切乗らない」というパターンが再現し続けていた。**背景色はKivyの毎フレームの`glClear()`（クリアカラー）で塗られる一方、文字・アイコンはKivyの「変更が無ければ再描画をスキップする」最適化のもとで`on_draw`経由のみ描画される**——これは、`on_draw`が`WindowPatch`によって断続的に（あるいは何らかの理由で継続的に）no-opへ差し替えられている状態と矛盾しない。
- 第4回セッションでDRM側が3枚のバッファをローテーションしていること(`672/674/675`)を確認済み、かつ`EGL_SWAP_BEHAVIOR=EGL_BUFFER_DESTROYED`（バッファ内容がスワップ間で保持されない）ことも確認済み。**`on_draw`が一時的にno-opの間はどのバッファにも新規コンテンツが乗らず、ローテーション中の他バッファも空のまま流れ続ける**ため、単発の`kmsgrab`キャプチャが「たまたま正しく描画された1/3のタイミング」を捉えられず「空/背景のみ」ばかり観測されていたのだとすれば、これまでの全結果と整合する。
- 第5〜6回セッションで試した「gdb注入による強制再描画ワークアラウンド」が最小アプリでは効いたのに実機`race_capture`では一切効かなかった理由も、**`WindowPatch`が`Window.on_draw`/`update_viewport`を自分の管理下に置いて頻繁に上書きしている**なら説明がつく（注入したコールバックが`Window.canvas.ask_update()`等を呼んでも、実際の描画エントリポイントである`on_draw`自体が`WindowPatch`のno-opラムダに握られていれば、いくら「再描画をリクエスト」しても意味がなかったことになる）。
- ただし**この仮説はまだ検証していない**。特に「リサイズイベントが本当に継続的・周期的に発生し続けているのか（単発の14秒後の1回だけなのか）」「`Window.on_draw`が実際に長時間no-opラムダのままになっているのか」は未確認。次回セッションの最優先事項とする。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/egl_interpose.c` / `.so`：単純なLD_PRELOADフック（v1、失敗版だが原理を示す参考として残置）
- `/tmp/egl_interpose2.c` / `.so`：`dlsym()`フック版（v2、動作確認済み）。次回もそのまま`LD_PRELOAD=/tmp/egl_interpose2.so`で再利用可能
- `/tmp/egl_interpose2.log`：v2フックで取得したEGL呼び出しログ（今回の主要な証拠）
- `/tmp/race_capture_egltest2.log`：interposer v2適用時の`race_capture`本体の標準出力ログ（`WindowPatch`のログ行を含む）
- `/tmp/windowpatch_disasm.txt`：`autosportlabs/monkey_patches/window.pyc`の逆アセンブル結果
- いずれも`/tmp`配下のため次回リブートで消滅する想定。`~/decompile_4-4-2/`（既存、前回までの成果物）は今回も無傷で再利用できた
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み。gdb等の注入は一切行っておらず（今回はLD_PRELOADベースの手法のみで、gdb infcallのリスクを回避できた）、プロセスの停止・再起動はいずれも「kill→15秒待機→watchdog自動復旧」という確立済みの安全な手順のみを使用した

**次回の最優先調査候補（優先度順、更新）**：
0. **最優先：`Window.on_draw`/`Window.update_viewport`が実際に`WindowPatch`のno-opラムダへ差し替わっている時間帯があるか、gdb Python注入（`set scheduler-locking off`必須、既存の安全な手順を使用）で`Window.on_draw.__module__`等を数秒間隔で複数回サンプリングして確認する。あわせて、リサイズイベント自体が起動後も継続的に発生し続けているか（`_on_resize`にログ埋め込み、または`~/racecapture.log`の`WindowPatch: Window resize detected`行の出現頻度で確認）を突き合わせる。** → **今回のセッション(第9回)で実施・完全否定（下記参照）。**
1. ~~上記が確認できれば、`WindowPatch`を無効化する検証を行う~~ → **仮説自体が否定されたため不要に**。
2. `eglCreateWindowSurface`が2回目に呼ばれる「起動14秒後」のタイミングと、リサイズイベント・ESP32接続シーケンス（`capabilities`タイムアウトのリトライ間隔）との相関を確認する。→ リサイズが一度も起きていないと判明した今、この相関調査自体の前提が崩れたため優先度を下げる。
3. `eglChooseConfig`が呼ばれていない件（config選択の実際の経路）は優先度低のまま。

---

**今回のセッション（4-4-2続き・第9回）で得た知見：WindowPatch仮説を完全否定、on_draw/flipは高頻度で正常動作と確認、そして新たな重大インシデント（gdb連続注入によるGILデッドロック）が発生・復旧**：

**接続情報の補記**：`rc-dash-3b`へのSSH接続は今回も正常（`ntakao@rc-dash-3b.local`、鍵`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`）。セッション開始時、放置プロセスはなく`race_capture`（PID 1581、watchdog経由）が正常稼働中だった。

**1. 🔴 WindowPatch仮説（前回セッションの最有力仮説）を完全否定**：
`~/racecapture.log`（`log_level=debug`のまま）を精査したところ、`_on_resize`/`_restore_drawing`はいずれも明示的なdebugログ（`WindowPatch: Window resize detected - {w}x{h}` / `WindowPatch: Resize operation completed`、逆アセンブル済みソースから確認）を持つにもかかわらず、起動から13分以上（21450行のログ全体）を通じて**一度もこれらのログが出現しなかった**（`apply_window_patch`実行時の`Applied window resize patch`が1回出るのみ）。gdb Python注入（`set scheduler-locking off`使用、安全な既存手順）で直接確認したところ、`Window.on_draw is wp._original_on_draw` → `True`、`wp._restore_drawing_trigger.is_triggered` → `0`と、**リサイズイベントは一度も発火しておらず、`Window.on_draw`は常にオリジナルのままだった**ことが確定した。「WindowPatchが継続的にリサイズを検知しon_drawを無効化し続けている」という前回の仮説は、この環境（`race_capture`単体起動、外部からのウィンドウリサイズ操作なし）では成立しないことが判明した。

**2. 🎉 `on_draw`/`flip`（実際のバッファスワップ）はいずれも高頻度で正常に呼ばれ続けていることを実測で確認**：
`Window.on_draw`と`Window.flip`をそれぞれgdb Python注入でカウンタ付きラッパーに置換し、数秒間隔で2回読み取ることで呼び出し頻度を実測した。`on_draw`は約5〜7秒間で444回（約70Hz）、`flip`は約10秒間で245回（約24〜25Hz）と、**いずれも実用的な頻度で継続的に呼ばれ続けている**ことを確認した。これは「Kivyが再描画自体をスキップしている」という単純な仮説（セッション5〜6で検証してきた方向）に対する新たな反証材料であり、少なくともイベントディスパッチのレベルでは描画ループは正常に回り続けている。

**3. 🔴⚠️ 重大インシデント：短時間の連続gdb attach/call注入により、メインスレッドが`Texture.blit_buffer`内でGILデッドロックに陥り、レンダーループが完全停止する事故が発生**：
上記2の計測を行うため、短時間（数分間）に合計8回程度のgdb attach/PyGILState_Ensure/PyRun_SimpleString/PyGILState_Release/detachサイクルを実行した。その後、`flip_count`/`on_draw_count`の値を2度連続で読み取ったところ、**約6秒の間隔を空けたにもかかわらず値が完全に同一のまま**（`flip_count=245 ondraw_count=2679`が変化しない）だった。心拍テスト（`Clock.schedule_interval`で0.1秒ごとに発火するはずのコールバック）も8秒間で0回しか発火せず、**Kivyのイベントループ自体が完全に停止していた**ことを確認した。一方でCPU使用率は108%と高いままで、`ps -T`でスレッド別に確認するとメインスレッド（TID=PID）のみが75%前後を消費し続けていた。`bt`（Cレベルのバックトレース）を2回連続で取得したところ、**全く同一のアドレス**（`pthread_cond_timedwait` → `PyEval_RestoreThread` → `Texture.blit_buffer`のGL呼び出し前後のnogilセクション境界）で静止していることを確認し、**真性のデッドロックと確定**した。
- **原因の推測**：セッション6で確立済みの「gdb infcallは選択中スレッド（今回は常にメインスレッド）に割り込んで実行される」という性質上、メインスレッドがちょうど`Texture.blit_buffer`のnogilブロック（テクスチャアップロードのGL呼び出し中、GIL解放中）にいたタイミングでgdb callによる割り込みが発生すると、GILの内部状態（スレッドローカルな保持カウンタ等）が破壊され、後続の`PyEval_RestoreThread`が永久に返ってこなくなると考えられる。8回中のどこかで運悪くこのタイミングに重なったものと推測される。`scheduler-locking off`は「他スレッドを停止させない」対策であり、この种類の「メインスレッド自身への割り込みタイミング事故」は防げないことが今回判明した。
- **対処・復旧**：`sudo kill -9 <PID>`でプロセスを強制終了し、watchdog（`run_racecapture_rpi.sh -w 1`）による自動再起動を確認（新PID、正常稼働・RCPAPI通信ログも正常に流れていることを確認済み）。実機は正常な状態に復旧済み。
- **⚠️ 今後の必須運用ルール（次回以降のセッションで厳守）**：**同一プロセスへのgdb attach/call注入は、短時間に何度も繰り返さず、可能な限り「1回のattachで複数の目的を完結させる」設計にすること**（Pythonスクリプト内で`time.sleep()`を使い、GILを解放しながら一定時間ポーリング・ログ収集を行うなど）。やむを得ず複数回に分ける場合も、可能な限り間隔を空け、各回の後に`ps -T -p <PID>`でメインスレッドのCPU使用率・状態が異常でないか確認する習慣をつけること。

**この事故が示唆する副次的な仮説（未検証、次回の調査候補として記録）**：
今回のデッドロックは外部からの人為的な割り込み（gdb call）が引き金だったと考えられ、通常運用下で自然発生する現象ではないと推測される。ただし、`Texture.blit_buffer`のnogilセクション境界という**GIL関連の脆弱なポイントが実際に存在する**ことが図らずも判明した。もし将来的に「文字が全く表示されない」バグの原因調査で他の仮説が尽きた場合、「通常運用下でも何らかの理由（他スレッドの長時間GIL保持等）でテクスチャアップロード処理が完了しないまま滞留するケースがないか」を调べる方向性もあり得るが、現時点では優先度の低い推測に留める。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`race_capture`は新PID（watchdog経由の自動復旧後）で正常稼働中。今回の調査で作成した一時ファイル（`/tmp/probe_ondraw.py`、`/tmp/inject_counter.py`、`/tmp/inject_flipcounter.py`、`/tmp/inject_heartbeat2.py`、各種`/tmp/gdb_*.txt`、`/tmp/kmscap9/`等）は`/tmp`配下のため次回リブートで自然に消える想定。実機に恒久的な変更は加えていない。

**次回の最優先調査候補（優先度順、更新）**：
0. ~~`window_sdl2`のCython実装（`.so`）を`objdump`等で静的解析~~ → 静的解析ではなく、下記の新手法（LD_PRELOADベースのバックバッファ直接読み取り）でより直接的な証拠が得られたため、この方向は保留。
1. **最優先：Setup画面からHome画面（Dashboard）へ実際に遷移させた状態で、下記のLD_PRELOADベースのバックバッファ直接読み取り手法を使い、メイン画面のコンテンツ（Label/MDIcon等）がスワップ直前のバックバッファに正しく描画されているかを確認する**。詳細は下記セッション記録参照。
2. `eglChooseConfig`が呼ばれていない件（config選択の実際の経路）は引き続き優先度低。

---

**今回のセッション（4-4-2続き・第9回、後半）で得た知見：LD_PRELOADベースの新しい安全な調査手法を確立、スワップ直前バッファにtoastが完璧に描画されていることを画像で実証**：

**背景**：本セッション前半（上記参照）でgdb call注入によるGILデッドロック事故が2回連続で発生したため、以降はgdbを使わない静的解析・LD_PRELOADベースの手法に方針転換した。

**1. 🎉 `egl_interpose2.c`（第8回セッションで確立済みのdlsymフック）を拡張し、`eglSwapBuffers`直前に`glReadPixels`でバックバッファの中身を直接読み取り、色のヒストグラムと実画像（PPM形式）を保存する`egl_interpose3.c`を新規作成**：
`GLES2/gl2.h`をインクルードし、`my_eglSwapBuffers`内で`glGetIntegerv(GL_VIEWPORT,...)`でサイズを取得した上で`glReadPixels`を実行、透過(0,0,0,0)・既知の背景色(18,18,18,255)・それ以外(other)の3種類にサンプリング分類してログに記録する機構を実装（`/tmp/egl_interpose3.c`、コンパイル済み`.so`を実機に保存済み）。当初は毎フレーム`glReadPixels`していたところ大幅なフレームレート低下を招いたため、最終版では離散的なチェックポイント（swap#2,5,10,20,40,80,150,250,400,600,900,1300,1800）でのみ読み取るよう調整した。

**2. 手順（LD_PRELOADによる安全な検証、gdb不使用）**：`sudo kill`でwatchdogスクリプト本体（`run_racecapture_rpi.sh`）とrace_capture本体の両方を停止 → `LD_PRELOAD=/tmp/egl_interpose3.so ./race_capture ...`で手動起動（バックグラウンド、ログを別ファイルへ） → 一定時間後`sudo kill -9`で停止 → `nohup ./run_racecapture_rpi.sh -w 1 -- ...`でwatchdogを再起動、という一連の流れを複数回繰り返した。gdbのattach/detachは一切使用しておらず、今回のようなデッドロックのリスクは無い。

**3. 🔴🎉 決定的な発見：スワップ直前のバックバッファに`"Session recording started"`というtoastの文字が、アンチエイリアス込みで完璧に描画されていることを実際の画像として確認**：
起動から約24〜25秒後（swap#9〜#12付近）に、サンプリングで「other」ピクセル（158サンプル、実ピクセル数約8000強）が複数フレームにわたって継続的に検出された。該当フレームのPPM画像をダウンロードし、非黒領域のバウンディングボックス（画面下部中央、x=862-1056, y=950-992付近）を切り出してPNG化・目視確認したところ、**`"Session recording started"`という文字列が完全に判読可能な形で、実際にKMSへスワップされる直前のバックバッファに正しく描画されていた**。これは、これまで`Window.screenshot()`という間接的な読み取り経路でしか確認できていなかった「文字描画パイプラインは正常」という知見を、**実際にハードウェアへ渡される直前のバッファの直接読み取り**によって、より強い証拠で裏付けるものである。第8回セッションで発見した「toastはWindow直下の別描画経路（ModalView系）を使う」という知見とも整合し、**toastに関しては、アプリ側の描画からEGLのスワップまでの経路全体が完全に正常であることが実証された**。

**4. ⚠️ 一方、90秒間・最大900回のスワップを観測してもメイン画面（Home/Dashboard）への遷移が確認できず、背景色矩形(18,18,18,255)すら一度も出現しなかった**：
ESP32(`/dev/ttyACM0`)は接続済み・RCPAPI通信（`Tx: {"s":0}`等の定期ポーリング）も正常に継続していたが、ログの最後は`Load .../setup/background_intro.jpg`（Setup画面のイントロ背景画像ロード）で止まっており、**Setup画面から抜けていない可能性が高い**。これまでの複数セッションで確認してきた「背景色矩形(18,18,18,255)は常に正しく描画される」という観測は、実際にはHome画面（Dashboard）到達後の話であった可能性があり、**Setup画面自体はそもそも全画面背景矩形を持たないUIデザインである可能性**が新たに浮上した。ヘッドレス環境（マウス/タッチ入力なし）ではSetup画面のフロー（デバイス検出確認→ユーザーによる次へ操作等）を自動で通過できず、Home画面まで到達できていないと推測される。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/egl_interpose3.c` / `.so`：バックバッファ直接読み取り＋画像保存機能付きのdlsymフック（次回もそのまま`LD_PRELOAD=/tmp/egl_interpose3.so`で再利用可能。現状は離散チェックポイント版・`other>20 || bgcolor>20`の時のみPPM保存する設定になっている）
- `/tmp/rebuild_egl3.py`：`egl_interpose2.c`から`egl_interpose3.c`を再生成するPythonパッチスクリプト（コード修正時の再現用に保存済み）
- `/tmp/race_capture_egltest3.log`〜`egltest7.log`：各回の手動起動時のrace_capture標準出力ログ
- `/tmp/swapframe_*.ppm`：保存された生画像（次回リブートまたは`/tmp`クリーンアップで消滅する想定、重要なものは`swapframe_009_crop.png`としてローカルにダウンロード済み・toast文字列を確認済み）
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み（新PID、gdb等の注入は一切残っていないクリーンな状態）

**次回の最優先調査候補（優先度順、更新）**：
0. ~~何らかの方法でSetup画面を通過しHome画面（Dashboard）へ到達させる~~ → **今回のセッションで手順を確立（下記参照）**。
1. **最優先：確立した手順でHome画面へ遷移させた上で、Home画面遷移後に`eglSwapBuffers`（≒`Window.flip`）が全く呼ばれなくなる現象の原因を特定する**。詳細は下記セッション記録参照。
2. `eglChooseConfig`が呼ばれていない件は引き続き優先度低。

---

**今回のセッション（4-4-2続き・第9回、さらに後半）で得た知見：Setup→Home画面遷移の手順を確立、しかし遷移後に`eglSwapBuffers`が完全に停止するという新たな謎を発見**：

**1. 🎉 gdb Python注入により、Setup画面からHome画面への遷移手順を確立**：
逆コンパイル済みソース(`racecapture/views/setup/setupview.py`、`/tmp/setupview_disasm.txt`に逆アセンブル結果保存済み)を解析し、以下の遷移ロジックを完全に復元した：
- `SetupView.on_skip()` → `_skip_request()` → `confirm_popup("Skip", "Continue setup next time?", confirm_skip, cancel_text="NO THANKS")`でダイアログ表示
- ダイアログの`buttons_and_callbacks['OK']['callback']`を直接呼ぶとダイアログが`dismiss()`され、`_setup_complete(skip)`が呼ばれる（`UserPrefs.set_pref("setup","setup_enabled",...)`保存を実測で確認）
- `_setup_complete`は`Clock.schedule_once(lambda dt: self.dispatch('on_setup_complete'), SETUP_COMPLETE_DELAY_SEC=1.0)`を登録するのみで、実際の画面遷移トリガーは`on_setup_complete`イベントのdispatch
- **`screen.dispatch('on_setup_complete')`を直接呼び出すことで、`sm.screen_names`が`['setup']`→`['setup', 'home']`、`sm.current`が`'setup'`→`'home'`へ実際に変わることを確認**（実機実証済み）。この一連の操作は実機の設定ファイルには影響せず、実験用の一時プロセス（本番watchdogとは別、既にkill済み）のメモリ内状態のみに作用する。なお`SetupView.on_skip()`は実UI上ではツールバーの「EXIT」ボタン(`LabelIconButton id=next`)の`on_release`にバインドされている（`.kv`定義より判明）。

**2. 🔴🔍 新たな謎：Home画面遷移後、`eglSwapBuffers`が完全に停止する（呼ばれなくなる）現象を発見**：
`egl_interpose3.so`のログでスワップ回数を監視したところ、Setup画面表示中に`swap#2`まで到達した後、上記の手順でHome画面へ遷移させ、`app_icon_512x512.png`のロードなどHome画面のアセット構築が進行しているログも確認できたにもかかわらず、**`swap#3`以降が一度も記録されなかった**（15秒以上待っても`swap#2`のまま）。念のため`Window.canvas.ask_update()`→`Window.dispatch('on_draw')`→`Window.dispatch('on_flip')`を明示的に注入して強制的に描画・スワップを促したが、それでも`eglSwapBuffers`は一度も呼ばれなかった。
- ⚠️ **重要な留保**：今回の実験環境ではESP32のシリアルポートオープンが`[DEBUG] [RCPAPI] Port not open...`で失敗し続けており（原因未特定、複数回のプロセス起動・killを繰り返したことによるポートの一時的な専有状態の可能性がある）、これが本番運用（ESP32接続済み）とは異なる特殊な状態だった可能性が高い。本セッション前半で確認した「on_draw ~70Hz、flip ~24Hz」という高頻度動作は、ESP32接続済み・RCPAPI通信が継続している本番watchdogプロセスに対する計測だったため、**「on_draw/flipの高頻度呼び出しは、実はClock.schedule_intervalによるRCPAPI通信ポーリングが間接的にトリガーしている可能性がある」という新しい仮説**が浮上した。この仮説が正しければ、ESP32との通信が確立できない状態（あるいは何らかの理由でポーリングが止まる状態）でHome画面に遷移すると、レンダーループ自体が実質的に停止し、その結果としてGPU上には正しい内容が構築されても実際の画面には一切反映されない、という一連の症状（本タスクでこれまで観測してきた全ての症状）を統一的に説明できる可能性がある。**ただし今回はこの仮説を裏付ける決定的な証拠は得られておらず、次回の最優先検証事項とする**。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/setupview_disasm.txt`：`setupview.py`の完全な逆アセンブル結果（Setup→Home遷移ロジックの参照用、次回も再利用可）
- `/tmp/probe_sm.py`、`/tmp/probe_setup.py`、`/tmp/probe_skip.py`、`/tmp/probe_dialog.py`、`/tmp/probe_dialog2.py`、`/tmp/click_ok.py`、`/tmp/dispatch_complete.py`、`/tmp/force_flip.py`：一連の調査用インジェクションスクリプト（Setup→Home遷移の再現手順として次回も再利用可能）
- ⚠️ **二重起動インシデントが再発**：実験用プロセスを起動する際、誤って本番watchdog（PID 3423）を停止せずに新規プロセス（PID 3480）を追加起動してしまい、一時的に二重起動状態になった。数秒以内に気付いて実験用プロセスのみをkillし復旧させたが、**セッション6で警告されていた同じ種類の事故が今回も発生した**。今後は実験用プロセスを起動する前に必ず`ps -ef | grep race_capture`で本番プロセスの有無を確認し、確実に停止してから実験用プロセスを起動する手順を徹底すること。
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み（新PID、実験用の注入は一切残っていないクリーンな状態）

**次回の最優先調査候補（優先度順、更新）**：
0. **最優先：ESP32のシリアルポートが正常にオープンできる状態（本番watchdogを止めてから実験用プロセスを起動する等、ポート専有状態を正しくクリーンにした上で）でHome画面まで遷移させ、その状態で`eglSwapBuffers`が正常に呼ばれ続けるか確認する**。もし正常に呼ばれるなら「RCPAPI通信ポーリングが間接的にレンダーループを駆動している」仮説が支持され、真因は「ESP32との通信が何らかの理由で不安定になるとレンダーループが停止する」という方向に絞り込める。**本セッションで一度試行したが、下記の新しいgdb安全事故によりデッドロックし未達に終わった。次回は`timeout`を使わない、あるいは十分に長いタイムアウトでgdb callを実行すること。**
1. 上記が確認できたら、`egl_interpose3.so`のバックバッファ直接読み取り手法で、Home画面のメインコンテンツ（Label/MDIcon等）が実際にスワップされるバッファに描画されているかを確認する（本セッション未達のまま持ち越し）。
2. `eglChooseConfig`が呼ばれていない件は引き続き優先度低。

**今回のセッション（4-4-2続き・第9回、最終盤）で得た決定的な知見：gdbを使わない安全な注入手法を確立し、Home画面のコンテンツが実際には一切描画されないことをクリーンに実証**：

**1. 🎉 gdbのライブアタッチを使わず、`LD_PRELOAD`ライブラリ自身の中からPython C APIを呼ぶ、新しい安全な注入手法を確立**：
`egl_interpose3.c`を元に`egl_interpose4.c`を作成し、`my_eglSwapBuffers`内（`swap_count==3`の時点で一度だけ）で`PyGILState_Ensure()`→`PyRun_SimpleString("exec(open('/tmp/setup_to_home.py').read())")`→`PyGILState_Release()`を呼ぶよう改造した。`Python.h`は実機に無かったため、`PyGILState_Ensure`等の関数を自前でプロトタイプ宣言するだけでコンパイル可能（実体は起動時に既にロードされている`/opt/racecapture/_internal/libpython3.11.so.1.0`にリンカが自動解決する）。
**この手法は、外部のgdbプロセスがメインスレッドの実行を任意のタイミングで横取りする（今回セッションで3回のデッドロック事故を起こした元凶）のとは異なり、対象プロセス自身のレンダースレッドが、まさに`SDL_GL_SwapWindow`呼び出し前後のGIL解放/再取得の作法(`PyEval_SaveThread`/`PyEval_RestoreThread`)を経る、その同じ場所・同じスレッドの通常の呼び出し経路の一部としてPythonコードを実行する**ため、GIL状態を破壊するリスクが本質的に低い。実際、この手法でSetup→Home遷移（`screen.on_skip()`→ダイアログOKコールバック→`dispatch('on_setup_complete')`）を実行したところ、1.7秒程度で正常に完了し、デッドロックは一切発生しなかった。**今後、この種のライブ注入が必要な場合はこの手法を最優先で使うこと。**

**2. 🔴🎉 決定的な実証：ESP32通信が正常な状態でHome画面へ遷移させると、`eglSwapBuffers`はスワップ#150まで継続して呼ばれ続けるにもかかわらず、Home画面のコンテンツ（背景矩形すら）は一切バックバッファに描画されないことを確認**：
本セッション前半の「Home画面遷移後にeglSwapBuffersが完全停止する」という観測は、**ESP32のシリアルポート競合（本番watchdogを完全に停止しないまま実験用プロセスを起動していたことによる`Port not open`状態）が原因だった**ことが今回判明した。今回はwatchdog・本番プロセスを確実に停止し`fuser /dev/ttyACM0`でポートの完全解放を確認してから実験用プロセスを起動したところ、ESP32との通信（RCPAPI）が正常に確立し、この状態でHome画面へ遷移させたところ、**`eglSwapBuffers`はswap#150（起動から約90秒後）まで継続して呼ばれ続けた**（＝レンダーループ自体は正常に回り続けている）。
にもかかわらず、`egl_interpose4.so`によるバックバッファ直接読み取りでは、**swap#40, #80, #150のいずれでも背景色矩形(18,18,18,255)すら一度も出現せず、完全に透過(0,0,0,0)のみ**という結果だった（唯一の例外はswap#10, #20で検出された、Setup時と全く同じ`"Session recording started"`というtoast文字列のみ）。これにより、**「Home画面のメインコンテンツ（背景矩形・Label・MDIcon等）が、レンダーループ自体は正常に回り続けているにもかかわらず、実際にスワップされるバッファには一切乗ってこない」**という、本タスク全体の核心的な症状を、gdbのハングリスクなしで、かつ確定的な証拠（実画像・スワップ継続ログ）とともに再現・実証することに成功した。
- **これにより、以下の可能性が排除された**：①「Home画面へ実際には到達していない」（→到達を実証済み）、②「ESP32通信の問題でレンダーループ自体が止まっている」（→スワップは継続していることを実証済み）、③「WindowPatchによるon_draw無効化」（→前半のセッションで完全否定済み）。**残る焦点は、「on_draw/canvas.draw()自体は呼ばれ続けているはずなのに、なぜHome画面のウィジェットツリーのColor/Rectangle/テクスチャ命令がGPUへ実際に発行されないのか」という、より狭い範囲に絞り込まれた**。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/egl_interpose4.c` / `.so`：gdb不要でSetup→Home遷移を自動実行する新版フック（`swap_count==3`のタイミングで`/tmp/setup_to_home.py`を実行。次回もそのまま`LD_PRELOAD=/tmp/egl_interpose4.so`で再利用可能。異なる調査をしたい場合は`/tmp/setup_to_home.py`の中身を差し替えるだけでよい）
- `/tmp/patch_egl4.py`：`egl_interpose3.c`から`egl_interpose4.c`を生成するパッチスクリプト（次回の改造のベースとして再利用可）
- `/tmp/setup_to_home.py`：Setup→Home遷移を実行するPythonスクリプト（gdb・LD_PRELOAD両方の注入経路から共通で呼び出せる）
- `swapframe_010_crop.png`をローカルにダウンロード済み（Home画面遷移後もtoastは同じ内容・同じ位置で再現することを確認）
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み

**次回の最優先調査候補（優先度順、更新）**：
0. ~~`egl_interpose4.so`ベースでHome画面のウィジェットツリー・canvas命令を検証~~ → **今回のセッションで実施・完了、決定的な結果を得た（下記参照）**。
1. **最優先：`egl_interpose6.so`（`SDL_GL_GetProcAddress`フックで実描画コマンド発行数を計測する版）がクラッシュした原因を切り分けて修正し、実際に`glDrawArrays`/`glDrawElements`/`glClear`がHome画面で何回呼ばれているかを計測する**。詳細は下記セッション記録参照。
2. **上記が確認できれば、確立した安全な注入経路（gdbではなく`egl_interpose*.so`内Python呼び出し）で、これまでの「force-redraw」系ワークアラウンド（第5〜6回セッションでgdb call経由では効果がなかった手法）を改めて試す**。gdb call特有の問題（GIL状態破壊等）がこれまでの失敗の一因だった可能性を排除できていないため、同じロジックを安全な経路で再試行する価値が高い。
3. `eglChooseConfig`が呼ばれていない件は引き続き優先度低。

**⚠️ 今回のセッション最後に発生した未解決事項：`SDL_GL_GetProcAddress`フックでrace_captureがクラッシュ**：
`kivy/graphics/cgl_backend/cgl_sdl2.so`が全GLES関数ポインタを`SDL_GL_GetProcAddress`経由で動的解決している（`eglChooseConfig`等と同じdlsym的パターン）ことを`objdump -T`で確認し、この関数自体をLD_PRELOADでフックして`glDrawArrays`/`glDrawElements`/`glClear`の呼び出し回数を計測する`egl_interpose6.c`を作成したが、実行したところ**race_capture本体がウィンドウ初期化の途中（ログの最後は`[GL] Using the "OpenGL" graphics system`）でクラッシュし、プロセスごと消滅した**（`dmesg`にはセグフォルト等の記録なし）。原因は未特定（フック関数のシグネチャ不一致、`dlsym(RTLD_NEXT,...)`の呼び出しコスト、`SDL_GL_GetProcAddress`が想定より高頻度・別スレッドから呼ばれている可能性等が考えられる）。実機は`kill`不要でプロセスが既に消滅していたため、`watchdog`を再起動するだけで復旧できた（`egl_interpose6.so`自体は実機に保存済み、`/tmp/egl_interpose6.c`が原因調査のベース）。

---

**今回のセッション（4-4-2続き・第9回、さらに最終盤）で得た最も決定的な知見：Home画面のPython/Kivyレベルの状態は完璧に正常であることを実機で確定**：

**`egl_interpose5.so`（`egl_interpose4.so`に「Home画面遷移後、ウィジェットツリーをダンプする」機能を追加したもの、`swap_count==30`のタイミングで`/tmp/dump_home.py`を自動実行）で、実際にHome画面（`HomePageView`、"Setup"/"Analysis"/"Dashboard"の3ボタンを持つメインメニュー画面、`racecapture.menu.homepageview`モジュール）のウィジェットツリーを再帰的にダンプしたところ、以下が判明した**：
- ウィジェットツリー構造は完全に正常（`HomePageView` → `MDBoxLayout` → `FeatureButton`×3（各"Setup"/"Analysis"/"Dashboard"の`MDLabel`テキスト付き）→ `MDIcon`等）
- **全ウィジェットの`opacity`が漏れなく`1.0`**（非表示になっているものは一つもない）
- **全ウィジェットの`size`が正の値**（0幅/0高さで潰れているものはない、例：`HomePageView`は`[1920, 1040.0]`という正しいフルスクリーンサイズ）
- **`canvas_children`（各ウィジェットのcanvasに登録されている描画インストラクション数）も軒並み1〜17個と、実際に描画命令が構築・登録されている**（例：`MDIcon`は17個、`MDLabel`は13個）
- この状態を確認した直後（swap#40、同一プロセス・同一タイミング）でも、`egl_interpose*.so`によるバックバッファ直接読み取りは**依然として完全に透過(0,0,0,0)のみ**（背景矩形すら無し）

**これにより、本タスク全体を通じて最も重要な結論に到達した**：**「アプリケーション（Python/Kivy/KivyMD）側の状態は、ウィジェットツリー構築・プロパティ設定・canvas命令登録のすべての段階において完全に正常であり、疑うべき箇所はもはや存在しない。真因は、これらの正しく登録された描画命令(`Color`/`Rectangle`/`BindTexture`等の`Instruction`オブジェクト)を実際にOpenGL ES呼び出しとしてGPUへ送出する、`GraphicsCompiler.compile()`/`InstructionGroup.apply()`（Cython実装、`kivy/graphics/*.so`）から`eglSwapBuffers`に至るまでのレンダリングパイプラインの、さらに下位のどこかに確実に存在する」**。これまでの3回のセッション（第7〜8回）で否定してきた各仮説（KivyMD RenderContext/FBO、SDL2バージョン単体、WindowPatch）に続き、今回で「アプリ側の設定・状態管理」という大きな方向性そのものが完全に排除され、焦点は純粋に「描画命令の実発行〜GPU〜スワップ」というレンダリングパイプライン内部（Cython/ネイティブコードレベル）に絞り込まれた。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/tmp/egl_interpose5.c` / `.so`：Setup→Home遷移＋ウィジェットツリーダンプの両方を自動実行する版（`swap_count==3`でHome遷移、`swap_count==30`でツリーダンプ。次回もそのまま`LD_PRELOAD=/tmp/egl_interpose5.so`で再利用可能）
- `/tmp/patch_egl5.py`：`egl_interpose4.c`から`egl_interpose5.c`を生成するパッチスクリプト
- `/tmp/dump_home.py`：Home画面のウィジェットツリーを再帰的にダンプするスクリプト（`opacity`/`size`/`canvas_children`を出力。次回、`canvas_children`の中身（実際のInstructionの型・パラメータ）までさらに深掘りする際のベースとして再利用可）
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み

---

**⚠️ 今回のセッションで発見した3つ目のgdb安全上の教訓（重要、次回以降必読）**：
「ESP32ポートを正しく解放した状態でHome画面へ遷移させる」再試行の際、`set_to_home.py`相当のスクリプトをgdb経由で実行しようとしたところ、`timeout 60 sudo gdb ...`の**bashの`timeout`コマンドがgdbプロセスを強制終了**した（`call`コマンドの実行が60秒以内に完了しなかったと推測される。原因は未特定だが、このスクリプトは複数の関数呼び出し・gc.get_objects()の全走査を含み、単純なping程度のスクリプトより時間がかかる可能性がある）。これにより、**`call PyGILState_Ensure()`の呼び出し自体が完了しないままメインスレッドに割り込まれた状態で残ってしまい**、その後のバックトレースで`pthread_mutex_lock`（`PyEval_RestoreThread`→`PyGILState_Ensure`内部）で完全に静止していることを確認、真性のデッドロックと判定して`kill -9`で復旧させた。
これまでの2つの教訓（①短時間の連続attachによるGIL状態破壊、②今回：`timeout`によるgdbの強制終了でcall呼び出し自体が未完了のまま残ることによるデッドロック）と合わせ、**このrace_capture環境でのgdb call注入は複数の異なる経路でデッドロックを誘発しうる、本質的にリスクの高い手法**であることが今回のセッションを通じて強く示唆された。次回以降は：
- gdb call実行時に`timeout`コマンドを使う場合は、実行内容の複雑さに応じて十分に長い時間（120秒以上）を設定するか、そもそも`timeout`を使わずgdb自体の応答を待つ
- 可能な限り、gdb call注入よりも本セッションで確立した`egl_interpose3.so`（LD_PRELOADベース、gdb不要）のような静的フック手法を優先する
- gdb call注入がどうしても必要な場合は、実行するPythonコードを事前に十分に軽量・高速に完了するものに絞り込む

---

**今回のセッション（4-4-2続き・第10回）で得た知見：前回セッション最後に持ち越した`SDL_GL_GetProcAddress`フックのクラッシュ原因を特定・修正し、Home画面で実際に大量のGL描画コマンドがデフォルトフレームバッファへ発行され続けていることを実測。FBO誤指定・シザークリップの2仮説を新たに否定し、`glClear`の引数異常という新しい手がかりを発見**：

**接続情報の補記（重要、次回以降必読）**：今回のセッション中、`rc-dash-3b.local`のmDNS名前解決がWindows側で断続的に完全失敗する事象が頻発した（`ssh: Could not resolve hostname`。過去セッションの「kill/pkill直後の瞬断は再接続すればすぐ復帰する」という軽微な事象とは異なり、今回は数十秒単位で完全に無応答になることが複数回あった）。`Resolve-DnsName -Type AAAA`で得られるIPv6リンクローカルアドレス（例：`fe80::a169:75dc:2a58:4f16`）に対し、`ssh -o HostKeyAlias=rc-dash-3b.local ntakao@<addr>%10`（`%10`はWindows側のインターフェースindex、`ipconfig`や`Resolve-DnsName`後に確認）の形で接続することで回避できた（`HostKeyAlias`を指定することで、既存の`known_hosts`のホスト名エントリと同じ鍵として検証される）。`scp`の場合は`ntakao@[fe80::...%10]:/path`とブラケットで囲む必要がある。Pi本体は`uptime`で確認した限り再起動しておらず（電源系の再発ではなく）、Windows側のネットワークスタック（mDNS解決 or IPv6近隣キャッシュ）の問題だったと推測される。今回は`Resolve-DnsName`のポーリングで復旧を検知して対処した。

**1. 🔴🎉 前回セッション最後の未解決事項だった`egl_interpose6.so`（`SDL_GL_GetProcAddress`フック版）のクラッシュ原因を特定・修正**：
`strace -f`でクラッシュ箇所を特定したところ、`SIGSEGV`（`si_addr=NULL`、`SEGV_MAPERR`）はSDL2の独自クラッシュハンドラ経由で観測され、実際の原因は`dlerror()`のログ出力で判明した：`dlsym(RTLD_NEXT, "SDL_GL_GetProcAddress")`が**`undefined symbol: SDL_GL_GetProcAddress`としてNULLを返し**、そのNULL関数ポインタをそのまま呼び出していたことがSIGSEGVの直接原因だった。根本原因は、`libSDL2.so`が`_window_sdl2.cpython-311-*.so`から**`RTLD_LOCAL`でdlopenされている**ため、そのシンボルが`RTLD_NEXT`のグローバルスコープ探索から見えないこと（`RTLD_NEXT`はグローバルスコープに参加しているモジュールしか探索できず、`RTLD_LOCAL`でdlopenされたライブラリはたとえロード済みでも対象外という、glibcのよく知られた落とし穴）。同じ仕組みで動いていた`eglChooseConfig`等（第8回セッション確立）が問題なかったのは、あちらは「SDL2自身が`dlsym(handle, name)`を呼ぶ際の`handle`」を横取りして中継する方式（`handle`はSDL2自身の`dlopen`が返した実ハンドル）であり、`RTLD_NEXT`のグローバルスコープ制約を最初から受けていなかったため。**修正**：`dlopen("/opt/racecapture/_internal/Kivy.libs/libSDL2-2-87637523.0.so.0.3000.7", RTLD_NOW|RTLD_NOLOAD)`で既にロード済みのSDL2ライブラリへの実ハンドルを直接取得し（`RTLD_NOLOAD`により新規ロードは発生せず参照カウントのみ増加）、そのハンドル経由で`dlsym`することでスコープ制約を回避した。この修正版（`egl_interpose8.so`〜）は20秒間・swap#400超までクラッシュなしで安定動作することを確認済み。

**2. ⚠️ 副産物として発見：前回セッション（第7回）が「MD5一致で復元済みと確認した」と記録していた`libSDL2`バンドル版ファイルが、実際にはシステムSDL2へのシンボリックリンクのまま放置されていたことが判明**：
`/opt/racecapture/_internal/Kivy.libs/libSDL2-2-87637523.0.so.0.3000.7`が、通常のファイルではなく`/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0`（システムSDL2へのシンボリックリンク）を指すシンボリックリンクになっていた。ただし内容自体は同一ファイル（`.bak_4-4-2`とMD5完全一致：`60689a9cef510e5b73ff3fba29bd3869`）だったため、これまでの検証結果（システムSDL2/バンドル版いずれでも症状不変）への影響はない。`sudo rm`＋`sudo cp -p .bak_4-4-2 → 正規ファイル名`でシンボリックリンクを解消し、通常の実体ファイルへ復元済み（MD5一致を再確認）。**教訓**：ファイル操作を伴う実験の「復元確認」は、MD5だけでなく`ls -la`（シンボリックリンクか実体か）も併せて確認すること。

**3. 🔴🎉 決定的な実測：修正済み`SDL_GL_GetProcAddress`フックで`glClear`/`glDrawArrays`/`glDrawElements`の実発行回数を計測した結果、Home画面で数千回規模の`glDrawElements`が実際に発行され続けていることを確認**：
Setup→Home遷移後、swap#2〜#400にかけて`glDrawElements`は継続的に増加し続けた（swap#40時点で11,048回、swap#400時点で108,638回、1フレームあたり約270回のペース）。`glClear`も1フレームあたり約5回のペースで継続して呼ばれている。これは「レンダーループは回り続けているが、canvas命令が実際にGPU呼び出しとして発行されていないのではないか」という第9回セッション末尾の推測を覆す、初めての直接計測による実証結果である。

**4. 🔴🎉 追加検証：これらの描画コマンドの発行先フレームバッファを`glBindFramebuffer`フックで計測し、ほぼ全て（99.99%以上）がFBO 0（デフォルト＝画面に出るフレームバッファ）向けであることを確認、「オフスクリーンFBO（テキストのグリフアトラス等）への描画がほとんどで、画面向けはごく僅か」という仮説を否定**：
swap#40時点でglDrawElements合計11,048回のうちfb0向けが11,047回（glClear合計202回のうちfb0向けが200回）と、ほぼ全てがデフォルトフレームバッファを対象にしていた。KivyMDがRenderContext/Fbo/InstructionGroupを使わないことは第7回セッションで既に確認済みだが、今回の計測はKivyコア自体の内部FBO使用（グリフアトラス生成等）も実質的に無視できる量であることを示している。

**5. ⚠️ 新たな手がかり：`glClear`の実引数を記録したところ、最後に観測された値が`0x400`（`GL_STENCIL_BUFFER_BIT`のみ）であり、`GL_COLOR_BUFFER_BIT`(`0x4000`)を含んでいないことが判明**：
Home画面の各swapチェックポイントで一貫して`last_clear_mask_fb0=0x400`のみが観測された。カラーバッファを明示的にクリアしていないこと自体が「画面が常に透過のまま」という症状の直接原因かは未確定（十分な量の`glDrawElements`で画面全域を毎フレーム上書きしているなら、クリアの有無自体は本質的でない可能性もある）が、通常のアプリでは考えにくい構成であり、次回優先的に深掘りすべき具体的な手がかりとして記録する。

**6. ⚠️ シザーテスト（スカラー矩形クリッピング）仮説を実測で否定**：
同じHome画面のswapチェックポイントで`glGetIntegerv(GL_SCISSOR_BOX,...)`を照会したところ`(0,0,1024,768)`という、実ウィンドウサイズ(1920x1080)と食い違う値が一貫して観測され、これまで未着手だった「実解像度が1024x768に内部上書きされる現象」（本ファイル4-4-2冒頭の次回候補リストに古くから残っていた項目）との関連を疑い、`glScissor`/`glEnable`/`glDisable(GL_SCISSOR_TEST)`を直接フックして実際の使用状況を計測した。結果、**Home画面描画中に`glScissor`は一度も呼ばれておらず、`GL_SCISSOR_TEST`も常に無効のままだった**（`drawelements_fb0_scissorON=0`、11,047回のfb0向け`glDrawElements`は全てシザー無効時に発行）。よってこの`(0,0,1024,768)`という値は、GLコンテキストの未使用の初期値（初期ウィンドウサイズがこの値だった名残）に過ぎず、実際のクリッピングには関与していないと判明。「解像度1024x768上書き」自体は依然として謎だが、少なくとも今回の画面表示問題（黒画面）の直接原因ではないと切り分けられた。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `/opt/racecapture/_internal/Kivy.libs/libSDL2-2-87637523.0.so.0.3000.7`：シンボリックリンクから通常ファイルへ復元済み（MD5確認済み、内容は変化なし）
- `/tmp/egl_interpose7.c`〜`/tmp/egl_interpose11.c`／対応する`.so`：段階的にクラッシュ修正・GL計測機能を追加していった一連のバージョン。**次回使うなら`egl_interpose11.so`が最新かつ全機能入り**（クラッシュ修正版`SDL_GL_GetProcAddress`フック＋`glClear`/`glDrawArrays`/`glDrawElements`のfb0別カウント＋`glBindFramebuffer`／`glScissor`／`glEnable`／`glDisable`フック＋スワップ時のGL状態ダンプ、`swap_count==3`でSetup→Home自動遷移・`swap_count==30`でウィジェットツリーダンプも内蔵）。ログは全バージョン共通で`/tmp/egl_interpose2.log`（旧バージョンからの名残、ファイル名は変えていない）。
- `/tmp/patch_egl7.py`〜`/tmp/patch_egl13.py`：各バージョンへの差分パッチスクリプト（Pythonの文字列置換ベース、次回の改造のベースとして再利用可）
- いずれも`/tmp`配下のため次回リブートで消滅する想定
- セッション終了時点、`race_capture`は通常のwatchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み（詳細は本セッションの実行ログ参照）

**次回の最優先調査候補（優先度順、更新）**：
0. **最優先：`glClear`が`GL_COLOR_BUFFER_BIT`を含まない件を深掘りする**。具体的には、①この`0x400`という値がフレームの「毎回」なのか「初回のみ」なのか（`my_glClear`のログを間引かず全件記録して確認）、②`glClearColor`の実引数（アルファ値含む）も併せて記録、③このタイミングで実際にバインドされているシェーダープログラム(`glGetIntegerv(GL_CURRENT_PROGRAM)`)・テクスチャ(`GL_ACTIVE_TEXTURE`/`glGetIntegerv(GL_TEXTURE_BINDING_2D)`)を記録し、描画コマンドが有効なシェーダー・テクスチャを伴っているかを確認する。
1. **`glBlendFunc`のRGB側（`GL_BLEND_SRC_RGB`/`GL_BLEND_DST_RGB`、今回はアルファ側しか計測していない）を追加計測する**。もしRGB側が`GL_ZERO,GL_ZERO`のような退化した組み合わせだった場合、描画コマンド自体は正しく発行されていても最終的な色出力が常にゼロになり、今回の症状（発行はされるが画面には出ない）を説明できる可能性がある。
2. 上記いずれでも手がかりが掴めない場合、`glDrawElements`直後（`eglSwapBuffers`を待たず、描画のごく直後）に`glReadPixels`でサンプリングし、「描画命令発行の直後ですら何も反映されていないのか」「スワップ直前になって初めて消えるのか」を切り分ける（現状は毎回swap直前の1点だけしかサンプリングしていない）。
3. `eglChooseConfig`が呼ばれていない件は引き続き優先度低のまま。

---

**今回のセッション（4-4-2続き・第11回）で得た知見：前回セッションの2大仮説（`GL_COLOR_BUFFER_BIT`欠落・RGB側ブレンド異常）をいずれも実測で完全否定。新ツール`apitrace`の導入により、自作LD_PRELOADインターポーザより遥かに安全・高精度な計測手法を確立**：

**接続情報の補記（重要、次回以降必読）**：今回セッション開始時、`rc-dash-3b.local`のmDNS解決がWindows側で完全に機能せず（Bonjour/mDNSサービス自体が見当たらない）、かつ前回記録のホットスポットIP(`192.168.137.162`)へも接続不能という状態から開始した。診断の結果、PC⇔Pi間は直結LANケーブル＋Windows ICS（Internet Connection Sharing、Wi-Fi→イーサネット共有）方式に変更されていたと判明（**Piの無線モジュールが物理的に故障しているための恒久措置、今後もこの接続方式が基本になる**）。イーサネットの物理リンクは終始「Up」だったが、Pi再起動後もICSのDHCPリースが一切払い出されない状態が続き、最終的に**Windows側で「ネットワーク接続」→Wi-Fiのプロパティ→「共有」タブのチェックを一度外して再度入れ直す**操作でICSのDHCPサーバーが再初期化され、Piが`192.168.137.162`でリースを取得して疎通した。**次回以降、同様に`rc-dash-3b.local`のmDNSが引けない場合は、まず`arp -a`で`192.168.137.x`帯を確認し（PowerShellの`Test-Connection`によるpingスイープが有効）、見つからなければ上記のICS共有チェックボックスの入れ直しを試すこと**（Pi本体の再起動は今回は直接の解決には寄与しなかった＝ネットワークが繋がらない場合の切り分けとしてはICS側を先に疑うべきという教訓）。SSH鍵・接続コマンドは`ssh -i ~/.ssh/racecapture_dash_ed25519 -o HostKeyAlias=rc-dash-3b.local ntakao@<取得したIP>`（IPが変わるためHostKeyAliasで`known_hosts`の既存エントリと同一視する）。

**1. 🔴🎉 決定的な発見：`apitrace`（Debian trixie公式リポジトリから`apt install apitrace apitrace-tracers`で導入可能、`/usr/lib/aarch64-linux-gnu/apitrace/wrappers/egltrace.so`）を使い、gdb/自作LD_PRELOADインターポーザより遥かに安全・簡便にEGL/GLES全呼び出しを引数付きで記録できることを確認**：
使い方は、①`sudo systemctl stop getty@tty1.service`でtty1のログインセッション（＝現在稼働中の`race_capture`とDRMマスター権限）を停止、②`cd /opt/racecapture && apitrace trace -a egl -o /tmp/rc.trace ./race_capture -c graphics:show_cursor:0 -a -m cursor -c kivy:keyboard_mode:systemandmulti`をSSH経由で（`nohup ... & disown`で明示的にバックグラウンド化・デタッチして）起動、③数十秒稼働させてから対象PIDに`kill -TERM`を送りトレースファイルを確定、④`apitrace dump --grep='<正規表現>' /tmp/rc.trace`で関数名フィルタしつつ引数付きでダンプ、という流れ。gdb infcallのGILデッドロックリスクや、`SDL_GL_GetProcAddress`のRTLD_LOCALスコープ問題（前回セッションで苦労した箇所）を一切気にする必要がなく、`eglGetProcAddress`経由のGL関数解決を`dlopen`フックも含めて透過的に処理してくれる。**次回以降のGL計測は、原則としてこの`apitrace`を第一選択とすべき**（自作インターポーザは`apitrace`で追えない情報（DRM ioctl等）が必要な場合のみ検討）。なお、SSH経由でバックグラウンド起動する際、`nohup cmd & disown; echo DONE`という一つのコマンド文字列をssh経由で送るとプロセス自体は正しくデタッチされる（`PPID=1`に再親化される）にもかかわらずSSHセッション自体がハングし続ける事象を確認した（原因未特定、子プロセスの標準入出力がリダイレクト済みでも発生）。実害はなく、ローカル側のタイムアウトで強制終了して問題ないが、次回は`ssh -f user@host "cmd > log 2>&1"`（`-f`でSSHクライアント自体をバックグラウンド化）を先に試すとよい。

**2. 🔴🎉 「`glClear`が`GL_COLOR_BUFFER_BIT`を含まない」という前回セッションの最有力仮説を完全否定**：
`apitrace dump`で全`glClear`系呼び出しを時系列で確認したところ、**各フレームの先頭で`glClearColor(0.0706, 0.0706, 0.0706, 1)`（アプリのダーク背景色）に続けて`glClear(GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT | GL_COLOR_BUFFER_BIT)`が正しく1回発行されている**ことを確認した。その後、同一フレーム内でネストしたstencilクリッピングウィジェット（`RelativeLayout`/`ScrollView`等）由来と見られる`glClearStencil(0)`+`glClear(GL_STENCIL_BUFFER_BIT)`（stencilのみ）が3〜4回追加で発行されており、**前回セッションの計測（`SDL_GL_GetProcAddressフックで「最後に観測された`glClear`のmask」だけを記録する方式）は、たまたまフレーム末尾に来るこの「ウィジェット単位のstencil専用クリア」を捕捉してしまい、「カラーバッファがクリアされていない」という誤った結論を導いていたことが判明した**（実際にはフレーム冒頭で正しくクリアされている）。この仮説はこれで完全に否定される。

**3. 🔴🎉 「`glBlendFunc`のRGB側が退化した組み合わせ（`GL_ZERO,GL_ZERO`等）になっているのでは」という仮説も完全否定**：
`glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)`・`glBlendFuncSeparate(sfactorRGB=GL_SRC_ALPHA, dfactorRGB=GL_ONE_MINUS_SRC_ALPHA, sfactorAlpha=GL_ONE, dfactorAlpha=GL_ONE)`が起動直後（呼び出し#185/#186）に一度だけ設定されており、以降変更されていないことを確認。RGB側は`GL_SRC_ALPHA`/`GL_ONE_MINUS_SRC_ALPHA`という、通常の半透明合成でよく使われる標準的な組み合わせであり、退化した値ではない。

**4. ⚠️ 副産物：過去セッションから未解決だった「実解像度が1024x768に内部上書きされる現象」の正体が判明（今回の黒画面バグとは無関係と確定）**：
`apitrace dump`で`glViewport`呼び出しを確認したところ、最初の1回（呼び出し#42）だけ`glViewport(0,0,1024,768) // fake`（apitrace自身が付与した"fake"注記＝実際のアプリ呼び出しではなくEGLコンテキスト生成直後の仮の初期値）となっており、以降（#234〜）は実ウィンドウサイズと一致する`glViewport(0,0,1920,1080)`が正しく呼ばれ続けている。つまり「1024x768」はEGLサーフェス生成直後・実際のリサイズイベント反映前の初期プレースホルダ値に過ぎず、アプリ側のバグではない。第10回セッションで見つかった`GL_SCISSOR_BOX`の`(0,0,1024,768)`という値も、同じ理由（GLコンテキストの未使用の初期値）で説明がつき、これで完全に解明・クローズできる。

**5. ⚠️ 未達：`apitrace dump-images`によるバッファ内容の直接画像化は今回失敗、次回への持ち越し**：
`apitrace dump-images -o frame /tmp/rc.trace`は`WAFFLE_PLATFORM=gbm`を指定すれば実行はできる（`surfaceless`は未対応で`unsupported WAFFLE_PLATFORM`エラー）ものの、出力される全PNGが94バイトの実質空画像だった。ログに`could not infer drawable size (glViewport never called)`という警告が出ており、トレース内には実際には正しい`glViewport(1920,1080)`呼び出しが存在するにもかかわらず、`gbm`プラットフォームでのオフスクリーン再生時にサーフェスサイズの自動推定に失敗している模様（ツール側の制約と見られる）。もしこれが動けば、`Window.screenshot()`（正常表示を確認済み）・`ffmpeg kmsgrab`（黒画面を確認済み）に次ぐ**第三の独立した経路でバッファ内容を直接確認**でき、問題がKivy/EGL側かDRM scanout側かの切り分けに強い証拠を追加できる。次回は`glretrace`（`apitrace dump-images`が内部的に使うツール）の直接呼び出しオプションで明示的に`-w 1920 -h 1080`のような幅・高さ指定ができないか確認する。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- `apitrace`・`apitrace-tracers`・`libwaffle-1-0`パッケージを`apt`でインストール済み（**恒久的な変更、次回以降も引き続き利用可能**）
- `/tmp/rc.trace`（約19.5MB、EGL/GLES全呼び出しのトレース、491フレーム分）・`/tmp/frame2*.png`（`dump-images`の失敗出力、94バイトの空画像）・`/tmp/rc_apitrace_stdout.log`：いずれも`/tmp`配下のため次回リブートで消滅する想定
- セッション終了時点、`race_capture`は`sudo systemctl start getty@tty1.service`により通常のtty1自動ログイン→watchdog付きフロー（`run_racecapture_rpi.sh -w 1`）で正常稼働中に復旧済み。gdbや手動プロセスkillは一切使用していない（`apitrace`配下のプロセスへの`kill -TERM`のみ）

**次回の最優先調査候補（優先度順、更新）**：
0. **最優先：`apitrace dump-images`のサイズ推定失敗を解消し、GBM経由オフスクリーン再生でのバッファ内容を画像として直接確認する**（`glretrace`の直接オプション調査、または`--calls`で特定の`eglSwapBuffers`呼び出し直前の`glReadPixels`挿入等の代替手段も検討）。もしここで正常な描画内容が見えれば、「アプリ・GL呼び出しは完全に正常、原因はDRM scanout経路のみ」がほぼ確定する。
1. `glClear`/`glBlendFunc`の仮説がいずれも否定されたことで、焦点は改めてDRM/KMS側（`eglSwapBuffers`が実際にどのGBMバッファ/DRMフレームバッファオブジェクトを渡しているか、`drmModePageFlip`で本当にそのバッファがスキャンアウトされているか）に戻る。`modetest`（`libdrm-tests`パッケージ）や`/sys/kernel/debug/dri/*/state`（`debugfs`、root権限要）で、実際にアクティブなプレーンがどのフレームバッファIDを指しているかを、`race_capture`稼働中に直接確認する。
2. `apitrace`は`-a egl`だけでなくDRM関連の呼び出し自体は追えない（EGL/GLESレイヤーまでのツールのため）。DRM ioctlレベルのトレースが必要になった場合は、`strace -e trace=ioctl`や`drm_info`等の別ツールを検討する。
3. `eglChooseConfig`が呼ばれていない件は引き続き優先度低のまま。

---

**今回のセッション（4-4-2続き・第12回）で得た知見：`apitrace dump-images`のGBMヘッドレスreplayが「最初の`eglSwapBuffers`を一度でも通過すると恒久的に使用不能になる」というツール自体の制限だと特定してこの経路を打ち切り、代わりに`/sys/kernel/debug/dri/0/state`のカーネル一次情報で「KMS/DRMのページフリップ機構自体は完全に正常」と実測で確定。加えて`eglretrace -D`（GL状態JSONダンプ）という新しい調査手法を確立し、アプリが実際にはデスクトップGL 2.1 Compatibility Profileで描画していることを発見**：

**接続情報の補記**：前回セッションで確立した直結LAN＋Windows ICS方式（`192.168.137.162`固定）で今回は特に問題なく接続できた（`arp -a`で即座に発見）。`race_capture`は前回セッション終了時点から`getty@tty1`経由で正常稼働を継続しており（今回セッション開始時点でuptime 1時間17分、`race_capture`自体は今回セッション開始の少し前に再起動された形跡があった）、`/tmp/rc.trace`（前回セッションが生成した19.5MBのapitraceトレース、491フレーム分）も消えずに残っていたため、今回はこれをそのまま再利用した。

**1. 🔴🎉 決定的な特定：`apitrace dump-images`（内部的には`eglretrace`）のGBMヘッドレスreplayは、トレース中で最初の`eglSwapBuffers`を一度でも処理すると、以降のトレース全体にわたって恒久的に`could not infer drawable size (glViewport never called)`となり、32x32ピクセルのフォールバック画像（前回セッションが「94バイトの空画像」と記録していたもの）しか出力できなくなることを突き止めた**：
`--calls`オプションで特定のcall番号範囲だけを指定した場合でも、apitrace/glretraceは常にトレースの先頭からシーケンシャルに全callを再生する（ランダムシークはできない）ため、「最初のswap前（call 200-210）」を指定した場合のみ実際に正しいサイズ（1024x768、Setup画面遷移前のため中身は黒一色）の画像が得られ、「最初のswap後の任意のcall」（swap境界そのものだけでなく、swap後はるか離れた中間フレームのcallでも同様）を指定すると必ず32x32へ縮退することを、複数のcall範囲（`200-210`は成功、`900000-900010`と`1862850-1862869`＝トレース最末尾は失敗）で確認した。**`--driver=sw`（ソフトウェアラスタライザ、llvmpipe）に切り替えても全く同じ32x32縮退が再現した**ため、この制限はGPU/ドライバ側の問題ではなく、apitrace/waffleのGBMプラットフォームにおけるウィンドウサイズ追跡ロジック自体の恒久的な制限（一度でも実スワップが発生すると、それ以降ウィンドウサイズの推定手段を失う）と判断した。この経路は前回セッション末尾で「次回最優先」と位置付けていたが、**ツール側の限界により事実上手詰まりと判定し、今回で打ち切る**。なお、副産物として`apitrace dump-images`が内部的に実行している実バイナリは`/usr/bin/glretrace`ではなく`/usr/bin/eglretrace`であること（`strace -f -e trace=execve`で確認）、および`glretrace`を直接叩くと`WAFFLE_PLATFORM=gbm`を指定していても`error: unable to open display`で即座に失敗する（`libX11`をロードしようとしている形跡がある）のに対し`eglretrace`では正しく`gbm`プラットフォームが使われることも判明した。今後この系統のツールを使う際は必ず`eglretrace`を直接使うこと。

**2. 🔴🎉 最大の成果：`/sys/kernel/debug/dri/0/state`をrace_capture稼働中（Home画面表示中）に直接読み、KMS/DRMのページフリップ機構自体が完全に正常に機能していることをカーネルの一次情報で実測・確定した**：
`sudo cat /sys/kernel/debug/dri/0/state`で全plane/crtcの現在の割り当て状態が確認でき、`plane-3`（`crtc=pixelvalve-2`にバインド）が`race_capture`によって確保された実バッファ（`allocated by = race_capture`）を表示しており、サイズ`1920x1080`・フォーマット`AR24`・`crtc-pos=1920x1080+0+0`と、期待通りの構成になっていることを確認した。さらに0.3秒間隔で8回連続してこの`fb=`値をポーリングしたところ、`672 → 675 → 674 → 672 → 674 → 672 → 675 → 672`と**実際に複数の実バッファ間で継続的にページフリップが発生している**ことを直接確認した（`/sys/kernel/debug/dri/0/framebuffer`でもこれら3枚のfb ID＝672/674/675がいずれも`race_capture`割り当て・1920x1080・AR24であることを裏付け確認済み）。これは、`apitrace`や`ffmpeg kmsgrab`のようなユーザー空間ツールを一切介さない、カーネルドライバ自身の内部状態を直接読む方式であり、前回セッション末尾で最優先候補として残っていた「`eglSwapBuffers`が実際にどのGBMバッファ/DRMフレームバッファオブジェクトを渡しているか、`drmModePageFlip`で本当にそのバッファがスキャンアウトされているか」という疑問に、これまでで最も直接的な形で答えを出した。**結論：KMS/DRMのページフリップ機構は完全に正常であり、「スキャンアウトが古いバッファに固定されている」「ページフリップが起きていない」という仮説は完全に否定される。**

**3. ⚠️ 補足調査：`dmesg`にV3D/DRM関連のGPUハング・フェンスタイムアウト・リセットの形跡が一切なく、クリーンな起動ログのみであることを確認**：
`sudo dmesg | grep -iE 'v3d|drm|gpu.*hang|fence|reset|timeout'`では起動時の正常なドライバbindログ（`vc4-drm soc:gpu: bound ...`等）しか見つからず、実行時のエラー・警告は皆無だった。また`/sys/kernel/debug/dri/0/bo_stats`では、V3D GPU上に841個・約54MBのバッファオブジェクト（うちtile binning用の`binner`だけで16MB）が確保されていることを確認し、GPU自体が実際に相応の規模のレンダリングワークロードを処理していることの間接的な傍証を得た（ただし複数回のサンプリングで値が変化しなかったため、「継続的に新しいジョブが発行され続けている」ことの直接証明にはならない点に注意）。

**4. 🔴🎉 新しい調査手法の確立：`eglretrace -D <call番号> --dump-format=json`で、任意のcall時点でのGL状態全体（全パラメータ・シェーダーソース・uniform値・頂点バッファ内容・カレントテクスチャ）をJSONとして直接ダンプできることを発見した。これは`--calls`によるピクセルスナップショットと異なり、前述の「最初のswap後は縮退する」制限を受けない（swap境界に関係なく常に正しく機能する）**：
Home画面終盤（call 1859085、`glBindTexture(texture=180)`直後の`glDrawElements(TRIANGLES, count=6)`）でこの手法を使い、以下を確認した。
- **アプリは実際にはデスクトップOpenGL 2.1 Compatibility Profileで描画している**（`GL_VERSION`＝`"2.1 Mesa 26.2.0-1~bpo13+0~rpt2"`、`GL_RENDERER`＝`"VC4 V3D 2.1"`、`GL_VENDOR`＝`"Broadcom"`）。固定機能パイプライン関連のパラメータ（`GL_LIGHTING`、`GL_MODELVIEW_MATRIX`等）も全て取得できており、GLESコンテキストではなくデスクトップGLコンテキストが使われていることを示している。KivyはRaspberry Pi環境では一般にGLES2を使う想定であることが多く、これが症状に関係するかは未検証だが、意外な事実として記録する。また、このMesaバージョン（`26.2.0-1~bpo13`、Debian trixieのbackportsパッケージ）は非常に新しい（2026年時点でのバックポート版）ビルドであり、比較的新しいドライバ特有の回帰バグの可能性も排除できない。
- **シェーダーソースはKivyの標準デフォルトシェーダーそのもの**（フラグメントシェーダーは`gl_FragColor = frag_color * texture2D(texture0, tex_coord0);`、頂点シェーダーは標準的なMVP変換）であり、シェーダー自体に異常は見られなかった。
- 同じ呼び出し時点で`GL_STENCIL_TEST=GL_TRUE`・`GL_STENCIL_FUNC=GL_EQUAL`・`GL_STENCIL_REF=1`という設定を確認したため、周辺の`glStencilFunc`/`glStencilOp`呼び出し列を`apitrace dump`で追加確認したところ、`GL_ALWAYS+INCR`（マスク領域へのスタンプ）→`GL_EQUAL+KEEP`（マスク内のみ描画）→`GL_GREATER+DECR`（ポップ）という、Kivyの`StencilPush`/`StencilUse`/`StencilPop`によるネストクリッピングの教科書的なパターンそのものであり、異常な使われ方ではないと判断した（第11回セッションが見つけた「stencilのみクリア」の正体と一致）。

**5. ⚠️ 未達・保留：個別`glDrawElements`呼び出しが実際に描画する頂点座標を、同一フレーム内で6箇所サンプリングしたが、値のばらつきが大きすぎて単純には解釈できず結論を保留した**：
`eglretrace -D`のJSON出力に含まれる`buffers.vertices`は、その呼び出し時点でバインドされている`GL_ARRAY_BUFFER`の**バッファ全体の内容**をそのまま頂点属性のストライドで区切って表示するものであり、そのcallの`glDrawElements`が実際にインデックスバッファ経由で参照する頂点だけに絞り込まれたものではないと判明した。例えばcall 1859085では、バッファサイズ128バイト（頂点属性ストライド16バイト＝8頂点分）に対し実際の描画に使われるインデックスはおそらく6個（`count=6`の三角形2枚）で、ダンプされた8頂点のうち前半4個は妥当に見える値（`vPosition`が(-166,26)〜(-136,44)の30x18の矩形＝同時に確認した30x18のテクスチャサイズと一致、ただし絶対ピクセル座標としては画面左端(x=0)より左＝画面外)だったのに対し、後半4個は明らかに未初期化メモリ由来と見られる値（`NaN`や`1e-26`〜`1e+30`オーダーの非正規化浮動小数点）だった。他の5箇所のサンプルでも同様に、一見妥当な値と明らかなゴミ値が混在し、`modelview_mat`が単位行列のケースとそうでないケースが混在するなど、単純な傾向を見出せなかった。これが「本当に使われる頂点だけを見れば実は全て正常」なのか「実際に使われる頂点自体に異常がある」のかを判別するには、同じcall時点での`GL_ELEMENT_ARRAY_BUFFER`（インデックスバッファ）の実内容を突き合わせる必要があるが、`eglretrace -D`のJSON出力はインデックスバッファの中身を直接含んでいないため、今回は確立できなかった。次回への持ち越し課題とする。

**6. 🔴🎉 課題5を解決：`apitrace dump --blobs`で実際のインデックスバッファ／頂点バッファの生バイト列を取り出し、フレーム内19箇所を正しい手法（実際に使われるインデックス範囲のみ）で再調査した結果、過半数の描画呼び出しが画面内の妥当な座標を持つ「本物のダッシュボード内容」であると確定した**：
課題5で使えなかった`apitrace dump -v --calls=<call> --blobs`（`--blobs`オプションで`glBufferData`の実データをファイルへ書き出せる）を使い、`buffer=415`（前述の30x18アイコン）の元となった`glGenBuffers`/`glBufferData`呼び出し（call 5703-5708）まで遡って実際のインデックスバッファを取得したところ、インデックスは`(0,1,2,2,3,0,0,0)`であり、`count=6`の描画では先頭6個（`0,1,2,2,3,0`）＝頂点0-3のみが使われ、課題5で「ゴミ値」と誤認していた頂点4-7は単に未使用の余剰確保領域（未初期化）だったと判明した。この手法により、フレーム内の`glDrawElements`呼び出し364個から均等に19個をサンプリングし、各呼び出しの`count`引数と実際に使われる先頭`count`個の頂点座標を突き合わせたところ、**19サンプル中11個（約58%）が画面内（0-1920, 0-1080）に完全に収まる妥当な座標を持ち**、うち複数はLINE_STRIP・197頂点（ゲージ・チャートの輪郭線と見られる）で、例えば call 1855764 は `x=[82,1556] y=[1040,1080]`（画面下端の横長要素、ステータスバー等）、call 1858033 は `x=[1830,1902] y=[10,60]`（画面右上の小さな円形要素、丸型ゲージ等）と、実際のダッシュボードUIとして自然な位置・形状だった。残り8個（約42%）は画面外または明らかな未初期化ゴミ値（例：`x=[0, 5.89e+29]`）だったが、これは前述の「余剰確保領域の混入」がこの簡易手法（インデックスバッファを毎回遡らず、先頭`count`個を機械的に採用）でも一部残っている可能性、または実際に画面外にスクロールされたウィジェットが混在している可能性の両方が考えられ、今回は区別できていない。**結論として、「まともな位置・形状を持つ実ダッシュボード内容がGPUへ正しく送出されている」ことがこれまでで最も具体的に確認された**。それにもかかわらず画面には何も表示されないという矛盾が、今回のセッションで到達した最終地点である。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- 今回のセッションは全て`race_capture`稼働中の読み取り専用操作（既存の`/tmp/rc.trace`に対する`eglretrace`/`apitrace`によるオフスクリーンreplay、`/tmp/blobs/`へのバッファ内容抽出、`/sys/kernel/debug/dri/`配下の読み取り、`dmesg`の読み取り）のみで完結しており、`race_capture`本体プロセスやDRM/KMSの状態には一切変更を加えていない（`getty@tty1`の停止・再開も今回は不要だった）。
- `/tmp/state_dump.json`・`/tmp/frametest_sw_*.png`・`/tmp/framemid_sw_*.png`・`/tmp/framemid*.png`・`/tmp/framelast*.png`・`/tmp/summarize_state.py`・`/tmp/survey_state.py`・`/tmp/sample_calls.txt`・`/tmp/blobs/`等、今回生成した検証用の一時ファイルは全て`/tmp`配下のため次回リブートで消滅する想定。
- セッション終了時点、`race_capture`は最初から最後まで中断なく正常稼働を継続していた（`ps aux`でPID 1685が一貫して稼働、GPS/テレメトリ等への影響なし）。

**7. ✅ 補足：「デスクトップGL 2.1 Compatibility Profileで描画している」件は、SDL2側の不具合・想定外のフォールバックではなく、アプリ自身の意図的な選択だったと判明しクローズ**：
トレース冒頭（call 9-40）を確認したところ、アプリ自身が明示的に`eglBindAPI(api = EGL_OPENGL_API)`（デスクトップGL API）を呼び、`eglChooseConfig`の`attrib_list`にも`EGL_RENDERABLE_TYPE = EGL_OPENGL_BIT`（GLESではなくデスクトップGL明示）を指定した上で`eglCreateContext`していることを確認した。つまりGLESへのフォールバック失敗や想定外の挙動ではなく、SDL2（またはKivyのSDL2 window provider）がこのプラットフォームで意図的にデスクトップGLを要求している、通常の設計通りの動作である。次回優先候補1（GLES/デスクトップGLの食い違い調査）はこれでクローズする。

**実機（`rc-dash-3b`）に今回のセッションで加えた変更・生成物（次回セッション用の記録）**：
- 今回のセッションは全て`race_capture`稼働中の読み取り専用操作（既存の`/tmp/rc.trace`に対する`eglretrace`/`apitrace`によるオフスクリーンreplay、`/tmp/blobs/`へのバッファ内容抽出、`/sys/kernel/debug/dri/`配下の読み取り、`dmesg`の読み取り）のみで完結しており、`race_capture`本体プロセスやDRM/KMSの状態には一切変更を加えていない（`getty@tty1`の停止・再開も今回は不要だった）。
- `/tmp/state_dump.json`・`/tmp/frametest_sw_*.png`・`/tmp/framemid_sw_*.png`・`/tmp/framemid*.png`・`/tmp/framelast*.png`・`/tmp/summarize_state.py`・`/tmp/survey_state.py`・`/tmp/sample_calls.txt`・`/tmp/blobs/`等、今回生成した検証用の一時ファイルは全て`/tmp`配下のため次回リブートで消滅する想定。
- セッション終了時点、`race_capture`は最初から最後まで中断なく正常稼働を継続していた（`ps aux`でPID 1685が一貫して稼働、GPS/テレメトリ等への影響なし）。

**次回の最優先調査候補（優先度順、更新）**：
0. **最優先：「画面内の妥当な座標・形状を持つ実コンテンツがGPUへ正しく送出され、KMSページフリップも正常に機能しているのに、画面には背景色しか表示されない」という、これまでで最も強く絞り込まれた矛盾を、GPU（V3D）が実際にそのジオメトリのピクセルを書き込んでいるかどうかのレベルで検証する。** 具体的な候補：(a) 今回確立した`apitrace dump --blobs`によるインデックスバッファ抽出手法を使い、画面内に収まることが確認できた呼び出し（例：call 1855764、1858033）について`glDrawElements`直後に`glReadPixels`でその領域をサンプリングする（LD_PRELOADインターポーザ`egl_interpose11.so`の後継版が必要、`/tmp`は消えているので再構築要。**ライブプロセスへの注入を伴うためリスクがあり、過去セッションでもgdb関連のクラッシュ・GILデッドロックが複数回発生している。ユーザー立ち会いのもとで慎重に実施することを推奨**）。(b) 同じ領域を`ffmpeg kmsgrab`で座標を絞ってキャプチャし、glReadPixels結果と比較する。
1. ~~デスクトップGL 2.1 Compatibility Profile（GLESではない）という意外な事実の深掘り~~ → 今回の課題7でクローズ済み（アプリの意図的な選択と判明）。
2. `apitrace dump-images`/`glretrace`のGBMヘッドレスreplayは、最初の`eglSwapBuffers`を過ぎると恒久的に使用不能になることが判明したため、今後この経路（ピクセルスナップショット目的）への依存は避ける。ただし`eglretrace -D`（GL状態JSONダンプ）・`apitrace dump --blobs`（バッファ実データ抽出）はswap境界に関係なく機能するため、今後も有効な調査手段として活用する。

---

### 4-4-3: X11+VNCでの目視調査時の電源負荷問題 ※記録のみ・要注意
`Xorg` + `x11vnc` + `race_capture`を同時稼働させた状態で、`throttled=0x50005`（アンダーボルテージ再発）が発生し、
システムウォッチドッグ（1分タイムアウト）による強制リブートが発生した。改善後の電源（PD/QC非対応 5V/2.1A固定出力）でも、
この複合負荷には耐えられないことが判明。次回X11+VNCでの調査を行う場合は、より高出力な電源（5V/3A程度）を先に用意するか、
あるいはX11+VNCを使わない別の調査手法（ソースコード読解等）を優先する。

### 4-4-4: 筐体格納・固定 ※未着手
4-4-2の画面表示問題解決後に着手。
