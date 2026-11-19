
from rest_framework import serializers


class OptimizeRouteSerializer(serializers.Serializer):
    start_location = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )

    end_location = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )

    corridor_width_miles = serializers.FloatField(
        required=False,
        default=10.0,
        min_value=1.0,
        max_value=100.0,
    )

    max_stations = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=500,
    )

    def validate_start_location(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Start location cannot be empty."
            )

        return value.strip()

    def validate_end_location(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Destination cannot be empty."
            )

        return value.strip()

    def validate(self, attrs):
        start = attrs["start_location"].casefold()
        end = attrs["end_location"].casefold()

        if start == end:
            raise serializers.ValidationError(
                {
                    "end_location": (
                        "Start and destination must be different."
                    )
                }
            )

        return attrs
