from django.db import models


class CityReference(models.Model):
    city = models.CharField(max_length=150)

    city_ascii = models.CharField(max_length=150)

    normalized_name = models.CharField(
        max_length=150,
        db_index=True,
    )

    state_code = models.CharField(max_length=2)

    state_name = models.CharField(max_length=100)

    latitude = models.FloatField()

    longitude = models.FloatField()

    population = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    ranking = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    source_id = models.CharField(
        max_length=30,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "city_references"

        constraints = [
            models.UniqueConstraint(
                fields=["normalized_name", "state_code"],
                name="unique_city_state_reference",
            ),
        ]

        indexes = [
            models.Index(
                fields=["state_code", "normalized_name"],
                name="city_state_lookup_idx",
            ),
        ]

        ordering = ["state_code", "city"]

    def __str__(self):
        return f"{self.city}, {self.state_code}"