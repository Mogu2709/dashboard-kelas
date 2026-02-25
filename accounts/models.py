from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu Persetujuan'),
        ('approved', 'Disetujui'),
        ('rejected', 'Ditolak'),
    ]

    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]

    # ── Approval ──────────────────────────────────────────────────────────────
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    dibuat_pada   = models.DateTimeField(auto_now_add=True)
    diproses_pada = models.DateTimeField(null=True, blank=True)
    diproses_oleh = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approvals'
    )

    # ── Data Mahasiswa ─────────────────────────────────────────────────────────
    nama_lengkap  = models.CharField(max_length=150, blank=True)
    nim           = models.CharField(max_length=20, blank=True, verbose_name='NIM')
    jurusan       = models.CharField(max_length=100, blank=True)
    angkatan      = models.PositiveIntegerField(null=True, blank=True)
    jenis_kelamin = models.CharField(
        max_length=1, choices=JENIS_KELAMIN_CHOICES, blank=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.status}"

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def display_name(self):
        """Nama lengkap kalau ada, fallback ke username."""
        return self.nama_lengkap or self.user.username

    @property
    def inisial(self):
        """Untuk avatar: ambil inisial dari nama lengkap atau username."""
        name = self.nama_lengkap or self.user.username
        parts = name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return name[0].upper()