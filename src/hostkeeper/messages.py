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
