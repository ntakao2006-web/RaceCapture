# RaceCapture互換 自作車載データロガー

RaceCaptureのロギングシステムのうち、ロガー端末部分だけを自作ハードウェア（ESP32）に置き換えるプロジェクト。

## まずはここを見てください

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — プロジェクト全体の唯一の一次情報源（目的・全体構成・現状ステータス・開発ロードマップ）
- **[hardware_interface_spec.md](hardware_interface_spec.md)** — 電気・回路系担当の方向け：入出力インターフェース仕様・相談事項まとめ

## その他の主なドキュメント

- [HANDOFF.md](HANDOFF.md) — RaceCapture JSON通信プロトコルの実測仕様
- [OBD2_SURVEY.md](OBD2_SURVEY.md) — 実車OBD2/CAN調査の記録
- `task_phaseX_breakdown.md` — 各開発フェーズのサブタスク分解
- `firmware/` — ESP32向けファームウェア（PlatformIO / ESP-IDF）
