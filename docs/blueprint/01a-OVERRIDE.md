# Override (menimpa 01-SPEC.md)

## Roadmap
SPEC bagian 11 dan 13 diganti: hanya 3 versi.
- v0.1 = tahap 1.1-1.5 (lingkup SPEC bagian 12, tanpa unit systemd)
- v0.2 = tahap 2.1-2.6 (rollback, user, sshkeys, sshd, updates, firewall, wizard)
- v0.3 = tahap 3.1-3.5 (monitoring, status, dokumentasi, siap rilis)

## Koreksi teknis
1. Drop-in sshd bernama /etc/ssh/sshd_config.d/00-hostkeeper.conf (BUKAN 99-). OpenSSH memakai
   nilai pertama yang ditemukan, dan file diproses berurutan nama. 99- kalah dari 50-cloud-init.conf.
   `check()` sshd wajib memakai `sshd -T` (nilai efektif), bukan membaca file.
2. Layanan SSH bernama `ssh` di Debian/Ubuntu. Jika `ssh.socket` aktif (Ubuntu 24.04),
   direktif Port di sshd_config diabaikan. Di v0.2, ssh.port selain 22 DITOLAK dengan penjelasan
   jika ssh.socket aktif. Port 22 tetap didukung.
3. Unit systemd tidak dipasang di v0.1. install.sh memasang packaging/systemd/* hanya bila ada
   (mulai tahap 3.3). Unit tidak di-enable oleh install.sh.
4. Paket ufw tidak boleh ada di contoh paket dasar. Firewall memakai nftables milik sendiri.
5. Kode wajib jalan di Python 3.10 sampai 3.13. Jangan memakai tomllib atau fitur 3.11+.
6. journal dan backup ditulis sejak v0.1. Perintah rollback baru di tahap 2.1.
7. hostname dan timezone adalah dua Step terpisah (tiga Step di v0.1).
8. Tabel nft memakai nama `inet hostkeeper`. Unit persistensi: hostkeeper-firewall.service.

## Penambahan profil (hanya field opsional baru; version tetap 1)
admin_user, admin_sudo_nopasswd, ssh_authorized_keys, ssh.{port,permit_root_login,password_auth},
firewall.allow, unattended_upgrades. Kunci tak dikenal tetap error.
