from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os

# Custom storage untuk file non-media (docx, xlsx, zip, dll)
try:
    from cloudinary_storage.storage import RawMediaCloudinaryStorage
    raw_storage = RawMediaCloudinaryStorage()
except Exception:
    raw_storage = None  # Fallback ke default storage


def tugas_soal_upload_path(instance, filename):
    return f'tugas/{instance.mata_kuliah.id}/soal/{filename}'


def tugas_submission_upload_path(instance, filename):
    return f'tugas/{instance.tugas.id}/jawaban/{instance.user.username}/{filename}'


def materi_upload_path(instance, filename):
    return f'materi/{instance.mata_kuliah.id}/{filename}'


class Tugas(models.Model):
    mata_kuliah  = models.ForeignKey('attendance.MataKuliah', on_delete=models.CASCADE, related_name='tugas')
    judul        = models.CharField(max_length=200)
    deskripsi    = models.TextField(blank=True)
    deadline     = models.DateTimeField()
    dibuat_oleh  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tugas_dibuat')
    dibuat_pada  = models.DateTimeField(auto_now_add=True)
    diedit_pada  = models.DateTimeField(null=True, blank=True)
    file_soal    = models.FileField(
        upload_to=tugas_soal_upload_path,
        blank=True, null=True,
        storage=raw_storage
    )
    nama_file_soal = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-dibuat_pada']

    def __str__(self):
        return f"{self.judul} - {self.mata_kuliah.nama}"

    @property
    def is_expired(self):
        return timezone.now() > self.deadline

    @property
    def sisa_waktu(self):
        delta = self.deadline - timezone.now()
        if delta.total_seconds() < 0:
            return None
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if days > 0:
            return f"{days} hari {hours} jam"
        elif hours > 0:
            return f"{hours} jam {minutes} menit"
        else:
            return f"{minutes} menit"

    def save(self, *args, **kwargs):
        if self.file_soal and not self.nama_file_soal:
            self.nama_file_soal = os.path.basename(self.file_soal.name)
        super().save(*args, **kwargs)


class TugasSubmission(models.Model):
    tugas         = models.ForeignKey(Tugas, on_delete=models.CASCADE, related_name='submissions')
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    file_jawaban  = models.FileField(
        upload_to=tugas_submission_upload_path,
        storage=raw_storage
    )
    nama_file     = models.CharField(max_length=255, blank=True)
    ukuran        = models.PositiveBigIntegerField(default=0)
    catatan       = models.TextField(blank=True)
    dikumpulkan_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tugas', 'user')
        ordering = ['-dikumpulkan_pada']

    def __str__(self):
        return f"{self.user.username} - {self.tugas.judul}"

    @property
    def terlambat(self):
        return self.dikumpulkan_pada > self.tugas.deadline

    @property
    def ukuran_display(self):
        if self.ukuran < 1024:
            return f'{self.ukuran} B'
        elif self.ukuran < 1024 * 1024:
            return f'{self.ukuran / 1024:.1f} KB'
        else:
            return f'{self.ukuran / (1024*1024):.1f} MB'

    def save(self, *args, **kwargs):
        if self.file_jawaban and not self.nama_file:
            self.nama_file = os.path.basename(self.file_jawaban.name)
        if self.file_jawaban and not self.ukuran:
            try:
                self.ukuran = self.file_jawaban.size
            except Exception:
                pass
        super().save(*args, **kwargs)


class Materi(models.Model):
    mata_kuliah  = models.ForeignKey('attendance.MataKuliah', on_delete=models.CASCADE, related_name='materi')
    judul        = models.CharField(max_length=200)
    deskripsi    = models.TextField(blank=True)
    file         = models.FileField(
        upload_to=materi_upload_path,
        blank=True, null=True,
        storage=raw_storage
    )
    nama_file    = models.CharField(max_length=255, blank=True)
    ukuran       = models.PositiveBigIntegerField(default=0)
    diunggah_oleh = models.ForeignKey(User, on_delete=models.CASCADE, related_name='materi_diunggah')
    diunggah_pada = models.DateTimeField(auto_now_add=True)
    diedit_pada   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-diunggah_pada']

    def __str__(self):
        return f"{self.judul} - {self.mata_kuliah.nama}"

    @property
    def ukuran_display(self):
        if self.ukuran < 1024:
            return f'{self.ukuran} B'
        elif self.ukuran < 1024 * 1024:
            return f'{self.ukuran / 1024:.1f} KB'
        else:
            return f'{self.ukuran / (1024*1024):.1f} MB'

    @property
    def ekstensi(self):
        if self.nama_file:
            return self.nama_file.split('.')[-1].lower()
        return ''

    def save(self, *args, **kwargs):
        if self.file and not self.nama_file:
            self.nama_file = os.path.basename(self.file.name)
        if self.file and not self.ukuran:
            try:
                self.ukuran = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)