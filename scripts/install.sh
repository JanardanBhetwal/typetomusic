#!/bin/bash
# =============================================================================
#  TypeToMusic – Quick Install Script
#  One-command setup for Ubuntu / Linux Mint users.
#  Usage: bash scripts/install.sh
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}►${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║       TypeToMusic Installer      ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# ── Check OS ──────────────────────────────────────────────────────────────────
if ! command -v apt-get &>/dev/null; then
    error "This installer requires a Debian/Ubuntu-based system with apt."
fi

# ── System packages ───────────────────────────────────────────────────────────
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    python3-pyqt5 \
    --no-install-recommends
ok "System packages installed."

# ── Virtual environment ────────────────────────────────────────────────────────
VENV_DIR="$PROJECT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" --system-site-packages
    ok "Virtual environment created at $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

info "Installing Python packages..."
pip install --upgrade pip --quiet
pip install -e ".[all]" --quiet || pip install -e . --quiet
ok "Python packages installed."

# ── Desktop shortcut ─────────────────────────────────────────────────────────
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/typetomusic.desktop" << EOF
[Desktop Entry]
Name=TypeToMusic
Comment=Turn your keyboard into a musical instrument
Exec=bash -c "source $VENV_DIR/bin/activate && python3 $PROJECT_DIR/main.py"
Terminal=false
Type=Application
Categories=AudioVideo;Music;
EOF
chmod +x "$DESKTOP_DIR/typetomusic.desktop"
ok "Desktop shortcut created."

# ── Launch wrapper ────────────────────────────────────────────────────────────
LAUNCHER="$PROJECT_DIR/run-typetomusic"
cat > "$LAUNCHER" << EOF
#!/bin/bash
source "$VENV_DIR/bin/activate"
exec python3 "$PROJECT_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"
ok "Launcher created: $LAUNCHER"

# ── SoundFont check ────────────────────────────────────────────────────────────
SF_FOUND=false
for sf in /usr/share/sounds/sf2/FluidR3_GM.sf2 /usr/share/soundfonts/FluidR3_GM.sf2 /usr/share/sounds/sf2/TimGM6mb.sf2; do
    if [ -f "$sf" ]; then
        ok "SoundFont found: $sf"
        SF_FOUND=true
        break
    fi
done
if [ "$SF_FOUND" = false ]; then
    warn "SoundFont not found. You can select one manually in the app."
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  Installation complete!              ║"
echo "  ║                                      ║"
echo "  ║  Run with:  ./typetomusic            ║"
echo "  ║  Or launch from your app menu.       ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
