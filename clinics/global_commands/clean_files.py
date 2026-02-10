"""
Limpia todos los archivos generados por la migración.

Borra:
- Todos los archivos .log en logs/
- Todos los archivos .json en processed/

NO borra:
- Scripts de migración
- Archivos fuente (fuente/)
- Configuración (queries.py, mappings.py)
"""
import os
import glob as glob_module


# Paths
CLINICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def get_files_to_delete(clinic_folder: str):
    """Obtiene lista de archivos a borrar"""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    logs_dir = os.path.join(clinic_dir, "logs")
    processed_dir = os.path.join(clinic_dir, "processed")

    files = {
        "logs": [],
        "processed": []
    }

    # Logs
    if os.path.exists(logs_dir):
        for f in glob_module.glob(os.path.join(logs_dir, "*.log")):
            files["logs"].append(f)

    # Processed JSONs
    if os.path.exists(processed_dir):
        for f in glob_module.glob(os.path.join(processed_dir, "*.json")):
            files["processed"].append(f)

    return files


def format_size(size_bytes):
    """Formatea tamaño en bytes a formato legible"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def clean_files(clinic_folder: str):
    """Función principal de limpieza"""
    print("=" * 60)
    print("LIMPIEZA DE ARCHIVOS GENERADOS")
    print("=" * 60)

    files = get_files_to_delete(clinic_folder)

    # Mostrar archivos a borrar
    total_files = 0
    total_size = 0

    print("\n--- Archivos de LOG ---")
    if files["logs"]:
        for f in sorted(files["logs"]):
            size = os.path.getsize(f)
            total_size += size
            print(f"  {os.path.basename(f)} ({format_size(size)})")
        total_files += len(files["logs"])
    else:
        print("  (ninguno)")

    print(f"\n--- Archivos JSON procesados ---")
    if files["processed"]:
        for f in sorted(files["processed"]):
            size = os.path.getsize(f)
            total_size += size
            print(f"  {os.path.basename(f)} ({format_size(size)})")
        total_files += len(files["processed"])
    else:
        print("  (ninguno)")

    if total_files == 0:
        print("\nNo hay archivos para borrar.")
        return

    print("\n" + "-" * 60)
    print(f"Total: {total_files} archivos, {format_size(total_size)}")
    print("-" * 60)

    # Confirmar
    print("\n¿Qué deseas borrar?")
    print("  1. Solo logs")
    print("  2. Solo JSONs procesados")
    print("  3. Todo (logs + JSONs)")
    print("  0. Cancelar")
    print("\nElige una opción (0-3):")

    try:
        option = input().strip()
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return

    if option == "0":
        print("\nOperación cancelada.")
        return

    deleted_count = 0
    deleted_size = 0

    # Borrar logs
    if option in ["1", "3"]:
        print("\n--- Borrando logs ---")
        for f in files["logs"]:
            try:
                size = os.path.getsize(f)
                os.remove(f)
                print(f"  [OK] {os.path.basename(f)}")
                deleted_count += 1
                deleted_size += size
            except Exception as e:
                print(f"  [ERROR] {os.path.basename(f)}: {e}")

    # Borrar JSONs
    if option in ["2", "3"]:
        print("\n--- Borrando JSONs procesados ---")
        for f in files["processed"]:
            try:
                size = os.path.getsize(f)
                os.remove(f)
                print(f"  [OK] {os.path.basename(f)}")
                deleted_count += 1
                deleted_size += size
            except Exception as e:
                print(f"  [ERROR] {os.path.basename(f)}: {e}")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Archivos borrados: {deleted_count}")
    print(f"Espacio liberado: {format_size(deleted_size)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Limpia archivos generados por la migración")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    args = parser.parse_args()
    clean_files(args.clinic_folder)
