"""
FICSY — Debug AI Tagger
Jalankan file ini langsung untuk melihat error asli dari Gemini API.

Cara pakai:
    python debug_ai.py

Letakkan file ini di folder root yang sama dengan main.py
"""

import os
import sys
import json
import traceback

# ── Pastikan package ficsy bisa diimport ──────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("=" * 60)
print("FICSY — Debug AI Tagger")
print("=" * 60)

# ── Langkah 1: Cek API key ────────────────────────────────────────────────────
print("\n[1] Cek API Key...")
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")
if not api_key:
    print("❌ GEMINI_API_KEY tidak ditemukan di environment / file .env")
    print("   Pastikan file .env ada dan berisi: GEMINI_API_KEY=your_key_here")
    sys.exit(1)
elif api_key == "isi_api_key_kamu_di_sini":
    print("❌ API key masih berisi nilai default, belum diganti")
    sys.exit(1)
else:
    masked = "*" * (len(api_key) - 4) + api_key[-4:]
    print(f"✅ API key ditemukan: {masked}")

# ── Langkah 2: Cek import google-generativeai ─────────────────────────────────
print("\n[2] Cek package google-generativeai...")
try:
    import google.generativeai as genai
    print(f"✅ Package tersedia: google-generativeai")
except ImportError:
    print("❌ Package tidak ditemukan")
    print("   Jalankan: pip install google-generativeai")
    sys.exit(1)

# ── Langkah 3: Konfigurasi Gemini ─────────────────────────────────────────────
print("\n[3] Konfigurasi Gemini API...")
try:
    genai.configure(api_key=api_key)
    print("✅ Konfigurasi berhasil")
except Exception as e:
    print(f"❌ Gagal konfigurasi: {e}")
    sys.exit(1)

# ── Langkah 4: Buat model ─────────────────────────────────────────────────────
print("\n[4] Membuat model Gemini...")
try:
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature":        0.1,
            "max_output_tokens":  200,
        },
    )
    print("✅ Model berhasil dibuat: gemini-1.5-flash")
except Exception as e:
    print(f"❌ Gagal membuat model: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Langkah 5: Test prompt sederhana ─────────────────────────────────────────
print("\n[5] Mengirim prompt test ke Gemini...")

TEST_PROMPT = """\
Kamu adalah sistem klasifikasi keuangan pelajar SMA Indonesia.
Klasifikasikan transaksi ke 'Needs' atau 'Wants'.

Input: "nonton film di bioskop"
Output (JSON saja):"""

try:
    response = model.generate_content(TEST_PROMPT)
    raw_text = response.text
    print(f"✅ Response diterima")
    print(f"\n--- Raw Response dari Gemini ---")
    print(repr(raw_text))
    print(f"--------------------------------")
except Exception as e:
    print(f"❌ Gagal memanggil Gemini API:")
    traceback.print_exc()
    sys.exit(1)

# ── Langkah 6: Parse response ─────────────────────────────────────────────────
print("\n[6] Mencoba parse JSON dari response...")
try:
    parsed = json.loads(raw_text.strip())
    print(f"✅ JSON berhasil diparsing:")
    print(f"   category   : {parsed.get('category')}")
    print(f"   confidence : {parsed.get('confidence')}")
    print(f"   reason     : {parsed.get('reason')}")
except json.JSONDecodeError as e:
    print(f"⚠️  JSON parse gagal: {e}")
    print(f"   Teks yang diterima: {repr(raw_text[:200])}")

# ── Langkah 7: Test via ai_tag() langsung ────────────────────────────────────
print("\n[7] Test via ficsy.core.ai_tagger.ai_tag()...")
try:
    from ficsy.core.ai_tagger import ai_tag, TagStatus

    test_cases = [
        "nonton film di bioskop",
        "beli boba taro 25rb",
        "ongkos angkot ke sekolah",
        "beli nasi goreng buat makan siang",
    ]

    for desc in test_cases:
        result = ai_tag(desc)
        status_icon = "✅" if result.status == TagStatus.AUTO else \
                      "⚠️ " if result.status == TagStatus.UNCERTAIN else "❌"
        print(f"\n  Input   : \"{desc}\"")
        print(f"  Hasil   : {status_icon} {result.status.value.upper()}")
        print(f"  Kategori: {result.category.value}")
        print(f"  Yakin   : {result.confidence_pct()}")
        print(f"  Alasan  : {result.reason}")

except Exception as e:
    print(f"❌ Error di ai_tag():")
    traceback.print_exc()

print("\n" + "=" * 60)
print("Debug selesai.")
print("=" * 60)
