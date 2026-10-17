# ADR 0003: Konfigurasi OpenSSH Menggunakan Drop-in 00-hostkeeper.conf

## Status
Diterima (*Accepted*)

## Konteks
Mengedit file `/etc/ssh/sshd_config` utama secara langsung menimbulkan risiko tinggi merusak konfigurasi lama pengguna, kehilangan komentar, dan memicu konflik interaktif (*dpkg conffile prompt*) saat pembaruan paket sistem operasi `apt upgrade`.

## Keputusan
Menempatkan seluruh konfigurasi hardening OpenSSH pada file drop-in khusus `/etc/ssh/sshd_config.d/00-hostkeeper.conf`.

## Konsekuensi
- **Positif**:
  - File utama `/etc/ssh/sshd_config` milik distro dan konfigurasi manual pengguna tetap utuh tanpa modifikasi langsung.
  - Awalan `00-` memastikan file dibaca paling awal oleh OpenSSH, sehingga aturan pengamanan (seperti `PasswordAuthentication no`) memiliki prioritas evaluasi yang jelas (*first-value-wins* pada parser OpenSSH).
  - Proses rollback dan pencopotan instalasi (*uninstall*) menjadi sangat bersih: cukup menghapus satu file `00-hostkeeper.conf` dan memuat ulang layanan SSH.
- **Negatif / Mitigasi**:
  - Membutuhkan versi OpenSSH 8.2 atau lebih baru yang secara bawaan menyertakan direktif `Include /etc/ssh/sshd_config.d/*.conf`. Seluruh distro target hostkeeper (Debian 12/13, Ubuntu 22.04/24.04) menggunakan OpenSSH >= 8.9 sehingga kompatibilitas terjamin 100%.
