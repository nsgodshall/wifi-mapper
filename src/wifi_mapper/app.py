from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from wifi_mapper import wifi
from wifi_mapper.models import Measurement
from wifi_mapper.screens import (
    ConfirmScreen,
    LabelScreen,
    NetworkScreen,
    NetworkSetScreen,
    PasswordScreen,
)
from wifi_mapper.speedtest_runner import run_speedtest
from wifi_mapper.storage import DEFAULT_DB_PATH, Storage

COLUMNS = ("Label", "SSID", "Signal", "Down Mbps", "Up Mbps", "Ping ms", "Time")


class WifiMapperApp(App):
    TITLE = "WiFi Mapper"
    CSS = """
    #status_bar {
        height: 1;
        padding: 0 1;
        background: $boost;
        color: $text;
    }
    #busy {
        height: 1;
        padding: 0 1;
        color: $warning;
    }
    """

    BINDINGS = [
        ("n", "new_measurement", "New measurement"),
        ("w", "wired_test", "Wired test (no WiFi)"),
        ("b", "batch_test", "Test network set"),
        ("s", "switch_network", "Switch network"),
        ("r", "refresh_status", "Refresh status"),
        ("e", "export_csv", "Export CSV"),
        ("d", "delete_selected", "Delete"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        super().__init__()
        self.storage = Storage(db_path)
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Network: checking...", id="status_bar")
        with Horizontal(id="busy_row"):
            yield Static("", id="busy")
        yield DataTable(id="table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.cursor_type = "row"
        table.add_columns(*COLUMNS)
        self._reload_table()
        self.call_after_refresh(self.action_refresh_status)

    def on_unmount(self) -> None:
        self.storage.close()

    # -- helpers ---------------------------------------------------------

    def _set_busy(self, message: str) -> None:
        self._busy = True
        self.query_one("#busy", Static).update(message)

    def _clear_busy(self) -> None:
        self._busy = False
        self.query_one("#busy", Static).update("")

    def _reload_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear()
        for m in self.storage.all():
            signal = "--"
            if m.signal_dbm is not None:
                signal = f"{m.signal_dbm} dBm"
            elif m.signal_percent is not None:
                signal = f"{m.signal_percent}%"
            table.add_row(
                m.label,
                m.ssid or "--",
                signal,
                f"{m.download_mbps:.1f}",
                f"{m.upload_mbps:.1f}",
                f"{m.ping_ms:.0f}" if m.ping_ms is not None else "n/a",
                m.timestamp,
                key=str(m.id),
            )

    def _update_status_bar(self, status: wifi.WifiStatus) -> None:
        if status.ssid is None:
            text = "Network: not connected to WiFi"
        else:
            bits = [f"Network: {status.ssid}"]
            if status.signal_dbm is not None:
                bits.append(f"{status.signal_dbm} dBm")
            if status.signal_percent is not None:
                bits.append(f"{status.signal_percent}%")
            text = "  |  ".join(bits)
        self.query_one("#status_bar", Static).update(text)

    # -- actions -----------------------------------------------------------

    async def action_refresh_status(self) -> None:
        status = await asyncio.to_thread(wifi.get_current_status)
        self._update_status_bar(status)

    @work(exclusive=True)
    async def action_new_measurement(self) -> None:
        if self._busy:
            self.notify("Already busy, please wait.", severity="warning")
            return
        status = await asyncio.to_thread(wifi.get_current_status)
        label = await self.push_screen_wait(LabelScreen(status.ssid))
        if label is None:
            return

        self._set_busy("Running speed test...")

        def progress(stage: str) -> None:
            self.call_from_thread(self._set_busy, stage)

        try:
            result = await asyncio.to_thread(run_speedtest, progress)
        except Exception as exc:  # speedtest can fail for many reasons (no servers, offline, etc.)
            self._clear_busy()
            self.notify(f"Speed test failed: {exc}", severity="error")
            return

        measurement = Measurement(
            id=None,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            label=label,
            ssid=status.ssid,
            signal_percent=status.signal_percent,
            signal_dbm=status.signal_dbm,
            download_mbps=result.download_mbps,
            upload_mbps=result.upload_mbps,
            ping_ms=result.ping_ms,
            server_name=result.server_name,
        )
        self.storage.add(measurement)
        self._clear_busy()
        self._reload_table()
        ping_text = f"{result.ping_ms:.0f} ms ping" if result.ping_ms is not None else "ping n/a"
        self.notify(
            f"Saved '{label}': {result.download_mbps:.1f}/{result.upload_mbps:.1f} Mbps, {ping_text}"
        )

    @work(exclusive=True)
    async def action_wired_test(self) -> None:
        """Run a speed test with no WiFi involved, to baseline the modem/router/ISP."""
        if self._busy:
            self.notify("Already busy, please wait.", severity="warning")
            return
        label = await self.push_screen_wait(
            LabelScreen(None, heading="Wired speed test (no WiFi) — label this connection point:")
        )
        if label is None:
            return

        self._set_busy("Running wired speed test...")

        def progress(stage: str) -> None:
            self.call_from_thread(self._set_busy, stage)

        try:
            result = await asyncio.to_thread(run_speedtest, progress)
        except Exception as exc:
            self._clear_busy()
            self.notify(f"Speed test failed: {exc}", severity="error")
            return

        measurement = Measurement(
            id=None,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            label=label,
            ssid="(wired)",
            signal_percent=None,
            signal_dbm=None,
            download_mbps=result.download_mbps,
            upload_mbps=result.upload_mbps,
            ping_ms=result.ping_ms,
            server_name=result.server_name,
        )
        self.storage.add(measurement)
        self._clear_busy()
        self._reload_table()
        ping_text = f"{result.ping_ms:.0f} ms ping" if result.ping_ms is not None else "ping n/a"
        self.notify(
            f"Saved wired '{label}': {result.download_mbps:.1f}/{result.upload_mbps:.1f} Mbps, {ping_text}"
        )

    @work(exclusive=True)
    async def action_batch_test(self) -> None:
        """Test a chosen set of saved networks back-to-back at the current spot."""
        if self._busy:
            self.notify("Already busy, please wait.", severity="warning")
            return

        saved = await asyncio.to_thread(wifi.list_saved_wifi_connections)
        if not saved:
            self.notify("No saved WiFi connections to test.", severity="warning")
            return

        self._set_busy("Scanning for signal preview...")
        try:
            scan_results = await asyncio.to_thread(wifi.scan_networks)
        finally:
            self._clear_busy()
        signal_by_ssid = {
            r.ssid: r.signal_percent for r in scan_results if r.signal_percent is not None
        }

        original_status = await asyncio.to_thread(wifi.get_current_status)
        original_connection = await asyncio.to_thread(wifi.get_active_wifi_connection_name)

        label = await self.push_screen_wait(
            LabelScreen(None, heading="Label this location before testing a set of networks:")
        )
        if label is None:
            return

        selection = await self.push_screen_wait(
            NetworkSetScreen(saved, signal_by_ssid, original_status.ssid)
        )
        if not selection:
            return

        summary: list[str] = []
        for name in selection:
            self._set_busy(f"Connecting to {name}...")
            ok, message = await asyncio.to_thread(wifi.connect_saved, name)
            if not ok:
                self.notify(f"Skipped {name}: {message}", severity="warning")
                continue

            # Give DHCP/routing a moment to settle before measuring.
            await asyncio.sleep(2)
            net_status = await asyncio.to_thread(wifi.get_current_status)

            def progress(stage: str, _name: str = name) -> None:
                self.call_from_thread(self._set_busy, f"{_name}: {stage}")

            try:
                result = await asyncio.to_thread(run_speedtest, progress)
            except Exception as exc:
                self.notify(f"Speed test failed for {name}: {exc}", severity="error")
                continue

            measurement = Measurement(
                id=None,
                timestamp=datetime.now().isoformat(timespec="seconds"),
                label=label,
                ssid=net_status.ssid or name,
                signal_percent=net_status.signal_percent,
                signal_dbm=net_status.signal_dbm,
                download_mbps=result.download_mbps,
                upload_mbps=result.upload_mbps,
                ping_ms=result.ping_ms,
                server_name=result.server_name,
            )
            self.storage.add(measurement)
            self._reload_table()
            summary.append(
                f"{net_status.ssid or name}: {result.download_mbps:.1f}/{result.upload_mbps:.1f} Mbps"
            )

        if original_connection:
            self._set_busy(f"Reconnecting to {original_connection}...")
            await asyncio.to_thread(wifi.connect_saved, original_connection)

        self._clear_busy()
        await self.action_refresh_status()

        if summary:
            self.notify(f"Batch '{label}' done — " + "; ".join(summary))
        else:
            self.notify(f"Batch '{label}': no successful measurements", severity="warning")

    @work(exclusive=True)
    async def action_switch_network(self) -> None:
        if self._busy:
            self.notify("Already busy, please wait.", severity="warning")
            return
        self._set_busy("Scanning for networks...")
        try:
            results = await asyncio.to_thread(wifi.scan_networks)
        finally:
            self._clear_busy()

        choice = await self.push_screen_wait(NetworkScreen(results))
        if choice is None:
            return
        ssid, saved = choice

        password = None
        if not saved:
            result = next((r for r in results if r.ssid == ssid), None)
            needs_password = result is not None and result.security not in ("--", "")
            if needs_password:
                password = await self.push_screen_wait(PasswordScreen(ssid))
                if password is None:
                    return

        self._set_busy(f"Connecting to {ssid}...")
        try:
            if saved:
                ok, message = await asyncio.to_thread(wifi.connect_saved, ssid)
            else:
                ok, message = await asyncio.to_thread(wifi.connect_new, ssid, password)
        finally:
            self._clear_busy()

        if ok:
            self.notify(message)
        else:
            self.notify(message, severity="error")
        await self.action_refresh_status()

    async def action_export_csv(self) -> None:
        export_path = self.storage.db_path.parent / (
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        count = await asyncio.to_thread(self.storage.export_csv, export_path)
        self.notify(f"Exported {count} measurements to {export_path}")

    @work(exclusive=True)
    async def action_delete_selected(self) -> None:
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None or row_key.value is None:
            return
        confirmed = await self.push_screen_wait(
            ConfirmScreen("Delete this measurement? This cannot be undone.")
        )
        if not confirmed:
            return
        self.storage.delete(int(row_key.value))
        self._reload_table()


def run(db_path: Path = DEFAULT_DB_PATH) -> None:
    WifiMapperApp(db_path=db_path).run()
