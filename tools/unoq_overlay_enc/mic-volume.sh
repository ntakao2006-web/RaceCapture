#!/bin/sh
# カメラのマイクの音量を決める（録画プログラムが arecord を始める前に毎回呼ぶ。手順書5-23）
#   カメラを挿し直す・電源が切れると、カメラの中の音量は元（大きすぎて割れる値）に戻るので、録り直すたびに入れ直す
#   $1：ALSAのカード名（plughw:CARD=○○ の○○）  $2：音量（amixer の値。例 30%・-10dB・生の数。空なら触らない）
#   $3：カメラの自動の音量調整（on・off。空なら触らない）
#   出力は標準エラー（録画の journal）へ
card=$1 vol=$2 agc=$3
[ -n "$card" ] || exit 0
amixer -c "$card" scontrols 2>/dev/null | sed -n "s/^Simple mixer control '\(.*\)',\([0-9]*\)\$/\1,\2/p" | while IFS= read -r c; do
    caps=$(amixer -c "$card" sget "$c" 2>/dev/null | sed -n 's/^ *Capabilities: //p')
    case "$c" in
        *[Gg]ain*[Cc]ontrol*|*AGC*)
            [ -n "$agc" ] && amixer -q -c "$card" sset "$c" "$agc" && echo "audio: mic $c -> $agc" >&2 ;;
        *)
            case " $caps " in
                *" cvolume"*|*" volume"*)
                    if [ -n "$vol" ]; then
                        # 「-15dB」の頭の - をオプションと取り違えないよう -- を挟む
                        amixer -q -c "$card" sset "$c" -- "$vol" cap 2>/dev/null || amixer -q -c "$card" sset "$c" -- "$vol" || echo "audio: mic $c: could not set $vol" >&2
                        echo "audio: mic $c -> $(amixer -c "$card" sget "$c" | grep -o '\[[^]]*\]' | tr '\n' ' ')" >&2
                    fi ;;
            esac ;;
    esac
done
exit 0
