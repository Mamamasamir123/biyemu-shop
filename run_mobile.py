#!/usr/bin/env python3
"""Mwongozo + anzisha server kwa kujaribu kwenye simu."""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from web.server import _all_ipv4_addresses, run


def _ips_from_ipconfig() -> list[str]:
    try:
        out = subprocess.check_output(["ipconfig"], text=True, encoding="utf-8", errors="ignore")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return sorted(set(re.findall(r"IPv4 Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", out)) - {"127.0.0.1"})


def main():
    print("\n  ============================================")
    print("    BiyeMu — Jaribu kwenye Simu")
    print("  ============================================\n")
    print("  PC haina Wi-Fi? Tumia badala yake:")
    print("    python run_phone_usb.py")
    print("  (tunnel ya mtandao — inafanya kazi na USB internet)\n")
    print("  PC ina Wi-Fi? Tumia HOTSPOT:")
    print("  1. Simu: Washa Wi-Fi Hotspot")
    print("  2. PC: Unganisha kwenye hotspot ya simu")
    print("  3. Endesha server, simu ifungue URL iliyoonyeshwa")
    print("  4. Firewall: open_firewall.bat (Admin)\n")

    ips = _ips_from_ipconfig() or _all_ipv4_addresses()
    if ips:
        print("  IP za PC sasa:")
        for ip in ips:
            print(f"    http://{ip}:5000")
    else:
        print("  Bado hakuna IP — unganisha PC kwenye hotspot kwanza.\n")

    print("\n  Inaanzisha server...\n")
    run()


if __name__ == "__main__":
    main()