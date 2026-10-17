# Model dan Kebijakan Keamanan hostkeeper

Dokumen ini mendefinisikan model ancaman (*threat model*), batas keamanan, dan kebijakan mitigasi yang diterapkan dalam `hostkeeper`.

---

## 1. Aset yang Dilindungi (*Protected Assets*)

1. **Akses Jarak Jauh Administrator**: Ketersediaan konektivitas SSH agar server tidak pernah terisolasi atau terkunci secara permanen.
2. **Integritas Sistem Operasi**: Keutuhan konfigurasi dasar host (hostname, timezone, paket sistem, aturan firewall) dan perlindungan agar file pengguna yang sudah ada tidak terhapus atau tertimpa secara liar.
3. **Kerahasiaan Kredensial dan Kunci**: Kunci privat SSH, kunci publik resmi, dan token webhook eksternal agar tidak terekspos di log sistem, journal, atau audit publik.
4. **Stabilitas dan Efisiensi Sumber Daya**: Pencegahan konsumsi CPU/RAM liar atau proses looping pada eksekusi monitoring dan otomasi.

---

## 2. Model Ancaman (*Threat Model*)

### 2.1 Injeksi Perintah (*Command Injection*)
- **Ancaman**: Nilai profil YAML yang memuat karakter kontrol shell (seperti `;`, `|`, `&&`, backtick, atau baris baru) yang berpotensi dieksekusi secara berbahaya saat berinteraksi dengan sistem operasi.
- **Mitigasi**: `hostkeeper` sepenuhnya melarang `shell=True`, `os.system`, `eval`, dan `exec`. Semua eksekusi proses melalui `system.Runner` menggunakan list argumen biner eksplisit. Semua input profil divalidasi dengan pola ekspresi reguler (misalnya hostname RFC 1123, nama user Linux standar, port numerik).

### 2.2 Terkunci dari Akses Server (*Remote Access Lockout*)
- **Ancaman**: Kesalahan konfigurasi OpenSSH (misalnya mematikan `PasswordAuthentication` sebelum kunci publik terpasang dengan benar) atau aturan firewall yang memblokir port SSH, menyebabkan administrator kehilangan akses selamanya.
- **Mitigasi**:
  1. **Uji Coba Kunci Sementara**: `SshdStep` membuat keypair sementara, memasangnya pada akun admin, dan memverifikasi login via `ssh -o BatchMode=yes` sebelum menerapkan konfigurasi permanen.
  2. **Gerbang Konfirmasi Manusia**: Sebelum mematikan login kata sandi, pengguna diminta menguji dari terminal kedua dan mengetik konfirmasi `"ya"`.
  3. **Safety Timer Independen**: Perubahan berisiko tinggi mengaktifkan timer systemd transien (`hostkeeper-rollback-<run_id>`). Jika koneksi terputus dan sesi mati sebelum dikonfirmasi, timer akan menjalankan rollback otomatis secara independen.
  4. **Port SSH Selalu Diizinkan di Firewall**: Ruleset `nftables` secara otomatis menyertakan port SSH efektif di samping port lain yang ditentukan.

### 2.3 Kebocoran Data Rahasia (*Credential & Webhook Leakage*)
- **Ancaman**: URL webhook notifikasi (yang sering kali memuat token akses pribadi seperti Discord atau Slack webhook) terekspos dalam log sistem, journal, audit trace, atau pesan error.
- **Mitigasi**: Fungsi `mask_url` menyamarkan token rahasia sebelum dicatat ke log, audit, atau ditampilkan ke konsol. Izin file `/etc/hostkeeper/watch.yml` diverifikasi agar berizin ketat `0600`.

### 2.4 Modifikasi Tidak Sah pada Operasi Baca-Saja (*Read-Only Mutation*)
- **Ancaman**: Bug pada kode evaluasi atau pemantauan yang tidak sengaja mengubah konfigurasi saat menjalankan `plan`, `verify`, atau `status`.
- **Mitigasi**: Modus baca-saja menggunakan `ReadOnlyRunner` dan `ReadOnlyFileOps` yang melempar exception fatal `ReadOnlyViolation` jika ada upaya penulisan file atau eksekusi perintah mutasi (`mutates=True`).

---

## 3. Batas Keamanan dan Hak Akses

- **Operasi Non-Root**:
  - `hostkeeper plan`, `hostkeeper verify`, dan `hostkeeper status` dapat dijalankan oleh user biasa selama perintah sistem baca-saja diizinkan.
- **Operasi Root Wajib**:
  - `hostkeeper apply`, `hostkeeper rollback`, dan `hostkeeper watch enable/disable` mewajibkan hak akses root (`os.geteuid() == 0`). Jika dijalankan tanpa root, perintah langsung keluar dengan kode `EXIT_ENV` (5).
- **Isolasi Konfigurasi**:
  - `hostkeeper` hanya mengelola file dalam domainnya: `/etc/hostkeeper/`, drop-in `/etc/ssh/sshd_config.d/00-hostkeeper.conf`, drop-in sudoers `/etc/sudoers.d/`, dan tabel nftables mandiri `inet hostkeeper`. Konfigurasi manual pengguna di luar file ini tidak disentuh.

---

## 4. Di Luar Cakupan (*Out of Scope*)

Aspek-aspek berikut berada di luar batas tanggung jawab teknis `hostkeeper`:
1. **Keamanan Mesin Fisik dan Hypervisor**: Keamanan host fisik, BIOS/UEFI, maupun hypervisor virtualisasi diasumsikan telah diamankan oleh pemilik infrastruktur.
2. **Akses Root yang Terkompromi Sebelumnya**: Jika penyerang telah memiliki akses root (`uid 0`) pada sistem sebelum hostkeeper dipasang, integritas biner Python dan kernel berada di luar kendali hostkeeper.
3. **Mitigasi Serangan Jaringan Terdistribusi (DDoS)**: Firewall nftables hostkeeper menyaring port masuk pada level host, tetapi tidak dirancang untuk menangkal serangan banjir bandwidth skala besar yang membutuhkan proteksi upstream/edge network.
4. **Kerentanan pada Aplikasi Pengguna**: Bug keamanan pada perangkat lunak aplikasi pihak ketiga yang diinstal oleh pengguna (mis. web server, database, CMS) merupakan tanggung jawab masing-masing pengelola aplikasi.

---

## 5. Pelaporan Kerentanan

Jika Anda menemukan potensi celah keamanan atau kerentanan (*vulnerability*) pada `hostkeeper`, mohon **tidak membuat Issue publik** di GitHub.

Silakan laporkan secara rahasia dan aman melalui fitur resmi:
- **GitHub Private Vulnerability Reporting**: Buka tab **Security** di repositori repositori GitHub `KmetZID/hostkeeper`, lalu klik tombol **Report a vulnerability**.

Laporan Anda akan ditinjau secara privat, diverifikasi, dan perbaikan akan disiapkan sebelum diumumkan ke publik melalui GitHub Security Advisory.
