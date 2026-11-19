
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory

from apps.trips.views import OptimizeRouteAPIView


@pytest.fixture
def api_factory():
    return APIRequestFactory()


@pytest.fixture
def sample_route():
    return {
        "start": {"name": "New York, NY"},
        "destination": {"name": "Los Angeles, CA"},
        "route": {
            "distance_miles": 2000.0,
            "duration_minutes": 1800.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0, 40.7],
                    [-118.2, 34.0],
                ],
            },
        },
    }


@pytest.fixture
def sample_matching():
    stations = []

    for station_id, distance, price in [
        (1, 400, 3.50),
        (2, 800, 3.20),
        (3, 1200, 3.10),
        (4, 1600, 3.00),
    ]:
        stations.append(
            {
                "truckstop_id": station_id,
                "name": f"Test Fuel {station_id}",
                "address": f"Address {station_id}",
                "city": "Test City",
                "state": "TX",
                "rack_id": f"TX0{station_id}",
                "retail_price": price,
                "latitude": 32.0,
                "longitude": -96.0,
                "coordinates_are_approximate": (
                    station_id == 2
                ),
                "distance_from_start_miles": distance,
                "distance_from_route_miles": 1.0,
                "detour_distance_miles": 2.0,
            }
        )

    return {
        "start": {},
        "destination": {},
        "route": {},
        "matching": {
            "corridor_width_miles": 10.0,
            "total_matched_stations": 4,
            "returned_stations": 4,
            "max_results": 100,
        },
        "stations": stations,
    }


@pytest.mark.django_db
@patch("apps.trips.views.match_fuel_stations_to_route")
@patch("apps.trips.views.calculate_route_analysis")
def test_optimize_route_success(
    mock_route,
    mock_matching,
    api_factory,
    sample_route,
    sample_matching,
):
    mock_route.return_value = sample_route
    mock_matching.return_value = sample_matching

    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York, NY",
            "end_location": "Los Angeles, CA",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["route"]["distance_miles"] == 2000

    assert response.data["vehicle"]["tank_range_miles"] == 500
    assert response.data["vehicle"]["mpg"] == 10

    optimization = response.data["fuel_optimization"]

    assert optimization["total_fuel_consumed_gallons"] == 200
    assert optimization["number_of_stops"] > 0

    assert response.data["data_quality"][
        "has_approximate_coordinates"
    ] is True

    mock_route.assert_called_once()
    mock_matching.assert_called_once()


@pytest.mark.django_db
def test_optimize_route_validation_error(api_factory):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "",
            "end_location": "Los Angeles, CA",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400
    assert response.data["success"] is False


@pytest.mark.django_db
def test_same_start_and_destination_rejected(api_factory):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York, NY",
            "end_location": "New York, NY",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400


@pytest.mark.django_db
@patch("apps.trips.views.calculate_route_analysis")
def test_route_service_error(mock_route, api_factory):
    mock_route.side_effect = ValueError(
        "Location could not be resolved."
    )

    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "Unknown Place",
            "end_location": "Los Angeles, CA",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 422
    assert response.data["success"] is False


@pytest.mark.django_db
@patch("apps.trips.views.match_fuel_stations_to_route")
@patch("apps.trips.views.calculate_route_analysis")
def test_no_feasible_fuel_route(
    mock_route,
    mock_matching,
    api_factory,
    sample_route,
):
    mock_route.return_value = sample_route

    mock_matching.return_value = {
        "matching": {
            "corridor_width_miles": 10.0,
            "total_matched_stations": 0,
            "returned_stations": 0,
            "max_results": 100,
        },
        "stations": [],
    }

    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York, NY",
            "end_location": "Los Angeles, CA",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 422
    assert response.data["success"] is False
