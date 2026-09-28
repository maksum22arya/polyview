# PolyView — image aplikasi (Flask + Gunicorn)
FROM python:3.12-slim

# UID/GID user aplikasi; samakan dengan pemilik folder data di host
ARG PUID=1000
ARG PGID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POLYVIEW_DATA_DIR=/data \
    GUNICORN_WORKERS=2 \
    GUNICORN_TIMEOUT=300

WORKDIR /srv/polyview

# Dependensi dulu agar layer ini ter-cache selama requirements.txt tidak berubah
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN groupadd --gid "${PGID}" polyview \
 && useradd --uid "${PUID}" --gid polyview --no-create-home --shell /usr/sbin/nologin polyview

COPY app/ app/
COPY static/ static/

USER polyview

EXPOSE 5000

# python:slim tidak punya curl/wget; urlopen melempar error untuk status >= 400 (mis. 503)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=4)"]

CMD ["sh", "-c", "exec gunicorn app.server:app --bind 0.0.0.0:5000 --workers \"$GUNICORN_WORKERS\" --timeout \"$GUNICORN_TIMEOUT\" --no-control-socket --access-logfile - --error-logfile -"]
