from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.jadwal_view,           name='jadwal'),
    path('api/',                      views.jadwal_api,            name='jadwal_api'),
    path('statis/tambah/',            views.jadwal_statis_tambah,  name='jadwal_statis_tambah'),
    path('statis/<int:pk>/edit/',     views.jadwal_statis_edit,    name='jadwal_statis_edit'),
    path('statis/<int:pk>/hapus/',    views.jadwal_statis_hapus,   name='jadwal_statis_hapus'),
    path('perubahan/tambah/',         views.jadwal_dinamis_tambah, name='jadwal_dinamis_tambah'),
    path('perubahan/<int:pk>/hapus/', views.jadwal_dinamis_hapus,  name='jadwal_dinamis_hapus'),
]
