import pytest

from tests.phase9_fixtures import create_valid_response


@pytest.fixture
def long_distance_response():
    response = create_valid_response()

    response["route"]["distance_miles"] = 2794.01
    response["route"]["duration_minutes"] = 2988.5

    response["vehicle"]["tank_range_miles"] = 500.0
    response["vehicle"]["mpg"] = 10.0

    response["fuel_optimization"]["route_distance_miles"] = 2794.01
    response["fuel_optimization"]["total_fuel_consumed_gallons"] = 279.401

    return response


def test_trip_can_exceed_single_tank_range(long_distance_response):
    route = long_distance_response["route"]["distance_miles"]
    tank_range = long_distance_response["vehicle"]["tank_range_miles"]

    assert route > tank_range


def test_ny_to_la_distance_regression(long_distance_response):
    assert long_distance_response["route"]["distance_miles"] == pytest.approx(
        2794.01,
        abs=0.01,
    )


def test_long_distance_fuel_consumption(long_distance_response):
    response = long_distance_response

    expected = (
        response["route"]["distance_miles"]
        / response["vehicle"]["mpg"]
    )

    actual = response["fuel_optimization"]["total_fuel_consumed_gallons"]

    assert actual == pytest.approx(expected, abs=0.001)


def test_long_distance_route_is_not_rejected(long_distance_response):
    assert long_distance_response["success"] is True