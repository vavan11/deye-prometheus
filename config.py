"""
config.py — Load inverter, cloud and exporter settings from the .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _secret(name: str, default: str = "") -> str:
    """
    Read a credential from NAME_FILE if set, else from NAME.

    The *_FILE form is how Docker secrets and Kubernetes secret volumes are consumed:
    the value lives in a mounted file rather than an environment variable, which
    `docker inspect` and /proc/<pid>/environ would expose.
    """
    path = os.getenv(f"{name}_FILE")
    if not path:
        return os.getenv(name, default)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            # Strip only the trailing newline editors and `echo` add, not other whitespace
            # that could legitimately be part of a password.
            return fh.read().rstrip("\r\n")
    except OSError as exc:
        raise SystemExit(f"error: {name}_FILE={path} could not be read: {exc.strerror}")

# ── Scrape source ──────────────────────────────────────────────────────────────
# "local" = Solarman V5 over LAN (default), "cloud" = Deye Cloud OpenAPI
DEYE_SOURCE          = os.getenv("DEYE_SOURCE", "local").strip().lower()

# ── Local (Solarman V5 / Modbus) ───────────────────────────────────────────────
INVERTER_IP          = os.getenv("INVERTER_IP", "192.168.0.6")
INVERTER_SERIAL      = int(os.getenv("INVERTER_SERIAL", "0"))
INVERTER_PORT        = int(os.getenv("INVERTER_PORT", "8899"))
INVERTER_MB_SLAVE_ID = int(os.getenv("INVERTER_MB_SLAVE_ID", "1"))

# ── Cloud (Deye Cloud OpenAPI) ─────────────────────────────────────────────────
# App credentials come from https://developer.deyecloud.com/app (manual approval).
# CLOUD_DEVICE_SN is the *inverter* serial from /device/list — NOT INVERTER_SERIAL,
# which is the Wi-Fi logger's serial used by pysolarmanv5.
CLOUD_BASE_URL        = os.getenv("CLOUD_BASE_URL", "https://eu1-developer.deyecloud.com/v1.0").rstrip("/")
# Each of these four also accepts a <NAME>_FILE variant (see _secret above).
CLOUD_APP_ID          = _secret("CLOUD_APP_ID")
CLOUD_APP_SECRET      = _secret("CLOUD_APP_SECRET")
CLOUD_EMAIL           = _secret("CLOUD_EMAIL")
CLOUD_PASSWORD        = _secret("CLOUD_PASSWORD")
CLOUD_COMPANY_ID      = os.getenv("CLOUD_COMPANY_ID", "0")
CLOUD_DEVICE_SN       = os.getenv("CLOUD_DEVICE_SN", "")
CLOUD_DEVICE_TYPE     = os.getenv("CLOUD_DEVICE_TYPE", "INVERTER")
CLOUD_TOKEN_CACHE     = os.getenv("CLOUD_TOKEN_CACHE", ".deye_token.json")
CLOUD_EXPOSE_UNMAPPED = os.getenv("CLOUD_EXPOSE_UNMAPPED", "false").strip().lower() == "true"
CLOUD_TIMEOUT         = int(os.getenv("CLOUD_TIMEOUT", "20"))
# Time-of-use settings come from a separate endpoint (/config/tou) and change rarely, so
# they get their own slow timer rather than riding the telemetry poll. Deye publishes no
# rate limit, but there is nothing to gain from re-fetching settings every minute.
# 0 disables TOU scraping entirely.
CLOUD_TOU_INTERVAL    = int(os.getenv("CLOUD_TOU_INTERVAL", "900"))

# ── Exporter ───────────────────────────────────────────────────────────────────
EXPORTER_PORT        = int(os.getenv("EXPORTER_PORT", "9105"))
# 0.0.0.0 so probes and scrapes reach it inside a container; set 127.0.0.1 on a bare
# host where Prometheus runs locally.
EXPORTER_BIND        = os.getenv("EXPORTER_BIND", "0.0.0.0")
POLL_INTERVAL        = int(os.getenv("POLL_INTERVAL", "60"))

# ── Probes (/readyz, /healthz) ─────────────────────────────────────────────────
# Readiness fails when no poll has *succeeded* for this long — covers 2 missed polls
# plus a margin, so one transient failure doesn't flap the pod out of the Service.
PROBE_READY_MAX_AGE  = int(os.getenv("PROBE_READY_MAX_AGE", str(max(POLL_INTERVAL * 3, 180))))
# Liveness fails only when the loop stops *attempting* polls for this long. Must stay
# comfortably above POLL_INTERVAL + CLOUD_TIMEOUT or a slow poll looks like a hang.
PROBE_LIVE_MAX_STALL = int(os.getenv("PROBE_LIVE_MAX_STALL", str(max(POLL_INTERVAL * 5, 300))))
