from django.contrib import admin
from .models import Pertemuan, Attendance
from .models import MataKuliah

admin.site.register(Pertemuan)
admin.site.register(Attendance)
admin.site.register(MataKuliah)