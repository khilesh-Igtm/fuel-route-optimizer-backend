
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from apps.fuel.models import FuelStation

logger = logging.getLogger(__name__)

EARTH_RADIUS_MILES = 3958.8
MILES_PER_DEGREE_LATITUDE = 69.0
GRID_CELL_SIZE_MILES = 10.0


@dataclass(frozen=True)
class RouteProjection:
    distance_from_start_miles: float
    distance_from_route_miles: float
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RouteSegment:
    segment_id: int
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float
    start_distance_miles: float
    segment_length_miles: float


@dataclass
class SpatialRouteIndex:
    segments: list[RouteSegment]
    grid: dict[tuple[int, int], set[int]]
    cell_size_latitude: float
    cell_size_longitude: float
    corridor_width_miles: float
    route_coordinates: list[tuple[float, float]]
    total_route_distance_miles: float
    candidate_segment_checks: int = 0

    @property
    def cells(self):
        """Backward-compatible public access to spatial grid cells."""
        return self.grid


def _validate_coordinates(latitude: float, longitude: float) -> bool:
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False

    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
    )


def haversine_distance(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    lat1 = math.radians(latitude_1)
    lat2 = math.radians(latitude_2)

    delta_lat = math.radians(latitude_2 - latitude_1)
    delta_lon = math.radians(longitude_2 - longitude_1)

    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_MILES * math.asin(
        min(1.0, math.sqrt(value))
    )


def _normalize_helper_route_coordinates(
    coordinates: list,
) -> list[tuple[float, float]]:
    normalized = []

    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            continue

        first = float(coordinate[0])
        second = float(coordinate[1])

        # Support normalized (latitude, longitude) pairs as well as
        # GeoJSON (longitude, latitude) coordinate pairs.
        if (
            -90.0 <= first <= 90.0
            and not -90.0 <= second <= 90.0
        ):
            latitude, longitude = first, second
        else:
            longitude, latitude = first, second

        if _validate_coordinates(latitude, longitude):
            normalized.append((latitude, longitude))

    return normalized


def _get_route_coordinates(route: dict) -> list[tuple[float, float]]:
    if not isinstance(route, dict):
        raise ValueError("Route must be a dictionary.")

    route_data = route.get("route", route)

    if not isinstance(route_data, dict):
        raise ValueError("Invalid route data.")

    geometry = route_data.get("geometry")

    if not isinstance(geometry, dict):
        raise ValueError("Route geometry is missing.")

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, (list, tuple)):
        raise ValueError("Route geometry coordinates are missing.")

    normalized = []

    # OSRM GeoJSON coordinates are [longitude, latitude].
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            continue

        try:
            longitude = float(coordinate[0])
            latitude = float(coordinate[1])
        except (TypeError, ValueError):
            continue

        if _validate_coordinates(latitude, longitude):
            normalized.append((latitude, longitude))

    if len(normalized) < 2:
        raise ValueError("Route must contain at least two valid coordinates.")

    return normalized


def _project_point_onto_segment(
    latitude: float,
    longitude: float,
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
    start_distance_miles: float = 0.0,
    segment_length_miles: float | None = None,
) -> RouteProjection:
    reference_latitude = math.radians(
        (start_latitude + end_latitude) / 2
    )

    longitude_scale = max(
        abs(math.cos(reference_latitude)),
        1e-8,
    )

    point_x = (
        math.radians(longitude - start_longitude)
        * EARTH_RADIUS_MILES
        * longitude_scale
    )
    point_y = (
        math.radians(latitude - start_latitude)
        * EARTH_RADIUS_MILES
    )

    end_x = (
        math.radians(end_longitude - start_longitude)
        * EARTH_RADIUS_MILES
        * longitude_scale
    )
    end_y = (
        math.radians(end_latitude - start_latitude)
        * EARTH_RADIUS_MILES
    )

    segment_squared = end_x**2 + end_y**2

    if segment_squared == 0:
        fraction = 0.0
    else:
        fraction = (
            point_x * end_x + point_y * end_y
        ) / segment_squared

        fraction = max(0.0, min(1.0, fraction))

    projected_latitude = (
        start_latitude + fraction * (end_latitude - start_latitude)
    )
    projected_longitude = (
        start_longitude + fraction * (end_longitude - start_longitude)
    )

    cross_track_distance = haversine_distance(
        latitude,
        longitude,
        projected_latitude,
        projected_longitude,
    )

    if segment_length_miles is None:
        segment_length_miles = haversine_distance(
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        )

    distance_from_start = (
        start_distance_miles + fraction * segment_length_miles
    )

    return RouteProjection(
        distance_from_start_miles=distance_from_start,
        distance_from_route_miles=cross_track_distance,
        latitude=projected_latitude,
        longitude=projected_longitude,
    )


def _grid_cell(
    latitude: float,
    longitude: float,
    cell_size_latitude: float,
    cell_size_longitude: float,
) -> tuple[int, int]:
    return (
        math.floor(latitude / cell_size_latitude),
        math.floor(longitude / cell_size_longitude),
    )


def _build_spatial_index(
    route_coordinates: list[tuple[float, float]],
    corridor_width_miles: float = 10.0,
) -> SpatialRouteIndex:
    if corridor_width_miles <= 0:
        raise ValueError("corridor_width_miles must be greater than zero.")

    if len(route_coordinates) < 2:
        raise ValueError("Route must contain at least two coordinates.")

    maximum_latitude = max(
        abs(latitude) for latitude, _ in route_coordinates
    )

    cell_size_latitude = GRID_CELL_SIZE_MILES / MILES_PER_DEGREE_LATITUDE

    longitude_scale = max(
        abs(math.cos(math.radians(maximum_latitude))),
        0.01,
    )

    cell_size_longitude = (
        GRID_CELL_SIZE_MILES
        / (MILES_PER_DEGREE_LATITUDE * longitude_scale)
    )

    segments = []
    grid: dict[tuple[int, int], set[int]] = {}

    cumulative_distance = 0.0

    for index in range(len(route_coordinates) - 1):
        start_latitude, start_longitude = route_coordinates[index]
        end_latitude, end_longitude = route_coordinates[index + 1]

        segment_length = haversine_distance(
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        )

        segment = RouteSegment(
            segment_id=index,
            start_latitude=start_latitude,
            start_longitude=start_longitude,
            end_latitude=end_latitude,
            end_longitude=end_longitude,
            start_distance_miles=cumulative_distance,
            segment_length_miles=segment_length,
        )

        segments.append(segment)

        latitude_padding = (
            corridor_width_miles / MILES_PER_DEGREE_LATITUDE
        )

        segment_max_latitude = max(
            abs(start_latitude),
            abs(end_latitude),
        )

        segment_longitude_scale = max(
            abs(math.cos(math.radians(segment_max_latitude))),
            0.01,
        )

        longitude_padding = (
            corridor_width_miles
            / (MILES_PER_DEGREE_LATITUDE * segment_longitude_scale)
        )

        min_latitude = min(start_latitude, end_latitude) - latitude_padding
        max_latitude = max(start_latitude, end_latitude) + latitude_padding

        min_longitude = min(start_longitude, end_longitude) - longitude_padding
        max_longitude = max(start_longitude, end_longitude) + longitude_padding

        min_row = math.floor(min_latitude / cell_size_latitude)
        max_row = math.floor(max_latitude / cell_size_latitude)

        min_column = math.floor(min_longitude / cell_size_longitude)
        max_column = math.floor(max_longitude / cell_size_longitude)

        for row in range(min_row, max_row + 1):
            for column in range(min_column, max_column + 1):
                grid.setdefault((row, column), set()).add(index)

        cumulative_distance += segment_length

    return SpatialRouteIndex(
        segments=segments,
        grid=grid,
        cell_size_latitude=cell_size_latitude,
        cell_size_longitude=cell_size_longitude,
        corridor_width_miles=corridor_width_miles,
        route_coordinates=route_coordinates,
        total_route_distance_miles=cumulative_distance,
    )


def _candidate_segments_for_point(
    latitude: float,
    longitude: float,
    spatial_index: SpatialRouteIndex,
) -> set[int] | tuple:
    if not _validate_coordinates(latitude, longitude):
        return ()

    cell = _grid_cell(
        latitude,
        longitude,
        spatial_index.cell_size_latitude,
        spatial_index.cell_size_longitude,
    )

    candidate_ids = spatial_index.cells.get(cell)

    # The empty tuple is intentional: performance tests and callers
    # use it to identify points outside every indexed corridor cell.
    if not candidate_ids:
        return ()

    return candidate_ids


def _project_onto_indexed_route(
    latitude: float,
    longitude: float,
    spatial_index: SpatialRouteIndex,
    candidate_segment_ids=None,
) -> tuple[RouteProjection | None, int]:
    if candidate_segment_ids is None:
        candidate_segment_ids = _candidate_segments_for_point(
            latitude,
            longitude,
            spatial_index,
        )

    if not candidate_segment_ids:
        return None, 0

    best_projection = None
    best_distance = float("inf")
    checks = 0

    for segment_id in candidate_segment_ids:
        segment = spatial_index.segments[segment_id]
        checks += 1

        projection = _project_point_onto_segment(
            latitude,
            longitude,
            segment.start_latitude,
            segment.start_longitude,
            segment.end_latitude,
            segment.end_longitude,
            segment.start_distance_miles,
            segment.segment_length_miles,
        )

        if projection.distance_from_route_miles < best_distance:
            best_distance = projection.distance_from_route_miles
            best_projection = projection

    if (
        best_projection is None
        or best_projection.distance_from_route_miles
        > spatial_index.corridor_width_miles
    ):
        return None, checks

    return best_projection, checks


def find_nearest_route_position(
    latitude: float,
    longitude: float,
    route_coordinates: list,
    corridor_width_miles: float = 10.0,
) -> RouteProjection:
    if not _validate_coordinates(latitude, longitude):
        raise ValueError("Invalid station coordinates.")

    normalized_coordinates = _normalize_helper_route_coordinates(
        route_coordinates
    )

    if len(normalized_coordinates) < 2:
        raise ValueError("Route must contain at least two valid coordinates.")

    best_projection = None
    best_distance = float("inf")
    cumulative_distance = 0.0

    for i in range(len(normalized_coordinates) - 1):
        start_lat, start_lon = normalized_coordinates[i]
        end_lat, end_lon = normalized_coordinates[i + 1]
        seg_len = haversine_distance(start_lat, start_lon, end_lat, end_lon)

        projection = _project_point_onto_segment(
            float(latitude),
            float(longitude),
            start_lat,
            start_lon,
            end_lat,
            end_lon,
            cumulative_distance,
            seg_len,
        )

        if projection.distance_from_route_miles < best_distance:
            best_distance = projection.distance_from_route_miles
            best_projection = projection

        cumulative_distance += seg_len

    return best_projection


def _get_stations():
    return FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).only(
        "truckstop_id",
        "name",
        "address",
        "city",
        "state",
        "rack_id",
        "retail_price",
        "latitude",
        "longitude",
        "coordinates_are_approximate",
    )


def _station_value(station: Any, field_name: str, default=None):
    if isinstance(station, dict):
        return station.get(field_name, default)

    return getattr(station, field_name, default)


def _serialize_station(
    station: Any,
    projection: RouteProjection,
) -> dict:
    retail_price = _station_value(station, "retail_price")

    if retail_price is not None:
        retail_price = float(retail_price)

    distance_from_route = projection.distance_from_route_miles

    return {
        "truckstop_id": _station_value(station, "truckstop_id"),
        "name": _station_value(station, "name"),
        "address": _station_value(station, "address"),
        "city": _station_value(station, "city"),
        "state": _station_value(station, "state"),
        "rack_id": _station_value(station, "rack_id"),
        "retail_price": retail_price,
        "latitude": float(_station_value(station, "latitude")),
        "longitude": float(_station_value(station, "longitude")),
        "coordinates_are_approximate": bool(
            _station_value(station, "coordinates_are_approximate", False)
        ),
        "distance_from_start_miles": projection.distance_from_start_miles,
        "distance_from_route_miles": distance_from_route,
        "detour_distance_miles": round(distance_from_route * 2, 2),
    }


def match_fuel_stations_to_route(
    route_analysis: dict,
    corridor_width_miles: float = 10.0,
    max_results: int = 100,
    stations=None,
) -> dict:
    started_at = time.perf_counter()

    if (
        not isinstance(corridor_width_miles, (int, float))
        or not math.isfinite(corridor_width_miles)
        or corridor_width_miles <= 0
    ):
        raise ValueError("corridor_width_miles must be greater than zero.")

    if max_results is not None and (
        not isinstance(max_results, int)
        or isinstance(max_results, bool)
        or max_results <= 0
    ):
        raise ValueError("max_results must be a positive integer.")

    if not isinstance(route_analysis, dict):
        raise ValueError("route_analysis must be a dictionary.")

    route_coordinates = _get_route_coordinates(route_analysis)

    index_started_at = time.perf_counter()

    spatial_index = _build_spatial_index(
        route_coordinates,
        corridor_width_miles=float(corridor_width_miles),
    )

    index_duration = time.perf_counter() - index_started_at

    database_started_at = time.perf_counter()

    station_list = list(_get_stations() if stations is None else stations)

    database_duration = time.perf_counter() - database_started_at

    matching_started_at = time.perf_counter()

    matched_stations = []
    invalid_stations_skipped = 0
    candidate_segment_checks = 0

    for station in station_list:
        try:
            latitude = float(_station_value(station, "latitude"))
            longitude = float(_station_value(station, "longitude"))
        except (TypeError, ValueError):
            invalid_stations_skipped += 1
            continue

        if not _validate_coordinates(latitude, longitude):
            invalid_stations_skipped += 1
            continue

        candidate_ids = _candidate_segments_for_point(
            latitude,
            longitude,
            spatial_index,
        )

        if not candidate_ids:
            continue

        projection, checks = _project_onto_indexed_route(
            latitude,
            longitude,
            spatial_index,
            candidate_ids,
        )

        candidate_segment_checks += checks

        if projection is None:
            continue

        serialized = _serialize_station(station, projection)
        matched_stations.append(serialized)

    matched_stations.sort(
        key=lambda station: (
            station["distance_from_start_miles"],
            station["distance_from_route_miles"],
            str(station["truckstop_id"]),
        )
    )

    total_matched_stations = len(matched_stations)
    returned_stations = (
        matched_stations if max_results is None else matched_stations[:max_results]
    )

    matching_duration = time.perf_counter() - matching_started_at
    total_duration = time.perf_counter() - started_at

    logger.info(
        "Station matching completed: stations=%s segments=%s cells=%s "
        "candidate_checks=%s matched=%s returned=%s invalid=%s "
        "index_seconds=%.4f database_seconds=%.4f "
        "matching_seconds=%.4f total_seconds=%.4f",
        len(station_list),
        len(spatial_index.segments),
        len(spatial_index.cells),
        candidate_segment_checks,
        total_matched_stations,
        len(returned_stations),
        invalid_stations_skipped,
        index_duration,
        database_duration,
        matching_duration,
        total_duration,
    )

    route_data = route_analysis.get("route", {})

    return {
        "start": route_analysis.get("start"),
        "destination": route_analysis.get("destination"),
        "route": route_data,
        "matching": {
            "corridor_width_miles": float(corridor_width_miles),
            "total_stations_checked": len(station_list),
            "total_matched_stations": total_matched_stations,
            "returned_stations": len(returned_stations),
            "max_results": max_results,
            "candidate_segment_checks": candidate_segment_checks,
            "invalid_stations_skipped": invalid_stations_skipped,
        },
        "stations": returned_stations,
    }
