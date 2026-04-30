"""
FICSY — Forecast & Early Warning Engine
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

import ficsy.core.config as cfg


class Status(Enum):
    SAFE    = "AMAN"
    WARNING = "WASPADA"
    DANGER  = "BAHAYA"
    EMPTY   = "HABIS"


STATUS_COLOR = {
    Status.SAFE:    "bold green",
    Status.WARNING: "bold yellow",
    Status.DANGER:  "bold red",
    Status.EMPTY:   "bold white on red",
}

STATUS_EMOJI = {
    Status.SAFE:    "✅",
    Status.WARNING: "⚠️ ",
    Status.DANGER:  "🚨",
    Status.EMPTY:   "💀",
}


@dataclass
class WarningResult:
    status:           Status
    runway_days:      float
    days_until_reset: int
    next_reset_date:  date
    daily_avg:        float
    health_score:     float

    @property
    def shortfall_amount(self) -> float:
        if self.runway_days == float("inf"):
            return 0.0
        return max(0.0, self.days_until_reset - self.runway_days) * self.daily_avg


@dataclass
class ForecastResult:
    warning:         WarningResult
    daily_avg:       float
    weekly_avg:      float
    monthly_avg:     float
    balance:         float
    reset_day:       int
    data_points:     int
    has_enough_data: bool


def _get_next_reset(today: date, reset_day: int) -> date:
    reset_day = max(1, min(28, reset_day))
    if today.day < reset_day:
        try:
            return today.replace(day=reset_day)
        except ValueError:
            nm = today.replace(day=1) + timedelta(days=32)
            return nm.replace(day=1) - timedelta(days=1)
    fn = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    try:
        return fn.replace(day=reset_day)
    except ValueError:
        return (fn + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def _daily_expense_map(transactions: list, window: int) -> dict:
    today = date.today()
    daily: dict = {}
    for tx in transactions:
        if tx.get("type") != "expense":
            continue
        try:
            tx_date = datetime.fromisoformat(tx["date"]).date()
        except Exception:
            continue
        delta = (today - tx_date).days
        if 0 <= delta < window:
            daily[tx_date] = daily.get(tx_date, 0.0) + float(tx.get("amount", 0))
    return daily


def calc_daily_avg(transactions: list, window: int = None) -> float:
    window = window or cfg.SMA_WINDOW
    if not transactions or window <= 0:
        return 0.0
    daily = _daily_expense_map(transactions, window)
    if not daily:
        return 0.0
    return sum(daily.values()) / window


def calc_runway(balance: float, daily_avg: float) -> float:
    if balance <= 0:
        return 0.0
    if daily_avg <= 0:
        return float("inf")
    return balance / daily_avg


def calc_health_score(runway: float, days_until_reset: int) -> float:
    if runway == float("inf"):
        return 100.0
    if runway <= 0:
        return 0.0
    if days_until_reset <= 0:
        return 100.0
    return round(min(100.0, runway / days_until_reset * 100), 1)


def check_early_warning(
    balance:      float,
    transactions: list,
    reset_day:    int,
    window:       int = None,
) -> WarningResult:
    window     = window or cfg.SMA_WINDOW
    today      = date.today()
    next_reset = _get_next_reset(today, reset_day)
    days_until = max(1, (next_reset - today).days)
    daily_avg  = calc_daily_avg(transactions, window)
    runway     = calc_runway(balance, daily_avg)
    health     = calc_health_score(runway, days_until)

    if balance <= 0:
        status = Status.EMPTY
    elif runway == float("inf"):
        status = Status.SAFE
    elif runway < days_until:
        status = Status.DANGER
    elif runway < days_until * cfg.WARNING_FACTOR:
        status = Status.WARNING
    else:
        status = Status.SAFE

    return WarningResult(status, runway, days_until, next_reset, daily_avg, health)


def get_full_forecast(data: dict) -> ForecastResult:
    profile   = data.get("profile", {})
    txs       = data.get("transactions", [])
    balance   = float(profile.get("current_balance", 0.0))
    reset_day = int(profile.get("reset_day", 1))
    daily_avg = calc_daily_avg(txs)
    warning   = check_early_warning(balance, txs, reset_day)
    dp        = len(_daily_expense_map(txs, cfg.SMA_WINDOW))
    return ForecastResult(
        warning, daily_avg, daily_avg * 7, daily_avg * 30,
        balance, reset_day, dp, dp >= 3,
    )
