"""Environment health-check and first-run guided setup.

Anti-loss principle:
- Regardless of system state, user always gets ONE clear next step.
- No silent downloads; all heavy actions require [Y/n] confirmation.
- Setup can be interrupted at any time; re-running resumes from last position.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .rules import GLOBAL_CONFIG_FILE, load_config, write_default_config

logger = logging.getLogger(__name__)

OLLAMA_API = "http://localhost:11434"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"
TESSERACT_DOWNLOAD_URL = "https://github.com/UB-Mannheim/tesseract/wiki"

OLLAMA_WIN_PATHS = [
    Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
]


def _find_ollama_exe() -> Optional[str]:
    found = shutil.which("ollama")
    if found:
        return found
    for p in OLLAMA_WIN_PATHS:
        if p.exists():
            return str(p)
    return None


@dataclass
class EnvStatus:
    ollama_running: bool = False
    model_installed: bool = False
    model_name: str = ""
    tesseract_found: bool = False

    @property
    def all_critical_ok(self) -> bool:
        return self.ollama_running and self.model_installed


def check_ollama_api() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_API}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as _resp:
            return True
    except Exception:
        return False


def check_model_installed(model: str) -> bool:
    """Check if a specific model is installed in Ollama."""
    bare = _strip_ollama_prefix(model)
    try:
        req = urllib.request.Request(f"{OLLAMA_API}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for m in data.get("models", []):
            if m.get("name", "").startswith(bare):
                return True
        return False
    except Exception:
        return False


def check_tesseract() -> bool:
    return shutil.which("tesseract") is not None


def check_environment(model: str) -> EnvStatus:
    ollama_ok = check_ollama_api()
    model_ok = check_model_installed(model) if ollama_ok else False
    tesseract_ok = check_tesseract()
    return EnvStatus(
        ollama_running=ollama_ok,
        model_installed=model_ok,
        model_name=model,
        tesseract_found=tesseract_ok,
    )


def render_status(console: Console, status: EnvStatus) -> None:
    table = Table(title="Environment Check", show_header=False)
    table.add_column("Component", style="bold", width=18)
    table.add_column("Status")

    table.add_row(
        "Ollama",
        "[green]Running[/green]"
        if status.ollama_running
        else "[red]Not running / not installed[/red]",
    )
    if status.ollama_running:
        table.add_row(
            f"Model {status.model_name}",
            "[green]Ready[/green]" if status.model_installed else "[red]Not installed[/red]",
        )
    table.add_row(
        "Tesseract OCR",
        "[green]Detected[/green]"
        if status.tesseract_found
        else "[yellow]Not found (optional, for scanned images)[/yellow]",
    )
    console.print(table)


def _strip_ollama_prefix(model: str) -> str:
    return model.removeprefix("ollama/").removeprefix("ollama:")


def _offer_winget_ollama_install(console: Console) -> bool:
    """Offer automatic Ollama install via winget. Returns True if install was attempted."""
    if not shutil.which("winget"):
        return False

    console.print("\n[bold]Ollama is not installed on this system.[/bold]")
    if not Confirm.ask(
        "Install Ollama automatically via winget now? (±700 MB)", default=True
    ):
        return False

    console.print("[cyan]Running winget install Ollama.Ollama ...[/cyan]")
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
            console.print("[green]Winget install complete.[/green]")
            return True
        console.print(f"[yellow]winget exited with code {result.returncode}.[/yellow]")
    except Exception as exc:
        logger.warning("winget invocation failed: %s", exc)
        console.print(f"[yellow]Failed to invoke winget: {exc}[/yellow]")
    return False


def _guide_manual_ollama(console: Console) -> None:
    console.print("\n[bold]Manual Ollama installation guide:[/bold]")
    console.print(f"  1. Open download page: {OLLAMA_DOWNLOAD_URL}")
    console.print("  2. Install like a normal Windows application")
    console.print("  3. Come back here and re-check")
    try:
        webbrowser.open(OLLAMA_DOWNLOAD_URL)
        console.print("[dim](Download page opened in browser)[/dim]")
    except Exception:
        pass


def _offer_model_pull(console: Console, status: EnvStatus) -> None:
    bare_model = _strip_ollama_prefix(status.model_name)
    model_size = "±1 GB" if "1.5b" in bare_model.lower() else "±4.7 GB"
    console.print(f"\n[bold]Model [cyan]{bare_model}[/cyan] is not installed yet.[/bold]")
    if not Confirm.ask(f"Download model now? ({bare_model} {model_size})", default=True):
        console.print(
            "[yellow]Skipped. Run manually anytime:[/yellow] "
            f"[cyan]ollama pull {bare_model}[/cyan]"
        )
        return

    ollama_path = _find_ollama_exe()
    if ollama_path is None:
        console.print(
            "[red]Ollama was installed but its executable is not in PATH.[/red]\n"
            "[yellow]Please close this terminal window, open a new one, "
            "then run dclassify.bat again.[/yellow]"
        )
        return

    console.print(f"[cyan]Running: {ollama_path} pull {bare_model} ...[/cyan]")
    try:
        result = subprocess.run([ollama_path, "pull", bare_model], check=False)
        if result.returncode == 0:
            console.print("[green]Done. Model is ready to use.[/green]")
        else:
            console.print(f"[red]ollama pull failed with code {result.returncode}.[/red]")
    except FileNotFoundError:
        console.print(
            "[red]Ollama executable not found at the expected path.[/red]\n"
            "[yellow]Please close this terminal, open a new one, "
            "then run dclassify.bat again.[/yellow]"
        )


def _guide_tesseract(console: Console) -> None:
    console.print("\n[yellow]Tesseract OCR not found (optional).[/yellow]")
    console.print(
        "Without it, scanned images (.jpg/.png/pdf scan) cannot be read for text."
    )
    if Confirm.ask("Open Tesseract OCR download page?", default=False):
        try:
            webbrowser.open(TESSERACT_DOWNLOAD_URL)
            console.print("[dim](Opened in browser)[/dim]")
        except Exception:
            pass


def run_guided_setup(console: Console, model: str) -> EnvStatus:
    """Interactive anti-loss loop until critical components are OK or user gives up."""
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
            "\n[Enter] Re-check / [s] Skip for now", choices=["", "s"], default=""
        )
        if choice == "s":
            console.print(
                "\n[yellow]Setup deferred. Run[/yellow] [cyan]dclassify[/cyan]"
                "[yellow] anytime to continue — progress is saved.[/yellow]"
            )
            return status


def ensure_ready(console: Console, model: str) -> EnvStatus:
    """Run health check once; guide user only when something is missing."""
    status = check_environment(model)
    if status.all_critical_ok:
        if not status.tesseract_found:
            console.print(
                "[yellow]Note: Tesseract OCR not found - "
                "scanned images will be skipped.[/yellow]"
            )
        return status
    return run_guided_setup(console, model)


def first_run_wizard(console: Console, home_dir=None) -> object:
    """Interactive first-run wizard: ask folders then write global config.

    Returns the loaded Config from the newly written file.
    """
    base_home = Path(home_dir) if home_dir else Path.home()
    default_source = str(base_home / "Downloads")
    default_output = str(Path.home() / "Documents" / "OrganizedDocs")

    console.print("\n[bold cyan]First-time setup detected.[/bold cyan]")
    console.print("We just need two folder paths:\n")

    source = Prompt.ask("SOURCE folder (documents to organize)", default=default_source)
    output = Prompt.ask("TARGET folder (organized archive)", default=default_output)

    config_path = write_default_config(GLOBAL_CONFIG_FILE, source_dir=source, output_dir=output)
    console.print(f"\n[green]Config saved to:[/green] {config_path}")

    return load_config(str(config_path))
