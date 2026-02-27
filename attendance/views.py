import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django import forms
from django.contrib import messages
from .models import (
    Pertemuan, Attendance, MataKuliah,
    Pengumuman, PengumumanAttachment, PengumumanDibaca,
    PengumumanLike, Komentar
)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def admin_check(user):
    return user.is_superuser


def get_attachment_tipe(file):
    name = file.name.lower()
    if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return 'foto'
    elif name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        return 'video'
    return 'file'


# ─── ABSENSI VIEWS ────────────────────────────────────────────────────────────

@login_required
def detail_pertemuan(request, pk):
    if not request.user.is_superuser:
        return redirect('pertemuan_list')
    pertemuan = get_object_or_404(Pertemuan, pk=pk)
    daftar_hadir = Attendance.objects.filter(pertemuan=pertemuan).select_related('user')
    return render(request, 'detail_pertemuan.html', {
        'pertemuan': pertemuan,
        'daftar_hadir': daftar_hadir,
    })


@login_required
def pertemuan_list(request):
    mata_kuliah_id = request.GET.get('mata_kuliah')
    semester = request.GET.get('semester')
    pertemuan = Pertemuan.objects.all().order_by('-tanggal')
    mata_kuliah_list = MataKuliah.objects.all().order_by('semester', 'nama')
    semester_list = MataKuliah.objects.values_list(
        'semester', flat=True).distinct().order_by('semester')

    if mata_kuliah_id:
        pertemuan = pertemuan.filter(mata_kuliah_id=mata_kuliah_id)
    if semester:
        pertemuan = pertemuan.filter(mata_kuliah__semester=semester)

    pertemuan = pertemuan.annotate(jumlah_hadir=Count('attendance'))
    hadir_ids = Attendance.objects.filter(
        user=request.user).values_list('pertemuan_id', flat=True)

    # Data izin untuk mahasiswa
    izin_ids = set()          # semua pertemuan yang punya record izin
    izin_rejected_ids = set() # hanya rejected → boleh ajukan ulang
    izin_status_map = {}
    izin_label_map = {}
    if not request.user.is_superuser:
        from .models import IzinAbsen
        STATUS_LABEL = {'pending': '⏳ Menunggu', 'approved': '✓ Izin Disetujui', 'rejected': '✗ Ditolak'}
        STATUS_CHIP  = {'pending': 'yellow', 'approved': 'green', 'rejected': 'red'}
        for izin in IzinAbsen.objects.filter(user=request.user).values('pertemuan_id', 'status'):
            pid = izin['pertemuan_id']
            izin_ids.add(pid)
            if izin['status'] == 'rejected':
                izin_rejected_ids.add(pid)
            izin_status_map[pid] = STATUS_CHIP.get(izin['status'], 'gray')
            izin_label_map[pid]  = STATUS_LABEL.get(izin['status'], izin['status'])

    # Admin: pending izin count untuk alert
    pending_izin = 0
    if request.user.is_superuser:
        from .models import IzinAbsen
        pending_izin = IzinAbsen.objects.filter(status='pending').count()

    return render(request, 'pertemuan_list.html', {
        'pertemuan_list': pertemuan,
        'mata_kuliah_list': mata_kuliah_list,
        'semester_list': semester_list,
        'hadir_ids': hadir_ids,
        'izin_ids': izin_ids,
        'izin_rejected_ids': izin_rejected_ids,
        'izin_status_map': izin_status_map,
        'izin_label_map': izin_label_map,
        'pending_izin': pending_izin,
        'now': timezone.now(),
    })


@login_required
def hadir(request, pertemuan_id):
    """
    Diganti: absensi sekarang wajib lewat input kode.
    Redirect ke halaman input kode, bukan langsung absen.
    """
    return redirect('absen_kode', pertemuan_id=pertemuan_id)


@login_required
def absen_kode(request, pertemuan_id):
    """
    Halaman input kode absen untuk mahasiswa.
    GET  → tampilkan form input kode
    POST → validasi kode lalu absen
    """
    pertemuan = get_object_or_404(Pertemuan, id=pertemuan_id)

    # Sudah hadir? Langsung redirect
    if Attendance.objects.filter(user=request.user, pertemuan=pertemuan).exists():
        return redirect('pertemuan_list')

    # Waktu sudah habis
    if not pertemuan.kode_aktif:
        return render(request, 'absen_kode.html', {
            'pertemuan': pertemuan,
            'error': 'expired',
        })

    error = None
    if request.method == 'POST':
        kode_input = request.POST.get('kode', '').strip().upper()

        if not kode_input:
            error = 'empty'
        elif kode_input != pertemuan.kode_absen:
            error = 'salah'
        else:
            # Kode benar — catat kehadiran
            Attendance.objects.get_or_create(user=request.user, pertemuan=pertemuan)
            return render(request, 'absen_kode.html', {
                'pertemuan': pertemuan,
                'sukses': True,
            })

    return render(request, 'absen_kode.html', {
        'pertemuan': pertemuan,
        'error': error,
    })


class PertemuanForm(forms.ModelForm):
    # FIX BUG 3: Tambah waktu_mulai & batas_absen agar bisa diatur dari form.
    # Sebelumnya hanya 3 field → waktu_mulai auto-set ke saat form dibuat,
    # bukan saat pertemuan sebenarnya.
    waktu_mulai = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        label='Waktu Mulai',
        required=True,
    )
    batas_absen = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        label='Batas Absen',
        required=False,
        help_text='Kosongkan untuk otomatis 2 jam setelah waktu mulai.',
    )

    class Meta:
        model = Pertemuan
        fields = ['mata_kuliah', 'judul', 'tanggal', 'waktu_mulai', 'batas_absen']


@login_required
@user_passes_test(admin_check, login_url='/login/')
def buat_pertemuan(request):
    if request.method == 'POST':
        form = PertemuanForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.dibuat_oleh = request.user
            # Pastikan aware timezone (Railway/prod pakai UTC → convert ke WIB)
            from django.utils import timezone as tz
            waktu_mulai = form.cleaned_data['waktu_mulai']
            batas_absen = form.cleaned_data.get('batas_absen')
            if waktu_mulai and tz.is_naive(waktu_mulai):
                waktu_mulai = tz.make_aware(waktu_mulai)
            p.waktu_mulai = waktu_mulai
            if batas_absen:
                if tz.is_naive(batas_absen):
                    batas_absen = tz.make_aware(batas_absen)
                p.batas_absen = batas_absen
            else:
                # Auto: 2 jam setelah waktu_mulai (model.save() juga handle ini,
                # tapi kita set eksplisit agar tidak overwrite)
                from datetime import timedelta
                p.batas_absen = waktu_mulai + timedelta(hours=2)
            p.save()
            return redirect('pertemuan_list')
    else:
        # Default waktu_mulai = sekarang (format datetime-local)
        from django.utils import timezone as tz
        now_local = tz.localtime(tz.now()).strftime('%Y-%m-%dT%H:%M')
        form = PertemuanForm(initial={'waktu_mulai': now_local})
    return render(request, 'buat_pertemuan.html', {
        'form': form,
        'mata_kuliah_list': MataKuliah.objects.all().order_by('semester', 'nama'),
    })


@login_required
def rekap_mahasiswa(request):
    """
    FITUR BARU: Filter rekap per mata kuliah.
    FIX: Persentase sekarang dihitung per MK yang difilter, bukan total semua pertemuan.
    """
    if not request.user.is_superuser:
        return redirect('pertemuan_list')

    mk_filter = request.GET.get('mk')
    mata_kuliah_list = MataKuliah.objects.all().order_by('semester', 'nama')

    # Query pertemuan sesuai filter
    pertemuan_qs = Pertemuan.objects.all()
    if mk_filter:
        pertemuan_qs = pertemuan_qs.filter(mata_kuliah_id=mk_filter)

    total_pertemuan = pertemuan_qs.count()
    pertemuan_ids = list(pertemuan_qs.values_list('id', flat=True))

    # FIX: Hanya hitung kehadiran di pertemuan yang terfilter
    from .models import IzinAbsen
    mahasiswa = User.objects.filter(is_superuser=False, profile__status='approved').annotate(
        total_hadir=Count(
            'attendance',
            filter=Q(attendance__pertemuan_id__in=pertemuan_ids)
        )
    ).order_by('username')

    # Izin per user (approved) — satu query
    izin_map = {}  # {user_id: {'izin': N, 'sakit': N, 'alpha': N}}
    if pertemuan_ids:
        for row in (
            IzinAbsen.objects
            .filter(pertemuan_id__in=pertemuan_ids, status='approved')
            .values('user_id', 'jenis')
            .annotate(jumlah=Count('id'))
        ):
            uid = row['user_id']
            if uid not in izin_map:
                izin_map[uid] = {'izin': 0, 'sakit': 0, 'alpha': 0}
            izin_map[uid][row['jenis']] = row['jumlah']

    data_rekap = []
    for mhs in mahasiswa:
        izin_data  = izin_map.get(mhs.id, {'izin': 0, 'sakit': 0, 'alpha': 0})
        tot_hadir  = mhs.total_hadir
        tot_izin   = izin_data['izin']
        tot_sakit  = izin_data['sakit']
        tot_alpha  = izin_data['alpha']
        # Efektif hadir = hadir + izin + sakit (alpha tidak dihitung)
        efektif    = tot_hadir + tot_izin + tot_sakit
        persen     = round((efektif / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
        persen_murni = round((tot_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
        data_rekap.append({
            'user_id': mhs.id,
            'username': mhs.username,
            'nama_lengkap': mhs.get_full_name() or mhs.username,
            'total_hadir': tot_hadir,
            'total_izin':  tot_izin,
            'total_sakit': tot_sakit,
            'total_alpha': tot_alpha,
            'persentase':  persen,
            'persentase_murni': persen_murni,
        })

    # ── Data nilai per mahasiswa ──────────────────────────────────────────────
    try:
        from tasks.models import TugasSubmission, Tugas
        from django.db.models import Avg, Count as DCount

        # Ambil tugas sesuai filter MK
        tugas_qs = Tugas.objects.all()
        if mk_filter:
            tugas_qs = tugas_qs.filter(mata_kuliah_id=mk_filter)
        tugas_ids = list(tugas_qs.values_list('id', flat=True))
        total_tugas = len(tugas_ids)

        # Map user_id → stats nilai
        nilai_map = {}
        if tugas_ids:
            subs = (
                TugasSubmission.objects
                .filter(tugas_id__in=tugas_ids)
                .values('user_id')
                .annotate(
                    rata_nilai=Avg('nilai'),
                    sudah_kumpul=DCount('id'),
                    sudah_dinilai=DCount('nilai'),
                )
            )
            for s in subs:
                nilai_map[s['user_id']] = s
    except Exception:
        total_tugas = 0
        nilai_map = {}

    # Gabungkan data kehadiran + nilai
    for item in data_rekap:
        uid = item.get('user_id')
        ndata = nilai_map.get(uid, {})
        rata = ndata.get('rata_nilai')
        item['rata_nilai']    = round(float(rata), 1) if rata is not None else None
        item['sudah_kumpul']  = ndata.get('sudah_kumpul', 0)
        item['sudah_dinilai'] = ndata.get('sudah_dinilai', 0)
        item['total_tugas']   = total_tugas

        # Grade huruf dari rata-rata
        if rata is None:
            item['grade'] = '-'
        else:
            n = float(rata)
            item['grade'] = 'A' if n >= 85 else 'B' if n >= 75 else 'C' if n >= 65 else 'D' if n >= 55 else 'E'

    # Sort descending persentase kehadiran
    data_rekap.sort(key=lambda x: x['persentase'], reverse=True)

    # Nama MK yang dipilih (untuk tampilan)
    mk_dipilih = None
    if mk_filter:
        try:
            mk_dipilih = MataKuliah.objects.get(pk=mk_filter)
        except MataKuliah.DoesNotExist:
            pass

    # Summary stats
    hadir_aman   = sum(1 for m in data_rekap if m['persentase'] >= 75)  # pakai persentase efektif
    ada_nilai    = [m for m in data_rekap if m['rata_nilai'] is not None]
    rata_kelas   = round(sum(m['rata_nilai'] for m in ada_nilai) / len(ada_nilai), 1) if ada_nilai else None

    return render(request, 'rekap_mahasiswa.html', {
        'data_rekap': data_rekap,
        'total_pertemuan': total_pertemuan,
        'total_tugas': total_tugas,
        'mata_kuliah_list': mata_kuliah_list,
        'mk_filter': mk_filter,
        'mk_dipilih': mk_dipilih,
        'hadir_aman': hadir_aman,
        'rata_kelas': rata_kelas,
    })


# ─── PENGUMUMAN VIEWS ─────────────────────────────────────────────────────────

@login_required
def pengumuman_list(request):
    """
    FITUR BARU: Pagination — 10 pengumuman per halaman.
    """
    semua = Pengumuman.objects.prefetch_related('attachments', 'likes', 'komentar').all()
    dibaca_ids = list(
        PengumumanDibaca.objects.filter(user=request.user).values_list('pengumuman_id', flat=True)
    )
    liked_ids = list(
        PengumumanLike.objects.filter(user=request.user).values_list('pengumuman_id', flat=True)
    )
    belum_dibaca = semua.exclude(id__in=dibaca_ids).count()

    # Pagination
    paginator = Paginator(semua, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'pengumuman_list.html', {
        'pengumuman_list': page_obj,      # sekarang page_obj, bukan semua
        'page_obj': page_obj,
        'dibaca_ids': dibaca_ids,
        'liked_ids': liked_ids,
        'belum_dibaca': belum_dibaca,
    })


@login_required
def tandai_dibaca(request, pk):
    pengumuman = get_object_or_404(Pengumuman, pk=pk)
    PengumumanDibaca.objects.get_or_create(user=request.user, pengumuman=pengumuman)
    return redirect('pengumuman_list')


@login_required
def tandai_semua_dibaca(request):
    # FIX: Ambil id yang belum dibaca lalu bulk create — lebih efisien
    dibaca_ids = PengumumanDibaca.objects.filter(
        user=request.user).values_list('pengumuman_id', flat=True)
    belum = Pengumuman.objects.exclude(id__in=dibaca_ids).values_list('id', flat=True)
    PengumumanDibaca.objects.bulk_create(
        [PengumumanDibaca(user=request.user, pengumuman_id=pid) for pid in belum],
        ignore_conflicts=True,
    )
    return redirect('pengumuman_list')


@login_required
@user_passes_test(admin_check, login_url='/login/')
def buat_pengumuman(request):
    if request.method == 'POST':
        judul     = request.POST.get('judul', '').strip()
        isi       = request.POST.get('isi', '').strip()
        prioritas = request.POST.get('prioritas', 'normal')
        pinned    = request.POST.get('pinned') == 'on'
        embed_url = request.POST.get('embed_url', '').strip() or None
        files     = request.FILES.getlist('attachments')

        if not judul or not isi:
            from django.contrib import messages as msg
            msg.error(request, '⚠️ Judul dan isi pengumuman tidak boleh kosong.')
            return render(request, 'buat_pengumuman.html')

        p = Pengumuman.objects.create(
            judul=judul, isi=isi, prioritas=prioritas,
            pinned=pinned, embed_url=embed_url,
            dibuat_oleh=request.user,
        )
        try:
            from tasks.views import _kirim_notif_semua
            _kirim_notif_semua(
                tipe='pengumuman',
                judul=f'Pengumuman: {judul}',
                pesan=isi[:100],
                url='/absensi/pengumuman/',
                exclude_user=request.user,
            )
        except Exception:
            pass

        for f in files:
            tipe = get_attachment_tipe(f)
            att = PengumumanAttachment(pengumuman=p, tipe=tipe, nama_asli=f.name)
            att.file = f
            att.ukuran = f.size
            att.save()

        return redirect('pengumuman_list')

    return render(request, 'buat_pengumuman.html')


@login_required
@user_passes_test(admin_check, login_url='/login/')
def edit_pengumuman(request, pk):
    pengumuman = get_object_or_404(Pengumuman, pk=pk)

    if request.method == 'POST':
        pengumuman.judul     = request.POST.get('judul', '').strip()
        pengumuman.isi       = request.POST.get('isi', '').strip()
        pengumuman.prioritas = request.POST.get('prioritas', 'normal')
        pengumuman.pinned    = request.POST.get('pinned') == 'on'
        pengumuman.embed_url = request.POST.get('embed_url', '').strip() or None
        pengumuman.diedit_pada = timezone.now()
        pengumuman.save()

        for f in request.FILES.getlist('attachments'):
            tipe = get_attachment_tipe(f)
            att = PengumumanAttachment(pengumuman=pengumuman, tipe=tipe, nama_asli=f.name)
            att.file = f
            att.ukuran = f.size
            att.save()

        hapus_ids = request.POST.getlist('hapus_attachment')
        if hapus_ids:
            PengumumanAttachment.objects.filter(
                id__in=hapus_ids, pengumuman=pengumuman).delete()

        return redirect('pengumuman_list')

    return render(request, 'edit_pengumuman.html', {'pengumuman': pengumuman})


@login_required
@user_passes_test(admin_check, login_url='/login/')
def hapus_pengumuman(request, pk):
    if request.method == 'POST':
        pengumuman = get_object_or_404(Pengumuman, pk=pk)
        pengumuman.delete()
    return redirect('pengumuman_list')


# ─── LIKE ─────────────────────────────────────────────────────────────────────

@login_required
def toggle_like(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    pengumuman = get_object_or_404(Pengumuman, pk=pk)
    like, created = PengumumanLike.objects.get_or_create(
        user=request.user, pengumuman=pengumuman)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    return JsonResponse({'liked': liked, 'count': pengumuman.like_count})


# ─── KOMENTAR ─────────────────────────────────────────────────────────────────

@login_required
def tambah_komentar(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    pengumuman = get_object_or_404(Pengumuman, pk=pk)
    isi = request.POST.get('isi', '').strip()
    parent_id = request.POST.get('parent_id')

    if not isi:
        return JsonResponse({'error': 'Komentar tidak boleh kosong'}, status=400)

    parent = None
    if parent_id:
        try:
            parent = Komentar.objects.get(id=parent_id, pengumuman=pengumuman)
        except Komentar.DoesNotExist:
            pass

    komentar = Komentar.objects.create(
        pengumuman=pengumuman, user=request.user,
        isi=isi, parent=parent,
    )

    return JsonResponse({
        'id': komentar.id,
        'user': komentar.user.username,
        'isi': komentar.isi,
        'dibuat_pada': komentar.dibuat_pada.strftime('%d %b %Y, %H:%M'),
        'parent_id': parent.id if parent else None,
        'is_superuser': komentar.user.is_superuser,
    })


@login_required
def edit_komentar(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    komentar = get_object_or_404(Komentar, pk=pk)
    if komentar.user != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Tidak diizinkan'}, status=403)

    isi = request.POST.get('isi', '').strip()
    if not isi:
        return JsonResponse({'error': 'Komentar tidak boleh kosong'}, status=400)

    komentar.isi = isi
    komentar.diedit_pada = timezone.now()
    komentar.save()

    return JsonResponse({
        'id': komentar.id,
        'isi': komentar.isi,
        'diedit_pada': komentar.diedit_pada.strftime('%d %b %Y, %H:%M'),
    })


@login_required
def hapus_komentar(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    komentar = get_object_or_404(Komentar, pk=pk)
    if komentar.user != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Tidak diizinkan'}, status=403)

    komentar.delete()
    return JsonResponse({'deleted': True})


# ─── NOTIF COUNT ──────────────────────────────────────────────────────────────

@login_required
def notif_count(request):
    dibaca_ids = PengumumanDibaca.objects.filter(
        user=request.user).values_list('pengumuman_id', flat=True)
    count = Pengumuman.objects.exclude(id__in=dibaca_ids).count()
    return JsonResponse({'count': count})

# ─── IZIN ABSEN ───────────────────────────────────────────────────────────────

@login_required
def ajukan_izin(request, pertemuan_id):
    """Mahasiswa mengajukan izin/sakit untuk pertemuan tertentu."""
    from .models import IzinAbsen
    pertemuan = get_object_or_404(Pertemuan, id=pertemuan_id)

    # Tidak bisa izin kalau sudah hadir
    if Attendance.objects.filter(user=request.user, pertemuan=pertemuan).exists():
        messages.error(request, 'Kamu sudah tercatat hadir di pertemuan ini.')
        return redirect('pertemuan_list')

    # Cek sudah pernah ajukan izin
    existing = IzinAbsen.objects.filter(user=request.user, pertemuan=pertemuan).first()

    if request.method == 'POST':
        jenis      = request.POST.get('jenis', 'izin')
        keterangan = request.POST.get('keterangan', '').strip()
        bukti      = request.FILES.get('bukti')

        if not keterangan:
            messages.error(request, '⚠️ Keterangan tidak boleh kosong.')
            return render(request, 'ajukan_izin.html', {
                'pertemuan': pertemuan, 'existing': existing
            })

        if existing:
            # Update pengajuan yang sudah ada (pending atau rejected boleh diajukan ulang)
            if existing.status == 'approved':
                messages.error(request, 'Pengajuan sudah disetujui, tidak bisa diubah.')
                return redirect('pertemuan_list')
            existing.jenis      = jenis
            existing.keterangan = keterangan
            if bukti:
                existing.bukti = bukti
            # Reset ke pending saat diajukan ulang setelah rejected
            existing.status = 'pending'
            existing.diproses_pada = None
            existing.diproses_oleh = None
            existing.catatan_admin = ''
            existing.save()
            messages.success(request, '✅ Pengajuan izin berhasil diperbarui. Menunggu persetujuan.')
        else:
            izin = IzinAbsen(
                user=request.user, pertemuan=pertemuan,
                jenis=jenis, keterangan=keterangan,
            )
            if bukti:
                izin.bukti = bukti
            izin.save()
            messages.success(request, '✅ Pengajuan izin berhasil dikirim. Menunggu persetujuan.')

        return redirect('pertemuan_list')

    from .models import IzinAbsen
    return render(request, 'ajukan_izin.html', {
        'pertemuan': pertemuan,
        'existing': existing,
        'jenis_choices': IzinAbsen.JENIS_CHOICES,
    })


@login_required
def daftar_izin(request):
    """Admin: lihat semua pengajuan izin."""
    if not request.user.is_superuser:
        return redirect('pertemuan_list')
    from .models import IzinAbsen

    status_filter = request.GET.get('status', 'pending')
    izin_qs = (
        IzinAbsen.objects
        .select_related('user', 'user__profile', 'pertemuan', 'pertemuan__mata_kuliah')
        .order_by('-dibuat_pada')
    )
    if status_filter and status_filter != 'semua':
        izin_qs = izin_qs.filter(status=status_filter)

    from django.core.paginator import Paginator
    paginator = Paginator(izin_qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    pending_count = IzinAbsen.objects.filter(status='pending').count()

    return render(request, 'daftar_izin.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'pending_count': pending_count,
    })


@login_required
def proses_izin(request, izin_id):
    """Admin: approve atau reject pengajuan izin."""
    if not request.user.is_superuser:
        return redirect('pertemuan_list')
    from .models import IzinAbsen

    izin   = get_object_or_404(IzinAbsen, id=izin_id)
    action = request.POST.get('action')  # 'approve' atau 'reject'

    if request.method == 'POST' and action in ('approve', 'reject'):
        izin.status        = 'approved' if action == 'approve' else 'rejected'
        izin.diproses_oleh = request.user
        izin.diproses_pada = timezone.now()
        izin.catatan_admin = request.POST.get('catatan_admin', '').strip()
        izin.save()

        # Kirim notif ke mahasiswa
        from tasks.models import Notifikasi
        status_label = 'disetujui ✓' if action == 'approve' else 'ditolak ✗'
        Notifikasi.objects.create(
            user=izin.user,
            tipe='pengumuman',
            judul=f'Izin {izin.get_jenis_display()} {status_label}',
            pesan=f'{izin.pertemuan.judul} · {izin.pertemuan.mata_kuliah.nama}',
            url='/absensi/',
        )
        messages.success(request, f'Izin {"disetujui" if action == "approve" else "ditolak"}.')

    return redirect(request.POST.get('next', 'daftar_izin'))


@login_required
def izin_saya(request):
    """Mahasiswa: lihat riwayat pengajuan izin sendiri."""
    from .models import IzinAbsen
    izin_list = (
        IzinAbsen.objects
        .filter(user=request.user)
        .select_related('pertemuan', 'pertemuan__mata_kuliah')
        .order_by('-dibuat_pada')
    )
    return render(request, 'izin_saya.html', {'izin_list': izin_list})