"""
Genera un archivo queries.py específico para una clínica seleccionada.
Usa el config.yaml y busca los IDs reales en la base de datos.
"""

import os
import sys
from datetime import datetime

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.database import execute_query, test_connection
from ui import (
    console,
    print_header,
    print_subheader,
    print_table,
    print_key_value,
    info,
    success,
    warning,
    error,
    step,
    ask,
)

CLINICS_DIR = os.path.dirname(os.path.abspath(__file__))


def list_clinics() -> list:
    """Lista todas las clínicas disponibles con config.yaml."""
    clinics = []
    for item in os.listdir(CLINICS_DIR):
        item_path = os.path.join(CLINICS_DIR, item)
        config_path = os.path.join(item_path, "config.yaml")
        if os.path.isdir(item_path) and os.path.exists(config_path):
            clinics.append(item)
    return sorted(clinics)


def load_config(clinic_name: str) -> dict:
    """Carga el config.yaml de una clínica."""
    config_path = os.path.join(CLINICS_DIR, clinic_name, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_clinic_in_db(clinic_name: str) -> dict | None:
    """Busca una clínica en la BD por nombre."""
    query = """
        SELECT c.id, c.organization_id, c.name, c.default_issuer_company_id
        FROM clinic c
        WHERE c.name ILIKE %s AND c.record_status = 'ACTIVE'
        LIMIT 1
    """
    results = execute_query(query, (f"%{clinic_name}%",))
    return dict(results[0]) if results else None


def find_organization_in_db(org_id: str) -> dict | None:
    """Obtiene una organización por ID."""
    query = """
        SELECT id, name
        FROM organization
        WHERE id = %s
    """
    results = execute_query(query, (org_id,))
    return dict(results[0]) if results else None


def find_sites_in_db(clinic_id: str) -> list[dict]:
    """Obtiene los sites de una clínica."""
    query = """
        SELECT id, name, timezone
        FROM site
        WHERE clinic_id = %s AND record_status = 'ACTIVE'
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (clinic_id,))]


def find_company_in_db(company_id: str) -> dict | None:
    """Obtiene una company por ID."""
    query = """
        SELECT id, name, type
        FROM company
        WHERE id = %s
    """
    results = execute_query(query, (company_id,))
    return dict(results[0]) if results else None


def generate_queries_file(clinic_name: str, clinic_data: dict, org_data: dict,
                          sites_data: list, company_data: dict | None) -> str:
    """Genera el contenido del archivo queries.py."""

    clinic_id = clinic_data["id"]
    org_id = clinic_data["organization_id"]
    company_id = clinic_data.get("default_issuer_company_id")

    # Generar diccionario de sites
    sites_dict = "\n".join([
        f'    "{s["name"]}": "{s["id"]}",'
        for s in sites_data
    ])

    sites_list = "\n".join([
        f'        "{s["id"]}",  # {s["name"]}'
        for s in sites_data
    ])

    content = f'''"""
Queries específicas para: {clinic_data["name"]}
Generado automáticamente: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Este archivo contiene funciones de consulta preconfiguradas
con los IDs de esta clínica para facilitar scripts de migración.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.database import execute_query


# =============================================================================
# IDS DE LA CLÍNICA
# =============================================================================

ORGANIZATION_ID = "{org_id}"
ORGANIZATION_NAME = "{org_data["name"]}"

CLINIC_ID = "{clinic_id}"
CLINIC_NAME = "{clinic_data["name"]}"

COMPANY_ID = "{company_id or ''}"
COMPANY_NAME = "{company_data["name"] if company_data else ''}"

SITES = {{
{sites_dict}
}}

SITE_IDS = [
{sites_list}
]


# =============================================================================
# FUNCIONES DE CONSULTA
# =============================================================================

def get_clinic() -> dict | None:
    """Obtiene los datos de esta clínica."""
    query = """
        SELECT id, organization_id, name, description,
               phone, email, country, timezone,
               default_currency, default_issuer_company_id,
               clinic_status, record_status,
               created_at, updated_at
        FROM clinic
        WHERE id = %s
    """
    results = execute_query(query, (CLINIC_ID,))
    return dict(results[0]) if results else None


def get_organization() -> dict | None:
    """Obtiene los datos de la organización."""
    query = """
        SELECT id, name, legal_name, home_country, home_timezone,
               plan_type, organization_status, record_status,
               created_at, updated_at
        FROM organization
        WHERE id = %s
    """
    results = execute_query(query, (ORGANIZATION_ID,))
    return dict(results[0]) if results else None


def get_company() -> dict | None:
    """Obtiene los datos de la company emisora."""
    if not COMPANY_ID:
        return None
    query = """
        SELECT id, organization_id, name, legal_name,
               tax_id_type, tax_id_number, address_fiscal,
               country, type, record_status,
               created_at, updated_at
        FROM company
        WHERE id = %s
    """
    results = execute_query(query, (COMPANY_ID,))
    return dict(results[0]) if results else None


def get_sites(active_only: bool = True) -> list[dict]:
    """Obtiene todos los sites de esta clínica."""
    query = """
        SELECT id, clinic_id, name, address, timezone,
               site_status, record_status, metadata,
               created_at, updated_at
        FROM site
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, active_only))]


def get_site_by_name(name: str) -> dict | None:
    """Obtiene un site por nombre."""
    site_id = SITES.get(name)
    if not site_id:
        return None
    query = """
        SELECT id, clinic_id, name, address, timezone,
               site_status, record_status, metadata,
               created_at, updated_at
        FROM site
        WHERE id = %s
    """
    results = execute_query(query, (site_id,))
    return dict(results[0]) if results else None


def get_site_by_id(site_id: str) -> dict | None:
    """Obtiene un site por ID."""
    query = """
        SELECT id, clinic_id, name, address, timezone,
               site_status, record_status, metadata,
               created_at, updated_at
        FROM site
        WHERE id = %s AND clinic_id = %s
    """
    results = execute_query(query, (site_id, CLINIC_ID))
    return dict(results[0]) if results else None


# =============================================================================
# PROFESSIONALS
# =============================================================================

def get_professionals(active_only: bool = True) -> list[dict]:
    """Obtiene todos los profesionales de esta clínica."""
    query = """
        SELECT id, clinic_id, name, last_name,
               professional_type_id, specialties, color,
               email, phone, employment_type,
               site_ids, user_id, record_status,
               created_at, updated_at
        FROM professional
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY last_name, name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, active_only))]


def get_professional_by_id(professional_id: str) -> dict | None:
    """Obtiene un profesional por ID."""
    query = """
        SELECT id, clinic_id, name, last_name,
               professional_type_id, specialties, color,
               email, phone, employment_type,
               site_ids, user_id, record_status,
               created_at, updated_at
        FROM professional
        WHERE id = %s AND clinic_id = %s
    """
    results = execute_query(query, (professional_id, CLINIC_ID))
    return dict(results[0]) if results else None


def get_professionals_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene profesionales que atienden en un site específico."""
    query = """
        SELECT id, clinic_id, name, last_name,
               professional_type_id, specialties, color,
               email, phone, employment_type,
               site_ids, user_id, record_status,
               created_at, updated_at
        FROM professional
        WHERE clinic_id = %s
          AND %s = ANY(site_ids)
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY last_name, name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, site_id, active_only))]


# =============================================================================
# PATIENTS
# =============================================================================

def get_patients(active_only: bool = True, limit: int = 100, offset: int = 0) -> list[dict]:
    """Obtiene pacientes de esta clínica."""
    query = """
        SELECT id, clinic_id, name, last_name,
               document_type, document_number, birth_date,
               gender, email, phone,
               patient_scheduling_status, record_status,
               created_at, updated_at
        FROM patient
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY last_name, name
        LIMIT %s OFFSET %s
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, active_only, limit, offset))]


def get_patient_by_id(patient_id: str) -> dict | None:
    """Obtiene un paciente por ID."""
    query = """
        SELECT id, clinic_id, name, last_name,
               document_type, document_number, birth_date,
               gender, email, phone,
               patient_scheduling_status, record_status,
               created_at, updated_at
        FROM patient
        WHERE id = %s AND clinic_id = %s
    """
    results = execute_query(query, (patient_id, CLINIC_ID))
    return dict(results[0]) if results else None


def get_patient_by_document(document_type: str, document_number: str) -> dict | None:
    """Obtiene un paciente por tipo y número de documento."""
    query = """
        SELECT id, clinic_id, name, last_name,
               document_type, document_number, birth_date,
               gender, email, phone,
               patient_scheduling_status, record_status,
               created_at, updated_at
        FROM patient
        WHERE clinic_id = %s
          AND document_type = %s
          AND document_number = %s
    """
    results = execute_query(query, (CLINIC_ID, document_type, document_number))
    return dict(results[0]) if results else None


def get_patient_count(active_only: bool = True) -> int:
    """Obtiene el total de pacientes de esta clínica."""
    query = """
        SELECT COUNT(*) as count
        FROM patient
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
    """
    results = execute_query(query, (CLINIC_ID, active_only))
    return results[0]["count"] if results else 0


# =============================================================================
# SERVICES & TREATMENTS
# =============================================================================

def get_services(active_only: bool = True) -> list[dict]:
    """Obtiene todos los servicios de esta clínica."""
    query = """
        SELECT id, clinic_id, name, description,
               record_status, created_at, updated_at
        FROM service
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, active_only))]


def get_treatments_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene tratamientos de un site."""
    query = """
        SELECT id, clinic_id, site_id, service_id, category_id,
               name, treatment_type, duration_minutes,
               base_price, currency, treatment_visibility,
               record_status, created_at, updated_at
        FROM treatment
        WHERE clinic_id = %s
          AND site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, site_id, active_only))]


# =============================================================================
# ROOMS & EQUIPMENT
# =============================================================================

def get_rooms_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene las salas de un site."""
    query = """
        SELECT id, clinic_id, site_id, name,
               room_type, capacity, room_status,
               record_status, created_at, updated_at
        FROM room
        WHERE clinic_id = %s
          AND site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, site_id, active_only))]


def get_equipment_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene el equipamiento de un site."""
    query = """
        SELECT id, clinic_id, site_id, name,
               equipment_type, model, serial_number,
               equipment_status, record_status,
               created_at, updated_at
        FROM equipment
        WHERE clinic_id = %s
          AND site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return [dict(r) for r in execute_query(query, (CLINIC_ID, site_id, active_only))]


# =============================================================================
# RESUMEN
# =============================================================================

def get_summary() -> dict:
    """Obtiene un resumen de esta clínica."""
    sites = get_sites()

    rooms_count = 0
    equipment_count = 0
    treatments_count = 0

    for site in sites:
        rooms_count += len(get_rooms_by_site(site["id"]))
        equipment_count += len(get_equipment_by_site(site["id"]))
        treatments_count += len(get_treatments_by_site(site["id"]))

    return {{
        "clinic_id": CLINIC_ID,
        "clinic_name": CLINIC_NAME,
        "organization_id": ORGANIZATION_ID,
        "organization_name": ORGANIZATION_NAME,
        "sites_count": len(sites),
        "sites": [s["name"] for s in sites],
        "professionals_count": len(get_professionals()),
        "patients_count": get_patient_count(),
        "services_count": len(get_services()),
        "rooms_count": rooms_count,
        "equipment_count": equipment_count,
        "treatments_count": treatments_count,
    }}


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import json

    print(f"Clínica: {{CLINIC_NAME}}")
    print(f"Organización: {{ORGANIZATION_NAME}}")
    print(f"Sites: {{list(SITES.keys())}}")
    print()

    summary = get_summary()
    print("Resumen:")
    print(json.dumps(summary, indent=2, default=str))
'''

    return content


def generate_queries(clinic_name: str = None):
    """Flujo principal para generar queries de una clínica."""
    print_header("GENERAR QUERIES DE CLÍNICA")

    # Verificar conexión
    step("Verificando conexión a la base de datos...")
    if not test_connection():
        error("No se pudo conectar a la base de datos")
        info("Verifique DATABASE_URL en .env")
        return
    success("Conexión exitosa")

    # Listar clínicas
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

    step(f"Procesando clínica: [cyan]{clinic_name}[/cyan]")

    # Cargar config
    try:
        config = load_config(clinic_name)
    except Exception as e:
        error(f"Error al cargar config.yaml: {e}")
        return

    clinic_config_name = config.get("clinic", {}).get("name", "")
    if not clinic_config_name:
        error("No se encontró nombre de clínica en config.yaml")
        return

    # Buscar en BD
    step(f"Buscando clínica '[cyan]{clinic_config_name}[/cyan]' en la base de datos...")
    clinic_data = find_clinic_in_db(clinic_config_name)

    if not clinic_data:
        error(f"No se encontró la clínica '{clinic_config_name}' en la base de datos")
        info("Primero ejecute 'Validar e insertar configuración' para crear la clínica")
        return

    success(f"Clínica encontrada: {clinic_data['name']} ({clinic_data['id'][:8]}...)")

    # Obtener datos relacionados
    step("Obteniendo datos de la organización...")
    org_data = find_organization_in_db(clinic_data["organization_id"])
    if not org_data:
        error("No se encontró la organización")
        return
    success(f"Organización: {org_data['name']}")

    step("Obteniendo sites...")
    sites_data = find_sites_in_db(clinic_data["id"])
    if not sites_data:
        warning("No se encontraron sites")
    else:
        success(f"Sites encontrados: {len(sites_data)}")
        for s in sites_data:
            info(f"  - {s['name']} ({s['id'][:8]}...)")

    company_data = None
    if clinic_data.get("default_issuer_company_id"):
        step("Obteniendo company emisora...")
        company_data = find_company_in_db(clinic_data["default_issuer_company_id"])
        if company_data:
            success(f"Company: {company_data['name']}")

    # Generar archivo
    step("Generando archivo queries.py...")
    content = generate_queries_file(clinic_name, clinic_data, org_data, sites_data, company_data)

    output_path = os.path.join(CLINICS_DIR, clinic_name, "queries.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    success(f"Archivo generado: [cyan]{output_path}[/cyan]")

    # Mostrar resumen
    console.print()
    print_subheader("Resumen de IDs generados")
    print_key_value({
        "Organization ID": org_data["id"],
        "Clinic ID": clinic_data["id"],
        "Company ID": clinic_data.get("default_issuer_company_id") or "N/A",
        "Sites": len(sites_data),
    })

    console.print()
    info("Uso del archivo generado:")
    console.print(f"  [dim]from clinics.{clinic_name}.queries import get_clinic, get_sites, get_patients[/dim]")


if __name__ == "__main__":
    clinic_arg = sys.argv[1] if len(sys.argv) > 1 else None
    generate_queries(clinic_arg)
