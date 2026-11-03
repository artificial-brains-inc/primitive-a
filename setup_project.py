"""Install Python dependencies only; preserve the saved design and device settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import venv

ROOT = Path(__file__).resolve().parent


def interpreter_details(python):
    try:
        result = subprocess.run(
            [str(python), "-I", "-c",
             "import json,sys; print(json.dumps({'prefix':sys.prefix,'version':list(sys.version_info[:2])}))"],
            check=True, text=True, capture_output=True)
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def pip_available(python):
    return subprocess.run([str(python), "-m", "pip", "--version"],
                          capture_output=True).returncode == 0


def create_environment(environment):
    if environment.exists() or environment.is_symlink():
        backup = environment.with_name(f".venv.backup-{time.time_ns()}")
        environment.rename(backup)
        print(f"Preserved the incomplete environment as {backup.name}.", flush=True)
    venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")).create(environment)


def ensure_environment(root):
    if sys.version_info < (3, 11):
        raise RuntimeError("Use Python 3.11 or newer; Ubuntu 24.04 includes Python 3.12.")
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    details = interpreter_details(python) if python.is_file() else None
    usable = ((environment / "pyvenv.cfg").is_file() and details is not None
              and Path(details["prefix"]).resolve() == environment.resolve()
              and tuple(details["version"]) >= (3, 11))
    if not usable:
        create_environment(environment)
    else:
        print("Reusing the project virtual environment.", flush=True)
    if not pip_available(python):
        print("Restoring pip in the project environment with ensurepip.", flush=True)
        restored = subprocess.run([str(python), "-m", "ensurepip", "--upgrade", "--default-pip"])
        if restored.returncode != 0 or not pip_available(python):
            create_environment(environment)
    if not pip_available(python):
        raise RuntimeError("pip could not be initialized. Check the ensurepip error above.")
    return python


def main(root=ROOT):
    python = ensure_environment(root)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True)
    subprocess.run([str(python), "-m", "pip", "check"], check=True)
    if not (root / ".env").exists():
        shutil.copyfile(root / ".env.example", root / ".env")
        if os.name != "nt":
            (root / ".env").chmod(0o600)
    print("Installation complete. Activate with: source .venv/bin/activate", flush=True)
    print("Set the Prima-Lux address and API key in .env, then follow the README's SDK steps.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
