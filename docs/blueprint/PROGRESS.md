# PROGRESS (satu-satunya blueprint yang boleh diubah agen)

## Status tahap
| Tahap | Status | Cabang | CI | Gerbang VM | Catatan |
|---|---|---|---|---|---|
| 1.1 | selesai | tahap-1-1 | hijau | n/a | Persiapan repo, tooling, check.sh, ci.yml selesai |
| 1.2 | selesai | tahap-1-2 | hijau | n/a | Runner, FileOps, Fakes, dan unit test selesai |
| 1.3 | selesai | tahap-1-3 | hijau | n/a | Step, Profile, Planner, hostname, timezone, messages, output selesai |
| 1.4 | selesai | tahap-1-4-1-5 | hijau | n/a | Step paket, Executor, Audit, Journal, Lock, CLI selesai |
| 1.5 | selesai | tahap-1-4-1-5 | hijau | V1 | install.sh, uninstall.sh, launcher, CI penuh, docs releasing selesai |
| 2.1 | selesai | tahap-2-1-to-2-6 | hijau | n/a | Engine rollback, CLI hostkeeper rollback, audit undo |
| 2.2 | selesai | tahap-2-1-to-2-6 | hijau | n/a | UserStep, SshKeysStep, visudo validation, hostkeeper markers |
| 2.3 | selesai | tahap-2-1-to-2-6 | hijau | n/a | SshdStep, temporary keypair auth verification, human gate |
| 2.4 | selesai | tahap-2-1-to-2-6 | hijau | n/a | SafetyTimer via systemd-run timer, auto rollback, timeout |
| 2.5 | selesai | tahap-2-1-to-2-6 | hijau | n/a | UpdatesStep, FirewallStep (nftables drop-in, systemd oneshot) |
| 2.6 | selesai | tahap-2-1-to-2-6 | hijau | V2 | Wizard setup interaktif, atomic profile writing, mode 0600 |
| 3.1 | selesai | tahap-3-1-3-5 | hijau | n/a | Collector CPU/load, memory/swap, PSI, disk/inode, time sync, services, updates, SSH failed |
| 3.2 | selesai | tahap-3-1-3-5 | hijau | n/a | Evaluator threshold/hysteresis, StateDB SQLite WAL, Notifier webhook masked |
| 3.3 | selesai | tahap-3-1-3-5 | hijau | n/a | CLI watch run/enable/disable/test-notify, systemd unit timer |
| 3.4 | selesai | tahap-3-1-3-5 | hijau | n/a | CLI status --json, profile compliance check, ReadOnlyRunner/FileOps, exit code 0/3 |
| 3.5 | selesai | tahap-3-1-3-5 | hijau | V3, V-FINAL | Versi 0.3.0, README, ARCHITECTURE, SECURITY, CHANGELOG, watch.example.yml, dependabot, issue template |

## Keputusan di luar spesifikasi (tanggal, tahap, keputusan, alasan)
- 2026-10-15, tahap 1.2: RealFileOps.write_atomic hanya memanggil os.chown jika dijalankan sebagai root (os.geteuid() == 0) dan menangani PermissionError jika non-root, agar unit test dapat berjalan pada lingkungan non-root tanpa sudo.
- 2026-10-15, tahap 1.2: RecordingFileOps mencatat perubahan file ke dalam list[FileChangeRecord] (action, path, content, mode, owner, group) sebelum objek Change dari engine/step.py dibuat di tahap 1.3.
- 2026-10-15, tahap 1.3: validate_timezone menggunakan Path.resolve().relative_to() untuk mencegah path traversal symlink, bukan hanya pengecekan string ".." (lebih aman).
- 2026-10-15, tahap 1.3: HostnameStep.verify() menambahkan peringatan informatif untuk kondisi getent dan cloud-init, namun tidak mengubah nilai compliant (peringatan bukan kegagalan).
- 2026-10-15, tahap 1.3: REGISTRY di steps/__init__.py adalah tuple[type[Step], ...] sehingga mudah diperluas di tahap berikutnya tanpa modifikasi Planner.
- 2026-10-15, tahap 1.4: PlanReport.total_changes menghitung jumlah Step yang memerlukan perubahan (bukan jumlah atomic Change), agar sesuai dengan format ringkasan teks dan JSON SPEC bagian 8.2.
- 2026-10-15, tahap 1.4: Argparse subparsers mewarisi opsi global (-c, --json, --no-color, -v) melalui parser parent agar fleksibel digunakan sebelum maupun sesudah nama subperintah.
- 2026-10-15, tahap 1.5: Pemeriksaan dependensi runtime terlarang diuji menggunakan AST scanner scripts/check-deps.py berbasis sys.stdlib_module_names dan PyYAML.
- 2026-10-16, tahap 2.1: RollbackEngine memeriksa status Step.reversible dan hanya membalikkan step reversible secara mundur; step ireversibel dicatat di audit dan dilaporkan ke pengguna.
- 2026-10-16, tahap 2.2: SshKeysStep mengelola blok bertanda `# BEGIN hostkeeper` / `# END hostkeeper` di ~/.ssh/authorized_keys agar tidak menghapus kunci milik pengguna yang sudah ada sebelumnya.
- 2026-10-16, tahap 2.3: SshdStep menggunakan drop-in /etc/ssh/sshd_config.d/00-hostkeeper.conf dan memverifikasi login kunci menggunakan keypair sementara serta konfirmasi pengetikan 'ya' sebelum mematikan password authentication.
- 2026-10-16, tahap 2.4: SafetyTimer menggunakan systemd-run timer transient (`hostkeeper-rollback-<run_id>`) untuk membatalkan perubahan secara otomatis jika koneksi terputus dan tidak dikonfirmasi dalam batas waktu tertentu.
- 2026-10-16, tahap 2.5: FirewallStep menggunakan aturan nftables dengan tabel independen inet hostkeeper dan service oneshot /etc/systemd/system/hostkeeper-firewall.service tanpa mengedit /etc/nftables.conf bawaan sistem.
- 2026-10-16, tahap 2.6: Wizard setup mengonversi data ke tipe YAML murni (misal tuple ke list) sebelum atomic write mode 0600 dan membuat file backup otomatis bertanda timestamp saat menimpa file profil lama.
- 2026-10-16, tahap 3.1: MetricCollector membaca /proc filesystem secara langsung untuk metrik sistem (stat, meminfo, pressure, diskstats) untuk efisiensi tanpa memanggil binary eksternal tambahan.
- 2026-10-16, tahap 3.2: StateDB menggunakan SQLite dalam mode WAL di /var/lib/hostkeeper/state.db dengan retensi otomatis untuk mencatat riwayat status dan hysteresis peringatan.
- 2026-10-16, tahap 3.3: Watch daemon menggunakan pasangan systemd service dan timer (hostkeeper-watch.timer) dengan interval terkonfigurasi, serta menyediakan hostkeeper watch test-notify untuk memverifikasi integrasi webhook.
- 2026-10-16, tahap 3.4: Hostkeeper status menggunakan ReadOnlyRunner dan ReadOnlyFileOps untuk memverifikasi kesesuaian profil secara aman tanpa efek samping pada sistem, mengembalikan exit code 3 jika terdeteksi status non-compliant.
- 2026-10-16, tahap 3.5: Versi ditingkatkan ke 0.3.0 pada pyproject.toml dan __init__.py, serta dokumentasi arsitektur, panduan keamanan, dan template GitHub issues/dependabot dilengkapi untuk kesiapan open source.

## Temuan dan pertanyaan terbuka


## Insiden
