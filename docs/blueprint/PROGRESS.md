# PROGRESS (satu-satunya blueprint yang boleh diubah agen)

## Status tahap
| Tahap | Status | Cabang | CI | Gerbang VM | Catatan |
|---|---|---|---|---|---|
| 1.1 | selesai | tahap-1-1 | hijau | n/a | Persiapan repo, tooling, check.sh, ci.yml selesai |
| 1.2 | selesai | tahap-1-2 | hijau | n/a | Runner, FileOps, Fakes, dan unit test selesai |
| 1.3 | selesai | tahap-1-3 | hijau | n/a | Step, Profile, Planner, hostname, timezone, messages, output selesai |
| 1.4 | selesai | tahap-1-4-1-5 | hijau | n/a | Step paket, Executor, Audit, Journal, Lock, CLI selesai |
| 1.5 | selesai | tahap-1-4-1-5 | hijau | V1 | install.sh, uninstall.sh, launcher, CI penuh, docs releasing selesai |
| 2.1 | belum | | | | |
| 2.2 | belum | | | | |
| 2.3 | belum | | | | |
| 2.4 | belum | | | | |
| 2.5 | belum | | | | |
| 2.6 | belum | | | V2 | |
| 3.1 | belum | | | | |
| 3.2 | belum | | | | |
| 3.3 | belum | | | | |
| 3.4 | belum | | | | |
| 3.5 | belum | | | V3, V-FINAL | |

## Keputusan di luar spesifikasi (tanggal, tahap, keputusan, alasan)
- 2026-10-15, tahap 1.2: RealFileOps.write_atomic hanya memanggil os.chown jika dijalankan sebagai root (os.geteuid() == 0) dan menangani PermissionError jika non-root, agar unit test dapat berjalan pada lingkungan non-root tanpa sudo.
- 2026-10-15, tahap 1.2: RecordingFileOps mencatat perubahan file ke dalam list[FileChangeRecord] (action, path, content, mode, owner, group) sebelum objek Change dari engine/step.py dibuat di tahap 1.3.
- 2026-10-15, tahap 1.3: validate_timezone menggunakan Path.resolve().relative_to() untuk mencegah path traversal symlink, bukan hanya pengecekan string ".." (lebih aman).
- 2026-10-15, tahap 1.3: HostnameStep.verify() menambahkan peringatan informatif untuk kondisi getent dan cloud-init, namun tidak mengubah nilai compliant (peringatan bukan kegagalan).
- 2026-10-15, tahap 1.3: REGISTRY di steps/__init__.py adalah tuple[type[Step], ...] sehingga mudah diperluas di tahap berikutnya tanpa modifikasi Planner.
- 2026-10-15, tahap 1.4: PlanReport.total_changes menghitung jumlah Step yang memerlukan perubahan (bukan jumlah atomic Change), agar sesuai dengan format ringkasan teks dan JSON SPEC bagian 8.2.
- 2026-10-15, tahap 1.4: Argparse subparsers mewarisi opsi global (-c, --json, --no-color, -v) melalui parser parent agar fleksibel digunakan sebelum maupun sesudah nama subperintah.
- 2026-10-15, tahap 1.5: Pemeriksaan dependensi runtime terlarang diuji menggunakan AST scanner scripts/check-deps.py berbasis sys.stdlib_module_names dan PyYAML.

## Temuan dan pertanyaan terbuka


## Insiden
