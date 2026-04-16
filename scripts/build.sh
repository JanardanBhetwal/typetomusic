#!/bin/bash
# =============================================================================
#  TypeToMusic – Build & Package Script
#  Usage:
#    ./scripts/build.sh [run|exe|deb|all]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_TARGET="${1:-help}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Helpers ──────────────────────────────────────────────────────────────────

check_python() {
    python3 --version >/dev/null 2>&1 || error "Python 3 not found. Install: sudo apt install python3"
    PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
    [ "$PY_VER" -ge 9 ] || error "Python 3.9+ required (found 3.$PY_VER)"
    info "Python OK: $(python3 --version)"
}

check_system_deps() {
    info "Checking system dependencies..."
    local missing=()
    for pkg in libfluidsynth-dev fluid-soundfont-gm; do
        dpkg -l "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        warn "Missing system packages: ${missing[*]}"
        info "Installing missing packages..."
        sudo apt-get install -y "${missing[@]}" || error "apt install failed"
    fi
    info "System deps OK."
}

install_python_deps() {
    info "Installing Python dependencies..."
    cd "$PROJECT_DIR"
    pip3 install --upgrade pip --quiet
    pip3 install -r requirements.txt --quiet
    info "Python deps installed."
}

# ── Targets ──────────────────────────────────────────────────────────────────

run_from_source() {
    info "Running TypeToMusic from source..."
    check_python
    check_system_deps
    install_python_deps
    cd "$PROJECT_DIR"
    python3 main.py
}

build_exe() {
    info "Building standalone executable with PyInstaller..."
    check_python
    check_system_deps
    install_python_deps
    pip3 install pyinstaller --quiet
    cd "$PROJECT_DIR"
    pyinstaller typetomusic.spec --clean --noconfirm
    info "Executable built: dist/TypeToMusic/typetomusic"
    info "Run with: ./dist/TypeToMusic/typetomusic"
}

build_deb() {
    info "Building .deb package..."

    DEB_ROOT="$PROJECT_DIR/packaging/deb"
    APP_DIR="$DEB_ROOT/usr/share/typetomusic"
    CONTROL_FILE="$DEB_ROOT/DEBIAN/control"
    PKG_VERSION=$(grep -E '^__version__\s*=\s*"' "$PROJECT_DIR/typetomusic/__init__.py" | sed -E 's/^__version__\s*=\s*"([^"]+)"/\1/')
    [ -n "$PKG_VERSION" ] || error "Could not determine package version from typetomusic/__init__.py"
    ARCH=$(dpkg --print-architecture)

    # Clean previous build
    rm -rf "$APP_DIR"
    mkdir -p "$APP_DIR"

    # Copy application source
    cp "$PROJECT_DIR/main.py"          "$APP_DIR/"
    cp -r "$PROJECT_DIR/typetomusic/"  "$APP_DIR/typetomusic/"
    cp "$PROJECT_DIR/requirements.txt" "$APP_DIR/"

    # Fix permissions
    chmod 755 "$DEB_ROOT/usr/bin/typetomusic"
    chmod 755 "$DEB_ROOT/DEBIAN/postinst"

    # Keep control metadata in sync
    sed -i "s/^Version:.*/Version: $PKG_VERSION/" "$CONTROL_FILE"
    sed -i "s/^Architecture:.*/Architecture: $ARCH/" "$CONTROL_FILE"

    # Set package size
    SIZE=$(du -sk "$DEB_ROOT" | awk '{print $1}')
    sed -i "s/^Installed-Size:.*/Installed-Size: $SIZE/" \
        "$CONTROL_FILE" 2>/dev/null || true

    # Build the .deb
    DEB_FILE="$PROJECT_DIR/dist/typetomusic_${PKG_VERSION}_${ARCH}.deb"
    mkdir -p "$PROJECT_DIR/dist"
    dpkg-deb --build "$DEB_ROOT" "$DEB_FILE" || error "dpkg-deb failed"

    info "Package built: $DEB_FILE"
    info "Install with: sudo dpkg -i $DEB_FILE"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "$BUILD_TARGET" in
    run)   run_from_source ;;
    exe)   build_exe ;;
    deb)   build_deb ;;
    all)   build_exe; build_deb ;;
    help|*)
        echo ""
        echo "  Usage: $0 [run|exe|deb|all]"
        echo ""
        echo "  run   – Install deps and run from source"
        echo "  exe   – Build standalone executable (PyInstaller)"
        echo "  deb   – Build .deb package"
        echo "  all   – Build both exe and deb"
        echo ""
        ;;
esac
