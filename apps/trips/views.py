
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fuel.cost_calculation import calculate_trip_cost
from apps.fuel.optimization import optimize_fuel_stops
from apps.routing.route_analysis import calculate_route_analysis
from apps.routing.station_matching import (
    match_fuel_stations_to_route,
)
from apps.trips.serializers import OptimizeRouteSerializer


logger = logging.getLogger(__name__)


class OptimizeRouteAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OptimizeRouteSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        start_location = data["start_location"]
        end_location = data["end_location"]

        corridor_width = data["corridor_width_miles"]
        max_stations = data["max_stations"]

        try:
            # Phase 3: Route calculation and analysis.
            route_analysis = calculate_route_analysis(
                start_location=start_location,
                end_location=end_location,
            )

            route_distance = route_analysis["route"][
                "distance_miles"
            ]

            # Phase 4: Match fuel stations to route.
            matching_result = match_fuel_stations_to_route(
                route_analysis=route_analysis,
                corridor_width_miles=corridor_width,
                max_results=max_stations,
            )

            matched_stations = matching_result["stations"]

            # Phase 5: Optimize fuel stops.
            tank_range = float(
                getattr(
                    settings,
                    "VEHICLE_MAX_RANGE_MILES",
                    500,
                )
            )

            mpg = float(
                getattr(
                    settings,
                    "VEHICLE_MPG",
                    10,
                )
            )

            optimization = optimize_fuel_stops(
                route_distance_miles=route_distance,
                stations=matched_stations,
                tank_range_miles=tank_range,
                mpg=mpg,
            )

            # Phase 6: Calculate trip cost.
            tank_capacity = tank_range / mpg

            cost_summary = calculate_trip_cost(
                route_distance_miles=route_distance,
                mpg=mpg,
                tank_capacity_gallons=tank_capacity,
                stops=optimization["stops"],
            )

            # Data quality information.
            approximate_stops = sum(
                1
                for stop in optimization["stops"]
                if stop["coordinates_are_approximate"]
            )

            response_data = {
                "success": True,

                "route": {
                    "start": route_analysis["start"],
                    "destination": route_analysis["destination"],
                    "distance_miles": route_distance,
                    "duration_minutes": (
                        route_analysis["route"]["duration_minutes"]
                    ),
                    "geometry": route_analysis["route"]["geometry"],
                },

                "vehicle": {
                    "tank_range_miles": tank_range,
                    "mpg": mpg,
                    "tank_capacity_gallons": round(
                        tank_capacity,
                        3,
                    ),
                    "initial_tank_status": "full",
                },

                "fuel_optimization": optimization,

                "cost_summary": {
                    key: value
                    for key, value in cost_summary.items()
                    if key != "stops"
                },

                "fuel_cost_breakdown": {
                    "stops": cost_summary["stops"],
                },

                "station_matching": {
                    "corridor_width_miles": (
                        matching_result["matching"][
                            "corridor_width_miles"
                        ]
                    ),
                    "total_matched_stations": (
                        matching_result["matching"][
                            "total_matched_stations"
                        ]
                    ),
                    "stations_considered": len(
                        matched_stations
                    ),
                    "selected_stops": (
                        optimization["number_of_stops"]
                    ),
                },

                "data_quality": {
                    "approximate_coordinate_stops": (
                        approximate_stops
                    ),
                    "has_approximate_coordinates": (
                        approximate_stops > 0
                    ),
                },
            }

            return Response(
                response_data,
                status=status.HTTP_200_OK,
            )

        except ValueError as exc:
            logger.warning(
                "Route optimization validation failed: %s",
                str(exc),
            )

            return Response(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": "ROUTE_OPTIMIZATION_ERROR",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        except Exception:
            logger.exception(
                "Fuel route optimization failed."
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "Unable to optimize this route. "
                        "Please try again later."
                    ),
                    "error_code": "ROUTE_SERVICE_UNAVAILABLE",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
