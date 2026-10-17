# hostkeeper

> Alat penyiapan (*setup*) dan pemeliharaan (*watch*) server Debian dan Ubuntu berbasis profil deklaratif YAML.

Satu host, root lokal, deterministik, tanpa daemon berat, tanpa dependensi rumit.

hostkeeper is a lightweight, single-host server setup and maintenance tool for Debian and Ubuntu systems driven by a declarative YAML profile. It automates essential baseline configurations—such as hostnames, timezones, administrator accounts, OpenSSH hardening, and nftables firewalls—with strict safety mechanisms including pre-execution plan diffs, atomic writes, and automated rollback timers. Without requiring heavy daemons or external agents, it continuously monitors server health, detects configuration drift, and sends alerts via webhooks.

[![CI](https://github.com/KmetZID/hostkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/KmetZID/hostkeeper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10-3.13](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](pyproject.toml)

---

## Masalah yang Dipecahkan

Menyiapkan server Linux baru sering kali berulang dan rawan salah:
1. **Risiko Terkunci**: Mengubah konfigurasi SSH atau firewall sering kali memutus sesi admin tanpa jalan kembali.
2. **Kelebihan Kompleksitas**: Menggunakan Ansible, Chef, atau Puppet untuk satu server tunggal membutuhkan instalasi runtime besar, agent, atau setup SSH remote yang berlebihan.
3. **Konfigurasi yang Bergeser (*Drift*)**: Server yang telah disiapkan seiring waktu berubah secara manual dan tidak terpantau.

**hostkeeper** memecahkan masalah ini dengan:
- **Profil Deklaratif Tunggal**: Semua konfigurasi didefinisikan dalam `/etc/hostkeeper/profile.yml`.
- **Siklus Aman**: `plan` menampilkan perubahan sebelum dieksekusi, `apply` menerapkan secara atomik dengan journal, dan `verify` memastikan kepatuhan sistem.
- **Gerbang Anti-Terkunci & Timer Rollback**: Perubahan SSH dan firewall diverifikasi secara otomatis, didukung timer rollback systemd independen jika koneksi terputus.
- **Monitoring Berkala & Deteksi Drift**: Siklus `watch` memantau beban CPU, memori, disk, update keamanan, dan mendeteksi jika konfigurasi server menyimpang dari profil.

---

## Fitur Utama

- **Konfigurasi Deklaratif Sederhana**: Dikelola melalui satu file YAML skema versi 1 (`/etc/hostkeeper/profile.yml`) atau dibuat dengan wizard interaktif `hostkeeper setup`.
- **Alur Kerja Deterministik**: Siklus empat tahap terstruktur (`plan` -> `apply` -> `verify` -> `rollback`).
- **Pemeriksaan Murni Baca-Saja**: Tahap `plan`, `verify`, dan `status` diproteksi secara ketat menggunakan `ReadOnlyRunner` dan `ReadOnlyFileOps` agar tidak menimbulkan efek samping mutasi pada sistem.
- **Perlindungan Anti-Terkunci OpenSSH**: Pembuatan keypair sementara untuk menguji login SSH secara lokal sebelum menerapkan aturan permanen, didukung gerbang konfirmasi manual interaktif.
- **Safety Timer Independen**: Mengaktifkan unit timer transien systemd saat operasi berisiko tinggi; jika koneksi admin terputus dan tidak dibatalkan, timer akan mengeksekusi rollback otomatis secara otonom.
- **Isolasi Firewall Bersih**: Seluruh aturan nftables dikelola dalam tabel mandiri `inet hostkeeper`, tidak menimpa rantai firewall atau tabel milik aplikasi lain seperti Docker.
- **Monitoring Tanpa Daemon**: Pemantauan berkala menggunakan unit timer systemd bawaan (`hostkeeper-watch.timer`), tanpa proses daemon yang terus-menerus memakan RAM.
- **Deteksi Drift & Riwayat Metrik**: Menggunakan SQLite WAL (`/var/lib/hostkeeper/state.db`) dengan retensi otomatis 14 hari dan notifikasi webhook (Slack, Discord, JSON) dengan penyamaran token sensitif.

---

## Demo

### 1. Perencanaan (`hostkeeper plan`)
```text
$ hostkeeper plan
hostkeeper 0.3.0 plan
Profil: /etc/hostkeeper/profile.yml (version 1)
Host  : web-01

 STATUS  STEP       PERUBAHAN                                   RISIKO
 [~]     hostname   web-old -> web-01                           rendah
 [=]     timezone   Asia/Jakarta (sudah sesuai)                 -
 [+]     packages   pasang: htop, vim (curl sudah terpasang)    rendah
 [~]     sshd       Port: 22, PasswordAuth: no                  tinggi
 [~]     firewall   izinkan: 22/tcp, 80/tcp, 443/tcp            tinggi

Ringkasan: 4 perubahan, 1 sudah sesuai, 2 berisiko tinggi.
Mode plan: tidak ada yang diubah. Jalankan `sudo hostkeeper apply` untuk menerapkan.
```

### 2. Penerapan (`sudo hostkeeper apply`)
```text
$ sudo hostkeeper apply
hostkeeper 0.3.0 apply (run 20261016T070000Z-a1b2)
 [!] Safety timer aktif (90s). Jangan tutup sesi ini, uji dari terminal kedua.
 [~] hostname   web-old -> web-01 ................. OK (verify lolos)
 [+] packages   htop, vim ......................... OK (verify lolos)
 [~] sshd       drop-in 00-hostkeeper.conf ........ OK (verify lolos)
 [~] firewall   inet hostkeeper ................... OK (verify lolos)
 [~] Safety timer dibatalkan.
Selesai: 4 diterapkan, 0 gagal. Jalankan `hostkeeper verify` untuk memastikan.
```

### 3. Verifikasi Kepatuhan (`hostkeeper verify`)
```text
$ hostkeeper verify
hostkeeper 0.3.0 verify
Profil: /etc/hostkeeper/profile.yml (version 1)
Host  : web-01

 [=] hostname   web-01
 [=] timezone   Asia/Jakarta
 [=] packages   curl, htop, vim terpasang
 [=] sshd       drop-in 00-hostkeeper.conf aktif
 [=] firewall   tabel inet hostkeeper aktif

Semua Step sesuai profil.
```

### 4. Kartu Kesehatan Sistem (`hostkeeper status`)
```text
$ hostkeeper status
hostkeeper 0.3.0 status
Host    : web-01

METRIK SISTEM:
 STATUS  METRIK                           NILAI                    
 [OK]    cpu.load1                        0.15                     
 [OK]    mem.used_percent                 42.5 %                   
 [OK]    disk./.used_percent              38.1 %                   
 [OK]    services.failed_count            0                        
 [OK]    updates.security                 0 packages               
 [OK]    time.ntp_synchronized            True                     

KESESUAIAN PROFIL:
 STATUS  STEP            KONDISI                                 
 [OK]    hostname        web-01 (sesuai)                         
 [OK]    timezone        Asia/Jakarta (sesuai)                   
 [OK]    packages        sudah terpasang (sesuai)                
 [OK]    sshd            konfigurasi efektif (sesuai)            
 [OK]    firewall        aturan aktif (sesuai)                   

Ringkasan: Semua metrik dan profil dalam kondisi OK.
```

---

## Persyaratan Sistem

- **Sistem Operasi**:
  - Debian 12 (Bookworm)
  - Debian 13 (Trixie)
  - Ubuntu 22.04 LTS (Jammy Jellyfish)
  - Ubuntu 24.04 LTS (Noble Numbat)
- **Init System**: systemd aktif (`/run/systemd/system`).
- **Hak Akses**:
  - Perintah pembacaan (`plan`, `verify`, `status`) dapat dijalankan oleh user biasa.
  - Perintah mutasi (`apply`, `rollback`, `watch enable`, `watch disable`) mewajibkan hak akses root (`sudo`).
- **Runtime**: Python 3.10 atau lebih baru dengan pustaka `python3-yaml` (dipasang otomatis oleh skrip instalasi).

---

## Instalasi

1. Klon repositori hostkeeper:
   ```bash
   git clone https://github.com/KmetZID/hostkeeper.git
   cd hostkeeper
   ```
2. Periksa skrip instalasi terlebih dahulu untuk memastikan keamanan perintah:
   ```bash
   less install.sh
   ```
3. Pasang ke sistem:
   ```bash
   sudo ./install.sh
   ```

Skrip instalasi akan memvalidasi lingkungan, memasang dependensi dasar (`python3`, `python3-yaml`), menyalin pustaka ke `/usr/local/lib/hostkeeper`, dan memasang launcher biner di `/usr/local/bin/hostkeeper`.

---

## Mulai Cepat

1. **Buat profil konfigurasi baru**:
   ```bash
   sudo hostkeeper setup
   ```
   Wizard interaktif akan memandu pembuatan `/etc/hostkeeper/profile.yml`.

2. **Periksa rencana perubahan**:
   ```bash
   hostkeeper plan
   ```

3. **Terapkan konfigurasi ke server**:
   ```bash
   sudo hostkeeper apply
   ```

4. **Verifikasi kepatuhan sistem**:
   ```bash
   hostkeeper verify
   ```

5. **Aktifkan pemantauan berkala**:
   ```bash
   sudo hostkeeper watch enable
   ```

6. **Pantau status server kapan saja**:
   ```bash
   hostkeeper status
   ```

7. **Kembalikan perubahan jika diperlukan (Rollback)**:
   ```bash
   # Melihat riwayat run yang tersimpan di journal
   sudo hostkeeper rollback --list

   # Membalikkan perubahan run tertentu
   sudo hostkeeper rollback <RUN_ID>
   ```

---

## Contoh Profil (`profile.yml`)

File profil utama disimpan di `/etc/hostkeeper/profile.yml`:

```yaml
version: 1
hostname: web-01
timezone: Asia/Jakarta

packages:
  - curl
  - htop
  - vim

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

Untuk dokumentasi seluruh kolom dan aturan validasi, lihat [docs/CONFIGURATION.md](docs/CONFIGURATION.md) dan contoh lengkap di [docs/example-profile.yml](docs/example-profile.yml).

---

## Konfigurasi Monitoring (`watch.yml`)

Konfigurasi pemantauan disimpan terpisah di `/etc/hostkeeper/watch.yml` dengan izin ketat mode `0600`:

```yaml
webhook_url: "https://example.invalid/hook"
webhook_format: "slack"  # slack, discord, atau json
cooldown_seconds: 3600

thresholds:
  mem_used_percent:
    warn: 80.0
    crit: 90.0
    recover: 75.0
  disk_used_percent:
    warn: 80.0
    crit: 90.0
    recover: 75.0
  cpu_load_per_core:
    warn: 2.0
    crit: 4.0
    recover: 1.5
```

Lihat referensi lengkap konfigurasi di [docs/CONFIGURATION.md](docs/CONFIGURATION.md) dan [docs/watch.example.yml](docs/watch.example.yml).

---

## Bagaimana Keselamatannya Dijaga

`hostkeeper` dirancang dengan prinsip kehati-hatian tinggi terhadap risiko kerusakan sistem:

1. **Plan Terlebih Dahulu**: Setiap tindakan diverifikasi terlebih dahulu sebelum diterapkan. Output `plan` menunjukkan dengan jelas parameter apa yang berubah dan tingkat risikonya.
2. **Pencadangan File Otomatis**: Sebelum file apa pun dimodifikasi, salinan cadangan dibuat di direktori `/var/lib/hostkeeper/backups/<run_id>/`.
3. **Rollback Terstruktur & Atomik**: Setiap eksekusi mencatat Journal terperinci. Jika eksekusi gagal di tengah jalan, sistem dapat dikembalikan menggunakan `sudo hostkeeper rollback <RUN_ID>`.
4. **Safety Timer Pemulih Otonom**: Perubahan pada layanan kritis (seperti OpenSSH) mengaktifkan timer systemd transien independen (`hostkeeper-rollback-<run_id>`). Jika koneksi admin terputus dan sesi mati sebelum konfirmasi diberikan, timer ini akan mengeksekusi rollback otomatis.
5. **Tidak Mengubah File Milik Pengguna**: `hostkeeper` tidak pernah mengedit file konfigurasi utama milik pengguna secara langsung. Semua setelan diterapkan melalui direktori drop-in (`/etc/ssh/sshd_config.d/00-hostkeeper.conf`, `/etc/sudoers.d/`, dan tabel mandiri nftables `inet hostkeeper`).

---

## Batasan dan "Kapan Jangan Pakai hostkeeper"

`hostkeeper` dirancang spesifik untuk satu server tunggal (*single host*). **Jangan gunakan hostkeeper bila:**

- **Memerlukan orkestrasi multi-node**: Mengelola armada puluhan atau ratusan server sekaligus dengan koordinasi terpusat (gunakan Ansible, Puppet, SaltStack, atau Terraform).
- **Sistem Operasi Non-Debian/Ubuntu**: Menggunakan distribusi Linux lain seperti RHEL/CentOS, Fedora, Alpine, Arch, atau keluarga BSD/Windows.
- **Arsitektur Kontainer Penuh / Serverless**: Sistem yang seluruhnya berjalan di atas Kubernetes, Nomad, atau container ephemeral tanpa server VM persisten.
- **Manajemen Kluster Terdistribusi**: Mengonfigurasi replikasi kluster basis data multi-master atau penyimpanan terdistribusi yang memerlukan konsensus jaringan antar-host.

---

## Pencopotan (*Uninstall*)

Untuk mencopot `hostkeeper` dari sistem:
```bash
sudo ./uninstall.sh
```

Jika Anda ingin sekaligus menghapus konfigurasi dan riwayat data di `/etc/hostkeeper` dan `/var/lib/hostkeeper`:
```bash
sudo ./uninstall.sh --purge
```

> [!WARNING]
> Perintah pencopotan (`uninstall.sh`) menghapus biner launcher dan file pustaka hostkeeper, **tetapi tidak membalikkan perubahan konfigurasi sistem** (seperti hostname, paket yang telah terpasang, aturan firewall, atau konfigurasi SSH) yang pernah diterapkan. Jika Anda ingin mengembalikan kondisi server, jalankan `sudo hostkeeper rollback` sebelum mencopot pemasangan.

---

## Status Proyek

- **Versi Saat Ini**: `0.3.0`
- **Kondisi Pengujian**: Diuji secara unit, golden output, dan pengujian manual pada mesin virtual bersih Debian 12, Debian 13, Ubuntu 22.04 LTS, dan Ubuntu 24.04 LTS.
- **Distribusi**: Belum tersedia dalam bentuk paket `.deb` resmi di repositori APT. Instalasi dilakukan melalui skrip instalasi `install.sh`.

---

## Tautan Dokumentasi

Pelajari lebih lanjut mengenai arsitektur internal dan panduan operasional di direktori [docs/](docs/):
- [docs/README.md](docs/README.md): Indeks dokumentasi lengkap.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Lapisan arsitektur, komponen internal, dan aliran data.
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md): Penjelasan konsep keselamatan, anti-lockout, drop-in, dan monitoring.
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md): Panduan lengkap seluruh kolom `profile.yml` dan `watch.yml`.
- [docs/SECURITY.md](docs/SECURITY.md): Model ancaman (*threat model*) dan pelaporan kerentanan keamanan.
- [docs/TESTING.md](docs/TESTING.md): Panduan pengujian unit, golden test, CI, dan verifikasi VM.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): Kode keluar CLI (*exit codes 0-5*) dan penanganan error umum.
- [docs/adr/](docs/adr/): Catatan Keputusan Arsitektur (*Architecture Decision Records*).

---

## Pengembangan

Jika Anda ingin berkontribusi atau mengembangkan hostkeeper:

1. Buat dan aktifkan lingkungan virtual Python 3.10+:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Pasang dependensi pengujian dan pengembangan:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```
3. Jalankan suite pemeriksaan lengkap:
   ```bash
   scripts/check.sh
   ```
4. Jalankan pengujian unit mandiri:
   ```bash
   pytest tests/unit tests/golden -q
   ```

---

## Kontribusi

Kontribusi dipersilakan! Sebelum mengirimkan Pull Request, pastikan untuk membaca [CONTRIBUTING.md](CONTRIBUTING.md) dan pastikan `scripts/check.sh` berhasil 100% tanpa kesalahan linting atau kegagalan tes.

---

## Lisensi

Didistribusikan di bawah lisensi MIT. Lihat file [LICENSE](LICENSE) untuk informasi hak cipta dan ketentuan penggunaan.
