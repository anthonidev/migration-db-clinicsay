"""
Limpia TODOS los datos de una clínica por su ID.

Script independiente que no requiere carpeta de clínica ni queries.py.
Busca la información de la clínica directamente en la base de datos.

Orden de borrado (respeta foreign keys del schema clinicsay_schema.sql):
1. cash_movement_file, cash_movement, cash_session_access, cash_session_incident, cash_session_count, cash_session, cash_register
2. task, task_status_group
3. trigger_scheduled_execution, trigger_rule (automatización)
4. payment_detail, payment_allocation, payment, billing_document_file, billing_item, billing_document, billing_client
5. receipt_item, receipt, billing_sequence
6. budget_proposal, budget, budget_status
7. schedule_history_entry, schedule_block
8. supply_consumption, planned_session_visit_state, planned_session
9. clinical_note_comment, clinical_note, clinical_note_template
10. form_assignment, care_plan
11. consent_evidence, consent_instance_signature, consent_instance_signer, consent_instance
12. consent_template
13. form_response, form_template_version, form_template
14. commission_entry, commission_settlement, commission_rule
15. pack_consumption, pack_payment_allocation, pack_item_definition, pack_instance, pack_definition
16. treatment, category, service
17. room, equipment
18. availability_exception, availability_template
19. patient_related_person_designation, patient_related_person
20. patient_email, patient_phone
21. patient_balance_movement, patient_balance
22. discount_application, discount_user_access, discount
23. gift_card_movement, gift_card, voucher
24. notification, binaries, document_references
25. patient
25b. acquisition_channel
26. professional, professional_type
27. user_context_suspension, user_context_tracking, user_permission_override, user_signature_profile
28. user_site, user_clinic, app_user
29. site_billing_line, site_mrn_configuration, mrn_counter
30. product, supply, scheduling_policy, visit_status_definition
31. tag, kommo_bot, partner_agreement, payment_method
32. site
33. clinic
34. user_organization, company, organization
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

from config.database import get_db_config
from ui import (
    print_header,
    print_subheader,
    info,
    success,
    warning,
    error,
    step,
    ask,
    confirm,
    print_key_value,
    print_separator,
)


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


def table_exists(cursor, table: str) -> bool:
    """Verifica si una tabla existe en la base de datos."""
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """,
        (table,),
    )
    return cursor.fetchone()["exists"]


def get_clinic_info(cursor, clinic_id: str) -> dict | None:
    """Busca la información de la clínica en la BD."""
    if not table_exists(cursor, "clinic"):
        return None

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

    organization_id = row["organization_id"]
    company_id = row["default_issuer_company_id"]

    # Si no hay default_issuer_company_id, buscar company por organization_id
    if not company_id and organization_id and table_exists(cursor, "company"):
        cursor.execute("SELECT id FROM company WHERE organization_id = %s", (organization_id,))
        company_row = cursor.fetchone()
        if company_row:
            company_id = company_row["id"]

    # Obtener site_ids
    site_ids = []
    if table_exists(cursor, "site"):
        cursor.execute("SELECT id FROM site WHERE clinic_id = %s", (clinic_id,))
        site_ids = [r["id"] for r in cursor.fetchall()]

    return {
        "clinic_id": row["id"],
        "clinic_name": row["name"],
        "company_id": company_id,
        "organization_id": organization_id,
        "site_ids": site_ids,
    }


def delete_all_records(cursor, table: str, id_column: str, filter_value: str) -> int:
    """Borra TODOS los registros de una tabla por filtro."""
    if not table_exists(cursor, table):
        return -1
    if filter_value is None:
        return 0
    query = f"DELETE FROM {table} WHERE {id_column} = %s"
    cursor.execute(query, (filter_value,))
    return cursor.rowcount


def delete_in_batches(conn, cursor, table: str, id_column: str, filter_value: str, batch_size: int = 1000) -> int:
    """Borra registros en lotes para evitar locks largos y timeouts."""
    if not table_exists(cursor, table):
        return -1
    if filter_value is None:
        return 0
    total = 0
    while True:
        cursor.execute(
            f"DELETE FROM {table} WHERE id IN (SELECT id FROM {table} WHERE {id_column} = %s LIMIT %s)",
            (filter_value, batch_size),
        )
        deleted = cursor.rowcount
        conn.commit()
        total += deleted
        if deleted > 0:
            step(f"  {table}: {total} borrados...")
        if deleted < batch_size:
            break
    return total


def delete_by_parent_id(cursor, table: str, parent_column: str, parent_ids: list) -> int:
    """Borra registros de una tabla hija por IDs de la tabla padre."""
    if not table_exists(cursor, table):
        return -1
    if not parent_ids:
        return 0
    placeholders = ",".join(["%s"] * len(parent_ids))
    query = f"DELETE FROM {table} WHERE {parent_column} IN ({placeholders})"
    cursor.execute(query, parent_ids)
    return cursor.rowcount


def delete_by_parent_site_ids(cursor, child_table: str, parent_table: str, fk_column: str, site_ids: list) -> int:
    """
    Borra registros de una tabla hija usando subconsulta por site_ids de la tabla padre.
    Útil para tablas hijas sin site_id propio (ej: cash_session_access).
    """
    if not table_exists(cursor, child_table):
        return -1
    if not site_ids:
        return 0
    placeholders = ",".join(["%s"] * len(site_ids))
    query = f"""
        DELETE FROM {child_table}
        WHERE {fk_column} IN (
            SELECT id FROM {parent_table} WHERE site_id IN ({placeholders})
        )
    """
    cursor.execute(query, site_ids)
    return cursor.rowcount


def get_ids_from_table(cursor, table: str, id_column: str, filter_column: str, filter_value: str) -> list:
    """Obtiene lista de IDs de una tabla."""
    if not table_exists(cursor, table):
        return []
    cursor.execute(f"SELECT {id_column} FROM {table} WHERE {filter_column} = %s", (filter_value,))
    return [row[id_column] for row in cursor.fetchall()]


def get_ids_from_table_for_sites(cursor, table: str, id_column: str, site_ids: list) -> list:
    """Obtiene lista de IDs de una tabla filtrando por site_id IN (...)."""
    if not table_exists(cursor, table):
        return []
    if not site_ids:
        return []
    placeholders = ",".join(["%s"] * len(site_ids))
    cursor.execute(f"SELECT {id_column} FROM {table} WHERE site_id IN ({placeholders})", site_ids)
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


def clean_clinic_by_id():
    """Función principal: pide el clinic_id y limpia todos sus datos."""
    print_header("Limpiar clínica por ID")

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

        CLINIC_ID = clinic_info["clinic_id"]
        SITE_IDS = clinic_info["site_ids"]
        COMPANY_ID = clinic_info["company_id"]
        ORGANIZATION_ID = clinic_info["organization_id"]

        # Mostrar info
        print_subheader("Información de la clínica")
        print_key_value({
            "Nombre": clinic_info["clinic_name"],
            "Clinic ID": CLINIC_ID,
            "Site IDs": ", ".join(SITE_IDS) if SITE_IDS else "(sin sites)",
            "Company ID": COMPANY_ID or "(sin company)",
            "Organization ID": ORGANIZATION_ID or "(sin organization)",
        })

        warning("SE BORRARÁN TODOS LOS DATOS DE ESTA CLÍNICA")
        warning("Incluyendo: datos, configuración, clinic, sites, company y organization")
        warning("Esta acción NO se puede deshacer")

        confirmation = ask("Escribe 'BORRAR TODO' para continuar").strip()
        if confirmation != "BORRAR TODO":
            info("Operación cancelada")
            return

        print_subheader("Iniciando limpieza")
        results = []

        def log_delete(table_name, count):
            if count >= 0:
                results.append((table_name, count))
                if count > 0:
                    step(f"{table_name}: {count} registros borrados")
            else:
                info(f"{table_name}: tabla no existe, omitida")

        # Obtener IDs necesarios para borrados en cascada
        consent_instance_ids = get_ids_from_table(cursor, "consent_instance", "id", "clinic_id", CLINIC_ID)
        form_template_ids = get_ids_from_table(cursor, "form_template", "id", "clinic_id", CLINIC_ID)
        availability_template_ids = get_ids_from_table(cursor, "availability_template", "id", "clinic_id", CLINIC_ID)
        user_ids = get_ids_from_table(cursor, "user_clinic", "user_id", "clinic_id", CLINIC_ID)
        billing_document_ids = get_ids_from_table(cursor, "billing_document", "id", "clinic_id", CLINIC_ID)
        payment_ids = get_ids_from_table(cursor, "payment", "id", "clinic_id", CLINIC_ID)
        schedule_block_ids = get_ids_from_table(cursor, "schedule_block", "id", "clinic_id", CLINIC_ID)
        planned_session_ids = get_ids_from_table(cursor, "planned_session", "id", "clinic_id", CLINIC_ID)
        discount_ids = get_ids_from_table(cursor, "discount", "id", "clinic_id", CLINIC_ID)
        gift_card_ids = get_ids_from_table(cursor, "gift_card", "id", "clinic_id", CLINIC_ID)
        pack_definition_ids = get_ids_from_table(cursor, "pack_definition", "id", "clinic_id", CLINIC_ID)
        pack_instance_ids = get_ids_from_table(cursor, "pack_instance", "id", "clinic_id", CLINIC_ID)
        patient_related_person_ids = get_ids_from_table(cursor, "patient_related_person", "id", "clinic_id", CLINIC_ID)
        patient_balance_ids = get_ids_from_table(cursor, "patient_balance", "id", "clinic_id", CLINIC_ID)
        receipt_ids = get_ids_from_table(cursor, "receipt", "id", "clinic_id", CLINIC_ID)

        # 1. CAJA
        info("1. Limpiando datos de caja...")

        # Hijas de cash_movement
        log_delete("cash_movement_file", delete_all_for_sites(cursor, "cash_movement_file", SITE_IDS))
        log_delete("cash_movement", delete_all_for_sites(cursor, "cash_movement", SITE_IDS))

        # Hijas de cash_session (schema actualizado: ON DELETE RESTRICT)
        # cash_session_access no tiene site_id, usar subconsulta
        log_delete(
            "cash_session_access",
            delete_by_parent_site_ids(cursor, "cash_session_access", "cash_session", "cash_session_id", SITE_IDS),
        )
        log_delete(
            "cash_session_incident",
            delete_by_parent_site_ids(cursor, "cash_session_incident", "cash_session", "cash_session_id", SITE_IDS),
        )
        # cash_session_count tiene site_id propio
        log_delete("cash_session_count", delete_all_for_sites(cursor, "cash_session_count", SITE_IDS))

        log_delete("cash_session", delete_all_for_sites(cursor, "cash_session", SITE_IDS))
        log_delete("cash_register", delete_all_records(cursor, "cash_register", "clinic_id", CLINIC_ID))
        conn.commit()

        # 2. TAREAS
        info("2. Limpiando tareas...")
        log_delete("task_comment", delete_all_records(cursor, "task_comment", "clinic_id", CLINIC_ID))
        log_delete("task", delete_all_for_sites(cursor, "task", SITE_IDS))
        log_delete("task_status_group", delete_all_for_sites(cursor, "task_status_group", SITE_IDS))
        conn.commit()

        # 3. AUTOMATIZACIÓN
        info("3. Limpiando reglas de automatización...")
        trigger_rule_ids = get_ids_from_table(cursor, "trigger_rule", "id", "clinic_id", CLINIC_ID)
        log_delete("trigger_scheduled_execution", delete_by_parent_id(cursor, "trigger_scheduled_execution", "trigger_rule_id", trigger_rule_ids))
        log_delete("trigger_rule", delete_all_records(cursor, "trigger_rule", "clinic_id", CLINIC_ID))
        conn.commit()

        # 4. FACTURACIÓN
        info("4. Limpiando facturación...")
        log_delete("payment_detail", delete_by_parent_id(cursor, "payment_detail", "payment_id", payment_ids))
        log_delete("payment_allocation", delete_all_records(cursor, "payment_allocation", "clinic_id", CLINIC_ID))
        log_delete("payment", delete_all_records(cursor, "payment", "clinic_id", CLINIC_ID))
        log_delete("billing_document_file", delete_by_parent_id(cursor, "billing_document_file", "billing_document_id", billing_document_ids))
        log_delete("billing_item", delete_by_parent_id(cursor, "billing_item", "billing_document_id", billing_document_ids))
        log_delete("billing_document", delete_all_records(cursor, "billing_document", "clinic_id", CLINIC_ID))
        log_delete("billing_client", delete_all_records(cursor, "billing_client", "clinic_id", CLINIC_ID))
        conn.commit()

        # 5. RECIBOS Y SECUENCIAS
        info("5. Limpiando recibos y secuencias...")
        log_delete("receipt_item", delete_by_parent_id(cursor, "receipt_item", "receipt_id", receipt_ids))
        log_delete("receipt", delete_all_records(cursor, "receipt", "clinic_id", CLINIC_ID))
        log_delete("billing_sequence", delete_all_records(cursor, "billing_sequence", "clinic_id", CLINIC_ID))
        conn.commit()

        # 6. PRESUPUESTOS
        info("6. Limpiando presupuestos...")
        log_delete("budget_proposal", delete_all_records(cursor, "budget_proposal", "clinic_id", CLINIC_ID))
        log_delete("budget", delete_all_records(cursor, "budget", "clinic_id", CLINIC_ID))
        log_delete("budget_status", delete_all_for_sites(cursor, "budget_status", SITE_IDS))
        conn.commit()

        # 7. AGENDA
        info("7. Limpiando agenda...")
        log_delete("schedule_history_entry", delete_by_parent_id(cursor, "schedule_history_entry", "schedule_block_id", schedule_block_ids))
        log_delete("schedule_block", delete_in_batches(conn, cursor, "schedule_block", "clinic_id", CLINIC_ID))
        conn.commit()

        # 8. SESIONES PLANIFICADAS
        info("8. Limpiando sesiones planificadas...")
        log_delete("supply_consumption", delete_all_records(cursor, "supply_consumption", "clinic_id", CLINIC_ID))
        log_delete("planned_session_visit_state", delete_by_parent_id(cursor, "planned_session_visit_state", "planned_session_id", planned_session_ids))
        log_delete("planned_session", delete_in_batches(conn, cursor, "planned_session", "clinic_id", CLINIC_ID))
        conn.commit()

        # 9. NOTAS CLÍNICAS
        info("9. Limpiando notas clínicas...")
        # clinical_note tiene FK auto-referencial (amended_from_id) que hace el DELETE muy lento.
        # Deshabilitamos triggers de FK temporalmente para borrado masivo.
        if table_exists(cursor, "clinical_note"):
            cursor.execute("ALTER TABLE clinical_note DISABLE TRIGGER ALL")
            cursor.execute("ALTER TABLE clinical_note_comment DISABLE TRIGGER ALL")
            conn.commit()
            log_delete("clinical_note_comment", delete_in_batches(conn, cursor, "clinical_note_comment", "clinic_id", CLINIC_ID, batch_size=5000))
            log_delete("clinical_note", delete_in_batches(conn, cursor, "clinical_note", "clinic_id", CLINIC_ID, batch_size=5000))
            cursor.execute("ALTER TABLE clinical_note_comment ENABLE TRIGGER ALL")
            cursor.execute("ALTER TABLE clinical_note ENABLE TRIGGER ALL")
            conn.commit()
        log_delete("clinical_note_template", delete_all_records(cursor, "clinical_note_template", "clinic_id", CLINIC_ID))
        conn.commit()

        # 10. CARE PLANS Y FORM ASSIGNMENTS
        info("10. Limpiando care plans...")
        # care_plan es referenciada por muchas tablas (budget, clinical_note, pack_instance,
        # planned_session, form_assignment, form_response) con ON DELETE SET NULL/CASCADE.
        # Deshabilitamos triggers para evitar verificación de FK en cada fila.
        if table_exists(cursor, "care_plan"):
            cursor.execute("ALTER TABLE care_plan DISABLE TRIGGER ALL")
            cursor.execute("ALTER TABLE form_assignment DISABLE TRIGGER ALL")
            conn.commit()
            log_delete("form_assignment", delete_in_batches(conn, cursor, "form_assignment", "clinic_id", CLINIC_ID, batch_size=5000))
            log_delete("care_plan", delete_in_batches(conn, cursor, "care_plan", "clinic_id", CLINIC_ID, batch_size=5000))
            cursor.execute("ALTER TABLE form_assignment ENABLE TRIGGER ALL")
            cursor.execute("ALTER TABLE care_plan ENABLE TRIGGER ALL")
            conn.commit()

        # 11. CONSENTIMIENTOS
        info("11. Limpiando consentimientos...")
        log_delete("consent_evidence", delete_by_parent_id(cursor, "consent_evidence", "consent_instance_id", consent_instance_ids))
        log_delete("consent_instance_signature", delete_by_parent_id(cursor, "consent_instance_signature", "consent_instance_id", consent_instance_ids))
        log_delete("consent_instance_signer", delete_by_parent_id(cursor, "consent_instance_signer", "consent_instance_id", consent_instance_ids))
        log_delete("consent_instance", delete_all_records(cursor, "consent_instance", "clinic_id", CLINIC_ID))
        conn.commit()

        # 12. CONSENT TEMPLATES
        info("12. Limpiando plantillas de consentimiento...")
        log_delete("consent_template", delete_all_records(cursor, "consent_template", "clinic_id", CLINIC_ID))
        conn.commit()

        # 13. CUESTIONARIOS
        info("13. Limpiando cuestionarios...")
        log_delete("form_response", delete_all_records(cursor, "form_response", "clinic_id", CLINIC_ID))
        log_delete("form_template_version", delete_by_parent_id(cursor, "form_template_version", "template_id", form_template_ids))
        log_delete("form_template", delete_all_records(cursor, "form_template", "clinic_id", CLINIC_ID))
        conn.commit()

        # 14. COMISIONES
        info("14. Limpiando comisiones...")
        log_delete("commission_entry", delete_all_records(cursor, "commission_entry", "clinic_id", CLINIC_ID))
        log_delete("commission_settlement", delete_all_records(cursor, "commission_settlement", "clinic_id", CLINIC_ID))
        log_delete("commission_rule", delete_all_records(cursor, "commission_rule", "clinic_id", CLINIC_ID))
        conn.commit()

        # 15. PACKS
        info("15. Limpiando packs...")
        log_delete("pack_consumption", delete_by_parent_id(cursor, "pack_consumption", "pack_instance_id", pack_instance_ids))
        log_delete("pack_payment_allocation", delete_all_records(cursor, "pack_payment_allocation", "clinic_id", CLINIC_ID))
        log_delete("pack_item_definition", delete_by_parent_id(cursor, "pack_item_definition", "pack_definition_id", pack_definition_ids))
        log_delete("pack_instance", delete_all_records(cursor, "pack_instance", "clinic_id", CLINIC_ID))
        log_delete("pack_definition", delete_all_records(cursor, "pack_definition", "clinic_id", CLINIC_ID))
        conn.commit()

        # 16. CATÁLOGO
        info("16. Limpiando catálogo...")
        log_delete("treatment", delete_all_for_sites(cursor, "treatment", SITE_IDS))
        if table_exists(cursor, "category"):
            cursor.execute("DELETE FROM category WHERE clinic_id = %s AND parent_id IS NOT NULL", (CLINIC_ID,))
            log_delete("category (subcategorías)", cursor.rowcount)
            log_delete("category (principales)", delete_all_records(cursor, "category", "clinic_id", CLINIC_ID))
        log_delete("service", delete_all_records(cursor, "service", "clinic_id", CLINIC_ID))
        conn.commit()

        # 17. SALAS Y EQUIPAMIENTO
        info("17. Limpiando salas y equipamiento...")
        log_delete("equipment", delete_all_records(cursor, "equipment", "clinic_id", CLINIC_ID))
        log_delete("room", delete_all_records(cursor, "room", "clinic_id", CLINIC_ID))
        conn.commit()

        # 18. DISPONIBILIDAD
        info("18. Limpiando disponibilidad...")
        log_delete("availability_exception", delete_by_parent_id(cursor, "availability_exception", "template_id", availability_template_ids))
        log_delete("availability_template", delete_all_records(cursor, "availability_template", "clinic_id", CLINIC_ID))
        conn.commit()

        # 19. PERSONAS RELACIONADAS
        info("19. Limpiando personas relacionadas...")
        log_delete("patient_related_person_designation", delete_by_parent_id(cursor, "patient_related_person_designation", "patient_related_person_id", patient_related_person_ids))
        log_delete("patient_related_person", delete_all_records(cursor, "patient_related_person", "clinic_id", CLINIC_ID))
        conn.commit()

        # 20. CONTACTOS DE PACIENTES
        info("20. Limpiando contactos de pacientes...")
        log_delete("patient_email", delete_all_records(cursor, "patient_email", "clinic_id", CLINIC_ID))
        log_delete("patient_phone", delete_all_records(cursor, "patient_phone", "clinic_id", CLINIC_ID))
        conn.commit()

        # 21. BALANCES DE PACIENTES
        info("21. Limpiando balances de pacientes...")
        log_delete("patient_balance_movement", delete_by_parent_id(cursor, "patient_balance_movement", "patient_balance_id", patient_balance_ids))
        log_delete("patient_balance", delete_all_records(cursor, "patient_balance", "clinic_id", CLINIC_ID))
        conn.commit()

        # 22. DESCUENTOS
        info("22. Limpiando descuentos...")
        log_delete("discount_application", delete_by_parent_id(cursor, "discount_application", "discount_id", discount_ids))
        log_delete("discount_user_access", delete_by_parent_id(cursor, "discount_user_access", "discount_id", discount_ids))
        log_delete("discount", delete_all_records(cursor, "discount", "clinic_id", CLINIC_ID))
        conn.commit()

        # 23. GIFT CARDS Y VOUCHERS
        info("23. Limpiando gift cards y vouchers...")
        log_delete("gift_card_movement", delete_by_parent_id(cursor, "gift_card_movement", "gift_card_id", gift_card_ids))
        log_delete("gift_card", delete_all_records(cursor, "gift_card", "clinic_id", CLINIC_ID))
        log_delete("voucher", delete_all_records(cursor, "voucher", "clinic_id", CLINIC_ID))
        conn.commit()

        # 24. NOTIFICACIONES Y DOCUMENTOS
        info("24. Limpiando notificaciones y documentos...")
        log_delete("notification", delete_in_batches(conn, cursor, "notification", "clinic_id", CLINIC_ID))
        log_delete("binaries", delete_in_batches(conn, cursor, "binaries", "clinic_id", CLINIC_ID))
        log_delete("document_references", delete_all_records(cursor, "document_references", "clinic_id", CLINIC_ID))
        conn.commit()

        # 25. PACIENTES
        info("25. Limpiando pacientes...")
        log_delete("patient", delete_in_batches(conn, cursor, "patient", "clinic_id", CLINIC_ID))
        conn.commit()

        # 25b. CANALES DE ADQUISICIÓN
        info("25b. Limpiando canales de adquisición...")
        log_delete("acquisition_channel", delete_all_records(cursor, "acquisition_channel", "clinic_id", CLINIC_ID))
        conn.commit()

        # 26. PROFESIONALES
        info("26. Limpiando profesionales...")
        log_delete("professional", delete_all_records(cursor, "professional", "clinic_id", CLINIC_ID))
        log_delete("professional_type", delete_all_records(cursor, "professional_type", "clinic_id", CLINIC_ID))
        conn.commit()

        # 27. CONTEXTOS Y PERMISOS DE USUARIO
        info("27. Limpiando contextos y permisos de usuario...")
        log_delete("user_permission_override", delete_all_records(cursor, "user_permission_override", "clinic_id", CLINIC_ID))
        log_delete("user_signature_profile", delete_all_records(cursor, "user_signature_profile", "clinic_id", CLINIC_ID))
        if table_exists(cursor, "user_context_tracking"):
            cursor.execute("DELETE FROM user_context_tracking WHERE primary_clinic_id = %s", (CLINIC_ID,))
            log_delete("user_context_tracking", cursor.rowcount)
        if table_exists(cursor, "user_context_suspension"):
            cursor.execute("DELETE FROM user_context_suspension WHERE context_type = 'CLINIC' AND context_id = %s", (CLINIC_ID,))
            log_delete("user_context_suspension", cursor.rowcount)
        conn.commit()

        # 28. USUARIOS
        info("28. Limpiando usuarios de clínica...")
        if table_exists(cursor, "user_site") and SITE_IDS:
            placeholders = ",".join(["%s"] * len(SITE_IDS))
            cursor.execute(f"DELETE FROM user_site WHERE site_id IN ({placeholders})", SITE_IDS)
            log_delete("user_site", cursor.rowcount)
        log_delete("user_clinic", delete_all_records(cursor, "user_clinic", "clinic_id", CLINIC_ID))
        if user_ids and table_exists(cursor, "app_user"):
            cursor.execute(
                """
                DELETE FROM app_user
                WHERE id = ANY(%s)
                  AND NOT EXISTS (
                      SELECT 1 FROM user_clinic uc WHERE uc.user_id = app_user.id
                  )
            """,
                (user_ids,),
            )
            log_delete("app_user (sin otras clínicas)", cursor.rowcount)
        conn.commit()

        # 29. CONFIG DE SITE
        info("29. Limpiando configuración de sites...")
        log_delete("site_billing_line", delete_all_for_sites(cursor, "site_billing_line", SITE_IDS))
        log_delete("site_mrn_configuration", delete_all_for_sites(cursor, "site_mrn_configuration", SITE_IDS))
        log_delete("mrn_counter", delete_all_for_sites(cursor, "mrn_counter", SITE_IDS))
        conn.commit()

        # 30. PRODUCTOS, SUPPLIES, POLÍTICAS
        info("30. Limpiando productos y políticas...")
        log_delete("product", delete_all_for_sites(cursor, "product", SITE_IDS))
        log_delete("supply", delete_all_for_sites(cursor, "supply", SITE_IDS))
        log_delete("scheduling_policy", delete_all_records(cursor, "scheduling_policy", "clinic_id", CLINIC_ID))
        log_delete("visit_status_definition", delete_all_records(cursor, "visit_status_definition", "clinic_id", CLINIC_ID))
        conn.commit()

        # 31. TAGS, INTEGRACIONES, OTROS
        info("31. Limpiando tags e integraciones...")
        log_delete("tag", delete_all_for_sites(cursor, "tag", SITE_IDS))  # tag tiene site_id, no clinic_id
        log_delete("kommo_bot", delete_all_records(cursor, "kommo_bot", "clinic_id", CLINIC_ID))
        log_delete("partner_agreement", delete_all_records(cursor, "partner_agreement", "clinic_id", CLINIC_ID))
        log_delete("payment_method", delete_all_records(cursor, "payment_method", "clinic_id", CLINIC_ID))
        conn.commit()

        # 32. SITE
        info("32. Limpiando sites...")
        log_delete("site", delete_all_records(cursor, "site", "clinic_id", CLINIC_ID))
        conn.commit()

        # 33. CLINIC
        info("33. Limpiando clinic...")
        if table_exists(cursor, "clinic"):
            cursor.execute("DELETE FROM clinic WHERE id = %s", (CLINIC_ID,))
            log_delete("clinic", cursor.rowcount)
        conn.commit()

        # 34. COMPANY Y ORGANIZATION
        info("34. Limpiando company y organization...")
        if ORGANIZATION_ID:
            log_delete("user_organization", delete_all_records(cursor, "user_organization", "organization_id", ORGANIZATION_ID))
        if COMPANY_ID:
            log_delete("company", delete_all_records(cursor, "company", "id", COMPANY_ID))
        if ORGANIZATION_ID:
            log_delete("organization", delete_all_records(cursor, "organization", "id", ORGANIZATION_ID))
        conn.commit()

        # Resumen
        total_deleted = sum(r[1] for r in results if r[1] > 0)
        print_separator()
        print_subheader("Resumen de limpieza")
        tables_with_data = [(t, c) for t, c in results if c > 0]
        if tables_with_data:
            for table, count in tables_with_data:
                success(f"{table}: {count}")
        else:
            info("No se encontraron datos para borrar")
        print_separator()
        success(f"TOTAL: {total_deleted} registros borrados")

    except Exception as e:
        conn.rollback()
        # Re-habilitar triggers por si quedaron deshabilitados
        try:
            for t in ["clinical_note", "clinical_note_comment", "care_plan", "form_assignment"]:
                cursor.execute(f"ALTER TABLE {t} ENABLE TRIGGER ALL")
            conn.commit()
        except Exception:
            pass
        error(f"Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    clean_clinic_by_id()
