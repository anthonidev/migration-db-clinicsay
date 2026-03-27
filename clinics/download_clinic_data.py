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


def download_consent_templates(cursor, clinic_id: str) -> list:
    """Descarga consent templates con su configuración completa."""
    cursor.execute(
        """
        SELECT
            ct.id,
            ct.clinic_id,
            ct.site_id,
            ct.name,
            ct.description,
            ct.category,
            ct.default_language,
            ct.consent_template_status,
            ct.consent_template_version,
            ct.token_expiry_days,
            ct.signer_config,
            ct.pdf_template_config,
            ct.automation_config,
            ct.pre_bindings,
            ct.record_status,
            ct.record_metadata,
            ct.created_at,
            ct.updated_at
        FROM consent_template ct
        WHERE ct.clinic_id = %s
        ORDER BY ct.name
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_instances(cursor, clinic_id: str) -> list:
    """Descarga consent instances con datos del paciente y template."""
    cursor.execute(
        """
        SELECT
            ci.id,
            ci.organization_id,
            ci.clinic_id,
            ci.site_id,
            ci.patient_id,
            p.first_name AS patient_first_name,
            p.last_name AS patient_last_name,
            ci.template_id,
            ct.name AS template_name,
            ci.template_version_tag,
            ci.language,
            ci.consent_instance_status,
            ci.signing_status,
            ci.treatment_id,
            ci.resolved_content,
            ci.placeholder_resolutions,
            ci.combined_content,
            ci.combination_metadata,
            ci.source_budget_id,
            ci.source_ref,
            ci.record_status,
            ci.record_metadata,
            ci.created_at,
            ci.updated_at
        FROM consent_instance ci
        LEFT JOIN patient p ON p.id = ci.patient_id
        LEFT JOIN consent_template ct ON ct.id = ci.template_id
        WHERE ci.clinic_id = %s
        ORDER BY ci.created_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_instance_signers(cursor, clinic_id: str) -> list:
    """Descarga firmantes de consent instances de la clínica."""
    cursor.execute(
        """
        SELECT
            cis.id,
            cis.consent_instance_id,
            cis.signer_type,
            cis.role_label,
            cis.patient_id,
            cis.related_person_id,
            cis.user_id,
            cis.external_contact_ref,
            cis.full_name,
            cis.document_type,
            cis.document_number,
            cis.email,
            cis.phone,
            cis.channel_preference,
            cis.created_at,
            cis.updated_at
        FROM consent_instance_signer cis
        JOIN consent_instance ci ON ci.id = cis.consent_instance_id
        WHERE ci.clinic_id = %s
        ORDER BY cis.created_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_instance_signatures(cursor, clinic_id: str) -> list:
    """Descarga firmas de consent instances de la clínica."""
    cursor.execute(
        """
        SELECT
            sig.id,
            sig.consent_instance_id,
            sig.signer_id,
            sig.signer_type,
            sig.role_label,
            sig.consent_signature_status,
            sig.signed_at,
            sig.signature_type,
            sig.signature_data_ref,
            sig.document_hash,
            sig.hash_algorithm,
            sig.ip_address,
            sig.user_agent,
            sig.channel,
            sig.metadata,
            sig.created_at,
            sig.updated_at
        FROM consent_instance_signature sig
        JOIN consent_instance ci ON ci.id = sig.consent_instance_id
        WHERE ci.clinic_id = %s
        ORDER BY sig.created_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_images(cursor, clinic_id: str) -> list:
    """Descarga imágenes asociadas a consent templates e instances de la clínica."""
    cursor.execute(
        """
        SELECT
            cimg.id,
            cimg.consent_template_id,
            cimg.consent_instance_id,
            cimg.storage_key,
            cimg.file_name,
            cimg.content_type,
            cimg.size_bytes,
            cimg.width,
            cimg.height,
            cimg.thumbnail_storage_key,
            cimg.thumbnail_size_bytes,
            cimg.webp_storage_key,
            cimg.webp_size_bytes,
            cimg.uploaded_by_user_id,
            cimg.deleted_at,
            cimg.deleted_by_user_id,
            cimg.record_status,
            cimg.record_metadata,
            cimg.created_at,
            cimg.updated_at
        FROM consent_images cimg
        LEFT JOIN consent_template ct ON ct.id = cimg.consent_template_id
        LEFT JOIN consent_instance ci ON ci.id = cimg.consent_instance_id
        WHERE ct.clinic_id = %s OR ci.clinic_id = %s
        ORDER BY cimg.created_at DESC
        """,
        (clinic_id, clinic_id),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_delivery_attempts(cursor, clinic_id: str) -> list:
    """Descarga intentos de entrega de consentimientos de la clínica."""
    cursor.execute(
        """
        SELECT
            cda.id,
            cda.clinic_id,
            cda.site_id,
            cda.consent_instance_id,
            cda.signer_id,
            cda.channel,
            cda.consent_delivery_attempt_status,
            cda.requested_at,
            cda.sent_at,
            cda.failed_at,
            cda.error_code,
            cda.error_detail,
            cda.provider,
            cda.provider_reference,
            cda.provider_metadata,
            cda.record_status,
            cda.record_metadata,
            cda.created_at,
            cda.updated_at
        FROM consent_delivery_attempt cda
        WHERE cda.clinic_id = %s
        ORDER BY cda.created_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_consent_evidence(cursor, clinic_id: str) -> list:
    """Descarga evidencia sellada de consentimientos de la clínica."""
    cursor.execute(
        """
        SELECT
            ce.id,
            ce.consent_instance_id,
            ce.document_hash,
            ce.hash_algorithm,
            ce.sealed_at,
            ce.seal_provider,
            ce.seal_data_ref,
            ce.storage_location,
            ce.metadata,
            ce.created_at,
            ce.updated_at
        FROM consent_evidence ce
        JOIN consent_instance ci ON ci.id = ce.consent_instance_id
        WHERE ci.clinic_id = %s
        ORDER BY ce.sealed_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_budget_consent_templates(cursor, clinic_id: str) -> list:
    """Descarga relaciones budget-consent template de la clínica."""
    cursor.execute(
        """
        SELECT
            bct.id,
            bct.budget_id,
            bct.consent_template_id,
            ct.name AS template_name,
            bct.record_status,
            bct.record_metadata,
            bct.created_at,
            bct.updated_at
        FROM budget_consent_template bct
        JOIN consent_template ct ON ct.id = bct.consent_template_id
        WHERE ct.clinic_id = %s
        ORDER BY bct.created_at DESC
        """,
        (clinic_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def download_all_consent_data(cursor, clinic_id: str) -> dict:
    """Descarga todas las tablas de consentimientos de la clínica."""
    return {
        "consent_templates": download_consent_templates(cursor, clinic_id),
        "consent_instances": download_consent_instances(cursor, clinic_id),
        "consent_instance_signers": download_consent_instance_signers(cursor, clinic_id),
        "consent_instance_signatures": download_consent_instance_signatures(cursor, clinic_id),
        "consent_images": download_consent_images(cursor, clinic_id),
        "consent_delivery_attempts": download_consent_delivery_attempts(cursor, clinic_id),
        "consent_evidence": download_consent_evidence(cursor, clinic_id),
        "budget_consent_templates": download_budget_consent_templates(cursor, clinic_id),
    }


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
    "2": {
        "name": "Consentimientos (todas las tablas)",
        "key": "consent",
        "fn": download_all_consent_data,
        "multi": True,
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
        result = entity["fn"](cursor, clinic_id)

        # Multi-tabla: descarga varias tablas como CSVs separados
        if entity.get("multi") and isinstance(result, dict):
            total = 0
            files = []
            for table_key, data in result.items():
                if not data:
                    info(f"  {table_key}: 0 registros")
                    continue
                filepath = save_csv(data, clinic_info["clinic_name"], table_key)
                files.append(filepath)
                total += len(data)
                success(f"  {table_key}: {len(data)} registros → {filepath}")

            if not files:
                info(f"No se encontraron datos de {entity['name'].lower()} para esta clínica")
                return

            success(f"Total: {total} registros en {len(files)} archivos")
        else:
            data = result
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
