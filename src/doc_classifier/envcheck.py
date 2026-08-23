"""Environment health-check and first-run guided setup.

Prinsip anti-hilang arah:
- APA PUN kondisi sistem, user selalu diberi SATU langkah berikutnya yang jelas.
- Tidak ada download diam-diam; semua aksi berat selalu dikonfirmasi [Y/n] dulu.
- Setup bisa terputus kapan pun; menjalankan ulang akan resume dari posisi terakhir.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import urllib.request
import webbrowser
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .parser import _configure_tesseract
from .rules import GLOBAL_CONFIG_FILE, load_config, write_default_config

logger = logging.getLogger(__name__)

OLLAMA_API = "http://localhost:11434"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"
TESSERACT_DOWNLOAD_URL = "https://github.com/UB-Mannheim/tesseract/wiki"


@dataclass
class EnvStatus:
    ollama_running: bool
    model_installed: bool
    tesseract_found: bool
    model_name: str

    @property
    def all_critical_ok(self) -> bool:
        return self.ollama_running and self.model_installed


def _strip_ollama_prefix(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("ollama/") else model


def _query_ollama_models() -> list[str]:
    """Return list of installed model names, or [] if Ollama unreachable."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_API}/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def check_environment(model: str) -> EnvStatus:
    """Lightweight check: Ollama API reachability, model presence, tesseract.exe."""
    models = _query_ollama_models()
    wanted = _strip_ollama_prefix(model)
    model_installed = any(m == wanted or m.split(":")[0] == wanted.split(":")[0] for m in models)

    return EnvStatus(
        ollama_running=bool(models) or _ping_ollama_root(),
        model_installed=model_installed,
        tesseract_found=_configure_tesseract(),
        model_name=model,
    )


def _ping_ollama_root() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_API}/api/version", timeout=3):
            return True
    except Exception:
        return False


def render_status(console: Console, status: EnvStatus) -> None:
    table = Table(title="Pemeriksaan Lingkungan", show_header=False)
    table.add_column("Komponen", style="bold", width=18)
    table.add_column("Status")

    table.add_row(
        "Ollama",
        "[green]Berjalan[/green]"
        if status.ollama_running
        else "[red]Tidak berjalan / belum terinstall[/red]",
    )
    if status.ollama_running:
        table.add_row(
            f"Model {status.model_name}",
            "[green]Siap[/green]" if status.model_installed else "[red]Belum terpasang[/red]",
        )
    table.add_row(
        "Tesseract OCR",
        "[green]Terdeteksi[/green]"
        if status.tesseract_found
        else "[yellow]Tidak ditemukan (opsional, untuk file scan/gambar)[/yellow]",
    )
    console.print(table)


def _offer_winget_ollama_install(console: Console) -> bool:
    """Offer automatic Ollama install via winget. Returns True if install was attempted."""
    if not shutil.which("winget"):
        return False

    console.print("\n[bold]Ollama belum terinstall di sistem ini.[/bold]")
    if not Confirm.ask(
        "Install Ollama otomatis via winget sekarang? (±700 MB)", default=True
    ):
        return False

    console.print("[cyan]Menjalankan winget install Ollama.Ollama ...[/cyan]")
    try:
        result = subprocess.run(
            [
                "winget",
                "install",
                "--id",
                "Ollama.Ollama",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            check=False,
        )
        if result.returncode == 0:
            console.print("[green]Instalasi winget selesai.[/green]")
            return True
        console.print(f"[yellow]winget keluar dengan kode {result.returncode}.[/yellow]")
    except Exception as exc:
        logger.warning("winget invocation failed: %s", exc)
        console.print(f"[yellow]Gagal memanggil winget: {exc}[/yellow]")
    return False


def _guide_manual_ollama(console: Console) -> None:
    console.print("\n[bold]Panduan pemasangan manual Ollama:[/bold]")
    console.print(f"  1. Buka halaman download : {OLLAMA_DOWNLOAD_URL}")
    console.print("  2. Install seperti aplikasi Windows biasa")
    console.print("  3. Kembali ke sini lalu pilih cek ulang")
    try:
        webbrowser.open(OLLAMA_DOWNLOAD_URL)
        console.print("[dim](Halaman download dibuka otomatis di browser)[/dim]")
    except Exception:
        pass


def _offer_model_pull(console: Console, status: EnvStatus) -> None:
    bare_model = _strip_ollama_prefix(status.model_name)
    console.print(f"\n[bold]Model [cyan]{bare_model}[/cyan] belum terpasang.[/bold]")
    if not Confirm.ask(f"Download model sekarang? ({bare_model} ±4.7 GB)", default=True):
        console.print(
            "[yellow]Lewati. Jalankan manual kapan saja:[/yellow] "
            f"[cyan]ollama pull {bare_model}[/cyan]"
        )
        return

    console.print(f"[cyan]Menjalankan: ollama pull {bare_model} ...[/cyan]")
    try:
        subprocess.run(["ollama", "pull", bare_model], check=False)
    except FileNotFoundError:
        console.print("[red]Perintah 'ollama' tidak ditemukan di PATH.[/red]")
        return
    console.print("[green]Selesai. Model siap digunakan.[/green]")


def _guide_tesseract(console: Console) -> None:
    console.print("\n[yellow]Tesseract OCR tidak ditemukan (opsional).[/yellow]")
    console.print(
        "Tanpa ini, file hasil scan/gambar (.jpg/.png/pdf scan) tidak bisa dibaca teksnya."
    )
    if Confirm.ask("Buka halaman download Tesseract OCR?", default=False):
        try:
            webbrowser.open(TESSERACT_DOWNLOAD_URL)
            console.print("[dim](Dibuka di browser)[/dim]")
        except Exception:
            pass


def run_guided_setup(console: Console, model: str) -> EnvStatus:
    """Interactive anti-lost loop until critical components are OK or user gives up."""
    while True:
        status = check_environment(model)
        render_status(console, status)

        if status.all_critical_ok:
            if not status.tesseract_found:
                _guide_tesseract(console)
                status.tesseract_found = check_environment(model).tesseract_found
            return status

        action_taken = False
        if not status.ollama_running:
            action_taken = _offer_winget_ollama_install(console)
            if not action_taken:
                _guide_manual_ollama(console)
        elif not status.model_installed:
            _offer_model_pull(console, status)
            action_taken = True

        choice = Prompt.ask(
            "\n[Enter] Cek ulang / [s] Selesaikan nanti", choices=["", "s"], default=""
        )
        if choice == "s":
            console.print(
                "\n[yellow]Setup ditunda. Jalankan lagi[/yellow] [cyan]dclassify[/cyan]"
                "[yellow] kapan pun untuk melanjutkan — progres tidak hilang.[/yellow]"
            )
            return status


def ensure_ready(console: Console, model: str) -> EnvStatus:
    """Run health check once; guide user only when something is missing."""
    status = check_environment(model)
    render_status(console, status)
    if status.all_critical_ok:
        if not status.tesseract_found:
            console.print(
                "[yellow]Catatan: Tesseract OCR belum ada - "
                "file scan/gambar akan dilewati.[/yellow]"
            )
        return status
    return run_guided_setup(console, model)


def first_run_wizard(console: Console, home_dir=None) -> object:
    """Interactive first-run wizard: ask folders then write global config.

    Returns the loaded Config from the newly written file.
    """
    from pathlib import Path

    base_home = Path(home_dir) if home_dir else Path.home()
    default_source = str(base_home / "Downloads")
    default_output = str(Path.home() / "Documents" / "ArsipDokumen")

    console.print("\n[bold cyan]Setup pertama kali terdeteksi.[/bold cyan]")
    console.print("Kita hanya perlu tahu dua folder ini:\n")

    source = Prompt.ask("Folder SUMBER dokumen yang mau dirapikan", default=default_source)
    output = Prompt.ask("Folder TUJUAN arsip rapi", default=default_output)

    config_path = write_default_config(GLOBAL_CONFIG_FILE, source_dir=source, output_dir=output)
    console.print(f"\n[green]Config disimpan ke:[/green] {config_path}")

    return load_config(str(config_path))
