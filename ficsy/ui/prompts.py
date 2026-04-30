"""
FICSY — Interactive Prompts
Semua alur input interaktif user via terminal.

Perubahan v1.2:
  - Setiap prompt punya opsi [B] Kembali di setiap langkah
  - Decision Lab mendukung multi-skenario sekaligus (keranjang simulasi)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box

from core.transaction import add_transaction, get_transactions, TransactionError
from core.simulator import (
    run_simulation,
    get_preset_by_id,
    PRESET_SCENARIOS,
    SimulatorError,
)
from core.storage import load, save, init_if_empty
from core.ai_tagger import TagResult, TagStatus, Category


# ─── SENTINEL: sinyal "user memilih kembali" ──────────────────────────────────

class _Back(Exception):
    """Dilempar ketika user memilih kembali di tengah prompt."""
    pass


# ─── LAZY UI IMPORT ───────────────────────────────────────────────────────────

def _get_ui():
    from ui.dashboard import (
        render_transaction_added,
        render_simulation_result,
        render_preset_scenarios,
        render_transaction_list,
        render_error,
        render_success,
        render_welcome,
        console,
        C_MUTED,
        C_WARN,
        _fmt_rp,
    )
    return (
        render_transaction_added, render_simulation_result,
        render_preset_scenarios,  render_transaction_list,
        render_error,             render_success,
        render_welcome,           console,
        C_MUTED,                  C_WARN,
        _fmt_rp,
    )


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> float | None:
    """Parse nominal user. Toleran: 15000, 15rb, 15k, 15.000, 1jt."""
    raw = raw.strip().lower().replace(".", "").replace(",", "")
    multiplier = 1
    for suffix, mult in [
        ("juta", 1_000_000), ("jt", 1_000_000),
        ("ribu", 1_000), ("rb", 1_000), ("k", 1_000),
    ]:
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            multiplier = mult
            break
    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def _ask(prompt_text: str, *, back_label: str = "B = Kembali", **kwargs) -> str:
    """
    Wrapper Prompt.ask yang selalu menampilkan opsi kembali.
    Melempar _Back jika user mengetik 'b' atau 'B'.
    """
    hint = f"[dim]({back_label})[/]"
    raw = Prompt.ask(f"  {prompt_text} {hint}", **kwargs).strip()
    if raw.lower() == "b":
        raise _Back()
    return raw


def _ask_amount(prompt_text: str) -> float:
    """
    Loop minta nominal sampai valid atau user ketik 'b' untuk kembali.
    Melempar _Back jika user ketik 'b'.
    """
    (_, _, _, _, render_error, _, _, console, C_MUTED, _, _) = _get_ui()
    console.print(f"  [dim](ketik 'b' untuk kembali)[/]")
    while True:
        raw = Prompt.ask(f"  {prompt_text}").strip()
        if raw.lower() == "b":
            raise _Back()
        amount = _parse_amount(raw)
        if amount is None:
            render_error("Format tidak valid.", "Contoh: 15000, 15rb, 15k")
            continue
        if amount <= 0:
            render_error("Nominal harus lebih dari 0.")
            continue
        return amount


# ─── CALLBACK KONFIRMASI KATEGORI AI ─────────────────────────────────────────

def prompt_confirm_category(tag_result: TagResult) -> str:
    """
    Callback on_uncertain untuk add_transaction().
    Dipanggil ketika AI ragu. Tidak ada opsi kembali di sini
    karena transaksi sudah di-halfway — user harus pilih salah satu.
    """
    (_, _, _, _, render_error, _, _, console,
     C_MUTED, C_WARN, _fmt_rp) = _get_ui()

    console.print()

    if tag_result.is_fallback:
        console.print(Panel(
            f"[{C_WARN}]⚠️  AI tidak bisa menentukan kategori untuk:[/]\n"
            f"[bold]\"{tag_result.raw_input}\"[/]\n\n"
            f"[{C_MUTED}]Pilih kategori secara manual.[/]",
            border_style="yellow", padding=(1, 2),
        ))
    else:
        console.print(Panel(
            f"[{C_WARN}]🤔 AI kurang yakin — confidence: {tag_result.confidence_pct()}[/]\n\n"
            f"[{C_MUTED}]Saran AI :[/] [bold]{tag_result.category.value}[/]\n"
            f"[{C_MUTED}]Alasan   :[/] {tag_result.reason or '—'}\n\n"
            f"[{C_MUTED}]Konfirmasi kategori:[/]",
            border_style="yellow", padding=(1, 2),
        ))

    console.print("  [bold][1][/] Needs  [dim](kebutuhan pokok)[/]")
    console.print("  [bold][2][/] Wants  [dim](keinginan / hiburan)[/]")
    console.print()

    default = "1" if tag_result.category == Category.NEEDS else "2"
    while True:
        choice = Prompt.ask("  Pilihan", choices=["1", "2"], default=default).strip()
        if choice == "1":
            return "Needs"
        if choice == "2":
            return "Wants"


# ─── PROMPT: TAMBAH TRANSAKSI ─────────────────────────────────────────────────

def prompt_add_transaction() -> None:
    """
    Alur tambah transaksi dengan opsi [B] Kembali di setiap langkah.
    """
    (render_transaction_added, _, _, _, render_error,
     _, _, console, C_MUTED, C_WARN, _fmt_rp) = _get_ui()

    console.print()
    console.print(Rule("[bold cyan]➕ Tambah Transaksi[/]", style="cyan"))
    console.print()

    try:
        # ── Step 1: Tipe ──────────────────────────────────────────────────────
        console.print("  [bold][1][/] Pengeluaran  [dim](expense)[/]")
        console.print("  [bold][2][/] Pemasukan    [dim](income)[/]")
        console.print()

        type_choice = _ask(
            "Tipe transaksi",
            back_label="B = Kembali ke menu",
            choices=["1", "2", "b", "B"],
            default="1",
        )
        tx_type = "expense" if type_choice == "1" else "income"

        # ── Step 2: Deskripsi ─────────────────────────────────────────────────
        console.print()
        if tx_type == "expense":
            console.print(f"  [{C_MUTED}]Contoh: beli boba, bayar angkot, jajan kantin[/]")
        else:
            console.print(f"  [{C_MUTED}]Contoh: uang jajan minggu ini, transferan ayah[/]")
        console.print(f"  [dim](ketik 'b' untuk kembali)[/]")

        while True:
            description = Prompt.ask("  Deskripsi").strip()
            if description.lower() == "b":
                raise _Back()
            if description:
                break
            render_error("Deskripsi tidak boleh kosong.")

        # ── Step 3: Nominal ───────────────────────────────────────────────────
        console.print()
        console.print(f"  [{C_MUTED}]Format: 15000 · 15rb · 15k · 15.000[/]")
        amount = _ask_amount("Nominal (Rp)")

        # ── Step 4–5: AI tagging ──────────────────────────────────────────────
        if tx_type == "expense":
            console.print()
            console.print(f"  [{C_MUTED}]🤖 Menganalisis kategori...[/]")

        tx = add_transaction(
            description=description,
            amount=amount,
            tx_type=tx_type,
            on_uncertain=prompt_confirm_category,
        )

    except _Back:
        console.print(f"\n  [{C_MUTED}]↩ Kembali ke menu.[/]\n")
        return
    except TransactionError as e:
        render_error(str(e))
        return
    except Exception as e:
        render_error(f"Terjadi kesalahan: {e}")
        return

    data = load()
    render_transaction_added(tx, data["profile"]["current_balance"])


# ─── PROMPT: DECISION LAB (MULTI-SKENARIO) ────────────────────────────────────

def prompt_lab() -> None:
    """
    Decision Lab dengan dukungan multi-skenario.

    Alur:
      1. User menambah skenario ke "keranjang" (bisa lebih dari satu)
      2. Setiap skenario ditampilkan di keranjang beserta total dampak
      3. User bisa tambah lagi, hapus, atau langsung jalankan semua
      4. Simulasi dijalankan sekali dengan total gabungan semua skenario
      5. Tampilkan hasil + rincian skenario yang dipilih
    """
    (_, render_simulation_result, render_preset_scenarios,
     _, render_error, _, _, console, C_MUTED, C_WARN, _fmt_rp) = _get_ui()

    console.print()
    console.print(Rule("[bold cyan]🔬 Decision Lab[/]", style="cyan"))
    console.print(
        f"  [{C_MUTED}]Pilih satu atau lebih skenario — "
        f"data asli TIDAK akan berubah.[/]"
    )
    console.print()

    # Peringatan data sedikit
    data = load()
    tx_count = len(data.get("transactions", []))
    if tx_count < 3:
        console.print(Panel(
            f"[{C_WARN}]⚠️  Baru ada {tx_count} transaksi.\n"
            f"Hasil lebih akurat setelah minimal 3 transaksi.[/]",
            border_style="yellow", padding=(0, 2),
        ))
        console.print()

    # ── Keranjang skenario ────────────────────────────────────────────────────
    # Format: [{"name": str, "amount": float, "emoji": str}, ...]
    keranjang: list[dict] = []

    def _render_keranjang() -> None:
        """Tampilkan isi keranjang dan total dampak."""
        if not keranjang:
            console.print(f"  [{C_MUTED}]Keranjang masih kosong.[/]\n")
            return

        total = sum(s["amount"] for s in keranjang)

        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold cyan",
            show_edge=False,
            padding=(0, 1),
        )
        table.add_column("No",       width=4,  justify="right", style="dim")
        table.add_column("Skenario", width=32)
        table.add_column("Dampak",   width=14, justify="right")

        for i, s in enumerate(keranjang, 1):
            table.add_row(
                str(i),
                f"{s['emoji']} {s['name']}",
                f"[yellow]-{_fmt_rp(s['amount'])}[/]",
            )

        # Baris total
        table.add_row("", "[bold]TOTAL DAMPAK[/]", f"[bold red]-{_fmt_rp(total)}[/]")

        console.print(Panel(
            table,
            title="[bold cyan]🛒 Keranjang Simulasi[/]",
            border_style="cyan",
            padding=(0, 1),
        ))

    # ── Loop keranjang ────────────────────────────────────────────────────────
    while True:
        _render_keranjang()

        # Menu keranjang
        console.print("  [bold][A][/] Tambah skenario preset")
        console.print("  [bold][K][/] Tambah skenario kustom")
        if keranjang:
            console.print("  [bold][H][/] Hapus skenario dari keranjang")
            console.print("  [bold][J][/] Jalankan simulasi sekarang")
        console.print("  [bold][B][/] Kembali ke menu")
        console.print()

        valid = ["a", "k", "b"]
        if keranjang:
            valid += ["h", "j"]

        aksi = Prompt.ask(
            "  Pilih aksi",
            choices=valid + [c.upper() for c in valid],
        ).strip().lower()

        # ── Kembali ──────────────────────────────────────────────────────────
        if aksi == "b":
            console.print(f"\n  [{C_MUTED}]↩ Kembali ke menu.[/]\n")
            return

        # ── Tambah preset ─────────────────────────────────────────────────────
        elif aksi == "a":
            console.print()
            render_preset_scenarios()

            preset_ids   = [str(p["id"]) for p in PRESET_SCENARIOS]
            valid_preset = preset_ids + [c.upper() for c in preset_ids] + ["b", "B"]

            console.print(f"  [dim](ketik 'b' untuk kembali)[/]")
            raw_choice = Prompt.ask(
                "  Pilih nomor skenario",
                choices=valid_preset,
            ).strip()

            if raw_choice.lower() == "b":
                console.print()
                continue

            preset = get_preset_by_id(int(raw_choice))
            if not preset:
                render_error("Skenario tidak ditemukan.")
                continue

            # Cek duplikat
            already = any(s["name"] == preset["name"] for s in keranjang)
            if already:
                console.print(Panel(
                    f"[{C_WARN}]⚠️  '{preset['name']}' sudah ada di keranjang.[/]",
                    border_style="yellow", padding=(0, 2),
                ))
                console.print()
                continue

            keranjang.append({
                "name":   preset["name"],
                "amount": float(preset["amount"]),
                "emoji":  preset["emoji"],
            })
            console.print(
                f"\n  [green]✅ '{preset['emoji']} {preset['name']}' "
                f"ditambahkan ke keranjang.[/]\n"
            )

        # ── Tambah kustom ─────────────────────────────────────────────────────
        elif aksi == "k":
            console.print()
            try:
                console.print(f"  [dim](ketik 'b' untuk kembali)[/]")
                while True:
                    nama = Prompt.ask("  Nama skenario kustom").strip()
                    if nama.lower() == "b":
                        raise _Back()
                    if nama:
                        break
                    render_error("Nama tidak boleh kosong.")

                console.print()
                console.print(f"  [{C_MUTED}]Format: 50000, 50rb, 50k[/]")
                impact = _ask_amount("Nominal pengeluaran (Rp)")

                keranjang.append({
                    "name":   nama,
                    "amount": impact,
                    "emoji":  "✏️ ",
                })
                console.print(
                    f"\n  [green]✅ '{nama}' ditambahkan ke keranjang.[/]\n"
                )

            except _Back:
                console.print()
                continue

        # ── Hapus dari keranjang ──────────────────────────────────────────────
        elif aksi == "h":
            if not keranjang:
                continue

            console.print()
            for i, s in enumerate(keranjang, 1):
                console.print(f"  [bold][{i}][/] {s['emoji']} {s['name']}")
            console.print(f"  [bold][B][/] Batal")
            console.print()

            valid_del = [str(i) for i in range(1, len(keranjang) + 1)] + ["b", "B"]
            raw_del = Prompt.ask(
                "  Hapus nomor berapa",
                choices=valid_del,
            ).strip()

            if raw_del.lower() == "b":
                console.print()
                continue

            idx = int(raw_del) - 1
            removed = keranjang.pop(idx)
            console.print(
                f"\n  [dim]🗑  '{removed['name']}' dihapus dari keranjang.[/]\n"
            )

        # ── Jalankan simulasi ─────────────────────────────────────────────────
        elif aksi == "j":
            if not keranjang:
                render_error("Keranjang masih kosong.")
                continue

            total_impact = sum(s["amount"] for s in keranjang)
            jumlah       = len(keranjang)

            # Nama gabungan untuk metadata
            if jumlah == 1:
                combined_name = keranjang[0]["name"]
            else:
                nama_list     = ", ".join(s["name"] for s in keranjang)
                combined_name = f"{jumlah} skenario: {nama_list}"

            console.print()
            console.print(Panel(
                Text.assemble(
                    ("Ringkasan Simulasi\n\n", "bold"),
                    *[
                        (f"  {s['emoji']} {s['name']} "
                         f"— {_fmt_rp(s['amount'])}\n", "white")
                        for s in keranjang
                    ],
                    ("\nTotal dampak: ", "dim white"),
                    (f"-{_fmt_rp(total_impact)}", "bold red"),
                ),
                border_style="cyan",
                padding=(1, 2),
            ))

            if not Confirm.ask("\n  Jalankan simulasi dengan skenario di atas?", default=True):
                console.print()
                continue

            console.print()
            console.print(f"  [{C_MUTED}]⚙️  Menghitung dampak gabungan...[/]")

            try:
                result = run_simulation(combined_name, total_impact)
            except SimulatorError as e:
                render_error(str(e))
                continue
            except Exception as e:
                render_error(f"Simulasi gagal: {e}")
                continue

            render_simulation_result(result)

            # Setelah simulasi — reset atau tambah lagi
            console.print("  [bold][1][/] Simulasi skenario baru  [dim](keranjang dikosongkan)[/]")
            console.print("  [bold][2][/] Tambah skenario ke keranjang saat ini")
            console.print("  [bold][0][/] Kembali ke menu")
            console.print()

            next_aksi = Prompt.ask(
                "  Pilih",
                choices=["1", "2", "0"],
                default="0",
            )

            if next_aksi == "0":
                console.print(f"\n  [{C_MUTED}]↩ Kembali ke menu.[/]\n")
                return
            elif next_aksi == "1":
                keranjang.clear()
                console.print(f"\n  [dim]Keranjang dikosongkan.[/]\n")
            # next_aksi == "2" → lanjut loop dengan keranjang yang sama


# ─── PROMPT: SETUP PROFIL ─────────────────────────────────────────────────────

def prompt_setup() -> None:
    """Setup atau update profil dengan opsi kembali."""
    (_, _, _, _, render_error, render_success,
     render_welcome, console, C_MUTED, _, _fmt_rp) = _get_ui()

    console.print()
    console.print(Rule("[bold cyan]⚙️  Setup Profil[/]", style="cyan"))
    console.print()

    is_new = init_if_empty()

    if is_new:
        render_welcome()
        console.print(f"  [{C_MUTED}]Belum ada profil. Mari atur keuangan kamu.[/]\n")
    else:
        data = load()
        p = data["profile"]
        console.print(f"  [{C_MUTED}]Profil saat ini:[/]")
        console.print(f"  Uang jajan bulanan : [bold]{_fmt_rp(p['monthly_allowance'])}[/]")
        console.print(f"  Saldo saat ini     : [bold]{_fmt_rp(p['current_balance'])}[/]")
        console.print(f"  Reset tanggal      : [bold]{p['reset_day']} tiap bulan[/]")
        console.print()

        if not Confirm.ask("  Update profil?", default=True):
            console.print(f"\n  [{C_MUTED}]↩ Tidak ada perubahan.[/]\n")
            return

    data    = load()
    profile = data["profile"]

    try:
        # ── Uang jajan ────────────────────────────────────────────────────────
        console.print()
        console.print(
            f"  [{C_MUTED}]Berapa total uang jajan bulanan kamu?[/]\n"
            f"  [{C_MUTED}]Format: 500000, 500rb, 500k[/]"
        )
        allowance = _ask_amount("Uang jajan bulanan (Rp)")

        # ── Saldo saat ini ────────────────────────────────────────────────────
        console.print()
        console.print(
            f"  [{C_MUTED}]Berapa uang yang kamu punya sekarang?[/]\n"
            f"  [{C_MUTED}](Cek dompet + rekening)[/]"
        )
        console.print(f"  [dim](ketik 'b' untuk kembali)[/]")

        while True:
            raw = Prompt.ask(
                "  Saldo saat ini (Rp)",
                default=str(int(profile.get("current_balance") or int(allowance))),
            ).strip()
            if raw.lower() == "b":
                raise _Back()
            balance = _parse_amount(raw)
            if balance is not None and balance >= 0:
                break
            render_error("Masukkan angka 0 atau lebih.")

        # ── Tanggal reset ─────────────────────────────────────────────────────
        console.print()
        console.print(f"  [{C_MUTED}]Tanggal berapa uang jajan masuk tiap bulan? (1–28)[/]")
        console.print(f"  [dim](ketik 'b' untuk kembali)[/]")

        while True:
            raw_day = Prompt.ask(
                "  Tanggal reset",
                default=str(profile.get("reset_day", 1)),
            ).strip()
            if raw_day.lower() == "b":
                raise _Back()
            try:
                reset_day = int(raw_day)
                if 1 <= reset_day <= 28:
                    break
                render_error("Masukkan angka antara 1 dan 28.")
            except ValueError:
                render_error("Input tidak valid.")

    except _Back:
        console.print(f"\n  [{C_MUTED}]↩ Setup dibatalkan.[/]\n")
        return

    # ── Konfirmasi & simpan ───────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold]Ringkasan Profil:[/]\n\n"
        f"  Uang jajan bulanan  : [bold cyan]{_fmt_rp(allowance)}[/]\n"
        f"  Saldo awal          : [bold cyan]{_fmt_rp(balance)}[/]\n"
        f"  Reset tiap tanggal  : [bold cyan]{reset_day}[/]",
        border_style="cyan", padding=(1, 2),
    ))

    if not Confirm.ask("\n  Simpan?", default=True):
        console.print(f"\n  [{C_MUTED}]↩ Setup dibatalkan.[/]\n")
        return

    profile["monthly_allowance"] = allowance
    profile["current_balance"]   = balance
    profile["reset_day"]         = reset_day
    data["profile"]              = profile
    save(data)

    render_success("Profil disimpan!")


# ─── PROMPT: LIHAT RIWAYAT ────────────────────────────────────────────────────

def prompt_list(limit: int = 20) -> None:
    """Tampilkan riwayat transaksi dengan opsi filter dan kembali."""
    (_, _, _, render_transaction_list,
     _, _, _, console, C_MUTED, _, _) = _get_ui()

    console.print()
    console.print("  [bold][1][/] Semua transaksi")
    console.print("  [bold][2][/] Pengeluaran saja")
    console.print("  [bold][3][/] Pemasukan saja")
    console.print("  [bold][B][/] Kembali ke menu")
    console.print()

    choice = Prompt.ask(
        "  Filter",
        choices=["1", "2", "3", "b", "B"],
        default="1",
    ).strip().lower()

    if choice == "b":
        console.print(f"\n  [{C_MUTED}]↩ Kembali ke menu.[/]\n")
        return

    tx_type_map  = {"1": None, "2": "expense", "3": "income"}
    transactions = get_transactions(limit=limit, tx_type=tx_type_map[choice])
    render_transaction_list(transactions)
