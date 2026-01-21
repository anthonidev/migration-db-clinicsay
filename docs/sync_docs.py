import os
import sys
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from ui import (
    console,
    print_header,
    print_subheader,
    info,
    success,
    warning,
    error,
    step,
    confirm,
)

load_dotenv()

# Archivos a excluir (no útiles para migración)
EXCLUDED_FILES = {
    "http.md",
    "adapters.md",
    "events.md",
    "application.md",
}

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
DOMAIN_DIR = os.path.join(DOCS_DIR, "DOMAIN")


def get_source_path() -> str:
    """Obtiene la ruta origen desde PATH_DOCS en .env"""
    path = os.getenv("PATH_DOCS")
    if not path:
        raise ValueError("PATH_DOCS no encontrada en .env")
    return path


def count_files(path: str, excluded: set) -> tuple:
    """Cuenta archivos totales y excluidos."""
    total = 0
    excluded_count = 0

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                total += 1
                if file in excluded:
                    excluded_count += 1

    return total, excluded_count


def copy_docs(source: str, dest: str, excluded: set) -> dict:
    """Copia documentación excluyendo archivos innecesarios."""
    stats = {
        "copied": 0,
        "excluded": 0,
        "folders": 0,
    }

    for root, dirs, files in os.walk(source):
        # Calcular ruta relativa
        rel_path = os.path.relpath(root, source)
        dest_path = os.path.join(dest, rel_path) if rel_path != "." else dest

        # Crear carpeta destino
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
            stats["folders"] += 1

        for file in files:
            if not file.endswith(".md"):
                continue

            if file in excluded:
                stats["excluded"] += 1
                continue

            src_file = os.path.join(root, file)
            dst_file = os.path.join(dest_path, file)
            shutil.copy2(src_file, dst_file)
            stats["copied"] += 1

    return stats


def sync_docs():
    """Sincroniza la documentación de dominio."""
    print_header("SINCRONIZAR DOCUMENTACIÓN")

    # Obtener ruta origen
    try:
        source_path = get_source_path()
    except ValueError as e:
        error(str(e))
        return

    # Verificar que existe
    if not os.path.exists(source_path):
        error(f"Ruta no encontrada: {source_path}")
        info("Verifique PATH_DOCS en .env")
        return

    step(f"Origen: [cyan]{source_path}[/cyan]")
    step(f"Destino: [cyan]{DOMAIN_DIR}[/cyan]")

    # Contar archivos
    total, excluded_count = count_files(source_path, EXCLUDED_FILES)
    to_copy = total - excluded_count

    print_subheader("Archivos")
    info(f"Total en origen: {total}")
    info(f"A copiar: {to_copy}")
    info(f"A excluir: {excluded_count}")

    console.print()
    console.print("  [dim]Archivos excluidos:[/dim]")
    for f in sorted(EXCLUDED_FILES):
        console.print(f"    [red]•[/red] {f}")

    console.print()

    # Verificar si ya existe DOMAIN
    if os.path.exists(DOMAIN_DIR):
        warning(f"La carpeta DOMAIN ya existe y será eliminada")
        console.print()

        if not confirm("¿Continuar con la sincronización?"):
            info("Operación cancelada")
            return

        # Eliminar carpeta existente
        step("Eliminando DOMAIN existente...")
        shutil.rmtree(DOMAIN_DIR)
        success("Carpeta eliminada")
    else:
        if not confirm("¿Iniciar sincronización?"):
            info("Operación cancelada")
            return

    # Copiar documentación
    step("Copiando documentación...")
    stats = copy_docs(source_path, DOMAIN_DIR, EXCLUDED_FILES)

    # Mostrar resultado
    console.print()
    success("Sincronización completada")

    print_subheader("Resumen")
    info(f"Carpetas creadas: {stats['folders']}")
    info(f"Archivos copiados: {stats['copied']}")
    info(f"Archivos excluidos: {stats['excluded']}")


if __name__ == "__main__":
    sync_docs()
