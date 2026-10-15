#!/usr/bin/env bash
set -euo pipefail

if [ -z "${TARGET:-}" ]; then
    echo "ERROR: variabel lingkungan TARGET belum diatur." >&2
    echo "Contoh: TARGET=user@hk-target:~/hostkeeper $0" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -avz --delete \
    --exclude=".venv" \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude="*.egg-info" \
    --exclude=".pytest_cache" \
    --exclude=".mypy_cache" \
    --exclude=".ruff_cache" \
    "$REPO_ROOT/" "$TARGET"
