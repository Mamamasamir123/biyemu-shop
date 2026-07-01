#!/usr/bin/env python3
"""
Jaribu BiyeMu kwenye simu — PC bila Wi-Fi.
Njia A (bora): ADB reverse + USB debugging
Njia B: Cloudflare tunnel (URL ya mtandao)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
TOOLS = ROOT / "tools"
CLOUDFLARED = TOOLS / "cloudflared.exe"
ADB = TOOLS / "platform-tools" / "adb.exe"
PLATFORM_TOOLS_ZIP = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
PORT = 5000

sys.path.insert(0, str(ROOT))
from web.server import flask_app  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _powershell_download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        f'$ProgressPreference="SilentlyContinue"; '
        f'Invoke-WebRequest -Uri "{url}" -OutFile "{dest}" -UseBasicParsing'
    )
    try:
        subprocess.check_call(
            ["powershell", "-NoProfile", "-Command", ps],
            timeout=300,
        )
        return dest.exists() and dest.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def _ensure_adb() -> Path | None:
    if ADB.exists():
        return ADB
    zip_path = TOOLS / "platform-tools.zip"
    _log("  Inapakua Android platform-tools (ADB)...")
    if not _powershell_download(PLATFORM_TOOLS_ZIP, zip_path):
        return None
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(TOOLS)
        zip_path.unlink(missing_ok=True)
    except (OSError, zipfile.BadZipFile):
        return None
    return ADB if ADB.exists() else None


def _ensure_cloudflared() -> Path | None:
    if CLOUDFLARED.exists():
        return CLOUDFLARED
    _log("  Inapakua cloudflared...")
    if _powershell_download(CLOUDFLARED_URL, CLOUDFLARED):
        return CLOUDFLARED
    return None


def _start_server():
    flask_app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def _try_adb_reverse() -> bool:
    adb = shutil.which("adb")
    if not adb:
        adb_path = _ensure_adb()
        adb = str(adb_path) if adb_path else None
    if not adb:
        return False
    try:
        subprocess.check_call([adb, "start-server"], timeout=15)
        devices = subprocess.check_output([adb, "devices"], text=True, timeout=10)
        if "\tdevice" not in devices:
            _log("  ADB: simu haionekani — washa USB debugging, kubali ruhusa.")
            return False
        subprocess.check_call([adb, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"], timeout=10)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run_tunnel(exe: Path) -> str | None:
    proc = subprocess.Popen(
        [str(exe), "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    deadline = time.time() + 60
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        match = url_pattern.search(line)
        if match:
            return match.group(0)
    return None


def main():
    _log("\n  ============================================")
    _log("    BiyeMu — Simu (PC bila Wi-Fi)")
    _log("  ============================================\n")
    _log("  PC haina Wi-Fi — hotspot haiwezekani kwenye PC.")
    _log("  Tumia ADB (USB) au tunnel ya mtandao.\n")

    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()
    time.sleep(1.2)

    if _try_adb_reverse():
        _log("\n  ADB reverse imewashwa!")
        _log(f"  Fungua KWENYE SIMU: http://127.0.0.1:{PORT}")
        _log("  (Simu imeunganishwa USB + USB debugging ON)\n")
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            _log("\n  Imesimamishwa.")
        return

    _log("  ADB haikufanya kazi. Inajaribu tunnel...")
    exe = _ensure_cloudflared()
    if exe:
        public_url = _run_tunnel(exe)
        if public_url:
            _log("\n  Fungua KWENYE SIMU (browser / data ya simu):")
            _log(f"    {public_url}\n")
            try:
                while server_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                _log("\n  Imesimamishwa.")
            return

    _log("\n  JARIBU HII (ADB — bila Wi-Fi PC):")
    _log("  1. Simu: Settings → About → gusa Build number mara 7")
    _log("  2. Simu: Developer options → USB debugging ON")
    _log("  3. Unganisha simu kwa USB, kubali 'Allow debugging'")
    _log("  4. Endesha tena: python run_phone_usb.py")
    _log(f"  5. Simu ifungue: http://127.0.0.1:{PORT}\n")
    _log("  Au pakua cloudflared kwa mkono:")
    _log(f"    {CLOUDFLARED_URL}")
    _log(f"    weka kwenye {CLOUDFLARED}\n")
    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        _log("\n  Imesimamishwa.")


if __name__ == "__main__":
    main()