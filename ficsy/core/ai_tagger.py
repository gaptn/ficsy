"""
FICSY — AI Auto-Tagger (Gemini Few-Shot)
Menggunakan few-shot prompting agar Gemini terkalibrasi
dengan standar Needs/Wants versi pelajar SMA Indonesia.
"""

import json
import os
import re
from dataclasses import dataclass
from enum import Enum

import ficsy.core.config as cfg


class TagStatus(Enum):
    AUTO      = "auto"
    UNCERTAIN = "uncertain"
    FALLBACK  = "fallback"


class Category(Enum):
    NEEDS   = "Needs"
    WANTS   = "Wants"
    UNKNOWN = "Unknown"


@dataclass
class TagResult:
    category:   Category
    confidence: float
    reason:     str
    status:     TagStatus
    raw_input:  str

    @property
    def is_confident(self) -> bool:
        return self.confidence >= cfg.AI_CONFIDENCE_THRESHOLD

    @property
    def is_fallback(self) -> bool:
        return self.status == TagStatus.FALLBACK

    def confidence_pct(self) -> str:
        return f"{int(self.confidence * 100)}%"


# ─── PROMPT ───────────────────────────────────────────────────────────────────
# Strategi: Few-shot prompting dengan:
#   1. Definisi ketat Needs vs Wants untuk konteks pelajar SMA Indonesia
#   2. 10 contoh berlabel (5 Needs, 5 Wants) agar Gemini terkalibrasi
#   3. Instruksi format output yang sangat eksplisit
#   4. Penanganan kasus ambigu (boba, jajan, dll)

_PROMPT = """\
Kamu adalah sistem klasifikasi keuangan untuk pelajar SMA Indonesia.

DEFINISI:
- Needs  = pengeluaran yang HARUS ada untuk bertahan dan belajar sehari-hari.
  Contoh kategori: makan/minum pokok, ongkos/transportasi, perlengkapan sekolah,
  kesehatan, komunikasi dasar (pulsa/data untuk sekolah), iuran wajib.

- Wants  = pengeluaran yang TIDAK harus ada, bisa ditunda atau dihilangkan
  tanpa mengganggu kegiatan sekolah.
  Contoh kategori: jajan hiburan, minuman kekinian, nonton, game, fashion,
  nongkrong, aksesoris, langganan hiburan.

ATURAN AMBIGU:
- Minuman kekinian (boba, es kopi, thai tea) → selalu Wants
- Makan di kantin/warteg untuk makan siang → Needs
- Makan di restoran/cafe untuk nongkrong → Wants
- Pulsa/data untuk WA dan sekolah → Needs
- Langganan Netflix/Spotify/game → Wants
- Buku pelajaran/LKS → Needs
- Buku komik/novel → Wants
- Ongkos angkot/ojol ke sekolah → Needs
- Ojol untuk jalan-jalan → Wants

CONTOH KLASIFIKASI:
Input: "beli nasi goreng buat makan siang"
Output: {{"category": "Needs", "confidence": 0.95, "reason": "makan siang adalah kebutuhan pokok"}}

Input: "boba taro 25rb"
Output: {{"category": "Wants", "confidence": 0.97, "reason": "minuman kekinian termasuk keinginan"}}

Input: "ongkos angkot ke sekolah"
Output: {{"category": "Needs", "confidence": 0.98, "reason": "transportasi wajib ke sekolah"}}

Input: "top up diamond mobile legends"
Output: {{"category": "Wants", "confidence": 0.99, "reason": "pembelian item game adalah hiburan"}}

Input: "beli LKS matematika"
Output: {{"category": "Needs", "confidence": 0.96, "reason": "buku pelajaran adalah kebutuhan belajar"}}

Input: "makan mcdonald sama teman"
Output: {{"category": "Wants", "confidence": 0.88, "reason": "makan di restoran cepat saji untuk nongkrong"}}

Input: "bayar iuran OSIS"
Output: {{"category": "Needs", "confidence": 0.93, "reason": "iuran wajib kegiatan sekolah"}}

Input: "beli pulsa 20rb"
Output: {{"category": "Needs", "confidence": 0.85, "reason": "komunikasi dasar untuk kegiatan sekolah"}}

Input: "nonton film di bioskop"
Output: {{"category": "Wants", "confidence": 0.97, "reason": "hiburan bioskop bukan kebutuhan pokok"}}

Input: "beli obat sakit kepala"
Output: {{"category": "Needs", "confidence": 0.99, "reason": "obat termasuk kebutuhan kesehatan"}}

SEKARANG KLASIFIKASIKAN:
Input: "{description}"
Output (JSON saja, tanpa teks lain, tanpa markdown):"""


# ─── PARSING ROBUST ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """
    Parsing berlapis — mencoba beberapa strategi agar tidak mudah gagal
    meski Gemini mengembalikan format yang sedikit berbeda.
    """
    text = text.strip()

    # Strategi 1: parse langsung
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategi 2: hapus markdown code block
    cleaned = re.sub(r"```(?:json)?", "", text).strip().strip("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategi 3: cari JSON object di dalam teks dengan regex
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategi 4: cari keyword category langsung dari teks
    # (last resort jika semua parsing gagal)
    text_lower = text.lower()
    if '"needs"' in text_lower or "'needs'" in text_lower or ': needs' in text_lower:
        return {"category": "Needs", "confidence": 0.6, "reason": "diparsing dari teks"}
    if '"wants"' in text_lower or "'wants'" in text_lower or ': wants' in text_lower:
        return {"category": "Wants", "confidence": 0.6, "reason": "diparsing dari teks"}

    raise ValueError(f"Tidak bisa mengekstrak JSON dari response: {text[:100]}")


# ─── GEMINI CLIENT ────────────────────────────────────────────────────────────

def _get_model():
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise Exception("GEMINI_API_KEY belum diset di environment.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=cfg.GEMINI_MODEL,
        generation_config={
            "response_mime_type": "application/json",
            "temperature":        0.1,   # rendah = konsisten, tidak kreatif
            "max_output_tokens":  200,   # sedikit lebih besar untuk jaga-jaga
        },
    )


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def ai_tag(description: str) -> TagResult:
    """
    Klasifikasikan deskripsi transaksi ke Needs atau Wants.
    Tidak pernah raise exception — semua error → FALLBACK.
    """
    description = description.strip()
    if not description:
        return TagResult(Category.UNKNOWN, 0.0, "", TagStatus.FALLBACK, description)

    try:
        model    = _get_model()
        prompt   = _PROMPT.format(description=description)
        response = model.generate_content(prompt)
        parsed   = _extract_json(response.text)

        cat_str  = str(parsed.get("category", "")).strip().capitalize()
        if cat_str not in ("Needs", "Wants"):
            raise ValueError(f"Kategori tidak valid: '{cat_str}'")

        conf   = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        reason = str(parsed.get("reason", "")).strip()
        cat    = Category.NEEDS if cat_str == "Needs" else Category.WANTS
        status = TagStatus.AUTO if conf >= cfg.AI_CONFIDENCE_THRESHOLD else TagStatus.UNCERTAIN

        return TagResult(cat, conf, reason, status, description)

    except Exception as e:
        return TagResult(
            Category.UNKNOWN, 0.0,
            f"Error: {type(e).__name__} — {str(e)[:80]}",
            TagStatus.FALLBACK,
            description,
        )


def ai_tag_manual(category_str: str, description: str = "") -> TagResult:
    """Buat TagResult dari pilihan manual user."""
    cat_str = category_str.strip().capitalize()
    if cat_str not in ("Needs", "Wants"):
        raise ValueError(f"Kategori harus 'Needs' atau 'Wants', bukan '{cat_str}'")
    cat = Category.NEEDS if cat_str == "Needs" else Category.WANTS
    return TagResult(cat, 1.0, "Dipilih manual oleh user", TagStatus.FALLBACK, description)
