import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django import forms

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

    return render(request, 'pertemuan_list.html', {
        'pertemuan_list': pertemuan,
        'mata_kuliah_list': mata_kuliah_list,
        'semester_list': semester_list,
        'hadir_ids': hadir_ids,
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
    class Meta:
        model = Pertemuan
        fields = ['mata_kuliah', 'judul', 'tanggal']


@login_required
@user_passes_test(admin_check, login_url='/login/')
def buat_pertemuan(request):
    if request.method == 'POST':
        form = PertemuanForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.dibuat_oleh = request.user
            p.save()
            return redirect('pertemuan_list')
    else:
        form = PertemuanForm()
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
    # FIX: Hanya mahasiswa yang sudah approved
    mahasiswa = User.objects.filter(is_superuser=False, profile__status='approved').annotate(
        total_hadir=Count(
            'attendance',
            filter=Q(attendance__pertemuan_id__in=pertemuan_ids)
        )
    ).order_by('username')

    data_rekap = []
    for mhs in mahasiswa:
        persen = (
            round((mhs.total_hadir / total_pertemuan) * 100, 1)
            if total_pertemuan > 0 else 0
        )
        data_rekap.append({
            'user_id': mhs.id,
            'username': mhs.username,
            'nama_lengkap': mhs.get_full_name() or mhs.username,
            'total_hadir': mhs.total_hadir,
            'persentase': persen,
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
    hadir_aman   = sum(1 for m in data_rekap if m['persentase'] >= 75)
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