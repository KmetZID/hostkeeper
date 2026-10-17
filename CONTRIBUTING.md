# Panduan Kontribusi hostkeeper

Terima kasih atas minat Anda untuk berkontribusi pada pengembangan `hostkeeper`! Kami menyambut kontribusi perbaikan bug, penyempurnaan dokumentasi, dan penambahan fitur yang sejalan dengan filosofi proyek.

---

## 1. Menyiapkan Lingkungan Pengembangan

1. **Prasyarat**:
   - Python 3.10, 3.11, 3.12, atau 3.13.
   - Git.
   - Sistem Linux berbasis Debian atau Ubuntu direkomendasikan untuk pengujian penuh.

2. **Klon dan Buat Virtual Environment**:
   ```bash
   git clone https://github.com/KmetZID/hostkeeper.git
   cd hostkeeper
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Pasang Dependensi Pengembangan**:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

---

## 2. Aturan Pengujian dan Kualitas Kode

Sebelum mengajukan perubahan, pastikan kode memenuhi standar berikut:

1. **Uji Perubahan dengan Skrip Tunggal**:
   Seluruh verifikasi wajib lolos melalui satu perintah:
   ```bash
   scripts/check.sh
   ```
   Skrip ini memverifikasi format kode (`ruff format`), linting (`ruff check`), pengetikan statis ketat (`mypy --strict src`), seluruh pengujian unit/golden (`pytest`), larangan dependensi runtime tambahan (`scripts/check-deps.py`), sintaks shell (`shellcheck`), dan pemindaian rahasia.

2. **Aturan Penulisan Tes**:
   - Setiap fitur baru atau perbaikan bug **wajib disertai tes unit** di `tests/unit/` atau golden tests di `tests/golden/`.
   - Modul `engine/` dan `steps/` wajib mempertahankan cakupan pengujian (*coverage*) minimal **85%**.
   - Pengujian unit tidak boleh mengeksekusi subprocess nyata atau memodifikasi file sistem nyata. Gunakan abstraksi `FakeRunner` dan `RecordingFileOps`.

3. **Standar Kode & Dependensi**:
   - **Type Hint Lengkap**: Semua fungsi dan metode wajib memiliki type annotations lengkap yang lulus pemeriksaan `mypy --strict`.
   - **Dependensi Runtime Sangat Terbatas**: Runtime `hostkeeper` hanya mengizinkan Python Standard Library dan `PyYAML`. Dilarang menambahkan dependensi runtime pihak ketiga baru.
   - **Keamanan Subprocess**: Dilarang menggunakan `shell=True`, `os.system`, `eval`, atau `exec`. Semua eksekusi wajib menggunakan list argumen biner via `system.Runner`.
   - **Bahasa**: Pesan keluaran CLI untuk pengguna wajib dalam Bahasa Indonesia (didefinisikan di `messages.py`). Identifier kode, nama fungsi, variabel, dan kelas menggunakan Bahasa Inggris.

---

## 3. Alur Kerja Kontribusi (Pull Request)

1. **Satu Perubahan per PR**:
   Fokuskan setiap Pull Request pada satu tujuan spesifik (satu bug fix atau satu penambahan fitur). Hindari menggabungkan refactoring besar dengan perubahan fungsional dalam PR yang sama.

2. **Buat Cabang Fitur**:
   ```bash
   git checkout -b feat/nama-fitur
   # atau
   git checkout -b fix/deskripsi-bug
   ```

3. **Verifikasi dan Buat Commit**:
   - Pastikan `scripts/check.sh` hijau 100%.
   - Tulis pesan commit yang jelas dan deskriptif.

4. **Ajukan Pull Request**:
   - Buka Pull Request ke cabang `main` di repositori GitHub `KmetZID/hostkeeper`.
   - Isi formulir deskripsi PR sesuai templat yang disediakan.
