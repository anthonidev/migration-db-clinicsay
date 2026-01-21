import os
import sys
from typing import Optional, List, Dict, Any

import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.rule import Rule
from rich.style import Style
from rich.theme import Theme

# Tema personalizado
custom_theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "step": "blue",
    "header": "magenta bold",
    "subheader": "cyan bold",
    "menu.option": "green",
    "menu.number": "cyan bold",
    "key": "cyan",
    "value": "white",
})

# Consola global con tema
console = Console(theme=custom_theme)


def clear():
    """Limpia la pantalla."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner(subtitle: str = None):
    """Muestra el banner principal con pyfiglet."""
    # Generar ASCII art
    ascii_art = pyfiglet.figlet_format("CLINICSAY", font="slant")

    # Crear texto con estilo
    banner_text = Text()
    banner_text.append(ascii_art, style="cyan bold")

    if subtitle:
        banner_text.append(f"\n{subtitle}", style="dim")

    console.print(Panel(
        banner_text,
        border_style="cyan",
        padding=(0, 2),
    ))


def print_header(text: str, style: str = "header"):
    """Imprime un encabezado principal."""
    console.print()
    console.print(Panel(
        Text(text, style=style, justify="center"),
        border_style="magenta",
        padding=(0, 2),
    ))


def print_subheader(text: str):
    """Imprime un subencabezado."""
    console.print()
    console.print(f"[subheader]▶ {text}[/subheader]")
    console.print(Rule(style="dim"))


def print_menu(title: str, options: List[Dict[str, str]]):
    """
    Imprime un menú formateado.

    options: Lista de dicts con 'key', 'label', y opcionalmente 'group'
    Ejemplo: [{'key': '1', 'label': 'Opción 1', 'group': 'Acciones'}]
    """
    console.print()

    current_group = None
    for opt in options:
        group = opt.get('group')
        if group and group != current_group:
            console.print()
            console.print(f"  [dim]── {group} ──[/dim]")
            current_group = group

        key = opt['key']
        label = opt['label']
        console.print(f"  [menu.number]{key}[/menu.number]. [menu.option]{label}[/menu.option]")

    console.print()
    print_separator()


def print_menu_option(key: str, label: str):
    """Imprime una opción de menú individual."""
    console.print(f"  [menu.number]{key}[/menu.number]. [menu.option]{label}[/menu.option]")


def print_separator(style: str = "dim"):
    """Imprime un separador."""
    console.print(Rule(style=style))


def print_rule(text: str = "", style: str = "cyan"):
    """Imprime una línea con texto opcional."""
    console.print(Rule(text, style=style))


def info(message: str):
    """Log de información."""
    console.print(f"[info]ℹ[/info]  {message}")


def success(message: str):
    """Log de éxito."""
    console.print(f"[success]✓[/success]  {message}")


def warning(message: str):
    """Log de advertencia."""
    console.print(f"[warning]⚠[/warning]  {message}")


def error(message: str):
    """Log de error."""
    console.print(f"[error]✗[/error]  {message}")


def step(message: str):
    """Log de paso en proceso."""
    console.print(f"[step]→[/step]  {message}")


def ask(prompt: str, default: str = None) -> str:
    """Solicita entrada del usuario."""
    return Prompt.ask(f"[cyan]?[/cyan] {prompt}", default=default, console=console)


def confirm(prompt: str, default: bool = False) -> bool:
    """Solicita confirmación del usuario."""
    return Confirm.ask(f"[cyan]?[/cyan] {prompt}", default=default, console=console)


def print_table(
    title: str,
    columns: List[str],
    rows: List[List[str]],
    show_header: bool = True
):
    """Imprime una tabla formateada."""
    table = Table(title=title, show_header=show_header, header_style="bold cyan")

    for col in columns:
        table.add_column(col)

    for row in rows:
        table.add_row(*row)

    console.print(table)


def print_key_value(data: Dict[str, Any], title: str = None):
    """Imprime pares clave-valor formateados."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")
        console.print(Rule(style="dim"))

    for key, value in data.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            value = "[dim]-[/dim]"
        console.print(f"  [key]{key}:[/key] [value]{value}[/value]")


def print_tree(title: str, items: Dict[str, Any], guide_style: str = "cyan"):
    """Imprime una estructura de árbol."""
    tree = Tree(f"[bold]{title}[/bold]", guide_style=guide_style)

    def add_items(parent, data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    branch = parent.add(f"[cyan]{key}[/cyan]")
                    add_items(branch, value)
                else:
                    display_value = value if value else "[dim]-[/dim]"
                    parent.add(f"[cyan]{key}:[/cyan] {display_value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    branch = parent.add(f"[yellow]Item {i + 1}[/yellow]")
                    add_items(branch, item)
                else:
                    parent.add(str(item))

    add_items(tree, items)
    console.print(tree)


def print_panel(
    content: str,
    title: str = None,
    style: str = "cyan",
    expand: bool = False
):
    """Imprime un panel con contenido."""
    console.print(Panel(
        content,
        title=title,
        border_style=style,
        expand=expand,
        padding=(1, 2),
    ))


def print_folder_structure(name: str, folders: List[str], files: List[str] = None):
    """Imprime estructura de carpetas."""
    tree = Tree(f"[bold cyan]{name}/[/bold cyan]", guide_style="dim")

    for folder in folders:
        tree.add(f"[cyan]{folder}/[/cyan]")

    if files:
        for file in files:
            tree.add(f"[green]{file}[/green]")

    console.print(tree)
