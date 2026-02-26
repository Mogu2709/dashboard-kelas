from django.contrib import admin
from .models import MataKuliah, Pertemuan, Attendance

admin.site.register(Pertemuan)
admin.site.register(Attendance)
admin.site.register(MataKuliah)