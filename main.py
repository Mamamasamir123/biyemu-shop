#!/usr/bin/env python3
"""
Mfumo wa Kudhibiti Maduka ya BiyeMu
Mfumo wa kudhibiti maduka mengi kwa Python (Kiolesura cha Terminal)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import BiyeMuApp
from seed_data import seed_if_empty
from ui.console import ConsoleUI


def main() -> None:
    print("\n  Inapakia data...", flush=True)
    app = BiyeMuApp()
    seed_if_empty(app.storage)
    print("  Tayari! Subiri skrini ya kuingia...\n", flush=True)
    ConsoleUI(app).run()


if __name__ == "__main__":
    main()