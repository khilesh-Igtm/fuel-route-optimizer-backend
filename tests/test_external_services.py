
import pytest
from unittest.mock import Mock, patch

from django.core.cache import cache

from apps.locations.geocoding import (
    GeocodingError,
    geocode_location,
)
from apps.routing.osrm import (
    RoutingError,
    get_driving_route,
)
from apps.routing.services import calculate_route


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def nominatim_response():
    return [
        {
            "lat": "40.7128",
            "lon": "-74.0060",
            "display_name": "New York, NY, USA",
        }
    ]


@pytest.fixture
def osrm_response():
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 306000,
                "duration": 14400,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-74.0060, 40.7128],
                        [-73.9000, 40.8000],
                        [-71.0589, 42.3601],
                    ],
                },
            }
        ],
    }


@pytest.mark.django_db
class TestGeocoding:

    @patch("apps.locations.geocoding.requests.get")
    def test_successful_geocoding(
        self,
        mock_get,
        nominatim_response,
    ):
        mock_response = Mock()
        mock_response.json.return_value = nominatim_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_location("New York, NY, USA")

        assert result["latitude"] == 40.7128
        assert result["longitude"] == -74.0060
        assert result["display_name"] == "New York, NY, USA"

        mock_get.assert_called_once()

    @patch("apps.locations.geocoding.requests.get")
    def test_geocoding_uses_cache(
        self,
        mock_get,
        nominatim_response,
    ):
        mock_response = Mock()
        mock_response.json.return_value = nominatim_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        first_result = geocode_location("New York, NY, USA")
        second_result = geocode_location("New York, NY, USA")

        assert first_result == second_result
        mock_get.assert_called_once()

    @patch("apps.locations.geocoding.requests.get")
    def test_location_not_found(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(GeocodingError):
            geocode_location("Unknown Invalid Location")

    def test_empty_location(self):
        with pytest.raises(GeocodingError):
            geocode_location("")

    @patch("apps.locations.geocoding.requests.get")
    def test_geocoding_api_failure(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException(
            "Connection failed"
        )

        with pytest.raises(GeocodingError):
            geocode_location("New York, NY, USA")


@pytest.mark.django_db
class TestOSRMRouting:

    @patch("apps.routing.osrm.requests.get")
    def test_successful_route(
        self,
        mock_get,
        osrm_response,
    ):
        mock_response = Mock()
        mock_response.json.return_value = osrm_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_driving_route(
            40.7128,
            -74.0060,
            42.3601,
            -71.0589,
        )

        assert result["distance_meters"] == 306000
        assert result["distance_miles"] == 190.14
        assert result["duration_minutes"] == 240

        assert result["geometry"]["type"] == "LineString"
        assert len(result["geometry"]["coordinates"]) == 3

    @patch("apps.routing.osrm.requests.get")
    def test_route_uses_cache(
        self,
        mock_get,
        osrm_response,
    ):
        mock_response = Mock()
        mock_response.json.return_value = osrm_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        first_result = get_driving_route(
            40.7128,
            -74.0060,
            42.3601,
            -71.0589,
        )

        second_result = get_driving_route(
            40.7128,
            -74.0060,
            42.3601,
            -71.0589,
        )

        assert first_result == second_result
        mock_get.assert_called_once()

    def test_invalid_coordinates(self):
        with pytest.raises(RoutingError):
            get_driving_route(
                100,
                -74.0060,
                42.3601,
                -71.0589,
            )

    def test_non_numeric_coordinates(self):
        with pytest.raises(RoutingError):
            get_driving_route(
                "invalid",
                -74.0060,
                42.3601,
                -71.0589,
            )

    @patch("apps.routing.osrm.requests.get")
    def test_no_route_found(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": "NoRoute",
            "message": "No route found",
            "routes": [],
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(RoutingError):
            get_driving_route(
                40.7128,
                -74.0060,
                42.3601,
                -71.0589,
            )

    @patch("apps.routing.osrm.requests.get")
    def test_osrm_api_failure(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException(
            "Connection failed"
        )

        with pytest.raises(RoutingError):
            get_driving_route(
                40.7128,
                -74.0060,
                42.3601,
                -71.0589,
            )


@pytest.mark.django_db
class TestCombinedRoutingService:

    @patch("apps.routing.services.get_driving_route")
    @patch("apps.routing.services.geocode_location")
    def test_calculate_route(
        self,
        mock_geocode,
        mock_route,
    ):
        mock_geocode.side_effect = [
            {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "display_name": "New York, NY, USA",
            },
            {
                "latitude": 42.3601,
                "longitude": -71.0589,
                "display_name": "Boston, MA, USA",
            },
        ]

        mock_route.return_value = {
            "distance_meters": 306000,
            "distance_miles": 190.14,
            "duration_seconds": 14400,
            "duration_minutes": 240,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0060, 40.7128],
                    [-71.0589, 42.3601],
                ],
            },
        }

        result = calculate_route(
            "New York, NY, USA",
            "Boston, MA, USA",
        )

        assert result["start"]["latitude"] == 40.7128

        assert result["destination"]["latitude"] == 42.3601

        assert result["route"]["distance_miles"] == 190.14

        assert result["route"]["duration_minutes"] == 240

        mock_geocode.assert_any_call("New York, NY, USA")
        mock_geocode.assert_any_call("Boston, MA, USA")

        mock_route.assert_called_once_with(
            start_latitude=40.7128,
            start_longitude=-74.0060,
            end_latitude=42.3601,
            end_longitude=-71.0589,
        )
