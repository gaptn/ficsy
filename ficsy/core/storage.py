"""
FICSY — Storage Layer
Baca/tulis data.json. Path dikontrol via ficsy.core.config.
"""

import json
import os
import shutil
from datetime import datetime

import ficsy.core.config as cfg


class StorageError(Exception):
    pass


def _empty_state() -> dict:
    return {
        "profile": {
            "monthly_allowance": 0.0,
            "current_balance":   0.0,
            "reset_day":         1,
            "created_at":        datetime.now().isoformat(),
        },
        "transactions": [],
        "simulations":  [],
    }


def storage_load() -> dict:
    if not os.path.exists(cfg.DATA_PATH):
        return _empty_state()
    try:
        with open(cfg.DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StorageError(f"File data.json korup: {e}") from e
    except OSError as e:
        raise StorageError(f"Gagal membaca file: {e}") from e
    data.setdefault("profile",      _empty_state()["profile"])
    data.setdefault("transactions", [])
    data.setdefault("simulations",  [])
    return data


def storage_save(data: dict) -> None:
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    tmp = cfg.DATA_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cfg.DATA_PATH)
    except OSError as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise StorageError(f"Gagal menyimpan: {e}") from e


def storage_file_exists() -> bool:
    return os.path.exists(cfg.DATA_PATH)


def storage_init_if_empty() -> bool:
    if os.path.exists(cfg.DATA_PATH):
        return False
    storage_save(_empty_state())
    return True


def storage_backup() -> str:
    if not os.path.exists(cfg.DATA_PATH):
        raise StorageError("Tidak ada data untuk di-backup.")
    from datetime import datetime
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = cfg.DATA_PATH.replace(".json", f"_{ts}.bak.json")
    shutil.copy2(cfg.DATA_PATH, bak)
    return bak
