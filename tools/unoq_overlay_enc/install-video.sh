#!/bin/sh
# 焼き込み録画（overlay_rec）を常駐サービス ecologger-video.service として入れる。UNO Q上でrootで実行する
# （UNO Qにはsudoが無いので、unoq_video_check_procedure.md 5-13 のdocker nsenterの形で動かす）
#   sh install-video.sh [このフォルダのUNO Q上の置き場所]
# 外すとき：systemctl disable --now ecologger-video.service
set -eu
src=${1:-/home/arduino/video_test/install}
dst=/opt/ecologger-video
mkdir -p "$dst"
# overlay_rec.c と同じ場所に hud_layout.h・lap_ref.h・video_store.h・ts_mux.h・audio_cap.h が要る
# 音（MP2）は録画プログラムが実行時に libtwolame.so.0 を読んで固める（ヘッダーは要らない）。
# 無ければ音なしで録る（前と同じ動き）。入れるとき：apt-get install -y libtwolame0（Debianの公式、libcだけに依存。手順書5-20）
ls /usr/lib/*/libtwolame.so.0 >/dev/null 2>&1 && echo "audio: libtwolame0 found" || echo "audio: libtwolame0 not installed (recording without audio)"
command -v arecord >/dev/null || echo "audio: arecord not found (recording without audio)"
gcc -O2 -o "$dst/overlay_rec" "$src/overlay_rec.c" -lEGL -lGLESv2 -ljpeg -lm -lpthread -ldl
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
