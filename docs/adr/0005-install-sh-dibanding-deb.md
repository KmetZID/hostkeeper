# ADR 0005: Distribusi Menggunakan install.sh Dibanding Paket .deb

## Status
Diterima (*Accepted*)

## Konteks
Pada fase awal pengembangan (v0.1 sampai v0.3), mendistribusikan perangkat lunak sebagai paket `.deb` membutuhkan infrastruktur repositori APT (PPA atau repositori Debian privat), penandatanganan GPG, dan pemeliharaan metadata debian/control yang rumit untuk beberapa versi rilis distro berbeda.

## Keputusan
Menyediakan skrip instalasi shell POSIX mandiri (`install.sh`) yang dapat dijalankan langsung setelah melakukan `git clone` repositori.

## Konsekuensi
- **Positif**:
  - Instalasi langsung dari sumber kode tanpa perantara repositori APT pihak ketiga.
  - Skrip instalasi transparan: administrator dapat memeriksa isi `install.sh` sebelum menjalankannya dengan sudo.
  - Menyalin kode ke `/usr/local/lib/hostkeeper`, membuat launcher di `/usr/local/bin/hostkeeper`, dan mencatat manifest file terpasang untuk pencopotan bersih via `uninstall.sh`.
  - Berfungsi identik di Debian 12, Debian 13, Ubuntu 22.04, dan Ubuntu 24.04.
- **Negatif / Mitigasi**:
  - Belum terintegrasi dengan siklus otomatisasi pembaruan paket `apt update && apt upgrade`.
  - Paket biner resmi `.deb` tetap direncanakan sebagai roadmap untuk rilis masa depan setelah spesifikasi stabil.
