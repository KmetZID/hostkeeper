# Blueprint hostkeeper: peta

hostkeeper menyiapkan server Debian/Ubuntu sesuai profil YAML (setup + wizard) lalu menjaganya
sehat dan sesuai profil (watch). Satu host, root lokal, tanpa daemon, tanpa database server.
Dibuat dalam 3 versi: 0.1 Fondasi, 0.2 Setup lengkap, 0.3 Watch dan rilis.

| File | Isi | Dibaca |
|---|---|---|
| 01-SPEC.md | Spesifikasi lengkap v0.1 (kontrak kode, format data, output CLI) | Semua tahap |
| 01a-OVERRIDE.md | Koreksi dan penyesuaian yang MENIMPA SPEC | Semua tahap |
| 02-SECURITY.md | Batas keamanan untuk agen dan untuk kode hostkeeper | Semua tahap |
| 03-WORKFLOW.md | Siklus kerja, definisi selesai, format laporan | Semua tahap |
| 04-STAGES.md | 16 tahap (1.1 sampai 3.5) beserta tugas dan gerbang | Tahap yang diminta |
| 05-TESTPLAN.md | Tes unit, CI, dan tes VM mentah (milik pemilik repo) | Hanya referensi |
| PROGRESS.md | Status, keputusan, catatan antar sesi | Awal dan akhir tiap task |

Konteks tidak terbawa antar task. PROGRESS.md adalah memorinya: baca di awal, perbarui di akhir.
