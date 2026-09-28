# Migrasi Tahap 1 & 2: Struktur, Path, Konfigurasi

Tanggal: 2026-09-26
Acuan: [project-audit.md](project-audit.md) §9, Tahap 1 (Rapikan struktur & path) dan Tahap 2 (Dependensi).

Lingkup: **hanya struktur, path, dan konfigurasi.** UI, fitur, dan cara kerja API tidak diubah.
Dockerfile dan docker-compose.yml **belum** dibuat.

---

## Ringkasan

| Tujuan | Status |
|---|---|
| Memperbaiki path yang rusak akibat perpindahan folder | ✅ |
| Memindahkan seluruh referensi aset statis ke `static/` | ✅ |
| `BASE_DIR` dibaca dari env `POLYVIEW_DATA_DIR` (default `/data`) | ✅ |
| Endpoint `/healthz` | ✅ |
| `requirements.txt` | ✅ |
| Mengganti `print` dengan `logging` | ✅ |
| Memperbarui `README.md` | ✅ |

---

## Daftar Perubahan File

| File | Aksi |
|---|---|
| `index.html` → `static/index.html` | **Dipindah** (isi hanya berubah pada referensi ikon, lihat di bawah) |
| `app/server.py` | Diubah: path, konfigurasi, logging, route `/healthz`, hapus route `/polyview.png` |
| `app/__init__.py` | **Baru** (kosong), agar `app.server:app` bisa di-import sebagai package |
| `static/manifest.json` | Diubah: path ikon |
| `polyview.service` | Diubah: target Gunicorn dan env data dir |
| `requirements.txt` | **Baru** |
| `README.md` | Diisi (sebelumnya kosong) |
| `docs/migration-stage1.md` | **Baru** (dokumen ini) |

Tidak disentuh: `static/sw.js`, `polyview.nginx.conf`, `.gitignore`, `static/icons/*`, `venv/`, `__pycache__/`.

---

## Detail Perubahan

### 1. `app/server.py`

**Path dan konfigurasi.** Semua path kini absolut, dihitung dari lokasi file. Hasilnya tidak bergantung pada working directory:

```python
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR  = os.path.join(PROJECT_DIR, 'static')
ICONS_DIR   = os.path.join(STATIC_DIR, 'icons')
BASE_DIR    = os.environ.get('POLYVIEW_DATA_DIR') or '/data'
```

- Sebelumnya: `BASE_DIR = os.path.expanduser('/mnt/vermax/arya_data/database/3dsmax')` (hardcode).
- `POLYVIEW_DATA_DIR` yang tidak diset **atau kosong** akan memakai default `/data`.

**Flask static folder.**

| | Sebelum | Sesudah |
|---|---|---|
| Deklarasi | `Flask(__name__, static_folder='.')` | `Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')` |
| Isi yang terbuka di `/static/...` | Seluruh folder modul (termasuk `server.py`) | Hanya isi `static/` |

Ini sekaligus menutup temuan audit **S2** (source code bisa di-download lewat `/static/server.py`).

**Route.**

| Route | Sebelum | Sesudah |
|---|---|---|
| `/` | `send_from_directory('.', 'index.html')`, sehingga 404 | `STATIC_DIR/index.html` |
| `/manifest.json` | dari `'.'`, sehingga 404 | `STATIC_DIR/manifest.json` (mimetype tetap `application/manifest+json`) |
| `/sw.js` | dari `'.'`, sehingga 404 | `STATIC_DIR/sw.js` (header `Service-Worker-Allowed: /` dan `Cache-Control: no-cache` tetap) |
| `/favicon.ico` | `BASE_PATH` tidak terdefinisi, sehingga **500 NameError** | `static/icons/favicon.ico` |
| `/polyview.png` | melayani file yang tidak ada, sehingga 404 | **Dihapus**; semua referensi dipindah ke `/static/icons/*` |
| `/healthz` | — | **Baru** (lihat di bawah) |
| `/api/tree`, `/api/file/<path>`, `/api/download/<path>` | — | **Tidak diubah** |

**`/healthz`.** Endpoint ringan untuk health check container/monitoring. Endpoint ini **tidak** men-scan isi folder.

```
200  {"status": "ok",    "data_dir": true}    folder data ada dan bisa dibaca
503  {"status": "error", "data_dir": false}   folder data tidak ada / tidak bisa dibaca
```

**Logging.** `print()` diganti `logging` (logger `polyview`, level INFO, output ke stderr). Isi pesannya tetap sama.

**Docstring** diperbarui: cara menjalankan (`app.server:app`), env var, dan `requirements.txt`.

### 2. `static/index.html`

Hanya tiga referensi ikon yang diubah. Referensi lama menunjuk `/polyview.png`, file yang tidak ada:

| Elemen | Sebelum | Sesudah |
|---|---|---|
| `<link rel="apple-touch-icon">` | `/polyview.png?v=2` | `/static/icons/apple-touch-icon.png` |
| `<link rel="icon">` | `/polyview.png?v=2` | `/static/icons/icon-192.png` |
| `<img>` logo di header | `/polyview.png?v=2` | `/static/icons/icon-192.png` |

Komentar basi `<!-- Apple touch icon fallback (inline SVG ...) -->` juga dihapus. Tidak ada perubahan pada CSS, layout, ataupun JS.

> Dampak visual: logo di header dan favicon yang sebelumnya **gambar rusak** (404) kini tampil memakai ikon dari `static/icons/`.

### 3. `static/manifest.json`

| Sebelum | Sesudah |
|---|---|
| 2 entri `/polyview.png` (file tidak ada), `purpose: "any maskable"` | `/static/icons/icon-192.png` (any), `/static/icons/icon-512.png` (any), `/static/icons/icon-maskable-512.png` (maskable) |

Pemisahan `any`/`maskable` diperlukan karena kini ada file maskable tersendiri. Ikon biasa yang ditandai `maskable` akan terpotong di Android.

### 4. `polyview.service` (deploy systemd lama)

Diperbarui agar tetap berfungsi dengan struktur baru:

```diff
 Environment="PATH=/var/www/polyview/venv/bin"
+# folder data yang dijelajahi (default di kode: /data)
+Environment="POLYVIEW_DATA_DIR=/mnt/vermax/arya_data/database/3dsmax"
 ...
-    server:app
+    app.server:app
```

`WorkingDirectory=/var/www/polyview` tetap, dan harus menunjuk ke **root project** (folder yang berisi `app/` dan `static/`).

### 5. `requirements.txt` (baru)

```
flask==3.1.*
pillow==12.*
gunicorn==25.*
```

Rentang versi mengikuti audit §9 Tahap 2 (patch-level fleksibel dalam satu minor/major). Versi yang terakhir dipakai di server lama (`venv/`): Flask 3.1.3, Pillow 12.2.0, Gunicorn 25.3.0.

---

## ⚠️ Yang Perlu Diperhatikan Saat Deploy

1. **Default data dir berubah menjadi `/data`.** Deploy yang tidak men-set `POLYVIEW_DATA_DIR` akan menampilkan tree kosong/error. Unit systemd sudah diperbarui. Kalau menjalankan manual, set env-nya terlebih dahulu.
2. **Perintah Gunicorn berubah**: `server:app` menjadi `app.server:app`, dan dijalankan dari **root project**.
3. **Mode dev**: `python3 server.py` menjadi `python3 app/server.py` (dari root project).
4. URL `/polyview.png` dan `/static/<file backend>` kini 404. Ini disengaja.

---

## Hasil Pengujian

Diuji di WSL Ubuntu (Python 3.14, venv sementara di `/tmp`, dihapus setelah selesai): `pip install -r requirements.txt` → Flask 3.1.3, Gunicorn 25.3.0, Pillow 12.3.0. Gunicorn dijalankan dengan `app.server:app` dari root project, memakai folder data uji (`sub/tri.obj`, `sub/tex.tif`).

| Request | Hasil |
|---|---|
| `/` | 200 `text/html` |
| `/manifest.json` | 200 `application/manifest+json` |
| `/sw.js` | 200, header `Service-Worker-Allowed: /` dan `Cache-Control: no-cache` |
| `/favicon.ico` | 200 `image/vnd.microsoft.icon` |
| `/static/icons/{icon-192,icon-512,icon-maskable-512,apple-touch-icon}.png` | 200 `image/png` |
| `/healthz` (data ada) | 200 `{"data_dir":true,"status":"ok"}` |
| `/healthz` (env tidak diset, `/data` tidak ada) | 503 `{"data_dir":false,"status":"error"}` |
| `/api/tree` | 200, struktur JSON sama seperti sebelumnya |
| `/api/file/sub/tri.obj` | 200 `application/octet-stream` |
| `/api/file/sub/tex.tif` | 200 `image/png` (konversi Pillow jalan) |
| `/api/download/sub/tri.obj` | 200 |
| `/api/download/sub` | 200 `application/zip`, isi `sub/tex.tif`, `sub/tri.obj` |
| `/polyview.png` | 404 (route dihapus) |
| `/static/server.py`, `/static/../app/server.py` | 404 (source tidak lagi terbuka) |
| `/api/file/../../etc/passwd` | 403 (`safe_path` tetap bekerja) |
| `python3 app/server.py` (mode dev) | `/` 200; log muncul lewat `logging` |

Pengujian dijalankan dengan `PYTHONDONTWRITEBYTECODE=1`, sehingga tidak ada `__pycache__` baru di project.

Belum diuji: tampilan di browser, preview FBX (butuh CDN + WebGL), dan deploy lewat Nginx/systemd di server asli.

---

## Temuan Selama Migrasi (belum diperbaiki, di luar lingkup)

1. **Service worker tidak pernah berhasil ter-install, sejak sebelum migrasi.** `SHELL` di `sw.js` mem-precache `'/index.html'`, tetapi route itu tidak pernah ada (hanya `/` dan `/static/index.html`). `cache.addAll()` gagal, sehingga SW gagal install. Ini **tidak** diperbaiki di tahap ini: memperbaikinya akan mengaktifkan SW dengan strategi cache-first yang bermasalah (audit P1: pengguna terjebak di versi lama). Sebaiknya ditangani bersama perbaikan SW di tahap PWA.
2. **`/api/tree` mengembalikan 500 jika folder data tidak ada** (`FileNotFoundError` tidak ditangkap; audit B2). Perilaku ini sama seperti sebelumnya dan sengaja tidak diubah. `/healthz` sudah memberi sinyal 503 untuk kondisi ini.
3. **Folder baru `database3d/`** (71 file, ±454 MB: `.max`, `.fbx`, `.tif`, dll.) muncul di root project selama pengerjaan. Folder ini bukan dibuat oleh migrasi ini. Folder data sebesar ini **tidak boleh masuk repository** dan belum ada di `.gitignore`. Untuk development lokal, folder ini bisa dipakai sebagai `POLYVIEW_DATA_DIR=./database3d`, dan nantinya di-mount sebagai volume `/data` di Docker.
4. Header ganda di `/sw.js` (Flask + Nginx, audit B9) dan konfigurasi Nginx lain belum diubah; ini dijadwalkan di Tahap 3.

---

## Langkah Berikutnya

- **Tahap 0** (belum dikerjakan): `git init`, `.gitattributes`, lengkapi `.gitignore` (tambahkan `database3d/`), hapus `venv/` dan `__pycache__/` di root.
- **Tahap 3**: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, adaptasi config Nginx.
