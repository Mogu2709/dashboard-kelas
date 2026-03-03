from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, timedelta, datetime

from attendance.models import MataKuliah
from .models import JadwalStatis, JadwalDinamis, HARI_CHOICES, MODE_CHOICES


HARI_ORDER = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu']


def get_semester_aktif():
    """Tebak semester aktif berdasarkan bulan."""
    bulan = date.today().month
    return 1 if bulan in [2, 3, 4, 5, 6, 7] else 2


@login_required
def jadwal_view(request):
    """Halaman utama jadwal — weekly calendar + list."""
    semester = int(request.GET.get('semester', get_semester_aktif()))
    tahun    = int(request.GET.get('tahun', date.today().year))

    # Semua jadwal statis semester ini
    jadwal_statis = JadwalStatis.objects.filter(
        semester=semester, aktif=True
    ).select_related('mata_kuliah')

    # Susun per hari untuk weekly view
    weekly = {hari: [] for hari in HARI_ORDER}
    for j in jadwal_statis:
        weekly[j.hari].append(j)

    # Perubahan 2 minggu ke depan
    hari_ini   = date.today()
    dua_minggu = hari_ini + timedelta(days=14)
    perubahan  = JadwalDinamis.objects.filter(
        tanggal_asli__gte=hari_ini,
        tanggal_asli__lte=dua_minggu,
        mata_kuliah__jadwal_statis__semester=semester,
    ).distinct().select_related('mata_kuliah', 'jadwal_statis').order_by('tanggal_asli')

    # Jadwal hari ini
    hari_ini_str = hari_ini.strftime('%A').lower()
    nama_hari_map = {
        'monday': 'senin', 'tuesday': 'selasa', 'wednesday': 'rabu',
        'thursday': 'kamis', 'friday': 'jumat', 'saturday': 'sabtu', 'sunday': 'minggu'
    }
    hari_ini_key = nama_hari_map.get(hari_ini_str, '')
    jadwal_hari_ini = [j for j in weekly.get(hari_ini_key, []) if j.semester == semester]

    # Override hari ini
    override_hari_ini = {
        o.jadwal_statis_id: o
        for o in JadwalDinamis.objects.filter(tanggal_asli=hari_ini)
        if o.jadwal_statis_id
    }

    semester_list = list(range(1, 9))

    hari_labels = dict(HARI_CHOICES)
    hari_ini_label = hari_labels.get(hari_ini_key, '')

    # Ambil semua override minggu ini (untuk weekly calendar)
    senin_ini = hari_ini - timedelta(days=hari_ini.weekday())
    minggu_ini = senin_ini + timedelta(days=6)
    overrides_minggu = JadwalDinamis.objects.filter(
        tanggal_asli__gte=senin_ini,
        tanggal_asli__lte=minggu_ini,
        jadwal_statis__semester=semester,
    ).select_related('mata_kuliah', 'jadwal_statis')

    # Map: jadwal_statis_id -> override
    override_map = {o.jadwal_statis_id: o for o in overrides_minggu if o.jadwal_statis_id}

    # Build weekly_display dengan info override
    weekly_display = []
    reschedule_tambahan = {h: [] for h in HARI_ORDER}  # slot pindahan

    for h in HARI_ORDER:
        slots = []
        for j in weekly[h]:
            ov = override_map.get(j.pk)
            slots.append({'jadwal': j, 'override': ov})
            # Jika reschedule ke hari lain minggu ini, tambahkan ke hari baru
            if ov and ov.tipe == 'reschedule' and ov.tanggal_baru:
                hari_baru_str = ov.tanggal_baru.strftime('%A').lower()
                nama_hari_map2 = {
                    'monday': 'senin', 'tuesday': 'selasa', 'wednesday': 'rabu',
                    'thursday': 'kamis', 'friday': 'jumat', 'saturday': 'sabtu'
                }
                hari_baru_key = nama_hari_map2.get(hari_baru_str, '')
                if hari_baru_key and hari_baru_key != h and hari_baru_key in reschedule_tambahan:
                    reschedule_tambahan[hari_baru_key].append({'jadwal': j, 'override': ov, 'is_pindahan': True})
        weekly_display.append((h, hari_labels[h], slots))

    # Gabungkan slot pindahan ke hari baru
    weekly_display = [
        (h, label, slots + reschedule_tambahan[h])
        for h, label, slots in weekly_display
    ]

    context = {
        'weekly_display':   weekly_display,
        'perubahan':        perubahan,
        'jadwal_hari_ini':  jadwal_hari_ini,
        'hari_ini_label':   hari_ini_label,
        'override_hari_ini': override_hari_ini,
        'semester':         semester,
        'tahun':            tahun,
        'semester_list':    semester_list,
        'hari_ini':         hari_ini,
        'hari_ini_key':     hari_ini_key,
        'is_ketua':         request.user.is_superuser,
    }
    return render(request, 'jadwal.html', context)


@login_required
def jadwal_statis_tambah(request):
    """Form tambah jadwal statis (ketua only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Hanya ketua kelas yang bisa mengelola jadwal.')
        return redirect('jadwal')

    matkul_list = MataKuliah.objects.all().order_by('semester', 'nama')

    if request.method == 'POST':
        try:
            jadwal = JadwalStatis(
                mata_kuliah_id = request.POST['mata_kuliah'],
                semester       = request.POST['semester'],
                hari           = request.POST['hari'],
                jam_mulai      = request.POST['jam_mulai'],
                jam_selesai    = request.POST['jam_selesai'],
                ruang          = request.POST.get('ruang', ''),
                dosen          = request.POST.get('dosen', ''),
                mode           = request.POST.get('mode', 'offline'),
                link_online    = request.POST.get('link_online', ''),
                dibuat_oleh    = request.user,
            )
            jadwal.save()
            messages.success(request, f'Jadwal {jadwal.mata_kuliah.nama} berhasil ditambahkan!')
            return redirect('jadwal')
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    context = {
        'matkul_list':  matkul_list,
        'hari_choices': HARI_CHOICES,
        'mode_choices': MODE_CHOICES,
        'semester_aktif': get_semester_aktif(),
        'action': 'Tambah',
    }
    return render(request, 'jadwal_statis_form.html', context)


@login_required
def jadwal_statis_edit(request, pk):
    """Form edit jadwal statis (ketua only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Hanya ketua kelas yang bisa mengelola jadwal.')
        return redirect('jadwal')

    jadwal      = get_object_or_404(JadwalStatis, pk=pk)
    matkul_list = MataKuliah.objects.all().order_by('semester', 'nama')

    if request.method == 'POST':
        try:
            jadwal.mata_kuliah_id = request.POST['mata_kuliah']
            jadwal.semester       = request.POST['semester']
            jadwal.hari           = request.POST['hari']
            jadwal.jam_mulai      = request.POST['jam_mulai']
            jadwal.jam_selesai    = request.POST['jam_selesai']
            jadwal.ruang          = request.POST.get('ruang', '')
            jadwal.dosen          = request.POST.get('dosen', '')
            jadwal.mode           = request.POST.get('mode', 'offline')
            jadwal.link_online    = request.POST.get('link_online', '')
            jadwal.aktif          = 'aktif' in request.POST
            jadwal.save()
            messages.success(request, 'Jadwal berhasil diperbarui!')
            return redirect('jadwal')
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    context = {
        'jadwal':       jadwal,
        'matkul_list':  matkul_list,
        'hari_choices': HARI_CHOICES,
        'mode_choices': MODE_CHOICES,
        'action': 'Edit',
    }
    return render(request, 'jadwal_statis_form.html', context)


@login_required
def jadwal_statis_hapus(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'Akses ditolak.')
        return redirect('jadwal')
    jadwal = get_object_or_404(JadwalStatis, pk=pk)
    if request.method == 'POST':
        nama = jadwal.mata_kuliah.nama
        jadwal.delete()
        messages.success(request, f'Jadwal {nama} dihapus.')
    return redirect('jadwal')


@login_required
def jadwal_dinamis_tambah(request):
    """Form tambah perubahan jadwal (ketua only)."""
    if not request.user.is_superuser:
        messages.error(request, 'Hanya ketua kelas yang bisa mengelola jadwal.')
        return redirect('jadwal')

    jadwal_statis_list = JadwalStatis.objects.filter(aktif=True).select_related('mata_kuliah').order_by('mata_kuliah__nama', 'hari', 'jam_mulai')

    if not jadwal_statis_list.exists():
        messages.warning(request, 'Belum ada jadwal statis. Buat jadwal dulu sebelum mencatat perubahan.')
        return redirect('jadwal_statis_tambah')

    if request.method == 'POST':
        try:
            jadwal_statis_id = request.POST.get('jadwal_statis')
            jadwal_obj = get_object_or_404(JadwalStatis, pk=jadwal_statis_id)
            perubahan = JadwalDinamis(
                jadwal_statis_id  = jadwal_statis_id,
                mata_kuliah       = jadwal_obj.mata_kuliah,
                tanggal_asli      = request.POST['tanggal_asli'],
                tipe              = request.POST['tipe'],
                tanggal_baru      = request.POST.get('tanggal_baru') or None,
                jam_mulai_baru    = request.POST.get('jam_mulai_baru') or None,
                jam_selesai_baru  = request.POST.get('jam_selesai_baru') or None,
                ruang_baru        = request.POST.get('ruang_baru', ''),
                mode_baru         = request.POST.get('mode_baru', ''),
                link_online       = request.POST.get('link_online', ''),
                catatan           = request.POST.get('catatan', ''),
                dibuat_oleh       = request.user,
            )
            perubahan.save()

            # Kirim notifikasi ke semua mahasiswa
            from tasks.views import _kirim_notif_semua
            tipe_label = dict(JadwalDinamis.TIPE_CHOICES).get(perubahan.tipe, 'Perubahan')
            matkul_nama = jadwal_obj.mata_kuliah.nama
            tanggal_str = perubahan.tanggal_asli.strftime('%d %b')

            if perubahan.tipe == 'cancel':
                judul = f"Kelas {matkul_nama} Dibatalkan"
                pesan = f"Pertemuan {tanggal_str} dibatalkan"
                if perubahan.catatan:
                    pesan += f" — {perubahan.catatan}"
            elif perubahan.tipe == 'reschedule':
                judul = f"Jadwal {matkul_nama} Dipindah"
                pesan = f"Dari {tanggal_str}"
                if perubahan.tanggal_baru:
                    pesan += f" → {perubahan.tanggal_baru.strftime('%d %b')}"
                if perubahan.jam_mulai_baru:
                    pesan += f" {perubahan.jam_mulai_baru.strftime('%H:%M')}"
            elif perubahan.tipe == 'mode':
                judul = f"Kelas {matkul_nama} Ganti Mode"
                pesan = f"{tanggal_str} → {perubahan.mode_baru.title()}"
                if perubahan.link_online:
                    pesan += f" | {perubahan.link_online}"
            else:
                judul = f"Info Jadwal {matkul_nama}"
                pesan = perubahan.catatan or tanggal_str

            _kirim_notif_semua(
                tipe='jadwal',
                judul=judul,
                pesan=pesan,
                url='/jadwal/',
                exclude_user=request.user,
            )

            messages.success(request, 'Perubahan jadwal berhasil disimpan & notifikasi terkirim!')
            return redirect('jadwal')
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    # Hitung tanggal berikutnya per jadwal
    hari_to_weekday = {'senin':0,'selasa':1,'rabu':2,'kamis':3,'jumat':4,'sabtu':5}
    today = date.today()
    jadwal_dengan_tanggal = []
    for j in jadwal_statis_list:
        target_wd = hari_to_weekday.get(j.hari, 0)
        days_ahead = (target_wd - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 0
        next_date = today + timedelta(days=days_ahead)
        jadwal_dengan_tanggal.append({
            'jadwal': j,
            'next_date': next_date.isoformat(),
            'jam_mulai': j.jam_mulai.strftime('%H:%M'),
            'jam_selesai': j.jam_selesai.strftime('%H:%M'),
            'ruang': j.ruang,
            'mode': j.mode,
        })

    context = {
        'jadwal_list':   jadwal_dengan_tanggal,
        'mode_choices':  MODE_CHOICES,
        'tipe_choices':  JadwalDinamis.TIPE_CHOICES,
    }
    return render(request, 'jadwal_dinamis_form.html', context)


@login_required
def jadwal_dinamis_hapus(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'Akses ditolak.')
        return redirect('jadwal')
    perubahan = get_object_or_404(JadwalDinamis, pk=pk)
    if request.method == 'POST':
        perubahan.delete()
        messages.success(request, 'Perubahan jadwal dihapus.')
    return redirect('jadwal')


@login_required
def jadwal_api(request):
    """JSON endpoint untuk kalender — returns jadwal minggu ini."""
    semester = int(request.GET.get('semester', get_semester_aktif()))
    jadwal   = JadwalStatis.objects.filter(semester=semester, aktif=True).select_related('mata_kuliah')

    data = []
    for j in jadwal:
        data.append({
            'id':          j.pk,
            'matkul':      j.mata_kuliah.nama,
            'hari':        j.hari,
            'jam_mulai':   j.jam_mulai.strftime('%H:%M'),
            'jam_selesai': j.jam_selesai.strftime('%H:%M'),
            'ruang':       j.ruang,
            'dosen':       j.dosen,
            'mode':        j.mode,
            'link_online': j.link_online,
        })
    return JsonResponse({'jadwal': data})
