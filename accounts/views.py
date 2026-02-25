from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from attendance.models import Pertemuan, Attendance


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'register.html', {'form': form})

# dashboard view
@login_required
def dashboard_view(request):
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