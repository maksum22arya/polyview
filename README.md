# PolyView

Web app untuk menjelajahi dan melihat pratinjau file 3D di server lokal.

- Pohon folder dari satu direktori data
- Preview **FBX** / **OBJ** (Three.js) dan gambar **PNG / JPG / TIF** (TIF dikonversi ke PNG di server)
- Download file, atau folder sebagai ZIP
- UI dua bahasa (ID/EN), responsif, dapat di-install sebagai PWA (butuh HTTPS)

## Struktur

```
polyview/
├── app/
│   ├── __init__.py
│   └── server.py          # backend Flask (API + melayani aset web)
├── static/                # semua aset web
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js
│   └── icons/
├── deploy/nginx/          # config nginx untuk docker compose
├── docs/                  # audit & catatan migrasi
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── polyview.nginx.conf    # contoh reverse proxy (deploy non-Docker)
└── polyview.service       # contoh unit systemd (deploy non-Docker)
```

## Konfigurasi

| Environment variable | Default | Keterangan |
|---|---|---|
| `POLYVIEW_DATA_DIR` | `/data` | Folder yang dijelajahi. App hanya membaca, tidak pernah menulis. |

## Menjalankan dengan Docker (disarankan)

```bash
cp .env.example .env        # opsional; tanpa .env data diambil dari ./database3d
docker compose up -d --build
# buka http://localhost:8080
```

Folder data di host diatur lewat `POLYVIEW_HOST_DATA_DIR` di `.env` dan di-mount read-only ke `/data`. Detail lengkap ada di [docs/docker-migration.md](docs/docker-migration.md).

## Menjalankan tanpa Docker

Butuh Python 3.12+.

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt

export POLYVIEW_DATA_DIR=/path/ke/folder/3d
```

**Development** (Flask debug server, `127.0.0.1:5000`):

```bash
python3 app/server.py
```

**Production** (dari root project):

```bash
gunicorn -w 2 -b 127.0.0.1:5000 app.server:app
```

Lalu pasang Nginx sebagai reverse proxy di depannya; lihat [polyview.nginx.conf](polyview.nginx.conf). Untuk systemd, lihat [polyview.service](polyview.service).

## Endpoint

| Route | Keterangan |
|---|---|
| `/` | UI (`static/index.html`) |
| `/manifest.json`, `/sw.js`, `/favicon.ico` | Aset PWA, dilayani dari root agar scope service worker benar |
| `/static/...` | Aset statis lain (ikon, dll.) |
| `/healthz` | Health check: `200 {"status":"ok"}` jika folder data bisa dibaca, `503` jika tidak. Tidak men-scan isi folder. |
| `/api/tree` | Pohon folder lengkap (JSON) |
| `/api/file/<path>` | Isi file untuk preview (TIF dikonversi ke PNG). `?alpha=1`: TIF 4-channel dikirim dengan alpha (dipakai untuk tekstur model 3D) |
| `/api/download/<path>` | Download file, atau folder sebagai ZIP |

## Test

```bash
python -m unittest discover -s tests -v
```

## Changelog

**2026-09-26: Perbaikan layout PWA iOS (Add to Home Screen)**
- Area kosong di bawah aplikasi pada iPhone mode standalone dihilangkan; panel kini sampai ke tepi layar.
- Status bar menyatu dengan warna header; tombol Download, hint 3D, dan daftar file tetap di atas home indicator.
- Landscape: isi header, sidebar, dan tombol Download tidak lagi tertutup notch.
- Hanya CSS; Safari biasa & desktop tidak berubah. Detail: [docs/ios-pwa-safe-area-fix.md](docs/ios-pwa-safe-area-fix.md)

**2026-09-26: Perbaikan rendering material FBX**
- Model dengan alpha/cutout mask dari 3ds Max (mis. kapal Bharata, Bisma) tidak lagi tampil tembus pandang; mask kini diperlakukan sebagai lubang (cutout).
- Material FBX dirender dua sisi, sehingga bagian tipis tidak hilang dari belakang.
- Server mempertahankan channel alpha TIF, hanya untuk tekstur model 3D (`?alpha=1`). Preview gambar dan download tidak berubah.
- Detail: [docs/material-rendering-fix.md](docs/material-rendering-fix.md)

## Dokumentasi

- [docs/project-audit.md](docs/project-audit.md): audit project dan rencana migrasi
- [docs/migration-stage1.md](docs/migration-stage1.md): perubahan Tahap 1 & 2
- [docs/docker-migration.md](docs/docker-migration.md): Docker Compose (Tahap 3)
- [docs/material-rendering-audit.md](docs/material-rendering-audit.md), [docs/material-rendering-summary.md](docs/material-rendering-summary.md), [docs/material-rendering-fix.md](docs/material-rendering-fix.md): material FBX
- [docs/ios-pwa-safe-area-audit.md](docs/ios-pwa-safe-area-audit.md), [docs/ios-pwa-safe-area-fix.md](docs/ios-pwa-safe-area-fix.md): layout PWA iOS
