from django.contrib import admin
from django.utils.html import format_html
from .models import (
    MataKuliah, Pertemuan, Attendance,
    Pengumuman, PengumumanAttachment, PengumumanDibaca,
    IzinAbsen
)


@admin.register(MataKuliah)
class MataKuliahAdmin(admin.ModelAdmin):
    list_display = ('nama', 'semester')
    list_filter = ('semester',)
    search_fields = ('nama',)
    ordering = ('semester', 'nama')


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    readonly_fields = ('user', 'waktu_hadir')
    can_delete = False


@admin.register(Pertemuan)
class PertemuanAdmin(admin.ModelAdmin):
    list_display = ('judul', 'mata_kuliah', 'tanggal', 'kode_absen', 'get_kode_aktif', 'jumlah_hadir')
    list_filter = ('mata_kuliah', 'tanggal')
    search_fields = ('judul', 'kode_absen')
    readonly_fields = ('kode_absen',)
    inlines = (AttendanceInline,)
    ordering = ('-tanggal',)

    @admin.display(description='Kode Aktif?', boolean=True)
    def get_kode_aktif(self, obj):
        return obj.kode_aktif

    @admin.display(description='Hadir')
    def jumlah_hadir(self, obj):
        return obj.attendance_set.count()


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'pertemuan', 'waktu_hadir')
    list_filter = ('pertemuan__mata_kuliah',)
    search_fields = ('user__username', 'pertemuan__judul')
    readonly_fields = ('waktu_hadir',)
    ordering = ('-waktu_hadir',)


@admin.register(IzinAbsen)
class IzinAbsenAdmin(admin.ModelAdmin):
    list_display = ('user', 'pertemuan', 'jenis', 'get_status_badge', 'dibuat_pada', 'diproses_oleh')
    list_filter = ('status', 'jenis')
    search_fields = ('user__username', 'pertemuan__judul')
    readonly_fields = ('dibuat_pada', 'diproses_pada')
    ordering = ('-dibuat_pada',)
    actions = ['approve_izin', 'reject_izin']

    @admin.display(description='Status')
    def get_status_badge(self, obj):
        colors = {'pending': '#f59e0b', 'approved': '#22c55e', 'rejected': '#ef4444'}
        color = colors.get(obj.status, '#gray')
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.action(description='✅ Setujui izin terpilih')
    def approve_izin(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='approved',
            diproses_oleh=request.user,
            diproses_pada=timezone.now()
        )
        self.message_user(request, f'{updated} izin berhasil disetujui.')

    @admin.action(description='❌ Tolak izin terpilih')
    def reject_izin(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='rejected',
            diproses_oleh=request.user,
            diproses_pada=timezone.now()
        )
        self.message_user(request, f'{updated} izin berhasil ditolak.')


@admin.register(Pengumuman)
class PengumumanAdmin(admin.ModelAdmin):
    list_display = ('judul', 'prioritas', 'pinned', 'dibuat_oleh', 'dibuat_pada')
    list_filter = ('prioritas', 'pinned')
    search_fields = ('judul', 'isi')
    readonly_fields = ('dibuat_pada', 'diedit_pada')
    ordering = ('-pinned', '-dibuat_pada')
