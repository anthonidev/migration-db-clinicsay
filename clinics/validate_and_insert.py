import os
import sys
import json
from datetime import datetime

from ulid import ULID

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.database import execute_script, test_connection
from ui import (
    console,
    print_header,
    print_subheader,
    print_panel,
    print_table,
    print_key_value,
    print_rule,
    info,
    success,
    warning,
    error,
    step,
    ask,
    confirm,
)

CLINICS_DIR = os.path.dirname(os.path.abspath(__file__))

REQUIRED_FIELDS = {
    "organization": ["name", "home_country", "home_timezone"],
    "company": [
        "name", "legal_name", "tax_id_type", "tax_id_number",
        "address_fiscal", "country", "legal_rep_name",
        "legal_rep_id_type", "legal_rep_id_number", "legal_rep_position"
    ],
    "clinic": ["name", "country", "timezone", "default_currency"],
    "site": ["name", "timezone"],
    "site_address": ["country", "region", "city", "street_line1"],
}


def load_config(clinic_name: str) -> dict:
    """Carga el archivo de configuración YAML de una clínica."""
    config_path = os.path.join(CLINICS_DIR, clinic_name, "config.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_clinics() -> list:
    """Lista todas las clínicas disponibles."""
    clinics = []
    for item in os.listdir(CLINICS_DIR):
        item_path = os.path.join(CLINICS_DIR, item)
        config_path = os.path.join(item_path, "config.yaml")
        if os.path.isdir(item_path) and os.path.exists(config_path):
            clinics.append(item)
    return sorted(clinics)


def validate_entity(entity: dict, required: list, entity_name: str) -> list:
    """Valida que una entidad tenga los campos requeridos."""
    errors = []
    if not entity:
        return [f"{entity_name}: No configurado"]

    for field in required:
        value = entity.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{entity_name}.{field}")

    return errors


def validate_config(config: dict) -> tuple:
    """Valida la configuración completa. Retorna (is_valid, errors)."""
    errors = []

    errors.extend(validate_entity(
        config.get("organization"),
        REQUIRED_FIELDS["organization"],
        "organization"
    ))

    errors.extend(validate_entity(
        config.get("company"),
        REQUIRED_FIELDS["company"],
        "company"
    ))

    errors.extend(validate_entity(
        config.get("clinic"),
        REQUIRED_FIELDS["clinic"],
        "clinic"
    ))

    sites = config.get("sites", [])
    if not sites:
        errors.append("sites: Debe tener al menos una sede")
    else:
        for i, site in enumerate(sites):
            errors.extend(validate_entity(
                site,
                REQUIRED_FIELDS["site"],
                f"sites[{i}]"
            ))
            address = site.get("address", {})
            errors.extend(validate_entity(
                address,
                REQUIRED_FIELDS["site_address"],
                f"sites[{i}].address"
            ))

    return len(errors) == 0, errors


def print_config(config: dict):
    """Muestra la configuración en pantalla de forma legible."""

    # Organization
    org = config.get("organization", {})
    print_subheader("1. ORGANIZATION")
    print_key_value({
        "Nombre": org.get('name'),
        "Razón social": org.get('legal_name'),
        "País": org.get('home_country'),
        "Timezone": org.get('home_timezone'),
        "Plan": org.get('plan_type'),
        "Estado": org.get('organization_status'),
    })

    # Company
    comp = config.get("company", {})
    print_subheader("2. COMPANY")
    print_key_value({
        "Nombre": comp.get('name'),
        "Razón social": comp.get('legal_name'),
        f"{comp.get('tax_id_type', 'ID')}": comp.get('tax_id_number'),
        "Dir. Fiscal": comp.get('address_fiscal'),
        "País": comp.get('country'),
        "Tipo": comp.get('type'),
    })
    console.print()
    console.print("  [dim]Representante Legal:[/dim]")
    console.print(f"    Nombre: {comp.get('legal_rep_name', '-')}")
    console.print(f"    {comp.get('legal_rep_id_type', 'Doc')}: {comp.get('legal_rep_id_number', '-')}")
    console.print(f"    Cargo: {comp.get('legal_rep_position', '-')}")

    # Clinic
    clinic = config.get("clinic", {})
    print_subheader("3. CLINIC")
    print_key_value({
        "Nombre": clinic.get('name'),
        "Descripción": clinic.get('description'),
        "Teléfono": clinic.get('phone'),
        "Email": clinic.get('email'),
        "País": clinic.get('country'),
        "Timezone": clinic.get('timezone'),
        "Moneda": clinic.get('default_currency'),
        "Data Policy": clinic.get('data_sharing_policy'),
        "Estado": clinic.get('clinic_status'),
    })

    # Sites
    sites = config.get("sites", [])
    print_subheader(f"4. SITES ({len(sites)} sede(s))")

    for i, site in enumerate(sites):
        addr = site.get("address", {})
        console.print()
        console.print(f"  [cyan bold]Sede {i + 1}: {site.get('name', '-')}[/cyan bold]")
        console.print(f"    Teléfono: {site.get('phone') or '-'}")
        console.print(f"    Email: {site.get('email') or '-'}")
        console.print(f"    Timezone: {site.get('timezone') or '-'}")
        console.print(f"    Estado: {site.get('site_status') or '-'}")
        console.print("    [dim]Dirección:[/dim]")
        console.print(f"      {addr.get('street_line1', '-')}")
        if addr.get('street_line2'):
            console.print(f"      {addr.get('street_line2')}")
        district = addr.get('district', '')
        console.print(f"      {district + ', ' if district else ''}{addr.get('city', '-')}, {addr.get('region', '-')}")
        console.print(f"      {addr.get('postal_code') or ''} {addr.get('country', '-')}")

        # Billing Lines de la sede
        billing_lines = site.get("billing_lines", [])
        if billing_lines:
            console.print("    [dim]Líneas de facturación:[/dim]")
            for bl in billing_lines:
                default_mark = " [green](default)[/green]" if bl.get("is_default") else ""
                console.print(f"      • {bl.get('name', '-')}{default_mark}")

    # Payment Methods
    payment_methods = config.get("payment_methods", [])
    if payment_methods:
        print_subheader(f"5. PAYMENT METHODS ({len(payment_methods)} método(s))")
        for pm in payment_methods:
            console.print(f"  [cyan]•[/cyan] {pm.get('name', '-')} ({pm.get('payment_method_type', '-')})")


def generate_sql(config: dict) -> str:
    """Genera el SQL de inserción para la configuración."""
    now = datetime.utcnow().isoformat()

    org_id = str(ULID()).upper()
    company_id = str(ULID()).upper()
    clinic_id = str(ULID()).upper()

    org = config["organization"]
    comp = config["company"]
    clinic = config["clinic"]
    sites = config["sites"]

    sql_parts = []

    sql_parts.append(f"""
-- ORGANIZATION
INSERT INTO organization (
    id, name, legal_name, home_country, home_timezone,
    plan_type, organization_status, record_status,
    created_at, updated_at
) VALUES (
    '{org_id}',
    '{escape_sql(org.get("name", ""))}',
    {sql_str(org.get("legal_name"))},
    {sql_str(org.get("home_country"))},
    {sql_str(org.get("home_timezone"))},
    {sql_str(org.get("plan_type", "professional"))},
    '{org.get("organization_status", "ONBOARDING")}',
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    sql_parts.append(f"""
-- COMPANY
INSERT INTO company (
    id, organization_id, name, legal_name,
    tax_id_type, tax_id_number, address_fiscal, country, type,
    legal_rep_name, legal_rep_id_type, legal_rep_id_number, legal_rep_position,
    record_status, created_at, updated_at
) VALUES (
    '{company_id}',
    '{org_id}',
    '{escape_sql(comp.get("name", ""))}',
    {sql_str(comp.get("legal_name"))},
    {sql_str(comp.get("tax_id_type"))},
    {sql_str(comp.get("tax_id_number"))},
    {sql_str(comp.get("address_fiscal"))},
    {sql_str(comp.get("country"))},
    '{comp.get("type", "CLINIC_ISSUER")}',
    {sql_str(comp.get("legal_rep_name"))},
    {sql_str(comp.get("legal_rep_id_type"))},
    {sql_str(comp.get("legal_rep_id_number"))},
    {sql_str(comp.get("legal_rep_position"))},
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    sql_parts.append(f"""
-- CLINIC
INSERT INTO clinic (
    id, organization_id, default_issuer_company_id,
    name, description, phone, email,
    country, timezone, default_currency,
    data_sharing_policy, clinic_status, record_status,
    created_at, updated_at
) VALUES (
    '{clinic_id}',
    '{org_id}',
    '{company_id}',
    '{escape_sql(clinic.get("name", ""))}',
    {sql_str(clinic.get("description"))},
    {sql_str(clinic.get("phone"))},
    {sql_str(clinic.get("email"))},
    {sql_str(clinic.get("country"))},
    {sql_str(clinic.get("timezone"))},
    {sql_str(clinic.get("default_currency"))},
    '{clinic.get("data_sharing_policy", "ISOLATED")}',
    '{clinic.get("clinic_status", "ONBOARDING")}',
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    site_ids = []  # Para guardar los IDs generados

    for i, site in enumerate(sites):
        site_id = str(ULID()).upper()
        site_ids.append((site_id, site))  # Guardar para billing_lines
        addr = site.get("address", {})

        address_json = json.dumps({
            "country": addr.get("country", ""),
            "region": addr.get("region", ""),
            "city": addr.get("city", ""),
            "district": addr.get("district", ""),
            "postalCode": addr.get("postal_code", ""),
            "streetLine1": addr.get("street_line1", ""),
            "streetLine2": addr.get("street_line2", ""),
        }, ensure_ascii=False)

        sql_parts.append(f"""
-- SITE {i + 1}: {site.get("name", "")}
INSERT INTO site (
    id, clinic_id, name, address, timezone,
    site_status, record_status, created_at, updated_at
) VALUES (
    '{site_id}',
    '{clinic_id}',
    '{escape_sql(site.get("name", ""))}',
    '{escape_sql(address_json)}'::jsonb,
    {sql_str(site.get("timezone"))},
    '{site.get("site_status", "ACTIVE")}',
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    # Site Billing Lines
    for site_id, site in site_ids:
        billing_lines = site.get("billing_lines", [])
        # Si no hay billing_lines configuradas, crear una por defecto
        if not billing_lines:
            billing_lines = [{"name": "Línea Principal", "is_default": True}]

        for j, bl in enumerate(billing_lines):
            bl_id = str(ULID()).upper()
            sql_parts.append(f"""
-- BILLING LINE: {site.get("name", "")} - {bl.get("name", "")}
INSERT INTO site_billing_line (
    id, site_id, company_id, name, description,
    is_default, record_status, created_at, updated_at
) VALUES (
    '{bl_id}',
    '{site_id}',
    '{company_id}',
    '{escape_sql(bl.get("name", "Línea Principal"))}',
    {sql_str(bl.get("description"))},
    {str(bl.get("is_default", j == 0)).lower()},
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    # Payment Methods
    payment_methods = config.get("payment_methods", [])
    for i, pm in enumerate(payment_methods):
        pm_id = str(ULID()).upper()

        sql_parts.append(f"""
-- PAYMENT METHOD {i + 1}: {pm.get("name", "")}
INSERT INTO payment_method (
    id, clinic_id, name, payment_method_type,
    requires_reference, allows_refunds, is_online_method,
    sort_order, payment_method_status, record_status,
    created_at, updated_at
) VALUES (
    '{pm_id}',
    '{clinic_id}',
    '{escape_sql(pm.get("name", ""))}',
    '{pm.get("payment_method_type", "OTHER")}',
    {str(pm.get("requires_reference", False)).lower()},
    {str(pm.get("allows_refunds", True)).lower()},
    {str(pm.get("is_online_method", False)).lower()},
    {pm.get("sort_order") or "NULL"},
    'ACTIVE',
    'ACTIVE',
    '{now}',
    '{now}'
);""")

    return "\n".join(sql_parts)


def escape_sql(value: str) -> str:
    """Escapa comillas simples para SQL."""
    if value is None:
        return ""
    return str(value).replace("'", "''")


def sql_str(value) -> str:
    """Convierte un valor a string SQL (NULL o 'valor')."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "NULL"
    return f"'{escape_sql(value)}'"


def save_sql_script(clinic_name: str, sql: str) -> str:
    """Guarda el script SQL en la carpeta de scripts de la clínica."""
    scripts_dir = os.path.join(CLINICS_DIR, clinic_name, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    script_path = os.path.join(scripts_dir, "01_configuracion_inicial.sql")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(sql)

    return script_path


def validate_and_insert(clinic_name: str = None):
    """Flujo principal de validación e inserción."""
    print_header("VALIDAR E INSERTAR CONFIGURACIÓN")

    # Listar clínicas disponibles
    clinics = list_clinics()
    if not clinics:
        warning("No hay clínicas configuradas")
        info("Primero ejecute la opción de inicializar clínica")
        return

    # Seleccionar clínica
    if not clinic_name:
        print_subheader("Clínicas disponibles")

        rows = [[str(i), c] for i, c in enumerate(clinics, 1)]
        print_table("", ["#", "Nombre"], rows, show_header=True)

        while True:
            try:
                choice = ask("Seleccione una clínica (número)")
                idx = int(choice) - 1
                if 0 <= idx < len(clinics):
                    clinic_name = clinics[idx]
                    break
                warning("Número inválido")
            except ValueError:
                warning("Ingrese un número")

    step(f"Cargando configuración de: [cyan]{clinic_name}[/cyan]")

    # Cargar configuración
    try:
        config = load_config(clinic_name)
    except FileNotFoundError as e:
        error(str(e))
        return
    except yaml.YAMLError as e:
        error(f"Error de sintaxis YAML: {e}")
        return

    if not config:
        error("El archivo de configuración está vacío")
        return

    # Validar
    step("Validando configuración...")
    is_valid, errors = validate_config(config)

    if not is_valid:
        console.print()
        error("La configuración tiene errores:")
        console.print()
        for err in errors:
            console.print(f"  [red]•[/red] {err}")
        console.print()
        info(f"Corrija el archivo: [cyan]clinics/{clinic_name}/config.yaml[/cyan]")
        return

    success("Configuración válida")

    # Mostrar configuración
    print_header("DATOS A INSERTAR")
    print_config(config)

    # Generar SQL
    console.print()
    step("Generando SQL...")
    sql = generate_sql(config)

    # Guardar SQL
    script_path = save_sql_script(clinic_name, sql)
    success(f"SQL guardado en: [cyan]{script_path}[/cyan]")

    # Confirmar inserción
    print_header("CONFIRMAR INSERCIÓN")

    step("Verificando conexión a la base de datos...")
    if not test_connection():
        error("No se pudo conectar a la base de datos")
        info("Verifique DATABASE_URL en .env")
        return

    success("Conexión exitosa")
    console.print()

    if not confirm("¿Desea insertar estos datos en la base de datos?"):
        console.print()
        info("Operación cancelada")
        info(f"El SQL se guardó en: [cyan]{script_path}[/cyan]")
        return

    # Ejecutar inserción
    console.print()
    step("Insertando datos...")

    try:
        execute_script(sql)
        console.print()
        print_panel(
            f"[green]Clínica '{clinic_name}' configurada exitosamente[/green]\n\n"
            "[cyan]Próximos pasos:[/cyan]\n"
            "  1. Configurar usuarios y profesionales\n"
            "  2. Configurar catálogo de servicios\n"
            "  3. Migrar pacientes",
            title="✓ DATOS INSERTADOS",
            style="green",
        )
    except Exception as e:
        error(f"Error al insertar datos: {e}")
        info(f"El SQL se guardó en: [cyan]{script_path}[/cyan]")
        info("Revise el error y ejecute manualmente si es necesario")


if __name__ == "__main__":
    clinic_arg = sys.argv[1] if len(sys.argv) > 1 else None
    validate_and_insert(clinic_arg)
