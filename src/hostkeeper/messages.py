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
ADMIN_USER_INVALID = (
    "Nama admin_user '{user}' tidak valid "
    "(huruf kecil, angka, _, -, maksimal 32 karakter, tidak boleh root)"
)
SSH_KEYS_INVALID_TYPE = "ssh_authorized_keys harus berupa list/daftar"
SSH_KEY_INVALID = "Kunci SSH tidak valid: '{key}'"
SSH_CONFIG_INVALID_TYPE = "ssh harus berupa pemetaan YAML (dictionary)"
SSH_CONFIG_UNKNOWN_KEYS = "Kunci tidak dikenal pada konfigurasi ssh: {keys}"
SSH_PORT_INVALID = "Port SSH harus berupa integer antara 1 dan 65535"
SSH_PERMIT_ROOT_INVALID = (
    "permit_root_login tidak valid: '{val}' "
    "(pilihan: yes, no, prohibit-password, forced-commands-only)"
)
SSH_PASSWORD_AUTH_INVALID = "password_auth harus berupa boolean (true/false)"
FIREWALL_CONFIG_INVALID_TYPE = "firewall harus berupa pemetaan YAML (dictionary)"
FIREWALL_CONFIG_UNKNOWN_KEYS = "Kunci tidak dikenal pada konfigurasi firewall: {keys}"
FIREWALL_ALLOW_INVALID_TYPE = "firewall.allow harus berupa list/daftar"
FIREWALL_RULE_INVALID = (
    "Aturan firewall '{rule}' tidak valid "
    "(format: <port>/tcp atau <port>/udp, port 1-65535)"
)
UNATTENDED_UPGRADES_INVALID = "unattended_upgrades harus berupa boolean (true/false)"


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

# Rollback messages
ROLLBACK_CONFIRM_PROMPT = "\nLanjutkan rollback run {run_id}? [y/N] "
ROLLBACK_ABORT = "Rollback dibatalkan."
ROLLBACK_NO_RUNS = "Tidak ada run yang dapat di-rollback."
ROLLBACK_RUN_NOT_FOUND = "Run '{run_id}' tidak ditemukan di {dir}."
ROLLBACK_JOURNAL_INVALID = "Journal run '{run_id}' rusak atau tidak valid: {detail}"
ROLLBACK_STEP_UNDONE = " [~] {name:<10} dikembalikan"
ROLLBACK_STEP_CANNOT_UNDO = " [!] {name:<10} tidak dapat dibalik otomatis"
ROLLBACK_DONE = "Rollback selesai untuk run {run_id} ({undone} step dikembalikan)."
ROLLBACK_LIST_HEADER = "Daftar run yang tersimpan:"
ROLLBACK_LIST_EMPTY = "Tidak ada riwayat run yang tersimpan."
ROLLBACK_ERROR_NEEDS_ROOT = (
    "rollback membutuhkan root. Jalankan: sudo hostkeeper rollback"
)

# Safety timer messages
SAFETY_TIMER_STARTED = (
    " [!] Safety timer aktif ({seconds}s). "
    "Jangan tutup sesi ini, uji dari terminal kedua."
)
SAFETY_TIMER_STOPPED = " [~] Safety timer dibatalkan."
SAFETY_TIMER_PROMPT = (
    "Perubahan berisiko tinggi '{step}' berhasil diverifikasi. "
    "Batalkan timer otomatis? [Y/n] "
)
SAFETY_TIMER_FAILED = "Safety timer gagal: {detail}"

# Wizard messages
WIZARD_WELCOME = (
    "=== hostkeeper setup ===\n"
    "Wizard ini akan membuat profil konfigurasi server.\n"
    "Tekan Ctrl+C untuk membatalkan kapan saja.\n"
)
WIZARD_PROMPT_HOSTNAME = "Hostname server [{default}]: "
WIZARD_PROMPT_TIMEZONE = "Timezone [{default}]: "
WIZARD_PROMPT_PACKAGES = (
    "Paket tambahan (pisahkan dengan spasi, kosongkan untuk lewati) [{default}]: "
)
WIZARD_PROMPT_ADMIN_USER = "Nama admin user (kosongkan untuk lewati) [{default}]: "
WIZARD_PROMPT_SSH_KEY = (
    "Kunci publik SSH (tempel isi atau path .pub, kosongkan untuk selesai): "
)
WIZARD_PROMPT_SSH_HARDEN = (
    "Hardening SSH (PermitRootLogin=no, PasswordAuth=false)? [y/N]: "
)
WIZARD_PROMPT_SSH_PORT = "Port SSH [{default}]: "
WIZARD_PROMPT_FIREWALL_PORTS = (
    "Port firewall yang diizinkan "
    "(format: 80/tcp 443/tcp, kosongkan untuk lewati) [{default}]: "
)
WIZARD_PROMPT_UPDATES = "Aktifkan pembaruan otomatis (unattended-upgrades)? [Y/n]: "
WIZARD_PROMPT_OVERWRITE = (
    "File profil {path} sudah ada. Timpa? (backup dibuat otomatis) [y/N]: "
)
WIZARD_PROMPT_RUN_PLAN = "Jalankan `hostkeeper plan` sekarang? [Y/n]: "
WIZARD_PROFILE_WRITTEN = "Profil ditulis ke {path}"
WIZARD_BACKUP_CREATED = "Backup profil lama: {path}"
WIZARD_INVALID_INPUT = "Input tidak valid: {detail}. Coba lagi."
WIZARD_CANCELLED = "Setup dibatalkan."
WIZARD_SKIP_COMPLIANT = "  [~] {field} sudah sesuai, dilewati."

# Watch & Monitoring messages
WATCH_CYCLE_SKIPPED = "Siklus watch dilewati: instance hostkeeper lain sedang berjalan."
WATCH_TIMER_ENABLED = "hostkeeper-watch.timer diaktifkan."
WATCH_TIMER_DISABLED = "hostkeeper-watch.timer dinonaktifkan."
WATCH_NO_WEBHOOK_URL = "URL webhook belum dikonfigurasi di {path}"
WATCH_TEST_SUCCESS = "Notifikasi uji coba berhasil dikirim ke {url}."
WATCH_TEST_FAILED = "Gagal mengirim notifikasi uji coba ke {url}."

# Status messages
STATUS_HEADER = "hostkeeper {version} status"
STATUS_SUMMARY_OK = "Ringkasan: Semua metrik dan profil dalam kondisi OK."
STATUS_SUMMARY_ISSUES = (
    "Ringkasan: Ditemukan {warn} peringatan, {crit} kritis, {drift} drift profil."
)
ERR_FEATURE_UNAVAILABLE = "Perintah ini tidak tersedia."
