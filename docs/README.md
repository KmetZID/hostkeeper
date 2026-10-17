# Dokumentasi hostkeeper

Selamat datang di repositori dokumentasi resmi `hostkeeper`. Direktori ini memuat spesifikasi arsitektur, panduan teknis operasional, referensi konfigurasi, panduan pengujian, dan catatan keputusan desain.

---

## Daftar Isi Dokumentasi

| Dokumen | Deskripsi |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Penjelasan mendalam tentang lapisan sistem, komponen internal, antarmuka `Step`, abstraksi `Runner`/`FileOps`, dan aliran siklus eksekusi. |
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Penjelasan konsep dalam bahasa sederhana: idempotensi, alasan pemeriksaan murni baca-saja, mekanisme anti-terkunci SSH, timer rollback otomatis, konfigurasi drop-in OpenSSH, firewall mandiri nftables, dan cara subsistem monitoring bekerja. |
| [CONFIGURATION.md](CONFIGURATION.md) | Referensi lengkap setiap kolom konfigurasi untuk profil utama (`profile.yml`) dan pemantauan sistem (`watch.yml`), mencakup tipe data, nilai bawaan, batasan validasi, dan contoh praktis. |
| [SECURITY.md](SECURITY.md) | Model ancaman (*threat model*), pemetaan aset, mitigasi risiko keamanan teknis, batasan cakupan, dan prosedur pelaporan celah keamanan melalui GitHub Private Vulnerability Reporting. |
| [TESTING.md](TESTING.md) | Panduan pengujian perangkat lunak: tes unit dengan pytest, golden test output CLI, matriks CI GitHub Actions, dan prosedur pengujian manual pada mesin virtual (VM). |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Panduan pemecahan masalah operasional, daftar lengkap kode keluar (*exit codes* 0 sampai 5), penyebab umum kegagalan, dan langkah remediasinya. |
| [RELEASING.md](RELEASING.md) | Daftar periksa langkah-langkah rilis versi baru untuk pemelihara repositori. |
| [adr/](adr/) | Catatan Keputusan Arsitektur (*Architecture Decision Records* / ADR) yang merangkum alasan teknis di balik pilihan desain utama. |

---

## File Contoh Konfigurasi

- [example-profile.yml](example-profile.yml): Contoh konfigurasi profil server lengkap siap pakai (`version: 1`).
- [watch.example.yml](watch.example.yml): Contoh konfigurasi ambang batas monitoring berkala dan webhook.
