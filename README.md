# Deye Inverter Prometheus Exporter

A lightweight **Prometheus metrics exporter** for Deye hybrid solar inverters,
with **two interchangeable scrape sources**:

| Source | How it reads | Metrics | Needs |
|--------|--------------|---------|-------|
| `local` *(default)* | Solarman V5 over local TCP (port 8899) | **73** | Same LAN as the inverter |
| `cloud` | [Deye Cloud OpenAPI](https://developer.deyecloud.com/api) | **64** | Internet + a Deye developer app |

Both emit **identical `deye_*` metric names**, so `grafana/dashboard.json` works with
either one — no query edits. Only one source runs per process; pick it with `DEYE_SOURCE`.
Cloud mode covers 38 of the dashboard's 46 metrics; see
[what cloud mode can't provide](#what-cloud-mode-cant-provide).

> ✅ **Tested on: Deye SUN-3K-SG04LP1-24-EU-SM1 Hybrid Inverter**  
> May also work on other Deye/Sunsynk/SolArk hybrid models that share the same register map.

---

## ✨ Features

- **73 Prometheus metrics** — solar, battery, grid, load, inverter temps, time-of-use
- **Two scrape sources** — local Modbus *or* the Deye Cloud API, same metric names either way
- **No cloud dependency in local mode** — talks straight to the Wi-Fi data logger on your LAN
- **Secrets in `.env`** — credentials, IP and serial numbers never touch your code
- **Grafana dashboard** — import `grafana/dashboard.json` for an instant visual overview
- **Debug mode** — run once without Prometheus to print all live values

---

## 📁 Project Structure

```
Deye-exporter/
├── .env.example        ← copy to .env and fill in your values
├── .gitignore
├── main.py             ← entry point
├── config.py           ← loads settings from .env
├── decoders.py         ← register decode logic (s16, s32, u32, ...)
├── parameters.py       ← all 73 metric definitions (local/register source of truth)
├── inverter.py         ← PySolarmanV5 client        (local source)
├── cloud.py            ← Deye Cloud API client      (cloud source)
├── cloud_parameters.py ← cloud key → metric name map (cloud source)
├── backends.py         ← the two sources behind one interface
├── health.py           ← /healthz /readyz /startupz probe endpoints
├── exporter.py         ← Prometheus Gauge setup + polling loop
├── requirements.txt
├── Dockerfile          ← non-root, read-only-rootfs image
├── docker-compose.yml  ← hardened Compose deployment
├── .dockerignore       ← allowlist: keeps secrets out of the image
├── grafana/
│   └── dashboard.json  ← importable Grafana dashboard
└── HA/
    └── deye_hybrid.yaml ← full register map (Home Assistant reference)
```

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/vavan11/deye-prometheus.git
cd deye-prometheus
cp .env.example .env
```

Edit `.env` and fill in your inverter details:

```env
DEYE_SOURCE=local              # "local" (LAN) or "cloud" (Deye Cloud API)
INVERTER_IP=192.168.1.100      # IP of the Solarman Wi-Fi data logger
INVERTER_SERIAL=1234567890     # Serial number shown in the logger web UI
INVERTER_PORT=8899
INVERTER_MB_SLAVE_ID=1
EXPORTER_PORT=9105
POLL_INTERVAL=60
```

> **Finding your serial:** Open `http://<logger-ip>` in a browser (login: `admin`/`admin`),  
> then expand "Device Information" → copy the **Device serial number**.

For cloud mode see [Cloud source](#️-cloud-source-deye-cloud-api) below.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

**Debug mode** (print all values once):
```bash
python main.py
```

**Exporter mode** (start Prometheus endpoint):
```bash
python main.py --exporter
```

Metrics are available at: `http://localhost:9105/metrics`

---

## ☁️ Cloud source (Deye Cloud API)

Reads the same measurements from Deye's servers instead of the LAN — useful when the
exporter can't reach the inverter's network.

### 1. Get API credentials

Register at [developer.deyecloud.com](https://developer.deyecloud.com/app) and create an
app to get an **App ID** and **App Secret**. Approval is manual and can take a few days.

### 2. Configure

```env
DEYE_SOURCE=cloud
CLOUD_BASE_URL=https://eu1-developer.deyecloud.com/v1.0   # us1- for the Americas
CLOUD_APP_ID=your-app-id
CLOUD_APP_SECRET=your-app-secret
CLOUD_EMAIL=you@example.com
CLOUD_PASSWORD=your-deyecloud-password
CLOUD_DEVICE_SN=                                          # see below
POLL_INTERVAL=60
```

The password is **SHA-256 hashed before it leaves the machine** — it is never sent in
plaintext. The access token (~60 day lifetime) is cached in `.deye_token.json`
(gitignored, mode `0600`) so restarts don't re-authenticate.

### 3. Find your device serial

```bash
python main.py --list-devices
```

> ⚠️ `CLOUD_DEVICE_SN` is the **inverter's** serial and is a *different value* from
> `INVERTER_SERIAL`, which is the Wi-Fi **logger's** serial used by local mode.

> **Known Deye quirk:** on personal (non-organization) accounts, `/device/list` rejects
> an otherwise-valid token with `code=2101019 auth invalid token`, even though
> `/account/info`, `/station/list` and the `/device/latest` endpoint the exporter
> actually uses all accept the same token. `--list-devices` detects this and falls back
> to listing your stations; read the inverter SN from the Deye Cloud app
> (Device → Inverter → SN) and confirm it with `--dump`.

### 4. Verify the key mapping

Deye Cloud identifies each measurement by a key such as `BMS_SOC` or `G_V_L1`, and
**the exact key set varies by inverter model and firmware**. `cloud_parameters.py`
ships with candidate keys; confirm them against your own inverter:

```bash
python main.py --source cloud --dump
```

This prints every measure point the inverter reports, which metrics are still unmapped,
and which returned keys nothing claims yet — edit `cloud_parameters.py` from its output
until the unmapped list is empty.

### 5. Run

```bash
python main.py --source cloud              # one-shot snapshot
python main.py --source cloud --exporter   # exporter on :9105
```

### What cloud mode can't provide

`/device/latest` returns what the inverter reports, which is not a superset of the local
register map. On a single-phase unit these 9 metrics have no cloud equivalent and are
**absent** (not zero — the series simply doesn't appear):

| Missing | Why |
|---------|-----|
| `deye_grid_voltage_l2`, `deye_grid_current_l2`, `deye_current_l2`, `deye_inverter_l2_power`, `deye_load_l2_power`, `deye_external_ct_l2_power` | Single-phase inverter — the cloud reports one combined `…L1L2` figure per measurement; there is no second phase |
| `deye_internal_ct_l1_power`, `deye_internal_ct_l2_power` | Only the external CT is exposed; the internal CT is local-register only |
| `deye_alert` | No fault/alarm bitmask key is returned |

8 of these appear on the bundled dashboard, so those panels stay empty in cloud mode.
They are deliberately **not** aliased onto the L1 readings — that would invent data the
inverter doesn't report. `python main.py --dump` re-checks this against your own unit.

### Notes

- **Cloud data is not real-time.** The logger uploads roughly every 5 minutes, so a 60s
  poll often returns unchanged values. `deye_data_timestamp_seconds` exposes the
  reading's true age — alert on
  `time() - deye_data_timestamp_seconds > 900` rather than assuming freshness.
- **Time-of-Use settings are scraped too.** The 25 `deye_time_of_use_*` gauges don't come
  from `/device/latest` — they have their own read-only endpoint, `/v1.0/config/tou`, polled
  on a slower timer (`CLOUD_TOU_INTERVAL`, default 900s) because they change rarely.
  `deye_tou_timestamp_seconds` shows when they were last read. A failure there is logged and
  the previous values are kept: it never fails the telemetry poll or flips `deye_up`.
- Set `CLOUD_EXPOSE_UNMAPPED=true` to also expose measure points that have no local
  equivalent, as `deye_cloud_<key>` gauges.

---

## 🔧 Run as a systemd Service (Linux)

This lets the exporter start automatically on boot and restart on failure.

### 1. Create a virtual environment

```bash
python3 -m venv /opt/deye-env
```

### 2. Install dependencies into the venv

> ⚠️ Common mistake: running `pip install` while inside an activated venv installs to the **wrong place** when systemd runs the service. Always use the full path to pip.

```bash
/opt/deye-env/bin/pip install -r /root/deye-prometheus/requirements.txt
```

### 3. Set up your `.env`

```bash
cp /root/deye-prometheus/.env.example /root/deye-prometheus/.env
nano /root/deye-prometheus/.env   # fill in your real IP and serial
```

### 4. Create the service file

```bash
nano /etc/systemd/system/deye-exporter.service
```

Paste this:

```ini
[Unit]
Description=Deye Inverter Prometheus Exporter
After=network.target

[Service]
User=root
WorkingDirectory=/root/deye-prometheus
ExecStart=/opt/deye-env/bin/python /root/deye-prometheus/main.py --exporter
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/root/deye-prometheus/.env

[Install]
WantedBy=multi-user.target
```

### 5. Enable and start

```bash
systemctl daemon-reload
systemctl enable deye-exporter   # start on boot
systemctl start deye-exporter
```

### 6. Check logs

```bash
journalctl -u deye-exporter -f
```

You should see:
```
[deye-exporter] Prometheus metrics running on :9105/metrics
[deye-exporter] Source: local
[deye-exporter] Exposing 73 gauges — polling every 60s
```

> To run the cloud source under systemd, either set `DEYE_SOURCE=cloud` in the
> `EnvironmentFile`, or append `--source cloud` to `ExecStart`.

---

## 🐳 Docker

The image is built for public use:

- **Non-root** — runs as UID/GID `10001`; no root at runtime
- **Patched** — Debian security updates are applied at build time (upstream `python:*-slim` tags lag Debian's fixes)
- **No pip, no setuid binaries** — pip is removed from the base image and the venv; setuid/setgid bits are stripped
- **Pinned dependencies** — every package in `requirements.txt`, transitive ones included, is an exact version
- **Random-UID friendly** — `/data` is group-0 writable, so OpenShift-style arbitrary UIDs work
- **Read-only root filesystem** and **all Linux capabilities dropped** — `/data` (the cached cloud token) is the only writable path
- **Secrets never enter the image** — `.dockerignore` is an *allowlist*: only `*.py` and `requirements.txt` reach the build context, so a stray `.env.prod`, `*.pem` or token dump can't end up in a layer
- **Stops cleanly** — handles `SIGTERM` as PID 1, so `docker stop` and pod termination are instant rather than waiting for `SIGKILL`
- **Kubernetes probes** — `/healthz`, `/readyz`, `/startupz` (see below)

### Docker Compose (recommended)

```bash
cp .env.example .env        # fill in your settings
docker compose up -d
curl localhost:9105/metrics
```

[docker-compose.yml](docker-compose.yml) applies the full hardening (non-root, read-only,
`cap_drop: ALL`, `no-new-privileges`, 128M memory limit, log rotation) and points the token
cache at the `/data` volume. Idle memory use is about 30 MiB.

### Plain `docker run`

```bash
docker build -t deye-exporter .

docker run -d --name deye-exporter \
  --env-file .env \
  -e CLOUD_TOKEN_CACHE=/data/token.json \
  -p 9105:9105 \
  -v deye-data:/data \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --restart unless-stopped \
  deye-exporter
```

`-e CLOUD_TOKEN_CACHE=/data/token.json` matters: the `.env.example` default resolves inside
the read-only `/app`. Without it the exporter still works, but logs a warning and
re-authenticates on every restart.

One-shot tools use the same entrypoint:

```bash
docker run --rm --env-file .env deye-exporter --source cloud    # snapshot
docker run --rm --env-file .env deye-exporter --dump            # measure-point inventory
docker run --rm --env-file .env deye-exporter --list-devices
```

### ⚠️ `.env` values: `$` and quotes

One `.env` file is read three different ways, and they disagree:

| Line in `.env` | python-dotenv (bare host) | `docker compose` | `docker run --env-file` |
|---|---|---|---|
| `PW=abc$def` | `abc$def` | **`abc`** — silently truncated | `abc$def` |
| `PW="abc"` | `abc` | `abc` | **`"abc"`** — quotes kept |

So: **never quote values**, and if a credential contains `$`, supply it with a `_FILE`
secret (below) — file contents are never interpolated.

### Docker secrets (credentials out of the environment)

Environment variables are visible to `docker inspect` and in `/proc/<pid>/environ`.
Each of `CLOUD_APP_ID`, `CLOUD_APP_SECRET`, `CLOUD_EMAIL` and `CLOUD_PASSWORD` also
accepts a `<NAME>_FILE` variant pointing at a mounted file:

```yaml
services:
  deye-exporter:
    # ...as in docker-compose.yml, but with the credentials removed from .env
    environment:
      CLOUD_TOKEN_CACHE: /data/token.json
      CLOUD_APP_SECRET_FILE: /run/secrets/deye_app_secret
      CLOUD_PASSWORD_FILE: /run/secrets/deye_password
    secrets: [deye_app_secret, deye_password]

secrets:
  deye_app_secret:
    file: ./secrets/app_secret.txt
  deye_password:
    file: ./secrets/password.txt
```

A trailing newline in the file is stripped; everything else is taken literally.

### Local source in Docker

For `DEYE_SOURCE=local` the container must reach the inverter's Wi-Fi logger on port 8899.
Bridge networking usually can; if the logger is on a subnet the container can't route to,
use `network_mode: host` (Linux only).

### Multi-arch

All dependencies are pure Python, so the image builds for any platform — including a
Raspberry Pi:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t you/deye-exporter:latest --push .
```

## ☸️ Kubernetes probes

The exporter serves three probe endpoints next to `/metrics`, each returning `200` or `503`
with a JSON body:

| Endpoint | Probe | Passes when | On failure |
|---|---|---|---|
| `/startupz` | startup | the first poll has **finished** — success *or* failure | container killed |
| `/healthz` (alias `/livez`) | liveness | the poll loop is still **attempting** polls | container restarted |
| `/readyz` | readiness | a poll **succeeded** within `PROBE_READY_MAX_AGE` | removed from Service endpoints |

The semantics are deliberate — **only readiness depends on Deye Cloud or the inverter being
reachable.** An upstream outage is not something a restart can fix, so it must never fail
startup or liveness: that would turn a Deye outage into a CrashLoopBackOff that
re-authenticates against your account on every restart. Liveness only fails if the loop
itself wedges (a hung socket, a deadlock).

All ages use the monotonic clock, so an NTP step — common on a Raspberry Pi without an RTC —
can't make a healthy pod look stalled.

Probe bodies never include error messages (they can contain the inverter IP or the cloud
`appId`); the full error is in the container log.

```yaml
containers:
  - name: deye-exporter
    image: you/deye-exporter:latest
    ports:
      - { name: metrics, containerPort: 9105 }
    env:
      - { name: CLOUD_TOKEN_CACHE, value: /data/token.json }
    envFrom:
      - secretRef: { name: deye-exporter }        # CLOUD_APP_ID, CLOUD_PASSWORD, ...
    startupProbe:
      httpGet: { path: /startupz, port: metrics }
      periodSeconds: 10
      failureThreshold: 30      # 5 min for the first poll: worst case ~2 min (local socket timeouts)
    livenessProbe:
      httpGet: { path: /healthz, port: metrics }
      periodSeconds: 30
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet: { path: /readyz, port: metrics }
      periodSeconds: 15
      timeoutSeconds: 5
      failureThreshold: 2
    resources:
      requests: { cpu: 10m, memory: 48Mi }
      limits:   { memory: 128Mi }
    securityContext:
      runAsNonRoot: true
      runAsUser: 10001
      runAsGroup: 10001
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
      capabilities: { drop: [ALL] }
      seccompProfile: { type: RuntimeDefault }
    volumeMounts:
      - { name: data, mountPath: /data }
volumes:
  - name: data
    emptyDir: {}                # survives container restarts; the token is re-fetched on reschedule
```

Tuning (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `PROBE_READY_MAX_AGE` | `max(3 × POLL_INTERVAL, 180)` | seconds without a successful poll before `/readyz` fails |
| `PROBE_LIVE_MAX_STALL` | `max(5 × POLL_INTERVAL, 300)` | seconds without a poll *attempt* before `/healthz` fails |
| `EXPORTER_BIND` | `0.0.0.0` | listen address — `127.0.0.1` on a bare host with local Prometheus |

> **Readiness trade-off:** if Prometheus scrapes *through a Service*, a NotReady pod drops
> out of its endpoints — so during an outage `deye_up` stops being scraped at all, and an
> alert on `deye_up == 0` won't fire. Scrape the pod directly (pod-level service discovery
> or scrape annotations) and alert on `absent(deye_up)` as well.

## 📊 Prometheus / Grafana Setup

### Prometheus scrape config

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: deye_inverter
    static_configs:
      - targets: ['localhost:9105']
    scrape_interval: 60s
```

### Grafana dashboard

1. Open Grafana → **Dashboards** → **Import**
2. Upload `grafana/dashboard.json`
3. Select your Prometheus datasource
4. Done 🎉

---

## 📈 Exposed Metrics (73 local / 64 cloud)

| Group | Count | Cloud | Examples |
|-------|-------|:-----:|---------|
| Solar | 9 | ✅ | `deye_pv1_power`, `deye_daily_production`, `deye_total_production` |
| Battery | 9 | ✅ | `deye_battery_soc`, `deye_battery_power`, `deye_daily_battery_charge` |
| Grid | 14 | ✅ | `deye_total_grid_power`, `deye_daily_energy_bought`, `deye_total_energy_sold` |
| Load | 6 | ✅ | `deye_total_load_power`, `deye_daily_load_consumption` |
| Inverter | 9 | ✅ | `deye_dc_temperature`, `deye_grid_frequency`, `deye_total_power` |
| Alert | 1 | ✅ | `deye_alert` (fault bitmask) |
| Time of Use | 25 | ✅ | `deye_time_of_use_soc_1` … `deye_time_of_use_enable_6` |

Cloud mode emits **39** of the 48 non-TOU metrics, plus all 25 Time-of-Use = **64** — see
[what cloud mode can't provide](#what-cloud-mode-cant-provide) for the 9 it can't.

Plus three health metrics in both modes:

| Metric | Meaning |
|--------|---------|
| `deye_up` | `1` if the last poll succeeded, `0` otherwise |
| `deye_scrape_duration_seconds` | How long the last poll took |
| `deye_data_timestamp_seconds` | Timestamp of the underlying reading (cloud only — shows true data age) |
| `deye_tou_timestamp_seconds` | Timestamp of the last successful time-of-use config fetch (cloud only) |

> **String-only metrics** (Battery Status, Running Status, Work Mode, etc.) are available in the  
> `HA/deye_hybrid.yaml` for Home Assistant but are not exposed as Prometheus gauges 
> since Prometheus cannot store text values in a Gauge.

---

## 🙏 Credits & Attribution

Register definitions in `HA/deye_hybrid.yaml` and the register mapping used in  
`parameters.py` are adapted from:

**[StephanJoubert/home_assistant_solarman](https://github.com/StephanJoubert/home_assistant_solarman)**  
Licensed under the [Apache License 2.0](https://github.com/StephanJoubert/home_assistant_solarman/blob/main/LICENSE).

The Solarman V5 protocol implementation is provided by:

**[jmccrohan/pysolarmanv5](https://github.com/jmccrohan/pysolarmanv5)**

---

## 📄 License

MIT — do whatever you want, just don't blame me if your battery explodes 🔋
