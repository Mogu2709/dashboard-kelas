from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

# Import dashboard_view langsung di sini
from accounts.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # ─── Dashboard (root '/') ─────────────────────────────────────────────────
    # FIX: Taruh dashboard_view di root SEBELUM include accounts.urls.
    # Dengan begini '/' selalu hit dashboard_view (yang sudah ada @login_required
    # di dalamnya), bukan tertimpa oleh accounts.urls.
    path('', dashboard_view, name='dashboard'),

    # ─── Accounts (login, register, profil, kelola user) ─────────────────────
    # accounts.urls TIDAK boleh punya path('') lagi — harus ada prefix
    # misal 'login/', 'register/', dll. (lihat accounts_urls_fixed.py)
    path('', include('accounts.urls')),

    # Logout pakai bawaan Django
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # ─── Fitur Utama ──────────────────────────────────────────────────────────
    path('absensi/', include('attendance.urls')),
    path('tugas/', include('tasks.urls')),
]

# Serve media files saat development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)