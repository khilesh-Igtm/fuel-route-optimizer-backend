
import pytest

from apps.fuel.cost_calculation import calculate_trip_cost


def create_stop(
    truckstop_id="1001",
    price=3.50,
    gallons=50,
):
    return {
        "truckstop_id": truckstop_id,
        "name": "Test Truck Stop",
        "city": "Denver",
        "state": "CO",
        "fuel_price_per_gallon": price,
        "fuel_to_purchase_gallons": gallons,
    }


def test_calculates_single_stop_cost():
    result = calculate_trip_cost(
        route_distance_miles=1000,
        mpg=10,
        tank_capacity_gallons=50,
        stops=[create_stop(price=3.50, gallons=50)],
    )

    assert result["total_fuel_consumed_gallons"] == 100
    assert result["initial_fuel_used_gallons"] == 50
    assert result["additional_fuel_purchased_gallons"] == 50
    assert result["total_fuel_cost"] == 175.00
    assert result["number_of_paid_stops"] == 1


def test_calculates_multiple_stop_costs():
    stops = [
        create_stop("1001", 3.50, 30),
        create_stop("1002", 3.80, 20),
    ]

    result = calculate_trip_cost(
        route_distance_miles=1000,
        mpg=10,
        tank_capacity_gallons=50,
        stops=stops,
    )

    assert result["total_fuel_cost"] == 181.00
    assert result["additional_fuel_purchased_gallons"] == 50
    assert result["number_of_paid_stops"] == 2
    assert len(result["stops"]) == 2


def test_initial_fuel_is_not_charged():
    result = calculate_trip_cost(
        route_distance_miles=300,
        mpg=10,
        tank_capacity_gallons=50,
        stops=[],
    )

    assert result["total_fuel_consumed_gallons"] == 30
    assert result["initial_fuel_used_gallons"] == 30
    assert result["initial_fuel_cost"] == 0
    assert result["total_fuel_cost"] == 0
    assert result["remaining_fuel_gallons"] == 20


def test_exact_tank_range_trip():
    result = calculate_trip_cost(
        route_distance_miles=500,
        mpg=10,
        tank_capacity_gallons=50,
        stops=[],
    )

    assert result["total_fuel_consumed_gallons"] == 50
    assert result["remaining_fuel_gallons"] == 0
    assert result["total_fuel_cost"] == 0


def test_long_distance_trip_is_supported():
    stops = [
        create_stop("1001", 3.50, 100),
        create_stop("1002", 3.80, 100),
        create_stop("1003", 3.60, 30),
    ]

    result = calculate_trip_cost(
        route_distance_miles=2800,
        mpg=10,
        tank_capacity_gallons=50,
        stops=stops,
    )

    assert result["total_fuel_consumed_gallons"] == 280
    assert result["additional_fuel_purchased_gallons"] == 230
    assert result["number_of_paid_stops"] == 3
    assert result["total_fuel_cost"] == 838.00


def test_stop_cost_is_calculated_from_price_and_quantity():
    result = calculate_trip_cost(
        route_distance_miles=1000,
        mpg=10,
        tank_capacity_gallons=50,
        stops=[create_stop(price=3.75, gallons=50)],
    )

    stop = result["stops"][0]

    assert stop["fuel_price_per_gallon"] == 3.75
    assert stop["fuel_purchased_gallons"] == 50
    assert stop["estimated_stop_cost"] == 187.50


def test_zero_purchase_is_not_counted_as_paid_stop():
    result = calculate_trip_cost(
        route_distance_miles=300,
        mpg=10,
        tank_capacity_gallons=50,
        stops=[create_stop(gallons=0)],
    )

    assert result["number_of_paid_stops"] == 0
    assert result["total_fuel_cost"] == 0
    assert result["stops"] == []


def test_negative_purchase_quantity_is_rejected():
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=1000,
            mpg=10,
            tank_capacity_gallons=50,
            stops=[create_stop(gallons=-10)],
        )


def test_invalid_station_price_is_rejected():
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=1000,
            mpg=10,
            tank_capacity_gallons=50,
            stops=[create_stop(price=0, gallons=50)],
        )


def test_missing_station_price_is_rejected():
    stop = create_stop()
    stop.pop("fuel_price_per_gallon")

    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=1000,
            mpg=10,
            tank_capacity_gallons=50,
            stops=[stop],
        )


def test_insufficient_fuel_is_rejected():
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=1000,
            mpg=10,
            tank_capacity_gallons=50,
            stops=[],
        )


@pytest.mark.parametrize(
    "distance, mpg, capacity",
    [
        (0, 10, 50),
        (-100, 10, 50),
        (100, 0, 50),
        (100, -10, 50),
        (100, 10, 0),
        (100, 10, -50),
    ],
)
def test_invalid_vehicle_or_route_values(
    distance,
    mpg,
    capacity,
):
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=distance,
            mpg=mpg,
            tank_capacity_gallons=capacity,
            stops=[],
        )


def test_non_finite_values_are_rejected():
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=float("inf"),
            mpg=10,
            tank_capacity_gallons=50,
            stops=[],
        )


def test_invalid_stops_argument_is_rejected():
    with pytest.raises(ValueError):
        calculate_trip_cost(
            route_distance_miles=100,
            mpg=10,
            tank_capacity_gallons=50,
            stops=None,
        )
