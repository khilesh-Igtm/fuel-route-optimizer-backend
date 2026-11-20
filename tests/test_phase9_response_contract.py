import pytest

from tests.phase9_fixtures import create_valid_response


@pytest.fixture
def valid_response():
    return create_valid_response()


def test_response_has_all_top_level_fields(valid_response):
    expected = {
        "success",
        "route",
        "vehicle",
        "fuel_optimization",
        "cost_summary",
        "fuel_cost_breakdown",
        "station_matching",
        "data_quality",
    }

    assert expected.issubset(valid_response)


def test_response_success_flag_is_boolean(valid_response):
    assert valid_response["success"] is True


def test_route_geometry_is_valid_linestring(valid_response):
    geometry = valid_response["route"]["geometry"]

    assert geometry["type"] == "LineString"
    assert len(geometry["coordinates"]) >= 2

    for longitude, latitude in geometry["coordinates"]:
        assert -180 <= longitude <= 180
        assert -90 <= latitude <= 90


def test_route_distance_is_positive(valid_response):
    assert valid_response["route"]["distance_miles"] > 0


def test_vehicle_information_is_valid(valid_response):
    vehicle = valid_response["vehicle"]

    assert vehicle["tank_range_miles"] > 0
    assert vehicle["mpg"] > 0
    assert vehicle["tank_capacity_gallons"] > 0


def test_fuel_optimization_contains_required_fields(valid_response):
    optimization = valid_response["fuel_optimization"]

    required = {
        "route_distance_miles",
        "total_fuel_consumed_gallons",
        "initial_fuel_gallons",
        "additional_fuel_purchased_gallons",
        "remaining_fuel_gallons",
        "estimated_total_fuel_cost",
        "number_of_stops",
        "stops",
        "optimization_method",
    }

    assert required.issubset(optimization)


def test_number_of_stops_matches_stop_list(valid_response):
    optimization = valid_response["fuel_optimization"]

    assert optimization["number_of_stops"] == len(
        optimization["stops"]
    )


def test_station_matching_statistics_are_consistent(valid_response):
    matching = valid_response["station_matching"]

    assert matching["corridor_width_miles"] > 0
    assert matching["stations_considered"] >= 0
    assert matching["total_matched_stations"] >= 0
    assert matching["selected_stops"] >= 0

    assert matching["selected_stops"] == (
        valid_response["fuel_optimization"]["number_of_stops"]
    )


def test_data_quality_flags_are_consistent(valid_response):
    quality = valid_response["data_quality"]

    assert quality["approximate_coordinate_stops"] >= 0

    assert quality["has_approximate_coordinates"] == (
        quality["approximate_coordinate_stops"] > 0
    )


def test_fuel_cost_breakdown_matches_paid_stops(valid_response):
    breakdown = valid_response["fuel_cost_breakdown"]

    assert isinstance(breakdown["stops"], list)

    assert len(breakdown["stops"]) == (
        valid_response["cost_summary"]["number_of_paid_stops"]
    )


def test_every_stop_has_required_information(valid_response):
    for stop in valid_response["fuel_optimization"]["stops"]:
        assert stop["truckstop_id"]
        assert stop["name"]
        assert stop["fuel_price_per_gallon"] > 0
        assert stop["fuel_to_purchase_gallons"] > 0
        assert stop["estimated_stop_cost"] >= 0

        assert -90 <= stop["latitude"] <= 90
        assert -180 <= stop["longitude"] <= 180


def test_response_currency_is_usd(valid_response):
    assert valid_response["cost_summary"]["currency"] == "USD"