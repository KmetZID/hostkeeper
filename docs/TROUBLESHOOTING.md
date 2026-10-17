# Panduan Pemecahan Masalah (*Troubleshooting*)

Dokumen ini memuat daftar kode keluar (*exit codes*), katalog pesan error umum pada `hostkeeper`, penyebab terjadinya, serta panduan langkah demi langkah untuk mengatasinya.

---

## 1. Daftar Kode Keluar (*Exit Codes*)

`hostkeeper` menggunakan kode keluar standar yang konsisten untuk mempermudah integrasi dengan skrip shell dan sistem monitoring:

| Kode Keluar | Nama Konstanta | Arti dan Kondisi | Tindakan yang Disarankan |
|---|---|---|---|
| **0** | `EXIT_OK` | Operasi berhasil diselesaikan tanpa kesalahan, atau sistem dalam kondisi 100% patuh terhadap profil. | Tidak ada tindakan yang diperlukan. |
| **1** | `EXIT_ERROR` | Kesalahan eksekusi umum (misalnya proses eksternal gagal, error saat rollback, kegagalan operasi sistem berkas). | Periksa log error terperinci atau gunakan opsi `-v / --verbose` untuk melihat *stack trace*. |
| **2** | `EXIT_USAGE` | Argumen baris perintah tidak valid, sintaks YAML rusak, atau profil gagal melewati validasi skema. | Periksa parameter CLI atau perbaiki isi file `/etc/hostkeeper/profile.yml`. |
| **3** | `EXIT_DRIFT` | Perintah `verify` atau `status` mendeteksi bahwa konfigurasi sistem menyimpang dari profil target. | Bukan *crash*. Tinjau perubahan dengan `hostkeeper plan` lalu terapkan kembali dengan `sudo hostkeeper apply`. |
| **4** | `EXIT_LOCK` | Terjadi konflik lock; proses `hostkeeper` lain sedang berjalan di server. | Tunggu proses lain selesai, atau periksa proses yang memegang `/run/hostkeeper.lock`. |
| **5** | `EXIT_ENV` | Lingkungan sistem tidak memenuhi syarat (bukan root, OS tidak didukung, systemd tidak aktif, atau Python < 3.10). | Jalankan sebagai root (`sudo`), atau pastikan berjalan pada distro yang didukung. |

---

## 2. Pesan Error Umum dan Solusinya

### 2.1 `ERROR: apply membutuhkan root.`
- **Kode Keluar**: `5` (`EXIT_ENV`)
- **Penyebab**: Perintah mutasi (`apply`, `rollback`, `watch enable`, `watch disable`) dijalankan oleh pengguna biasa (`UID != 0`).
- **Solusi**:
  Jalankan perintah dengan hak akses superuser:
  ```bash
  sudo hostkeeper apply
  ```

---

### 2.2 `ERROR: hostkeeper lain sedang berjalan (/run/hostkeeper.lock terkunci).`
- **Kode Keluar**: `4` (`EXIT_LOCK`)
- **Penyebab**: File `/run/hostkeeper.lock` sedang dipegang oleh proses `hostkeeper` lain (misalnya proses `watch run` berkala atau administrator lain yang sedang menjalankan `apply`).
- **Solusi**:
  1. Tunggu beberapa detik hingga proses yang sedang berjalan selesai.
  2. Jika proses sebelumnya terhenti secara tidak normal (*hung*), temukan prosesnya:
     ```bash
     sudo fuser /run/hostkeeper.lock
     ```
  3. Matikan proses yang macet bila dipastikan sudah tidak beroperasi.

---

### 2.3 `ERROR: profil tidak valid: ...`
- **Kode Keluar**: `2` (`EXIT_USAGE`)
- **Penyebab**: File profil `/etc/hostkeeper/profile.yml` melanggar skema atau batasan validasi. Beberapa contoh pesan rincian:
  - `hostname '...' tidak sah`: Hostname tidak memenuhi standar RFC 1123 (misalnya memuat huruf besar, spasi, garis bawah `_`, atau simbol).
  - `timezone '...' tidak valid`: Zona waktu tidak ditemukan dalam direktori sistem `/usr/share/zoneinfo/` atau memuat traversal `..`.
  - `admin_user 'root' tidak diizinkan`: Kolom `admin_user` tidak boleh menggunakan nama `"root"`.
  - `kunci publik SSH tidak valid`: Format kunci publik SSH tidak dikenali atau bagian base64 rusak.
  - `aturan firewall '...' tidak sah`: Aturan harus mengikuti format `<port>/<proto>` (mis. `80/tcp`).
- **Solusi**:
  Perbaiki konfigurasi profil sesuai aturan di [docs/CONFIGURATION.md](CONFIGURATION.md) atau jalankan wizard interaktif untuk membuat profil baru yang valid:
  ```bash
  sudo hostkeeper setup
  ```

---

### 2.4 `Port tidak dapat diubah ke <port> karena ssh.socket aktif; ubah listen port socket terlebih dahulu atau gunakan port 22.`
- **Kode Keluar**: `1` (`EXIT_ERROR`)
- **Penyebab**: Pada distribusi modern (seperti Ubuntu 22.10+ / 24.04), layanan OpenSSH dikelola melalui unit systemd socket activation (`ssh.socket`). Mengubah `Port` pada `sshd_config` saja tidak akan mengubah port dengar socket systemd dan berisiko mengunci admin dari server.
- **Solusi**:
  Jika Anda ingin menggunakan port non-standar:
  1. Matikan socket activation dan beralih ke unit service OpenSSH tradisional:
     ```bash
     sudo systemctl disable --now ssh.socket
     sudo systemctl enable --now ssh.service
     ```
  2. Jalankan kembali:
     ```bash
     sudo hostkeeper apply
     ```
  3. Atau, pertahankan port SSH tetap bernilai `22` pada profil Anda.

---

### 2.5 `Safety timer aktif (90s). Jangan tutup sesi ini, uji dari terminal kedua.`
- **Status**: Bukan error (Informasi Keselamatan).
- **Penyebab**: Anda sedang menerapkan perubahan konfigurasi OpenSSH atau Firewall. `hostkeeper` mengaktifkan timer systemd di latar belakang untuk melindungi server dari risiko terputus.
- **Solusi**:
  1. **JANGAN menutup terminal yang sedang aktif**.
  2. Buka terminal baru dari komputer lokal Anda, lalu coba lakukan koneksi SSH ke server:
     ```bash
     ssh -p <PORT> <USER>@<IP_SERVER>
     ```
  3. Jika koneksi di terminal baru berhasil, kembali ke terminal pertama dan konfirmasikan bahwa koneksi berjalan normal. Safety timer akan dibatalkan otomatis.
  4. Jika koneksi terputus dan Anda tidak bisa mengakses terminal pertama, jangan panik: tunggu 90 detik, safety timer akan otomatis membatalkan perubahan dan memulihkan konfigurasi SSH lama.

---

### 2.6 `Izin file /etc/hostkeeper/watch.yml tidak aman (harus 0600).`
- **Kode Keluar**: `1` (`EXIT_ERROR`)
- **Penyebab**: File `/etc/hostkeeper/watch.yml` memuat izin akses yang dapat dibaca oleh pengguna non-root di sistem. Karena file ini memuat token webhook rahasia, izin longgar dilarang.
- **Solusi**:
  Kunci izin file hanya untuk root:
  ```bash
  sudo chmod 600 /etc/hostkeeper/watch.yml
  ```

---

### 2.7 `aktifkan venv: source .venv/bin/activate`
- **Kode Keluar**: `1`
- **Penyebab**: Skrip `scripts/check.sh` dijalankan di lingkungan luar virtual environment Python, sehingga perintah linter `ruff` tidak ditemukan di `PATH`.
- **Solusi**:
  Aktifkan virtual environment sebelum menjalankan skrip pemeriksaan:
  ```bash
  source .venv/bin/activate
  scripts/check.sh
  ```

---

### 2.8 Mengaktifkan Debug Trace (`--verbose`)
Jika Anda menghadapi kegagalan yang tidak terdokumentasi dan ingin melihat *full stack trace* Python:
```bash
hostkeeper -v plan
# atau
sudo hostkeeper -v apply
```
