from __future__ import annotations

from typing import Callable

import speedtest

from wifi_mapper.models import SpeedResult

ProgressCallback = Callable[[str], None]


def run_speedtest(on_progress: ProgressCallback | None = None) -> SpeedResult:
    """Run a full download/upload/ping test via speedtest.net. Blocking."""

    def report(stage: str) -> None:
        if on_progress:
            on_progress(stage)

    report("Finding best server...")
    st = speedtest.Speedtest()
    st.get_servers()
    st.get_best_server()

    report("Testing download...")
    st.download()

    report("Testing upload...")
    st.upload()

    results = st.results.dict()
    server = results.get("server", {})

    # speedtest-cli's latency probe falls back to a 3600ms-per-attempt sentinel
    # when it can't reach a server's latency endpoint, which averages out to
    # exactly 1,800,000ms when every attempt fails. A real round trip over
    # WiFi/broadband is never remotely close to that, so treat anything above
    # a generous ceiling as "ping unavailable" rather than storing it.
    ping_ms = results["ping"]
    if ping_ms is None or ping_ms > 5000:
        ping_ms = None

    return SpeedResult(
        download_mbps=results["download"] / 1_000_000,
        upload_mbps=results["upload"] / 1_000_000,
        ping_ms=ping_ms,
        server_name=server.get("name", "unknown"),
        server_sponsor=server.get("sponsor", "unknown"),
    )
