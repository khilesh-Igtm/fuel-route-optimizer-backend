
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory

from apps.trips.views import OptimizeRouteAPIView


@pytest.fixture
def api_factory():
    return APIRequestFactory()


@pytest.fixture
def valid_payload():
    return {
        "start_location": "New York, NY",
        "end_location": "Los Angeles, CA",
        "corridor_width_miles": 10,
        "max_stations": 500,
    }


@pytest.fixture
def mock_route_analysis():
    return {
        "start": {
            "name": "New York, NY",
        },
        "destination": {
            "name": "Los Angeles, CA",
        },
        "route": {
            "distance_miles": 2794.01,
            "duration_minutes": 2400,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0060, 40.7128],
                    [-118.2437, 34.0522],
                ],
            },
        },
    }


@pytest.fixture
def mock_matching_result():
    return {
        "stations": [
            {
                "id": 1,
                "name": "Test Fuel Station",
            },
        ],
        "matching": {
            "corridor_width_miles": 10,
            "total_matched_stations": 1,
        },
    }


@pytest.fixture
def mock_optimization():
    return {
        "stops": [
            {
                "coordinates_are_approximate": False,
                "name": "Test Fuel Station",
            },
        ],
        "number_of_stops": 1,
    }


@pytest.fixture
def mock_cost_summary():
    return {
        "total_fuel_cost": 703.38,
        "total_gallons": 70.338,
        "stops": [
            {
                "station": "Test Fuel Station",
                "fuel_cost": 703.38,
            },
        ],
    }


@pytest.mark.django_db
def test_optimize_route_success(
    api_factory,
    valid_payload,
    mock_route_analysis,
    mock_matching_result,
    mock_optimization,
    mock_cost_summary,
):
    with (
        patch(
            "apps.trips.views.calculate_route_analysis",
            return_value=mock_route_analysis,
        ) as route_mock,
        patch(
            "apps.trips.views.match_fuel_stations_to_route",
            return_value=mock_matching_result,
        ) as matching_mock,
        patch(
            "apps.trips.views.optimize_fuel_stops",
            return_value=mock_optimization,
        ) as optimization_mock,
        patch(
            "apps.trips.views.calculate_trip_cost",
            return_value=mock_cost_summary,
        ) as cost_mock,
    ):
        request = api_factory.post(
            "/api/v1/route/optimize/",
            valid_payload,
            format="json",
        )

        response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 200

    assert response.data["success"] is True

    assert response.data["route"]["distance_miles"] == 2794.01

    assert "fuel_optimization" in response.data

    assert "cost_summary" in response.data

    assert "fuel_cost_breakdown" in response.data

    assert response.data["cost_summary"]["total_fuel_cost"] == 703.38

    assert len(
        response.data["fuel_cost_breakdown"]["stops"]
    ) == 1

    assert response.data["station_matching"]["selected_stops"] == 1

    assert route_mock.called
    assert matching_mock.called
    assert optimization_mock.called
    assert cost_mock.called


@pytest.mark.django_db
def test_optimize_route_accepts_long_trips(
    api_factory,
    valid_payload,
    mock_route_analysis,
    mock_matching_result,
    mock_optimization,
    mock_cost_summary,
):
    with (
        patch(
            "apps.trips.views.calculate_route_analysis",
            return_value=mock_route_analysis,
        ),
        patch(
            "apps.trips.views.match_fuel_stations_to_route",
            return_value=mock_matching_result,
        ),
        patch(
            "apps.trips.views.optimize_fuel_stops",
            return_value=mock_optimization,
        ),
        patch(
            "apps.trips.views.calculate_trip_cost",
            return_value=mock_cost_summary,
        ),
    ):
        request = api_factory.post(
            "/api/v1/route/optimize/",
            valid_payload,
            format="json",
        )

        response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 200
    assert response.data["route"]["distance_miles"] > 500


@pytest.mark.django_db
def test_optimize_route_rejects_missing_locations(
    api_factory,
):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400
    assert response.data["success"] is False
    assert "end_location" in response.data["errors"]


@pytest.mark.django_db
def test_optimize_route_rejects_same_locations(
    api_factory,
):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York",
            "end_location": "new york",
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400
    assert response.data["success"] is False


@pytest.mark.django_db
def test_optimize_route_rejects_invalid_corridor_width(
    api_factory,
):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York",
            "end_location": "Los Angeles",
            "corridor_width_miles": 0,
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400
    assert "corridor_width_miles" in response.data["errors"]


@pytest.mark.django_db
def test_optimize_route_rejects_excessive_max_stations(
    api_factory,
):
    request = api_factory.post(
        "/api/v1/route/optimize/",
        {
            "start_location": "New York",
            "end_location": "Los Angeles",
            "max_stations": 501,
        },
        format="json",
    )

    response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 400
    assert "max_stations" in response.data["errors"]


@pytest.mark.django_db
def test_optimize_route_returns_422_for_value_error(
    api_factory,
    valid_payload,
):
    with patch(
        "apps.trips.views.calculate_route_analysis",
        side_effect=ValueError("No valid route found."),
    ):
        request = api_factory.post(
            "/api/v1/route/optimize/",
            valid_payload,
            format="json",
        )

        response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 422
    assert response.data["success"] is False
    assert response.data["error"] == "No valid route found."
    assert response.data["error_code"] == "ROUTE_OPTIMIZATION_ERROR"


@pytest.mark.django_db
def test_optimize_route_returns_502_for_unexpected_error(
    api_factory,
    valid_payload,
):
    with patch(
        "apps.trips.views.calculate_route_analysis",
        side_effect=RuntimeError("External routing service failed."),
    ):
        request = api_factory.post(
            "/api/v1/route/optimize/",
            valid_payload,
            format="json",
        )

        response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 502
    assert response.data["success"] is False
    assert response.data["error_code"] == "ROUTE_SERVICE_UNAVAILABLE"


@pytest.mark.django_db
def test_optimize_route_uses_default_parameters(
    api_factory,
    mock_route_analysis,
    mock_matching_result,
    mock_optimization,
    mock_cost_summary,
):
    with (
        patch(
            "apps.trips.views.calculate_route_analysis",
            return_value=mock_route_analysis,
        ),
        patch(
            "apps.trips.views.match_fuel_stations_to_route",
            return_value=mock_matching_result,
        ) as matching_mock,
        patch(
            "apps.trips.views.optimize_fuel_stops",
            return_value=mock_optimization,
        ),
        patch(
            "apps.trips.views.calculate_trip_cost",
            return_value=mock_cost_summary,
        ),
    ):
        request = api_factory.post(
            "/api/v1/route/optimize/",
            {
                "start_location": "New York",
                "end_location": "Los Angeles",
            },
            format="json",
        )

        response = OptimizeRouteAPIView.as_view()(request)

    assert response.status_code == 200

    matching_mock.assert_called_once()

    assert (
        matching_mock.call_args.kwargs["corridor_width_miles"]
        == 10.0
    )

    assert matching_mock.call_args.kwargs["max_results"] == 100
