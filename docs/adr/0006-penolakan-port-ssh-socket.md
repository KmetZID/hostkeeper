# ADR 0006: Penolakan Perubahan ssh.port Selain 22 Saat ssh.socket Aktif

## Status
Diterima (*Accepted*)

## Konteks
Pada Ubuntu 22.10, Ubuntu 24.04 LTS, dan rilis Debian terbaru, OpenSSH secara bawaan dikelola melalui socket activation systemd (`ssh.socket`) yang mendengarkan (*listen*) secara statis pada port 22.

Jika administrator mengubah baris `Port <baru>` di `sshd_config` (atau drop-in), daemon OpenSSH yang dipicu oleh systemd socket tidak akan membuka port baru tersebut. Akibatnya, server tetap hanya mendengarkan di port 22, atau daemon gagal terikat (*bind error*), menciptakan kebingungan besar atau pemutusan akses tak terduga (*lockout*).

## Keputusan
`hostkeeper` memeriksa status keaktifan unit `ssh.socket` (`systemctl is-active ssh.socket`). Jika `ssh.socket` aktif dan profil meminta `ssh.port` selain 22, `hostkeeper` menolak operasi penerapan dan melempar error penjelasan yang memandu admin.

## Konsekuensi
- **Positif**:
  - Mencegah administrator terjebak dalam kondisi salah konfigurasi yang membingungkan atau kehilangan koneksi SSH.
  - Memberikan pesan edukatif yang jelas: memberi tahu admin untuk mengubah socket systemd secara manual atau menonaktifkan `ssh.socket` sebelum mengubah port SSH.
- **Negatif / Mitigasi**:
  - Mengharuskan langkah manual tambahan dari administrator jika ingin beralih ke port SSH non-standar pada distro berbasis systemd socket. Langkah remediasi didokumentasikan di `docs/TROUBLESHOOTING.md`.
