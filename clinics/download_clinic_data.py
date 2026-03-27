"""
Descarga datos de una clínica desde la base de datos por su ID.

Permite seleccionar qué tipo de datos descargar y los exporta como CSV.
"""
import csv
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

from config.database import get_db_config
from ui import (
    print_header,
    print_subheader,
    print_menu,
    print_key_value,
    info,
    success,
    error,
    step,
    ask,
)

# Directorio de descargas
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")


def get_connection():
    """Get database connection."""
    config = get_db_config()
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
        cursor_factory=RealDictCursor,
    )


def get_clinic_info(cursor, clinic_id: str) -> dict | None:
    """Busca la información de la clínica en la BD."""
    cursor.execute(
        """
        SELECT c.id, c.name, c.organization_id, c.default_issuer_company_id
        FROM clinic c
        WHERE c.id = %s
        """,
        (clinic_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    # Obtener site_ids
    cursor.execute("SELECT id FROM site WHERE clinic_id = %s", (clinic_id,))
    site_ids = [r["id"] for r in cursor.fetchall()]

    return {
        "clinic_id": row["id"],
        "clinic_name": row["name"],
        "organization_id": row["organization_id"],
        "company_id": row["default_issuer_company_id"],
        "site_ids": site_ids,
    }


def format_value(val):
    """Formatea un valor para CSV."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def save_csv(data: list, clinic_name: str, entity_name: str) -> str:
    """Guarda los datos como CSV y retorna la ruta del archivo."""
    clinic_dir = os.path.join(DOWNLOADS_DIR, clinic_name.lower().replace(" ", "_"))
    os.makedirs(clinic_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{entity_name}_{timestamp}.csv"
    filepath = os.path.join(clinic_dir, filename)

    headers = list(data[0].keys())

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data:
            writer.writerow([format_value(row.get(h)) for h in headers])

    return filepath


def download_professionals(cursor, clinic_id: str) -> list:
    """Descarga profesionales con su tipo profesional."""
    cursor.execute(
        """
        SELECT
            p.id,
            p.name,
            p.last_name,
            p.email,
            p.phone_country_prefix,
            p.phone_number,
            p.professional_type_id,
            pt.name AS professional_type_name,
            p.specialties,
            p.color,
            p.employment_type,
            p.site_ids,
            p.record_status,
            p.record_metadata,
            p.metadata,
            p.created_at,
            p.updated_at
        FROM professional p
        LEFT JOIN professional_type pt ON pt.id = p.professional_type_id
        WHERE p.clinic_id = %s
        ORDER BY p.last_name, p.name
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


# Registro de entidades disponibles para descarga
ENTITIES = {
    "1": {
        "name": "Profesionales",
        "key": "professionals",
        "fn": download_professionals,
    },
}


def download_clinic_data():
    """Función principal: pide clinic_id, selecciona entidad y descarga."""
    print_header("Descargar datos de clínica")

    clinic_id = ask("Ingresa el ID de la clínica").strip()
    if not clinic_id:
        error("No se ingresó un ID")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Buscar info de la clínica
        step("Buscando clínica en la base de datos...")
        clinic_info = get_clinic_info(cursor, clinic_id)

        if not clinic_info:
            error(f"No se encontró la clínica con ID: {clinic_id}")
            return

        print_subheader("Información de la clínica")
        print_key_value({
            "Nombre": clinic_info["clinic_name"],
            "Clinic ID": clinic_info["clinic_id"],
            "Sites": len(clinic_info["site_ids"]),
        })

        # Menú de selección de entidad
        print_menu(
            title="¿Qué datos descargar?",
            options=[
                {"key": k, "label": v["name"]}
                for k, v in ENTITIES.items()
            ],
        )

        option = ask("Selecciona una opción").strip()
        entity = ENTITIES.get(option)

        if not entity:
            error("Opción no válida")
            return

        # Descargar datos
        step(f"Descargando {entity['name']}...")
        data = entity["fn"](cursor, clinic_id)

        if not data:
            info(f"No se encontraron {entity['name'].lower()} para esta clínica")
            return

        # Guardar CSV
        filepath = save_csv(data, clinic_info["clinic_name"], entity["key"])
        success(f"{len(data)} registros descargados")
        success(f"Archivo: {filepath}")

    except Exception as e:
        error(f"{e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
