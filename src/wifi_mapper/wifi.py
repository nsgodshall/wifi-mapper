from __future__ import annotations

import re
import subprocess

from wifi_mapper.models import ScanResult, WifiStatus

_UNESCAPED_COLON = re.compile(r"(?<!\\):")


def _split_terse(line: str) -> list[str]:
    """Split an nmcli -t line on unescaped ':' and unescape the rest."""
    fields = _UNESCAPED_COLON.split(line)
    return [f.replace(r"\:", ":").replace("\\\\", "\\") for f in fields]


def _run(args: list[str], timeout: float = 15) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


class WifiError(RuntimeError):
    pass


def get_active_iface() -> str | None:
    """Return the device name of the connected WiFi interface, if any."""
    try:
        proc = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
            return parts[0]
    return None


def _signal_dbm(iface: str) -> int | None:
    try:
        proc = _run(["iw", "dev", iface, "link"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"signal:\s*(-?\d+)\s*dBm", proc.stdout)
    return int(match.group(1)) if match else None


def get_current_status() -> WifiStatus:
    iface = get_active_iface()
    if iface is None:
        return WifiStatus(ssid=None, iface=None, signal_percent=None, signal_dbm=None)

    ssid = None
    signal_percent = None
    try:
        proc = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list"])
        for line in proc.stdout.splitlines():
            parts = _split_terse(line)
            if len(parts) >= 3 and parts[0] == "*":
                ssid = parts[1] or None
                try:
                    signal_percent = int(parts[2])
                except ValueError:
                    signal_percent = None
                break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return WifiStatus(
        ssid=ssid,
        iface=iface,
        signal_percent=signal_percent,
        signal_dbm=_signal_dbm(iface),
    )


def list_saved_wifi_connections() -> list[str]:
    try:
        proc = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    names = []
    for line in proc.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            names.append(parts[0])
    return names


def get_active_wifi_connection_name() -> str | None:
    """Return the connection profile NAME currently active on the WiFi device, if any."""
    try:
        proc = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            return parts[0]
    return None


def scan_networks(rescan: bool = True) -> list[ScanResult]:
    saved = set(list_saved_wifi_connections())
    args = ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    if rescan:
        args += ["--rescan", "yes"]
    try:
        proc = _run(args, timeout=25)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    results: list[ScanResult] = []
    seen_ssids: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) < 4:
            continue
        in_use, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
        if not ssid or ssid in seen_ssids:
            continue
        seen_ssids.add(ssid)
        try:
            signal_percent = int(signal)
        except ValueError:
            signal_percent = None
        results.append(
            ScanResult(
                ssid=ssid,
                signal_percent=signal_percent,
                security=security or "--",
                in_use=(in_use == "*"),
                saved=ssid in saved,
            )
        )
    results.sort(key=lambda r: (r.signal_percent is None, -(r.signal_percent or 0)))
    return results


def connect_saved(name: str) -> tuple[bool, str]:
    try:
        proc = _run(["nmcli", "connection", "up", "id", name], timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, proc.stdout.strip() or f"Connected to {name}"
    return False, (proc.stderr or proc.stdout).strip()


def connect_new(ssid: str, password: str | None) -> tuple[bool, str]:
    args = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    try:
        proc = _run(args, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, proc.stdout.strip() or f"Connected to {ssid}"
    return False, (proc.stderr or proc.stdout).strip()
