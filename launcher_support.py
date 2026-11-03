"""Host setup only. No sensor, neural or motor control logic."""
from pathlib import Path
import configparser
import os
import re
import shutil
import subprocess

WEBOTS_RELEASE = "R2025a"
CONTROLLERS = ("primalux_front_obstacle",)


def env_values(path):
    """Read the simple KEY=value format accepted by SDK 0.4.0; never execute it."""
    if not path.exists():
        return {}
    result = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def find_webots(root, explicit=None):
    settings = env_values(Path(os.environ.get("AB_ENV", str(root / ".env"))))
    chosen = explicit or os.environ.get("WEBOTS_EXECUTABLE") or settings.get("WEBOTS_EXECUTABLE")
    if chosen:
        candidate = Path(chosen).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise RuntimeError("WEBOTS_EXECUTABLE must name an executable file. See docs/REQUIREMENTS.md.")
    candidates = [shutil.which("webots"), "/usr/local/webots/webots", "/opt/webots/webots",
                  "/usr/share/webots/webots", str(Path.home()/"webots/webots"),
                  str(Path.home()/"webots/webots/webots")]
    for name in candidates:
        if name and Path(name).is_file() and os.access(name, os.X_OK):
            return str(Path(name).resolve())
    raise RuntimeError("Webots R2025a was not found. Install it separately from Cyberbotics, "
                       "or point to your existing installation with WEBOTS_EXECUTABLE in .env. "
                       "See docs/REQUIREMENTS.md.")


def check_webots(executable):
    try:
        result = subprocess.run([executable, "--version"], capture_output=True,
                                text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Could not start Webots. Check its installation and graphical libraries.") from exc
    version = re.search(r"\bR\d{4}[a-z]\b", result.stdout + result.stderr)
    if result.returncode != 0 or not version or version.group() != WEBOTS_RELEASE:
        found = version.group() if version else "unavailable"
        raise RuntimeError(f"This demo requires Webots {WEBOTS_RELEASE}; found {found}. See docs/REQUIREMENTS.md.")
    return version.group()


def write_controller_runtime(root):
    # Webots documents runtime.ini [python]/COMMAND. Resolving python3 through
    # the launch PATH avoids embedding one person's absolute venv path in Git.
    for name in CONTROLLERS:
        directory = root / "controllers" / name
        if not directory.is_dir():
            continue
        path = directory / "runtime.ini"
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        if path.exists():
            config.read(path)
        if not config.has_section("python"):
            config.add_section("python")
        config.set("python", "COMMAND", "python3")
        with path.open("w") as stream:
            config.write(stream)


def webots_environment(root):
    env = os.environ.copy()
    env["PATH"] = str(root / ".venv" / "bin") + os.pathsep + env.get("PATH", "")
    return env
