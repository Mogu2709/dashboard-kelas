from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
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
        # FIX BUG: denom bisa 0 kalau total_mahasiswa=0 walau total_pertemuan>0
        total_attendance = Attendance.objects.count()
        _denom = total_pertemuan * total_mahasiswa
        rata_hadir = round((total_attendance / _denom) * 100, 1) if _denom > 0 else 0

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

        # Distribusi grade — FIX: satu query aggregation, bukan loop
        distribusi_grade = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0}
        for row in TugasSubmission.objects.filter(nilai__isnull=False).values_list('nilai', flat=True).iterator():
            n = float(row)
            if n >= 85: distribusi_grade['A'] += 1
            elif n >= 75: distribusi_grade['B'] += 1
            elif n >= 65: distribusi_grade['C'] += 1
            elif n >= 55: distribusi_grade['D'] += 1
            else: distribusi_grade['E'] += 1

        # ── Pertemuan aktif sekarang ───────────────────────────────────────────
        pertemuan_aktif = Pertemuan.objects.filter(batas_absen__gt=now).select_related('mata_kuliah').first()

        # ── Notifikasi unread ─────────────────────────────────────────────────
        notif_unread = Notifikasi.objects.filter(user=request.user, dibaca=False).count()

        # ── Pertemuan 5 terbaru — FIX N+1: annotate jumlah_hadir sekaligus ──────
        pertemuan_terbaru_qs = (
            Pertemuan.objects
            .select_related('mata_kuliah')
            .annotate(jumlah_hadir=Count('attendance'))
            .order_by('-tanggal')[:5]
        )
        pertemuan_terbaru_data = [
            {
                'pertemuan': pt,
                'jumlah_hadir': pt.jumlah_hadir,
                'persen_hadir': round((pt.jumlah_hadir / total_mahasiswa) * 100) if total_mahasiswa > 0 else 0,
            }
            for pt in pertemuan_terbaru_qs
        ]

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

        # FIX BUG 4: Hitung izin+sakit approved agar persentase konsisten dengan rekap_mahasiswa
        from attendance.models import IzinAbsen
        from django.db.models import Count as _DCount
        izin_counts = (
            IzinAbsen.objects
            .filter(user=request.user, status='approved', jenis__in=['izin', 'sakit'])
            .values('jenis').annotate(n=_DCount('id'))
        )
        total_izin = total_sakit = 0
        for row in izin_counts:
            if row['jenis'] == 'izin': total_izin = row['n']
            elif row['jenis'] == 'sakit': total_sakit = row['n']
        efektif = total_hadir + total_izin + total_sakit
        persentase = round((efektif / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0
        persentase_murni = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0

        tugas_aktif = Tugas.objects.filter(deadline__gt=timezone.now()).count()
        total_materi = Materi.objects.count()
        notif_unread = Notifikasi.objects.filter(user=request.user, dibaca=False).count()

        pertemuan_terbaru = Pertemuan.objects.select_related('mata_kuliah').order_by('-tanggal')[:5]
        hadir_ids = set(Attendance.objects.filter(
            user=request.user,
            pertemuan__in=pertemuan_terbaru
        ).values_list('pertemuan_id', flat=True))

        # Ambil status izin untuk pertemuan terbaru agar ditampilkan di dashboard
        from attendance.models import IzinAbsen
        izin_map_dashboard = {}
        for izin in IzinAbsen.objects.filter(
            user=request.user,
            pertemuan__in=pertemuan_terbaru
        ).values('pertemuan_id', 'status', 'jenis'):
            izin_map_dashboard[izin['pertemuan_id']] = izin

        # Tugas aktif dengan info deadline terdekat
        tugas_aktif_list = Tugas.objects.filter(
            deadline__gt=timezone.now()
        ).select_related('mata_kuliah').order_by('deadline')[:3]

        # Nilai tugas terbaru
        from tasks.models import TugasSubmission
        nilai_terbaru = TugasSubmission.objects.filter(
            user=request.user, nilai__isnull=False
        ).select_related('tugas', 'tugas__mata_kuliah').order_by('-dinilai_pada')[:3]

        context = {
            'is_ketua': False,
            'pending_users': [],
            'total_pertemuan': total_pertemuan,
            'total_hadir': total_hadir,
            'total_izin': total_izin,
            'total_sakit': total_sakit,
            'efektif': efektif,
            'persentase': persentase,
            'persentase_murni': persentase_murni,
            'tugas_aktif': tugas_aktif,
            'tugas_aktif_list': tugas_aktif_list,
            'nilai_terbaru': nilai_terbaru,
            'total_materi': total_materi,
            'notif_unread': notif_unread,
            'pertemuan_terbaru': pertemuan_terbaru,
            'hadir_ids': hadir_ids,
            'izin_map_dashboard': izin_map_dashboard,
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

    # Statistik per MK — FIX N+1: dua query total, bukan 2*N query
    from attendance.models import MataKuliah
    from django.db.models import Count
    pertemuan_per_mk = dict(
        Pertemuan.objects.values('mata_kuliah_id').annotate(c=Count('id')).values_list('mata_kuliah_id', 'c')
    )
    hadir_per_mk = dict(
        Attendance.objects.filter(user=request.user)
        .values('pertemuan__mata_kuliah_id')
        .annotate(c=Count('id'))
        .values_list('pertemuan__mata_kuliah_id', 'c')
    )
    stats_mk = []
    for mk in MataKuliah.objects.all():
        total_mk = pertemuan_per_mk.get(mk.id, 0)
        hadir_mk = hadir_per_mk.get(mk.id, 0)
        persen_mk = round((hadir_mk / total_mk) * 100, 1) if total_mk > 0 else 0
        stats_mk.append({'mk': mk, 'total': total_mk, 'hadir': hadir_mk, 'persen': persen_mk})

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

    # Statistik per MK untuk user ini — FIX N+1
    from attendance.models import MataKuliah
    from django.db.models import Count as _Count
    pertemuan_per_mk = dict(
        Pertemuan.objects.values('mata_kuliah_id').annotate(c=_Count('id')).values_list('mata_kuliah_id', 'c')
    )
    hadir_per_mk = dict(
        Attendance.objects.filter(user=target_user)
        .values('pertemuan__mata_kuliah_id')
        .annotate(c=_Count('id'))
        .values_list('pertemuan__mata_kuliah_id', 'c')
    )
    stats_mk = []
    for mk in MataKuliah.objects.all():
        total_mk = pertemuan_per_mk.get(mk.id, 0)
        hadir_mk = hadir_per_mk.get(mk.id, 0)
        persen_mk = round((hadir_mk / total_mk) * 100, 1) if total_mk > 0 else 0
        stats_mk.append({'mk': mk, 'total': total_mk, 'hadir': hadir_mk, 'persen': persen_mk})

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
    """Helper: simpan data profil dari POST dengan validasi."""
    profile.nama_lengkap  = request.POST.get('nama_lengkap', '').strip()[:150]
    profile.nim           = request.POST.get('nim', '').strip()[:20]
    profile.jurusan       = request.POST.get('jurusan', '').strip()[:100]
    jk = request.POST.get('jenis_kelamin', '')
    profile.jenis_kelamin = jk if jk in ('L', 'P') else ''
    angkatan = request.POST.get('angkatan', '').strip()
    if angkatan.isdigit():
        year = int(angkatan)
        # Validasi tahun angkatan masuk akal
        profile.angkatan = year if 2000 <= year <= 2040 else None
    else:
        profile.angkatan = None
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
@require_POST
def approve_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.status = 'approved'
    profile.diproses_pada = timezone.now()
    profile.diproses_oleh = request.user
    profile.save()
    messages.success(request, f'✅ {profile.user.username} berhasil disetujui.')
    return redirect('kelola_user')


@login_required
@require_POST
def reject_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.status = 'rejected'
    profile.diproses_pada = timezone.now()
    profile.diproses_oleh = request.user
    profile.save()
    messages.success(request, f'❌ {profile.user.username} berhasil ditolak.')
    return redirect('kelola_user')


@login_required
@require_POST
def hapus_user_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')
    user = get_object_or_404(User, id=user_id, is_superuser=False)
    username = user.username
    user.delete()
    messages.success(request, f'🗑️ User {username} berhasil dihapus.')
    return redirect('kelola_user')