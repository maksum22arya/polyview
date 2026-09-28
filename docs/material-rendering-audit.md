# Audit Import FBX & Rendering Material

Tanggal: 2026-09-26
Sifat: **read-only**. Tidak ada kode yang diubah.
Objek audit: pipeline FBX di `static/index.html` + `app/server.py`, Three.js **r128** dan `FBXLoader.js` **r128** (source diperiksa langsung dari CDN yang sama dengan yang dipakai app), serta semua FBX dan tekstur di `database3d/`.

Masalah yang dilaporkan:

1. Material dengan alpha/cutout mask dari 3ds Max tampil sebagai objek transparan penuh.
2. Hasilnya berbeda dengan Windows 3D Viewer.
3. Backface culling aktif, sehingga objek tipis hilang bila dilihat dari belakang.
4. Dugaan: alpha mask diperlakukan sebagai transparency, bukan cutout.

**Ringkasan:** dugaan no. 4 **benar**, tetapi itu baru separuh masalah. Ada **dua bug yang bertumpuk**:

- **(A) Server membuang channel alpha TIF.** Mask cutout-nya hilang sebelum sampai ke browser.
- **(B) FBXLoader mengubah opacity map menjadi `alphaMap` + `transparent: true`.** `alphaMap` di Three.js membaca **channel hijau (G)**, bukan alpha. Karena mask asli sudah hilang di (A), yang terbaca adalah warna hijau dari tekstur diffuse. Akibatnya kapal tampil ±35% opaque (tembus pandang), sementara area yang seharusnya terpotong malah ±51% opaque.

Backface culling (no. 3) adalah masalah terpisah. Penyebabnya: FBXLoader tidak pernah men-set `side`, dan PolyView juga tidak mengubahnya.

---

## 1. Temuan

### 1.1 Pipeline import FBX saat ini

```
Klik file .fbx di tree
  └─ onSelect() → load3D('/api/file/<path>', 'fbx')                    static/index.html:619
       └─ new THREE.FBXLoader().load(url, onLoaded, …)                  static/index.html:939
            ├─ FileLoader GET /api/file/<folder>/<nama>.fbx             (binary FBX apa adanya)
            ├─ BinaryParser → fbxTree
            ├─ parseImages(): Video.RelativeFilename → ambil basename   FBXLoader.js:179-220
            ├─ parseTextures(): TextureLoader.load(basename)            FBXLoader.js:335-385
            │    path = folder URL FBX → GET /api/file/<folder>/<tekstur>.tif
            │         └─ server.py: TIF → Pillow → PNG (RGB/RGBA)       app/server.py:101-113
            ├─ parseMaterials(): ShadingModel → MeshPhongMaterial       FBXLoader.js:410-450
            │    parseParameters(): mapping properti & slot tekstur     FBXLoader.js:454-600
            └─ callback onLoaded(obj)                                   static/index.html:908
                 └─ traverse: hanya isi material default kalau kosong; tidak menyentuh side/alpha
```

Poin penting:
- **Tidak ada post-processing material di PolyView.** `onLoaded` hanya mengisi material default kalau kosong dan mematikan `castShadow` ([index.html:909-914](../static/index.html#L909-L914)). Semua keputusan material berasal dari FBXLoader r128.
- Semua FBX di `database3d/` memakai **tekstur eksternal** (tidak ada konten embedded). Tekstur dimuat lewat `/api/file/...` di folder yang sama dengan FBX; semua basename ditemukan.
- Karena tekstur `.tif` dimuat lewat `/api/file`, **setiap tekstur TIF melewati konversi Pillow di server**. Ini titik di mana alpha hilang (§2.1).

### 1.2 Konversi material FBX ke Three.js (FBXLoader r128)

Diverifikasi dari source `three@0.128.0/examples/js/loaders/FBXLoader.js`:

| Properti / slot FBX | Hasil di Three.js | Catatan |
|---|---|---|
| `ShadingModel` `phong` / `lambert` / lainnya | `MeshPhongMaterial` / `MeshLambertMaterial` / Phong + warning | Semua FBX di `database3d` adalah `phong` |
| `Diffuse` / `DiffuseColor` (warna) | `color` | |
| `Opacity` (angka) | `opacity`; kalau `< 1.0` maka `transparent = true` | Semua file: `Opacity = 1.0` |
| Slot **`DiffuseColor`** (tekstur) | `map` (sRGB) | Channel alpha `map` **ikut dikalikan** ke `diffuseColor.a` (lihat §1.4) |
| Slot **`TransparentColor`** / **`TransparencyFactor`** (tekstur) | **`alphaMap` + `transparent = true`** | **Inti masalah.** Tidak ada opsi cutout sama sekali |
| `Bump`, `NormalMap`, `SpecularColor`, `EmissiveColor`, `ReflectionColor`, `DisplacementColor` | `bumpMap`, `normalMap`, `specularMap`, … | |
| `ShininessExponent`, `SpecularFactor`, `AmbientColor` | diabaikan (warning) | |
| **`side`** | **tidak di-set → `FrontSide`** (default Three.js) | Tidak ada satu pun referensi `side`/`DoubleSide` di FBXLoader |
| **`alphaTest`** | **tidak di-set → 0** | Tidak ada satu pun referensi `alphaTest` di FBXLoader |

Sebagai perbandingan, parser **OBJ** buatan PolyView memakai `side: THREE.DoubleSide` ([index.html:894](../static/index.html#L894)). Jadi OBJ dan FBX sudah berperilaku berbeda di aplikasi yang sama.

### 1.3 Isi FBX di `database3d/`

Diurai langsung dari file binary FBX (semua dibuat oleh FBX SDK 2020.x, plugin 3ds Max):

| Model | Material | Slot `DiffuseColor` | Slot `TransparentColor` |
|---|---|---|---|
| AS 332 Super Puma | as332superpuma | `AS 332 Super Puma.tif` | — |
| AS 365 N3 | AS365N3 | `AS 365 N3.tif` | — |
| AS 550 Fennec | as550 | `AS 550 Fennec.tif` | — |
| AS 565 Panther | AS565Panther | `AS 565 Panther.tif` | — |
| Bell 505 Jet Ranger X | bell505jetranger | `Bell 505 Jet Ranger X.tif` | — |
| **Bharata_8004** | bharata8004 | `KP Bharata.tif` | **`KP Bharata.tif`** (file yang sama) |
| **Sanjaya_7017** | sanjaya7017 | `KP Sanjaya.tif` | **`KP Sanjaya.tif`** (file yang sama) |
| **Baladewa_8002** | Baladewa_8002 | `KP Baladewa.tif` | **`KP Baladewa.tif`** (file yang sama) |
| **Bisma_8001** | Bisma_8001 | `KP Bisma.tif` | **`KP Bisma.tif`** (file yang sama) |
| KRI Balaputeradewa | Material #4, Material #108 | `KRI Balaputradewa.png`, `gun_assmbl.png` | — |
| KRI Belati | Belati | `KRI Belati.tif` | — |

Semua material: `Opacity = 1.0`, `TransparentColor` (warna) = `[1,1,1]`.

**Pola 3ds Max:** tekstur yang sama dipasang di slot Diffuse **dan** Opacity. Di Max ini adalah cara standar membuat cutout: Opacity map memakai **channel alpha** bitmap (`Mono Channel Output: Alpha`). Namun FBX **tidak menyimpan** pengaturan "pakai channel alpha" tersebut, hanya "tekstur X terhubung ke TransparentColor".

### 1.4 Isi tekstur: channel alpha ada di file, tetapi hilang di jalan

| Tekstur | SamplesPerPixel | ExtraSamples | Dibuka Pillow sebagai | Output `/api/file` |
|---|---|---|---|---|
| KP Bharata/Sanjaya/Baladewa/Bisma.tif | **4** | **0 (unspecified)** | `RGB` (raw `RGBX`, channel ke-4 **dibuang**) | PNG **RGB** |
| KRI Balaputradewa.tif, …1.tif, …2.tif | 4 | 0 | `RGB` | PNG RGB |
| KRI Belati.tif | 4 | 0 | `RGB` | PNG RGB |
| Helikopter AS 3xx, Bell 505, Balaputradewa3.tif | 3 | — | `RGB` | PNG RGB |

**Isi channel ke-4** pada TIF kapal (dibaca paksa sebagai alpha):

| Tekstur | Nilai 0 | Nilai 255 | Di antaranya | Kesimpulan |
|---|---|---|---|---|
| KP Bharata/Sanjaya/Baladewa/Bisma.tif | 9,6% | 87,1% | 3,3% | **Mask cutout** (hampir biner, dengan tepi anti-alias) |
| KRI Belati.tif | 8,4% | 88,4% | 3,2% | Mask (tidak dipakai sebagai opacity di FBX) |
| KRI Balaputradewa*.tif | 0,2% | 99,8% | 0,0% | Hampir penuh opaque |

Channel ke-4 bertipe *unspecified* (ExtraSamples=0) umum dihasilkan Photoshop/3ds Max untuk alpha. Aplikasi Autodesk/Adobe membacanya sebagai alpha, sedangkan **Pillow tidak** (dibuka sebagai `RGBX`, yaitu RGB + padding).

### 1.5 Yang sebenarnya dirender PolyView (kuantitatif)

Shader Three.js r128 (diverifikasi dari `three.min.js`):

```glsl
// map_fragment
vec4 texelColor = texture2D( map, vUv );
diffuseColor *= texelColor;                              // alpha map ikut dikalikan
// alphamap_fragment
diffuseColor.a *= texture2D( alphaMap, vUv ).g;          // ← channel HIJAU, bukan alpha
// alphatest_fragment
if ( diffuseColor.a < ALPHATEST ) discard;               // hanya jika alphaTest > 0
```

Untuk material kapal (`map` = `alphaMap` = PNG RGB hasil konversi):

| Area tekstur (menurut mask asli) | Opacity seharusnya | Opacity di PolyView (= rata-rata channel G) |
|---|---|---|
| Area **opaque** (lambung, dek, dll.) | 1,0 | **0,33–0,37** |
| Area **cutout** (seharusnya berlubang) | 0 (dibuang) | **0,51** |

Artinya kapal tampil ±⅓ opaque, seperti hantu atau kaca. Bagian yang seharusnya hilang malah lebih pekat daripada lambung. Karena `transparent = true`:
- Mesh dirender pada pass transparan dengan alpha blending, dan **diurutkan per objek, bukan per segitiga**. Dinding dalam dan belakang terlihat tembus dengan urutan yang salah (efek x-ray).
- Hasilnya terlihat seperti "objek transparan penuh", **sesuai laporan no. 1**.

Model helikopter dan KRI tidak punya slot `TransparentColor`, jadi **tidak terkena** bug alpha. Namun semuanya tetap terkena backface culling.

### 1.6 Backface culling

- FBXLoader tidak men-set `side`, sehingga semua material FBX memakai `FrontSide` dan face yang membelakangi kamera dibuang GPU.
- Model 3ds Max sering memakai **single-sided plane** untuk bagian tipis (railing, antena, rotor, sirip, jaring, kaca). Di Max, material bisa diberi opsi **2-Sided**, tetapi opsi ini **tidak diekspor** ke properti material FBX standar, sehingga FBXLoader tidak tahu. Akibatnya objek tipis hilang dari satu sisi (laporan no. 3).
- Bagian cutout (railing, jaring) hampir selalu berupa plane tipis, jadi kedua bug saling memperparah.

### 1.7 Evaluasi: apakah `DoubleSide` aman dijadikan default?

**Kesimpulan: aman dan disarankan untuk FBX di viewer ini, dengan syarat material cutout tidak memakai `transparent = true`.**

| Aspek | Penilaian |
|---|---|
| Pencahayaan sisi belakang | ✅ Benar. r128 membalik normal untuk back-face (`faceDirection = gl_FrontFacing ? 1.0 : -1.0`), jadi sisi belakang tidak gelap atau salah terang. |
| Performa | ✅ Dampak kecil. Hanya back-face yang terlihat ikut dirasterisasi; tidak ada geometri tambahan. Untuk viewer satu model tidak terasa. |
| Konsistensi | ✅ Menyamakan FBX dengan OBJ (sudah `DoubleSide`) dan dengan perilaku viewer umum. |
| Model yang sudah punya face ganda (face depan + face terbalik yang coplanar) | ⚠️ Bisa muncul z-fighting atau flicker. Jarang, dan bisa diatasi dengan toggle. |
| Model dengan normal terbalik | ➖ Saat ini bagian tersebut **hilang**; dengan DoubleSide akan **tampil**. Ini perbaikan, bukan risiko. |
| Material **transparan sungguhan** + DoubleSide | ⚠️ Di r128, DoubleSide transparan dirender dalam **satu pass**, sehingga urutan depan/belakang dalam satu mesh bisa salah. Tidak masalah untuk cutout (`alphaTest`, opaque pass, depth write aktif). Hanya relevan untuk kaca atau opacity parsial. |
| Mode wireframe | ✅ Tidak terpengaruh. |

### 1.8 Perbandingan dengan Windows 3D Viewer

> Catatan kejujuran: Windows 3D Viewer tidak bisa dijalankan di lingkungan audit ini dan source-nya tertutup. Kolom 3D Viewer di bawah berasal dari laporan pengguna ("hasil berbeda") dan perilaku umum viewer desktop; **belum diverifikasi**. Kolom PolyView diverifikasi dari source dan data.

| Aspek | PolyView saat ini (terverifikasi) | Windows 3D Viewer (perkiraan) | Dampak |
|---|---|---|---|
| Channel ke-4 TIF (ExtraSamples=0) | **Dibuang** (Pillow → RGB) | Kemungkinan dibaca sebagai alpha (decoder TIFF Windows/WIC) | Mask hilang di PolyView |
| Opacity map (`TransparentColor`) | `alphaMap` dari **channel G** + alpha blending | Diperlakukan sebagai mask/alpha tekstur | Kapal tembus pandang di PolyView |
| Mode alpha | Blend (`transparent`), tanpa `alphaTest` | Cutout/mask (tepi tegas, depth benar) | Efek x-ray di PolyView |
| Sisi face | `FrontSide` (culling) | Double-sided / tanpa culling | Objek tipis hilang di PolyView |
| Model shading | Phong (FBX legacy) | PBR | Perbedaan kilap & warna minor, di luar lingkup |

Langkah verifikasi yang disarankan sebelum implementasi: buka `KP Bharata.tif` di Photoshop/GIMP dan pastikan channel ke-4 memang mask cutout yang dimaksud (secara statistik sudah terlihat: 87% opaque, 9,6% nol).

### 1.9 Temuan sampingan

1. **Tekstur dimuat dan dikonversi dua kali.** Untuk kapal, `KP *.tif` (2048×2048) diminta dua kali (slot Diffuse dan Opacity), sehingga server menjalankan konversi TIF ke PNG dua kali per model.
2. **Tekstur gagal dimuat menjadi objek tak terlihat.** Kalau tekstur `alphaMap` gagal (404, TGA/PSD tidak didukung), Three.js men-sample tekstur kosong (0,0,0), sehingga `alpha × G = 0` dan mesh **hilang total**. Tidak ada penanganan error tekstur di PolyView.
3. **Preview gambar TIF juga kehilangan alpha.** Masalah (A) juga berlaku saat membuka `KP Bharata.tif` langsung di panel preview.
4. `alphaToCoverage` tersedia di r128, dan renderer PolyView sudah `antialias: true`. Opsi ini bisa dipakai untuk menghaluskan tepi cutout.

---

## 2. Penyebab Bug

| # | Gejala | Akar masalah | Lokasi |
|---|---|---|---|
| **C1** | Mask cutout tidak pernah sampai ke browser | TIF 4-channel dengan `ExtraSamples=0` dibuka Pillow sebagai `RGB` (`RGBX`). `server.py` hanya mempertahankan alpha untuk mode `RGBA/LA/PA`, sehingga PNG output **tanpa alpha** | [app/server.py:105-108](../app/server.py#L105-L108) + perilaku Pillow |
| **C2** | Opacity map dianggap transparency, bukan cutout (**laporan no. 4: benar**) | FBXLoader r128: slot `TransparentColor`/`TransparencyFactor` → `alphaMap` + `transparent = true`, tanpa `alphaTest` | `FBXLoader.js` r128 baris 579-582 (library, CDN) |
| **C3** | Nilai mask salah, bukan sekadar blending | `alphaMap` Three.js membaca **channel G**. Karena C1, G adalah warna hijau tekstur diffuse, bukan mask | Shader `alphamap_fragment` r128 |
| **C4** | Tampak "transparan penuh" / x-ray | Kombinasi C2 + C3: opacity ±0,35 di area solid, ditambah alpha blending tanpa depth sorting per segitiga | — |
| **C5** | Objek tipis hilang dari belakang (**laporan no. 3**) | FBXLoader tidak men-set `side` (default `FrontSide`); flag 2-Sided 3ds Max tidak ada di FBX; PolyView tidak meng-override | `FBXLoader.js` + [index.html:908-914](../static/index.html#L908-L914) |
| **C6** | Berbeda dengan Windows 3D Viewer (**laporan no. 2**) | Akibat C1 + C2 + C5. Tidak ada tahap normalisasi material di PolyView | [index.html:908-921](../static/index.html#L908-L921) |

---

## 3. Solusi yang Direkomendasikan

Diurutkan sesuai prioritas. Semuanya **tanpa mengganti versi Three.js/FBXLoader** (tetap r128 dari CDN).

### S1. Server: pertahankan channel ke-4 TIF sebagai alpha (memperbaiki C1)

Di konversi TIF ([app/server.py:101-113](../app/server.py#L101-L113)): kalau `SamplesPerPixel == 4`, mode Pillow `RGB`, dan raw mode tile `RGBX` (channel ke-4 *unspecified*), buka ulang dengan raw mode `RGBA` sehingga PNG hasil konversi membawa alpha. Kalau gagal, fallback ke perilaku sekarang (RGB).

Dua opsi cakupan:

| Opsi | Cara | Kelebihan | Kekurangan |
|---|---|---|---|
| **S1-a (disarankan)** | Alpha hanya dipertahankan bila diminta: `/api/file/<path>?alpha=1`. Frontend menambahkan `?alpha=1` **hanya** untuk request tekstur dari FBXLoader (lewat `LoadingManager.setURLModifier`) | Respons default `/api/file` **tidak berubah**. Preview gambar dan download tetap sama | Menambah satu query parameter opsional ke API |
| S1-b | Selalu pertahankan alpha untuk TIF 4-channel | Paling sederhana. Preview TIF ikut menampilkan transparansi (sesuai Photoshop) | Mengubah output `/api/file` untuk semua TIF 4-channel. `KP *.tif` di preview akan tampak berlubang 9,6% |

Implementasi memakai detail internal Pillow (mengganti raw mode tile). Alternatifnya library `tifffile` + `imagecodecs` untuk LZW, tetapi ini menambah ±30–60 MB ke image Docker. Disarankan tetap memakai Pillow, dengan unit test dan pin versi.

### S2. Frontend: normalisasi material setelah load FBX (memperbaiki C2, C3, C5)

Tambahkan fungsi `normalizeFbxMaterials(object)` yang dipanggil di `onLoaded` untuk FBX saja (OBJ tidak berubah). Aturan per material (termasuk material array):

```text
1. side = DoubleSide                                                     (C5)

2. Jika material punya alphaMap (berasal dari slot TransparentColor/TransparencyFactor):
     a. Jika alphaMap berasal dari file yang SAMA dengan map (diffuse):
          → hapus alphaMap; pakai channel alpha dari map (butuh S1)      (C3)
     b. Jika file berbeda (opacity map grayscale terpisah):
          → pertahankan alphaMap (untuk gambar grayscale, G = luminance = mask yang benar)
     c. Mode cutout:  alphaTest = 0.5, transparent = false, depthWrite = true   (C2)
        (opsional) alphaToCoverage = true untuk tepi halus (MSAA sudah aktif)
     d. Jika tekstur alphaMap gagal dimuat → hapus alphaMap (hindari mesh hilang total)

3. Jika TIDAK ada alphaMap tetapi opacity < 1 (kaca, transparansi sungguhan):
     → tetap transparent = true (perilaku sekarang), depthWrite = false

4. material.needsUpdate = true
```

Cara mendeteksi "file yang sama" (2a): FBXLoader memuat tekstur secara asinkron, jadi perbandingan dilakukan setelah semua tekstur selesai. Gunakan `THREE.LoadingManager` khusus untuk FBXLoader dan jalankan normalisasi di `manager.onLoad`, dengan membandingkan `map.image.src === alphaMap.image.src`. `setURLModifier` di manager yang sama dipakai untuk S1-a.

Kalau S1 **tidak** dikerjakan, langkah 2a tetap memperbaiki efek tembus pandang: material menjadi opaque dan depth benar, tetapi **tanpa lubang cutout**, karena mask memang tidak tersedia. Ini masih jauh lebih baik dari kondisi sekarang, tetapi belum sama dengan 3D Viewer.

### S3. (Opsional) Hindari konversi TIF ganda

Aktifkan `THREE.Cache.enabled = true` sebelum load FBX, atau deduplikasi URL di `setURLModifier`, supaya tekstur yang sama tidak dikonversi dua kali oleh server. Catatan: cache Three.js hanya efektif setelah request pertama selesai; request paralel tetap bisa ganda. Deduplikasi penuh butuh cache di server (di luar lingkup).

### S4. (Opsional, UI) Toggle "2-Sided"

Tombol di toolbar (di samping *Wire*) untuk kembali ke `FrontSide` pada model yang bermasalah dengan DoubleSide (z-fighting). Ini **mengubah UI**, jadi hanya dikerjakan bila disetujui. Tanpa toggle, S2 tetap berfungsi.

### Hasil yang diharapkan setelah S1 + S2

| Model | Sebelum | Sesudah |
|---|---|---|
| Bharata / Sanjaya / Baladewa / Bisma | Tembus pandang ±35%, efek x-ray, area cutout justru pekat | Opaque penuh, area mask (9,6%) terpotong tegas, depth benar |
| Helikopter, KRI Belati, KRI Balaputradewa | Opaque; bagian tipis hilang dari belakang | Opaque; bagian tipis terlihat dari dua sisi |
| OBJ | DoubleSide, tanpa tekstur | Tidak berubah |

---

## 4. Risiko Perubahan

| Perubahan | Risiko | Tingkat | Mitigasi |
|---|---|---|---|
| S1: raw mode Pillow `RGBX` → `RGBA` | Bergantung pada detail internal Pillow (`tile`, mode); bisa berubah di Pillow 13/14 | Sedang | Pin `pillow==12.*` (sudah), unit test dengan `KP Bharata.tif`, fallback ke RGB bila gagal |
| S1: channel ke-4 bukan alpha | Beberapa TIF memakai channel ekstra untuk hal lain (spot color, mask seleksi) | Rendah | Dengan S1-a, alpha hanya dipakai untuk tekstur FBX, dan hanya berpengaruh bila material memang punya opacity map |
| S1-b: output `/api/file` berubah | Preview TIF 4-channel menampilkan area transparan; perubahan perilaku API | Sedang | Pilih S1-a |
| S2: `alphaTest = 0.5` | Mask dengan gradasi lembut (rambut, asap, daun) menjadi bergerigi | Rendah (data saat ini: mask hampir biner, 3,3% gradasi) | `alphaToCoverage`; threshold bisa disesuaikan |
| S2: material dengan opacity map yang memang dimaksudkan semi-transparan (kaca bertekstur) | Menjadi cutout (opaque/lubang), bukan tembus | Rendah–Sedang | Aturan: kalau alpha mask punya >X% nilai tengah, pertahankan blending. Bisa ditambahkan setelah ada contoh data |
| S2: `DoubleSide` default | Z-fighting pada model dengan face ganda; transparan+DoubleSide urutan salah (r128) | Rendah | S4 (toggle), cutout tidak memakai blending |
| S2: `manager.onLoad` | Kalau satu tekstur gagal, `onLoad` tetap terpanggil (r128 menghitung item selesai/gagal), tetapi urutan dengan `onLoaded` FBX perlu dijaga | Rendah | Normalisasi dijalankan di kedua titik (idempoten) |
| Umum | Perubahan hanya pada **FBX**. OBJ, gambar, tree, dan download tidak tersentuh (kecuali S1-b) | — | Uji regresi di semua 11 FBX di `database3d/` |
| Cache browser / SW | Tidak relevan: SW tidak ter-install (lihat migration-stage1). `index.html` dilayani dengan validasi ETag, jadi perubahan langsung terlihat | — | — |

---

## 5. File yang Perlu Diubah

| File | Perubahan | Solusi |
|---|---|---|
| [static/index.html](../static/index.html) | `load3D()`: buat `THREE.LoadingManager` untuk FBXLoader (`setURLModifier` → `?alpha=1` untuk ekstensi gambar; `onLoad`/`onError`). Tambah fungsi `normalizeFbxMaterials()` dan panggil untuk FBX. (Opsional) `THREE.Cache.enabled`. (Opsional, UI) tombol 2-Sided | S1-a (sisi klien), S2, S3, S4 |
| [app/server.py](../app/server.py) | Konversi TIF di `api_file()`: deteksi TIF 4-channel `ExtraSamples=0` dan pertahankan sebagai RGBA. Dengan S1-a hanya bila `request.args.get('alpha') == '1'`. Fallback ke RGB | S1 |
| `tests/` (baru) | Unit test konversi TIF (RGB 3-channel tetap RGB; 4-channel + `alpha=1` menjadi RGBA dengan histogram alpha sesuai; tanpa `alpha` tetap RGB) | S1 |
| [README.md](../README.md) | Dokumentasikan query `?alpha=1` di tabel endpoint (jika S1-a) | S1-a |
| `docs/material-rendering-fix.md` (baru) | Catatan implementasi & hasil uji visual | — |

**Tidak perlu diubah:** `static/sw.js`, `static/manifest.json`, `Dockerfile`, `docker-compose.yml`, `deploy/nginx/polyview.conf`, `requirements.txt` (Pillow tetap), dan versi Three.js/FBXLoader di CDN.

**Rencana uji setelah implementasi:**
1. Unit test konversi TIF (server).
2. Visual di browser: Bharata_8004, Sanjaya_7017, Baladewa_8002, Bisma_8001 (cutout); AS 550 Fennec dan KRI Belati (backface pada bagian tipis); satu OBJ (regresi).
3. Bandingkan screenshot berdampingan dengan Windows 3D Viewer dan render 3ds Max (`rend.png`/screenshot di folder model).
4. Cek tidak ada request/konversi tekstur yang gagal di log Gunicorn.

---

*Audit selesai. Belum ada kode yang diubah; implementasi menunggu persetujuan, termasuk pilihan S1-a vs S1-b dan apakah S4 (perubahan UI) ikut dikerjakan.*
