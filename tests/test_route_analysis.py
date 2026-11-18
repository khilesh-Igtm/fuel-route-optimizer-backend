
import math
from unittest.mock import patch

import pytest

from apps.routing.route_analysis import (
    RouteAnalysisError,
    analyze_route,
    calculate_route_analysis,
    haversine_distance,
    normalize_route_geometry,
    sample_route_points,
)


@pytest.fixture
def sample_geometry():
    return {
        "type": "LineString",
        "coordinates": [
            [-100.0, 40.0],
            [-99.5, 40.0],
            [-99.0, 40.0],
        ],
    }


@pytest.fixture
def sample_route(sample_geometry):
    return {
        "distance_meters": 170000,
        "distance_miles": 105.63,
        "duration_seconds": 7200,
        "duration_minutes": 120,
        "geometry": sample_geometry,
    }


def test_haversine_distance_same_coordinates():
    distance = haversine_distance(
        40.0,
        -100.0,
        40.0,
        -100.0,
    )

    assert distance == 0


def test_haversine_distance_calculation():
    distance = haversine_distance(
        0,
        0,
        0,
        1,
    )

    assert 69 < distance < 70


def test_normalize_route_geometry(sample_geometry):
    coordinates = normalize_route_geometry(sample_geometry)

    assert coordinates == [
        (-100.0, 40.0),
        (-99.5, 40.0),
        (-99.0, 40.0),
    ]


def test_invalid_geometry_type():
    with pytest.raises(RouteAnalysisError):
        normalize_route_geometry(
            {
                "type": "Point",
                "coordinates": [-100, 40],
            }
        )


def test_invalid_coordinate_range():
    with pytest.raises(RouteAnalysisError):
        normalize_route_geometry(
            {
                "type": "LineString",
                "coordinates": [
                    [200, 40],
                    [201, 41],
                ],
            }
        )


def test_sample_route_points(sample_geometry):
    coordinates = normalize_route_geometry(sample_geometry)

    points = sample_route_points(
        coordinates,
        interval_miles=25,
    )

    assert len(points) >= 2

    assert points[0]["latitude"] == 40.0
    assert points[0]["longitude"] == -100.0

    assert points[-1]["latitude"] == 40.0
    assert points[-1]["longitude"] == -99.0

    assert points[0]["distance_from_start_miles"] == 0
    assert points[-1]["distance_from_start_miles"] > 0


def test_sampling_interval_validation(sample_geometry):
    coordinates = normalize_route_geometry(sample_geometry)

    with pytest.raises(ValueError):
        sample_route_points(
            coordinates,
            interval_miles=0,
        )


def test_analyze_route_success(sample_route):
    result = analyze_route(sample_route)

    assert result["distance_miles"] == 105.63
    assert result["duration_minutes"] == 120
    assert result["route_coordinates_count"] == 3
    assert result["sampled_points_count"] >= 2

    assert result["geometry"]["type"] == "LineString"


def test_analyze_route_accepts_long_distance_trip(sample_route):
    """
    A trip can exceed the vehicle's single-tank range.
    Refueling will be handled by the optimization layer.
    """

    sample_route["distance_miles"] = 2000
    sample_route["duration_minutes"] = 1800

    result = analyze_route(sample_route)

    assert result["distance_miles"] == 2000
    assert result["duration_minutes"] == 1800
    assert result["sampled_points_count"] >= 2


def test_analyze_route_invalid_distance(sample_route):
    sample_route["distance_miles"] = math.inf

    with pytest.raises(RouteAnalysisError):
        analyze_route(sample_route)


def test_calculate_route_analysis_success(sample_route):
    with patch(
        "apps.routing.route_analysis.calculate_route"
    ) as mock_calculate_route:

        mock_calculate_route.return_value = {
            "start": {
                "latitude": 40.0,
                "longitude": -100.0,
                "display_name": "Start City",
            },
            "destination": {
                "latitude": 40.0,
                "longitude": -99.0,
                "display_name": "Destination City",
            },
            "route": sample_route,
        }

        result = calculate_route_analysis(
            "Start City",
            "Destination City",
        )

    assert result["start"]["display_name"] == "Start City"
    assert result["destination"]["display_name"] == "Destination City"

    assert result["route"]["distance_miles"] == 105.63

    mock_calculate_route.assert_called_once_with(
        "Start City",
        "Destination City",
    )


def test_calculate_route_analysis_strips_locations(sample_route):
    with patch(
        "apps.routing.route_analysis.calculate_route"
    ) as mock_calculate_route:

        mock_calculate_route.return_value = {
            "start": {},
            "destination": {},
            "route": sample_route,
        }

        calculate_route_analysis(
            "  Start City  ",
            "  Destination City  ",
        )

    mock_calculate_route.assert_called_once_with(
        "Start City",
        "Destination City",
    )


def test_calculate_route_analysis_requires_locations():
    with pytest.raises(ValueError):
        calculate_route_analysis("", "Destination")

    with pytest.raises(ValueError):
        calculate_route_analysis("Start", "  ")
