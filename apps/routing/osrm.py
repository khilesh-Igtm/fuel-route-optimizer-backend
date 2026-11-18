
import hashlib
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

ROUTE_CACHE_TIMEOUT = 60 * 60 * 24
REQUEST_TIMEOUT = 20


class RoutingError(Exception):
    """Raised when route calculation fails."""


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not (-90 <= latitude <= 90):
        raise RoutingError("Latitude must be between -90 and 90.")

    if not (-180 <= longitude <= 180):
        raise RoutingError("Longitude must be between -180 and 180.")


def _route_cache_key(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> str:
    coordinates = (
        f"{start_latitude:.6f},"
        f"{start_longitude:.6f},"
        f"{end_latitude:.6f},"
        f"{end_longitude:.6f}"
    )

    digest = hashlib.sha256(
        coordinates.encode("utf-8")
    ).hexdigest()

    return f"osrm:route:{digest}"


def get_driving_route(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> dict[str, Any]:
    """
    Calculate a driving route between two geographic coordinates.

    Coordinates are accepted in latitude/longitude order.
    OSRM expects longitude/latitude order.
    """
    try:
        start_latitude = float(start_latitude)
        start_longitude = float(start_longitude)
        end_latitude = float(end_latitude)
        end_longitude = float(end_longitude)

    except (TypeError, ValueError) as exc:
        raise RoutingError("Coordinates must be valid numbers.") from exc

    _validate_coordinates(start_latitude, start_longitude)
    _validate_coordinates(end_latitude, end_longitude)

    key = _route_cache_key(
        start_latitude,
        start_longitude,
        end_latitude,
        end_longitude,
    )

    cached_result = cache.get(key)

    if cached_result is not None:
        logger.debug("OSRM route cache hit.")
        return cached_result

    # OSRM requires longitude,latitude order.
    coordinates = (
        f"{start_longitude},{start_latitude};"
        f"{end_longitude},{end_latitude}"
    )

    url = (
        f"{settings.OSRM_BASE_URL.rstrip('/')}"
        f"/route/v1/driving/{coordinates}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException as exc:
        logger.exception("OSRM routing request failed.")
        raise RoutingError(
            "Unable to communicate with the routing service."
        ) from exc

    except ValueError as exc:
        raise RoutingError(
            "Routing service returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RoutingError("Invalid routing response.")

    if data.get("code") != "Ok":
        raise RoutingError(
            data.get("message", "No driving route could be found.")
        )

    routes = data.get("routes")

    if not isinstance(routes, list) or not routes:
        raise RoutingError("No driving route was found.")

    route = routes[0]

    try:
        distance_meters = float(route["distance"])
        duration_seconds = float(route["duration"])
        geometry = route["geometry"]
        coordinates_list = geometry["coordinates"]

    except (KeyError, TypeError, ValueError) as exc:
        raise RoutingError(
            "Routing service returned incomplete route information."
        ) from exc

    if distance_meters < 0 or duration_seconds < 0:
        raise RoutingError("Invalid route distance or duration.")

    if (
        not isinstance(coordinates_list, list)
        or not coordinates_list
        or not all(
            isinstance(point, (list, tuple))
            and len(point) >= 2
            for point in coordinates_list
        )
    ):
        raise RoutingError("Routing service returned invalid geometry.")

    distance_miles = distance_meters / 1609.344
    duration_minutes = duration_seconds / 60

    result = {
        "distance_meters": distance_meters,
        "distance_miles": round(distance_miles, 2),
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_minutes, 2),
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates_list,
        },
    }

    cache.set(
        key,
        result,
        timeout=ROUTE_CACHE_TIMEOUT,
    )

    logger.info(
        "Driving route calculated: %.2f miles",
        distance_miles,
    )

    return result
