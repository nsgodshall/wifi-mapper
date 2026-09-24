# wifi-mapper

A terminal UI for measuring WiFi speed and signal strength at different
locations around a house, so you can build a map of dead zones and good
spots.

Each measurement records:

- **Signal strength** (dBm from `iw`, and quality % from NetworkManager) as
  a proxy for distance from your access point
- **Download / upload throughput** and **ping**, via a real
  [speedtest.net](https://www.speedtest.net) test (using the `speedtest-cli`
  library)
- **SSID** of the network you were on
- A **label** you type in, e.g. "Living Room", "Upstairs Bedroom", "Garage"

Data is stored in a local SQLite database and can be exported to CSV.

## Requirements

- Linux with NetworkManager (`nmcli`) and `iw` — both are used to read
  signal strength and to switch networks. (Already present on most
  NetworkManager-based distros, including Debian/Ubuntu desktop installs.)
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)

## Install & run

```bash
uv sync
uv run wifi-mapper
```

Or run as a module:

```bash
uv run python -m wifi_mapper
```

By default the database lives at `~/.local/share/wifi-mapper/measurements.db`.
Override with `--db`:

```bash
uv run wifi-mapper --db ./my-house.db
```

## Using it

Walk to a location in your house, then:

1. Press **`n`** — type a label for where you're standing (e.g. "Basement"),
   then hit Enter / "Start test". The app captures your current network's
   signal strength and runs a full download/upload/ping test. This takes
   10–30 seconds depending on your connection.
2. Move to the next spot and repeat.

If you want to test a different network (e.g. comparing a 2.4GHz vs 5GHz
SSID, or a mesh node) press **`s`** to scan and switch networks. Saved
connections switch immediately; new networks prompt for a password if
they're secured.

| Key | Action |
|-----|--------|
| `n` | Start a new measurement (prompts for a label) |
| `s` | Scan for and switch to a different WiFi network |
| `r` | Refresh the current network/signal display |
| `e` | Export all measurements to a timestamped CSV file |
| `d` | Delete the highlighted measurement (with confirmation) |
| `q` | Quit |

## Notes & caveats

- **Ping**: the `speedtest-cli` library occasionally can't reach a server's
  latency endpoint (flaky network, corporate proxy, restrictive firewall)
  and falls back to a nonsense placeholder value. wifi-mapper detects this
  and records ping as unavailable (`n/a`) rather than storing garbage —
  download/upload figures are unaffected.
- **Passwords**: when connecting to a new (unsaved) secured network,
  wifi-mapper passes the password to `nmcli` as a command-line argument,
  which is briefly visible to other processes on the machine via the
  process list (`ps`). This is a limitation of `nmcli` itself. Prefer
  connecting to networks you've already saved via your system's network
  settings when possible.
- **Signal strength as distance proxy**: signal strength depends on walls,
  interference, and AP placement, not just straight-line distance — treat
  it as a relative "how good is it here" number rather than a precise
  distance measurement.

## Project layout

```
src/wifi_mapper/
  models.py            dataclasses for measurements/status/scan results
  storage.py            SQLite persistence + CSV export
  wifi.py                nmcli/iw wrappers: status, scanning, connecting
  speedtest_runner.py    speedtest-cli wrapper
  screens.py              Textual modal screens (label, confirm, network picker, password)
  app.py                   main Textual App
  __init__.py               CLI entry point (argparse)
```
