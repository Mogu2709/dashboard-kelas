from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu Persetujuan'),
        ('approved', 'Disetujui'),
        ('rejected', 'Ditolak'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diproses_pada = models.DateTimeField(null=True, blank=True)
    diproses_oleh = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approvals'
    )

    def __str__(self):
        return f"{self.user.username} - {self.status}"

    @property
    def is_approved(self):
        return self.status == 'approved'
