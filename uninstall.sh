#!/usr/bin/env bash
# uninstall.sh: Pencopot hostkeeper (SPEC bagian 9)
set -Eeuo pipefail

PREFIX="/usr/local"
DRY_RUN=0
PURGE=0
# shellcheck disable=SC2034
YES_MODE=0


# Parse argumen
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --prefix membutuhkan direktori" >&2
                exit 2
            fi
            PREFIX="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --purge)
            PURGE=1
            shift
            ;;
        --yes|-y)
            YES_MODE=1
            shift
            ;;
        *)
            echo "ERROR: Opsi tidak dikenal: $1" >&2
            exit 2
            ;;
    esac
done
_=$YES_MODE


run() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# Pastikan dijalankan sebagai root (kecuali dry-run jika ingin simulasi)
if [[ "$(id -u)" -ne 0 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] exec sudo -- $0 $*"
    else
        exec sudo -- "$0" "$@"
    fi
fi

LIB_DIR="$PREFIX/lib/hostkeeper"
BIN_DIR="$PREFIX/bin"
LAUNCHER="$BIN_DIR/hostkeeper"
MANIFEST="$LIB_DIR/MANIFEST"

# Cek apakah terpasang (idempotency)
if [[ ! -d "$LIB_DIR" && ! -f "$LAUNCHER" ]]; then
    echo "hostkeeper tidak terpasang di $PREFIX."
    exit 0
fi

echo "Peringatan: uninstall tidak membalik perubahan konfigurasi sistem yang pernah diterapkan."

# Matikan timer monitoring bila aktif
if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    run systemctl disable --now hostkeeper-watch.timer >/dev/null 2>&1 || true
    run systemctl stop hostkeeper-watch.service >/dev/null 2>&1 || true
fi

# Hapus file berdasarkan MANIFEST jika ada
if [[ -f "$MANIFEST" ]]; then
    while IFS= read -r item || [[ -n "$item" ]]; do
        item_trimmed=$(echo "$item" | xargs)
        if [[ -n "$item_trimmed" && -e "$item_trimmed" ]]; then
            run rm -rf "$item_trimmed"
        fi
    done < "$MANIFEST"
fi

# Pastikan direktori library dan launcher bersih
run rm -rf "$LIB_DIR"
run rm -f "$LAUNCHER"

# Jika --purge, hapus config dan data
if [[ "$PURGE" -eq 1 ]]; then
    run rm -rf /etc/hostkeeper /var/lib/hostkeeper /var/log/hostkeeper
fi

echo "hostkeeper berhasil dicopot dari $PREFIX."
