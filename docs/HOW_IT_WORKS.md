# Cara Kerja hostkeeper

Dokumen ini menjelaskan prinsip operasional, filosofi desain, dan mekanisme keselamatan di balik `hostkeeper` dalam bahasa yang sederhana dan lugas.

---

## Konsep Utama

### 1. Idempotensi (*Idempotency*)
Dalam rekayasa sistem, operasi yang idempoten adalah operasi yang memberikan hasil akhir yang sama persis, tidak peduli apakah operasi tersebut dijalankan satu kali atau seratus kali.
- Jika Anda mendefinisikan sebuah user admin dan paket `vim` di profil Anda, lalu menjalankan `hostkeeper apply`, sistem akan membuat user dan memasang paket tersebut.
- Jika Anda menjalankan `hostkeeper apply` kedua kalinya tanpa mengubah profil, `hostkeeper` akan mendeteksi bahwa sistem sudah berada pada status yang diharapkan (`[=] sudah sesuai`) dan **tidak akan melakukan pekerjaan berulang atau memulai ulang layanan tanpa alasan**.

### 2. Mengapa `check()` Bersifat Murni Baca-Saja (*Pure Read-Only*)
Di banyak alat otomatisasi, kode pemeriksaan status terkadang secara tidak sengaja memodifikasi status sistem (misalnya membuat file sementara di `/tmp`, menjalankan perintah yang mengubah timestamp file, atau menginstal paket untuk memeriksa versi).

Di `hostkeeper`, tahap evaluasi status (`step.check()`) dijamin **murni baca-saja (*pure read-only*)**:
- Perintah seperti `hostkeeper plan`, `hostkeeper verify`, dan `hostkeeper status` dipanggil untuk mengamati keadaan, bukan untuk mengubahnya.
- Modus baca-saja dilindungi oleh `ReadOnlyRunner` dan `ReadOnlyFileOps`. Jika seorang pengembang membuat bug yang mencoba menulis file atau mengeksekusi perintah mutatif saat `check()`, sistem operasi internal `hostkeeper` akan langsung melempar error fatal `ReadOnlyViolation`.
- Hal ini menjamin bahwa administrator dapat menjalankan `hostkeeper plan` atau monitoring berkala tanpa pernah khawatir kondisi server terganggu.

---

## Alur Kerja: Plan, Apply, Verify, Rollback

Siklus kerja `hostkeeper` dirancang seperti transaksi basis data yang transparan:

1. **Plan (Perencanaan Sebelum Bertindak)**:
   - Sebelum ada satu bit pun data di server yang diubah, `hostkeeper plan` membandingkan kondisi riil server saat ini dengan profil target Anda.
   - Hasilnya ditampilkan dalam tabel yang sangat jelas: apa yang akan dibuat `[+]`, apa yang akan diubah `[~]`, apa yang sudah sesuai `[=]`, dan berapa tingkat risikonya.
   - Administrator memegang kendali penuh dan tidak akan dikejutkan oleh perubahan tersembunyi.

2. **Apply (Eksekusi Terkendali)**:
   - Tahap penerapan mewajibkan hak akses root dan mengambil kunci non-blocking (`/run/hostkeeper.lock`) untuk mencegah tabrakan proses.
   - Setiap file sistem yang akan ditimpa selalu dicadangkan (*backup*) terlebih dahulu ke `/var/lib/hostkeeper/backups/<run_id>/`.
   - File baru ditulis secara atomik melalui file sementara lalu dipindahkan menggunakan `os.replace`, sehingga sistem tidak akan pernah membaca konfigurasi setengah jadi.
   - Jika ada langkah berisiko tinggi (seperti mengubah SSH atau Firewall), `SafetyTimer` diaktifkan otomatis.

3. **Verify (Validasi Instan Pasca-Eksekusi)**:
   - Begitu sebuah Step selesai dijalankan, `verify()` langsung dipanggil untuk membuktikan bahwa perubahan benar-benar aktif di tingkat sistem operasi (misalnya memastikan port baru benar-benar terbuka, bukan sekadar syntax file valid).
   - Jika validasi gagal, eksekusi dihentikan dan rollback otomatis dapat dipicu.

4. **Rollback (Jaring Pengaman Pemulihan)**:
   - Setiap eksekusi `apply` menghasilkan Journal JSON Lines yang mencatat file apa yang diubah dan lokasi cadangannya.
   - Jika konfigurasi baru menimbulkan masalah, administrator cukup menjalankan `sudo hostkeeper rollback <RUN_ID>` untuk mengembalikan seluruh file cadangan dan memanggil `step.undo()` secara terbalik.

---

## Eksekusi dan Keamanan Sistem

### 1. Perlindungan Anti-Terkunci SSH (*Anti-Lockout Mechanism*)
Mengubah konfigurasi OpenSSH pada server jarak jauh (remote VPS/cloud) adalah operasi paling berbahaya bagi administrator sistem. Sedikit kesalahan pada `sshd_config` bisa memutus koneksi dan membuat server tidak dapat diakses selamanya.

`hostkeeper` menerapkan 3 lapis perlindungan anti-terkunci:
- **Uji Coba Kunci Sementara**: Saat Anda mengonfigurasi SSH, `SshdStep` membuat sepasang kunci SSH sementara, menambahkannya ke akun admin, dan mencoba melakukan login simulasi lokal melalui `ssh -o BatchMode=yes` pada port target. Jika login gagal, konfigurasi baru ditolak dan dibatalkan sebelum menyentuh konfigurasi utama.
- **Deteksi `ssh.socket` Systemd**: Pada Ubuntu versi baru dan Debian modern, OpenSSH menggunakan socket activation (`ssh.socket`). Mengubah `Port` di sshd tanpa mengubah socket akan menyebabkan port baru tidak pernah dibuka. `hostkeeper` menolak perubahan port selain 22 jika `ssh.socket` aktif, memandu admin untuk menonaktifkan socket terlebih dahulu.
- **Konfirmasi Terminal Kedua**: Sebelum mematikan login berbasis kata sandi (`password_auth: false`), sistem mewajibkan administrator membuka terminal kedua, menguji koneksi login kunci, lalu mengetik konfirmasi `"ya"` secara eksplisit di konsol.

### 2. Safety Timer Independen
Bagaimana jika koneksi internet Anda tiba-tiba putus tepat saat OpenSSH atau firewall sedang dimulai ulang? Sesi terminal SSH Anda akan hang (*freeze*), sehingga Anda tidak bisa mengetikkan perintah konfirmasi atau membatalkan perubahan.

Untuk mengatasi ini, `hostkeeper` memanfaatkan `systemd-run` untuk menjadwalkan timer transien (`hostkeeper-rollback-<run_id>`) berdurasi 90 detik di latar belakang sistem:
- Timer ini berjalan independen dari sesi shell SSH Anda.
- Jika dalam 90 detik Anda berhasil mengonfirmasi bahwa koneksi bekerja normal, timer dibatalkan dengan aman.
- Namun jika sesi Anda terputus dan Anda tidak bisa membatalkan timer, timer systemd akan menyala secara otomatis dan mengeksekusi `hostkeeper rollback <run_id>`, memulihkan konfigurasi SSH lama sehingga server dapat Anda akses kembali.

### 3. Mengapa Menggunakan Drop-in `00-hostkeeper.conf`?
Banyak skrip konfigurasi lama mengedit file `/etc/ssh/sshd_config` secara langsung menggunakan `sed` atau mengganti seluruh isinya. Pendekatan ini sangat buruk karena:
- Menghapus komentar dan konfigurasi kustom yang sengaja dibuat oleh pemilik server.
- Menimbulkan konflik paket (*conffile prompt*) setiap kali sistem operasi memperbarui paket OpenSSH via `apt upgrade`.

OpenSSH versi modern (8.2+) secara bawaan mendukung direktori drop-in `/etc/ssh/sshd_config.d/`. `hostkeeper` menempatkan semua aturannya dalam file `/etc/ssh/sshd_config.d/00-hostkeeper.conf`:
- File `/etc/ssh/sshd_config` asli milik distro dan pengaturan pengguna lainnya tetap utuh 100%.
- Prefiks `00-` memastikan pengaturan `hostkeeper` diparsing pertama kali oleh OpenSSH (karena OpenSSH menerapkan prinsip *first-value-wins* untuk sebagian besar direktif).
- Proses rollback atau pencopotan menjadi sangat bersih: cukup hapus file `00-hostkeeper.conf` dan reload daemon SSH.

### 4. Mengapa Memiliki Tabel nftables Mandiri (`inet hostkeeper`)?
Alih-alih mengotak-atik rantai global iptables atau bertabrakan dengan alat lain seperti UFW atau Docker, `hostkeeper` memanfaatkan fitur arsitektur `nftables` yang modular:
- `hostkeeper` membuat tabel sendiri: `table inet hostkeeper`.
- Di dalam tabel ini, rantai input (`type filter hook input priority filter; policy drop;`) hanya memfilter lalu lintas yang didefinisikan pada profil (`firewall.allow`), koneksi `established,related`, dan antarmuka `lo` (loopback).
- Tabel mandiri ini tidak menyentuh tabel `inet filter` milik distro, tabel `nat` milik Docker, atau set yang dikelola oleh fail2ban.
- Persistensi aturan disimpan rapi pada `/etc/hostkeeper/nftables.rules` dan dipulihkan saat boot oleh unit oneshot `hostkeeper-firewall.service`.

---

## Monitoring dan Status

Subsistem `watch` dan `status` dirancang untuk memelihara kesehatan server tanpa membebani sumber daya komputasi:

### 1. Monitoring Tanpa Daemon Latar Belakang
Alih-alih menjalankan program daemon Python yang terus berjalan di latar belakang dan menghabiskan 30-50 MB memori secara statis, `hostkeeper` memanfaatkan penjadwal bawaan kernel dan sistem operasi:
- Unit timer `hostkeeper-watch.timer` memicu eksekusi `hostkeeper watch run` setiap 5 menit.
- Proses dijalankan dalam hitungan detik, mengumpulkan data, mengevaluasi ambang batas, mengirim webhook jika perlu, lalu keluar (*exit*).
- Penggunaan memori saat idle adalah **nol (0 bytes)**.

### 2. Lock Non-Blocking yang Bersahabat
Sebelum menjalankan siklus pengumpulan, `watch run` mencoba mengambil lock `/run/hostkeeper.lock` dalam mode non-blocking (`fcntl.LOCK_EX | fcntl.LOCK_NB`).
- Jika pada saat yang bersamaan administrator sedang menjalankan `sudo hostkeeper apply`, proses `watch` tidak akan memblokir atau menabrak eksekusi apply.
- Proses `watch` cukup mencatat bahwa server sedang sibuk dan keluar secara elegan dengan kode sukses (0), lalu menunggu siklus 5 menit berikutnya.

### 3. Logika Hysteresis dan Cooldown Alert
Masalah terbesar sistem monitoring adalah "alert fatigue" (kebisingan peringatan). Jika penggunaan RAM berfluktuasi di sekitar ambang batas 80% (misalnya 79.9% lalu 80.1% bolak-balik setiap menit), sistem monitoring biasa akan mengirim lusinan pesan berulang kali ke kanal chat Anda.

`hostkeeper` mencegah hal ini dengan dua mekanisme:
- **Hysteresis (Ambang Pemulihan Terpisah)**:
  - Peringatan `warn` aktif saat penggunaan memori mencapai **80%**.
  - Peringatan tidak akan dianggap pulih (`ok`) sampai penggunaan memori turun ke ambang pemulihan, misalnya **75%**.
  - Ini mencegah status berkedip (*flapping*) di perbatasan nilai.
- **Cooldown**:
  - Jika suatu kondisi buruk terus bertahan (misalnya RAM tetap di atas 80%), pesan alert tidak akan dikirim ulang secara terus-menerus pada setiap siklus 5 menit.
  - Parameter `cooldown_seconds` (bawaan: 3600 detik = 1 jam) memastikan Anda hanya mendapatkan pengingat ulang sekali setiap jam selama masalah belum selesai.

### 4. Penyimpanan SQLite Mode WAL dan Retensi Otomatis
- Semua riwayat metrik dan status transisi disimpan di `/var/lib/hostkeeper/state.db`.
- Menggunakan mode SQLite WAL (*Write-Ahead Logging*) untuk konkurensi pembacaan dan penulisan yang cepat dan aman terhadap *crash*.
- Setiap siklus `watch`, data metrik yang lebih tua dari 14 hari dipangkas otomatis (`DELETE FROM metrics WHERE timestamp < ?`), menjaga ukuran berkas database tetap kecil (beberapa megabyte saja).

### 5. Keamanan Webhook & Masking Token
URL Webhook untuk platform seperti Slack atau Discord umumnya memuat token rahasia di dalam query parameter atau path URL (misalnya `https://hooks.slack.com/services/T00/B00/SECRET_TOKEN`).
- Fungsi `mask_url()` pada modul notifikasi `hostkeeper` secara otomatis menyamarkan token menjadi `https://hooks.slack.com/services/T00/B00/******`.
- URL asli tidak akan pernah muncul di stdout, stderr, log journal, maupun audit trace sistem.
