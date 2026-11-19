
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class OptimizationNode:
    index: int
    distance: float
    price: float | None
    station: dict[str, Any] | None


@dataclass
class OptimizationState:
    cost: float
    previous_state: tuple[int, int] | None
    purchase: float
    stop_index: int | None


def _valid_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if isfinite(number) else None


def _prepare_stations(
    stations: list[dict[str, Any]],
    route_distance: float,
) -> list[OptimizationNode]:

    prepared = []
    seen_ids = set()

    for station in stations:
        distance = _valid_number(
            station.get("distance_from_start_miles")
        )
        price = _valid_number(
            station.get("retail_price")
        )

        if distance is None or price is None:
            continue

        if not 0 <= distance <= route_distance:
            continue

        if price <= 0:
            continue

        station_id = station.get("truckstop_id")

        if station_id is not None:
            if station_id in seen_ids:
                continue
            seen_ids.add(station_id)

        prepared.append(
            {
                "distance": distance,
                "price": price,
                "station": station,
            }
        )

    prepared.sort(key=lambda item: item["distance"])

    nodes = [
        OptimizationNode(
            index=0,
            distance=0.0,
            price=None,
            station=None,
        )
    ]

    for item in prepared:
        nodes.append(
            OptimizationNode(
                index=len(nodes),
                distance=item["distance"],
                price=item["price"],
                station=item["station"],
            )
        )

    nodes.append(
        OptimizationNode(
            index=len(nodes),
            distance=route_distance,
            price=None,
            station=None,
        )
    )

    return nodes


def optimize_fuel_stops(
    *,
    route_distance_miles: float,
    stations: list[dict[str, Any]],
    tank_range_miles: float = 500.0,
    mpg: float = 10.0,
) -> dict[str, Any]:

    route_distance = _valid_number(route_distance_miles)
    tank_range = _valid_number(tank_range_miles)
    efficiency = _valid_number(mpg)

    if route_distance is None or route_distance <= 0:
        raise ValueError("Route distance must be positive.")

    if tank_range is None or tank_range <= 0:
        raise ValueError("Tank range must be positive.")

    if efficiency is None or efficiency <= 0:
        raise ValueError("Vehicle MPG must be positive.")

    if not isinstance(stations, list):
        raise ValueError("Stations must be a list.")

    tank_capacity = tank_range / efficiency

    nodes = _prepare_stations(
        stations,
        route_distance,
    )

    # State key:
    # (last_refuel_node, current_node)
    #
    # Before the first paid refueling stop, remaining fuel
    # comes from the original full tank.
    #
    # After a paid stop, the purchase is exactly enough
    # to reach the next node, so arrival fuel is zero.

    states = {
        (0, 0): OptimizationState(
            cost=0.0,
            previous_state=None,
            purchase=0.0,
            stop_index=None,
        )
    }

    for current_index, current_node in enumerate(nodes[:-1]):

        current_states = [
            (key, state)
            for key, state in states.items()
            if key[1] == current_index
        ]

        for state_key, state in current_states:

            last_refuel_index, _ = state_key

            if last_refuel_index == 0:
                remaining_fuel = (
                    tank_capacity
                    - current_node.distance / efficiency
                )
            else:
                remaining_fuel = 0.0

            remaining_fuel = max(
                0.0,
                remaining_fuel,
            )

            for next_index in range(
                current_index + 1,
                len(nodes),
            ):

                next_node = nodes[next_index]

                distance = (
                    next_node.distance
                    - current_node.distance
                )

                if distance > tank_range:
                    break

                required_fuel = distance / efficiency

                purchase = max(
                    0.0,
                    required_fuel - remaining_fuel,
                )

                if purchase > 0:
                    if current_node.station is None:
                        continue

                    if current_node.price is None:
                        continue

                new_last_refuel = (
                    current_index
                    if purchase > 0
                    else last_refuel_index
                )

                purchase_cost = (
                    purchase * (current_node.price or 0.0)
                )

                new_cost = state.cost + purchase_cost

                new_key = (
                    new_last_refuel,
                    next_index,
                )

                existing = states.get(new_key)

                if existing is None or new_cost < existing.cost:
                    states[new_key] = OptimizationState(
                        cost=new_cost,
                        previous_state=state_key,
                        purchase=purchase,
                        stop_index=(
                            current_index
                            if purchase > 0
                            else None
                        ),
                    )

    destination_index = len(nodes) - 1

    possible_destinations = [
        (key, state)
        for key, state in states.items()
        if key[1] == destination_index
    ]

    if not possible_destinations:
        raise ValueError(
            "No feasible fuel-stop route found. "
            "Available stations cannot cover the journey "
            "within the vehicle's tank range."
        )

    best_key, best_state = min(
        possible_destinations,
        key=lambda item: item[1].cost,
    )

    path = []
    current_key = best_key

    while current_key is not None:
        state = states[current_key]
        path.append((current_key, state))
        current_key = state.previous_state

    path.reverse()

    selected_stops = []

    for _, state in path:
        if state.stop_index is None:
            continue

        node = nodes[state.stop_index]
        station = node.station

        if station is None:
            continue

        price = node.price or 0.0
        gallons = state.purchase

        selected_stops.append(
            {
                "truckstop_id": station.get("truckstop_id"),
                "name": station.get("name"),
                "address": station.get("address"),
                "city": station.get("city"),
                "state": station.get("state"),
                "latitude": station.get("latitude"),
                "longitude": station.get("longitude"),
                "coordinates_are_approximate": bool(
                    station.get(
                        "coordinates_are_approximate",
                        False,
                    )
                ),
                "distance_from_start_miles": round(
                    node.distance,
                    2,
                ),
                "detour_distance_miles": station.get(
                    "detour_distance_miles"
                ),
                "fuel_price_per_gallon": round(price, 3),
                "fuel_to_purchase_gallons": round(
                    gallons,
                    3,
                ),
                "estimated_stop_cost": round(
                    gallons * price,
                    2,
                ),
            }
        )

    total_consumed = route_distance / efficiency

    total_purchased = sum(
        stop["fuel_to_purchase_gallons"]
        for stop in selected_stops
    )

    return {
        "route_distance_miles": round(
            route_distance,
            2,
        ),
        "total_fuel_consumed_gallons": round(
            total_consumed,
            3,
        ),
        "initial_fuel_gallons": round(
            tank_capacity,
            3,
        ),
        "additional_fuel_purchased_gallons": round(
            total_purchased,
            3,
        ),
        "remaining_fuel_gallons": round(
            max(
                0.0,
                tank_capacity
                + total_purchased
                - total_consumed,
            ),
            3,
        ),
        "estimated_total_fuel_cost": round(
            best_state.cost,
            2,
        ),
        "number_of_stops": len(selected_stops),
        "stops": selected_stops,
        "optimization_method": "dynamic_programming",
    }
