
"""
Fuel station matching against an OSRM road route.

This module:
- Finds existing FuelStation records near a route.
- Calculates the nearest point on the route geometry.
- Measures distance from the route using Haversine distance.
- Calculates approximate geometric detour distance.
- Orders stations from origin to destination.

No fuel-stop optimization is performed here.
"""

from dataclasses import dataclass
from math import cos, radians
from typing import Any, Iterable

from apps.fuel.models import FuelStation
from apps.routing.route_analysis import haversine_distance


DEFAULT_CORRIDOR_WIDTH_MILES = 10.0
DEFAULT_MAX_RESULTS = 100


@dataclass(frozen=True)
class RouteProjection:
    """A station's nearest projected position on the route."""

    distance_from_start_miles: float
    distance_from_route_miles: float
    latitude: float
    longitude: float


def _validate_coordinates(
    latitude: float,
    longitude: float,
) -> bool:
    """Check whether latitude and longitude are geographically valid."""

    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def _project_point_onto_segment(
    point_latitude: float,
    point_longitude: float,
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> tuple[float, float, float]:
    """
    Project a geographic point onto a route segment.

    Uses a local equirectangular projection to calculate the
    closest point along the segment.

    Returns:
        (fraction, projected_latitude, projected_longitude)
    """

    mean_latitude = radians(
        (start_latitude + end_latitude) / 2
    )

    longitude_scale = cos(mean_latitude)

    start_x = start_longitude * longitude_scale
    start_y = start_latitude

    end_x = end_longitude * longitude_scale
    end_y = end_latitude

    point_x = point_longitude * longitude_scale
    point_y = point_latitude

    segment_x = end_x - start_x
    segment_y = end_y - start_y

    segment_length_squared = (
        segment_x**2 + segment_y**2
    )

    if segment_length_squared == 0:
        fraction = 0.0
    else:
        fraction = (
            (point_x - start_x) * segment_x
            + (point_y - start_y) * segment_y
        ) / segment_length_squared

        fraction = max(0.0, min(1.0, fraction))

    projected_latitude = (
        start_latitude
        + fraction * (end_latitude - start_latitude)
    )

    projected_longitude = (
        start_longitude
        + fraction * (end_longitude - start_longitude)
    )

    return (
        fraction,
        projected_latitude,
        projected_longitude,
    )


def find_nearest_route_position(
    latitude: float,
    longitude: float,
    route_coordinates: list[list[float]],
) -> RouteProjection:
    """
    Find the nearest point on a route to a station.

    GeoJSON coordinates use [longitude, latitude].
    """

    if not _validate_coordinates(latitude, longitude):
        raise ValueError("Invalid station coordinates.")

    if len(route_coordinates) < 2:
        raise ValueError(
            "Route must contain at least two coordinates."
        )

    cumulative_distance = 0.0
    best_projection = None
    best_distance = float("inf")

    for index in range(len(route_coordinates) - 1):
        start_longitude, start_latitude = route_coordinates[index]
        end_longitude, end_latitude = route_coordinates[index + 1]

        if not (
            _validate_coordinates(start_latitude, start_longitude)
            and _validate_coordinates(end_latitude, end_longitude)
        ):
            raise ValueError("Route contains invalid coordinates.")

        segment_distance = haversine_distance(
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        )

        fraction, projected_latitude, projected_longitude = (
            _project_point_onto_segment(
                latitude,
                longitude,
                start_latitude,
                start_longitude,
                end_latitude,
                end_longitude,
            )
        )

        distance_from_route = haversine_distance(
            latitude,
            longitude,
            projected_latitude,
            projected_longitude,
        )

        if distance_from_route < best_distance:
            best_distance = distance_from_route

            best_projection = RouteProjection(
                distance_from_start_miles=(
                    cumulative_distance
                    + fraction * segment_distance
                ),
                distance_from_route_miles=distance_from_route,
                latitude=projected_latitude,
                longitude=projected_longitude,
            )

        cumulative_distance += segment_distance

    if best_projection is None:
        raise ValueError("Unable to project station onto route.")

    return best_projection


def _get_route_coordinates(
    route_analysis: dict[str, Any],
) -> list[list[float]]:
    """Extract and validate GeoJSON route coordinates."""

    try:
        coordinates = route_analysis["route"]["geometry"]["coordinates"]
    except (KeyError, TypeError):
        raise ValueError(
            "Invalid route analysis: GeoJSON geometry is missing."
        ) from None

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError(
            "Route must contain at least two coordinates."
        )

    return coordinates


def _get_stations() -> Iterable[FuelStation]:
    """Load stations with usable geographic coordinates."""

    return FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )


def _serialize_station(
    station: FuelStation,
    projection: RouteProjection,
) -> dict[str, Any]:
    """
    Create the structured station matching result.

    Geometric detour assumes the vehicle leaves and rejoins
    the route at the nearest projected point.
    """

    return {
        "truckstop_id": station.truckstop_id,
        "name": station.name,
        "address": station.address,
        "city": station.city,
        "state": station.state,
        "rack_id": station.rack_id,
        "retail_price": station.retail_price,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "coordinates_are_approximate": (
            station.coordinates_are_approximate
        ),
        "distance_from_start_miles": round(
            projection.distance_from_start_miles,
            2,
        ),
        "distance_from_route_miles": round(
            projection.distance_from_route_miles,
            2,
        ),
        "detour_distance_miles": round(
            projection.distance_from_route_miles * 2,
            2,
        ),
    }


def match_fuel_stations_to_route(
    route_analysis: dict[str, Any],
    corridor_width_miles: float = DEFAULT_CORRIDOR_WIDTH_MILES,
    max_results: int | None = DEFAULT_MAX_RESULTS,
    stations: Iterable[FuelStation] | None = None,
) -> dict[str, Any]:
    """
    Match fuel stations to an existing calculated road route.

    Args:
        route_analysis:
            Output of calculate_route_analysis().

        corridor_width_miles:
            Maximum perpendicular distance from route.

        max_results:
            Maximum number of matched stations.
            Pass None to return every matching station.

        stations:
            Optional station collection for testing or reuse.
            Normally loaded from the FuelStation database.

    Returns:
        Structured route and station matching information.

    Note:
        This function does not enforce vehicle tank range.
        It also does not select optimal fuel stops.
    """

    if corridor_width_miles < 0:
        raise ValueError(
            "Corridor width cannot be negative."
        )

    if max_results is not None and max_results < 1:
        raise ValueError(
            "max_results must be at least 1 or None."
        )

    route_coordinates = _get_route_coordinates(route_analysis)

    if stations is None:
        stations = _get_stations()

    matched_stations = []

    for station in stations:
        latitude = station.latitude
        longitude = station.longitude

        if latitude is None or longitude is None:
            continue

        if not _validate_coordinates(latitude, longitude):
            continue

        latitude = float(latitude)
        longitude = float(longitude)

        projection = find_nearest_route_position(
            latitude=latitude,
            longitude=longitude,
            route_coordinates=route_coordinates,
        )

        if (
            projection.distance_from_route_miles
            > corridor_width_miles
        ):
            continue

        matched_stations.append(
            _serialize_station(station, projection)
        )

    matched_stations.sort(
        key=lambda station: (
            station["distance_from_start_miles"],
            station["distance_from_route_miles"],
            str(station["truckstop_id"]),
        )
    )

    total_matched = len(matched_stations)

    if max_results is not None:
        matched_stations = matched_stations[:max_results]

    route = route_analysis["route"]

    return {
        "start": route_analysis.get("start"),
        "destination": route_analysis.get("destination"),
        "route": {
            "distance_miles": route["distance_miles"],
            "duration_minutes": route["duration_minutes"],
        },
        "matching": {
            "corridor_width_miles": corridor_width_miles,
            "total_matched_stations": total_matched,
            "returned_stations": len(matched_stations),
            "max_results": max_results,
        },
        "stations": matched_stations,
    }
