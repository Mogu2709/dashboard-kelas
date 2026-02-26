from django.urls import path
from . import views

urlpatterns = [
    # Tugas
    path('', views.tugas_list, name='tugas_list'),
    path('buat/', views.buat_tugas, name='buat_tugas'),
    path('<int:pk>/', views.detail_tugas, name='detail_tugas'),
    path('<int:pk>/edit/', views.edit_tugas, name='edit_tugas'),
    path('<int:pk>/hapus/', views.hapus_tugas, name='hapus_tugas'),
    path('submission/<int:pk>/hapus/', views.hapus_submission, name='hapus_submission'),

    # Materi
    path('materi/', views.materi_list, name='materi_list'),
    path('materi/unggah/', views.unggah_materi, name='unggah_materi'),
    path('materi/<int:pk>/edit/', views.edit_materi, name='edit_materi'),
    path('materi/<int:pk>/hapus/', views.hapus_materi, name='hapus_materi'),
]
