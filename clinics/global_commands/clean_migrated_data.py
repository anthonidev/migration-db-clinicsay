"""
Limpia TODOS los datos de la clínica.

IMPORTANTE: Este script borra TODOS los registros de la clínica especificada.
Incluye: datos, configuración, clinic, site y company.

Orden de borrado (respeta foreign keys):
1. cash_movement, cash_session, cash_register
2. task
3. trigger_scheduled_execution, trigger_rule (automatización)
4. payment, billing_document, billing_client
5. budget
6. schedule_block
7. planned_session, care_plan
8. consent_instance_evidence, consent_instance_signature, consent_instance_signer, consent_instance
9. consent_template
10. form_response, form_template_version, form_template (cuestionario)
11. treatment, category, service
12. room
13. availability_exception, availability_template
14. commission_rule
15. patient
15b. acquisition_channel
16. professional
17. user_clinic, app_user
18. site
19. clinic
20. company
"""
import importlib.util
import os
import sys
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

# Paths
CLINICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

sys.path.insert(0, os.path.dirname(CLINICS_DIR))

from config.database import get_db_config


def load_clinic_queries(clinic_folder: str):
    """Carga queries.py de la clínica dinámicamente."""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    queries_path = os.path.join(clinic_dir, "queries.py")
    spec = importlib.util.spec_from_file_location("queries", queries_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_connection():
    """Get database connection"""
    config = get_db_config()
    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        user=config["user"],
        password=config["password"],
        cursor_factory=RealDictCursor
    )


def setup_logging(clinic_folder: str):
    """Configura el archivo de log."""
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"clean_migrated_data_{timestamp}.log")
    return open(log_file, "w", encoding="utf-8")


def table_exists(cursor, table: str) -> bool:
    """Verifica si una tabla existe en la base de datos."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """, (table,))
    return cursor.fetchone()["exists"]


def delete_all_records(cursor, table: str, id_column: str, filter_value: str) -> int:
    """
    Borra TODOS los registros de una tabla por filtro.

    Args:
        table: Nombre de la tabla
        id_column: Columna de filtro (clinic_id, site_id, etc.)
        filter_value: Valor del filtro

    Returns:
        Número de registros borrados (-1 si la tabla no existe)
    """
    if not table_exists(cursor, table):
        return -1

    if filter_value is None:
        return 0

    query = f"DELETE FROM {table} WHERE {id_column} = %s"
    cursor.execute(query, (filter_value,))
    return cursor.rowcount


def delete_by_parent_id(cursor, table: str, parent_column: str, parent_ids: list) -> int:
    """
    Borra registros de una tabla hija por IDs de la tabla padre.

    Returns: -1 si la tabla no existe, 0 si no hay parent_ids
    """
    if not table_exists(cursor, table):
        return -1

    if not parent_ids:
        return 0

    placeholders = ','.join(['%s'] * len(parent_ids))
    query = f"DELETE FROM {table} WHERE {parent_column} IN ({placeholders})"
    cursor.execute(query, parent_ids)
    return cursor.rowcount


def get_ids_from_table(cursor, table: str, id_column: str, filter_column: str, filter_value: str) -> list:
    """Obtiene lista de IDs de una tabla."""
    if not table_exists(cursor, table):
        return []

    cursor.execute(f"SELECT {id_column} FROM {table} WHERE {filter_column} = %s", (filter_value,))
    return [row[id_column] for row in cursor.fetchall()]


def clean_all_clinic_data(clinic_folder: str, force: bool = False):
    """Función principal de limpieza TOTAL"""
    # Cargar queries de la clínica
    queries = load_clinic_queries(clinic_folder)
    CLINIC_ID = queries.CLINIC_ID
    SITE_IDS = queries.SITE_IDS
    COMPANY_ID = queries.COMPANY_ID

    print("=" * 60, flush=True)
    print("LIMPIEZA TOTAL DE LA CLÍNICA", flush=True)
    print("=" * 60, flush=True)

    site_id = SITE_IDS[0] if SITE_IDS else None
    print(f"\nClinic ID: {CLINIC_ID}", flush=True)
    print(f"Site ID: {site_id}", flush=True)
    print(f"Company ID: {COMPANY_ID}", flush=True)
    print("\n*** SE BORRARÁN TODOS LOS DATOS DE LA CLÍNICA ***", flush=True)
    print("*** INCLUYENDO: clinic, site, company ***", flush=True)

    if not force:
        # Confirmar antes de proceder
        print("\n¿Estás seguro de que deseas borrar TODOS los datos de la clínica?", flush=True)
        print("Esta acción NO se puede deshacer.", flush=True)
        print("Escribe 'BORRAR TODO' para continuar:", flush=True)
        confirmation = input().strip()

        if confirmation != "BORRAR TODO":
            print("\nOperación cancelada.", flush=True)
            return
    else:
        print("\n[--force] Ejecutando sin confirmación...", flush=True)

    conn = get_connection()
    cursor = conn.cursor()
    log = setup_logging(clinic_folder)

    try:
        site_id = SITE_IDS[0] if SITE_IDS else None

        log.write(f"Limpieza TOTAL de clínica - {datetime.now().isoformat()}\n")
        log.write(f"Clinic ID: {CLINIC_ID}\n")
        log.write(f"Site ID: {site_id}\n")
        log.write(f"Company ID: {COMPANY_ID}\n")
        log.write("-" * 60 + "\n\n")

        print("\n--- Iniciando limpieza TOTAL ---\n", flush=True)
        log.write("=== INICIO DE LIMPIEZA TOTAL ===\n\n")

        results = []

        def log_delete(table_name, count):
            """Helper para registrar borrado"""
            if count >= 0:
                results.append((table_name, count))
                log.write(f"[DELETE] {table_name}: {count}\n")
                if count > 0:
                    print(f"    {table_name}: {count}")
            else:
                log.write(f"[SKIP] {table_name}: tabla no existe\n")

        # Obtener IDs necesarios para borrados en cascada
        consent_instance_ids = get_ids_from_table(cursor, "consent_instance", "id", "clinic_id", CLINIC_ID)
        form_template_ids = get_ids_from_table(cursor, "form_template", "id", "clinic_id", CLINIC_ID)
        availability_template_ids = get_ids_from_table(cursor, "availability_template", "id", "clinic_id", CLINIC_ID)
        user_ids = get_ids_from_table(cursor, "user_clinic", "user_id", "clinic_id", CLINIC_ID)

        # 1. CAJA
        print("1. Limpiando datos de caja...")
        count = delete_all_records(cursor, "cash_movement", "site_id", site_id)
        log_delete("cash_movement", count)
        count = delete_all_records(cursor, "cash_session", "site_id", site_id)
        log_delete("cash_session", count)
        count = delete_all_records(cursor, "cash_register", "clinic_id", CLINIC_ID)
        log_delete("cash_register", count)
        conn.commit()

        # 2. TAREAS
        print("2. Limpiando tareas...")
        count = delete_all_records(cursor, "task", "clinic_id", CLINIC_ID)
        log_delete("task", count)
        conn.commit()

        # 3. AUTOMATIZACIÓN (trigger_rules)
        print("3. Limpiando reglas de automatización...")
        trigger_rule_ids = get_ids_from_table(cursor, "trigger_rule", "id", "clinic_id", CLINIC_ID)
        count = delete_by_parent_id(cursor, "trigger_scheduled_execution", "trigger_rule_id", trigger_rule_ids)
        log_delete("trigger_scheduled_execution", count)
        count = delete_all_records(cursor, "trigger_rule", "clinic_id", CLINIC_ID)
        log_delete("trigger_rule", count)
        conn.commit()

        # 4. FACTURACIÓN
        print("4. Limpiando facturación...")
        count = delete_all_records(cursor, "payment", "clinic_id", CLINIC_ID)
        log_delete("payment", count)
        count = delete_all_records(cursor, "billing_document", "clinic_id", CLINIC_ID)
        log_delete("billing_document", count)
        count = delete_all_records(cursor, "billing_client", "clinic_id", CLINIC_ID)
        log_delete("billing_client", count)
        conn.commit()

        # 5. PRESUPUESTOS
        print("5. Limpiando presupuestos...")
        count = delete_all_records(cursor, "budget", "clinic_id", CLINIC_ID)
        log_delete("budget", count)
        conn.commit()

        # 6. AGENDA
        print("6. Limpiando agenda...")
        count = delete_all_records(cursor, "schedule_block", "clinic_id", CLINIC_ID)
        log_delete("schedule_block", count)
        conn.commit()

        # 7. CARE PLANS
        print("7. Limpiando care plans...")
        count = delete_all_records(cursor, "planned_session", "clinic_id", CLINIC_ID)
        log_delete("planned_session", count)
        count = delete_all_records(cursor, "care_plan", "clinic_id", CLINIC_ID)
        log_delete("care_plan", count)
        conn.commit()

        # 8. CONSENTIMIENTOS
        print("8. Limpiando consentimientos...")
        count = delete_by_parent_id(cursor, "consent_instance_evidence", "consent_instance_id", consent_instance_ids)
        log_delete("consent_instance_evidence", count)
        count = delete_by_parent_id(cursor, "consent_instance_signature", "consent_instance_id", consent_instance_ids)
        log_delete("consent_instance_signature", count)
        count = delete_by_parent_id(cursor, "consent_instance_signer", "consent_instance_id", consent_instance_ids)
        log_delete("consent_instance_signer", count)
        count = delete_all_records(cursor, "consent_instance", "clinic_id", CLINIC_ID)
        log_delete("consent_instance", count)
        conn.commit()

        # 9. CONSENT TEMPLATES
        print("9. Limpiando plantillas de consentimiento...")
        count = delete_all_records(cursor, "consent_template", "clinic_id", CLINIC_ID)
        log_delete("consent_template", count)
        conn.commit()

        # 10. CUESTIONARIOS (form)
        print("10. Limpiando cuestionarios...")
        count = delete_all_records(cursor, "form_response", "clinic_id", CLINIC_ID)
        log_delete("form_response", count)
        count = delete_by_parent_id(cursor, "form_template_version", "template_id", form_template_ids)
        log_delete("form_template_version", count)
        count = delete_all_records(cursor, "form_template", "clinic_id", CLINIC_ID)
        log_delete("form_template", count)
        conn.commit()

        # 11. CATÁLOGO
        print("11. Limpiando catálogo...")
        count = delete_all_records(cursor, "treatment", "site_id", site_id)
        log_delete("treatment", count)

        # category - subcategorías primero (parent_id IS NOT NULL)
        if table_exists(cursor, "category"):
            cursor.execute("""
                DELETE FROM category
                WHERE clinic_id = %s
                  AND parent_id IS NOT NULL
            """, (CLINIC_ID,))
            count = cursor.rowcount
            log_delete("category (subcategorías)", count)

            # category - categorías principales
            count = delete_all_records(cursor, "category", "clinic_id", CLINIC_ID)
            log_delete("category (principales)", count)
        else:
            log.write(f"[SKIP] category: tabla no existe\n")

        count = delete_all_records(cursor, "service", "clinic_id", CLINIC_ID)
        log_delete("service", count)
        conn.commit()

        # 12. ROOMS
        print("12. Limpiando salas...")
        count = delete_all_records(cursor, "room", "clinic_id", CLINIC_ID)
        log_delete("room", count)
        conn.commit()

        # 13. DISPONIBILIDAD (horarios)
        print("13. Limpiando disponibilidad...")
        count = delete_by_parent_id(cursor, "availability_exception", "template_id", availability_template_ids)
        log_delete("availability_exception", count)
        count = delete_all_records(cursor, "availability_template", "clinic_id", CLINIC_ID)
        log_delete("availability_template", count)
        conn.commit()

        # 14. COMISIONES
        print("14. Limpiando comisiones...")
        count = delete_all_records(cursor, "commission_rule", "clinic_id", CLINIC_ID)
        log_delete("commission_rule", count)
        conn.commit()

        # 15. PACIENTES
        print("15. Limpiando pacientes...")
        count = delete_all_records(cursor, "patient", "clinic_id", CLINIC_ID)
        log_delete("patient", count)
        conn.commit()

        # 15b. CANALES DE ADQUISICIÓN (después de pacientes que tienen FK)
        print("15b. Limpiando canales de adquisición...")
        count = delete_all_records(cursor, "acquisition_channel", "clinic_id", CLINIC_ID)
        log_delete("acquisition_channel", count)
        conn.commit()

        # 16. PROFESIONALES
        print("16. Limpiando profesionales...")
        count = delete_all_records(cursor, "professional", "clinic_id", CLINIC_ID)
        log_delete("professional", count)
        conn.commit()

        # 17. USUARIOS
        print("17. Limpiando usuarios de clínica...")
        count = delete_all_records(cursor, "user_clinic", "clinic_id", CLINIC_ID)
        log_delete("user_clinic", count)
        # Borrar app_user solo si no tienen otras clínicas
        if user_ids and table_exists(cursor, "app_user"):
            cursor.execute("""
                DELETE FROM app_user
                WHERE id = ANY(%s)
                  AND NOT EXISTS (
                      SELECT 1 FROM user_clinic uc WHERE uc.user_id = app_user.id
                  )
            """, (user_ids,))
            count = cursor.rowcount
            log_delete("app_user (sin otras clínicas)", count)
        conn.commit()

        # 18. SITE
        print("18. Limpiando site...")
        count = delete_all_records(cursor, "site", "clinic_id", CLINIC_ID)
        log_delete("site", count)
        conn.commit()

        # 19. CLINIC
        print("19. Limpiando clinic...")
        if table_exists(cursor, "clinic"):
            cursor.execute("DELETE FROM clinic WHERE id = %s", (CLINIC_ID,))
            count = cursor.rowcount
            log_delete("clinic", count)
        conn.commit()

        # 20. COMPANY Y ORGANIZATION
        print("20. Limpiando company y organization...", flush=True)
        if COMPANY_ID:
            count = delete_all_records(cursor, "company", "id", COMPANY_ID)
            log_delete("company", count)

        # Borrar organization
        ORGANIZATION_ID = queries.ORGANIZATION_ID
        if ORGANIZATION_ID:
            count = delete_all_records(cursor, "organization", "id", ORGANIZATION_ID)
            log_delete("organization", count)
        conn.commit()

        # Calcular total
        total_deleted = sum(r[1] for r in results if r[1] > 0)

        # Resumen
        print("\n" + "=" * 60)
        print("RESUMEN DE LIMPIEZA TOTAL")
        print("=" * 60)

        log.write("\n" + "=" * 60 + "\n")
        log.write("RESUMEN\n")
        log.write("=" * 60 + "\n")

        for table, count in results:
            if count > 0:
                log.write(f"{table}: {count}\n")

        print(f"\nTOTAL: {total_deleted} registros borrados")
        log.write(f"\nTOTAL: {total_deleted}\n")
        logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")
        print(f"\nLog guardado en: {logs_dir}")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        log.write(f"\nERROR GENERAL: {e}\n")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cursor.close()
        conn.close()
        log.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Limpia todos los datos de la clínica")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    parser.add_argument("--force", "-f", action="store_true", help="Ejecutar sin confirmación")
    args = parser.parse_args()
    clean_all_clinic_data(args.clinic_folder, force=args.force)
