# 📚 Dashboard Kelas

Aplikasi web manajemen kelas berbasis Django — absensi, tugas, pengumuman, dan rekap mahasiswa dalam satu platform.

**Live:** [Railway Deployment](https://your-app.railway.app) &nbsp;·&nbsp; **Stack:** Django 6 · PostgreSQL · Cloudinary · Railway

---

## ✨ Fitur Utama

| Fitur | Mahasiswa | Ketua Kelas |
|---|---|---|
| Absensi dengan kode unik per pertemuan | ✅ | ✅ Kelola |
| Pengajuan izin / sakit dengan bukti | ✅ | ✅ Approve/Reject |
| Kumpulkan & lihat nilai tugas | ✅ | ✅ Buat & Nilai |
| Download materi kuliah | ✅ | ✅ Upload |
| Pengumuman + komentar + like | ✅ | ✅ Buat |
| Rekap kehadiran & grafik | — | ✅ |
| Export rekap ke Excel & PDF | — | ✅ |
| Notifikasi realtime (bell) | ✅ | ✅ |
| Search tugas & materi | ✅ | ✅ |
| Grafik kehadiran & kalender deadline | ✅ | ✅ |

---

## 🗂️ Struktur Proyek

```
dashboard_kelas/
├── accounts/          # Auth, profil user, kelola user (approve/reject)
├── attendance/        # Absensi, pertemuan, pengumuman, izin, export
├── tasks/             # Tugas, materi, notifikasi, grading
├── config/            # Settings, URL utama
├── templates/         # Semua HTML template
│   └── partials/      # Komponen reusable (_submit_form.html)
├── manage.py
├── requirements.txt
├── Procfile           # Untuk Railway
└── runtime.txt        # Python version
```

### Role User
- **Superuser (Ketua Kelas)** — akses penuh ke semua fitur admin
- **Mahasiswa** — akses fitur mahasiswa setelah disetujui ketua

---

## 🚀 Setup Lokal

### Prasyarat
- Python 3.12+
- pip
- Git

### Langkah-langkah

**1. Clone repo**
```bash
git clone https://github.com/Mogu2709/dashboard-kelas.git
cd dashboard-kelas
```

**2. Buat virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Buat file `.env`** di root folder
```env
SECRET_KEY=ganti-dengan-secret-key-panjang-minimal-50-karakter
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database — kosongkan untuk pakai SQLite lokal
# DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Cloudinary — kosongkan untuk pakai local storage
# CLOUDINARY_CLOUD_NAME=your_cloud_name
# CLOUDINARY_API_KEY=your_api_key
# CLOUDINARY_API_SECRET=your_api_secret

# CSRF (isi kalau deploy)
# CSRF_TRUSTED_ORIGINS=https://your-app.railway.app
```

> **Generate SECRET_KEY:**
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

**5. Migrasi database**
```bash
python manage.py migrate
```

**6. Buat akun superuser (Ketua Kelas)**
```bash
python manage.py createsuperuser
```

**7. Jalankan server**
```bash
python manage.py runserver
```

Buka [http://127.0.0.1:8000](http://127.0.0.1:8000) di browser.

---

## ☁️ Deploy ke Railway

### Environment Variables yang wajib diset di Railway:

| Variable | Keterangan |
|---|---|
| `SECRET_KEY` | Django secret key (wajib, jangan pakai yang sama dengan lokal) |
| `DEBUG` | Set ke `False` di production |
| `ALLOWED_HOSTS` | Domain Railway kamu, misal `your-app.railway.app` |
| `DATABASE_URL` | Otomatis diisi Railway kalau kamu tambah PostgreSQL plugin |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.railway.app` |
| `CLOUDINARY_CLOUD_NAME` | Dari dashboard Cloudinary |
| `CLOUDINARY_API_KEY` | Dari dashboard Cloudinary |
| `CLOUDINARY_API_SECRET` | Dari dashboard Cloudinary |

### Langkah deploy:

**1. Push ke GitHub**
```bash
git add .
git commit -m "your message"
git push origin main
```

**2. Di Railway:**
- Hubungkan repo GitHub ke Railway project
- Tambahkan plugin **PostgreSQL** dari Railway dashboard
- Set semua environment variables di atas
- Railway akan auto-deploy setiap kali ada push ke `main`

**3. Setelah deploy pertama, jalankan migrasi via Railway CLI:**
```bash
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

---

## 🛠️ Panduan Kontribusi

### Alur kerja (Git Flow sederhana)

```
main          ← production, selalu stable
  └── dev     ← development, semua fitur merge ke sini dulu
        ├── feature/nama-fitur
        ├── fix/nama-bug
        └── ...
```

**Jangan pernah push langsung ke `main`!**

### Cara mulai kontribusi

**1. Fork / clone repo, lalu buat branch baru dari `dev`:**
```bash
git checkout dev
git pull origin dev
git checkout -b feature/nama-fitur-kamu
```

**2. Koding, lalu commit dengan pesan yang jelas:**
```bash
git add .
git commit -m "feat: tambah fitur export PDF per mahasiswa"
```

Konvensi commit message:
| Prefix | Kapan dipakai |
|---|---|
| `feat:` | Fitur baru |
| `fix:` | Bugfix |
| `refactor:` | Refactor kode tanpa mengubah behavior |
| `style:` | Perubahan tampilan / CSS |
| `docs:` | Update dokumentasi |
| `chore:` | Update dependency, config, dll |

**3. Push branch kamu:**
```bash
git push origin feature/nama-fitur-kamu
```

**4. Buat Pull Request ke branch `dev`** di GitHub.

---

## 🗃️ Models Penting

### `accounts`
- **`UserProfile`** — extend User dengan nama lengkap, NIM, jurusan, angkatan, status (`pending` / `approved` / `rejected`)

### `attendance`
- **`MataKuliah`** — mata kuliah dengan semester
- **`Pertemuan`** — sesi kuliah dengan kode absen unik (auto-generate), waktu mulai & batas absen
- **`Attendance`** — record kehadiran mahasiswa per pertemuan
- **`Pengumuman`** — pengumuman dengan attachment, like, komentar, embed YouTube
- **`IzinAbsen`** — pengajuan izin/sakit dengan bukti file, alur approve/reject

### `tasks`
- **`Tugas`** — tugas dengan deadline, file soal opsional
- **`TugasSubmission`** — jawaban mahasiswa + sistem grading (nilai 0-100, grade A-E, feedback)
- **`Materi`** — file materi kuliah
- **`Notifikasi`** — notifikasi in-app (tugas baru, materi baru, deadline, pengumuman, absensi, izin)

---

## ⚙️ Management Commands

```bash
# Kirim reminder deadline tugas (default 24 jam ke depan)
python manage.py kirim_reminder_deadline

# Custom jam
python manage.py kirim_reminder_deadline --jam 48
```

Jadwalkan di Railway dengan cron job: `0 7 * * *` (setiap hari jam 07.00 WIB).

---

## 🗺️ Roadmap (TODO)

- [ ] **Dark mode** — toggle tema gelap/terang
- [ ] **Jadwal kuliah / kalender akademik** — integrasi jadwal per semester
- [ ] **Mobile app** — React Native atau PWA

---

## 🐛 Melaporkan Bug

Buka [GitHub Issues](https://github.com/Mogu2709/dashboard-kelas/issues) dengan format:

```
**Deskripsi bug:**
...

**Langkah reproduksi:**
1. Buka halaman ...
2. Klik ...
3. Error muncul ...

**Expected behavior:**
...

**Screenshot (kalau ada):**
...
```

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan internal kelas. Bebas dimodifikasi untuk kebutuhan sendiri.