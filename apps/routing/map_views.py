from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def optimizer_map_page(request):
    """
    Render the Fuel Route Optimizer interactive map interface.
    """
    return render(
        request,
        "routing/optimizer.html",
        {
            "api_endpoint": "/api/v1/route/optimize/",
        },
    )