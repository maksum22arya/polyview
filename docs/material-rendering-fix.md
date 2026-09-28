# Perbaikan Rendering Material FBX

Tanggal: 2026-09-26
Acuan: [material-rendering-summary.md](material-rendering-summary.md) (rekomendasi poin 13–14) dan [material-rendering-audit.md](material-rendering-audit.md) (solusi S1-a + S2).
Commit sebelum perbaikan (titik rollback): `deead4c before material rendering fix`

## Ringkasan

| Tujuan | Status |
|---|---|
| Alpha/stensil TIF dipertahankan server, **hanya** saat model 3D memintanya | ✅ `?alpha=1` |
| Alpha mask diperlakukan sebagai cutout (lubang), bukan kaca | ✅ `alphaTest` 0.5, non-transparent |
| DoubleSide pada material FBX | ✅ |
| Perilaku OBJ tidak berubah | ✅ screenshot identik piksel demi piksel |
| UI tidak berubah, tanpa tombol baru | ✅ |
| Docker & struktur project tidak berubah | ✅ (hanya menambah folder `tests/`) |
| Preview gambar & download tetap sama | ✅ URL tanpa `?alpha`, output identik |

---

## 1. File yang Diubah

| File | Perubahan |
|---|---|
| `app/server.py` | + fungsi `open_tif_with_alpha()`; `api_file()` memakainya bila `?alpha=1`; `request` ditambahkan ke import Flask |
| `static/index.html` | + fungsi `fbxMaterials()`, `prepareFbxMaterials()`, `finishFbxMaterials()`; cabang FBX di `load3D()` memakai `THREE.LoadingManager` khusus |
| `tests/test_tif_alpha.py` | **Baru**: 9 unit test konversi TIF |
| `README.md` | Changelog + dokumentasi `?alpha=1` di tabel endpoint |
| `docs/material-rendering-fix.md` | **Baru** (dokumen ini) |

Tidak disentuh: cabang OBJ (`parseOBJ`, `load3D` untuk OBJ), preview gambar, download, tree, `sw.js`, `manifest.json`, `Dockerfile`, `docker-compose.yml`, config nginx, `requirements.txt`, versi Three.js/FBXLoader.

---

## 2. Alasan dan Isi Perubahan

### 2.1 Server: mempertahankan stensil TIF (`app/server.py`)

**Masalah:** TIF kapal (mis. `KP Bharata.tif`) punya 4 channel, dengan channel ke-4 bertanda *unspecified* (`ExtraSamples=0`). 3ds Max/Photoshop memakai channel itu sebagai alpha, tetapi Pillow membukanya sebagai `RGB` dan **membuang** channel ke-4. PNG yang dikirim ke browser jadi tanpa stensil.

**Perbaikan:** fungsi baru `open_tif_with_alpha(path)`:
- Hanya bertindak bila Pillow membuka file sebagai `RGB` dengan raw mode `RGBX`, yaitu tepat kasus di atas. File lain dikembalikan apa adanya.
- Membuka ulang file dan menginstruksikan decoder membaca channel ke-4 sebagai alpha (`RGBA`).
- Kalau gagal (misalnya format tak terduga atau versi Pillow berbeda): log warning, lalu **fallback ke perilaku lama** (RGB).

Di `api_file()`, fungsi ini **hanya** dipanggil bila `request.args.get('alpha') == '1'`. Tanpa parameter itu (preview, `<img>`, link langsung), kode berjalan persis seperti sebelumnya. `/api/download` tidak diubah sama sekali.

### 2.2 Frontend: cutout + DoubleSide (`static/index.html`)

**Masalah:** FBXLoader r128 mengubah slot Opacity 3ds Max menjadi `alphaMap` + `transparent: true`. Akibatnya objek dirender seperti kaca, dengan tingkat tembus pandang diambil dari **channel hijau** tekstur. Material FBX juga tidak pernah di-set dua sisi.

**Perbaikan (hanya di cabang FBX):**

1. `LoadingManager` khusus untuk FBXLoader dengan `setURLModifier`: URL tekstur yang berakhiran `.tif`/`.tiff` diberi `?alpha=1`. Hanya tekstur yang diminta FBXLoader yang lewat manager ini. Preview gambar dan download memakai jalur lain, sehingga tidak terpengaruh.
2. `prepareFbxMaterials(obj)`, dijalankan sesaat setelah FBX selesai di-parse:
   - `side = DoubleSide` untuk semua material FBX.
   - Material dengan `alphaMap` diubah menjadi cutout: `transparent = false`, `depthWrite = true`, `alphaTest = 0.5`. `alphaMap` **ditahan sementara** sampai teksturnya selesai dimuat, karena tekstur yang belum ada dibaca sebagai alpha 0 dan mesh bisa hilang total.
3. `finishFbxMaterials(obj)`, dijalankan saat semua tekstur selesai (`manager.onLoad`):
   - `alphaMap` berasal dari **file yang sama** dengan tekstur diffuse (pola 3ds Max): `alphaMap` dibuang, dan stensil diambil dari channel alpha tekstur diffuse (yang kini dikirim server berkat `?alpha=1`).
   - `alphaMap` dari **file lain** dan berhasil dimuat: dipasang kembali sebagai mask grayscale.
   - `alphaMap` gagal dimuat: dibuang, sehingga material tetap opaque dan tidak hilang.

Material **tanpa** slot Opacity tidak mendapat `alphaTest`. Alpha pada tekstur diffuse-nya tetap diabaikan seperti sebelumnya, sehingga model helikopter dan KRI tidak tiba-tiba berlubang.

---

## 3. Sebelum vs Sesudah

### 3.1 Status material (diukur di browser, Edge headless)

| Model | | side | transparent | alphaTest | Stensil | Request tekstur |
|---|---|---|---|---|---|---|
| Bharata_8004, Bisma_8001 (juga Sanjaya, Baladewa) | Sebelum | Front | **true** | 0 | `alphaMap` = channel hijau | `KP *.tif` |
| | Sesudah | **Double** | **false** | **0.5** | channel alpha tekstur diffuse | `KP *.tif?alpha=1` |
| AS 550 Fennec, KRI Belati (semua model tanpa slot Opacity) | Sebelum | Front | false | 0 | — | `*.tif` |
| | Sesudah | **Double** | false | 0 | — | `*.tif?alpha=1` |
| OBJ | Sebelum = Sesudah | Double | false | 0 | — | — |

### 3.2 Visual

| Model | Sebelum | Sesudah |
|---|---|---|
| Kapal Bharata/Bisma/Sanjaya/Baladewa | Redup & tembus pandang (±35% opaque), bagian dalam terlihat (x-ray) | Padat; railing tampil sebagai pagar berlubang; dek dan turret solid |
| Helikopter, KRI | Bagian tipis (rotor, sirip) hilang bila dilihat dari sisi belakangnya | Terlihat dari kedua sisi; tampak depan praktis sama |
| OBJ | — | **Identik piksel demi piksel** (hash screenshot sama) |
| Preview `KP Bharata.tif` | — | **Identik piksel demi piksel**, tanpa `?alpha` |
| Download | `/api/download/...` | Sama (URL & isi file) |

### 3.3 Hasil Test

**Unit test server:** `python -m unittest discover -s tests -v`, dijalankan di image `polyview:latest` (Python 3.12, Pillow 12.3.0, Flask 3.1.3), **9/9 lulus**:

| Test | Memastikan |
|---|---|
| `test_sanity_pillow_membuang_channel_ke4` | Prasyarat bug: Pillow membuka TIF 4-channel `ExtraSamples=0` sebagai RGB |
| `test_default_tanpa_alpha_tidak_berubah` | Tanpa `?alpha`, output tetap RGB dengan piksel identik |
| `test_alpha_1_mempertahankan_channel_ke4` | Dengan `?alpha=1`, output RGBA dan nilai alpha per piksel benar |
| `test_alpha_nilai_lain_diabaikan` | `?alpha=0` / `?alpha=true` tidak mengubah apa pun |
| `test_tif_3_channel_tetap_rgb` | TIF RGB biasa tidak terpengaruh |
| `test_tif_rgba_standar_sama_seperti_sebelumnya` | TIF RGBA standar (`ExtraSamples=2`) sama dengan/tanpa parameter |
| `test_non_tif_tidak_terpengaruh` | PNG dengan/tanpa `?alpha=1` byte-identik |
| `test_download_tidak_berubah` | `/api/download` byte-identik dengan file asli |
| `test_kp_bharata_mask_terbaca` | Data asli (LZW): alpha 9,6% cutout / 87,1% opaque, RGB identik dengan output default (di-skip otomatis bila data tidak tersedia) |

**Uji browser:** Edge headless + `playwright-core` terhadap stack Docker (`docker compose up -d --build`), memakai 4 model FBX asli + 1 OBJ tiruan (di-mock di browser; data tidak diubah) + preview/download TIF. Tidak ada request gagal atau error JavaScript.

Belum diuji: GPU fisik (uji memakai renderer software SwiftShader), perbandingan berdampingan dengan Windows 3D Viewer, dan browser mobile.

---

## 4. Risiko Kompatibilitas

| Risiko | Tingkat | Keterangan / mitigasi |
|---|---|---|
| Detail internal Pillow (`_mode`, raw mode tile) berubah di versi mendatang | Sedang | Pillow di-pin `12.*`. Kalau gagal, **otomatis fallback** ke RGB (kembali ke tampilan lama, tidak crash). Unit test `test_alpha_1_...` dan `test_kp_bharata_...` akan gagal lebih dulu saat upgrade Pillow |
| Channel ke-4 TIF ternyata bukan alpha | Rendah | Hanya berdampak pada material yang punya slot Opacity. Preview & download tidak terpengaruh |
| Tepi lubang bergerigi (`alphaTest` = ambang tegas) | Rendah | Mask di data saat ini hampir biner (3,3% gradasi) |
| Opacity map yang memang dimaksudkan semi-transparan (kaca bertekstur) jadi cutout | Rendah–Sedang | Tidak ada kasus di data saat ini. Kaca dengan `Opacity < 1` tanpa tekstur tetap transparan seperti sebelumnya |
| `DoubleSide`: flicker (z-fighting) pada model yang punya face ganda saling menempel | Rendah | Tidak terlihat di 4 model yang diuji. Tanpa tombol toggle (sesuai permintaan: UI tidak berubah) |
| Tekstur TIF model 3D sedikit lebih besar (PNG RGBA vs RGB) | Rendah | Hanya untuk TIF 4-channel |
| Klien lama yang meng-cache `index.html` versi lama | Tidak ada | Service worker tidak aktif; nginx melayani `index.html` dengan validasi ETag |
| Server lama + frontend baru (atau sebaliknya) | Tidak ada | Server lama mengabaikan `?alpha=1` (hasilnya seperti sebelumnya); frontend lama tidak mengirim parameter |

---

## 5. Cara Rollback

**Rollback penuh** (kembali ke commit sebelum perbaikan):

```bash
git checkout deead4c -- app/server.py static/index.html
rm -rf tests/                                             # opsional: hapus unit test
docker compose up -d --build                              # app/ ada di dalam image → perlu rebuild
```

`static/index.html` dilayani nginx dari bind mount, jadi perubahan frontend langsung berlaku setelah file dikembalikan (cukup refresh browser).

**Rollback sebagian:**

| Ingin | Cara |
|---|---|
| Kembalikan hanya tampilan (frontend) | `git checkout deead4c -- static/index.html`. Server boleh tetap versi baru: tanpa `?alpha=1`, perilakunya sama dengan versi lama |
| Matikan DoubleSide saja | Hapus baris `m.side=THREE.DoubleSide;` di `prepareFbxMaterials()` |
| Matikan cutout saja | Hapus pemanggilan `prepareFbxMaterials(obj);` dan `finishFbxMaterials(...)` di cabang FBX `load3D()` |
| Matikan pengambilan alpha TIF saja | Hapus baris `manager.setURLModifier(...)` di `load3D()`; tidak perlu rebuild |

---

## Catatan

- **Koreksi audit (§1.9 no. 1):** audit menduga tekstur yang sama dikonversi dua kali. Di browser nyata, request gambar identik digabung, sehingga `KP *.tif` hanya diminta **sekali**, baik sebelum maupun sesudah perbaikan.
- **Di luar lingkup (tidak diubah):** KRI Belati tampak hampir hitam, baik sebelum maupun sesudah perbaikan. Ini bukan akibat perubahan ini; perlu investigasi terpisah (kemungkinan normal/UV/tekstur).
- **Di luar lingkup (tidak diubah):** healthcheck nginx di `docker-compose.yml` gagal (`nginx:latest` tidak punya `wget`), sehingga container nginx berstatus *unhealthy* walaupun berfungsi normal.
