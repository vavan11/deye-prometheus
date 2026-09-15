#!/usr/bin/env python3
"""
main.py — Entry point for the Deye inverter Prometheus exporter.

Usage:
    python main.py                                # Print all values once (debug)
    python main.py --exporter                     # Start Prometheus metrics server on :9105
    python main.py --source cloud                 # Same, but scraped from the Deye Cloud API
    python main.py --source cloud --exporter
    python main.py --list-devices                 # Cloud: list devices, find your deviceSn
    python main.py --dump                         # Cloud: measure-point inventory + mapping report
"""
import sys

from config import CLOUD_DEVICE_SN, CLOUD_DEVICE_TYPE, DEYE_SOURCE
from exporter import DeyeExporter


def _arg_value(flag: str, default: str) -> str:
    """Read `--flag value` out of argv, falling back to `default`."""
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
        sys.exit(f"error: {flag} needs a value")
    return default


def list_devices() -> None:
    """Print the account's devices so the user can copy the right deviceSn into .env."""
    from cloud import DeyeCloudClient, DeyeCloudError

    client = DeyeCloudClient()
    try:
        devices = client.device_list()
    except DeyeCloudError as exc:
        # /device/list rejects valid tokens on personal accounts (code 2101019) even
        # though /device/latest accepts them. Fall back to the station list, which works.
        print(f"\n/device/list is unavailable on this account: {exc}")
        print("(This endpoint appears to require an organization account. The scrape "
              "endpoint /device/latest is unaffected.)")
        try:
            stations = client.station_list()
        except DeyeCloudError as exc2:
            sys.exit(f"error: /station/list also failed: {exc2}")
        print(f"\nStations on this account ({len(stations)}):")
        for s in stations:
            print(f"    id={s.get('id', s.get('stationId',''))}  "
                  f"name={s.get('name','')}  type={s.get('type','')}")
        print("\nFind the inverter's serial in the Deye Cloud app or web UI "
              "(Device → Inverter → SN) and set it as CLOUD_DEVICE_SN in .env.")
        print("Verify it with: python main.py --dump\n")
        return

    if not devices:
        print("No devices returned. Check the account has the inverter registered.")
        return

    states = {0: "offline", 1: "online", 2: "alert"}
    print(f"\n{'deviceSn':<24} {'type':<12} {'status':<10} stationId")
    print("─" * 64)
    for d in devices:
        status = states.get(d.get("connectStatus"), str(d.get("connectStatus")))
        print(f"{str(d.get('deviceSn','')):<24} {str(d.get('deviceType','')):<12} "
              f"{status:<10} {d.get('stationId','')}")
    print("\nPut the inverter's deviceSn in .env as CLOUD_DEVICE_SN.")
    print("(This is NOT the same value as INVERTER_SERIAL, which is the Wi-Fi logger's serial.)\n")


def dump() -> None:
    """
    Cloud discovery: show every measure point this inverter reports, and report which
    cloud_parameters.py entries are still unmapped. Use the output to correct that table —
    the candidate keys shipped there are guesses until confirmed against a real device.
    """
    from cloud import DeyeCloudClient
    from cloud_parameters import CLOUD_PARAMETERS

    if not CLOUD_DEVICE_SN:
        sys.exit("error: CLOUD_DEVICE_SN is not set — run `python main.py --list-devices` first")

    client = DeyeCloudClient()

    try:
        points = client.measure_points(CLOUD_DEVICE_SN, CLOUD_DEVICE_TYPE)
    except Exception as exc:  # measurePoints is optional — the latest dump is what matters
        points = []
        print(f"[dump] /device/measurePoints unavailable: {exc}")

    values, items, collection_time = client.latest(CLOUD_DEVICE_SN)

    if points:
        print(f"\n─── /device/measurePoints ({len(points)}) ───────────────────────")
        for p in points:
            print(f"    {p.get('key', p) if isinstance(p, dict) else p}")

    print(f"\n─── /device/latest ({len(items)} data points) ──────────────────────")
    print(f"    {'key':<24} {'value':>14}  {'unit':<8} name")
    print("    " + "─" * 76)
    for item in sorted(items, key=lambda i: str(i.get("key", ""))):
        print(f"    {str(item.get('key','')):<24} {str(item.get('value','')):>14}  "
              f"{str(item.get('unit') or ''):<8} {item.get('name','')}")

    # ── Mapping report ─────────────────────────────────────────────────────────
    mapped, unmapped = [], []
    claimed: set[str] = set()
    for p in CLOUD_PARAMETERS:
        candidates = [p["key"], *p.get("alt_keys", [])]
        claimed.update(candidates)
        hit = next((k for k in candidates if k in values), None)
        (mapped if hit else unmapped).append((p["name"], hit or " / ".join(candidates)))

    print(f"\n─── MAPPED ({len(mapped)}/{len(CLOUD_PARAMETERS)}) ─────────────────────────────────")
    for name, key in mapped:
        print(f"    {name:<28} ← {key}")

    if unmapped:
        print(f"\n─── UNMAPPED TARGETS ({len(unmapped)}) — fix cloud_parameters.py ──────")
        for name, tried in unmapped:
            print(f"    {name:<28} tried: {tried}")

    unclaimed = sorted(k for k in values if k not in claimed)
    if unclaimed:
        print(f"\n─── RETURNED BUT UNCLAIMED ({len(unclaimed)}) ──────────────────────")
        print("    (candidates for the unmapped targets above, or for CLOUD_EXPOSE_UNMAPPED)")
        for key in unclaimed:
            print(f"    {key:<24} = {values[key]}")

    if collection_time:
        import time
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(collection_time))
        print(f"\n    Reading collected {stamp} ({time.time() - collection_time:.0f}s ago)")
    print()


def main():
    if "--list-devices" in sys.argv:
        list_devices()
        return
    if "--dump" in sys.argv:
        dump()
        return

    source = _arg_value("--source", DEYE_SOURCE)

    from backends import get_backend

    try:
        backend = get_backend(source)
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    exporter = DeyeExporter(backend)

    if "--exporter" in sys.argv:
        exporter.setup_metrics()
        exporter.run()
    else:
        # One-shot mode has no retry loop, so report an unreachable source plainly
        # instead of dumping a traceback from deep inside the client library.
        try:
            exporter.print_once()
        except Exception as exc:
            hint = ("Check INVERTER_IP / INVERTER_SERIAL and that this host is on the "
                    "inverter's LAN." if backend.name == "local"
                    else "Check the CLOUD_* settings in .env.")
            sys.exit(f"error: {backend.name} source failed: {exc}\n{hint}")


if __name__ == "__main__":
    main()
