from django.contrib import admin
from .models import JadwalStatis, JadwalDinamis


@admin.register(JadwalStatis)
class JadwalStatisAdmin(admin.ModelAdmin):
    list_display  = ['mata_kuliah', 'semester', 'hari', 'jam_mulai', 'jam_selesai', 'ruang', 'mode', 'aktif']
    list_filter   = ['semester', 'hari', 'mode', 'aktif']
    search_fields = ['mata_kuliah__nama', 'ruang', 'dosen']
    ordering      = ['semester', 'hari', 'jam_mulai']


@admin.register(JadwalDinamis)
class JadwalDinamisAdmin(admin.ModelAdmin):
    list_display  = ['mata_kuliah', 'tipe', 'tanggal_asli', 'tanggal_baru', 'mode_baru', 'dibuat_oleh']
    list_filter   = ['tipe', 'mode_baru']
    search_fields = ['mata_kuliah__nama', 'catatan']
    ordering      = ['-tanggal_asli']
