"""Property-based tests for the Route Planner.

Property 17: Fuel reachability computation correctness.
Property 18: Route options ranked by deviation (ascending).
Property 19: Route constraint satisfaction.
Property 20: Combined route includes deviation and time metadata.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from speechless.routing.planner import (
    GeoPoint,
    RouteConstraint,
    RouteOption,
    RoutePlanner,
)


class TestFuelReachability:
    """Property 17: Fuel reachability computation correctness."""

    @given(
        fuel_level=st.floats(min_value=0.0, max_value=100.0),
        consumption_rate=st.floats(min_value=0.1, max_value=30.0),
        distance=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=200)
    def test_reachable_iff_within_range(
        self, fuel_level: float, consumption_rate: float, distance: float
    ):
        """Destination reachable iff computed range >= distance."""
        planner = RoutePlanner(tank_capacity=50.0)
        range_km = planner.compute_range_km(fuel_level, consumption_rate)
        is_reachable = planner.is_reachable(fuel_level, consumption_rate, distance)

        if range_km >= distance:
            assert is_reachable is True
        else:
            assert is_reachable is False

    @given(
        fuel_level=st.floats(min_value=0.0, max_value=100.0),
        consumption_rate=st.floats(min_value=0.1, max_value=30.0),
    )
    @settings(max_examples=100)
    def test_range_formula_correct(self, fuel_level: float, consumption_rate: float):
        """Range = (fuel_level/100 * tank_capacity / consumption_rate) * 100."""
        tank = 50.0
        planner = RoutePlanner(tank_capacity=tank)
        range_km = planner.compute_range_km(fuel_level, consumption_rate)

        expected = (fuel_level / 100.0 * tank / consumption_rate) * 100.0
        assert abs(range_km - expected) < 1e-6

    @given(
        fuel_level=st.floats(min_value=0.0, max_value=100.0),
        consumption_rate=st.floats(min_value=0.1, max_value=30.0),
    )
    @settings(max_examples=100)
    def test_range_is_non_negative(self, fuel_level: float, consumption_rate: float):
        """Computed range is always non-negative."""
        planner = RoutePlanner()
        range_km = planner.compute_range_km(fuel_level, consumption_rate)
        assert range_km >= 0.0

    def test_zero_fuel_gives_zero_range(self):
        """Zero fuel level means zero range."""
        planner = RoutePlanner()
        assert planner.compute_range_km(0.0, 8.0) == 0.0

    def test_zero_consumption_gives_zero_range(self):
        """Zero/negative consumption returns zero range (safety)."""
        planner = RoutePlanner()
        assert planner.compute_range_km(50.0, 0.0) == 0.0
        assert planner.compute_range_km(50.0, -1.0) == 0.0


class TestRouteRanking:
    """Property 18: Route options ranked by deviation (ascending)."""

    @given(
        deviations=st.lists(
            st.floats(min_value=0.0, max_value=500.0),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_routes_sorted_ascending_by_deviation(self, deviations: list):
        """Ranked routes are sorted by total_deviation_km ascending."""
        planner = RoutePlanner()
        routes = [
            RouteOption(total_deviation_km=d, additional_time_minutes=d * 2)
            for d in deviations
        ]

        ranked = planner.rank_routes(routes)
        for i in range(len(ranked) - 1):
            assert ranked[i].total_deviation_km <= ranked[i + 1].total_deviation_km

    @given(
        deviations=st.lists(
            st.floats(min_value=0.0, max_value=500.0),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_ranking_preserves_all_routes(self, deviations: list):
        """Ranking doesn't add or remove routes."""
        planner = RoutePlanner()
        routes = [RouteOption(total_deviation_km=d) for d in deviations]
        ranked = planner.rank_routes(routes)
        assert len(ranked) == len(routes)

    def test_first_route_has_least_deviation(self):
        """First route in ranked list has the smallest deviation."""
        planner = RoutePlanner()
        routes = [
            RouteOption(total_deviation_km=15.0),
            RouteOption(total_deviation_km=5.0),
            RouteOption(total_deviation_km=10.0),
        ]
        ranked = planner.rank_routes(routes)
        assert ranked[0].total_deviation_km == 5.0


class TestRouteConstraintSatisfaction:
    """Property 19: Route constraint satisfaction."""

    @given(
        fuel_level=st.floats(min_value=10.0, max_value=100.0),
        consumption_rate=st.floats(min_value=3.0, max_value=15.0),
    )
    @settings(max_examples=100)
    def test_constraints_map_to_waypoints(self, fuel_level: float, consumption_rate: float):
        """Each satisfied constraint maps to a waypoint in the route."""
        planner = RoutePlanner(tank_capacity=50.0)
        origin = GeoPoint(latitude=48.8, longitude=2.3, label="Paris")
        destination = GeoPoint(latitude=48.9, longitude=2.4, label="Destination")
        fuel_stop = GeoPoint(latitude=48.85, longitude=2.35, label="Gas Station")

        constraints = [
            RouteConstraint(type="fuel", location=fuel_stop, label="Gas Station"),
        ]

        route = planner.compute_route_with_constraints(
            origin, destination, constraints, fuel_level, consumption_rate
        )

        # Fuel constraint should be satisfied
        assert "fuel" in route.constraints_satisfied
        assert route.constraints_satisfied["fuel"] == fuel_stop

    def test_out_of_range_stop_has_warning(self):
        """Stops outside fuel range produce warnings."""
        planner = RoutePlanner(tank_capacity=50.0)
        origin = GeoPoint(latitude=48.0, longitude=2.0)
        destination = GeoPoint(latitude=50.0, longitude=4.0)
        far_stop = GeoPoint(latitude=52.0, longitude=6.0, label="Far Restaurant")

        constraints = [
            RouteConstraint(type="food", location=far_stop, label="Far Restaurant"),
        ]

        # Low fuel, far stop
        route = planner.compute_route_with_constraints(
            origin, destination, constraints, fuel_level=5.0, consumption_rate=10.0
        )

        assert len(route.warnings) > 0
        assert "Far Restaurant" in route.warnings[0]


class TestCombinedRouteMetadata:
    """Property 20: Combined route includes deviation and time metadata."""

    @given(
        fuel_level=st.floats(min_value=10.0, max_value=100.0),
        consumption_rate=st.floats(min_value=3.0, max_value=15.0),
    )
    @settings(max_examples=100)
    def test_deviation_non_negative(self, fuel_level: float, consumption_rate: float):
        """Total deviation is always non-negative."""
        planner = RoutePlanner(tank_capacity=50.0)
        origin = GeoPoint(latitude=48.8, longitude=2.3)
        destination = GeoPoint(latitude=49.0, longitude=2.5)
        stop = GeoPoint(latitude=48.9, longitude=2.4)

        constraints = [RouteConstraint(type="fuel", location=stop, label="Stop")]
        route = planner.compute_route_with_constraints(
            origin, destination, constraints, fuel_level, consumption_rate
        )

        assert route.total_deviation_km >= 0.0

    @given(
        fuel_level=st.floats(min_value=10.0, max_value=100.0),
        consumption_rate=st.floats(min_value=3.0, max_value=15.0),
    )
    @settings(max_examples=100)
    def test_additional_time_non_negative(self, fuel_level: float, consumption_rate: float):
        """Additional time is always non-negative."""
        planner = RoutePlanner(tank_capacity=50.0)
        origin = GeoPoint(latitude=48.8, longitude=2.3)
        destination = GeoPoint(latitude=49.0, longitude=2.5)
        stop = GeoPoint(latitude=48.9, longitude=2.4)

        constraints = [RouteConstraint(type="food", location=stop, label="Restaurant")]
        route = planner.compute_route_with_constraints(
            origin, destination, constraints, fuel_level, consumption_rate
        )

        assert route.additional_time_minutes >= 0.0

    def test_empty_constraints_no_deviation(self):
        """Route with no constraints has zero deviation."""
        planner = RoutePlanner()
        origin = GeoPoint(latitude=48.8, longitude=2.3)
        destination = GeoPoint(latitude=49.0, longitude=2.5)

        route = planner.compute_route_with_constraints(
            origin, destination, [], fuel_level=50.0, consumption_rate=8.0
        )

        assert route.total_deviation_km == 0.0
