from pathlib import Path

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.fuel.services.data_importer import import_datasets


class Command(BaseCommand):

    help = (
        "Import fuel station and SimpleMaps city reference data."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--fuel-csv",
            type=str,
            default="data/fuel-prices-for-be-assessment.csv",
        )

        parser.add_argument(
            "--cities-csv",
            type=str,
            default="data/uscities.csv",
        )

    def handle(self, *args, **options):

        fuel_csv = Path(options["fuel_csv"])

        cities_csv = Path(options["cities_csv"])

        if not fuel_csv.is_absolute():
            fuel_csv = settings.BASE_DIR / fuel_csv

        if not cities_csv.is_absolute():
            cities_csv = settings.BASE_DIR / cities_csv

        if not fuel_csv.exists():
            raise CommandError(
                f"Fuel CSV not found: {fuel_csv}"
            )

        if not cities_csv.exists():
            raise CommandError(
                f"Cities CSV not found: {cities_csv}"
            )

        self.stdout.write(
            self.style.NOTICE(
                "Starting Phase 1 data ingestion..."
            )
        )

        try:

            stats = import_datasets(
                fuel_csv,
                cities_csv,
            )

        except Exception as exc:

            raise CommandError(
                f"Data import failed: {exc}"
            ) from exc

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Phase 1 data ingestion completed."
            )
        )

        self.stdout.write("")
        self.stdout.write("SIMPLEMAPS CITY DATA")

        self.stdout.write(
            f"Rows read: {stats['city_rows_read']}"
        )

        self.stdout.write(
            f"Invalid rows: {stats['invalid_city_rows']}"
        )

        self.stdout.write(
            f"City records processed: "
            f"{stats['city_records_processed']}"
        )

        self.stdout.write("")

        self.stdout.write("FUEL STATION DATA")

        self.stdout.write(
            f"Rows read: {stats['fuel_rows_read']}"
        )

        self.stdout.write(
            f"Non-US rows skipped: {stats['non_us_rows']}"
        )

        self.stdout.write(
            f"Invalid rows skipped: {stats['invalid_rows']}"
        )

        self.stdout.write(
            f"Duplicate rows: {stats['duplicate_rows']}"
        )

        self.stdout.write(
            f"Stations processed: {stats['stations_processed']}"
        )

        self.stdout.write(
            f"City matched: {stats['matched_stations']}"
        )

        self.stdout.write(
            f"City unmatched: {stats['unmatched_stations']}"
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Import finished successfully."
            )
        )