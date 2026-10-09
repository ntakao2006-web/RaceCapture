# Lintarohさんへの共有メモ その2（2026-10-09）

前回のメモ（`lintaroh_share_20261009.md`）と、その回答（`lintaroh_answer_20261009.md`）を受けて、UNO Qを実機につないで作業しました。
**STM32のファームとRouterBridgeのビルド時修正を変更し、Linux側に常駐サービスを1つ追加しました。**
何をしたか・何が分かったか・**相談したいこと（4章）**をまとめます。

---

## 1. 結論

- 稼働中ファームの元ソースが確定しました。それを土台に**CAN2のACK**と**ループ監視（30秒停止で自動再起動）**を入れ、本番として書き込み済みです。
- **STM32の内部からリセットすると（Linuxが通信している最中だと）、Linuxとの通信路が戻りません。** 原因の半分（SDが止まる方）は特定して直しました。**残り半分（UARTの通信路）が分からず、相談したいところです。**
- 当面は、Linux側の監視役が通信断を検知し、NRSTリセットの手順で復帰させます。ループ停止試験では、止めてから**48秒で全自動で復帰**しました。

## 2. UNO Q上でしたこと

| やったこと | 今の状態 |
|---|---|
| 書き込み前に機器側のソース・ビルド成果物・`~/fw_backup/`をPCへ退避 | PC `Documents\UNOQ_fw_backup\2026-10-09\device_snapshot_t1020\` |
| `flash-mcu.sh`と`--no-start`対応の`install-router.sh`を機器へ配置 | 配置済み。旧`install-router.sh`は`.bak-20261009`。**実機で10回以上、全段階を問題なく通過** |
| STM32ファームを更新 | 本番：`~/ecologger_v2_wdog_20261009.bin`（SHA256 `a77ecbcc…`）。試験用ファームを何度か挟んだが、最後に本番版へ戻し済み |
| 機器側`~/ecologger_v2/`をリポジトリと同じ内容へ更新 | `compare_sources.py`で一致を確認。直前の版は`~/ecologger_v2.before-wdog-20261009/` |
| `build.sh`のRouterBridge修正を追加（3-2） | **インストール済みライブラリの`bridge.h`を書き換え済み**（`build.sh`が毎回当てる） |
| `ecocapture-mcu-supervisor.service`を追加（rootで常駐） | 有効化済み。止めるなら`systemctl disable --now ecocapture-mcu-supervisor` |
| 置いたファイル | `/tmp/v_*`（試験ビルド）、`~/ecologger_v2_can2ack_20261009.bin`（途中の版）。消して構いません |

試験でリセットを繰り返したので、SDの`EL000474`〜`EL000566`あたりは机上の短いログです。

## 3. 分かったこと

### 3-1. ソースの食い違い（前回の3章1）の答え
- 稼働中ファーム（10/3 19:13ビルド）は、**機器側`~/ecologger_v2/`（10/3 18:58版）を再ビルドするとバイト一致**しました。
- リポジトリ版（10/4のコミット）には、ループ監視とCAN2の通常モードが入っていましたが、**UNO Q上ではリンクエラー（`sys_reboot`未定義）でビルドできませんでした**。`sys_reboot`はスケッチ（LLEXT）側に公開されていません。`NVIC_SystemReset()`へ置き換えています。
- 監視をスレッドで立てる作り（スタック768B）だと、静的領域が128KiBを53B超えました。`k_timer`方式に変えて、増加を232Bに抑えています。

### 3-2. 内部リセット後にSDが0バイトになる → 原因を特定して修正
- `Bridge.begin()`は`$/reset`の返事を待つ間、`updateEntryPoint`が`if (Bridge)`で弾かれ、`k_yield()`で空回りします。
- `k_yield()`は同じか高い優先度にしか譲らないので、**優先度6のSD保存スレッド（`sdWorker`）にCPUが回りません**。
- `build.sh`で`Bridge.update()`を無条件に呼ぶよう修正しました（RPCが無ければ`update()`の中で1ms休む）。修正後は、内部リセット後に通信が切れたままでもSD記録が続きました（約2分半で1.5MB）。
- 副作用として、`$/reset`完了前に届いた問い合わせには「未登録の機能」のエラーを返すことになります。

### 3-3. 内部リセット後に通信路が戻らない → 未解決
| リセットの方法 | Linuxが通信中 | 結果 |
|---|---|---|
| NRST（openocd `srst_only`） | 通信中 | ✅ 復帰 |
| デバッガのSYSRESETREQ（`reset_config none`） | Web停止・ルーター再起動直後 | ✅ 復帰 |
| デバッガのSYSRESETREQ | 通信中 | ❌ |
| スケッチ内の`NVIC_SystemReset()` | 通信中 | ❌（ループ監視も同じ） |
| IWDG（0.5秒で発火させる試験） | 通信中 | ❌ |

- ❌のときもSTM32はメインループまで動いています（PCを標本化して確認）。
- Linux側`/proc/tty/driver`で`ttyHS1`の**rxカウンタが増えず、txもほぼ止まります**。ルーターを再起動しただけでは戻らず、「Web停止→ルーター再起動→NRSTリセット→Web起動」で戻ります。
- NRSTの成功は1回しか試していないので、たまたまの可能性もあります。

### 3-4. RAMの実際の限界
- 静的領域（`audit_image.py`）が**130,365Bでは起動し、130,601Bではエラーも出さずに起動しませんでした**（`logger.status`が未登録のまま）。ローダーの追加領域で、128KiBより500〜900B手前が限界です。
- 前回の「残り6,475B」は10/3 14:03版の値でした。実際に動いていた19:13版は残り1,191Bで、今の本番版は**残り967B**です。E-6の受け皿はこの中から捻出する必要があります。

## 4. 相談したいこと

1. **3-3の原因**：内部リセットのとき（通信中）だけ、Linux側の受信が止まる理由に心当たりはありますか。STM32の起動中にLPUARTのRTSがどう見えているか、`loggerBridgeSerialInit`でRTS/CTSを有効にする前後の窓、GENIのRXが止まる件（`build.sh`のコメント）あたりを疑っています。
2. **3-2のライブラリ修正**は、RouterBridgeの使い方として問題ないでしょうか。
3. **監視役（`mcu-supervisor.py`）の置き場所と作り**：EcoCapture-Webの外の常駐サービスにしましたが、`server.py`側に持たせる方がよければ合わせます。
4. **E-6のRAM**：残り967Bの前提で、取得待ち行列（64KiB）の再配分の案があれば教えてください。

## 資料
- `ARCHITECTURE.md` 4章（2026-10-09追記の後半4件）
- `firmware/ecologger_v2/README.md`、`firmware/ecologger_v2/build.sh`（RouterBridge修正）、`firmware/ecologger_v2/logger_impl.h`（`LOGGER_STALL_TEST`で試験コマンド）
- `EcoCapture-Web/mcu-supervisor.py`・`ecocapture-mcu-supervisor.service`・`install-mcu-supervisor.sh`・`README.md`
