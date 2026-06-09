// VSS signal paths the dashboard renders — the UI-side mirror of the bridge
// catalog (bridge/signals.py). Path→UI-element mapping is inherently UI-side,
// so it lives here; the bridge stays the authority on which signals exist
// (the dashboard ignores any path it doesn't know how to draw).
//
// Keep these strings in sync with bridge/signals.py. If a path is renamed for a
// different VSS version, change it in both places (or fetch GET /signals).

export const P = {
  lowBeam: "Vehicle.Body.Lights.Beam.Low.IsOn",
  highBeam: "Vehicle.Body.Lights.Beam.High.IsOn",
  indLeft: "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
  indRight: "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling",
  hazard: "Vehicle.Body.Lights.Hazard.IsSignaling",
  lockDriver: "Vehicle.Cabin.Door.Row1.DriverSide.IsLocked",
  lockPass: "Vehicle.Cabin.Door.Row1.PassengerSide.IsLocked",
  doorDriverOpen: "Vehicle.Cabin.Door.Row1.DriverSide.IsOpen",
  windowDriver: "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position",
  temp: "Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature",
  ac: "Vehicle.Cabin.HVAC.IsAirConditioningActive",
  speed: "Vehicle.Speed",
  battery: "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
};

// Short labels for the command feed / debugging.
export const LABELS = {
  [P.lowBeam]: "Low beam",
  [P.highBeam]: "High beam",
  [P.indLeft]: "Left indicator",
  [P.indRight]: "Right indicator",
  [P.hazard]: "Hazards",
  [P.lockDriver]: "Driver lock",
  [P.lockPass]: "Passenger lock",
  [P.doorDriverOpen]: "Driver door",
  [P.windowDriver]: "Driver window",
  [P.temp]: "Cabin temp",
  [P.ac]: "A/C",
  [P.speed]: "Speed",
  [P.battery]: "Battery",
};

export const labelFor = (path) => LABELS[path] || path;

// Truthy helper tolerant of bool / "true" / 1.
export const on = (v) => v === true || v === 1 || v === "true";
