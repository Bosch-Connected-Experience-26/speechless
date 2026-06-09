"""VSS signal catalog for the demo dashboard.

These are COVESA VSS (Vehicle Signal Specification) paths. The Kuksa Databroker
loads a specific `vss.json`, and exact path names DIFFER between VSS versions
(e.g. older VSS used `Vehicle.Body.Lights.IsLowBeamOn` instead of
`Vehicle.Body.Lights.Beam.Low.IsOn`).

>>> Before wiring the real databroker, confirm these paths against the tree your
>>> databroker actually loaded:  `kuksa-client` -> getMetaData '*'  (or `getValue`)

Each entry: path -> {type, default}. `type` is informational (used for parsing
values coming in over HTTP/WebSocket as strings).
"""

# fmt: off
SIGNALS = {
    # Lighting
    "Vehicle.Body.Lights.Beam.Low.IsOn":                          {"type": "bool",  "default": False},
    "Vehicle.Body.Lights.Beam.High.IsOn":                         {"type": "bool",  "default": False},
    "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling":    {"type": "bool",  "default": False},
    "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling":   {"type": "bool",  "default": False},
    "Vehicle.Body.Lights.Hazard.IsSignaling":                     {"type": "bool",  "default": False},

    # Doors / locks / windows
    "Vehicle.Cabin.Door.Row1.DriverSide.IsLocked":                {"type": "bool",  "default": True},
    "Vehicle.Cabin.Door.Row1.PassengerSide.IsLocked":             {"type": "bool",  "default": True},
    "Vehicle.Cabin.Door.Row1.DriverSide.IsOpen":                  {"type": "bool",  "default": False},
    "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position":         {"type": "uint8", "default": 0},   # 0 closed .. 100 open

    # Climate
    "Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature":           {"type": "float", "default": 21.0},
    "Vehicle.Cabin.HVAC.IsAirConditioningActive":                 {"type": "bool",  "default": False},

    # Drivetrain / energy
    "Vehicle.Speed":                                              {"type": "float", "default": 0.0},
    "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current":   {"type": "float", "default": 78.0},
}
# fmt: on

PATHS = list(SIGNALS.keys())


def default_state() -> dict:
    """Initial value for every signal."""
    return {path: meta["default"] for path, meta in SIGNALS.items()}


def coerce(path: str, value):
    """Best-effort coerce an incoming value to the signal's declared type."""
    meta = SIGNALS.get(path)
    if meta is None:
        return value
    t = meta["type"]
    try:
        if t == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if t in ("uint8", "int"):
            return int(float(value))
        if t == "float":
            return float(value)
    except (TypeError, ValueError):
        return value
    return value
