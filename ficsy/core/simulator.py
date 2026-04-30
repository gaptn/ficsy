"""
FICSY — Decision Lab Simulator
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

from ficsy.core.storage  import storage_load, storage_save
from ficsy.core.forecast import (
    get_full_forecast, check_early_warning,
    Status, WarningResult, ForecastResult,
)


class SimulatorError(Exception):
    pass


PRESET_SCENARIOS: list[dict] = [
    {"id":1, "name":"HP rusak — servis layar",    "amount":250_000, "category":"Darurat",        "emoji":"📱"},
    {"id":2, "name":"Nonton bioskop + jajan",      "amount": 80_000, "category":"Hiburan",        "emoji":"🎬"},
    {"id":3, "name":"Beli buku pelajaran",         "amount": 75_000, "category":"Pendidikan",     "emoji":"📚"},
    {"id":4, "name":"Makan di luar seminggu",      "amount":150_000, "category":"Makanan",        "emoji":"🍜"},
    {"id":5, "name":"Beli outfit baru",            "amount":200_000, "category":"Fashion",        "emoji":"👕"},
    {"id":6, "name":"Top-up game/subscription",    "amount":100_000, "category":"Hiburan Digital","emoji":"🎮"},
    {"id":7, "name":"Bayar iuran kelas",           "amount": 50_000, "category":"Kewajiban",      "emoji":"🏫"},
    {"id":8, "name":"Kado ulang tahun teman",      "amount":120_000, "category":"Sosial",         "emoji":"🎁"},
]


@dataclass
class SimulationResult:
    scenario_name:    str
    impact_amount:    float
    before_balance:   float
    before_health:    float
    before_runway:    float
    before_status:    Status
    before_daily_avg: float
    after_balance:    float
    after_health:     float
    after_runway:     float
    after_status:     Status
    after_daily_avg:  float
    days_until_reset: int
    has_enough_data:  bool

    @property
    def health_delta(self) -> float:
        return round(self.after_health - self.before_health, 1)

    @property
    def is_affordable(self) -> bool:
        return self.after_balance >= 0

    @property
    def will_trigger_danger(self) -> bool:
        return self.after_status in (Status.DANGER, Status.EMPTY)

    def verdict(self) -> str:
        if not self.is_affordable:
            return "❌ Tidak mampu — saldo akan jadi negatif."
        if self.will_trigger_danger and self.before_status != Status.DANGER:
            return "🚨 Berisiko — uang jajan diprediksi habis sebelum waktunya."
        if self.health_delta < -20:
            return "⚠️  Perhatian — kesehatan keuangan turun signifikan."
        if self.health_delta < -5:
            return "⚠️  Waspada — ada dampak ke saldo akhir bulan."
        return "✅ Aman — dampak masih dalam batas wajar."


def run_simulation(scenario_name: str, impact_amount: float) -> SimulationResult:
    impact_amount = float(impact_amount)
    if impact_amount <= 0:
        raise SimulatorError("Amount harus lebih dari 0.")
    if not scenario_name.strip():
        raise SimulatorError("Nama skenario tidak boleh kosong.")

    data      = storage_load()
    profile   = data.get("profile", {})
    txs       = data.get("transactions", [])
    balance   = float(profile.get("current_balance", 0))
    reset_day = int(profile.get("reset_day", 1))

    bf  = get_full_forecast(data)
    bw  = bf.warning

    sim_bal  = balance - impact_amount
    fake_tx  = {"type":"expense","amount":impact_amount,"date":datetime.now().isoformat()}
    sim_txs  = txs + [fake_tx]
    aw       = check_early_warning(sim_bal, sim_txs, reset_day)

    rec = {
        "id":                  str(uuid4()),
        "scenario_name":       scenario_name.strip(),
        "impact_amount":       impact_amount,
        "before_balance":      balance,
        "before_health_score": bw.health_score,
        "after_balance":       sim_bal,
        "after_health_score":  aw.health_score,
        "date":                datetime.now().isoformat(),
    }
    data["simulations"].append(rec)
    storage_save(data)

    return SimulationResult(
        scenario_name.strip(), impact_amount,
        balance,  bw.health_score, bw.runway_days, bw.status, bw.daily_avg,
        sim_bal,  aw.health_score, aw.runway_days, aw.status, aw.daily_avg,
        bw.days_until_reset, bf.has_enough_data,
    )


def get_simulation_history(limit: int = 10) -> list:
    data = storage_load()
    sims = sorted(data.get("simulations", []), key=lambda x: x.get("date",""), reverse=True)
    return sims[:limit] if limit else sims
