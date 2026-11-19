
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
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Starting location cannot be empty."
            )

        return value

    def validate_end_location(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Destination cannot be empty."
            )

        return value

    def validate(self, attrs):
        start = attrs["start_location"]
        end = attrs["end_location"]

        if start.casefold() == end.casefold():
            raise serializers.ValidationError(
                {
                    "end_location": (
                        "Starting location and destination "
                        "must be different."
                    )
                }
            )

        return attrs
