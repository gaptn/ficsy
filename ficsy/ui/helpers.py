"""
FICSY — UI Helpers
Fungsi-fungsi kecil yang dipakai di semua tampilan Rich.
"""

from rich.console import Console
from rich.text import Text

console = Console()


def fmt_rp(amount: float, sign: str = "") -> str:
    return f"{sign}Rp {abs(amount):,.0f}".replace(",", ".")


def fmt_runway(runway: float) -> str:
    return "∞ hari" if runway == float("inf") else f"{runway:.1f} hari"


def health_bar(score: float, width: int = 20) -> str:
    score  = max(0, min(100, score))
    filled = int(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def parse_amount(raw: str) -> float | None:
    raw  = raw.strip().lower().replace(".", "").replace(",", "")
    mult = 1
    for suf, m in [
        ("juta", 1_000_000), ("jt", 1_000_000),
        ("ribu", 1_000), ("rb", 1_000), ("k", 1_000),
    ]:
        if raw.endswith(suf):
            raw  = raw[:-len(suf)].strip()
            mult = m
            break
    try:
        return float(raw) * mult
    except ValueError:
        return None


def prompt(label: str, default=None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    raw    = input(f"  {label}{suffix}: ").strip()
    return raw if raw else (str(default) if default is not None else "")


def confirm(label: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw    = input(f"  {label} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "ya", "yes")


def back_check(value: str) -> bool:
    return value.strip().lower() in ("b", "back", "kembali")


def error(msg: str) -> None:
    console.print(f"\n  [bold red]❌ {msg}[/]\n")


def success(msg: str) -> None:
    console.print(f"\n  [bold green]✅ {msg}[/]\n")
