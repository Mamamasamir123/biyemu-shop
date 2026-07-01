#!/usr/bin/env python3
"""Anzisha toleo la wavuti la BiyeMu."""

import sys
import webbrowser
from pathlib import Path
from threading import Timer

sys.path.insert(0, str(Path(__file__).parent))

from web.server import run


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("\n  ============================================")
    print("    BiyeMu — Toleo la Wavuti")
    print("  ============================================")
    print("\n  Inaendesha server...")
    print("  PC:   http://127.0.0.1:5000")
    print("  Simu: angalia anwani ya Wi-Fi inayochapishwa hapa chini")
    print("  Simamisha kwa Ctrl+C\n")
    Timer(1.5, open_browser).start()
    run()