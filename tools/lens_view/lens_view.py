# -*- coding: utf-8 -*-
"""USBカメラの映像を、レンズの歪みを補正してズームして見る（PC用の確認アプリ）。

使い方:  python tools/lens_view/lens_view.py  [--size 1280x720] [--cam 番号]
  つまみ（Controlsの窓）:
    k1 / k2   : 歪みの補正の強さ（たる型の歪みは k1 をマイナスへ）
    zoom      : 補正後のズーム（1.00 = 等倍）
    shift x/y : ズームの中心をずらす
  キー（映像の窓で押す）:
    g = 格子の表示/非表示   o = 補正前と見比べ   s = 設定を lens.json に保存
    r = つまみを初期値へ    c = 次のカメラへ     q / Esc = 終わる

補正のしかた: 窓枠・電柱・建物の角など「本当はまっすぐな線」を画面の端に映し、
格子と平行にまっすぐになるまで k1 を動かす（端だけ曲がりが残るなら k2 も少し）。
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(HERE, "lens.json")

# 焦点距離の目安（画像の幅に対する比）。4.3mmのM12レンズ＋IMX323で水平約64°→約0.8。
# 歪みの係数はこの値と組で意味を持つので、保存するときも一緒に書く。
F_RATIO = 0.8

CTRL = "Controls"
VIEW = "Lens view (q: quit)"

# つまみの範囲（整数で持つので、値 = (pos - オフセット) / 倍率）
K1_MIN, K1_MAX = -0.80, 0.30
K2_MIN, K2_MAX = -0.30, 0.30
ZOOM_MIN, ZOOM_MAX = 1.00, 3.00
SHIFT_MAX = 0.40  # 画像の幅・高さに対する割合


def to_pos(v, vmin, step):
    return int(round((v - vmin) / step))


def open_camera(index, w, h):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, 30)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        return None
    return cap


def probe_full_hd(index):
    """1920x1080を受け付けるか（ELPは受け付け、ノートPC内蔵やIRカメラは受け付けない）。"""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return False
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    ok, frame = cap.read()
    cap.release()
    return bool(ok and frame is not None and frame.shape[1] == 1920)


def find_usb_camera():
    for i in range(5):
        if probe_full_hd(i):
            return i
    return 0


def build_maps(w, h, k1, k2, zoom, sx, sy):
    f = F_RATIO * w
    K = np.array([[f, 0, w / 2.0], [0, f, h / 2.0], [0, 0, 1]], dtype=np.float64)
    dist = np.array([k1, k2, 0.0, 0.0], dtype=np.float64)
    newK = np.array(
        [[f * zoom, 0, w / 2.0 - sx * w * zoom], [0, f * zoom, h / 2.0 - sy * h * zoom], [0, 0, 1]],
        dtype=np.float64,
    )
    return cv2.initUndistortRectifyMap(K, dist, None, newK, (w, h), cv2.CV_16SC2)


def draw_grid(img, n_x=8, n_y=6):
    h, w = img.shape[:2]
    color = (0, 255, 255)
    for i in range(1, n_x):
        x = int(w * i / n_x)
        cv2.line(img, (x, 0), (x, h), color, 1, cv2.LINE_AA)
    for j in range(1, n_y):
        y = int(h * j / n_y)
        cv2.line(img, (0, y), (w, y), color, 1, cv2.LINE_AA)


def put_label(img, text, y):
    cv2.putText(img, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def load_saved():
    try:
        with open(SAVE_PATH, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x720", help="カメラの解像度（UNO Qの焼き込みは1280x720）")
    ap.add_argument("--cam", type=int, default=None, help="カメラの番号（省略時は1080pが出るものを探す）")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))

    index = args.cam if args.cam is not None else find_usb_camera()
    cap = open_camera(index, w, h)
    if cap is None:
        print(f"カメラ{index}を開けませんでした。Windowsの「カメラ」アプリが開いていたら閉じてください。")
        return 1
    print(f"カメラ{index}を {w}x{h} で開きました。")

    saved = load_saved()
    init = {
        "k1": saved.get("k1", -0.20),
        "k2": saved.get("k2", 0.0),
        "zoom": saved.get("zoom", 1.0),
        "shift_x": saved.get("shift_x", 0.0),
        "shift_y": saved.get("shift_y", 0.0),
    }

    cv2.namedWindow(VIEW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VIEW, 1280, 720)
    cv2.namedWindow(CTRL, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(CTRL, 520, 260)
    nothing = lambda _v: None
    cv2.createTrackbar("k1 x1000", CTRL, to_pos(init["k1"], K1_MIN, 0.001), to_pos(K1_MAX, K1_MIN, 0.001), nothing)
    cv2.createTrackbar("k2 x1000", CTRL, to_pos(init["k2"], K2_MIN, 0.001), to_pos(K2_MAX, K2_MIN, 0.001), nothing)
    cv2.createTrackbar("zoom x100", CTRL, to_pos(init["zoom"], ZOOM_MIN, 0.01), to_pos(ZOOM_MAX, ZOOM_MIN, 0.01), nothing)
    cv2.createTrackbar("shift x %", CTRL, to_pos(init["shift_x"], -SHIFT_MAX, 0.01), to_pos(SHIFT_MAX, -SHIFT_MAX, 0.01), nothing)
    cv2.createTrackbar("shift y %", CTRL, to_pos(init["shift_y"], -SHIFT_MAX, 0.01), to_pos(SHIFT_MAX, -SHIFT_MAX, 0.01), nothing)

    show_grid = True
    show_raw = False
    last_params = None
    maps = None
    msg, msg_until = "", 0.0
    fps, n, t0 = 0.0, 0, time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(0.05)
            continue
        fh, fw = frame.shape[:2]

        k1 = K1_MIN + cv2.getTrackbarPos("k1 x1000", CTRL) * 0.001
        k2 = K2_MIN + cv2.getTrackbarPos("k2 x1000", CTRL) * 0.001
        zoom = ZOOM_MIN + cv2.getTrackbarPos("zoom x100", CTRL) * 0.01
        sx = -SHIFT_MAX + cv2.getTrackbarPos("shift x %", CTRL) * 0.01
        sy = -SHIFT_MAX + cv2.getTrackbarPos("shift y %", CTRL) * 0.01
        params = (fw, fh, round(k1, 3), round(k2, 3), round(zoom, 2), round(sx, 2), round(sy, 2))
        if params != last_params:
            maps = build_maps(*params)
            last_params = params

        out = frame.copy() if show_raw else cv2.remap(frame, maps[0], maps[1], cv2.INTER_LINEAR)
        if show_grid:
            draw_grid(out)

        n += 1
        if time.time() - t0 >= 1.0:
            fps, n, t0 = n / (time.time() - t0), 0, time.time()
        mode = "RAW (no correction)" if show_raw else "CORRECTED"
        put_label(out, f"cam{index} {fw}x{fh} {fps:4.1f}fps  {mode}", 26)
        put_label(out, f"k1={k1:+.3f}  k2={k2:+.3f}  zoom={zoom:.2f}  shift=({sx:+.2f},{sy:+.2f})", 50)
        put_label(out, "g:grid  o:raw/corrected  s:save  r:reset  c:next cam  q:quit", fh - 14)
        if time.time() < msg_until:
            put_label(out, msg, 74)
        cv2.imshow(VIEW, out)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if cv2.getWindowProperty(VIEW, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord("g"):
            show_grid = not show_grid
        elif key == ord("o"):
            show_raw = not show_raw
        elif key == ord("r"):
            cv2.setTrackbarPos("k1 x1000", CTRL, to_pos(-0.20, K1_MIN, 0.001))
            cv2.setTrackbarPos("k2 x1000", CTRL, to_pos(0.0, K2_MIN, 0.001))
            cv2.setTrackbarPos("zoom x100", CTRL, to_pos(1.0, ZOOM_MIN, 0.01))
            cv2.setTrackbarPos("shift x %", CTRL, to_pos(0.0, -SHIFT_MAX, 0.01))
            cv2.setTrackbarPos("shift y %", CTRL, to_pos(0.0, -SHIFT_MAX, 0.01))
        elif key == ord("s"):
            data = {
                "model": "opencv_radial_k1k2",
                "f_ratio": F_RATIO,
                "size": [fw, fh],
                "k1": round(k1, 3),
                "k2": round(k2, 3),
                "zoom": round(zoom, 2),
                "shift_x": round(sx, 2),
                "shift_y": round(sy, 2),
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(SAVE_PATH, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            msg, msg_until = f"saved: {SAVE_PATH}", time.time() + 3
            print(f"保存しました: {SAVE_PATH}  {data}")
        elif key == ord("c"):
            cap.release()
            for step in range(1, 6):
                nxt = (index + step) % 5
                c2 = open_camera(nxt, w, h)
                if c2 is not None:
                    index, cap = nxt, c2
                    break
            else:
                cap = open_camera(index, w, h)
            last_params = None
            print(f"カメラ{index}に切り替えました。")

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
