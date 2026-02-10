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

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
DOMAIN_DIR = os.path.join(DOCS_DIR, "DOMAIN")


def get_source_path() -> str:
    """Obtiene la ruta origen desde PATH_DOCS en .env"""
    path = os.getenv("PATH_DOCS")
    if not path:
        raise ValueError("PATH_DOCS no encontrada en .env")
    return path


def count_files(path: str) -> int:
    """Cuenta archivos .md totales."""
    total = 0
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                total += 1
    return total


def copy_docs(source: str, dest: str) -> dict:
    """Copia documentación de dominio."""
    stats = {
        "copied": 0,
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

            src_file = os.path.join(root, file)
            dst_file = os.path.join(dest_path, file)
            shutil.copy2(src_file, dst_file)
            stats["copied"] += 1

    return stats


def copy_prisma_schema(source_base: str) -> bool:
    """Copia el schema de Prisma desde PATH_DOCS/prisma/schema.prisma."""
    src = os.path.join(source_base, "prisma", "schema.prisma")
    if not os.path.exists(src):
        warning(f"Schema de Prisma no encontrado: {src}")
        return False

    dest_dir = os.path.join(DOMAIN_DIR, "prisma")
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, "schema.prisma")
    shutil.copy2(src, dst)
    return True


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
    total = count_files(source_path)

    # Verificar prisma schema
    prisma_path = os.path.join(source_path, "prisma", "schema.prisma")
    has_prisma = os.path.exists(prisma_path)

    print_subheader("Archivos")
    info(f"Documentación .md: {total}")
    info(f"Prisma schema: {'encontrado' if has_prisma else 'no encontrado'}")

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
    stats = copy_docs(source_path, DOMAIN_DIR)

    # Copiar prisma schema
    step("Copiando schema de Prisma...")
    if copy_prisma_schema(source_path):
        success("Schema de Prisma copiado")
    else:
        warning("Schema de Prisma no copiado")

    # Mostrar resultado
    console.print()
    success("Sincronización completada")

    print_subheader("Resumen")
    info(f"Carpetas creadas: {stats['folders']}")
    info(f"Archivos .md copiados: {stats['copied']}")
    info(f"Schema Prisma: {'copiado' if has_prisma else 'no encontrado'}")


if __name__ == "__main__":
    sync_docs()
