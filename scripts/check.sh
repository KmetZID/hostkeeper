#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Memeriksa integritas blueprint protected..."
sha256sum -c docs/blueprint/PROTECTED.sha256

echo "==> Menjalankan ruff check..."
ruff check

echo "==> Menjalankan ruff format --check..."
ruff format --check

echo "==> Menjalankan mypy --strict src..."
mypy --strict src

echo "==> Menjalankan pytest -q..."
pytest -q

echo "==> Menjalankan shellcheck..."
if command -v shellcheck >/dev/null 2>&1; then
    mapfile -t sh_files < <(find . -name "*.sh" -not -path "*/.*/*")
    if [ "${#sh_files[@]}" -gt 0 ]; then
        shellcheck "${sh_files[@]}"
    fi
else
    echo "Peringatan: shellcheck tidak terpasang, dilewati."
fi

echo "==> Memindai rahasia sederhana..."
SECRET_PATTERN='(BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9\-]{20}|xox[baprs]-[A-Za-z0-9\-]+|AKIA[0-9A-Z]{16})'

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    matches=$(git grep -I -E "$SECRET_PATTERN" -- ":(exclude)scripts/check.sh" || true)
else
    matches=$(grep -r -I -E "$SECRET_PATTERN" --exclude-dir=".git" --exclude-dir=".venv" --exclude="check.sh" . || true)
fi

if [ -n "$matches" ]; then
    echo "ERROR: Ditemukan pola rahasia yang dicurigai:" >&2
    echo "$matches" >&2
    exit 1
fi

echo "Semua pemeriksaan check.sh berhasil!"
