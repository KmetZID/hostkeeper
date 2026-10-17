#!/usr/bin/env bash
# install.sh: Pemasang hostkeeper
set -Eeuo pipefail

PREFIX="/usr/local"
DRY_RUN=0
NO_DEPS=0
LINK_MODE=0
NO_SYSTEMD=0
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
        --no-deps)
            NO_DEPS=1
            shift
            ;;
        --link)
            LINK_MODE=1
            shift
            ;;
        --no-systemd)
            NO_SYSTEMD=1
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

# 1. Pastikan dijalankan sebagai root (kecuali dry-run jika ingin simulasi)
if [[ "$(id -u)" -ne 0 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] exec sudo -- $0 $*"
    else
        exec sudo -- "$0" "$@"
    fi
fi

# Lokasi sumber
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. Pre-flight checks
if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    OS_KEY="${ID:-}:${VERSION_ID:-}"
    case "$OS_KEY" in
        debian:12|debian:13|ubuntu:22.04|ubuntu:24.04)
            ;;
        *)
            echo "ERROR: OS '$OS_KEY' tidak didukung. Didukung: debian:12, debian:13, ubuntu:22.04, ubuntu:24.04" >&2
            exit 5
            ;;
    esac
else
    echo "ERROR: /etc/os-release tidak ditemukan." >&2
    exit 5
fi

if [[ "$NO_SYSTEMD" -eq 0 && ! -d /run/systemd/system ]]; then
    echo "ERROR: systemd tidak aktif (/run/systemd/system tidak ada). Gunakan --no-systemd di container/CI." >&2
    exit 5
fi

# 3. Dependensi sistem (python3 dan python3-yaml)
if [[ "$NO_DEPS" -eq 0 ]]; then
    NEED_APT=0
    if ! command -v python3 >/dev/null 2>&1; then
        NEED_APT=1
    elif ! python3 -c "import yaml" >/dev/null 2>&1; then
        NEED_APT=1
    fi

    if [[ "$NEED_APT" -eq 1 ]]; then
        run apt-get update -qq
        run apt-get install -y --no-install-recommends python3 python3-yaml
    fi
fi

# Validasi versi Python >= 3.10
if command -v python3 >/dev/null 2>&1; then
    PY_VER_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)")
    if [[ "$PY_VER_OK" -ne 1 ]]; then
        echo "ERROR: Python 3.10+ dibutuhkan." >&2
        exit 5
    fi
fi

# 4. Salin / symlink kode
LIB_DIR="$PREFIX/lib/hostkeeper"
BIN_DIR="$PREFIX/bin"

run mkdir -p "$LIB_DIR" "$BIN_DIR"

if [[ "$LINK_MODE" -eq 1 ]]; then
    run ln -sfn "$SCRIPT_DIR/src/hostkeeper" "$LIB_DIR/hostkeeper"
else
    run rm -rf "$LIB_DIR/hostkeeper"
    run cp -r "$SCRIPT_DIR/src/hostkeeper" "$LIB_DIR/hostkeeper"
fi

# 5. Pasang launcher
LAUNCHER_PATH="$BIN_DIR/hostkeeper"
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] pasang launcher di $LAUNCHER_PATH"
else
    cat <<EOF > "$LAUNCHER_PATH"
#!/usr/bin/env bash
set -eu
PYTHONPATH="$LIB_DIR" exec python3 -m hostkeeper "\$@"
EOF
    chmod 755 "$LAUNCHER_PATH"
fi

# 6. Direktori data & log
run mkdir -p /etc/hostkeeper /var/lib/hostkeeper /var/log/hostkeeper
run chmod 700 /etc/hostkeeper /var/lib/hostkeeper
run chmod 750 /var/log/hostkeeper

# 7. Unit systemd
if [[ -d "$SCRIPT_DIR/packaging/systemd" ]]; then
    mapfile -t UNITS < <(find "$SCRIPT_DIR/packaging/systemd" -maxdepth 1 -type f \( -name "*.service" -o -name "*.timer" \))
    if [[ "${#UNITS[@]}" -gt 0 ]]; then
        run cp "${UNITS[@]}" /etc/systemd/system/
        if [[ "$NO_SYSTEMD" -eq 0 && -d /run/systemd/system ]]; then
            run systemctl daemon-reload
        fi
    fi
fi

# 8. Tulis VERSION dan MANIFEST
VERSION_VAL="0.1.0"
if [[ -f "$SCRIPT_DIR/src/hostkeeper/__init__.py" ]]; then
    PARSED_VER=$(grep -E '^__version__' "$SCRIPT_DIR/src/hostkeeper/__init__.py" | cut -d'"' -f2 || true)
    if [[ -n "$PARSED_VER" ]]; then
        VERSION_VAL="$PARSED_VER"
    fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] tulis $LIB_DIR/VERSION ($VERSION_VAL)"
    echo "[dry-run] tulis $LIB_DIR/MANIFEST"
else
    echo "$VERSION_VAL" > "$LIB_DIR/VERSION"
    cat <<EOF > "$LIB_DIR/MANIFEST"
$LAUNCHER_PATH
$LIB_DIR/VERSION
$LIB_DIR/MANIFEST
$LIB_DIR/hostkeeper
EOF
    if [[ -d "$SCRIPT_DIR/packaging/systemd" && "${#UNITS[@]}" -gt 0 ]]; then
        for u in "${UNITS[@]}"; do
            echo "/etc/systemd/system/$(basename "$u")" >> "$LIB_DIR/MANIFEST"
        done
    fi
fi

# 9. Smoke test
if [[ "$DRY_RUN" -eq 0 ]]; then
    if ! "$LAUNCHER_PATH" version >/dev/null 2>&1; then
        echo "ERROR: Smoke test hostkeeper version gagal." >&2
        exit 1
    fi
fi

# 10. Cetak ringkasan
PROFILE_NOTE="(belum ada profil)"
if [[ -f /etc/hostkeeper/profile.yml ]]; then
    PROFILE_NOTE="(profil ada)"
fi

cat <<EOF
hostkeeper $VERSION_VAL terpasang.
  Kode      : $LIB_DIR
  Perintah  : $BIN_DIR/hostkeeper
  Config    : /etc/hostkeeper $PROFILE_NOTE
Server TIDAK diubah. Langkah berikutnya:
  1. Buat /etc/hostkeeper/profile.yml (lihat docs/example-profile.yml)
  2. sudo hostkeeper plan
  3. sudo hostkeeper apply
EOF
