"""
Logger estandarizado para scripts de migración.

Provee salida uniforme en terminal (con Rich) y archivo de log.
Reemplaza los print() sueltos de cada script por un formato consistente.

Uso:
    from config.logger import MigrationLogger

    log = MigrationLogger("extract_patients")
    log.header("Extraer Pacientes")
    log.section("Leyendo CSV")
    log.stat("Filas leídas", 2112)
    log.detail("Con email", 1477)
    log.warning("Sin documento: 87")
    log.item("Juan Pérez")
    log.progress(500, 2112)   # solo cada N registros
    log.summary({"Pacientes": 2112, "Con email": 1477, "Sin doc": 87})
    log.finish()
"""
import os
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.theme import Theme

# Tema alineado con ui/console.py
_theme = Theme({
    "mlog.header": "magenta bold",
    "mlog.section": "cyan bold",
    "mlog.stat.key": "white",
    "mlog.stat.val": "cyan bold",
    "mlog.detail.key": "dim",
    "mlog.detail.val": "white",
    "mlog.ok": "green",
    "mlog.warn": "yellow",
    "mlog.err": "red bold",
    "mlog.item": "green",
    "mlog.dim": "dim",
    "mlog.progress": "blue",
})

_console = Console(theme=_theme)

# Umbral: si hay más de N items, solo mostrar resumen en terminal
_ITEM_THRESHOLD = 15


class MigrationLogger:
    """Logger dual: terminal (Rich) + archivo de log."""

    def __init__(self, script_name: str, logs_dir: str = None):
        self._script = script_name
        self._ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._stats: list[tuple[str, Any]] = []
        self._item_count = 0
        self._item_error_count = 0
        self._item_skip_count = 0
        self._in_batch = False

        if logs_dir is None:
            import inspect
            caller = inspect.stack()[1].filename
            clinic_dir = os.path.dirname(os.path.dirname(os.path.abspath(caller)))
            logs_dir = os.path.join(clinic_dir, "logs")

        os.makedirs(logs_dir, exist_ok=True)
        self._log_path = os.path.join(logs_dir, f"{script_name}_{self._ts}.log")
        self._log = open(self._log_path, "w", encoding="utf-8")
        self._log.write(f"{script_name} - {datetime.now().isoformat()}\n")
        self._log.write("-" * 60 + "\n\n")

    # ── Encabezado principal ──────────────────────────────────

    def header(self, title: str, subtitle: str = None):
        """Título principal del script."""
        _console.print()
        _console.print(Rule(style="mlog.header"))
        _console.print(f"  [mlog.header]{title}[/mlog.header]")
        if subtitle:
            _console.print(f"  [mlog.dim]{subtitle}[/mlog.dim]")
        _console.print(Rule(style="mlog.header"))
        self._log.write(f"=== {title} ===\n")
        if subtitle:
            self._log.write(f"    {subtitle}\n")
        self._log.write("\n")

    # ── Secciones ─────────────────────────────────────────────

    def section(self, title: str):
        """Sección dentro del script."""
        self._flush_batch()
        _console.print()
        _console.print(f"  [mlog.section]▸ {title}[/mlog.section]")
        self._log.write(f"\n--- {title} ---\n")

    # ── Estadísticas y datos ──────────────────────────────────

    def stat(self, key: str, value: Any):
        """Dato clave-valor destacado."""
        _console.print(f"    [mlog.stat.key]{key}:[/mlog.stat.key] [mlog.stat.val]{value}[/mlog.stat.val]")
        self._log.write(f"  {key}: {value}\n")

    def detail(self, key: str, value: Any):
        """Dato secundario — solo archivo de log, no terminal."""
        self._log.write(f"    {key}: {value}\n")

    def count(self, key: str, value: int):
        """Igual que stat pero guarda para el resumen final automático."""
        self.stat(key, value)
        self._stats.append((key, value))

    # ── Items individuales ────────────────────────────────────
    # En terminal: muestra los primeros N, luego solo cuenta.
    # En log: siempre escribe todo.

    def item(self, text: str):
        """Item procesado exitosamente."""
        self._item_count += 1
        self._log.write(f"  [OK] {text}\n")
        if self._item_count <= _ITEM_THRESHOLD:
            _console.print(f"    [mlog.ok]✓[/mlog.ok] {text}")
        elif self._item_count == _ITEM_THRESHOLD + 1:
            _console.print(f"    [mlog.dim]... (detalle en log)[/mlog.dim]")

    def item_skip(self, text: str):
        """Item omitido."""
        self._item_skip_count += 1
        self._log.write(f"  [SKIP] {text}\n")
        if (self._item_count + self._item_skip_count) <= _ITEM_THRESHOLD:
            _console.print(f"    [mlog.dim]–[/mlog.dim] [mlog.dim]{text}[/mlog.dim]")

    def item_error(self, text: str):
        """Item con error — siempre visible en terminal."""
        self._item_error_count += 1
        _console.print(f"    [mlog.err]✗[/mlog.err] {text}")
        self._log.write(f"  [ERROR] {text}\n")

    def reset_items(self):
        """Reset item counters para nueva sección de items."""
        self._flush_batch()
        self._item_count = 0
        self._item_error_count = 0
        self._item_skip_count = 0

    # ── Progreso en batch ─────────────────────────────────────

    def progress(self, current: int, total: int, every: int = 2000):
        """Muestra progreso cada `every` registros. Solo terminal."""
        if total <= 0:
            return
        self._in_batch = True
        if current % every == 0 or current == total:
            pct = round(current / total * 100)
            _console.print(
                f"    [mlog.progress]↳ {current:,}/{total:,}[/mlog.progress] [mlog.dim]({pct}%)[/mlog.dim]",
                highlight=False,
            )

    # ── Mensajes de estado ────────────────────────────────────

    def ok(self, message: str):
        """Mensaje de éxito."""
        _console.print(f"    [mlog.ok]✓[/mlog.ok] {message}")
        self._log.write(f"  [OK] {message}\n")

    def warning(self, message: str):
        """Mensaje de advertencia."""
        _console.print(f"    [mlog.warn]⚠[/mlog.warn] {message}")
        self._log.write(f"  [WARN] {message}\n")

    def error(self, message: str):
        """Mensaje de error."""
        _console.print(f"    [mlog.err]✗[/mlog.err] {message}")
        self._log.write(f"  [ERROR] {message}\n")

    # ── Resumen final ─────────────────────────────────────────

    def summary(self, data: dict[str, Any] = None):
        """Tabla de resumen final."""
        self._flush_batch()
        items = list((data or {}).items()) or self._stats
        if not items:
            return

        _console.print()
        table = Table(
            show_header=False,
            border_style="dim",
            padding=(0, 1),
            expand=False,
        )
        table.add_column("Concepto", style="white", min_width=24)
        table.add_column("Valor", style="cyan bold", justify="right", min_width=8)

        total = 0
        for key, val in items:
            display = f"{val:,}" if isinstance(val, int) else str(val)
            table.add_row(key, display)
            if isinstance(val, int):
                total += val

        if len(items) > 1 and total > 0:
            table.add_section()
            table.add_row("[bold]TOTAL[/bold]", f"[bold]{total:,}[/bold]")

        _console.print(table)

        self._log.write("\n=== RESUMEN ===\n")
        for key, val in items:
            self._log.write(f"  {key}: {val}\n")
        if len(items) > 1 and total > 0:
            self._log.write(f"  TOTAL: {total}\n")

    # ── Internos ──────────────────────────────────────────────

    def _flush_batch(self):
        """Imprime resumen de items si hubo muchos en la sección anterior."""
        if self._item_count > _ITEM_THRESHOLD:
            shown = min(self._item_count, _ITEM_THRESHOLD)
            hidden = self._item_count - shown
            if hidden > 0:
                pass  # El "... (detalle en log)" ya se mostró
        self._item_count = 0
        self._item_error_count = 0
        self._item_skip_count = 0
        self._in_batch = False

    # ── Cierre ────────────────────────────────────────────────

    def finish(self):
        """Cierra el archivo de log y muestra la ruta. Idempotente."""
        if self._log.closed:
            return
        self._flush_batch()
        rel = os.path.basename(self._log_path)
        _console.print(f"    [mlog.dim]Log: {rel}[/mlog.dim]")
        self._log.write(f"\n=== FIN ===\n")
        self._log.close()

    @property
    def log_path(self) -> str:
        return self._log_path

    @property
    def file(self):
        """Acceso directo al file handle para escrituras extra."""
        return self._log

    # ── Context manager ───────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.finish()
        return False
