from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Prefetch

from .models import Tugas, TugasSubmission, Materi, Notifikasi
from .forms import TugasForm, TugasSubmissionForm, MateriForm
from attendance.models import MataKuliah


# ─── HELPER NOTIFIKASI ────────────────────────────────────────────────────────

def _kirim_notif_semua(tipe, judul, pesan, url, exclude_user=None):
    """
    Kirim notifikasi ke semua user approved + superuser.
    FIX: Kumpulkan semua user_id unik dulu sebelum bulk create,
    sehingga superuser yang juga approved tidak dapat notif duplikat.
    """
    from accounts.models import UserProfile

    target_user_ids = set()

    # User approved (mahasiswa)
    profiles = UserProfile.objects.filter(status='approved').values_list('user_id', flat=True)
    target_user_ids.update(profiles)

    # Superuser (untuk semua tipe, bukan hanya pengumuman)
    superuser_ids = User.objects.filter(is_superuser=True).values_list('id', flat=True)
    target_user_ids.update(superuser_ids)

    # Exclude pengirim
    if exclude_user:
        target_user_ids.discard(exclude_user.id)

    # Bulk create — jauh lebih efisien dari loop satu per satu
    notif_list = [
        Notifikasi(user_id=uid, tipe=tipe, judul=judul, pesan=pesan, url=url)
        for uid in target_user_ids
    ]
    Notifikasi.objects.bulk_create(notif_list, ignore_conflicts=True)


# ─── NOTIFIKASI API ───────────────────────────────────────────────────────────

@login_required
def notif_list_api(request):
    notifs = Notifikasi.objects.filter(user=request.user).order_by('-dibuat_pada')[:20]
    unread_count = Notifikasi.objects.filter(user=request.user, dibaca=False).count()
    data = [
        {
            'id': n.id,
            'tipe': n.tipe,
            'icon': n.icon,
            'judul': n.judul,
            'pesan': n.pesan,
            'url': n.url,
            'dibaca': n.dibaca,
            'waktu': n.waktu_relatif,
        }
        for n in notifs
    ]
    return JsonResponse({'notifikasi': data, 'unread': unread_count})


@login_required
def notif_baca(request, pk):
    if request.method == 'POST':
        notif = get_object_or_404(Notifikasi, pk=pk, user=request.user)
        notif.dibaca = True
        notif.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'method not allowed'}, status=405)


@login_required
def notif_baca_semua(request):
    if request.method == 'POST':
        Notifikasi.objects.filter(user=request.user, dibaca=False).update(dibaca=True)
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'method not allowed'}, status=405)


# ─── TUGAS ────────────────────────────────────────────────────────────────────

@login_required
def tugas_list(request):
    mk_filter = request.GET.get('mk')
    status_filter = request.GET.get('status')
    now = timezone.now()

    # FIX N+1: prefetch submissions sekaligus, bukan query per iterasi
    tugas_qs = (
        Tugas.objects
        .select_related('mata_kuliah', 'dibuat_oleh')
        .prefetch_related(
            Prefetch(
                'submissions',
                queryset=TugasSubmission.objects.select_related('user'),
            )
        )
    )

    if mk_filter:
        tugas_qs = tugas_qs.filter(mata_kuliah_id=mk_filter)
    if status_filter == 'aktif':
        tugas_qs = tugas_qs.filter(deadline__gt=now)
    elif status_filter == 'selesai':
        tugas_qs = tugas_qs.filter(deadline__lte=now)

    tugas_list_data = []
    for tugas in tugas_qs:
        # Ambil dari prefetch cache, tidak ada query tambahan
        all_subs = list(tugas.submissions.all())
        submission = None
        submit_count = len(all_subs)

        if not request.user.is_superuser:
            for s in all_subs:
                if s.user_id == request.user.id:
                    submission = s
                    break

        tugas_list_data.append({
            'tugas': tugas,
            'submission': submission,
            'submit_count': submit_count if request.user.is_superuser else 0,
        })

    return render(request, 'tugas_list.html', {
        'tugas_list': tugas_list_data,
        'mata_kuliah_list': MataKuliah.objects.all(),
        'mk_filter': mk_filter,
        'status_filter': status_filter,
    })


@login_required
def detail_tugas(request, pk):
    tugas = get_object_or_404(Tugas, pk=pk)
    submission = None
    form = None
    submissions = None

    if request.user.is_superuser:
        submissions = (
            TugasSubmission.objects
            .filter(tugas=tugas)
            .select_related('user', 'user__profile')
            .order_by('-dikumpulkan_pada')
        )
    else:
        try:
            submission = TugasSubmission.objects.get(tugas=tugas, user=request.user)
        except TugasSubmission.DoesNotExist:
            pass

        if request.method == 'POST':
            if tugas.is_expired and not submission:
                messages.error(request, 'Deadline sudah lewat.')
                return redirect('detail_tugas', pk=pk)
            form = (
                TugasSubmissionForm(request.POST, request.FILES, instance=submission)
                if submission
                else TugasSubmissionForm(request.POST, request.FILES)
            )
            if form.is_valid():
                sub = form.save(commit=False)
                sub.tugas = tugas
                sub.user = request.user
                sub.nama_file = ''
                sub.ukuran = 0
                sub.save()
                action = 'diperbarui' if submission else 'dikumpulkan'
                messages.success(request, f'✅ Tugas berhasil {action}!')
                return redirect('detail_tugas', pk=pk)
        else:
            form = TugasSubmissionForm(instance=submission) if submission else TugasSubmissionForm()

    return render(request, 'detail_tugas.html', {
        'tugas': tugas,
        'submission': submission,
        'form': form,
        'submissions': submissions,
    })


@login_required
def buat_tugas(request):
    if not request.user.is_superuser:
        return redirect('tugas_list')
    if request.method == 'POST':
        form = TugasForm(request.POST, request.FILES)
        if form.is_valid():
            tugas = form.save(commit=False)
            tugas.dibuat_oleh = request.user
            tugas.nama_file_soal = ''
            tugas.save()
            _kirim_notif_semua(
                tipe='tugas_baru',
                judul=f'Tugas Baru: {tugas.judul}',
                pesan=f'{tugas.mata_kuliah.nama} · Deadline {tugas.deadline.strftime("%d %b %Y, %H:%M")}',
                url=f'/tugas/{tugas.pk}/',
                exclude_user=request.user,
            )
            messages.success(request, f'✅ Tugas "{tugas.judul}" berhasil dibuat!')
            return redirect('detail_tugas', pk=tugas.pk)
    else:
        form = TugasForm()
    return render(request, 'buat_tugas.html', {'form': form, 'mode': 'buat'})


@login_required
def edit_tugas(request, pk):
    if not request.user.is_superuser:
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
    if not request.user.is_superuser:
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
    submission = get_object_or_404(TugasSubmission, pk=pk)
    if submission.user != request.user and not request.user.is_superuser:
        return redirect('tugas_list')
    tugas_pk = submission.tugas.pk
    submission.delete()
    messages.success(request, '🗑️ Submission berhasil dihapus.')
    return redirect('detail_tugas', pk=tugas_pk)


# ─── FITUR BARU: GRADING / NILAI ─────────────────────────────────────────────

@login_required
def beri_nilai(request, pk):
    """Admin memberi nilai dan feedback ke satu submission."""
    if not request.user.is_superuser:
        return redirect('tugas_list')

    submission = get_object_or_404(TugasSubmission, pk=pk)

    if request.method == 'POST':
        nilai_str = request.POST.get('nilai', '').strip()
        feedback = request.POST.get('feedback', '').strip()

        try:
            nilai = float(nilai_str)
            if not (0 <= nilai <= 100):
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Nilai harus berupa angka antara 0–100.')
            return redirect('detail_tugas', pk=submission.tugas.pk)

        submission.nilai = nilai
        submission.feedback = feedback
        submission.dinilai_pada = timezone.now()
        submission.dinilai_oleh = request.user
        submission.save(update_fields=['nilai', 'feedback', 'dinilai_pada', 'dinilai_oleh'])

        # Kirim notifikasi ke mahasiswa
        Notifikasi.objects.create(
            user=submission.user,
            tipe='tugas_baru',
            judul=f'Tugas Dinilai: {submission.tugas.judul}',
            pesan=f'Nilai kamu: {nilai} ({submission.grade_label})',
            url=f'/tugas/{submission.tugas.pk}/',
        )

        messages.success(request, f'✅ Nilai untuk {submission.user.username} berhasil disimpan.')
        return redirect('detail_tugas', pk=submission.tugas.pk)

    # GET - tampilkan form nilai
    return render(request, 'beri_nilai.html', {'submission': submission})


# ─── MATERI ───────────────────────────────────────────────────────────────────

@login_required
def materi_list(request):
    materi_qs = Materi.objects.select_related('mata_kuliah', 'diunggah_oleh').all()
    mk_filter = request.GET.get('mk')
    if mk_filter:
        materi_qs = materi_qs.filter(mata_kuliah_id=mk_filter)
    return render(request, 'materi_list.html', {
        'materi_list': materi_qs,
        'mata_kuliah_list': MataKuliah.objects.all(),
        'mk_filter': mk_filter,
    })


@login_required
def unggah_materi(request):
    if not request.user.is_superuser:
        return redirect('materi_list')
    if request.method == 'POST':
        form = MateriForm(request.POST, request.FILES)
        if form.is_valid():
            materi = form.save(commit=False)
            materi.diunggah_oleh = request.user
            materi.save()
            _kirim_notif_semua(
                tipe='materi_baru',
                judul=f'Materi Baru: {materi.judul}',
                pesan=f'{materi.mata_kuliah.nama}',
                url='/tugas/materi/',
                exclude_user=request.user,
            )
            messages.success(request, f'✅ Materi "{materi.judul}" berhasil diunggah!')
            return redirect('materi_list')
    else:
        form = MateriForm()
    return render(request, 'unggah_materi.html', {'form': form, 'mode': 'buat'})


@login_required
def edit_materi(request, pk):
    if not request.user.is_superuser:
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
    if not request.user.is_superuser:
        return redirect('materi_list')
    materi = get_object_or_404(Materi, pk=pk)
    if request.method == 'POST':
        nama = materi.judul
        materi.delete()
        messages.success(request, f'🗑️ Materi "{nama}" berhasil dihapus.')
        return redirect('materi_list')
    return render(request, 'konfirmasi_hapus.html', {'obj': materi, 'tipe': 'materi'})