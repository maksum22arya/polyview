# Audit Layout PWA iOS (Standalone / Add to Home Screen)

Tanggal: 2026-09-26
Sifat: **read-only**. Tidak ada kode yang diubah.
Objek: `static/index.html` (meta tag & CSS layout), `static/manifest.json`.

**Masalah yang dilaporkan:** setelah *Add to Home Screen* di iPhone, muncul area kosong di bawah aplikasi. Di Safari biasa tidak muncul.

> **Keterbatasan:** audit ini tidak memakai iPhone asli. Kesimpulan diambil dari analisis kode, lalu dikonfirmasi dengan **simulasi** di browser headless: viewport iPhone 15 Pro 393×852, dengan nilai `env(safe-area-inset-*)` diganti angka standalone iPhone (atas 59px, bawah 34px). Langkah verifikasi di perangkat asli ada di §6.

---

## 1. Ringkasan

**Penyebab paling mungkin:** `body` diberi `padding-bottom: env(safe-area-inset-bottom)` ([index.html:42](../static/index.html#L42)).

- **Di mode standalone**, iOS mengisi nilai ini dengan tinggi area *home indicator* (±34px di iPhone ber-Face ID). Karena `body` memakai `box-sizing: border-box` dengan `height: 100%`, seluruh isi aplikasi menyusut 34px. Di bawahnya tersisa strip kosong berwarna latar `body` (`#0e0f11`), yang lebih gelap dan berbeda dari panel preview (`#121316`) dan sidebar (`#141518`).
- **Di Safari biasa (portrait)**, toolbar Safari berada di bawah halaman, sehingga nilai `safe-area-inset-bottom` = **0** dan strip itu tidak muncul. Inilah alasan masalah hanya terlihat di mode standalone.

`100vh`, `100dvh`, dan `100svh` **tidak dipakai** di mana pun, jadi bukan penyebab. `viewport-fit=cover` sudah benar dan justru diperlukan. Masalahnya ada pada **di elemen mana** safe-area diterapkan.

---

## 2. Temuan

### 2.1 `manifest.json`

| Field | Nilai | Penilaian |
|---|---|---|
| `display` | `standalone` | ✅ Benar. Ini yang membuat iOS membuka app tanpa UI Safari, sehingga safe-area bawah menjadi > 0 |
| `start_url` | `/` | ✅ |
| `background_color` | `#0e0f11` | ✅ Sama dengan `--bg` (warna splash) |
| `theme_color` | `#141518` | ✅ Sama dengan `<meta name="theme-color">` dan warna header |
| `orientation` | `any` | ✅. Catatan: landscape belum menangani safe-area kiri/kanan (§2.4) |
| `id`, `scope` | tidak ada | ⚪ Tidak berkaitan dengan layout. Opsional untuk identitas PWA |
| `icons` | 192 / 512 / maskable 512 | ✅. iOS memakai `apple-touch-icon`, bukan ikon manifest |

**Kesimpulan:** manifest **tidak menyebabkan** area kosong. Tidak perlu diubah untuk bug ini.

### 2.2 Meta tag PWA di `index.html`

| Baris | Tag | Penilaian |
|---|---|---|
| [5](../static/index.html#L5) | `viewport: width=device-width, initial-scale=1.0, viewport-fit=cover` | ✅ **Diperlukan.** Tanpa `viewport-fit=cover`, iOS membuat letterbox (bingkai kosong) di area notch dan home indicator, dan semua `env(safe-area-*)` bernilai 0 |
| [6](../static/index.html#L6) | `theme-color #141518` | ✅ |
| [7](../static/index.html#L7) | `apple-mobile-web-app-capable: yes` | ✅ Masih dibaca iOS; bersama `display: standalone` membuat app terbuka fullscreen |
| [8](../static/index.html#L8) | `apple-mobile-web-app-status-bar-style: black-translucent` | ✅, dengan konsekuensi: konten dirender **di bawah status bar**, sehingga butuh padding atas (sudah ada) |
| [9](../static/index.html#L9) | `apple-mobile-web-app-title` | ✅ |
| [10](../static/index.html#L10) | `mobile-web-app-capable` | ✅ (Android/Chrome) |
| [12](../static/index.html#L12) | `apple-touch-icon` → `/static/icons/apple-touch-icon.png` 180×180 | ✅ |

**Kesimpulan:** kombinasi meta tag sudah tepat untuk fullscreen edge-to-edge. Tidak perlu diubah.

### 2.3 Unit viewport & safe-area

| Item | Dipakai? | Lokasi | Catatan |
|---|---|---|---|
| `100vh` | ❌ tidak | — | Bagus. Di Safari biasa, `100vh` lebih tinggi dari area terlihat (termasuk area di balik toolbar) |
| `100dvh` / `100svh` / `100lvh` | ❌ tidak | — | Tidak diperlukan; lihat §4.3 |
| `height: 100%` pada `html, body` | ✅ | [index.html:35](../static/index.html#L35) | Mengikuti *initial containing block*: di standalone = seluruh layar (852px), di Safari = area terlihat. **Sudah benar** |
| `overflow: hidden` pada `html, body` | ✅ | [index.html:35](../static/index.html#L35) | Mencegah scroll halaman; tidak berkaitan dengan gap |
| `box-sizing: border-box` untuk semua elemen (`*`) | ✅ | [index.html:35](../static/index.html#L35) | Membuat padding `body` **mengurangi** ruang konten (bukan menambah tinggi) |
| `padding-top: env(safe-area-inset-top)` pada `body` | ✅ | [index.html:41](../static/index.html#L41) | Diperlukan karena `black-translucent`. Efek samping: area status bar berwarna `--bg`, bukan warna header |
| **`padding-bottom: env(safe-area-inset-bottom)` pada `body`** | ✅ | [index.html:42](../static/index.html#L42) | **Penyebab area kosong** |
| `env(safe-area-inset-left/right)` | ❌ tidak | — | Landscape: header & sidebar bisa tertutup notch (§2.4) |
| `.dl-wrap { bottom: 16px }` | ✅ | [index.html:279](../static/index.html#L279) | Saat ini aman *karena* body sudah dipadding. Kalau padding body dilepas, tombol ini harus diberi offset safe-area sendiri |
| `.three-hint { bottom: 10px / 8px }` | ✅ | [index.html:250](../static/index.html#L250), [315](../static/index.html#L315) | Sama seperti `.dl-wrap` |
| `.sidebar` mobile `position:absolute; height:100%` | ✅ | [index.html:300-301](../static/index.html#L300-L301) | Mengikuti tinggi `.main`, jadi ikut berhenti 34px sebelum tepi bawah |

### 2.4 Hasil simulasi (iPhone 15 Pro, portrait)

Diukur dengan `getBoundingClientRect()`. `innerHeight` = 852px pada ketiga skenario.

| Skenario | `#preview` (atas → bawah) | Tombol Download (bawah) | **Gap di bawah panel** |
|---|---|---|---|
| Safari biasa (inset bawah = 0) | 52 → **852** | 836 | **0 px** |
| **Standalone, CSS saat ini** (inset atas 59, bawah 34) | 111 → **818** | 802 | **34 px** strip warna `#0e0f11` |
| Standalone, **usulan** (§4) | 111 → **852** | 802 | **0 px** |

Screenshot simulasi memperlihatkan strip gelap selebar layar di bawah sidebar dan panel preview pada skenario "standalone saat ini". Strip itu hilang pada skenario usulan, sementara tombol Download tetap di atas area home indicator.

Temuan tambahan dari simulasi: area status bar (atas, 59px) juga berwarna `--bg` (`#0e0f11`), sedangkan header `#141518`. Ini bukan "kosong" seperti di bawah, tetapi tampak sebagai pita gelap di atas header. Perbaikannya searah (§4.2).

**Landscape** (iPhone ber-notch): `safe-area-inset-left/right` ±59px tidak ditangani. Tombol menu dan logo di header, serta sisi kiri sidebar, bisa tertutup notch atau Dynamic Island. Ini masalah terpisah yang ikut ditemukan.

### 2.5 Faktor lain yang dievaluasi

| Faktor | Penyebab? | Alasan |
|---|---|---|
| Service worker / cache | ❌ | SW tidak pernah ter-install (lihat [migration-stage1.md](migration-stage1.md)), jadi tidak ada `index.html` lama yang tertahan |
| Keyboard iOS (input "Cari file…") | ⚪ Kemungkinan kecil | Setelah keyboard ditutup, iOS kadang menyisakan offset scroll. `overflow:hidden` pada html/body umumnya mencegahnya. Perlu dicek kalau gap hanya muncul setelah mengetik |
| Bug WebKit tinggi viewport standalone (mis. setelah rotasi) | ⚪ Kemungkinan kecil | Pernah dilaporkan di beberapa versi iOS. Diagnostik §6 membedakannya: kalau `innerHeight` < `screen.height`, masalahnya ada di OS, bukan di CSS |
| `100vh` | ❌ | Tidak dipakai |

---

## 3. File yang Perlu Diubah

| File | Perlu? | Bagian |
|---|---|---|
| **`static/index.html`** | **Ya**, hanya CSS | `body` (baris 36-43), `header` (46-53), `.tree-wrap` (146), `.three-hint` (249-250 & 315), `.dl-wrap` (279), media query mobile (293-320) |
| `static/manifest.json` | Tidak | Tidak berkaitan dengan gap. (Opsional di luar bug: `id`, `scope`) |
| Meta tag di `index.html` | Tidak | Sudah benar, dan **jangan** hapus `viewport-fit=cover` |
| `static/sw.js`, server, Docker | Tidak | — |

---

## 4. Rekomendasi Implementasi

Prinsip: **jangan padding wadah terluar.** Biarkan latar panel membentang sampai tepi layar (di balik status bar dan home indicator), lalu terapkan safe-area hanya pada **isi** yang bisa disentuh atau dibaca.

### 4.1 Hapus padding bawah pada `body` (inti perbaikan)

```css
body{
  /* ... */
  padding-top: env(safe-area-inset-top);   /* sementara tetap; lihat 4.2 */
  /* padding-bottom dihapus */
}
```

### 4.2 (Disarankan) Pindahkan padding atas ke header

Supaya area status bar berwarna sama dengan header:

```css
body{ /* tanpa padding safe-area */ }
header{
  height: calc(var(--header-h) + env(safe-area-inset-top));
  padding-top: env(safe-area-inset-top);
}
```

### 4.3 Beri offset safe-area pada elemen dekat tepi bawah

```css
.tree-wrap{ padding-bottom: calc(6px + env(safe-area-inset-bottom)); }   /* item tree terakhir bisa di-scroll di atas home indicator */
.dl-wrap{ bottom: calc(16px + env(safe-area-inset-bottom)); }
.three-hint{ bottom: calc(10px + env(safe-area-inset-bottom)); }
@media (max-width:640px){
  .three-hint{ bottom: calc(8px + env(safe-area-inset-bottom)); }
}
```

`html, body { height: 100% }` **dipertahankan**. Tidak perlu beralih ke `100vh` (salah di Safari biasa), dan `100dvh` tidak memberi keuntungan di sini karena `height: 100%` sudah mengikuti viewport yang benar di kedua mode. Kalau diagnostik §6 menunjukkan bug WebKit, `height: 100dvh` bisa ditambahkan sebagai lapisan kedua (dengan fallback `100%` untuk iOS < 15.4).

### 4.4 (Opsional) Landscape: safe-area kiri/kanan

```css
header{ padding-left: max(14px, env(safe-area-inset-left)); padding-right: max(14px, env(safe-area-inset-right)); }
.sidebar{ padding-left: env(safe-area-inset-left); }
.dl-wrap{ right: calc(16px + env(safe-area-inset-right)); }
```

### Hasil yang diharapkan

| | Sebelum | Sesudah |
|---|---|---|
| Standalone, bawah | Strip gelap kosong 34px | Panel/sidebar sampai tepi layar; tombol & hint tetap di atas home indicator |
| Standalone, atas | Pita `#0e0f11` di atas header | Status bar menyatu dengan warna header |
| Safari biasa (portrait) | Normal | **Tidak berubah** (semua inset = 0) |
| Desktop / browser tanpa notch | Normal | **Tidak berubah** (`env()` = 0) |

---

## 5. Risiko Perubahan

| Risiko | Tingkat | Keterangan / mitigasi |
|---|---|---|
| Tombol Download atau hint tertutup home indicator bila offset lupa ditambahkan | Sedang | Semua elemen `position:absolute; bottom:…` sudah didaftar di §4.3 (hanya 2: `.dl-wrap`, `.three-hint`) |
| Item terakhir tree tertutup home indicator | Rendah | `.tree-wrap` diberi `padding-bottom` safe-area |
| Canvas 3D membentang ke area home indicator | Tidak ada | Diinginkan (sama dengan app native); interaksi di area itu tetap berfungsi, gesture home iOS memakai tepi paling bawah |
| Safari biasa landscape / toolbar tersembunyi | Rendah | Inset bawah bisa > 0 di Safari biasa (landscape). Perilakunya menjadi sama seperti standalone: panel sampai tepi, tombol tetap aman |
| Android Chrome edge-to-edge (Android 15+) | Rendah (positif) | Chrome modern juga mengisi `safe-area-inset-bottom` untuk `viewport-fit=cover`, sehingga strip yang sama kemungkinan muncul di PWA Android dan ikut hilang |
| Header lebih tinggi (4.2) | Rendah | Hanya di perangkat dengan inset atas > 0; tinggi konten header tetap `--header-h` |
| Perubahan meta/manifest butuh app di-*Add to Home Screen* ulang | Tidak relevan | Rekomendasi **hanya CSS**. Cukup tutup paksa app dan buka lagi; nginx melayani `index.html` dengan validasi ETag |
| Desktop | Tidak ada | `env()` bernilai 0 |

---

## 6. Verifikasi di iPhone Asli (disarankan sebelum & sesudah)

Karena audit ini berbasis simulasi, pastikan di perangkat:

1. **Konfirmasi penyebab (tanpa mengubah kode):** buka app dari Home Screen, lalu lihat strip bawah. Kalau tingginya ±34px (setinggi area home indicator) dan warnanya lebih gelap dari panel, penyebabnya adalah §1.
2. **Diagnostik (opsional, sementara):** tampilkan nilai berikut di layar via Safari Web Inspector (Mac → Develop → iPhone → PolyView):
   ```js
   ({ standalone: navigator.standalone,
      displayMode: matchMedia('(display-mode: standalone)').matches,
      innerHeight, screenH: screen.height,
      vv: visualViewport && visualViewport.height,
      sab: getComputedStyle(document.body).paddingBottom })
   ```
   - `innerHeight == screen.height` dan `sab ≈ 34px`: penyebabnya CSS (§1). Perbaikan §4 cukup.
   - `innerHeight < screen.height`: ada bug tinggi viewport dari iOS. Tambahkan `height: 100dvh` (§4.3).
3. **Setelah perbaikan**, uji: portrait & landscape, drawer sidebar terbuka, preview 3D (tombol Download dan hint), preview gambar, serta Safari biasa sebagai regresi.

---

*Audit selesai. Belum ada kode yang diubah; implementasi menunggu persetujuan, termasuk apakah §4.2 (padding atas ke header) dan §4.4 (landscape) ikut dikerjakan.*
