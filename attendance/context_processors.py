from .models import IzinAbsen


def izin_pending_count(request):
    """Inject pending izin count untuk admin badge di sidebar."""
    # FIX BUG: guard lengkap agar tidak crash di error handlers atau middleware early exit
    if not hasattr(request, 'user'):
        return {'pending_izin_count': 0}
    if not request.user.is_authenticated:
        return {'pending_izin_count': 0}
    if not request.user.is_superuser:
        return {'pending_izin_count': 0}
    count = IzinAbsen.objects.filter(status='pending').count()
    return {'pending_izin_count': count}
