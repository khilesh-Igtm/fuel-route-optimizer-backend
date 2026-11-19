
from django.urls import path

from apps.trips.views import OptimizeRouteAPIView


urlpatterns = [
    path(
        "route/optimize/",
        OptimizeRouteAPIView.as_view(),
        name="optimize-route",
    ),
]
