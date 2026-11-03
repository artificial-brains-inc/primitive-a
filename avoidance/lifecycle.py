"""Public SDK lifecycle checks, separate from all flight decisions."""
from __future__ import annotations



def engine_status(report):
    engine = report.get("engine")
    if not isinstance(engine, dict) or not isinstance(engine.get("state"), str):
        raise RuntimeError("Prima-Lux returned no usable engine status.")
    state = engine["state"].upper()
    if engine.get("error") or engine.get("available") is False or state in (
        "ERROR", "FAULT", "SAFE_MODE", "UNAVAILABLE"
    ):
        raise RuntimeError(f"Prima-Lux is unavailable ({state}). Check: ab device --env .env status")
    return engine, state


def installed_hash(report):
    return ((report.get("package") or {}).get("active") or {}).get("design_sha256")


def require_installed(report, digest, states=("READY", "STOPPED")):
    engine, state = engine_status(report)
    if engine.get("busy") or (report.get("package") or {}).get("pending"):
        raise RuntimeError("Prima-Lux still has an operation in progress; Run was not started.")
    if state not in states:
        raise RuntimeError(f"Prima-Lux is {state}; expected {' or '.join(states)}. Stop the active session first.")
    if engine.get("has_brain") is not True or installed_hash(report) != digest:
        raise RuntimeError("The installed brain does not match this package. Use: ab build brain --brain brain.abdesign.json --env .env")
    return state

