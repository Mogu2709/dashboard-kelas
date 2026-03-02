from django.contrib import admin
from .models import Tugas, TugasSubmission, Materi, Notifikasi


class TugasSubmissionInline(admin.TabularInline):
    model = TugasSubmission
    extra = 0
    readonly_fields = ("user", "dikumpulkan_pada", "nilai", "grade_label")
    can_delete = False
    fields = ("user", "nilai", "grade_label", "dikumpulkan_pada")


@admin.register(Tugas)
class TugasAdmin(admin.ModelAdmin):
    list_display = ("judul", "mata_kuliah", "deadline", "get_expired", "jumlah_submit")
    list_filter = ("mata_kuliah",)
    search_fields = ("judul",)
    readonly_fields = ("dibuat_pada", "diedit_pada")
    inlines = (TugasSubmissionInline,)
    ordering = ("-dibuat_pada",)

    @admin.display(description="Expired?", boolean=True)
    def get_expired(self, obj):
        return obj.is_expired

    @admin.display(description="Submit")
    def jumlah_submit(self, obj):
        return obj.submissions.count()


@admin.register(TugasSubmission)
class TugasSubmissionAdmin(admin.ModelAdmin):
    list_display = ("user", "tugas", "nilai", "grade_label", "dikumpulkan_pada")
    list_filter = ("tugas__mata_kuliah",)
    search_fields = ("user__username", "tugas__judul")
    readonly_fields = ("dikumpulkan_pada", "diperbarui_pada")
    ordering = ("-dikumpulkan_pada",)


@admin.register(Materi)
class MateriAdmin(admin.ModelAdmin):
    list_display = ("judul", "mata_kuliah", "diunggah_oleh", "diunggah_pada", "ukuran_display")
    list_filter = ("mata_kuliah",)
    search_fields = ("judul",)
    readonly_fields = ("diunggah_pada", "diedit_pada")
    ordering = ("-diunggah_pada",)


@admin.register(Notifikasi)
class NotifikasiAdmin(admin.ModelAdmin):
    list_display = ("user", "tipe", "judul", "dibaca", "dibuat_pada")
    list_filter = ("tipe", "dibaca")
    search_fields = ("user__username", "judul")
    readonly_fields = ("dibuat_pada",)
    ordering = ("-dibuat_pada",)
    actions = ["tandai_dibaca"]

    @admin.action(description="Tandai sudah dibaca")
    def tandai_dibaca(self, request, queryset):
        updated = queryset.update(dibaca=True)
        self.message_user(request, f"{updated} notifikasi ditandai dibaca.")
