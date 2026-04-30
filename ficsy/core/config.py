"""
FICSY — Runtime Configuration
Path dan konstanta dapat di-override sebelum import modul lain.

Penggunaan di Colab:
    import ficsy.core.config as cfg
    cfg.DATA_PATH = '/content/drive/MyDrive/FICSY_Data/data.json'
    cfg.DATA_DIR  = '/content/drive/MyDrive/FICSY_Data'
"""

import os

# ─── PATH (default: folder ./data relatif dari working directory) ─────────────
DATA_DIR  = os.path.join(os.getcwd(), "data")
DATA_PATH = os.path.join(DATA_DIR, "data.json")

# ─── AI ───────────────────────────────────────────────────────────────────────
AI_CONFIDENCE_THRESHOLD = 0.75
AI_TIMEOUT_SECONDS      = 8
GEMINI_MODEL            = "gemini-1.5-flash"

# ─── FORECAST ─────────────────────────────────────────────────────────────────
SMA_WINDOW     = 7
WARNING_FACTOR = 1.2

# ─── APP ──────────────────────────────────────────────────────────────────────
APP_NAME    = "FICSY"
APP_VERSION = "1.1.0"
LIST_TX_LIMIT = 20
