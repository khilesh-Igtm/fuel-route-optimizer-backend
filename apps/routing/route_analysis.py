
"""
Route analysis utilities.

This module processes the route returned by the existing OSRM service.
It does not perform fuel station matching or fuel optimization.

Important:
- Vehicle maximum single-tank range is NOT the maximum trip distance.
- Long-distance routes are supported.
- Refueling stops will be handled by subsequent optimization phases.
"""

import math

from apps.routing.services import calculate_route


DEFAULT_SAMPLE_INTERVAL_MILES = 25.0
EARTH_RADIUS_MILES = 3958.7613


class RouteAnalysisError(Exception):
    """Raised when route analysis cannot be completed."""


def haversine_distance(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Calculate great-circle distance between two coordinates in miles.
    """

    lat_1 = math.radians(latitude_1)
    lon_1 = math.radians(longitude_1)
    lat_2 = math.radians(latitude_2)
    lon_2 = math.radians(longitude_2)

    delta_lat = lat_2 - lat_1
    delta_lon = lon_2 - lon_1

    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_1)
        * math.cos(lat_2)
        * math.sin(delta_lon / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    angular_distance = 2 * math.asin(math.sqrt(value))

    return EARTH_RADIUS_MILES * angular_distance


def normalize_route_geometry(geometry: dict) -> list[tuple[float, float]]:
    """
    Convert GeoJSON LineString geometry into coordinate tuples.

    Returns:
        List of (longitude, latitude) tuples.
    """

    if not isinstance(geometry, dict):
        raise RouteAnalysisError("Invalid route geometry.")

    if geometry.get("type") != "LineString":
        raise RouteAnalysisError(
            "Route geometry must be a GeoJSON LineString."
        )

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise RouteAnalysisError(
            "Route geometry must contain at least two coordinates."
        )

    normalized = []

    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)):
            raise RouteAnalysisError("Invalid coordinate format.")

        if len(coordinate) < 2:
            raise RouteAnalysisError(
                "Coordinate requires longitude and latitude."
            )

        longitude, latitude = coordinate[:2]

        if isinstance(longitude, bool) or isinstance(latitude, bool):
            raise RouteAnalysisError("Coordinates must be numeric.")

        try:
            longitude = float(longitude)
            latitude = float(latitude)
        except (TypeError, ValueError):
            raise RouteAnalysisError(
                "Coordinates must contain valid numeric values."
            ) from None

        if not (
            math.isfinite(longitude)
            and math.isfinite(latitude)
            and -180 <= longitude <= 180
            and -90 <= latitude <= 90
        ):
            raise RouteAnalysisError("Coordinate values are out of range.")

        normalized.append((longitude, latitude))

    return normalized


def interpolate_coordinate(
    start: tuple[float, float],
    end: tuple[float, float],
    fraction: float,
) -> tuple[float, float]:
    """
    Linearly interpolate between two nearby route coordinates.

    Coordinates use (longitude, latitude) ordering.
    """

    longitude = start[0] + (end[0] - start[0]) * fraction
    latitude = start[1] + (end[1] - start[1]) * fraction

    return longitude, latitude


def sample_route_points(
    coordinates: list[tuple[float, float]],
    interval_miles: float = DEFAULT_SAMPLE_INTERVAL_MILES,
) -> list[dict]:
    """
    Generate geographical sample points along a route.

    The first and last route coordinates are always included.
    Intermediate points are generated at approximately equal
    travelled-distance intervals.
    """

    if (
        not math.isfinite(interval_miles)
        or interval_miles <= 0
    ):
        raise ValueError(
            "Sample interval must be a positive finite number."
        )

    if len(coordinates) < 2:
        raise RouteAnalysisError(
            "At least two route coordinates are required."
        )

    segment_distances = []
    total_distance = 0.0

    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]

        segment_distance = haversine_distance(
            start[1],
            start[0],
            end[1],
            end[0],
        )

        segment_distances.append(segment_distance)
        total_distance += segment_distance

    if total_distance <= 0:
        raise RouteAnalysisError(
            "Route has zero geographical distance."
        )

    sample_distances = [0.0]
    current_distance = interval_miles

    while current_distance < total_distance:
        sample_distances.append(current_distance)
        current_distance += interval_miles

    sample_distances.append(total_distance)

    sampled_points = []
    segment_index = 0
    cumulative_distance = 0.0

    for target_distance in sample_distances:

        while (
            segment_index < len(segment_distances) - 1
            and cumulative_distance + segment_distances[segment_index]
            < target_distance
        ):
            cumulative_distance += segment_distances[segment_index]
            segment_index += 1

        segment_distance = segment_distances[segment_index]

        if segment_distance == 0:
            fraction = 0.0
        else:
            fraction = (
                target_distance - cumulative_distance
            ) / segment_distance

        fraction = min(1.0, max(0.0, fraction))

        start = coordinates[segment_index]
        end = coordinates[segment_index + 1]

        longitude, latitude = interpolate_coordinate(
            start,
            end,
            fraction,
        )

        sampled_points.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "distance_from_start_miles": round(
                    target_distance,
                    3,
                ),
            }
        )

    return sampled_points


def analyze_route(
    route_data: dict,
    sample_interval_miles: float = DEFAULT_SAMPLE_INTERVAL_MILES,
) -> dict:
    """
    Validate and analyze an existing OSRM route response.

    There is intentionally no maximum trip-distance restriction.
    """

    if not isinstance(route_data, dict):
        raise RouteAnalysisError("Invalid route response.")

    geometry = route_data.get("geometry")
    coordinates = normalize_route_geometry(geometry)

    try:
        distance_miles = float(route_data["distance_miles"])
        duration_minutes = float(route_data["duration_minutes"])
    except (KeyError, TypeError, ValueError):
        raise RouteAnalysisError(
            "Route distance or duration is missing or invalid."
        ) from None

    if not (
        math.isfinite(distance_miles)
        and math.isfinite(duration_minutes)
        and distance_miles > 0
        and duration_minutes >= 0
    ):
        raise RouteAnalysisError(
            "Route distance and duration must be valid."
        )

    sampled_points = sample_route_points(
        coordinates,
        interval_miles=sample_interval_miles,
    )

    return {
        "distance_miles": round(distance_miles, 2),
        "duration_minutes": round(duration_minutes, 2),
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [longitude, latitude]
                for longitude, latitude in coordinates
            ],
        },
        "route_coordinates_count": len(coordinates),
        "sample_interval_miles": sample_interval_miles,
        "sampled_points": sampled_points,
        "sampled_points_count": len(sampled_points),
    }


def calculate_route_analysis(
    start_location: str,
    end_location: str,
    sample_interval_miles: float = DEFAULT_SAMPLE_INTERVAL_MILES,
) -> dict:
    """
    Calculate a driving route and return its analyzed representation.

    Reuses the existing Phase 2 geocoding and OSRM integration.
    """

    if not isinstance(start_location, str) or not start_location.strip():
        raise ValueError("Start location is required.")

    if not isinstance(end_location, str) or not end_location.strip():
        raise ValueError("Destination is required.")

    route_response = calculate_route(
        start_location.strip(),
        end_location.strip(),
    )

    if not isinstance(route_response, dict):
        raise RouteAnalysisError(
            "Invalid routing service response."
        )

    route_data = route_response.get("route")

    if not isinstance(route_data, dict):
        raise RouteAnalysisError("Route details are missing.")

    analysis = analyze_route(
        route_data,
        sample_interval_miles=sample_interval_miles,
    )

    return {
        "start": route_response.get("start"),
        "destination": route_response.get("destination"),
        "route": analysis,
    }
