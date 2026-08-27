from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__
from .ai import check_ollama_connection
from .envcheck import ensure_ready, first_run_wizard
from .parser import extract_text_metadata, get_supported_extensions, is_media_file
from .rules import (
    GLOBAL_CONFIG_FILE,
    apply_classification,
    classify_by_extension,
    find_config_file,
    generate_title_from_text,
    load_config,
    load_history,
    save_config_paths,
    save_history,
    undo_all,
    undo_last,
    unique_path,
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


def _track_folder_time(
    folder_times: dict[str, tuple[float, int]],
    category: str,
    start: float,
) -> None:
    elapsed = time.time() - start
    cur_time, cur_count = folder_times.get(category, (0.0, 0))
    folder_times[category] = (cur_time + elapsed, cur_count + 1)


def _show_runtime_summary(
    folder_times: dict[str, tuple[float, int]],
    start_time: float,
) -> None:
    total_elapsed = time.time() - start_time
    table = Table(title="Execution Time", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Total Time", style="yellow")
    table.add_column("Files", style="green")
    table.add_column("Average", style="dim")
    for cat, (cat_time, count) in sorted(folder_times.items(), key=lambda x: -x[1][0]):
        avg = cat_time / count if count else 0
        table.add_row(cat, f"{cat_time:.1f}s", str(count), f"{avg:.1f}s")
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_elapsed:.1f}s[/bold]",
        str(sum(c for _, c in folder_times.values())),
        "",
    )
    console.print(table)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold]doc-classifier-cli[/bold] v{__version__}")
        raise typer.Exit()


def _resolve_config_path(explicit: Optional[str] = None) -> Optional[Path]:
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without moving files"),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Process directories recursively"
    ),
) -> None:
    exit_code = run_classify(
        path=path,
        config_file=config_file,
        output_dir=output_dir,
        dry_run=dry_run,
        recursive=recursive,
    )
    if exit_code:
        raise typer.Exit(exit_code)


def run_classify(
    path: Optional[str] = None,
    config_file: Optional[str] = None,
    output_dir: Optional[str] = None,
    dry_run: bool = False,
    recursive: bool = False,
) -> int:
    config, resolved_path = _load_resolved_config(config_file)
    if resolved_path is None:
        console.print(
            "[bold red]No config found.[/bold red] Run [cyan]dclassify[/cyan] "
            "(without arguments) to set up for the first time."
        )
        return 1
    if config_file and not Path(config_file).exists():
        console.print(f"[bold red]Error:[/bold red] Config file not found: {config_file}")
        return 1

    target_path = path or config.paths.source_dir
    base_output = output_dir or config.paths.output_dir or "."

    if target_path is None:
        console.print(
            "[bold red]Source folder not set.[/bold red] Configure via menu option [1] "
            "or fill 'paths.source_dir' in config.yaml."
        )
        return 1

    console.print(
        Panel(
            f"[bold green]doc-classifier-cli[/bold green] v{__version__}\n"
            f"Mode: [cyan]FILE-TYPE + CONTENT NAMING[/cyan] | Dry-run: [yellow]{dry_run}[/yellow]\n"
            f"Source: [cyan]{target_path}[/cyan] | Output: [cyan]{base_output}[/cyan]",
            title="Document Classifier",
        )
    )

    target = Path(target_path)
    if not target.exists():
        console.print(f"[bold red]Error:[/bold red] Path not found: {target_path}")
        return 1

    files: list[Path] = []
    media_files: list[Path] = []
    supported = get_supported_extensions()

    if target.is_file():
        ext = target.suffix.lower()
        if is_media_file(target):
            media_files.append(target)
        elif ext in supported:
            files.append(target)
        else:
            console.print(f"[bold red]Error:[/bold red] Unsupported file type: {target.suffix}")
            return 1
    elif target.is_dir():
        glob_pattern = "**/*" if recursive else "*"
        for f in target.glob(glob_pattern):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if is_media_file(f):
                media_files.append(f)
            elif ext in supported:
                files.append(f)

    total_files = len(files) + len(media_files)
    if not files and not media_files:
        console.print("[yellow]No supported files found.[/yellow]")
        return 0

    n_text = len(files)
    n_media = len(media_files)
    console.print(
        f"\nFound [bold]{n_text}[/bold] file(s) and "
        f"[bold]{n_media}[/bold] media file(s) to process.\n"
    )

    results_table = Table(title="Classification Results")
    results_table.add_column("#", style="dim", width=4)
    results_table.add_column("Original File", style="cyan", max_width=30)
    results_table.add_column("Category", style="green")
    results_table.add_column("New Name", style="magenta", max_width=40)
    results_table.add_column("Status", style="bold")

    start_time = time.time()
    folder_times: dict[str, tuple[float, int]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing files...", total=total_files)

        for idx, file_path in enumerate(files, 1):
            progress.update(task, description=f"Processing: {file_path.name}")
            file_start = time.time()

            category = classify_by_extension(file_path, config.taxonomy)

            title_meta, text = extract_text_metadata(file_path)
            title = title_meta or generate_title_from_text(text, file_path.name)

            operation = apply_classification(
                file_path, category, title, config, output_dir=base_output, dry_run=dry_run
            )
            status = (
                "[green]OK[/green]"
                if operation.action == "move"
                else "[yellow]DRY-RUN[/yellow]"
            )
            results_table.add_row(
                str(idx),
                file_path.name,
                category,
                Path(operation.target_path).name,
                status,
            )
            progress.advance(task)
            _track_folder_time(folder_times, category, file_start)

        for idx, media_path in enumerate(media_files, len(files) + 1):
            progress.update(task, description=f"Media: {media_path.name}")
            file_start = time.time()
            progress.advance(task)

            media_folder = Path(base_output) / "Audio"
            target_name = media_path.name
            media_target = unique_path(media_folder / target_name)

            if not dry_run:
                media_folder.mkdir(parents=True, exist_ok=True)
                shutil.move(str(media_path), str(media_target))
                from .models import FileOperation
                operation = FileOperation(
                    original_path=str(media_path.resolve()),
                    target_path=str(media_target.resolve()),
                    action="move",
                )
                history = load_history()
                history.append(operation)
                save_history(history)

            status = "[blue]MOVED[/blue]" if not dry_run else "[yellow]DRY-RUN[/yellow]"
            results_table.add_row(
                str(idx),
                media_path.name,
                "Audio",
                media_target.name,
                status,
            )
            _track_folder_time(folder_times, "Audio", file_start)

    console.print()
    console.print(results_table)

    if dry_run:
        console.print("\n[yellow]Dry-run mode - no files were moved.[/yellow]")
    else:
        console.print("\n[bold green]Done![/bold green] Files have been organized.")

    _show_runtime_summary(folder_times, start_time)

    return 0


@app.command()
def scan(
    path: Optional[str] = typer.Argument(
        None, help="Directory path to scan (default: source_dir from config)"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Config YAML path (default: auto-detect)"
    ),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Scan directories recursively"
    ),
    output_report: Optional[str] = typer.Option(
        None, "--output-report", "-o", help="Export report to JSON file path"
    ),
    output_csv: Optional[str] = typer.Option(
        None, "--output-csv", help="Export report to CSV file path"
    ),
) -> None:
    """Scan and analyze a dataset without moving files."""
    config, resolved_path = _load_resolved_config(config_file)
    if resolved_path is None:
        console.print(
            "[bold red]No config found.[/bold red] Run [cyan]dclassify[/cyan] "
            "(without arguments) to set up for the first time."
        )
        raise typer.Exit(1)

    target_path = path or config.paths.source_dir
    if target_path is None:
        console.print("[bold red]Source folder not set.[/bold red]")
        raise typer.Exit(1)

    target = Path(target_path)
    if not target.exists():
        console.print(f"[bold red]Error:[/bold red] Path not found: {target_path}")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold green]Document Scanner[/bold green] v{__version__}\n"
            f"Path: [cyan]{target}[/cyan]",
            title="Dataset Scanner",
        )
    )

    with console.status("[bold green]Scanning dataset..."):
        from .scanner import scan_directory
        scan_start = time.time()
        report = scan_directory(
            path=target,
            config=config,
            recursive=recursive,
        )
        scan_elapsed = time.time() - scan_start

    s = report.stats
    table = Table(title="Scan Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total files", str(s.total_files))
    table.add_row("Supported (attempted)", str(s.supported_files + s.media_files))
    table.add_row("Classified successfully", str(s.classified_files))
    table.add_row("Media files (skipped)", str(s.media_files))
    table.add_row("Execution time", f"{scan_elapsed:.1f}s")
    console.print(table)

    if s.by_category:
        cat_table = Table(title="Category Distribution")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", style="green")
        cat_table.add_column("Percentage", style="yellow")
        cat_table.add_column("Time", style="dim")
        for cat, count in sorted(s.by_category.items(), key=lambda x: -x[1]):
            pct = count * 100 / s.classified_files if s.classified_files else 0
            cat_time = s.by_category_time.get(cat, 0)
            cat_table.add_row(
                cat, str(count), f"{pct:.1f}%",
                f"{cat_time:.1f}s" if cat_time else "-",
            )
        console.print(cat_table)

    if s.by_extension:
        ext_table = Table(title="Extension Distribution")
        ext_table.add_column("Extension", style="cyan")
        ext_table.add_column("Count", style="green")
        for ext, count in sorted(s.by_extension.items(), key=lambda x: -x[1])[:10]:
            ext_table.add_row(ext, str(count))
        console.print(ext_table)

    if output_report:
        from .scanner import write_report_json
        out_path = Path(output_report)
        write_report_json(report, out_path)
        console.print(f"[green]Report saved to:[/green] {out_path}")

    if output_csv:
        from .scanner import write_report_csv
        out_path = Path(output_csv)
        write_report_csv(report, out_path)
        console.print(f"[green]CSV saved to:[/green] {out_path}")

    console.print(
        f"\n[bold green]Scan complete![/bold green] "
        f"({s.classified_files}/{s.supported_files} files classified)"
    )


@app.command()
def undo(
    all_ops: bool = typer.Option(False, "--all", help="Undo all recorded operations"),
) -> None:
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
        console.print("  [cyan][3][/cyan] Run document cleanup (file-type + naming)")
        console.print("  [cyan][4][/cyan] Undo last operation")
        console.print("  [cyan][0][/cyan] Exit")

        choice = Prompt.ask("Choose", choices=["0", "1", "2", "3", "4"], default="3")

        if choice == "1":
            _menu_configure_paths()
        elif choice == "2":
            _check_connection()
        elif choice == "3":
            _menu_run_classify()
        elif choice == "4":
            _menu_undo()
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
    code = run_classify(dry_run=False)
    if code:
        console.print("[red]Cleanup failed. See error above.[/red]")


def _menu_undo() -> None:
    all_ops = Confirm.ask("Undo ALL operations instead of only the last one?", default=False)
    _undo(all_ops)


if __name__ == "__main__":
    app()
