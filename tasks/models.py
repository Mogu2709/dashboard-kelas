from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


# ─── STORAGE HELPER ───────────────────────────────────────────────────────────
# FIX: Jangan set storage=None ke field. Kalau Cloudinary tidak tersedia,
# biarkan Django pakai default storage (local/media).

def _get_raw_storage():
    """Return RawMediaCloudinaryStorage jika tersedia, else None (pakai default)."""
    try:
        from cloudinary_storage.storage import RawMediaCloudinaryStorage
        import cloudinary
        # Pastikan config Cloudinary sudah diset
        if cloudinary.config().cloud_name:
            return RawMediaCloudinaryStorage()
    except Exception:
        pass
    return None


# Dipanggil sekali saat startup
_raw_storage = _get_raw_storage()


def tugas_soal_upload_path(instance, filename):
    return f'tugas/{instance.mata_kuliah.id}/soal/{filename}'

def tugas_submission_upload_path(instance, filename):
    return f'tugas/{instance.tugas.id}/jawaban/{instance.user.username}/{filename}'

def materi_upload_path(instance, filename):
    return f'materi/{instance.mata_kuliah.id}/{filename}'


class Tugas(models.Model):
    mata_kuliah    = models.ForeignKey('attendance.MataKuliah', on_delete=models.CASCADE, related_name='tugas')
    judul          = models.CharField(max_length=200)
    deskripsi      = models.TextField(blank=True)
    deadline       = models.DateTimeField()
    dibuat_oleh    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tugas_dibuat')
    dibuat_pada    = models.DateTimeField(auto_now_add=True)
    diedit_pada    = models.DateTimeField(null=True, blank=True)
    # FIX: Kondisional storage - pakai Cloudinary kalau tersedia, kalau tidak pakai default
    file_soal      = models.FileField(
        upload_to=tugas_soal_upload_path,
        blank=True, null=True,
        storage=_raw_storage  # None = pakai DEFAULT_FILE_STORAGE dari settings
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
    tugas            = models.ForeignKey(Tugas, on_delete=models.CASCADE, related_name='submissions')
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    file_jawaban     = models.FileField(
        upload_to=tugas_submission_upload_path,
        storage=_raw_storage
    )
    nama_file        = models.CharField(max_length=255, blank=True)
    ukuran           = models.PositiveBigIntegerField(default=0)
    catatan          = models.TextField(blank=True)
    dikumpulkan_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada  = models.DateTimeField(auto_now=True)

    # ─── FITUR BARU: Nilai/Grading ────────────────────────────────────────────
    nilai            = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Nilai 0–100'
    )
    feedback         = models.TextField(blank=True, help_text='Feedback dari dosen/admin')
    dinilai_pada     = models.DateTimeField(null=True, blank=True)
    dinilai_oleh     = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='penilaian_diberikan'
    )

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

    @property
    def grade_label(self):
        """Konversi nilai numerik ke grade huruf."""
        if self.nilai is None:
            return '-'
        n = float(self.nilai)
        if n >= 85:
            return 'A'
        elif n >= 75:
            return 'B'
        elif n >= 65:
            return 'C'
        elif n >= 55:
            return 'D'
        return 'E'

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
    mata_kuliah   = models.ForeignKey('attendance.MataKuliah', on_delete=models.CASCADE, related_name='materi')
    judul         = models.CharField(max_length=200)
    deskripsi     = models.TextField(blank=True)
    file          = models.FileField(
        upload_to=materi_upload_path,
        blank=True, null=True,
        storage=_raw_storage
    )
    nama_file     = models.CharField(max_length=255, blank=True)
    ukuran        = models.PositiveBigIntegerField(default=0)
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


# ─── NOTIFIKASI ───────────────────────────────────────────────────────────────

class Notifikasi(models.Model):
    TIPE_CHOICES = [
        ('tugas_baru', 'Tugas Baru'),
        ('materi_baru', 'Materi Baru'),
        ('deadline', 'Deadline Mendekat'),
        ('pengumuman', 'Pengumuman Baru'),
        ('absensi', 'Absensi'),
        ('izin', 'Izin Absen'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifikasi')
    tipe        = models.CharField(max_length=20, choices=TIPE_CHOICES)
    judul       = models.CharField(max_length=200)
    pesan       = models.TextField(blank=True)
    url         = models.CharField(max_length=300, blank=True)
    dibaca      = models.BooleanField(default=False)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dibuat_pada']

    def __str__(self):
        return f"{self.user.username} - {self.tipe}: {self.judul}"

    @property
    def icon(self):
        return {
            'tugas_baru': '📝',
            'materi_baru': '📚',
            'deadline': '⏰',
            'pengumuman': '🔔',
            'absensi': '📋',
            'izin': '📩',
        }.get(self.tipe, '🔔')

    @property
    def waktu_relatif(self):
        delta = timezone.now() - self.dibuat_pada
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return "baru saja"
        elif total_seconds < 3600:
            return f"{total_seconds // 60} menit lalu"
        elif delta.days == 0:
            return f"{total_seconds // 3600} jam lalu"
        elif delta.days == 1:
            return "kemarin"
        else:
            return f"{delta.days} hari lalu"