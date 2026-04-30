# 💰 FICSY — Financial Literacy CLI

> Platform literasi keuangan berbasis Terminal/CLI untuk pelajar SMA.  
> Catat keuangan, prediksi saldo, dan simulasikan risiko pengeluaran dengan AI.

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 📊 **Dashboard** | Saldo, status kesehatan keuangan, dan prediksi cashflow |
| 🤖 **AI Auto-Tagging** | Kategorisasi Needs/Wants otomatis via Gemini API |
| 📈 **Forecast** | Prediksi saldo habis dengan Simple Moving Average |
| ⚠️ **Early Warning** | Peringatan dini jika saldo diprediksi habis sebelum waktunya |
| 🔬 **Decision Lab** | Simulasi skenario pengeluaran fiktif tanpa mengubah data asli |
| 📋 **Riwayat** | Lihat semua transaksi dengan filter tipe dan kategori |

---

## 🚀 Cara Menjalankan

### Prasyarat
- Python 3.10 atau lebih baru
- API key Gemini (gratis di [aistudio.google.com](https://aistudio.google.com/app/apikey))

### Install

```bash
# 1. Clone repo
git clone https://github.com/username/ficsy.git
cd ficsy

# 2. Install dependensi
pip install -r requirements.txt

# 3. Buat file .env dan isi API key
cp .env.example .env
# Buka .env, ganti dengan API key kamu

# 4. Jalankan
python ficsy.py
```

### Perintah yang Tersedia

```bash
python ficsy.py          # Buka menu utama
```

Menu interaktif akan tampil dengan pilihan:
```
[1] 📊 Dashboard
[2] ➕ Tambah Transaksi
[3] 📋 Riwayat Transaksi
[4] 🔬 Decision Lab
[5] 📈 Statistik
[6] 🗂️  Riwayat Simulasi
[7] ⚙️  Setup Profil
[0] 👋 Keluar
```

---

## 📓 Google Colab

Tersedia versi notebook untuk dijalankan di Google Colab tanpa instalasi lokal.

### Install via pip (dari repo ini)

```python
!pip install git+https://github.com/username/ficsy.git -q
```

### Buka Notebook

File tersedia di folder [`notebooks/FICSY_Colab.ipynb`](notebooks/FICSY_Colab.ipynb).

---

## 📁 Struktur Project

```
ficsy/
├── ficsy.py                  # Entry point CLI
├── setup.py                  # Konfigurasi package
├── requirements.txt          # Dependensi
├── .env.example              # Template API key
├── .gitignore
├── README.md
│
├── ficsy/                    # Package utama
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py         # Konstanta & path (bisa di-override)
│   │   ├── storage.py        # Baca/tulis JSON
│   │   ├── ai_tagger.py      # Gemini zero-shot tagging
│   │   ├── transaction.py    # CRUD transaksi
│   │   ├── forecast.py       # SMA + Early Warning
│   │   └── simulator.py      # Decision Lab
│   └── ui/
│       ├── __init__.py
│       ├── helpers.py        # Fungsi UI reusable
│       ├── dashboard.py      # Tampilan dashboard Rich
│       ├── prompts.py        # Alur input interaktif
│       └── panels.py         # Komponen UI tambahan
│
└── notebooks/
    └── FICSY_Colab.ipynb     # Versi Google Colab
```

---

## 🛠️ Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Bahasa | Python 3.10+ |
| CLI UI | [Rich](https://github.com/Textualize/rich) |
| AI Tagging | Gemini 1.5 Flash (Zero-shot) |
| Forecasting | Simple Moving Average (SMA-7) |
| Storage | JSON lokal |
| Distribusi | pip / PyInstaller |

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
