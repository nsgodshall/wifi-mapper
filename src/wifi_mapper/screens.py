from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, SelectionList, Static
from textual.widgets.selection_list import Selection

from wifi_mapper.models import ScanResult


class LabelScreen(ModalScreen[str | None]):
    """Prompt the user for a location label before starting a measurement."""

    DEFAULT_CSS = """
    LabelScreen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $panel;
    }
    #dialog Input {
        margin-top: 1;
    }
    #buttons {
        margin-top: 1;
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, current_ssid: str | None, heading: str | None = None) -> None:
        super().__init__()
        self._current_ssid = current_ssid
        self._heading = heading

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            heading = self._heading or f"New measurement on [b]{self._current_ssid or 'unknown network'}[/b]"
            yield Label(heading)
            yield Label("Label this location (e.g. 'Living Room', 'Garage'):")
            yield Input(placeholder="Location label", id="label_input")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Start test", id="start", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#label_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self._submit()
        else:
            self.dismiss(None)

    def _submit(self) -> None:
        label = self.query_one("#label_input", Input).value.strip()
        self.dismiss(label or "Unlabeled")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $error;
        background: $panel;
    }
    #buttons {
        margin-top: 1;
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message)
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Delete", id="confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)


class PasswordScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    PasswordScreen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $panel;
    }
    #dialog Input {
        margin-top: 1;
    }
    #buttons {
        margin-top: 1;
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, ssid: str) -> None:
        super().__init__()
        self._ssid = ssid

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Password for [b]{self._ssid}[/b]:")
            yield Input(placeholder="Password", password=True, id="pw_input")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Connect", id="connect", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#pw_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(self.query_one("#pw_input", Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect":
            self.dismiss(self.query_one("#pw_input", Input).value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class NetworkSetScreen(ModalScreen[list[str] | None]):
    """Pick a set of saved networks to test one after another at this spot."""

    DEFAULT_CSS = """
    NetworkSetScreen {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        max-height: 30;
        padding: 1 2;
        border: thick $accent;
        background: $panel;
    }
    #dialog SelectionList {
        height: auto;
        max-height: 18;
        margin-top: 1;
    }
    #buttons {
        margin-top: 1;
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, saved_names: list[str], signal_by_ssid: dict[str, int], current_ssid: str | None) -> None:
        super().__init__()
        self._saved_names = saved_names
        self._signal_by_ssid = signal_by_ssid
        self._current_ssid = current_ssid

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Select networks to test at this location (space to toggle):")
            if not self._saved_names:
                yield Static("No saved WiFi connections found.")
            else:
                selections = []
                for name in self._saved_names:
                    signal = self._signal_by_ssid.get(name)
                    bits = [name]
                    if signal is not None:
                        bits.append(f"{signal}%")
                    if name == self._current_ssid:
                        bits.append("current")
                    text = " — ".join(bits)
                    selections.append(Selection(text, name, True))
                yield SelectionList(*selections, id="net_selection")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Test selected", id="confirm", variant="primary")

    def on_mount(self) -> None:
        try:
            self.query_one("#net_selection", SelectionList).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self._submit()
        else:
            self.dismiss(None)

    def _submit(self) -> None:
        try:
            selection_list = self.query_one("#net_selection", SelectionList)
        except Exception:
            self.dismiss(None)
            return
        selected = list(selection_list.selected)
        self.dismiss(selected or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class NetworkScreen(ModalScreen[tuple[str, bool] | None]):
    """Pick a network to switch to. Result is (ssid_or_name, is_saved)."""

    DEFAULT_CSS = """
    NetworkScreen {
        align: center middle;
    }
    #dialog {
        width: 70;
        height: 26;
        padding: 1 2;
        border: thick $accent;
        background: $panel;
    }
    #dialog ListView {
        height: 1fr;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, results: list[ScanResult]) -> None:
        super().__init__()
        self._results = results

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Select a network (Enter to connect, Esc to cancel)")
            if not self._results:
                yield Static("No networks found. Is WiFi enabled?")
            else:
                items = []
                for r in self._results:
                    tag = "[green]saved[/]" if r.saved else "[yellow]new[/]"
                    marker = " (current)" if r.in_use else ""
                    signal = f"{r.signal_percent}%" if r.signal_percent is not None else "?"
                    text = f"{tag} {r.ssid}{marker} — {signal} — {r.security}"
                    item = ListItem(Label(text), name=r.ssid)
                    item.set_class(r.saved, "-saved")
                    items.append(item)
                yield ListView(*items, id="net_list")

    def on_mount(self) -> None:
        try:
            self.query_one("#net_list", ListView).focus()
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        ssid = event.item.name
        result = next((r for r in self._results if r.ssid == ssid), None)
        if result is not None:
            self.dismiss((ssid, result.saved))

    def action_cancel(self) -> None:
        self.dismiss(None)
