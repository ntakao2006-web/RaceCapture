FROM ghcr.io/arduino/app-bricks/python-apps-base:0.5.0
WORKDIR /app
COPY --chown=1000:1000 vendor /app/vendor
ENV PYTHONPATH=/app/vendor
COPY --chown=1000:1000 podium.py sim7070.py hardware.py sd_storage.py sd_timestamp.py sd_decode.py server.py models.py public_server.py telemetry_bridge.py ncec.py /app/
COPY --chown=1000:1000 web /app/web
COPY --chown=1000:1000 public /app/public
ENV PYTHONPYCACHEPREFIX=/tmp/pycache
RUN python3 -m compileall -q /app/server.py /app/models.py /app/public_server.py
ENV ECOCAPTURE_DATA=/data PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--ws-per-message-deflate", "false"]
