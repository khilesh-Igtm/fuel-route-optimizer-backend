from django.urls import path

from apps.routing.map_views import optimizer_map_page


urlpatterns = [
    path(
        "optimizer/",
        optimizer_map_page,
        name="fuel-route-optimizer-map",
    ),
]