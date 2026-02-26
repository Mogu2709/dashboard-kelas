from django.urls import path
from . import views

urlpatterns = [
    # ─── Auth ─────────────────────────────────────────────────────────────────
    # FIX: TIDAK ada path('') di sini supaya tidak bentrok dengan
    # dashboard_view di config/urls.py yang juga pakai path('').
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('pending/', views.pending_approval_view, name='pending_approval'),

    # ─── Profil ───────────────────────────────────────────────────────────────
    path('profil/', views.profil_view, name='profil'),
    path('profil/<int:user_id>/', views.profil_user_view, name='profil_user'),

    # ─── Kelola User (superuser) ──────────────────────────────────────────────
    path('kelola-user/', views.kelola_user_view, name='kelola_user'),
    path('kelola-user/<int:user_id>/approve/', views.approve_user_view, name='approve_user'),
    path('kelola-user/<int:user_id>/reject/', views.reject_user_view, name='reject_user'),
    path('kelola-user/<int:user_id>/hapus/', views.hapus_user_view, name='hapus_user'),
]