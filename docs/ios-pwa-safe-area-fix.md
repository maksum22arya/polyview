# Perbaikan Safe-Area PWA iOS (Standalone)

Tanggal: 2026-09-26
Acuan: [ios-pwa-safe-area-audit.md](ios-pwa-safe-area-audit.md), rekomendasi §4.1–§4.4.
Masalah: setelah *Add to Home Screen* di iPhone muncul area kosong di bawah aplikasi (tidak muncul di Safari biasa).

**Ruang lingkup:** hanya CSS di `static/index.html`. **Tidak** mengubah JavaScript, `manifest.json`, meta tag, HTML, atau server.

---

## 1. File yang Diubah

| File | Perubahan |
|---|---|
| `static/index.html` | 6 aturan CSS di blok `<style>` (lihat §2) |
| `README.md` | Entri changelog |
| `docs/ios-pwa-safe-area-fix.md` | **Baru** (dokumen ini) |

Tidak disentuh: `manifest.json`, semua `<meta>`, markup HTML, seluruh `<script>`, server, Docker.

---

## 2. Perubahan CSS

Prinsip: safe-area **tidak lagi** dipasang sebagai padding pada `body` (yang membuat latar `body` tampil sebagai strip kosong). Latar header, sidebar, dan panel kini membentang sampai tepi layar, dan hanya **isi** yang digeser keluar dari area status bar, home indicator, dan notch.

### §4.1 `body`: padding safe-area dihapus

```diff
 body{
   font-family:'JetBrains Mono',monospace;
   background:var(--bg); color:var(--text);
   display:flex; flex-direction:column;
-  /* safe area for notch phones */
-  padding-top: env(safe-area-inset-top);
-  padding-bottom: env(safe-area-inset-bottom);
+  /* safe area: tidak dipasang di body, tapi di elemen tepi (header, tree, tombol)
+     agar latar panel membentang sampai tepi layar di iOS standalone */
 }
```

### §4.2 `header`: padding atas pindah ke header (+ §4.4 kiri/kanan)

```diff
 header{
-  height:var(--header-h); flex-shrink:0;
+  /* ikut membentang di balik status bar (black-translucent) */
+  height:calc(var(--header-h) + env(safe-area-inset-top)); flex-shrink:0;
   background:var(--sidebar);
   border-bottom:1px solid var(--sidebar-border);
   display:flex; align-items:center;
-  padding:0 14px; gap:10px;
+  padding:env(safe-area-inset-top) max(14px, env(safe-area-inset-right)) 0 max(14px, env(safe-area-inset-left));
+  gap:10px;
   position:relative; z-index:100;
 }
```

Tinggi area isi header tetap `--header-h` (52px) karena `box-sizing: border-box`; area status bar ditambahkan di atasnya dengan warna header.

### §4.3 Elemen dekat tepi bawah: offset home indicator

```diff
-.tree-wrap{flex:1;overflow-y:auto;overflow-x:hidden;padding:6px 0;}
+.tree-wrap{flex:1;overflow-y:auto;overflow-x:hidden;padding:6px 0 calc(6px + env(safe-area-inset-bottom));}
```
```diff
 .three-hint{
-  position:absolute;bottom:10px;left:50%;transform:translateX(-50%);
+  position:absolute;bottom:calc(10px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);
```
```diff
-.dl-wrap{position:absolute;bottom:16px;right:16px;z-index:20;}
+.dl-wrap{
+  position:absolute;z-index:20;
+  bottom:calc(16px + env(safe-area-inset-bottom));
+  right:calc(16px + env(safe-area-inset-right));     /* §4.4 */
+}
```
```diff
 @media (max-width: 640px) {
-  .three-hint { font-size:9px; bottom:8px; }
+  .three-hint { font-size:9px; bottom:calc(8px + env(safe-area-inset-bottom)); }
```

### §4.4 Landscape: notch kiri/kanan

Selain `header` dan `.dl-wrap` di atas:

```diff
 .sidebar{
   ...
   z-index:91;
+  padding-left:env(safe-area-inset-left); /* landscape: notch di kiri */
 }
```

`html, body { height: 100% }` **dipertahankan** (tidak diganti `100vh`/`100dvh`, sesuai audit §4.3).

---

## 3. Sebelum vs Sesudah

### 3.1 Hasil verifikasi (simulasi)

> Diuji di Edge headless dengan viewport iPhone 15 Pro. Nilai `env(safe-area-inset-*)` diganti angka iOS standalone (portrait: atas 59, bawah 34; landscape: kiri/kanan 59, bawah 21). Versi "sebelum" = CSS lama yang direkonstruksi persis (script gagal bila tidak cocok). **Bukan iPhone asli**; lihat §5.

| Cek | Safari portrait | Standalone portrait | Standalone landscape |
|---|---|---|---|
| **Strip kosong di bawah panel** | 0 → 0 px | **34 → 0 px** ✅ | **21 → 0 px** ✅ |
| Header dimulai di tepi atas (status bar berwarna header) | ya → ya | **tidak → ya** ✅ | ya → ya |
| Logo/menu di bawah status bar | ✅ → ✅ | ✅ → ✅ | ✅ → ✅ |
| Tombol Download di luar home indicator & notch | ✅ → ✅ | ✅ → ✅ | **❌ → ✅** |
| Hint kontrol 3D di atas home indicator | ✅ → ✅ | ✅ → ✅ | ✅ → ✅ |
| Item tree terakhir (setelah scroll) di atas home indicator | ✅ → ✅ | ✅ → ✅ | ✅ → ✅ |
| Header kiri/kanan di luar notch | ✅ → ✅ | ✅ → ✅ | **❌ → ✅** |
| Isi sidebar di luar notch kiri | — | — | **❌ → ✅** |

**Regresi desktop (1280×800, `env()` = 0):** screenshot tree dan preview 3D + tombol **identik piksel demi piksel** antara sebelum dan sesudah.

### 3.2 Visual

| | Sebelum | Sesudah |
|---|---|---|
| Standalone portrait, atas | Pita gelap `#0e0f11` setinggi status bar di atas header | Status bar menyatu dengan warna header |
| Standalone portrait, bawah | **Strip gelap kosong 34px** di bawah panel & sidebar | Panel & sidebar sampai tepi layar; tombol Download & hint tetap di posisi yang sama (di atas home indicator) |
| Standalone landscape | Logo, tree, dan tombol Download bisa tertutup notch; strip kosong 21px di bawah | Isi bergeser keluar dari notch; latar tetap penuh; tanpa strip |
| Safari biasa, desktop, Android tanpa inset | — | **Tidak berubah** |

---

## 4. Risiko

| Risiko | Tingkat | Keterangan |
|---|---|---|
| Elemen `position:absolute` dekat tepi bawah lupa diberi offset | Rendah | Semua sudah didata dan diberi offset: `.dl-wrap`, `.three-hint` (desktop & mobile), `.tree-wrap`. Tidak ada elemen `fixed` |
| Tombol **Reset/Wire** di toolbar preview mepet tepi kanan saat landscape | Rendah | **Belum ditangani**, karena tidak termasuk §4.4 audit. Toolbar berada di bawah header (bukan di area notch vertikal tertinggi), tetapi di iPhone landscape dengan notch di kanan, tombol bisa berada dekat sudut membulat. Bisa ditambah `padding-right: max(12px, env(safe-area-inset-right))` pada `.preview-toolbar` bila perlu |
| Sidebar landscape lebih sempit untuk isi (dikurangi inset kiri ±59px) | Rendah | Lebar sidebar tetap 280px (atau hasil resize); isi berkurang ±59px hanya di iPhone landscape dengan notch |
| Canvas 3D kini membentang ke area home indicator | Tidak ada | Diinginkan (seperti app native). Gesture home iOS memakai tepi paling bawah; interaksi 3D di atasnya tetap normal |
| Android Chrome edge-to-edge (Android 15+) | Rendah, positif | Chrome modern juga mengisi `safe-area-inset-*` untuk `viewport-fit=cover`; strip serupa di PWA Android ikut hilang |
| Browser lama tanpa `env()` / `max()` | Sangat rendah | Didukung sejak iOS 11.2+/Safari 11.1+ dan semua browser desktop modern. Di browser yang tidak mendukung, deklarasi `height`/`padding` header dibuang, sehingga header kehilangan tinggi tetap dan padding samping. Tidak relevan untuk perangkat yang masih didukung |
| Perlu *Add to Home Screen* ulang | Tidak | Hanya CSS. Cukup tutup paksa app lalu buka lagi (lihat §5) |

---

## 5. Langkah Verifikasi di iPhone

Karena hasil di atas berasal dari simulasi, lakukan verifikasi berikut di perangkat asli (iPhone dengan Face ID/Dynamic Island, mis. iPhone X ke atas):

**Persiapan**
1. Pastikan server sudah melayani `index.html` baru: di Mac/PC buka `http://<server>:<port>/`, *view source*, lalu cari `safe-area: tidak dipasang di body`.
2. Di iPhone: **tutup paksa** app PolyView (geser ke atas dari app switcher), lalu buka lagi dari Home Screen. Tidak perlu menghapus dan menambah ulang ke Home Screen. Kalau tampilan belum berubah, buka sekali di Safari biasa lalu tutup paksa app lagi.

**Portrait (mode standalone, dari ikon Home Screen)**
3. ✅ Tidak ada strip gelap di bawah; panel preview/tree sampai ke tepi bawah layar.
4. ✅ Status bar (jam, baterai) berada di atas latar berwarna sama dengan header; logo & tombol menu tepat di bawahnya.
5. ✅ Pilih file 3D: tombol **Download** dan teks hint ("1 jari: Putar…") berada **di atas** garis home indicator, tidak tertutup.
6. ✅ Buka drawer (☰), expand folder panjang, scroll ke paling bawah: item terakhir bisa di-tap dan tidak tertutup home indicator.

**Landscape (putar ke kiri dan ke kanan)**
7. ✅ Logo, tombol bahasa, isi tree, dan tombol Download tidak tertutup notch/Dynamic Island di sisi mana pun.
8. ✅ Tidak ada strip kosong di bawah.
9. ⚠️ Perhatikan tombol **Reset/Wire** di kanan atas panel preview (lihat §4, belum ditangani).

**Regresi**
10. ✅ Safari biasa (bukan dari Home Screen): tampilan sama seperti sebelumnya.
11. ✅ Desktop: tampilan sama seperti sebelumnya.

**Diagnostik bila masih ada gap** (Safari Web Inspector, Mac → Develop → [iPhone] → PolyView):
```js
({ innerHeight, screenH: screen.height,
   header: getComputedStyle(document.querySelector('header')).paddingTop,
   tree:   getComputedStyle(document.querySelector('.tree-wrap')).paddingBottom })
```
- `header` ±`59px` dan `tree` ±`40px` (6 + 34): CSS baru aktif.
- `innerHeight < screen.height`: bug tinggi viewport iOS (bukan CSS). Lihat audit §4.3 (opsi `100dvh`).

---

## 6. Rollback

Kembalikan 6 aturan CSS di §2 ke versi "sebelum" (baris `-` pada diff). Tidak perlu rebuild Docker: `static/` dilayani nginx dari bind mount, sehingga perubahan berlaku setelah refresh (iPhone: tutup paksa app).
