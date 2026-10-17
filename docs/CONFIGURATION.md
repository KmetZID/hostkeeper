# Panduan Konfigurasi hostkeeper

Dokumen ini memuat referensi lengkap dan mendalam mengenai format konfigurasi profil server (`profile.yml`) dan konfigurasi monitoring sistem (`watch.yml`).

---

## 1. Konfigurasi Profil Utama (`profile.yml`)

File konfigurasi profil mendefinisikan status target (*desired state*) yang harus dicapai oleh server. File default berada pada `/etc/hostkeeper/profile.yml`, atau dapat diarahkan ke berkas lain melalui opsi `-c / --config <PATH>`.

### 1.1 Skema dan Kolom `profile.yml`

| Kolom | Tipe Data | Wajib? | Nilai Bawaan | Deskripsi & Aturan Validasi |
|---|---|---|---|---|
| `version` | `integer` | **Ya** | - | Versi skema profil. Saat ini hanya mendukung nilai `1`. |
| `hostname` | `string` | Tidak | `null` | Hostname statis sistem sesuai RFC 1123. Label maksimal 63 karakter, total maksimal 253 karakter, alfanumerik huruf kecil dan tanda minus `-`, tidak boleh diawali/diakhiri tanda minus. |
| `timezone` | `string` | Tidak | `null` | Zona waktu sistem. Wajib merujuk ke file valid dalam `/usr/share/zoneinfo/` (mis. `"Asia/Jakarta"`, `"UTC"`). Tidak mengizinkan path traversal (`..`) atau path absolut. |
| `packages` | `list of string` | Tidak | `[]` | Daftar nama paket APT dasar yang harus terpasang. Maksimal 100 paket. Nama paket harus memenuhi pola regex `^[a-z0-9][a-z0-9+.-]*$`. |
| `admin_user` | `string` | Tidak | `null` | Nama akun pengguna administrator lokal. Maksimal 32 karakter, dilarang menggunakan `"root"`, regex `^[a-z_][a-z0-9_-]*[$]?$`. |
| `admin_sudo_nopasswd` | `boolean` | Tidak | `false` | Jika bernilai `true`, akun `admin_user` diberikan hak akses sudo tanpa kata sandi via drop-in `/etc/sudoers.d/hostkeeper-<admin_user>`. |
| `ssh_authorized_keys` | `list of string` | Tidak | `[]` | Daftar kunci publik SSH untuk akun `admin_user`. Mendukung tipe kunci: `ssh-ed25519`, `ssh-rsa`, `ecdsa-sha2-nistp256`, `ecdsa-sha2-nistp384`, `ecdsa-sha2-nistp521`, `sk-ssh-ed25519@openssh.com`, `sk-ecdsa-sha2-nistp256@openssh.com`. Bagian blob base64 divalidasi secara ketat. |
| `ssh` | `mapping` | Tidak | `null` | Pengaturan hardening daemon OpenSSH. Lihat rincian sub-field di bawah. |
| `firewall` | `mapping` | Tidak | `null` | Pengaturan aturan firewall nftables. Lihat rincian sub-field di bawah. |
| `unattended_upgrades`| `boolean` | Tidak | `null` | Mengonfigurasi pembaruan keamanan otomatis via paket `unattended-upgrades`. |

### 1.2 Sub-Field `ssh`

| Kolom | Tipe Data | Nilai Bawaan | Deskripsi |
|---|---|---|---|
| `port` | `integer` | Port aktif (22) | Port dengar OpenSSH (rentang 1-65535). **Catatan**: Jika layanan `ssh.socket` aktif pada sistem, perubahan ke port selain 22 akan ditolak sampai socket dinonaktifkan. |
| `permit_root_login` | `string` / `boolean` | Nilai aktif | Pengaturan izin login user root. Nilai yang sah: `"yes"`, `"no"`, `"prohibit-password"`, `"forced-commands-only"`. Boolean `true` dipetakan ke `"yes"` dan `false` ke `"no"`. |
| `password_auth` | `boolean` | Nilai aktif | Jika bernilai `false`, mematikan autentikasi kata sandi (`PasswordAuthentication no`). Mengubah ke `false` mewajibkan adanya kunci pada `ssh_authorized_keys` dan konfirmasi interaktif. |

### 1.3 Sub-Field `firewall`

| Kolom | Tipe Data | Nilai Bawaan | Deskripsi |
|---|---|---|---|
| `allow` | `list of string` | `[]` | Daftar port dan protokol jaringan yang diizinkan masuk (*incoming traffic*). Setiap aturan wajib berformat `<port>/<proto>` di mana port bernilai 1-65535 dan proto adalah `tcp` atau `udp`. Contoh: `["22/tcp", "80/tcp", "443/tcp"]`. |

### 1.4 Contoh Lengkap `profile.yml`

```yaml
version: 1
hostname: web-01
timezone: Asia/Jakarta

packages:
  - curl
  - htop
  - vim
  - git

admin_user: deployer
admin_sudo_nopasswd: true

ssh_authorized_keys:
  - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyForHostkeeperProfileDocOnly12345 user@example"

ssh:
  port: 22
  permit_root_login: "no"
  password_auth: false

firewall:
  allow:
    - 22/tcp
    - 80/tcp
    - 443/tcp

unattended_upgrades: true
```

---

## 2. Konfigurasi Monitoring (`watch.yml`)

File konfigurasi pemantauan disimpan di `/etc/hostkeeper/watch.yml`. Untuk alasan keamanan token webhook, file ini **wajib memiliki izin akses mode `0600`** (hanya dapat dibaca oleh pemilik berkas/root).

### 2.1 Kolom Utama `watch.yml`

| Kolom | Tipe Data | Nilai Bawaan | Deskripsi |
|---|---|---|---|
| `webhook_url` | `string` | `null` | URL target pengiriman notifikasi webhook. Mendukung platform Slack, Discord, atau endpoint HTTP custom. |
| `webhook_format` | `string` | `"slack"` | Format struktur data webhook yang dikirimkan. Pilihan nilai: `"slack"`, `"discord"`, atau `"json"`. |
| `cooldown_seconds` | `float` / `int` | `3600.0` (1 jam) | Durasi jeda minimum dalam detik sebelum peringatan untuk masalah yang sama dikirimkan ulang. |
| `thresholds` | `mapping` | Nilai default | Pemetaan konfigurasi ambang batas metrik. Lihat rincian di bawah. |

### 2.2 Struktur Ambang Batas (*Thresholds*) dan Hysteresis

Setiap metrik di bawah `thresholds` dapat mengonfigurasi tiga nilai batas:
- `warn`: Batas memicu status peringatan (*warning*).
- `crit`: Batas memicu status kritis (*critical*) (opsional).
- `recover`: Batas untuk menyatakan metrik telah pulih normal (*recovery / hysteresis*) (opsional).

### 2.3 Daftar Lengkap Metrik dan Nilai Bawaan

| Kunci Threshold | Tipe Nilai | Bawaan `warn` | Bawaan `crit` | Bawaan `recover` | Deskripsi Metrik |
|---|---|---|---|---|---|
| `mem_used_percent` | Persentase | `80.0` | `90.0` | `75.0` | Persentase memori RAM terpakai dari `/proc/meminfo`. |
| `swap_used_percent` | Persentase | `50.0` | `80.0` | `40.0` | Persentase ruang swap terpakai. |
| `disk_used_percent` | Persentase | `80.0` | `90.0` | `75.0` | Persentase kapasitas disk terpakai pada partisi root (`/`). |
| `disk_inodes_used_percent` | Persentase | `80.0` | `90.0` | `75.0` | Persentase inode sistem berkas terpakai pada partisi root (`/`). |
| `cpu_load_per_core` | Rasio | `2.0` | `4.0` | `1.5` | Beban prosesor 1 menit dibagi jumlah inti CPU (`cpu.load1 / cores`). |
| `psi_cpu_some_avg10` | Persentase | `25.0` | `50.0` | `15.0` | Pressure Stall Information: tekanan beban CPU 10 detik terakhir. |
| `psi_memory_some_avg10` | Persentase | `25.0` | `50.0` | `15.0` | Pressure Stall Information: tekanan alokasi RAM 10 detik terakhir. |
| `psi_io_some_avg10` | Persentase | `25.0` | `50.0` | `15.0` | Pressure Stall Information: hambatan operasi I/O disk 10 detik terakhir. |
| `services_failed_count` | Integer | `1` | `1` | `0` | Jumlah unit layanan systemd yang berada dalam status gagal (*failed*). |
| `updates_security` | Integer | `1` | `5` | `0` | Jumlah pembaruan keamanan APT tertunda yang belum dipasang. |
| `updates_reboot_required` | Boolean | `true` | - | `false` | Status apakah file `/run/reboot-required` ada pada sistem. |
| `ssh_failed_logins` | Integer | `10` | `50` | `5` | Jumlah percobaan login SSH gagal dalam rentang 10 menit terakhir. |
| `time_ntp_synchronized` | Boolean | `false` | - | `true` | Status apakah jam server tersinkronisasi via protokol NTP. |

### 2.4 Contoh Lengkap `watch.yml`

```yaml
# Simpan berkas ini di /etc/hostkeeper/watch.yml dengan mode 0600:
#   sudo cp docs/watch.example.yml /etc/hostkeeper/watch.yml
#   sudo chmod 600 /etc/hostkeeper/watch.yml

webhook_url: "https://example.invalid/hook"
webhook_format: "slack"
cooldown_seconds: 3600

thresholds:
  mem_used_percent:
    warn: 80.0
    crit: 90.0
    recover: 75.0

  swap_used_percent:
    warn: 50.0
    crit: 80.0
    recover: 40.0

  disk_used_percent:
    warn: 80.0
    crit: 90.0
    recover: 75.0

  cpu_load_per_core:
    warn: 2.0
    crit: 4.0
    recover: 1.5

  services_failed_count:
    warn: 1
    crit: 1
    recover: 0

  updates_security:
    warn: 1
    crit: 5
    recover: 0

  ssh_failed_logins:
    warn: 10
    crit: 50
    recover: 5
```
