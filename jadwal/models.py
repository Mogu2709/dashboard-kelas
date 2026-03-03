from django.db import models
from django.contrib.auth.models import User
from attendance.models import MataKuliah


HARI_CHOICES = [
    ('senin',  'Senin'),
    ('selasa', 'Selasa'),
    ('rabu',   'Rabu'),
    ('kamis',  'Kamis'),
    ('jumat',  'Jumat'),
    ('sabtu',  'Sabtu'),
]

MODE_CHOICES = [
    ('offline', 'Offline'),
    ('online',  'Online'),
    ('hybrid',  'Hybrid'),
]


class JadwalStatis(models.Model):
    """Jadwal tetap per semester — template mingguan."""
    mata_kuliah = models.ForeignKey(
        MataKuliah, on_delete=models.CASCADE, related_name='jadwal_statis'
    )
    semester    = models.IntegerField()
    hari        = models.CharField(max_length=10, choices=HARI_CHOICES)
    jam_mulai   = models.TimeField()
    jam_selesai = models.TimeField()
    ruang       = models.CharField(max_length=50, blank=True)
    dosen       = models.CharField(max_length=100, blank=True)
    mode        = models.CharField(max_length=10, choices=MODE_CHOICES, default='offline')
    link_online = models.URLField(blank=True, help_text='Link Zoom/Meet jika online')
    aktif       = models.BooleanField(default=True)
    dibuat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diupdate_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['hari', 'jam_mulai']
        verbose_name = 'Jadwal Statis'
        verbose_name_plural = 'Jadwal Statis'

    def __str__(self):
        return f"{self.mata_kuliah.nama} — {self.get_hari_display()} {self.jam_mulai}"

    @property
    def durasi_menit(self):
        from datetime import datetime, date
        start = datetime.combine(date.today(), self.jam_mulai)
        end   = datetime.combine(date.today(), self.jam_selesai)
        return int((end - start).total_seconds() / 60)


class JadwalDinamis(models.Model):
    """Override per tanggal — cancel, pindah, ganti mode, dll."""

    TIPE_CHOICES = [
        ('cancel',   'Kelas Dibatalkan'),
        ('reschedule', 'Pindah Jadwal'),
        ('mode',     'Ganti Mode'),
        ('info',     'Informasi'),
    ]

    jadwal_statis = models.ForeignKey(
        JadwalStatis, on_delete=models.CASCADE,
        related_name='overrides', null=True, blank=True,
        help_text='Kosongkan jika ini jadwal tambahan (tidak ada di statis)'
    )
    mata_kuliah   = models.ForeignKey(
        MataKuliah, on_delete=models.CASCADE, related_name='jadwal_dinamis'
    )
    tanggal_asli  = models.DateField(help_text='Tanggal pertemuan yang terpengaruh')
    tipe          = models.CharField(max_length=20, choices=TIPE_CHOICES)

    # Field untuk reschedule
    tanggal_baru  = models.DateField(null=True, blank=True)
    jam_mulai_baru   = models.TimeField(null=True, blank=True)
    jam_selesai_baru = models.TimeField(null=True, blank=True)
    ruang_baru    = models.CharField(max_length=50, blank=True)

    # Field untuk ganti mode
    mode_baru     = models.CharField(max_length=10, choices=MODE_CHOICES, blank=True)
    link_online   = models.URLField(blank=True)

    catatan       = models.TextField(blank=True, help_text='Alasan/keterangan tambahan')
    dibuat_oleh   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    dibuat_pada   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tanggal_asli']
        verbose_name = 'Perubahan Jadwal'
        verbose_name_plural = 'Perubahan Jadwal'

    def __str__(self):
        return f"{self.mata_kuliah.nama} — {self.get_tipe_display()} ({self.tanggal_asli})"
