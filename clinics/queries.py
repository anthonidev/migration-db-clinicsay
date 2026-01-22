"""
Funciones de consulta para obtener datos de clínicas desde la base de datos.
Utiliza la conexión configurada en DATABASE_URL.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.database import execute_query


# =============================================================================
# ORGANIZATION
# =============================================================================

def get_organizations(active_only: bool = True) -> list[dict]:
    """Obtiene todas las organizaciones."""
    query = """
        SELECT id, name, legal_name, home_country, home_timezone,
               plan_type, organization_status, record_status,
               created_at, updated_at
        FROM organization
        WHERE ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (active_only,))


def get_organization_by_id(organization_id: str) -> dict | None:
    """Obtiene una organización por su ID."""
    query = """
        SELECT id, name, legal_name, home_country, home_timezone,
               plan_type, organization_status, record_status,
               created_at, updated_at
        FROM organization
        WHERE id = %s
    """
    results = execute_query(query, (organization_id,))
    return results[0] if results else None


def get_organization_by_name(name: str) -> dict | None:
    """Obtiene una organización por su nombre."""
    query = """
        SELECT id, name, legal_name, home_country, home_timezone,
               plan_type, organization_status, record_status,
               created_at, updated_at
        FROM organization
        WHERE name ILIKE %s AND record_status = 'ACTIVE'
    """
    results = execute_query(query, (f"%{name}%",))
    return results[0] if results else None


# =============================================================================
# CLINIC
# =============================================================================

def get_clinics(active_only: bool = True) -> list[dict]:
    """Obtiene todas las clínicas."""
    query = """
        SELECT c.id, c.organization_id, c.name, c.description,
               c.phone, c.email, c.country, c.timezone,
               c.default_currency, c.default_issuer_company_id,
               c.data_sharing_policy, c.clinic_status, c.record_status,
               c.created_at, c.updated_at,
               o.name as organization_name
        FROM clinic c
        JOIN organization o ON c.organization_id = o.id
        WHERE ($1 = false OR c.record_status = 'ACTIVE')
        ORDER BY c.name
    """
    return execute_query(query, (active_only,))


def get_clinic_by_id(clinic_id: str) -> dict | None:
    """Obtiene una clínica por su ID."""
    query = """
        SELECT c.id, c.organization_id, c.name, c.description,
               c.phone, c.email, c.country, c.timezone,
               c.default_currency, c.default_issuer_company_id,
               c.data_sharing_policy, c.clinic_status, c.record_status,
               c.created_at, c.updated_at,
               o.name as organization_name
        FROM clinic c
        JOIN organization o ON c.organization_id = o.id
        WHERE c.id = %s
    """
    results = execute_query(query, (clinic_id,))
    return results[0] if results else None


def get_clinic_by_name(name: str) -> dict | None:
    """Obtiene una clínica por su nombre."""
    query = """
        SELECT c.id, c.organization_id, c.name, c.description,
               c.phone, c.email, c.country, c.timezone,
               c.default_currency, c.default_issuer_company_id,
               c.data_sharing_policy, c.clinic_status, c.record_status,
               c.created_at, c.updated_at,
               o.name as organization_name
        FROM clinic c
        JOIN organization o ON c.organization_id = o.id
        WHERE c.name ILIKE %s AND c.record_status = 'ACTIVE'
    """
    results = execute_query(query, (f"%{name}%",))
    return results[0] if results else None


def get_clinics_by_organization(organization_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todas las clínicas de una organización."""
    query = """
        SELECT id, organization_id, name, description,
               phone, email, country, timezone,
               default_currency, default_issuer_company_id,
               data_sharing_policy, clinic_status, record_status,
               created_at, updated_at
        FROM clinic
        WHERE organization_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (organization_id, active_only))


# =============================================================================
# SITE
# =============================================================================

def get_sites(active_only: bool = True) -> list[dict]:
    """Obtiene todos los sites."""
    query = """
        SELECT s.id, s.clinic_id, s.name, s.address, s.timezone,
               s.site_status, s.record_status, s.metadata,
               s.created_at, s.updated_at,
               c.name as clinic_name
        FROM site s
        JOIN clinic c ON s.clinic_id = c.id
        WHERE ($1 = false OR s.record_status = 'ACTIVE')
        ORDER BY c.name, s.name
    """
    return execute_query(query, (active_only,))


def get_site_by_id(site_id: str) -> dict | None:
    """Obtiene un site por su ID."""
    query = """
        SELECT s.id, s.clinic_id, s.name, s.address, s.timezone,
               s.site_status, s.record_status, s.metadata,
               s.created_at, s.updated_at,
               c.name as clinic_name
        FROM site s
        JOIN clinic c ON s.clinic_id = c.id
        WHERE s.id = %s
    """
    results = execute_query(query, (site_id,))
    return results[0] if results else None


def get_site_by_name(clinic_id: str, name: str) -> dict | None:
    """Obtiene un site por nombre dentro de una clínica."""
    query = """
        SELECT id, clinic_id, name, address, timezone,
               site_status, record_status, metadata,
               created_at, updated_at
        FROM site
        WHERE clinic_id = %s
          AND name ILIKE %s
          AND record_status = 'ACTIVE'
    """
    results = execute_query(query, (clinic_id, f"%{name}%"))
    return results[0] if results else None


def get_sites_by_clinic(clinic_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todos los sites de una clínica."""
    query = """
        SELECT id, clinic_id, name, address, timezone,
               site_status, record_status, metadata,
               created_at, updated_at
        FROM site
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (clinic_id, active_only))


# =============================================================================
# COMPANY
# =============================================================================

def get_companies(active_only: bool = True) -> list[dict]:
    """Obtiene todas las companies."""
    query = """
        SELECT c.id, c.organization_id, c.name, c.legal_name,
               c.tax_id_type, c.tax_id_number, c.address_fiscal,
               c.country, c.type, c.record_status,
               c.created_at, c.updated_at,
               o.name as organization_name
        FROM company c
        JOIN organization o ON c.organization_id = o.id
        WHERE ($1 = false OR c.record_status = 'ACTIVE')
        ORDER BY c.name
    """
    return execute_query(query, (active_only,))


def get_company_by_id(company_id: str) -> dict | None:
    """Obtiene una company por su ID."""
    query = """
        SELECT id, organization_id, name, legal_name,
               tax_id_type, tax_id_number, address_fiscal,
               country, type, record_status,
               created_at, updated_at
        FROM company
        WHERE id = %s
    """
    results = execute_query(query, (company_id,))
    return results[0] if results else None


def get_companies_by_organization(organization_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todas las companies de una organización."""
    query = """
        SELECT id, organization_id, name, legal_name,
               tax_id_type, tax_id_number, address_fiscal,
               country, type, record_status,
               created_at, updated_at
        FROM company
        WHERE organization_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (organization_id, active_only))


def get_clinic_issuer(organization_id: str) -> dict | None:
    """Obtiene la company emisora (CLINIC_ISSUER) de una organización."""
    query = """
        SELECT id, organization_id, name, legal_name,
               tax_id_type, tax_id_number, address_fiscal,
               country, type, record_status,
               created_at, updated_at
        FROM company
        WHERE organization_id = %s
          AND type = 'CLINIC_ISSUER'
          AND record_status = 'ACTIVE'
        LIMIT 1
    """
    results = execute_query(query, (organization_id,))
    return results[0] if results else None


# =============================================================================
# PROFESSIONAL
# =============================================================================

def get_professionals(active_only: bool = True) -> list[dict]:
    """Obtiene todos los profesionales."""
    query = """
        SELECT p.id, p.clinic_id, p.name, p.last_name,
               p.professional_type_id, p.specialties, p.color,
               p.email, p.phone, p.employment_type,
               p.site_ids, p.user_id, p.record_status,
               p.created_at, p.updated_at,
               c.name as clinic_name
        FROM professional p
        JOIN clinic c ON p.clinic_id = c.id
        WHERE ($1 = false OR p.record_status = 'ACTIVE')
        ORDER BY p.last_name, p.name
    """
    return execute_query(query, (active_only,))


def get_professional_by_id(professional_id: str) -> dict | None:
    """Obtiene un profesional por su ID."""
    query = """
        SELECT id, clinic_id, name, last_name,
               professional_type_id, specialties, color,
               email, phone, employment_type,
               site_ids, user_id, record_status,
               created_at, updated_at
        FROM professional
        WHERE id = %s
    """
    results = execute_query(query, (professional_id,))
    return results[0] if results else None


def get_professionals_by_clinic(clinic_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todos los profesionales de una clínica."""
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
    return execute_query(query, (clinic_id, active_only))


def get_professionals_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todos los profesionales que atienden en un site."""
    query = """
        SELECT id, clinic_id, name, last_name,
               professional_type_id, specialties, color,
               email, phone, employment_type,
               site_ids, user_id, record_status,
               created_at, updated_at
        FROM professional
        WHERE %s = ANY(site_ids)
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY last_name, name
    """
    return execute_query(query, (site_id, active_only))


# =============================================================================
# SERVICE & TREATMENT
# =============================================================================

def get_services_by_clinic(clinic_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todos los servicios de una clínica."""
    query = """
        SELECT id, clinic_id, name, description,
               record_status, created_at, updated_at
        FROM service
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (clinic_id, active_only))


def get_treatments_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todos los tratamientos de un site."""
    query = """
        SELECT id, clinic_id, site_id, service_id, category_id,
               name, treatment_type, duration_minutes,
               base_price, currency, treatment_visibility,
               record_status, created_at, updated_at
        FROM treatment
        WHERE site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (site_id, active_only))


# =============================================================================
# PATIENT
# =============================================================================

def get_patients_by_clinic(clinic_id: str, active_only: bool = True, limit: int = 100) -> list[dict]:
    """Obtiene pacientes de una clínica (con límite)."""
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
        LIMIT %s
    """
    return execute_query(query, (clinic_id, active_only, limit))


def get_patient_by_id(patient_id: str) -> dict | None:
    """Obtiene un paciente por su ID."""
    query = """
        SELECT id, clinic_id, name, last_name,
               document_type, document_number, birth_date,
               gender, email, phone,
               patient_scheduling_status, record_status,
               created_at, updated_at
        FROM patient
        WHERE id = %s
    """
    results = execute_query(query, (patient_id,))
    return results[0] if results else None


def get_patient_count_by_clinic(clinic_id: str, active_only: bool = True) -> int:
    """Obtiene el conteo de pacientes de una clínica."""
    query = """
        SELECT COUNT(*) as count
        FROM patient
        WHERE clinic_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
    """
    results = execute_query(query, (clinic_id, active_only))
    return results[0]["count"] if results else 0


# =============================================================================
# ROOM & EQUIPMENT
# =============================================================================

def get_rooms_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todas las salas de un site."""
    query = """
        SELECT id, clinic_id, site_id, name,
               room_type, capacity, room_status,
               record_status, created_at, updated_at
        FROM room
        WHERE site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (site_id, active_only))


def get_equipment_by_site(site_id: str, active_only: bool = True) -> list[dict]:
    """Obtiene todo el equipamiento de un site."""
    query = """
        SELECT id, clinic_id, site_id, name,
               equipment_type, model, serial_number,
               equipment_status, record_status,
               created_at, updated_at
        FROM equipment
        WHERE site_id = %s
          AND ($1 = false OR record_status = 'ACTIVE')
        ORDER BY name
    """
    return execute_query(query, (site_id, active_only))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_table_count(table_name: str) -> int:
    """Obtiene el conteo de registros de una tabla."""
    query = f"SELECT COUNT(*) as count FROM {table_name}"
    results = execute_query(query)
    return results[0]["count"] if results else 0


def get_clinic_summary(clinic_id: str) -> dict:
    """Obtiene un resumen de una clínica con conteos."""
    clinic = get_clinic_by_id(clinic_id)
    if not clinic:
        return None

    sites = get_sites_by_clinic(clinic_id)
    site_ids = [s["id"] for s in sites]

    rooms_count = 0
    equipment_count = 0
    treatments_count = 0

    for site_id in site_ids:
        rooms_count += len(get_rooms_by_site(site_id))
        equipment_count += len(get_equipment_by_site(site_id))
        treatments_count += len(get_treatments_by_site(site_id))

    return {
        "clinic": clinic,
        "sites_count": len(sites),
        "sites": sites,
        "professionals_count": len(get_professionals_by_clinic(clinic_id)),
        "services_count": len(get_services_by_clinic(clinic_id)),
        "patients_count": get_patient_count_by_clinic(clinic_id),
        "rooms_count": rooms_count,
        "equipment_count": equipment_count,
        "treatments_count": treatments_count,
    }


if __name__ == "__main__":
    # Test básico
    from ui import info, success, error, print_table

    info("Probando conexión y queries...")

    try:
        clinics = get_clinics()
        if clinics:
            success(f"Se encontraron {len(clinics)} clínica(s)")
            for c in clinics:
                print(f"  - {c['name']} ({c['id'][:8]}...)")

                sites = get_sites_by_clinic(c["id"])
                for s in sites:
                    print(f"      └── Site: {s['name']} ({s['id'][:8]}...)")
        else:
            info("No hay clínicas registradas")

    except Exception as e:
        error(f"Error: {e}")
