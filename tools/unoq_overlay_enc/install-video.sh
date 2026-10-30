#!/bin/sh
# 焼き込み録画（overlay_rec）を常駐サービス ecologger-video.service として入れる。UNO Q上でrootで実行する
# （UNO Qにはsudoが無いので、unoq_video_check_procedure.md 5-13 のdocker nsenterの形で動かす）
#   sh install-video.sh [このフォルダのUNO Q上の置き場所]
# 外すとき：systemctl disable --now ecologger-video.service
set -eu
src=${1:-/home/arduino/video_test/install}
dst=/opt/ecologger-video
mkdir -p "$dst"
# overlay_rec.c と同じ場所に hud_layout.h が要る
gcc -O2 -o "$dst/overlay_rec" "$src/overlay_rec.c" -lEGL -lGLESv2 -ljpeg -lm -lpthread
install -m 0644 "$src/hud_font_64.pgm" "$dst/"
# 元の計器の配置（自分の配置 /home/arduino/ecologger-video/hud.ini が無いときに使う）
install -m 0644 "$src/hud_default.ini" "$dst/"
install -m 0755 "$src/run-video.sh" "$dst/"
# .serviceはWindowsで取り出すとCRLFになることがあるので、CRを落として置く
tr -d '\r' < "$src/ecologger-video.service" > /etc/systemd/system/ecologger-video.service
systemctl daemon-reload
# 入れ直しのときも新しい版で動くように、動いていても止めてから起動し直す（録画中のファイルは閉じられる）
systemctl enable ecologger-video.service
systemctl restart ecologger-video.service
systemctl --no-pager status ecologger-video.service | head -5
