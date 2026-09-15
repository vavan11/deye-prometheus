"""
parameters.py — All numeric parameter definitions for the Deye SUN-3K-SG04LP1-24-EU-SM1.

Register definitions adapted from StephanJoubert/home_assistant_solarman
(https://github.com/StephanJoubert/home_assistant_solarman), licensed Apache-2.0.

Only numeric parameters are included here (73 total: 48 telemetry + 25 time-of-use
settings). String/lookup-only parameters (Battery Status, Running Status, Work Mode,
etc.) are intentionally omitted since Prometheus Gauge metrics cannot represent text
values.

The `name` of each entry is the contract with cloud_parameters.py — both files use the
same names so either scrape source produces identical deye_* metric names.
"""

PARAMETERS: list[dict] = []

# ── Solar ──────────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "PV1 Power",            "group": "solar",   "rule": 1, "scale": 1,    "registers": [0x00BA], "uom": "W",   "help": "PV string 1 input power"},
    {"name": "PV2 Power",            "group": "solar",   "rule": 1, "scale": 1,    "registers": [0x00BB], "uom": "W",   "help": "PV string 2 input power"},
    {"name": "PV1 Voltage",          "group": "solar",   "rule": 1, "scale": 0.1,  "registers": [0x006D], "uom": "V",   "help": "PV string 1 voltage"},
    {"name": "PV2 Voltage",          "group": "solar",   "rule": 1, "scale": 0.1,  "registers": [0x006F], "uom": "V",   "help": "PV string 2 voltage"},
    {"name": "PV1 Current",          "group": "solar",   "rule": 1, "scale": 0.1,  "registers": [0x006E], "uom": "A",   "help": "PV string 1 current"},
    {"name": "PV2 Current",          "group": "solar",   "rule": 1, "scale": 0.1,  "registers": [0x0070], "uom": "A",   "help": "PV string 2 current"},
    {"name": "Daily Production",     "group": "solar",   "rule": 1, "scale": 0.1,  "registers": [0x006C], "uom": "kWh", "help": "Solar energy produced today"},
    {"name": "Total Production",     "group": "solar",   "rule": 3, "scale": 0.1,  "registers": [0x0060, 0x0061], "uom": "kWh", "help": "Total lifetime solar energy produced"},
    {"name": "Micro Inverter Power", "group": "solar",   "rule": 1, "scale": 1,    "registers": [0x00A6], "uom": "W",   "help": "Micro-inverter / generator input power"},
]

# ── Battery ────────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Battery Voltage",          "group": "battery", "rule": 1, "scale": 0.01, "registers": [0x00B7], "uom": "V",   "help": "Battery pack voltage"},
    {"name": "Battery Current",          "group": "battery", "rule": 2, "scale": 0.01, "registers": [0x00BF], "uom": "A",   "help": "Battery current (negative = charging)"},
    {"name": "Battery Power",            "group": "battery", "rule": 2, "scale": 1,    "registers": [0x00BE], "uom": "W",   "help": "Battery power (negative = charging)"},
    {"name": "Battery SOC",              "group": "battery", "rule": 1, "scale": 1,    "registers": [0x00B8], "uom": "%",   "help": "Battery state of charge"},
    {"name": "Battery Temperature",      "group": "battery", "rule": 1, "scale": 0.1,  "offset": 1000, "registers": [0x00B6], "uom": "°C", "help": "Battery temperature"},
    {"name": "Daily Battery Charge",     "group": "battery", "rule": 1, "scale": 0.1,  "registers": [0x0046], "uom": "kWh", "help": "Energy charged into battery today"},
    {"name": "Daily Battery Discharge",  "group": "battery", "rule": 1, "scale": 0.1,  "registers": [0x0047], "uom": "kWh", "help": "Energy discharged from battery today"},
    {"name": "Total Battery Charge",     "group": "battery", "rule": 3, "scale": 0.1,  "registers": [0x0048, 0x0049], "uom": "kWh", "help": "Total lifetime energy charged into battery"},
    {"name": "Total Battery Discharge",  "group": "battery", "rule": 3, "scale": 0.1,  "registers": [0x004A, 0x004B], "uom": "kWh", "help": "Total lifetime energy discharged from battery"},
]

# ── Grid ───────────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Total Grid Power",      "group": "grid", "rule": 2, "scale": 1,   "registers": [0x00A9], "uom": "W",   "help": "Net grid power (positive = importing)"},
    {"name": "Grid Voltage L1",       "group": "grid", "rule": 1, "scale": 0.1, "registers": [0x0096], "uom": "V",   "help": "Grid voltage phase L1"},
    {"name": "Grid Voltage L2",       "group": "grid", "rule": 1, "scale": 0.1, "registers": [0x0097], "uom": "V",   "help": "Grid voltage phase L2"},
    {"name": "Grid Current L1",       "group": "grid", "rule": 1, "scale": 0.01,"registers": [0x00A0], "uom": "A",   "help": "Grid current phase L1"},
    {"name": "Grid Current L2",       "group": "grid", "rule": 1, "scale": 0.01,"registers": [0x00A1], "uom": "A",   "help": "Grid current phase L2"},
    {"name": "Internal CT L1 Power",  "group": "grid", "rule": 2, "scale": 1,   "registers": [0x00A7], "uom": "W",   "help": "Internal CT sensor power L1"},
    {"name": "Internal CT L2 Power",  "group": "grid", "rule": 2, "scale": 1,   "registers": [0x00A8], "uom": "W",   "help": "Internal CT sensor power L2"},
    {"name": "External CT L1 Power",  "group": "grid", "rule": 2, "scale": 1,   "registers": [0x00AA], "uom": "W",   "help": "External CT sensor power L1"},
    {"name": "External CT L2 Power",  "group": "grid", "rule": 2, "scale": 1,   "registers": [0x00AB], "uom": "W",   "help": "External CT sensor power L2"},
    {"name": "Daily Energy Bought",   "group": "grid", "rule": 1, "scale": 0.1, "registers": [0x004C], "uom": "kWh", "help": "Energy imported from grid today"},
    {"name": "Daily Energy Sold",     "group": "grid", "rule": 1, "scale": 0.1, "registers": [0x004D], "uom": "kWh", "help": "Energy exported to grid today"},
    {"name": "Total Energy Bought",   "group": "grid", "rule": 1, "scale": 0.1, "registers": [0x004E], "uom": "kWh", "help": "Total lifetime energy imported from grid"},
    {"name": "Total Energy Sold",     "group": "grid", "rule": 3, "scale": 0.1, "registers": [0x0051, 0x0052], "uom": "kWh", "help": "Total lifetime energy exported to grid"},
    {"name": "Total Grid Production", "group": "grid", "rule": 4, "scale": 0.1, "registers": [0x003F, 0x0040], "uom": "kWh", "help": "Total grid production energy"},
]

# ── Load ───────────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Total Load Power",       "group": "load", "rule": 1, "scale": 1,   "registers": [0x00B2], "uom": "W",   "help": "Total house load power"},
    {"name": "Load L1 Power",          "group": "load", "rule": 1, "scale": 1,   "registers": [0x00B0], "uom": "W",   "help": "House load power phase L1"},
    {"name": "Load L2 Power",          "group": "load", "rule": 1, "scale": 1,   "registers": [0x00B1], "uom": "W",   "help": "House load power phase L2"},
    {"name": "Load Voltage",           "group": "load", "rule": 1, "scale": 0.1, "registers": [0x009D], "uom": "V",   "help": "Load output voltage"},
    {"name": "Daily Load Consumption", "group": "load", "rule": 1, "scale": 0.1, "registers": [0x0054], "uom": "kWh", "help": "Load energy consumed today"},
    {"name": "Total Load Consumption", "group": "load", "rule": 3, "scale": 0.1, "registers": [0x0055, 0x0056], "uom": "kWh", "help": "Total lifetime load energy consumed"},
]

# ── Inverter ───────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Total Power",       "group": "inverter", "rule": 2, "scale": 1,    "registers": [0x00AF], "uom": "W",  "help": "Total inverter output power"},
    {"name": "Grid Frequency",    "group": "inverter", "rule": 1, "scale": 0.01, "registers": [0x004F], "uom": "Hz", "help": "Grid frequency"},
    {"name": "Load Frequency",    "group": "inverter", "rule": 1, "scale": 0.01, "registers": [0x00C0], "uom": "Hz", "help": "Load output frequency"},
    {"name": "Current L1",        "group": "inverter", "rule": 2, "scale": 0.01, "registers": [0x00A4], "uom": "A",  "help": "Inverter output current L1"},
    {"name": "Current L2",        "group": "inverter", "rule": 2, "scale": 0.01, "registers": [0x00A5], "uom": "A",  "help": "Inverter output current L2"},
    {"name": "Inverter L1 Power", "group": "inverter", "rule": 2, "scale": 1,    "registers": [0x00AD], "uom": "W",  "help": "Inverter output power L1"},
    {"name": "Inverter L2 Power", "group": "inverter", "rule": 2, "scale": 1,    "registers": [0x00AE], "uom": "W",  "help": "Inverter output power L2"},
    {"name": "DC Temperature",    "group": "inverter", "rule": 2, "scale": 0.1,  "offset": 1000, "registers": [0x005A], "uom": "°C", "help": "DC side (MPPT) heatsink temperature"},
    {"name": "AC Temperature",    "group": "inverter", "rule": 2, "scale": 0.1,  "offset": 1000, "registers": [0x005B], "uom": "°C", "help": "AC side inverter heatsink temperature"},
]

# ── Alert ──────────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Alert",  "group": "alert", "rule": 6, "scale": 1, "registers": [0x0065, 0x0066, 0x0067, 0x0068, 0x0069, 0x006A], "uom": "", "help": "Inverter fault/alert bitmask"},
]

# ── Time of Use ────────────────────────────────────────────────────────────────
PARAMETERS += [
    {"name": "Time of Use",          "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x00F8], "uom": "", "help": "Time-of-use master enable (0=off, 1=on)"},
    {"name": "Time of Use Time 1",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FA], "uom": "", "help": "TOU slot 1 end time (HHMM)"},
    {"name": "Time of Use Time 2",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FB], "uom": "", "help": "TOU slot 2 end time"},
    {"name": "Time of Use Time 3",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FC], "uom": "", "help": "TOU slot 3 end time"},
    {"name": "Time of Use Time 4",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FD], "uom": "", "help": "TOU slot 4 end time"},
    {"name": "Time of Use Time 5",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FE], "uom": "", "help": "TOU slot 5 end time"},
    {"name": "Time of Use Time 6",   "group": "tou", "rule": 9, "scale": 1, "registers": [0x00FF], "uom": "", "help": "TOU slot 6 end time"},
    {"name": "Time of Use Power 1",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0100], "uom": "", "help": "TOU slot 1 charge power limit (%)"},
    {"name": "Time of Use Power 2",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0101], "uom": "", "help": "TOU slot 2 charge power limit"},
    {"name": "Time of Use Power 3",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0102], "uom": "", "help": "TOU slot 3 charge power limit"},
    {"name": "Time of Use Power 4",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0103], "uom": "", "help": "TOU slot 4 charge power limit"},
    {"name": "Time of Use Power 5",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0104], "uom": "", "help": "TOU slot 5 charge power limit"},
    {"name": "Time of Use Power 6",  "group": "tou", "rule": 1, "scale": 1, "registers": [0x0105], "uom": "", "help": "TOU slot 6 charge power limit"},
    {"name": "Time of Use SOC 1",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x010C], "uom": "%", "help": "TOU slot 1 minimum SOC"},
    {"name": "Time of Use SOC 2",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x010D], "uom": "%", "help": "TOU slot 2 minimum SOC"},
    {"name": "Time of Use SOC 3",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x010E], "uom": "%", "help": "TOU slot 3 minimum SOC"},
    {"name": "Time of Use SOC 4",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x010F], "uom": "%", "help": "TOU slot 4 minimum SOC"},
    {"name": "Time of Use SOC 5",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x0110], "uom": "%", "help": "TOU slot 5 minimum SOC"},
    {"name": "Time of Use SOC 6",    "group": "tou", "rule": 1, "scale": 1, "registers": [0x0111], "uom": "%", "help": "TOU slot 6 minimum SOC"},
    {"name": "Time of Use Enable 1", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0112], "uom": "", "help": "TOU slot 1 enabled"},
    {"name": "Time of Use Enable 2", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0113], "uom": "", "help": "TOU slot 2 enabled"},
    {"name": "Time of Use Enable 3", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0114], "uom": "", "help": "TOU slot 3 enabled"},
    {"name": "Time of Use Enable 4", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0115], "uom": "", "help": "TOU slot 4 enabled"},
    {"name": "Time of Use Enable 5", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0116], "uom": "", "help": "TOU slot 5 enabled"},
    {"name": "Time of Use Enable 6", "group": "tou", "rule": 1, "scale": 1, "mask": 1, "registers": [0x0117], "uom": "", "help": "TOU slot 6 enabled"},
]
