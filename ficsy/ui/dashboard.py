"""
FICSY — Dashboard UI
Semua tampilan terminal menggunakan Rich library.

Setiap fungsi render_*() adalah unit UI yang berdiri sendiri.
dashboard.py tidak menyimpan state — hanya membaca data dan menampilkan.

Public API:
  render_dashboard()                    → tampilan utama (saldo, status, transaksi)
  render_transaction_added(tx, balance) → konfirmasi setelah add transaksi
  render_simulation_result(result)      → hasil Decision Lab
  render_transaction_list(transactions) → tabel riwayat transaksi
  render_error(message)                 → pesan error terformat
  render_welcome()                      → banner pertama kali buka app
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding
from rich.progress import BarColumn, Progress, TextColumn
from rich import box

from config import APP_NAME, APP_VERSION, DASHBOARD_TX_LIMIT
from core.storage import load
from core.forecast import (
    get_full_forecast,
    Status,
    STATUS_COLOR,
    STATUS_EMOJI,
    ForecastResult,
)
from core.simulator import SimulationResult, PRESET_SCENARIOS

# ─── CONSOLE SINGLETON ────────────────────────────────────────────────────────

console = Console()


# ─── KONSTANTA WARNA ──────────────────────────────────────────────────────────

C_BRAND     = "cyan"
C_MUTED     = "dim white"
C_INCOME    = "green"
C_EXPENSE   = "red"
C_NEEDS     = "blue"
C_WANTS     = "magenta"
C_HIGHLIGHT = "bold white"
C_WARN      = "yellow"


# ─── HELPER FORMATTERS ────────────────────────────────────────────────────────

def _fmt_rp(amount: float, sign: str = "") -> str:
    """Format angka ke Rupiah. Contoh: 150000 → 'Rp 150.000'"""
    return f"{sign}Rp {abs(amount):,.0f}".replace(",", ".")


def _fmt_date(iso_str: str) -> str:
    """Ubah ISO string ke format 'DD MMM YYYY'. Fallback ke raw string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(iso_str)[:10]


def _fmt_runway(runway: float) -> str:
    """Format runway untuk tampilan. inf → '∞'"""
    if runway == float("inf"):
        return "∞ hari"
    return f"{runway:.1f} hari"


def _health_bar(score: float) -> str:
    """
    Buat mini bar teks untuk health score.
    score 0–100 → blok unicode ████░░░░░░
    """
    filled = int(score / 10)
    empty  = 10 - filled
    return "█" * filled + "░" * empty


def _category_badge(category: str | None) -> str:
    """Kembalikan string berwarna untuk kategori transaksi."""
    if category == "Needs":
        return f"[{C_NEEDS}]Needs[/]"
    if category == "Wants":
        return f"[{C_WANTS}]Wants[/]"
    return f"[{C_MUTED}] — [/]"


# ─── PANEL BUILDER ────────────────────────────────────────────────────────────

def _build_status_panel(forecast: ForecastResult) -> Panel:
    """Panel kiri atas: saldo, status, health score."""
    w = forecast.warning
    status_color = STATUS_COLOR[w.status]
    status_emoji = STATUS_EMOJI[w.status]

    # Health bar
    bar_color = status_color.split()[-1]  # ambil nama warna dari "bold green" dll
    bar_text   = Text(_health_bar(w.health_score), style=bar_color)

    balance_color = C_INCOME if forecast.balance >= 0 else C_EXPENSE
    balance_str   = _fmt_rp(forecast.balance)

    content = Text()
    content.append("Saldo Saat Ini\n", style=C_MUTED)
    content.append(f"{balance_str}\n\n", style=f"bold {balance_color}")

    content.append("Status Keuangan\n", style=C_MUTED)
    content.append(f"{status_emoji} {w.status.value}\n\n", style=status_color)

    content.append("Health Score\n", style=C_MUTED)
    content.append(f"{_health_bar(w.health_score)} {w.health_score}/100\n", style=bar_color)

    return Panel(
        content,
        title=f"[bold {C_BRAND}]💰 Keuangan[/]",
        border_style=C_BRAND,
        padding=(1, 2),
    )


def _build_forecast_panel(forecast: ForecastResult) -> Panel:
    """Panel kanan atas: runway, avg, reset."""
    w = forecast.warning

    runway_color = STATUS_COLOR[w.status].split()[-1]

    content = Text()
    content.append("Runway (Saldo Tahan)\n", style=C_MUTED)
    content.append(f"{_fmt_runway(w.runway_days)}\n\n", style=f"bold {runway_color}")

    content.append("Avg Pengeluaran/Hari\n", style=C_MUTED)
    content.append(f"{_fmt_rp(forecast.daily_avg)}\n\n", style=C_HIGHLIGHT)

    content.append("Reset Uang Jajan\n", style=C_MUTED)
    content.append(
        f"{w.next_reset_date.strftime('%d %b %Y')} ({w.days_until_reset} hari lagi)\n",
        style=C_HIGHLIGHT,
    )

    # Data quality notice
    if not forecast.has_enough_data:
        content.append(
            f"\n⚠ Data baru {forecast.data_points} hari — forecast perkiraan",
            style=C_WARN,
        )

    return Panel(
        content,
        title=f"[bold {C_BRAND}]📈 Forecast[/]",
        border_style=C_BRAND,
        padding=(1, 2),
    )


def _build_warning_panel(forecast: ForecastResult) -> Panel | None:
    """
    Panel peringatan merah — hanya ditampilkan jika status WARNING atau DANGER/EMPTY.
    Return None jika status SAFE.
    """
    w = forecast.warning
    if w.status == Status.SAFE:
        return None

    if w.status == Status.EMPTY:
        msg = "💀 Saldo kamu sudah habis! Hubungi orang tua atau cari sumber pemasukan."
        border = "red"
    elif w.status == Status.DANGER:
        shortfall = w.shortfall_amount
        msg = (
            f"🚨 PERINGATAN: Uang jajan diprediksi habis {w.runway_days:.1f} hari lagi — "
            f"{w.days_until_reset} hari sebelum reset.\n"
            f"   Estimasi kekurangan: {_fmt_rp(shortfall)}"
        )
        border = "red"
    else:  # WARNING
        msg = (
            f"⚠️  WASPADA: Runway ({_fmt_runway(w.runway_days)}) mendekati batas reset "
            f"({w.days_until_reset} hari). Kurangi pengeluaran Wants."
        )
        border = "yellow"

    return Panel(
        Text(msg, style=f"bold {border}"),
        border_style=border,
        padding=(0, 2),
    )


def _build_recent_tx_panel(transactions: list[dict]) -> Panel:
    """Panel bawah: 5 transaksi terakhir dalam tabel."""
    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=f"bold {C_BRAND}",
        show_edge=False,
        padding=(0, 1),
    )
    table.add_column("Tanggal",   style=C_MUTED, width=12, no_wrap=True)
    table.add_column("Deskripsi", width=28)
    table.add_column("Kategori",  width=8,  justify="center")
    table.add_column("Jumlah",    width=14, justify="right")

    recent = sorted(transactions, key=lambda x: x.get("date", ""), reverse=True)
    recent = recent[:DASHBOARD_TX_LIMIT]

    if not recent:
        table.add_row(
            "—", "[dim]Belum ada transaksi[/]", "—", "—"
        )
    else:
        for tx in recent:
            is_expense = tx.get("type") == "expense"
            sign       = "-" if is_expense else "+"
            color      = C_EXPENSE if is_expense else C_INCOME
            amount_str = f"[{color}]{_fmt_rp(tx['amount'], sign)}[/]"
            cat_str    = _category_badge(tx.get("auto_category"))
            desc       = tx.get("description", "")[:28]
            date_str   = _fmt_date(tx.get("date", ""))

            table.add_row(date_str, desc, cat_str, amount_str)

    return Panel(
        table,
        title=f"[bold]📋 Transaksi Terakhir[/]",
        border_style="dim",
        padding=(0, 1),
    )


# ─── PUBLIC RENDER FUNCTIONS ──────────────────────────────────────────────────

def render_dashboard() -> None:
    """
    Tampilan utama FICSY.
    Menampilkan: header, panel saldo+status, panel forecast, early warning, tabel transaksi.
    """
    data     = load()
    forecast = get_full_forecast(data)
    transactions = data.get("transactions", [])

    console.print()
    console.print(Rule(f"[bold {C_BRAND}]{APP_NAME} v{APP_VERSION}[/]", style=C_BRAND))
    console.print()

    # Dua kolom atas: status | forecast
    status_panel   = _build_status_panel(forecast)
    forecast_panel = _build_forecast_panel(forecast)
    console.print(Columns([status_panel, forecast_panel], equal=True, expand=True))

    # Early warning (hanya jika perlu)
    warning_panel = _build_warning_panel(forecast)
    if warning_panel:
        console.print(warning_panel)

    # Tabel transaksi
    console.print(_build_recent_tx_panel(transactions))

    # Footer hint
    console.print(
        f"[{C_MUTED}]  ficsy add · ficsy list · ficsy lab · ficsy setup[/]"
    )
    console.print()


def render_transaction_added(tx: dict, new_balance: float) -> None:
    """
    Tampilkan konfirmasi setelah transaksi berhasil disimpan.

    Args:
        tx:          Dict transaksi yang baru disimpan.
        new_balance: Saldo setelah transaksi.
    """
    is_expense = tx.get("type") == "expense"
    sign       = "-" if is_expense else "+"
    color      = C_EXPENSE if is_expense else C_INCOME
    cat        = tx.get("auto_category")
    confidence = tx.get("ai_confidence")

    content = Text()
    content.append("✅ Transaksi berhasil dicatat!\n\n", style="bold green")

    content.append("Deskripsi   : ", style=C_MUTED)
    content.append(f"{tx.get('description', '')}\n", style=C_HIGHLIGHT)

    content.append("Jumlah      : ", style=C_MUTED)
    content.append(f"{_fmt_rp(tx['amount'], sign)}\n", style=f"bold {color}")

    if cat:
        conf_str = f" ({int(confidence * 100)}%)" if confidence else ""
        content.append("Kategori    : ", style=C_MUTED)
        content.append(f"{cat}{conf_str}\n", style=C_HIGHLIGHT)

    content.append("Saldo Baru  : ", style=C_MUTED)
    bal_color = C_INCOME if new_balance >= 0 else C_EXPENSE
    content.append(f"{_fmt_rp(new_balance)}", style=f"bold {bal_color}")

    console.print()
    console.print(Panel(content, border_style="green", padding=(1, 2)))
    console.print()


def render_simulation_result(result: SimulationResult) -> None:
    """
    Tampilkan hasil Decision Lab: perbandingan before/after.

    Args:
        result: SimulationResult dari simulator.run_simulation().
    """
    from core.forecast import STATUS_COLOR, STATUS_EMOJI

    b_color = STATUS_COLOR[result.before_status].split()[-1]
    a_color = STATUS_COLOR[result.after_status].split()[-1]

    console.print()
    console.print(Rule(f"[bold cyan]🔬 Hasil Simulasi: {result.scenario_name}[/]", style="cyan"))
    console.print()

    # Tabel before/after
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 2),
    )
    table.add_column("Metrik",       style=C_MUTED, width=22)
    table.add_column("Sebelum",      justify="center", width=20)
    table.add_column("Sesudah",      justify="center", width=20)
    table.add_column("Δ Perubahan",  justify="center", width=16)

    def _delta_str(val: float, higher_is_better: bool = True) -> str:
        if val == 0:
            return "[dim]—[/]"
        arrow  = "▲" if val > 0 else "▼"
        color  = C_INCOME if (val > 0) == higher_is_better else C_EXPENSE
        return f"[{color}]{arrow} {abs(val):.1f}[/]"

    # Baris saldo
    bal_delta = result.after_balance - result.before_balance
    table.add_row(
        "Saldo",
        f"[bold]{_fmt_rp(result.before_balance)}[/]",
        f"[bold {'red' if result.after_balance < 0 else 'white'}]{_fmt_rp(result.after_balance)}[/]",
        _delta_str(bal_delta),
    )

    # Baris health score
    table.add_row(
        "Health Score",
        f"[{b_color}]{_health_bar(result.before_health)} {result.before_health}[/]",
        f"[{a_color}]{_health_bar(result.after_health)} {result.after_health}[/]",
        _delta_str(result.health_delta),
    )

    # Baris runway
    before_run_str = _fmt_runway(result.before_runway)
    after_run_str  = _fmt_runway(result.after_runway)
    table.add_row(
        "Runway",
        f"[{b_color}]{before_run_str}[/]",
        f"[{a_color}]{after_run_str}[/]",
        _delta_str(result.runway_delta),
    )

    # Baris status
    b_emoji = STATUS_EMOJI[result.before_status]
    a_emoji = STATUS_EMOJI[result.after_status]
    table.add_row(
        "Status",
        f"[{b_color}]{b_emoji} {result.before_status.value}[/]",
        f"[{a_color}]{a_emoji} {result.after_status.value}[/]",
        "[dim]—[/]" if not result.status_changed else "[bold yellow]berubah![/]",
    )

    console.print(table)

    # Verdict
    verdict_panel = Panel(
        Text(result.verdict(), justify="center"),
        border_style="cyan",
        padding=(0, 4),
    )
    console.print(verdict_panel)

    # Data warning
    if not result.has_enough_data:
        console.print(
            f"[{C_WARN}]  ⚠ Data transaksi masih sedikit — akurasi simulasi terbatas.[/]"
        )

    console.print()


def render_transaction_list(transactions: list[dict]) -> None:
    """
    Tampilkan riwayat transaksi dalam tabel lengkap.

    Args:
        transactions: List dict transaksi dari transaction.get_transactions().
    """
    console.print()
    console.print(Rule("[bold]📋 Riwayat Transaksi[/]", style=C_BRAND))
    console.print()

    if not transactions:
        console.print(Panel(
            "[dim]Belum ada transaksi. Gunakan 'ficsy add' untuk mencatat.[/]",
            border_style="dim",
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
    table.add_column("#",          width=4,  justify="right", style=C_MUTED)
    table.add_column("Tanggal",    width=12, no_wrap=True)
    table.add_column("Deskripsi",  width=30)
    table.add_column("Tipe",       width=8,  justify="center")
    table.add_column("Kategori",   width=8,  justify="center")
    table.add_column("AI%",        width=5,  justify="right", style=C_MUTED)
    table.add_column("Jumlah",     width=15, justify="right")

    for i, tx in enumerate(transactions, 1):
        is_expense = tx.get("type") == "expense"
        sign       = "-" if is_expense else "+"
        color      = C_EXPENSE if is_expense else C_INCOME
        type_str   = f"[{color}]{'exp' if is_expense else 'inc'}[/]"
        cat_str    = _category_badge(tx.get("auto_category")) if is_expense else "[dim] — [/]"

        conf = tx.get("ai_confidence")
        conf_str = f"{int(conf * 100)}%" if conf else "—"
        if tx.get("user_confirmed"):
            conf_str = "[dim]usr[/]"

        amount_str = f"[{color}]{_fmt_rp(tx['amount'], sign)}[/]"

        table.add_row(
            str(i),
            _fmt_date(tx.get("date", "")),
            tx.get("description", "")[:30],
            type_str,
            cat_str,
            conf_str,
            amount_str,
        )

    console.print(table)
    console.print(f"  [{C_MUTED}]Total: {len(transactions)} transaksi[/]")
    console.print()


def render_preset_scenarios() -> None:
    """Tampilkan daftar preset skenario Decision Lab untuk dipilih user."""
    console.print()
    console.print(Rule("[bold cyan]🔬 Decision Lab — Pilih Skenario[/]", style="cyan"))
    console.print()

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        show_edge=False,
        padding=(0, 1),
    )
    table.add_column("No",        width=4,  justify="right", style=C_MUTED)
    table.add_column("Skenario",  width=32)
    table.add_column("Kategori",  width=16, style=C_MUTED)
    table.add_column("Estimasi",  width=14, justify="right")

    for p in PRESET_SCENARIOS:
        table.add_row(
            str(p["id"]),
            f"{p['emoji']} {p['name']}",
            p["category"],
            f"[yellow]{_fmt_rp(p['amount'])}[/]",
        )

    # Opsi kustom
    table.add_row(
        "0",
        "✏️  Input kustom...",
        "—",
        "[dim]manual[/]",
    )

    console.print(table)
    console.print()


def render_error(message: str, hint: str = "") -> None:
    """Tampilkan pesan error terformat."""
    content = Text()
    content.append(f"❌ {message}", style="bold red")
    if hint:
        content.append(f"\n   💡 {hint}", style=C_MUTED)
    console.print()
    console.print(Panel(content, border_style="red", padding=(0, 2)))
    console.print()


def render_success(message: str) -> None:
    """Tampilkan pesan sukses singkat."""
    console.print(f"\n  [bold green]✅ {message}[/]\n")


def render_welcome() -> None:
    """Banner selamat datang untuk pertama kali membuka FICSY."""
    banner = f"""[bold cyan]
  ███████╗██╗ ██████╗███████╗██╗   ██╗
  ██╔════╝██║██╔════╝██╔════╝╚██╗ ██╔╝
  █████╗  ██║██║     ███████╗ ╚████╔╝ 
  ██╔══╝  ██║██║     ╚════██║  ╚██╔╝  
  ██║     ██║╚██████╗███████║   ██║   
  ╚═╝     ╚═╝ ╚═════╝╚══════╝   ╚═╝  
[/bold cyan]
[dim]  Financial Literacy CLI for High School Students[/dim]
[{C_MUTED}]  v{APP_VERSION}[/]
"""

    console.print(Panel(banner, border_style=C_BRAND, padding=(0, 4)))
    console.print()
    console.print(f"  [{C_MUTED}]Jalankan[/] [bold]ficsy setup[/] [{C_MUTED}]untuk mulai mengatur profil keuangan.[/]")
    console.print()
