import pytest

from tests.phase9_fixtures import create_valid_response

@pytest.fixture
def response():
    return create_valid_response()


def test_fuel_consumption_matches_distance_and_mpg(response):
    route_distance = response["route"]["distance_miles"]
    mpg = response["vehicle"]["mpg"]

    expected_consumption = route_distance / mpg

    actual_consumption = (
        response["fuel_optimization"]
        ["total_fuel_consumed_gallons"]
    )

    assert actual_consumption == pytest.approx(
        expected_consumption,
        abs=0.01,
    )


def test_fuel_balance_is_consistent(response):
    optimization = response["fuel_optimization"]

    available_fuel = (
        optimization["initial_fuel_gallons"]
        + optimization["additional_fuel_purchased_gallons"]
    )

    consumed_and_remaining = (
        optimization["total_fuel_consumed_gallons"]
        + optimization["remaining_fuel_gallons"]
    )

    assert available_fuel == pytest.approx(
        consumed_and_remaining,
        abs=0.01,
    )


def test_stop_cost_matches_gallons_and_price(response):
    for stop in response["fuel_optimization"]["stops"]:
        expected_cost = (
            stop["fuel_to_purchase_gallons"]
            * stop["fuel_price_per_gallon"]
        )

        assert stop["estimated_stop_cost"] == pytest.approx(
            expected_cost,
            abs=0.02,
        )


def test_total_cost_matches_stop_costs(response):
    stops = response["fuel_optimization"]["stops"]

    expected_cost = sum(
        stop["estimated_stop_cost"]
        for stop in stops
    )

    actual_cost = response["cost_summary"]["total_fuel_cost"]

    assert actual_cost == pytest.approx(
        expected_cost,
        abs=0.02,
    )


def test_optimization_and_cost_summary_match(response):
    optimization = response["fuel_optimization"]
    summary = response["cost_summary"]

    assert optimization["number_of_stops"] == (
        summary["number_of_paid_stops"]
    )

    assert optimization["total_fuel_consumed_gallons"] == pytest.approx(
        summary["total_fuel_consumed_gallons"],
        abs=0.01,
    )

    assert optimization["estimated_total_fuel_cost"] == pytest.approx(
        summary["total_fuel_cost"],
        abs=0.01,
    )

    assert optimization["remaining_fuel_gallons"] == pytest.approx(
        summary["remaining_fuel_gallons"],
        abs=0.01,
    )


def test_fuel_purchases_never_exceed_tank_capacity(response):
    capacity = response["vehicle"]["tank_capacity_gallons"]
    remaining = response["fuel_optimization"]["remaining_fuel_gallons"]

    assert capacity > 0
    assert remaining <= capacity


def test_fuel_values_cannot_be_negative(response):
    optimization = response["fuel_optimization"]

    fields = [
        "total_fuel_consumed_gallons",
        "initial_fuel_gallons",
        "additional_fuel_purchased_gallons",
        "remaining_fuel_gallons",
        "estimated_total_fuel_cost",
    ]

    for field in fields:
        assert optimization[field] >= 0


def test_stop_distances_are_in_route_order(response):
    stops = response["fuel_optimization"]["stops"]

    distances = [
        stop["distance_from_start_miles"]
        for stop in stops
    ]

    assert distances == sorted(distances)


def test_initial_full_tank_has_no_initial_purchase_cost(response):
    summary = response["cost_summary"]

    assert summary["initial_fuel_cost"] == 0