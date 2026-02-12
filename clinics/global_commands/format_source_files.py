"""
Formatea los nombres de archivos en la carpeta fuente/ de una clínica.

Reglas de formato:
1. Eliminar sufijos de exportación: ".xlsx - Hoja1", ".xlsx - Hoja 1", ".xls - Hoja1", etc.
2. Convertir a minúsculas
3. Reemplazar espacios por guiones bajos
4. Reemplazar caracteres especiales (paréntesis, comas, etc.) por guiones bajos
5. Colapsar guiones bajos consecutivos
6. Eliminar guiones bajos al inicio/final del nombre
7. Mantener la extensión original (.csv, .xlsx, etc.)

Ejemplo:
  "Actuaciones (tratamientos que se ponen en la cita).xlsx - Hoja1.csv"
  → "actuaciones_tratamientos_que_se_ponen_en_la_cita.csv"
"""
import os
import re
import unicodedata


CLINICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def normalize_filename(filename: str) -> str:
    """Aplica todas las reglas de formato a un nombre de archivo."""
    # Separar nombre y extensión
    name, ext = os.path.splitext(filename)

    # 1. Eliminar sufijos de exportación (.xlsx - Hoja1, .xls - Hoja 1, etc.)
    name = re.sub(r'\.xlsx?\s*-\s*Hoja\s*\d*', '', name, flags=re.IGNORECASE)

    # 2. Normalizar caracteres unicode (á → a, ñ → n, etc.)
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode('ascii')

    # 3. Convertir a minúsculas
    name = name.lower()

    # 4. Reemplazar caracteres especiales por guion bajo
    name = re.sub(r'[^a-z0-9._-]', '_', name)

    # 5. Colapsar guiones bajos consecutivos
    name = re.sub(r'_+', '_', name)

    # 6. Eliminar guiones bajos al inicio/final
    name = name.strip('_')

    # 7. Extensión en minúsculas
    ext = ext.lower()

    return f"{name}{ext}"


def format_source_files(clinic_folder: str):
    """Función principal: renombra archivos en fuente/"""
    fuente_dir = os.path.join(CLINICS_DIR, clinic_folder, "fuente")

    if not os.path.exists(fuente_dir):
        print(f"ERROR: No existe la carpeta: {fuente_dir}")
        return

    # Listar archivos (no carpetas)
    files = [f for f in os.listdir(fuente_dir) if os.path.isfile(os.path.join(fuente_dir, f))]

    if not files:
        print("No hay archivos en fuente/")
        return

    print("=" * 60)
    print("FORMATEAR NOMBRES DE ARCHIVOS FUENTE")
    print("=" * 60)

    # Calcular renombramientos
    renames = []
    already_ok = []
    conflicts = []

    for original in sorted(files):
        new_name = normalize_filename(original)

        if new_name == original:
            already_ok.append(original)
            continue

        new_path = os.path.join(fuente_dir, new_name)
        if os.path.exists(new_path) and new_name != original:
            conflicts.append((original, new_name))
        else:
            renames.append((original, new_name))

    # Mostrar resultados
    if renames:
        print(f"\n--- Archivos a renombrar ({len(renames)}) ---")
        for original, new_name in renames:
            print(f"  {original}")
            print(f"    → {new_name}")
            print()

    if already_ok:
        print(f"\n--- Ya tienen formato correcto ({len(already_ok)}) ---")
        for f in already_ok:
            print(f"  {f}")

    if conflicts:
        print(f"\n--- CONFLICTOS ({len(conflicts)}) ---")
        for original, new_name in conflicts:
            print(f"  {original} → {new_name} [YA EXISTE]")

    if not renames:
        print("\nNo hay archivos para renombrar.")
        return

    # Confirmar
    print(f"\n¿Renombrar {len(renames)} archivo(s)?")
    print("Escribe 'SI' para continuar:")

    try:
        confirmation = input().strip()
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return

    if confirmation != "SI":
        print("\nOperación cancelada.")
        return

    # Ejecutar renombramientos
    print("\n--- Renombrando ---")
    renamed_count = 0

    for original, new_name in renames:
        original_path = os.path.join(fuente_dir, original)
        new_path = os.path.join(fuente_dir, new_name)
        try:
            os.rename(original_path, new_path)
            print(f"  [OK] {new_name}")
            renamed_count += 1
        except Exception as e:
            print(f"  [ERROR] {original}: {e}")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Archivos renombrados: {renamed_count}/{len(renames)}")
    if conflicts:
        print(f"Conflictos (no renombrados): {len(conflicts)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Formatea nombres de archivos fuente")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    args = parser.parse_args()
    format_source_files(args.clinic_folder)
