# LTE / Podium preparation — 2026-10-02

UNO Q MCUを書込み、EcoCapture-Webを更新済み。LTE送信はOFF、内蔵CSVは自動記録中。

- APN・送信キー・信号選択・自動接続・10Hz間引き・認証拒否停止・再接続を実装。
- MCUは非同期PWRKEY、UART IRQ、4096B受信、512B送信、GPIO RTS/CTS、20秒の操作途絶による電源OFFを追加。
- 最終ファーム56104B、64KiB制限内。52試験が成功。
- `live_report.json`: 32.37秒の点検/通信監視試験中に99.65Hzで3226件の内蔵記録。UART溢れ・追加センサ/Bridgeエラー0、電源OFF保護成功。
- 実回線・TCP・Podium到達・持続10Hzは未確認。SIM、LTEアンテナ、APN、送信キーが必要。
- SDは既存256MiB FAT32領域が満杯。既存データを保持し、SD継続試験は行っていない。
- Gitの更新取得はSSHホスト鍵確認/HTTPS認証で失敗。既存のntakao資料と公式RaceCapture Appソースで実装。

使い方と範囲: `EcoCapture-Web/LTE_PODIUM.md`。
`firmware.before.bin` と `web.before.tar` は作業前の保存。
