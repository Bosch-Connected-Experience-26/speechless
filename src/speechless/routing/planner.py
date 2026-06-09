"""Fuel-aware route planner with multi-constraint routing.

Computes reachable destinations based on fuel level and consumption,
ranks routes by deviation, and handles multi-constraint routing
(refueling stops, food stops, hospital for emergencies).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GeoPoint:
    """Geographic coordinate."""

    latitude: float
    longitude: float
    label: Optional[str] = None


@dataclass
class RouteConstraint:
    """A constraint that must be satisfied along the route."""

    type: str  # "fuel", "food", "hospital"
    location: Optional[GeoPoint] = None
    label: Optional[str] = None


@dataclass
class RouteOption:
    """A computed route option with deviation metadata."""

    waypoints: list[GeoPoint] = field(default_factory=list)
    total_deviation_km: float = 0.0
    additional_time_minutes: float = 0.0
    constraints_satisfied: dict[str, GeoPoint] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


EARTH_RADIUS_KM = 6371.0
ASSUMED_TANK_CAPACITY_LITERS = 50.0  # Default tank capacity


class RoutePlanner:
    """Fuel-aware, multi-constraint route planner.

    Computes reachability based on fuel level and consumption rate,
    ranks route options by total deviation, and supports constraints
    (refueling, food stops, hospital for emergency).

    Args:
        tank_capacity: Vehicle fuel tank capacity in liters.
    """

    def __init__(self, tank_capacity: float = ASSUMED_TANK_CAPACITY_LITERS):
        self.tank_capacity = tank_capacity

    def compute_range_km(self, fuel_level: float, consumption_rate: float) -> float:
        """Compute remaining driving range in km.

        Args:
            fuel_level: Current fuel level as percentage (0-100).
            consumption_rate: Fuel consumption in liters per 100km.

        Returns:
            Estimated range in kilometers. Returns 0 if inputs invalid.
        """
        if consumption_rate <= 0 or fuel_level < 0:
            return 0.0
        fuel_liters = (fuel_level / 100.0) * self.tank_capacity
        range_km = (fuel_liters / consumption_rate) * 100.0
        return range_km

    def is_reachable(
        self, fuel_level: float, consumption_rate: float, distance_km: float
    ) -> bool:
        """Check if a destination is reachable with current fuel.

        Args:
            fuel_level: Current fuel level percentage.
            consumption_rate: Liters per 100km.
            distance_km: Distance to destination in km.

        Returns:
            True if destination is within fuel range.
        """
        if distance_km < 0:
            return False
        range_km = self.compute_range_km(fuel_level, consumption_rate)
        return range_km >= distance_km

    def compute_distance_km(self, origin: GeoPoint, destination: GeoPoint) -> float:
        """Compute distance between two points using Haversine formula.

        Args:
            origin: Starting point.
            destination: Ending point.

        Returns:
            Distance in kilometers.
        """
        lat1 = math.radians(origin.latitude)
        lat2 = math.radians(destination.latitude)
        dlat = math.radians(destination.latitude - origin.latitude)
        dlon = math.radians(destination.longitude - origin.longitude)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return EARTH_RADIUS_KM * c

    def rank_routes(self, routes: list[RouteOption]) -> list[RouteOption]:
        """Sort route options by total deviation (ascending).

        Args:
            routes: List of route options to rank.

        Returns:
            Sorted list with least-deviation route first.
        """
        return sorted(routes, key=lambda r: r.total_deviation_km)

    def compute_route_with_constraints(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        constraints: list[RouteConstraint],
        fuel_level: float,
        consumption_rate: float,
    ) -> RouteOption:
        """Compute a route satisfying all constraints with minimal deviation.

        Checks each constraint location for reachability and adds warnings
        when stops are outside fuel range.

        Args:
            origin: Starting point.
            destination: Final destination.
            constraints: Required stops (fuel, food, hospital).
            fuel_level: Current fuel level percentage.
            consumption_rate: Liters per 100km.

        Returns:
            RouteOption with waypoints, deviation, and warnings.
        """
        waypoints = [origin]
        total_deviation = 0.0
        constraints_satisfied: dict[str, GeoPoint] = {}
        warnings: list[str] = []

        # Direct distance for baseline
        direct_distance = self.compute_distance_km(origin, destination)
        current_range = self.compute_range_km(fuel_level, consumption_rate)
        current_pos = origin

        for constraint in constraints:
            if constraint.location is None:
                continue

            # Distance from current position to constraint stop
            dist_to_stop = self.compute_distance_km(current_pos, constraint.location)

            # Check if stop is reachable with current fuel
            if dist_to_stop > current_range:
                warnings.append(
                    f"{constraint.type} stop '{constraint.label or 'unknown'}' is outside "
                    f"current fuel range ({dist_to_stop:.1f}km away, range: {current_range:.1f}km)"
                )

            # Compute deviation: distance via stop vs direct to destination
            dist_stop_to_dest = self.compute_distance_km(constraint.location, destination)
            route_via_stop = dist_to_stop + dist_stop_to_dest
            deviation = route_via_stop - self.compute_distance_km(current_pos, destination)
            total_deviation += max(0.0, deviation)

            waypoints.append(constraint.location)
            constraints_satisfied[constraint.type] = constraint.location
            current_pos = constraint.location

            # If fuel constraint, assume refuel restores range
            if constraint.type == "fuel":
                current_range = self.compute_range_km(100.0, consumption_rate)
            else:
                current_range -= dist_to_stop

        waypoints.append(destination)

        # Estimate additional time (assuming 60 km/h average + 10min per stop)
        additional_time = (total_deviation / 60.0) * 60.0 + len(constraints) * 10.0

        return RouteOption(
            waypoints=waypoints,
            total_deviation_km=total_deviation,
            additional_time_minutes=additional_time,
            constraints_satisfied=constraints_satisfied,
            warnings=warnings,
        )
