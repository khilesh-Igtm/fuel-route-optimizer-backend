
import pytest

from apps.fuel.optimization import optimize_fuel_stops


def make_station(
    station_id,
    distance,
    price,
    approximate=False,
):
    return {
        "truckstop_id": station_id,
        "name": f"Station {station_id}",
        "address": "Test Address",
        "city": "Test City",
        "state": "TX",
        "retail_price": price,
        "latitude": 32.0,
        "longitude": -96.0,
        "coordinates_are_approximate": approximate,
        "distance_from_start_miles": distance,
        "distance_from_route_miles": 1.0,
        "detour_distance_miles": 2.0,
    }


def test_short_trip_needs_no_stops():
    result = optimize_fuel_stops(
        route_distance_miles=300,
        stations=[],
    )

    assert result["number_of_stops"] == 0
    assert result["total_fuel_consumed_gallons"] == 30
    assert result["initial_fuel_gallons"] == 50
    assert result["additional_fuel_purchased_gallons"] == 0
    assert result["remaining_fuel_gallons"] == 20
    assert result["estimated_total_fuel_cost"] == 0


def test_trip_of_exactly_one_tank_range():
    result = optimize_fuel_stops(
        route_distance_miles=500,
        stations=[],
    )

    assert result["number_of_stops"] == 0
    assert result["remaining_fuel_gallons"] == 0


def test_long_trip_uses_multiple_stops():
    stations = [
        make_station(1, 400, 3.50),
        make_station(2, 800, 3.20),
    ]

    result = optimize_fuel_stops(
        route_distance_miles=1200,
        stations=stations,
    )

    assert result["number_of_stops"] == 2
    assert result["additional_fuel_purchased_gallons"] == 70
    assert result["estimated_total_fuel_cost"] == 233
    assert result["remaining_fuel_gallons"] == 0


def test_optimizer_prefers_lower_cost_feasible_path():
    stations = [
        make_station(1, 400, 4.00),
        make_station(2, 450, 3.00),
        make_station(3, 800, 2.00),
    ]

    result = optimize_fuel_stops(
        route_distance_miles=1000,
        stations=stations,
    )

    selected_ids = [
        stop["truckstop_id"]
        for stop in result["stops"]
    ]

    assert selected_ids == [2, 3]

    assert result["additional_fuel_purchased_gallons"] == 50

    assert result["estimated_total_fuel_cost"] == 130


def test_2000_mile_trip_is_accepted():
    stations = [
        make_station(1, 400, 3.50),
        make_station(2, 800, 3.20),
        make_station(3, 1200, 3.10),
        make_station(4, 1600, 3.00),
    ]

    result = optimize_fuel_stops(
        route_distance_miles=2000,
        stations=stations,
    )

    assert result["route_distance_miles"] == 2000
    assert result["total_fuel_consumed_gallons"] == 200
    assert result["number_of_stops"] == 4


def test_unreachable_destination_raises_error():
    stations = [
        make_station(1, 600, 3.50),
    ]

    with pytest.raises(ValueError, match="No feasible"):
        optimize_fuel_stops(
            route_distance_miles=1000,
            stations=stations,
        )


def test_invalid_station_prices_are_ignored():
    stations = [
        make_station(1, 400, None),
        make_station(2, 450, -1),
    ]

    with pytest.raises(ValueError, match="No feasible"):
        optimize_fuel_stops(
            route_distance_miles=1000,
            stations=stations,
        )


def test_duplicate_station_ids_are_ignored():
    stations = [
        make_station(1, 400, 3.50),
        make_station(1, 450, 2.00),
        make_station(2, 800, 3.20),
    ]

    result = optimize_fuel_stops(
        route_distance_miles=1000,
        stations=stations,
    )

    selected_ids = [
        stop["truckstop_id"]
        for stop in result["stops"]
    ]

    assert selected_ids == [1, 2]


def test_approximate_coordinates_are_preserved():
    stations = [
        make_station(
            1,
            400,
            3.50,
            approximate=True,
        ),
    ]

    result = optimize_fuel_stops(
        route_distance_miles=600,
        stations=stations,
    )

    assert result["stops"][0][
        "coordinates_are_approximate"
    ] is True


def test_invalid_vehicle_configuration():
    with pytest.raises(ValueError):
        optimize_fuel_stops(
            route_distance_miles=100,
            stations=[],
            mpg=0,
        )

    with pytest.raises(ValueError):
        optimize_fuel_stops(
            route_distance_miles=100,
            stations=[],
            tank_range_miles=0,
        )
