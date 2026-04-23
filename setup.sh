#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# my-fi setup script
# One command to go from zero to running.
# Works on macOS and Linux. Windows users: use WSL.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { printf "${GREEN}  ✓${RESET} %s\n" "$1"; }
fail() { printf "${RED}  ✗${RESET} %s\n" "$1"; }
warn() { printf "${YELLOW}  ⚠${RESET} %s\n" "$1"; }
info() { printf "${CYAN}  →${RESET} %s\n" "$1"; }

DATA_HOME="$HOME/.my-fi"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Banner ────────────────────────────────────────────────────
echo ""
printf "${BOLD}  my-fi — setup${RESET}\n"
echo "  ─────────────────────────────────────────"
echo ""

# ── 1. Check Python ──────────────────────────────────────────
info "Checking Python..."
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 12 ]; then
        ok "Python $PY_VERSION found"
    else
        fail "Python $PY_VERSION found, but 3.12+ is required"
        echo ""
        echo "  Download Python 3.12+:"
        echo "    macOS:  brew install python@3.12"
        echo "    Linux:  sudo apt install python3.12  (or your package manager)"
        echo "    All:    https://www.python.org/downloads/"
        echo ""
        exit 1
    fi
else
    fail "Python not found"
    echo ""
    echo "  Install Python 3.12+:"
    echo "    macOS:  brew install python@3.12"
    echo "    Linux:  sudo apt install python3.12  (or your package manager)"
    echo "    All:    https://www.python.org/downloads/"
    echo ""
    exit 1
fi

# ── 2. Check / Install uv ───────────────────────────────────
info "Checking uv..."
if command -v uv &>/dev/null; then
    UV_VERSION=$(uv --version 2>/dev/null | head -1)
    ok "$UV_VERSION found"
else
    warn "uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the env so uv is available in this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if command -v uv &>/dev/null; then
        UV_VERSION=$(uv --version 2>/dev/null | head -1)
        ok "$UV_VERSION installed"
    else
        fail "uv installation failed"
        echo ""
        echo "  Try installing manually:"
        echo "    macOS:  brew install uv"
        echo "    All:    https://docs.astral.sh/uv/getting-started/installation/"
        echo ""
        exit 1
    fi
fi

# ── 3. Install dependencies ─────────────────────────────────
info "Installing dependencies..."
cd "$SCRIPT_DIR"
uv sync --dev
ok "Dependencies installed"

# ── 4. Environment file ─────────────────────────────────────
info "Checking .env..."
if [ -f "$SCRIPT_DIR/.env" ]; then
    ok ".env already exists (not overwriting)"
else
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    ok ".env created from .env.example"
fi

# ── 5. Create data directories ──────────────────────────────
info "Setting up data directory at $DATA_HOME..."
mkdir -p "$DATA_HOME/data/uploads"
mkdir -p "$DATA_HOME/data/quarantine"
mkdir -p "$DATA_HOME/storage/logs"
mkdir -p "$DATA_HOME/storage/upload-staging"
ok "Data directories ready"

# ── 6. Copy sample CSVs ─────────────────────────────────────
info "Copying sample CSV files..."
if [ -d "$SCRIPT_DIR/samples" ]; then
    mkdir -p "$DATA_HOME/samples"
    cp -n "$SCRIPT_DIR/samples/"*.csv "$DATA_HOME/samples/" 2>/dev/null || true
    ok "Sample CSVs available at $DATA_HOME/samples/"
else
    warn "No samples/ directory found — skipping"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "  ─────────────────────────────────────────"
printf "${GREEN}${BOLD}  ✓ Setup complete!${RESET}\n"
echo ""
echo "  Next steps:"
echo ""
printf "    ${BOLD}Start the app:${RESET}        make run\n"
printf "    ${BOLD}Open in browser:${RESET}      http://127.0.0.1:8000/ui\n"
printf "    ${BOLD}Try a sample upload:${RESET}  Upload a CSV from $DATA_HOME/samples/\n"
printf "    ${BOLD}Run tests:${RESET}            make test\n"
printf "    ${BOLD}See all commands:${RESET}     make help\n"
echo ""
printf "  Your data lives at: ${CYAN}$DATA_HOME${RESET}\n"
printf "  It never leaves your machine.\n"
echo ""
