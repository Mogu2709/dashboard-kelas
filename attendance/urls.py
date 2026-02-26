from django.urls import path
from .views import pertemuan_list, hadir, buat_pertemuan
from . import views
from . import exports

urlpatterns = [
    # Absensi
    path('', pertemuan_list, name='pertemuan_list'),
    path('hadir/<int:pertemuan_id>/', hadir, name='hadir'),
    path('hadir/<int:pertemuan_id>/kode/', views.absen_kode, name='absen_kode'),
    path('buat/', buat_pertemuan, name='buat_pertemuan'),
    path('pertemuan/<int:pk>/', views.detail_pertemuan, name='detail_pertemuan'),
    path('rekap/', views.rekap_mahasiswa, name='rekap_mahasiswa'),

    # Izin Absen
    path('izin/', views.daftar_izin, name='daftar_izin'),
    path('izin/saya/', views.izin_saya, name='izin_saya'),
    path('izin/<int:pertemuan_id>/ajukan/', views.ajukan_izin, name='ajukan_izin'),
    path('izin/<int:izin_id>/proses/', views.proses_izin, name='proses_izin'),

    # Export
    path('rekap/export/excel/', exports.export_excel, name='export_excel'),
    path('rekap/export/pdf/', exports.export_pdf, name='export_pdf'),

    # Pengumuman
    path('pengumuman/', views.pengumuman_list, name='pengumuman_list'),
    path('pengumuman/buat/', views.buat_pengumuman, name='buat_pengumuman'),
    path('pengumuman/<int:pk>/edit/', views.edit_pengumuman, name='edit_pengumuman'),
    path('pengumuman/<int:pk>/hapus/', views.hapus_pengumuman, name='hapus_pengumuman'),
    path('pengumuman/<int:pk>/baca/', views.tandai_dibaca, name='tandai_dibaca'),
    path('pengumuman/baca-semua/', views.tandai_semua_dibaca, name='tandai_semua_dibaca'),
    path('pengumuman/notif-count/', views.notif_count, name='notif_count'),

    # Like & Komentar (AJAX)
    path('pengumuman/<int:pk>/like/', views.toggle_like, name='toggle_like'),
    path('pengumuman/<int:pk>/komentar/', views.tambah_komentar, name='tambah_komentar'),
    path('komentar/<int:pk>/edit/', views.edit_komentar, name='edit_komentar'),
    path('komentar/<int:pk>/hapus/', views.hapus_komentar, name='hapus_komentar'),
]