# EcoCapture Live（Firebase）

EcoCaptureの走行値を1 HzでFirebase Realtime Databaseへ保存し、Firebase Hostingのスマホ画面へリアルタイム表示します。送信用・閲覧用キーの登録はありません。EcoCaptureが自動生成する32文字の共有URL IDを、URLを知る人だけで共有します。

## 初回セットアップ

1. Firebase Consoleで無料のSparkプランのプロジェクトを作る。
2. Realtime Databaseを作り、表示されたURLを控える。
3. このフォルダーで `npm install`、`npx firebase login`、`npx firebase use --add` を実行する。
4. `npx firebase deploy --only hosting,database` を実行する。
5. EcoCaptureのSettings > ライブ共有へDatabase URLと表示されたHosting URLを貼る。
6. 「接続確認」の後、「共有URLをコピー」でスマホへ渡す。

`database.rules.json`はデータベース全体の一覧取得を拒否し、24〜48文字の共有URL ID配下だけを読み書き可能にします。認証を使わないため、URLを知った人はその走行データを閲覧でき、同じIDへ値を書き込むこともできます。内輪利用の範囲を越える場合はFirebase Authenticationを追加してください。

履歴はUTC日ごとに分けて保存し、EcoCaptureが8日前の日を削除します。1 Hzで24時間なら1日86,400点です。無料枠に余裕を残すための7日保持であり、長期間連続運用する場合はFirebase Consoleの使用量も確認してください。
