from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django import forms

from attendance.models import Pertemuan, Attendance
from .models import UserProfile


# ─── CUSTOM REGISTER FORM ─────────────────────────────────────────────────────

class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'password1', 'password2')


# ─── MIDDLEWARE CHECK: blokir user pending/rejected ───────────────────────────

def check_user_approved(user):
    """Return True jika user adalah superuser atau sudah approved."""
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
            user.is_active = True  # aktif tapi belum bisa login karena status pending
            user.save()
            # Buat profile dengan status pending
            UserProfile.objects.create(user=user, status='pending')
            return redirect('pending_approval')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


# ─── PENDING APPROVAL PAGE ────────────────────────────────────────────────────

def pending_approval_view(request):
    return render(request, 'pending_approval.html')


# ─── CUSTOM LOGIN: cek status approval ───────────────────────────────────────

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
                # User tanpa profile dianggap pending
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
    # Blokir user yang belum approved
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


# ─── KELOLA USER (SUPERUSER ONLY) ─────────────────────────────────────────────

@login_required
def kelola_user_view(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    pending = UserProfile.objects.filter(status='pending').select_related('user').order_by('dibuat_pada')
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
