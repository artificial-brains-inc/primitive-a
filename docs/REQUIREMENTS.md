# Requirements and installation

The reference host is Ubuntu 24.04 x86_64 with a graphical desktop and OpenGL.
Git is needed to clone the repository. Python 3.11 or newer is supported;
Ubuntu 24.04 provides Python 3.12.

Download and install Webots independently from the
[Cyberbotics R2025a release](https://github.com/cyberbotics/webots/releases/tag/R2025a),
or reuse your existing R2025a installation. This package does not download,
install or update Webots.

## Install Python dependencies

```bash
bash install.sh
source .venv/bin/activate
```

On Ubuntu, the installer uses apt only if Python or the required venv/ensurepip
modules are missing. It creates the local environment, restores missing pip
with Python's ensurepip, and installs `requirements.txt`, including SDK 0.4.0
and its dependencies. A damaged environment that must be replaced is preserved
under a `.venv.backup-...` name. An existing `.env` and saved brain design remain
unchanged. Installation does not contact Prima-Lux or start Webots.

Webots supplies the `controller` Python module. Do not install an unrelated
PyPI package named `controller`. The application's Webots controller uses the
project's installed Python environment.

## Configure the device

Edit the local `.env` to set `AB_DEVICE_URL` and `AB_DEVICE_API_KEY` for your
onboarded device. Keep the key private. An IP address can replace the example
hostname if hostname discovery is unavailable. Network sharing is configured
outside this project.

The application finds Webots on PATH or in common installation directories.
For another location, set `WEBOTS_EXECUTABLE` in `.env` to its executable.

## Use the SDK

```bash
ab design --brain brain.abdesign.json --env .env
ab build brain --brain brain.abdesign.json --env .env
ab run -ab --env .env
```

These are separate stages. Close the Designer after saving any edits, then
build. Wait for the build to report READY before running. The README explains
how the Designer's downloaded file becomes the project's saved design.
