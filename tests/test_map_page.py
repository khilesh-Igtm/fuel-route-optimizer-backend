from django.test import TestCase
from django.urls import reverse


class FuelOptimizerMapPageTests(TestCase):

    def test_optimizer_map_page_returns_200(self):
        response = self.client.get(
            reverse("fuel-route-optimizer-map")
        )

        self.assertEqual(response.status_code, 200)

    def test_optimizer_map_page_uses_correct_template(self):
        response = self.client.get(
            reverse("fuel-route-optimizer-map")
        )

        self.assertTemplateUsed(
            response,
            "routing/optimizer.html",
        )

    def test_optimizer_page_contains_api_endpoint(self):
        response = self.client.get(
            reverse("fuel-route-optimizer-map")
        )

        self.assertContains(
            response,
            "/api/v1/route/optimize/",
        )

    def test_optimizer_page_contains_leaflet(self):
        response = self.client.get(
            reverse("fuel-route-optimizer-map")
        )

        self.assertContains(response, "leaflet")
        self.assertContains(response, "route-map")

    def test_optimizer_page_contains_route_form(self):
        response = self.client.get(
            reverse("fuel-route-optimizer-map")
        )

        self.assertContains(response, "start-location")
        self.assertContains(response, "end-location")
        self.assertContains(response, "optimize-button")

    def test_optimizer_map_page_rejects_post(self):
        response = self.client.post(
            reverse("fuel-route-optimizer-map")
        )

        self.assertEqual(response.status_code, 405)