
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.routing.station_matching import (
    find_nearest_route_position,
    match_fuel_stations_to_route,
)


def create_station(
    truckstop_id,
    latitude,
    longitude,
    name=None,
    coordinates_are_approximate=False,
):
    return SimpleNamespace(
        truckstop_id=truckstop_id,
        name=name or f"Station {truckstop_id}",
        address="123 Test Road",
        city="Test City",
        state="CA",
        rack_id="RACK-01",
        retail_price=Decimal("3.459"),
        latitude=latitude,
        longitude=longitude,
        coordinates_are_approximate=coordinates_are_approximate,
    )


def create_route(
    coordinates=None,
    distance_miles=100.0,
    duration_minutes=120.0,
):
    if coordinates is None:
        coordinates = [
            [-100.0, 40.0],
            [-99.0, 40.0],
        ]

    return {
        "start": {
            "name": "Origin",
            "latitude": 40.0,
            "longitude": -100.0,
        },
        "destination": {
            "name": "Destination",
            "latitude": 40.0,
            "longitude": -99.0,
        },
        "route": {
            "distance_miles": distance_miles,
            "duration_minutes": duration_minutes,
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
        },
    }


class TestFindNearestRoutePosition:

    def test_station_on_route_has_zero_cross_track_distance(self):
        coordinates = [
            [-100.0, 40.0],
            [-99.0, 40.0],
        ]

        result = find_nearest_route_position(
            latitude=40.0,
            longitude=-99.5,
            route_coordinates=coordinates,
        )

        assert result.distance_from_route_miles == pytest.approx(
            0,
            abs=0.01,
        )

        assert result.distance_from_start_miles > 0

    def test_station_near_route_returns_positive_distance(self):
        coordinates = [
            [-100.0, 40.0],
            [-99.0, 40.0],
        ]

        result = find_nearest_route_position(
            latitude=40.01,
            longitude=-99.5,
            route_coordinates=coordinates,
        )

        assert result.distance_from_route_miles > 0

        assert result.distance_from_start_miles > 0

    def test_station_before_route_segment_is_projected_to_endpoint(self):
        coordinates = [
            [-100.0, 40.0],
            [-99.0, 40.0],
        ]

        result = find_nearest_route_position(
            latitude=40.0,
            longitude=-101.0,
            route_coordinates=coordinates,
        )

        assert result.longitude == pytest.approx(-100.0)

        assert result.distance_from_start_miles == pytest.approx(
            0,
            abs=0.01,
        )

    def test_invalid_station_coordinates_raise_error(self):
        with pytest.raises(ValueError):
            find_nearest_route_position(
                latitude=95.0,
                longitude=-100.0,
                route_coordinates=[
                    [-100.0, 40.0],
                    [-99.0, 40.0],
                ],
            )

    def test_route_requires_at_least_two_coordinates(self):
        with pytest.raises(ValueError):
            find_nearest_route_position(
                latitude=40.0,
                longitude=-100.0,
                route_coordinates=[
                    [-100.0, 40.0],
                ],
            )


class TestMatchFuelStationsToRoute:

    def test_matches_station_inside_corridor(self):
        route = create_route()

        station = create_station(
            truckstop_id="1001",
            latitude=40.005,
            longitude=-99.5,
        )

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=10,
            stations=[station],
        )

        assert result["matching"]["total_matched_stations"] == 1

        assert len(result["stations"]) == 1

        assert result["stations"][0]["truckstop_id"] == "1001"

    def test_excludes_station_outside_corridor(self):
        route = create_route()

        station = create_station(
            truckstop_id="1002",
            latitude=40.2,
            longitude=-99.5,
        )

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=5,
            stations=[station],
        )

        assert result["matching"]["total_matched_stations"] == 0

        assert result["stations"] == []

    def test_stations_are_sorted_from_origin_to_destination(self):
        route = create_route()

        stations = [
            create_station("3", 40.0, -99.2),
            create_station("1", 40.0, -99.8),
            create_station("2", 40.0, -99.5),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=5,
            stations=stations,
        )

        station_ids = [
            station["truckstop_id"]
            for station in result["stations"]
        ]

        assert station_ids == ["1", "2", "3"]

    def test_detour_is_twice_cross_track_distance(self):
        route = create_route()

        station = create_station(
            "1003",
            latitude=40.01,
            longitude=-99.5,
        )

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=10,
            stations=[station],
        )

        matched_station = result["stations"][0]

        expected_detour = (
            matched_station["distance_from_route_miles"] * 2
        )

        assert matched_station["detour_distance_miles"] == pytest.approx(
            expected_detour,
            abs=0.01,
        )

    def test_stations_with_missing_coordinates_are_skipped(self):
        route = create_route()

        stations = [
            create_station("1004", None, None),
            create_station("1005", 40.0, -99.5),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            stations=stations,
        )

        assert result["matching"]["total_matched_stations"] == 1

    def test_invalid_station_coordinates_are_skipped(self):
        route = create_route()

        stations = [
            create_station("1006", 95.0, -99.5),
            create_station("1007", 40.0, -99.5),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            stations=stations,
        )

        assert result["matching"]["total_matched_stations"] == 1

        assert result["stations"][0]["truckstop_id"] == "1007"

    def test_max_results_limits_returned_stations(self):
        route = create_route()

        stations = [
            create_station("1", 40.0, -99.8),
            create_station("2", 40.0, -99.6),
            create_station("3", 40.0, -99.4),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=5,
            max_results=2,
            stations=stations,
        )

        assert result["matching"]["total_matched_stations"] == 3

        assert result["matching"]["returned_stations"] == 2

        assert len(result["stations"]) == 2

    def test_none_max_results_returns_all_matching_stations(self):
        route = create_route()

        stations = [
            create_station("1", 40.0, -99.8),
            create_station("2", 40.0, -99.6),
            create_station("3", 40.0, -99.4),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            max_results=None,
            stations=stations,
        )

        assert len(result["stations"]) == 3

    def test_approximate_coordinates_flag_is_preserved(self):
        route = create_route()

        station = create_station(
            "1008",
            40.0,
            -99.5,
            coordinates_are_approximate=True,
        )

        result = match_fuel_stations_to_route(
            route_analysis=route,
            stations=[station],
        )

        assert (
            result["stations"][0]["coordinates_are_approximate"]
            is True
        )

    def test_invalid_corridor_width_raises_error(self):
        with pytest.raises(ValueError):
            match_fuel_stations_to_route(
                route_analysis=create_route(),
                corridor_width_miles=-5,
                stations=[],
            )

    def test_invalid_max_results_raises_error(self):
        with pytest.raises(ValueError):
            match_fuel_stations_to_route(
                route_analysis=create_route(),
                max_results=0,
                stations=[],
            )

    def test_invalid_route_geometry_raises_error(self):
        route = {
            "route": {
                "distance_miles": 100,
                "duration_minutes": 120,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [],
                },
            }
        }

        with pytest.raises(ValueError):
            match_fuel_stations_to_route(
                route_analysis=route,
                stations=[],
            )

    def test_database_station_loader_is_used_by_default(self):
        route = create_route()

        station = create_station(
            "1010",
            40.0,
            -99.5,
        )

        with patch(
            "apps.routing.station_matching._get_stations",
            return_value=[station],
        ) as mock_loader:

            result = match_fuel_stations_to_route(
                route_analysis=route,
            )

        mock_loader.assert_called_once()

        assert result["matching"]["total_matched_stations"] == 1

    def test_long_distance_routes_are_supported(self):
        # 30 degrees of longitude at the equator is over 2,000 miles.
        route = create_route(
            coordinates=[
                [-120.0, 0.0],
                [-90.0, 0.0],
            ],
            distance_miles=2071.0,
            duration_minutes=2000.0,
        )

        stations = [
            create_station("2001", 0.0, -110.0),
            create_station("2002", 0.0, -100.0),
        ]

        result = match_fuel_stations_to_route(
            route_analysis=route,
            corridor_width_miles=5,
            stations=stations,
        )

        assert result["route"]["distance_miles"] == 2071.0

        assert result["matching"]["total_matched_stations"] == 2

        assert len(result["stations"]) == 2
