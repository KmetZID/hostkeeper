# Panduan Rilis Manual (hostkeeper)

Proses rilis hostkeeper dilakukan secara manual oleh pemilik repositori untuk memastikan verifikasi keamanan dan integritas sebelum rilis publik.

## Daftar Periksa Pra-Rilis

1. [ ] **Verifikasi Lokal dan Linting**
   - Jalankan pemeriksaan integritas penuh di lingkungan pengembangan:
     ```bash
     scripts/check.sh
     ```
   - Pastikan ruff, mypy, pytest, dan shellcheck 100% hijau.
   - Periksa cakupan pengujian (minimal 85% di `engine/` dan `steps/`):
     ```bash
     pytest --cov=hostkeeper.engine --cov=hostkeeper.steps --cov-fail-under=85
     ```

2. [ ] **Verifikasi Gerbang Mesin Virtual (VM Uji)**
   - Jalankan skenario pengujian VM di target Debian/Ubuntu bersih (lihat `docs/TESTING.md`):
     - Jalankan `install.sh` dua kali (menguji idempoten).
     - Jalankan `hostkeeper plan`.
     - Jalankan `sudo hostkeeper apply`.
     - Jalankan `hostkeeper verify`.
     - Jalankan `uninstall.sh`.
   - Kembalikan (*restore*) snapshot VM uji setelah selesai.

3. [ ] **Perbarui Catatan Perubahan (CHANGELOG.md)**
   - Perbarui versi pada `CHANGELOG.md` dan `src/hostkeeper/__init__.py`.
   - Dokumentasikan fitur baru, perbaikan bug, dan perubahan penting.

4. [ ] **Buat dan Tandatangani Tag Git**
   - Buat git annotated tag:
     ```bash
     git tag -a v0.1.0 -m "hostkeeper v0.1.0: fondasi awal"
     git push origin v0.1.0
     ```

5. [ ] **Buat GitHub Release**
   - Buka halaman GitHub Releases pada repositori.
   - Buat Release baru dari tag `v0.1.0`.
   - Lampirkan catatan rilis dari CHANGELOG.md.
