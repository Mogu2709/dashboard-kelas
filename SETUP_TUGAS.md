# 📝 Panduan Setup Fitur Tugas & Materi

## Struktur File yang Dibuat

```
tasks/
├── __init__.py
├── apps.py
├── models.py        ← Model Tugas, TugasSubmission, Materi
├── forms.py         ← Form untuk buat tugas, submit, upload materi
├── views.py         ← Semua logic views
└── urls.py          ← URL routing

templates/
├── tugas_list.html          ← Daftar semua tugas
├── detail_tugas.html        ← Detail tugas + form submit
├── buat_tugas.html          ← Form buat/edit tugas (superuser)
├── materi_list.html         ← Daftar semua materi
├── unggah_materi.html       ← Form upload/edit materi (superuser)
└── konfirmasi_hapus.html    ← Halaman konfirmasi hapus
```

---

## Langkah Setup

### 1. Copy folder `tasks/` ke root project
```
dashboard_kelas/
├── accounts/
├── attendance/
├── tasks/          ← taruh di sini
├── config/
└── ...
```

### 2. Copy semua template baru ke folder `templates/`

### 3. Tambahkan `tasks` ke INSTALLED_APPS di `config/settings.py`
```python
INSTALLED_APPS = [
    ...
    'accounts',
    'attendance',
    'tasks',         # ← tambahkan ini
]
```

### 4. Tambahkan URL tasks di `config/urls.py`
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('absensi/', include('attendance.urls')),
    path('tugas/', include('tasks.urls')),    # ← tambahkan ini
    path('', dashboard_view, name='dashboard'),
]
```

### 5. Tambahkan nav Tugas & Materi di `templates/base.html`
Cari bagian nav-section pertama di sidebar dan tambahkan 2 link baru:

```html
<a href="{% url 'tugas_list' %}" class="nav-item {% block nav_tugas %}{% endblock %}" onclick="closeSidebar()">
    <span class="nav-icon">📝</span> Tugas
</a>
<a href="{% url 'materi_list' %}" class="nav-item {% block nav_materi %}{% endblock %}" onclick="closeSidebar()">
    <span class="nav-icon">📚</span> Materi
</a>
```

Letakkan setelah nav Absensi:
```html
<a href="/absensi/" class="nav-item ...">📋 Absensi</a>
<!-- tambahkan di sini -->
<a href="{% url 'tugas_list' %}" ...>📝 Tugas</a>
<a href="{% url 'materi_list' %}" ...>📚 Materi</a>
```

### 6. Untuk superuser, tambahkan juga di section Admin:
```html
{% if user.is_superuser %}
<div class="nav-section">
    <div class="nav-section-label">Admin</div>
    <a href="{% url 'buat_tugas' %}" class="nav-item {% block nav_buat_tugas %}{% endblock %}" onclick="closeSidebar()">
        <span class="nav-icon">＋</span> Buat Tugas
    </a>
    <a href="{% url 'unggah_materi' %}" class="nav-item {% block nav_unggah_materi %}{% endblock %}" onclick="closeSidebar()">
        <span class="nav-icon">⬆️</span> Unggah Materi
    </a>
    ... (nav admin yang sudah ada)
</div>
{% endif %}
```

### 7. Jalankan migrasi
```bash
python manage.py makemigrations tasks
python manage.py migrate
```

### 8. Test di lokal
```bash
python manage.py runserver
```
Buka http://localhost:8000/tugas/ dan http://localhost:8000/tugas/materi/

### 9. Deploy ke Railway
```bash
git add .
git commit -m "feat: tambah fitur tugas & materi"
git push
```

---

## Fitur yang Tersedia

### Untuk Superuser (Ketua Kelas):
- ✅ Buat tugas baru dengan deadline, deskripsi, file soal
- ✅ Edit & hapus tugas
- ✅ Lihat semua submission mahasiswa + status (tepat waktu / terlambat)
- ✅ Download file jawaban mahasiswa
- ✅ Upload materi per mata kuliah
- ✅ Edit & hapus materi

### Untuk Mahasiswa:
- ✅ Lihat daftar tugas dengan status (sudah/belum dikumpul)
- ✅ Kumpulkan tugas (upload file + catatan opsional)
- ✅ Ganti/update jawaban sebelum deadline
- ✅ Tarik ulang submission
- ✅ Download materi

### Fitur Umum:
- ✅ Filter per mata kuliah & status
- ✅ Drag & drop upload file
- ✅ Indikator sisa waktu deadline
- ✅ File tersimpan di Cloudinary (sudah ada di settings.py kamu)
- ✅ Validasi format file (PDF, Word, Excel, JPG, PNG, ZIP, RAR)
- ✅ Validasi ukuran file maks. 20MB

---

## Catatan
- Model `Tugas` dan `Materi` menggunakan FK ke `attendance.MataKuliah`, jadi mata kuliah yang muncul di dropdown tugas/materi adalah yang sudah dibuat lewat MataKuliah di app attendance.
- Pastikan sudah ada data MataKuliah sebelum membuat tugas/materi.
