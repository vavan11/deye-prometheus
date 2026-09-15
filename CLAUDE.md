# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small, dependency-light Prometheus exporter for Deye hybrid solar inverters. It runs as a long-lived Python process — as a `systemd` service on a host, in Docker, or interactively for debugging.

Container files: `Dockerfile` (non-root UID/GID 10001, Debian security updates applied at build, pip and setuid bits removed, read-only-rootfs compatible, `/data` the only writable path for the cached cloud token), `docker-compose.yml` (applies that hardening), and `.dockerignore`. **`.dockerignore` is an allowlist** (`*` then `!*.py`, `!requirements.txt`) and the Dockerfile copies files explicitly — so if you add a runtime file that isn't a root-level `.py`, add a `!` line for it or the image will be missing it. Never loosen it to `COPY . .`: the working tree holds a live `.env`.

It has **two interchangeable scrape sources**, selected by `DEYE_SOURCE` (or `--source`), one per process:

- **`local`** (default) — Solarman V5 straight to the Wi-Fi data logger over TCP 8899 via `pysolarmanv5`. No cloud account. Exposes all 73 metrics.
- **`cloud`** — the Deye Cloud OpenAPI (`developer.deyecloud.com`). Needs an approved developer app, no LAN access. Exposes **39**: the 48 non-TOU metrics minus 9 the cloud has no key for (all L2/per-phase figures on this single-phase unit, both internal-CT powers, and `Alert`). The 25 time-of-use entries are *settings*, not telemetry, and aren't in `/device/latest` either.

**The invariant that matters: both sources emit identical `deye_*` metric names.** That is what lets `grafana/dashboard.json` work unchanged with either. It holds because `cloud_parameters.py` reuses the exact `name` strings from `parameters.py`, and `exporter._sanitize()` derives the metric name from that string. Changing a `name` in one file without the other silently forks the series.

## Commands

No build step, no test suite, no linter configured — this is a handful of plain scripts run directly with `python3`.

```bash
pip install -r requirements.txt        # exact pins, transitive deps included — bump deliberately, then rescan the image
cp .env.example .env                   # then fill in the local and/or cloud settings

python main.py                         # debug: read once, print all values, exit
python main.py --exporter              # start the Prometheus HTTP server (default :9105/metrics)
python main.py --source cloud          # same two modes against the cloud source
python main.py --source cloud --exporter
python main.py --list-devices          # cloud: find CLOUD_DEVICE_SN
python main.py --dump                  # cloud: measure-point inventory + mapping report
```

Requires **Python 3.10+** (`float | None` annotations are evaluated at import time).

`.env` (loaded by `config.py` via `python-dotenv`) is the only configuration surface, and it is gitignored — never hardcode real IPs, serials or credentials into the scripts. `.deye_token.json` (the cached cloud access token) is likewise gitignored.

- Shared: `DEYE_SOURCE`, `EXPORTER_PORT`, `POLL_INTERVAL` (default 60).
- Local: `INVERTER_IP`, `INVERTER_SERIAL` (the *logger's* serial), `INVERTER_PORT`, `INVERTER_MB_SLAVE_ID`.
- Cloud: `CLOUD_BASE_URL`, `CLOUD_APP_ID`, `CLOUD_APP_SECRET`, `CLOUD_EMAIL`, `CLOUD_PASSWORD`, `CLOUD_COMPANY_ID`, `CLOUD_DEVICE_SN` (the *inverter's* serial — a different value from `INVERTER_SERIAL`), `CLOUD_TOKEN_CACHE`, `CLOUD_EXPOSE_UNMAPPED`, `CLOUD_TIMEOUT`.

When deployed as a systemd service (see README for the full unit file), dependencies must be installed with the venv's full pip path (`/opt/deye-env/bin/pip install ...`), not from inside an activated venv — otherwise systemd's `ExecStart` picks up the wrong interpreter/packages.

## Architecture

`backends.py` defines a duck-typed contract that `exporter.py` drives, so the exporter never knows which source produced the numbers:

```
.name               "local" | "cloud"
.parameters         list[dict] with name / group / uom / help
.read_values()      dict[str, float] keyed by those `name` strings
.collection_time    epoch of the underlying reading, or None
.extra_descriptions help text for names not in .parameters (opt-in cloud keys)
```

### Local path
1. **`parameters.py`** — source of truth for local mode. A flat `PARAMETERS` list of dicts (73 numeric entries: 48 telemetry + 25 time-of-use, grouped by comment banner), each declaring a human name, register address(es), a decode `rule`, `scale`/`offset`/`mask`, and unit (`uom`). String-only registers (battery status, work mode, etc.) are deliberately omitted because Prometheus Gauges can't hold text — they still exist in `HA/deye_hybrid.yaml` (a Home Assistant register-map reference, not consumed by any code here).
2. **`inverter.py`** (`InverterClient.read_all`) — opens a fresh `PySolarmanV5` connection *per poll* (a deliberate fix, see git history: long-lived sockets went stale and caused flatlined metrics), reads the three hard-coded `REGISTER_BLOCKS` ranges in ≤100-register chunks, returns `{register_address: raw_value}`.
3. **`decoders.py`** (`decode(param, regs)`) — one `PARAMETERS` entry + raw registers → one float, applying the numeric `rule` (1=u16, 2=s16, 3=u32, 4=s32, 6=bitwise-OR, 9=u16 alias for time-of-use slots), then `(val - offset) * scale`. Returns `None` for string/unsupported rules.

### Cloud path
1. **`cloud_parameters.py`** — `CLOUD_PARAMETERS` maps a Deye Cloud measure-point `key` onto a metric `name` copied verbatim from `parameters.py`. Each entry may carry `alt_keys`, tried in order, because the same measurement is spelled differently across firmware revisions. Keys were captured from a real `--dump` (65 measure points, 58 reported). Deye uses **readable names** (`DCPowerPV1`, `BatteryVoltage`, `SOC`), not the SolarMAN-style short codes (`BMS_SOC`, `G_V_L1`) other clouds use — and three keys contain literal spaces or a stray hyphen: `"DC Temperature"`, `"AC Temperature"`, `"Temperature- Battery"`. Re-run `--dump` after a firmware update; a silently renamed key shows up there as an unmapped target. The comment banner at the foot of the file records which parameters have no cloud key **and why** — they are left absent rather than aliased onto an L1 reading, which would invent data.
2. **`cloud.py`** (`DeyeCloudClient`) — token lifecycle plus `latest()` / `device_list()` / `measure_points()`. Auth is `POST /account/token?appId=<id>` (appId is a **query** param) with a SHA-256-hex password; the token (~60 days) is cached to `CLOUD_TOKEN_CACHE` at mode `0600` so a `Restart=always` crash loop doesn't re-auth every few seconds. Every response carries a `success`/`code`/`msg` envelope that `_post()` checks before parsing, and an HTTP 401 or token-ish business code triggers exactly one silent re-auth + retry.
3. **`CloudBackend`** — applies `alt_keys` fallback and `scale`, skips non-numeric values (status text), and with `CLOUD_EXPOSE_UNMAPPED=true` emits unclaimed keys under the name `f"cloud {key}"` — which `_sanitize()` turns into `deye_cloud_<key>`, so they need no special case anywhere in `exporter.py`.

**Deye API quirk worth knowing:** on personal (non-organization) accounts `/device/list` rejects a valid token with `code=2101019 auth invalid token`, while `/account/info`, `/station/list` and `/device/latest` accept the very same token. `main.py --list-devices` catches this and falls back to `station_list()`. Don't "fix" it by re-authenticating — the token is fine; that endpoint wants an org-scoped one.

### Probes
**`health.py`** — `HealthState` (poll bookkeeping) plus a small threaded WSGI server that routes `/metrics` to prometheus_client and serves `/healthz` (alias `/livez`), `/readyz`, `/startupz`. The semantics are load-bearing, don't "simplify" them:
- `/startupz` passes once the first poll has **finished**, success or failure. Requiring success would get the container killed during an upstream outage at boot → CrashLoopBackOff, re-authenticating against Deye each restart.
- `/healthz` passes while the loop is still **attempting** polls. It must never depend on upstream reachability.
- `/readyz` is the only probe that requires a **successful** poll, within `PROBE_READY_MAX_AGE`.
- All ages use `time.monotonic()` — a wall-clock step (NTP on an RTC-less Raspberry Pi) must not look like a stall.
- Probe JSON never includes error text (it can carry the inverter IP or `appId`); only `last_poll_failed`.

`exporter.run()` installs SIGTERM/SIGINT handlers (main thread only) that exit immediately — as container PID 1, Python otherwise ignores SIGTERM and every stop waits for SIGKILL.

`config._secret()` lets the four `CLOUD_*` credentials be read from `<NAME>_FILE` (Docker/k8s secret files). Docker Compose interpolates `$` inside `env_file` values and `docker run --env-file` keeps quotes literally, so `_FILE` is the answer for credentials containing `$`.

### Exporter
**`exporter.py`** (`DeyeExporter(backend)`) — `setup_metrics()` creates one `Gauge` per `backend.parameters` entry (metric name is `deye_` + a sanitized lowercase `name`) plus `deye_up`, `deye_scrape_duration_seconds` and `deye_data_timestamp_seconds`; `collect()` re-reads and re-sets every gauge each poll, **lazily creating** a gauge for any name it hasn't seen (this is what lets opt-in cloud keys appear undeclared); `run()` starts the HTTP server and loops on `POLL_INTERVAL`, catching and logging (not raising) any poll error so one bad read doesn't kill the process — it only flips `deye_up` to 0; `print_once()` is the human-readable debug dump.

`deye_data_timestamp_seconds` exists because cloud data refreshes at the logger's upload cadence (~5 min), so identical values across 60s polls are normal, not a fault. Alert on its age rather than on flatlining.

### Adding metrics
- **Local:** add one dict to the right group in `parameters.py`; `exporter.py` and `decoders.py` pick it up automatically, provided the register falls inside one of `inverter.py`'s `REGISTER_BLOCKS` ranges (extend that list if not).
- **Cloud:** run `--dump`, find the key, add an entry to `cloud_parameters.py` whose `name` matches the `parameters.py` entry **exactly**.

Register definitions and decode rules are adapted from `StephanJoubert/home_assistant_solarman` (Apache-2.0); the Solarman V5 client itself is the third-party `pysolarmanv5` package — check upstream there before assuming a decoding bug is local to this repo. The cloud API shapes were taken from Deye's live OpenAPI spec at `https://eu1-developer.deyecloud.com/v2/api-docs` and their `DeyeCloudDevelopers/deye-openapi-client-sample-code` samples.

`grafana/dashboard.json` is an importable dashboard covering the exposed metrics; it isn't validated by any code and won't fail silently-wrong if metric names drift, so update it by hand when renaming/adding parameters. It references 46 metrics, all non-TOU — so cloud mode covers every panel. A quick check that a change hasn't broken it:

```bash
curl -s localhost:9105/metrics | grep -o '^deye_[a-z0-9_]*' | sort -u > /tmp/emitted.txt
grep -o 'deye_[a-z0-9_]*' grafana/dashboard.json | sort -u > /tmp/dash.txt
comm -13 /tmp/emitted.txt /tmp/dash.txt     # must be empty
```
