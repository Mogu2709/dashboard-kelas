from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import os


class MataKuliah(models.Model):
    nama = models.CharField(max_length=100)
    semester = models.IntegerField()

    def __str__(self):
        return f"{self.nama} (Semester {self.semester})"


class Pertemuan(models.Model):
    mata_kuliah = models.ForeignKey(MataKuliah, on_delete=models.CASCADE)
    judul = models.CharField(max_length=100)
    tanggal = models.DateField()
    dibuat_oleh = models.ForeignKey(User, on_delete=models.CASCADE)
    waktu_mulai = models.DateTimeField(default=timezone.now)
    batas_absen = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.batas_absen:
            self.batas_absen = self.waktu_mulai + timedelta(hours=2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mata_kuliah.nama} - {self.judul}"


class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    pertemuan = models.ForeignKey(Pertemuan, on_delete=models.CASCADE)
    waktu_hadir = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'pertemuan')

    def __str__(self):
        return f"{self.user.username} - {self.pertemuan.judul}"


# ─── PENGUMUMAN ───────────────────────────────────────────────────────────────

class Pengumuman(models.Model):
    PRIORITAS_CHOICES = [
        ('normal', 'Normal'),
        ('penting', 'Penting'),
        ('urgent', 'Urgent'),
    ]

    judul          = models.CharField(max_length=200)
    isi            = models.TextField()
    dibuat_oleh    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pengumuman_dibuat')
    dibuat_pada    = models.DateTimeField(auto_now_add=True)
    diedit_pada    = models.DateTimeField(null=True, blank=True)
    prioritas      = models.CharField(max_length=10, choices=PRIORITAS_CHOICES, default='normal')
    pinned         = models.BooleanField(default=False)
    embed_url      = models.URLField(blank=True, null=True, help_text='Link YouTube atau URL lainnya')

    class Meta:
        ordering = ['-pinned', '-dibuat_pada']

    def __str__(self):
        return self.judul

    @property
    def is_edited(self):
        return self.diedit_pada is not None

    @property
    def youtube_embed_url(self):
        """Convert YouTube watch URL to embed URL."""
        if not self.embed_url:
            return None
        url = self.embed_url
        # Handle youtu.be short links
        if 'youtu.be/' in url:
            vid = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{vid}?origin=https://web-production-1d4d8.up.railway.app'
        # Handle youtube.com/watch?v=
        if 'youtube.com/watch' in url:
            import urllib.parse
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            vid = params.get('v', [None])[0]
            if vid:
                return f'https://www.youtube.com/embed/{vid}?origin=https://web-production-1d4d8.up.railway.app'
        # Handle youtube.com/embed/ already
        if 'youtube.com/embed/' in url:
            return url
        return None

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def comment_count(self):
        return self.komentar.filter(parent=None).count()


def pengumuman_upload_path(instance, filename):
    ext = filename.split('.')[-1].lower()
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        folder = 'foto'
    elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
        folder = 'video'
    else:
        folder = 'files'
    return f'pengumuman/{instance.pengumuman.id}/{folder}/{filename}'


class PengumumanAttachment(models.Model):
    TIPE_CHOICES = [
        ('foto',  'Foto'),
        ('video', 'Video'),
        ('file',  'File'),
    ]
    pengumuman = models.ForeignKey(Pengumuman, on_delete=models.CASCADE, related_name='attachments')
    file       = models.FileField(upload_to=pengumuman_upload_path)
    tipe       = models.CharField(max_length=10, choices=TIPE_CHOICES)
    nama_asli  = models.CharField(max_length=255, blank=True)
    ukuran     = models.PositiveBigIntegerField(default=0, help_text='Ukuran file dalam bytes')
    diunggah_pada = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.file and not self.nama_asli:
            self.nama_asli = os.path.basename(self.file.name)
        if self.file and not self.ukuran:
            try:
                self.ukuran = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def ukuran_display(self):
        if self.ukuran < 1024:
            return f'{self.ukuran} B'
        elif self.ukuran < 1024 * 1024:
            return f'{self.ukuran / 1024:.1f} KB'
        else:
            return f'{self.ukuran / (1024*1024):.1f} MB'

    def __str__(self):
        return f'{self.tipe}: {self.nama_asli}'


class PengumumanDibaca(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    pengumuman = models.ForeignKey(Pengumuman, on_delete=models.CASCADE, related_name='dibaca_oleh')
    dibaca_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'pengumuman')


class PengumumanLike(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    pengumuman = models.ForeignKey(Pengumuman, on_delete=models.CASCADE, related_name='likes')
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'pengumuman')


class Komentar(models.Model):
    pengumuman = models.ForeignKey(Pengumuman, on_delete=models.CASCADE, related_name='komentar')
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    parent     = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    isi        = models.TextField()
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diedit_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['dibuat_pada']

    def __str__(self):
        return f'{self.user.username}: {self.isi[:40]}'

    @property
    def is_edited(self):
        return self.diedit_pada is not None
