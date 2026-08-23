from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__
from .ai import check_ollama_connection, classify_text
from .envcheck import ensure_ready, first_run_wizard
from .parser import extract_text, get_supported_extensions
from .rules import (
    GLOBAL_CONFIG_FILE,
    apply_classification,
    classify_by_keywords,
    find_config_file,
    load_config,
    save_config_paths,
    undo_all,
    undo_last,
)

app = typer.Typer(
    name="dclassify",
    help="A Privacy-First, Local-AI Powered CLI Tool for Smart Document Organization.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold]doc-classifier-cli[/bold] v{__version__}")
        raise typer.Exit()


def _resolve_config_path(explicit: Optional[str] = None) -> Optional[Path]:
    """Config chain: --config flag -> ./config.yaml -> ~/.doc-classifier/config.yaml."""
    return find_config_file(explicit=explicit)


def _load_resolved_config(
    explicit: Optional[str] = None,
) -> tuple[object, Optional[Path]]:
    from .models import Config

    path = _resolve_config_path(explicit)
    if path is None:
        return Config(), None
    return load_config(str(path)), path


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        _menu_loop()


@app.command()
def classify(
    path: Optional[str] = typer.Argument(
        None, help="File or directory path to classify (default: source_dir from config)"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Config YAML path (default: auto-detect)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Base output directory (default: output_dir from config)"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override AI model"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without moving files"),
    local_only: bool = typer.Option(
        True, "--local-only/--allow-cloud", help="Block cloud API calls"
    ),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Process directories recursively"
    ),
) -> None:
    """Classify and organize documents using local AI."""
    exit_code = run_classify(
        path=path,
        config_file=config_file,
        output_dir=output_dir,
        model=model,
        dry_run=dry_run,
        local_only=local_only,
        recursive=recursive,
    )
    if exit_code:
        raise typer.Exit(exit_code)


def run_classify(
    path: Optional[str] = None,
    config_file: Optional[str] = None,
    output_dir: Optional[str] = None,
    model: Optional[str] = None,
    dry_run: bool = False,
    local_only: bool = True,
    recursive: bool = False,
) -> int:
    """Classify and organize documents using local AI. Returns process exit code."""
    config, resolved_path = _load_resolved_config(config_file)
    if resolved_path is None:
        console.print(
            "[bold red]Config belum ada.[/bold red] Jalankan [cyan]dclassify[/cyan] "
            "(tanpa perintah) sekali untuk setup pertama kali."
        )
        return 1
    if config_file and not Path(config_file).exists():
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config_file}")
        return 1
    ai_model = model or config.classification.default_model

    target_path = path or config.paths.source_dir
    base_output = output_dir or config.paths.output_dir or "."

    if target_path is None:
        console.print(
            "[bold red]Folder sumber belum diatur.[/bold red] Atur via menu opsi [1] "
            "atau isi 'paths.source_dir' di config.yaml."
        )
        return 1

    console.print(
        Panel(
            f"[bold green]doc-classifier-cli[/bold green] v{__version__}\n"
            f"Model: [cyan]{ai_model}[/cyan] | Dry-run: [yellow]{dry_run}[/yellow] | "
            f"Local-only: {local_only}\n"
            f"Source: [cyan]{target_path}[/cyan] | Output: [cyan]{base_output}[/cyan]",
            title="Document Classifier",
        )
    )

    target = Path(target_path)
    if not target.exists():
        console.print(f"[bold red]Error:[/bold red] Path not found: {target_path}")
        return 1

    files: list[Path] = []
    supported = get_supported_extensions()

    if target.is_file():
        if target.suffix.lower() in supported:
            files.append(target)
        else:
            console.print(f"[bold red]Error:[/bold red] Unsupported file type: {target.suffix}")
            return 1
    elif target.is_dir():
        glob_pattern = "**/*" if recursive else "*"
        files = [
            f
            for f in target.glob(glob_pattern)
            if f.is_file() and f.suffix.lower() in supported
        ]

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        return 0

    console.print(f"\nFound [bold]{len(files)}[/bold] file(s) to process.\n")

    results_table = Table(title="Classification Results")
    results_table.add_column("#", style="dim", width=4)
    results_table.add_column("Original File", style="cyan", max_width=30)
    results_table.add_column("Category", style="green")
    results_table.add_column("Type", style="yellow")
    results_table.add_column("New Name", style="magenta", max_width=40)
    results_table.add_column("Status", style="bold")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing files...", total=len(files))

        for idx, file_path in enumerate(files, 1):
            progress.update(task, description=f"Processing: {file_path.name}")

            text = extract_text(file_path)

            classification = None
            if text:
                classification = classify_text(
                    text,
                    model=ai_model,
                    temperature=config.classification.temperature,
                    local_only=local_only,
                )

            if not classification and config.classification.fallback_keywords:
                classification = classify_by_keywords(
                    text or "", config.taxonomy, original_name=file_path.name
                )
                operation = apply_classification(
                    file_path, classification, config, output_dir=base_output, dry_run=dry_run
                )
                keyword_status = (
                    "[yellow]KEYWORD[/yellow]"
                    if operation.action == "move"
                    else "[yellow]DRY-RUN[/yellow]"
                )
                results_table.add_row(
                    str(idx),
                    file_path.name,
                    classification.main_category,
                    "keyword",
                    Path(operation.target_path).name,
                    keyword_status,
                )
                progress.advance(task)
                continue

            if not classification:
                results_table.add_row(
                    str(idx), file_path.name, "-", "-", "-",
                    "[red]AI error - jalankan dclassify untuk cek Ollama[/red]",
                )
                progress.advance(task)
                continue

            operation = apply_classification(
                file_path, classification, config, output_dir=base_output, dry_run=dry_run
            )

            status = (
                "[green]OK[/green]"
                if operation.action == "move"
                else "[yellow]DRY-RUN[/yellow]"
            )
            results_table.add_row(
                str(idx),
                file_path.name,
                classification.main_category,
                classification.document_type,
                Path(operation.target_path).name,
                status,
            )
            progress.advance(task)

    console.print()
    console.print(results_table)

    if dry_run:
        console.print("\n[yellow]Dry-run mode — no files were moved.[/yellow]")
    else:
        console.print("\n[bold green]Done![/bold green] Files have been organized.")

    return 0


@app.command()
def undo(
    all_ops: bool = typer.Option(False, "--all", help="Undo all recorded operations"),
) -> None:
    """Undo the last (or all) file operations."""
    _undo(all_ops)


def _undo(all_ops: bool = False) -> None:
    if all_ops:
        undone = undo_all()
        if undone:
            console.print(f"[green]Undone {len(undone)} operation(s).[/green]")
        else:
            console.print("[yellow]No operations to undo.[/yellow]")
    else:
        op = undo_last()
        if op:
            console.print(
                f"[green]Undo:[/green] {Path(op.target_path).name} -> {Path(op.original_path).name}"
            )
        else:
            console.print("[yellow]No operations to undo.[/yellow]")


@app.command()
def check() -> None:
    """Check if Ollama / AI model is reachable."""
    exit_code = _check_connection()
    if exit_code:
        raise typer.Exit(exit_code)


def _check_connection() -> int:
    config, _ = _load_resolved_config()
    model = config.classification.default_model
    console.print(f"Checking connection to [cyan]{model}[/cyan]...")

    if check_ollama_connection(model):
        console.print("[bold green]OK![/bold green] Model is reachable.")
        return 0

    console.print("[bold red]FAIL![/bold red] Cannot reach model. Is Ollama running?")
    return 1


@app.command()
def menu() -> None:
    """Open the interactive main menu."""
    _menu_loop()


def _menu_loop() -> None:
    config, config_path = _load_resolved_config()
    if config_path is None:
        config = first_run_wizard(console)
        console.print()
        ensure_ready(console, config.classification.default_model)

    while True:
        source_label = str(config_path) if config_path else GLOBAL_CONFIG_FILE
        console.print(
            Panel(
                f"[bold green]doc-classifier-cli[/bold green] v{__version__}\n"
                "Privacy-First, Local-AI Powered Document Organizer\n"
                f"Config: [dim]{source_label}[/dim]",
                title="Main Menu",
            )
        )
        console.print("[bold]Choose an option:[/bold]")
        console.print("  [cyan][1][/cyan] Configure source & target folders")
        console.print("  [cyan][2][/cyan] Check AI connection (Ollama)")
        console.print("  [cyan][3][/cyan] Run document cleanup")
        console.print("  [cyan][4][/cyan] Undo last operation")
        console.print("  [cyan][5][/cyan] Open Web UI")
        console.print("  [cyan][0][/cyan] Exit")

        choice = Prompt.ask("Choose", choices=["0", "1", "2", "3", "4", "5"], default="0")

        if choice == "1":
            _menu_configure_paths()
        elif choice == "2":
            _check_connection()
        elif choice == "3":
            _menu_run_classify()
        elif choice == "4":
            _menu_undo()
        elif choice == "5":
            _menu_web_ui()
        else:
            console.print("[green]Goodbye![/green]")
            break
        console.print()


def _menu_configure_paths() -> None:
    config, config_path = _load_resolved_config()
    target_file = str(config_path) if config_path else str(GLOBAL_CONFIG_FILE)

    default_source = config.paths.source_dir or str(Path.home() / "Downloads")
    default_output = config.paths.output_dir or "."

    console.print("\n[bold]Configure folders[/bold]")
    source = Prompt.ask("Source folder", default=default_source)
    output = Prompt.ask("Target folder", default=default_output)

    save_config_paths(source_dir=source, output_dir=output, config_path=target_file)
    console.print(f"[green]Paths updated successfully.[/green] [dim]({target_file})[/dim]")


def _menu_run_classify() -> None:
    dry_run = Confirm.ask("Dry-run (simulate only, no files moved)?", default=False)
    code = run_classify(dry_run=dry_run)
    if code:
        console.print("[red]Cleanup failed. See error above.[/red]")


def _menu_undo() -> None:
    all_ops = Confirm.ask("Undo ALL operations instead of only the last one?", default=False)
    _undo(all_ops)


def _menu_web_ui() -> None:
    web_path = Path(__file__).resolve().parent / "web.py"
    console.print(f"Launching Web UI: [cyan]{web_path}[/cyan]")
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(web_path)],
            check=False,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Web UI closed.[/yellow]")


if __name__ == "__main__":
    app()
