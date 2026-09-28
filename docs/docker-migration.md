# Migrasi Docker (Tahap 3)

Tanggal: 2026-09-26
Acuan: [project-audit.md](project-audit.md) §6 dan §9 Tahap 3. Kelanjutan dari [migration-stage1.md](migration-stage1.md).

Lingkup: **hanya containerisasi.** UI, API, struktur JSON, dan logika aplikasi tidak diubah; tidak ada file di `app/` maupun `static/` yang disentuh.

---

## Daftar Isi

1. [Ringkasan](#1-ringkasan)
2. [Arsitektur](#2-arsitektur)
3. [Cara Pakai](#3-cara-pakai)
4. [File yang Dibuat](#4-file-yang-dibuat), berisi isi lengkap dan alasan setiap konfigurasi
   - [Dockerfile](#41-dockerfile)
   - [docker-compose.yml](#42-docker-composeyml)
   - [deploy/nginx/polyview.conf](#43-deploynginxpolyviewconf)
   - [.dockerignore](#44-dockerignore)
   - [.env.example](#45-envexample)
5. [Hasil Pengujian](#5-hasil-pengujian)
6. [Perbedaan dengan Deploy Lama](#6-perbedaan-dengan-deploy-lama)
7. [Troubleshooting](#7-troubleshooting)
8. [Belum Dikerjakan / Langkah Berikutnya](#8-belum-dikerjakan--langkah-berikutnya)

---

## 1. Ringkasan

| Kebutuhan | Implementasi |
|---|---|
| Python 3.12-slim | `FROM python:3.12-slim` |
| Gunicorn | `gunicorn app.server:app`, worker & timeout dari env |
| Nginx container | Service `nginx` (`nginx:1.28-alpine`) |
| Healthcheck `/healthz` | `HEALTHCHECK` di Dockerfile (app), `healthcheck` di compose (nginx → app) |
| `restart: unless-stopped` | Di kedua service |
| `POLYVIEW_DATA_DIR=/data` | Di Dockerfile (`ENV`) dan compose (`environment`) |
| Volume development `./database3d:/data:ro` | `${POLYVIEW_HOST_DATA_DIR:-./database3d}:/data:ro` |

File baru:

```
polyview/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── deploy/
│   └── nginx/
│       └── polyview.conf
└── docs/
    └── docker-migration.md   (dokumen ini)
```

Juga diperbarui: bagian Docker di `README.md`.

---

## 2. Arsitektur

```
                 host:8080
Browser ───────────► ┌──────────────────── compose network "polyview_default" ─────────────────────┐
                     │                                                                             │
                     │  nginx (nginx:1.28-alpine) :80                                               │
                     │   ├─ /, /sw.js, /manifest.json,      ◄── ./static (ro) → /srv/polyview/static│
                     │   │  /favicon.ico, /static/*   → dilayani langsung dari disk                 │
                     │   └─ /api/*, /healthz, lainnya  → proxy ──► polyview:5000                   │
                     │                                                                             │
                     │  polyview (python:3.12-slim) :5000  (tidak di-publish ke host)              │
                     │   gunicorn app.server:app, user non-root                                    │
                     │   /data (ro) ◄── ${POLYVIEW_HOST_DATA_DIR:-./database3d}                    │
                     └─────────────────────────────────────────────────────────────────────────────┘
```

Urutan start: `polyview` start, lalu `/healthz` harus 200 (status **healthy**), baru `nginx` start.

---

## 3. Cara Pakai

### Development (data: `./database3d`)

```bash
docker compose up -d --build
# buka http://localhost:8080
docker compose logs -f
docker compose down
```

Tanpa `.env`, semua nilai memakai default, termasuk `./database3d` sebagai folder data.

### Production / data di lokasi lain

```bash
cp .env.example .env
# edit .env:
#   POLYVIEW_HOST_DATA_DIR=/mnt/vermax/arya_data/database/3dsmax
#   PUID / PGID = pemilik folder data (id -u ; id -g)
docker compose up -d --build
```

### Perintah berguna

| Perintah | Fungsi |
|---|---|
| `docker compose ps` | Status & health kedua container |
| `docker compose logs -f polyview` | Log Gunicorn (access + error) dan app |
| `docker compose restart polyview` | Restart app saja |
| `docker compose up -d --build` | Rebuild setelah mengubah `app/` atau `requirements.txt` |
| `docker compose restart nginx` | Setelah mengubah `deploy/nginx/polyview.conf` |

Perubahan pada `static/` langsung terlihat di nginx tanpa restart, karena folder itu di-bind-mount. Image app juga berisi salinan `static/`, jadi rebuild tetap diperlukan agar keduanya tetap sama.

---

## 4. File yang Dibuat

### 4.1 `Dockerfile`

```dockerfile
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
```

| Konfigurasi | Alasan |
|---|---|
| `FROM python:3.12-slim` | Sesuai kebutuhan dan versi Python di server lama (3.12.3). Varian `slim` jauh lebih kecil dari image penuh. Pillow tersedia sebagai wheel manylinux, jadi tidak butuh compiler/`build-essential`. Image akhir ±219 MB. |
| `ARG PUID/PGID` | Container membaca folder data milik host. Di Linux, UID di dalam container harus punya izin baca, jadi UID bisa disamakan dengan pemilik data saat build. Default 1000 = user pertama di kebanyakan distro. |
| `PYTHONDONTWRITEBYTECODE=1` | Tidak membuat `__pycache__` di container (yang tidak berguna karena filesystem image tidak persisten). |
| `PYTHONUNBUFFERED=1` | Output Python langsung muncul di `docker logs`, tidak tertahan buffer. |
| `PIP_NO_CACHE_DIR`, `PIP_DISABLE_PIP_VERSION_CHECK` | Cache pip tidak ikut tersimpan di layer image, dan tidak ada warning versi pip saat build. |
| `POLYVIEW_DATA_DIR=/data` | Sesuai kebutuhan. Didefinisikan juga di image supaya `docker run` tanpa compose tetap benar. |
| `GUNICORN_WORKERS=2` | Sama dengan deploy lama (`-w 2`). Bisa diubah lewat `.env`. |
| `GUNICORN_TIMEOUT=300` | **Memperbaiki audit B4.** Default Gunicorn 30 detik mematikan worker saat ZIP folder besar atau konversi TIF besar, sedangkan nginx menunggu 300 detik. Nilai ini disamakan dengan nginx. |
| `WORKDIR /srv/polyview` | Root project di dalam container. `app/` dan `static/` berdampingan, sesuai asumsi `PROJECT_DIR` di `server.py`. |
| `COPY requirements.txt` → `pip install` sebelum `COPY app/` | Urutan layer: dependensi jarang berubah, sehingga layer ter-cache. Mengubah kode hanya me-rebuild layer `COPY` (±1 detik). |
| `groupadd` / `useradd ... --no-create-home --shell /usr/sbin/nologin` | App berjalan sebagai **non-root**. Kalau ada celah di app, penyerang tidak menjadi root di container. User tidak butuh home maupun shell login. |
| `COPY static/` | Image tetap mandiri: bisa dijalankan tanpa nginx (`docker run -p 5000:5000 ...`) dan Flask tetap melayani UI. |
| `USER polyview` | Semua proses setelah ini (termasuk Gunicorn dan healthcheck) berjalan non-root. |
| `EXPOSE 5000` | Dokumentasi port. Port tidak di-publish ke host; di compose hanya nginx yang di-publish. |
| `HEALTHCHECK` via `python -c urllib...` | `python:slim` tidak punya `curl`/`wget`, dan menambahkannya menambah ukuran serta attack surface. `urlopen` melempar `HTTPError` untuk status ≥ 400, sehingga `/healthz` 503 (folder data tidak ada/tidak terbaca) membuat container **unhealthy**. Healthcheck ditaruh di Dockerfile supaya image membawa healthcheck-nya sendiri, dengan atau tanpa compose. |
| `--interval=30s --timeout=5s --start-period=10s --retries=3` | Cek setiap 30 detik. `start-period` memberi waktu Gunicorn boot. Butuh 3 kegagalan berturut-turut sebelum ditandai unhealthy, supaya tidak flapping. |
| `CMD ["sh", "-c", "exec gunicorn ..."]` | `sh -c` diperlukan supaya `$GUNICORN_WORKERS`/`$GUNICORN_TIMEOUT` di-expand saat runtime. `exec` membuat Gunicorn menggantikan shell sebagai **PID 1**, sehingga `SIGTERM` dari `docker stop` sampai ke Gunicorn dan shutdown berjalan graceful. |
| `app.server:app` | Entry point baru setelah Tahap 1 (`app/` adalah package). |
| `--bind 0.0.0.0:5000` | **Audit D4.** Di container, `127.0.0.1` tidak bisa dijangkau dari container nginx. |
| `--no-control-socket` | Gunicorn 25 membuat control socket di `~/.gunicorn/`. User container tidak punya home, sehingga muncul `Control server error: Permission denied` di log. Control socket tidak dibutuhkan karena lifecycle diurus Docker, jadi dinonaktifkan. |
| `--access-logfile - --error-logfile -` | Semua log ke stdout/stderr, dan terbaca lewat `docker compose logs`. |

### 4.2 `docker-compose.yml`

```yaml
name: polyview

services:
  polyview:
    build:
      context: .
      args:
        PUID: ${PUID:-1000}
        PGID: ${PGID:-1000}
    image: polyview:latest
    environment:
      POLYVIEW_DATA_DIR: /data
      GUNICORN_WORKERS: ${GUNICORN_WORKERS:-2}
      GUNICORN_TIMEOUT: ${GUNICORN_TIMEOUT:-300}
    volumes:
      # Development default: ./database3d. Production: set POLYVIEW_HOST_DATA_DIR di .env
      - ${POLYVIEW_HOST_DATA_DIR:-./database3d}:/data:ro
    # Tidak di-publish ke host; hanya dapat dijangkau nginx lewat jaringan compose
    expose:
      - "5000"
    # healthcheck (/healthz) didefinisikan di Dockerfile
    restart: unless-stopped

  nginx:
    image: nginx:1.28-alpine
    ports:
      - "${POLYVIEW_PORT:-8080}:80"
    volumes:
      - ./deploy/nginx/polyview.conf:/etc/nginx/conf.d/default.conf:ro
      - ./static:/srv/polyview/static:ro
    depends_on:
      polyview:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1/healthz"]
      interval: 30s
      timeout: 5s
      start_period: 5s
      retries: 3
    restart: unless-stopped
```

| Konfigurasi | Alasan |
|---|---|
| `name: polyview` | Nama project tetap (container `polyview-polyview-1`, `polyview-nginx-1`, network `polyview_default`), tidak bergantung pada nama folder. |
| `build.args PUID/PGID` | Meneruskan UID/GID dari `.env` ke Dockerfile. |
| `image: polyview:latest` | Memberi nama image hasil build, supaya bisa di-`docker run` langsung atau di-push ke registry. |
| `environment.POLYVIEW_DATA_DIR: /data` | Sesuai kebutuhan. Ditulis eksplisit (walaupun sudah ada di image) agar jelas dari compose file. |
| `GUNICORN_*: ${VAR:-default}` | Bisa di-tuning lewat `.env` tanpa rebuild image. |
| Tidak memakai `env_file` | Disengaja. `.env` hanya dipakai compose untuk substitusi `${...}`. Kalau `env_file: .env` dipakai, **semua** variabel (termasuk `POLYVIEW_HOST_DATA_DIR`, yaitu path host) ikut masuk ke container dan membingungkan. Variabel yang masuk container ditulis eksplisit. |
| `${POLYVIEW_HOST_DATA_DIR:-./database3d}:/data:ro` | Sesuai kebutuhan development `./database3d:/data:ro`, sekaligus bisa diarahkan ke path produksi lewat `.env` tanpa mengedit compose. **`:ro`** karena app tidak pernah menulis ke data. Ini juga lapisan keamanan tambahan: app tidak bisa mengubah atau menghapus aset walaupun ada bug. |
| `expose: 5000` (bukan `ports`) | Gunicorn **tidak** di-publish ke host. Semua akses harus lewat nginx (timeout, gzip, header). |
| `restart: unless-stopped` | Sesuai kebutuhan. Pengganti `Restart=always` di systemd: container naik lagi setelah crash atau reboot host, tetapi tetap mati kalau sengaja di-`docker compose stop`. |
| `nginx:1.28-alpine` | Nginx stable, varian Alpine yang kecil. Tag di-pin ke minor version supaya update tidak tiba-tiba mengubah perilaku. |
| `ports: ${POLYVIEW_PORT:-8080}:80` | Port 8080 sama dengan deploy lama, jadi bookmark/URL pengguna tetap berlaku. Bisa diubah lewat `.env`. |
| Mount `polyview.conf` → `/etc/nginx/conf.d/default.conf:ro` | Menggantikan default site nginx (yang menampilkan "Welcome to nginx"). |
| Mount `./static` → `/srv/polyview/static:ro` | Nginx melayani aset web langsung dari disk tanpa melewati Python. |
| `depends_on: condition: service_healthy` | Nginx baru start setelah `/healthz` app 200, sehingga tidak ada periode 502 saat startup. Kalau `/data` tidak terbaca, app unhealthy dan nginx tidak start (lihat [§7](#7-troubleshooting)). |
| Healthcheck nginx `wget ... /healthz` | Memeriksa **seluruh jalur** (nginx, proxy, app, folder data), bukan hanya "nginx hidup". `wget` (busybox) sudah ada di Alpine; `-q -O /dev/null` membuat exit code ≠ 0 untuk status ≥ 400. |

### 4.3 `deploy/nginx/polyview.conf`

```nginx
# PolyView — Nginx di dalam docker compose
# Dimount ke /etc/nginx/conf.d/default.conf (menggantikan default site nginx).
#
# - Aset web (static/) dilayani langsung dari disk: /, /sw.js, /manifest.json, /favicon.ico, /static/*
# - Selain itu (/api/*, /healthz, dan URL lain) di-proxy ke Gunicorn

upstream polyview_app {
    server polyview:5000;
}

server {
    listen 80;
    server_name _;

    root /srv/polyview/static;

    # Timeout panjang untuk file besar, ZIP folder, dan konversi TIF.
    # Samakan dengan GUNICORN_TIMEOUT.
    proxy_read_timeout    300s;
    proxy_connect_timeout 60s;
    proxy_send_timeout    300s;

    # Kompresi respons teks (JSON /api/tree bisa besar). File biner tidak dikompres.
    gzip            on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_proxied    any;
    gzip_vary       on;
    gzip_types      application/json application/javascript application/manifest+json text/css;

    # ── Aset web (sama dengan route Flask) ─────────────────────

    location = / {
        try_files /index.html =404;
    }

    # Service Worker — wajib no-cache + header scope
    location = /sw.js {
        types { } default_type application/javascript;
        add_header Cache-Control "no-cache" always;
        add_header Service-Worker-Allowed "/" always;
        try_files /sw.js =404;
    }

    # Manifest PWA
    location = /manifest.json {
        types { } default_type application/manifest+json;
        add_header Cache-Control "public, max-age=3600" always;
        try_files /manifest.json =404;
    }

    location = /favicon.ico {
        try_files /icons/favicon.ico =404;
    }

    location /static/ {
        alias /srv/polyview/static/;
    }

    # ── Aplikasi ───────────────────────────────────────────────

    location / {
        proxy_pass         http://polyview_app;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # Download besar langsung di-stream ke klien
        proxy_buffering         off;
        proxy_request_buffering off;
    }
}
```

Diadaptasi dari `polyview.nginx.conf` (deploy lama). Perubahannya:

| Konfigurasi | Alasan |
|---|---|
| `upstream polyview_app { server polyview:5000; }` | Di compose, app dijangkau lewat **nama service** (DNS internal Docker), bukan `127.0.0.1:5000`. |
| `listen 80` | Port di dalam container. Port host (8080) diatur di compose, sehingga config nginx tidak perlu tahu port host. |
| `root /srv/polyview/static` | Titik mount `./static`. |
| `proxy_*_timeout 300s/60s/300s` | Dipertahankan dari config lama dan disamakan dengan `GUNICORN_TIMEOUT` (audit B4). |
| `gzip ...` | **Baru.** `/api/tree` untuk `database3d` turun dari 9.477 B menjadi 1.691 B (−82%); untuk database produksi yang jauh lebih besar dampaknya lebih terasa. `gzip_types` sengaja **tidak** mencakup `application/octet-stream`, `image/*`, dan `application/zip`: FBX/gambar/ZIP sudah terkompresi atau besar, sehingga kompresi hanya membuang CPU. `gzip_proxied any` diperlukan agar respons dari Gunicorn ikut dikompres. `gzip_vary` menambahkan `Vary: Accept-Encoding` untuk cache perantara. Isi JSON tidak berubah; ini hanya encoding transport yang di-decode otomatis oleh browser. |
| `location = /` → `index.html` | Sama dengan route Flask `/`. `/index.html` sendiri **sengaja tidak** dilayani nginx dan diteruskan ke Flask (404), supaya perilakunya sama persis dengan Flask (lihat [§8](#8-belum-dikerjakan--langkah-berikutnya) tentang SW). |
| `location = /sw.js` + `types { } default_type application/javascript` | Header `Service-Worker-Allowed: /` dan `Cache-Control: no-cache` **identik dengan Flask**. Karena nginx yang melayani file ini, header tidak lagi dobel (Flask + nginx), sehingga **audit B9 teratasi**. `always` memastikan header tetap dikirim pada respons 304. |
| `location = /manifest.json` + `default_type application/manifest+json` | `mime.types` nginx memetakan `.json` ke `application/json`. Override ini mempertahankan MIME yang sama dengan Flask. `max-age=3600` dipertahankan dari config lama. |
| `location = /favicon.ico` → `icons/favicon.ico` | Sama dengan route Flask. |
| `location /static/` + `alias` | Sama dengan URL `/static/...` milik Flask. Hanya isi `static/` yang terbuka, dan nginx menormalisasi `../`. |
| `location /` → proxy | Semua yang bukan aset web (`/api/*`, `/healthz`, URL tak dikenal) diteruskan ke Flask, sehingga 404/403 tetap berasal dari Flask seperti sebelumnya. |
| `proxy_set_header Host / X-Real-IP / X-Forwarded-*` | Dipertahankan dari config lama. |
| `proxy_buffering off`, `proxy_request_buffering off` | Dipertahankan: download file besar di-stream langsung, tidak ditampung dulu di disk nginx. |
| **Dihapus:** `client_max_body_size 500M` | Tidak ada endpoint upload (audit §4). |
| **Dihapus:** `location ~* \.(css\|woff2?)$` | Tidak ada file CSS/WOFF yang dilayani origin (audit §4). |
| **Dihapus:** blok `/sw.js` & `/manifest.json` versi proxy | Diganti dengan melayani langsung dari disk. |

> Alasan nginx melayani aset statis: Gunicorn memakai *sync worker* (2 worker). Setiap request ikon/HTML yang melewati Python memakan slot worker yang sama dengan download besar. Dengan nginx melayani aset, worker Gunicorn hanya dipakai untuk API.

### 4.4 `.dockerignore`

```gitignore
# Hanya app/, static/, dan requirements.txt yang dibutuhkan image.
# Yang lain dikecualikan agar build context kecil dan tidak ada data/rahasia yang ikut.

# Data 3D (di-mount sebagai volume, bukan di-bake ke image)
database3d/

# Environment lokal & artefak Python
venv/
.venv/
__pycache__/
**/__pycache__/
*.pyc

# Rahasia / konfigurasi lokal
.env
.env.*

# VCS, editor, OS
.git/
.gitignore
.gitattributes
.vscode/
.idea/
.DS_Store
Thumbs.db
desktop.ini

# Dokumentasi & file deploy (tidak dipakai di dalam image)
docs/
deploy/
README.md
Dockerfile
.dockerignore
docker-compose*.yml
polyview.service
polyview.nginx.conf
```

| Entri | Alasan |
|---|---|
| `database3d/` | ±454 MB data. Tanpa entri ini, **setiap build** mengirim semuanya ke Docker daemon. Data harus di-mount sebagai volume, bukan dimasukkan ke image. |
| `venv/`, `__pycache__/`, `*.pyc` | `venv/` ±102 MB berisi binary Linux yang tidak portable; image meng-install dependensinya sendiri dari `requirements.txt`. |
| `.env`, `.env.*` | Mencegah konfigurasi lokal atau rahasia ikut ter-bake ke image. |
| `.git/`, editor, OS | Tidak dibutuhkan saat runtime; `.git` bisa berukuran besar. |
| `docs/`, `deploy/`, `Dockerfile`, compose, file systemd/nginx lama | Tidak dipakai di dalam image. Mengecualikannya juga berarti mengedit dokumentasi atau config nginx tidak meng-invalidate cache build. |

Hasil: build context turun dari ±556 MB menjadi **468 KB** (12 file: `app/`, `static/`, `requirements.txt`).

### 4.5 `.env.example`

```dotenv
# Salin ke .env lalu sesuaikan:  cp .env.example .env
# docker compose membaca .env secara otomatis (untuk substitusi ${VAR} di docker-compose.yml).

# Folder data 3D di HOST, di-mount read-only ke /data di container.
# Development: ./database3d   Production: mis. /mnt/vermax/arya_data/database/3dsmax
POLYVIEW_HOST_DATA_DIR=./database3d

# Port di host untuk mengakses PolyView (lewat nginx)
POLYVIEW_PORT=8080

# Gunicorn
GUNICORN_WORKERS=2
# detik; samakan dengan proxy_read_timeout di deploy/nginx/polyview.conf
GUNICORN_TIMEOUT=300

# UID/GID user aplikasi di container (build arg). Harus bisa membaca folder data.
# Cek di host: id -u ; id -g
PUID=1000
PGID=1000
```

| Variabel | Alasan |
|---|---|
| `POLYVIEW_HOST_DATA_DIR` | Path **host**. Sengaja diberi nama berbeda dari `POLYVIEW_DATA_DIR` (path **container**, selalu `/data`) supaya keduanya tidak tertukar. |
| `POLYVIEW_PORT` | Port publik. Default 8080 sama dengan deploy lama. |
| `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT` | Tuning tanpa rebuild. |
| `PUID`, `PGID` | Build arg untuk izin baca volume di host Linux. Mengubahnya butuh `--build`. |
| Semua nilai = default compose | Tanpa `.env` pun stack langsung jalan untuk development. `.env.example` berfungsi sebagai dokumentasi dan template. `.env` sendiri sudah ada di `.gitignore`. |

---

## 5. Hasil Pengujian

Lingkungan: WSL Ubuntu, Docker 29.6.2, Compose v5.3.1, data asli `./database3d`, port uji 18080.

**Build & start**

| Cek | Hasil |
|---|---|
| `docker compose config` | valid |
| Build image | berhasil, `polyview:latest` ±219 MB |
| Build context | 468 KB, 12 file (`.dockerignore` bekerja) |
| Urutan start | `polyview` **healthy**, lalu `nginx` start, lalu `nginx` **healthy** |
| Restart policy | kedua container `unless-stopped` |
| User app | `uid=1000(polyview)`, bukan root |
| Volume `/data` | `touch /data/x` gagal: *Read-only file system* |
| Env di container | `POLYVIEW_DATA_DIR=/data`, `GUNICORN_WORKERS=2`, `GUNICORN_TIMEOUT=300` |
| Log Gunicorn | bersih (setelah `--no-control-socket`), access log muncul di `docker compose logs` |
| Container tanpa volume data | `/healthz` 503, container ditandai unhealthy |

**Route lewat nginx (port 18080)**

| Request | Hasil |
|---|---|
| `/` | 200 `text/html` |
| `/manifest.json` | 200 `application/manifest+json`, `Cache-Control: public, max-age=3600` |
| `/sw.js` | 200 `application/javascript`, `Cache-Control: no-cache`, `Service-Worker-Allowed: /`, masing-masing **sekali** |
| `/favicon.ico` | 200 |
| `/static/icons/*.png` | 200 `image/png` |
| `/healthz` | 200 `{"data_dir":true,"status":"ok"}` |
| `/api/tree` | 200 JSON; gzip 1.691 B vs plain 9.477 B |
| `/api/file/AS 365 N3/AS 365 N3.fbx` | 200 `application/octet-stream` (479 KB) |
| `/api/file/AS 365 N3/AS 365 N3.tif` | 200 `image/png`, dikonversi Pillow (1,6 MB) |
| `/api/file/.../82908_1506146893.jpg` | 200 `image/jpeg` |
| `/api/download/.../AS 365 N3.max` | 200 (1,9 MB) |
| `/api/download/AS 365 N3` (folder) | 200 `application/zip` 7,9 MB, isi 4 file dengan path yang benar |
| `/index.html`, `/polyview.png` | 404 (sama seperti Flask) |
| `/static/server.py`, `/static/../app/server.py` | 404 |
| `/api/file/../../etc/passwd` | 403 (`safe_path`) |

**Kesamaan respons nginx vs Flask langsung** (sha256 isi respons):

| Path | Hasil |
|---|---|
| `/`, `/sw.js`, `/manifest.json`, `/favicon.ico`, `/static/icons/icon-192.png`, `/api/tree` | **identik** |

Belum diuji: tampilan & preview 3D di browser, serta deploy di server produksi (izin baca `/mnt/vermax/...` dengan UID container).

---

## 6. Perbedaan dengan Deploy Lama

| Aspek | Lama (systemd) | Baru (Docker) |
|---|---|---|
| Menjalankan | `systemctl start polyview` + nginx host | `docker compose up -d` |
| Python / dependensi | `venv/` di server | Di dalam image, dari `requirements.txt` |
| User | `windy` (akun personal) | `polyview` (UID dari `PUID`) |
| Data | Path hardcode | Volume `:ro`, path dari `.env` |
| Gunicorn timeout | 30 detik (default) | 300 detik |
| Aset statis | Lewat Flask | Langsung nginx |
| Header `/sw.js` | Dobel (Flask + nginx) | Sekali |
| gzip | Tidak | Ya (teks/JSON) |
| Port publik | 8080 | 8080 (default) |
| Health check | Tidak ada | `/healthz` di app & nginx |
| Restart | `Restart=always` | `restart: unless-stopped` |

`polyview.service` dan `polyview.nginx.conf` di root **tidak dihapus**. Keduanya masih berlaku untuk deploy non-Docker. Setelah Docker berjalan di produksi, keduanya bisa dipindah ke `deploy/legacy/` atau dihapus.

**Migrasi dari server lama:**
1. `sudo systemctl disable --now polyview` dan nonaktifkan site nginx lama (`/etc/nginx/sites-enabled/polyview`), karena port 8080 dipakai compose.
2. Buat `.env`: `POLYVIEW_HOST_DATA_DIR=/mnt/vermax/arya_data/database/3dsmax`, `PUID`/`PGID` sesuai pemilik data.
3. `docker compose up -d --build`, lalu `docker compose ps` (keduanya harus *healthy*).

---

## 7. Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| `nginx` tidak start, `polyview` **unhealthy** | `/healthz` 503: `/data` tidak bisa dibaca oleh user container. Samakan `PUID`/`PGID` dengan pemilik data (`stat -c '%u:%g' <folder>`), lalu `docker compose up -d --build`. |
| Semua healthy tetapi tree **kosong** | `POLYVIEW_HOST_DATA_DIR` salah ketik atau path tidak ada. Pada bind mount, Docker **membuat folder kosong** di host untuk path yang tidak ada, sehingga `/healthz` tetap 200. Cek `.env`, lalu `docker compose exec polyview ls -la /data`, dan hapus folder kosong yang terlanjur dibuat. |
| `/api/tree` error 500 | Ada subfolder/file yang tidak terbaca atau symlink rusak di data (audit B2). Cek izin dengan `docker compose exec polyview ls -laR /data`. |
| Build gagal di `groupadd: GID ... already exists` | `PGID` bentrok dengan grup bawaan image (mis. 100 = `users`). Pakai GID lain, atau beri izin baca "others" pada folder data. |
| `port is already allocated` | Port 8080 masih dipakai nginx host atau service lain. Matikan, atau ganti `POLYVIEW_PORT`. |
| 504 Gateway Timeout saat download ZIP besar | Butuh lebih dari 300 detik. Naikkan `GUNICORN_TIMEOUT` **dan** `proxy_read_timeout`/`proxy_send_timeout` di `deploy/nginx/polyview.conf` bersamaan. |
| Perubahan di `app/` tidak terlihat | Kode app ada di dalam image: `docker compose up -d --build`. |

---

## 8. Belum Dikerjakan / Langkah Berikutnya

Di luar lingkup Tahap 3 (tidak mengubah app):

1. **HTTPS**: syarat PWA dan service worker di luar `localhost`. Pasang di reverse proxy host (Traefik/Caddy/NPM) di depan port 8080, atau tambahkan Caddy di compose.
2. **Service worker tidak pernah ter-install** (precache `/index.html` yang 404, lihat [migration-stage1.md](migration-stage1.md)). Ditangani di tahap PWA.
3. **Autentikasi** (audit S1): nginx sekarang titik yang tepat untuk Basic Auth atau pembatasan IP (`allow`/`deny`).
4. ZIP folder masih dibuat di RAM (audit B3). Batasi memori container (`mem_limit`) setelah pola pemakaian diketahui.
5. Pindahkan `polyview.service` & `polyview.nginx.conf` ke `deploy/legacy/` setelah deploy Docker stabil.
