#!/usr/bin/env bash
# One-command installer for mc-shot-sync (Linux / macOS).
#
#   curl -fsSL https://raw.githubusercontent.com/codingmachineedge/mc-shot-sync/main/install.sh | bash
#
# Or, from a local checkout:   ./install.sh
#
# Env overrides:
#   MCSS_REPO   git URL to clone (default: this project's GitHub repo)
#   MCSS_HOME   install dir       (default: ~/.mc-shot-sync)
#   MCSS_NOINIT set to 1 to skip the interactive `init` step
set -euo pipefail

REPO_URL="${MCSS_REPO:-https://github.com/codingmachineedge/mc-shot-sync.git}"
HOME_DIR="${MCSS_HOME:-$HOME/.mc-shot-sync}"
SRC_DIR=""

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!  \033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx \033[0m %s\n' "$*" >&2; exit 1; }

# --- Locate source: local checkout or clone ---------------------------------
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SOURCE" && -f "$(dirname "$SCRIPT_SOURCE")/pyproject.toml" ]]; then
  SRC_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
  say "Installing from local checkout: $SRC_DIR"
else
  command -v git >/dev/null 2>&1 || die "git is required. Install git and retry."
  SRC_DIR="$HOME_DIR/src"
  if [[ -d "$SRC_DIR/.git" ]]; then
    say "Updating existing checkout in $SRC_DIR"
    git -C "$SRC_DIR" pull --ff-only || warn "git pull failed; using existing copy"
  else
    say "Cloning $REPO_URL -> $SRC_DIR"
    mkdir -p "$HOME_DIR"
    git clone --depth 1 "$REPO_URL" "$SRC_DIR"
  fi
fi

# --- Python venv ------------------------------------------------------------
PY="$(command -v python3 || command -v python || true)"
[[ -n "$PY" ]] || die "Python 3.9+ is required but was not found."

VENV="$HOME_DIR/venv"
say "Creating virtualenv: $VENV"
mkdir -p "$HOME_DIR"
"$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip >/dev/null
say "Installing mc-shot-sync and dependencies"
python -m pip install "$SRC_DIR"

# --- Linux clipboard tooling check ------------------------------------------
if [[ "$(uname -s)" == "Linux" ]]; then
  if ! command -v wl-copy >/dev/null 2>&1 && ! command -v xclip >/dev/null 2>&1; then
    warn "No clipboard tool found. Install one for the clipboard feature:"
    warn "  Wayland:  sudo apt install wl-clipboard   (or your distro's pkg)"
    warn "  X11:      sudo apt install xclip"
  fi
fi

# --- Launcher shim on PATH --------------------------------------------------
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/mc-shot-sync" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/mc-shot-sync" "\$@"
EOF
chmod +x "$BIN_DIR/mc-shot-sync"
say "Installed launcher: $BIN_DIR/mc-shot-sync"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "Add $BIN_DIR to your PATH (e.g. in ~/.bashrc): export PATH=\"\$HOME/.local/bin:\$PATH\"";;
esac

# --- First-run setup --------------------------------------------------------
if [[ "${MCSS_NOINIT:-0}" != "1" ]]; then
  say "Running setup (detect screenshots, create the public GitHub repo)..."
  "$VENV/bin/mc-shot-sync" init || warn "init did not finish — re-run 'mc-shot-sync init' after fixing the issue above."
fi

cat <<EOF

$(say "Done!")
Start the tray GUI:     mc-shot-sync tray
Or run headless:        mc-shot-sync watch
Check configuration:    mc-shot-sync status
EOF
