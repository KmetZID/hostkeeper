## Ringkasan Perubahan
Jelaskan secara ringkas perubahan apa yang dilakukan dan masalah apa yang diselesaikan.

## Jenis Perubahan
- [ ] Perbaikan bug (*bugfix*)
- [ ] Fitur baru (*feature*)
- [ ] Dokumentasi (*docs*)
- [ ] Peningkatan pengujian (*tests*)
- [ ] Pemeliharaan / refaktorisasi internal (*chore*)

## Daftar Periksa (Checklist)
- [ ] Perubahan berfokus pada satu hal (satu PR satu topik perubahan).
- [ ] Menambahkan atau memperbarui pengujian unit/golden terkait.
- [ ] Pesan untuk pengguna menggunakan Bahasa Indonesia di `messages.py`.
- [ ] Identifier kode menggunakan Bahasa Inggris dan memiliki type hint lengkap (`mypy --strict`).
- [ ] Tidak menambah dependensi runtime baru di luar stdlib dan PyYAML.
- [ ] Telah menjalankan `scripts/check.sh` secara lokal dan seluruh pemeriksaan hijau (ruff, mypy, pytest, shellcheck).
