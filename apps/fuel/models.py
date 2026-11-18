from django.db import models

from apps.locations.models import CityReference


class FuelStation(models.Model):
    truckstop_id = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(max_length=255)

    address = models.CharField(
        max_length=255,
        blank=True,
    )

    city = models.CharField(max_length=150)

    state = models.CharField(max_length=2)

    rack_id = models.CharField(
        max_length=50,
        blank=True,
    )

    retail_price = models.DecimalField(
        max_digits=8,
        decimal_places=3,
    )

    city_reference = models.ForeignKey(
        CityReference,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fuel_stations",
    )

    latitude = models.FloatField(
        null=True,
        blank=True,
    )

    longitude = models.FloatField(
        null=True,
        blank=True,
    )

    coordinates_are_approximate = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fuel_stations"

        indexes = [
            models.Index(
                fields=["state", "city"],
                name="fuel_city_state_idx",
            ),
            models.Index(
                fields=["retail_price"],
                name="fuel_price_idx",
            ),
        ]

        ordering = ["truckstop_id"]

    def __str__(self):
        return f"{self.name} ({self.truckstop_id})"