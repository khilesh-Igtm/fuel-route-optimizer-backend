from django.http import JsonResponse
from django.utils import timezone


def health_check(request):
    return JsonResponse(
        {
            "status": "healthy",
            "service": "fuel-route-optimizer",
            "timestamp": timezone.now().isoformat(),
        }
    )