from django import forms
from .models import Tugas, TugasSubmission, Materi


ALLOWED_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'rar', 'txt'
]
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def validate_file(file):
    if file:
        ext = file.name.split('.')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(f'Format file tidak didukung. Gunakan: {", ".join(ALLOWED_EXTENSIONS)}')
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError('Ukuran file maksimal 20 MB.')


class TugasForm(forms.ModelForm):
    class Meta:
        model = Tugas
        fields = ['mata_kuliah', 'judul', 'deskripsi', 'deadline', 'file_soal']
        widgets = {
            'mata_kuliah': forms.Select(attrs={
                'class': 'form-input',
            }),
            'judul': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contoh: Tugas 1 - Algoritma Sorting',
            }),
            'deskripsi': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': 'Jelaskan detail tugas, instruksi pengerjaan, format pengumpulan, dll.',
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
            'file_soal': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
        }
        labels = {
            'mata_kuliah': 'Mata Kuliah',
            'judul': 'Judul Tugas',
            'deskripsi': 'Deskripsi / Instruksi',
            'deadline': 'Batas Pengumpulan',
            'file_soal': 'File Soal (opsional)',
        }

    def clean_file_soal(self):
        file = self.cleaned_data.get('file_soal')
        validate_file(file)
        return file


class TugasSubmissionForm(forms.ModelForm):
    class Meta:
        model = TugasSubmission
        fields = ['file_jawaban', 'catatan']
        widgets = {
            'file_jawaban': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.zip,.rar',
            }),
            'catatan': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Catatan tambahan untuk dosen/ketua kelas (opsional)',
            }),
        }
        labels = {
            'file_jawaban': 'File Jawaban',
            'catatan': 'Catatan',
        }

    def clean_file_jawaban(self):
        file = self.cleaned_data.get('file_jawaban')
        validate_file(file)
        return file


class MateriForm(forms.ModelForm):
    class Meta:
        model = Materi
        fields = ['mata_kuliah', 'judul', 'deskripsi', 'file']
        widgets = {
            'mata_kuliah': forms.Select(attrs={
                'class': 'form-input',
            }),
            'judul': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contoh: Pertemuan 3 - Rekursi dan Dynamic Programming',
            }),
            'deskripsi': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Deskripsi singkat isi materi (opsional)',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png,.zip',
            }),
        }
        labels = {
            'mata_kuliah': 'Mata Kuliah',
            'judul': 'Judul Materi',
            'deskripsi': 'Deskripsi',
            'file': 'File Materi',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        validate_file(file)
        return file
