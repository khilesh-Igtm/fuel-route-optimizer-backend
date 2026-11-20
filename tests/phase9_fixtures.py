def create_valid_response():
    stop = {
        "truckstop_id": "1001",
        "name": "TEST TRUCK STOP",
        "address": "Highway Exit 10",
        "city": "Test City",
        "state": "NY",
        "latitude": 40.0,
        "longitude": -75.0,
        "coordinates_are_approximate": False,
        "distance_from_start_miles": 50,
        "detour_distance_miles": 2,
        "fuel_price_per_gallon": 3.0,
        "fuel_to_purchase_gallons": 5.0,
        "estimated_stop_cost": 15.0,
    }

    breakdown_stop = {
        "truckstop_id": "1001",
        "name": "TEST TRUCK STOP",
        "city": "Test City",
        "state": "NY",
        "fuel_price_per_gallon": 3.0,
        "fuel_purchased_gallons": 5.0,
        "estimated_stop_cost": 15.0,
    }

    return {
        "success": True,
        "route": {
            "start": {
                "latitude": 40.7127,
                "longitude": -74.0060,
                "display_name": "New York, United States",
            },
            "destination": {
                "latitude": 34.0536,
                "longitude": -118.2427,
                "display_name": "Los Angeles, United States",
            },
            "distance_miles": 100.0,
            "duration_minutes": 120.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0, 40.7],
                    [-75.0, 40.0],
                ],
            },
        },
        "vehicle": {
            "tank_range_miles": 500.0,
            "mpg": 10.0,
            "tank_capacity_gallons": 50.0,
            "initial_tank_status": "full",
        },
        "fuel_optimization": {
            "route_distance_miles": 100.0,
            "total_fuel_consumed_gallons": 10.0,
            "initial_fuel_gallons": 5.0,
            "additional_fuel_purchased_gallons": 5.0,
            "remaining_fuel_gallons": 0.0,
            "estimated_total_fuel_cost": 15.0,
            "number_of_stops": 1,
            "stops": [stop],
            "optimization_method": "dynamic_programming",
        },
        "cost_summary": {
            "currency": "USD",
            "total_fuel_consumed_gallons": 10.0,
            "initial_fuel_available_gallons": 5.0,
            "initial_fuel_used_gallons": 5.0,
            "initial_fuel_cost": 0.0,
            "additional_fuel_purchased_gallons": 5.0,
            "remaining_fuel_gallons": 0.0,
            "total_fuel_cost": 15.0,
            "number_of_paid_stops": 1,
        },
        "fuel_cost_breakdown": {
            "stops": [breakdown_stop],
        },
        "station_matching": {
            "corridor_width_miles": 10.0,
            "total_matched_stations": 1,
            "stations_considered": 100,
            "selected_stops": 1,
        },
        "data_quality": {
            "approximate_coordinate_stops": 0,
            "has_approximate_coordinates": False,
        },
    }