from .models import IzinAbsen


def izin_pending_count(request):
    """Inject pending izin count untuk admin badge di sidebar."""
    if request.user.is_authenticated and request.user.is_superuser:
        count = IzinAbsen.objects.filter(status='pending').count()
        return {'pending_izin_count': count}
    return {'pending_izin_count': 0}
