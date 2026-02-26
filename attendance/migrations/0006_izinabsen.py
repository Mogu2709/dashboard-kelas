from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import attendance.models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_pertemuan_kode_absen'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IzinAbsen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jenis', models.CharField(choices=[('izin', 'Izin'), ('sakit', 'Sakit'), ('alpha', 'Alpha')], max_length=10)),
                ('keterangan', models.TextField(blank=True)),
                ('bukti', models.FileField(blank=True, null=True, upload_to=attendance.models.izin_upload_path)),
                ('status', models.CharField(choices=[('pending', 'Menunggu'), ('approved', 'Disetujui'), ('rejected', 'Ditolak')], default='pending', max_length=10)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diproses_pada', models.DateTimeField(blank=True, null=True)),
                ('catatan_admin', models.TextField(blank=True)),
                ('diproses_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='izin_diproses', to=settings.AUTH_USER_MODEL)),
                ('pertemuan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='izin_absen', to='attendance.pertemuan')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='izin_absen', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-dibuat_pada'],
                'unique_together': {('user', 'pertemuan')},
            },
        ),
    ]
