# Fuel Route Optimizer

A Django REST API that calculates cost-effective fuel stops
for road journeys across the United States.

## Technology Stack

- Python 3.12
- Django 6.1
- Django REST Framework
- SQLite
- OSRM Routing API
- Nominatim Geocoding API
- SimpleMaps US Cities Dataset
- Leaflet Map
- Pytest

## Core Constraints

- Maximum vehicle range: 500 miles
- Fuel efficiency: 10 MPG
- Focus: USA road journeys

## Architecture

### Common
Shared utilities and health checks.

### Locations
City lookup, geocoding and location resolution.

### Routing
Road route calculation using OSRM.

### Fuel
Fuel consumption and fuel-stop optimization.

### Trips
Trip API, request validation and response serialization.

## API

GET /api/v1/health/

POST /api/v1/routes/

## Development

Activate virtual environment:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Run migrations:

python manage.py migrate

Start server:

python manage.py runserver

Run tests:

pytest