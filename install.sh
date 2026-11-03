#!/usr/bin/env bash
# Install Python prerequisites and project dependencies. Webots is external.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

install_python_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo 'Install Python 3.11+ with venv and ensurepip for your operating system, then rerun install.sh.' >&2
    exit 1
  fi
  local elevate=()
  if [[ "$EUID" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo 'Installing missing Python system packages requires sudo or root.' >&2
      exit 1
    fi
    elevate=(sudo)
  fi
  "${elevate[@]}" apt-get update
  "${elevate[@]}" apt-get install -y "$@"
}

setup_python="${PYTHON:-python3}"
if ! command -v "$setup_python" >/dev/null 2>&1; then
  install_python_packages python3 python3-venv python3-pip
  setup_python=python3
fi
# Use the base interpreter even if the caller activated the broken project venv.
setup_python="$("$setup_python" -c 'import sys; print(getattr(sys, "_base_executable", sys.executable))')"
"$setup_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11 or newer is required.")'
if ! "$setup_python" -c 'import venv, ensurepip' >/dev/null 2>&1; then
  python_minor="$("$setup_python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  install_python_packages "python${python_minor}-venv" python3-pip
fi
"$setup_python" -c 'import venv, ensurepip'
exec "$setup_python" setup_project.py
