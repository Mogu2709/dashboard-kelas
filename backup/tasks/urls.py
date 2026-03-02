from django.urls import path
from . import views

urlpatterns = [
    # Notifikasi API
    path('notif/', views.notif_list_api, name='notif_list_api'),
    path('notif/baca-semua/', views.notif_baca_semua, name='notif_baca_semua'),
    path('notif/<int:pk>/baca/', views.notif_baca, name='notif_baca'),

    # Tugas
    path('', views.tugas_list, name='tugas_list'),
    path('buat/', views.buat_tugas, name='buat_tugas'),
    path('<int:pk>/', views.detail_tugas, name='detail_tugas'),
    path('<int:pk>/edit/', views.edit_tugas, name='edit_tugas'),
    path('<int:pk>/hapus/', views.hapus_tugas, name='hapus_tugas'),
    path('submission/<int:pk>/hapus/', views.hapus_submission, name='hapus_submission'),

    # FITUR BARU: Grading / Nilai
    path('submission/<int:pk>/nilai/', views.beri_nilai, name='beri_nilai'),

    # Grafik & Kalender halaman
    path('grafik/', views.grafik_kalender_page, name='grafik_kalender'),

    # Search
    path('search/', views.search, name='search'),

    # Grafik & Kalender API
    path('grafik-kehadiran/', views.grafik_kehadiran, name='grafik_kehadiran'),
    path('kalender/', views.kalender_data, name='kalender_data'),

    # Materi
    path('materi/', views.materi_list, name='materi_list'),
    path('materi/unggah/', views.unggah_materi, name='unggah_materi'),
    path('materi/<int:pk>/edit/', views.edit_materi, name='edit_materi'),
    path('materi/<int:pk>/hapus/', views.hapus_materi, name='hapus_materi'),
]