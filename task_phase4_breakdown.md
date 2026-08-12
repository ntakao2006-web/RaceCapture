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

### 4-4-3: X11+VNCでの目視調査時の電源負荷問題 ※記録のみ・要注意
`Xorg` + `x11vnc` + `race_capture`を同時稼働させた状態で、`throttled=0x50005`（アンダーボルテージ再発）が発生し、
システムウォッチドッグ（1分タイムアウト）による強制リブートが発生した。改善後の電源（PD/QC非対応 5V/2.1A固定出力）でも、
この複合負荷には耐えられないことが判明。次回X11+VNCでの調査を行う場合は、より高出力な電源（5V/3A程度）を先に用意するか、
あるいはX11+VNCを使わない別の調査手法（ソースコード読解等）を優先する。

### 4-4-4: 筐体格納・固定 ※未着手
4-4-2の画面表示問題解決後に着手。
