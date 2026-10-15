# hostkeeper: Spesifikasi Fondasi v0.1

Dokumen untuk AI agent pelaksana. Isinya: kerangka, file, perintah sistem, kontrak kode, format data, perintah CLI, output yang diharapkan, tes, dan CI.

## 0. Aturan untuk agen pelaksana

1. Kerjakan **hanya lingkup v0.1** (bagian 12). Jangan menambah fitur dari versi lain.
2. **Hanya stdlib Python 3.10+** ditambah `python3-yaml` (import `yaml`). Dilarang menambah dependensi runtime lain.
3. **Dilarang `shell=True`**, `os.system`, dan `eval`. Semua perintah berupa list argumen.
4. **Dilarang akses jaringan** dari kode hostkeeper (selain apa yang dilakukan `apt-get`).
5. **Tidak ada Step yang boleh memanggil `subprocess`, `open()` untuk menulis, atau `os.*` yang mengubah file secara langsung.** Semuanya lewat `system.Runner` dan `system.FileOps`.
6. Identifier kode dalam bahasa Inggris, pesan untuk pengguna dalam bahasa Indonesia dan dikumpulkan di satu modul `messages.py`.
7. Semua kode diberi type hint dan lolos `ruff` dan `mypy --strict` untuk `src/`.
8. Setiap Step wajib punya tes idempotency (apply dua kali, kali kedua nol perubahan) memakai `FakeRunner`.
9. Jika ada hal ambigu, pilih opsi paling aman (tidak mengubah sistem) dan catat di `docs/adr/`.
10. CI dikerjakan agen. CD (rilis) dilakukan manual oleh pemilik repo.

## 1. Ringkasan produk dan batas

hostkeeper menyiapkan server Debian/Ubuntu sesuai profil YAML, lalu (v0.4) menjaganya tetap sehat dan sesuai profil. Satu host, dijalankan lokal sebagai root, tanpa daemon, tanpa database server.

| Item | Nilai |
|---|---|
| OS didukung | Debian 12, Debian 13, Ubuntu 22.04, Ubuntu 24.04 |
| Init | systemd wajib |
| Bahasa | Python 3.10+ |
| Dependensi runtime | `python3`, `python3-yaml` (paket apt) |
| Instalasi | `git clone` lalu `sudo ./install.sh` |
| Prinsip | plan, apply, verify, rollback. Default aman. File milik sendiri saja |

**Batas dengan project lain:** konfigurasi IP, DHCP, NAT, routing adalah ranah project `netagent`, bukan hostkeeper.

## 2. Kerangka kerja

```
profile.yml -> PLAN -> tampilkan diff -> konfirmasi -> APPLY -> VERIFY
                                                        |         |
                                                        +-gagal?--+-> UNDO (langkah yang reversible)
```

Tiga jenis komponen:

| Komponen | Peran |
|---|---|
| **Step** | Satu unit pekerjaan dengan `check / plan / apply / verify / undo`. Hanya berisi logika |
| **Engine** | Mengurutkan Step, menjalankan, mencatat audit, mengelola lock dan journal |
| **System** | Satu-satunya pintu ke OS: `Runner` (perintah) dan `FileOps` (file). Bisa diganti versi palsu saat tes |

Aliran lapisan:

```
CLI -> Profile -> Planner -> Step -> Runner / FileOps -> OS
                     |
                  Executor -> Audit, Journal, Lock
```

**Mekanisme jaminan keamanan:**

- `Runner.run(argv, mutates=False)`. Perintah yang mengubah sistem harus dipanggil dengan `mutates=True`. Pada mode plan/verify, Runner yang dipakai adalah `ReadOnlyRunner`, yang melempar `ReadOnlyViolation` jika `mutates=True`. Dengan begitu `plan` terbukti tidak bisa mengubah sistem.
- `FileOps` punya tiga implementasi: `RealFileOps` (apply), `RecordingFileOps` (plan, hanya mencatat), `ReadOnlyFileOps` (verify, melempar error jika menulis).
- `check()` wajib murni: hanya membaca. Ini diuji otomatis dan akan dipakai ulang oleh monitoring di v0.4.

## 3. Peta file

```
hostkeeper/
|-- install.sh                    pasang tool ke /usr/local (tidak mengubah server)
|-- uninstall.sh                  hapus tool (config dan data tetap, kecuali --purge)
|-- README.md  CHANGELOG.md  LICENSE  pyproject.toml
|-- packaging/
|   +-- hostkeeper.launcher       skrip shell kecil yang menjadi /usr/local/bin/hostkeeper
|-- src/hostkeeper/
|   |-- __init__.py               __version__
|   |-- __main__.py               memanggil cli.main()
|   |-- cli.py                    argparse, dispatch subcommand, exit code
|   |-- messages.py               semua teks untuk pengguna (Indonesia)
|   |-- output.py                 render tabel, warna (hormati NO_COLOR dan non-TTY), mode --json
|   |-- env.py                    deteksi OS (/etc/os-release), root, systemd, versi Python
|   |-- profile.py                load YAML, skema, validasi, default
|   |-- engine/
|   |   |-- step.py               kelas dasar Step, Change, State, Risk, CheckResult
|   |   |-- planner.py            susun urutan Step, panggil check() dan plan()
|   |   |-- executor.py           apply, verify, kebijakan gagal
|   |   |-- journal.py            catatan undo per run
|   |   |-- audit.py              audit.jsonl (append-only)
|   |   +-- lock.py               flock /run/hostkeeper.lock
|   |-- system/
|   |   |-- runner.py             Runner, ReadOnlyRunner, CmdResult
|   |   |-- fakes.py              FakeRunner, FakeFileOps (untuk tes)
|   |   +-- fileops.py            RealFileOps, RecordingFileOps, ReadOnlyFileOps
|   +-- steps/
|       |-- __init__.py           REGISTRY urutan Step
|       |-- hostname.py
|       |-- timezone.py
|       +-- packages.py
|-- tests/
|   |-- unit/                     pytest + FakeRunner (jalan tanpa root)
|   |-- golden/                   output plan yang dibekukan (teks dan JSON)
|   +-- integration/run_vm.sh     skrip tes di VM nyata (dijalankan manual)
|-- docs/  ARCHITECTURE.md  HOW_IT_WORKS.md (dikosongkan untuk pemilik)  SECURITY.md  adr/
+-- .github/workflows/ci.yml
```

`docs/HOW_IT_WORKS.md` hanya diberi kerangka judul. Isinya ditulis pemilik repo sendiri.

## 4. Kontrak kode

### 4.1 system/runner.py

```python
@dataclass(frozen=True)
class CmdResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    @property
    def ok(self) -> bool: ...

class Runner(Protocol):
    def run(self, argv: Sequence[str], *, mutates: bool = False,
            timeout: float = 60.0, input: str | None = None,
            env: Mapping[str, str] | None = None) -> CmdResult: ...
```

- `SubprocessRunner`: `subprocess.run(argv, capture_output=True, text=True, timeout=...)`, tidak melempar saat returncode bukan 0, `timed_out=True` saat timeout. Mengatur `LC_ALL=C` agar output bisa diparse, dan `DEBIAN_FRONTEND=noninteractive` untuk apt.
- `ReadOnlyRunner`: membungkus runner asli, menolak `mutates=True`.
- `FakeRunner` (tes): menerima tabel respons terprogram, mencatat semua panggilan di `.calls`, melempar error jika ada perintah tak terprogram.
- Setiap panggilan ditulis ke audit (event `command`, tanpa env dan tanpa `input`).

### 4.2 system/fileops.py

```python
class FileOps(Protocol):
    def read_text(self, path: Path) -> str | None: ...        # None jika tidak ada
    def write_atomic(self, path: Path, content: str, *, mode: int,
                     owner: str = 'root', group: str = 'root') -> None: ...
    def remove(self, path: Path) -> None: ...
```

- `write_atomic`: tulis ke file sementara di direktori yang sama, `fsync`, set mode dan pemilik, lalu `os.replace`. Jika file lama ada, **salin dulu ke** `/var/lib/hostkeeper/backups/<run_id>/<path absolut>` dan catat ke journal.
- `RecordingFileOps`: tidak menyentuh disk, hanya menambah `Change`.
- `ReadOnlyFileOps`: `read_text` jalan, tulis/hapus melempar `ReadOnlyViolation`.

### 4.3 engine/step.py

```python
class Risk(str, Enum): LOW='rendah'; MEDIUM='sedang'; HIGH='tinggi'

@dataclass(frozen=True)
class Change:
    step: str
    action: str        # 'set' | 'install' | 'write' | 'remove'
    target: str        # mis. 'hostname', 'pkg:htop', '/etc/x'
    before: str | None
    after: str | None

@dataclass(frozen=True)
class CheckResult:
    compliant: bool
    current: str       # nilai sekarang, untuk ditampilkan
    detail: str = ''

class Step(ABC):
    name: ClassVar[str]
    risk: ClassVar[Risk]
    requires: ClassVar[tuple[str, ...]] = ()
    reversible: ClassVar[bool] = True

    def __init__(self, profile: Profile, runner: Runner, fs: FileOps): ...
    def enabled(self) -> bool        # False jika profil tidak mengatur bagian ini
    def check(self) -> CheckResult   # MURNI: hanya membaca
    def plan(self) -> list[Change]   # kosong jika compliant
    def apply(self, changes: list[Change]) -> None
    def verify(self) -> CheckResult  # default: check() ulang
    def undo(self, changes: list[Change]) -> None
```

### 4.4 engine/executor.py (kebijakan)

1. Ambil lock eksklusif (`flock` non-blocking). Gagal -> exit 4.
2. Buat `run_id` format `20260114T093000Z-ab12`.
3. Untuk tiap Step berurutan: `plan()`. Tampilkan. Minta konfirmasi (kecuali `--yes`).
4. Per Step yang punya perubahan: `apply()` -> `verify()`.
5. Jika `apply` melempar error atau `verify` tidak compliant: **berhenti (fail-fast)**, panggil `undo()` untuk Step itu dan Step yang sudah diterapkan di run ini secara mundur, **hanya yang `reversible=True`**. Sisa Step ditandai `dilewati`. Exit 1.
6. Tulis journal dan audit di setiap tahap.

### 4.5 Journal, audit, lock

- Journal: `/var/lib/hostkeeper/journal/<run_id>.json`, berisi daftar Step, `Change`, dan lokasi backup. Dipakai `rollback` mulai v0.2.
- Audit: `/var/log/hostkeeper/audit.jsonl`, mode 640, append-only (satu objek JSON per baris).
- Lock: `/run/hostkeeper.lock`.

## 5. Cara kerja tiap Step di sistem

Urutan eksekusi: hostname, timezone, packages.

### 5.1 `hostname` (risiko rendah)

| Fase | Perintah / aksi |
|---|---|
| check | `hostnamectl --static` (baca-saja). Bandingkan dengan `profile.hostname` |
| plan | `Change(set, hostname, before, after)` |
| apply | `hostnamectl set-hostname <nama>` (`mutates=True`) |
| verify | `hostnamectl --static` harus sama dengan profil |
| undo | `hostnamectl set-hostname <before>` |
| peringatan | Jika `getent hosts <nama>` gagal, verify memberi **peringatan** (bukan gagal): sudo bisa mengeluh. v0.1 **tidak mengedit /etc/hosts**. Jika `/etc/cloud/` ada dan `preserve_hostname` tidak true, beri peringatan bahwa cloud-init bisa mengembalikan hostname saat reboot |

Validasi: RFC 1123, huruf kecil, angka, tanda hubung, tiap label 1-63 karakter, total maksimal 253.

### 5.2 `timezone` (risiko rendah)

| Fase | Perintah / aksi |
|---|---|
| check | `timedatectl show -p Timezone --value` |
| plan | `Change(set, timezone, before, after)` |
| apply | `timedatectl set-timezone <zona>` |
| verify | baca lagi, harus sama |
| undo | `timedatectl set-timezone <before>` |

Validasi: file `/usr/share/zoneinfo/<zona>` harus ada dan zona tidak boleh mengandung `..`.

### 5.3 `packages` (risiko rendah, `reversible=False`)

| Fase | Perintah / aksi |
|---|---|
| check | `dpkg-query -W -f='${Package} ${Status}\n' <pkg...>`. Terpasang jika status `install ok installed`. Returncode 1 untuk paket tak dikenal itu normal, parse stdout |
| validasi | `apt-cache policy <pkg>`: jika `Candidate: (none)` atau tidak ada, plan gagal dengan pesan jelas (paket tidak tersedia, mungkin perlu `apt-get update`) |
| plan | satu `Change(install, pkg:<nama>)` per paket yang belum terpasang |
| apply | `apt-get update` sekali, lalu `apt-get install -y --no-install-recommends <pkg...>` dengan `DEBIAN_FRONTEND=noninteractive`, timeout 600 detik |
| verify | `check()` ulang, semua harus terpasang |
| undo | **tidak ada**. Paket tidak dihapus otomatis (berisiko). Executor melaporkan: `tidak dapat dibalik otomatis` |

Validasi nama paket: regex `^[a-z0-9][a-z0-9+.-]*$`. Maksimal 100 paket.

## 6. Format data

### 6.1 Profil `/etc/hostkeeper/profile.yml` (mode 600)

```yaml
version: 1
hostname: web-01
timezone: Asia/Jakarta
packages:
  - curl
  - vim
  - htop
```

Aturan: `version` wajib bernilai 1. Bagian yang tidak ada berarti Step tersebut `enabled() == False` dan dilewati. Kunci tak dikenal -> error (menangkap salah ketik). Skema hanya boleh **bertambah** dengan field opsional di versi berikutnya.

### 6.2 Audit `audit.jsonl`

```json
{"ts":"2026-01-14T09:30:00Z","run_id":"20260114T093000Z-ab12","event":"step_applied","step":"hostname","changes":1,"result":"ok"}
```

Event: `run_start`, `plan`, `command`, `step_applied`, `step_verified`, `step_failed`, `undo`, `run_end`. Field baru boleh ditambah, jangan dihapus atau diganti nama.

### 6.3 Journal `journal/<run_id>.json`

```json
{"run_id":"...","hostkeeper":"0.1.0","profile_sha256":"...",
 "steps":[{"name":"hostname","status":"applied","reversible":true,
           "changes":[{"action":"set","target":"hostname","before":"web-old","after":"web-01"}],
           "backups":[]}]}
```

### 6.4 Lokasi di server

```
/usr/local/lib/hostkeeper/hostkeeper/   kode (+ MANIFEST daftar file terpasang)
/usr/local/bin/hostkeeper               launcher
/etc/hostkeeper/profile.yml             profil (600), direktori 700
/var/lib/hostkeeper/backups/<run_id>/   backup file sebelum diubah
/var/lib/hostkeeper/journal/<run_id>.json
/var/log/hostkeeper/audit.jsonl         (640)
/run/hostkeeper.lock
```

## 7. Peta perintah CLI (seluruh roadmap)

| Perintah | Fungsi | Versi |
|---|---|---|
| `hostkeeper version` | Versi dan info lingkungan | **v0.1** |
| `hostkeeper plan [-c FILE] [--json] [--check]` | Tampilkan perubahan, tanpa mengubah apa pun | **v0.1** |
| `hostkeeper apply [-c FILE] [--yes] [--dry-run]` | Terapkan dengan konfirmasi, lalu verify | **v0.1** |
| `hostkeeper verify [-c FILE] [--json]` | Cek kesesuaian, tanpa mengubah | **v0.1** |
| `hostkeeper rollback [RUN_ID]` | Kembalikan run (dari journal) | v0.2 |
| `hostkeeper setup` | Wizard interaktif, menulis profil | v0.3 |
| `hostkeeper watch run/enable/disable` | Satu siklus monitoring, atur timer | v0.4 |
| `hostkeeper status` | Kartu kesehatan dan kecocokan profil | v0.4 |

Di v0.1, `rollback`, `setup`, `watch`, `status` **terdaftar** di argparse dan mencetak `Belum tersedia (direncanakan v0.X)` dengan exit 2.

**Opsi global:** `-c/--config FILE` (default `/etc/hostkeeper/profile.yml`), `--json`, `--no-color`, `-v` (tampilkan perintah yang dijalankan).

**Exit code:**

| Kode | Arti |
|---|---|
| 0 | Sukses / sudah sesuai |
| 1 | Error saat eksekusi (apply atau verify Step gagal) |
| 2 | Pemakaian salah / profil tidak valid / fitur belum tersedia |
| 3 | Drift: `verify` atau `plan --check` menemukan ketidaksesuaian |
| 4 | Instance lain sedang berjalan (lock) |
| 5 | Lingkungan tidak didukung atau butuh root |

`plan` dan `verify` boleh dijalankan tanpa root selama perintah baca-saja berhasil. `apply` wajib root.

## 8. Output yang diharapkan (v0.1)

Warna hanya pada TTY dan dimatikan oleh `NO_COLOR` atau `--no-color`. Lambang: `[=]` sudah sesuai, `[~]` ubah, `[+]` tambah, `[!]` gagal, `[-]` dilewati.

### 8.1 `hostkeeper version`

```
hostkeeper 0.1.0
OS      : Debian GNU/Linux 12 (bookworm)  [didukung]
Python  : 3.11.2
systemd : aktif
Profil  : /etc/hostkeeper/profile.yml (ada)
```

### 8.2 `hostkeeper plan`

```
hostkeeper 0.1.0 plan
Profil: /etc/hostkeeper/profile.yml (version 1)
Host  : web-old

 STATUS  STEP       PERUBAHAN                                   RISIKO
 [~]     hostname   web-old -> web-01                           rendah
 [=]     timezone   Asia/Jakarta (sudah sesuai)                 -
 [+]     packages   pasang: htop, vim (curl sudah terpasang)    rendah

Ringkasan: 2 perubahan, 1 sudah sesuai, 0 berisiko tinggi.
Mode plan: tidak ada yang diubah. Jalankan `sudo hostkeeper apply` untuk menerapkan.
```

Jika semua sesuai: `Ringkasan: 0 perubahan. Server sudah sesuai profil.` dengan exit 0.

`plan --json`:

```json
{"version":"0.1.0","profile":"/etc/hostkeeper/profile.yml",
 "steps":[{"name":"hostname","status":"change","risk":"rendah",
   "changes":[{"action":"set","target":"hostname","before":"web-old","after":"web-01"}]},
  {"name":"timezone","status":"ok","risk":"rendah","changes":[]}],
 "summary":{"changes":2,"ok":1,"high_risk":0}}
```

### 8.3 `sudo hostkeeper apply`

```
hostkeeper 0.1.0 apply (run 20260114T093000Z-ab12)
[tampilkan tabel plan seperti 8.2]

Lanjutkan menerapkan 2 perubahan? [y/N] y

 [~] hostname   web-old -> web-01 ........ OK (verify lolos)
 [+] packages   htop, vim ................ OK (verify lolos)

Selesai: 2 diterapkan, 0 gagal. Jalankan `hostkeeper verify` untuk memastikan.
Journal: /var/lib/hostkeeper/journal/20260114T093000Z-ab12.json
```

Menjalankan `apply` lagi segera setelahnya harus mencetak `Ringkasan: 0 perubahan. Server sudah sesuai profil.` dan **tidak** meminta konfirmasi (**ini tes utama idempotency**).

Jika langkah gagal:

```
 [~] hostname   web-old -> web-01 ........ OK
 [!] packages   apt-get install gagal (exit 100): E: Unable to locate package foo
 [-] (tidak ada Step tersisa)
Kegagalan: Step packages. Membalik Step yang reversible: hostname dikembalikan ke web-old.
Catatan: packages tidak dapat dibalik otomatis.
```

Exit 1. `--dry-run` identik dengan `plan` tetapi lewat jalur apply (diuji sama).

### 8.4 `hostkeeper verify`

Sesuai (exit 0):

```
 [=] hostname   web-01
 [=] timezone   Asia/Jakarta
 [=] packages   curl, vim, htop terpasang
Semua Step sesuai profil.
```

Drift (exit 3):

```
 [~] hostname   diharapkan web-01, sekarang web-old
 [=] timezone   Asia/Jakarta
 [~] packages   belum terpasang: htop
2 Step menyimpang dari profil. Jalankan `hostkeeper plan` untuk detail.
```

### 8.5 Error yang harus ditangani rapi (tanpa stack trace)

```
$ hostkeeper apply            (bukan root)
ERROR: apply membutuhkan root. Jalankan: sudo hostkeeper apply        [exit 5]

$ hostkeeper plan -c bad.yml
ERROR: profil tidak valid: hostname 'Web_01' tidak sah (hanya a-z, 0-9, '-')   [exit 2]

$ hostkeeper apply            (instance lain berjalan)
ERROR: hostkeeper lain sedang berjalan (lock /run/hostkeeper.lock).    [exit 4]
```

Stack trace hanya muncul dengan `-v`. Semua exception tak terduga ditangkap di `cli.main()`, dicatat ke audit, dan exit 1.

## 9. install.sh dan uninstall.sh

**Prinsip:** menginstal tool tidak mengubah server (tidak menyentuh hostname, SSH, firewall). Perubahan hanya terjadi lewat `hostkeeper apply`.

### install.sh

Opsi: `--dry-run`, `--no-deps`, `--link` (symlink ke clone, mode developer), `--no-systemd` (untuk Docker/CI), `--yes`, `--prefix DIR` (default `/usr/local`).

| # | Langkah |
|---|---|
| 1 | `set -Eeuo pipefail`. Jika bukan root, `exec sudo -- "$0" "$@"` |
| 2 | Pre-flight: `/etc/os-release` harus `debian:12`, `debian:13`, `ubuntu:22.04`, `ubuntu:24.04`. `/run/systemd/system` harus ada kecuali `--no-systemd`. Python >= 3.10 |
| 3 | Jika `python3` atau `import yaml` belum ada: `apt-get update -qq` lalu `apt-get install -y --no-install-recommends python3 python3-yaml` (dilewati dengan `--no-deps`) |
| 4 | Salin `src/hostkeeper` ke `$PREFIX/lib/hostkeeper/hostkeeper` (hapus versi lama dulu, kecuali mode `--link`) |
| 5 | Pasang launcher `$PREFIX/bin/hostkeeper` (`PYTHONPATH=$PREFIX/lib/hostkeeper exec python3 -m hostkeeper "$@"`) |
| 6 | Buat `/etc/hostkeeper` (700), `/var/lib/hostkeeper` (700), `/var/log/hostkeeper` (750). **Tidak menimpa isi yang sudah ada** |
| 7 | Jika ada `packaging/systemd/*.service|*.timer`, salin ke `/etc/systemd/system/` dan `daemon-reload` (tidak di-enable). Di v0.1 folder ini belum ada, jadi langkah dilewati |
| 8 | Tulis `$PREFIX/lib/hostkeeper/VERSION` dan `MANIFEST` (daftar semua file terpasang) |
| 9 | Smoke test: jalankan `hostkeeper version`, gagal -> exit non-zero |
| 10 | Cetak ringkasan |

Output akhir:

```
hostkeeper 0.1.0 terpasang.
  Kode      : /usr/local/lib/hostkeeper
  Perintah  : /usr/local/bin/hostkeeper
  Config    : /etc/hostkeeper (belum ada profil)
Server TIDAK diubah. Langkah berikutnya:
  1. Buat /etc/hostkeeper/profile.yml (lihat docs/example-profile.yml)
  2. sudo hostkeeper plan
  3. sudo hostkeeper apply
```

Menjalankan ulang = upgrade: kode ditimpa, profil, backup, journal, dan audit tidak disentuh. Fungsi `run()` membuat `--dry-run` mencetak `[dry-run] <perintah>` tanpa menjalankannya.

### uninstall.sh

- Default: hapus file dalam `MANIFEST`, launcher, dan unit systemd (disable dulu jika ada). **Config dan data tetap**.
- `--purge`: hapus juga `/etc/hostkeeper`, `/var/lib/hostkeeper`, `/var/log/hostkeeper`.
- Mencetak peringatan: uninstall **tidak** membalik perubahan yang pernah dibuat `apply`.
- Idempotent: dijalankan saat belum terpasang -> pesan `tidak terpasang`, exit 0.
- Setelah uninstall (tanpa purge), tidak boleh ada sisa di `/usr/local/lib/hostkeeper` dan `/usr/local/bin/hostkeeper`.

## 10. Strategi tes

| Lapis | Isi | Lingkungan |
|---|---|---|
| Unit | Tiap Step dengan `FakeRunner` dan `FakeFileOps`: check, plan, apply, verify, undo, kasus gagal | pytest, tanpa root |
| Idempotency | Untuk tiap Step: apply lalu plan ulang -> kosong. Tes generik yang menjalankan semua Step di `REGISTRY` | pytest |
| Keamanan | `plan` dengan `ReadOnlyRunner` tidak pernah memanggil perintah `mutates=True`. `check()` tidak menulis | pytest |
| Validasi profil | Hostname jelek, zona fiktif, nama paket aneh (`foo; rm -rf /`), kunci tak dikenal, version salah | pytest |
| Golden | Output `plan` teks dan JSON dibekukan di `tests/golden/` | pytest |
| Engine | Fail-fast, undo mundur hanya yang reversible, lock bentrok, audit dan journal tertulis | pytest |
| CLI | Exit code dan pesan error (8.5) | pytest |
| Instalasi | `install.sh` dua kali, `hostkeeper version`, `uninstall.sh`, cek tidak ada sisa | Docker 4 OS |
| Integrasi | Alur penuh apply, verify, apply ulang di VM nyata | `tests/integration/run_vm.sh`, manual |

Catatan: container Docker tidak punya systemd penuh, jadi `hostnamectl` dan `timedatectl` tidak bisa dites di sana. Itu sebabnya Step dites dengan FakeRunner dan di VM. Tes Docker hanya untuk instalasi dan perintah yang tidak butuh systemd.

## 11. CI (GitHub Actions: `.github/workflows/ci.yml`)

Trigger: `push` dan `pull_request`. `permissions: contents: read`. Semua action dipin ke versi mayor yang tetap.

| Job | Isi |
|---|---|
| `lint` | `ruff check`, `ruff format --check`, `mypy --strict src`, `shellcheck install.sh uninstall.sh packaging/hostkeeper.launcher` |
| `unit` | Matriks Python 3.10, 3.11, 3.12, 3.13. Pasang `pytest`, `pyyaml`. Jalankan `pytest tests/unit tests/golden` dengan cakupan, ambang minimal 85% pada `engine/` dan `steps/` |
| `install` | Matriks container `debian:12`, `debian:13`, `ubuntu:22.04`, `ubuntu:24.04`. Di tiap container: pasang `sudo`, jalankan `./install.sh --no-systemd --yes` **dua kali**, `hostkeeper version` harus sukses, `hostkeeper plan -c tests/data/profile.example.yml` harus berjalan dan mencetak tabel (Step yang butuh systemd menggunakan mode lewati yang jelas, atau gunakan profil hanya berisi `packages`), `./uninstall.sh`, lalu pastikan `/usr/local/bin/hostkeeper` dan `/usr/local/lib/hostkeeper` tidak ada |
| `no-extra-deps` | Skrip yang memastikan import di `src/` hanya stdlib dan `yaml` |

CD (rilis: tag, GitHub Release, changelog) **tidak diotomatiskan**. Pemilik repo melakukannya manual dengan daftar periksa di `docs/RELEASING.md` (agen cukup membuat file daftar itu).

## 12. Lingkup v0.1 dan kriteria selesai

**Dikerjakan:** semua file di bagian 3, tiga Step (hostname, timezone, packages), perintah `version`, `plan`, `apply`, `verify`, stub perintah lain, `install.sh`, `uninstall.sh`, tes, CI, dokumen kerangka.

**Tidak dikerjakan (jangan):** user, SSH, sshd, firewall, unattended-upgrades, wizard, monitoring, rollback, `.deb`, unit systemd, edit `/etc/hosts`, dukungan multi-host, dukungan OS selain empat di atas.

**Selesai jika semua benar:**

1. `pytest` hijau di Python 3.10 sampai 3.13, cakupan >= 85% di `engine/` dan `steps/`.
2. `ruff`, `mypy --strict`, dan `shellcheck` bersih.
3. Tes idempotency lolos untuk semua Step.
4. Tes membuktikan `plan` tidak memanggil perintah mutating dan tidak menulis file.
5. `install.sh` dua kali berturut-turut dan `uninstall.sh` lolos di 4 container.
6. Output `plan`, `apply`, `verify`, dan pesan error sesuai bagian 8 (golden test).
7. Di VM Debian 12 (manual oleh pemilik): `apply` mengubah hostname, timezone, dan paket. `apply` kedua menghasilkan 0 perubahan. `verify` exit 0. Mengubah hostname manual lalu `verify` exit 3.
8. Tidak ada dependensi runtime selain `python3-yaml`.

## 13. Pandangan ke depan (supaya kontrak tidak rusak)

Kontrak yang dibekukan sejak v0.1: antarmuka `Step`, `Runner`, `FileOps`; skema profil `version: 1` (hanya bertambah field opsional); format audit JSON Lines; tata letak file di bagian 6.4; exit code di bagian 7.

| Versi | Menambah | Memakai fondasi ini lewat |
|---|---|---|
| v0.2 | Step user, sshkeys, sshd, perintah `rollback`, timer rollback independen (`systemd-run`) | Journal dan backup dari v0.1, `requires` antar Step |
| v0.3 | Step firewall (tabel nft `inet hostkeeper`) dan unattended-upgrades, wizard | Wizard menulis profil dengan validator `profile.py` yang sama |
| v0.4 | Monitoring, `status`, webhook, kesesuaian profil | Collector profil memanggil `check()` semua Step dengan `ReadOnlyRunner` dan `ReadOnlyFileOps`, memakai lock yang sama |
| v0.5 | Dokumentasi final, rilis, `.deb` opsional | Struktur file yang sama |

## 14. Catatan keputusan dari diskusi

- Instalasi lewat `install.sh` hasil clone. Tidak menyarankan `curl | bash`.
- Format konfigurasi YAML dengan `python3-yaml` agar Ubuntu 22.04 (Python 3.10) tetap didukung.
- Penyesuaian dari rancangan awal: hostname dan timezone dipisah menjadi dua Step (tiga Step di v0.1); unit systemd baru dipasang saat monitoring ada (v0.4); `rollback` penuh di v0.2, tetapi journal dan backup sudah ditulis sejak v0.1.
- Paket `ufw` tidak dimasukkan ke contoh paket dasar karena firewall nanti memakai nftables milik sendiri dan menolak jika ufw/firewalld aktif.
