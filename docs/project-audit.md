# Audit Project PolyView

Tanggal audit: 2026-09-26
Lingkup: seluruh isi folder `polyview/` (termasuk `venv/` dan `__pycache__/`).
Sifat audit: **read-only**. Tidak ada file yang diubah, dipindah, atau dibuat selain laporan ini.

---

## 1. Ringkasan Project

**PolyView** adalah web app untuk menjelajahi dan melihat pratinjau file 3D di server lokal. Fiturnya:

- Menampilkan pohon folder dari satu direktori di server (`BASE_DIR`).
- Pratinjau model **FBX** dan **OBJ** di browser memakai Three.js r128.
- Pratinjau gambar **PNG/JPG**, serta **TIF/TIFF** yang dikonversi ke PNG di server memakai Pillow.
- Download file tunggal, atau satu folder sebagai ZIP yang dibuat saat itu juga.
- UI dua bahasa (ID/EN) dan responsif (sidebar menjadi drawer di layar mobile).
- Sudah ada upaya awal PWA (manifest + service worker).

| Aspek | Nilai |
|---|---|
| Backend | Python 3.12, Flask 3.1.3, Gunicorn 25.3.0, Pillow 12.2.0 (versi dibaca dari `venv/`) |
| Frontend | Satu file `index.html` (~42 KB) berisi HTML, CSS, dan JS inline; library dari CDN |
| Deploy lama | systemd (`polyview.service`), lalu Gunicorn di `127.0.0.1:5000`, lalu Nginx di `:8080` |
| Data | Folder host yang di-hardcode: `/mnt/vermax/arya_data/database/3dsmax` |
| Autentikasi | **Tidak ada** |
| Version control | **Folder ini belum menjadi repository git** (`.gitignore` sudah ada, tetapi belum berlaku) |
| Test | Tidak ada |

**Kesimpulan singkat:** kodenya kecil dan mudah dipahami. Namun project **sedang dalam kondisi setengah-migrasi**: `server.py` sudah dipindah ke `app/`, dan `manifest.json`/`sw.js` ke `static/`, tetapi path di dalam kode belum diubah. **Dengan struktur folder sekarang, aplikasi tidak akan berjalan dengan benar** (lihat §5.1).

---

## 2. Struktur Folder Saat Ini

```
polyview/
├── .gitignore                 32 B    (CRLF — beda sendiri, file lain LF)
├── README.md                   0 B    (kosong)
├── index.html             41.915 B    frontend lengkap (HTML+CSS+JS inline)
├── polyview.nginx.conf     1.690 B    config Nginx (deploy lama)
├── polyview.service          360 B    unit systemd (deploy lama)
├── app/
│   └── server.py           4.927 B    backend Flask
├── static/
│   ├── manifest.json         575 B    manifest PWA
│   ├── sw.js               1.727 B    service worker
│   └── icons/
│       ├── apple-touch-icon.png   180×180
│       ├── favicon.ico            1 entry 192×192 (152 KB)
│       ├── icon-192.png           192×192
│       ├── icon-512.png           512×512
│       └── icon-maskable-512.png  512×512
├── docs/
│   └── project-audit.md       (laporan ini)
├── __pycache__/
│   └── server.cpython-312.pyc   artefak lama — dikompilasi dari /var/www/polyview/server.py
└── venv/                     ±101,7 MB — virtualenv Linux (python 3.12.3, /var/www/polyview/venv)
    ├── bin/  include/  pyvenv.cfg
    ├── lib/python3.12/site-packages/...
    └── lib64/python3.12/site-packages/...   ← salinan penuh dari lib/ (seharusnya symlink)
```

Catatan urutan waktu, dari timestamp:
- 4–5 Mei 2026: `index.html`, `server.py`, `sw.js`, `manifest.json`, config nginx/systemd. Ini periode server lama.
- 26 Sep 2026: `static/icons/*.png`, `.gitignore`, `README.md`, `docs/`. Ini persiapan migrasi yang belum selesai.

---

## 3. File yang Digunakan

| File | Dipakai oleh | Status |
|---|---|---|
| [app/server.py](../app/server.py) | Gunicorn (`server:app`) | ✅ Inti backend, tetapi path-nya rusak setelah dipindah (§5.1) |
| [index.html](../index.html) | Route `/` di server.py | ✅ Inti frontend; server mencarinya di `app/`, bukan di root |
| [static/manifest.json](../static/manifest.json) | `<link rel="manifest">` di index.html, route `/manifest.json` | ⚠️ Dipakai, tetapi server mencarinya di `app/`, sehingga 404 |
| [static/sw.js](../static/sw.js) | `navigator.serviceWorker.register('/sw.js')`, route `/sw.js` | ⚠️ Dipakai, tetapi server mencarinya di `app/`, sehingga 404 |
| [static/icons/favicon.ico](../static/icons/favicon.ico) | Route `/favicon.ico` | ⚠️ Route crash karena variabel `BASE_PATH` tidak terdefinisi |
| [polyview.nginx.conf](../polyview.nginx.conf) | Nginx di server lama | Dipakai di deploy lama; perlu diadaptasi untuk Docker |
| [polyview.service](../polyview.service) | systemd di server lama | Dipakai di deploy lama; **tidak diperlukan** setelah memakai Docker |
| [.gitignore](../.gitignore) | git | Ada, tetapi belum berlaku karena belum `git init` |

**Dependensi eksternal (CDN) yang dimuat saat runtime:**

| Sumber | Versi | Dipakai untuk |
|---|---|---|
| `cdnjs.cloudflare.com/.../three.js/r128/three.min.js` | r128 (2021) | Core Three.js |
| `cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/FBXLoader.js` | 0.128.0 | Loader FBX |
| `cdn.jsdelivr.net/npm/fflate@0.7.4/umd/index.js` | 0.7.4 | Dekompresi FBX (dibutuhkan FBXLoader) |
| `fonts.googleapis.com` (JetBrains Mono, Syne) | — | Font UI |

**Dependensi Python yang benar-benar di-import:** `flask`, `Pillow` (opsional). `gunicorn` adalah server runtime. Sisanya (`werkzeug`, `jinja2`, `click`, `blinker`, `itsdangerous`, `markupsafe`) merupakan dependensi transitif Flask. `packaging` adalah dependensi transitif gunicorn.

---

## 4. File yang Tidak Digunakan atau Mencurigakan

| File / folder | Temuan | Rekomendasi |
|---|---|---|
| `venv/` (±101,7 MB) | Virtualenv **Linux** yang tersalin ke Windows. Isinya binary ELF `python` 8 MB (×3 salinan), `pyvenv.cfg` menunjuk `/usr/bin` dan `/var/www/polyview/venv`. `lib64/` adalah salinan penuh `lib/` (di Linux aslinya symlink), sehingga ukurannya dobel. **Tidak bisa dipakai di mesin ini maupun di container.** | Hapus. Ganti dengan `requirements.txt`. Jangan masuk repo (sudah ada di `.gitignore`). |
| `__pycache__/server.cpython-312.pyc` | Bytecode lama di **root**, hasil kompilasi dari `/var/www/polyview/server.py`. Ini bukti bahwa `server.py` dulunya berada di root. Sudah basi. | Hapus. |
| `README.md` | Kosong (0 byte). | Isi dengan cara menjalankan app, env var, dan cara deploy. |
| `static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png` | **Tidak direferensikan di mana pun.** Manifest dan `index.html` masih menunjuk `/polyview.png`. | Pakai di manifest dan `<link>`; hapus referensi `/polyview.png`. |
| `/polyview.png` (direferensikan) | **File tidak ada** di project. Direferensikan di manifest (2×), `index.html` (3×), dan route `/polyview.png`. | Ganti dengan ikon di `static/icons/`. |
| `static/icons/favicon.ico` | 152 KB, hanya berisi 1 ukuran (192×192). Favicon umumnya 16/32/48 px dan ukurannya < 20 KB. | Buat ulang multi-size (16, 32, 48), atau pakai PNG 32×32. |
| `polyview.service` | Khusus systemd, memakai `User=windy` (akun personal) dan path `/var/www/polyview`. | Setelah migrasi Docker: pindah ke `deploy/legacy/` atau hapus. |
| `polyview.nginx.conf` | Blok `location ~* \.(css\|woff2?)$` tidak ada gunanya karena tidak ada file CSS/WOFF di-serve dari origin. `client_max_body_size 500M` tidak relevan karena tidak ada endpoint upload. | Sederhanakan saat diadaptasi ke Docker. |
| Route `/polyview.png` di server.py | Melayani file yang tidak ada. | Hapus atau arahkan ke ikon baru. |
| Ekstensi `.mtl` di server.py | Ditangani backend, tetapi frontend tidak pernah memuat MTL (parser OBJ mengabaikan material). | Kode mati kecil; boleh dibiarkan atau dipakai untuk fitur material. |
| Komentar `<!-- Apple touch icon fallback (inline SVG sebagai data URI) -->` | Tidak sesuai dengan kode di bawahnya. | Perbarui atau hapus. |

---

## 5. Masalah yang Ditemukan

Tingkat keparahan: 🔴 Kritis (app rusak / risiko keamanan besar) · 🟠 Tinggi · 🟡 Sedang · ⚪ Rendah

### 5.1 Migrasi setengah jalan membuat app rusak 🔴

Flask me-resolve path relatif di `send_from_directory('.')` dan `static_folder='.'` terhadap **folder modul**, yaitu `app/`. Di struktur sekarang:

| Route | Mencari file di | Hasil |
|---|---|---|
| `/` | `app/index.html` | **404** (file ada di root) |
| `/manifest.json` | `app/manifest.json` | **404** (file ada di `static/`) |
| `/sw.js` | `app/sw.js` | **404**, sehingga service worker gagal register |
| `/polyview.png` | `app/polyview.png` | **404** (file tidak ada di mana pun) |
| `/favicon.ico` | `BASE_PATH` | **500 NameError**: variabel `BASE_PATH` tidak pernah didefinisikan ([server.py:76](../app/server.py#L76)) |

Selain itu, `polyview.service` menjalankan `gunicorn server:app` dari `/var/www/polyview`. Ini tidak cocok lagi karena modulnya sekarang `app/server.py`.

### 5.2 Keamanan

| # | Masalah | Lokasi | Sev. |
|---|---|---|---|
| S1 | **Tidak ada autentikasi.** Siapa pun yang bisa menjangkau port 8080 dapat melihat dan men-download seluruh `BASE_DIR`, termasuk ZIP satu folder penuh. Nginx `listen 8080; server_name _;` menerima semua host. | server.py, nginx | 🔴 |
| S2 | `static_folder='.'` membuat Flask membuka route `/static/<file>` untuk **seluruh isi folder modul**. Di layout lama (root) ini membuka `/static/server.py`, `/static/polyview.service`, dan `/static/venv/...`. Di layout baru ini membuka `/static/server.py`. Source code bisa bocor. | [server.py:19](../app/server.py#L19) | 🟠 |
| S3 | **XSS lewat nama file.** `node.name` dan `node.path` dimasukkan ke `innerHTML` tanpa escape. File bernama `<img src=x onerror=alert(1)>.fbx` di share akan mengeksekusi JS di browser semua pengguna. | [index.html:547](../index.html#L547), [index.html:612](../index.html#L612) | 🟠 |
| S4 | ZIP folder memakai `os.walk` + `zf.write`. Symlink **file** di dalam folder yang menunjuk ke luar `BASE_DIR` tetap ikut ter-zip. `safe_path` hanya memeriksa path yang diminta, bukan isi folder. | [server.py:132-135](../app/server.py#L132-L135) | 🟡 |
| S5 | Info infrastruktur/personal di-hardcode: `/mnt/vermax/arya_data/...`, `User=windy`. | server.py, polyview.service | ⚪ |
| S6 | Mode dev `debug=True` (Werkzeug debugger). Aman selama hanya bind `127.0.0.1`, tetapi berbahaya kalau suatu saat diubah ke `0.0.0.0` di container. | [server.py:147](../app/server.py#L147) | 🟡 |

### 5.3 Bug dan keandalan

| # | Masalah | Lokasi | Sev. |
|---|---|---|---|
| B1 | URL file **tidak di-encode**: `` `/api/file/${node.path}` ``. Nama file yang mengandung `#`, `?`, `%`, atau `+` akan gagal dimuat atau di-download. | [index.html:619](../index.html#L619), [index.html:622](../index.html#L622), [index.html:972](../index.html#L972) | 🟠 |
| B2 | `get_tree` hanya menangkap `PermissionError`. Symlink rusak menyebabkan `FileNotFoundError` di `getsize`, sehingga **seluruh `/api/tree` gagal 500**. Symlink yang menunjuk ke folder induk menyebabkan **rekursi tak berujung** (`RecursionError`). | [server.py:42-59](../app/server.py#L42-L59) | 🟠 |
| B3 | ZIP folder dibuat **penuh di RAM** (`BytesIO`). Folder aset 3D berukuran GB dapat menghabiskan memori container. | [server.py:130-139](../app/server.py#L130-L139) | 🟠 |
| B4 | Gunicorn tidak men-set `--timeout` (default 30 detik), sedangkan Nginx menunggu 300 detik. ZIP besar atau konversi TIF besar akan membuat worker **di-kill** (`WORKER TIMEOUT`), dan klien menerima 502. | polyview.service | 🟠 |
| B5 | `/api/tree` men-scan **seluruh pohon direktori secara rekursif di setiap request**, tanpa cache dan tanpa lazy-load. Untuk database aset besar, ini lambat dan payload JSON-nya besar. | server.py, index.html | 🟡 |
| B6 | Konversi TIF tidak dibatasi ukurannya. File sangat besar bisa memicu `DecompressionBombError` (yang berujung 500) atau memakan banyak RAM. Hasil konversi juga tidak di-cache. | [server.py:101-113](../app/server.py#L101-L113) | 🟡 |
| B7 | **Kebocoran event listener**: `setupOrbitControls` menambahkan listener `mousemove`/`mouseup` ke `window` setiap kali model dibuka, dan tidak pernah dilepas. Geometry, material, dan texture juga tidak di-`dispose()`. Setelah membuka banyak model, UI makin berat. | [index.html:786-792](../index.html#L786-L792), [index.html:665-672](../index.html#L665-L672) | 🟡 |
| B8 | Race condition: `fflate` dan `FBXLoader` dimuat async tanpa urutan. Kalau user membuka FBX sebelum keduanya selesai dimuat, akan muncul error "FBXLoader belum tersedia". | [index.html:1017-1027](../index.html#L1017-L1027) | ⚪ |
| B9 | Header ganda: Flask **dan** Nginx sama-sama menambahkan `Cache-Control` dan `Service-Worker-Allowed` di `/sw.js`, sehingga respons berisi dua header dengan nilai berbeda. | server.py:82-83, nginx:38-39 | ⚪ |

### 5.4 Technical debt dari project lama

| # | Temuan |
|---|---|
| T1 | **Tidak ada `requirements.txt`**. Dependensi hanya tercatat di docstring (`pip3 install flask pillow gunicorn`) tanpa versi. Satu-satunya sumber versi adalah `venv/` yang tidak portable. |
| T2 | **Konfigurasi di-hardcode** (`BASE_DIR`, host, port). Tidak ada env var. `os.path.expanduser()` dipakai pada path absolut, sehingga tidak ada efeknya. |
| T3 | Frontend **monolitik**: 1.029 baris HTML+CSS+JS dalam satu file. Sulit di-cache terpisah dan sulit di-maintain. |
| T4 | **Three.js r128** (2021) memakai `examples/js` (script global non-module) yang sudah **dihapus sejak r148**. Upgrade berarti pindah ke ES modules / importmap. `renderer.outputEncoding` juga sudah deprecated di versi baru. |
| T5 | **Ketergantungan penuh pada CDN**: tanpa internet, preview 3D tidak berfungsi sama sekali. Ini bertentangan dengan tujuan "server lokal" dan dengan PWA offline. |
| T6 | Parser OBJ buatan sendiri: tidak mendukung indeks negatif, `o`/`g`/`usemtl`, maupun material MTL. |
| T7 | Logging memakai `print()`, bukan modul `logging`. Tidak ada endpoint health check. |
| T8 | Teks yang di-hardcode: `"polyview / Documents"`, `"Gagal memuat direktori"`, `"Gagal memuat OBJ/FBX"`, dan label `Wire` tidak ikut sistem i18n. Pesan error WebGL menyebut VMware, yang merupakan sisa lingkungan dev. |
| T9 | Format kode tidak konsisten (indentasi rusak di [index.html:709-710](../index.html#L709-L710) dan [index.html:738-746](../index.html#L738-L746); spasi trailing di [server.py:69](../app/server.py#L69) dan [server.py:73](../app/server.py#L73)). |
| T10 | Line ending campur: `.gitignore` memakai CRLF, file lain LF. Tidak ada `.gitattributes`. Ini berisiko pada script shell atau entrypoint di Docker. |
| T11 | Tidak ada test, linter, CI, maupun LICENSE. |
| T12 | Belum ada repository git, jadi tidak ada riwayat perubahan untuk rollback. |

### 5.5 File yang tidak perlu masuk repository

| Path | Alasan | Sudah di `.gitignore`? |
|---|---|---|
| `venv/` | Environment lokal, 100+ MB, binary Linux | ✅ |
| `__pycache__/`, `*.pyc` | Artefak kompilasi | ✅ |
| `.env` | Rahasia/konfigurasi lokal | ✅ |
| `.vscode/`, `.idea/` | Setting editor | ❌ tambahkan |
| `*.log` | Log runtime | ❌ tambahkan |
| `.DS_Store`, `Thumbs.db`, `desktop.ini` | Sampah OS | ❌ tambahkan |
| `docker-compose.override.yml` | Override lokal per mesin | ❌ tambahkan (jika dipakai) |

Selain `.gitignore`, Docker juga butuh **`.dockerignore`** (saat ini belum ada). Tanpa itu, `COPY . .` akan ikut menyalin `venv/` (100 MB) ke build context.

---

## 6. Kesiapan Docker

**Status: ❌ Belum siap.** Tidak ada `Dockerfile`, `docker-compose.yml`, `.dockerignore`, maupun `requirements.txt`.

### 6.1 Penghambat (harus diselesaikan)

| # | Penghambat | Solusi |
|---|---|---|
| D1 | Path file statis rusak (§5.1) | Tentukan satu folder web (mis. `static/`) dan pakai path absolut berbasis `os.path.dirname(__file__)` atau env var |
| D2 | `BASE_DIR` di-hardcode ke path host | Baca dari env var `POLYVIEW_DATA_DIR` (default `/data`). Mount folder host ke `/data` sebagai **read-only** |
| D3 | Tidak ada `requirements.txt` | Buat dengan versi di-pin (Flask 3.1.x, Pillow 12.x, Gunicorn 25.x) |
| D4 | Gunicorn bind `127.0.0.1` | Di container harus `0.0.0.0:5000` |
| D5 | `BASE_PATH` NameError | Perbaiki route favicon |

### 6.2 Yang sebaiknya ada

| Item | Catatan |
|---|---|
| Base image | `python:3.12-slim`. Pillow menyediakan wheel manylinux, jadi tidak butuh compiler |
| User non-root | UID/GID sebaiknya bisa diatur (`PUID`/`PGID`) supaya bisa membaca volume data host |
| Gunicorn config | `--workers`, `--timeout` (≥ 300 agar sama dengan nginx), `--access-logfile -` lewat env |
| Health check | Tambah endpoint ringan `/healthz`. Jangan memakai `/api/tree` karena scan penuh |
| Volume data | `:ro`, karena app tidak pernah menulis |
| Reverse proxy | **Opsi A (disarankan):** service `nginx` di compose. Nginx melayani `index.html`/`sw.js`/`manifest`/`icons` langsung dan mem-proxy `/api/*` ke `polyview:5000`. `proxy_pass` harus diganti dari `127.0.0.1` ke nama service. **Opsi B:** tanpa nginx, Gunicorn langsung di-expose. Ini lebih sederhana, tetapi Gunicorn sync worker rentan terhadap klien lambat/unduhan besar |
| HTTPS | Dibutuhkan untuk PWA (lihat §7). Bisa lewat reverse proxy yang sudah ada di host (Traefik/Caddy/NPM) atau dengan menambahkan Caddy di compose |
| Log | ke stdout/stderr (bukan `print` biasa) |
| `restart: unless-stopped` | Pengganti `Restart=always` dari systemd |

### 6.3 Sketsa arsitektur target

```
                       ┌────────────── docker compose ───────────────┐
Browser ──HTTPS──► [reverse proxy] ──► nginx:80 ──/api/*──► polyview:5000 (gunicorn)
                       │                 │ static: index.html,         │
                       │                 │ sw.js, manifest, icons      │
                       │                                   /data (ro) ◄┼── /mnt/.../3dsmax (host)
                       └─────────────────────────────────────────────┘
```

---

## 7. Kesiapan PWA

**Status: ⚠️ Fondasi ada, tetapi saat ini tidak bisa di-install.**

### 7.1 Checklist installability

| Syarat | Status | Keterangan |
|---|---|---|
| Disajikan lewat **HTTPS** (atau `localhost`) | ❌ | Deploy lama memakai `http://<ip>:8080`. Di luar localhost, service worker **tidak akan pernah ter-register**. Ini penghambat terbesar. |
| `manifest.json` bisa diakses | ❌ | 404 karena path server salah (§5.1) |
| `name`, `short_name`, `start_url`, `display` | ✅ | Ada |
| Ikon 192 & 512 yang valid | ❌ | Menunjuk `/polyview.png` yang tidak ada. Ikon yang benar sudah tersedia di `static/icons/` tetapi tidak dipakai |
| `purpose` ikon | ⚠️ | `"any maskable"` digabung dalam satu entry tidak disarankan. Pisahkan: `icon-512.png` → `any`, `icon-maskable-512.png` → `maskable` |
| `id`, `scope` | ⚠️ | Belum ada; disarankan `"id": "/"`, `"scope": "/"` |
| `screenshots` | ⚪ | Opsional; membuat dialog install Android/desktop lebih kaya |
| Service worker ter-register dengan handler `fetch` | ❌ | `sw.js` 404 |
| `apple-touch-icon` | ❌ | Menunjuk `/polyview.png`; seharusnya `static/icons/apple-touch-icon.png` (180×180, sudah ada) |
| `theme-color` | ✅ | Ada dan konsisten dengan manifest |

### 7.2 Masalah perilaku service worker ([static/sw.js](../static/sw.js))

| # | Masalah | Dampak |
|---|---|---|
| P1 | App shell memakai **cache-first tanpa revalidasi**, dan versi cache tetap (`polyview-v1`) | Setelah `index.html` diubah, pengguna **tetap melihat versi lama** sampai nama cache di-bump secara manual |
| P2 | `three.min.js` dimuat dengan `<script>` **tanpa atribut `crossorigin`**, sehingga respons berupa *opaque* dan `res.ok === false`. Akibatnya file itu **tidak pernah di-cache** | Offline: Three.js tidak ada, jadi preview 3D mati |
| P3 | `.catch(() => cached)` saat `cached` bernilai `undefined` membuat `respondWith(undefined)` | Error di SW saat offline, bukan fallback yang rapi |
| P4 | Tidak ada fallback offline untuk `/api/*` | Saat offline, tree menampilkan "Gagal memuat direktori" tanpa penjelasan |
| P5 | Semua request same-origin non-API (termasuk yang tidak dikenal) di-cache tanpa batas | Cache bisa membengkak |
| P6 | Tidak ada pengecekan `request.method === 'GET'` | Aman untuk sekarang (semua request GET), tetapi rapuh |

### 7.3 Catatan desain PWA

- Aplikasi ini **bergantung pada data server** (file 3D di share). "Offline penuh" tidak realistis. Target yang masuk akal: **app shell + library bisa dibuka offline**, dengan pesan "server tidak terjangkau" yang jelas.
- Supaya itu tercapai, **Three.js, FBXLoader, fflate, dan font sebaiknya di-host sendiri** (vendor ke `static/vendor/`). Cara ini sekaligus menyelesaikan T5 dan P2.
- Strategi yang disarankan: shell memakai *stale-while-revalidate* atau *network-first*, vendor/ikon memakai *cache-first* dengan nama berversi, `/api/*` memakai *network-only* dengan fallback JSON error.

---

## 8. Struktur Folder yang Direkomendasikan

```
polyview/
├── app/                          # backend Python
│   ├── __init__.py
│   ├── server.py                 # Flask app; config dari env
│   └── config.py                 # (opsional) baca env: DATA_DIR, dsb.
├── static/                       # semua aset web — dilayani nginx/Flask apa adanya
│   ├── index.html                # dipindah dari root
│   ├── manifest.webmanifest      # (atau tetap manifest.json)
│   ├── sw.js
│   ├── css/app.css               # (opsional, dipecah dari index.html)
│   ├── js/app.js                 # (opsional, dipecah dari index.html)
│   ├── vendor/                   # three.min.js, FBXLoader.js, fflate — self-host
│   ├── fonts/                    # (opsional) JetBrains Mono, Syne
│   └── icons/                    # sudah ada
├── deploy/
│   ├── nginx/polyview.conf       # adaptasi dari polyview.nginx.conf (upstream = service compose)
│   └── legacy/polyview.service   # arsip deploy systemd lama (atau hapus)
├── docs/
│   └── project-audit.md
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example                  # POLYVIEW_DATA_DIR, PORT, WORKERS, TIMEOUT, PUID/PGID
├── requirements.txt
├── .gitignore
├── .gitattributes                # * text=auto eol=lf
└── README.md
```

Prinsip:
1. **Satu folder web** (`static/`) yang dilayani nginx secara langsung. Flask hanya menangani `/api/*` (dan `/` sebagai fallback kalau tanpa nginx).
2. **Tidak ada path absolut host di dalam kode**. Semuanya lewat env var dan volume.
3. File deploy dikumpulkan di `deploy/`, supaya root project tetap bersih.
4. Pemecahan `index.html` menjadi css/js **opsional** dan dikerjakan terpisah, supaya risiko perubahan perilaku kecil.

---

## 9. Checklist Migrasi Docker

**Tahap 0: Persiapan**
- [ ] `git init`, lalu commit kondisi sekarang (sebagai baseline sebelum perubahan apa pun)
- [ ] Tambah `.gitattributes` (`* text=auto eol=lf`)
- [ ] Lengkapi `.gitignore` (§5.5)
- [ ] Hapus `venv/` dan `__pycache__/`

**Tahap 1: Rapikan struktur & path**
- [ ] Pindahkan `index.html` ke `static/`
- [ ] Ubah `server.py`: `static_folder` diarahkan ke `../static` (path absolut dari `__file__`), `static_url_path` dikosongkan atau dibatasi, dan hentikan eksposur `static_folder='.'`
- [ ] Perbaiki route `/favicon.ico` (hapus `BASE_PATH`)
- [ ] Hapus route `/polyview.png` dan perbarui referensinya ke `static/icons/*`
- [ ] `BASE_DIR` dibaca dari env `POLYVIEW_DATA_DIR` (default `/data`)
- [ ] Tambah endpoint `/healthz`
- [ ] Ganti `print` dengan `logging`

**Tahap 2: Dependensi**
- [ ] Buat `requirements.txt` dengan versi di-pin: `flask==3.1.*`, `pillow==12.*`, `gunicorn==25.*`

**Tahap 3: Container**
- [ ] `Dockerfile`: `python:3.12-slim`, `pip install --no-cache-dir -r requirements.txt`, user non-root, `EXPOSE 5000`, `CMD gunicorn -b 0.0.0.0:5000 --timeout 300 --workers ${WORKERS} app.server:app`
- [ ] `.dockerignore`: `venv/`, `__pycache__/`, `.git/`, `docs/`, `*.pyc`, `.env`
- [ ] `docker-compose.yml`:
  - [ ] service `polyview`: env dari `.env`, volume `${POLYVIEW_DATA_DIR}:/data:ro`, `healthcheck` ke `/healthz`, `restart: unless-stopped`
  - [ ] service `nginx`: mount `static/` read-only dan `deploy/nginx/polyview.conf`, publish port (mis. `8080:80`), `depends_on: polyview (service_healthy)`
- [ ] `.env.example` untuk dokumentasi variabel
- [ ] Adaptasi config nginx: `proxy_pass http://polyview:5000`, serve static dari disk, hapus header ganda `/sw.js`, hapus blok css/woff dan `client_max_body_size`, tambah `gzip` untuk JSON

**Tahap 4: Verifikasi**
- [ ] `docker compose up -d --build`, lalu cek `/`, `/manifest.json`, `/sw.js`, `/favicon.ico`, `/api/tree`, preview FBX, OBJ, TIF, dan download ZIP
- [ ] Pastikan user container bisa membaca volume data (atur UID/GID)
- [ ] Uji download folder besar (timeout & memori)
- [ ] Nonaktifkan `polyview.service` di server lama, lalu arsipkan filenya

---

## 10. Checklist Perbaikan Project

Diurutkan berdasarkan prioritas. Item bertanda ⚙️ **mengubah perilaku aplikasi**, sehingga butuh persetujuan terpisah.

**🔴 Prioritas 1: App berjalan & aman**
- [ ] Perbaiki semua path statis dan `BASE_PATH` (§5.1)
- [ ] Hentikan eksposur `static_folder='.'` (S2)
- [ ] Escape nama file sebelum dimasukkan ke HTML: pakai `textContent`, bukan `innerHTML` (S3)
- [ ] ⚙️ Tambah autentikasi minimal (Basic Auth di nginx, atau batasi ke jaringan LAN) (S1)
- [ ] Pakai `encodeURIComponent` per segmen path di semua URL `/api/...` (B1)

**🟠 Prioritas 2: Keandalan**
- [ ] `get_tree`: tangani `OSError` secara umum, jangan ikuti symlink direktori (atau lacak inode yang sudah dikunjungi) (B2)
- [ ] ZIP: skip symlink yang keluar dari `BASE_DIR` (S4); ⚙️ streaming ZIP ke respons alih-alih `BytesIO` (B3)
- [ ] Samakan timeout Gunicorn dan nginx (B4)
- [ ] Batasi ukuran/piksel TIF dan tangani `DecompressionBombError` → 413 (B6)

**🟡 Prioritas 3: PWA**
- [ ] Manifest: pakai ikon `static/icons/*`, pisahkan `any`/`maskable`, tambah `id` & `scope`
- [ ] `index.html`: perbarui `<link rel="icon">` dan `apple-touch-icon`
- [ ] Self-host Three.js r128, FBXLoader, fflate, dan font ke `static/vendor/` (T5, P2)
- [ ] ⚙️ Service worker: versi cache otomatis/berbasis build, shell network-first atau SWR, fallback offline yang rapi (P1, P3, P4)
- [ ] Siapkan HTTPS di reverse proxy

**⚪ Prioritas 4: Kualitas kode & maintainability**
- [ ] Lepas listener `window` dan `dispose()` geometry/material saat ganti model (B7)
- [ ] Muat `fflate` lalu `FBXLoader` secara berurutan (B8)
- [ ] Pindahkan teks yang di-hardcode ke i18n; hapus referensi VMware (T8)
- [ ] Rapikan indentasi & trailing whitespace (T9)
- [ ] Isi `README.md`
- [ ] Buat ulang `favicon.ico` multi-size yang kecil
- [ ] (Opsional) Pecah `index.html` menjadi `css/app.css` + `js/app.js` (T3)
- [ ] ⚙️ (Opsional) Lazy-load tree per folder atau cache hasil scan (B5)
- [ ] (Jangka panjang) Upgrade Three.js ke versi modern berbasis ES module (T4)
- [ ] Tambah test dasar untuk `safe_path` dan endpoint API, plus linter (ruff)

---

*Akhir laporan. Belum ada perubahan yang dilakukan pada project. Semua langkah di atas menunggu persetujuan.*
