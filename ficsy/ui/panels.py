"""
FICSY — Reusable UI Panels
Komponen tampilan Rich yang dapat dipanggil dari mana saja.

Berbeda dari dashboard.py yang menampilkan halaman penuh,
panels.py berisi komponen lebih kecil dan reusable:
  - render_simulation_history() → tabel riwayat simulasi
  - render_balance_summary()    → ringkasan saldo 1 baris
  - render_needs_wants_bar()    → breakdown Needs vs Wants visual
  - render_category_stats()     → statistik keuangan lengkap

Public API:
  render_simulation_history(simulations)
  render_balance_summary()
  render_needs_wants_bar()
  render_category_stats()
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
from rich import box

from core.storage import load
from core.transaction import get_summary
from core.forecast import get_full_forecast, STATUS_COLOR, STATUS_EMOJI

console = Console()

C_BRAND   = "cyan"
C_MUTED   = "dim white"
C_INCOME  = "green"
C_EXPENSE = "red"
C_NEEDS   = "blue"
C_WANTS   = "magenta"
C_WARN    = "yellow"


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _fmt_rp(amount: float, sign: str = "") -> str:
    return f"{sign}Rp {abs(amount):,.0f}".replace(",", ".")


def _fmt_date(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(iso_str)[:10]


def _health_bar(score: float, width: int = 10) -> str:
    filled = int(min(score, 100) / 10)
    return "█" * filled + "░" * (width - filled)


# ─── SIMULATION HISTORY ───────────────────────────────────────────────────────

def render_simulation_history(simulations: list[dict]) -> None:
    """
    Tampilkan tabel riwayat simulasi Decision Lab.

    Args:
        simulations: List dict dari simulator.get_simulation_history().
    """
    console.print()
    console.print(Rule("[bold cyan]🔬 Riwayat Decision Lab[/]", style="cyan"))
    console.print()

    if not simulations:
        console.print(Panel(
            "[dim]Belum ada riwayat simulasi.\nGunakan 'ficsy lab' untuk mulai.[/]",
            border_style="dim",
            padding=(1, 2),
        ))
        console.print()
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=f"bold {C_BRAND}",
        show_edge=False,
        padding=(0, 1),
    )
    table.add_column("Tanggal",     width=12, no_wrap=True)
    table.add_column("Skenario",    width=28)
    table.add_column("Biaya",       width=13, justify="right")
    table.add_column("Score Δ",     width=10, justify="center")
    table.add_column("Saldo Akhir", width=14, justify="right")

    for sim in simulations:
        before_h = float(sim.get("before_health_score", 0))
        after_h  = float(sim.get("after_health_score", 0))
        delta    = after_h - before_h
        after_b  = float(sim.get("after_balance", 0))

        if delta >= 0:
            delta_str = f"[{C_INCOME}]+{delta:.1f}[/]"
        elif delta > -15:
            delta_str = f"[{C_WARN}]{delta:.1f}[/]"
        else:
            delta_str = f"[{C_EXPENSE}]{delta:.1f}[/]"

        bal_color = C_INCOME if after_b >= 0 else C_EXPENSE

        table.add_row(
            _fmt_date(sim.get("date", "")),
            sim.get("scenario_name", "—")[:28],
            f"[{C_WARN}]{_fmt_rp(sim.get('impact_amount', 0))}[/]",
            delta_str,
            f"[{bal_color}]{_fmt_rp(after_b)}[/]",
        )

    console.print(table)
    console.print(f"  [{C_MUTED}]Total {len(simulations)} simulasi[/]")
    console.print()


# ─── BALANCE SUMMARY (1 BARIS) ────────────────────────────────────────────────

def render_balance_summary() -> None:
    """
    Ringkasan saldo satu baris — cocok sebagai header cepat.
    """
    data     = load()
    balance  = float(data["profile"].get("current_balance", 0))
    color    = C_INCOME if balance >= 0 else C_EXPENSE
    forecast = get_full_forecast(data)
    w        = forecast.warning
    s_color  = STATUS_COLOR[w.status].split()[-1]
    s_emoji  = STATUS_EMOJI[w.status]
    runway   = "∞" if w.runway_days == float("inf") else f"{w.runway_days:.1f}"

    console.print(
        f"  💰 Saldo: [{color}][bold]{_fmt_rp(balance)}[/][/]"
        f"  │  [{s_color}]{s_emoji} {w.status.value}[/]"
        f"  │  [{C_MUTED}]Runway: {runway} hari[/]"
    )


# ─── NEEDS vs WANTS BAR ───────────────────────────────────────────────────────

def render_needs_wants_bar() -> None:
    """
    Breakdown visual Needs vs Wants dari seluruh riwayat pengeluaran.
    """
    summary    = get_summary()
    total_exp  = summary["total_expense"]
    needs_pct  = summary["needs_pct"]
    wants_pct  = summary["wants_pct"]
    total_needs = summary["total_needs"]
    total_wants = summary["total_wants"]

    console.print()
    console.print(Rule("[bold]📊 Breakdown Pengeluaran[/]", style=C_BRAND))
    console.print()

    if total_exp == 0:
        console.print(Panel("[dim]Belum ada data pengeluaran.[/]", border_style="dim"))
        console.print()
        return

    # Bar 40 karakter
    bar_width   = 40
    needs_fill  = int(needs_pct / 100 * bar_width)
    wants_fill  = bar_width - needs_fill

    bar = Text()
    bar.append("█" * needs_fill,  style=f"bold {C_NEEDS}")
    bar.append("█" * wants_fill, style=f"bold {C_WANTS}")

    needs_panel = Panel(
        Text.assemble(
            (f"{_fmt_rp(total_needs)}\n", f"bold {C_NEEDS}"),
            (f"{needs_pct:.1f}% dari total\n", C_MUTED),
            ("Kebutuhan Pokok", C_MUTED),
        ),
        title=f"[{C_NEEDS}]🔵 Needs[/]",
        border_style=C_NEEDS,
        padding=(0, 2),
    )

    wants_panel = Panel(
        Text.assemble(
            (f"{_fmt_rp(total_wants)}\n", f"bold {C_WANTS}"),
            (f"{wants_pct:.1f}% dari total\n", C_MUTED),
            ("Keinginan / Hiburan", C_MUTED),
        ),
        title=f"[{C_WANTS}]🟣 Wants[/]",
        border_style=C_WANTS,
        padding=(0, 2),
    )

    console.print(Columns([needs_panel, wants_panel], equal=True, expand=True))
    console.print()
    console.print(f"  [{C_MUTED}]  Needs [/]", end="")
    console.print(bar, end="")
    console.print(f"  [{C_MUTED}] Wants[/]")
    console.print(
        f"\n  [{C_MUTED}]Total: [/][bold]{_fmt_rp(total_exp)}[/]"
        f"  [{C_MUTED}]({summary['expense_count']} transaksi)[/]"
    )
    console.print()


# ─── CATEGORY STATS ───────────────────────────────────────────────────────────

def render_category_stats() -> None:
    """
    Statistik keuangan lengkap: income, expense, breakdown, health score.
    """
    summary  = get_summary()
    data     = load()
    forecast = get_full_forecast(data)
    w        = forecast.warning
    runway   = "∞" if w.runway_days == float("inf") else f"{w.runway_days:.1f}"

    console.print()
    console.print(Rule("[bold]📈 Statistik Keuangan[/]", style=C_BRAND))
    console.print()

    table = Table(
        box=box.SIMPLE,
        show_header=False,
        show_edge=False,
        padding=(0, 2),
    )
    table.add_column("Label", style=C_MUTED, width=26)
    table.add_column("Nilai", width=22, justify="right")

    table.add_row(
        "Total Pemasukan",
        f"[{C_INCOME}]{_fmt_rp(summary['total_income'])}[/]",
    )
    table.add_row(
        "Total Pengeluaran",
        f"[{C_EXPENSE}]{_fmt_rp(summary['total_expense'])}[/]",
    )
    table.add_row(
        "  ── Needs (Kebutuhan)",
        f"[{C_NEEDS}]{_fmt_rp(summary['total_needs'])} ({summary['needs_pct']}%)[/]",
    )
    table.add_row(
        "  ── Wants (Keinginan)",
        f"[{C_WANTS}]{_fmt_rp(summary['total_wants'])} ({summary['wants_pct']}%)[/]",
    )
    table.add_row(
        "Jumlah Transaksi",
        f"[bold]{summary['transaction_count']}[/] transaksi",
    )
    table.add_row(
        "Rata-rata Pengeluaran/Hari",
        f"[bold]{_fmt_rp(forecast.daily_avg)}[/]",
    )
    table.add_row(
        "Health Score",
        f"[bold]{_health_bar(w.health_score)} {w.health_score}/100[/]",
    )
    table.add_row(
        "Runway",
        f"[bold]{runway} hari[/]",
    )

    console.print(table)
    console.print()
