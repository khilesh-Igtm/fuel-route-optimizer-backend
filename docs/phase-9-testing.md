# Fuel Route Optimizer - Phase 9

## Objective

Establish automated regression testing, API contract validation,
fuel calculation invariants, and long-distance route reliability.

## API Contract

POST /api/v1/route/optimize/

Request:

{
    "start_location": "New York, NY",
    "end_location": "Los Angeles, CA",
    "corridor_width_miles": 10,
    "max_stations": 500
}

## Test Coverage

1. API request validation
2. JSON response structure
3. GeoJSON LineString validation
4. Vehicle and fuel information
5. Fuel consumption calculations
6. Fuel balance reconciliation
7. Individual station cost calculations
8. Total cost reconciliation
9. Stop ordering
10. Station matching consistency
11. Coordinate quality flags
12. Long-distance route regression

## Business Rules

- Tank range is not maximum trip distance.
- Long-distance journeys are supported.
- Fuel consumption is calculated using distance / MPG.
- Fuel purchases must reconcile with fuel consumption.
- Stop costs must reconcile with fuel price and purchased gallons.
- Approximate station coordinates must remain identifiable.

## Existing Regression Coverage

Existing station matching tests and performance tests
must remain operational.

## External Services

Unit tests must use deterministic data.

Live OSRM, Nominatim and external fuel-data calls
are not required for deterministic unit tests.

## Verification

Run:

pytest -v

Run focused Phase 9 tests:

pytest tests/test_phase9_api_validation.py -v
pytest tests/test_phase9_response_contract.py -v
pytest tests/test_phase9_fuel_invariants.py -v
pytest tests/test_phase9_long_distance_regression.py -v

Run lint:

ruff check tests

Run Django checks:

python manage.py check