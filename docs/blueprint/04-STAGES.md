# Tahap pengembangan

Format: Mode | Tugas | Tes wajib | Selesai jika. Rujukan SPEC = 01-SPEC.md. Semua tahap tunduk pada AGENTS.md.

# TAHAP 1 = v0.1 Fondasi

## 1.1 Persiapan repo dan tooling | Mode: Fast
Tugas:
- Struktur folder SPEC bagian 3 (placeholder valid), pyproject.toml (nama hostkeeper, 0.1.0, requires-python >=3.10,
  ruff, mypy strict dengan platform = "linux", pytest; extras dev: pytest, pytest-cov, ruff, mypy, pyyaml, types-PyYAML).
- src/hostkeeper/__init__.py (__version__) dan __main__.py minimal. .gitignore sesuai daftar: Python cache, .venv,
  .pytest_cache/.mypy_cache/.ruff_cache, .coverage, profile.yml, watch.yml (kecuali *.example.yml), .env, *.key, *.pem,
  state.db, audit.jsonl, backups/, journal/.
- scripts/check.sh: berhenti saat gagal; menjalankan sha256sum -c docs/blueprint/PROTECTED.sha256, ruff check, ruff format --check,
  mypy --strict src, pytest -q, shellcheck (jika skrip ada), dan pemindaian rahasia sederhana (grep pola token/private key).
- scripts/vm-sync.sh: rsync repo ke $TARGET (variabel lingkungan), mengecualikan .venv dan .git. Hanya untuk pemilik.
- .github/workflows/ci.yml: satu job lint (ruff, mypy) + pytest, permissions contents: read.
- Satu tes dummy. Kerangka docs/ARCHITECTURE.md, SECURITY.md, HOW_IT_WORKS.md (hanya judul bagian).
Selesai jika: check.sh hijau. Jangan mengerjakan modul lain.

## 1.2 Runner dan FileOps | Mode: Planning
Tugas: system/runner.py, system/fakes.py, system/fileops.py persis SPEC 4.1-4.2 (Runner, SubprocessRunner, ReadOnlyRunner,
FakeRunner, ReadOnlyViolation, RealFileOps, RecordingFileOps, ReadOnlyFileOps, FakeFileOps).
Tes wajib: timeout (timed_out=True), returncode bukan nol tidak melempar, mutates=True ditolak ReadOnlyRunner, FakeRunner mencatat
dan menolak perintah tak terprogram, write_atomic tidak meninggalkan file setengah jadi (simulasikan gagal di tengah), backup dibuat
sebelum menimpa, Recording tidak menyentuh disk, ReadOnly menolak tulis dan hapus. Pakai tmp_path. Impor fcntl/pwd/grp hanya di modul yang butuh.

## 1.3 Step, Profile, Planner, hostname, timezone | Mode: Planning
Tugas: engine/step.py (Risk, Change, CheckResult, Step), profile.py (skema v1, validasi hostname RFC 1123, timezone terhadap
/usr/share/zoneinfo dengan path injectable, nama paket, kunci tak dikenal = error), engine/planner.py (urutan requires, enabled()),
steps/hostname.py dan steps/timezone.py sesuai SPEC 5.1-5.2, steps/__init__.py (REGISTRY), messages.py, output.py minimal.
Tes wajib: tes generik atas REGISTRY (idempotency dengan FakeRunner), check() tidak memanggil perintah mutating, validasi input jahat
(hostname "a;b", zona "../x"), urutan requires, siklus requires terdeteksi.

## 1.4 Step paket, Executor, Audit, Journal, Lock, CLI | Mode: Planning
Tugas: steps/packages.py (SPEC 5.3, reversible=False), engine/executor.py (kebijakan SPEC 4.4: fail-fast, undo mundur hanya reversible),
engine/audit.py, engine/journal.py, engine/lock.py (flock /run/hostkeeper.lock, path injectable), env.py, output.py lengkap
(tabel, warna, NO_COLOR, --json), cli.py dengan version/plan/apply/verify, stub rollback/setup/watch/status (exit 2),
exit code SPEC bagian 7, penanganan error tanpa stack trace (kecuali -v).
Tes wajib: golden test output plan teks dan JSON, apply, verify, dan pesan error SPEC bagian 8; fail-fast dan undo; lock bentrok = exit 4;
bukan root saat apply = exit 5; plan dengan ReadOnlyRunner tidak pernah memanggil perintah mutating.

## 1.5 install.sh, uninstall.sh, launcher, CI penuh | Mode: Planning
Tugas: install.sh, uninstall.sh, packaging/hostkeeper.launcher sesuai SPEC bagian 9 (opsi --dry-run --no-deps --link --no-systemd --yes --prefix,
MANIFEST, idempotent, tidak menimpa config/data), docs/example-profile.yml, tests/data/profile.example.yml, docs/RELEASING.md,
ci.yml penuh sesuai SPEC bagian 11 (lint, unit matriks Python 3.10-3.13, install matriks Docker debian:12, debian:13, ubuntu:22.04, ubuntu:24.04, no-extra-deps).
Tes wajib: install dua kali, uninstall, cek tidak ada sisa, shellcheck bersih.
Gerbang VM: 05-TESTPLAN.md bagian V1.

# TAHAP 2 = v0.2 Setup lengkap
Semua tahap tahap 2 berisiko. Mode Planning dan WAJIB berhenti untuk persetujuan rencana. Semua perilaku nyata diuji pemilik di hk-target.

## 2.1 Rollback | Mode: Planning
Tugas: `hostkeeper rollback [RUN_ID] [--list] [--yes]`. Default: run terakhir. Baca journal, panggil undo() mundur hanya untuk Step reversible,
pulihkan backup file, tulis audit (event undo, termasuk alasan: manual atau timer). Step ireversibel dilaporkan "tidak dapat dibalik otomatis".
Tes wajib: rollback mengembalikan isi file persis, urutan mundur, journal rusak ditangani, run tidak ada = exit 2, idempotent bila diulang.

## 2.2 Step user dan sshkeys | Mode: Planning
Tugas: steps/user.py (useradd -m -s /bin/bash, grup sudo, /etc/sudoers.d/90-hostkeeper-<user> mode 0440, divalidasi visudo -cf pada file sementara
sebelum dipasang; admin_sudo_nopasswd default false, beri peringatan di plan jika false dan user tanpa password), steps/sshkeys.py
(~user/.ssh 700, authorized_keys 600 milik user; validasi format kunci ssh-ed25519/ecdsa/rsa dan base64; kelola blok bertanda hostkeeper,
JANGAN menghapus kunci milik pengguna). requires: sshkeys memerlukan user.
Tes wajib: sudoers tidak valid ditolak sebelum menyentuh /etc/sudoers.d, nama user jahat ditolak, kunci cacat ditolak, kunci lama tetap ada.

## 2.3 Step sshd dengan gerbang anti-terkunci | Mode: Planning
Tugas: steps/sshd.py: drop-in 00-hostkeeper.conf (lihat 01a koreksi 1 dan 2), check() lewat sshd -T. Pengubahan: PermitRootLogin, PasswordAuthentication, Port
(hanya 22 bila ssh.socket aktif). requires: user, sshkeys. risk high. Gerbang: (a) tes mekanisme: buat keypair sementara, pasang sementara untuk admin_user,
ssh -o BatchMode=yes ke 127.0.0.1 pada port efektif, hapus kunci sementara (selalu, dalam finally); (b) konfirmasi manusia: sebelum password_auth=false,
cetak instruksi login dari terminal kedua dan minta pengetikan "ya"; --yes TIDAK melewati gerbang ini kecuali flag --saya-sudah-uji-login-kunci.
Urutan apply: tulis drop-in, sshd -t (gagal = hapus drop-in), reload ssh (bukan restart), tes mekanisme lagi, baru tandai selesai.
Tes wajib: gerbang gagal berarti drop-in tidak ditulis, sshd -t gagal berarti file dihapus, ssh.socket aktif plus port bukan 22 ditolak, kunci sementara selalu dihapus.

## 2.4 Timer rollback independen | Mode: Planning
Tugas: untuk Step risk high, sebelum apply: systemd-run --on-active=<N>s --unit=hostkeeper-rollback-<run_id> hostkeeper rollback <run_id> --yes --reason timer
(N default 90, opsi --confirm-timeout). Setelah verify dan konfirmasi pemilik: systemctl stop hostkeeper-rollback-<run_id>.timer. Jika tidak dikonfirmasi,
perubahan kembali sendiri walau sesi SSH putus dan proses hostkeeper sudah mati. Cetak peringatan "Jangan tutup sesi ini, uji dari terminal kedua".
Tes wajib: urutan panggilan Runner (pasang timer, apply, verify, konfirmasi lalu batalkan timer), kegagalan memasang timer berarti apply TIDAK jalan.

## 2.5 Step updates dan firewall | Mode: Planning
Tugas: steps/updates.py (paket unattended-upgrades, /etc/apt/apt.conf.d/20auto-upgrades berisi Update-Package-Lists "1" dan Unattended-Upgrade "1").
steps/firewall.py: profil firewall.allow (mis. 22/tcp, 80/tcp); /etc/hostkeeper/firewall.nft berisi `delete table inet hostkeeper` lalu tabel dengan chain input
policy drop, ct established,related accept, iif lo accept, ICMP dan ICMPv6 accept, port yang diizinkan, DAN port SSH efektif selalu disertakan; validasi nft -c -f sebelum nft -f;
persistensi lewat hostkeeper-firewall.service (oneshot, WantedBy multi-user.target) milik sendiri, tidak mengedit /etc/nftables.conf; paket nftables dipastikan terpasang.
Tolak dengan penjelasan jika ufw atau firewalld aktif. requires: sshd. risk high, memakai timer 2.4.
Tes wajib: SSH port selalu ada di ruleset yang dihasilkan, ufw aktif ditolak, ruleset tidak valid tidak diterapkan, idempotent, undo menghapus tabel milik sendiri saja.

## 2.6 Wizard setup | Mode: Planning
Tugas: wizard.py dan `hostkeeper setup`. Pertanyaan berurutan: hostname, timezone, paket, admin user, kunci SSH (tempel atau path .pub, divalidasi), hardening SSH (konfirmasi),
port firewall, update otomatis. Memakai validator profile.py yang sama. Fungsi input diinjeksi agar bisa dites. Menulis profile.yml atomik mode 600; menimpa file lama hanya dengan konfirmasi dan backup.
Melewati pertanyaan yang kondisi server saat ini sudah sesuai (memanggil check). Menawarkan menjalankan plan, TIDAK pernah apply sendiri.
Tes wajib: profil hasil wizard identik dengan profil tulis tangan setara, input salah diulang, Ctrl-C tidak meninggalkan file setengah jadi.

# TAHAP 3 = v0.3 Watch dan rilis

## 3.1 Collector | Mode: Planning
Tugas: monitor/collectors/*.py, tiap collector menerima konteks dengan ProcFS injectable dan Runner read-only, mengembalikan daftar Metric (nama, nilai, satuan, status_hint).
Cpu/load, memori dan swap (MemAvailable), tekanan PSI /proc/pressure/{cpu,memory,io} (file tidak ada = status unknown, bukan error), disk dan inode (os.statvfs, mount dari konfigurasi),
sinkron waktu (timedatectl show: NTPSynchronized), service gagal (systemctl --failed --no-legend), update tertunda (apt-get -s upgrade, hitung Inst, hitung baris -security) dan /var/run/reboot-required,
login SSH gagal (journalctl -u ssh --since "-10min", hitung "Failed password" dan "Invalid user"). Semua baca-saja.
Tes wajib: isi /proc tiruan, output perintah tiruan, file hilang tidak membuat crash.

## 3.2 Evaluator dan state | Mode: Planning
Tugas: monitor/evaluator.py (ambang di /etc/hostkeeper/watch.yml dengan default aman; status ok/warn/crit/unknown; hysteresis dengan ambang pulih terpisah; cooldown; alert hanya saat transisi),
monitor/state.py (SQLite /var/lib/hostkeeper/state.db: tabel metrics(ts, name, value) dan alerts(name, status, since, last_notified); retensi 14 hari dipangkas tiap siklus; WAL; path injectable).
Tes wajib: tidak ada alert berulang untuk kondisi yang sama, pulih hanya setelah melewati ambang pulih, cooldown, retensi, DB rusak ditangani (buat ulang dan catat).

## 3.3 Notifier, perintah watch, unit systemd | Mode: Planning
Tugas: monitor/notify.py (urllib, POST JSON, timeout 5 detik, format slack|discord|json, URL webhook dari watch.yml mode 600, dimaskir di semua log; kegagalan dicatat tetapi tidak fatal),
`hostkeeper watch run|enable|disable|test-notify`; watch run mengambil lock non-blocking dan melewati siklus bila apply berjalan; packaging/systemd/hostkeeper-watch.service (oneshot, ExecStart watch run,
NoNewPrivileges, ReadWritePaths hanya /var/lib/hostkeeper /var/log/hostkeeper /run) dan .timer (OnBootSec=2min, OnUnitActiveSec=5min); update install.sh memasang unit (tidak di-enable);
docs/watch.example.yml dengan URL palsu.
Tes wajib: webhook gagal tidak menggagalkan siklus, URL tidak muncul di output atau log, lock bentrok melewati siklus, unit lolos `systemd-analyze verify` bila tersedia (tes di VM, bukan wajib CI).

## 3.4 Kesesuaian profil dan status | Mode: Planning
Tugas: collector profil yang memanggil check() semua Step enabled dengan ReadOnlyRunner dan ReadOnlyFileOps; tiap Step tidak sesuai menjadi status warn "Step <nama> tidak lagi sesuai profil".
`hostkeeper status [--json]`: tabel metrik terbaru berwarna dan baris kesesuaian profil; exit 0 jika semua ok, 3 jika ada warn atau crit.
Tes wajib: percobaan menulis di mode baca-saja melempar ReadOnlyViolation, drift terdeteksi dari sshd/hostname yang diubah, golden test status.

## 3.5 Dokumentasi dan kesiapan rilis | Mode: Fast
Tugas: README (masalah, demo teks, instalasi tiga baris, bagian "Kapan jangan pakai hostkeeper"), ARCHITECTURE.md, SECURITY.md (model ancaman), contoh profil,
CHANGELOG.md (0.1.0, 0.2.0, 0.3.0), template issue, .github/dependabot.yml untuk github-actions, kerangka docs/adr/. HOW_IT_WORKS.md hanya judul bagian (pemilik menulis isinya).
Selesai jika: check.sh hijau dan semua perintah di README benar-benar terverifikasi di VM mentah.
