"""
cloud_parameters.py — Maps Deye Cloud measure-point keys onto the *same* metric names
that parameters.py produces, so both scrape backends expose identical Prometheus series.

Shape mirrors parameters.py, with `registers` replaced by `key`:

    {"name", "group", "key", "alt_keys", "scale", "uom", "help"}

`name` MUST be byte-identical to the corresponding entry in parameters.py — that string
is what exporter._sanitize() turns into the deye_* metric name. A typo here silently
creates a second, divergent series instead of matching local mode.

Unlike the register path, the cloud returns values already in human units (V, A, W, kWh,
°C), so no `scale` is needed anywhere below.

━━ Verified against a real inverter ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
These keys came from `python main.py --dump` against a Deye hybrid (RatedPower 8000 W,
65 measure points, 58 reported in /device/latest). Deye uses readable names, not the
SolarMAN-style short codes (`BMS_SOC`, `G_V_L1`) used by other clouds. Note the literal
spaces in "DC Temperature" / "AC Temperature" and the stray hyphen in
"Temperature- Battery" — these are the keys exactly as the API returns them.

`alt_keys` are tried in order after `key`, covering firmware variations and the cases
where two plausible cloud keys exist for one local metric.

Re-run `--dump` after a firmware update to confirm nothing was renamed.
"""

CLOUD_PARAMETERS: list[dict] = []

# ── Solar ──────────────────────────────────────────────────────────────────────
CLOUD_PARAMETERS += [
    {"name": "PV1 Power",            "group": "solar", "key": "DCPowerPV1",   "uom": "W",   "help": "PV string 1 input power"},
    {"name": "PV2 Power",            "group": "solar", "key": "DCPowerPV2",   "uom": "W",   "help": "PV string 2 input power"},
    {"name": "PV1 Voltage",          "group": "solar", "key": "DCVoltagePV1", "uom": "V",   "help": "PV string 1 voltage"},
    {"name": "PV2 Voltage",          "group": "solar", "key": "DCVoltagePV2", "uom": "V",   "help": "PV string 2 voltage"},
    {"name": "PV1 Current",          "group": "solar", "key": "DCCurrentPV1", "uom": "A",   "help": "PV string 1 current"},
    {"name": "PV2 Current",          "group": "solar", "key": "DCCurrentPV2", "uom": "A",   "help": "PV string 2 current"},
    {"name": "Daily Production",     "group": "solar", "key": "PVDailyPowerGenerationActive",
     "alt_keys": ["DailyActiveProduction"],      "uom": "kWh", "help": "Solar energy produced today"},
    {"name": "Total Production",     "group": "solar", "key": "PVCumulativePowerGenerationActive",
     "alt_keys": ["TotalActiveProduction"],      "uom": "kWh", "help": "Total lifetime solar energy produced"},
    # Listed in /device/measurePoints but absent from /device/latest on this unit —
    # it simply yields no value rather than failing.
    {"name": "Micro Inverter Power", "group": "solar", "key": "MIPower",      "uom": "W",   "help": "Micro-inverter / generator input power"},
]

# ── Battery ────────────────────────────────────────────────────────────────────
CLOUD_PARAMETERS += [
    {"name": "Battery Voltage",         "group": "battery", "key": "BatteryVoltage",         "uom": "V",   "help": "Battery pack voltage"},
    {"name": "Battery Current",         "group": "battery", "key": "BatteryCurrent",         "uom": "A",   "help": "Battery current (negative = charging)"},
    {"name": "Battery Power",           "group": "battery", "key": "BatteryPower",           "uom": "W",   "help": "Battery power (negative = charging)"},
    {"name": "Battery SOC",             "group": "battery", "key": "SOC",                    "uom": "%",   "help": "Battery state of charge"},
    {"name": "Battery Temperature",     "group": "battery", "key": "Temperature- Battery",   "uom": "°C",  "help": "Battery temperature"},
    {"name": "Daily Battery Charge",    "group": "battery", "key": "DailyChargingEnergy",    "uom": "kWh", "help": "Energy charged into battery today"},
    {"name": "Daily Battery Discharge", "group": "battery", "key": "DailyDischargingEnergy", "uom": "kWh", "help": "Energy discharged from battery today"},
    {"name": "Total Battery Charge",    "group": "battery", "key": "TotalChargeEnergy",      "uom": "kWh", "help": "Total lifetime energy charged into battery"},
    {"name": "Total Battery Discharge", "group": "battery", "key": "TotalDischargeEnergy",   "uom": "kWh", "help": "Total lifetime energy discharged from battery"},
]

# ── Grid ───────────────────────────────────────────────────────────────────────
CLOUD_PARAMETERS += [
    {"name": "Total Grid Power",      "group": "grid", "key": "TotalGridPower",            "uom": "W",   "help": "Net grid power (positive = importing)"},
    {"name": "Grid Voltage L1",       "group": "grid", "key": "GridVoltageL1L2",           "uom": "V",   "help": "Grid voltage phase L1"},
    {"name": "Grid Current L1",       "group": "grid", "key": "GridCurrentL1L2",           "uom": "A",   "help": "Grid current phase L1"},
    {"name": "External CT L1 Power",  "group": "grid", "key": "ExternalCTPowerL1L2",       "uom": "W",   "help": "External CT sensor power L1"},
    {"name": "Daily Energy Bought",   "group": "grid", "key": "DailyEnergyPurchased",      "uom": "kWh", "help": "Energy imported from grid today"},
    {"name": "Daily Energy Sold",     "group": "grid", "key": "DailyGridFeedIn",           "uom": "kWh", "help": "Energy exported to grid today"},
    {"name": "Total Energy Bought",   "group": "grid", "key": "CumulativeEnergyPurchased", "uom": "kWh", "help": "Total lifetime energy imported from grid"},
    {"name": "Total Energy Sold",     "group": "grid", "key": "CumulativeGridFeedIn",      "uom": "kWh", "help": "Total lifetime energy exported to grid"},
    {"name": "Total Grid Production", "group": "grid", "key": "TotalActiveProduction",     "uom": "kWh", "help": "Total grid production energy"},
]

# ── Load ───────────────────────────────────────────────────────────────────────
CLOUD_PARAMETERS += [
    {"name": "Total Load Power",       "group": "load", "key": "TotalConsumptionPower",
     "alt_keys": ["UPSLoadPower"],   "uom": "W",   "help": "Total house load power"},
    # Single-phase unit: the L1 leg carries the whole load, so this equals Total Load Power.
    {"name": "Load L1 Power",          "group": "load", "key": "UPSLoadPower",
     "alt_keys": ["TotalConsumptionPower"], "uom": "W", "help": "House load power phase L1"},
    {"name": "Load Voltage",           "group": "load", "key": "LoadVoltageL1L2",   "uom": "V",   "help": "Load output voltage"},
    {"name": "Daily Load Consumption", "group": "load", "key": "DailyConsumption",  "uom": "kWh", "help": "Load energy consumed today"},
    {"name": "Total Load Consumption", "group": "load", "key": "CumulativeConsumption", "uom": "kWh", "help": "Total lifetime load energy consumed"},
]

# ── Inverter ───────────────────────────────────────────────────────────────────
CLOUD_PARAMETERS += [
    {"name": "Total Power",       "group": "inverter", "key": "InverterOutputPowerL1L2", "uom": "W",  "help": "Total inverter output power"},
    # Single-phase unit: L1 output is the whole output, so this equals Total Power.
    {"name": "Inverter L1 Power", "group": "inverter", "key": "InverterOutputPowerL1L2", "uom": "W",  "help": "Inverter output power L1"},
    {"name": "Grid Frequency",    "group": "inverter", "key": "GridFrequency",           "uom": "Hz", "help": "Grid frequency"},
    {"name": "Load Frequency",    "group": "inverter", "key": "ACOutputFrequencyR",      "uom": "Hz", "help": "Load output frequency"},
    {"name": "Current L1",        "group": "inverter", "key": "ACCurrentRUA",            "uom": "A",  "help": "Inverter output current L1"},
    {"name": "DC Temperature",    "group": "inverter", "key": "DC Temperature",          "uom": "°C", "help": "DC side (MPPT) heatsink temperature"},
    {"name": "AC Temperature",    "group": "inverter", "key": "AC Temperature",          "uom": "°C", "help": "AC side inverter heatsink temperature"},
]

# ── Not available from the cloud ───────────────────────────────────────────────
# These parameters.py entries have NO equivalent key in /device/latest on this inverter,
# so cloud mode does not emit them. They are absent, not zero — the metric simply does
# not appear, which is the honest representation. Do not alias them onto an L1 key:
# that would invent data the inverter does not report.
#
#   Grid Voltage L2 / Grid Current L2 / Current L2 / Inverter L2 Power / Load L2 Power
#       This is a single-phase unit (GridVoltageL1L2 ≈ 224 V). The cloud reports one
#       "L1L2" figure per measurement; there is no second phase to report.
#   Internal CT L1 Power / Internal CT L2 Power
#       Only ExternalCTPowerL1L2 is exposed; the internal CT is local-register only.
#   External CT L2 Power
#       Same single-phase reason as above.
#   Alert
#       No fault/alarm bitmask key is returned. MAIN / HMI / ProtocolVersion are
#       firmware version strings, not fault codes.
#
# The 25 "Time of Use" entries are inverter *settings* and are absent from /device/latest,
# but they ARE available from the dedicated read-only endpoint /v1.0/config/tou — see
# TOU_PARAMETERS and parse_tou() below.
#
# Net: cloud mode emits 39 of the 48 non-TOU metrics, plus 25 TOU = 64; local mode emits 73.


# ══ Time of Use ═══════════════════════════════════════════════════════════════
#
# Sourced from POST /v1.0/config/tou, not /device/latest, and refreshed on its own
# slow timer (CLOUD_TOU_INTERVAL) because these are settings that change rarely.
#
# Response shape, verified live:
#     touAction: "on"
#     timeUseSettingItems: [ {time, power, soc, voltage,
#                             enableGridCharge, enableGeneration}, ... x6 ]
#
# Names are copied verbatim from parameters.py's "tou" group so cloud and local emit
# identical deye_time_of_use_* series. test_tou.py asserts that equality.

TOU_SLOTS = 6

TOU_PARAMETERS: list[dict] = [
    {"name": "Time of Use", "group": "tou", "uom": "",
     "help": "Time-of-use master enable (0=off, 1=on)"},
]
for _n in range(1, TOU_SLOTS + 1):
    TOU_PARAMETERS += [
        {"name": f"Time of Use Time {_n}",   "group": "tou", "uom": "",
         "help": f"TOU slot {_n} end time (HHMM)"},
        {"name": f"Time of Use Power {_n}",  "group": "tou", "uom": "W",
         "help": f"TOU slot {_n} charge power limit"},
        {"name": f"Time of Use SOC {_n}",    "group": "tou", "uom": "%",
         "help": f"TOU slot {_n} minimum SOC"},
        {"name": f"Time of Use Enable {_n}", "group": "tou", "uom": "",
         "help": f"TOU slot {_n} grid charge enabled"},
    ]

# Cloud-only: no local register equivalent, so they are gated behind
# CLOUD_EXPOSE_UNMAPPED to keep the default output name-identical to local mode.
TOU_EXTRA_PARAMETERS: list[dict] = []
for _n in range(1, TOU_SLOTS + 1):
    TOU_EXTRA_PARAMETERS += [
        {"name": f"Time of Use Voltage {_n}",    "group": "tou", "uom": "V",
         "help": f"TOU slot {_n} battery voltage setpoint (cloud only)"},
        {"name": f"Time of Use Generation {_n}", "group": "tou", "uom": "",
         "help": f"TOU slot {_n} generator charge enabled (cloud only)"},
    ]


def _tou_time(value) -> float | None:
    """
    "0700" -> 700.0, matching the local HHMM register exactly.

    int() rather than float(): "0700" would be fine either way, but a value like
    "07:00" must not silently become something wrong — it returns None instead.
    """
    if value is None:
        return None
    text = str(value).strip()
    return float(int(text)) if text.isdigit() else None


def parse_tou(tou_action, items, include_extras: bool = False) -> dict[str, float]:
    """
    Turn a /config/tou response into {metric name: value}.

    Pure function — no network, no state — so the mapping is testable directly.
    A short or empty item list simply yields no value for the missing slots rather
    than inventing zeros.
    """
    out: dict[str, float] = {}

    if tou_action is not None:
        out["Time of Use"] = 1.0 if str(tou_action).strip().lower() in ("on", "true", "1") else 0.0

    for index, item in enumerate(items or [], start=1):
        if index > TOU_SLOTS or not isinstance(item, dict):
            break

        slot_time = _tou_time(item.get("time"))
        if slot_time is not None:
            out[f"Time of Use Time {index}"] = slot_time

        for field, name in (("power", "Power"), ("soc", "SOC")):
            value = item.get(field)
            if value is not None:
                try:
                    out[f"Time of Use {name} {index}"] = float(value)
                except (TypeError, ValueError):
                    pass

        # The local register is read with mask 1, i.e. bit 0 = grid charge enable.
        if item.get("enableGridCharge") is not None:
            out[f"Time of Use Enable {index}"] = 1.0 if item["enableGridCharge"] else 0.0

        if include_extras:
            if item.get("voltage") is not None:
                try:
                    out[f"Time of Use Voltage {index}"] = float(item["voltage"])
                except (TypeError, ValueError):
                    pass
            if item.get("enableGeneration") is not None:
                out[f"Time of Use Generation {index}"] = 1.0 if item["enableGeneration"] else 0.0

    return out
