import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth.models import User
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
    daftar_hadir = Attendance.objects.filter(pertemuan=pertemuan)
    return render(request, 'detail_pertemuan.html', {
        'pertemuan': pertemuan, 'daftar_hadir': daftar_hadir,
    })


@login_required
def pertemuan_list(request):
    mata_kuliah_id = request.GET.get('mata_kuliah')
    pertemuan = Pertemuan.objects.all().order_by('-tanggal')
    mata_kuliah_list = MataKuliah.objects.all()
    if mata_kuliah_id:
        pertemuan = pertemuan.filter(mata_kuliah_id=mata_kuliah_id)
    pertemuan = pertemuan.annotate(jumlah_hadir=Count('attendance'))
    hadir_ids = Attendance.objects.filter(
        user=request.user).values_list('pertemuan_id', flat=True)
    return render(request, 'pertemuan_list.html', {
        'pertemuan_list': pertemuan, 'mata_kuliah_list': mata_kuliah_list,
        'hadir_ids': hadir_ids, 'now': timezone.now(),
    })


@login_required
def hadir(request, pertemuan_id):
    pertemuan = get_object_or_404(Pertemuan, id=pertemuan_id)
    if timezone.now() > pertemuan.batas_absen:
        return redirect('pertemuan_list')
    Attendance.objects.get_or_create(user=request.user, pertemuan=pertemuan)
    return redirect('pertemuan_list')


class PertemuanForm(forms.ModelForm):
    class Meta:
        model = Pertemuan
        fields = ['mata_kuliah', 'judul', 'tanggal']


# FIX: tambah @login_required + login_url agar tidak error redirect
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
    return render(request, 'buat_pertemuan.html', {'form': form})


@login_required
def rekap_mahasiswa(request):
    if not request.user.is_superuser:
        return redirect('pertemuan_list')
    total_pertemuan = Pertemuan.objects.count()
    mahasiswa = User.objects.filter(is_superuser=False).annotate(
        total_hadir=Count('attendance'))
    data_rekap = []
    for mhs in mahasiswa:
        persen = round((mhs.total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
        data_rekap.append({
            'username': mhs.username, 'total_hadir': mhs.total_hadir, 'persentase': persen,
        })
    return render(request, 'rekap_mahasiswa.html', {
        'data_rekap': data_rekap, 'total_pertemuan': total_pertemuan,
    })


# ─── PENGUMUMAN VIEWS ─────────────────────────────────────────────────────────

@login_required
def pengumuman_list(request):
    semua = Pengumuman.objects.prefetch_related('attachments', 'likes', 'komentar').all()
    dibaca_ids = PengumumanDibaca.objects.filter(
        user=request.user).values_list('pengumuman_id', flat=True)
    liked_ids = PengumumanLike.objects.filter(
        user=request.user).values_list('pengumuman_id', flat=True)
    belum_dibaca = semua.exclude(id__in=dibaca_ids).count()

    return render(request, 'pengumuman_list.html', {
        'pengumuman_list': semua,
        'dibaca_ids': list(dibaca_ids),
        'liked_ids': list(liked_ids),
        'belum_dibaca': belum_dibaca,
    })


@login_required
def tandai_dibaca(request, pk):
    pengumuman = get_object_or_404(Pengumuman, pk=pk)
    PengumumanDibaca.objects.get_or_create(user=request.user, pengumuman=pengumuman)
    return redirect('pengumuman_list')


@login_required
def tandai_semua_dibaca(request):
    for p in Pengumuman.objects.all():
        PengumumanDibaca.objects.get_or_create(user=request.user, pengumuman=p)
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

        if judul and isi:
            p = Pengumuman.objects.create(
                judul=judul, isi=isi, prioritas=prioritas,
                pinned=pinned, embed_url=embed_url,
                dibuat_oleh=request.user,
            )
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

        files = request.FILES.getlist('attachments')
        for f in files:
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


# FIX: hapus template konfirmasi yang belum ada, langsung hapus via POST
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
