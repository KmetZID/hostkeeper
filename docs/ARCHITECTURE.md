# Arsitektur hostkeeper

Dokumen ini menjelaskan arsitektur internal, komponen, dan aliran data `hostkeeper` v0.3.

---

## 1. Ringkasan Arsitektur

`hostkeeper` beroperasi secara lokal pada satu server (*single host*) Debian atau Ubuntu. Alat ini tidak memiliki daemon latar belakang persisten; sebagai gantinya, eksekusi periodik dikelola oleh unit timer `systemd`.

```text
               +----------------------------------+
               |   CLI / Wizard (argparse)        |
               +-----------------+----------------+
                                 |
        +------------------------+------------------------+
        |                                                 |
  [Setup / Plan / Apply / Rollback]                 [Watch & Status]
        |                                                 |
        v                                                 v
+-------+--------+                               +--------+-------+
|    Planner     |                               |   Collectors   |
| (DAG Resolver) |                               | (CPU, Mem, PSI,|
+-------+--------+                               |  Disk, Svcs...) |
        |                                        +--------+-------+
        v                                                 |
+-------+--------+      +------------------+              v
|    Executor    |<---->|  SafetyTimer     |     +--------+-------+
|  (Journal &    |      |  (systemd-run    |     | ProfileChecker |
|   Audit Log)   |      |   auto-rollback) |     +--------+-------+
+-------+--------+      +------------------+              |
        |                                                 v
        |                                        +--------+-------+
        |                                        |   Evaluator    |
        |                                        |  (Hysteresis)  |
        |                                        +--------+-------+
        |                                                 |
        |                                                 v
        |                                        +--------+-------+
        |                                        |  StateManager  |
        |                                        |  (SQLite WAL)  |
        |                                        +--------+-------+
        |                                                 |
        |                                                 v
        |                                        +--------+-------+
        |                                        |    Notifier    |
        |                                        | (Webhook POST) |
        |                                        +----------------+
        v
+-------+---------------------------------------------------------+
|                  System Abstraction Layer                       |
|   Runner (Subprocess / ReadOnly)  |  FileOps (Real / ReadOnly)  |
+-----------------------------------+-----------------------------+
```

---

## 2. Komponen Utama

### 2.1 Step (`hostkeeper.engine.step`)
Setiap unit konfigurasi sistem mengimplementasikan antarmuka abstrak `Step`:
- `enabled() -> bool`: menentukan apakah Step aktif berdasarkan profil.
- `check() -> CheckResult`: memeriksa kepatuhan sistem saat ini secara murni *read-only*.
- `plan() -> list[Change]`: merinci perubahan yang diperlukan.
- `apply() -> None`: menerapkan perubahan ke sistem.
- `verify() -> bool`: memverifikasi ulang bahwa sistem telah sesuai.
- `undo() -> None`: membalikkan perubahan (bila `reversible = True`).

Daftar Step yang didukung:
1. `HostnameStep`: Pengaturan hostname via `/etc/hostname` dan `hostnamectl`.
2. `TimezoneStep`: Pengaturan zona waktu via symlink `/etc/localtime` dan `timedatectl`.
3. `PackagesStep`: Instalasi paket dasar via `apt-get` non-interaktif.
4. `UserStep`: Pembuatan user admin dan konfigurasi `sudoers.d` (divalidasi dengan `visudo -cf`).
5. `SshKeysStep`: Pemasangan kunci publik SSH pada `authorized_keys` dengan penanda blok `# BEGIN hostkeeper` / `# END hostkeeper`.
6. `SshdStep`: Hardening OpenSSH via drop-in `/etc/ssh/sshd_config.d/00-hostkeeper.conf` dan verifikasi kunci login sebelum mematikan autentikasi kata sandi.
7. `UpdatesStep`: Konfigurasi pembaruan otomatis via `unattended-upgrades`.
8. `FirewallStep`: Konfigurasi aturan firewall `nftables` pada tabel mandiri `inet hostkeeper` dan persistensi via service oneshot.

### 2.2 Engine
- **Planner (`engine.planner`)**: Mengurutkan Step berdasarkan dependensi (`requires`) menggunakan Topological Sort (Kahn's Algorithm) dan mendeteksi siklus.
- **Executor (`engine.executor`)**: Menjalankan Step dengan pembuatan Journal terstruktur dan pencatatan audit JSON Lines.
- **RollbackEngine (`engine.rollback`)**: Mengembalikan konfigurasi ke status sebelumnya menggunakan snapshot file backup dan pemanggilan `step.undo()` secara terbalik.
- **SafetyTimer (`engine.safety_timer`)**: Mengaktifkan unit timer `systemd-run` transien saat melakukan perubahan berisiko tinggi. Jika koneksi terputus dan pemilik tidak mengonfirmasi pembatalan timer, sistem akan melakukan rollback otomatis secara independen.
- **LockManager (`engine.lock`)**: Menggunakan `fcntl.flock` eksklusif non-blocking pada `/run/hostkeeper.lock` untuk mencegah *race condition* antar-proses.

### 2.3 System Layer
- **Runner (`system.runner`)**: Menjalankan subprocess perintah Linux tanpa `shell=True`. Mendukung `ReadOnlyRunner` yang memblokir semua perintah mutasi (`mutates=True`).
- **FileOps (`system.fileops`)**: Mengelola operasi file secara atomik (`write_atomic` menggunakan file sementara dan `os.replace`), pencadangan otomatis (`shutil.copy2`), dan penegakan izin mode `0600`/`0700`.

### 2.4 Monitoring Subsystem (`hostkeeper.monitor`)
- **Collectors (`monitor.collectors`)**: Pengumpul metrik sistem berbasis read-only:
  - `cpu`: Beban loadavg 1/5/15 menit dan jumlah inti prosesor.
  - `memory`: Memori bebas, tersedia, dan swap dari `/proc/meminfo`.
  - `psi`: Pressure Stall Information dari `/proc/pressure/{cpu,memory,io}`.
  - `disk`: Penggunaan ruang dan inode via `os.statvfs`.
  - `time_sync`: Status sinkronisasi NTP via `timedatectl show`.
  - `services`: Deteksi layanan systemd yang gagal via `systemctl --failed`.
  - `updates`: Paket tertunda dan update keamanan via `apt-get -s upgrade` serta status `/run/reboot-required`.
  - `ssh_failed`: Deteksi percobaan login gagal via `journalctl -u ssh`.
- **ProfileChecker (`monitor.profile_checker`)**: Memeriksa drift konfigurasi terhadap profil YAML menggunakan `ReadOnlyRunner` dan `ReadOnlyFileOps`.
- **Evaluator (`monitor.evaluator`)**: Mengevaluasi metrik terhadap ambang batas `/etc/hostkeeper/watch.yml`. Menggunakan logika *hysteresis* (ambang batas pulih terpisah) dan *cooldown* untuk mencegah alert berulang.
- **StateManager (`monitor.state`)**: Menyimpan metrik dan status alert pada SQLite `/var/lib/hostkeeper/state.db` dengan mode WAL dan retensi 14 hari.
- **Notifier (`monitor.notify`)**: Mengirimkan webhook alert (Slack, Discord, JSON) dengan penyamaran (*masking*) token dan URL rahasia.

---

## 3. Aliran Data dan Siklus Eksekusi

1. **Siklus Plan-Apply**:
   - Profil dibaca dan divalidasi skemanya (`version: 1`, tipe data, sanitasi input).
   - Planner menyusun urutan eksekusi Step.
   - Mode `plan` memanggil `step.check()` dan menghasilkan ringkasan perbedaan tanpa memodifikasi sistem.
   - Mode `apply` meminta konfirmasi pemilik, mengaktifkan `SafetyTimer` bila ada Step berisiko tinggi, menulis perubahan atomik, memverifikasi hasil, dan mencatat ke Journal.

2. **Siklus Watch**:
   - Dipicu setiap 5 menit oleh `hostkeeper-watch.timer`.
   - Mengambil lock non-blocking; jika proses `hostkeeper` lain sedang berjalan, siklus monitoring dilewati dengan aman.
   - Seluruh collector mengumpulkan metrik sistem dan memeriksa kesesuaian profil.
   - Metrik disimpan ke SQLite `state.db`.
   - Evaluator mendeteksi apakah terjadi transisi status (`ok -> warn`, `warn -> crit`, `crit/warn -> ok`).
   - Notifikasi dikirimkan ke webhook hanya jika terjadi transisi status baru.
   - Metrik yang berusia lebih dari 14 hari dipangkas otomatis.

---

## 4. Kontrak Antarmuka Abstraksi

Untuk menjamin keamanan eksekusi dan memfasilitasi pengujian tanpa efek samping, sistem dibagi atas kontrak antarmuka yang ketat:

### 4.1 Kontrak Step (`hostkeeper.engine.step.Step`)
Setiap konfigurasi domain sistem wajib merupakan turunan dari kelas basis abstrak `Step`:
- **Atribut Kelas**:
  - `name: str`: Nama identifikasi unik Step dalam huruf kecil (mis. `"sshd"`, `"firewall"`).
  - `description: str`: Deskripsi satu baris dalam Bahasa Indonesia.
  - `risk: RiskLevel`: Tingkat risiko (`RiskLevel.LOW` atau `RiskLevel.HIGH`).
  - `reversible: bool`: Menandakan apakah mutasi yang dilakukan dapat dibalikkan secara aman (bawaan: `True`).
  - `requires: tuple[type[Step], ...]`: Tuple dependensi `Step` lain yang harus dieksekusi sebelumnya.
- **Metode Siklus Hidup**:
  - `enabled() -> bool`: Mengembalikan `True` jika Step aktif berdasarkan konfigurasi profil yang dimuat.
  - `check() -> CheckResult`: Memeriksa kondisi sistem saat ini secara murni *read-only*. Dilarang keras melakukan mutasi file atau mengeksekusi perintah dengan `mutates=True`. Mengembalikan objek `CheckResult(compliant, current, target, drift_details)`.
  - `plan() -> list[Change]`: Menghitung daftar perubahan deskriptif yang diperlukan untuk membawa sistem ke kondisi profil target.
  - `apply() -> None`: Menerapkan perubahan pada sistem operasi melalui `self.runner` dan `self.fileops`.
  - `verify() -> bool`: Memeriksa ulang apakah sistem telah mencapai kondisi compliant setelah `apply()`.
  - `undo() -> None`: Membalikkan mutasi sistem ke kondisi semula jika terjadi kegagalan atau dipicu oleh perintah `rollback`.

### 4.2 Kontrak Runner (`hostkeeper.system.runner.Runner`)
Menyediakan abstraksi eksekusi perintah sistem biner:
- **Metode**: `run(argv: Sequence[str], mutates: bool = False, check: bool = False, timeout: float | None = None) -> ProcessResult`
- **Aturan Ketat**:
  - Dilarang memanggil `shell=True`, `os.system`, atau `eval`/`exec`. Parameter `argv` wajib berupa list argumen biner eksplisit.
  - Nilai balik `ProcessResult(returncode: int, stdout: str, stderr: str, ok: bool)`.
  - **Implementasi**:
    - `SubprocessRunner`: Menjalankan proses biner nyata via `subprocess.run`.
    - `ReadOnlyRunner`: Digunakan pada mode `plan`, `verify`, `status`, dan `watch`. Jika dipanggil dengan flag `mutates=True`, langsung melempar exception fatal `ReadOnlyViolation`.
    - `FakeRunner`: Digunakan pada pengujian unit terisolasi.

### 4.3 Kontrak FileOps (`hostkeeper.system.fileops.FileOps`)
Menyediakan abstraksi manipulasi sistem berkas:
- **Metode Inti**:
  - `read_text(path: Path | str) -> str`: Membaca konten berkas UTF-8.
  - `write_text(path: Path | str, content: str, mode: int | None = None, backup: bool = True) -> None`: Menulis berkas secara atomik (menggunakan berkas sementara di direktori yang sama lalu `os.replace`). Jika `backup=True` dan berkas sudah ada, salinan dicadangkan otomatis.
  - `exists(path: Path | str) -> bool`: Memeriksa keberadaan berkas atau direktori.
  - `copy(src: Path | str, dst: Path | str) -> None`: Menyalin berkas dengan mempertahankan metadata (`shutil.copy2`).
- **Implementasi**:
  - `RealFileOps`: Operasi berkas nyata pada filesystem Linux.
  - `ReadOnlyFileOps`: Melempar `ReadOnlyViolation` jika ada metode penulisan, penghapusan, atau penyalinan mutatif yang dipanggil.

---

## 5. Alur Alur Eksekusi Terperinci (Plan, Apply, Verify, Rollback)

```text
+-----------------------------------------------------------------------------+
| 1. PLAN FLOW (hostkeeper plan)                                              |
|                                                                             |
| load_profile() --> detect_env() --> Planner.resolve()                       |
|        |                                    |                               |
|        v                                    v                               |
| ReadOnlyRunner & ReadOnlyFileOps   Topological DAG order                    |
|        |                                    |                               |
|        +------------------------------------+                               |
|                                 |                                           |
|                     for step in ordered_steps:                              |
|                       step.enabled()?                                       |
|                         yes: step.check() & step.plan()                     |
|                                 |                                           |
|                     render plan table / JSON --> EXIT_OK                    |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| 2. APPLY FLOW (sudo hostkeeper apply)                                       |
|                                                                             |
| verify_root() --> LockManager.acquire() --> load_profile()                  |
|        |                                                                    |
|        v                                                                    |
| Planner.resolve() --> prompt_user_confirmation()                           |
|        |                                                                    |
|        v (jika ada Step berisiko tinggi)                                    |
| SafetyTimer.start(90s) via transient systemd-run timer                      |
|        |                                                                    |
|        v                                                                    |
| Executor: buat journal entry (/var/lib/hostkeeper/journal/<run_id>.jsonl)   |
| for step in ordered_steps:                                                  |
|   backup existing files --> step.apply() --> step.verify()                  |
|   if verify failed: trigger RollbackEngine automatically                    |
|        |                                                                    |
|        v                                                                    |
| SafetyTimer.cancel() --> tulis status selesai ke Journal & Audit            |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| 3. VERIFY FLOW (hostkeeper verify)                                          |
|                                                                             |
| ReadOnlyRunner & ReadOnlyFileOps                                            |
| for step in ordered_steps:                                                  |
|   res = step.check()                                                        |
|   if not res.compliant: record drift                                       |
|        |                                                                    |
|        v                                                                    |
| if any drift: return EXIT_DRIFT (3)                                         |
| else: return EXIT_OK (0)                                                    |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| 4. ROLLBACK FLOW (sudo hostkeeper rollback <RUN_ID>)                        |
|                                                                             |
| verify_root() --> LockManager.acquire()                                     |
| JournalManager.read_run(<RUN_ID>)                                           |
|        |                                                                    |
|        v                                                                    |
| for step_entry in reversed(journal.steps):                                  |
|   1. restore backed-up files from /var/lib/hostkeeper/backups/<run_id>/    |
|   2. if step.reversible: step.undo()                                        |
|   3. step.verify()                                                          |
|        |                                                                    |
|        v                                                                    |
| catat audit rollback selesai --> return EXIT_OK (0)                         |
+-----------------------------------------------------------------------------+
```

