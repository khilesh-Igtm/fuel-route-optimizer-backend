import pytest

from django.db import IntegrityError, transaction

from apps.fuel.models import FuelStation
from apps.locations.models import CityReference

from apps.fuel.services.data_importer import (
    import_datasets,
    normalize_name,
    parse_price,
)


@pytest.fixture
def csv_files(tmp_path):

    cities_csv = tmp_path / "cities.csv"

    fuel_csv = tmp_path / "fuel.csv"

    cities_csv.write_text(
        (
            "city,city_ascii,state_id,state_name,"
            "county_fips,county_name,lat,lng,"
            "population,density,source,military,"
            "incorporated,timezone,ranking,zips,id\n"
            "New York,New York,NY,New York,"
            "061,New York,40.7128,-74.0060,"
            "8000000,10000,test,0,TRUE,America/New_York,1,10001,1\n"
            "Los Angeles,Los Angeles,CA,California,"
            "037,Los Angeles,34.0522,-118.2437,"
            "3800000,3000,test,0,TRUE,America/Los_Angeles,1,90001,2\n"
        ),
        encoding="utf-8",
    )

    fuel_csv.write_text(
        (
            '"OPIS Truckstop ID","Truckstop Name",'
            '"Address","City","State","Rack ID",'
            '"Retail Price"\n'
            '"1001","Station One","Address One",'
            '"New York","NY","R1","3.499"\n'
            '"1001","Station One","Address One",'
            '"New York","NY","R2","3.299"\n'
            '"1002","Station Two","Address Two",'
            '"Los Angeles","CA","R1","4.199"\n'
            '"1003","Station Three","Address Three",'
            '"Unknown City","TX","R1","3.599"\n'
            '"1004","Invalid Price","Address Four",'
            '"New York","NY","R1","invalid"\n'
            '"1005","Non US","Address Five",'
            '"Toronto","ON","R1","3.999"\n'
        ),
        encoding="utf-8",
    )

    return fuel_csv, cities_csv


@pytest.mark.django_db
def test_complete_dataset_import(csv_files):

    fuel_csv, cities_csv = csv_files

    stats = import_datasets(
        fuel_csv,
        cities_csv,
    )

    assert CityReference.objects.count() == 2

    assert FuelStation.objects.count() == 3

    assert stats["stations_processed"] == 3

    assert stats["matched_stations"] == 2

    assert stats["unmatched_stations"] == 1

    assert stats["invalid_rows"] == 1

    assert stats["non_us_rows"] == 1


@pytest.mark.django_db
def test_duplicate_station_uses_lowest_price(csv_files):

    fuel_csv, cities_csv = csv_files

    import_datasets(fuel_csv, cities_csv)

    station = FuelStation.objects.get(
        truckstop_id="1001"
    )

    assert str(station.retail_price) == "3.299"


@pytest.mark.django_db
def test_city_coordinates_are_matched(csv_files):

    fuel_csv, cities_csv = csv_files

    import_datasets(fuel_csv, cities_csv)

    station = FuelStation.objects.get(
        truckstop_id="1001"
    )

    assert station.city_reference is not None

    assert station.latitude == pytest.approx(40.7128)

    assert station.longitude == pytest.approx(-74.0060)

    assert station.coordinates_are_approximate is True


@pytest.mark.django_db
def test_unmatched_city_has_null_coordinates(csv_files):

    fuel_csv, cities_csv = csv_files

    import_datasets(fuel_csv, cities_csv)

    station = FuelStation.objects.get(
        truckstop_id="1003"
    )

    assert station.city_reference is None

    assert station.latitude is None

    assert station.longitude is None


@pytest.mark.django_db
def test_repeated_import_does_not_create_duplicates(csv_files):

    fuel_csv, cities_csv = csv_files

    import_datasets(fuel_csv, cities_csv)

    import_datasets(fuel_csv, cities_csv)

    assert CityReference.objects.count() == 2

    assert FuelStation.objects.count() == 3


def test_normalize_name():

    assert normalize_name(" New York ") == "new york"

    assert normalize_name("LOS-ANGELES") == "los angeles"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("3.499", "3.499"),
        ("$4.299", "4.299"),
        ("", None),
        ("invalid", None),
        ("-2.50", None),
        ("0", None),
    ],
)
def test_parse_price(value, expected):

    result = parse_price(value)

    if expected is None:
        assert result is None

    else:
        assert str(result) == expected


@pytest.mark.django_db
def test_duplicate_city_state_constraint():

    CityReference.objects.create(
        city="New York",
        city_ascii="New York",
        normalized_name="new york",
        state_code="NY",
        state_name="New York",
        latitude=40.7128,
        longitude=-74.0060,
    )

    with pytest.raises(IntegrityError):

        with transaction.atomic():

            CityReference.objects.create(
                city="New York",
                city_ascii="New York",
                normalized_name="new york",
                state_code="NY",
                state_name="New York",
                latitude=40.7128,
                longitude=-74.0060,
            )