from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('pending/', views.pending_approval_view, name='pending_approval'),
    path('kelola-user/', views.kelola_user_view, name='kelola_user'),
    path('kelola-user/approve/<int:user_id>/', views.approve_user_view, name='approve_user'),
    path('kelola-user/reject/<int:user_id>/', views.reject_user_view, name='reject_user'),
    path('kelola-user/hapus/<int:user_id>/', views.hapus_user_view, name='hapus_user'),
]
