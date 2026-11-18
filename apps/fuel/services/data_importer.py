import csv
import re

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.fuel.models import FuelStation
from apps.locations.models import CityReference


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE",
    "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}


def normalize_name(value):
    """
    Normalize city names for consistent matching.
    """

    value = value.strip().casefold()

    value = re.sub(r"[^a-z0-9]+", " ", value)

    return " ".join(value.split())


def parse_price(value):
    """
    Convert CSV retail price into Decimal.
    """

    if not value:
        return None

    cleaned = value.strip().replace("$", "").replace(",", "")

    try:
        price = Decimal(cleaned)
    except InvalidOperation:
        return None

    if not price.is_finite() or price <= 0:
        return None

    return price.quantize(Decimal("0.001"))


def parse_coordinate(value, minimum, maximum):
    try:
        coordinate = float(value)

        if not minimum <= coordinate <= maximum:
            return None

        return coordinate

    except (ValueError, TypeError):
        return None


def import_city_references(csv_path):
    """
    Import SimpleMaps city reference data.

    Duplicate city-state entries are resolved by retaining
    the better-ranked record.
    """

    records = {}
    stats = {
        "city_rows_read": 0,
        "invalid_city_rows": 0,
        "city_records_processed": 0,
    }

    required_columns = {
        "city",
        "city_ascii",
        "state_id",
        "state_name",
        "lat",
        "lng",
    }

    with open(
        csv_path,
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if not required_columns.issubset(
            set(reader.fieldnames or [])
        ):
            raise ValueError(
                "SimpleMaps CSV is missing required columns."
            )

        for row in reader:

            stats["city_rows_read"] += 1

            city = (row.get("city") or "").strip()

            city_ascii = (
                row.get("city_ascii") or ""
            ).strip()

            state_code = (
                row.get("state_id") or ""
            ).strip().upper()

            state_name = (
                row.get("state_name") or ""
            ).strip()

            normalized_name = normalize_name(city_ascii)

            latitude = parse_coordinate(
                row.get("lat"),
                -90,
                90,
            )

            longitude = parse_coordinate(
                row.get("lng"),
                -180,
                180,
            )

            if (
                not city
                or not normalized_name
                or state_code not in US_STATES
                or not state_name
                or latitude is None
                or longitude is None
            ):
                stats["invalid_city_rows"] += 1
                continue

            try:
                population_value = (
                    row.get("population") or ""
                ).strip()

                population = (
                    int(float(population_value))
                    if population_value
                    else None
                )

                ranking_value = (
                    row.get("ranking") or ""
                ).strip()

                ranking = (
                    int(ranking_value)
                    if ranking_value
                    else None
                )

                if (
                    population is not None
                    and population < 0
                ):
                    raise ValueError

                if ranking is not None and ranking < 0:
                    raise ValueError

            except (ValueError, OverflowError):
                stats["invalid_city_rows"] += 1
                continue

            key = (normalized_name, state_code)

            record = {
                "city": city,
                "city_ascii": city_ascii,
                "normalized_name": normalized_name,
                "state_code": state_code,
                "state_name": state_name,
                "latitude": latitude,
                "longitude": longitude,
                "population": population,
                "ranking": ranking,
                "source_id": (row.get("id") or "").strip(),
            }

            existing = records.get(key)

            if existing is None:
                records[key] = record

            else:
                old_rank = existing["ranking"]
                new_rank = record["ranking"]

                if (
                    new_rank is not None
                    and (
                        old_rank is None
                        or new_rank < old_rank
                    )
                ):
                    records[key] = record

        stats["city_records_processed"] = len(records)

    objects = [
        CityReference(**record)
        for record in records.values()
    ]

    with transaction.atomic():

        CityReference.objects.bulk_create(
            objects,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=[
                "normalized_name",
                "state_code",
            ],
            update_fields=[
                "city",
                "city_ascii",
                "state_name",
                "latitude",
                "longitude",
                "population",
                "ranking",
                "source_id",
                "updated_at",
            ],
        )

    return stats


def import_fuel_stations(csv_path):
    """
    Import fuel stations and resolve city references.

    Duplicate station IDs retain the lowest valid retail price.
    """

    required_columns = {
        "OPIS Truckstop ID",
        "Truckstop Name",
        "Address",
        "City",
        "State",
        "Rack ID",
        "Retail Price",
    }

    stats = {
        "fuel_rows_read": 0,
        "non_us_rows": 0,
        "invalid_rows": 0,
        "duplicate_rows": 0,
        "stations_processed": 0,
        "matched_stations": 0,
        "unmatched_stations": 0,
    }

    stations = {}

    with open(
        csv_path,
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if not required_columns.issubset(
            set(reader.fieldnames or [])
        ):
            raise ValueError(
                "Fuel CSV is missing required columns."
            )

        for row in reader:

            stats["fuel_rows_read"] += 1

            truckstop_id = (
                row.get("OPIS Truckstop ID") or ""
            ).strip()

            state = (
                row.get("State") or ""
            ).strip().upper()

            city = (
                row.get("City") or ""
            ).strip()

            price = parse_price(
                row.get("Retail Price")
            )

            if state not in US_STATES:
                stats["non_us_rows"] += 1
                continue

            if (
                not truckstop_id
                or not city
                or price is None
            ):
                stats["invalid_rows"] += 1
                continue

            record = {
                "truckstop_id": truckstop_id,
                "name": (
                    row.get("Truckstop Name") or ""
                ).strip() or truckstop_id,
                "address": (
                    row.get("Address") or ""
                ).strip(),
                "city": city,
                "state": state,
                "rack_id": (
                    row.get("Rack ID") or ""
                ).strip(),
                "retail_price": price,
            }

            existing = stations.get(truckstop_id)

            if existing is not None:

                stats["duplicate_rows"] += 1

                if price < existing["retail_price"]:
                    record["name"] = existing["name"]
                    record["address"] = existing["address"]
                    record["city"] = existing["city"]
                    record["state"] = existing["state"]

                    stations[truckstop_id] = record

            else:
                stations[truckstop_id] = record

    city_lookup = {
        (city.normalized_name, city.state_code): city
        for city in CityReference.objects.all()
    }

    station_objects = []

    for record in stations.values():

        key = (
            normalize_name(record["city"]),
            record["state"],
        )

        city_reference = city_lookup.get(key)

        if city_reference:

            record["city_reference"] = city_reference

            record["latitude"] = city_reference.latitude

            record["longitude"] = city_reference.longitude

            record["coordinates_are_approximate"] = True

            stats["matched_stations"] += 1

        else:

            record["city_reference"] = None

            record["latitude"] = None

            record["longitude"] = None

            record["coordinates_are_approximate"] = True

            stats["unmatched_stations"] += 1

        station_objects.append(
            FuelStation(**record)
        )

    with transaction.atomic():

        FuelStation.objects.bulk_create(
            station_objects,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=["truckstop_id"],
            update_fields=[
                "name",
                "address",
                "city",
                "state",
                "rack_id",
                "retail_price",
                "city_reference",
                "latitude",
                "longitude",
                "coordinates_are_approximate",
                "updated_at",
            ],
        )

    stats["stations_processed"] = len(station_objects)

    return stats


def import_datasets(fuel_csv, cities_csv):
    """
    Execute complete Phase 1 data ingestion.
    """

    with transaction.atomic():

        city_stats = import_city_references(cities_csv)

        fuel_stats = import_fuel_stations(fuel_csv)

    return {
        **city_stats,
        **fuel_stats,
    }