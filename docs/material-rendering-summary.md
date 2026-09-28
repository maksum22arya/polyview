# Ringkasan: Masalah Tampilan Material FBX di PolyView

Ringkasan dari [material-rendering-audit.md](material-rendering-audit.md). Belum ada perubahan kode.

---

## Mengapa model kapal terlihat tembus pandang?

1. **Model yang terkena hanya 4 kapal**: Bharata, Sanjaya, Baladewa, dan Bisma. Di 3ds Max, keempatnya memakai satu gambar tekstur yang sekaligus berisi "stensil" (mask): bagian gambar yang harus terlihat dan bagian yang harus dilubangi, misalnya celah pada railing.

2. **Stensil itu hilang di tengah jalan.** Saat server mengubah gambar TIF menjadi format yang bisa dibaca browser, bagian stensilnya ikut terbuang. Browser menerima gambar tanpa informasi "mana yang harus dilubangi".

3. **Browser lalu menebak dengan cara yang salah.** Tanpa stensil, viewer memakai warna gambar sebagai ukuran tembus pandang. Akibatnya badan kapal hanya sekitar **35% terlihat** (seperti hantu), sedangkan bagian yang seharusnya berlubang malah lebih pekat (**±51%**).

4. **Stensil juga diperlakukan sebagai "kaca", bukan "lubang".** Seharusnya bagian yang dilubangi hilang bersih dan sisanya tampil padat. Yang terjadi, seluruh kapal dibuat semi-transparan seperti kaca, sehingga bagian dalam dan belakang kapal ikut terlihat.

## Mengapa bagian tipis hilang bila dilihat dari belakang?

5. **Viewer hanya menggambar satu sisi dari setiap permukaan.** Bagian tipis seperti railing, antena, atau baling-baling sering dibuat sebagai lembaran satu sisi. Dari depan terlihat, dari belakang hilang.

6. **Pengaturan "2-Sided" di 3ds Max tidak ikut tersimpan di file FBX**, dan PolyView tidak mengaturnya sendiri. Ini berlaku untuk **semua 11 model**. Sebagai catatan, model OBJ di PolyView sudah digambar dua sisi.

## Apakah dugaan awal benar?

7. **Ya, dugaan bahwa stensil dianggap sebagai transparansi (bukan potongan/cutout) benar.** Namun itu baru separuh masalah. Separuh lainnya adalah stensilnya sudah hilang di server sebelum sampai ke browser (poin 2). Keduanya harus diperbaiki agar hasilnya sama dengan Windows 3D Viewer.

## File yang perlu diubah

8. **`static/index.html`** (tampilan di browser): menambahkan langkah "merapikan material" setelah model dimuat, yaitu gambar dua sisi, dan stensil diperlakukan sebagai lubang, bukan kaca.

9. **`app/server.py`** (server): menjaga stensil pada gambar TIF agar tidak terbuang saat dikirim ke browser.

10. **Tambahan kecil:** file uji otomatis untuk bagian server, dan catatan di `README.md`. Pengaturan Docker, versi library 3D, dan fitur lain tidak perlu diubah.

## Risiko perubahan

11. **Risiko umumnya rendah**, karena perubahan hanya berlaku untuk model FBX. Daftar folder, preview gambar, download, dan model OBJ tetap seperti sekarang.

12. **Ada beberapa efek samping kecil yang mungkin terjadi:**
    - Beberapa model lain bisa sedikit berkedip di permukaan yang bertumpuk, karena sekarang digambar dua sisi.
    - Tepi lubang bisa tampak sedikit bergerigi.
    - Perbaikan di server memakai cara kerja internal library gambar (Pillow), jadi perlu diuji ulang saat library itu di-update.

## Rekomendasi

13. **Kerjakan dua perbaikan sekaligus:** server (menjaga stensil) dan browser (menggambar dua sisi, stensil sebagai lubang). Kalau hanya bagian browser yang dikerjakan, kapal sudah tidak tembus pandang, tetapi lubang-lubangnya belum muncul.

14. **Stensil hanya dikirim saat model 3D memintanya.** Dengan begitu, preview gambar TIF biasa dan file yang di-download tetap persis seperti sekarang. Ini pilihan yang paling aman.

15. **Sebelum mulai, perlu dua keputusan:**
    - Setuju dengan pendekatan di poin 14, atau stensil ikut ditampilkan juga di preview gambar?
    - Perlu tombol baru "2-Sided" untuk mematikan gambar dua sisi pada model yang bermasalah? (Ini mengubah tampilan toolbar.)

    Setelah diimplementasikan, hasilnya akan dicek dengan membandingkan screenshot PolyView dan Windows 3D Viewer secara berdampingan.
