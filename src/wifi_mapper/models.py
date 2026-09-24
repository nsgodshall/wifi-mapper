from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WifiStatus:
    """Snapshot of the currently connected WiFi network."""

    ssid: str | None
    iface: str | None
    signal_percent: int | None
    signal_dbm: int | None


@dataclass
class ScanResult:
    ssid: str
    signal_percent: int | None
    security: str
    in_use: bool
    saved: bool


@dataclass
class SpeedResult:
    download_mbps: float
    upload_mbps: float
    ping_ms: float | None
    server_name: str
    server_sponsor: str


@dataclass
class Measurement:
    id: int | None
    timestamp: str
    label: str
    ssid: str | None
    signal_percent: int | None
    signal_dbm: int | None
    download_mbps: float
    upload_mbps: float
    ping_ms: float | None
    server_name: str
