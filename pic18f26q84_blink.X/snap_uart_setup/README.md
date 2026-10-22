# Snap UART / COMポート設定

## 2026-09-04の確認結果

- 対象Snapのシリアル番号: `021038102RYN014624`
- 変更前: MPLAB用ファーム、USB `04D8:9018`。USBインターフェースは書き込み用のみで、CDCなし。
- 変更後: 公式CMSIS-DAP v2用ファーム、USB `04D8:90B1`。
- WindowsはCDCインターフェースを `USB シリアル デバイス (COM16)` として認識。ドライバーはWindows標準の `usbser.inf`。
- PIC側UART1をRC6/TX・RC7/RX、115200 baud / 8N1 / フロー制御なしに設定。
- PICへ書き込み・照合後、COM16からPIC固有の識別応答を確認。
- ランダム長データ、未知コマンド、長すぎる入力を含む104回と1004回の独立した双方向テストが全件成功。
- Lチカは終了し、RA0はLow固定。最終状態はPICがUARTテスト用、SnapがCMSIS-DAP v2（COM16あり）。
- COM番号は今後のUSBポート変更等で変わる可能性がある。

## 使用した公式ファームとツール

Microchip `Snap_TP 3.0.1942` の配布ファームを `firmware` に保存した。これはPICのプログラムではなくSnap自身のファーム。元の実機から読み出したバックアップではなく、元に戻すための公式配布イメージ。

- `snap_app_cmsis-dap.hex`: COMポートを公開するCMSIS-DAP用
- `snap_app.hex`: MPLAB用への復帰用
- `snap_boot.hex`: 緊急復旧用として保存。今回ブートローダーは書き換えていない。

切り替えにはMicrochip公式 `pycmsisdapswitcher 2.0.2.19` を使用し、書き込み・照合と切り替えの成功を確認した。

## モード切り替え

切り替え前にMPLAB、VS CodeのSnap使用セッション、COM16を使う端末を閉じる。更新中はUSBを抜かない。

このフォルダーでPowerShellから実行する。

```powershell
# 読み取りのみ: Snapの識別と保存ファームのハッシュを確認
.\Set-SnapFirmware.ps1 -Mode Cmsis -CheckOnly

# UART用COMポートを使う
.\Set-SnapFirmware.ps1 -Mode Cmsis

# 従来のMPLABによるPIC書き込み用へ戻す（COMポートは消える）
.\Set-SnapFirmware.ps1 -Mode Mplab
```

スクリプトは上記シリアル番号のSnapのみを対象にする。複数の対応書き込み器がつながっている場合は停止する。通常の切り替えでJ3をショートさせる必要はない。

PICへの再書き込み時はSnapをMplabモードにし、書き込み後にCmsisモードへ戻す。両方向の切り替えと照合を実機で確認済み。

## UART実機テスト

```powershell
C:\Users\lintaroh\AppData\Local\Microchip\snap-uart-tools\Scripts\python.exe .\test_uart.py --count 100
```

SnapのUSBシリアル番号からCOMポートを選ぶため、COM番号が変わっても誤ったポートを試験しない。`PASS`ならPICが入力を解析・加工した全応答が一致している。

## UART配線

PIC18F26Q84-E/SPでRC6をTX、RC7をRXに設定する場合:

- Snap 8ピンコネクタの7番 → PIC 17番 RC6/TX
- Snap 8ピンコネクタの8番 → PIC 18番 RC7/RX
- Snap 3番 → 共通GND
- Snap 2番 TVDD → PIC VDD

Snap資料のTX/RX表記はターゲット側基準。PICには外部電源が必要。

## 証跡・資料

- `switch_to_cmsis_20260904.log`: 公式ツールの書き込み・照合成功ログ
- `com_check_20260904.log`: 同一SnapのCOM16識別と開閉確認
- `../programming_20260904_2238_uart.log`: PIC検出、書き込み、照合の成功ログ
- `uart_test_20260904_224438_845405.jsonl`: 104応答の成功ログ
- `uart_test_20260904_224454_193169.jsonl`: 1004応答の連続成功ログ
- [PIC18-Q84 UART端子設定](https://onlinedocs.microchip.com/oxy/GUID-7112B2B7-9230-4367-BBFB-942C5B51D8BF-en-US-15/GUID-916D8EB0-94EA-4316-A3CA-29CB139B3416.html)
- [PIC18-Q84 UARTボーレート計算](https://onlinedocs.microchip.com/oxy/GUID-7112B2B7-9230-4367-BBFB-942C5B51D8BF-en-US-15/GUID-5D554793-676E-4F0B-8022-67C65136118D.html)
- [Microchip公式切り替えツール説明](https://developerhelp.microchip.com/xwiki/bin/view/software-tools/programmers-and-debuggers/cmsis-dap/)
- [公式ツールのコマンド仕様](https://pypi.org/project/pycmsisdapswitcher/)
- [Snap公式UART端子表](https://onlinedocs.microchip.com/oxy/GUID-671CAF55-DB13-4D9A-8881-F58C984111B5-en-US-4/GUID-ECE487E3-CCF2-49C8-97A6-01CEEDE5FD22.html)
