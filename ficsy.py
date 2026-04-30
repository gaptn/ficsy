#!/usr/bin/env python3
"""
FICSY — Financial Literacy CLI for High School Students

Jalankan: python ficsy.py
"""

import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─── GUARD: cek dependensi ────────────────────────────────────────────────────

def _check_dependencies() -> None:
    missing = []
    required = {
        "rich":                "rich>=13.7.0",
        "google.generativeai": "google-generativeai>=0.7.0",
        "dotenv":              "python-dotenv>=1.0.0",
    }
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print("\n❌ Dependensi belum terinstall:\n")
        for m in missing:
            print(f"   • {m}")
        print("\nJalankan:\n   pip install -r requirements.txt\n")
        sys.exit(1)


def _check_first_run() -> bool:
    from core.storage import file_exists
    return not file_exists()


# ─── MENU UTAMA ───────────────────────────────────────────────────────────────

MENU_ITEMS = [
    {
        "key":         "1",
        "label":       "Dashboard",
        "description": "Lihat saldo, status, dan transaksi terakhir",
        "emoji":       "📊",
    },
    {
        "key":         "2",
        "label":       "Tambah Transaksi",
        "description": "Catat pengeluaran atau pemasukan baru",
        "emoji":       "➕",
    },
    {
        "key":         "3",
        "label":       "Riwayat Transaksi",
        "description": "Lihat semua transaksi yang pernah dicatat",
        "emoji":       "📋",
    },
    {
        "key":         "4",
        "label":       "Decision Lab",
        "description": "Simulasi skenario pengeluaran fiktif",
        "emoji":       "🔬",
    },
    {
        "key":         "5",
        "label":       "Statistik",
        "description": "Breakdown Needs vs Wants dan health score",
        "emoji":       "📈",
    },
    {
        "key":         "6",
        "label":       "Riwayat Simulasi",
        "description": "Lihat semua simulasi yang pernah dijalankan",
        "emoji":       "🗂️ ",
    },
    {
        "key":         "7",
        "label":       "Setup Profil",
        "description": "Update uang jajan, saldo, atau tanggal reset",
        "emoji":       "⚙️ ",
    },
    {
        "key":         "0",
        "label":       "Keluar",
        "description": "Tutup aplikasi",
        "emoji":       "👋",
    },
]


def _render_menu(console) -> None:
    """Render tampilan menu utama dengan Rich."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich import box
    from config import APP_NAME, APP_VERSION
    from core.storage import load
    from core.forecast import get_full_forecast
    from core.forecast import STATUS_COLOR, STATUS_EMOJI

    console.print()

    # ── Header brand ─────────────────────────────────────────────────────────
    console.print(Panel(
        Text.assemble(
            (f"  {APP_NAME}  ", "bold cyan"),
            (f"v{APP_VERSION}", "dim"),
            ("\n  Financial Literacy CLI untuk Pelajar SMA", "dim white"),
        ),
        border_style="cyan",
        padding=(0, 2),
    ))

    # ── Status bar ringkas ────────────────────────────────────────────────────
    try:
        data     = load()
        forecast = get_full_forecast(data)
        w        = forecast.warning
        balance  = forecast.balance
        s_color  = STATUS_COLOR[w.status].split()[-1]
        s_emoji  = STATUS_EMOJI[w.status]
        bal_color = "green" if balance >= 0 else "red"
        runway    = "∞" if w.runway_days == float("inf") else f"{w.runway_days:.1f}"

        status_line = Text.assemble(
            ("  Saldo: ", "dim white"),
            (f"Rp {abs(balance):,.0f}".replace(",", "."), f"bold {bal_color}"),
            ("  │  ", "dim"),
            (f"{s_emoji} {w.status.value}", s_color),
            ("  │  ", "dim"),
            (f"Runway: {runway} hari", "dim white"),
        )
        console.print(status_line)
    except Exception:
        console.print("  [dim]Profil belum diatur. Pilih Setup Profil untuk memulai.[/]")

    console.print()
    console.print(Rule("[dim]Menu Utama[/]", style="dim"))
    console.print()

    # ── Tabel menu ───────────────────────────────────────────────────────────
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        show_edge=False,
        padding=(0, 2),
    )
    table.add_column("Key",   width=4,  justify="center")
    table.add_column("Emoji", width=3)
    table.add_column("Label", width=22, style="bold white")
    table.add_column("Desc",  style="dim white")

    for item in MENU_ITEMS:
        key_style = "bold cyan" if item["key"] != "0" else "dim red"
        table.add_row(
            f"[{key_style}][{item['key']}][/]",
            item["emoji"],
            item["label"],
            item["description"],
        )

    console.print(table)
    console.print()


def _run_menu_loop() -> None:
    """Loop menu utama — terus tampilkan menu sampai user pilih keluar."""
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()

    valid_keys = [item["key"] for item in MENU_ITEMS]

    while True:
        _render_menu(console)

        choice = Prompt.ask(
            "  Pilih menu",
            choices=valid_keys,
            default="1",
        )

        console.print()

        # ── Dispatch ─────────────────────────────────────────────────────────
        if choice == "0":
            console.print("  [dim]Sampai jumpa! 👋[/]\n")
            break

        elif choice == "1":
            from ui.dashboard import render_dashboard
            render_dashboard()

        elif choice == "2":
            from ui.prompts import prompt_add_transaction
            prompt_add_transaction()

        elif choice == "3":
            from ui.prompts import prompt_list
            prompt_list()

        elif choice == "4":
            from ui.prompts import prompt_lab
            prompt_lab()

        elif choice == "5":
            from ui.panels import render_needs_wants_bar, render_category_stats
            render_needs_wants_bar()
            render_category_stats()

        elif choice == "6":
            from core.simulator import get_simulation_history
            from ui.panels import render_simulation_history
            history = get_simulation_history(limit=15)
            render_simulation_history(history)

        elif choice == "7":
            from ui.prompts import prompt_setup
            prompt_setup()

        # Setelah setiap aksi, jeda sebelum kembali ke menu
        Prompt.ask(
            "\n  [dim]Tekan Enter untuk kembali ke menu[/]",
            default="",
            show_default=False,
        )
        console.clear()


# ─── FIRST RUN ────────────────────────────────────────────────────────────────

def _handle_first_run() -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    console.print()
    console.print(Panel(
        Text.assemble(
            ("Selamat datang di FICSY! 🎉\n\n", "bold cyan"),
            ("Sepertinya ini pertama kali kamu menggunakan FICSY.\n", "white"),
            ("Mari atur profil keuangan kamu dulu.\n\n", "white"),
            ("(Hanya perlu dilakukan sekali)", "dim"),
        ),
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()

    from ui.prompts import prompt_setup
    prompt_setup()

    from rich.console import Console
    Console().clear()


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _check_dependencies()

    if _check_first_run():
        _handle_first_run()

    _run_menu_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Keluar. Sampai jumpa! 👋\n")
        sys.exit(0)
    except Exception as e:
        from rich.console import Console
        Console().print(
            f"\n  [bold red]❌ Error:[/] {e}\n"
            f"  [dim]Coba jalankan ulang atau hubungi developer.[/]\n"
        )
        sys.exit(1)
