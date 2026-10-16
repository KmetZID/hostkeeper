# Model dan Kebijakan Keamanan hostkeeper

Dokumen ini mendefinisikan model ancaman (*threat model*), batas keamanan, dan kebijakan mitigasi yang diterapkan dalam `hostkeeper`.

---

## 1. Model Ancaman (*Threat Model*)

### 1.1 Injeksi Perintah (*Command Injection*)
- **Ancaman**: Nilai profil YAML yang memuat karakter kontrol shell (seperti `;`, `|`, `&&`, backtick, atau baris baru) yang berpotensi dieksekusi secara berbahaya saat berinteraksi dengan sistem operasi.
- **Mitigasi**: `hostkeeper` sepenuhnya melarang `shell=True`, `os.system`, `eval`, dan `exec`. Semua eksekusi proses melalui `system.Runner` menggunakan list argumen biner eksplisit. Semua input profil divalidasi dengan pola ekspresi reguler (misalnya hostname RFC 1123, nama user Linux standar, port numerik).

### 1.2 Terkunci dari Akses Server (*Remote Access Lockout*)
- **Ancaman**: Kesalahan konfigurasi OpenSSH (misalnya mematikan `PasswordAuthentication` sebelum kunci publik terpasang dengan benar) atau aturan firewall yang memblokir port SSH, menyebabkan administrator kehilangan akses selamanya.
- **Mitigasi**:
  1. **Uji Coba Kunci Sementara**: `SshdStep` membuat keypair sementara, memasangnya pada akun admin, dan memverifikasi login via `ssh -o BatchMode=yes` sebelum menerapkan konfigurasi permanen.
  2. **Gerbang Konfirmasi Manusia**: Sebelum mematikan login kata sandi, pengguna diminta menguji dari terminal kedua dan mengetik konfirmasi `"ya"`.
  3. **Safety Timer Independen**: Perubahan berisiko tinggi mengaktifkan timer systemd transien (`hostkeeper-rollback-<run_id>`). Jika koneksi terputus dan sesi mati sebelum dikonfirmasi, timer akan menjalankan rollback otomatis secara independen.
  4. **Port SSH Selalu Diizinkan di Firewall**: Ruleset `nftables` secara otomatis menyertakan port SSH efektif di samping port lain yang ditentukan.

### 1.3 Kebocoran Data Rahasia (*Credential & Webhook Leakage*)
- **Ancaman**: URL webhook notifikasi (yang sering kali memuat token akses pribadi seperti Discord atau Slack webhook) terekspos dalam log sistem, journal, audit trace, atau pesan error.
- **Mitigasi**: Fungsi `mask_url` menyamarkan token rahasia sebelum dicatat ke log, audit, atau ditampilkan ke konsol. Izin file `/etc/hostkeeper/watch.yml` diverifikasi agar berizin ketat `0600`.

### 1.4 Modifikasi Tidak Sah pada Operasi Baca-Saja (*Read-Only Mutation*)
- **Ancaman**: Bug pada kode evaluasi atau pemantauan yang tidak sengaja mengubah konfigurasi saat menjalankan `plan`, `verify`, atau `status`.
- **Mitigasi**: Modus baca-saja menggunakan `ReadOnlyRunner` dan `ReadOnlyFileOps` yang melempar exception fatal `ReadOnlyViolation` jika ada upaya penulisan file atau eksekusi perintah mutasi (`mutates=True`).

---

## 2. Batas Keamanan dan Hak Akses

- **Operasi Non-Root**:
  - `hostkeeper plan`, `hostkeeper verify`, dan `hostkeeper status` dapat dijalankan oleh user biasa selama perintah sistem baca-saja diizinkan.
- **Operasi Root Wajib**:
  - `hostkeeper apply`, `hostkeeper rollback`, dan `hostkeeper watch enable/disable` mewajibkan hak akses root (`os.geteuid() == 0`). Jika dijalankan tanpa root, perintah langsung keluar dengan kode `EXIT_ENV` (5).
- **Isolasi Konfigurasi**:
  - `hostkeeper` hanya mengelola file dalam domainnya: `/etc/hostkeeper/`, drop-in `/etc/ssh/sshd_config.d/00-hostkeeper.conf`, drop-in sudoers `/etc/sudoers.d/`, dan tabel nftables mandiri `inet hostkeeper`. Konfigurasi manual pengguna di luar file ini tidak disentuh.

---

## 3. Pelaporan Kerentanan

Jika Anda menemukan potensi kerentanan keamanan pada `hostkeeper`, silakan laporkan secara privat melalui fitur *Security Advisory* di repositori GitHub kami atau hubungi pemelihara repositori melalui surel. Mohon tidak membuat issue publik untuk celah keamanan yang belum diperbaiki.
