from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts.views import dashboard_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth & Accounts (register, login custom, pending, kelola user)
    path('', include('accounts.urls')),

    # Logout tetap pakai bawaan Django
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Absensi & Pengumuman
    path('absensi/', include('attendance.urls')),

    # tugas
    path('tugas/', include('tasks.urls')),

    # Dashboard (root URL)
    path('', dashboard_view, name='dashboard'),
]

# Serve media files saat development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
