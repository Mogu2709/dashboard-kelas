from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django import forms

from attendance.models import Pertemuan, Attendance
from .models import UserProfile


# ─── CUSTOM REGISTER FORM ─────────────────────────────────────────────────────

class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'password1', 'password2')


# ─── HELPER ───────────────────────────────────────────────────────────────────

def check_user_approved(user):
    if user.is_superuser:
        # Pastikan superuser punya profile (agar template tidak error)
        UserProfile.objects.get_or_create(user=user, defaults={'status': 'approved'})
        return True
    try:
        return user.profile.status == 'approved'
    except UserProfile.DoesNotExist:
        return False


# ─── REGISTER ─────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()
            # FITUR BARU: langsung buat profil kosong dengan data awal
            UserProfile.objects.create(user=user, status='pending')
            return redirect('pending_approval')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


# ─── PENDING APPROVAL PAGE ────────────────────────────────────────────────────

def pending_approval_view(request):
    return render(request, 'pending_approval.html')


# ─── LOGIN ────────────────────────────────────────────────────────────────────

def login_view(request):
    # FIX: kalau sudah login, langsung ke dashboard (bukan loop ke login lagi)
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_superuser:
                login(request, user)
                # Pastikan superuser punya profile
                UserProfile.objects.get_or_create(user=user, defaults={'status': 'approved'})
                return redirect('dashboard')

            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                error = 'pending'
                return render(request, 'login.html', {'error': error})

            if profile.status == 'approved':
                login(request, user)
                return redirect('dashboard')
            elif profile.status == 'pending':
                error = 'pending'
            elif profile.status == 'rejected':
                error = 'rejected'
        else:
            error = 'invalid'

    return render(request, 'login.html', {'error': error})


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    if not check_user_approved(request.user):
        logout(request)
        return redirect('pending_approval')

    # ── Data pending users (untuk alert) ──────────────────────────────────────
    from .models import UserProfile as UP
    pending_users = UP.objects.filter(status='pending').select_related('user') if request.user.is_superuser else []

    if request.user.is_superuser:
        # ══════════════════════════════════════════════════════════════════════
        # DASHBOARD KETUA KELAS
        # ══════════════════════════════════════════════════════════════════════
        from django.db.models import Count, Avg, Q
        from tasks.models import Tugas, TugasSubmission, Notifikasi
        from attendance.models import Pertemuan, Attendance, MataKuliah

        total_mahasiswa  = User.objects.filter(is_superuser=False, profile__status='approved').count()
        total_pertemuan  = Pertemuan.objects.count()

        # ── Kehadiran kelas ───────────────────────────────────────────────────
        # Mahasiswa yang kehadirannya di bawah 75%
        mahasiswa_qs = User.objects.filter(is_superuser=False, profile__status='approved').annotate(
            total_hadir=Count('attendance')
        )
        absen_parah = []
        for mhs in mahasiswa_qs:
            persen = round((mhs.total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
            if persen < 75:
                absen_parah.append({
                    'user': mhs,
                    'total_hadir': mhs.total_hadir,
                    'persentase': persen,
                })
        absen_parah.sort(key=lambda x: x['persentase'])

        # Rata-rata kehadiran kelas
        total_attendance = Attendance.objects.count()
        rata_hadir = round((total_attendance / (total_pertemuan * total_mahasiswa)) * 100, 1) \
            if total_pertemuan > 0 and total_mahasiswa > 0 else 0

        # ── Tugas ─────────────────────────────────────────────────────────────
        from django.utils import timezone
        now = timezone.now()
        tugas_aktif_qs = Tugas.objects.filter(deadline__gt=now).select_related('mata_kuliah').order_by('deadline')[:5]

        # Submission yang belum dinilai
        belum_dinilai = TugasSubmission.objects.filter(nilai__isnull=True).count()

        # Tugas yang deadline-nya dalam 3 hari
        deadline_dekat = Tugas.objects.filter(
            deadline__gt=now,
            deadline__lte=now + timezone.timedelta(days=3)
        ).count()

        # ── Statistik nilai kelas ─────────────────────────────────────────────
        nilai_stats = TugasSubmission.objects.filter(nilai__isnull=False).aggregate(
            rata=Avg('nilai'),
            total=Count('id'),
        )
        rata_nilai_kelas = round(float(nilai_stats['rata']), 1) if nilai_stats['rata'] else None

        # Distribusi grade
        distribusi_grade = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0}
        for sub in TugasSubmission.objects.filter(nilai__isnull=False).values_list('nilai', flat=True):
            n = float(sub)
            if n >= 85: distribusi_grade['A'] += 1
            elif n >= 75: distribusi_grade['B'] += 1
            elif n >= 65: distribusi_grade['C'] += 1
            elif n >= 55: distribusi_grade['D'] += 1
            else: distribusi_grade['E'] += 1

        # ── Pertemuan aktif sekarang ───────────────────────────────────────────
        pertemuan_aktif = Pertemuan.objects.filter(batas_absen__gt=now).select_related('mata_kuliah').first()

        # ── Notifikasi unread ─────────────────────────────────────────────────
        notif_unread = Notifikasi.objects.filter(user=request.user, dibaca=False).count()

        # ── Pertemuan 5 terbaru ────────────────────────────────────────────────
        pertemuan_terbaru = Pertemuan.objects.select_related('mata_kuliah').order_by('-tanggal')[:5]
        pertemuan_terbaru_data = []
        for pt in pertemuan_terbaru:
            jumlah_hadir = Attendance.objects.filter(pertemuan=pt).count()
            persen_hadir = round((jumlah_hadir / total_mahasiswa) * 100) if total_mahasiswa > 0 else 0
            pertemuan_terbaru_data.append({
                'pertemuan': pt,
                'jumlah_hadir': jumlah_hadir,
                'persen_hadir': persen_hadir,
            })

        context = {
            'is_ketua': True,
            'pending_users': pending_users,
            # Stats utama
            'total_mahasiswa': total_mahasiswa,
            'total_pertemuan': total_pertemuan,
            'rata_hadir': rata_hadir,
            'belum_dinilai': belum_dinilai,
            'deadline_dekat': deadline_dekat,
            'rata_nilai_kelas': rata_nilai_kelas,
            # Alerts
            'absen_parah': absen_parah[:5],  # max 5
            'absen_parah_count': len(absen_parah),
            # Tugas
            'tugas_aktif_qs': tugas_aktif_qs,
            # Nilai
            'distribusi_grade': distribusi_grade,
            'total_dinilai': nilai_stats['total'] or 0,
            # Pertemuan
            'pertemuan_aktif': pertemuan_aktif,
            'pertemuan_terbaru': pertemuan_terbaru_data,
            # Notif
            'notif_unread': notif_unread,
        }

    else:
        # ══════════════════════════════════════════════════════════════════════
        # DASHBOARD MAHASISWA (tidak berubah)
        # ══════════════════════════════════════════════════════════════════════
        from attendance.models import Pertemuan, Attendance
        from tasks.models import Tugas, Materi, Notifikasi
        from django.utils import timezone

        total_pertemuan = Pertemuan.objects.count()
        total_hadir = Attendance.objects.filter(user=request.user).count()
        persentase = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
        tugas_aktif = Tugas.objects.filter(deadline__gt=timezone.now()).count()
        total_materi = Materi.objects.count()
        notif_unread = Notifikasi.objects.filter(user=request.user, dibaca=False).count()

        pertemuan_terbaru = Pertemuan.objects.order_by('-tanggal')[:5]
        hadir_ids = Attendance.objects.filter(
            user=request.user,
            pertemuan__in=pertemuan_terbaru
        ).values_list('pertemuan_id', flat=True)

        context = {
            'is_ketua': False,
            'pending_users': [],
            'total_pertemuan': total_pertemuan,
            'total_hadir': total_hadir,
            'persentase': persentase,
            'tugas_aktif': tugas_aktif,
            'total_materi': total_materi,
            'notif_unread': notif_unread,
            'pertemuan_terbaru': pertemuan_terbaru,
            'hadir_ids': list(hadir_ids),
        }

    return render(request, 'dashboard.html', context)


# ─── PROFIL ───────────────────────────────────────────────────────────────────

@login_required
def profil_view(request):
    """Profil milik sendiri."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        _simpan_profil(request, profile)
        messages.success(request, '✅ Profil berhasil diperbarui.')
        return redirect('profil')

    total_hadir = Attendance.objects.filter(user=request.user).count()
    total_pertemuan = Pertemuan.objects.count()
    persentase = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0

    # Riwayat kehadiran untuk profil lengkap
    riwayat_hadir = (
        Attendance.objects
        .filter(user=request.user)
        .select_related('pertemuan', 'pertemuan__mata_kuliah')
        .order_by('-waktu_hadir')[:10]
    )

    # Statistik per mata kuliah
    from attendance.models import MataKuliah
    from django.db.models import Count
    stats_mk = []
    for mk in MataKuliah.objects.all():
        total_mk = Pertemuan.objects.filter(mata_kuliah=mk).count()
        hadir_mk = Attendance.objects.filter(
            user=request.user, pertemuan__mata_kuliah=mk
        ).count()
        persen_mk = round((hadir_mk / total_mk) * 100, 1) if total_mk > 0 else 0
        stats_mk.append({
            'mk': mk,
            'total': total_mk,
            'hadir': hadir_mk,
            'persen': persen_mk,
        })

    return render(request, 'profil.html', {
        'profile': profile,
        'is_own_profile': True,
        'can_edit': True,
        'total_hadir': total_hadir,
        'persentase': persentase,
        'riwayat_hadir': riwayat_hadir,
        'stats_mk': stats_mk,
    })


@login_required
def profil_user_view(request, user_id):
    """Superuser melihat/edit profil mahasiswa lain."""
    if not request.user.is_superuser:
        return redirect('profil')

    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    if request.method == 'POST':
        _simpan_profil(request, profile)
        messages.success(request, f'✅ Profil {target_user.username} berhasil diperbarui.')
        return redirect('profil_user', user_id=user_id)

    total_hadir = Attendance.objects.filter(user=target_user).count()
    total_pertemuan = Pertemuan.objects.count()
    persentase = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0

    # Riwayat kehadiran untuk superuser lihat profil mahasiswa
    riwayat_hadir = (
        Attendance.objects
        .filter(user=target_user)
        .select_related('pertemuan', 'pertemuan__mata_kuliah')
        .order_by('-waktu_hadir')[:10]
    )

    # Statistik per MK untuk user ini
    from attendance.models import MataKuliah
    stats_mk = []
    for mk in MataKuliah.objects.all():
        total_mk = Pertemuan.objects.filter(mata_kuliah=mk).count()
        hadir_mk = Attendance.objects.filter(
            user=target_user, pertemuan__mata_kuliah=mk
        ).count()
        persen_mk = round((hadir_mk / total_mk) * 100, 1) if total_mk > 0 else 0
        stats_mk.append({
            'mk': mk,
            'total': total_mk,
            'hadir': hadir_mk,
            'persen': persen_mk,
        })

    # Nilai tugas untuk superuser lihat profil mahasiswa
    try:
        from tasks.models import TugasSubmission
        submissions = (
            TugasSubmission.objects
            .filter(user=target_user, nilai__isnull=False)
            .select_related('tugas', 'tugas__mata_kuliah')
            .order_by('-dinilai_pada')
        )
    except Exception:
        submissions = []

    return render(request, 'profil.html', {
        'profile': profile,
        'target_user': target_user,
        'is_own_profile': False,
        'can_edit': True,
        'total_hadir': total_hadir,
        'persentase': persentase,
        'riwayat_hadir': riwayat_hadir,
        'stats_mk': stats_mk,
        'submissions': submissions,
    })


def _simpan_profil(request, profile):
    """Helper: simpan data profil dari POST."""
    profile.nama_lengkap  = request.POST.get('nama_lengkap', '').strip()
    profile.nim           = request.POST.get('nim', '').strip()
    profile.jurusan       = request.POST.get('jurusan', '').strip()
    profile.jenis_kelamin = request.POST.get('jenis_kelamin', '')
    angkatan = request.POST.get('angkatan', '').strip()
    profile.angkatan      = int(angkatan) if angkatan.isdigit() else None

    profile.save()


# ─── KELOLA USER (SUPERUSER) ──────────────────────────────────────────────────

@login_required
def kelola_user_view(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    pending  = UserProfile.objects.filter(status='pending').select_related('user').order_by('dibuat_pada')
    approved = UserProfile.objects.filter(status='approved').select_related('user').order_by('user__username')
    rejected = UserProfile.objects.filter(status='rejected').select_related('user').order_by('user__username')

    return render(request, 'kelola_user.html', {
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
    })


@login_required
def approve_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    if request.method == 'POST':
        profile = get_object_or_404(UserProfile, user_id=user_id)
        profile.status = 'approved'
        profile.diproses_pada = timezone.now()
        profile.diproses_oleh = request.user
        profile.save()
    return redirect('kelola_user')


@login_required
def reject_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    if request.method == 'POST':
        profile = get_object_or_404(UserProfile, user_id=user_id)
        profile.status = 'rejected'
        profile.diproses_pada = timezone.now()
        profile.diproses_oleh = request.user
        profile.save()
    return redirect('kelola_user')


@login_required
def hapus_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id, is_superuser=False)
        user.delete()
    return redirect('kelola_user')