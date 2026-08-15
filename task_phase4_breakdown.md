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

### 4-4-2: 画面表示問題（黒画面）のデバッグ・解決 ※ScreenManagerの初回描画＋画面遷移は恒久修正済み・本番稼働中（第36回セッション）。ToolbarView代替のステータスバー常時表示はHome画面限定で実機実証済みだがDashboard画面では未解決（第37回セッション、下記参照）。次回もタスクID指定は引き続き4-4-2でOK。

**現状（第36回セッション時点）**：`ScreenManager`（メインコンテンツ）が描画されない根本原因は、Mesa VC4 GLドライバが`RelativeLayout`配下の一部ウィジェットを"最後にadd_widgetされた1つ"しか正しく描画しない特性にあると特定済み。恒久修正として、起動から30秒後に`ScreenManager`を`box_layout`から`relative_layout`へ自動的に移し替え、以降は`ScreenManager.current`が変化する（＝画面遷移する）たびに同じ再配置を自動再適用するLD_PRELOAD常駐ライブラリ`scmove_persist.so`を実装し、本番の`run_racecapture_rpi.sh`に組み込み済み。電源投入・アプリ再起動のたびに開発者の手動操作なしで自動的にメインコンテンツが正しく描画され、かつHome→Setup→Dashboard→Homeのような通常のナビゲーション操作を繰り返しても都度正しく描画されることを実機で確認済み（第36回セッションで新規に実証）。`ToolbarView`（画面上部の状態バー）・`NavigationDrawer`は`ScreenManager`本体との共存（＝ウィジェットとして両方を`RelativeLayout`直下に配置し同時にadd_widgetする）は原理的に不可能と確定している。ただし第37回セッションで、`ToolbarView`を`export_as_image()`でFBO経由のスナップショット化し、`ScreenManager`の`canvas.after`へ直接描き足す（新規ウィジェットのadd/remove_widgetを伴わない）手法を発見し、**Home画面では画面遷移を挟んでも確実に機能する**ことを実機実証した。ただし**Dashboard画面では同じ手法が一度も成功しておらず未解決**（原因はDashboardView内部の`Carousel`/`Scatter`系ウィジェットとの干渉が疑われる、詳細は本セクション末尾候補24参照）。逆コンパイルにより、Home画面のタイルボタン（Dashboard/Analysis/Setup）と、アプリ内蔵のキーボードショートカット（`a`=Analysis/`d`=Dashboard/`s`=Setup/`p`=Preferences/`t`=Status、Escapeキーで常にHomeへ）だけで全画面へのナビゲーションが可能なことも判明しており、ステータスバー問題とは独立に実用上は操作可能。
残作業：①**最優先：Dashboard画面でステータスバー重ね描きが機能しない根本原因の特定**（第37回セッション候補0参照）、②実運用（複数回の電源サイクル）での継続的安定性確認、③車載時（キーボードなし・タッチのみ）を見据えたHome画面への「戻る」導線の本番組み込み（実装案は確立済み、第37回セッション候補2参照）、④Mesa GitLabへの`glClear`部分マスクバグ報告（任意、優先度低〜中）。詳細な調査経緯・実装内容は本セクション末尾（第35回セッション候補20、第36回セッション追記、第37回セッション追記）参照。
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

**今回のセッション（4-4-2続き・第13回）で得た知見：`ffmpeg kmsgrab`によるピンポイント領域キャプチャで「画面内の妥当な座標を持つ」と確認済みの2箇所を直接検証したが背景色のみと再確認、`glBindFramebuffer`が全トレース中0回であることを確定しFBO仮説を完全に閉じ、焦点をステンシルテストの実バッファ内容へ絞り込んだ**：

**接続情報の補記**：前回セッションと同じ直結LAN＋Windows ICS方式（`192.168.137.162`固定）で`arp -a`により即座に接続でき、mDNS/ICS関連のトラブルは今回発生しなかった。`race_capture`（PID 1685）はセッション開始時点でuptime約1時間、セッション終了まで中断なく稼働を継続。前回セッションが生成した`/tmp/rc.trace`（491フレーム分）・`/tmp/blobs/`も消えずに残っており、今回も再利用した。今回の全操作は読み取り専用（`ffmpeg kmsgrab`による部分領域キャプチャ、`apitrace dump`、`eglretrace -D`の再実行）で、`race_capture`本体プロセスやDRM/KMS状態、`getty@tty1`には一切変更を加えていない。

**1. 🔴🎉 `ffmpeg kmsgrab`のcropフィルタで、第12回セッションが「画面内に収まる妥当な座標を持つ本物のダッシュボード内容」と特定した2箇所（call 1858033: 画面右上 x=[1830,1902] y=[10,60]の円形要素、call 1855764: 画面下端 x=[82,1556] y=[1040,1080]のステータスバー領域）を、実スキャンアウトバッファから直接ピンポイントでクロップ撮影したが、いずれも背景色（透過黒`(0,0,0,0)`とダーク背景色`(18,18,18,255)`の2色のみ）しか写っておらず、期待されるコンテンツの痕跡は皆無だった**（`sudo ffmpeg -f kmsgrab -i - -vf hwdownload,format=bgra,crop=<w>:<h>:<x>:<y>`で実現、フォーマットはフレームバッファの実フォーマット`AR24`に合わせて`bgra`を指定する必要があった）。これまでの「全画面キャプチャで背景2色のみ」という結果を、GPUコマンドレベルで実際に妥当なジオメトリが送出されていると確認済みの座標にピンポイントで絞り込んだ上で再確認した形であり、「コマンドは正しく発行されているのに、その座標のピクセルは実際には一切書き込まれていない」という矛盾がさらに明確になった。

**2. 🔴🎉 `glBindFramebuffer`が全トレース（約186万コール）中0回であることを`apitrace dump`のグレップで確定し、オフスクリーンFBOへの誤描画・破棄という仮説を完全に閉じた**：これにより、全ての描画は常にデフォルトフレームバッファ（画面に出るFBO 0）へ向けて発行されていることが確定した。

**3. 🔴🎉 `eglretrace -D`（前回セッション確立の手法、`WAFFLE_PLATFORM=gbm`環境変数が必要）で call 1858033（前述の画面右上・円形要素のLINE_STRIP描画）の完全なGLステートをJSONダンプし、以下を確認した**：
   - `GL_DRAW_FRAMEBUFFER_BINDING=0`（デフォルトFB、上記1.と整合）
   - `GL_DEPTH_TEST=GL_FALSE`・`GL_SCISSOR_TEST=GL_FALSE`（`GL_SCISSOR_BOX=[0,0,1920,1080]`で全画面）・`GL_BLEND=GL_TRUE`（標準的な半透明合成）：これらは全て正常で描画を妨げる要因ではない。
   - **`GL_STENCIL_TEST=GL_TRUE`・`GL_STENCIL_FUNC=GL_EQUAL`・`GL_STENCIL_REF=2`・`GL_STENCIL_VALUE_MASK=255`**：この描画は「実際のステンシルバッファ値が2と一致する画素のみ」に限定されている。もしこのピクセル位置のステンシルバッファ実値が2でなければ、GLコマンド上は完全に正常でもフラグメントは静かに破棄され画面には一切反映されない。

**4. ⚠️ call 1858033直前のステンシルPush/Use/Popコマンド列（call 1857780-1858035）を`apitrace dump`で確認したが、コマンドログのレベルでは第12回セッションが確認した「教科書通りのネストクリッピングパターン」と完全に一致しており、異常は見当たらなかった**（`GL_ALWAYS+INCR`でスタンプ描画→`GL_EQUAL+ref+KEEP`で本描画、を入れ子レベルごとに正しく繰り返している）。**コマンド列は正常に見えても、実際にステンシルバッファへ書き込まれた値そのものが正しいかどうかはコマンドログだけでは判定できず**、次の調査対象として残った。

**次回の最優先調査候補（優先度順、第14回セッションでの実機直接操作の結果を受けて更新）**：
0. **最優先：今回ユーザーの実機直接操作で確定した「オーバーレイ系（ナビゲーションドロワー・パネル・ポップアップ・カーソル）は描画される／ScreenManagerのメインコンテンツ領域は描画されない」という境界線を手がかりに、逆コンパイル済みソース（`~/decompile_4-4-2/`）上で両者のウィジェット構造の違いを比較する。** 具体的には、ナビゲーションドロワー（`MDNavigationDrawer`等）がKivyMD内部でどう`Window`に追加されているか（`RelativeLayout`/`ScrollView`等のクリッピングコンテナを経由しないルートcanvas直付けになっていないか）と、`ScreenManager`配下の各`Screen`（Dashboard/SystemStatus/Setup）がどのようなコンテナに包まれているかを突き合わせ、「ステンシルクリッピングを使うコンテナに入っているかどうか」が両者の分岐点になっているかを確認する。ライブ注入なしで進められる分析のため、次回はここから着手するのが効率的。
1. 上記0で「ScreenManager配下だけがクリッピングコンテナに包まれている」ことが確認できたら、そのクリッピングコンテナのステンシル設定（`glStencilFunc`のref値等）が、なぜナビゲーションドロワー等と違って機能不全を起こすのかを`apitrace dump`で突き合わせる。
2. ステンシルバッファの実ピクセル値を直接読み取る方向（`egl_interpose7.so`）は今回0件のまま実機負荷で描画悪化を招いたため保留。再挑戦する場合は、全描画呼び出しへの毎回のステート照会をやめ、事前に対象を絞ったコールカウント一致方式（例：`swap_count`や累積`glDrawArrays`呼び出し回数が特定の値に達した1回だけ`glReadPixels`する）に改良してから行うこと。
3. 今回発見した「単一スキャンライン状の断続コンテンツ」（第14回セッション記録参照）は正体未確認のまま。連続動画キャプチャでの追跡は優先度を下げてよい（0・1の対人観察による絞り込みの方が効率的なため）。

---

**今回のセッション（4-4-2続き・第14回、ユーザー立ち会いあり）で得た知見：ステンシルバッファ直読みインタポーザ(`egl_interpose7.so`)を新規構築・単体検証まで完了したが、実機適用では過負荷により描画がさらに悪化し目的のデータは得られず。代わりに副産物として2つの新しい手がかり（透過黒の見え方の誤解の訂正、および単一スキャンライン状の断続的コンテンツ）を得た**：

**1. `egl_interpose7.c`を新規作成**：`dlsym()`インターセプト方式（第8回セッション確立の安全な手法、gdb不要）で`glDrawArrays`/`glDrawElements`をフックし、直後にステンシルステート（`GL_STENCIL_TEST`/`GL_STENCIL_FUNC`/`GL_STENCIL_REF`）を`glGetIntegerv`/`glIsEnabled`で確認、`GL_EQUAL`かつ`ref=2`の時のみ画面右上領域（x=[1830,1902) y=[10,60)、call 1858033で使われていた座標）を`glReadPixels(..., GL_STENCIL_INDEX, GL_UNSIGNED_BYTE, ...)`でサンプリングしログ出力するLD_PRELOADライブラリ。最大30サンプルでキャップ。dlsymの実体解決には`dlvsym(RTLD_NEXT, "dlsym", ...)`が必要だが、**このPi（Debian trixie、glibc 2.41）では`dlsym`のシンボルバージョンが`GLIBC_2.34`であり、過去環境を想定した`GLIBC_2.2.5`指定では解決に失敗してセグフォルトすることが判明**（`readelf -Ws libc.so.6 | grep dlsym`で確認可能。次回以降、同種のdlsymフックを書く際は両バージョンを試すフォールバックを入れること）。修正後、`race_capture`本体には触れない単体テストプログラム（`dlopen("libGL.so.1")`→`dlsym`→`dladdr`で解決先ライブラリを確認）でフックが正しく作動することを検証してから実機へ適用した。
- `/tmp/egl_interpose7.c`/`.so`：今回作成したステンシル直読みインタポーザ（次回`GLIBC_2.34`フォールバック込みでそのまま再利用可能、ただし下記2の理由で運用には改良が必要）

**2. 🔴 実機へ適用したところ、ステンシルサンプルは26分間で0件のまま、代わりに通常なら安定して描画されるはずのツールバー背景矩形(18,18,18,255)まで描画されなくなり画面が完全に無地の状態になった**：カーネルログ(`dmesg`)にはGPUリセット・アンダーボルテージは一切記録されておらず、プロセスもクラッシュせずESP32との通信も正常に継続していたため、ハードウェア障害ではなく**インタポーザが全`glDrawArrays`/`glDrawElements`呼び出しごとに`glGetIntegerv`×2 + `glIsEnabled`×1を追加で挟んでいるオーバーヘッドが、Pi 3Bの限られた性能下でフレームタイミングを乱し、既存の（別原因による）描画不安定さをさらに悪化させた**と考えられる。目的のステンシル値は結局取得できなかった。ユーザー立ち会いのもと、実機の物理モニタが「何も見えない」状態になったことを確認した時点で切り上げ、プロセスをkillして`LD_PRELOAD`無しのwatchdog付きクリーンな状態へ復元した（`.bashrc`は編集がブロックされたため無傷、実機に恒久的な変更は残っていない）。**次回この方向を再挑戦する場合は、全描画呼び出しに対して毎回ステート照会するのではなく、事前に対象を絞ったコールカウント一致方式など、より低オーバーヘッドな実装に改良する必要がある。**

**3. 🔴🎉 副産物：「透過黒(0,0,0,0)＝実機では黒く見える」を、今回の誤解とその訂正を通じて再確認・補強した**：セッション中、kmsgrabで撮影したPNGを筆者（Claude）が画像ビューアで目視した際、透過(alpha=0)領域が白背景に合成されて「画面が真っ白になった」と誤って報告した。しかしユーザーが物理モニタを直接見て「黒にしか見えない」と指摘し、`PIL`で該当ピクセルのRGBA値を直接ダンプして確認したところ`(0,0,0,0)`（RGBも0、アルファも0）であることが判明した。KMSスキャンアウトはアルファを無視してRGBをそのまま表示するため、物理モニタでは黒く見えるのが正しい。**今後この種のkmsgrab画像を確認する際は、目視ではなく`PIL`等で生のRGBA値を確認すること**（今回のセッションの反省点）。

**4. 🔴🎉 副産物：DRMプレーン一覧（`/sys/kernel/debug/dri/0/state`）を確認したところ、有効なプレーンは`race_capture`が使う1枚（plane-3、fb割当あり）のみで、独立したハードウェアカーソルプレーンは存在しないことを確認**。ユーザーがマウスを実機に接続したところ物理モニタ上に白いマウスポインタが見えたとのことだが、これは起動引数`-m cursor`（Kivy標準の`cursor`モジュール、マウス位置に追従する画像ウィジェットをKivy自身のcanvas上に描画する仕組み）による、**race_captureの通常の描画パス経由**のはずである。もしこのカーソルが安定して表示され続けているなら、「メインコンテンツと同じ描画パスの一部（カーソルはクリッピングコンテナの外側にある可能性が高い）は正常に描画されている」という、ステンシルクリッピング仮説をさらに補強する材料になり得る。**今回はカーソル自体のピクセルを確定的に特定できなかった（下記5の断続コンテンツとの区別が未確認）ため、次回の確認候補として残す。**

**5. 🔴 副産物：kmsgrabによる全画面ピクセルスキャン（生RGBA値をPILで走査、視覚判断に頼らない手法）で、背景2色以外の非背景ピクセルが特定のy座標にのみ出現する現象を発見**：1〜2秒間隔で3回連続撮影したところ、1回目・3回目は完全に同一の内容（同じy座標群`[65, 126, 555, 556]`、同じピクセル数338個）が出現し、間の2回目は完全に無地（0ピクセル）だった。該当ピクセルは高倍率で確認すると、**縦方向にはほぼ1〜2ピクセル分の高さしかない、グレースケールの小さな点・線の断片が水平方向に規則的な間隔で並ぶパターン**で、通常の文字・アイコンの2D形状（複数行にまたがる）とは一致しない。同一内容が再現する点からランダムなキャプチャタイミングのノイズではなさそうだが、正体は特定できていない。**新しい仮説候補：(a) kmsgrabがページフリップ境界の一瞬（走査線の一部だけが新フレームに切り替わった状態）を捉えている「ティアリング」的なキャプチャアーティファクト、(b) 何らかのジオメトリ変換バグでコンテンツの縦方向が潰れて1〜2px高さに退化して描画されている、のいずれか。次回、単発キャプチャではなく短時間の連続動画キャプチャで同じ現象を追跡し、(a)(b)いずれかに絞り込むこと。**

**実機（`rc-dash-3b`）に加えた変更・復元状況（次回セッション用の記録）**：
- `/tmp/egl_interpose7.c`/`.so`、`/tmp/test_gl.c`/バイナリ：今回作成、`/tmp`配下のため次回リブートで消滅する想定
- `.bashrc`編集は自動モードの権限チェックにブロックされ実施されなかった（`.bashrc`は無傷、バックアップファイルも作成されていない）
- セッション中、`race_capture`を2回再起動した：①watchdog経由の通常プロセス(PID 1685)をkillし、`LD_PRELOAD=/tmp/egl_interpose7.so`付きで手動起動(PID 3389、watchdog無し) → ②これをkillし、`LD_PRELOAD`無しでwatchdog付き(`run_racecapture_rpi.sh -w 1`)で再起動(PID 3848)。**セッション終了時点、PID 3848がクリーンな状態（`LD_PRELOAD`無し、watchdog付き、ESP32/GPS通信正常）で稼働中。**

**6. 🔴🎉 決定的な進展：ユーザーが物理モニター・マウスで実機を直接操作し、「どの種類の画面なら描画され、どの種類なら描画されないか」の境界線をクリーンに実証した**：マウス接続後、画面上のボタン位置を勘で推測してクリックしたところ、以下が判明した。
   - ✅ **描画される**：ナビゲーションドロワー（サイドバー、"DASHBOARD"/"ANALYSIS"/"SETUP"/"SYSTEM STATUS"/"EXIT"、アイコン・文字とも完璧に表示。ただし全体的な操作感は重くカクつく）、トラック/セッション管理パネル（"Reset Session"/"Add"/"Save"/"Manage"/"Locked"/"More Settings"、これもアイコン・文字とも完璧）、ローディングポップアップ（スピナー＋"CLOSE"ボタン）、マウスカーソル（`-m cursor`モジュール、カクつくが表示はされる）
   - ❌ **描画されない**：DASHBOARD画面・SYSTEM STATUS画面の中身（ボタンを押しても真っ暗のまま）。SETUP画面についても、ローディングポップアップの"CLOSE"を押すと同じ真っ暗な状態に戻ることを確認（＝ハングではなく画面遷移自体は正常に進んでいるが、遷移先の中身が見えない）。
   
   この結果は、**「`ScreenManager`が画面切り替えで表示するメインコンテンツ領域だけが描画されず、ウィンドウに直接オーバーレイされる系のウィジェット（ナビゲーションドロワー、各種パネル、ポップアップ、カーソル）は正常」という、非常にクリーンな境界線**を示しており、これまで複数セッションかけて追ってきた「ステンシルクリッピング仮説」（ネストしたスクロール領域等のクリッピングに使われるステンシルテストが、メインコンテンツ領域内でのみ機能不全を起こしている）と強く整合する。またサイドバー等の操作感が「乱れはないが遅延はある」点は、描画の可否とは別に一般的なパフォーマンス問題（重い`busy-work`ダミータスク・電源対策によるCPUクロック制限800MHz等）が存在することも示しており、これは「単純な処理能力不足」では説明できない今回の主症状（0か100かの一貫した描画有無）とは区別して記録しておく。

**7. 🔴 上記6を受けて逆コンパイル済みソース（`~/decompile_4-4-2/`）上でウィジェット構造を突き合わせたところ、「ステンシルクリッピング仮説」は単独では説明力不足であることが判明し、「`ScreenManager`の`current`Screenの中に入っているかどうか」という構造的な境界の方がより正確であることが強まった**：
   - `AppMainFrame`の実際のウィジェットツリーを確認：`<AppMainFrame>: RelativeLayout: BoxLayout: ToolbarView(id: status_bar) / ScreenManager(id: main) / NavigationDrawer(id: navigation_drawer)`。**`NavigationDrawer`は`ScreenManager`の外側にある特別な存在ではなく、同じ`RelativeLayout`内の兄弟ウィジェット**（`ToolbarView`と`NavigationDrawer`はいずれも`ScreenManager`の外）。
   - `ScreenManager`の`transition`には明示的に**`NoTransition`が設定されている**ことを確認（`main.py`内`LOAD_GLOBAL (NULL + NoTransition)`）。これにより、`screenmanager.py`内に存在する`RenderContext`/`Fbo`ベースの遷移エフェクト機構は実際には一切使われていないことが確定し、第13回セッションでapitraceが実測した「`glBindFramebuffer`呼び出し0回」と完全に整合した。**FBO関連の仮説はこれで完全にクローズしてよい。**
   - `kivy/uix/screenmanager.py`本体（`real_add_widget`/`real_remove_widget`/`on_current`）を確認したが、標準的なKivyライブラリの素のコードで、`opacity`操作やクリッピングの類は一切なく、疑わしい点は見当たらなかった。
   - **`NavigationDrawer`自体は`FloatLayout`と`StencilView`の両方を継承しており、実は独自のステンシルクリッピングを使っている**（KVコメントに`# stencil boundaries`と明記）。つまり「ステンシルクリッピングを使っているかどうか」自体は描画可否の分かれ目ではない。
   - `DashboardView`は素の`Screen`（`RelativeLayout`）を継承するのみでStencilViewは無し。その子ウィジェットのうち`AnalysisCarousel`は`Carousel`（→`StencilView`）を継承しステンシルクリッピングを使うが、**同じく描画されなかった`TripleGaugeBar`（`BoxLayout`ベース）・`FullCourseFlagIndicator`（素の`Widget`ベース）・`MDLabel`（`dash_notice`）はいずれもステンシルクリッピングを一切使っていない**。それでも実機ではDASHBOARD画面の中身は（カルーセル部分に限らず）全体が表示されなかった。
   
   **結論：「ステンシルクリッピングの有無」では、描画される／されないの境界線を説明しきれないことが今回の調査で判明した。** より正確な境界線は「`ScreenManager`の`current`として表示されるScreenの子孫かどうか」であり、そのメカニズム自体（`ScreenManager`本体のコードは正常と確認済み）はまだ特定できていない。

**次回の最優先調査候補（優先度順、第14回セッション完了時点で更新）**：
0. **最優先：`ScreenManager`配下でだけ描画が壊れる具体的なメカニズムを特定する。** `ScreenManager`自体のコードは正常と確認済みのため、次に疑うべきは(a) `kivy.uix.screenmanager.Screen`（`RelativeLayout`継承）が`AppMainFrame`の外側`RelativeLayout`とネストすることで生じる座標変換（`PushMatrix`/`Translate`/`PopMatrix`）の二重ネストが、このMesa/VC4ドライバで問題を起こしていないか、(b) `Widget.canvas`の親子関係で`current`Screen切り替え時にcanvasの追加順序・グループ分けが崩れていないか（`kivy/uix/widget.py`の`add_widget`/`canvas`まわりを次回確認）、(c) バンドルされているKivyのバージョンに既知の関連issueがないか（バージョン確認と変更履歴の確認）。ライブ注入なしで進められる。
1. どうしても静的解析で決着しない場合は、ステンシルバッファではなく**カラーバッファの実ピクセル値**を`glReadPixels`で、DASHBOARD画面表示中の既知の座標（例：`gauge_bar`領域）に対して1回だけ低オーバーヘッドで読み取る（今回の`egl_interpose7.so`のような毎コールステート照会ではなく、`swap_count`一致等のワンショット方式に改良すること）。
2. 今回発見した「単一スキャンライン状の断続コンテンツ」（第14回セッション前半の記録参照）は正体未確認のまま優先度低で保留。

---

**今回のセッション（4-4-2続き・第15回、実機直接操作・ライブ注入なし）で得た知見：前回の最優先候補0（(a)(b)(c)の静的解析）を実施した結果、いずれも「Kivyライブラリ側の一般的な不具合」としては説明力を持たないと判明し、この方向性を実質的にクローズした**：

**接続情報の補記**：`rc-dash-3b`へのSSH接続（`ntakao@192.168.137.162`、直結LAN＋Windows ICS方式、鍵は`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`）は正常。セッション開始時点で`race_capture`（PID 3848、前回セッション終了時と同一PID）がwatchdog付きクリーンな状態で稼働継続中（uptime約4時間強）だった。今回のセッションは全て読み取り専用操作（`~/decompile_4-4-2/`配下の`.pyc`を`xdis`で解析、GitHub上の本家Kivyソース取得、GitHub issue検索）のみで完結しており、`race_capture`本体プロセスやDRM/KMS状態には一切変更を加えていない（SSH接続も`find`/`strings`/`xdis`による静的解析コマンドのみ）。

**1. 🔴🎉 バンドルされているKivyの正確なバージョンを確定：`kivy/_version.pyc`から`2.3.1`（git commit `20d74dcd30f143abbd1aa94c76bafc5bd934d5bd`、ビルド日`20241226`）と判明**。これは第6〜7回セッションの最小再現実験で使用した`apt`版`python3-kivy`（`2.3.1-1+b1`）と**同一バージョン**であることが判明し、「バンドル版とapt版でKivyバージョンが違うのでは」という潜在的な疑問を解消した。

**2. 🔴🎉 `kivy/uix/widget.py`・`floatlayout.py`・`relativelayout.py`・`screenmanager.py`の実機`.pyc`を、GitHub上の本家Kivy 2.3.1タグのソースと突き合わせ（`co_names`/`co_consts`/関数一覧の構造比較）、いずれも標準ライブラリと完全に一致し独自パッチが無いことを確認した**。`DashboardView`（`racecapture/views/dashboard/dashboardview.pyc`）についても`co_names`を横断検索し、`canvas`/`opacity`/`RenderContext`/`Fbo`のいずれも一切参照していないことを確認。また同ファイルのimport一覧から`DashboardView`は`kivymd.uix.screen.MDScreen`ではなく**素の`kivy.uix.screenmanager.Screen`**をインポート・継承していることも再確認した（前回セッションの逆コンパイル読解結果と整合）。**RaceCapture独自コードがScreen配下で特別な描画操作をしている可能性も排除された。**

**3. 🔴🎉 候補(a)「`PushMatrix`/`Translate`/`PopMatrix`の二重ネスト」を、本家`kivy/graphics/context_instructions.pyx`と`instructions.pyx`のソースで裏付け確認し、仮説としての説得力が大きく低下した**：`<RelativeLayout>`の`canvas.before`（`kivy/data/style.kv`）は`PushMatrix`+`Translate: xy: self.pos`、`canvas.after`は`PopMatrix`という標準パターンだが、これらは**レガシー固定機能GLの`glPushMatrix`/`glPopMatrix`ではなく、Kivy独自のPythonリストベースのソフトウェア行列スタック**（`RenderContext.state_stacks['modelview_mat']`への`push_state`/`pop_state`、単一グローバルな`RenderContext`＝`Window.render_context`を全ウィジェットが共有）であることをソースで確認した。GPU/ドライバ側の行列スタック深度制限とは無関係な、CPU側の単純なリストpush/pop＋行列乗算にすぎず、`ScreenManager`（`FloatLayout`、変換なし）の下で`Screen`（`RelativeLayout`）が1段ネストするだけの構成は、Kivyエコシステムで極めて日常的に使われるパターンである。この機構自体が本件のような「全か無か」の一貫した描画消失を引き起こす可能性は低いと判断した。

**4. ⚠️ 候補(c)「既知issue」をGitHub検索・調査したが、直接関連する既知issueは見つからなかった**：`kivy/kivy#5581`（"Raspberry Pi OpenGL issue with screenmanager"）がヒットしたが、内容を精読した結果、2018年当時の**画像スライドショーアプリでのメモリリークに起因する`SwapTransition`（Fbo使用）時の`glGetError 0x502`/FBO初期化失敗**であり、本件（`NoTransition`使用でFbo不使用、メモリリークなし、ステンシルテストで静かにフラグメント破棄という異なる症状）とは無関係と判断しクローズした。

**結論・今回のセッションの意義**：前回セッションが立てた3つの候補(a)(b)(c)はいずれも「Kivyライブラリまたはアプリコード側の一般的な不具合」としては説明力を持たないと判明した。`ScreenManager`の`current`Screen配下だけ描画が消失するという境界線は、静的解析（ソースコード読解）だけでは原因を特定できず、**GPU側で実際にピクセルが書き込まれているかどうかを直接確認する（`glReadPixels`によるライブ検証）以外に前進する手段がない**という結論に至った。これは前々回セッションの最優先候補1（現・優先候補0に降格）と実質的に同じ結論であり、次回セッションは静的解析ではなくライブ注入によるピクセル値直接確認から着手するのが妥当。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`race_capture`は最初から最後まで中断なく正常稼働を継続（PID 3848、GPS/テレメトリ等への影響なし）。今回のセッションは実機への変更を一切伴わない読み取り専用のSSH操作のみで完結した。

**次回の最優先調査候補（優先度順、第15回セッション完了時点で更新）**：
0. **最優先（静的解析では決着しないため、優先候補が実質1本化）：カラーバッファの実ピクセル値を`glReadPixels`で直接確認する。** DASHBOARD画面表示中の既知の座標（例：第13回セッションで画面内の妥当な座標と確認済みのcall 1858033の領域、x=[1830,1902) y=[10,60)）に対し、`glDrawElements`直後に1回だけ低オーバーヘッドで`glReadPixels(GL_RGBA, ...)`を実行する（第14回セッションの`egl_interpose7.so`のような毎コールステート照会は重すぎて描画をさらに悪化させたため、`swap_count`や累積`glDrawArrays`呼び出し回数が特定の値に達した1回のみサンプリングするワンショット方式に改良すること）。**ライブプロセスへの注入を伴うためユーザー立ち会いのもとで慎重に実施することを推奨。**
1. 今回発見した「単一スキャンライン状の断続コンテンツ」（第14回セッション前半の記録参照）は正体未確認のまま優先度低で保留。

---

**今回のセッション（4-4-2続き・第16回、ユーザー立ち会いあり、ライブ注入複数回）で得た知見：`glReadPixels`によるライブ検証をついに実現し、DASHBOARD画面が実際にはほぼ全域にわたり何も描画されていないことを実機内部から直接確認。副産物として`DashboardView`のKVソースを入手し、これまでの「ScreenManagerのcurrent Screen配下かどうか」という境界線仮説と矛盾する新事実を発見した**：

**接続情報の補記**：`rc-dash-3b`（`ntakao@192.168.137.162`、鍵は`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`）。今回はサンドボックス環境側の自動承認分類器が`sudo kill`・プロセス起動系のBashコマンドを繰り返しブロックしたため、これらのコマンドは全てユーザー自身に実機のPowerShellターミナルから直接実行してもらう運用で進めた（Claude側はSSHでの読み取り専用確認・ビルド・ファイル転送のみ担当）。また`ssh -f`はWindows OpenSSHクライアントでは期待通りに動作せず、バックグラウンド起動コマンドを実行してもローカルのPowerShellプロンプトが返ってこない現象が発生したが、実機側の処理自体は正常に完了していることを別セッションから確認した（見た目だけの問題、実害なし）。

**1. 🔴🎉 前回セッション最優先課題だった「低オーバーヘッド版`glReadPixels`ライブ検証」を、複数回の試行錯誤の末に実現した**。過程で2つの新しいdlsym/RTLD_NEXTスコープ問題を発見・解決：
   - **`eglSwapBuffers`自体が`RTLD_NEXT`経由の古典的LD_PRELOADシンボル上書きでは一切フックできない**（10分以上・数百回のスワップが発生しても0回しかフックされない）ことが判明。実際には`dlsym(handle, "eglSwapBuffers")`で動的に解決されており、第8回セッションの`SDL_GL_GetProcAddress`と同種の問題だった。修正：`dlsym()`自体をグローバルにフックし、`"eglSwapBuffers"`を要求された時だけ自前の関数を返す方式（第7-9回で確立済みの手法）で解決。
   - **`glReadPixels`も同様に`dlsym(RTLD_NEXT, "glReadPixels")`では解決できず（`NULL`が返り続ける）**、`/proc/<pid>/maps`で実際にロードされている`libGL.so.1`のパス（`/usr/lib/aarch64-linux-gnu/libGL.so.1.7.0`）を特定した上で`dlopen(path, RTLD_NOW|RTLD_NOLOAD)`により当該ライブラリの実ハンドルを取得し、そのハンドル経由で`dlsym`することで解決した（第8回セッションがSDL2に対して確立した手法と同一パターン）。
   - また、第13回セッションの`egl_interpose7.c`（ステンシル直読み版）が`glReadPixels`の呼び出し時に**y座標をウィンドウ座標系（左上原点）のまま渡しており、GLの左下原点への変換をしていなかった**というバグに気づいた（今回作成した後継版では`GL_Y = WIN_H - WINDOW_Y_TOP - HEIGHT`で正しく変換）。ただし第13回はステンシル条件が一度もマッチせず実害はなかった。
   - 完成した最終版インタポーザ（`egl_interpose17.so`）は、トリガーファイル（`/tmp/take_sample`）の存在を10スワップごとに軽量にチェックし、見つかった時だけ画面全体（1920x1080）を`glReadPixels`で1回だけダンプする設計（`Window.screenshot()`相当の全画面読み取りを、任意のタイミングでオンデマンド実行できる）。

**2. 🔴🎉 決定的な結果：ユーザーがDASHBOARD画面を表示している最中に画面全体をライブダンプしたところ、透過(0,0,0,0)が2,073,376ピクセル・背景色(18,18,18,255)がわずか4ピクセル・それ以外(other)が220ピクセルのみ（全2,073,600ピクセル中）という結果だった。この220ピクセルの位置を解析したところ、x=[95,110] y=[62,87]（画面左上寄りの小さな領域、グレースケール系の色）に集中しており、ユーザーが物理モニターで同時に確認していた「ページ切り替え用の矢印ボタン」の位置と一致すると考えられる**。つまり、**アプリ内部の`glReadPixels`（`Window.screenshot()`と同じ経路のはず）自体が、DASHBOARD画面表示中はこの矢印アイコン以外ほぼ何も見せていない**。これは第9回セッションの「`Window.screenshot()`は465色で完璧に描画されている」という結果と真っ向から矛盾するように見えるが、**第9回の`Window.screenshot()`検証はSetup→Home遷移直後の「Home画面」（Setup/Analysis/Dashboardの3ボタンを持つメニュー画面）に対して行われたものであり、DASHBOARD画面自体で同じ検証を行ったのは今回が初めてだった**という重要な違いに気づいた。すなわち、「GPU内部の読み戻しは常に完璧、スキャンアウトだけが壊れている」という長年の前提は、少なくともDASHBOARD画面については未検証のまま置かれていた可能性が高く、DASHBOARD画面固有の描画そのものに問題がある可能性が新たに浮上した。

**3. 🔴🎉 副産物：`DashboardView`のKVソース（`racecapture/views/dashboard/dashboardview.pyc`の文字列定数から抽出）を入手し、正確なウィジェット構造を確認した**：
```
<DashboardView>:
    canvas.before: Color / Rectangle（背景）
    FloatLayout: id: dash_container
        MDLabel: id: dash_notice
        AnalysisCarousel: id: tabs        # ← ゲージ本体のページ送りコンテナ（Carousel→StencilView継承）
        TripleGaugeBar: id: gauge_bar     # ← 下部ゲージバー
        IconButton: (左矢印, on_nav_left)  # ← ユーザーが見ている矢印ボタン
        IconButton: (右矢印, on_nav_right)
        AnchorLayout → PreferencesLockComboButton
        FullCourseFlagIndicator: id: fcflag
        AnchorLayout → MDBoxLayout → PopupAlertView 等
```
   **重要な矛盾を発見**：矢印ボタン（`IconButton`）は`AnalysisCarousel`・`TripleGaugeBar`と**全く同じ階層**（`dash_container`の直接の子、`DashboardView`＝`ScreenManager`のcurrent Screen配下）にあるにもかかわらず、矢印ボタンだけが描画され、他は描画されない。これは第14回セッションが確立した「`ScreenManager`のcurrent Screen配下かどうか」という境界線仮説と直接矛盾する新事実であり、単純な祖先ウィジェットの階層だけでは説明できないことが判明した。当初は「`AnalysisCarousel`（Carousel→StencilView継承）のステンシルクリップが壊れているだけでは」という仮説を立てたが、`TripleGaugeBar`はCarouselの外側（`dash_container`の直接の子、`AnalysisCarousel`とは兄弟）にありCarouselのステンシルクリップの影響を受けないはずなのに描画されないため、この仮説だけでは矢印ボタンとの違いを説明しきれない。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`race_capture`はユーザーの操作により元のwatchdog付きクリーンな状態（`run_racecapture_rpi.sh -w 1`、`LD_PRELOAD`なし）へ復旧済み、GPS/テレメトリ等正常。今回作成した`egl_interpose12〜17.c`/`.so`、`/tmp/gl_dump_0_swap1440.raw`（画面全体のRGBA生データ、ローカルにも保存済み）等は全て`/tmp`配下のため次回リブートで消滅する想定。

**次回の最優先調査候補（優先度順、第16回セッション完了時点で更新）**：
0. **最優先：矢印ボタン（`IconButton`）と`TripleGaugeBar`/`AnalysisCarousel`/`MDLabel`の違いを特定する。** 同じ階層にありながら描画の有無が分かれる具体的な要因を絞り込む。候補：(a) `IconButton`の実装（`autosportlabs.uix.button.iconbutton`）がKivy標準`Button`ベースで、他のウィジェットと異なる描画経路（テクスチャベースのボタン背景等）を使っている可能性、(b) KV上の記述順序・`canvas`挿入順序の違い（`IconButton`はcanvas.beforeで独自の背景描画を持たない一方、他は複雑な`canvas`命令を持つ）、(c) `AnalysisCarousel`/`TripleGaugeBar`/`MDLabel`が`size`/`size_hint`絡みで実際には0サイズになっている可能性（`egl_interpose17.so`の全画面ダンプ結果は0サイズでも矛盾しない）。`gauge_bar.top`等の値を各ウィジェットのランタイムプロパティとして確認する追加のライブ注入検証が有効。
1. 今回入手した`DashboardView`のKVソース全文（3000文字で打ち切ったため後半が未取得）を次回追加取得し、`PopupAlertView`以降の残り部分も確認する。
2. `egl_interpose17.so`のトリガーファイル方式（`/tmp/take_sample`）は低オーバーヘッドかつタイミング調整が容易な手法として確立できたため、次回以降のライブ検証でも継続利用する。

---

**今回のセッション（4-4-2続き・第17回、実機直接操作なし・静的解析のみ）で得た知見：矢印ボタン(IconButton)と他ウィジェットの違いを「pos/sizeの絶対値指定 vs pos_hint/size_hint依存」という観点で特定し、過去に未解決だった「実解像度1024x576固定」問題・Home画面とDashboard画面の描画差との整合性を確認、FloatLayoutのpos_hint計算が本件の核心である可能性が高いという統一仮説に到達した**：

**接続情報の補記**：`rc-dash-3b`（`ntakao@192.168.137.162`、鍵は`C:\Users\ntaka\.ssh\racecapture_dash_ed25519`）。セッション開始時、`race_capture`はPID 9260（前回セッション終了時のPID 3848とは異なるため間に何らかの再起動があった模様だが、前回終了時点で正常復旧済みだったことは確認済みのため特段の異常ではないと判断）で正常稼働中だった。今回のセッションは全て読み取り専用のSSH操作（既存の`~/decompile_4-4-2/`配下の`.pyc`を`xdis`/`pydisasm`で解析）のみで完結しており、`race_capture`本体プロセスやDRM/KMS状態には一切変更を加えていない。

**1. 🔴🎉 `IconButton`クラス自体の実装を`autosportlabs/uix/button/iconbutton.pyc`から確認、特別な描画機構を持たないと判明**：
`IconButton(FadeableWidget, Button)`（`FadeableWidget`は`EventDispatcher`のみを継承する軽量ミックスイン、実体はKivy標準の`kivy.uix.button.Button`）であり、KVルールは
```
<IconButton>:
    background_color: [0, 0, 0, 0]
    background_down: ''
    font_size: self.height
    color: [1.0, 1.0, 1.0, 0.2] if self.disabled else [1.0, 1.0, 1.0, 0.8]
    font_name: 'resource/fonts/fa_otf.ttf'
```
のみ。背景は透過（`background_color`のalpha=0、`background_down`は空文字で下状態画像も無効化）、可視部分はKivy標準`Label`のテクスチャベース文字グリフ描画（`font_name`にFontAwesomeアイコンフォントを指定）のみで完結しており、他の候補ウィジェットと比べて特別なcanvas命令・独自RenderContext等は一切持たない。次回セッション最優先候補(a)「`IconButton`が特殊な描画経路を使っている」は説明力が低いと判明した。

**2. 🔴🎉 前回3000文字で打ち切られていた`DashboardView`のKVソース全文を、`pydisasm`のCLI出力ではなく`xdis`のPython API（`load_module()`の`co_consts`を再帰的に走査）で取得し直し打ち切り問題を解消、決定的な構造上の違いを発見した**：
```
<DashboardView>:
    canvas.before: Color / Rectangle（背景）
    FloatLayout: id: dash_container   # ← pos_hint/size_hint指定なし（デフォルトsize_hint=(1,1)で親いっぱいに広がる想定）
        MDLabel: id: dash_notice       # ← size_hint/pos指定なし（デフォルト(1,1)、全面表示想定）
        AnalysisCarousel: id: tabs
            pos_hint: {"top": 1}
            size_hint_y: None
            height: root.height - gauge_bar.top     # widthはsize_hint_x未指定＝デフォルト1（親いっぱい）
        TripleGaugeBar: id: gauge_bar
            size_hint: None, None
            width: root.width - dp(150)
            height: dp(75)
            pos_hint: {"center_x": 0.5, "y": 0}      # ← サイズは絶対値だが位置はpos_hint
        IconButton: (左矢印)
            size_hint: None, None
            size: dp(45), dp(45)
            pos: 0, dp(15)                            # ← サイズ・位置とも絶対値
        IconButton: (右矢印)
            size_hint: None, None
            size: dp(45), dp(45)
            right: root.right
            y: dp(15)                                 # ← 絶対値（Widget.rightは絶対座標プロパティ）
        AnchorLayout → PreferencesLockComboButton      # ← AnchorLayoutのデフォルトlayout依存
        FullCourseFlagIndicator: id: fcflag             # ← size/pos指定なし
        AnchorLayout → MDBoxLayout → PopupAlertView 等  # ← AnchorLayoutのデフォルトlayout依存
```
**描画される矢印ボタン2つだけが、`size`・`pos`（または`right`/`y`）を全て絶対値（`dp()`定数、または一度確定すれば固定される`root.right`）で指定しており、`FloatLayout`の`pos_hint`計算を一切経由していない。それ以外（`AnalysisCarousel`・`TripleGaugeBar`の位置・`MDLabel`・`AnchorLayout`系）は全て`pos_hint`または無指定（デフォルトsize_hint=(1,1)、`FloatLayout`の`do_layout()`による計算に依存）である。** この境界線は、これまでに発見した「矢印ボタンだけ描画される」という現象を完全に一貫して説明する。

**3. 🔴🎉 正常に描画される「Home画面」（`racecapture/menu/homepageview.pyc`）のKVを同様に取得・比較し、この仮説をさらに補強する事実を発見**：
```
<HomePageView>:
    MDBoxLayout:              # ← ルートがFloatLayoutではなくBoxLayout系
        orientation: 'horizontal' if root.width > root.height else 'vertical'
        AnchorLayout: size_hint: (1,1) if ... else (0,0)
            Image: size_hint: (0.7, 0.7)
        MDBoxLayout:
            FeatureButton: size_hint_y: 0.5 ...
            MDBoxLayout: size_hint_y: 0.5
                FeatureButton × 2
        AnchorLayout: size_hint: (0.0, 0.0) if ... else (1,1)
            Image: size_hint: (0.7, 0.7)
```
**Home画面のルートコンテナは`FloatLayout`ではなく`MDBoxLayout`（`BoxLayout`系）であり、子要素の配置は全て`BoxLayout`独自の`do_layout()`（`orientation`に沿った単純な逐次配置アルゴリズム）に依存している。`FloatLayout`の`pos_hint`計算は一切使われていない。** これは「Home画面は完璧に描画される・Dashboard画面はほぼ描画されない」という第9回セッション以来の未解明の矛盾（`ScreenManager`のcurrent Screen配下という共通点だけでは説明できなかった差異）に対しても、**「`FloatLayout`のpos_hint計算経路を通るかどうか」という同一の軸で一貫した説明を与える**。

**4. 補記：以前から未着手のまま残っていた「実解像度が1024x768（実際は1024x576）に固定される現象」を`main.py`で確認**：
`main.py`は、Android/iOS以外のプラットフォームでは`--size`起動引数が無い限り`Config.set('graphics', 'width', 1024)` / `Config.set('graphics', 'height', 576)`を明示的に設定した後、`autosportlabs.util.fullscreen_wrapper.enable_full_screen_mode(True)`を呼び出す（Linux/RPi等では`Window.fullscreen = 'auto'`をセットするのみで、`Window.size`を明示的に上書きするコードはこのラッパー内には無い）。実機の起動スクリプト`run_racecapture_rpi.sh`は`-w`/`-l`オプションのみを解釈し、`--size`は一切渡していないことを確認した。**この「1024x576固定 → `fullscreen='auto'`」という流れが、`FloatLayout`のpos_hint計算に使われる`Window.size`ないし`dash_container.size`にどう影響しているか（設定値の1024x576のまま止まっているのか、fullscreen化で実際の1920x1080に更新されているのか）は、今回は静的解析の範囲では確定できず、次回のライブ確認が必要**。

**結論・今回のセッションの意義**：今回のセッション（純粋な静的解析、実機への操作は一切なし）により、これまで別々に扱われていた3つの謎──①矢印ボタンだけ描画される現象（第16回）、②Home画面は完璧・Dashboard画面はほぼ描画されない現象（第9回）、③実解像度1024x576固定問題（未着手のまま放置）──が、**「`FloatLayout`のpos_hint/デフォルトsize_hint(1,1)計算が、この実機環境で正しく機能していない（あるいは計算の元になる`Window.size`/親サイズが異常な値になっている）」という単一の仮説で統一的に説明できる**という重要な進展を得た。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`race_capture`は最初から最後まで中断なく正常稼働を継続（PID 9260、GPS/テレメトリ等への影響なし）。今回のセッションは実機への変更を一切伴わない読み取り専用のSSH操作のみで完結した。

**次回の最優先調査候補（優先度順、第17回セッション完了時点で更新）**：
0. **最優先・ライブ確認（ユーザー立ち会い推奨）：DASHBOARD画面表示中に`Window.size`・`dash_container.size`・`dash_container.pos`・`tabs.size`（AnalysisCarousel）・`gauge_bar.pos`（TripleGaugeBarの実際に計算されたpos_hint結果）を実際に読み取る。** 既存の`egl_interpose17.so`（トリガーファイル方式、`eglSwapBuffers`フック内で安全に実行）を拡張し、GL呼び出しではなく`PyGILState_Ensure()`→`PyRun_SimpleString()`でPythonレベルの値をファイルへ書き出す方式を検討する。これは第9回セッションでGILデッドロックを起こした「gdbによる非同期的な割り込み」とは異なり、`eglSwapBuffers`が呼ばれるその瞬間（メインスレッドの正常な実行フロー内）に同期的にPython C APIを呼ぶ設計のため理論上はより安全なはずだが、実機での実証は未検証。慎重に、まず無害な読み取り（`repr()`をログファイルへ書くのみ）から始めること。
1. もし上記(0)で`dash_container.size`等が明らかに異常な値（0や1024x576のまま等）であれば、その値がどの時点で・なぜ確定してしまうのか（`on_pre_enter`/`on_enter`のタイミング、`Window.size`変更イベントの伝播有無等）をさらに追う。
2. 上記(0)で仮に`dash_container.size`等が正常（1920x1080相当）であった場合は、この統一仮説自体が崩れるため、`FloatLayout.do_layout()`実装そのもの（`kivy/uix/floatlayout.py`）の実機バイナリと本家ソースの再突き合わせ、または全く別の角度を再検討する。

---

**今回のセッション（4-4-2続き・第18回、ユーザー立ち会いあり、ライブ注入複数回）で得た知見：Pythonレベルのライブプロパティ読み取りを新規に確立し「第17回のFloatLayout仮説」を実測で完全に否定、続くステンシル除去実験で「ステンシル仮説」もtabsについて完全に否定、さらに座標を厳密照合した結果「矢印ボタンだけ描画される」という第16回セッション以来の前提そのものが誤りだったと判明、第14回セッションの本来の境界線（ScreenManagerのcurrent Screen配下は一切描画されない）を再確認する形で調査が振り出しに戻った**：

**背景**：前セッション（第17回、静的解析のみ）で「矢印ボタンだけpos/sizeが絶対値指定でFloatLayoutのpos_hint計算を経由しない」という統一仮説を立てたが、ユーザーから「ハードウェアが壊れない限り何をしてもよい」との許可を得て、今回はその場でライブ確認まで実施した。

**1. 🔴🎉 新手法を確立：`eglSwapBuffers`フック内で`PyGILState_Ensure()`→`PyRun_SimpleString("exec(open('/tmp/py_probe_script.py').read())")`→`PyGILState_Release()`という、メインスレッドの正常な実行フロー内で同期的にPython C APIを呼ぶ方式が実機で安全に動作することを実証した（`egl_interpose18.so`〜`19.so`）**。
`/opt/racecapture/_internal/libpython3.11.so.1.0`を`dlopen(RTLD_NOLOAD)`で取得し`PyGILState_Ensure`/`PyGILState_Release`/`PyRun_SimpleString`を`dlsym`解決、実際のPythonロジックは`/tmp/py_probe_script.py`という外部ファイルに書いて`exec(open(...).read())`一行で呼び出す設計とした（Cソース側の再コンパイル無しで検証内容を変更できる）。トリガーファイル方式（`/tmp/take_py_sample`等）を10swapごとの軽量`stat()`チェックで実現。今回、この手法を6回以上使用したが、**一度もデッドロック・ハング・クラッシュを起こさなかった**。第9回セッションのGILデッドロック事故（gdbによる非同期割り込みが原因）とは異なり、`eglSwapBuffers`呼び出しという実際の同期的な実行フロー内でPython C APIを正規の作法で呼ぶ今回の方式は、実機でも安全であることが実証された。今後のライブ検証の標準手法として確立できた。

**2. 🔴🎉 DASHBOARD画面表示中に`Window.size`・`dash_container`・`tabs`（AnalysisCarousel）・`gauge_bar`（TripleGaugeBar）等の実際のプロパティを読み取ったところ、全て完全に正常な値であることが判明し、第17回セッションの「FloatLayoutのpos_hint計算が壊れている」という統一仮説は実測により完全に否定された**：
`Window.size=(1920,1080)`（設定値1024x576ではなく実解像度に正しく追従、この件はクローズ）、`dash_container`（FloatLayout）は`size=[1920,1040.0] pos=[0,0] size_hint=[1,1]`、`tabs`は`size=[1920,965.0] pos=[0,75.0] size_hint=[1,None] pos_hint={'top':1}`、`gauge_bar`は`size=[1770.0,75.0] pos=[75.0,0] size_hint=[None,None] pos_hint={'center_x':0.5,'y':0}`と、KVの指定通りに正しく計算された、画面内に収まる妥当な値だった（`sm`のサイズが`[1920,1040.0]`と40px低いのは画面上部のツールバー分と推測され正常）。`opacity`も全て`1.0`、`disabled`も`False`。

**3. 🔴🎉 `dash_container`の子ウィジェット全8個（`children`プロパティ）を確認したところ、Kivyの標準的な子リスト順序（KV記述の逆順＝最後に追加されたものが`children[0]`＝最前面）通りに全て存在し、全ての`opacity=1.0`・正しいサイズ・位置を持つことを確認**。KVで最初に書かれた`dash_notice`(MDLabel)が最背面、最後に書かれた`AnchorLayout`（`popup_alert`関連）が最前面という一般的なz順序も裏付けられ、ウィジェットツリーの構築自体には一切異常が無いことが確定した。

**4. 🔴🎉 `tabs`（`canvas.before`=4命令）・`gauge_bar`（`canvas.before`=6命令）の実際のcanvas命令の型を1つずつ確認したところ、いずれも正しいジオメトリを持つ有効な描画命令が実在することを確認した**：
`tabs.canvas.before`は`StencilPush`→`BindTexture`→`Rectangle(pos=(0,75.0), size=(1920,965.0))`→`StencilUse`（`canvas.after`はその対称形`StencilUnUse`→...→`StencilPop`）と、`AnalysisCarousel`が継承する`StencilView`の標準的なクリッピング命令列であり、マスク矩形のサイズも正しかった。`gauge_bar.canvas.before`は`Color(rgba=[0,0,0,1])`+`Rectangle`が2セット（それぞれ`pos=(75,0) size=(1770,75)`と`pos=(0,0) size=(1920,75)`、後者はDashboardViewのKVで明示された`canvas.before`のオーバーレイ黒帯に相当）で、いずれも不透明・画面内の妥当な座標だった。比較用に単独の`IconButton`（`dash_container`直下）の`canvas`も確認し、`Color(rgba=[1,1,1,1])`+`Rectangle(pos=(1880,15) size=(35,45))`という、文字グリフのテクスチャ矩形が不透明白で存在することを確認した。

**5. ⚠️ `glReadPixels(GL_STENCIL_INDEX)`によるステンシルバッファの直接読み取りを試みたが、画面全体（207万3600ピクセル）が不自然なほど均一に値0であり、`tabs`のステンシルマスク矩形（`pos=(0,75) size=(1920,965)`）が書き込まれるはずの領域にも一切の空間的パターンが見られなかった**（`glGetError`は`0x0`＝エラー無し）。第13回セッションで`apitrace`がGLコマンドストリームの束縛状態として直接検出した「ステンシルテスト有効・`GL_EQUAL`・`ref=2`」という情報とは異なり、今回の`glReadPixels`によるバッファ読み戻しはこのMesa/VC4ドライバでは実際のステンシルバッファ内容を正しく返していない可能性が高く（読み戻し経路自体が未実装/スタブという既知のドライバ制限のカテゴリ）、この結果単体では仮説の証明にも反証にもならないと判断した。

**6. 🔴🎉🔑 決定打：`tabs.canvas.before`と`canvas.after`を実行時に完全にクリア（`tabs.canvas.before.clear()` / `tabs.canvas.after.clear()`でStencilPush等の命令を丸ごと除去）した上で画面全体を再度`glReadPixels`ダンプしたところ、Carousel内部のコンテンツは一切出現せず、むしろ「other」ピクセル数は337→220に減少した（ステンシル矩形自体の副産物と思われる分が消えただけ）。これにより「ステンシルテストが`tabs`のコンテンツを隠している」という仮説は、`tabs`について完全に否定された**。この実験は`tabs`インスタンスのcanvas命令を永続的に破壊する不可逆な変更だったため、実験後はプロセスを再起動して復旧した。

**7. 🔴🎉🔑 さらに`tabs`の実際に表示中のスライド（`RelativeLayout`→`FreeformView`→`RelativeLayout`→`FreeScatter`→`AnchorLayout`×4+`ChannelAnalysisWidget`、および兄弟の`AnchorLayout`→`AddGaugeUserNote`→`FieldLabel`×2+`IconButton`）を再帰的に確認したところ、5階層すべてで正しいサイズ・位置・`opacity=1.0`・有効なcanvas命令数を持つことを確認した。特に注目すべきは、`AddGaugeUserNote`内に単独成功時と全く同じクラスの`IconButton`（`pos=[850.0,467.5] size=[40.0,30.0]`）がネストされていた点である**。

**8. 🔴🎉🔑🚨 最重要の訂正：ピクセル座標を厳密照合した結果、第16回セッション以来「描画される」とされてきた矢印ボタン自体が、実際にはどちらも一切描画されていないことが判明した。「220個のotherピクセル」の正体は矢印とは無関係の別の場所だった**：
`gl_color_swap*.raw`の全画面スキャンにより、非背景ピクセルの実際のバウンディングボックスは`x=[100,115] y=[985,1010]`（バッファ座標）であると特定した。これに対し、KVで確認済みの左矢印の座標（`x=[0,45] y=[15,60]`）・右矢印の座標（`x=[1875,1920] y=[15,60]`）を、バッファのY軸反転あり・なしの両方の解釈で厳密にスキャンしたが、**いずれの座標・いずれの解釈でも「other」ピクセルは0個**だった。すなわち、第16回セッションが「ユーザーが物理モニターで同時に確認していた矢印ボタンの位置と一致すると考えられる」として立てた対応付けは、精密な座標照合を経ない目視ベースの推測であり、誤りだった可能性が高い。実際に光っている220ピクセルの塊（白`(255,255,255,255)`＋黒`(0,0,0,237)`という不透明な文字/アイコン様の配色）は、`DashboardView`のいかなる既知ウィジェットの座標とも一致せず、位置（画面上部寄り、ツールバー領域のすぐ下）から見て、**第14回セッションで「描画される」と確認済みのオーバーレイ系UI（ナビゲーションドロワーのハンバーガーアイコン等）である可能性が高い**。また同じダンプの全体histogramでは、画面のほぼ全域が透過`(0,0,0,0)`で埋まっており、期待していた背景色`(18,18,18,255)`はわずか4ピクセルしか存在しなかった。

**結論・今回のセッションの意義**：今回のライブ検証により、①第17回の「FloatLayoutのpos_hint計算」仮説と②「ステンシルテストがtabsの内容を隠している」仮説の両方を、実測によって明確に反証できた。同時に、③これまで数セッションにわたり分析の足場としてきた「矢印ボタンだけ描画される」という観測自体が誤りだったと判明し、**実際には`DashboardView`（`ScreenManager`のcurrent Screen）配下のウィジェットは、矢印ボタンを含め一つも描画されていない**ことが確定した。これは奇しくも、第14回セッションでユーザーの実機直接操作により実証された「ナビゲーションドロワー・パネル・ポップアップ・カーソルなどのオーバーレイ系は描画される、`ScreenManager`のメイン画面コンテンツだけ描画されない」という境界線を、より精密な形で再確認する結果となった。ウィジェットツリー・プロパティ・canvas命令列はすべてのレベルで完全に正常であるにもかかわらず、この境界線を挟んでピクセルが出現するかどうかが分かれるという、根本的な謎は依然として未解決である。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての実験終了後、`sudo kill -9`でテスト用プロセスを終了し、`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み（新PID、RCPAPI通信正常）。今回使用した`egl_interpose18.c`/`19.c`とその`.so`、`/tmp/py_probe_script.py`（内容は最後の実験用のまま）、各種`/tmp/gl_color_swap*.raw`・`/tmp/gl_stencil_swap*.raw`・`/tmp/py_probe_result*.txt`は全て`/tmp`配下のため次回リブートで自然に消える想定。ハードウェアへの損傷は無し（GILデッドロック等の事故も今回は一切発生しなかった）。

**次回の最優先調査候補（優先度順、第18回セッション完了時点で更新）**：
0. **最優先：`ScreenManager`のcurrent Screen配下では canvas命令が100%正しく存在するにもかかわらず一切のピクセルが出力されない、という根本的な境界線のメカニズムを、今回確立した安全なライブPython注入手法を使い、GL呼び出しレベル（`glDrawArrays`/`glDrawElements`の呼び出し有無そのもの）でさらに追う。** 具体的には、`tabs`や`gauge_bar`のRectangle/Line命令に対応する実際の`glDrawElements`呼び出しが本当に発行されているか（第12回セッションのapitrace調査では発行されていると確認されたが、あれは`swap_count`ベースの離散サンプリングであり`tabs`/`gauge_bar`個別には未確認）を、今回のフレームワークに`glDrawElements`のフックを追加して確認する。
1. 今回発見したオーバーレイ系と思われる正体不明の220ピクセルの塊（`x=[100,115] y=[985,1010]`、バッファ座標）の正体を特定する（ナビゲーションドロワーのハンバーガーアイコン等の候補を検証）。優先度は低いが、「オーバーレイは描画される」という境界線の再確認材料として有用。
2. 今回確立した`PyGILState_Ensure`ベースのライブ注入手法（`egl_interpose18/19.so`のパターン）は、今後のセッションでも安全に再利用できる標準ツールとして記録しておく。Cソースの再コンパイル無しに`/tmp/py_probe_script.py`を書き換えるだけで検証内容を変更できる。

---

**今回のセッション（4-4-2続き・第19回、同日・ユーザー立ち会いあり、ライブ注入複数回）で得た知見：ユーザーの実況（「介入すると矢印が消える」）をきっかけに、第16回以来「矢印ボタン」として扱ってきたものが実は一時的に表示されて自動的に消える別要素（トースト/ヒント的なもの）であり、DashboardViewの本物のナビゲーション矢印（`IconButton`×2）はそれとは別に一度も描画されていなかったと判明。生ピクセルバッファを実際に画像化する新手法も確立した**：

**背景**：第18回セッションの最後にユーザーから「ダッシュボード画面を表示して矢印が見えるが、あなたが介入した瞬間に消える」との実況があった。当初は「LD_PRELOAD注入がフェードアウトを誘発しているのでは」と疑ったが、確認の結果「実験中・現在のクリーンな状態の両方で起きている」「操作せず放置しても矢印は約30秒で自然に消える（再表示操作をしても戻らない）」ことが分かり、**筆者の介入とは無関係な、時間経過で自然にフェードアウトする一時的なUI要素である**可能性が浮上した。さらにユーザーへ形状を確認したところ「文字を含むトースト風ボックスではなく、三角形の矢印記号そのもの」、位置は「画面端ではなく中央からやや右寄り」との証言を得た。これはDashboardViewのKVで確認済みの矢印ボタンの座標（`x=[0,45]`または`x=[1875,1920]`、いずれも`y=[15,60]`＝画面端）とは全く異なる。

**1. 🔴🎉 新手法を確立：純粋なPython標準ライブラリ（`zlib`）のみで生RGBAバッファから任意領域を切り出しPNGへ変換する手法を確立し、`glReadPixels`で得た生データを実際に「目で見て」確認できるようになった**（PILは端末に未インストール、`struct`+`zlib.compress`で最小限のPNGエンコーダを自前実装、alpha=0の透過部分は白背景に合成）。これにより、これまでピクセル値のヒストグラム・バウンディングボックスといった間接的な数値情報でしか判断できなかった描画内容を、直接視覚的に確認できるようになった。

**2. 🔴🎉 `glReadPixels`直前に`glFinish()`を追加した改良版インタポーザ（`egl_interpose20.so`）でも、以前（`glFinish()`無し）と全く同じピクセル数・バウンディングボックスが再現され、以前の「幅広く散らばったグレー系ピクセル」という結果がフレーム破損（読み取りタイミングとGPU描画完了のレースコンディション）によるものではなく、実際に再現性のある描画内容であることを確認した**。

**3. 🔴🎉🔑 ユーザーが矢印を目視確認したタイミングで撮った生バッファをPNG化して確認したところ、「幅広く散らばったグレーのピクセル」は実は互いに離れた場所にある2つの小さな図形であり、そのうち一つは画面中央よりやや右・高さ中央付近に位置する右向きの三角形（矢印記号）であると判明した。ユーザーに提示したところ、これが実機で見えた「小さい矢印」の位置・形状と完全に一致すると確認が取れた**。もう一つはさらに別の位置（画面バッファ座標で左上寄り、実際の画面では左上コーナー付近）にある稲妻状／斜線状の小さな図形で、正体は未特定（ナビゲーションドロワーのアイコン等の可能性、優先度低で保留）。

**4. 🔴🎉🔑 発見した三角形の絶対座標をもとに、`current_screen`配下、`root`配下、`Window.children`直下の3段階でウィジェットツリーを`to_window()`（相対座標変換込みの正式なKivy API）を使い全探索したが、いずれの探索でも一致するウィジェットが見つからなかった**。探索を行った時点で、ユーザーとの確認のやり取りに要した時間（数分程度）が経過しており、証言通り約30秒でフェードアウトする一時的な要素だとすれば、探索時点では**ウィジェットツリーから完全に削除済み**（`opacity=0`になるだけでなく実際に`remove_widget`されるタイプの一時要素）だったと考えるのが最も自然な説明である。

**結論・今回のセッションの意義**：今回のセッション全体を通じて、**これまで「矢印ボタンが描画される／されない」という軸で組み立ててきた第16〜18回の分析の一部（特に「矢印ボタンだけ描画される」という第16回の観測）が誤りだったと確定した**。実際には：
- ユーザーが見ていた「矢印」は、DashboardViewのKVで確認済みの恒久的なナビゲーション`IconButton`（画面端、`x=[0,45]`/`x=[1875,1920]`）とは別の、画面中央付近に一時的に表示されるヒント/トースト的な要素であり、約30秒でフェードアウトして完全に削除される。この一時要素は正常に描画される（トースト系がWindow直下の別経路で正常描画されるという第8〜9回の知見と整合）。
- DashboardViewの本物のナビゲーション`IconButton`（画面端の2つ）は、第18回セッションで正確な座標を精密照合した結果、**一度も描画が確認できていない**（`tabs`/`gauge_bar`と全く同じ扱いで、`ScreenManager`のcurrent Screen配下は矢印ボタンを含め何一つ描画されないという、より単純でクリーンな境界線に帰着した）。
これにより、調査の焦点は再び第14回セッションが確立した本来の境界線（`ScreenManager`のcurrent Screen配下は一切描画されない、オーバーレイ・一時要素は正常に描画される）に一本化された。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての実験終了後、`sudo kill -9`でテスト用プロセスを終了し、`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み。今回のセッション中、複数回のプロセスkill/再起動を行ったが、いずれもハードウェアへの影響は無し。作成した`egl_interpose20.c`/`.so`、PNG変換スクリプト、各種ダンプファイルは全て`/tmp`配下。

**次回の最優先調査候補（優先度順、第19回セッション完了時点で更新）**：
0. **最優先：DashboardViewの本物のナビゲーション`IconButton`（画面端）についても、今回確立したPNG可視化手法で実際に画像として確認し、「本当に何も描画されていない」ことを視覚的にも最終確認する。** これまでの結論はヒストグラム・バウンディングボックスという間接的な数値のみに基づいており、第16回の「矢印ボタンだけ描画される」という誤った結論を生んだ反省を踏まえ、今後は必ずPNG化して目視確認する運用とする。
1. 見つかった正体不明のヒント/トースト的な一時要素（三角形の矢印）が、どのクラス・どの描画経路（`ModalView`系か、`Window`への直接`add_widget`か等）で実装されているかを、次回は**表示された瞬間により迅速にウィジェットツリー探索を行う**（今回は数分の遅延で消失後になってしまった）ことで特定する。この要素が「なぜ`ScreenManager`のcurrent Screen配下ではないのに正常描画されるのか」を理解できれば、逆に「なぜcurrent Screen配下は描画されないのか」の理解にも繋がる可能性がある。
2. 今回確立したPure Python（PIL不要）でのPNG可視化手法・`glFinish()`付きの改良版`glReadPixels`手法は、今後のライブ検証における標準ツールとして継続利用する。

---

**今回のセッション（4-4-2続き・第20回、同日深夜・ユーザー不在の自律調査）で得た知見：ユーザーが就寝したため単独で継続。タッチ操作なしで任意の画面へ直接遷移する手法を新規確立し、Python/Kivyレベルで確認可能な項目を全て確認し尽くしたが「描画されない」という結論は変わらず、GLコールレベルの検証は技術的な壁にぶつかり未達に終わった**：

**背景**：ユーザーから「ハードウェアが壊れない限り好きに動いてよい、自分一人で解決できる範囲で動けるだけ動いてほしい」との許可を得て、物理タッチ操作が必要な部分を除き単独調査を継続した。

**1. 🔴🎉🔑 新手法を確立：`App`インスタンスの`switchMainView(view_name)`メソッドを発見し、`app.switchMainView('dash')`をPython注入で直接呼び出すことで、Setup→Home→Dashboardという通常のタッチ操作によるナビゲーションフローを完全にバイパスして、タッチ入力なしで任意の画面（`'setup'`/`'dash'`/`'home'`/`'analysis'`/`'config'`/`'status'`）へ直接遷移できることを実証した**。これは第9回セッション以来「ヘッドレス環境ではSetup画面のフローを自動で通過できない」として何度も立ちはだかっていた制約を根本的に解消するものであり、今後のセッションで（ユーザー不在時も含め）ライブ検証を大幅に効率化できる。`app.mainViews`（生成済み画面のキャッシュ）・`app.view_builders`（画面名→ビルダーメソッドの辞書）を経由するAPIで、画面は遅延生成される（`switchMainView`呼び出し時に初回のみ`build_dash_view`等が走る、ログに`[INFO] [DashboardView] Initialization`等が出力される）。

**2. ⚠️ 次回の最優先候補だった「`glDrawElements`/`glDrawArrays`呼び出し自体が発行されているか」をLD_PRELOADベースの自作インタポーザ（`egl_interpose21.so`/`22.so`）で検証しようとしたが、複数の手法（`dlsym`フック・`eglGetProcAddress`フック・シンボル直接エクスポート）いずれでも一切のフック発火が確認できず、技術的な壁にぶつかり未達に終わった**。setup画面表示中に240swap以上（数秒間）観測しても`drawElements calls=0 indices=0 drawArrays calls=0 verts=0`のままだった。`nm -D`で`libGL.so.1.7.0`・自作`.so`双方に`glDrawElements`/`glDrawArrays`が通常のシンボル（バージョンタグ無し、`Base`）としてエクスポートされていることは確認したため、シンボル自体の問題ではなく、**Kivyのコンパイル済みCython拡張モジュールが`RTLD_DEEPBIND`相当のシンボル分離を伴う形でロードされている可能性が高い**と推測している（未確定）。第12回セッションで`apitrace`（より成熟した外部ツール）がこれらの呼び出しを実際に捕捉できていたことを踏まえると、自作インタポーザでのGLコール捕捉という方向自体は筋が悪く、**次回この方向へ再挑戦する場合は自作インタポーザの拡張ではなく`apitrace`を使うべき**。

**3. 🔴🎉 上記2の代わりに、より安全でリスクの低い検証として、既存の安全なPython注入手法のみを使い、正常に描画される`setup`画面と描画されない`dash`画面の`Screen`オブジェクト自体のcanvas構造を初めて直接比較し、「両者の`canvas.before`/`canvas`/`canvas.after`はいずれも標準的な`RelativeLayout`変換（`PushMatrix`/`Translate`...`PopMatrix`）パターンに従っており構造上の違いは無い」ことを確認した**。唯一の違いは`DashboardView`のcanvas.beforeには（`setup`側には無い）画面全体を覆う不透明な背景`Color`+`Rectangle`（`rgba=(0.165,0.165,0.165,1.0)`、`pos=(0,0) size=(1920,1040)`）が`<DashboardView>:`のKVルール通り存在する点のみだったが、**この最も単純な「画面全体を塗りつぶすだけの矩形」ですら実際には描画されていない**（透過ピクセルが大半を占める既存の観測と整合）。これにより「複雑なStencilクリップ・深いネスト・特定のウィジェットクラス」といった複雑性に基づく仮説群は完全に排除され、**`ScreenManager`のcurrent Screenとして表示されるとき、その画面が持つ最も単純な描画命令すら一切実行されない**という、これまでで最もクリーンな形で問題が絞り込まれた。

**4. 🎉 `cur.canvas`（`dash`のScreenのcanvasオブジェクト）が、`sm.canvas`（ScreenManager自身のcanvas）の子孫ツリー内に正しく（Pythonオブジェクトの同一性で）存在することを確認し、canvasツリーへのアタッチ自体は正常であることも確認した**（比較として、切り替え済みの`setup`のcanvasは`sm.canvas`ツリーから正しく外れており、これはKivyの標準的な「currentでなくなったScreenのcanvasは描画対象から外れる」という仕様通りの挙動であり異常ではない）。

**結論・今回のセッションの意義**：Pythonレベルで確認できる項目（ウィジェットプロパティ、canvas命令の内容・型・ジオメトリ・色・opacity、canvasツリーへのアタッチ状態）は、今回で実質的に**全て確認し尽くした**。いずれも一切の異常が見当たらないにもかかわらず、`ScreenManager`のcurrent Screen（`dash`に限らず`setup`以外の全画面が同様の可能性がある）配下の描画命令は一切GPUへの実効的な出力を生んでいないという結論に変わりはなかった。残された唯一の手がかりは「実際のGLコール（`glDrawElements`等）が発行されているか」であり、これはPythonレベルの調査では原理的に確認できない領域である。自作インタポーザでの追跡が技術的に困難だったため、次回は`apitrace`（第11〜13回セッションで実績のある、より成熟したツール）を、今回確立した`switchMainView()`によるタッチ不要のナビゲーションと組み合わせて使うのが最有力の次の一手となる。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：セッション中、複数回のプロセスkill/再起動・`switchMainView`によるプログラム的な画面遷移を行ったが、いずれもハードウェアへの影響は無し。最終的に`sudo kill -9`でテスト用プロセスを終了し、`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み（PID親子関係も正常：watchdogラッパー→race_capture本体）。作成した`egl_interpose21.c`/`22.c`とその`.so`、各種プローブ結果ファイルは全て`/tmp`配下。

**次回の最優先調査候補（優先度順、第20回セッション完了時点で更新）**：
0. **最優先：`apitrace`と、今回確立した`app.switchMainView('dash')`（タッチ不要のプログラム的画面遷移）を組み合わせ、`dash`画面表示中に実際に`glDrawElements`/`glDrawArrays`等の描画コールが発行されているかを確認する。** 自作インタポーザによるPython注入（`PyGILState_Ensure`方式）と`apitrace`は共に`eglSwapBuffers`等をフックするため素朴に共存させると競合する可能性がある点に注意（本文中の検討を参照）。回避策の一案として、Python注入部分はGL関連のフックを一切持たない最小構成にし、`apitrace`側のフックを優先させる、または`switchMainView`の呼び出しを「起動後一定時間で1回だけ発火するバックグラウンドスレッド」のような`eglSwapBuffers`フックに依存しない方式に変更することが考えられる（ただし後者は第9回のGILデッドロック事故と同種の非同期呼び出しリスクを伴うため、実施する場合は影響範囲を1回限りの呼び出しに絞るなど慎重な設計が必要）。
1. 見つかった正体不明のヒント/トースト的な一時要素（三角形の矢印）の正体特定は、優先度を維持しつつ持ち越し。`switchMainView('dash')`を呼んだ直後に間髪入れずウィジェットツリー探索するトリガー設計にすれば、次回は捕捉できる可能性が高い。
2. `app.switchMainView(view_name)`によるタッチ不要のナビゲーション手法は、今後のセッション（ユーザー立ち会いの有無を問わず）で標準的に使える強力なツールとして記録しておく。

---

**今回のセッション（4-4-2続き・第21回、ユーザー不在の自律調査、4時間枠）で得た知見：GL描画コール発行を`apitrace`で確定的に確認、テクスチャ内容も正常と判明した一方、GPU側の実測ツール（オフラインsnapshot・occlusion query）2種が本ドライバ上でいずれも機能不全と判明し、真犯人候補として「異常に新しいMesaバックポート版」という新方針に到達**：

**背景**：ユーザー就寝中の単独調査（4時間枠）。第20回セッションの「次回の最優先候補#0」（`apitrace`と`switchMainView`の組み合わせ）から着手。

**1. 🔴🎉 新手法確立：GL/EGL関数を一切フックしないpthreadコンストラクタ方式のインジェクタ（`timer_inject23.c`）を確立し、`apitrace`（`egltrace.so`）と完全に競合なく共存できることを実証した**。手法は、ライブラリロード時に`__attribute__((constructor))`でdetached pthreadを1本起動し、そのスレッド内でのみ`sleep`＋ポーリングののち`PyGILState_Ensure`→`PyRun_SimpleString`で`app.switchMainView('dash')`を呼ぶという設計（`eglSwapBuffers`等のGLシンボルは一切オーバーライドしない）。`LD_PRELOAD=/tmp/timer_inject23.so:/usr/lib/aarch64-linux-gnu/apitrace/wrappers/egltrace.so`（自作ライブラリを先頭に）＋`TRACE_FILE=...`を`apitrace trace`コマンドを介さず直接環境変数で指定することで、`apitrace trace`自身が`LD_PRELOAD`を上書きしてしまう問題も回避した。この手法により、タッチ入力なしで`dash`画面表示中の完全なGLトレース（297,683コール、うち`glDrawElements`/`glDrawArrays`が28,894回、スイッチ後だけでも26,168回）を取得することに成功した。

**2. 🎉 第20回の最優先課題「dash画面表示中に実際にGL描画コールが発行されているか」に決定的な決着：`apitrace dump`で確認した結果、`dash`画面表示中も`glDrawElements`/`glDrawArrays`は大量かつ継続的に発行されていることを確定した**。自作インタポーザによる直接フック（第20回で試みて技術的な壁にぶつかった手法）ではなく、実績のある`apitrace`経由で確認できたことが第20回からの前進。サンプリングした個別の描画コール（`eglretrace -D <call>`でGLステート全体をJSONダンプ）についても、stencil/scissor/depthテストはいずれも無効、viewportは正しく`[0,0,1920,1080]`、`GL_DRAW_FRAMEBUFFER_BINDING=0`（正しいデフォルトFB）、blendも正常と、既存セッションの知見と完全に整合する「異常なし」の結果だった。

**3. 🎉 新規の検証観点：`apitrace dump --blobs`でテクスチャの実バイト内容を初めて直接検証し、`dash`画面のラベルテクスチャの内容自体は正常（空白ではない）と判明した**。`glTexImage2D`単体（テクスチャ確保のみ）はsetup画面・dash画面どちらのラベルも全ピクセルalpha=0の空バッファだったが、これは正常な初期確保パターンで、直後に続く`glTexSubImage2D`（実内容の書き込み）を確認したところ、setup画面・dash画面の両方でmax_alpha=255の本物のグリフ内容が含まれていることを確認した。これにより「dash画面のラベルはラスタライズ自体が空になっている」という仮説を明確に否定できた。

**4. ⚠️ GPUハードウェアパフォーマンスカウンタ（`GL_AMD_performance_monitor`、`eglretrace --pdrawcalls`）によるプロファイリングを試みたが、ツール側の問題（正しいbackend:metric構文でも per-drawcall の出力が一切得られない）で未達に終わった**。apitrace本家ソース（`retrace/metric_helper.cpp`）を読み構文は`GL_AMD_performance_monitor:MetricName`で合っていることを確認し、`--list-metrics`ではVC4の実カウンタ（`TLB-quads-written-to-color-buffer`等）が正しく列挙されるにもかかわらず、実際のプロファイリング実行では警告もエラーも出さずに単に出力が生成されない。原因は未特定（今回はここで打ち切り、深追いしない判断）。

**5. 🔴🎉🚨 決定的な発見：`eglretrace`のオフラインsnapshot機能（`-S`/`--snapshot-prefix`、GBMヘッドレスリプレイ）を使い`dash`画面表示中の描画コール（call 282827）を可視化したところ背景色のみの完全な単色画像が得られ、一見「オフラインリプレイでもバグが再現した」ように見えたが、サニティチェックとして同じ手法でsetup画面（既知の正常系）を同様にsnapshotしたところ、こちらも完全な単色（黒一色、PILで2,073,600ピクセル全て同一色と確認）となり、**このオフラインリプレイ機能自体がこのドライバ環境では前景コンテンツを一切正しく再現できない、壊れた/信頼できないツールであると判明した**。この誤った初期解釈（オフラインリプレイでバグ再現）は危険な早合点になりかねなかったが、正常系での必須サニティチェックにより正しく訂正できた。今後のセッションはこのオフラインsnapshot手法を追加のドライバ調査なしに信頼しないこと。

**6. 🔴🎉🚨🔑 さらに決定的な発見：ライブプロセス内でのcore GL Occlusion Query（`GL_SAMPLES_PASSED`、`eglSwapBuffers`境界でbegin/end）という第3の独立した検証手法を確立したところ、`dash`画面表示中の190フレーム連続ですべて`samples_passed=0`（`glGetError`は常に`0x0`でエラーなし）という結果を得たが、これも上記5と同様の理由でサニティチェックが必須と判断し検証した結果、**Kivy/race_captureの内容に一切依存しない自前のimmediate mode描画（画面の大部分を覆う単純なマゼンタ三角形、`glBegin`/`glVertex2f`/`glEnd`）でも同一のocclusion queryで`samples_passed=0`（エラーなし）という結果になった**。これにより、GPUハードウェアレベルでの実測手段として最も信頼できるはずだったocclusion query自体がこのドライバ上で機能不全であることが確定し、5・6いずれの「dash画面はゼロ」という結果も**バグの実証ではなくツールの不具合であると判明した**（setup画面での強制再描画テストでも同様にsamples_passed=0だったため、これも同じツール不具合の影響だったと考えられる）。

**7. 🔴🎉🔑🔑 上記5・6を踏まえた最重要の新方針：本機のMesaドライバのバージョンを確認したところ、Raspberry Pi公式リポジトリ由来の非常に新しいバックポート版`26.2.0-1~bpo13+0~rpt2`（`libegl-mesa0`/`libgbm1`/`libgl1-mesa-dri`/`libglx-mesa0`/`mesa-libgallium`等）がインストールされている一方、Debian trixie標準リポジトリには明らかに枯れた`25.0.7-2+deb13u1`が存在することが判明した**。オフラインリプレイ・occlusion queryという独立した2つのGPU観測手段がいずれもこの特定のドライバ上でのみ機能不全を起こしているという事実は、単なる偶然の2重のツール不具合というより、**このバックポート版Mesa/VC4ドライバ自体に何らかの根本的な欠陥がある可能性を強く示唆する**。これは20回のセッションを通じて一度も検証されていなかった、全く新しい切り口であり、これまでの「アプリ・Kivy・GLコマンドストリームはすべて正常なのに画面に出ない」という膠着状態を説明しうる最有力候補となった。

**次回（第22回）の最優先候補（優先度順）**：
0. **最優先・要ユーザー判断：`libegl-mesa0`/`libgbm1`/`libgl1-mesa-dri`/`libglx-mesa0`/`mesa-libgallium`をDebian標準の`25.0.7-2+deb13u1`へダウングレードし（`apt install <pkg>=25.0.7-2+deb13u1`の形で一括指定）、(a) オフラインsnapshot・occlusion queryが正常に機能するようになるか、(b) 本題の`dash`画面の描画欠落自体が解消するか、の両方を確認する。** パッケージのダウングレードは`apt`で理論上は元のバージョンへ戻せる（キャッシュが残っていれば`apt install <pkg>=26.2.0-1~bpo13+0~rpt2`で復元可能）が、ディスプレイ出力に関わる低レベルドライバの変更でありSSH接続自体は生きたまま作業できる一方、万一の非互換で表示系が余計に不安定化するリスクもゼロではないため、**ユーザー立ち会いのもとで実施することを推奨**（今回は自律調査のため実行を見送った）。
1. 上記ダウングレードが効果なしだった場合、GPUハードウェアパフォーマンスカウンタ（`eglretrace --pdrawcalls`）が出力を生成しない問題を深掘りする（apitrace側のバグ報告・Issueの確認、あるいは`--pcalls`/`--pframes`など他の粒度での再試行）。
2. 今回確立した3つの新手法（GL/EGLフック無しのpthreadインジェクタ、`apitrace --blobs`によるテクスチャ内容検証、occlusion queryによるGPU実測）は、ダウングレード後の再検証にそのまま使い回せる。特にocclusion queryはツール不具合さえ解消すれば非常に強力な検証手段になる。

**8. 🔴🎉🔑 第16回セッション以来、5セッションにわたり持ち越されてきた「正体不明のヒント/トースト的な一時要素（画面中央付近の右向き三角形）」の正体を完全特定した**。`switchMainView('dash')`実行の前後・複数時点（switch直後、1/2/3/5/8/12/18/25/32秒後）で`Window.children`のウィジェットツリーを再帰的にスナップショットし比較したところ、t=12秒とt=18秒の間で新たに`HelpBubble`ウィジェット（`pos=[710,420] size=[500,200]`、画面中央よりやや右）が`Window`の直接の子として出現することを確認した。中身は矢印部分（`RelativeLayout`→`BoxLayout`→`Scatter`→`Image`、`size=[15,11]`前後）と本体（`HelpInfo`、`BoxLayout`内に`MDLabel`×2＋`LabelIconButton`「GOT IT」ボタン）で構成される。逆コンパイル済みソース（`autosportlabs/help/helpmanager.pyc`、`pydisasm`で逆アセンブル）のdocstringには「show once only / first time user's help」（初回ユーザー向けの一度きりのヘルプポップアップ、`resource/help/help_text.json`から文言を取得し指定ウィジェットを中心に矢印付きで表示する汎用システム）と明記されており、矢印画像は`autosportlabs/help/help_arrow.png`という実ファイル（ベクター描画ではなく静的PNG画像）、背景は`SmoothRoundedRectangle`（KivyMD独自の角丸矩形canvas命令）と判明した。**このウィジェットが`Window`の直接の子（`RelativeLayout`/`ScreenManager`と兄弟関係）として追加されており`ScreenManager`のcurrent Screen配下ではないことが、実際に正常描画される理由と完全に整合し**、「`ScreenManager`のcurrent Screen配下だけ描画されない」という第14回以来の境界線仮説をさらに補強する第3の実例となった。バグそのものの原因究明には直接寄与しないが、長年の謎だった副次的な観測対象が解決したことで、今後のセッションはこの要素を気にせず本題（`ScreenManager`配下の描画欠落）に集中できる。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：セッション中に作成した複数のテスト用インタポーザ（`timer_inject23.so`、`query_interpose24/25/26.so`、`hint_finder27.so`等、いずれも`/tmp`配下）でrace_captureを何度も再起動したが、いずれもハードウェアへの影響はなし。最終的に`sudo kill -9`で全テストプロセスを終了し、`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み。Mesaパッケージ自体には一切手を加えていない（バージョン確認のみ、ダウングレードは未実施）。

**訂正（同セッション内、公式Mesaドキュメント`docs.mesa3d.org/drivers/vc4.html`調査により判明）**：上記6.のocclusion query（`GL_SAMPLES_PASSED`）が常に`samples_passed=0`を返す件は、**ドライバの不具合ではなく「VC4ハードウェアはocclusion queryを一切サポートしない（query counter bitsは常に0を報告する仕様）」という公式ドキュメントに明記された既知の仕様**と判明した。したがって「本機ドライバ上でoccluion queryが機能しない」こと自体は本題のバグとは無関係であり、今後のセッションでVC4機（Raspberry Pi 3B等）に対してocclusion queryを検証手段として使うこと自体を避けるべきである（同ドキュメントでは他に「`GL_UNSIGNED_INT`インデックスバッファ非対応」「プリミティブのline/point変換非対応」の2点のみが既知の制約として明記されており、いずれも今回の描画欠落症状とは直接関係しない）。一方、5.のオフラインsnapshotリプレイ（`eglretrace -S`）が正常系画面でも単色画像しか返さない件は上記ドキュメントに説明がなく、**依然として原因不明の実ツール限界として残る**。結果として「独立した2つのGPU観測ツールがいずれも壊れている→ドライバ自体に根本的欠陥がある」という上記7.の推論は、根拠の半分（occlusion query）が実は「仕様通り」だったことが判明したため**やや弱まった**。とはいえ本機のMesaが`26.2.0-1~bpo13+0~rpt2`という非常に新しいRaspberry Pi専用バックポートである事実自体は変わらず、Debian標準の枯れた`25.0.7-2+deb13u1`との比較検証（次回最優先候補0）は、eglretrace snapshot不具合の原因切り分けとしても、また万一の本題バグとの関連性を排除する意味でも、依然として次回試す価値のある候補ではあるが、**その優先度・確度は上記の訂正を踏まえてやや控えめに評価すべき**。

**9. 🔴🎉🔑🔑🔑 同セッション内・最終盤で得た、20回のセッションを通じて未検証だった新しい切り口からの決定的な追加知見：「ScreenManagerのcurrent Screen配下だけ描画されない」という第14回以来の境界線仮説を、より広く・より正確な形に精緻化した**。プロセス内で全く新しいウィジェットを動的生成し、ツリー上の異なる位置に追加して`glReadPixels`で直接検証する一連の実験（test28〜33）を行った。

- **test28（`Window`直下に新規`ScreenManager`+`Screen`+緑矩形を追加）**：正常に描画された（`glReadPixels`で400×300=120,000ピクセル分の非透過領域を検出）。グラフィックス命令はKivyの安全機構により別スレッドから直接生成できない（`TypeError: Cannot create graphics instruction outside the main Kivy thread`）と判明したため、`Clock.schedule_once()`でメインスレッドに処理を委譲する手法を確立（今後の標準手法として記録）。
- **test29（既存の壊れた`ScreenManager`と全く同じ親`BoxLayout`の3人目の子として、同様に新規`ScreenManager`+シアン矩形を追加）**：**画面全体（既存のScreenManager/ToolbarViewを含む）が完全に透過（全2,073,600ピクセルが`RGBA(0,0,0,0)`）になった**。
- **test30（`ScreenManager`を使わない単純な`Widget`+オレンジ矩形を同じ`BoxLayout`の3人目の子として追加）**：test29と同じく画面全体が完全に透過。**ScreenManagerというクラス自体は無関係と判明**。
- **test31（ウィジェット追加の前後で明示的に2回`glReadPixels`ダンプを比較）**：**追加前(before)の時点で既に画面全体が完全に透過だった**（`transparent=2073600/2073600`）。追加後(after)も同じく完全に透過。→ test29/30の「透過になった」という結果は、ウィジェット追加によって「壊れた」のではなく、**追加前から既にその場所（サブツリー）が透過状態だった**ことが判明。
- **test32（`BoxLayout`の親である`RelativeLayout`＝`NavigationDrawer`と同階層に同様の`Widget`+矩形を追加）**：同じく完全に透過（before/after共に）。**境界線は`BoxLayout`固有ではなく、`RelativeLayout`のサブツリー全体に及ぶ**ことが判明。
- **test33（`BoxLayout`内に追加した`Widget`に対し`canvas.ask_update()`を10Hzで最大60回連続呼び出しし、5/15/30/60回時点で`glReadPixels`ダンプ）**：0〜5回時点は完全に透過のままだったが、**15回・30回時点で非透過ピクセルが8,392個出現し（オレンジ矩形の一部と推定、120,000ピクセル中の約7%）、その後60回時点で再び完全に透過へ戻った**という、不安定・一時的な描画成功を観測した（`instr.flag_update()`部分は毎回スレッド違反例外で失敗していたが、`canvas.ask_update()`/`Window.canvas.ask_update()`部分は例外なく実行されていた）。

**解釈・今回の意義**：test28（`Window`直下）は常に正常描画され、test29/30/32（`RelativeLayout`サブツリー内のどこであれ、ウィジェット種別を問わず）は追加前から一貫して完全に透過という、極めてクリーンな二分法が得られた。これは「`ScreenManager`のcurrent Screen配下」という従来の境界線の説明よりも、**「アプリの`RelativeLayout`ルートコンテナのサブツリー全体（`ScreenManager`だけでなく`BoxLayout`・`ToolbarView`等、新規に生成した無関係のWidgetすら含む）が、`glReadPixels`による直接観測では一貫して非表示になる」という、より広範囲かつウィジェット種別に依存しない境界線**を示唆する。ただし第14回セッションの「ナビゲーションドロワー・パネル・ポップアップ・カーソルは描画される」という人間による目視確認（`RelativeLayout`直下の`NavigationDrawer`を含む）と、今回のtest32（`RelativeLayout`直下がidle状態では`glReadPixels`で完全に透過）は一見矛盾するように見えるが、これは**NavigationDrawerの「開く」動作等の能動的なアニメーション中（＝毎フレーム強制的に再描画される状態）でのみ正しく表示され、静止・アイドル状態では同様に描画されていない可能性**を示唆しており、test33の「連続強制再描画で一時的に描画が成功した」という結果とも整合する。すなわち、**過去に確立済みの「Kivyの再描画スキップ最適化と、GPU/ドライバのバッファ内容がスワップ間で保持されない制約（EGL_BUFFER_DESTROYED）が組み合わさった構造的な非互換」という根本原因（第9回セッションで実証済み）と、今回得られた知見は矛盾せず、むしろ全く別の手法（動的ウィジェット生成+位置別`glReadPixels`検証）による新たな裏付けとなった**可能性が高い。ただしtest33の強制再描画は「グラフィックス命令を別スレッドから直接操作する」部分が毎回例外で失敗していたにもかかわらず部分的に成功しており、成功のメカニズムは完全には解明できていない。

**次回の最優先候補（このtest28-33シリーズを受けて追加）**：
- `NavigationDrawer`が実際に開いている最中（アニメーション中）とアイドル状態（閉じたまま）の両方で`glReadPixels`ダンプを取り、アイドル状態でも本当に非表示なのかを直接確認する（人間の目視確認との矛盾を解消する最優先実験）。
- test33の force-redraw手法を洗練させる：`instr.flag_update()`によるスレッド違反を避けつつ（`Clock.schedule_once`でメインスレッドから安全に呼ぶ）、より長時間・高頻度の強制再描画を行い、8,392ピクセルの部分的成功が再現・拡大するか、あるいは完全な描画に至るかを検証する。これが成功すれば、根本原因の再確認だけでなく実用的なワークアラウンドの糸口にもなりうる。
- 今回確立した`Clock.schedule_once()`によるメインスレッド委譲パターンは、グラフィックス命令を安全に生成・操作するための標準手法として今後のセッションで再利用する。

**実機（`rc-dash-3b`）の状態（test28-33終了時点）**：test28〜33それぞれについて`sudo kill -9`でテストプロセスを終了し、最終的に`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み。ハードウェアへの影響はなし。

**10. 🔴🎉🔑🔑🔑🔑 test34（NavigationDrawerの開閉テスト）により、上記9.の疑問点（人間の目視確認との矛盾）を解消し、第9回セッションで実証済みの根本原因説を統一的に裏付ける、今回セッション最大の成果を得た**。実際の`NavigationDrawer`インスタンス（`racecapture.menu.navigation_drawer.NavigationDrawer`、KivyMDの`MDNavigationDrawer`ではなく自前実装）を`nav.state = 'open'`で直接プログラム的に開き、①閉じたアイドル状態、②開くアニメーション中（0.08秒間隔で15回連続ダンプ）、③開き終わって2秒後の設定済みアイドル状態、の3段階で`glReadPixels`を比較した。結果：①は完全に透過。②はアニメーション中の一瞬（15回中4回、約0.3秒間）だけ8,392ピクセルの非透過領域が出現し、その後アニメーションが進むにつれ再び透過に戻った。③（`state='open'`を実測で確認済みにもかかわらず）**完全に透過に戻っていた**。

**統一的な解釈**：この「アクティブな連続再描画期間中だけ一瞬コンテンツが見え、静止すると消える」というパターンは、test33（force-redrawループ中に8,392ピクセルが一時出現→消失）と完全に一致する。さらに、これは第9回セッションで実証済みの根本原因──「**Kivyは"変化がなければ再描画をスキップする"最適化を行うが、このGPU/ドライバはバッファ内容をスワップ間で保持しない（`EGL_BUFFER_DESTROYED`、3枚のバッファをローテーション）ため、"スキップされた"領域は次に実際にスキャンアウトされるバッファでは未定義（＝透過）になる**」──と完全に整合する、全く別の手法（動的ウィジェット生成・位置別比較・実際のUI要素の開閉操作）による独立した追加実証と言える。この統一理論は、今回セッションの全観測を矛盾なく説明する：
  - `ScreenManager`のcurrent Screen配下：画面遷移時に1回描画されたきり、その後は「変化なし」としてスキップされ続ける→透過（20回のセッションを通じての中心的な観測）
  - `HelpBubble`：表示中は継続的なフェードアウトアニメーション（opacity変化）で毎フレーム再描画され続ける→正常に見える
  - test28（`Window`直下の新規`ScreenManager`）：生成直後の「初めて描画される」フレームを捉えており、まだ「スキップ」判定がされる前だった可能性が高い（test33/34のように複数フレームにわたる継続観測は行っていない）
  - test29/30/32（`RelativeLayout`サブツリー内の新規ウィジェット）：生成後、静止状態でのみ観測しており、`ScreenManager`content と同じく「スキップ」対象になっていたと考えられる
  - test33/34（強制連続再描画・実際のアニメーション中）：継続的な再描画がかかっている間だけ一時的に見える

**次回への示唆**：この統一理論が正しければ、恒久的な修正には「Kivyの再描画スキップ判定を、このバッファ非保持環境に対応させて無効化する（全フレーム強制フル再描画）」ようなアプローチが必要になる。第9回セッションでは同種のワークアラウンド（gdb注入による毎フレーム`ask_update()`強制）を実機`race_capture`本体に適用する試みが3手法とも効果がなかったと記録されているが、今回のtest33で「`Clock.schedule_once`経由・10Hz・60回」という異なるアプローチで**部分的な成功（8,392ピクセル分）**を得られたことは、この方向性が完全に手詰まりではない可能性を示唆する。次回は「グラフィックス命令への直接アクセスを伴わない安全な形で、`Window`全体に対して毎フレーム確実に強制フル再描画をかけ続ける」仕組みを、より洗練された形で実装・検証することを最優先候補とする。

**実機（`rc-dash-3b`）の状態（test34終了時点）**：`sudo kill -9`でテストプロセスを終了し、`run_racecapture_rpi.sh -w 1`で正常に再起動・復旧したことを確認済み。ハードウェアへの影響はなし。

**11. ⚠️ test35（実用ワークアラウンド案の検証・セッション最後の実験）：`switchMainView('dash')`実行後、Kivyネイティブの`Clock.schedule_interval(callback, 0)`で`Window.canvas`・`ScreenManager.canvas`・current Screen・その全子孫ウィジェットのcanvasに対し毎フレーム`ask_update()`を呼び続けるワークアラウンド案を試したが、11秒間観測しても本物のダッシュボードコンテンツ（ゲージ・ラベル等）は一切出現しなかった**。6秒後・11秒後の時点で117ピクセルだけ非透過領域が安定して存在したが、バウンディングボックス（x=1199-1209, y=512-526）を確認したところ、これは`DashboardView`のコンテンツではなく、**このテストで`switchMainView('dash')`を呼んだことで再度トリガーされた`HelpBubble`ヒントの矢印部分**（座標が第16-19回セッションで特定した位置と一致）であると判明した。すなわち本ワークアラウンド案は**dash画面本体の描画には効果がなかった**。また11秒間でスワップ回数がわずか51回程度と低いままだったことから、`ask_update()`の呼び出しだけでは`Window`/`EventLoop`レベルで「今回は本当にフル再描画が必要」と正しく認識されていない可能性が高い（単純な`ask_update()`だけでは不十分で、より強い強制手段が必要と考えられる）。**この結果は第9回セッションの「同種のワークアラウンドを実機race_capture本体へ適用する試み（3手法）はいずれも効果がなかった」という記録と一致する独立の再確認となった**。次回、この方向性をさらに追求する場合は、`ask_update()`より強い強制再描画トリガー（例：ウィジェットの`size`/`pos`をごくわずかに変化させてから元に戻す、または`Window`の`_needs_redraw`的な内部フラグを直接調べる）を検討する必要がある。

**実機（`rc-dash-3b`）の状態（test35・セッション終了時点）**：`sudo kill -9`でテストプロセスを終了し、`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）で正常に再起動・復旧したことを確認済み。ハードウェアへの影響はなし。今回セッション（第21回）で作成した全テスト用インタポーザ・スクリプトは`/tmp`配下に残置（次回セッションで再利用可能、再起動で消滅する想定）。

---

**今回のセッション（4-4-2続き・第22回、ユーザー不在の自律調査・4時間枠）で得た知見：「実プロパティ変化」「毎フレームask_update()」いずれも強制再描画ワークアラウンドとして機能しないことを確定、GL描画コール数の直接計測は自作インタポーザの手法的欠陥により今回は結論を出せず、`/tmp`がtmpfsで再起動により消滅する点を再確認**：

**背景**：第21回セッションの「次回（第22回）の最優先候補」のうち、候補0（Mesaダウングレード）は同セッション自身が「要ユーザー判断・立ち会い推奨」と明記していたため、ユーザー不在の本セッションでは見送った。代わりに候補1・2の周辺、および根本原因の統一理論（Kivyの再描画スキップ最適化 x GPU/ドライバのバッファ非保持）から導かれる「次の一手」として、test33/34で部分的成功のみだった強制再描画ワークアラウンドの精緻化に取り組んだ。

**1. 🔴 実プロパティ変化によるjitterワークアラウンド、3種類全てで完全に効果なしと確定**：
「ask_update()のようなフラグだけの更新ではなく、本物の値の変化を継続的に注入すればNavigationDrawerのアニメーション中と同様に描画され続けるのでは」という仮説のもと、以下3種類を実機`race_capture`（setup画面、ESP32接続済み・GPS/テレメトリ正常受信の完全に正常な稼働状態）で検証した。いずれも`glReadPixels`によるKMS実スキャンアウトバッファの直接読み取りで判定。
   - (a) `current_screen.y`を毎フレーム0.0↔1.0で往復（小振幅）：swap#1050～1215（jitter有効区間）で非透過ピクセル0、効果なし。
   - (b) `ScreenManager.y`を毎フレーム0.0↔30.0で往復（大振幅、視覚的にも明確な変化）：swap#525～660で同じく非透過ピクセル0。振幅の大きさは無関係と判明。
   - (c) Kivy純正の`Animation`クラスでping-pongアニメーション（`Animation(y=target, duration=0.3)`を`on_complete`で自己再起動）を`ScreenManager`に対して起動：Kivy自身のClock駆動による連続補間更新にもかかわらず、swap#1110～1500以上にわたって非透過ピクセル0。
   - **結論**：test34で観測された「NavigationDrawerの開閉アニメーション中だけ一時的に見える」現象は、単純な「プロパティが実際に変化し続けているかどうか」では再現できないと判明した。NavigationDrawer固有の何か（StencilViewの再評価タイミング、またはアニメーション対象プロパティの種類等）に依存する可能性が高く、汎用的なワークアラウンドの糸口としては使えないと結論づける。

**2. 🔴 `Window.canvas.ask_update()` / `sm.canvas.ask_update()` / `screen.canvas.ask_update()` を毎フレーム（10Hzではなく実際のswap毎、Pi 3Bの低フレームレート下で実質同等以上の頻度）呼び続けても効果なしと再確認**：
第9回・第21回(test35)の知見（gdb注入・Clock.schedule_interval経由でも効果なし）を、今回は「本物のクリーンな再起動直後の状態」かつ「eglSwapBuffersフック内から直接呼ぶ、最もオーバーヘッドが少ない経路」で追加確認した。結果は同じく非透過ピクセル0で、既存knowledgeを追加の独立した手法で裏付けた。

**3. ⚠️ 重要な方法論上の教訓：本セッションで実装したLD_PRELOADベースの`glDrawElements`/`glDrawArrays`直接フック（`jitter_interpose30.c`、第21回`egl_interpose21/22.c`と同じ「直接エクスポートしたシンボルがLD_PRELOADのロード順で勝つ」方式）は、このビルド環境では機能していないと判明した**。
   - 実機`race_capture`のsetup/dash画面で継続的に`drawElements=0, drawArrays=0`（swap#480～1215、ask_update()連打中も含め一貫してゼロ）という結果を得たため、当初は「GLレベルで描画コールが一切発行されていない」という、根本原因理論を裏付ける決定的な直接証拠かと考えた。
   - しかし念のためのサニティチェックとして、`Window.add_widget()`で新規に緑色矩形(400x300)を追加したところ、`glReadPixels`では正しく120,000ピクセル分の緑色が複数フレームにわたり安定して検出された（＝実際に描画され画面に残り続けている）にもかかわらず、**同じ区間で`glDrawElements`/`glDrawArrays`のフックカウントは0のままだった**。これは「本当に描画コールがゼロ」という解釈と矛盾する（何かが描画されている以上、GLの描画コールは必ず発行されているはず）ため、**このセッションで作成したフック自体が実際のGL描画コールを捕捉できていない（false negative）と結論づける**。
   - 原因は未特定。第21回セッションのコメントには「`glDrawElements`/`glDrawArrays`は通常のPLT/GOT動的リンクで解決されるため、直接エクスポートしたシンボルがLD_PRELOADのロード順で勝つ」とあるが、これは**第21回では`apitrace`（`egltrace.so`）と併用していた**（`LD_PRELOAD=timer_inject23.so:egltrace.so`）ため、実際にはapitrace側のインターセプト機構に依存していた可能性がある。**今後GL描画コール数を数える場合は、自作インタポーザの直接シンボルフックに頼らず、第21回で確立済みの`apitrace`（`apitrace trace -a egl`→`apitrace dump --grep`）を第一選択とすること**。この教訓により、本セッション前半の「drawElements=0」に基づく考察・仮説はすべて撤回する（前提となる計測手法が壊れていたため）。
   - 一方、**`glReadPixels`による画面内容の直接読み取り（サニティチェックの新規ウィジェットで正しく緑色を検出できた）自体の信頼性は今回のサニティチェックで再確認・裏付けられた**。したがって上記1・2の「非透過ピクセル0」という結果自体（drawElementsカウントとは独立した`glReadPixels`ベースの判定）は引き続き有効な知見として扱ってよい。

**4. 運用上の再確認：`/tmp`はtmpfsであり、Piの再起動で内容が完全に消える（`mount`で確認：`tmpfs on /tmp type tmpfs`）**。第21回セッションの記録にも「次回リブートで消滅する想定」と既に明記されていたが、今回セッション中に実際にPiを再起動した際、事前の再コンパイルを怠ったため`jitter_interpose30.so`が消え`LD_PRELOAD`が無言で失敗する（`/proc/<pid>/environ`にはLD_PRELOADの指定が残るが`/proc/<pid>/maps`にロードされない）事象に直面し、原因特定に時間を要した。**次回セッション以降、Piを再起動した後は`/tmp`配下の`.c`/`.so`を必ず再ビルドしてから使うこと**（`~/decompile_4-4-2/`はホームディレクトリ配下のため再起動後も残る）。

**5. 実機を再起動した副次的効果として、「今回のセッション内で複数回kill/relaunchを繰り返したこと自体が何らかの不安定要因になっていないか」という懸念を検証できた**：再起動直後のクリーンな状態でも上記1・2と同じ結果（非透過ピクセル0）が再現したため、本セッション内での繰り返しテストによる状態劣化が原因ではなく、再現性のある症状であることを確認した。

**次回の最優先候補（優先度順、更新）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し、詳細は同セッションの記述を参照）。
1. GL描画コール数の実測は自作インタポーザではなく`apitrace`を使うこと。特に「setup/dash画面がidle状態のとき、`glDrawElements`は本当にゼロになるのか、それとも第21回セッション同様に継続的に発行されているのか」を`apitrace`で正確に再検証する価値は高い（今回のフックの欠陥により未決着のまま）。決着すれば「Kivyが再描画自体をスキップしている」のか「描画はされているがバッファに反映されない」のかの最終的な切り分けになる。
2. 強制再描画ワークアラウンド路線（プロパティjitter・ask_update()系）は今回で3種類×複数回にわたり全て否定されたため、**この方向性は事実上手詰まりと判断し、次回以降は深追いしない**。NavigationDrawer固有の一時的成功（test34）の再現条件を追加調査する価値は低いと判断する。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：セッション中に1回`sudo reboot`で実機を再起動した（クリーンな状態での再検証目的）。最終的に`sudo kill -9`で全テストプロセスを終了し、`getty@tty1.service`を`systemctl start`で再開、標準の自動ログイン→`run_racecapture_rpi.sh -w 1`（LD_PRELOADなし、通常のwatchdog付き）経由で正常に起動・復旧したことを確認済み（PID 1466、ESP32接続・通信正常）。ハードウェアへの影響はなし。今回作成したインタポーザ一式（`jitter_interpose28/29/30.c`等）・スクリプトは`/tmp`配下に残置しているが、上記4.の通り次回セッション開始時のPi再起動有無に関わらず使う前に再ビルドが必要な点に注意。

---

**今回のセッション（4-4-2続き・第22回、続き）で得た決定的な訂正：`apitrace`による正確な再計測により、「Kivyがidle時に再描画自体をスキップする」という第9回セッション以来の統一理論の一部が誤りだったと確定した**：

**背景**：上記の通り自作LD_PRELOADによる`glDrawElements`直接フックがサニティチェックで無効と判明したため、第21回セッションで確立済みの`apitrace`（`LD_PRELOAD=<自作pthreadインジェクタ>:egltrace.so`方式、GLシンボルは一切フックしない設計にして`apitrace`本体と競合を避けた）で正確に再計測した。今回新規作成した`autoswitch31.c`（GLフック無し、`switchMainView('dash')`実行後は何もせず放置するだけのpthreadインジェクタ、`app.root`未初期化による`AttributeError`が初回発生したためリトライループを追加）を使用。

**1. 🔴🎉🔑 `dash`画面へ切り替え後、約50秒間の完全なidle区間（ユーザー操作もタッチ操作エミュレーションも一切なし）を含む全384フレームを`apitrace`でトレースし、`glDrawElements`の発行回数をフレームごとに集計したところ、idle区間全体を通じて1フレームも欠かさず295〜434回（後半は396回で完全に安定）という高い頻度で継続的に発行され続けていることを確定した**（`apitrace dump --grep='^(eglSwapBuffers|glDrawElements|glDrawArrays)$'`でスワップ境界とdraw呼び出しを抽出し、Pythonでフレーム間差分を集計。トレース終盤・call番号150万台の代表サンプルを`apitrace dump --calls=`で目視確認したところ、頂点属性ポインタ・ユニフォーム行列・テクスチャバインド・ステンシル操作を含む完全に健全な描画コマンド列で、色`(0.153, 0.682, 0.376)`のような実際のUI色も含まれていた）。`glDrawArrays`は0回（このアプリは一貫して`glDrawElements`のみ使用）。
   - **これは「Kivyの変化なし再描画スキップ最適化により、idle中は描画コールの発行自体が止まる」という第9回セッション以来ずっと統一理論の一方の柱としてきた説明を直接的に否定する**。実際にはidle中も一切スキップされず、フレームごとに数百回規模の描画コールが安定して発行され続けている。
   - 本セッション前半で試した3種類の強制再描画ワークアラウンド（プロパティjitter・Animation・毎フレームask_update()）がいずれも無効だった理由も、これで自然に説明できる：**そもそも「描画コールの発行を再開させる」ことが目的のワークアラウンドだったが、描画コールは最初から一度も止まっていなかったため、的外れな対策だった**。
   - 一方、第12回セッションで確定した「GLコマンドは正しく発行されKMSページフリップも正常なのに画面には背景色（またはRelativeLayoutサブツリーの場合は透過）しか出ない」という核心的な矛盾、および第21回セッションで確定した「テクスチャ内容も正常」という知見とは矛盾せず、むしろ整合する（今回はこれを「idle時も含め常に」という条件でさらに強く裏付けた形）。

**2. 統一理論の修正が必要な範囲の整理**：
   - ❌ **誤りと判明**：「Kivyのidle時再描画スキップ最適化」が原因の一部であるという説明。
   - ✅ **今回のセッションでも変わらず支持される**：GPU内部読み戻し（`glReadPixels`、`Window.screenshot()`）は正常なウィジェットツリーでは正しい内容を返す一方、`RelativeLayout`ルートコンテナのサブツリー内（ScreenManager等）は継続的に大量の正常な描画コールが発行されているにもかかわらず`glReadPixels`で一貫して透過として観測される、という核心的な乖離（第12〜21回、および本セッション前半のjitter実験でも再確認）。
   - **未解決のまま残る最大の謎**：「正しい内容の描画コールが継続的に発行されているのに、なぜ特定のサブツリーだけ実際のピクセルとして現れないのか」。次回はこの一点に集中すべきで、「描画を再開させる」系のワークアラウンドは的外れと判明したため試す必要はない。

**次回の最優先候補（優先度順、更新）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し）。
1. 今回`apitrace`で確立した「idle中でも継続的にdraw callが発行される」計測手法を使い、**「ScreenManagerのcurrent Screen配下」のdraw callと「Window直下（正常に表示される）」のdraw callを、同じidle区間で見比べる**。両方とも同程度の頻度で発行されているのか、それとも透過側だけ実は頻度が低いのか（今回は透過側＝dash画面全体でしか計測しておらず、正常系との対比はまだ行っていない）。
2. `glDrawElements`の引数（`glBindBuffer`で指定されるバッファID等）が、idle中に**同じフレームで毎回同一のバッファ/シェーダー状態を指しているか、それとも呼び出しごとに再構築されているか**を確認する。「描画コールは発行されるが中身が古いキャッシュのままGPUに送られていない」ような経路が残っていないか、`apitrace`の`--calls`で連続する複数フレームの同一箇所を比較する。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`kill -TERM`でトレース対象プロセスを正常終了させ（トレースファイル`/tmp/rc22.trace`、18.6MB、確定済み）、`getty@tty1.service`を`systemctl start`で再開、標準の自動ログイン経由で`race_capture`が正常に復旧したことを確認済み（PID 2048、通常のwatchdog付き、LD_PRELOADなし）。ハードウェアへの影響はなし。`/tmp/rc22.trace`・`/tmp/autoswitch31.c`等は次回セッションで再利用可能だが、Piが再起動していれば消えているため使用前に要再確認・再ビルド。

---

**今回のセッション（4-4-2続き・第22回、2時間延長分）で得た知見：Window直下（確実に表示される）とdash画面（透過）のdraw callを同一トレース内で直接比較したが、GLステート面では有意な違いを発見できず、代わりに「確実に表示され続けている静的ウィジェットですら、実際には全フレームのうち約半分でしか描画コールが発行されていない」という、根本原因の理解を複雑にする新たな観測を得た**：

**背景**：前回（本セッション前半）で「idle中もdraw callは継続的に発行される」ことをapitraceで確定したため、次の一手として「Window直下に一意な色（RGB=0.123456, 0.234567, 0.345678、実UIでは絶対に使われない値）を持つマーカー矩形を追加し、同じapitraceトレース内で`ScreenManager`配下（dash画面、透過）のdraw callと直接比較する」実験を行った（`autoswitch32.c`、`Clock.schedule_once`経由でメインスレッドから安全にグラフィックス命令を生成する既存手法を使用）。

**1. マーカーウィジェットの描画コール（`glUniform4f`のv0/v1/v2でユニーク色を検出）周辺のGLステートを、隣接するdash画面content（例：色`(0.3764706, 0.4901961, 0.5450981)`）のdraw callと突き合わせたが、構造上の違いは見つからなかった**：`glBindTexture`→`glBindBuffer`(ELEMENT/ARRAY)→`glVertexAttribPointer`×2→`glDrawElements`という定型パターンがマーカー・dash content問わず完全に同一。フレーム全体（1フレームあたり約4200 API呼び出し）を通じて`glViewport`・`glBindFramebuffer`・`glBlendFunc`・`glScissor`の明示呼び出しは一度も見られず（コンテキスト初期化時に一度設定されたまま、という既存knowledge=第11回セッションと整合）、`glStencilTest`のenable/disableはウィジェットのクリッピング範囲ごとに頻繁に切り替わるが、マーカーの描画とその直前直後のdash content描画はいずれも「ステンシル無効」の同じ状態区間内にあった。**apitraceで捕捉できるGL API呼び出しの引数レベルでは、「確実に表示される描画」と「透過する描画」を区別する手がかりが見つからない**、という第12回セッション以来の結論を追加のクロスチェックでも再確認した形になる。

**2. 🔴🔑 予期しない副産物：マーカー（確実に表示され、`glReadPixels`でも安定して検出され続ける静的ウィジェット）の描画コールが、全844スワップ中421回（約50%）でしか検出されなかった**（比較対象のdash画面content色は154回、約18%）。もしKivyが本当に「毎フレーム無条件に全キャンバスを再発行」しているなら、変化しない静的ウィジェットの描画コールも100%の頻度で現れるはずだが、実際には約半分に留まっていた。それにもかかわらず、本セッション前半で同じ種類のマーカーウィジェットを`glReadPixels`で複数回（15スワップ間隔）サンプリングした際は、全サンプルで安定して同じピクセル数（120,000px）を検出しており、**目に見える範囲では一切のちらつき・消失は観測されていない**。
   - この「描画コールは半分の頻度でしか発行されないのに、見た目は常に安定して見える」という組み合わせは、**「3枚のバッファをローテーションしながら、実際には何らかの形でバッファ間の内容が部分的に保持されている」可能性**を示唆しており、第9回セッション以来の「`EGL_BUFFER_DESTROYED`でバッファ内容はスワップ間で一切保持されない」という前提を、少なくとも単純な形では再検証する必要があるかもしれない。ただし、この観測はまだ一度の実験のみに基づくものであり、そもそも「50%」という数字自体の意味（Kivyの内部フレームスキップ機構によるものか、apitraceのグレップパターンの取りこぼしか等）を含めて未検証・未解釈のまま次回へ持ち越す。

**次回の最優先候補（優先度順、更新）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し）。
1. 🆕 **マーカーウィジェットの描画コール発行頻度が約50%だった件を追加検証する**：(a) 同じ実験を複数回繰り返して50%という数字が安定して再現するか、(b) `glReadPixels`のサンプリングタイミングをスワップ単位で密に取り、実際に「描画コールが無い」フレームで見た目のピクセル内容がどうなっているか（本当に前フレームの内容を保持しているのか）を直接確認する、(c) dash画面content側も同様に「draw callがない」フレームでの実際の見え方（透過なのか、何かが残っているのか）を確認する。
2. `glDrawElements`の引数（バッファID等）が、draw callが発行される/されないフレーム間で一貫しているかの確認（今回は未着手のまま）。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`kill -TERM`でトレース対象プロセスを正常終了させ（トレースファイル`/tmp/rc23.trace`、確定済み）、`getty@tty1.service`を`systemctl start`で再開、標準の自動ログイン経由で`race_capture`が正常に復旧したことを確認済み（PID 2701、通常のwatchdog付き、LD_PRELOADなし）。ハードウェアへの影響はなし。

---

**今回のセッション（4-4-2続き・第22回、続き）で得た追加知見：マーカーウィジェットの描画コール発行頻度「約50%」が、独立した2回目の実験でもほぼ完全に一致する数字（誤差0.01%未満）で再現し、単発のノイズではなく安定した決定論的な現象であると確定した**：

**1. 🔴🔑 同一条件（`autoswitch32.so`でdash画面へ切り替え＋Window直下マーカー追加、約45秒のidle区間をapitraceで記録）で実験を1回繰り返したところ、1回目：421/844スワップ（49.88%）、2回目：379/760スワップ（49.87%）と、総スワップ数自体は異なるにもかかわらずマーカーの描画コール発行率はほぼ完全に一致した**。この精度の高い再現性は、単なる測定ノイズやタイミング依存の偶然ではなく、**何らかの決定論的なメカニズムにより、確実に表示され続けている静的ウィジェットであっても実際には約2スワップに1回しか描画コールが発行されていない**ことを強く示唆する。
   - 有力な新仮説：**`eglSwapBuffers`が実際の描画フレーム1回につき2回呼ばれている（例：ダブルバッファリングの内部実装上の理由で、"見かけ上のスワップ回数"が実際にKivyが描画を更新する頻度の2倍になっている）可能性**。もしこれが正しければ、「マーカーの描画コールは全スワップの半分でしか検出されない」という観測は、実際には「Kivyは正しく毎フレーム描画しているが、apitraceが数えている“スワップ”の単位が実際の描画更新の半分の粒度である」という、計測上の解釈の問題に帰着するかもしれない。この仮説は次回、`eglSwapBuffers`の呼び出しごとに実際にKMS側のページフリップ（バッファ内容の変化）が起きているかを`/sys/kernel/debug/dri/0/state`（第12回セッションで確立済みの手法）と突き合わせることで検証可能。

**次回の最優先候補（優先度順、更新）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し）。
1. 🆕 **「約50%」の原因を切り分ける**：`eglSwapBuffers`の奇数回目・偶数回目で`/sys/kernel/debug/dri/0/state`のfb_idが実際に変化しているかを突き合わせ、「2回に1回は実質的なno-opスワップ」という仮説を検証する。もしこれが正しいと確定すれば、これまでの「idle中もdraw callが継続的に発行される」という第22回前半の結論も「実際の描画更新頻度」で言えば半分に修正する必要が出てくる可能性がある。
2. `glReadPixels`のサンプリングタイミングをスワップ単位で密に取り、実際に「描画コールが無い」フレームで見た目のピクセル内容がどうなっているか（本当に前フレームの内容を保持しているのか）を直接確認する（前回から持ち越し）。
3. dash画面content側も同様に「draw callがない」フレームでの実際の見え方を確認する（前回から持ち越し）。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`kill -TERM`でトレース対象プロセスを正常終了させ（トレースファイル`/tmp/rc24.trace`、確定済み）、`getty@tty1.service`を`systemctl start`で再開、標準の自動ログイン経由で`race_capture`が正常に復旧したことを確認済み（PID 2942、通常のwatchdog付き、LD_PRELOADなし）。ハードウェアへの影響はなし。

---

**今回のセッション（4-4-2続き・第22回、最終盤）で得た知見：「eglSwapBuffersが実描画更新頻度の2倍」という自ら立てた新仮説を直接検証で否定し、「約50%」という数字自体は計測アーティファクトではなく本物の現象であることをクロスチェックで再確認した。DRM側のバッファローテーション自体は完全に正常・規則的であると確定し、謎の焦点をより明確化した**：

**1. 🔴 新規インタポーザ`fbtrack33.c`（`eglSwapBuffers`フックのみ、GLシンボルは一切フックせず、毎スワップ`/sys/kernel/debug/dri/0/state`を読んで実際にKMSでアクティブなfb idを記録）で、上記の仮説（「2回に1回はno-opスワップ」）を検証したところ、**完全に否定された**：dash画面idle中の348回連続スワップ全てで、fb idは`672→674→675→672→674→675…`という3枚のバッファを一切乱れなく規則正しくローテーションし続けており、**同じfb idが2回連続で現れることは一度もなかった**。すなわち、`eglSwapBuffers`の呼び出し1回1回が、間違いなく実際のKMSページフリップ（新しい物理バッファへの切り替え）に対応している。第12回セッションで確立済みの「DRM/KMSのページフリップ機構自体は完全に正常」という知見を、より長時間・より簡便な手法（gdb不要、`eglSwapBuffers`フック内から直接debugfsを読むだけ）で改めて裏付けた形にもなった。

**2. 🔴🔑 マーカーウィジェットの描画コール（`glUniform4f`でのユニーク色検出、421回）と、そのVBO（頂点バッファ）のバインド回数（`glBindBuffer(buffer=807)`）を同一トレース内で突き合わせたところ、両者は完全に一致（421=421）した**。これにより「uniform値のGL側キャッシュにより`glUniform4f`呼び出し自体は省略されるが実際のバインド・描画は毎回行われている」という、より単純な計測アーティファクト説を否定でき、**「マーカーの描画シーケンス（バインド＋描画）自体が本当に約50%のスワップでしか発行されていない」ことが、独立した2つの指標で確認された**。

**3. 現時点での整理（未解決の核心）**：DRM側は3枚のバッファへ一切乱れなく規則正しくページフリップし続けている（1.）。にもかかわらず、確実に画面に表示され続けている（`glReadPixels`で常に安定検出）静的マーカーの描画コールは全スワップの約半分でしか発行されていない（2.、第22回続き分）。バッファ内容がスワップ間で保持されない（`EGL_BUFFER_DESTROYED`、第9回セッション）という前提と、この「50%」「常に安定して見える」という2つの事実を単純な形で両立させる説明はまだ見つかっていない。次回はこの三者（規則正しいバッファローテーション／間欠的な描画コール／安定した見た目）を統一的に説明できるモデルの構築に集中すべきである。

**次回の最優先候補（優先度順、更新）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し）。
1. 🆕 **「swap番号→fb id」（`fbtrack33.c`で確立済み）と「swap番号→マーカー描画コールの有無」（`glUniform4f`または`glBindBuffer`の検出、apitrace）を同一実行内で同時に記録し、fb id 672/674/675のそれぞれについて「マーカーが描画された回数／されなかった回数」を集計する**。もし特定のfb id（例えば672だけ）に偏って描画されている、あるいは3枚のうち常に同じ1〜2枚だけが更新されているといった偏りがあれば、「実は3枚のうち特定のバッファだけが実際にスキャンアウトされている」といった新しい仮説の手がかりになる可能性がある。
2. `glReadPixels`のサンプリングタイミングをスワップ単位で密に取り、実際に「描画コールが無い」フレームで見た目のピクセル内容がどうなっているか（本当に前フレームの内容を保持しているのか）を直接確認する（前回から持ち越し）。
3. dash画面content側も同様に「draw callがない」フレームでの実際の見え方を確認する（前回から持ち越し）。

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`sudo kill -9`でテストプロセスを終了し、`getty@tty1.service`を`systemctl start`で再開、標準の自動ログイン経由で`race_capture`が正常に復旧したことを確認済み（PID 3259、通常のwatchdog付き、LD_PRELOADなし）。ハードウェアへの影響はなし。

---

**🔴🚨 重要な訂正（4-4-2続き・第22回、1時間延長分）：直前の3件のコミットで報告した「マーカーウィジェットの描画コール発行頻度が約50%」という結果は、`apitrace dump`の出力形式に起因する自分自身の集計バグによる誤りであり、実際には約99.7%（ほぼ毎フレーム）だったと判明した。これに伴い、「約50%の再現性確認」および「eglSwapBuffersが実描画更新頻度の2倍」という仮説とその検証（DRM debugfsでの反証）も、存在しない現象を追いかけていたことになる**：

**原因**：`apitrace dump --grep=PATTERN`は、マッチした各行の直後に空行を1行挿入する（フレーム区切りを見やすくするための仕様と推測される）。「swap番号→描画コールの有無」を比較するため、①マーカーの色を`grep -c`で数える（空行は`0.123456`にマッチしないため正しくカウントされる）のに対し、②総スワップ数を`--grep='^eglSwapBuffers$'`で絞り込んだ出力に対して`wc -l`で数えた（絞り込んだ結果、実際のマッチ行と空行が1:1で交互に並ぶため、`wc -l`の値が実際のスワップ数のちょうど2倍に膨れ上がっていた）。この非対称な集計方法の組み合わせにより、実際には「421/422（99.76%）」「379/380（99.74%）」であるべきところを「421/844（49.88%）」「379/760（49.87%）」と誤って算出してしまった。

**訂正の検証**：`apitrace dump --grep='^eglSwapBuffers$' | grep -c eglSwapBuffers`（空行を数えない）で再集計したところ、rc23.traceは422スワップ、rc24.traceは380スワップとなり、マーカー描画回数（421・379）とほぼ完全に一致することを確認した。また、eglSwapBuffers・glUniform4fを同時に`--grep`で抽出しPythonで「各スワップ区間内にマーカーのglUniform4fが存在するか」を直接判定する独立した方法でも、rc24.traceで379/380（99.7%）という整合する結果を得た。

**今回の一連の誤りが調査全体に与える影響の整理**：
- ❌ **完全に撤回**：「マーカー描画コールが約50%の頻度」「この50%が2回の実験で再現した」「`eglSwapBuffers`が実描画更新頻度の2倍」という3つの結論・仮説はいずれも存在しない現象に基づくものであり、撤回する。
- ✅ **引き続き有効**：`fbtrack33.c`によるDRM debugfsの直接読み取り自体（fb id 672→674→675の規則正しいローテーション、348回連続で一切乱れなし）は、`apitrace`のテキスト出力を一切経由しない独立した計測（C言語の整数カウンタ`g_swap_count`をインタポーザ自身が保持）であり、上記のバグの影響を受けない。**結果として「DRM/KMSのページフリップ機構は完全に正常」という第12回セッション以来の結論を追加で裏付けた、という当初の評価はそのまま有効**（ただし「50%現象を説明する仮説の反証」という文脈づけは誤りだったため撤回し、単なる正常系の追加確認として位置づけ直す）。
- ✅ **引き続き有効**：本セッション前半の「idle中もdash画面のglDrawElementsが継続的に295〜434回/フレーム発行され続ける」という結論は、**`grep -n`による行番号の差分計算**（`wc -l`ではない別の手法）で導出したものであり、今回発覚したバグの影響を受けない（空行はスワップ境界に1行だけ挟まるため、行番号の差分は最大でも1のずれに留まり、300〜400という規模の数字には実質的な影響がない）。**「Kivyがidle時に再描画コールをスキップする」という統一理論の一部を否定した、という第22回前半の結論は訂正の必要がない**。
- **教訓**：`apitrace dump`の出力を件数集計に使う場合、`--grep`で絞り込んだ後に`wc -l`を使うと、絞り込みの結果マッチ行と空行が1:1で交互に並ぶケースで実際の件数の2倍を返すことがある。**今後は`grep -c <パターン>`（実際にマッチする行だけを数える）を使うか、絞り込まずに`--calls`でPythonスクリプト側でパースする方式を徹底すること。**

**次回の最優先候補（優先度順、更新・上記の訂正を反映）**：
0. 引き続き最優先・要ユーザー判断：Mesaダウングレード検証（第21回から持ち越し）。
1. 上記の訂正により「マーカー描画頻度」関連の調査課題（旧・次回候補1〜3）はクローズする。核心的な謎は第22回前半の結論のまま変わらない：**「正しい描画コールがidle中も継続的に（ほぼ毎フレーム）発行されているのに、なぜ`RelativeLayout`ルートコンテナのサブツリーだけ`glReadPixels`で一貫して透過として観測されるのか」**。

**追記：`eglretrace -D`によるマーカー・dash content間のGLステート全項目比較を実施したが有意差は見つからなかった**（既存の`rc23.trace`を再利用、実機への新規操作なし）。call 90586（マーカー、確実に表示される）とcall 90594（dash画面のTRIANGLE_FANゲージ、透過）それぞれの完全なGLステートJSONを`WAFFLE_PLATFORM=gbm eglretrace -D <call> <trace>`で取得し差分を取ったところ、①バインドされているバッファID・サイズが異なるのは当然の差（各ウィジェット固有のVBO）、②両者とも実際に使われる頂点座標はいずれも妥当な画面内スクリーン座標（マーカー：x=1600-1900/y=850-1050、dash content：x≈700-1200/y≈420-620の滑らかな曲線状データ、TRIANGLE_FANによる円弧・ゲージ形状と整合）、③頂点バッファの末尾（実際の描画には使われないインデックス範囲外の領域）にはいずれも過去のデータやデノーマル値のようなゴミが残っているが、これは通常のVBO再利用・容量超過確保による一般的な現象で両者に共通、という結果だった。**GLステートの引数・頂点データレベルでは、表示される描画と透過する描画を区別する手がかりが依然として見つからない**。次回はこの一点に立ち返り、今回確立した信頼できる計測手法（`apitrace`での`grep -c`集計、`fbtrack33.c`でのDRM debugfs直接読み取り、`eglretrace -D`でのGLステート比較）を土台に、Mesaダウングレード検証など全く別のレイヤーへの転換を検討すべき段階に来ている可能性がある。

---

**今回のセッション（4-4-2続き・第23回、ユーザー立ち会いのもとで実施）で得た知見：2セッション連続で持ち越されてきた最優先候補「Mesaダウングレード検証」を実施したが、症状に一切変化はなく、Mesaバージョンが根本原因であるという仮説は明確に否定された**：

**背景**：ユーザーが数時間立ち会い可能とのことだったため、第21回セッションから「要ユーザー判断・立ち会い推奨」として持ち越されていた最優先候補0に初めて着手した。

**1. 🔴 `libegl-mesa0`/`libgbm1`/`libgl1-mesa-dri`/`libglx-mesa0`/`mesa-libgallium`を、インストール済みのRaspberry Pi公式バックポート版`26.2.0-1~bpo13+0~rpt2`からDebian標準の`25.0.7-2+deb13u1`へ`apt-get install --allow-downgrades <pkg>=25.0.7-2+deb13u1`で一括ダウングレードした**（事前に`--simulate`でドライラン確認済み。副作用として`vdpau-driver-all`が依存関係により削除されたが、これは動画デコードアクセラレーション用パッケージで本題の描画欠落問題とは無関係）。ダウングレード後、`race_capture`プロセスを`kill -9`→`systemctl restart getty@tty1.service`で再起動し新ライブラリを読み込ませた（`kill`だけではtty1のログインシェル自体が終了し自動復旧しないため、`getty@tty1.service`の再起動が必要と判明。第9回セッション以来の記録にあった手順を再確認した形）。
   - **ユーザーが実機画面を直接目視確認した結果、setup画面のポップアップ・サイドメニューは従来通り表示される一方、dash画面のメーター・ゲージ等のグラフィックは今回も一切表示されず、昨日までと全く同じ挙動だった**。ESP32との接続も切れることなく継続し、`~/racecapture.log`でも`{"s":0}`のテレメトリストリームメッセージが途切れず送受信され続けていることを確認した（表示以外は正常）。
   - **結論**：Mesaのバージョン（Raspberry Pi公式バックポート版か、Debian標準の枯れた版か）は描画欠落症状の原因ではないと確定した。第21回セッションで提起された「異常に新しいMesaバックポート版」という真犯人候補は、これで明確に排除できる。

**2. 検証後、直ちにMesaパッケージ一式を`apt-get install --allow-downgrades <pkg>=26.2.0-1~bpo13+0~rpt2 vdpau-driver-all`で元のバックポート版へ復元し（`vdpau-driver-all`も再インストール）、`dpkg -l`でバージョン一致を確認、`race_capture`を再起動して正常稼働状態に戻したことを確認済み**。ハードウェアへの影響・恒久的な変更は残っていない。

**3. 注記：オフラインsnapshot（`eglretrace -S`）等のツール不具合がDebian標準Mesaでも再現するかどうかの副次確認（第21回セッション時点の当初の検証目的の一部）は、症状の再現を優先し今回は実施しなかった**。主目的である「描画欠落症状そのものの解消」が明確に否定された時点で優先度が下がったため、次回以降も特に必要がない限り追跡しない。

**4. 🆕 続けて着手した「swap番号→fb id×swap番号→マーカー描画コールの有無」の突き合わせ実験（次回候補1として持ち越し済みだったもの）は、2つの技術的な壁にぶつかり未達で撤退した**：
   - `fbtrack33.c`（`eglSwapBuffers`直接フック）を、マーカー追加ロジックを持つ`autoswitch32.c`と統合した`fbtrack34.c`を新規作成し、apitrace（`egltrace.so`）と併用したところ即座にセグフォルトした。原因は、`fbtrack33.c`由来の**グローバル`dlsym()`オーバーライドが、apitrace側`egltrace.so`自身の内部`dlsym(RTLD_NEXT, "eglSwapBuffers")`呼び出しも横取りしてしまい、`egltrace.so`の「本物の`eglSwapBuffers`」ポインタが誤って自分自身のフック関数を指す無限再帰**を起こしていたためと判明した（`fbtrack33.c`は単体では問題なかったが、apitraceとの併用は今回が初めてだった）。`dlsym()`のグローバルオーバーライドを削除し直接エクスポート＋`eglGetProcAddress`フックのみに絞ったところセグフォルトは解消した。
   - しかし修正後も、**自作フックの`eglSwapBuffers`エクスポート・`eglGetProcAddress`フックのいずれも実際には一度も呼ばれず**（ログファイルが全く生成されない）、apitrace側のトレース自体は正常に9MB超取得できるという状態になった。実機アプリ（SDL2/Kivy）は`libEGL.so.1`を`dlopen`し特定のハンドルに対して`dlsym`で`eglSwapBuffers`を取得している可能性が高く、apitraceの`egltrace.so`はこの`dlopen`呼び出し自体を横取りする、より高度な手法で動作していると推測される（未検証の推測）。この経路に対抗するには自作インタポーザ側でも`dlopen`のフックが必要になり、直前のセグフォルトと同種の衝突リスクを伴う作り込みが要る。
   - **この時点で本実験を撤退と判断した**：そもそもこの実験は「マーカー描画頻度が約50%」という、第22回セッション内の別の集計バグにより**後に撤回済みの現象**を追いかけるために立てた仮説（訂正後の実測値は99.7%）であり、残る「稀に欠ける0.3%」のfb id偏りを見るだけの調査としては、投入する実装コストに見合わないと判断した。実機は検証後、通常のwatchdog経由稼働状態に復旧済み（ハードウェアへの影響・恒久的変更なし）。

**5. 🆕 続けてKMS/DRM側のバッファ確保方式・SDL2/EGL初期化オプションをread-onlyで調査したが、有力な手がかりは見つからず、いくつかの仮説を新たに排除できた**（実機への変更は一切なし、`race_capture`本体は通常稼働のまま並行して調査）：
   - `sudo cat /sys/kernel/debug/dri/0/state`でスキャンアウト中のfb(675)のDRMフォーマット修飾子を確認したところ`modifier=0x700000000000001`＝`DRM_FORMAT_MOD_BROADCOM_VC4_T_TILED`（`drm_fourcc.h`で確認）と判明。ヘッダのコメントに「V3D GPUがテクスチャ元にできる唯一のレイアウトで、V3Dはlinearを出力できない」と明記されており、これはVC4/V3Dでは標準・必須の構成であって異常ではないと確認した。
   - `eglinfo`のEGL拡張一覧を全件確認したところ、`EGL_EXT_buffer_age`はサポートされているが、`EGL_KHR_partial_update`・`EGL_EXT_swap_buffers_with_damage`・`EGL_KHR_swap_buffers_with_damage`はいずれも一覧に存在しないと判明。すなわちこのドライバは部分再描画（damage rect）系のEGL拡張を一切サポートしていない。
   - 本セッションで新規取得した`rc25.trace`（約70万コール規模）を`apitrace dump --grep='^egl'`で確認したところ、実際に呼ばれているのは一貫して素の`eglSwapBuffers`のみで、`eglSwapBuffersWithDamage`系は一度も呼ばれていないことを確認した。ドライバの拡張非対応という上記の確認と整合する。
   - **これにより「部分再描画とT-Tiled配置（4kタイルを偶数行・奇数行で左右反転しながら並べるserpentine配置）の食い違いにより特定領域が化けているのでは」という新仮説は、そもそも部分再描画機能自体が使われていない（ドライバがサポートしていない）ことから明確に排除できた**。
   - `/proc/<pid>/environ`で稼働中プロセスのSDL/EGL/KMS関連環境変数を確認したが何も設定されておらず、`~/.kivy/config.ini`の`[graphics]`セクションも標準的な値（`multisamples=0`に修正済み・`vsync`は空欄＝デフォルト等）のみで、特殊な初期化オプションは一切使われていないと確認した。
   - **結論**：このread-only調査だけでは新たな決定的手がかりは得られず、「KMS/DRM側のバッファ確保方式」という軸のうち「フォーマット修飾子」「部分再描画拡張の有無」「SDL2/EGL初期化オプション」の3点はいずれも異常なし・仮説排除という形でクローズした。ダブル/トリプルバッファリングの実際の枚数設定（GBM surfaceのbuffer count等、ソースレベルでの確認が必要）は今回未着手のまま残っている。

**次回の最優先候補（優先度順、更新・候補0クローズ、候補1撤退、候補3の一部排除を反映）**：
0. ~~Mesaダウングレード検証~~ → 否定・クローズ済み（第23回）。
1. ~~swap番号→fb id×マーカー描画コール有無の突き合わせ~~ → 技術的コストに見合わないと判断し撤退（第23回）。
2. ~~`glReadPixels`のスワップ単位密サンプリング~~ → 第24回で技術的に実現したが、想定と異なる新たな謎（下記）にぶつかり本来の目的は未達。次回はこの新しい謎の解明を優先。
3. ~~部分再描画(damage rect)とT-Tiled配置の食い違い仮説~~ → ドライバが部分再描画拡張自体を持たないため排除済み（第23回）。GBM surfaceのバッファ枚数設定等、ソースレベルでの確認はまだ手つかず。

---

**今回のセッション（4-4-2続き・第24回、ユーザー不在の自律調査）で得た知見：`eglSwapBuffers`フックの正しい実装方法（dlsym直接エクスポート方式は効かない）を確立したが、実際に検証してみると`apitrace`計測時と乖離した「スワップがほぼ発生しない」という新たな謎に突き当たり、当初の目的（ステンシルバッファ実内容の直接確認）は未達に終わった**：

**背景**：前回（第23回）末尾で次点候補としていた「`glReadPixels`のスワップ単位密サンプリング」に加え、第13回以来9セッション以上未解決のまま残っていた「stencilテスト（`GL_EQUAL`・`ref=2`）実行時、実際のステンシルバッファ値が2と一致しているか」を直接検証する計画で着手した。実機（`rc-dash-3b`、`192.168.137.162`、Wi-Fi物理故障のためLAN直結+ICS共有で接続）にSSH接続し、`/tmp`はtmpfsで前回セッションの成果物（インタポーザ.c等）は消滅済みだが、`~/decompile_4-4-2/`等の重量成果物は無事だったことを確認した。

**1. 🔴🎉 `eglSwapBuffers`をLD_PRELOADで直接エクスポートする方式（`fbtrack33.c`等、過去セッションで使われていたと記録されていた方式）は、このアプリでは機能しないことを実測で確定した**：新規作成した`stencil_probe.c`で`EGLBoolean eglSwapBuffers(...)`をトップレベルで直接エクスポートし`dlsym(RTLD_NEXT,...)`で本物を取得する素朴な実装を試したところ、`.so`は正しく`LD_PRELOAD`されプロセスにマップされる（`/proc/pid/maps`で確認）にもかかわらず、フック関数が一度も呼ばれない（ログファイルすら生成されない）ことを確認した。原因は、SDL2のEGLバックエンドが`eglSwapBuffers`を**`dlopen(libEGL.so, RTLD_LOCAL)`した特定ハンドルに対する`dlsym(handle, "eglSwapBuffers")`で取得しており**、この呼び出しはグローバルスコープ（LD_PRELOADが差し込まれる場所）を経由しないため、直接エクスポートによる素朴なシンボル差し替えでは横取りできないためと判明した。

**2. 🔴🎉 対策として`dlsym`自体をオーバーライドする手法（第9回以降で確立済みと記録されていたが、具体的な実装詳細は`/tmp`消失により失われていた）を実装し直し、正しく機能することを確認した**：`dlsym(void*, const char*)`をグローバルシンボルとして自前定義し、要求されたシンボル名が`"eglSwapBuffers"`の場合のみ自作フック関数を返し、それ以外は本物の`dlsym`（`dlvsym(RTLD_NEXT, "dlsym", <version>)`で別途取得）に委譲する実装とした。加えて、`"eglGetProcAddress"`も同様にフックし、そちら経由での問い合わせにも対応した（実際にはアプリは両方の経路で`"eglSwapBuffers"`を問い合わせていることをログで確認した）。

**3. 🆕 上記2の実装で当初ハマった罠：`dlvsym`用のバージョン文字列`"GLIBC_2.2.5"`（Web上の解説記事等でよく使われる定番値）は、このPi（Debian 13 trixie、glibc 2.41、aarch64）では**`dlsym`のシンボルバージョンとして存在せず`NULL`を返す**ことが判明した**。`readelf -Ws /lib/aarch64-linux-gnu/libc.so.6 | grep dlsym`で実際のバージョンタグを確認したところ、`dlsym@GLIBC_2.17`（互換版）と`dlsym@@GLIBC_2.34`（デフォルト版、glibc 2.34でlibdlがlibcへ統合されて以降のタグ）の2つのみが存在し、`GLIBC_2.2.5`は存在しなかった。この状態で`dlvsym`が`NULL`を返したまま自前`dlsym`内で使用すると、後続の`dlsym`呼び出しがNULL関数ポインタ経由でクラッシュし、**PyInstallerのブートローダーが起動する最初期の段階で、標準出力に1行も出力されないまま無言でクラッシュする**という事象を引き起こしていた（今回最初の2回の起動試行はこれが原因だったと判明）。`"GLIBC_2.34"`→`"GLIBC_2.17"`→`"GLIBC_2.2.5"`の順にフォールバックする実装に修正し解決した。**教訓：`dlvsym`のバージョン文字列はOS/glibcバージョンに依存するため、事前に対象システムの`libc.so.6`を`readelf -Ws`で確認してから決め打ちすること。glibc 2.34以降（libdl統合後）のシステムでは`GLIBC_2.2.5`は無効な可能性が高い。**

**4. 🔴🚨 上記の修正により`eglSwapBuffers`フックの捕捉自体は成功し、`App.get_running_app().switchMainView('dash')`によるdash画面への遷移も成功を確認した（`switchMainView OK`をファイル書き込みで確認、Python側の`print()`はstdoutがファイルへリダイレクトされる際にフルバッファリングされ即座に反映されないことが判明したため、ファイル書き込みでの確認に切り替えた）にもかかわらず、肝心の`eglSwapBuffers`自体がその後ほとんど呼ばれなくなるという新たな謎に遭遇した**：起動直後の数秒間に5回のスワップが発生した後、dash画面への遷移成功を含め、その後2分30秒以上（プロセスのCPU使用率は70〜115%で高いまま）にわたって**スワップが1回も追加で発生しなかった**。ESP32との接続は継続し`~/racecapture_stencilprobe.log`上でRCPAPIのTx/Rx（`{"s":0}`等）が途切れず記録され続けていることを確認しており、通信自体は正常に継続していた。これは、第22回セッションで`apitrace`により実測された「dash画面idle中、約50秒間で422回（≒8.4Hz）のスワップが継続的に発生する」という結果と真っ向から矛盾する。**考えられる仮説（いずれも未検証）**：①`apitrace`自身の計測がスワップ頻度に何らかの副作用を与えている（計測すると挙動が変わるハイゼンバグ的な現象）、②今回のセッションでは実際に画面内容が変化していなかった（ESP32から送られる値が静止的なダミー値のみで、GPS移動等を伴っていた過去セッションとは条件が異なる可能性）、③自作の`dlsym`/`eglGetProcAddress`グローバルオーバーライドがSDL2内部のvsync/swap-interval関連の初期化ネゴシエーションに予期しない影響を与えている。**この矛盾の解明が次回の最優先課題**であり、これが解決するまで、当初目的だった「ステンシルバッファ実内容の直接確認」（第13回以来の宿題）には進めなかった。

**5. 実機の状態（セッション終了時点）**：検証プロセスは`kill -9`で終了、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き）に復旧したことを確認済み（`throttled=0x0`、電源健全性も確認）。ハードウェアへの恒久的な変更なし。実機は物理Wi-Fi故障のためLAN直結+Windows ICS共有（`192.168.137.162`、ARPで`b8-27-eb`系MACから特定）で接続する運用。

**次回の最優先候補（優先度順、更新）**：
0. ~~「`apitrace`計測時は約8Hzでスワップが継続するが、素の実行ではスワップがほぼ停止する」という矛盾を解明する~~ → **今回のセッション（第25回）で実施、「apitrace有無」という軸自体が誤りだったと判明（下記参照）**。
1. 上記が解決すれば、当初目的の「ステンシルバッファ実内容の直接確認（`glReadPixels(..., GL_STENCIL_INDEX, ...)`、`ref=2`と一致するか）」に進む。今回確立した`dlsym`+`eglGetProcAddress`オーバーライド方式とバージョン文字列フォールバックの実装は、`stencil_probe.c`の技法として今後のセッションでも再利用可能（詳細は本セッションの記録を参照）。
2. 「描画コールが無いフレームでの実際のピクセル内容」確認は、上記0の謎が解けてスワップ頻度の実態が明らかになってから改めて設計し直す。

---

**今回のセッション（4-4-2続き・第25回、ユーザー不在の自律調査）で得た知見：「スワップ停止はapitrace有無で決まる」という前回セッションの前提を反証し、スワップ停止自体が同一手順でも再現したりしなかったりする非決定的な現象であることを実測で確定した。副産物としてKivyのグラフィックス命令操作がメインスレッド限定であることを発見、また今回追加したステンシルバッファ読み取りロジック自体に実装バグがあり目的のデータ取得は今回も未達**：

**背景**：前回（第24回）末尾の最優先課題「`apitrace`計測時は約8Hzでスワップが継続するが、素の実行（`dlsym`+`eglGetProcAddress`フックのみ）ではスワップがほぼ停止する」という矛盾の解明に着手した。まず、この矛盾の代替仮説として浮上していた「ESP32側データが静止的なダミー値のみだった可能性」を`racecapture_stencilprobe.log`（前回セッションの生ログ）から検証したところ、GPS座標（242通りの異なる`lat`/`lon`値）・`predTime`の走行距離（秒ごとに300m以上増加）とも継続的に変化しており、この仮説は退けられた。

**1. 🔴🎉 実験1（`swaptimeline.so`）：前回と同一のフック方式（`dlsym`+`eglGetProcAddress`）で単体再現実験を行ったところ、前回と異なりスワップは一度停止せず再開した**：`switchMainView('dash')`実行（swap#3）から5.8秒の間隙を挟んでswap#4が発生し、そこから約9秒間でswap#38まで駆け上がった後、そこで完全に停止し、残り約60秒間（プロセスは生存・CPU使用率高いまま・RCPAPI通信も継続）スワップが1回も追加発生しなかった。**「apitraceを使うかどうか」ではなく、同一手法・同一手順でもスワップ停止が発生する回としない回があるという、より単純な非決定性が真の現象であることが示唆された**（前回`apitrace`計測時に継続、`dlsym`フックのみで停止、という2回の観測は「手法の違い」ではなく単なる試行間のばらつきだった可能性が高い）。

**2. 🆕 副産物：Kivyのグラフィックス命令（`Window.canvas.ask_update()`等）は、Pythonレベルで`PyGILState_Ensure()`によりGILを正しく取得していても、Kivy自身のメインスレッドチェックにより外部スレッドからの呼び出しを拒否することを実測で確認した**：上記の停止区間中、独立した監視用pthread（`eglSwapBuffers`フックとは別に、`__attribute__((constructor))`で起動するwatcherスレッド）から`Window.canvas.ask_update()`を注入したところ、`TypeError: Cannot change graphics instruction outside the main Kivy thread`（`kivy/graphics/instructions.pyx`の`Instruction.flag_data_update`内のチェック）で例外となり、実際には何も注入できていなかったと判明した。**今後、Kivyのcanvas/Instruction操作を伴う注入を行う場合は、レンダースレッド自身（`eglSwapBuffers`フック内、これまでの`switchMainView`呼び出しと同じ経路）から呼ぶか、`Clock.schedule_once`でメインループに委譲する必要があり、独立スレッドから`PyGILState_Ensure`経由で直接呼ぶ方式は無効**という、今後の注入手法設計に関わる教訓を得た（GIL取得自体は成功しすぐ例外で復帰するため、ハング等の実害はなかった）。

**3. 🔴 実験2（`stenciltimeline.so`、ステンシルバッファ読み取りロジックを統合し再実行）：今回は約295秒間・551回のスワップが一度も停止せず継続し、実験1で観測した停止が全く再現しなかった**：実験1と全く同じ起動手順（`LD_PRELOAD`+`switchMainView('dash')`トリガー）にもかかわらず、今回はスワップが完全に安定して継続し続けた（手動で`kill -9`するまで停止の兆候なし）。これにより、**「スワップが継続するか途中で停止するかは、同一の起動手順・同一のインタポーザ設計であっても試行ごとに異なる非決定的な現象である」**ことが2回の独立した試行で確定した。停止条件の解明にはもはや単発実行では不十分で、複数回（5〜10回程度）の試行による統計的なアプローチが必要と判明した。

**4. ⚠️ 実装バグにより、本セッションでも当初目的（ステンシルバッファ実内容の直接確認）は未達に終わった**：`stenciltimeline.so`は各スワップ時に`glReadPixels(GL_STENCIL_INDEX,...)`でステンシルバッファを読み取りヒストグラムをログ出力する設計だったが、551回のスワップ全てで期待したヒストグラム付きログ行が出力されず、単純な`SWAP #N`のみの行になっていた。原因は、`real_glReadPixels`の解決に使った`dlsym(RTLD_NEXT, "glReadPixels")`（このファイル自身がオーバーライドしている`dlsym()`を経由し、最終的に実`dlsym`へ委譲される実装）が終始NULLを返し続けていたことで、コード上`if (... && real_glReadPixels)`という条件が静かに偽になり、エラーログも一切出さずヒストグラム取得処理全体がスキップされていた（サイレント失敗）。原因は未特定（Mesa VC4ドライバ上で`glReadPixels`が`RTLD_NEXT`経由の素朴な`dlsym`では解決できないシンボルである可能性が、過去の`eglSwapBuffers`と同種の問題として考えられる）。

**5. 🆕 運用上の新知見：`timeout <N> ./race_capture`はrace_capture本体を確実には止めない**：実験1で`timeout 100 ./race_capture ...`として起動したにもかかわらず、100秒経過後もプロセスは終了せず、数分間動き続けているのを確認した（`timeout`のデフォルトはSIGTERM送信のみで、PyInstallerバンドル版race_captureがこれを捕捉/無視している可能性が高い）。**次回以降、時間制限付きでrace_captureを起動する場合は`timeout --signal=KILL <N>`を使うか、実行後に明示的な`kill -9`で確実に終了させること。**

**実機（`rc-dash-3b`）の状態（セッション終了時点）**：`swaptimeline.so`・`stenciltimeline.so`いずれのプロセスも`kill -9`で終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き）に復旧したことを確認済み（`throttled=0x0`、電源健全性も確認）。ハードウェアへの恒久的な変更なし。生成物（`~/swaptimeline.c`/`.so`、`~/stenciltimeline.c`/`.so`とそれぞれのログ）は`/tmp`ではなくホームディレクトリに保存済みのため次回セッションでも再利用可能。

**次回の最優先候補（優先度順、更新）**：
0. 最優先：`real_glReadPixels`がNULLになる原因を切り分ける（`eglGetProcAddress("glReadPixels")`経由での取得に切り替える、または`dlsym`の戻り値を毎回明示的にログ出力してNULL判定を即座に検知できるようにする）。この修正により、スワップが発生している限りステンシルバッファのヒストグラムが確実に記録される状態を先に確立する。
1. 上記が解決したら、`stenciltimeline.so`を複数回（5〜10回）実行し、スワップが停止する回・しない回の発生条件（起動からの経過時間、CPU負荷、ESP32データの変化頻度等との相関）を統計的に探る。停止が発生した回については、最後に記録されたスワップのステンシルヒストグラム（`curRef`・`histN`）を確認し、9セッション以上未解決の「stencilテスト（`GL_EQUAL`・`ref=2`）実行時、実際のバッファ値が2と一致しているか」に決着をつける。
2. `Window.canvas.ask_update()`等のKivyグラフィックス命令を使った強制再描画ワークアラウンドを再検証する場合は、独立スレッドからではなく`eglSwapBuffers`フック内（レンダースレッド）または`Clock.schedule_once`経由で呼ぶこと（今回得た教訓）。

---

**今回のセッション（4-4-2続き・第26回、ユーザー不在の自律調査）で得た決定的な知見：`real_glReadPixels`がNULLになる原因（`eglSwapBuffers`と同種の「`RTLD_NEXT`経由のdlsymでは解決できないシンボル」問題）を特定・修正し、9セッション以上未解決だった「ステンシルバッファの実測値」をついに取得した。対象領域は591回のスワップを通じて一貫してステンシル値0、`GL_STENCIL_REF`は一貫して255で、`GL_EQUAL`テストなら常に不一致・破棄されることが確定した**：

**背景**：前回（第25回）末尾の最優先課題「`real_glReadPixels`がNULLになる原因の切り分け」に着手した。

**1. 🔴🎉 原因を特定：`glReadPixels`は`eglSwapBuffers`と同じ理由で`dlsym(RTLD_NEXT,...)`では解決できないシンボルだったと判明**。前回`stenciltimeline.c`の`real_glReadPixels`解決ロジックは、このファイル自身がオーバーライドしている`dlsym()`経由で`dlsym(RTLD_NEXT, "glReadPixels")`を呼ぶ実装だったが、`RTLD_NEXT`のシンボル探索順序では見つからない（SDL2/Mesaの内部シンボル解決経路が`eglGetProcAddress`のみを経由するため）ことが原因だったと判明した。修正版（`stenciltimeline2.c`、実機`~/stenciltimeline2.c`/`.so`に保存）では、まず`real_eglGetProcAddress`（既存の`eglGetProcAddress`フックで捕捉済み）経由での解決を試み、それが使えない場合のみ`dlsym(RTLD_NEXT,...)`にフォールバックする`resolve_gl_fn()`ヘルパーへ書き直し、かつ解決結果（成否・使用した経路・ポインタ値）を毎回ログへ即時出力するようにした。この修正により`glReadPixels`・`glPixelStorei`・`glGetIntegerv`・`glGetError`の4関数すべてが`eglGetProcAddress`経由で正しく解決されることをログで確認した（実装時の注意点：`resolve_gl_fn()`内のログ出力が`ensure_resolved()`を呼ぶ`logf_ts()`を再度呼ぶと無限再帰になるため、ログのファイルオープン処理とタイムスタンプ出力処理を`ensure_resolved()`系から独立させる必要があった）。

**2. 🔴🎉🔑 決定的知見：対象領域（画面座標`x=[700,1200)`, `y=[460,660)`、500×200px）のステンシルバッファを591回のスワップにわたって連続readbackした結果、全スワップ・全ピクセルで一貫してステンシル値=0（`hist0=100000`／全該当ピクセル数と完全一致、他の値は0件）、`glGetIntegerv(GL_STENCIL_REF,...)`も一貫して255だった**。`glReadPixels`のエラーコードは全て`GL_NO_ERROR`（`err1=err2=0x0`）で、readback自体は正常に機能している。これにより、第13回セッション以来9セッション以上未解決だった「stencilテスト（`GL_EQUAL`）実行時、実際のバッファ値が参照値と一致しているか」という問いに、初めて実測データで答えが出た：**バッファ値(0)と参照値(255)は一致せず、この組み合わせで`GL_EQUAL`ステンシルテストが行われれば該当ピクセルは常に破棄される**。`nonzero_color`（対象領域内でRGBA非ゼロのピクセル数）も起動直後の一瞬（15px、遷移アニメーションの残滓と推測）を除き常に0で、実際に画面へ何も出力されていないこととも整合する。
　- **注意点（次回への申し送り）**：`curRef=255`は各スワップ（フレーム末尾）時点でのグローバルな`GL_STENCIL_REF`状態のスナップショットであり、対象領域の描画コールが実際に発行された瞬間の値そのものではない。「バッファに一度も2（または他の非0値）が書き込まれていない」ことは確実な事実だが、「なぜ書き込まれないのか」（`glStencilOp`のREPLACE等が機能していない／該当領域がそもそも描画スキップされている／該当ウィジェットの`ref`自体が255相当で運用されている、等）は未解明で次回の課題。

**3. 🎉 副次的成果：今回は591回のスワップを通じて一度もスワップ停止が発生しなかった**（第25回セッションで確定した「スワップ停止は同一手順でも試行ごとに非決定的」という現象自体は否定されないが、少なくとも今回の1回の試行では発生しなかった）。ウォッチャースレッドが起動直後10秒間だけ「STALLED」を誤検知したのはスワップ開始前の起動処理中の正常な期間であり、実質的な停止ではない。

**4. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：検証プロセスは`kill -9`（PID直接指定）で終了、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き）に復旧したことを確認済み（`throttled=0x0`、電源健全性も確認）。ハードウェアへの恒久的な変更なし。生成物（`~/stenciltimeline2.c`/`.so`、`~/stenciltimeline.log`、`~/nav_result3.txt`）はホームディレクトリ（`/tmp`ではない）に保存済みのため次回セッションでも再利用可能。

**次回の最優先候補（優先度順、更新）**：
0. 最優先：「なぜステンシルバッファへの書き込みが反映されないのか」の切り分け。案：①対象領域の描画コール発行直前・直後（`glReadPixels`ではなく`glStencilFunc`/`glStencilOp`呼び出し自体）をフックして、実際に使われている`ref`値・書き込みモードを直接確認する、②対象領域の座標選定が過去セッションで「妥当な座標」と確認済みのウィジェット位置と一致しているか再確認する（第13回セッションの座標との整合性チェック）。
1. 上記で「stencil書き込みが機能していない」と確定すれば、Mesa VC4ドライバのstencil書き込みパス自体の欠陥という、これまでで最も具体的な根本原因候補に到達する。次はドライバソースレベルの調査、またはstencilを使わない代替クリッピング手法（`glScissor`等）へのアプリ側ワークアラウンドの検討に進む。
2. 今回確立した`resolve_gl_fn()`（`eglGetProcAddress`優先＋`dlsym(RTLD_NEXT,...)`フォールバック＋即時ログ）は、今後GLES関数を新規にフックする際の標準手法として再利用すること。

---

**今回のセッション（4-4-2続き・第27回、ユーザー不在の自律調査）で得た決定的な知見：第26回セッションの結論（「ステンシル値0・GL_STENCIL_REF=255で不一致」）が測定タイミングの欠陥による誤りだったことを突き止め、正しいタイミングで再測定した結果、`GL_EQUAL`ステンシルテストは対象領域全体で一貫してパスしている（＝ステンシルクリッピングは正常に機能している）ことを確定した。9セッション以上の主軸だった「ステンシル値不一致」仮説は事実上ここで閉じ、黒画面の真犯人は別の場所（ステンシルテストを通過した後、色が一切書き込まれない何か）にあるという新たな焦点へ絞り込んだ**：

**背景**：前回（第26回）末尾の最優先課題「なぜステンシルバッファへの書き込みが反映されないのか」の切り分けに着手した。まず`stenciltimeline3.c`を新規作成し、`glStencilFunc`/`glStencilOp`呼び出し自体をフックして全呼び出しをログする（低頻度なコール、ネスト深さの状態変化ごとにしか呼ばれないため`glDrawArrays`フック（第14回セッションで過負荷を招いた手法）よりはるかに低オーバーヘッドと判断）ことから始めた。

**1. 🔴🎉🔑 決定的発見：`glStencilFunc`/`glStencilOp`の全呼び出しログにより、「push（スタンプ）→本描画→pop（後始末）」の3段構成と、popが`GL_GREATER(ref=255)`という「8bitバッファでは絶対にパスしない番兵値」＋`StencilOp(DECR,DECR,DECR)`（テスト結果に関わらず常時デクリメントする設定）で実装されていることを突き止めた**：651回のスワップ・31368回の`glStencilFunc`呼び出しを解析した結果、`func`は4種類（`GL_EQUAL`=9806回、`GL_LEQUAL`=1296回、`GL_GREATER`=11744回、`GL_ALWAYS`=8522回）に限られ、かつ`ref`値との組み合わせが完全に規則的だった：`GL_ALWAYS`は常に`ref=1`（push、`StencilOp`は常に`INCR/INCR/INCR`）、`GL_EQUAL`は`ref∈{1,2,3}`のみで**`ref=255`は一度も現れない**（本描画のクリップ判定、`StencilOp`は常に`KEEP/KEEP/KEEP`）、`GL_GREATER`は`ref=255`が8523回（`GL_GREATER`全体11744回のうち最多）で`StencilOp`は常に`DECR/DECR/DECR`（pop、`ref=255`は8bitステンシルバッファでは`ref>value`が絶対に成立しないため必ずテスト失敗＝`sfail`分岐が必ず実行される、3つとも`DECR`にしてあるのは分岐に関わらず確実にデクリメントするための実装上の工夫と判明）。

**2. 🔴🚨🔑 この構造から、第22〜26回セッションが採用してきた「`eglSwapBuffers`（スワップ時点）でのステンシルバッファ読み取り」という測定方法そのものが原理的に無効だったと判明した**：スワップ時点は必ず1フレーム分の「push→本描画→pop」が全て完了した後であり、popは`GL_EQUAL`本描画テストの成否に関わらず無条件に実行される（`ref=255`は`GL_GREATER`で絶対に失敗する番兵のため）。つまり、本描画が成功しようが失敗しようが、スワップ時点でのステンシルバッファは常に「pop後のベースライン値」に戻っており、両者は区別不能。第26回セッションが「9セッション以上未解決の問題に決着をつけた」としていた「ステンシル値0・`GL_STENCIL_REF=255`で不一致」という結論は、**実際には何の情報も持たない測定（popによって強制的に均されたベースライン値を見ていただけ）だった**と結論づけられる。当該コミット（4d67be4）の見出しは実質的に誤りだったことになる。

**3. 🔴🎉🔑 上記2の教訓を踏まえ`stenciltimeline4.c`を新規作成、`glStencilFunc(GL_EQUAL, ref, ...)`が呼ばれた「その瞬間」（本描画テストの直前、push完了後・pop実行前）にステンシルバッファをプローブするよう変更して再計測した結果、対象領域（x=[700,1200) y=[460,660)、500×200px）全体で`GL_EQUAL`テストは高い割合〜完全にパスしていることが判明した**：246スワップ・3680回の`GL_EQUAL`直前プローブの結果、**`ref=3`（最も深いネストレベル）は239/239件（100%）で対象領域全ピクセルのステンシル値が3と完全一致**（テストは常にパス）。`ref=2`は967件中725件（75%）で全ピクセル一致、242件（25%）は全ピクセルが1（＝この特定の`GL_EQUAL(ref=2)`呼び出しはこの対象領域を含まない別ウィジェットの判定であり、対象領域はまだpushされる前の状態だったと解釈できる、値が部分的に混在するケースは一件もなく常に全ピクセル一律だった点が重要）。`ref=1`は2474件中1939件（78%）で全ピクセル一致、485件（20%）は全ピクセルが0（同様に対象領域外の判定と解釈）。**いずれのケースでも「一部のピクセルだけ値が違う」という部分不一致は一度も観測されず、常に対象領域500×200px全体が単一のステンシル値で揃っていた**（同一ウィジェット境界内に完全に収まっている証拠）。これにより、「ステンシルバッファの実値が参照値と一致しない」という第13回以来の仮説は、少なくとも本描画テストの実行タイミングで見る限り明確に否定された。

**4. 🆕🔑 副次的だが重要な発見：スワップ#6〜#55（約50フレーム、遷移直後の約1.5秒間）に限り、対象領域内に一貫して15ピクセルだけ色が非ゼロ（`nonzero_color=15`）となり、かつ同時刻の`GL_EQUAL(ref=1)`プローブが常に`hist1=15`（ステンシル値1のピクセルがちょうど15個）を示すという、色とステンシルの完全な相関を確認した。スワップ#56以降はこの15pxも含めて`nonzero_color`が最後まで（#246まで）恒久的に0のままだった**。この「起動直後だけ現れる15px」は第26回セッションが「遷移アニメーションの残滓と推測」として一度観測済みのものと同一現象と考えられ、新規の手がかりではないが、今回初めてステンシル値との厳密な相関（15個のステンシル値=1のピクセルと15個の非ゼロ色ピクセルが完全に一致）が取れたことで、この一時的な描画が実際に「ステンシルテストを通過した本物の描画」であったことが確認できた。

**5. 🔴🚨🔑🎯 上記3・4を総合すると、黒画面問題の焦点は完全に組み替わる：ステンシルクリッピングは（少なくとも`ref=3`の最深レベルでは）常に正常にパスしているにもかかわらず、スワップ#56以降は対象領域の色が恒久的に一切変化しない（透過黒`(0,0,0,0)`のまま）。つまり「ステンシルテストに通過した後、何らかの理由で色が一切書き込まれていない」という、これまでとは全く別の段階に問題があることが強く示唆される**。考えられる仮説（いずれも未検証、次回の調査対象）：①該当描画コールの頂点数が実際には0または縮退している（ジオメトリが空）、②`glColorMask`が該当描画時に無効化されている、③ブレンド関数の組み合わせにより、書き込まれた色が結果的に`(0,0,0,0)`のまま変化しないケース（例：ソースアルファ0のブレンドなど）。

**6. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：検証プロセス（`stenciltimeline3.so`実行分・`stenciltimeline4.so`実行分とも）は`kill -9`で終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き）に復旧したことを確認済み（`throttled=0x0`、電源健全性も確認）。ハードウェアへの恒久的な変更なし。生成物（`~/stenciltimeline3.c`/`.so`、`~/stenciltimeline4.c`/`.so`とそれぞれのログ、`~/stenciltimeline4_<pid>.log`形式）はホームディレクトリ（`/tmp`ではない）に保存済みのため次回セッションでも再利用可能。

**7. 🆕 運用上の新知見：LD_PRELOADは`race_capture`がforkする全ての子プロセスにも適用される**：`stenciltimeline3.so`実行時、`eglSwapBuffers`を一度も呼ばない別プロセス（詳細未特定、`race_capture`が生成する何らかのヘルパープロセスと推測）でも本インタポーザのコンストラクタが起動し、独自のwatcherスレッドが「`swap_count=0`のまま停止」というログを本体プロセスと同じログファイルへ書き込んでいたため、ログが2プロセス分混在していた（幸い破損はしなかったが、両プロセスが同じパスへ`fopen(..., "w")`する設計は事故の元）。`stenciltimeline4.c`ではログファイル名に`getpid()`を含める（`stenciltimeline4_<pid>.log`）よう修正済みで、以後もこの方式を踏襲すること。

**次回の最優先候補（優先度順、更新）**：
0. 最優先：「`GL_EQUAL`ステンシルテストを通過した本描画コールが、実際に色を書き込んでいるか」の直接切り分け。低オーバーヘッドで実施する方法として、`glDrawArrays`/`glDrawElements`をフックし、GL状態照会（第14回セッションで過負荷を招いた`glGetIntegerv`/`glIsEnabled`呼び出し）を一切行わず、**引数の頂点数（`count`）をそのままログするだけ**（追加のGL呼び出しなし、極めて低オーバーヘッド）の実装で、対象領域に該当する描画コールの頂点数が0（縮退ジオメトリ）になっていないか確認する。
1. 上記で頂点数が正常なら、`glColorMask`の呼び出し（低頻度なはずなので同様に安価にフック可能）と`glBlendFunc`/`glEnable(GL_BLEND)`の状態を確認し、色書き込みが構造的に無効化されていないか調べる。
2. 対象領域（x=[700,1200) y=[460,660)）が「ScreenManagerのメインコンテンツ領域」を代表する座標として妥当かは今回も未検証のまま。今回`ref=3`が100%一致という非常にクリーンな結果が出ているため、座標選定の誤りである可能性は低いと考えられるが、逆コンパイル済みソース（`~/decompile_4-4-2/`）との突き合わせによる確認は依然として次点の課題として残る。

---

**今回のセッション（4-4-2続き・第28回、ユーザー不在の自律調査、3時間枠）で得た決定的な知見：9セッション以上の中心的な謎だった「黒画面（透過）問題」の根本原因を実測で確定し、さらに有効なワークアラウンドまで実証した。真犯人はMesa VC4ドライバの`glClear()`のバグで、`GL_COLOR_BUFFER_BIT`を含まない部分マスク（ステンシルのみ等）でのクリア要求が、要求されていない色バッファまで強制的にゼロクリアしてしまうというものだった**：

**背景**：前回（第27回）末尾の最優先候補0「`GL_EQUAL`ステンシルテストを通過した本描画コールが、実際に色を書き込んでいるか」の直接切り分けに着手した。`stenciltimeline4.c`を土台に、`drawtimeline1.c`〜`drawtimeline8.c`まで8世代のLD_PRELOADインタポーザを実機（`rc-dash-3b`、`ntakao@192.168.137.162`、直結LAN＋Windows ICS方式、鍵は`racecapture_dash_ed25519`）上で反復開発・実行する形で調査を進めた。各世代の`.c`/`.so`はホームディレクトリ（`/tmp`ではない）に保存済みで次回も再利用可能。

**1. 🎉`drawtimeline1.c`：前回の最優先候補0・1をいずれも実測で否定**。`glDrawArrays`/`glDrawElements`をフックし、直前の`glStencilFunc(GL_EQUAL,...)`呼び出しに続く「本描画コール」の頂点数をログした結果、759件全てで頂点数は正常（縮退ジオメトリではない、count=5〜54等）だった（候補0を否定）。また`glColorMask`・`glBlendFunc`・`glEnable(GL_BLEND)`もフックしたところ、本描画コール直前の`glColorMask`は常に`(1,1,1,1)`（有効）、`glBlendFunc`は起動時に一度だけ`GL_SRC_ALPHA`/`GL_ONE_MINUS_SRC_ALPHA`（標準的なアルファブレンド）に設定されて以降変化なしと判明し、候補1（色書き込みが構造的に無効化されている）も否定された。

**2. 🔴🎉🔑`drawtimeline2.c`：本描画コール実行直後に対象領域を直接readbackしたところ、実際には正常に色が書き込まれている（`nonzero=100000/100000`＝対象領域500×200px全体が非ゼロ）ことを確認。しかし同一フレーム内の"最後の"本描画コール直後には必ず`nonzero=0`に戻っており、フレーム内のどこかで書き込んだ色が消されていることが判明した**。標準的な`SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA`ブレンド（ソースアルファ0なら書き込み先は変化しないはず）ではこの「一度書き込まれた色が消える」現象を説明できず、`glClear`の関与を疑う端緒となった。

**3. `drawtimeline3.c`：`glClear`をフックしログしたところ、1フレームあたり複数回（大半は`mask=0x400`＝`GL_STENCIL_BUFFER_BIT`のみ）呼ばれていることを確認**。全体で354回中293回が`mask=0x400`（ステンシルのみ）、61回が`mask=0x4500`（`COLOR|DEPTH|STENCIL`、フレーム冒頭の通常のフルクリア）、`mask=0x4000`（`COLOR`のみ）は1回のみだった。フルクリア直後の対象領域readbackは`nonzero=100000`（不透明な背景色`(18,18,18,255)`で塗りつぶし）で正常。

**4. 🔴🎉🔑`drawtimeline4.c`：ゲートなし（`GL_EQUAL`に紐付かない）描画コールも含め、スワップ#4〜#6の全描画コール後に無条件でreadbackする集中実験（900サンプル）を実施し、犯人となる特定の1コールを直接特定した**。フレーム冒頭のフルクリア直後は対象領域が背景色で埋まっている（`nonzero=100000`）が、`glClear(mask=0x400)`＋`glColorMask(0,0,0,0)`に続く`count=3462`という桁違いに大きい`glDrawElements`呼び出しの直後、対象領域は完全に`(0,0,0,0)`へ変化し、以降そのフレーム内では二度と戻らないことを確認した。ただしこの巨大描画コール自体は`glColorMask(0,0,0,0)`（色書き込み無効）の状態で実行されており、GL仕様上は色バッファに影響できないはずで、真犯人は描画コールではなくその直前の`glClear(mask=0x400)`だと推測するに至った。

**5. 🔴🎉🔑🎯`drawtimeline5.c`：全ての`glClear`呼び出しの直前・直後で対象領域を直接readbackする実験により、上記4の推測を完全に実証した**。`mask=0x400`（ステンシルのみ）のクリア呼び出しは、直前に対象領域が非ゼロ（`100000`または`78921`）だった場合、直後に必ず`0`へ変化する（12回中12回、例外なし）ことを確認。`mask=0x4500`（フルクリア）は正常（背景色で塗りつぶされるだけ）。**これにより、要求されていない`GL_COLOR_BUFFER_BIT`まで巻き込んで色バッファをゼロクリアしてしまうMesa VC4ドライバのバグが根本原因であることを、直接の前後比較で確定した**。

**6. `drawtimeline6.c`：シザーテストの関与を切り分け**。`glScissor`をフックしたところ全実行を通じて一度も呼ばれておらず（`g_scissor_count=0`）、`glIsEnabled(GL_SCISSOR_TEST)`も常に`0`（無効）だった。これによりシザー領域限定のバグという可能性を排除し、上記5の現象がフレームバッファ全体に及ぶ無条件のバグであることを確認した。また`glClearColor`の呼び出し履歴も記録し、起動時（swap=0）に背景色`(0.070588, 0.070588, 0.070588, 1.0)`（＝`18,18,18,255`）が一度設定された後、dash画面遷移直後（swap=3）に`(0,0,0,0)`（完全透過）へ上書きされ、以降一度も復元されていないことが判明した。この「透過黒のまま放置されたクリア色」が、バグによって誤って色バッファへ適用される値の正体と推測された。

**7. 🔴`drawtimeline7.c`：ワークアラウンド案①（クリア色の一時差し替え）を検証したが効果なし**。バグ発生時のクリア色を正しい背景色へ一時的に差し替え、実クリア呼び出し後に元へ戻す実装を試したが、結果は差し替え前と完全に同一（`after=0/100000`のまま）だった。これにより「バグは`glClearColor`の値を（誤った値であれ）参照して塗りつぶしている」という当初の推測が誤りで、**実際には設定されているクリア色を一切無視し、強制的にゼロへリセットしている**ことが判明した（VC4のタイルクリア高速パスが、フルクリア以外の部分マスク要求を正しく処理できず、無条件のゼロクリアへ縮退している可能性が濃厚）。

**8. 🎉🎉🎉`drawtimeline8.c`：ワークアラウンド案②（クリアマスクへの`GL_COLOR_BUFFER_BIT`明示的追加）が完全に有効であることを実測で確認した**。`glClear`呼び出し時、要求マスクに`GL_COLOR_BUFFER_BIT`が含まれていない場合、クリア色を正しい背景色へ一時差し替えた上で、**実際にドライバへ渡すマスクへも`GL_COLOR_BUFFER_BIT`を明示的にOR演算で追加**してから本物の`glClear`を呼ぶよう変更した結果、対象領域は`glClear`前後で常に`nonzero=100000/100000`を維持し、スワップ時点（`eglSwapBuffers`直前）でも`nonzero_color=100000`が継続的に（swap#68〜#77、以降も安定して）観測された。**フルマスク（`COLOR|DEPTH|STENCIL`等、`GL_COLOR_BUFFER_BIT`を含む）でのクリア要求はドライバが正しく処理する（クリア色を正確に反映する）一方、部分マスク要求のみが色バッファを巻き込んでゼロクリアするバグであり、要求を「常にフルマスクへ拡張しクリア色を正しく設定する」ことで完全に回避できる**ことが実証された。レンダリングループ自体もクラッシュ・スタールなく安定して継続し（`draws_total`が継続的に増加）、副作用は確認されなかった。

**9. 総括：これで9セッション以上（第13回〜第27回）の中心的な謎だった「黒画面（透過）問題」の根本原因とワークアラウンドの両方が実測で確定した**。真の原因は、dash画面の各ウィジェットが多重ネストしたステンシルクリップ（push/content/pop、第27回で確立済みのパターン）を実装する際に発行する「ステンシルバッファのみをクリアする」意図の`glClear(GL_STENCIL_BUFFER_BIT)`呼び出しが、本機のMesa VC4ドライバ（バックポート版26.2.0-1〜bpo13+0〜rpt2、第23回でDebian標準版25.0.7-2+deb13u1へのダウングレードでも症状不変と確認済み＝バージョン固有ではなく本ドライバ系列に共通する欠陥の可能性が高い）上で、要求されていない色バッファまで巻き込んで強制的にゼロクリアしてしまうというものだった。ドライバの部分クリアパスに何らかの欠陥があり、色バッファのゼロクリアはクリア色の設定値を一切参照しない（案①が無効だったことから確定）。ワークアラウンドとして、`glClear`呼び出しのマスクへ常に`GL_COLOR_BUFFER_BIT`を明示的に追加し、同時にクリア色を正しい背景色へ一時差し替える方式（案②、`drawtimeline8.c`）が完全に有効であることを実測で確認した。

**10. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての検証プロセスは`sudo kill -9`で終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き、PID 7203）に復旧したことを確認済み（`throttled=0x0`、電源健全性も確認）。ハードウェアへの恒久的な変更なし。生成物（`~/drawtimeline1.c`〜`~/drawtimeline8.c`とそれぞれの`.so`・ログファイル）はホームディレクトリに保存済みのため次回セッションでも再利用可能。**`~/drawtimeline8.c`が、実証済みワークアラウンドを含む最新版であり、次回の本番適用検討のベースとなる**。

**11. 🆕 未確認・要視覚検証事項**：今回の実証は全て`glReadPixels`による定量的readback（対象領域内の非ゼロピクセル数）に基づくものであり、実際にHDMIモニタ上で正常な画面（メーター・ゲージ・テキスト等）が表示されるかの視覚的確認は行っていない（ユーザー不在のため）。`nonzero_color=100000`（対象領域全体が非ゼロ）が継続することは「透過が解消され何らかの色が描画され続けている」ことの強い証拠だが、その内容が意図通りの正しい見た目（各ウィジェットの正しい色・アイコン・文字等）になっているかは次回ユーザー立ち会いの上でHDMIモニタ目視、またはVNC等での確認が必要。

**次回の最優先候補（優先度順、更新）**：
0. 最優先：ユーザー立ち会いのもとで`drawtimeline8.c`のワークアラウンドを適用した状態のHDMIモニタ目視確認を行い、実際に正常な画面が表示されることを視覚的に確定する。
1. 視覚確認が取れたら、本番適用方法を検討する。候補：①`run_racecapture_rpi.sh`から常時このワークアラウンドをLD_PRELOADする恒久対応、②Mesa VC4ドライバ側のバグとしてアップストリーム（Mesa gitlab等）への報告・より新しい修正版ドライバの探索、③アプリ側（逆コンパイル済みソース`~/decompile_4-4-2/`）でステンシルのみのクリア呼び出し自体を避けるパッチの検討。①が最も即効性が高く低リスクだが、LD_PRELOADを本番運用に組み込むことの是非（保守性・今後のRaceCapture Appアップデート時の互換性等）はユーザーと相談の上で決定する。
2. ワークアラウンド適用下で長時間（走行を想定した数十分オーダー）の安定性・パフォーマンス（フレームレート低下の有無）も未検証のため、視覚確認と合わせて確認する。

**（第28回セッション、続き）ワークアラウンド適用下での追加安定性検証（`drawtimeline9.c`）**：上記候補2の一部として、ワークアラウンド適用状態でdash画面遷移後に約100秒間（swap#4〜#246超、約250フレーム分）継続運用し、`eglSwapBuffers`の完全停止（watcherの`STALLED`検知）が起きないか確認した。`STALLED`は起動直後（t=10.0〜20.5秒、スワップ開始前の正常な準備期間）とt=50秒台の一瞬（5.5〜6.0秒の短いギャップ、swap_count=5で足踏み）の計5件のみで、それ以降（t=50.5秒〜観測終了の約100秒まで）は一切発生せず、レンダリングループは安定して継続した。また対象領域の色内容を「背景色そのままか否か」で分類する診断（`differs_from_bg`）を追加したところ、194フレームで0（背景色のみ）・49フレームで15（背景色と異なるピクセルが15個）という結果が得られ、**背景の塗りつぶしだけでなく、実際に動的な前景コンテンツ（第26回セッションで既知の「15px」シグネチャと一致）も継続的に描画され続けている**ことを確認した。これによりワークアラウンドは短時間の実証だけでなく、数十秒〜100秒オーダーでも安定して機能し続けることが分かった（数十分オーダーの走行想定はなお未検証）。実機は検証後、通常のwatchdog付きクリーンな状態（LD_PRELOADなし）へ復旧済み（`throttled=0x0`確認済み）。

**（第28回セッション、最終盤）本番適用検討用に、診断ログ・`glReadPixels`readback処理を一切含まない最小構成のクリーン版ワークアラウンドを作成**：`racecapture_glclear_fix.c`（実機`~/racecapture_glclear_fix.c`に保存済み、次回も再利用可）。フックする関数を`glClear`・`glClearColor`の2つのみに絞り、`eglSwapBuffers`フック・Python注入・watcherスレッド・ログ出力を全て排除した、本番投入を想定した軽量実装。コンパイル確認（警告のみ、エラーなし）の上、単体でLD_PRELOADして約24秒間のスモークテスト（プロセスがクラッシュ・watchdog再起動ループに陥らないことのみ確認、詳細な色内容の検証は`drawtimeline8/9.c`で既に実施済みのロジックと同一のため省略）を行い、問題なく安定動作することを確認した。**まだ`run_racecapture_rpi.sh`等への恒久組み込みは行っていない**（本番適用の是非はユーザー判断のため）。実機は検証後、通常のwatchdog付きクリーンな状態へ復旧済み（`throttled=0x0`確認済み）。

**（第28回セッション、文献調査）Mesa VC4ドライバの公式ドキュメント・issue検索を行い、今回発見した不具合が既知の報告済みバグかを確認**：Mesa公式ドキュメント（`docs.mesa3d.org/drivers/vc4.html`）に、VC4は「`glClear()`でカラー・デプス両バッファを明示的にクリアする方が、GPU側の安価なタイルバッファmemset相当の高速パスを使えるため効率的」という趣旨の性能上の助言があり、**タイルベースレンダラ特有の「クリア専用高速パス」がVC4に実在すること自体は公式ドキュメントで裏付けが取れた**（今回のバグの発生機序＝部分マスク要求がこの高速パスで正しく扱われず全バッファ強制ゼロクリアに縮退する、という推測と整合的）。一方、Mesa GitLabやRaspberry Pi Forums等を検索した範囲では、「`GL_STENCIL_BUFFER_BIT`のみのクリア要求が色バッファまで巻き込んでゼロクリアする」というピンポイントな既存バグ報告は見つからなかった。**今回の発見は（少なくとも一般に検索可能な範囲では）未報告の新規バグである可能性が高く、次回以降でMesa GitLabへの正式なバグ報告を検討する価値がある**。

---

**（第29回セッション、ユーザー立ち会いのもとで実施）視覚確認の結果、`glClear`ワークアラウンドは有効だが「黒画面」問題を完全には解決しないと判明：サイドバー（ナビゲーションドロワー）は実際に描画されるようになった一方、DASHBOARD・SYSTEM STATUS等のメインコンテンツ領域は依然として完全に黒いままという、新しい形の問題が残っていることを確定した**：

**1. 本番適用検討用のクリーン版ワークアラウンド（`racecapture_glclear_fix.c`、第28回セッションで作成済み）をビルドし、実機のtty1コンソールで稼働中の無修正版`race_capture`をLD_PRELOAD版へ差し替えて視覚確認を開始した**。ユーザーの目視では「これまでと大きく変わったようには見えない」という報告だったが、サイドバーを開くと背景色がわずかに変化する挙動が確認された。

**2. `ffmpeg kmsgrab`によるキャプチャが、ワークアラウンド適用後は信頼できなくなっていることが判明**：ほぼ同時刻に撮った3枚のキャプチャがそれぞれ「背景色+上部にテキスト」「画面上半分が真っ白」「全体に横縞状のノイズ」という全く異なる内容になり、ユーザーの安定した目視結果と矛盾した。プロセスは安定稼働（クラッシュ・再起動なし、電源健全）していたことから、以前は完全に静止していた画面がワークアラウンドで実際に動的に再描画されるようになった結果、kmsgrabのタイル圧縮バッファ展開（detiling）処理側の別の不具合が新たに露呈したと判断し、以後は物理モニタの写真を主な確認手段に切り替えた。

**3. 🔴🔑 ユーザーが撮影した実機モニタの写真により、サイドバー（DASHBOARD/ANALYSIS/SETUP/SYSTEM STATUS/EXITの文字とアイコン）が完全に正常表示されていることを確認**。ワークアラウンドは実際に効果を発揮しており、9セッション以上未描画だった文字・アイコンが初めて物理モニタ上で確認できた。一方、サイドバーの右側（メインコンテンツ領域）は写真上も完全に黒いままだった。ユーザーから「サイドバーは10秒程度で自動的に閉じる仕様」という新情報も得た。

**4. 🔴🎯 Kivy自身の`Window.screenshot()`（第9回セッション以来この調査で最も信頼できる手法、GPU内部からの直接読み戻し）による全画面ダンプでも、DASHBOARD画面表示中はカーソル以外一切何も写らないことを確認し、「メインコンテンツ領域が本当に何も描画されていない」ことをkmsgrabに依存しない形で確定した**。トリガーファイルの存在を`eglSwapBuffers`フック内でチェックし、検出時に`PyGILState_Ensure`経由で`Window.screenshot(name=...)`をオンデマンド実行する仕組み（`frametrace.c`系列の基盤）を新規に確立し、以後の検証で継続的に使用した。

**5. 🆕 ESP32デバイスとのシリアル通信が、繰り返した`kill -9`による強制再起動の影響で不安定化していたことが判明（`Timeout waiting for ver`／`PortNotOpenException`）**。ポートを掴んでいる古いプロセスは残っていなかった（`fuser`で確認）ため、ESP32側の状態が原因と推測し、ユーザーにUSBケーブルの抜き差しを依頼。デバイスは`/dev/ttyACM1`として再認識され、再起動後`on_data_connected: True`・ファームウェアバージョン`RCPMK3 2.16.1`を正常に認識できることを確認した。**この状態（デバイス接続正常）でもDASHBOARD画面は`Window.screenshot()`で依然として完全に黒く、「データが無いから何も表示するものがない」という可能性を排除した**。

**6. 🔴🔑🔑 GLコールレベルの主要な原因候補をほぼ全て実測で除外した**（実機`rc-dash-3b`上、`drawtimeline9.c`系列のインタポーザを拡張しながら検証）：
   - **stencilテスト**：`glStencilFunc`の`GL_EQUAL`呼び出しを強制的に`GL_ALWAYS`へ書き換える実験的ワークアラウンド（`stencilbypass.c`）を実装し18,900回以上のバイパスを実際に発生させたが、視覚的な変化は一切なかった（`Window.screenshot()`で確認）。9セッション以上の主軸だったstencil仮説は、今回のワークアラウンド適用後の文脈でも完全に無関係と再確認された。
   - **1フレーム分の完全なGL呼び出しトレース**（トリガーファイルで武装し次のスワップまでの全呼び出しを記録する`frametrace.c`の仕組みを新規開発）により、1フレームあたり395〜751回の`glDrawElements`呼び出し（頂点数3〜3462、いずれも妥当な範囲）、正しく交互するcolorMask（(1,1,1,1)/(0,0,0,0)が各5万回ずつ）、フレーム冒頭の1回だけの全マスククリア（`mask=0x4500`、クリア色は起動時からほぼ一貫して正しい背景色`(18,18,18,255)`のまま）、を確認した。
   - **色uniform**（`glUniform4f`、Kivyのcanvas Colorインストラクションに対応するシェーダuniform、`loc=2`）を新規にフックしたところ、不透明白`(1,1,1,1)`（アイコン・テクスチャそのまま表示）、半透明黒`(0,0,0,0.5)`/`(0,0,0,0.15)`（Material Designのシャドウ効果と推測される値）など、いずれも妥当な値だった。
   - **viewport**（`glViewport`）は起動直後（swap=0）に一度だけフルスクリーン`(0,0,1920,1080)`に設定されて以降、一度も変化していないことを確認した。
   - **FBOバインド**（`glBindFramebuffer`）は起動直後（swap=3）に一瞬`framebuffer=1`へバインドされた後すぐ`framebuffer=0`（デフォルトフレームバッファ、画面そのもの）へ戻っており、DASHBOARD画面表示中の実際の描画は一貫してデフォルトフレームバッファに対して行われていることを確定した（オフスクリーンへの誤描画という仮説は排除）。

**7. `apitrace`によるさらに詳細な検証（テクスチャ・シェーダuniformの完全な状態ダンプ）を試みたが、トレースファイルの書き出しに失敗し続け（プロセスの終了順序を変えても`.trace`ファイルが一切生成されない）、原因不明のまま断念した**。この点は次回、時間があれば深追いする価値がある（apitraceのバージョン・このシステム特有の非互換の可能性）。

**8. 🎯 総括：今回の視覚確認で、9セッション以上かけて特定・修正した`glClear`部分マスクバグは実際に有効であり、サイドバー（ナビゲーションドロワー）の描画を回復させたことが実証された。一方、`ScreenManager`のメイン画面コンテンツ（DASHBOARD・SYSTEM STATUS等）だけが描画されないという、第14回セッション以来ずっと未解決だった境界線は、今回のワークアラウンド適用後も全く変わらず残存していることが判明した**。GLコールレベルで考えられる一般的な原因（stencil・colorMask・clear・頂点数・色uniform・viewport・FBO）は今回ほぼ全て潰したため、これは`glClear`バグとは独立した、別の未解決の問題である可能性が高い。次回はテクスチャの実データ（`glTexImage2D`/`glTexSubImage2D`の中身が空・破損していないか）、シェーダプログラムの切り替え（`glUseProgram`）、あるいはSDL2の最終合成・ブリット層（KivyはSDL2バックエンド経由でGL→ウィンドウの最終表示を行っており、通常のGLコール傍受では見えない層）の調査が候補となる。

**9. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由の`race_capture`（LD_PRELOADなし、通常のwatchdog付き）に復旧したことを確認済み（`throttled=0x0`確認済み）。ハードウェアへの恒久的な変更なし。ESP32は`/dev/ttyACM1`として認識された状態が維持されている（次回セッションでポート名が変わっている可能性に注意）。生成物（`racecapture_glclear_fix.so`、`drawtimeline9b.c`、`stencilbypass.c`、`frametrace.c`〜`frametrace4.c`とそれぞれの`.so`・ログファイル）はホームディレクトリに保存済みのため次回セッションでも再利用可能。`frametrace4.c`が最新版（uniform4f・viewport・glBindFramebufferのトレース機能を含む、stencilバイパスは無効化済み）。

**（第29回セッション、セッション終了後の追加検討）ユーザーとの会話で、そもそも今回のRaspberry Pi環境が公式サポート範囲から外れていた可能性が浮上し、次回の最優先方針を変更した**：公式Wiki（[RaceCapture on Raspberry Pi](https://wiki.autosportlabs.com/RaceCapture_on_Raspberry_Pi)）を確認したところ、①**OS要件は「Raspberry Pi OS Lite, Debian Version 12 (bookworm) 64bit」と明記**されているが、今回のセットアップでは当時最新だった**Debian 13 (trixie)** を使用していた（インストール時点で「公式インストーラーはbookworm前提のため、trixie向けにパッケージ名を修正して非対話化した」という記録が残っており、trixie使用は当初から自覚された逸脱だった）。②**公式が正式サポートするディスプレイは「純正Raspberry Pi公式ディスプレイ（静電容量式タッチ）」または「AR1100抵抗膜式タッチコントローラ対応ディスプレイ」の2種類のみ**で、それ以外は"additional work may be needed"と明記されている。今回使用した一般的なフルHD(1920x1080) HDMIモニタはこの「それ以外」に該当する。実際、`RESOLUTION=800x480`という純正タッチパネル向けデフォルト値との不整合・`full_screen_mode`既定無効・`multisamples=2`起因の描画破綻など、序盤で見つかった問題群はいずれも「非公式ディスプレイ構成」の影響として説明がつく。**これまで29セッションかけて追ってきたMesa VC4ドライバの`glClear`バグ・今回発見したメインコンテンツ非描画の謎は、いずれも公式が動作確認していないOS世代（trixieの新しいバックポート版Mesa）・ディスプレイ構成に起因する「公式未検証の組み合わせ固有の問題」だった可能性が高いと判断した**。ユーザーと相談の上、次回はこの角度からの検証を最優先とすることに決定した。

**次回の最優先候補（優先度順、第29回セッション終了時点で更新・決定済み）**：
0. **最優先（決定事項）：Raspberry Pi 3B（`rc-dash-3b`）を、公式サポート対象の`Raspberry Pi OS Lite, Debian 12 (bookworm) 64bit`でクリーンに作り直し、公式インストーラーをtrixie向けパッチなし・そのままの手順で実行する**。ディスプレイは同じ一般的なフルHD HDMIモニタのまま接続し、OS世代の違いだけを切り分ける。もしこれで黒画面・メインコンテンツ非描画が解消すれば、29セッションの調査全体の根本原因が「公式未検証のOS/ドライバ世代」だったと確定し、以降はtrixie環境でのワークアラウンド運用ではなくbookwormでの正規運用に切り替える方針となる。
1. 上記でも症状が再現する場合：ディスプレイ側の要因（非公式ディスプレイ構成）を疑い、購入予定・入手可能であれば純正Raspberry Pi公式ディスプレイまたはAR1100対応ディスプレイでの再検証を検討する。
2. 上記2点でも症状が再現する場合のみ、GLコールレベルの調査（第29回セッションからの持ち越し）へ戻る：`glTexImage2D`/`glTexSubImage2D`のフックによるテクスチャ実データ確認、`glUseProgram`によるシェーダプログラム切り替えの確認、`apitrace`のトレースファイル書き出し失敗の原因調査。
3. 視覚確認・本番適用方法の検討（第28回セッションから持ち越し）は、上記のメインコンテンツ問題が解決してから再開する。

---

**（第30回セッション、ユーザー立ち会いのもとRaspberry Pi 3Bをbookworm 64bitでクリーン再インストールして実施）で得た知見：第29回セッションの「OS世代(trixie)が根本原因」という仮説を否定。一方でクリーン再インストールを機に、これまで電源アンダーボルテージと一括りにされていた「GPUリセット」に、電圧不足とは独立した別要因（`vc4-fkms-v3d`の非同期フリップ非対応・既知バグ修正の再適用漏れによるCMA枯渇・過大な描画解像度）が複合していたことを新たに発見・解消し、メインコンテンツ非描画バグ以外のノイズ要因を取り除いたクリーンな土台を確立した**：

**1. 🔴 決定事項通りbookworm 64bitでクリーン再インストールを実施し、公式インストーラー（`bit.ly/3yTbPyZ`）をtrixie向けの読み替えなし・無改造でそのまま実行できることを確認した**（パッケージ名の不整合等は一切発生せず、trixie特有の対応が必要だったという第29回までの前提を裏付けた）。しかし**視覚確認の結果、黒画面・メインコンテンツ非描画の症状はtrixie環境とほぼ同じまま再現し、「OS世代が根本原因」という第29回セッションの仮説は否定された**。

**2. 電源アンダーボルテージが同一電源（5V/2.1A固定出力）で再発することを確認、対処は従来と同一**：`vcgencmd get_throttled`が`0x50000`（アンダーボルテージ発生履歴あり）、`dmesg`にも`hwmon1: Undervoltage detected!`を確認。SDカードが新品でありconfig.txtに過去の緩和策が入っていなかったことが原因。従来と同じ`/boot/firmware/config.txt`への`arm_freq=800`（1.2GHz→800MHz）・`dtoverlay=disable-bt`追記で解消することを再確認した。

**3. 🔴🎉🔑 新発見：`dtoverlay=vc4-fkms-v3d`（レガシーFake-KMSドライバ、bookwormのデフォルト）で、電圧不足とは無関係に`[drm:vc4_fkms_page_flip] *ERROR* Async flips aren't allowed`→`[drm] Resetting GPU.`が1〜4秒間隔で継続発生していることを`dmesg`で発見した**。`throttled=0x0`（電圧不足なし）の状態でも発生することを確認しており、従来「GPUリセットは電源問題の随伴症状」としていた理解（ARCHITECTURE.md該当箇所参照）を修正する必要がある新事実。ユーザーが物理モニタで目視した「2秒おきに上から順にスキャンされるように点滅する」という症状は、`dmesg`上のGPUリセット間隔と一致した。

**4. `dtoverlay=vc4-kms-v3d`（フルKMSドライバ）へ切替えたところ`Async flips aren't allowed`エラーは0件に解消したが、`Resetting GPU`自体は同程度の頻度で残存**。切替直後の検証中に実機が完全にハングし、物理電源の抜き差しが必要になる事故が1件発生した（ウォームリブートでは復旧できない状態だった）。

**5. 🔴🎉 クリーン再インストールのため、過去に確定済みだった実バグ修正2件（`~/.kivy/config.ini`の`multisamples`を`2`→`0`、`~/.config/racecapture/prefs.json`の`full_screen_mode`を`0`→`1`）が未適用のままだったと判明**。この状態でCMA（GPU用メモリプール、`config.txt`の`gpu_mem=256`で256MB確保）の空き容量を確認したところ**256MB中わずか8MBまで枯渇**しており、GPUリセット頻発の直接要因と強く疑われた。既知修正を再適用した結果、CMA空きは19MBへ倍増、GPUリセット頻度は144秒間で25回→同程度の時間で2回まで激減した。

**6. 🔴🎉 解像度を過去セッションで判明していた純正タッチパネル想定値`800x480`へ強制的に固定したところ、CMA空きが250MB超（ほぼ全解放）まで回復し、GPUリセットは7分間の稼働で0件、体感の滑らかさも明確に改善した**。ただし試行錯誤の過程で重要な運用知見を得た：**`vc4-kms-v3d`（フルKMSドライバ）では解像度指定は`config.txt`の`hdmi_cvt`/`hdmi_mode`/`display_auto_detect`では効かず（起動コンソールの一時的な表示にしか反映されず、アプリ起動後はモニタのEDID優先解像度＝1920x1080へ戻ってしまう）、`/boot/firmware/cmdline.txt`へのカーネルパラメータ`video=HDMI-A-1:800x480@60`の追加で初めて実際に反映されることを確認した**（コネクタ名は`/sys/class/drm/`で`card0-HDMI-A-1`と確認済み）。

**7. 🔴🚨🎯 上記5・6の対処でGPUリセット・CMA枯渇はほぼ解消し、動作も明確に改善したにもかかわらず、DASHBOARD等メインコンテンツ領域が描画されない本丸のバグ自体（`Sessions`/`Import Logs`タブ等、背景がほぼ真っ黒でラベル文字のみ見える状態）は変化しなかった**。つまり今回発見・解消したGPUリセット系の問題群は、29セッションにわたり追ってきた本丸バグとは別の、独立した複合的なノイズ要因だったと結論づけられる。本丸バグの原因究明は引き続き未解決だが、**電圧不足・GPUリセット・CMA枯渇という3つの不安定要因を全て取り除いたクリーンな環境が今回初めて整った**ことは大きな前進である。

**実機（`rc-dash-3b`）に加えた変更点（次回セッション用の記録、いずれも再起動後も維持される）**：
- `/boot/firmware/config.txt`：`arm_freq=800`・`dtoverlay=disable-bt`（電圧対策）、`dtoverlay=vc4-fkms-v3d`→`vc4-kms-v3d`（GPUドライバ切替）、`display_auto_detect=1`→`0`（効果なしと判明、切り戻し不要ではあるが残置）、`hdmi_group=2`/`hdmi_mode=87`/`hdmi_cvt=800 480 60 6 0 0 0`/`hdmi_drive=2`（実際には効いていないが残置、次回整理候補）。変更前バックアップは`config.txt.bak_4-4-2_kms`・`config.txt.bak_4-4-2_res`として同ディレクトリに保存済み。
- `/boot/firmware/cmdline.txt`：末尾に`video=HDMI-A-1:800x480@60`を追加（解像度固定の本体）。バックアップは`cmdline.txt.bak_4-4-2`。
- `~/.kivy/config.ini`：`multisamples`を`2`→`0`、`fullscreen`を`0`→`1`、`width`/`height`を`800`/`600`→`800`/`480`（最終的に`hdmi_cvt`ではなく解像度固定と合わせた値）
- `~/.config/racecapture/prefs.json`：`full_screen_mode`を`0`→`1`
- SSH接続：新規インストールのためパスワード認証で1回ログインし、既存の公開鍵（`racecapture_dash_ed25519`）を`~/.ssh/authorized_keys`に再登録済み。以降は従来通り鍵認証で接続可能。接続先IPは今回`192.168.137.83`（再起動のたびに変わる可能性がある点に注意、`rc-dash-3b.local`のmDNS解決も引き続き不安定）。

**次回の最優先候補（優先度順、第30回セッション終了時点で更新）**：
0. **最優先：今回確立したクリーンな環境（bookworm・`vc4-kms-v3d`・800x480固定・MSAA無効）の上で、メインコンテンツ非描画バグ本体の調査を再開する**。GPUリセット等のノイズが無くなったことで、第29回セッションが持ち越していたGLコールレベルの調査（`glTexImage2D`/`glTexSubImage2D`のテクスチャ実データ確認、`glUseProgram`のシェーダ切り替え確認、`apitrace`のトレース書き出し失敗の原因調査）がより正確に行えるはずである。
1. 電源そのものの交換（5V/2.5A以上、できれば純正Raspberry Pi電源）は依然として根本対策として有効。`arm_freq=800`の制限を外せれば、現状わずかに残るカクつきもさらに改善する可能性がある。
2. ディスプレイを純正タッチパネル/AR1100対応品へ変更する案は、解像度を800x480へ合わせたことである程度代替できた可能性が高く、優先度を下げてよい。
3. `config.txt`に残置した効果のなかった設定（`display_auto_detect=0`・`hdmi_group`/`hdmi_mode`/`hdmi_cvt`/`hdmi_drive`）は実害はないが、次回整理する余地がある（`cmdline.txt`の`video=`指定と重複・無意味な設定のため）。

---

**今回のセッション（4-4-2続き・第31回、ユーザー不在の自律調査・6時間枠）で得た知見：クリーン再インストールで消失した調査ツールをdlsymフック方式で再構築し、メインコンテンツ非描画バグがノイズを全て排除した環境でも再現することを確認。GLコールレベルで考えられる原因（プログラム・行列・エラー・viewport・blend・scissor・FBO・頂点座標）を新ツールで網羅的に再検証し、いずれも正常と判明。既知の`glClear`部分マスク修正を本環境で再現・再適用し、背景色・トースト表示は修正されるがメインコンテンツは依然として一切描画されないことをピクセルレベルで再確認した**：

**1. 🆕 前提の確認：クリーン再インストール（第30回セッション）により、それ以前のセッションで作成した調査ツール一式（`~/decompile_4-4-2/`、`~/capture_4-4-2/`、`egl_interpose*.c`〜`drawtimeline*.c`等）はホームディレクトリごと消失していた**。新規SDカードでのクリーンインストールのため想定内。`config.txt`/`cmdline.txt`/`~/.kivy/config.ini`/`~/.config/racecapture/prefs.json`は第30回セッション終了時点の設定（bookworm・`vc4-kms-v3d`・800x480固定・MSAA無効・電圧対策）がそのまま維持されていることを確認した。`mesa-common-dev`/`libgles2-mesa-dev`/`libegl1-mesa-dev`/`apitrace`/`apitrace-tracers`を新規インストール。

**2. 🔴🎉🔑 調査ツールを`dlsym()`フック方式で再構築し、なぜ単純なLD_PRELOADシンボル上書きが効かないかを独自に特定・文書化した（第8回セッションの既知事項と一致）**：SDL2がEGL/GLESの関数を、通常のグローバルシンボル解決（LD_PRELOADが効く経路）ではなく、自前で`dlopen()`した`libEGL.so`/`libGLESv2.so`ハンドルに対する明示的な`dlsym(handle, name)`呼び出しで解決しているため、素朴な関数名の再定義だけでは横取りできない。対策として`dlsym()`自体をフックし（`dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.34")`→失敗時`"GLIBC_2.2.5"`→失敗時無版数の順にフォールバックしてブートストラップ）、SDL2が対象シンボル名を問い合わせてきた瞬間に自作ラッパーのアドレスを返す方式（`frametrace5.c`〜）を確立。あわせて`eglGetProcAddress()`も第二の横取りポイントとしてフック。アプリ自身が`dlsym`で問い合わせない関数（`glIsEnabled`・`glGetError`）向けに、SDL2が使った実際のハンドルを最初のフック成功時に保存しておき（`captured_gles_handle`）、それを使って解決する工夫も追加した（`RTLD_NEXT`はSDL2が`RTLD_LOCAL`で`dlopen`したライブラリのシンボルを拾えないため）。

**3. 🔴🎯 クリーン環境（bookworm・`vc4-kms-v3d`・800x480固定・MSAA無効・GPUリセット/電圧不足なし）でも、メインコンテンツ非描画バグが第29回セッションと全く同じ形で再現することを確認した**：`Window.screenshot()`（トリガーファイル方式、`eglSwapBuffers`フック内から`PyGILState_Ensure`→`PyRun_SimpleString`→`PyGILState_Release`で安全に呼び出す、gdb不使用）でダッシュボード画面をダンプしたところ、画面はほぼ完全な黒`(0,0,0,255)`一色（サンプリングした42,667点中41,812点=98%）で、唯一の例外はトースト（"Session recording started"）の背景矩形部分だけだった。ピクセルレベルでの座標特定により、この非黒領域のbounding boxが(302,411)-(497,452)と、トーストの表示位置に正確に一致することを確認し、「メインコンテンツ以外の何かがうっすら描画されている」可能性を排除した。

**4. 🔴🎉 GLコールレベルで考えられるほぼ全ての原因候補を新ツール（`frametrace5.c`〜`frametrace14.c`）で個別に検証し、いずれも正常と判明した（新規に完全否定した仮説群）**：
   - **無効プログラムでの描画**：`glUseProgram`は`1`と`0`のみが呼ばれるが、描画コール（`glDrawElements`/`glDrawArrays`）はプログラム別バケット集計で全て`program=1`に紐づいており、`program=0`（バインドなし）状態での描画は1件も存在しなかった（1フレーム369描画・22,957頂点）。
   - **MVP変換行列の退化・NaN**：`glGetUniformLocation`でuniform名を突き止めた上で`glUniformMatrix4fv`を検証。`projection_mat`は800x480に対応した標準的な正射影行列、`modelview_mat`は単位行列で、NaN/Infや異常な平行移動は一切なかった。
   - **GLエラー**：`glGetError()`を毎描画コール後に呼び出したが、342〜369描画全てで`err=0`（エラーなし）。
   - **viewport不整合**：`glViewport(0,0,800,480)`が起動時に一度設定され、解像度と完全に一致（過去セッションで疑われた1920x1080の残置値は無かった）。
   - **ブレンド関数の退化**：`glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)`が起動時に一度設定されて以降不変、標準的な半透明合成でブレンドは常時有効。
   - **シザークリップ**：`glScissor`は一度も呼ばれず、`GL_SCISSOR_TEST`も常に無効。
   - **オフスクリーンFBOへの誤描画**：`glBindFramebuffer`をフックした結果、サンプルした全描画がFBO 0（デフォルト＝画面向け）に対して発行されていた。
   - **危険な破棄系ステート**：トレース開始時点の`glIsEnabled`一括ダンプで`GL_DEPTH_TEST`=0・`GL_CULL_FACE`=0・`GL_SCISSOR_TEST`=0・`GL_STENCIL_TEST`=0（フレーム中は多用されるが起点は無効）。

**5. 🆕 ステンシルテストの有効/無効と「本来見えるはずの描画（不透明度>0）」の相関を新規に定量化したが、きれいな二値分離にはならなかった**：1フレーム342描画のうち、stencil有効時（268描画）はalpha>0が143件（53%）・alpha=0が123件（47%）、stencil無効時（96描画、トーストや非クリップ要素と推測）はalpha>0が49件（51%）・alpha=0が47件（49%）と、ほぼ同じ比率だった。もし「ステンシルバッファの汚染による誤クリップ」が唯一の原因なら、stencil無効時のalpha>0描画（49件）は無条件に画面へ反映されるはずだが、実際にはこれらもスクリーンショット上には現れておらず、単純なステンシル起因説だけでは説明がつかないことが判明した。

**6. 🔴🎉🔑 GLES2に`glGetBufferSubData`が存在しないため、`glBufferData`フックでアップロード時点（クライアント側ポインタ）の頂点データを直接検査する手法を新規確立し、単純な不透明白色矩形ですら画面内の妥当な座標を持ちながら描画されていないことを実証した**：Kivyの標準頂点フォーマット（`glVertexAttribPointer`で確認済み：`stride=16`=位置(x,y)+UV(u,v)の4 float）を前提に、VBOアップロード時のバイト列をfloatとして解釈しbounding boxを計算する仕組み（`frametrace12.c`〜）をプロセス起動直後から無条件で記録し、後から個々の描画コールの`arraybuf`（GL_ARRAY_BUFFERバインドID）と突き合わせた（`correlate.py`）。結果：
   - **X座標が負の頂点群（-230〜0等）**は、閉じたNavigationDrawer（デフォルト幅約200〜230pxで画面外`x=-drawer_width`に配置される、KivyMD標準の"閉状態"実装）に対応すると推測され、バグではなく意図した挙動と判断した。
   - **X座標が800を超える頂点群**（最大1193まで確認）は、横スクロールカルーセル（AnalysisCarousel等）のビューポート外にある未表示アイテムに対応すると推測され、同様にバグではない。
   - **画面内(0-800, 0-480)に完全に収まる妥当な座標を持つ描画**（例：`tex=1`(デフォルト白テクスチャ)・`color=(1,1,1,1)`(不透明白)・`stencil=0`(クリップなし)・`bbox=(0,0)-(134,504)`）が複数存在し、これらは個々の状態（テクスチャ・色・行列・ブレンド・シザー・FBO・エラー）が全て検証済みで正常であるにもかかわらず、実際のスクリーンショットには一切現れていなかった。**これは「クリップ・状態異常のいずれでも説明できない、正当な描画コールが画面に反映されない」という、これまでで最も直接的な証拠である**。
   - 一部のバッファ（KivyMDの角丸シャドウ等、複雑なメッシュ）は天文学的に大きい非現実的な値を示したが、これは`stride=16`という前提が単純な矩形以外のメッシュには当てはまらない（頂点フォーマットが異なる）ツール側の限界であり、バグの証拠ではないと判断した（次回の課題として記録）。

**7. 🔴🎉🎯 第28回セッションで確立済みの`glClear`部分マスクバグ修正（`drawtimeline8.c`のワークアラウンド：マスクが`GL_COLOR_BUFFER_BIT`を含まない場合、クリア色を正しい背景色へ一時差し替え、マスクへ`GL_COLOR_BUFFER_BIT`を強制追加してから実際の`glClear`を呼び、その後元のクリア色へ復元する）を本セッションのクリーン環境で再構築・適用し、文書化通りに機能することを確認した一方、メインコンテンツの非描画は全く解消しないことを改めてピクセルレベルで確定した**：
   - ワークアラウンドは実際に作動（約700スワップの観測中に部分マスク`glClear`2,800回を修正、フルマスク700回はそのまま通過）。
   - 修正適用状態でのスクリーンショットは、背景色が正しいダークグレー`(18,18,18,255)`になり（ワークアラウンドなしでは`(0,0,0,255)`だった）、トーストも問題なく表示された。**これは第29回セッション（trixie環境）で確認された「サイドバー/背景色は回復するがメインコンテンツは回復しない」という結果と完全に一致する**。
   - トースト・ドロワーいずれも表示されていない瞬間のスクリーンショットをフル解像度でヒストグラム解析したところ、**384,000ピクセル全てが単一の色`(18,18,18,255)`（背景色そのもの）で、ゲージ・ラベル・アイコン等のメインコンテンツに相当するピクセルは1つも存在しなかった**。既知の`glClear`バグはメインコンテンツ非描画の（唯一の、あるいは主要な）原因ではないことが、これまでで最も明確な形で再確認された。

**8. 🎯 総括：GLコールの引数レベルで検証可能な原因はほぼ全て潰れた。次に疑うべきは、GLコールの引数としては正常でも実際のラスタライズ結果に反映されないという、Mesa VC4ドライバの（既知の`glClear`バグとは別の）タイル化レンダラ固有の不具合の可能性が、これまでで最も強く示唆される状況になった**。既知の`glClear`バグ自体、VC4の「タイルバッファ高速クリアパス」が部分マスク要求を正しく扱えないという実装欠陥だったことを踏まえると、同種のタイラー実装の欠陥が、大量の小さな半透明矩形描画＋頻繁なステンシルpush/popという今回確認したパターン（1フレーム342〜369描画、ステンシル有効/無効の頻繁な切り替え）の一部に対しても起きている可能性が高いと推測される（未検証の仮説）。

**9. 実機（`rc-dash-3b`）の状態（セッション中盤時点）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの`race_capture`に復旧したことを確認済み（`throttled=0x0`、`dmesg`上のGPUリセット0件）。ハードウェアへの恒久的な変更なし（`config.txt`等は第30回セッション終了時点のまま）。生成物（`~/frametrace5.c`〜`~/frametrace15.c`とそれぞれの`.so`、いずれもホームディレクトリに保存済みのため次回セッションでも再利用可能）のうち、**`~/frametrace15.c`が最新かつ最も完全な版**（per-draw状態ログ・VBO座標ログ・viewport/blendfunc/scissor/FBOログ・capability一括ダンプ・`glClear`ワークアラウンドを全て統合）。トリガーファイルは`/tmp/rc_trigger_shot`（スクリーンショット、`Window.screenshot()`使用）・`/tmp/rc_trigger_trace`（Nフレームトレース）・`/tmp/rc_trigger_done`（完了通知）の3種類、ログは`/tmp/ft.log`固定パス。

**10. 🔴🎉🔑 セッション後半、`apitrace`のトレース書き出しが第27〜28回セッション以来失敗し続けていた原因を特定・解消し、独自インタポーザの全結論を独立した業界標準ツールで裏付けた上、これまで未検証だった観点（テクスチャパラメータ・opacity uniform・colorMask/描画の時系列インターリーブ）も新たに検証していずれも正常と確認した**：
   - **修正内容**：`LD_PRELOAD=/usr/lib/aarch64-linux-gnu/apitrace/wrappers/egltrace.so`に加え、**環境変数`TRACE_FILE`で出力先を明示的にホームディレクトリ配下の書き込み可能なパスへ指定する**ことで、これまで原因不明とされていたトレース書き出し失敗が解消し、477フレーム・19MBの完全なトレースファイルを正常に取得できた（過去セッションはデフォルトの出力先解決に失敗していたと推測される）。
   - `apitrace dump-images`（GPU実レンダリング結果の画像化）は今回も`waffle_display_connect failed`で失敗し、第12回セッションで特定済みの「GBMヘッドレスreplayがこの実機では使用不能」という制限が変わっていないことを再確認した。一方`apitrace dump`（トレース内容のテキスト化、リプレイ不要）は問題なく動作し、以降の分析はこちらに専念した。
   - **テクスチャパラメータ**：`glTexParameteri`は全449回とも`WRAP_S/T=GL_CLAMP_TO_EDGE`・`MIN/MAG_FILTER=GL_LINEAR`（ミップマップ不要な標準構成）で統一されており、`glGenerateMipmap`は0回。GLES2の「不完全テクスチャ（ミップマップ未生成なのにミップマップ系フィルタを指定）は`(0,0,0,0)`としてサンプリングされる」という既知の落とし穴には該当しないことを確認した（新たに検証・否定した仮説）。
   - **opacity uniform**：`glGetUniformLocation`で`"opacity"`(loc=3)の存在は既に把握していたが値の追跡は未実施だったため、`glUniform1f(location=3, ...)`の全呼び出し（507回）を集計したところ、499回が`v0=1`（完全不透明）、8回が`v0=0`、残りはフェードアニメーション中と見られる中間値だった。メインコンテンツ全体のopacityが恒常的に0になっているような系統的な異常はなく、この新仮説も否定された。
   - **colorMask/描画のインターリーブ順序**：`glColorMask`は`(TRUE×4)`/`(FALSE×4)`が全体でちょうど7,613回ずつと完全に対（既知）だが、今回初めて実際の呼び出し順序を1フレーム分通しで確認し、`count=3462`という大きな描画（ステンシルスタンプ、第28回セッションで特定済みの巨大描画と一致）は一貫して`colorMask=(FALSE,FALSE,FALSE,FALSE)`の直後に、`count=6`等の小さな本描画は一貫して`colorMask=(TRUE,TRUE,TRUE,TRUE)`の直後に発行されており、ペアの対応関係・順序ともに破綻は見られなかった（新たに検証・否定した仮説）。
   - 成果物は`~/apitrace_4-4-2/`（`dash_session31.trace`本体、`dump_texparam.txt`/`dump_uniform1f.txt`/`dump_misc.txt`の分析結果、突き合わせ用`correlate.py`）に保存済み。**トレース取得自体が初めて成功したことは、今後Mesa GitLabへの不具合報告を行う際の直接的な証拠としても活用できる**。

**11. 実機（`rc-dash-3b`）の状態（セッション中盤時点）**：apitrace検証用に起動した`race_capture`は`kill -INT`で正常終了（トレースファイルも正常にフラッシュ・完了）、その後`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの状態へ再度復旧したことを確認済み（`throttled=0x0`）。ハードウェアへの恒久的な変更なし。

**12. 🔴🎉🎯🔑 セッション最終盤、「最小構成の再現アプリ」を作成・実機検証し、これまでの調査全体の方向性を覆す決定的な結果を得た：RaceCaptureのコードを一切含まない標準Kivy（システムパッケージ`python3-kivy` 2.1.0、bookwormリポジトリ）だけで、apitraceで特定した構造パターン（`ScrollView`によるステンシルpush/use/unuse/pop・多数の半透明角丸矩形・ウィジェットごとのVBO・colorMaskトグル）を再現したところ、色・影・角丸・スクロールバーとも完璧に正常描画された。同じ実機・同じMesa VC4ドライバ・同じOSの上で標準Kivyの同種パターンが問題なく動作することが実証され、「Mesa VC4ドライバのタイラー固有バグ」という前回（本セッション前半）の最有力仮説は覆り、焦点はRaceCapture固有のビルド・コードへ戻った**：
   - **検証方法**：`race_capture`を停止してDRMマスター権を空け、`ScrollView`＋`GridLayout`（60個の`ShadowedCell`、各セルは`RoundedRectangle`×2枚の半透明黒シャドウ（`(0,0,0,0.5)`/`(0,0,0,0.15)`、apitraceで確認済みのRaceCapture本体のシャドウ色パターンと同一）＋不透明カード本体）を持つ最小アプリ（`~/minimal_repro_4-4-2/minimal_repro.py`）を作成し、`frametrace15.so`（今回のセッションで構築した最新インタポーザ、`glClear`ワークアラウンド込み）を`LD_PRELOAD`して`Window.screenshot()`で撮影した。
   - **結果**：グリッド全体（ダークグレー・別トーンのグレー・ティール・白の角丸カード、下に薄い影）が実機モニタ相当のスクリーンショット上で完璧に正常表示された。テキストレンダリング単体（`Label`のみの別アプリ）も、強制再描画してから撮影した場合は正常表示された（最初の撮影が黒一色だったのは、静的シーンでは`eglSwapBuffers`が最初の数フレーム後に停止するという既知の挙動下で撮影タイミングが早すぎた単なるテスト側の不備と判明、`Clock.schedule_interval`で強制的に`ask_update()`し続けてから撮影したところ再現しなくなった）。
   - **意味合い**：GLコールレベルで検証可能な原因（第31回セッション前半で全て潰した）に続き、「Mesa VC4ドライバのタイル化レンダラ自体に、大量の小さな半透明描画＋頻繁なステンシルpush/popという構造に起因する固有バグがあるのでは」という前半の推測も、より直接的な形で否定された。**残る可能性は、RaceCapture本体固有の何か**（PyInstallerでバンドルされたKivy 2.3.1・KivyMD 1.0.2・バンドルSDL2 2.30.7という、システム版（今回のテストで使ったKivy 2.1.0・システムSDL2）とは異なるバージョン構成、または`DashboardView`等アプリ自身のKV/Pythonコード）に絞り込まれた。次回はバンドル版と同じバージョン構成（Kivy 2.3.1・KivyMD 1.0.2・SDL2 2.30.7）での再現実験、または実際の`DashboardView`のKVソース（`~/decompile_4-4-2/`、今回のクリーン環境では再取得が必要）を土台にした再現実験が最優先候補となる。

**13. 実機（`rc-dash-3b`）の状態（セッション中盤・追加検証前）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの`race_capture`に復旧したことを確認済み（`throttled=0x0`）。ハードウェアへの恒久的な変更なし。最小構成再現アプリのソース（`minimal_repro.py`・`label_only2.py`）は`~/minimal_repro_4-4-2/`に保存済みのため次回セッションでも再利用可能。

**14. 🔴🎉🔑🎯 セッション最終盤、点12の結果を受けて「バンドル版と同一バージョン構成（Kivy 2.3.1・KivyMD 1.0.2）」での再現実験を実施したが、これも完璧に正常描画され、Kivy/KivyMDのバージョン自体も原因候補から外れた。原因はRaceCapture自身のコード（`DashboardView`等のKV/Pythonコード）、またはPyInstallerバンドル実行環境固有の何かへとさらに絞り込まれた**：
   - **背景**：PyInstallerバンドル（`/opt/racecapture/_internal/kivy`・`kivymd`）を`PYTHONPATH`経由で直接importしようと試みたが、バンドル側に通常の`__init__.py`を伴うパッケージ構造が無く（PyInstaller特有の凍結パッケージ形式）、`sys.path`の先頭に挿入してもPythonの名前空間パッケージ解決規則によりシステム版（`kivy` 2.1.0）へフォールバックしてしまい断念。代わりにvenvへ`pip install kivy==2.3.1 kivymd==1.0.2`で正確に同じバージョンをソースからビルドする方式に切り替えた（ビルド依存関係`cython3`・`libsdl2-dev`等は`apt`で導入、コンパイル込みで数分程度）。
   - **結果**：`kivy 2.3.1`・`kivymd 1.0.2`（インストール先ログでバージョン確認済み）の環境で`minimal_repro.py`（点12と全く同じ、`ScrollView`＋60個の影付き角丸カード）を実行したところ、**サイドバー等ではなくグリッド本体が、点12（システム版Kivy 2.1.0）の時と寸分違わず完璧に正常描画された**。
   - **意味合い**：Kivy/KivyMDともにバンドル版と同一のバージョンで検証してもなお正常描画されたため、「バンドルされたKivy/KivyMDバージョン自体が原因」という仮説は否定された。残る有力候補は、①バンドルSDL2 2.30.7固有の問題（システムSDL2 2.26.5とは異なる。ただし第7回セッションで「SDL2コアライブラリ単体の差し替え」は既に無効と確認済みのため優先度は控えめ）、②PyInstallerの凍結実行環境そのもの（`sys.frozen`・リソースパス解決・`_internal`ディレクトリからの実行等、通常のPython実行とは異なる要因）、③**RaceCaptureアプリ自身の`DashboardView`等のKV/Pythonコードの具体的な内容**（今回の最小構成アプリは一般的なウィジェット構成を模しただけで、実際のDashboardViewのKV構造そのものではない）の3つに絞られ、③が最も有力と判断される。

**15. 実機（`rc-dash-3b`）の状態（セッション中盤・逆コンパイル再開前）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの`race_capture`に復旧したことを確認済み（`throttled=0x0`）。ハードウェアへの恒久的な変更なし。`~/kivy_repro_venv/`（Kivy 2.3.1・KivyMD 1.0.2のvenv、次回セッションでも再利用可能）・`~/minimal_repro_4-4-2/`（再現アプリソース一式）を保存済み。

---

**（ユーザーから「あと3時間続けて」と指示を受け、自律調査を継続）**

**16. 🔴🎉🔑 `DashboardView`の実KVソースを再逆コンパイルで取得し、`AnalysisCarousel`（`kivy.uix.carousel.Carousel`のサブクラス）・`TripleGaugeBar`（`kivy.uix.scatter.Scatter`のサブクラス）という基底クラスも確認した上で、実KV構造をほぼそのまま（子ウィジェットはスタブ化）`ScreenManager`でラップして再現実験したが、これも完璧に正常描画され、DashboardViewのKV構造自体も原因候補から外れた**：`pyinstxtractor-ng`+`xdis`を使い`race_capture`バイナリからPYZアーカイブを再展開、`.pyc`のcode object定数プールを走査して`Builder.load_string`相当のKV文字列を直接抽出する手法（`~/decompile_4-4-2/search_kv.py`）を確立し、`<DashboardView>`の実KVルール全文（`FloatLayout`直下に`AnalysisCarousel`・`TripleGaugeBar`・`IconButton`×2・`PreferencesLockComboButton`・`FullCourseFlagIndicator`・`PopupAlertView`が並ぶ構造）を取得した。これをバンドル同等のKivy 2.3.1/KivyMD 1.0.2 venv上で、`ScreenManager`に載せた`Screen`の中身として実行したところ、カルーセルのスライド・ゲージバーの子ウィジェット・各スタブウィジェットとも全て正常に色付き表示された。**ScreenManagerでラップした実DashboardView構造ですら再現しなかったことで、原因はDashboardView自体のKV構造でもないと判明し、「実際に稼働中のRaceCaptureプロセスの何らかの状態」に焦点が移った**。

**17. 🔴🎉🔑🎯 稼働中の実`race_capture`プロセスへ任意のPythonコードを注入できる汎用機構（`rc_trigger_pyexec`）を新規に確立し、これを使って「新しく作った単純なウィジェットを、実際に稼働中のアプリの各階層へ直接追加する」比較実験を行った結果、これまでで最も明確な形で境界線を特定した：`app.root`直下・`RelativeLayout`直下は正常描画されるが、その子である`BoxLayout`（`ScreenManager`と`ToolbarView`を包む）に追加したマーカーだけが完全に消える**：
   - **汎用注入機構**：`frametrace15.c`をベースに、`eglSwapBuffers`フック内で`/tmp/rc_trigger_pyexec`（中身は実行したい`.py`ファイルのパス）を検知したら`PyGILState_Ensure`→`PyRun_SimpleString("exec(open(path).read())")`→`PyGILState_Release`で安全に任意コードを実行する仕組みを追加（`frametrace16.c`）。既存の`Window.screenshot()`トリガーと全く同じ安全な実行コンテキスト（レンダースレッド・GIL同期）を再利用しており、gdb不使用・事故なく多数回（10回以上）実行できた。
   - **ウィジェットツリーの実構造を確認**：`app.root`（`AppMainFrame`）→`RelativeLayout`→（`NavigationDrawer`, `BoxLayout`→（`ScreenManager`→`Screen`(`SetupView`または`DashboardView`), `ToolbarView`)）という階層を実測で確認。
   - **比較実験**：同一の単純な`Widget`（`Rectangle`のみのcanvas）を、①`Window`直下、②`app.root`直下、③`RelativeLayout`直下、④現在の`Screen`（`ScreenManager`配下）直下、の4箇所に追加して単一のスクリーンショットで比較したところ、**①②③は全て正常に表示され、④（`ScreenManager`配下）だけが完全に非表示**だった（`add_widget`自体は例外なく成功、`widget.parent`も正しく設定されていることを確認済み）。
   - **境界の精密特定（二分探索）**：`Lroot`（`app.root`直下）・`L0`（`RelativeLayout`直下）・`L1`（`BoxLayout`直下）にそれぞれ異なる色のマーカーを同時に追加して1枚のスクリーンショットで比較したところ、**Lroot（白）とL0（黄）は表示されたが、L1（オレンジ、`BoxLayout`直下）だけが完全に非表示**だった。これにより境界は`RelativeLayout`と`BoxLayout`の間に精密に特定された。
   - **意味合い**：これは第21回セッション（test28〜33）が確立した「`Window`直下は描画されるが、アプリの`RelativeLayout`ルートコンテナのサブツリー内は描画されない」という知見と一致するが、今回はより正確に「`RelativeLayout`自体は含まれず、その子`BoxLayout`（`ScreenManager`と`ToolbarView`を包む具体的な1つのウィジェットインスタンス）以下」という、1階層分だけ精密な境界を今回確立した。ウィジェットの種類・複雑さに関係なく（単純な`Widget`+`Rectangle`ですら）このBoxLayout以下では描画されないことから、**問題はウィジェットの内容ではなく、この特定のBoxLayoutインスタンス（またはそのレンダリングコンテキスト）固有の何かにある**と強く示唆される。

**18. ⚠️🔑 上記BoxLayout自体の canvas.before/canvas.after は空（0命令）で、`opacity`も1.0、クラスも素の`kivy.uix.boxlayout.BoxLayout`（カスタムサブクラスではない）であることを確認し、BoxLayout自身に明示的な異常は見当たらなかった。一方、調査の過程で兄弟ウィジェット`NavigationDrawer`（`racecapture.menu.navigation_drawer.NavigationDrawer`）のcanvas.beforeに、範囲外の負のアルファ値`Color: rgba=[0,0,0,-0.25]`という、RaceCaptureアプリ自身の実装バグと見られる異常値を発見した**：このColorは直前の`Rectangle: pos=(0,0) size=(0.0, 440.0)`（ドロワーが閉じている間は幅0の退化した矩形）に対応しており、`StencilPush`〜`StencilUse`〜（このColor+矩形）〜`StencilUnUse`〜`StencilPop`という、ドロワーの開閉状態に関わらず**毎フレーム無条件に実行される**canvas.before命令列の一部だった。`relative_layout.children`の描画順（`[NavigationDrawer, BoxLayout]`、Kivyの子リストは`children[0]`が最後に=最前面に描画される）から、NavigationDrawerはBoxLayoutより後（＝手前）に描画されることも確認した。

**19. ⚠️ 上記の負アルファ値が実際にGL側の色書き込みへ影響しているかを、`glUniform4f`の引数を`[0,1]`へ強制クランプするワークアラウンド（`frametrace16.c`に追加）で直接検証したが、結果は否定的だった**：ドロワーが閉じている間はRectangleの幅が0のため退化描画（頂点0個、GLコール自体発行されない）となりクランプは一度も発火しなかった。`nav.state = 'open'`のようにプロパティを直接書き換えて幅を非ゼロにするとクランプが発火する（`glUniform4f`実引数の負値をログで確認）ことは確認できたが、その状態でもScreenManager領域・NavigationDrawer自身のメニュー項目とも依然として非表示のままだった。後に判明した通りこの直接プロパティ書き換えは正規の開閉アニメーション経路（`.open()`メソッド）を経由しない不完全な操作だったため、この特定の否定結果はクランプ自体の有効性を完全には切り分けられていない点に注意（次点参照）。

**20. 🔴🎯 正規の`nav.open()`メソッド（`nav.state`の直接代入ではなく）でドロワーを開いたところ、サイドバー（DASHBOARD/ANALYSIS/SETUP/SYSTEM STATUS/EXITの項目・アイコンとも）は完璧に正常表示され、第29回セッションの知見（サイドバーは`glClear`修正で回復する）を本セッションでも再確認した。一方、ドロワーが開いている最中でもScreenManager領域（画面右側）は依然としてスクリム暗転効果のみが見え、DASHBOARD/SETUP等の中身は一切表示されないままだった**：ピクセル解析により、ScreenManager領域は`(5,5,5)`（スクリムで暗転された背景）と`(18,18,18)`（素の背景）の2色のみで構成されており、ウィジェット内容に相当する色の変化は皆無だった。これにより、「負のアルファ値のクランプがメインコンテンツ非描画を解決する」という仮説は、正規の開閉経路を使った条件でも明確に否定された。負のアルファ自体はRaceCaptureアプリ側の実装上の欠陥（度数計算の符号ミスと推測される）として記録に値するが、今回の主要バグの直接原因ではないと判断する。

**21. 実機（`rc-dash-3b`）の状態（セッション中盤・BoxLayout切り分け実験前）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの`race_capture`に復旧したことを確認済み（`throttled=0x0`、GPUリセット0件）。ハードウェアへの恒久的な変更なし。生成物：`~/frametrace16.c`/`.so`（pyexec注入機構＋色クランプワークアラウンド込み、最新版）、`~/inject_scripts_4-4-2/`（`probe_tree.py`・`inject_widget.py`・`inject_widget_root.py`・`inject_bisect.py`・`inspect_boxlayout.py`・`inspect_navdrawer.py`・`check_nav_alpha.py`・`open_drawer2.py`、いずれも再利用可能）、`~/decompile_4-4-2/`（`search_kv.py`含む逆コンパイル一式、再構築済み）。

**22. 🔴🎉🔑🎯🎯 セッション最終盤、稼働中の実`race_capture`プロセスに対して`ScreenManager`を`BoxLayout`から`RelativeLayout`直下へその場で移し替える実験を行ったところ、SetupView（タブ・案内文・画像・EXIT/NEXTボタン全て）が完璧に正常表示され、29セッション以上探し続けてきたメインコンテンツ非描画バグに対する初めての実動ワークアラウンドを実機で確認した**：
   - **実験**：`app.root`→`RelativeLayout`→`BoxLayout`（`ScreenManager`と`ToolbarView`を内包）という実構造に対し、`rc_trigger_pyexec`機構経由で`box_layout.remove_widget(sm); sm.size_hint=(1,1); sm.pos=(0,0); relative_layout.add_widget(sm)`を実行（`~/isolate_tests_4-4-2/bypass_boxlayout.py`）。実行直後のスクリーンショットで、それまで完全に黒一色だったSetupView画面が、公式RaceCapture Appの実際のセットアップウィザード画面（"Welcome / Device / Connection / Preset / Tracks / Podium / Cell Service / Tour"タブ、案内文、レーシングカー画像、EXIT/NEXTボタン）として完璧に表示された。
   - **切り分け実験①（否定）**：同じ`ScreenManager`を`box_layout.remove_widget(sm)`した直後に**同じ`box_layout`へ再度`add_widget`**（親を変えない）した場合は効果なし（黒画面のまま）。単純な「remove+re-addによる再描画強制」では説明できないと判明。
   - **切り分け実験②（否定）**：`BoxLayout`クラス自体・特定インスタンスの汚染という仮説を検証するため、①素の`kivy.uix.boxlayout.BoxLayout`インスタンスを`RelativeLayout`の子として新規作成し`ScreenManager`をそちらへ移動（`swap_boxlayout.py`）→効果なし（新しいBoxLayoutインスタンスでも黒画面のまま）、②RaceCapture本体を介さない完全独立の最小Kivyアプリで`RelativeLayout`→`BoxLayout`→`ScreenManager`→`Screen`（+`Widget`+`Rectangle`）という全く同じクラス構成をゼロから構築（`isolate_screenmanager.py`）→**こちらは正常描画され、再現しなかった**。同様に`RelativeLayout`→`BoxLayout`→単純な`Widget`×2（`isolate_clean.py`）も正常描画。**これにより「`BoxLayout`というクラス自体、または`RelativeLayout`の子としての`BoxLayout`という組み合わせ自体が一般的に壊れている」という仮説は完全に否定され、原因は「稼働中の実`race_capture`プロセスの、この特定の`BoxLayout`が置かれているレンダリングコンテキストに蓄積された何らかの実行時状態」に絞り込まれた**（正体は依然未特定。候補：本セッション前半で発見した`NavigationDrawer`の毎フレーム無条件のステンシルpush/pop列が、`BoxLayout`自身がcanvas.before/afterに何の命令も持たない＝GL状態を明示的にリセットしない一方で`RelativeLayout`はcanvas.beforeで`PushMatrix`+`Translate`を行い新しい`modelview_mat`を強制的に再設定する、という非対称性が関係している可能性が高いと推測されるが未検証）。
   - **意味合い**：メカニズムの完全解明には至らなかったが、**実機で実際に動作する具体的なワークアラウンド（`ScreenManager`を`BoxLayout`でラップせず`RelativeLayout`の直接の子として配置する）**を初めて確認できた。これは`AppMainFrame`（`app.root`）を構成する実際のPython/KVコード（`racecapture`パッケージ内、ファイル名は次回要特定）を変更すれば恒久的に適用できる可能性が高い、これまでで最も具体的で実装可能な次の一手である。

**23. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての検証プロセスは終了済み、`sudo systemctl restart getty@tty1.service`で標準の自動ログイン経由・LD_PRELOADなし・watchdog付きの`race_capture`に復旧したことを確認済み（`throttled=0x0`、GPUリセット0件）。ハードウェアへの恒久的な変更なし。生成物：`~/frametrace16.c`/`.so`、`~/inject_scripts_4-4-2/`、`~/decompile_4-4-2/`（前回同様）に加え、`~/isolate_tests_4-4-2/`（`bypass_boxlayout.py`・`swap_boxlayout.py`・`reinsert_same_box.py`・`check_sizes.py`・`inject_box_proper.py`・`inject_box_direct.py`・`isolate_boxlayout_bug.py`・`isolate_clean.py`・`isolate_screenmanager.py`、いずれも再利用可能）。

**次回の最優先候補（優先度順、第31回セッション最終更新）**：
0. ~~最優先：`app.root`（`AppMainFrame`）を構成する実際のソースコードを特定し...~~ → **第32回セッション（ユーザー不在の自律調査、3時間枠）で特定・検証完了。静的KVトポロジー変更だけでは直らないという重要な訂正結果が出た。詳細は下記参照、次の最優先候補は下記32回セッション末尾に記載**。
1. 上記0で完全解明に至らなかった根本メカニズム（`BoxLayout`のcanvas.before/afterが空でGL状態を明示的にリセットしないこと、`NavigationDrawer`の毎フレームのステンシルpush/pop列との関連）は、時間があれば引き続き深掘りする価値がある。
2. NavigationDrawerの負アルファ値（`rgba=[0,0,0,-0.25]`）はメインバグの原因ではないと判明したが、RaceCaptureアプリ自身の実装バグとして記録し、いずれ`autosportlabs/menu/navigation_drawer`側の修正を検討する価値はある（優先度低）。
3. `frametrace12〜15`系列の頂点バッファ解析における`stride=16`前提の限界（KivyMDの角丸シャドウ等、複雑なメッシュで異常値が出る問題）を解消し、全描画コールのbounding boxを正確に把握できるようにする。
4. 今回再確認した`glClear`部分マスクワークアラウンドの本番適用（`run_racecapture_rpi.sh`への組み込み）は、メインコンテンツ問題の解決とは独立に、背景色・サイドバー・トーストの正常化という実利があるため、ユーザーと相談の上で先行適用を検討する価値がある。
5. Mesa GitLabへの`glClear`部分マスクバグ報告は、`~/apitrace_4-4-2/dash_session31.trace`を証拠として引き続き価値がある。

---

**（ユーザーが3時間就寝、その間の自律調査を依頼。第32回セッション）**

**1. 🔴🎉🎯🔑 `AppMainFrame`の実ソースを特定：`racecapture`パッケージ内ではなく、PyInstallerがELFバイナリに直接埋め込む「エントリスクリプト」（`main.py`、`pyinstxtractor-ng`で`main.pyc`として単独展開される、PYZアーカイブとは別物）の中に、`Builder.load_string()`へ渡す巨大なKV文字列リテラルとして存在していた**：
`~/decompile_4-4-2/race_capture_extracted/main.pyc`を`pydisasm`（`xdis`付属）で逆アセンブルし、`AppMainFrame`という定数文字列を検索することで一発で特定した（`racecapture`パッケージ配下を`search_kv.py`でいくら探しても見つからなかった理由はこれだった）。実際のKVルールは以下の通りで、これまでの実機調査で判明していた構造（`RelativeLayout`直下に`BoxLayout`（`ToolbarView`+`ScreenManager`を内包）と`NavigationDrawer`が並ぶ）と完全に一致した：
```
<AppMainFrame>:
    padding: self.app_padding
    RelativeLayout:
        BoxLayout:
            orientation: 'vertical'
            ToolbarView:
                id: status_bar
            ScreenManager:
                id: main
                pos_hint: {"center_x": 0.5, "center_y": 0.5}
        NavigationDrawer:
            id: navigation_drawer
            size_hint_y: None
            height: self.parent.height - status_bar.height
```
同じ`main.pyc`内に`RaceCaptureApp`（Appサブクラス）・`CrashHandler`も定義されていることも確認した。

**2. 🔴🎉🔑 ELFバイナリ内に埋め込まれたPyInstaller CArchiveの当該エントリを安全に書き換える汎用リパックパイプラインを新規に構築し、実際に動作することを実証した**：
`main`エントリ（type=`s`=ARCHIVE_ITEM_PYSOURCE、`race_capture`本体のELF内でzlib圧縮されて格納）は`pyinstxtractor-ng`の実装（`pip`で取得、ソース公開）を解析することでCArchiveのTOC（Table of Contents）構造とCookie構造を完全に把握し、以下を実現する`~/repack_4-4-2/repack_main_kv.py`を新規作成した：①対象エントリをzlib展開→②KV文字列を新しい内容へバイト列レベルで置換→③zlib再圧縮（圧縮後サイズは元と一致しなくてよい）→④TOC内の該当エントリの`entryPos`・`cmprsdDataSize`、後続する全エントリの`entryPos`、CArchive Cookieの`lengthofPackage`・`toc`オフセットを、サイズ差分（delta）に応じて漏れなく補正→⑤ファイル全体を再構築。**本番バイナリのコピー（`~/repack_4-4-2/race_capture.orig`）に対して実際にパッチを適用し（`race_capture.patched`）、`pyinstxtractor-ng`で再展開して`main.pyc`以外の全16ファイルがバイト単位で完全一致することを`diff -rq`で確認、`main.pyc`は`xdis`で正常にロードでき意図した新KV文字列(444バイト、元と同じ長さになるようパディング調整済み)が正確に反映されていることも確認した。実際に実機でこのパッチ済みバイナリを起動し、正常にKivy/RCPAPI/Datastore等が初期化されることも確認済み**（本番バイナリ自体には一切触れず、コピー上でのみ作業。本番の`/opt/racecapture/race_capture`はMD5ハッシュ一致でセッション終始無傷だったことを確認済み）。同一長パディングによる差し替えだけでなく、サイズが変わるパッチ（今回実測: delta=-29バイト）でも上記TOC補正ロジックにより正しく動作することも実証済みであり、**今後main.pyc内の任意の文字列定数を安全に書き換えるための再利用可能な基盤が整った**。

**3. ⚠️🔴 重要な訂正：上記の静的KVトポロジー変更（`ScreenManager`を`BoxLayout`経由ではなく`RelativeLayout`直下に最初から配置）を実際にパッチしたバイナリで実機検証したところ、メインコンテンツは描画されなかった。第31回セッション最終盤の「トポロジーを変えれば直る」という想定は誤りだったと判明した**：
新KVは`padding: self.app_padding; RelativeLayout: ScreenManager(id:main, size_hint_y:None, height: self.parent.height - status_bar.height) / ToolbarView(id:status_bar, pos_hint:{"top":1}) / NavigationDrawer(...)`という構成（`BoxLayout`を完全排除、`ToolbarView`も`ScreenManager`も`RelativeLayout`の直接の子）。パッチ済みバイナリを実機で起動し、`rc_trigger_pyexec`機構（第31回セッションで確立済みの`frametrace16.so`）でウィジェットツリーを確認したところ、**意図通り`RelativeLayout`の子が`[NavigationDrawer, ToolbarView, ScreenManager]`（`BoxLayout`なし）、`ToolbarView`の`pos=[0,440] size=[800,40]`（画面上部固定）、`ScreenManager`の`pos=[0,0] size=[800,440]`（残り全域）と、設計通りの幾何構造が正確に構築されていることを確認**した。ところが`Window.screenshot()`で実際の描画結果を確認すると、画面全体が単色`(18,18,18,255)`のみ（`PIL`のヒストグラム解析で1色のみ、384000ピクセル全てが同一色と確認）で、これまでの31セッション分と全く同じ「メインコンテンツが一切描画されない」症状がそのまま再現した。**つまり「ウィジェットツリーの静的な親子関係（トポロジー）」自体はメインバグの直接原因ではなく、構造が正しくてもバグは再現することが実証された**。

**4. 🔴🎉🔑🎯 一方、第31回セッションが実機の稼働中プロセスに対して行った「動的な`remove_widget`→`add_widget`による付け替え」というワークアラウンド手順は、無改造の元バイナリ上で本セッションでも独立に再現に成功した（2回目の独立確認）**：
無改造の`race_capture.orig`（`~/repack_4-4-2/`に保存済みのコピー）を`LD_PRELOAD=frametrace16.so`で起動し、`rc_trigger_pyexec`経由で「`box_layout.remove_widget(sm)`→`sm.size_hint=(1,1)`→`sm.pos=(0,0)`→`relative_layout.add_widget(sm)`」という第31回セッションと全く同じ操作を実行した。操作直後の`Window.screenshot()`は単色のままだったが、**操作から約1000スワップ分（数秒程度）待ってから再度スクリーンショットを撮ったところ、公式RaceCapture AppのSetupView（"Welcome / Device / Connection / Preset / Tracks / Podium / Cell Service / Tour"タブ・案内文・レーシングカー画像・EXIT/NEXTボタン）が完璧に描画されていることを確認した**（ファイルサイズ149,255バイト vs 単色時の2,608バイトという明確な差でも裏付けられる）。**「即座に確認すると直っていないように見えるが、数百〜千スワップ程度の猶予を置けば描画される」という重要なタイミング上の注意点も本セッションで再確認した**（第31回セッション点12の知見と一致）。

**5. 🔴🎯🔑 決定的な新発見：このワークアラウンドは極めて脆弱（fragile）であり、`ScreenManager`が`size_hint=(1,1)`（`RelativeLayout`全域と完全に同一サイズ）のまま一切触れられない状態を維持する場合のみ有効。その後に加えるいかなる変更（`ScreenManager`自身のサイズ変更ですら）も、再び描画消失を引き起こす**：
上記4で「直った」状態を確認した直後、`ToolbarView`との共存のため`ScreenManager`のサイズを`(1,1)`から`(1,None)`+`height=440`（`ToolbarView`の高さ40pxを除いた領域）へ**通常のPythonプロパティ代入のみで**（KVの反応的バインディングは使わず、`rl`と`tb`を直接参照する値を一度だけ計算して代入）変更したところ、**再び画面全体が単色`(18,18,18,255)`のみに戻り、メインコンテンツは消失した**（スクリーンショット8,296バイト、単色パターンと一致）。さらに、`ScreenManager`自体には一切触れず、**兄弟ウィジェットである`ToolbarView`だけを同様に`box`から`RelativeLayout`直下へ付け替える操作を追加で行っただけでも**、`ScreenManager`のメインコンテンツは再び消失した（8,608バイト）。**最後に、ウィジェットツリー（`parent`/`children`）を一切変更せず、`rl.canvas.remove(box.canvas)`→`rl.canvas.add(box.canvas)`というcanvasレベルのz-order入れ替えのみ（`ScreenManager`のウィジェットツリー上の親子関係やプロパティには無関係のはず）を行った場合でも、同様に`ScreenManager`のメインコンテンツは消失した**（8,326バイト）。**これにより、このワークアラウンドは「特定のウィジェットを恒久的に正しい状態へ『登録』する」ものではなく、「`RelativeLayout`のレイアウト/canvas再構築が発生した直後、最後にその再構築のトリガーとなった1つの操作に関連するウィジェットのみが、次の再構築が起きるまでの間だけ」正しく描画される、という極めて一時的（transient）な現象である可能性が高いと判明した**。`ToolbarView`単体を同じ手順で付け替えた場合も（実アイコン・接続状態の緑ドット・デバイス名テキストが正しく描画され、`SetupView`自身のタブとは明確に異なる見た目で確認済み）同様に描画に成功しており、**メカニズム自体はウィジェットの種類に依存しない一般的なものである**ことも確認できた。しかし「`ScreenManager`と`ToolbarView`の両方を同時に、かつ重ならないサイズで、共に正しく描画された状態を維持する」という実用上必要な組み合わせは、本セッションで試した全ての順序・手法（同時操作、順次操作、ウィジェットツリー操作、canvasのみの操作）で達成できなかった。

**6. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：全てのテストプロセス（`race_capture.orig`・`race_capture.patched`の一時起動、いずれも複数回）を終了済み。本番の`/opt/racecapture/race_capture`はMD5ハッシュ`887a219b47b57557951435ee924d0d77`でセッション開始時と完全一致（無改造）、`run_racecapture_rpi.sh -w 1`による標準watchdogフローで正常復旧済み（`LD_PRELOAD`なし、ESP32接続・GPS/テレメトリ・セッション記録とも正常動作を確認、`throttled=0x0`）。生成物：`~/repack_4-4-2/`（`pyinstxtractor_ng.py`・`repack_main_kv.py`・`race_capture.orig`・`race_capture.patched`・`_internal`シンボリックリンク、いずれも次回セッションでも再利用可能。`race_capture.patched`は「静的トポロジー変更のみ」パッチなので効果なしと判明済みだが、リパックパイプライン自体の動作実証サンプルとして有用）。`/tmp/stage*.py`・`/tmp/reparent*.py`等の一連の検証スクリプトは`/tmp`（tmpfs）上のため次回リブートで消滅する想定（重要なものは`~/repack_4-4-2/`等の永続領域に控えを残すことが望ましい、次回セッション冒頭で対応可）。

**次回の最優先候補（優先度順、第32回セッション最終更新）**：
0. **最優先：「`ScreenManager`と`ToolbarView`を同時に正しく描画された状態で共存させる」方法を見つける**。本セッションで試して効果がなかった手法（両者を同時/順次に`remove_widget`+`add_widget`、`ScreenManager`のみ移動して`ToolbarView`を後から別移動、canvasレベルのz-order入れ替えのみ）以外のアプローチを検討する。候補：①`ScreenManager`を`size_hint=(1,1)`のまま一切動かさず、`ToolbarView`側は`RelativeLayout`に頼らず`Window`直下（第21回セッションで確認済みの「`Window`直下は常に正常描画される」領域）に别途オーバーレイとして配置する、②`ScreenManager`の`remove_widget`+`add_widget`操作を、画面上で本当に「最後の」操作にできるよう、逆に`ToolbarView`を先に`RelativeLayout`直下へ配置してから`ScreenManager`を最後に正しいサイズで付け替える（本セッション未試行の順序）、③そもそも「なぜ`RelativeLayout`の再レイアウト直後の1回だけ有効なのか」というGL/ステンシルレベルの根本メカニズムを`apitrace`等で直接解明し、恒久的な修正（例えば`RelativeLayout`のcanvas再構築ロジック自体へのパッチ、または起動時に定期的にこのreparentサイクルを回し続けるタイマーを仕込む等）を設計する。
1. 上記0が解決した場合、実際の恒久修正（`RaceCaptureApp.build()`または`on_start()`への、起動直後1回だけ実行するreparentコードの追加）を`main.pyc`へ実装する必要があるが、これは今回実証したような「同一/可変長の文字列定数置換」では実現できない（新しいPythonバイトコード命令列を追加する必要がある）。`main.pyc`の`build`/`on_start`メソッドのコードオブジェクトへ新規bytecodeを安全に挿入する方法（完全なPythonコンパイラでの再アセンブル、または`xdis`の逆アセンブル結果を土台にした手動bytecode合成）を確立する必要があり、これ自体が次回の技術的ハードルになる。
2. 上記1の代替として、`main.pyc`を直接パッチするのではなく、`sitecustomize.py`等のPyInstaller外部フック機構でコード注入できないか改めて調査する価値がある（本セッションでは「PyInstallerのrthookは`.spec`ビルド時に固定されたリストのためCArchiveへの追加だけでは実行されない」という結論に達したが、他の注入経路（`PYTHONSTARTUP`、`.pth`ファイル、`LD_PRELOAD`を`run_racecapture_rpi.sh`へ恒久的に組み込む等）は未検討）。特に**`LD_PRELOAD`を`run_racecapture_rpi.sh`起動スクリプトへ恒久的に組み込み、`frametrace16.so`の`rc_trigger_pyexec`相当の仕組み（起動後1回だけ自動的にreparentコードを実行する軽量版）を常駐させる案は、`main.pyc`のバイトコード改造が一切不要で、`run_racecapture_rpi.sh`という通常の設定ファイル同然の箇所を書き換えるだけで済むため、最も低リスクかつ現実的な実装経路である可能性が高い**（次回最優先で検討する価値あり）。
3. 第31回セッションまでの候補（上記「次回の最優先候補（優先度順、第31回セッション最終更新）」の1〜5）は、0が解決するまで据え置き。

---

**（ユーザーが3時間就寝、その間の自律調査を依頼。第33回セッション）**

**1. 🔴🚨🔑 候補0の①②（`ToolbarView`を`Window`直下へオーバーレイ配置し`ScreenManager`を`RelativeLayout`側の最終操作として温存する案）を、順序を入れ替えた2パターンで検証したが、いずれも失敗し、「`RelativeLayout`部分木への最後の操作だけが得をする」という第32回セッションの仮説が、より厳密には「その時点でアプリ全体を通じて生涯最初の1回だけ得をする」という、さらに厳しい制約であることを実証した**：
   - **パターンA（`ToolbarView`移動→`ScreenManager`移動の順、単一exec内で連続実行）**：`box_layout.remove_widget(toolbar)`→`Window.add_widget(toolbar)`→`box_layout.remove_widget(sm)`→`relative_layout.add_widget(sm)`を1回のpyexecで連続実行。`ToolbarView`は`Window`直下で完璧に描画された（`RaceCapture/Pr...32-c3-proto-build`の文字・アイコン4つを実際にスクリーンショットで確認）が、`ScreenManager`側は描画されなかった。
   - **パターンB（`ScreenManager`移動→`ToolbarView`移動の順、別々のpyexecトリガーで数秒の間隔を空けて実行）**：まず`ScreenManager`のみを`box_layout`から`relative_layout`へ移動（単独操作）した直後にスクリーンショットで完璧な描画（149,187バイト、SetupViewの案内文・レーシングカー画像とも正常）を確認。**続けて`ToolbarView`を`box_layout`から`Window`直下へ移動する操作（`ScreenManager`自体には一切触れない、`relative_layout`への直接の`add_widget`でもない、`box_layout`という既に空になっていた別のコンテナを触るだけの操作）を追加しただけで、直前まで完璧に描画されていた`ScreenManager`側のコンテンツが再び完全に消失した**（8,622バイト、単色パターンに一致）。
   - **意味合い**：パターンBは「`ScreenManager`への操作を文字通り最後にする」という第32回セッションの仮説①②を最も素直な形で実装したものだが失敗した。これにより、「`RelativeLayout`部分木の中で最後に触られた1つが勝つ」という理解も不十分であり、**「`box_layout`という、その時点では`ScreenManager`と全く無関係な別コンテナを触っただけ」でも巻き添えで壊れる**ことが確定した。

**2. 🔴🎉🔑🎯 上記1を受けて「そもそも“最後の操作”という考え方自体が誤りで、実際には“アプリ生涯で最初の1回”しか効かないのでは」という、より厳しい仮説を検証するため、`Clock.schedule_interval`で1秒おきに全く同一の`relative_layout.remove_widget(sm); relative_layout.add_widget(sm)`を反復実行する永続リフレッシュタイマーを実装し検証したところ、この仮説が正しいことが確定した**：
   起動直後に`ScreenManager`を`relative_layout`へ一度だけ移動（1回目の実行）した後、1秒間隔のタイマーで同一の`remove_widget`+`add_widget`を46回以上反復させ、タイマー発火直後（0.数秒以内）のタイミングでスクリーンショットを取得したが、**結果は一貫して単色（7,706バイト）で、一度も描画状態には戻らなかった**。これにより、「`RelativeLayout`への`add_widget`」という操作自体を何度繰り返しても、2回目以降は一切効果がない（＝救済されるのは文字通りアプリのプロセス生涯で最初の1回限りの、二度と再現しない一過性のイベントである）ことが確定した。この結果は第32回セッションが未検証のまま候補として残していた「起動時に定期的にreparentサイクルを回し続けるタイマー」というワークアラウンド案（次回候補2の一部）を実証的に完全否定するものである。

**3. 🔴🎉🎯 一方、ウィジェットツリー・canvasを一切変更しない操作（プロパティアニメーションのみ）は、既に成立している「救済」状態を壊さないことを実証した。`NavigationDrawer`の正規`nav.open()`メソッド呼び出し（ドロワーの開閉アニメーション、第29回セッションでは`ScreenManager`が未修正の状態でしか試していなかった組み合わせ）を、`ScreenManager`移動が成功した直後に実行したところ、ドロワーが開閉して自動的に閉じるまでの間（`state`が`pre_open`→おそらく`open`→`close`と遷移する間）を通じて、`SetupView`のコンテンツ（案内文・レーシングカー画像・EXIT/NEXTボタン）は一度も消えず描画され続けた**（3回のスクリーンショットいずれも149,187〜152,069バイトの範囲で安定）。これにより、実運用で頻繁に発生するドロワーの開閉操作自体は、この救済状態を破壊しないことが確認できた（実用上重要な安定性の裏付け）。

**4. 🔴🎉🔑🎯🎯 最大の新発見：`ScreenManager`移動が成功した状態のまま`app.switchMainView('dash')`で画面を切り替えたところ、これまで29セッション以上にわたり完全な黒一色としてしか観測されたことのなかったDASHBOARD画面で、初めて実質的なコンテンツ（歯車アイコン・ロックアイコン・`TripleGaugeBar`の3枚の"No data"ゲージカード・左右ナビゲーション矢印）が描画されることを実写のスクリーンショットで確認した**：
   `switchMainView('dash')`実行後のスクリーンショットで、画面右上の歯車＋赤い鍵アイコン、画面下部の緑・オレンジ・青の角丸枠で縁取られた3枚の"No data"ゲージカード（各カードの下に小さく`CurrentLap`/`SessionTime`等のラベルも確認）、左右の三角矢印ボタンが、いずれも正しい色・位置で描画されていた。一方、画面中央の大きな領域（`AnalysisCarousel`が占める部分）は依然として完全な黒のままだった。
   ウィジェットツリーを直接照会したところ、この黒い領域には`AnalysisCarousel`（`kivy.uix.carousel.Carousel`）が実在し、その直下に**`RelativeLayout`インスタンスが2つ**（Carousel自身がスライド用に内部生成する、標準Kivyの実装パターン）、いずれも画面内の妥当な座標（`pos=[0, 75.0]`/`pos=[-800, 75.0]`、`size=[800, 405.0]`）を持つ子として存在していることを確認した。
   **これにより、「`ScreenManager`と`ToolbarView`のどちらが勝つか」という第32回セッションの二択の構図は誤りだったと判明した。実際には`TripleGaugeBar`（`kivy.uix.scatter.Scatter`のサブクラス）や歯車・鍵アイコン（`RelativeLayout`を経由しない通常のWidget/Image系）は最初から問題なく描画されており、"救済"を必要とするのは常に「`RelativeLayout`（またはそのサブクラス）が新しくcanvasに組み込まれた（かつ、生涯最初の1回の救済イベントの受益者になれなかった）瞬間」に限られる**、という、これまでで最も的を絞った統一仮説に到達した。`AnalysisCarousel`内の2つの`RelativeLayout`は、`dash`画面が`switchMainView`により（アプリ生涯で最初の`ScreenManager`移動より後に）構築されたため、この一度きりの救済に間に合わなかったものと解釈できる。

**5. ⚠️ 上記4を踏まえ、`AnalysisCarousel`自身のページ（`RelativeLayout`×2）に同じ`remove_widget`+`add_widget`トリックを適用しようと試みたが、`Carousel`ウィジェット独自の`add_widget`実装（`slides`プロパティ経由の内部管理、`on_slides`イベントで`_insert_visible_slides()`が自動的に再実行される）と衝突し、`WidgetException: ...it already has a parent`で失敗した**。`Carousel`は生の`children`リストではなく`slides`プロパティを介して独自にページを管理しているため、汎用ウィジェットに対して確立してきた素朴な`remove_widget`/`add_widget`パターンはそのまま適用できないと判明した。`car.slides`プロパティを直接操作する（`slides`リストへの再代入等）か、`Carousel`のソース（`kivy/uix/carousel.py`の`_insert_visible_slides`/`_curtain`実装）を読んでその内部状態遷移に沿った形で「remove→re-add相当」を行う必要があり、次回への持ち越し課題となった。

**6. 🎯 中間総括：「`ScreenManager`と`ToolbarView`の共存」という第32回セッション末尾の問いは、実際には「両者は競合しない（`ToolbarView`は元々問題なく描画される部類のウィジェットである）」という形で解消されたが、より本質的な制約（`RelativeLayout`系ウィジェットの救済はアプリ生涯で1回限りで、かつ後から生成される`RelativeLayout`（`Carousel`のページ等）には及ばない）が新たに確定し、「1箇所を直しても他が直せない」問題の射程が`ScreenManager`本体だけでなく、その配下で新しく作られる`RelativeLayout`全てに及ぶことが判明した。

**7. ⚠️ 上記6を受け、`AnalysisCarousel`固有の`add_widget`/`remove_widget`オーバーライド（`slides`プロパティ経由の内部管理）を迂回し、内部スライドコンテナ（`car._prev`/`_current`/`_next`）に対して基底クラス`Widget.add_widget`/`remove_widget`を直接呼ぶ手法で再挑戦したところ、例外なく実行には成功したが、`Carousel`のページも救済されず、かつ直前まで正常表示されていた`TripleGaugeBar`のゲージカード・アイコン類まで巻き添えで再び全て消失した**。これにより、「救済は特定のウィジェットへ"移し替え"できるものではなく、アプリ生涯で最初の1回だけ発生し、二度と発生しない使い切りのイベントである」という仮説がさらに強く裏付けられた（2回目の操作は対象が何であれ常に無駄骨に終わり、かつ既存の救済状態を巻き添えで破壊する）。

**8. 🔴 上記7を受け、GLレベルでこの"一度きりの救済"の正体を探るため、`frametrace16.c`を拡張した`frametrace17.c`（`glGenTextures`/`glDeleteTextures`/`glGenFramebuffers`/`glDeleteFramebuffers`/`glGenRenderbuffers`/`glDeleteRenderbuffers`の6関数を新規フック、実機で再コンパイル済み）で、`ScreenManager`移動（成功する操作）の前後でGPUリソース確保イベントに特徴的な差分がないか調査したが、有意な相関は見つからなかった**：`glGenFramebuffers`・`glGenRenderbuffers`・`glDeleteFramebuffers`・`glDeleteRenderbuffers`はアプリ起動から検証終了まで一貫して**呼び出し回数0**（第29回セッション点6の「FBOバインドは常に0=デフォルトフレームバッファ」という知見と整合）。`glGenTextures`/`glDeleteTextures`はフォントグリフキャッシュ等により起動直後から常時継続的に発生している（`ScreenManager`移動操作の前後で1個ずつ増分する程度の通常のペースで、操作に紐づく明確なスパイクや一括生成/破棄イベントは観測されなかった）。**これにより、「救済」はGL API呼び出しレベルで観測可能な新規リソース確保とは無関係で、Kivy側のcanvas命令グラフ構築、またはGL APIの外側（Mesa VC4ドライバ内部のタイラー状態等）で起きている現象である可能性が高いと確定した**。

**9. 実機（`rc-dash-3b`）の状態（セッション終了時点）**：全ての検証プロセス（`LD_PRELOAD=frametrace16.so`/`frametrace17.so`で起動した複数の一時インスタンス）は`sudo kill -9`で終了済み。標準の`run_racecapture_rpi.sh -w 1`（`LD_PRELOAD`なし、watchdog付き）で本番相当のクリーンな状態へ復旧し、`throttled=0x0`（電圧健全）・`dmesg`上のGPUリセット0件を確認済み。ハードウェアへの恒久的な変更なし。接続先IPは今回`192.168.137.83`（前回セッションから不変）。生成物：`~/isolate_tests_4-4-2/`に`s33_approach1.py`・`s33_step_sm_only.py`・`s33_step_toolbar_to_window.py`・`s33_perpetual_refresh.py`・`s33_step_nav_open.py`・`s33_nav_state.py`・`s33_switch_dash.py`・`s33_list_screens.py`・`s33_inspect_carousel.py`・`s33_fix_carousel.py`（Carousel独自APIとの衝突で例外、失敗記録として保存）・`s33_fix_carousel2.py`（基底`Widget`メソッド直接呼び出し版、実行は成功したが救済されず）を追加保存済み。`~/frametrace16.c`/`.so`（無改造のまま再利用）に加え、`~/frametrace17.c`/`.so`（GPUリソース生成フック追加版、テクスチャ/FBO/レンダーバッファのgen/delete計6関数）を新規保存、次回も再利用可能。

**10. ⚠️🔑 セッション最終盤、`switchMainView('dash')`直後に`ScreenManager`移動を行い数秒待ってから`AnalysisCarousel`のコンテナ（`car.children`を直接、`Widget.add_widget`/`remove_widget`基底メソッドで）を追加で再接続する一連の操作を試したところ、1回だけチャンネル一覧（RPM/Speed/WaterTemp等、約24項目のラベルグリッド）とゲージカードが完璧に描画される結果が得られたが、直後に全く同一の手順・同等のタイミングで再現を試みたところ再現せず、単独の`AnalysisCarousel`のみを最初の一度きりの操作として触れる制御実験でも変化なし（黒画面のまま、ファイルサイズも操作前後で完全に同一の2908バイト）だった**。これにより、この1回限りの「成功」は手順の因果的な再現性を持たず、本セッションが確立した「アプリ生涯で最初の1回だけ効く」という統一仮説（候補6〜8）とは別の、非決定的な現象（第25回セッションで確立済みの「スワップ継続/停止の非決定性」等と同系統の可能性）によるものだった可能性が高いと判断する。**この観測自体は今後の調査で再訪する価値があるが、現時点では再現条件が不明な単発のアノマリーとして記録するにとどめ、確立した手法としては採用しない。**

**11. 🆕 セッション最終盤、Kivy本家ソース（GitHub、`kivy/graphics/instructions.pyx`・`kivy/core/window/__init__.py`・`kivy/graphics/context.pyx`、いずれもバンドル版と同じ2.3.1タグ）をWeb経由で読み込み、"一度きりの救済"を説明しうるKivy内部の類似パターンを調査したが、いずれも直接の原因ではないか実用上使えないと判明した**：
   - **`_need_reset_gl`（`instructions.pyx`）**：`RenderContext.apply()`は、モジュールグローバルな`cdef int _need_reset_gl = 1`が真の間だけ`reset_gl_context()`（`glEnable(GL_BLEND)`等のGL状態初期化）を実行し、実行後は`_need_reset_gl = 0`となり**プロセスの残り生涯、二度と実行されない**という、まさに探していた「一度きり・グローバル・二度と戻らない」パターンがKivy自身の内部に実在することを確認できた。ただしこの実行タイミングは（グローバルな単一`RenderContext`の）**アプリ起動直後の最初のフレームで確実に消費される**ため、数秒〜数十秒後に行う本セッションの遅延ウィジェット操作のタイミングとは噛み合わず、直接の原因ではないと判断した。
   - **`RenderContext.reload()`**：`_need_reset_gl`を無視して無条件に`reset_gl_context()`を呼ぶメソッドが存在するが、`cdef void reload(self)`宣言のため**Pythonからは呼び出し不可**（`Window.render_context.reload()`は`AttributeError`で実証済み）。
   - **`kivy.graphics.context.get_context().reload()`**：`Context`クラスの`def reload(self)`はPythonから呼び出し可能で、登録済み全`Canvas`・全テクスチャ/VBO/Shaderを再読み込みする、より広範なコンテキストロスト復旧用の機構だが、**実機で実行したところ、動的生成されたインラインテクスチャ（`Exception: Unknown <__inline__> type, no loader found`、ファイルパスを持たないプログラム生成テクスチャの再読み込みに失敗）で例外が発生し、テクスチャ再読み込みの途中で処理が止まることを確認した**。プロセスはクラッシュせず継続動作したが、画面の描画状態にも変化はなかった（2,608バイトのまま、前後で完全に同一）。この経路はアプリ改造（インラインテクスチャの扱いへのパッチ等）なしでは実用にならないと判明した。

**12. 🆕🔑 セッション終了後、ユーザーが起床し実機モニターを直接目視確認した結果、本セッションのスクリーンショットベースの結論を裏付ける独立した確認が得られた。加えて、Raw Dataモードで「枠は表示されるが数値は表示されない」という、本セッションでは未検証だった新しい症状パターンが判明した**：
   - ユーザーの目視で、Home画面の画像・DASHBOARD画面周辺の枠・歯車アイコンが実際に表示されていることを確認（本セッションのスクリーンショット調査結果と整合）。
   - **Raw Data表示モードでは、データ項目の枠（レイアウト構造）自体は表示される一方、RaceCaptureからの実際の数値は表示されないという新しい観察を得た**。これは本セッションで確認した「歯車・ロックアイコン・ゲージカードの"No data"ラベルは表示されるがAnalysisCarouselの中身は非表示」というパターンとは微妙に異なる（"No data"は文字自体が表示されているのに対し、Raw Dataモードでは数値そのものが非表示になっている）。次回、Raw Data画面のウィジェット構造を調査し、これが「RelativeLayout限定」という統一仮説（候補6〜8）で説明できるか、あるいは数値ラベル自体の別の描画経路（動的テキスト更新特有の問題等）が関与しているかを切り分ける価値がある。

**次回の最優先候補（優先度順、第34回セッション最終更新）**：
0. **最優先：候補14で確立した「settlingモデル」（`ScreenManager`移動→60〜90秒完全放置→安定描画）を土台に、`apitrace`で60〜90秒間の長時間GLコールトレースを取得し、settling期間中に何が起きているか（`Carousel`の子孫`RelativeLayout`がいつ・どう構築されるか、`PushMatrix`/`Translate`/`PopMatrix`に対応する`glUniformMatrix4fv`等のGLコールがsettling完了の前後でどう変化するか）を直接観察する**。これまでのGLコールレベル調査は全て「操作直後」のスナップショットに限られており、settling期間全体を通したトレースは未取得。
1. 🆕 `ToolbarView`についても`ScreenManager`とは別に「`box_layout`から`relative_layout`または`Window`直下へ移動→他に触れず60〜90秒放置」という同じsettlingパターン単独で試し、`ToolbarView`単体なら安定描画するか確認する（候補14の反証実験は`ScreenManager`のsettling完了"前"に`ToolbarView`を触ったケースであり、`ScreenManager`側を一切操作せず`ToolbarView`側だけを独立にsettleさせる、という順序は未検証）。もし両者を「別々のタイミングで」settleさせれば共存できるなら、恒久修正の設計（起動時に`ScreenManager`→(60秒待つ的な処理は不要、単に)通常のアプリ起動シーケンスの中で`ToolbarView`と`ScreenManager`を時間差で"タッチ"する）に直結する重要な手がかりになる。
2. `Carousel.slides`プロパティへの直接代入や、`AnalysisCarousel`のページ自体を`RelativeLayout`を使わない代替コンテナへ差し替える改造は、候補14により「settlingさせれば`Carousel`は自然に直る」と判明したため優先度を下げてよい（もはや不要な可能性が高い）。
3. Mesa GitLabへの`glClear`部分マスクバグ報告（第31回セッションから持ち越し、`~/apitrace_4-4-2/dash_session31.trace`が証拠として利用可能）は引き続き優先度中で残置。
4. 恒久適用の実装経路（`main.pyc`バイトコード注入 or `LD_PRELOAD`常駐）は、候補0・1でsettlingの正体とToolbarViewの扱いが判明してから設計する。案として、`run_racecapture_rpi.sh`起動時にLD_PRELOADされる軽量な常駐フックが「`ScreenManager`移動→90秒待機→（`ToolbarView`も安定分離できるなら）`ToolbarView`移動→90秒待機」のような一度きりの起動シーケンスを自動実行する、という設計が現実的な候補になる。
5. ~~候補12でユーザーが目視確認した「Raw Dataモードで枠は出るが数値が出ない」現象のウィジェット構造調査~~ → **クローズ。原因はGPU描画バグではなく、公式アプリ自体のRCPサンプル送信スレッド再起動ロジックのバグ（`DataBusPump._start_polling_telemetry()`の`if self._sample_thread:`が生存確認ではなく存在チェックになっている）と判明・確認済み。詳細は`task_phase1_breakdown.md`の1-8参照。この件はPhase4-4-2の描画バグとは無関係な別問題として切り分け完了。**
6. ~~候補10で観測した「1回だけ再現した成功」の再現条件の統計的探索~~ → **クローズ。候補14で確定的に再現条件（settling）を特定できたため、統計的アプローチは不要になった。**

**13. 🆕🔑 Kivy本家ソース（GitHub、`kivy/uix/relativelayout.py`・`kivy/data/style.kv`、いずれも2.3.1タグ）を確認し、第32回セッションの推測（`RelativeLayout`がcanvas.beforeで`PushMatrix`+`Translate`を行う）の正確な出典を特定した。ただし推測していた「一度きり」現象への直接的な説明にはならないと判明した**：`relativelayout.py`自体のPython `__init__`にはcanvas操作が一切無く（`_apply_transform`はタッチ座標変換専用でGL描画には無関係）、実際の`PushMatrix`/`Translate(xy=self.pos)`/`PopMatrix`は**Kivy本体が起動時に一度だけ読み込む共通KVスタイル定義`kivy/data/style.kv`の`<RelativeLayout>:`ルール**として定義されており、Kivyの`Builder`により**全ての`RelativeLayout`インスタンスに対して、生成タイミング（起動時か実行時か）に関わらず完全に同一の手順で一律適用される**。この適用機構自体に「最初のインスタンスだけ特別」という余地は無いため、候補0（`RelativeLayout`固有のcanvas再構築ロジックを読む）はこの3命令（PushMatrix/Translate/PopMatrix）自体の"特別扱い"を疑う方向としては手詰まりで、**焦点はこの3命令がGPU側で実際にコンパイル・実行される際のタイミング・GL状態（Mesa VC4ドライバのタイル管理・行列スタックの内部実装）へ絞り込まれた**。次回、`apitrace`等で「救済に成功した最初のRelativeLayout」と「救済されなかった後発のRelativeLayout」の、この3命令に対応する実際のGLコール列（`glUniformMatrix4fv`等）を直接比較することが、GLレベル調査の最も具体的な次の一歩となる。

---

**（同日、ユーザーがPhase1-8のファームウェア書き込み作業に立ち会った流れで、Phase4-4-2の続きにも波及。第34回セッション相当）**

**14. 🔴🎉🔑🎯🎯 決定的な前進：候補1（「1回だけ再現した成功」の再現条件の探索）に着手し、ユーザー自身が実機モニターを目視して「本物の直った画面」を複数回にわたり直接確認した。再現条件は「`ScreenManager`移動後、他に一切触れず60〜90秒程度放置する」ことであり、これにより`AnalysisCarousel`の中身（チャンネル一覧・複数種類のゲージ画面）まで自然に正常描画されることが、独立した2回の試行で確定的に再現した**：
   - **試行1**：`switchMainView('dash')`→`ScreenManager`移動（`box_layout.remove_widget(sm)`→`relative_layout.add_widget(sm)`のみ、他は一切触れない）→**75秒放置**→スクリーンショット（50,655バイト）で、チャンネル一覧（RPM/Speed/WaterTemp等24項目）・ラベル・ゲージカード・歯車/鍵アイコンが完璧に描画されていることを確認。ユーザーもこの瞬間、物理モニターで同一内容を直接目撃したと証言（本セッション最大の収穫）。20秒追加放置後も劣化せず安定継続を確認。
   - **試行2（独立再現）**：プロセスを再起動し、同一手順（`switchMainView`→`ScreenManager`移動→**90秒放置**、今度は一切の追加操作なし）で実施したところ、今度は`AnalysisCarousel`が自然に別ページ（PredTime/BestLap/CurrentLap/LapTime/SessionTimeの色分けされたゲージ、65,097〜66,522バイト）へ切り替わった状態で完璧に描画されることを再確認した。ユーザーも物理モニターでこの状態を確認済み。
   - **反証実験（失敗、重要な追加知見）**：試行1と2の間に行った1回の試行では、`ScreenManager`移動の直後（3〜10秒以内）に他の操作（`SerialConnection.read_line`のライブパッチ、`DataBusPump`のスレッド状態確認・修正、`Clock.schedule_interval`ウォッチドッグのインストールなど、**いずれもウィジェットツリー/canvasには一切触れない純粋なPython操作**）を複数回連続して実行したところ、その後60秒・さらに30秒（計90秒）放置しても一切回復せず黒画面のまま固定された。**「一度壊れると待っても二度と回復しない」という第33回セッションまでの知見と完全に整合する一方、`ScreenManager`移動後の"未確定・settling中"の数十秒間は、canvasに直接触れない操作であってもこのタイミングに割り込むと自然な描画完了プロセスを阻害しうる（あるいは操作のたびにレンダースレッドで同期的に実行されるPyRun_SimpleString自体がフレームタイミングに影響する）ことが新たに示唆された**。
   - **成功パターンの確立**：`ScreenManager`移動 →（何もせず60〜90秒放置）→ スクリーンショット等で安定描画を確認 →（確認後であれば）`DataBusPump`のサンプルスレッド修正等の純粋なPython操作を追加しても、その後は描画状態を破壊しないことも確認した（試行1・2とも、安定描画確認後に1-8のデータ受信修正を追加適用し、実際の数値が表示され続けることまで確認済み。ユーザーが目撃した完成形のスクリーンショットは本ファイル冒頭の会話に添付済み）。
   - **未解決のまま残る制約**：この状態でも`ToolbarView`（画面上部の状態バー）・`NavigationDrawer`を開くボタン（`ToolbarView`内にあるため連動して使用不可）は直っていない。試行として`ToolbarView`も同様に`box_layout`から`relative_layout`へ移動してみたが、これは`ScreenManager`移動後の新たな「触る」操作にあたるため、`ToolbarView`自体は描画されるようになった（ただし`pos`が意図した位置(画面上部)ではなく`[0,0]`(画面下部)になった）一方、`ScreenManager`側の描画は即座に黒画面へ戻った。**「同時に2つ以上を直した状態を維持することはできない」という制約は本質的に変わっていない。**

**15. 🎯 総括・次回への申し送り**：「アプリ生涯で最初の1回だけ」という第33回セッションの理解は不正確だった。より正確には**「`ScreenManager`移動という単一の操作の後、他に一切妨害されない数十秒（60〜90秒が目安）の"settling"期間を経ることで、Kivyが内部的に構築する子孫ウィジェット（`Carousel`のページ等）まで含めて自然に正しく描画されるようになる。ただし、この期間中・期間後を問わず、ウィジェットツリーやcanvasに影響しうる新たな操作（settling期間中は純粋なPython操作すら含む）が入ると、その時点で不可逆的に黒画面へ戻り、二度と回復しない」**というモデルがより正確である。この「settling」の正体（Kivyのcanvas再構築が完了するまでの時間なのか、GPU/ドライバ側の何らかの非同期処理が完了するまでの時間なのか）は依然として未解明。次回はこのモデルを土台に、①`ToolbarView`側も同様に「移動→settling待ち」を単独で試し安定描画するか確認する（`ScreenManager`とは別々にsettleさせられるか）、②settling中に何が起きているかをGLコールトレース（`apitrace`、60〜90秒間の長時間トレース）で直接観察する、の2方向を優先すべきである。

---

**（同日、ユーザー立ち会いなしで作業を継続。第35回セッション相当）**

**16. 🔴🎯🔑 決定的な知見：候補1（`ToolbarView`単独settling）を検証した結果、「`ScreenManager`のsettling救済成功後に`ToolbarView`を移動すると、90秒間放置しても`ScreenManager`側の描画は一切回復しない」ことが確定した**：
   前回セッション終了時点から継続して稼働していたプロセス（`ScreenManager`移動→settling済み、DASHBOARD画面のPredTime/BestLap/CurrentLap/LapTime/SessionTimeゲージが実データ付きで完璧に描画された安定状態。加えてPhase1-8のデータ受信パッチ（`s34_fix_sample_thread.py`等）も適用済みで、その後もこの安定描画状態がswap数にして1746から10795まで（アイドル状態で長時間）破壊されず継続することも確認できた）に対し、`s35_rescue_toolbar.py`（`ToolbarView`を`box_layout`から`relative_layout`直下へ`remove_widget`+`add_widget`で移動、`pos`/`size`は移動前の値を保持して再代入）を実行し、その後**一切操作を加えず90秒間放置**してからスクリーンショットを取得した。結果は、`ToolbarView`自体は正しく描画された（`RaceCapture/Pr...32-c3-proto-build`の文字・アイコン4つ、ただし`pos`は意図した画面上部ではなく`[0,0]`＝画面下部になる問題は未解決のまま）一方、**直前まで完璧に描画されていた`ScreenManager`側のコンテンツは完全に消失し、90秒待っても一切回復しなかった**（画面はほぼ全面黒、ファイルサイズ8,650バイトで単色に近い）。
   **これにより、「`ScreenManager`の救済成立後に新たな`remove_widget`/`add_widget`操作が入ると、その時点で不可逆的に破壊が確定し、settling期間を与えても回復しない」ことが確定した。「settling」は"操作の悪影響を打ち消す猶予期間"ではなく、"操作をトリガーとした一過性の再構築プロセスが完了するまでの時間"であり、既に破壊が起きた後にいくら待っても意味がないという理解がより正確になった。** 次回最優先候補1（「両者を別々のタイミングでsettleさせれば共存できるか」）はこの順序（`ScreenManager`→`ToolbarView`）では否定されたが、逆順（`ToolbarView`を先に移動しsettling→その後`ScreenManager`を移動しsettling）は本セッションでは未検証のまま残っている。

**18. 🔴🎯🔑 決定的な知見：候補0（逆順パターン）を検証した結果、順序を`ToolbarView`→`ScreenManager`に入れ替えても共存できないことが確定した。ただし単純な対称形ではなく、`ToolbarView`側に非対称な手がかりが見つかった**：
   プロセスを再起動（watchdog経由、`LD_PRELOAD=frametrace16.so`は環境変数継承で自動的に維持されることを確認済み）し、`switchMainView('dash')`後、まず`ToolbarView`のみを`box_layout`から`relative_layout`直下へ移動（`box_layout.children[0]`が`ScreenManager`である初期状態では候補16の`s35_rescue_toolbar.py`は誤って`ScreenManager`を掴んでしまうバグがあると判明したため、クラス名で`ToolbarView`を明示的に選別する新スクリプト`s35_move_toolbar_only.py`を作成して使用）、`pos=(0, 440.0)`（画面上部、意図した正しい位置）で移動。**90秒放置後、`ToolbarView`は正しい位置に安定描画された**（候補16で見られた`pos=[0,0]`問題は、box_layout内での初期位置がまだ正しく設定されていた今回は発生しなかった）。続けて`ScreenManager`を`box_layout`から`relative_layout`へ移動し、さらに90秒放置したが、**`ScreenManager`側のコンテンツは一切描画されず（画面は`ToolbarView`のみが表示された状態で固定、ファイルサイズ8,296バイトで`ToolbarView`移動直後と完全に同一）、settling待機は無意味だった**。
   **これにより「同時に2つ以上のRelativeLayout系ウィジェットを共存させることはできない」という制約は、順序を入れ替えても変わらないことが確定した。** 一方で、候補16（`ScreenManager`→`ToolbarView`の順）では後着の`ToolbarView`が救済され先着の`ScreenManager`が破壊されたのに対し、今回（`ToolbarView`→`ScreenManager`の順）では後着の`ScreenManager`が救済されず先着の`ToolbarView`は破壊されなかった、という非対称な結果が出た。これは「後から`relative_layout`へ`add_widget`された方が常に勝つ」という単純な規則ではなく、**「`ToolbarView`はそもそも救済（settling）を必要としない部類のウィジェットであり（第33回セッション点3・6の分類と整合）、`relative_layout`内に存在し続けること自体は他の操作の影響を受けない。真に脆弱で"最後の`add_widget`操作"に依存するのは`ScreenManager`（`RelativeLayout`を内包する側）だけである」という、より正確な統一理論と整合する結果である。**

**20. 🔴🎉🔑🎯🎯🎯 恒久修正を実装・本番組み込みし、動作確認まで完了した。Phase4-4-2のメインコンテンツ非描画バグは、ユーザー操作なしで自動的に回避されるようになった**：
   候補0（`ScreenManager`のみ救済する恒久修正）を実装。新規Cライブラリ`scmove_persist.c`（`eglSwapBuffers`のみをフックする最小構成。`frametrace16.c`同様`dlsym`/`eglGetProcAddress`の両方でシンボル差し替えに対応）を作成し、**「最初の`eglSwapBuffers`呼び出しから30秒経過した最初のフレームで、`PyGILState_Ensure`+`PyRun_SimpleString`経由で`ScreenManager`を`box_layout`から`relative_layout`へ`remove_widget`/`add_widget`し、以降は`triggered`フラグにより二度と何もしない」という処理を実装した。検証用にスクリーンショットトリガーのみ追加した`scmove_persist_debug.c`でまず動作確認し、新規プロセスで**人手を介さず**SetupView（Welcomeタブ、タブ・案内文・レーシングカー画像・ボタン全て）が完璧に描画されることを確認した（149,907バイト）。
   続けて本番の`/opt/racecapture/run_racecapture_rpi.sh`（`sudo cp`でrootに配置されたファイル、事前に`/home/ntakao/run_racecapture_rpi.sh.bak_4-4-2`としてMD5ハッシュ確認済みのバックアップを取得）に`export LD_PRELOAD=/home/ntakao/scmove_persist.so`を追記し、**外部から`LD_PRELOAD`を一切指定せず標準の起動コマンド（`./run_racecapture_rpi.sh -w 1 -- ...`）だけで起動したプロセスでも、環境変数が正しく継承され自動修正が発動することを確認した**（`/proc/<pid>/environ`で確認）。最終確認として一時的に本番パスの`.so`をデバッグ版に差し替えて視覚確認したところ、90秒のsettling後にSetup画面「Device」タブ（"Select your device"、PodiumConnect MK2カード、背景画像、EXIT/NEXTボタン全て）が完璧に描画されていることを確認できた（231,710バイト）。確認後、本番用（スクリーンショット機能なし）の`.so`に戻し、標準の起動コマンドでクリーンな状態に復旧した。
   **これにより、今後は電源投入・アプリ再起動のたびに、開発者の手動操作を一切必要とせず、起動から約30秒後にメインコンテンツ（`ScreenManager`配下、SetupView/DASHBOARD等）が正しく描画されるようになった。** ただし`ToolbarView`（画面上部の状態バー・ハンバーガーメニュー）は依然として非表示のまま（候補18で確認済みの制約、恒久修正では意図的に対象外としている）。

**次回の最優先候補（優先度順、第35回セッション最終更新）**：
0. **本番組み込み後の実運用での安定性を継続確認する。** 実際のドライブ・セッション記録・複数回の電源サイクルを通じて、①毎回確実に30秒後の自動修正が発動するか、②`ScreenManager.current`を切り替える通常のナビゲーション操作（Setup→Dashboard等の画面遷移）がsettling後の描画状態を壊さないか、を確認する。
1. `ToolbarView`を失う代替として、接続状態・ハンバーガーメニュー相当の最小限の情報を`Window`直下へ別途オーバーレイ配置する改造（第32回セッションの案、`ScreenManager`のsettling"前"に済ませ、settling中は一切追加操作をしない前提で再検証する価値はある。ただしQOL向上の位置づけであり、優先度は0より低い）。
2. Mesa GitLabへの`glClear`部分マスクバグ報告（`~/apitrace_4-4-2/dash_session31.trace`が証拠として利用可能）は引き続き優先度低〜中で残置。

**21. 実機（`rc-dash-3b`）の状態（本追記時点）**：本番の`/opt/racecapture/run_racecapture_rpi.sh`は恒久修正組み込み済み（バックアップ`/home/ntakao/run_racecapture_rpi.sh.bak_4-4-2`、本番用ライブラリ本体`/home/ntakao/scmove_persist.so`、ソース`/home/ntakao/scmove_persist.c`、検証用デバッグ版`/home/ntakao/scmove_persist_debug.c`/`.so`はいずれも保存済み・次回セッションでも再利用可能）。標準の起動コマンド（`LD_PRELOAD`明示指定なし）でクリーンに起動し直した状態。`throttled=0x0`（電圧健全）。

---

**（第36回セッション、ユーザーから「4-4-2を続けて」との指示を受けて再開）**

**22. 🔴🎉🔑🎯🎯🎯 上記「残作業①実運用での安定性確認」を実際に検証したところ、初回描画後に`ScreenManager.current`が一度でも変化する（＝通常のナビゲーション操作）と再び黒画面へ戻る、という重大な未発見の制約があることが判明。ユーザーからも「サイドバー・インジケーターランプが出ておらず画面遷移操作ができず実用上不便、直してほしい」と明確な修理依頼を受けた**：
   - `rc-dash-3b`にSSH再接続し（`rc-dash-3b.local`、鍵は`~/.ssh/racecapture_dash_ed25519`）、稼働中の本番プロセスで`LD_PRELOAD=scmove_persist.so`が正しく効いていることをまず確認。逆コンパイル済み`main.pyc`を`pydisasm`で再解析し、`RaceCaptureApp.switchMainView(view_name)`（`main.py`571〜584行目付近）が全ナビゲーション経路（NavigationDrawerのメニュー項目、Home画面のFeatureButtonタイル、アプリ内蔵キーボードショートカット`_on_keyboard`の`a`=analysis/`d`=dash/`s`=config/`p`=preferences/`t`=status、Escapeキーの`on_esc_pressed`→`switchMainView('home')`無条件）が最終的に呼び出す共通の正規APIであることを特定した。内部は`self._main_frame_scr_manager.current = screen.name`（または`switch_to(screen)`）を呼ぶだけのシンプルな実装。
   - `frametrace16.so`（`rc_trigger_pyexec`/`rc_trigger_shot`機構）をLD_PRELOADしたテストインスタンスで、初回のScreenManager救済（`box_layout`→`relative_layout`の`remove_widget`/`add_widget`）後に`app.switchMainView('dash')`を実行したところ、**Home画面のタイルボタンは正常表示されていたにもかかわらず、Dashboard画面への遷移後は再び黒画面（`Window.screenshot()`のファイルサイズが2,600〜3,000バイト程度、単色相当）に戻ることを実機で確認した**。これは本番の恒久修正が「初回描画のみ」にしか有効でないことを意味する、見落とされていた重大な制約。
   - 切り分け実験として、黒画面に戻った状態から改めて`relative_layout.remove_widget(sm); relative_layout.add_widget(sm)`（初回救済と全く同じ操作、ただし`box_layout`は経由せず`relative_layout`上で直接remove/re-add）を実行したところ、**Dashboard画面のゲージ・ラップタイム等のライブデータが完璧に正常描画されることを確認した（`Window.screenshot()`が69,904バイトへ増大）**。同様の再配置操作をHome→Setup（`config`）→Dashboard（`dash`）→Home の一連の遷移で繰り返し適用したところ、毎回例外なく正しく描画されることを確認した。**つまり「救済トリックは使い切りではなく、`ScreenManager.current`が変わるたびに再適用すれば毎回有効」という、第33回セッションで「アプリ生涯で最初の1回だけ」と結論づけていた理解をさらに修正する新知見が得られた**（第34回セッションが覆した「1回だけ」を、今回は「画面遷移時にも当てはまる」という形でさらに一般化）。
   - 上記を踏まえ、`scmove_persist.c`を拡張：初回の`remove_widget`/`add_widget`実行直後に`sm.bind(current=_rc_on_current)`を追加し、`current`プロパティが変化するたび`Clock.schedule_once`で約0.6秒後に同じ`remove_widget`/`add_widget`を自動再実行するようにした（`Clock.unschedule`で連続遷移時の多重スケジュールを防止）。デバッグ版（`rc_trigger_shot`/`rc_trigger_pyexec`付き）でHome→Setup→Dashboard→Homeの一巡を実機検証し、いずれの画面も自動的に正しく描画されることを確認（ログでも`on_current fired`→`scheduled reheal`→`reheal firing`→`reheal done ok`の流れを確認済み）。検証後、本番の`/home/ntakao/scmove_persist.so`をこの拡張版に差し替え（旧版は`scmove_persist.so.bak_session36`としてバックアップ）、標準の起動コマンド（`run_racecapture_rpi.sh -w 1 -- ...`、`LD_PRELOAD`明示指定なし）でクリーンに起動し直した。`run_racecapture_rpi.sh`自体はファイル名を変更していないため編集不要。
   - **副産物として、`ToolbarView`/`NavigationDrawer`が使えなくても、Home画面のFeatureButtonタイル（Dashboard/Analysis/Setupの3つ）とキーボードショートカット（USBキーボード接続時、`a`/`d`/`s`/`p`/`t`+Escape）だけで全画面へのナビゲーションが可能なことが判明した**。ただし車載時（タッチのみ・キーボードなし）を想定すると、Dashboard/Analysis/Setup以外（Preferences/System Status）や、各画面からHomeへの「戻る」導線がタッチだけでは存在しない点は今後の課題として残る（下記次回候補②参照）。

**23. 実機（`rc-dash-3b`）の状態（本追記時点）**：本番の`/opt/racecapture/run_racecapture_rpi.sh`は無変更（ファイル名`scmove_persist.so`のまま拡張版へ差し替えたため）。本番用ライブラリ`/home/ntakao/scmove_persist.so`は画面遷移時の自動再修復バインドを含む新版（バックアップ`/home/ntakao/scmove_persist.so.bak_session36`・`scmove_persist.c.bak_session36`）。検証用生成物：`/home/ntakao/scmove_persist_v2.c`/`.so`（トリガーなしの本番相当版）、`/home/ntakao/scmove_persist_v2_debug.c`/`.so`（`rc_trigger_shot`/`rc_trigger_pyexec`付き検証版）、`/home/ntakao/probe_tree.py`・`switch_dash.py`・`switch_config.py`・`switch_home.py`・`reheal.py`・`debug_bind.py`・`probe2.py`（いずれも次回セッションで再利用可能）。標準の起動コマンドで本番プロセスがクリーンに稼働中、`throttled=0x0`（電圧健全）。解像度設定（`~/.kivy/config.ini`が`800x480`）はユーザーが別作業で意図的に変更したものと確認済みのため今回は触れていない。

**次回の最優先候補（優先度順、第36回セッション最終更新）**：
0. ~~本番組み込み後の実運用での安定性を継続確認する~~ → **第36回セッションで検証・恒久修正完了（画面遷移時の自動再修復含む）**。
1. **車載時（タッチのみ・キーボードなし）を見据えたHome画面への「戻る」導線の検討**（優先度中）。各画面（Dashboard/Analysis/Setup等）からHomeへ戻る手段が現状Escapeキー（`on_esc_pressed`）しかなく、キーボード非接続の車載環境では機能しない。案：`Window`直下（`RelativeLayout`を経由しないため常に正常描画される領域）へ「Home」ボタンを1つだけ常設オーバーレイし、タップで`app.switchMainView('home')`を呼ぶ（ScreenManager内部の操作のみで完結し、`NavigationDrawer`/`ToolbarView`には触れないため今回確立した自動再修復の対象内）。
2. `ToolbarView`を失う代替として、接続状態相当の最小限の情報を`Window`直下へ別途オーバーレイ配置する改造（QOL、優先度低）。
3. Mesa GitLabへの`glClear`部分マスクバグ報告（`~/apitrace_4-4-2/dash_session31.trace`が証拠として利用可能）は引き続き優先度低〜中で残置。

---

**（第37回セッション、ユーザーから「サイドバー/ステータスバーのインジケーターは重要な情報なので省略しないでほしい」との指摘を受け、`ToolbarView`代替オーバーレイの優先度を上げて再調査）**

**24. 🔴🎉🔑 `ToolbarView`の"見た目だけ"を`ScreenManager`の描画を一切壊さずに重ね描きする方法を発見・実機実証したが、`Dashboard`画面など一部の複雑な画面では機能しないという新たな制約も判明した**：
   - **手法**：`toolbar.export_as_image()`（KivyがFBO経由でウィジェットをオフスクリーンテクスチャへレンダリングする標準API）を使うと、`ToolbarView`が`RelativeLayout`直下の"敗者"側（本来の意味で非表示）になっている状態でも、**FBO側のレンダリングはこのMesa VC4バグの影響を受けず正しい内容（デバイス名・接続状態の緑ドット・GPS・雲アイコン・メニューアイコン）を取得できる**ことを実機で確認した（`toolbar_export.png`で単体確認済み）。
   - **決定的な発見**：このテクスチャを`Rectangle`インストラクションとして、**新規ウィジェットを追加するのではなく、既に正常描画されている`ScreenManager`自身の`canvas.after`へ直接描き足す**（`with sm.canvas.after: Rectangle(texture=tex, ...)`）と、`ScreenManager`のメインコンテンツと`ToolbarView`のライブ状態表示が**同一画面上に同時に**正常表示されることを実機で確認した（`canvastest.png`、38,065バイト）。これは新規ウィジェットの`add_widget`/`remove_widget`（＝これまで29セッション以上悩まされてきた"最後に触った方が勝つ"競合のトリガー）を一切使わない手法であり、既存の恒久修正（`ScreenManager`のsettling）と共存できる初めての方法。
   - **重要な失敗パターンの特定**：`sm.canvas.after.clear()`を呼ぶと（たとえ空の状態でも）このclear操作自体が新たな"最後に触った"イベントとして扱われ、直後に追加した内容が消えるだけでなく、**1秒間隔で`clear()`を呼び続けると`Exception: Cannot push more than 128 level of stencil (stack overflow)`でアプリがクラッシュする**ことを実機で確認した（原因は未特定だが`export_as_image()`のFBO内部処理か`clear()`自体が余分なstencil push/popを蓄積させている可能性が高い）。対策として`clear()`を一切使わず、古い`Rectangle`インストラクションは`canvas.after`に残したまま新しいものを追加する方式（同一pos/sizeなので視覚的には最新のものが上に乗るだけで無害）に変更した。
   - **新たな制約（未解明）**：上記の手法は**アプリの`current`が`'home'`のときは何度でも・何度画面遷移した後でも確実に機能する**が、**`'dash'`（Dashboard）のときは、初回訪問・2回目訪問・settling待ち時間を60秒以上に延ばす・0.3秒間隔で連続的に追加し続ける、のいずれを試しても一度も表示に成功しなかった**。`'config'`（Setup、比較的静的な画面）でも1回試したが同様に失敗した。`sm.canvas.after`・`relative_layout.canvas.after`・`sm.current_screen.canvas.after`のいずれに描き足しても結果は同じだった。DashboardViewが内部で使う`AnalysisCarousel`（`Carousel`）・`TripleGaugeBar`（`Scatter`）は、本タスクの調査史を通じて度々「settlingに間に合わない」「他と挙動が異なる」と報告されてきた特殊なウィジェット群であり（第33回セッション候補参照）、これらの存在がDashboard画面固有の失敗と関係している可能性が高いが未検証。
   - **実機での確認範囲**：Home画面での重ね描きは、Home→Dashboard→Home、Home→Dashboard(2回目)という複数の画面遷移サイクルを経ても一貫して復元できることを確認済み（`v9_backhome0001.png`、38,973バイト）。

**25. 実機（`rc-dash-3b`）の状態（本追記時点）**：全てのテストプロセス（`frametrace16.so`使用）は終了済み。本番の`/opt/racecapture/run_racecapture_rpi.sh`・`/home/ntakao/scmove_persist.so`は第36回セッション終了時点のまま**無変更**（今回の調査は全て別プロセスでのみ実施し、本番は都度標準の起動コマンドで復旧済み、`throttled=0x0`）。新規生成物：`/home/ntakao/combined_fix.py`〜`combined_fix5.py`（重ね描き+自動再修復の統合スクリプト各バリエーション）、`/home/ntakao/reheal_boxlayout.py`・`reorder_test.py`・`flip_back.py`・`export_test.py`・`overlay_test.py`・`canvas_overlay_test.py`・`touch_test.py`・`redo_toolbar_after_reheal.py`・`try_relativelayout_canvas.py`・`reorder_reheal_toolbar.py`・`probe_canvas.py`・`rapid_readd_test.py`（いずれも次回セッションで再利用可能、`/home/ntakao/`直下）。

**26. 🔴🎯 （第37回セッション、追加検証・15分枠）`analysis`画面（Sessions/Import Logsタブのシンプルなリスト画面、`Carousel`/`Scatter`は含まれていない）でも同じ手法を試したところ、Dashboard・Setupと同様に`canvas.after`重ね描きは表示に失敗した**：これにより「`Carousel`/`Scatter`系ウィジェットが原因」という候補0の仮説①の優先度は下がった。**`'home'`以外のあらゆる画面（`dash`・`config`・`analysis`のいずれも）で一貫して失敗する一方、`'home'`だけは画面遷移を何度挟んでも一貫して成功する**、という、画面の内容やウィジェット構成に依存しない、より単純な二分法が濃厚になった。`'home'`が特別な理由の最有力候補：**`'home'`はKVパース時点（`ScreenManager`が初めて構築された瞬間）から存在する唯一のScreenであり、他の全ての画面は`switch_to()`によって実行時に動的生成される**という違い（ただし前回セッションで`'dash'`への2回目訪問＝`switch_to()`を経由しない`current=`代入パスでも同様に失敗することは確認済みのため、単純な「動的生成か否か」だけでは説明がつかない。`'home'`がScreenManagerの起動時デフォルト`current`値であったこと自体に何か特別な意味がある可能性が残る）。

**27. 🔴🎯 （第37回セッション、追加検証・2回目の15分枠）「再追加を試みる操作自体が失敗の原因では」という仮説を反証実験で否定し、「`_rc_reheal`（`relative_layout`上での`sm`のremove/re-add）という操作自体が、たとえ`canvas.after`へ一切触れなくても、既存の`canvas.after`内容を破壊する」ことを確定した**：Home画面で`canvas.after`への重ね描きに成功した直後、**以降一切`canvas.after`を触らない**（`_rc_reheal`は`sm`のremove/re-addのみ行い、ツールバーの再追加は一切試みない）設定で`'dash'`へ遷移したところ、`sm`本体のコンテンツ（Dashboardのゲージ表示）は例によって数秒後に正しく復活したが、**Home画面で追加したツールバーのRectangleは、再追加を一切試みていないにもかかわらず、遷移後は跡形もなく消えていた**（`nr_dash30001.png`、69,410バイト＝ツールバー無しのDashboardのみのサイズと一致）。これにより「`redo_toolbar_after_reheal.py`等での再追加の試みそのものが何か余計な副作用を起こしている」という可能性のあった仮説は完全に排除され、**破壊の原因は`_rc_reheal`が行う`relative_layout.remove_widget(sm)`/`add_widget(sm)`という操作自体にある**（`sm`本体のコンテンツを復活させるために必須のこの操作が、副作用として`canvas.after`の内容を巻き添えにして消してしまう）ことが確定した。この結論は「`'home'`以外の画面では再追加を試みても復活しない」という既知の事実とも矛盾せず、**`_rc_reheal`実行時点でのcurrent screenが`'home'`かどうかだけが結果を左右する**という理解に一本化された。

**28. ⚠️ （第37回セッション、追加検証・3回目の15分枠）「`relative_layout.canvas.after`なら`_rc_reheal`の巻き添えを回避できるはず」という候補③を`'home'`起点で再検証したが、これも失敗した**：`'home'`にいる間に`relative_layout.canvas.after`（`_rc_reheal`が直接remove/re-addする`sm`ではなく、その親である`relative_layout`自身のcanvas）へ重ね描きし、Home画面での表示成功（38,973バイト）を確認した上で`'dash'`へ遷移したところ、`sm`本体のコンテンツは例によって数秒後に正しく復活したが、`relative_layout.canvas.after`の内容もやはり跡形もなく消えていた（`rls_dash30001.png`、70,916バイト＝ツールバー無しのDashboardのみのサイズと一致）。**これにより「`_rc_reheal`が直接触るウィジェットのcanvasだから壊れる」という説明では不十分であることが判明した**：`_rc_reheal`は`sm`のみをremove/re-addし`relative_layout`自体には一切触れていないにもかかわらず、`relative_layout`のcanvas内容も巻き添えで消えている。これは「特定のウィジェットのcanvas操作が破壊の引き金」ではなく、**`sm.current`が`'home'`以外の値になった、という状態遷移そのもの（あるいはそれに伴うScreenManagerの内部処理全体）が、RelativeLayoutのサブツリー全体の再コンパイルを引き起こし、その際に`'home'`以外の状態でだけ余分な内容が巻き添えで消える**という、より広範囲・より`'home'`固有の仮説を裏付ける結果。

**29. 🔴🎉🔑 （第37回セッション、追加検証・4回目の15分枠）破壊の犯人が我々自身の`_rc_reheal`ではなく、Kivy自身のScreenManager画面遷移機構であることを実機実証で確定した**：`sm.bind(current=...)`による自動再修復を一切セットアップせず（＝`_rc_reheal`が存在しない状態）、Home画面で`canvas.after`重ね描きに成功させた直後、`app.switchMainView('dash')`を素朴に1回呼ぶだけの実験を行った。この場合`sm`本体のコンテンツは（`_rc_reheal`が無いため）予想通り黒画面のままだったが、**ツールバーの重ね描きも同時に跡形もなく消えていた**（`noa_dash0001.png`、2,869バイト＝完全な黒画面と一致）。これにより、**`canvas.after`を破壊しているのは我々が実装した`relative_layout.remove_widget(sm)`/`add_widget(sm)`という再配置トリックではなく、Kivy標準の`ScreenManager`が`current`変更時に内部で行う画面遷移アニメーション機構（`TransitionBase`のサブクラス、おそらくFBOベースの画面合成に`canvas.after`を使っている）そのものである**ことが確定した。これは第37回セッション冒頭で`probe_canvas.py`により`sm.canvas.after`の中に`StencilUnUse`/`BindTexture`/`Rectangle(0,0,800,480)`/`StencilPop`というScreenManager自身が管理していると見られる命令列が既に存在していたことの直接的な裏付けとなる。一方で`'home'`への遷移だけはこの破壊を免れる（またはKivy自身のtransition機構が`'home'`遷移時だけ何か違う処理をしている）という非対称性の理由は依然として未解明。

**30. ⚠️ （第37回セッション、追加検証・5回目の15分枠）候補1「`NoTransition`化」を検証したが効果なしと判明。同時に、`sm.canvas.after`内の謎の`Stencil`/`Rectangle(0,0,800,480)`構造が、`Transition`の種類に関係なく常に存在することを確認した**：`sm.transition = NoTransition()`をアプリ起動直後・`sm`の再配置より前に注入した状態で同じ手順を実施したが、Home画面では従来通り成功（38,864バイト）した一方、`'dash'`への遷移では**やはりツールバーは表示されなかった**（`nt_dash30001.png`、70,661バイト＝ツールバー無しのDashboardのみのサイズと一致）。`NoTransition`適用下で`sm.canvas.after`の中身を`probe_canvas.py`で確認したところ、`['StencilUnUse', 'BindTexture', 'Rectangle(0,0,800,480)', 'StencilPop', ...]`という、デフォルトTransition使用時と全く同じ構造が存在していることを確認した。**これにより、この`Stencil`/`Rectangle`構造は画面遷移アニメーション（`Transition`クラス）由来ではなく、`ScreenManager`のより基本的な機構（現在のScreenの描画範囲をクリップする等の恒常的な仕組み）に由来すると判明し、`Transition`変更というアプローチ自体の望みは薄いと判断される**。

**31. ⚠️🔑 （第37回セッション、追加検証・6回目の15分枠）`kivy_repro_venv`（バンドル同等のKivy 2.3.1）のソースコードを直接読み、`sm.canvas.after`内の謎の`StencilUnUse`/`BindTexture`/`Rectangle(0,0,800,480)`/`StencilPop`構造の正体を追ったが、Kivy本体・KivyMDの`ScreenManager`/`Transition`実装のどこにも該当コードが見つからず、この構造自体が`'home'`と`'dash'`の違いの原因ではないと判明した**：`screenmanager.py`を精読したところ、`Stencil`系命令は同ファイル中に一切登場しない（`SwapTransition`は`PushMatrix`/`Scale`、`ShaderTransition`系（`FadeTransition`等）は`Fbo`/`BindTexture`/`RenderContext`/`Rectangle`を使うが対象は`manager.canvas`ではなく個別Screenのfbo）。`kivymd/uix/screenmanager.py`（`MDScreenManager`）も`DeclarativeBehavior`を足すだけの薄いサブクラスで該当コードなし。加えて実機で、`sm`を`box_layout`から`relative_layout`へ移した直後（`current='home'`のまま、ツールバー操作は一切していない状態）でも`sm.canvas.after`に同じ`['StencilUnUse', 'BindTexture', 'Rectangle(0,0,800,480)', 'StencilPop']`が既に存在することを確認した。**つまりこの構造は`'home'`・`'dash'`どちらでも同様に存在する共通の背景要素（恐らくKivyMDのグローバルなSnackbar/Toastオーバーレイ機構、またはRaceCapture独自の何らかの全画面オーバーレイ）であり、`'home'`固有の差異の原因ではないと判明した**。根本原因は依然としてKivy/KivyMD標準コードの外（RaceCapture独自の`main.py`/各Viewクラス、またはウィジェットツリーの実行時状態）にあると考えられる。

**32. 🔑 （第37回セッション、追加検証・7回目の15分枠）`main_disasm.txt`を精読し、`build_dash_view`/`build_analysis_view`/`build_homepage_view`の実装を比較したところ、いずれも対象クラス（`DashboardView`/`AnalysisView`/`HomePageView`）が直接`kivy.uix.screenmanager.Screen`を継承しており、`Screen(...)`でラップする／しないという構造上の違いは無いと確認した。一方で、`_get_main_screen`（`self.mainViews.get(view_name)`によるキャッシュ）・`view_builders`（`{'home': build_homepage_view, 'dash': build_dash_view, ...}`という辞書、いずれも起動時は空でどのview_nameも対等に扱われる）を確認した結果、**RaceCapture独自コードのレベルでは`'home'`だけを特別扱いする分岐は存在しないと判明した**。この結果から、より有力な統一仮説に到達した：`'home'`は`ScreenManager`がKVパースの時点で最初から普通のウィジェットとして持っていた唯一のScreenであり、**一度も`TransitionBase.add_screen()`/`remove_screen()`（内部で`manager.real_add_widget()`/`real_remove_widget()`を呼ぶ、`current`変更のたびに必ず起動するアニメーション機構）を経由したことがない**。それ以外の全ての画面（`dash`/`analysis`/`config`等）は、初回訪問・2回目訪問を問わず`current`プロパティの変更のたびに必ずこの`TransitionBase`経由の`real_add_widget`/`real_remove_widget`サイクルを踏む（Kivyの`ScreenManager.on_current`が内部で無条件に`self.transition.start(self)`を呼ぶため、`switchMainView`側で`current=`と`switch_to()`のどちらの経路を通っても同じ）。**この「`TransitionBase`を一度でも経由したかどうか」という違いこそが、`canvas.after`重ね描きの生死を分けている最有力候補**（Kivy/KivyMD標準コードにはStencil関連の記述が無かったため、`real_add_widget`/`real_remove_widget`自体、またはそれがトリガーする`ScreenManager`内部の未知の副作用が、Mesa VC4タイラーのバグと絡んで`canvas.after`を巻き添えにしている可能性が高い）。この仮説はランタイムのpyexecトリックでは検証不能（`current`プロパティの変更は必ず`TransitionBase`を起動するため、`'dash'`を"KVパース時から存在したかのように"偽装する手段が無い）で、**`main.pyc`のKV文字列を書き換えて`ScreenManager`の初期`current`を`'dash'`に変更するバイトコードパッチ実験が、次回の確実な検証方法として残る**。

**33. ⚠️🔑 （第37回セッション、追加検証・8回目の15分枠）候補0（KV文字列で初期`current`を`'dash'`に変更するバイトコードパッチ）を実際に試みたが、`current: "dash"`をKVの`ScreenManager`ルールへ静的に追加すると、アプリがクラッシュではなく**起動シーケンスの途中で無限にハングする**ことが判明し、この検証方法自体が使えないと分かった**：`~/repack_4-4-2/repack_current_dash.py`（`repack_main_kv.py`を流用、`pos_hint`行を`current: "dash"`に置換）で`race_capture.orig`をパッチし（`pycryptodome`未導入によるインポートエラーは`~/decompile_4-4-2/venv/bin/python3`で解消）、実機で起動したところ、ログが`[INFO] [AppConfig] using user storage directory: ...`で完全に停止し、それ以降Pythonの例外・トレースバックも一切出力されないまま`timeout 10`でSIGTERMするまでプロセスが生き続けた（exit code 124＝ハング、クラッシュではない）。**KVパース時点では`ScreenManager`にまだ`'dash'`という名前のScreenが1つも`add_widget`されていない（Screenは`view_builders`経由で遅延生成される）ため、`current: "dash"`というKVプロパティ代入が、存在しないScreen名への`current`設定として`ScreenManager`内部のロジックを無限ループまたはデッドロックさせている**と推測される。このため「KV文字列の単純な置換」という手法では候補0の検証はできず、真に検証するには`main.pyc`の`build()`/`on_start()`メソッド自体にバイトコードを追加し、`Builder.load_string()`実行後・最初のScreen登録後というタイミングで`sm.current = 'dash'`相当を実行する必要がある（第32回セッションが「文字列定数置換ではなく新規バイトコード命令列の挿入が必要」と結論づけていた技術的ハードルに、今回別の角度から改めて到達した）。本番バイナリ・設定は無変更（`race_capture.currentdash`は`~/repack_4-4-2/`に検証用として保存済み、次回に活用する場合はバイトコード挿入の目処が立ってから）。

**34. 🔴🔑 （第37回セッション、追加検証・9回目の15分枠）「セットアップ時に`current`が何であったか」という順序仮説を、`'dash'`起点で完全に反証した。これにより候補32の「`TransitionBase`未経由が鍵」という仮説も暗に反証された**：`app.switchMainView('dash')`を最初に呼び、2秒待って画面遷移を完了させた上で（この時点で`current='dash'`）、初めて`sm`の`box_layout`→`relative_layout`への移動と`canvas.after`重ね描きセットアップを行うテストを実施した。これは「`'home'`だから安全」ではなく「セットアップ時にcurrentだった画面が安全になる」という仮説を検証するものだったが、**`'dash'`起点でセットアップしても、その`'dash'`自身の上でツールバーは全く表示されなかった**（`sodf_dash20001.png`、66,341バイト＝ツールバー無しのDashboardのみのサイズと一致）。これにより「初回の`sm`移動時にcurrentだった画面が"safe"になる」という仮説は完全に否定された。**同時に、この`'dash'`→sm移動の遷移は`switchMainView('dash')`が引き起こす通常の`TransitionBase`サイクルを経由しているため、`'home'`から`'dash'`への遷移が`TransitionBase`を経由したこと自体が原因ではなく（`'home'`はそもそも一度もこの遷移を経由していないのに安全なので）、依然として`'home'`という画面固有の何か（コンテンツの単純さ、または`HomePageView`固有の実装）が原因である可能性が再浮上した**。これで「画面の順序・タイミング」に関する主要な仮説（初回訪問/2回目訪問、`'home'`経由/非経由、セットアップ時のcurrent値）はほぼ全て反証され尽くし、残る有力な方向性は「`'home'`（`HomePageView`）と他画面（`DashboardView`等）のコンテンツ量・複雑さの違いが、Mesa VC4タイラーの`'last touched'`判定に使われる時間窓（1フレーム内で完了する描画コール数）に影響している」という、フレーム内の描画コール量に着目した新しい方向性、またはバイトコード挿入による`'home'`のコンテンツ自体を`'dash'`と入れ替える実験（本セクション末尾の技術的ハードル参照）に絞られた。

**次回の最優先候補（優先度順、第37回セッション最終更新）**：
0. **最優先：`main.pyc`の`build()`または`on_start()`メソッドへ、`Builder.load_string()`完了後・最初のScreen登録後というタイミングで`sm.current = 'dash'`相当を実行する新規バイトコードを挿入する。** KV静的プロパティでの指定はハングするため使えないと判明した（候補33参照）。`xdis`の逆アセンブル結果を土台にした手動バイトコード合成、または完全なPythonコンパイラでの再アセンブルが必要（第32回セッションから持ち越しの技術的ハードル）。ただし候補34により「セットアップ時にcurrentだった画面が安全になる」という前提そのものが崩れたため、この実験の意義（起動時デフォルトを変えれば解決するか）は薄れた。**より有望な次の一手は、`HomePageView`固有の何か（`FeatureButton`のみの単純な構成、`Carousel`/`Scatter`/`ScrollView`等の複雑ウィジェット不使用）が真の原因である可能性を検証すること**：例えば`DashboardView`の画面に一時的に`HomePageView`と全く同じ単純な内容（ボタン数個のみ）を表示させてみて、`canvas.after`重ね描きが機能するようになるかを確認する（`DashboardView`のKVを丸ごと`HomePageView`のKVへ実行時に差し替える、または新規の単純なScreenを`'dash'`として登録し直す等）。
1. 上記0が解決しない場合、または部分的な効果に留まる場合の次善策：Home画面以外はステータスバー無し、Home画面のみステータスバー表示、という画面ごとの妥協案を検討する。
2. 車載時のHome導線（前回候補1）は本セッションで`Window.bind(on_touch_down=...)`によるタップ→`switchMainView('home')`という実装案を確立済み（`combined_fix4.py`〜`5.py`に実装・動作確認込み）。ステータスバー問題と合わせて本番組み込みを検討する。
3. Mesa GitLabへの`glClear`部分マスクバグ報告は引き続き優先度低〜中で残置。

---

### 4-4-3: X11+VNCでの目視調査時の電源負荷問題 ※記録のみ・要注意
`Xorg` + `x11vnc` + `race_capture`を同時稼働させた状態で、`throttled=0x50005`（アンダーボルテージ再発）が発生し、
システムウォッチドッグ（1分タイムアウト）による強制リブートが発生した。改善後の電源（PD/QC非対応 5V/2.1A固定出力）でも、
この複合負荷には耐えられないことが判明。次回X11+VNCでの調査を行う場合は、より高出力な電源（5V/3A程度）を先に用意するか、
あるいはX11+VNCを使わない別の調査手法（ソースコード読解等）を優先する。

### 4-4-4: 筐体格納・固定 ※未着手
4-4-2の画面表示問題解決後に着手。
