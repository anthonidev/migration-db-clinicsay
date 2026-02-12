"""
Limpia TODOS los datos de la clínica.

IMPORTANTE: Este script borra TODOS los registros de la clínica especificada.
Incluye: datos, configuración, clinic, site y company.

Orden de borrado (respeta foreign keys):
1. cash_movement, cash_session, cash_register
2. task, task_status_group
3. trigger_scheduled_execution, trigger_rule (automatización)
4. payment_allocation, payment, billing_item, billing_document, billing_client
5. receipt_item, receipt, billing_sequence
6. budget_proposal, budget
7. schedule_history_entry, schedule_block
8. supply_consumption, planned_session_visit_state, planned_session
9. clinical_note_comment, clinical_note, clinical_note_template
10. form_assignment, care_plan
11. consent_evidence, consent_instance_signature, consent_instance_signer, consent_instance
12. consent_template
13. form_response, form_template_version, form_template
14. commission_entry, commission_settlement, commission_rule
15. pack_item_definition, pack_instance, pack_definition
16. treatment, category, service
17. room, equipment
18. availability_exception, availability_template
19. patient_related_person_designation, patient_related_person
20. patient_email, patient_phone
21. patient_balance_movement, patient_balance
22. discount_application, discount_user_access, discount
23. gift_card_movement, gift_card, voucher
24. notification, document_references, binaries
25. patient
25b. acquisition_channel
26. professional
27. user_context_suspension, user_context_tracking, user_permission_override, user_signature_profile
28. user_site, user_clinic, app_user
29. site_billing_line, site_mrn_configuration, mrn_counter
30. product, supply, scheduling_policy, visit_status_definition
31. tag, kommo_bot, partner_agreement, payment_method
32. site
33. clinic
34. user_organization, company, organization
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


def delete_all_for_sites(cursor, table: str, site_ids: list) -> int:
    """Borra registros de una tabla para todos los site_ids."""
    if not table_exists(cursor, table):
        return -1
    if not site_ids:
        return 0
    total = 0
    for sid in site_ids:
        cursor.execute(f"DELETE FROM {table} WHERE site_id = %s", (sid,))
        total += cursor.rowcount
    return total


def clean_all_clinic_data(clinic_folder: str, force: bool = False):
    """Función principal de limpieza TOTAL"""
    # Cargar queries de la clínica
    queries = load_clinic_queries(clinic_folder)
    CLINIC_ID = queries.CLINIC_ID
    SITE_IDS = queries.SITE_IDS
    COMPANY_ID = queries.COMPANY_ID
    ORGANIZATION_ID = queries.ORGANIZATION_ID

    print("=" * 60, flush=True)
    print("LIMPIEZA TOTAL DE LA CLÍNICA", flush=True)
    print("=" * 60, flush=True)

    print(f"\nClinic ID: {CLINIC_ID}", flush=True)
    print(f"Site IDs: {SITE_IDS}", flush=True)
    print(f"Company ID: {COMPANY_ID}", flush=True)
    print(f"Organization ID: {ORGANIZATION_ID}", flush=True)
    print("\n*** SE BORRARÁN TODOS LOS DATOS DE LA CLÍNICA ***", flush=True)
    print("*** INCLUYENDO: clinic, site, company ***", flush=True)

    if not force:
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
        log.write(f"Limpieza TOTAL de clínica - {datetime.now().isoformat()}\n")
        log.write(f"Clinic ID: {CLINIC_ID}\n")
        log.write(f"Site IDs: {SITE_IDS}\n")
        log.write(f"Company ID: {COMPANY_ID}\n")
        log.write(f"Organization ID: {ORGANIZATION_ID}\n")
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
        billing_document_ids = get_ids_from_table(cursor, "billing_document", "id", "clinic_id", CLINIC_ID)
        schedule_block_ids = get_ids_from_table(cursor, "schedule_block", "id", "clinic_id", CLINIC_ID)
        planned_session_ids = get_ids_from_table(cursor, "planned_session", "id", "clinic_id", CLINIC_ID)
        discount_ids = get_ids_from_table(cursor, "discount", "id", "clinic_id", CLINIC_ID)
        gift_card_ids = get_ids_from_table(cursor, "gift_card", "id", "clinic_id", CLINIC_ID)
        pack_definition_ids = get_ids_from_table(cursor, "pack_definition", "id", "clinic_id", CLINIC_ID)
        patient_related_person_ids = get_ids_from_table(cursor, "patient_related_person", "id", "clinic_id", CLINIC_ID)
        patient_balance_ids = get_ids_from_table(cursor, "patient_balance", "id", "clinic_id", CLINIC_ID)
        receipt_ids = get_ids_from_table(cursor, "receipt", "id", "clinic_id", CLINIC_ID)

        # 1. CAJA (todos los sites)
        print("1. Limpiando datos de caja...")
        count = delete_all_for_sites(cursor, "cash_movement", SITE_IDS)
        log_delete("cash_movement", count)
        count = delete_all_for_sites(cursor, "cash_session", SITE_IDS)
        log_delete("cash_session", count)
        count = delete_all_records(cursor, "cash_register", "clinic_id", CLINIC_ID)
        log_delete("cash_register", count)
        conn.commit()

        # 2. TAREAS
        print("2. Limpiando tareas...")
        count = delete_all_records(cursor, "task", "clinic_id", CLINIC_ID)
        log_delete("task", count)
        count = delete_all_for_sites(cursor, "task_status_group", SITE_IDS)
        log_delete("task_status_group", count)
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
        count = delete_all_records(cursor, "payment_allocation", "clinic_id", CLINIC_ID)
        log_delete("payment_allocation", count)
        count = delete_all_records(cursor, "payment", "clinic_id", CLINIC_ID)
        log_delete("payment", count)
        count = delete_by_parent_id(cursor, "billing_item", "billing_document_id", billing_document_ids)
        log_delete("billing_item", count)
        count = delete_all_records(cursor, "billing_document", "clinic_id", CLINIC_ID)
        log_delete("billing_document", count)
        count = delete_all_records(cursor, "billing_client", "clinic_id", CLINIC_ID)
        log_delete("billing_client", count)
        conn.commit()

        # 5. RECIBOS Y SECUENCIAS
        print("5. Limpiando recibos y secuencias...")
        count = delete_by_parent_id(cursor, "receipt_item", "receipt_id", receipt_ids)
        log_delete("receipt_item", count)
        count = delete_all_records(cursor, "receipt", "clinic_id", CLINIC_ID)
        log_delete("receipt", count)
        count = delete_all_records(cursor, "billing_sequence", "clinic_id", CLINIC_ID)
        log_delete("billing_sequence", count)
        conn.commit()

        # 6. PRESUPUESTOS
        print("6. Limpiando presupuestos...")
        count = delete_all_records(cursor, "budget_proposal", "clinic_id", CLINIC_ID)
        log_delete("budget_proposal", count)
        count = delete_all_records(cursor, "budget", "clinic_id", CLINIC_ID)
        log_delete("budget", count)
        conn.commit()

        # 7. AGENDA
        print("7. Limpiando agenda...")
        count = delete_by_parent_id(cursor, "schedule_history_entry", "schedule_block_id", schedule_block_ids)
        log_delete("schedule_history_entry", count)
        count = delete_all_records(cursor, "schedule_block", "clinic_id", CLINIC_ID)
        log_delete("schedule_block", count)
        conn.commit()

        # 8. SESIONES PLANIFICADAS
        print("8. Limpiando sesiones planificadas...")
        count = delete_all_records(cursor, "supply_consumption", "clinic_id", CLINIC_ID)
        log_delete("supply_consumption", count)
        count = delete_by_parent_id(cursor, "planned_session_visit_state", "planned_session_id", planned_session_ids)
        log_delete("planned_session_visit_state", count)
        count = delete_all_records(cursor, "planned_session", "clinic_id", CLINIC_ID)
        log_delete("planned_session", count)
        conn.commit()

        # 9. NOTAS CLÍNICAS
        print("9. Limpiando notas clínicas...")
        count = delete_all_records(cursor, "clinical_note_comment", "clinic_id", CLINIC_ID)
        log_delete("clinical_note_comment", count)
        count = delete_all_records(cursor, "clinical_note", "clinic_id", CLINIC_ID)
        log_delete("clinical_note", count)
        count = delete_all_records(cursor, "clinical_note_template", "clinic_id", CLINIC_ID)
        log_delete("clinical_note_template", count)
        conn.commit()

        # 10. CARE PLANS Y FORM ASSIGNMENTS
        print("10. Limpiando care plans...")
        count = delete_all_records(cursor, "form_assignment", "clinic_id", CLINIC_ID)
        log_delete("form_assignment", count)
        count = delete_all_records(cursor, "care_plan", "clinic_id", CLINIC_ID)
        log_delete("care_plan", count)
        conn.commit()

        # 11. CONSENTIMIENTOS
        print("11. Limpiando consentimientos...")
        count = delete_by_parent_id(cursor, "consent_evidence", "consent_instance_id", consent_instance_ids)
        log_delete("consent_evidence", count)
        count = delete_by_parent_id(cursor, "consent_instance_signature", "consent_instance_id", consent_instance_ids)
        log_delete("consent_instance_signature", count)
        count = delete_by_parent_id(cursor, "consent_instance_signer", "consent_instance_id", consent_instance_ids)
        log_delete("consent_instance_signer", count)
        count = delete_all_records(cursor, "consent_instance", "clinic_id", CLINIC_ID)
        log_delete("consent_instance", count)
        conn.commit()

        # 12. CONSENT TEMPLATES
        print("12. Limpiando plantillas de consentimiento...")
        count = delete_all_records(cursor, "consent_template", "clinic_id", CLINIC_ID)
        log_delete("consent_template", count)
        conn.commit()

        # 13. CUESTIONARIOS (form)
        print("13. Limpiando cuestionarios...")
        count = delete_all_records(cursor, "form_response", "clinic_id", CLINIC_ID)
        log_delete("form_response", count)
        count = delete_by_parent_id(cursor, "form_template_version", "template_id", form_template_ids)
        log_delete("form_template_version", count)
        count = delete_all_records(cursor, "form_template", "clinic_id", CLINIC_ID)
        log_delete("form_template", count)
        conn.commit()

        # 14. COMISIONES
        print("14. Limpiando comisiones...")
        count = delete_all_records(cursor, "commission_entry", "clinic_id", CLINIC_ID)
        log_delete("commission_entry", count)
        count = delete_all_records(cursor, "commission_settlement", "clinic_id", CLINIC_ID)
        log_delete("commission_settlement", count)
        count = delete_all_records(cursor, "commission_rule", "clinic_id", CLINIC_ID)
        log_delete("commission_rule", count)
        conn.commit()

        # 15. PACKS
        print("15. Limpiando packs...")
        count = delete_by_parent_id(cursor, "pack_item_definition", "pack_definition_id", pack_definition_ids)
        log_delete("pack_item_definition", count)
        count = delete_all_records(cursor, "pack_instance", "clinic_id", CLINIC_ID)
        log_delete("pack_instance", count)
        count = delete_all_records(cursor, "pack_definition", "clinic_id", CLINIC_ID)
        log_delete("pack_definition", count)
        conn.commit()

        # 16. CATÁLOGO
        print("16. Limpiando catálogo...")
        count = delete_all_for_sites(cursor, "treatment", SITE_IDS)
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

            count = delete_all_records(cursor, "category", "clinic_id", CLINIC_ID)
            log_delete("category (principales)", count)
        else:
            log.write("[SKIP] category: tabla no existe\n")

        count = delete_all_records(cursor, "service", "clinic_id", CLINIC_ID)
        log_delete("service", count)
        conn.commit()

        # 17. SALAS Y EQUIPAMIENTO
        print("17. Limpiando salas y equipamiento...")
        count = delete_all_records(cursor, "equipment", "clinic_id", CLINIC_ID)
        log_delete("equipment", count)
        count = delete_all_records(cursor, "room", "clinic_id", CLINIC_ID)
        log_delete("room", count)
        conn.commit()

        # 18. DISPONIBILIDAD (horarios)
        print("18. Limpiando disponibilidad...")
        count = delete_by_parent_id(cursor, "availability_exception", "template_id", availability_template_ids)
        log_delete("availability_exception", count)
        count = delete_all_records(cursor, "availability_template", "clinic_id", CLINIC_ID)
        log_delete("availability_template", count)
        conn.commit()

        # 19. PERSONAS RELACIONADAS CON PACIENTES
        print("19. Limpiando personas relacionadas...")
        count = delete_by_parent_id(cursor, "patient_related_person_designation", "patient_related_person_id", patient_related_person_ids)
        log_delete("patient_related_person_designation", count)
        count = delete_all_records(cursor, "patient_related_person", "clinic_id", CLINIC_ID)
        log_delete("patient_related_person", count)
        conn.commit()

        # 20. CONTACTOS DE PACIENTES
        print("20. Limpiando contactos de pacientes...")
        count = delete_all_records(cursor, "patient_email", "clinic_id", CLINIC_ID)
        log_delete("patient_email", count)
        count = delete_all_records(cursor, "patient_phone", "clinic_id", CLINIC_ID)
        log_delete("patient_phone", count)
        conn.commit()

        # 21. BALANCES DE PACIENTES
        print("21. Limpiando balances de pacientes...")
        count = delete_by_parent_id(cursor, "patient_balance_movement", "patient_balance_id", patient_balance_ids)
        log_delete("patient_balance_movement", count)
        count = delete_all_records(cursor, "patient_balance", "clinic_id", CLINIC_ID)
        log_delete("patient_balance", count)
        conn.commit()

        # 22. DESCUENTOS
        print("22. Limpiando descuentos...")
        count = delete_by_parent_id(cursor, "discount_application", "discount_id", discount_ids)
        log_delete("discount_application", count)
        count = delete_by_parent_id(cursor, "discount_user_access", "discount_id", discount_ids)
        log_delete("discount_user_access", count)
        count = delete_all_records(cursor, "discount", "clinic_id", CLINIC_ID)
        log_delete("discount", count)
        conn.commit()

        # 23. GIFT CARDS Y VOUCHERS
        print("23. Limpiando gift cards y vouchers...")
        count = delete_by_parent_id(cursor, "gift_card_movement", "gift_card_id", gift_card_ids)
        log_delete("gift_card_movement", count)
        count = delete_all_records(cursor, "gift_card", "clinic_id", CLINIC_ID)
        log_delete("gift_card", count)
        count = delete_all_records(cursor, "voucher", "clinic_id", CLINIC_ID)
        log_delete("voucher", count)
        conn.commit()

        # 24. NOTIFICACIONES, DOCUMENTOS
        print("24. Limpiando notificaciones y documentos...")
        count = delete_all_records(cursor, "notification", "clinic_id", CLINIC_ID)
        log_delete("notification", count)
        count = delete_all_records(cursor, "binaries", "clinic_id", CLINIC_ID)
        log_delete("binaries", count)
        count = delete_all_records(cursor, "document_references", "clinic_id", CLINIC_ID)
        log_delete("document_references", count)
        conn.commit()

        # 25. PACIENTES
        print("25. Limpiando pacientes...")
        count = delete_all_records(cursor, "patient", "clinic_id", CLINIC_ID)
        log_delete("patient", count)
        conn.commit()

        # 25b. CANALES DE ADQUISICIÓN
        print("25b. Limpiando canales de adquisición...")
        count = delete_all_records(cursor, "acquisition_channel", "clinic_id", CLINIC_ID)
        log_delete("acquisition_channel", count)
        conn.commit()

        # 26. PROFESIONALES
        print("26. Limpiando profesionales...")
        count = delete_all_records(cursor, "professional", "clinic_id", CLINIC_ID)
        log_delete("professional", count)
        conn.commit()

        # 27. CONTEXTOS Y PERMISOS DE USUARIO
        print("27. Limpiando contextos y permisos de usuario...")
        count = delete_all_records(cursor, "user_permission_override", "clinic_id", CLINIC_ID)
        log_delete("user_permission_override", count)
        count = delete_all_records(cursor, "user_signature_profile", "clinic_id", CLINIC_ID)
        log_delete("user_signature_profile", count)
        # user_context_tracking: borrar por primary_clinic_id
        if table_exists(cursor, "user_context_tracking"):
            cursor.execute("DELETE FROM user_context_tracking WHERE primary_clinic_id = %s", (CLINIC_ID,))
            log_delete("user_context_tracking", cursor.rowcount)
        # user_context_suspension: borrar donde context_type='CLINIC' y context_id=CLINIC_ID
        if table_exists(cursor, "user_context_suspension"):
            cursor.execute("DELETE FROM user_context_suspension WHERE context_type = 'CLINIC' AND context_id = %s", (CLINIC_ID,))
            log_delete("user_context_suspension", cursor.rowcount)
        conn.commit()

        # 28. USUARIOS
        print("28. Limpiando usuarios de clínica...")
        # user_site: borrar por site_ids
        if table_exists(cursor, "user_site") and SITE_IDS:
            placeholders = ','.join(['%s'] * len(SITE_IDS))
            cursor.execute(f"DELETE FROM user_site WHERE site_id IN ({placeholders})", SITE_IDS)
            log_delete("user_site", cursor.rowcount)
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

        # 29. CONFIG DE SITE
        print("29. Limpiando configuración de sites...")
        count = delete_all_for_sites(cursor, "site_billing_line", SITE_IDS)
        log_delete("site_billing_line", count)
        count = delete_all_for_sites(cursor, "site_mrn_configuration", SITE_IDS)
        log_delete("site_mrn_configuration", count)
        count = delete_all_for_sites(cursor, "mrn_counter", SITE_IDS)
        log_delete("mrn_counter", count)
        conn.commit()

        # 30. PRODUCTOS, SUPPLIES, POLÍTICAS
        print("30. Limpiando productos y políticas...")
        count = delete_all_for_sites(cursor, "product", SITE_IDS)
        log_delete("product", count)
        count = delete_all_for_sites(cursor, "supply", SITE_IDS)
        log_delete("supply", count)
        count = delete_all_records(cursor, "scheduling_policy", "clinic_id", CLINIC_ID)
        log_delete("scheduling_policy", count)
        count = delete_all_records(cursor, "visit_status_definition", "clinic_id", CLINIC_ID)
        log_delete("visit_status_definition", count)
        conn.commit()

        # 31. TAGS, INTEGRACIONES, OTROS
        print("31. Limpiando tags e integraciones...")
        count = delete_all_records(cursor, "tag", "clinic_id", CLINIC_ID)
        log_delete("tag", count)
        count = delete_all_records(cursor, "kommo_bot", "clinic_id", CLINIC_ID)
        log_delete("kommo_bot", count)
        count = delete_all_records(cursor, "partner_agreement", "clinic_id", CLINIC_ID)
        log_delete("partner_agreement", count)
        count = delete_all_records(cursor, "payment_method", "clinic_id", CLINIC_ID)
        log_delete("payment_method", count)
        conn.commit()

        # 32. SITE
        print("32. Limpiando site...")
        count = delete_all_records(cursor, "site", "clinic_id", CLINIC_ID)
        log_delete("site", count)
        conn.commit()

        # 33. CLINIC
        print("33. Limpiando clinic...")
        if table_exists(cursor, "clinic"):
            cursor.execute("DELETE FROM clinic WHERE id = %s", (CLINIC_ID,))
            count = cursor.rowcount
            log_delete("clinic", count)
        conn.commit()

        # 34. COMPANY Y ORGANIZATION
        print("34. Limpiando company y organization...", flush=True)
        if ORGANIZATION_ID:
            count = delete_all_records(cursor, "user_organization", "organization_id", ORGANIZATION_ID)
            log_delete("user_organization", count)
        if COMPANY_ID:
            count = delete_all_records(cursor, "company", "id", COMPANY_ID)
            log_delete("company", count)
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
