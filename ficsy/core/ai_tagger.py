"""
FICSY — AI Auto-Tagger (Gemini Zero-Shot)
"""

import json
import os
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


_PROMPT = """\
Kamu adalah sistem klasifikasi keuangan pelajar SMA Indonesia.
Klasifikasikan transaksi ke 'Needs' (kebutuhan pokok) atau 'Wants' (keinginan/hiburan).
Transaksi: "{description}"
Balas HANYA dengan JSON valid, tanpa teks lain:
{{"category": "Needs", "confidence": 0.95, "reason": "alasan singkat"}}"""


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
            "temperature":        0.1,
            "max_output_tokens":  150,
        },
    )


def ai_tag(description: str) -> TagResult:
    description = description.strip()
    if not description:
        return TagResult(Category.UNKNOWN, 0.0, "", TagStatus.FALLBACK, description)
    try:
        model    = _get_model()
        response = model.generate_content(_PROMPT.format(description=description))
        text     = response.text.strip().strip("```").strip()
        parsed   = json.loads(text)
        cat_str  = str(parsed.get("category", "")).strip()
        if cat_str not in ("Needs", "Wants"):
            raise ValueError(f"Kategori tidak valid: {cat_str}")
        conf   = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        reason = str(parsed.get("reason", "")).strip()
        cat    = Category.NEEDS if cat_str == "Needs" else Category.WANTS
        status = TagStatus.AUTO if conf >= cfg.AI_CONFIDENCE_THRESHOLD else TagStatus.UNCERTAIN
        return TagResult(cat, conf, reason, status, description)
    except Exception as e:
        return TagResult(Category.UNKNOWN, 0.0, str(e), TagStatus.FALLBACK, description)


def ai_tag_manual(category_str: str, description: str = "") -> TagResult:
    cat_str = category_str.strip().capitalize()
    if cat_str not in ("Needs", "Wants"):
        raise ValueError(f"Kategori harus 'Needs' atau 'Wants', bukan '{cat_str}'")
    cat = Category.NEEDS if cat_str == "Needs" else Category.WANTS
    return TagResult(cat, 1.0, "Dipilih manual", TagStatus.FALLBACK, description)
