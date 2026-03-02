from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'  # FIX: tunjuk FK yang benar, bukan diproses_oleh
    can_delete = False
    verbose_name_plural = 'Profil'
    fields = ('status', 'nama_lengkap', 'nim', 'jurusan', 'angkatan', 'jenis_kelamin',
              'diproses_pada', 'diproses_oleh')
    readonly_fields = ('diproses_pada', 'diproses_oleh')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'get_nama_lengkap', 'get_status', 'is_superuser', 'date_joined')
    list_filter = ('profile__status', 'is_superuser')
    search_fields = ('username', 'profile__nama_lengkap', 'profile__nim')

    @admin.display(description='Nama Lengkap')
    def get_nama_lengkap(self, obj):
        try:
            return obj.profile.nama_lengkap or '-'
        except UserProfile.DoesNotExist:
            return '-'

    @admin.display(description='Status')
    def get_status(self, obj):
        try:
            return obj.profile.get_status_display()
        except UserProfile.DoesNotExist:
            return '-'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nama_lengkap', 'nim', 'status', 'dibuat_pada')
    list_filter = ('status', 'jenis_kelamin')
    search_fields = ('user__username', 'nama_lengkap', 'nim')
    readonly_fields = ('dibuat_pada', 'diproses_pada')
    actions = ['approve_users', 'reject_users']

    @admin.action(description='✅ Setujui user terpilih')
    def approve_users(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='approved', diproses_pada=timezone.now(), diproses_oleh=request.user)
        self.message_user(request, f'{updated} user berhasil disetujui.')

    @admin.action(description='❌ Tolak user terpilih')
    def reject_users(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='rejected', diproses_pada=timezone.now(), diproses_oleh=request.user)
        self.message_user(request, f'{updated} user berhasil ditolak.')