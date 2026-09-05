# EcoCapture Live（Firebase）

EcoCaptureの走行値を1 HzでFirebase Realtime Databaseへ保存し、Firebase Hostingのスマホ画面へリアルタイム表示します。送信用・閲覧用キーの登録はありません。EcoCaptureが自動生成する32文字の共有URL IDを、URLを知る人だけで共有します。

## 利用方法

1. EcoCaptureのSettings > ライブ共有で「共有リンクを作ってコピー」を押す。
2. 「データ共有をONにする」を有効にする。
3. コピーした `https://ecocapture-live.web.app/?id=...` をLINEなどで渡す。共有相手はブラウザで開くだけでよく、Firebaseへのログインは不要。

サービスはFirebase Sparkの `ecocapture-live` へ配備済みです。配布アプリにもRealtime Database URLとHosting URLを組み込んでいるため、利用者によるFirebase設定はありません。再配備する開発者はこのフォルダーで `firebase deploy --only hosting,database --project ecocapture-live` を実行します。

0.3.7の走行経路は国土地理院の淡色地図へWeb Mercatorで重ねます。地図の拡縮・移動・全体表示に対応します。
測位断、DEMO/実測切替、車体切替をまたいで線をつなぎません。タイル通信失敗時も経路は描画し、エラーを表示します。
タイルは端末から地理院へ直接取得します（出典表示・Referer送信なし）。Firebaseの要求頻度は変えていません。
この更新の公開は `firebase deploy --only hosting --project ecocapture-live` で行います。データベースルールや課金設定は変更しません。

`database.rules.json`はデータベース全体の一覧取得を拒否し、24〜48文字の共有URL ID配下だけを読み書き可能にします。認証を使わないため、URLを知った人はその走行データを閲覧でき、同じIDへ値を書き込むこともできます。内輪利用の範囲を越える場合はFirebase Authenticationを追加してください。

履歴はUTC日ごとに分けて保存し、EcoCaptureが8日前の日を削除します。1 Hzで24時間なら1日86,400点です。無料枠に余裕を残すための7日保持であり、長期間連続運用する場合はFirebase Consoleの使用量も確認してください。
