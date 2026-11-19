
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.routing.station_matching import (
    _build_spatial_index,
    _candidate_segments_for_point,
    _get_route_coordinates,
    _project_onto_indexed_route,
    find_nearest_route_position,
    match_fuel_stations_to_route,
)


def make_route():
    coordinates = [
        [-100.0 + (index * 0.1), 40.0]
        for index in range(101)
    ]

    return {
        "start": {"name": "Start"},
        "destination": {"name": "Destination"},
        "route": {
            "distance_miles": 500.0,
            "duration_minutes": 500.0,
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
        },
    }


def make_station(
    station_id,
    latitude,
    longitude,
):
    return SimpleNamespace(
        truckstop_id=station_id,
        name=f"Station {station_id}",
        address="Test Address",
        city="Test City",
        state="TX",
        rack_id="TX01",
        retail_price=3.50,
        latitude=latitude,
        longitude=longitude,
        coordinates_are_approximate=False,
    )


def test_spatial_index_contains_route_segments():
    route = make_route()

    coordinates = _get_route_coordinates(route)

    index = _build_spatial_index(
        coordinates,
        corridor_width_miles=10,
    )

    assert len(index.segments) == 100
    assert len(index.cells) > 0


def test_spatial_index_finds_nearby_segments():
    route = make_route()

    coordinates = _get_route_coordinates(route)

    index = _build_spatial_index(
        coordinates,
        corridor_width_miles=10,
    )

    candidate_ids = _candidate_segments_for_point(
        40.02,
        -95.0,
        index,
    )

    assert len(candidate_ids) > 0


def test_spatial_index_excludes_faraway_segments():
    route = make_route()

    coordinates = _get_route_coordinates(route)

    index = _build_spatial_index(
        coordinates,
        corridor_width_miles=10,
    )

    candidate_ids = _candidate_segments_for_point(
        20.0,
        -95.0,
        index,
    )

    assert candidate_ids == ()


def test_indexed_projection_matches_nearby_station():
    route = make_route()

    coordinates = _get_route_coordinates(route)

    index = _build_spatial_index(
        coordinates,
        corridor_width_miles=10,
    )

    projection, checks = _project_onto_indexed_route(
        40.02,
        -95.0,
        index,
    )

    assert projection is not None
    assert projection.distance_from_route_miles < 10
    assert checks < len(index.segments)


def test_indexed_projection_ignores_distant_station():
    route = make_route()

    coordinates = _get_route_coordinates(route)

    index = _build_spatial_index(
        coordinates,
        corridor_width_miles=10,
    )

    projection, checks = _project_onto_indexed_route(
        20.0,
        -95.0,
        index,
    )

    assert projection is None
    assert checks == 0


def test_full_match_uses_spatial_index():
    route = make_route()

    stations = [
        make_station(
            station_id=index,
            latitude=20.0,
            longitude=-95.0,
        )
        for index in range(6099)
    ]

    stations.append(
        make_station(
            7000,
            40.02,
            -95.0,
        )
    )

    with patch(
        "apps.routing.station_matching._get_stations",
        return_value=stations,
    ):
        result = match_fuel_stations_to_route(
            route,
            corridor_width_miles=10,
            max_results=100,
        )

    assert result["matching"]["total_stations_checked"] == 6100

    assert result["matching"][
        "candidate_segment_checks"
    ] < 6100 * 100

    assert result["matching"][
        "total_matched_stations"
    ] == 1

    assert result["stations"][0]["truckstop_id"] == 7000


def test_full_match_preserves_station_metadata():
    route = make_route()

    station = make_station(
        101,
        40.02,
        -95.0,
    )

    station.coordinates_are_approximate = True

    with patch(
        "apps.routing.station_matching._get_stations",
        return_value=[station],
    ):
        result = match_fuel_stations_to_route(route)

    matched = result["stations"][0]

    assert matched["coordinates_are_approximate"] is True
    assert matched["retail_price"] == 3.50
    assert matched["detour_distance_miles"] == round(
        matched["distance_from_route_miles"] * 2,
        2,
    )


def test_invalid_corridor_is_rejected():
    route = make_route()

    with pytest.raises(ValueError):
        match_fuel_stations_to_route(
            route,
            corridor_width_miles=0,
        )


def test_invalid_max_results_is_rejected():
    route = make_route()

    with pytest.raises(ValueError):
        match_fuel_stations_to_route(
            route,
            max_results=0,
        )


def test_nearest_route_position_still_works():
    coordinates = [
        (40.0, -100.0),
        (40.0, -99.0),
        (40.0, -98.0),
    ]

    projection = find_nearest_route_position(
        40.05,
        -99.0,
        coordinates,
    )

    assert projection.distance_from_start_miles > 0
    assert projection.distance_from_route_miles > 0
