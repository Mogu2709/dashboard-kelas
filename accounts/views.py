from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from django import forms

from attendance.models import MataKuliah, Pertemuan, Attendance
from .models import UserProfile


# ─── CUSTOM REGISTER FORM ─────────────────────────────────────────────────────

class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'password1', 'password2')


# ─── HELPER ───────────────────────────────────────────────────────────────────

def check_user_approved(user):
    if user.is_superuser:
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

    total_pertemuan = Pertemuan.objects.count()
    total_hadir = Attendance.objects.filter(user=request.user).count()

    if total_pertemuan > 0:
        persentase = (total_hadir / total_pertemuan) * 100
    else:
        persentase = 0

    context = {
        'total_pertemuan': total_pertemuan,
        'total_hadir': total_hadir,
        'persentase': round(persentase, 1),
    }

    return render(request, 'dashboard.html', context)


# ─── PROFIL ───────────────────────────────────────────────────────────────────

@login_required
def profil_view(request):
    """Profil milik sendiri."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        _simpan_profil(request, profile)
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('profil')

    total_hadir = Attendance.objects.filter(user=request.user).count()
    total_pertemuan = Pertemuan.objects.count()
    persentase = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0

    return render(request, 'profil.html', {
        'profile': profile,
        'is_own_profile': True,
        'can_edit': True,
        'total_hadir': total_hadir,
        'persentase': persentase,
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
        messages.success(request, f'Profil {target_user.username} berhasil diperbarui.')
        return redirect('profil_user', user_id=user_id)

    total_hadir = Attendance.objects.filter(user=target_user).count()
    total_pertemuan = Pertemuan.objects.count()
    persentase = round((total_hadir / total_pertemuan) * 100, 1) if total_pertemuan > 0 else 0

    return render(request, 'profil.html', {
        'profile': profile,
        'is_own_profile': False,
        'can_edit': True,  # superuser selalu bisa edit
        'total_hadir': total_hadir,
        'persentase': persentase,
    })


def _simpan_profil(request, profile):
    """Helper: simpan data profil dari POST."""
    profile.nama_lengkap  = request.POST.get('nama_lengkap', '').strip()
    profile.nim           = request.POST.get('nim', '').strip()
    profile.jurusan       = request.POST.get('jurusan', '').strip()
    profile.jenis_kelamin = request.POST.get('jenis_kelamin', '')
    angkatan = request.POST.get('angkatan', '').strip()
    profile.angkatan = int(angkatan) if angkatan.isdigit() else None
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

@login_required
def pertemuan_list(request):
    mata_kuliah_id = request.GET.get('mata_kuliah')
    semester = request.GET.get('semester')

    pertemuan = Pertemuan.objects.all().order_by('-tanggal')
    mata_kuliah_list = MataKuliah.objects.all().order_by('semester', 'nama')

    # Ambil daftar semester unik untuk filter dropdown
    semester_list = MataKuliah.objects.values_list('semester', flat=True).distinct().order_by('semester')

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