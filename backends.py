"""
backends.py — The two interchangeable scrape sources.

Both expose the same duck-typed contract, so exporter.py never needs to know whether
the numbers came off the LAN or out of Deye's cloud:

    .name                  -> "local" | "cloud"
    .parameters            -> list[dict] with name / group / uom / help
    .read_values()         -> dict[str, float] keyed by the SAME `name` strings
    .collection_time       -> epoch seconds of the underlying reading, or None
    .extra_descriptions    -> help text for names not present in .parameters

Metric-name parity between the two backends is the whole point: `name` strings are
shared between parameters.py and cloud_parameters.py, so exporter._sanitize() yields
identical deye_* series either way and grafana/dashboard.json needs no edits.
"""
from config import (
    CLOUD_APP_ID,
    CLOUD_APP_SECRET,
    CLOUD_DEVICE_SN,
    CLOUD_EMAIL,
    CLOUD_EXPOSE_UNMAPPED,
    CLOUD_PASSWORD,
)
from cloud import DeyeCloudClient
from cloud_parameters import CLOUD_PARAMETERS
from decoders import decode
from inverter import InverterClient
from parameters import PARAMETERS


def to_float(value) -> float | None:
    """Coerce a cloud string value to float, or None if it isn't numeric (status text, etc.)."""
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


class LocalBackend:
    """Solarman V5 over LAN — the original path, unchanged in behaviour."""

    name = "local"

    def __init__(self):
        self.parameters = PARAMETERS
        self.client = InverterClient()
        self.collection_time = None
        self.extra_descriptions: dict[str, str] = {}

    def read_values(self) -> dict[str, float]:
        regs = self.client.read_all()
        values = {}
        for p in self.parameters:
            value = decode(p, regs)
            if value is not None:
                values[p["name"]] = value
        return values


class CloudBackend:
    """Deye Cloud OpenAPI — /device/latest, mapped onto the local metric names."""

    name = "cloud"

    def __init__(self, client: DeyeCloudClient | None = None, device_sn: str = CLOUD_DEVICE_SN,
                 expose_unmapped: bool = CLOUD_EXPOSE_UNMAPPED):
        missing = [
            var for var, val in (
                ("CLOUD_APP_ID", CLOUD_APP_ID),
                ("CLOUD_APP_SECRET", CLOUD_APP_SECRET),
                ("CLOUD_EMAIL", CLOUD_EMAIL),
                ("CLOUD_PASSWORD", CLOUD_PASSWORD),
                ("CLOUD_DEVICE_SN", device_sn),
            ) if not val
        ]
        if missing:
            raise ValueError(
                "Cloud source is missing required settings in .env: "
                + ", ".join(missing)
                + "\nRun `python main.py --source cloud --list-devices` to find CLOUD_DEVICE_SN "
                  "(the inverter serial — not INVERTER_SERIAL, which is the logger's)."
            )

        self.parameters = CLOUD_PARAMETERS
        self.client = client or DeyeCloudClient()
        self.device_sn = device_sn
        self.expose_unmapped = expose_unmapped
        self.collection_time = None
        self.extra_descriptions: dict[str, str] = {}

        # Every key (primary + alternates) claimed by the mapping table.
        self._claimed = {p["key"] for p in self.parameters}
        for p in self.parameters:
            self._claimed.update(p.get("alt_keys", []))

    @staticmethod
    def _pick(param: dict, values: dict):
        """Return the first present value among the param's primary key and its alternates."""
        for key in (param["key"], *param.get("alt_keys", [])):
            if key in values:
                return values[key]
        return None

    def read_values(self) -> dict[str, float]:
        values, items, collection_time = self.client.latest(self.device_sn)
        self.collection_time = collection_time

        out: dict[str, float] = {}
        for p in self.parameters:
            raw = self._pick(p, values)
            number = to_float(raw)
            if number is None:
                continue
            out[p["name"]] = (number - p.get("offset", 0)) * p.get("scale", 1)

        if self.expose_unmapped:
            for item in items:
                key = str(item.get("key", ""))
                if not key or key in self._claimed:
                    continue
                number = to_float(item.get("value"))
                if number is None:
                    continue
                # "cloud <key>" sanitizes to deye_cloud_<key>, so these need no special
                # casing in the exporter — they ride the same lazy-gauge path.
                name = f"cloud {key}"
                out[name] = number
                unit = item.get("unit") or ""
                label = item.get("name") or key
                self.extra_descriptions[name] = f"{label} [{unit}]" if unit else str(label)

        return out


def get_backend(source: str):
    """Build the backend named by `source` ("local" or "cloud")."""
    source = (source or "").strip().lower()
    if source == "local":
        return LocalBackend()
    if source == "cloud":
        return CloudBackend()
    raise ValueError(f"Unknown source {source!r} — expected 'local' or 'cloud'")
