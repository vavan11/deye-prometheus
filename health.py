"""
health.py — Kubernetes probe endpoints served alongside /metrics.

Three probes with deliberately different semantics:

  /startupz   Has the first poll *finished* — successfully or not?
              Lets a slow first scrape finish without liveness killing the pod. It must
              not require success: a failing startup probe gets the container killed, so
              an outage at boot would become a CrashLoopBackOff that re-authenticates
              against Deye Cloud on every restart. Readiness reports the failure instead.

  /readyz     Did a poll succeed recently?
              Goes 503 during a Deye Cloud outage or an unreachable inverter, so the
              pod leaves the Service endpoints — but is NOT restarted.

  /healthz    Is the poll loop still ticking?
              Only fails if the loop stopped *attempting* (deadlocked thread, wedged
              socket). It deliberately ignores whether polls succeed.

That last distinction is the important one: liveness must not depend on an upstream
being reachable. If /healthz failed whenever Deye Cloud was down, Kubernetes would
crash-loop a perfectly healthy pod for an outage it cannot fix by restarting.

All ages are measured on the monotonic clock. A wall-clock step — NTP syncing on a
Raspberry Pi that booted with no RTC, say — would otherwise make a healthy loop look
stalled for days and get the pod restarted.
"""
import json
import threading
import time
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from prometheus_client import make_wsgi_app


class HealthState:
    """Mutable poll state shared between the poll loop and the probe handlers."""

    def __init__(self, source: str, poll_interval: int,
                 ready_max_age: int, live_max_stall: int):
        self.source = source
        self.poll_interval = poll_interval
        self.ready_max_age = ready_max_age
        self.live_max_stall = live_max_stall

        # Monotonic timestamps — only ever subtracted from each other, never shown.
        self.started_at = time.monotonic()
        self.last_attempt_at: float | None = None
        self.last_success_at: float | None = None
        self.first_completed_at: float | None = None
        self.last_error: str | None = None
        self.poll_count = 0
        self.failure_count = 0

    # ── called by the poll loop ────────────────────────────────────────────────

    def record_attempt(self) -> None:
        self.last_attempt_at = time.monotonic()
        self.poll_count += 1

    def _record_completed(self, now: float) -> None:
        if self.first_completed_at is None:
            self.first_completed_at = now

    def record_success(self) -> None:
        now = time.monotonic()
        self.last_success_at = now
        self._record_completed(now)
        self.last_error = None

    def record_failure(self, error: str) -> None:
        self._record_completed(time.monotonic())
        self.last_error = error
        self.failure_count += 1

    # ── probe predicates ───────────────────────────────────────────────────────

    def startup_ok(self) -> tuple[bool, str]:
        if self.first_completed_at is None:
            return False, "waiting for first poll to finish"
        return True, "started"

    def ready_ok(self) -> tuple[bool, str]:
        if self.last_success_at is None:
            return False, "no successful poll yet"
        age = time.monotonic() - self.last_success_at
        if age > self.ready_max_age:
            return False, f"last successful poll {age:.0f}s ago (max {self.ready_max_age}s)"
        return True, f"last successful poll {age:.0f}s ago"

    def live_ok(self) -> tuple[bool, str]:
        # Before the first attempt, fall back to process start so a slow first poll
        # doesn't look like a stall.
        reference = self.last_attempt_at or self.started_at
        stall = time.monotonic() - reference
        if stall > self.live_max_stall:
            return False, f"poll loop stalled {stall:.0f}s (max {self.live_max_stall}s)"
        return True, f"poll loop active, last attempt {stall:.0f}s ago"

    def snapshot(self) -> dict:
        now = time.monotonic()
        return {
            "source": self.source,
            "uptime_seconds": round(now - self.started_at, 1),
            "poll_interval_seconds": self.poll_interval,
            "polls": self.poll_count,
            "failures": self.failure_count,
            "last_attempt_age_seconds": (
                round(now - self.last_attempt_at, 1) if self.last_attempt_at else None),
            "last_success_age_seconds": (
                round(now - self.last_success_at, 1) if self.last_success_at else None),
            # Only whether the last poll failed — never the message. Probe endpoints are
            # unauthenticated, and error text can carry the inverter IP or the appId from
            # a request URL. The full error is already written to the container log.
            "last_poll_failed": self.last_error is not None,
        }


def _json_response(start_response, ok: bool, probe: str, detail: str, state: HealthState):
    status = "200 OK" if ok else "503 Service Unavailable"
    body = json.dumps(
        {"probe": probe, "status": "ok" if ok else "unavailable", "detail": detail,
         **state.snapshot()},
        indent=2,
    ).encode() + b"\n"
    start_response(status, [("Content-Type", "application/json"),
                            ("Content-Length", str(len(body)))])
    return [body]


def make_app(state: HealthState):
    """Build a WSGI app serving /metrics plus the three probe endpoints."""
    metrics_app = make_wsgi_app()

    routes = {
        "/healthz":  ("liveness",  state.live_ok),
        "/livez":    ("liveness",  state.live_ok),
        "/readyz":   ("readiness", state.ready_ok),
        "/startupz": ("startup",   state.startup_ok),
    }

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/").rstrip("/") or "/"

        if path in ("/metrics", "/"):
            if path == "/":
                body = (b"deye-prometheus exporter\n"
                        b"/metrics  /healthz  /readyz  /startupz\n")
                start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"),
                                          ("Content-Length", str(len(body)))])
                return [body]
            return metrics_app(environ, start_response)

        route = routes.get(path)
        if route is not None:
            probe, check = route
            ok, detail = check()
            return _json_response(start_response, ok, probe, detail, state)

        body = b"not found\n"
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8"),
                                         ("Content-Length", str(len(body)))])
        return [body]

    return app


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Threaded so a slow probe can't block a concurrent /metrics scrape."""
    daemon_threads = True
    # Allow immediate rebind after a restart instead of waiting out TIME_WAIT.
    allow_reuse_address = True


class _QuietHandler(WSGIRequestHandler):
    """
    Suppress per-request logging — probes every few seconds would flood the container
    log. This also skips the reverse-DNS lookup, which only happens in address_string()
    when a request is logged.
    """

    def log_message(self, format, *args):
        pass


def serve(state: HealthState, port: int, addr: str = "0.0.0.0"):
    """Start the HTTP server in a daemon thread and return it."""
    httpd = make_server(addr, port, make_app(state),
                        server_class=_ThreadingWSGIServer,
                        handler_class=_QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True,
                              name="deye-http")
    thread.start()
    return httpd
