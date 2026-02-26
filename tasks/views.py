from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count, Q

from .models import Tugas, TugasSubmission, Materi
from .forms import TugasForm, TugasSubmissionForm, MateriForm
from attendance.models import MataKuliah


# ─────────────────────────────────────────────
# TUGAS
# ─────────────────────────────────────────────

@login_required
def tugas_list(request):
    """Daftar semua tugas. Superuser lihat semua, mahasiswa lihat + status submit."""
    tugas_qs = Tugas.objects.select_related('mata_kuliah', 'dibuat_oleh').all()

    # Filter per mata kuliah
    mk_filter = request.GET.get('mk')
    if mk_filter:
        tugas_qs = tugas_qs.filter(mata_kuliah_id=mk_filter)

    # Filter status (aktif / selesai)
    status_filter = request.GET.get('status')
    now = timezone.now()
    if status_filter == 'aktif':
        tugas_qs = tugas_qs.filter(deadline__gt=now)
    elif status_filter == 'selesai':
        tugas_qs = tugas_qs.filter(deadline__lte=now)

    # Tambahkan info submission per user
    tugas_list_data = []
    for tugas in tugas_qs:
        submission = None
        if not request.user.is_superuser:
            try:
                submission = TugasSubmission.objects.get(tugas=tugas, user=request.user)
            except TugasSubmission.DoesNotExist:
                pass

        # Untuk superuser: hitung berapa yang sudah submit
        submit_count = 0
        if request.user.is_superuser:
            submit_count = tugas.submissions.count()

        tugas_list_data.append({
            'tugas': tugas,
            'submission': submission,
            'submit_count': submit_count,
        })

    mata_kuliah_list = MataKuliah.objects.all()

    context = {
        'tugas_list': tugas_list_data,
        'mata_kuliah_list': mata_kuliah_list,
        'mk_filter': mk_filter,
        'status_filter': status_filter,
    }
    return render(request, 'tugas_list.html', context)


@login_required
def detail_tugas(request, pk):
    """Detail tugas + form submit untuk mahasiswa / daftar submission untuk superuser."""
    tugas = get_object_or_404(Tugas, pk=pk)

    submission = None
    form = None
    submissions = None

    if request.user.is_superuser:
        # Superuser: lihat semua submission
        submissions = TugasSubmission.objects.filter(tugas=tugas).select_related('user', 'user__profile')
    else:
        # Mahasiswa: cek submission sendiri
        try:
            submission = TugasSubmission.objects.get(tugas=tugas, user=request.user)
        except TugasSubmission.DoesNotExist:
            pass

        if request.method == 'POST':
            if tugas.is_expired and not submission:
                messages.error(request, 'Deadline sudah lewat. Kamu tidak bisa mengumpulkan tugas.')
                return redirect('detail_tugas', pk=pk)

            if submission:
                # Edit submission existing
                form = TugasSubmissionForm(request.POST, request.FILES, instance=submission)
            else:
                form = TugasSubmissionForm(request.POST, request.FILES)

            if form.is_valid():
                sub = form.save(commit=False)
                sub.tugas = tugas
                sub.user = request.user
                # Reset nama_file & ukuran agar di-recompute di save()
                sub.nama_file = ''
                sub.ukuran = 0
                sub.save()
                messages.success(request, '✅ Tugas berhasil dikumpulkan!')
                return redirect('detail_tugas', pk=pk)
        else:
            if submission:
                form = TugasSubmissionForm(instance=submission)
            else:
                form = TugasSubmissionForm()

    context = {
        'tugas': tugas,
        'submission': submission,
        'form': form,
        'submissions': submissions,
    }
    return render(request, 'detail_tugas.html', context)


@login_required
def buat_tugas(request):
    """Superuser membuat tugas baru."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses ke halaman ini.')
        return redirect('tugas_list')

    if request.method == 'POST':
        form = TugasForm(request.POST, request.FILES)
        if form.is_valid():
            tugas = form.save(commit=False)
            tugas.dibuat_oleh = request.user
            tugas.nama_file_soal = ''
            tugas.save()
            messages.success(request, f'✅ Tugas "{tugas.judul}" berhasil dibuat!')
            return redirect('detail_tugas', pk=tugas.pk)
    else:
        form = TugasForm()

    return render(request, 'buat_tugas.html', {'form': form, 'mode': 'buat'})


@login_required
def edit_tugas(request, pk):
    """Superuser edit tugas."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses ke halaman ini.')
        return redirect('tugas_list')

    tugas = get_object_or_404(Tugas, pk=pk)

    if request.method == 'POST':
        form = TugasForm(request.POST, request.FILES, instance=tugas)
        if form.is_valid():
            t = form.save(commit=False)
            t.diedit_pada = timezone.now()
            t.save()
            messages.success(request, f'✅ Tugas "{t.judul}" berhasil diperbarui!')
            return redirect('detail_tugas', pk=pk)
    else:
        form = TugasForm(instance=tugas)

    return render(request, 'buat_tugas.html', {'form': form, 'mode': 'edit', 'tugas': tugas})


@login_required
def hapus_tugas(request, pk):
    """Superuser hapus tugas."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses.')
        return redirect('tugas_list')

    tugas = get_object_or_404(Tugas, pk=pk)
    if request.method == 'POST':
        nama = tugas.judul
        tugas.delete()
        messages.success(request, f'🗑️ Tugas "{nama}" berhasil dihapus.')
        return redirect('tugas_list')

    return render(request, 'konfirmasi_hapus.html', {'obj': tugas, 'tipe': 'tugas'})


@login_required
def hapus_submission(request, pk):
    """Mahasiswa hapus / tarik ulang submission mereka."""
    submission = get_object_or_404(TugasSubmission, pk=pk)

    # Hanya pemilik atau superuser yang bisa hapus
    if submission.user != request.user and not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses.')
        return redirect('tugas_list')

    tugas_pk = submission.tugas.pk
    submission.delete()
    messages.success(request, '🗑️ Submission berhasil dihapus.')
    return redirect('detail_tugas', pk=tugas_pk)


# ─────────────────────────────────────────────
# MATERI
# ─────────────────────────────────────────────

@login_required
def materi_list(request):
    """Daftar semua materi."""
    materi_qs = Materi.objects.select_related('mata_kuliah', 'diunggah_oleh').all()

    mk_filter = request.GET.get('mk')
    if mk_filter:
        materi_qs = materi_qs.filter(mata_kuliah_id=mk_filter)

    mata_kuliah_list = MataKuliah.objects.all()

    context = {
        'materi_list': materi_qs,
        'mata_kuliah_list': mata_kuliah_list,
        'mk_filter': mk_filter,
    }
    return render(request, 'materi_list.html', context)


@login_required
def unggah_materi(request):
    """Superuser upload materi baru."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses ke halaman ini.')
        return redirect('materi_list')

    if request.method == 'POST':
        form = MateriForm(request.POST, request.FILES)
        if form.is_valid():
            materi = form.save(commit=False)
            materi.diunggah_oleh = request.user
            materi.save()
            messages.success(request, f'✅ Materi "{materi.judul}" berhasil diunggah!')
            return redirect('materi_list')
    else:
        form = MateriForm()

    return render(request, 'unggah_materi.html', {'form': form, 'mode': 'buat'})


@login_required
def edit_materi(request, pk):
    """Superuser edit materi."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses.')
        return redirect('materi_list')

    materi = get_object_or_404(Materi, pk=pk)

    if request.method == 'POST':
        form = MateriForm(request.POST, request.FILES, instance=materi)
        if form.is_valid():
            m = form.save(commit=False)
            m.diedit_pada = timezone.now()
            m.save()
            messages.success(request, f'✅ Materi "{m.judul}" berhasil diperbarui!')
            return redirect('materi_list')
    else:
        form = MateriForm(instance=materi)

    return render(request, 'unggah_materi.html', {'form': form, 'mode': 'edit', 'materi': materi})


@login_required
def hapus_materi(request, pk):
    """Superuser hapus materi."""
    if not request.user.is_superuser:
        messages.error(request, 'Kamu tidak punya akses.')
        return redirect('materi_list')

    materi = get_object_or_404(Materi, pk=pk)
    if request.method == 'POST':
        nama = materi.judul
        materi.delete()
        messages.success(request, f'🗑️ Materi "{nama}" berhasil dihapus.')
        return redirect('materi_list')

    return render(request, 'konfirmasi_hapus.html', {'obj': materi, 'tipe': 'materi'})
