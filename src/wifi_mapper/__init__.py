from __future__ import annotations

import argparse
from pathlib import Path

from wifi_mapper.app import run
from wifi_mapper.storage import DEFAULT_DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wifi-mapper",
        description="TUI tool for mapping WiFi speed and signal strength around a house.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()
    run(db_path=args.db)


if __name__ == "__main__":
    main()
