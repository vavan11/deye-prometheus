"""
exporter.py — Prometheus metrics setup, collection loop and debug print mode.

Backend-agnostic: it drives whatever object it is handed (see backends.py), so the
same gauges are produced whether the numbers came from the LAN or from Deye Cloud.
"""
import re
import signal
import sys
import threading
import time

from prometheus_client import Gauge

from config import (
    EXPORTER_BIND,
    EXPORTER_PORT,
    POLL_INTERVAL,
    PROBE_LIVE_MAX_STALL,
    PROBE_READY_MAX_AGE,
)
from health import HealthState, serve


def _exit_on_signal(signum, _frame) -> None:
    print(f"[deye-exporter] Received {signal.Signals(signum).name}, shutting down")
    sys.exit(0)


def _sanitize(name: str) -> str:
    """Convert a human-readable parameter name to a valid Prometheus metric name."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return "deye_" + name


class DeyeExporter:
    """Sets up and runs the Prometheus metrics exporter for a given backend."""

    def __init__(self, backend):
        self.backend = backend
        self.gauges: dict[str, Gauge] = {}
        self._metric_owners: dict[str, str] = {}   # sanitized metric name -> owning name
        self._warned_collisions: set[str] = set()
        self.up = None
        self.scrape_duration = None
        self.data_timestamp = None

    def _ensure_gauge(self, name: str, description: str = "") -> Gauge | None:
        """
        Create a gauge for `name` on first sight. Lets opt-in cloud keys appear un-declared.

        Returns None if some other name already claimed the same sanitized metric name.
        Distinct API keys can collide once sanitized ("Gen V" and "Gen_V" both become
        deye_cloud_gen_v); registering the second would raise DuplicateTimeseries and,
        because collect() runs on every poll, would stop the exporter updating anything.
        """
        gauge = self.gauges.get(name)
        if gauge is not None:
            return gauge

        metric_name = _sanitize(name)
        owner = self._metric_owners.get(metric_name)
        if owner is not None:
            if metric_name not in self._warned_collisions:
                self._warned_collisions.add(metric_name)
                print(f"[deye-exporter] Skipping {name!r}: metric name {metric_name} "
                      f"is already used by {owner!r}")
            return None

        gauge = Gauge(metric_name, description or name)
        self.gauges[name] = gauge
        self._metric_owners[metric_name] = name
        return gauge

    def setup_metrics(self) -> None:
        """Register every parameter the backend declares, plus the exporter's own health gauges."""
        for p in self.backend.parameters:
            uom = p.get("uom", "")
            description = p.get("help", p["name"])
            if uom:
                description += f" [{uom}]"
            self._ensure_gauge(p["name"], description)

        self.up = Gauge("deye_up", "1 if the last poll succeeded, 0 otherwise")
        self.scrape_duration = Gauge(
            "deye_scrape_duration_seconds", "Time the last poll took [s]"
        )
        # Cloud data is only as fresh as the logger's last upload (typically ~5 min),
        # so expose the reading's own timestamp rather than letting it look like a flatline.
        self.data_timestamp = Gauge(
            "deye_data_timestamp_seconds",
            "Epoch timestamp of the underlying reading (cloud collectionTime) [s]",
        )

    def collect(self) -> None:
        """Poll the backend and update all gauges."""
        started = time.monotonic()
        values = self.backend.read_values()

        for name, value in values.items():
            gauge = self.gauges.get(name)
            if gauge is None:
                gauge = self._ensure_gauge(name, self.backend.extra_descriptions.get(name, name))
            if gauge is not None:
                gauge.set(value)

        if self.scrape_duration is not None:
            self.scrape_duration.set(time.monotonic() - started)
        if self.data_timestamp is not None and self.backend.collection_time:
            self.data_timestamp.set(self.backend.collection_time)

    def run(self) -> None:
        """Start the HTTP server (metrics + probes) and enter the polling loop."""
        self.health = HealthState(
            source=self.backend.name,
            poll_interval=POLL_INTERVAL,
            ready_max_age=PROBE_READY_MAX_AGE,
            live_max_stall=PROBE_LIVE_MAX_STALL,
        )
        httpd = serve(self.health, EXPORTER_PORT, EXPORTER_BIND)
        print(f"[deye-exporter] Listening on {EXPORTER_BIND}:{EXPORTER_PORT} "
              f"— /metrics /healthz /readyz /startupz")
        print(f"[deye-exporter] Source: {self.backend.name}")
        print(f"[deye-exporter] Exposing {len(self.gauges)} gauges — polling every {POLL_INTERVAL}s\n")

        # As PID 1 in a container, Python has no SIGTERM handler and the kernel ignores
        # default-action signals for PID 1 — so `docker stop` / a pod termination would
        # hang for the full grace period and end in SIGKILL. Exit promptly instead, even
        # mid-poll (SystemExit is not caught by the `except Exception` below).
        # signal.signal() only works from the main thread; skip it when embedded.
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, _exit_on_signal)

        try:
            while True:
                self.health.record_attempt()
                try:
                    self.collect()
                    if self.up is not None:
                        self.up.set(1)
                    self.health.record_success()
                except Exception as exc:
                    if self.up is not None:
                        self.up.set(0)
                    self.health.record_failure(str(exc))
                    print(f"[deye-exporter] Poll error: {exc}")
                time.sleep(POLL_INTERVAL)
        finally:
            httpd.shutdown()
            httpd.server_close()
            print("[deye-exporter] Stopped")

    def print_once(self) -> None:
        """Debug mode: read once and print all values to stdout."""
        values = self.backend.read_values()
        print(f"\n─── DEYE INVERTER SNAPSHOT (source: {self.backend.name}) ────────────────")
        current_group = None
        for p in self.backend.parameters:
            if p.get("group") != current_group:
                current_group = p.get("group", "")
                print(f"\n  [{current_group.upper()}]")
            value = values.get(p["name"])
            uom = p.get("uom", "")
            if value is None:
                print(f"    {p['name']:35} {'(no value)':>12}")
            else:
                print(f"    {p['name']:35} {value:>12.3f}  {uom}")

        extras = {n: v for n, v in values.items() if n.startswith("cloud ")}
        if extras:
            print("\n  [UNMAPPED CLOUD KEYS]")
            for name, value in sorted(extras.items()):
                print(f"    {name[len('cloud '):]:35} {value:>12.3f}")

        if self.backend.collection_time:
            age = time.time() - self.backend.collection_time
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.backend.collection_time))
            print(f"\n  Reading collected {stamp} ({age:.0f}s ago)")
        print("\n────────────────────────────────────────────────────────────────\n")
