# live_bridge.py（地図ページ・G-G・VictoriaMetricsへの書き込み・Grafana Live）。
# 5BはPython 3.13.5＋websockets 15.0.1で動いている
FROM python:3.13-slim
RUN pip install --no-cache-dir websockets==15.0.1 \
 && mkdir /data && chown 1000:1000 /data   # 名前付きボリュームはこの所有者で作られる
WORKDIR /app
COPY live_bridge.py map.html gg.html owntracks.html ./
USER 1000:1000
ENTRYPOINT ["python", "-u", "live_bridge.py"]
