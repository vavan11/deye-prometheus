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
# The 25 "Time of Use" entries are inverter *settings*, not telemetry, and are likewise
# absent from /device/latest — reading them would need the /v1.0/system/* endpoints,
# which cloud mode deliberately does not call.
#
# Net: cloud mode emits 39 of the 48 non-TOU metrics; local mode still emits all 73.
