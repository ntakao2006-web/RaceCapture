# logger_v1.net 受領記録

## 概要

- **受領日**：2026-08-14（電気・回路系担当の友人 lintaroh より受領）
- **ファイル情報**：KiCadエクスポートのネットリスト（Eeschema 9.0.6）。rev A / v1。回路図自体の作成日は2026-08-14
- **タイトル**：RaceCapture Compatible Data Logger / ESP32-S3
- **友人環境での元パス**：`C:\Users\lintaroh\Documents\datalogger\circuit\logger_v1\logger_v1.kicad_sch`

メインロガー基板（`ARCHITECTURE.md`6章「製作を依頼したい基板一覧」の1枚目）の初回設計案として送付されたもの。KiCadの回路図(`.kicad_sch`)本体は友人側の環境にのみ存在し、こちらにはネットリスト(`.net`)のみが共有されている。

## このファイルを受けて確認・決定した内容（2026-08-14〜2026-08-16）

`logger_v1.net`のネットリスト解析、および友人・lintarohとの会話を通じて、以下を確認・決定した。詳細と最新状態は`ARCHITECTURE.md`4章「メインロガー基板の回路設計」・`hardware_interface_spec.md`を参照（このファイルは受領時点の一次資料として保存するのみで、以後の更新はARCHITECTURE.md側で追う）。

- メインマイコンは ESP32-S3-DevKitC-1ボードではなく、ESP32-S3-WROOM-1-N16R8モジュールを直接実装するフルカスタム基板と判明
- GNSS：STMicroelectronics Teseo-LIV3FLに確定（UART接続、CR2032バックアップ電池付き）
- IMU：Bosch BNO055（9軸、UART接続）に確定（従来のLSM6DSV16X/I2Cから変更）
- CAN 2系統：車載CAN＝MCP2562FD-E/P（単体トランシーバ）、外部CAN＝MCP25625T-E/SS（SPIコントローラ+トランシーバ一体型）
- 車載CAN側に120Ω終端抵抗(R41)が実装されていた件 → ハンダジャンパーで有無を切り替え可能な方式に決定
- 外部CANバスの電源ラインを3.3Vから5Vへ変更
- USB表示器出力(J5)をType-BからType-C（USB OTG構成）へ変更
- USB電源入力の規格はPDではなくQC（Quick Charge）と判明。12V-1.5A（18W）にネゴシエーションし、DCDCコンバータで5V→三端子レギュレータで3.3Vへ降圧する2段構成
- 車両側の給電構成を決定：ロードスターはシガーソケット充電器でモバイルバッテリーを充電し毎回着脱で給電、エコマイレッジチャレンジ車両はシガーソケット充電器から直接給電（バッテリー分離のためクランキング対策不要）
- SDカードソケット：Molex 47219-2001（金属カバー固定式）に確定
- GNSSアンテナ：現状の回路はパッシブアンテナ仕様。将来的にアクティブ／パッシブ両対応の切り替え可能回路を目指す方針
- ステータスLEDの参照元をRaceCapture/Pro MK3に決定
- グラウンド設計：車載CAN(J6)・外部CAN(J4)のGNDが基板の共通GNDに直結されている実態を確認。対策は検討中
- IMUの実装方式（基板直付け／モジュール化）、磁力計とケーシングのアルミシールドの影響について論点整理

## 関連ドキュメント

- `ARCHITECTURE.md` 4章「メインロガー基板の回路設計」
- `hardware_interface_spec.md`（友人との認識合わせ用の仕様書、3章に未確定事項の最新状態あり）
- `archive/can_termination_check.md`（終端抵抗の件で友人へ送付した確認資料）
