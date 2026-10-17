# Panduan Pengujian hostkeeper

Dokumen ini menjelaskan strategi pengujian, struktur direktori tes, integrasi CI/CD, dan prosedur verifikasi pada mesin virtual (*Virtual Machine*).

---

## 1. Piramida Strategi Pengujian

Strategi pengujian `hostkeeper` dirancang berlapis untuk memastikan kestabilan kode sebelum menyentuh sistem operasi riil:

```text
       +---------------------------------------------+
       |   Uji Manual VM (Clean Snapshot Baseline)   |
       +---------------------------------------------+
       |   CI Multi-Distro Container (Debian/Ubuntu) |
       +---------------------------------------------+
       |   Golden Tests (Kesesuaian Format CLI Teks) |
       +---------------------------------------------+
       |   Unit Tests (Pytest + Mocking Runner/File) |
       +---------------------------------------------+
```

---

## 2. Pengujian Unit (*Unit Tests*)

Pengujian unit berada di direktori `tests/unit/`. Pengujian ini menguji setiap komponen secara terisolasi tanpa memerlukan hak akses root dan tanpa memodifikasi sistem operasi mesin lokal.

### 2.1 Menjalankan Tes Unit
Pastikan virtual environment telah aktif:
```bash
source .venv/bin/activate
pytest tests/unit -q
```

### 2.2 Memeriksa Cakupan Kode (*Coverage*)
Ambang batas cakupan kode minimum untuk modul kritis (`engine` dan `steps`) adalah **85%**:
```bash
pytest tests/unit --cov=hostkeeper.engine --cov=hostkeeper.steps --cov-fail-under=85
```

### 2.3 Abstraksi Runner dan FileOps
Pengujian unit memanfaatkan `FakeRunner` dan `RecordingFileOps` dari `hostkeeper.system.fakes` untuk memvalidasi perintah apa yang dieksekusi dan file apa yang ditulis tanpa menyentuh filesystem sistem operasi:
- Memverifikasi perintah subprocess dipanggil dengan argumen biner yang tepat (`argv`).
- Memverifikasi penulisan file menggunakan mode izin yang benar (`0600` / `0700`).
- Mensimulasikan kegagalan perintah untuk menguji penanganan error dan rollback.

---

## 3. Pengujian Golden Output (*Golden Tests*)

Pengujian golden output (`tests/golden/test_golden_output.py`) memastikan bahwa antarmuka baris perintah (CLI) menghasilkan format output teks dan JSON yang konsisten:
- Format judul dan kolom tabel `plan`, `verify`, dan `status`.
- Penanda status perubahan (`[+]` tambah, `[~]` ubah, `[=]` sesuai, `[-]` hapus).
- Kode keluar (*exit codes* 0 sampai 5).
- Teks pesan error Bahasa Indonesia.

Jalankan pengujian golden output:
```bash
pytest tests/golden -q
```

---

## 4. Otomasi Pemeriksaan (*Check Script*)

Sebelum setiap perubahan kode dianggap siap, skrip pemeriksaan lokal tunggal harus dijalankan:
```bash
scripts/check.sh
```

Skrip ini menjalankan seluruh rantai verifikasi:
1. `ruff check`: Memeriksa kepatuhan linter Python.
2. `ruff format --check`: Memeriksa konsistensi pemformatan kode.
3. `mypy --strict src`: Pemeriksaan tipe statis ketat pada seluruh kode sumber.
4. `pytest -q`: Menjalankan seluruh pengujian unit dan golden tests.
5. `python3 scripts/check-deps.py`: Memastikan dependensi runtime hanya stdlib dan PyYAML.
6. `shellcheck`: Memindai seluruh skrip shell (`*.sh`) terhadap potensi kesalahan sintaksis atau kelemahan POSIX.
7. Pemindaian rahasia sederhana: Memastikan tidak ada kunci privat atau token API yang tidak sengaja tertinggal.

---

## 5. Integrasi Berkelanjutan (*Continuous Integration*)

Alur kerja GitHub Actions (`.github/workflows/ci.yml`) dipicu pada setiap *push* ke cabang `main` dan setiap *pull request*.

Pekerjaan yang dijalankan di CI:
1. **Lint Job**: Menjalankan ruff, ruff format, mypy --strict, dan shellcheck.
2. **Unit Job**: Menjalankan pytest dengan coverage pada matriks Python 3.10, 3.11, 3.12, dan 3.13.
3. **No-Extra-Deps Job**: Memverifikasi larangan dependensi runtime tambahan di luar stdlib dan PyYAML.
4. **Install Job**: Menguji skrip instalasi nyata pada container Linux bersih:
   - `debian:12`
   - `debian:13`
   - `ubuntu:22.04`
   - `ubuntu:24.04`
   - Memastikan `install.sh` bersifat idempoten (bisa dijalankan 2 kali berturut-turut tanpa error).
   - Menjalankan smoke test `hostkeeper version` dan `hostkeeper plan`.
   - Menguji pencopotan bersih melalui `uninstall.sh` dan memverifikasi tidak ada file instalasi yang tertinggal.

---

## 6. Prosedur Pengujian Mesin Virtual (*VM Testing*)

Untuk memverifikasi perilaku mutasi nyata pada sistem operasi sesungguhnya (seperti konfigurasi OpenSSH, restart layanan systemd, pembuatan user admin, dan pengaktifan tabel nftables), pengujian dilakukan pada mesin virtual pengujian terisolasi.

### 6.1 Persiapan Mesin Virtual Uji
1. Siapkan VM bersih dengan sistem operasi target (Debian 12/13 atau Ubuntu 22.04/24.04).
2. Buat snapshot awal (*clean-baseline*) sebelum memulai pengujian agar VM dapat dipulihkan dengan cepat ke kondisi bersih.
3. Pastikan Anda memiliki akses konsol darurat (VNC / konsol hypervisor) untuk mengantisipasi kemungkinan salah konfigurasi jaringan saat menguji SSH dan firewall.

### 6.2 Sinkronisasi Kode ke VM Uji
Gunakan skrip pembantu `scripts/vm-sync.sh`:
```bash
TARGET="user@<IP_VM_UJI>:~/hostkeeper" scripts/vm-sync.sh
```

### 6.3 Skenario Verifikasi Komprehensif
Di dalam VM uji, jalankan skenario pengujian berikut secara berurutan:

1. **Uji Instalasi**:
   ```bash
   sudo ./install.sh
   # Jalankan kedua kali untuk membuktikan idempotensi:
   sudo ./install.sh
   ```
2. **Uji Wizard Konfigurasi**:
   ```bash
   sudo hostkeeper setup
   ```
   Pastikan file profil terbentuk di `/etc/hostkeeper/profile.yml` dengan mode `0600`.
3. **Uji Plan**:
   ```bash
   hostkeeper plan
   ```
   Periksa apakah ringkasan perubahan sesuai dengan input wizard.
4. **Uji Penerapan (Apply) & Anti-Lockout**:
   ```bash
   sudo hostkeeper apply
   ```
   Buka terminal SSH kedua untuk menguji koneksi masuk menggunakan kunci SSH yang baru dikonfigurasi sebelum memberikan konfirmasi.
5. **Uji Verifikasi Pasca-Apply**:
   ```bash
   hostkeeper verify
   ```
   Harus menghasilkan keluaran: `Semua Step sesuai profil.` dengan kode keluar 0.
6. **Uji Monitoring & Status**:
   ```bash
   sudo hostkeeper watch enable
   sudo hostkeeper watch run
   hostkeeper status
   ```
   Pastikan tabel status menampilkan metrik sistem dan kesesuaian profil.
7. **Uji Rollback**:
   ```bash
   sudo hostkeeper rollback --list
   sudo hostkeeper rollback <RUN_ID>
   hostkeeper verify
   ```
   Pastikan konfigurasi sistem berhasil dikembalikan ke status sebelum apply.
8. **Uji Pencopotan**:
   ```bash
   sudo ./uninstall.sh --purge
   ```
   Pastikan `/usr/local/bin/hostkeeper` dan direktori `/usr/local/lib/hostkeeper` telah bersih.
9. **Pemulihan Snapshot**:
   Kembalikan (*restore*) snapshot VM ke *clean-baseline* untuk siklus pengujian berikutnya.
