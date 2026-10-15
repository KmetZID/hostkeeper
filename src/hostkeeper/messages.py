"""Pesan untuk pengguna dalam Bahasa Indonesia."""

from __future__ import annotations

# Profile error messages
PROFILE_FILE_NOT_FOUND = "File profil tidak ditemukan: {path}"
PROFILE_INVALID_YAML = "Format YAML profil tidak valid: {detail}"
PROFILE_NOT_A_MAPPING = "Profil harus berupa pemetaan YAML (dictionary)"
PROFILE_INVALID_VERSION = "Versi profil harus 1 (ditemukan: {version})"
PROFILE_UNKNOWN_KEYS = "Kunci tidak dikenal pada profil: {keys}"
HOSTNAME_INVALID = (
    "Hostname '{hostname}' tidak sah "
    "(RFC 1123: huruf kecil a-z, angka 0-9, '-', "
    "1-63 karakter per label, maksimal 253 karakter)"
)
TIMEZONE_INVALID = (
    "Timezone '{timezone}' tidak valid "
    "(harus ada di {zoneinfo_dir} dan tidak boleh mengandung '..')"
)
PACKAGES_INVALID_TYPE = "Daftar paket harus berupa list/daftar"
PACKAGES_TOO_MANY = "Jumlah paket ({count}) melebihi batas maksimal 100 paket"
PACKAGE_INVALID_NAME = (
    "Nama paket '{package}' tidak valid (harus sesuai regex ^[a-z0-9][a-z0-9+.-]*$)"
)

# Step status & results
STEP_COMPLIANT = "sudah sesuai"
STEP_CHANGE_SET = "{before} -> {after}"
HOSTNAME_WARN_GETENT = "getent hosts gagal untuk '{hostname}', sudo mungkin mengeluh"
HOSTNAME_WARN_CLOUD_INIT = (
    "/etc/cloud/ terdeteksi dan preserve_hostname tidak aktif, "
    "cloud-init bisa menimpa hostname saat reboot"
)

# Planner & dependency errors
DEPENDENCY_CYCLE = "Siklus dependensi terdeteksi antar Step: {cycle}"
MISSING_DEPENDENCY = "Step '{step}' memerlukan Step '{dep}' yang tidak terdaftar"

# Plan output
PLAN_SUMMARY = (
    "Ringkasan: {changes} perubahan, {ok} sudah sesuai, {high_risk} berisiko tinggi."
)
PLAN_SUMMARY_ALL_OK = "Ringkasan: 0 perubahan. Server sudah sesuai profil."
PLAN_FOOTER = (
    "Mode plan: tidak ada yang diubah. "
    "Jalankan `sudo hostkeeper apply` untuk menerapkan."
)

# Packages step messages
PACKAGE_NOT_AVAILABLE = (
    "Paket '{package}' tidak tersedia di apt "
    "(Candidate: none). Mungkin perlu `apt-get update` terlebih dahulu."
)
APT_UPDATE_FAILED = "apt-get update gagal: {stderr}"
APT_INSTALL_FAILED = "apt-get install gagal (exit {returncode}): {stderr}"
PACKAGES_CANNOT_UNDO = "packages tidak dapat dibalik otomatis."

# Executor messages
APPLY_HEADER = "hostkeeper {version} apply (run {run_id})"
APPLY_CONFIRM_PROMPT = "\nLanjutkan menerapkan {changes} perubahan? [y/N] "
APPLY_STEP_OK = " {sym} {name:<10} {desc} OK (verify lolos)"
APPLY_STEP_FAIL = " {sym} {name:<10} {desc}"
APPLY_STEP_SKIP = " {sym} (tidak ada Step tersisa)"
APPLY_DONE = (
    "Selesai: {applied} diterapkan, {failed} gagal. "
    "Jalankan `hostkeeper verify` untuk memastikan."
)
APPLY_JOURNAL = "Journal: {path}"
APPLY_FAIL_SUMMARY = "Kegagalan: Step {step}. Membalik Step yang reversible: {undone}."
APPLY_ABORT = "Apply dibatalkan."
APPLY_DRY_RUN = "[dry-run] {cmd}"

# Lock messages
LOCK_CONFLICT = "hostkeeper lain sedang berjalan (lock /run/hostkeeper.lock)."

# CLI error messages
ERROR_APPLY_NEEDS_ROOT = "apply membutuhkan root. Jalankan: sudo hostkeeper apply"
ERROR_PROFILE_INVALID = "profil tidak valid: {detail}"
ERROR_UNEXPECTED = "Kesalahan tidak terduga: {detail}"
ERROR_UNSUPPORTED_ENV = "Lingkungan tidak didukung: {detail}"

# CLI subcommand stubs
STUB_ROLLBACK = "Belum tersedia (direncanakan v0.2)"
STUB_SETUP = "Belum tersedia (direncanakan v0.2)"
STUB_WATCH = "Belum tersedia (direncanakan v0.2)"
STUB_STATUS = "Belum tersedia (direncanakan v0.3)"

# Version output
VERSION_OS = "OS      : {os_name}  [{support}]"
VERSION_PYTHON = "Python  : {python_version}"
VERSION_SYSTEMD = "systemd : {status}"
VERSION_PROFILE = "Profil  : {path} ({exists})"
VERSION_SUPPORTED = "didukung"
VERSION_UNSUPPORTED = "tidak didukung"
VERSION_SYSTEMD_ACTIVE = "aktif"
VERSION_SYSTEMD_INACTIVE = "tidak aktif"
PROFILE_EXISTS = "ada"
PROFILE_NOT_FOUND = "tidak ada"

# Plan header
PLAN_HEADER = "hostkeeper {version} plan"
PLAN_PROFILE_LINE = "Profil: {path} (version {version})"
PLAN_HOST_LINE = "Host  : {hostname}"
PLAN_TABLE_HEADER = (
    " STATUS  STEP       PERUBAHAN                                   RISIKO"
)

# Apply step descriptions
STEP_DESC_SET = "{before} -> {after}"
STEP_DESC_INSTALL = "pasang: {pkgs}"
STEP_DESC_ALREADY = "{current} (sudah sesuai)"

# Verify output
VERIFY_ALL_OK = "Semua Step sesuai profil."
VERIFY_DRIFT = (
    "{n} Step menyimpang dari profil. Jalankan `hostkeeper plan` untuk detail."
)
VERIFY_EXPECT = "diharapkan {expected}, sekarang {current}"
