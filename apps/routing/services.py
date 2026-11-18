
from typing import Any

from apps.locations.geocoding import geocode_location
from apps.routing.osrm import get_driving_route


def calculate_route(
    start_location: str,
    end_location: str,
) -> dict[str, Any]:
    """
    Resolve two locations and calculate the driving route.
    """

    start = geocode_location(start_location)
    end = geocode_location(end_location)

    route = get_driving_route(
        start_latitude=start["latitude"],
        start_longitude=start["longitude"],
        end_latitude=end["latitude"],
        end_longitude=end["longitude"],
    )

    return {
        "start": start,
        "destination": end,
        "route": route,
    }
