import json

import pytest
from django.test import Client


ENDPOINT = "/api/v1/route/optimize/"

VALID_PAYLOAD = {
    "start_location": "New York, NY",
    "end_location": "Los Angeles, CA",
    "corridor_width_miles": 10,
    "max_stations": 500,
}


@pytest.fixture
def api_client():
    return Client()


def post_json(client, payload):
    return client.post(
        ENDPOINT,
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_missing_start_location_is_rejected(api_client):
    payload = VALID_PAYLOAD.copy()
    payload.pop("start_location")

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)


def test_missing_destination_is_rejected(api_client):
    payload = VALID_PAYLOAD.copy()
    payload.pop("end_location")

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)


def test_empty_locations_are_rejected(api_client):
    payload = VALID_PAYLOAD.copy()
    payload["start_location"] = ""
    payload["end_location"] = ""

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)


@pytest.mark.parametrize("corridor_width", [0, -1, -10])
def test_invalid_corridor_width_is_rejected(
    api_client,
    corridor_width,
):
    payload = VALID_PAYLOAD.copy()
    payload["corridor_width_miles"] = corridor_width

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)


@pytest.mark.parametrize("max_stations", [0, -1, -500])
def test_invalid_max_stations_is_rejected(
    api_client,
    max_stations,
):
    payload = VALID_PAYLOAD.copy()
    payload["max_stations"] = max_stations

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)


def test_invalid_json_is_rejected(api_client):
    response = api_client.post(
        ENDPOINT,
        data="{invalid-json",
        content_type="application/json",
    )

    assert response.status_code in (400, 415)


def test_unrelated_fields_do_not_replace_required_fields(api_client):
    payload = {
        "start": "New York",
        "destination": "Los Angeles",
        "corridor_width_miles": 10,
        "max_stations": 500,
    }

    response = post_json(api_client, payload)

    assert response.status_code in (400, 422)