
import hashlib
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

GEOCODING_CACHE_TIMEOUT = 60 * 60 * 24 * 7
REQUEST_TIMEOUT = 15


class GeocodingError(Exception):
    """Raised when a location cannot be geocoded."""


def _cache_key(location: str) -> str:
    normalized = location.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"geocoding:{digest}"


def geocode_location(location: str) -> dict[str, Any]:
    """
    Convert a human-readable location into geographic coordinates.

    Returns:
        {
            "latitude": float,
            "longitude": float,
            "display_name": str
        }
    """
    if not isinstance(location, str) or not location.strip():
        raise GeocodingError("Location must be a non-empty string.")

    location = location.strip()
    key = _cache_key(location)

    cached_result = cache.get(key)

    if cached_result is not None:
        logger.debug("Geocoding cache hit for %s", location)
        return cached_result

    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search"

    params = {
        "q": location,
        "format": "jsonv2",
        "limit": 1,
    }

    headers = {
        "User-Agent": "FuelRouteOptimizer/1.0",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()

    except requests.RequestException as exc:
        logger.exception("Nominatim request failed.")
        raise GeocodingError(
            "Unable to communicate with the geocoding service."
        ) from exc

    except ValueError as exc:
        raise GeocodingError(
            "Geocoding service returned invalid JSON."
        ) from exc

    if not isinstance(results, list) or not results:
        raise GeocodingError(
            f"No coordinates found for location: {location}"
        )

    result = results[0]

    try:
        latitude = float(result["lat"])
        longitude = float(result["lon"])
        display_name = result["display_name"]

    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(
            "Geocoding service returned an invalid location."
        ) from exc

    if not (-90 <= latitude <= 90):
        raise GeocodingError("Invalid latitude returned by geocoding service.")

    if not (-180 <= longitude <= 180):
        raise GeocodingError("Invalid longitude returned by geocoding service.")

    geocoded_location = {
        "latitude": latitude,
        "longitude": longitude,
        "display_name": display_name,
    }

    cache.set(
        key,
        geocoded_location,
        timeout=GEOCODING_CACHE_TIMEOUT,
    )

    logger.info("Successfully geocoded location: %s", location)

    return geocoded_location
