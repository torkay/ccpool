#!/usr/bin/env bash
# install.sh — curl-bash one-liner for ccpool.
#
#   curl -fsSL https://raw.githubusercontent.com/torkay/ccpool/main/install/install.sh | bash
#
# Idempotent. Re-running picks up where the last attempt stopped.
# Per plan §10. POSIX-shell-friendly enough that bash 3.2 (macOS default)
# works without modern bash features.

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11
CAAM_INSTALL_HINT='go install github.com/Dicklesworthstone/coding_agent_account_manager/cmd/caam@latest'
CLAUDE_INSTALL_HINT='https://docs.claude.com/en/docs/claude-code/setup'
PYPI_PACKAGE='ccpool'

# ─────────────────────────────────────────────────────────────────────
# Output helpers (no-color when not a TTY)
# ─────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
  BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; BOLD=''; RESET=''
fi

step() { printf '%s%s ➜%s %s\n' "${BOLD}" "${YELLOW}" "${RESET}" "$1" >&2; }
ok()   { printf '%s ✓%s %s\n' "${GREEN}" "${RESET}" "$1" >&2; }
warn() { printf '%s ⚠%s %s\n' "${YELLOW}" "${RESET}" "$1" >&2; }
die()  { printf '%s ✗%s %s\n' "${RED}" "${RESET}" "$1" >&2; exit 1; }

# ─────────────────────────────────────────────────────────────────────
# Step 1 — Detect OS
# ─────────────────────────────────────────────────────────────────────
step "Detecting OS"
case "$(uname -s)" in
  Darwin) OS=macos ;;
  Linux)  OS=linux ;;
  *)      die "unsupported OS: $(uname -s). ccpool supports macOS + Linux only." ;;
esac
ok "OS: ${OS}"

# ─────────────────────────────────────────────────────────────────────
# Step 2 — Detect package manager
# ─────────────────────────────────────────────────────────────────────
step "Detecting package manager"
PKG_MGR=''
if [ "${OS}" = "macos" ] && command -v brew >/dev/null 2>&1; then
  PKG_MGR=brew
elif command -v pipx >/dev/null 2>&1; then
  PKG_MGR=pipx
elif command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
  PKG_MGR=pip
else
  die "no Python package manager found. Install pipx (recommended): https://pipx.pypa.io/"
fi
ok "package manager: ${PKG_MGR}"

# ─────────────────────────────────────────────────────────────────────
# Step 3 — Verify Python ≥3.11
# ─────────────────────────────────────────────────────────────────────
step "Verifying Python ≥${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}"
PY=python3
if ! command -v "${PY}" >/dev/null 2>&1; then
  PY=python
fi
if ! command -v "${PY}" >/dev/null 2>&1; then
  die "no python3 found on PATH"
fi
PY_VER="$("${PY}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$(printf '%s' "${PY_VER}" | cut -d. -f1)"
PY_MINOR="$(printf '%s' "${PY_VER}" | cut -d. -f2)"
if [ "${PY_MAJOR}" -lt "${PYTHON_MIN_MAJOR}" ] \
   || { [ "${PY_MAJOR}" -eq "${PYTHON_MIN_MAJOR}" ] && [ "${PY_MINOR}" -lt "${PYTHON_MIN_MINOR}" ]; }; then
  die "Python ${PY_VER} is too old. Need ≥${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}."
fi
ok "Python ${PY_VER}"

# ─────────────────────────────────────────────────────────────────────
# Step 4 — Verify caam on PATH
# ─────────────────────────────────────────────────────────────────────
step "Verifying caam binary"
if ! command -v caam >/dev/null 2>&1; then
  warn "caam not found on PATH"
  printf '  Install caam first:\n  %s\n\n' "${CAAM_INSTALL_HINT}" >&2
  die "ccpool requires caam (per ADR-0006). Install caam, then re-run."
fi
ok "caam: $(command -v caam)"

# ─────────────────────────────────────────────────────────────────────
# Step 5 — Verify claude on PATH
# ─────────────────────────────────────────────────────────────────────
step "Verifying claude binary"
if ! command -v claude >/dev/null 2>&1; then
  warn "claude binary not found on PATH"
  printf '  Install claude: %s\n\n' "${CLAUDE_INSTALL_HINT}" >&2
  warn "continuing without claude — ccpool install will succeed but you'll need to install claude before running ccpool."
else
  ok "claude: $(command -v claude)"
fi

# ─────────────────────────────────────────────────────────────────────
# Step 6 — Install ccpool
# ─────────────────────────────────────────────────────────────────────
step "Installing ${PYPI_PACKAGE}"
case "${PKG_MGR}" in
  brew)
    if brew list --formula | grep -q "^ccpool$"; then
      brew upgrade ccpool || true
    else
      # Tap is published at torkay/ccpool (see docs/INSTALL.md)
      brew tap torkay/ccpool 2>/dev/null || true
      brew install ccpool
    fi
    ;;
  pipx)
    if pipx list --short 2>/dev/null | grep -q "^${PYPI_PACKAGE} "; then
      pipx upgrade "${PYPI_PACKAGE}"
    else
      pipx install "${PYPI_PACKAGE}"
    fi
    ;;
  pip)
    PIP="$(command -v pip3 || command -v pip)"
    "${PIP}" install --user --upgrade "${PYPI_PACKAGE}"
    ;;
esac
ok "${PYPI_PACKAGE} installed"

# ─────────────────────────────────────────────────────────────────────
# Step 7 — Run doctor (warn-only; we don't fail install on findings)
# ─────────────────────────────────────────────────────────────────────
step "Running ccpool doctor"
if command -v ccpool >/dev/null 2>&1; then
  if ccpool doctor --json >/dev/null 2>&1; then
    ok "doctor: clean"
  else
    warn "doctor surfaced findings — run 'ccpool doctor' for details"
  fi
else
  warn "ccpool is not on PATH yet. You may need to add ~/.local/bin to PATH or open a new shell."
fi

# ─────────────────────────────────────────────────────────────────────
# Step 8 — Next-step pointer
# ─────────────────────────────────────────────────────────────────────
echo
printf '%sAll set.%s Next:\n\n' "${BOLD}${GREEN}" "${RESET}"
echo "  ccpool setup       interactive: link your Claude Max accounts"
echo "  ccpool status      health snapshot"
echo "  ccpool usage       live utilization"
echo
echo "Docs: https://github.com/torkay/ccpool/tree/main/docs"
