#!/bin/sh
# rc-dash-4B の画面を EcoCapture へ切り替える（dash-switch の薄いラッパ）。
# 設置先: Pi の /usr/local/bin/ecocapture-start
exec /usr/local/bin/dash-switch ecocapture
