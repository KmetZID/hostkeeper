# Changelog

All notable changes to hostkeeper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - Belum dirilis

### Added
- Subcommand `hostkeeper watch run`: Satu siklus pemantauan kesehatan metrik sistem dan deteksi drift profil dengan non-blocking lock.
- Subcommand `hostkeeper watch enable` dan `disable`: Mengaktifkan dan menonaktifkan timer berkala `hostkeeper-watch.timer`.
- Subcommand `hostkeeper watch test-notify`: Menguji konektivitas dan format notifikasi webhook.
- Subcommand `hostkeeper status [--json]`: Menampilkan kartu kesehatan sistem berwarna dan status kepatuhan profil.
- Modul `hostkeeper.monitor.collectors`:
  - `cpu`: Load average 1/5/15 menit dan jumlah core.
  - `memory`: Memori bebas, tersedia, dan penggunaan swap.
  - `psi`: Pressure Stall Information (CPU, memory, IO).
  - `disk`: Penggunaan ruang dan inode via `statvfs`.
  - `time_sync`: Status sinkronisasi NTP via `timedatectl`.
  - `services`: Deteksi unit systemd yang gagal.
  - `updates`: Deteksi pembaruan paket tertunda dan status reboot-required.
  - `ssh_failed`: Deteksi percobaan login gagal dari journalctl.
- Evaluator ambang batas dengan logika hysteresis (ambang pulih terpisah) dan cooldown alert di `watch.yml`.
- Penyimpanan riwayat metrik dan status alert SQLite (`/var/lib/hostkeeper/state.db`) mode WAL dengan retensi otomatis 14 hari dan *recovery* database rusak.
- Webhook Notifier (mendukung format Slack, Discord, dan JSON) dengan *token masking* di semua output dan audit log.
- Unit systemd `hostkeeper-watch.service` dan `hostkeeper-watch.timer`.
- Contoh konfigurasi monitoring di `docs/watch.example.yml`.
- Dokumentasi arsitektur lengkap di `docs/ARCHITECTURE.md` dan model ancaman di `docs/SECURITY.md`.

## [0.2.0] - 2026-10-16

### Added
- Engine rollback dan subperintah `hostkeeper rollback [RUN_ID] [--yes] [--list]`.
- `UserStep`: Pembuatan pengguna administrator dengan sudoers divalidasi via `visudo -cf`.
- `SshKeysStep`: Pengelolaan kunci publik SSH di `authorized_keys` dengan blok bertanda `# BEGIN hostkeeper` / `# END hostkeeper`.
- `SshdStep`: Hardening OpenSSH via drop-in `00-hostkeeper.conf`, verifikasi login kunci sementara, dan konfirmasi manual sebelum menonaktifkan kata sandi.
- `SafetyTimer`: Integrasi rollback otomatis berbasis `systemd-run` timer independen jika koneksi terputus.
- `UpdatesStep`: Otomasi pembaruan keamanan menggunakan `unattended-upgrades`.
- `FirewallStep`: Manajemen aturan firewall `nftables` pada tabel mandiri `inet hostkeeper` dengan service oneshot.
- Wizard setup interaktif `hostkeeper setup` dengan pembuatan profil atomik mode `0600` dan backup otomatis.

## [0.1.0] - 2026-10-15

### Added
- Struktur proyek inti, tooling CI/CD (`ruff`, `mypy --strict`, `pytest`, `shellcheck`, `scripts/check.sh`).
- Abstraksi sistem `Runner` (`SubprocessRunner`, `ReadOnlyRunner`, `FakeRunner`) dan `FileOps` (`RealFileOps`, `ReadOnlyFileOps`, `RecordingFileOps`).
- Skema dan validasi profil deklaratif YAML `version: 1` (`profile.py`).
- Topological sort Planner dengan deteksi siklus dependensi.
- Step dasar: `HostnameStep`, `TimezoneStep`, dan `PackagesStep`.
- Executor dengan pembuatan Journal eksekusi atomik dan Audit logger JSON Lines.
- Lock eksklusif non-blocking `/run/hostkeeper.lock`.
- Antarmuka CLI dasar: `version`, `plan`, `apply`, `verify`.
- Skrip instalasi (`install.sh`) dan pencopotan (`uninstall.sh`).
