"""
Management command: kirim_reminder_deadline
Kirim notifikasi ke mahasiswa yang belum submit tugas yang deadline-nya
dalam N jam ke depan.

Cara pakai:
    python manage.py kirim_reminder_deadline            # default 24 jam
    python manage.py kirim_reminder_deadline --jam 48   # 48 jam ke depan

Cara jadwalkan di Railway (cron job / worker):
    Tambahkan di Procfile:
        clock: python manage.py kirim_reminder_deadline --jam 24
    Atau gunakan Railway Cron di dashboard → setiap hari jam 07:00 WIB.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Kirim notifikasi reminder deadline tugas ke mahasiswa yang belum submit.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--jam', type=int, default=24,
            help='Kirim reminder untuk tugas yang deadline-nya dalam N jam (default: 24).'
        )

    def handle(self, *args, **options):
        jam = options['jam']
        now = timezone.now()
        batas = now + timezone.timedelta(hours=jam)

        from tasks.models import Tugas, TugasSubmission, Notifikasi
        from accounts.models import UserProfile

        # Tugas yang deadline-nya dalam rentang [sekarang, +N jam]
        tugas_dekat = Tugas.objects.filter(
            deadline__gt=now,
            deadline__lte=batas,
        ).select_related('mata_kuliah')

        if not tugas_dekat.exists():
            self.stdout.write(self.style.SUCCESS(f'Tidak ada tugas deadline dalam {jam} jam ke depan.'))
            return

        # Mahasiswa approved
        mahasiswa_ids = list(
            UserProfile.objects.filter(status='approved').values_list('user_id', flat=True)
        )

        notif_baru = 0
        for tugas in tugas_dekat:
            # Yang sudah submit — skip mereka
            sudah_submit_ids = set(
                TugasSubmission.objects.filter(tugas=tugas)
                .values_list('user_id', flat=True)
            )

            belum_submit_ids = [uid for uid in mahasiswa_ids if uid not in sudah_submit_ids]
            if not belum_submit_ids:
                continue

            sisa = tugas.sisa_waktu or 'segera'
            judul_notif = f'⏰ Deadline {tugas.judul}'
            pesan_notif = f'{tugas.mata_kuliah.nama} — sisa waktu {sisa}'

            # Buat notif hanya untuk yang belum ada notif reminder untuk tugas ini hari ini
            for uid in belum_submit_ids:
                sudah_ada = Notifikasi.objects.filter(
                    user_id=uid,
                    tipe='deadline',
                    judul=judul_notif,
                    dibuat_pada__date=now.date(),
                ).exists()
                if not sudah_ada:
                    Notifikasi.objects.create(
                        user_id=uid,
                        tipe='deadline',
                        judul=judul_notif,
                        pesan=pesan_notif,
                        url=f'/tugas/{tugas.pk}/',
                    )
                    notif_baru += 1

        self.stdout.write(self.style.SUCCESS(
            f'Berhasil kirim {notif_baru} reminder untuk {tugas_dekat.count()} tugas '
            f'(deadline dalam {jam} jam).'
        ))
