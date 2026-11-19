
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


MONEY_PRECISION = Decimal("0.01")
GALLON_PRECISION = Decimal("0.001")


def _to_decimal(value: Any, field_name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")

    if not number.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    return number


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _round_gallons(value: Decimal) -> Decimal:
    return value.quantize(
        GALLON_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def calculate_trip_cost(
    route_distance_miles: float,
    mpg: float,
    tank_capacity_gallons: float,
    stops: list[dict],
) -> dict:
    """
    Calculate the complete fuel-cost breakdown for a trip.

    Initial tank fuel is considered already available.
    Only additional fuel purchases contribute to trip cost.
    """

    distance = _to_decimal(
        route_distance_miles,
        "route_distance_miles",
    )

    efficiency = _to_decimal(mpg, "mpg")

    tank_capacity = _to_decimal(
        tank_capacity_gallons,
        "tank_capacity_gallons",
    )

    if distance <= 0:
        raise ValueError("Route distance must be greater than zero.")

    if efficiency <= 0:
        raise ValueError("MPG must be greater than zero.")

    if tank_capacity <= 0:
        raise ValueError(
            "Tank capacity must be greater than zero."
        )

    if not isinstance(stops, list):
        raise ValueError("Stops must be provided as a list.")

    total_fuel_consumed = distance / efficiency

    initial_fuel_used = min(
        total_fuel_consumed,
        tank_capacity,
    )

    additional_fuel_purchased = Decimal("0")

    total_fuel_cost = Decimal("0")

    paid_stops = 0

    stop_breakdown = []

    for index, stop in enumerate(stops):
        if not isinstance(stop, dict):
            raise ValueError(
                f"Stop at index {index} must be a dictionary."
            )

        purchased_gallons = _to_decimal(
            stop.get("fuel_to_purchase_gallons", 0),
            f"Stop {index} fuel quantity",
        )

        if purchased_gallons < 0:
            raise ValueError(
                f"Stop {index} has a negative fuel quantity."
            )

        if purchased_gallons == 0:
            continue

        price = _to_decimal(
            stop.get("fuel_price_per_gallon"),
            f"Stop {index} fuel price",
        )

        if price <= 0:
            raise ValueError(
                f"Stop {index} has an invalid fuel price."
            )

        stop_cost = _round_money(
            purchased_gallons * price
        )

        additional_fuel_purchased += purchased_gallons
        total_fuel_cost += stop_cost
        paid_stops += 1

        stop_breakdown.append(
            {
                "truckstop_id": stop.get("truckstop_id"),
                "name": stop.get("name"),
                "city": stop.get("city"),
                "state": stop.get("state"),
                "fuel_price_per_gallon": float(price),
                "fuel_purchased_gallons": float(
                    _round_gallons(purchased_gallons)
                ),
                "estimated_stop_cost": float(stop_cost),
            }
        )

    remaining_fuel = (
        tank_capacity
        + additional_fuel_purchased
        - total_fuel_consumed
    )

    if remaining_fuel < Decimal("-0.001"):
        raise ValueError(
            "Selected fuel purchases are insufficient "
            "to cover total route fuel consumption."
        )

    remaining_fuel = max(
        Decimal("0"),
        remaining_fuel,
    )

    return {
        "currency": "USD",
        "total_fuel_consumed_gallons": float(
            _round_gallons(total_fuel_consumed)
        ),
        "initial_fuel_available_gallons": float(
            _round_gallons(tank_capacity)
        ),
        "initial_fuel_used_gallons": float(
            _round_gallons(initial_fuel_used)
        ),
        "initial_fuel_cost": 0.0,
        "additional_fuel_purchased_gallons": float(
            _round_gallons(additional_fuel_purchased)
        ),
        "remaining_fuel_gallons": float(
            _round_gallons(remaining_fuel)
        ),
        "total_fuel_cost": float(
            _round_money(total_fuel_cost)
        ),
        "number_of_paid_stops": paid_stops,
        "stops": stop_breakdown,
    }
