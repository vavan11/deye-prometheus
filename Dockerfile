# Deye Prometheus exporter
#
# Non-root (UID/GID 10001), no pip in the final image, compatible with a read-only
# root filesystem and all Linux capabilities dropped.
#
#   docker build -t deye-exporter .
#   docker compose up -d                       # see docker-compose.yml
#
# Endpoints on EXPORTER_PORT (default 9105):
#   /metrics    Prometheus metrics
#   /healthz    liveness  — poll loop still running (ignores upstream failures)
#   /readyz     readiness — a poll succeeded recently
#   /startupz   startup   — first poll has finished
#
# One-shot tools use the same entrypoint:
#   docker run --rm --env-file .env deye-exporter --dump

# Builder and runtime MUST use the same base: the venv's interpreter symlinks into it.
ARG PYTHON_IMAGE=python:3.12-slim-trixie

# ── Build stage ───────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .

# All dependencies are pure Python (pysolarmanv5 -> umodbus -> pyserial), so no
# compiler or -dev headers are installed. pip is removed from the venv once it has
# done its job so it never reaches the runtime image.
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
 && /opt/venv/bin/python -m pip uninstall --yes pip

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE}

ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.title="deye-prometheus" \
      org.opencontainers.image.description="Prometheus exporter for Deye hybrid inverters (local Solarman V5 or Deye Cloud API)" \
      org.opencontainers.image.source="https://github.com/vavan11/deye-prometheus" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

# 1. Apply Debian security updates. Upstream python:*-slim tags lag Debian's fixes —
#    a scan of the unpatched base found 28 fixable CVEs, including 3 critical.
#    This trades bit-for-bit reproducibility for patch level; rebuild regularly.
# 2. Remove the base image's own pip (published CVEs in older releases). Nothing
#    installs packages at runtime.
# 3. Strip setuid/setgid bits (su, mount, passwd, ...). The exporter needs none, and it
#    keeps privilege escalation closed even if run without no-new-privileges.
# 4. Fixed numeric UID/GID so Kubernetes runAsNonRoot/runAsUser works without a name
#    lookup. /data is group 0 + g+rwx so runtimes that assign a random UID in group 0
#    (OpenShift) can still write the token cache; the token file itself is 0600.
RUN apt-get update \
 && apt-get upgrade --yes \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall --yes pip \
 && find / -xdev -perm /6000 -type f -exec chmod a-s {} + \
 && groupadd --gid 10001 deye \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin deye \
 && install -d -o 10001 -g 0 -m 0770 /data

# CLOUD_TOKEN_CACHE is a file *path*, not a secret; hadolint flags it on the name alone.
# hadolint ignore=DL3064
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    EXPORTER_BIND=0.0.0.0 \
    EXPORTER_PORT=9105 \
    POLL_INTERVAL=60 \
    CLOUD_TOKEN_CACHE=/data/token.json

COPY --from=builder /opt/venv /opt/venv

# Explicit file list rather than `COPY . .` — together with the allowlist
# .dockerignore, nothing but application code can land in the image.
WORKDIR /app
COPY --chown=root:root requirements.txt *.py /app/

# /data is the only writable path (cached cloud access token). /app stays root-owned
# and read-only to the process.
VOLUME ["/data"]

USER 10001:10001

EXPOSE 9105

# Liveness, not readiness: a Deye Cloud outage or an unreachable inverter must not mark
# the container unhealthy (Swarm and autoheal-style tools replace unhealthy containers).
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('EXPORTER_PORT','9105')+'/healthz',timeout=4)"]

ENTRYPOINT ["python", "main.py"]
CMD ["--exporter"]
