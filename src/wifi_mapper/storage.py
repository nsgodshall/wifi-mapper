from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from wifi_mapper.models import Measurement

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "wifi-mapper" / "measurements.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    label TEXT NOT NULL,
    ssid TEXT,
    signal_percent INTEGER,
    signal_dbm INTEGER,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    ping_ms REAL,
    server_name TEXT
);
"""


class Storage:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the app dispatches storage calls to worker
        # threads via asyncio.to_thread, but never concurrently (each call is
        # awaited before the next one starts), so a single connection is safe.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def add(self, m: Measurement) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO measurements
                (timestamp, label, ssid, signal_percent, signal_dbm,
                 download_mbps, upload_mbps, ping_ms, server_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                m.timestamp,
                m.label,
                m.ssid,
                m.signal_percent,
                m.signal_dbm,
                m.download_mbps,
                m.upload_mbps,
                m.ping_ms,
                m.server_name,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def all(self) -> list[Measurement]:
        rows = self._conn.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC"
        ).fetchall()
        return [self._row_to_measurement(r) for r in rows]

    def delete(self, measurement_id: int) -> None:
        self._conn.execute("DELETE FROM measurements WHERE id = ?", (measurement_id,))
        self._conn.commit()

    def export_csv(self, path: Path) -> int:
        rows = self.all()
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "timestamp",
                    "label",
                    "ssid",
                    "signal_percent",
                    "signal_dbm",
                    "download_mbps",
                    "upload_mbps",
                    "ping_ms",
                    "server_name",
                ]
            )
            for m in rows:
                writer.writerow(
                    [
                        m.id,
                        m.timestamp,
                        m.label,
                        m.ssid,
                        m.signal_percent,
                        m.signal_dbm,
                        m.download_mbps,
                        m.upload_mbps,
                        m.ping_ms,
                        m.server_name,
                    ]
                )
        return len(rows)

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_measurement(row: sqlite3.Row) -> Measurement:
        return Measurement(
            id=row["id"],
            timestamp=row["timestamp"],
            label=row["label"],
            ssid=row["ssid"],
            signal_percent=row["signal_percent"],
            signal_dbm=row["signal_dbm"],
            download_mbps=row["download_mbps"],
            upload_mbps=row["upload_mbps"],
            ping_ms=row["ping_ms"],
            server_name=row["server_name"],
        )
