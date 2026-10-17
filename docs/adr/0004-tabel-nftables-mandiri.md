# ADR 0004: Manajemen Aturan Firewall dalam Tabel nftables Mandiri (inet hostkeeper)

## Status
Diterima (*Accepted*)

## Konteks
Konfigurasi firewall pada Linux sering kali bertabrakan jika berbagai perangkat lunak (seperti UFW, Docker, Fail2ban, atau skrip iptables lama) memanipulasi rantai (*chains*) yang sama pada tabel filter global. Hal ini sering memicu terputusnya koneksi atau rusaknya aturan perutean kontainer.

## Keputusan
`hostkeeper` menggunakan `nftables` modern dan mengisolasi seluruh rantai input serta aturannya dalam tabel mandiri `table inet hostkeeper`.

## Konsekuensi
- **Positif**:
  - Isolasi total: operasi flush atau modifikasi pada tabel `inet hostkeeper` tidak akan menyentuh tabel `filter`, tabel `nat` milik Docker, atau set dinamis milik fail2ban.
  - Sesuai dengan arsitektur modern Linux kernel di mana `nftables` merupakan subsistem penyaring paket standar pengganti iptables.
  - Persistensi dikelola rapi melalui file aturan `/etc/hostkeeper/nftables.rules` dan dimuat saat boot oleh unit oneshot `hostkeeper-firewall.service`.
- **Negatif / Mitigasi**:
  - Paket `nftables` harus terpasang pada sistem. `hostkeeper` secara otomatis memastikan paket `nftables` terpasang sebelum menerapkan konfigurasi firewall.
