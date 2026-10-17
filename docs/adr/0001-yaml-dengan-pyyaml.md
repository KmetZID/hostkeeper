# ADR 0001: Penggunaan Format YAML dengan python3-yaml (PyYAML)

## Status
Diterima (*Accepted*)

## Konteks
`hostkeeper` memerlukan format konfigurasi deklaratif yang mudah dibaca, ditulis, dan dikelola oleh administrator sistem secara manual, serta dapat diparsing dengan cepat di Python. Format alternatif yang dipertimbangkan adalah JSON, TOML, dan INI.

## Keputusan
Memilih format YAML (`version: 1`) dan menggunakan pustaka standar distribusi `python3-yaml` (PyYAML).

## Konsekuensi
- **Positif**:
  - Format sangat ramah manusia (*human-readable*) dan mendukung komentar deskriptif di dalam file konfigurasi.
  - Paket `python3-yaml` tersedia secara resmi di repositori dasar (*main repository*) Debian dan Ubuntu tanpa perlu kompilasi dependensi C eksternal.
  - Struktur hierarkis YAML sangat cocok memetakan konfigurasi bertingkat seperti `ssh` dan `firewall.allow`.
- **Negatif / Mitigasi**:
  - Parsing YAML dapat rentan terhadap eksekusi objek Python sembarangan jika menggunakan `yaml.load()`.
  - **Mitigasi**: `hostkeeper` secara ketat hanya menggunakan `yaml.safe_load()`.
