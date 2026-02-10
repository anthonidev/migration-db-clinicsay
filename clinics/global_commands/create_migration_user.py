"""
Crea un usuario de sistema para operaciones de migración.

Este usuario se utiliza como created_by_user_id y assignee_user_id
en tablas que requieren un usuario (task, etc.) cuando no hay
usuarios reales en el sistema.

Tablas impactadas: app_user, user_clinic
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.utils import generate_id
from config.database import get_db_config

import psycopg2
import yaml
from psycopg2.extras import RealDictCursor

# Paths
CLINICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load_clinic_queries(clinic_folder: str):
    """Carga queries.py de la clínica dinámicamente."""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    queries_path = os.path.join(clinic_dir, "queries.py")
    spec = importlib.util.spec_from_file_location("queries", queries_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_migration_config(clinic_folder: str) -> dict:
    """Carga la configuración de migración desde config.yaml."""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    config_path = os.path.join(clinic_dir, "config.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró config.yaml en {clinic_dir}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    migration = config.get("migration", {})
    if not migration.get("user_email"):
        raise ValueError("Falta 'migration.user_email' en config.yaml")

    return {
        "email": migration.get("user_email"),
        "name": migration.get("user_name", "Sistema"),
        "last_name": migration.get("user_last_name", "Migración"),
    }


def setup_logging(clinic_folder: str):
    """Configura el archivo de log."""
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"create_migration_user_{timestamp}.log")
    return open(log_file, "w", encoding="utf-8")


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


def check_existing_migration_user(cursor, clinic_id: str, email: str) -> dict | None:
    """Verifica si ya existe el usuario de migración"""
    cursor.execute(
        """
        SELECT u.id, u.email, u.name, u.last_name, u.record_status,
               uc.role_in_clinic
        FROM app_user u
        LEFT JOIN user_clinic uc ON u.id = uc.user_id AND uc.clinic_id = %s
        WHERE u.email = %s
        """,
        (clinic_id, email)
    )
    return cursor.fetchone()


def create_migration_user(clinic_folder: str):
    """Función principal para crear usuario de migración"""
    # Cargar queries de la clínica
    queries = load_clinic_queries(clinic_folder)
    CLINIC_ID = queries.CLINIC_ID

    # Cargar configuración
    try:
        migration_config = load_migration_config(clinic_folder)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return

    user_email = migration_config["email"]
    user_name = migration_config["name"]
    user_last_name = migration_config["last_name"]

    conn = get_connection()
    cursor = conn.cursor()
    log = setup_logging(clinic_folder)
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")

    try:
        print("=" * 60)
        print("CREACIÓN DE USUARIO DE MIGRACIÓN")
        print("=" * 60)
        print(f"\nConfiguración desde config.yaml:")
        print(f"  Email: {user_email}")
        print(f"  Nombre: {user_name} {user_last_name}")

        log.write(f"Creación de usuario de migración - {datetime.now().isoformat()}\n")
        log.write(f"Clinic ID: {CLINIC_ID}\n")
        log.write(f"Email: {user_email}\n")
        log.write(f"Nombre: {user_name} {user_last_name}\n")
        log.write("-" * 60 + "\n\n")

        # Verificar si ya existe
        existing = check_existing_migration_user(cursor, CLINIC_ID, user_email)
        if existing:
            print(f"\nEl usuario de migración ya existe:")
            print(f"  ID: {existing['id']}")
            print(f"  Email: {existing['email']}")
            print(f"  Nombre: {existing['name']} {existing['last_name']}")
            print(f"  Estado: {existing['record_status']}")
            print(f"  Rol en clínica: {existing['role_in_clinic'] or 'N/A'}")
            print("\nNo se requiere acción.")
            print(f"\nLog guardado en: {logs_dir}")

            log.write(f"[EXISTS] Usuario ya existe: {existing['id']}\n")
            log.write(f"  Email: {existing['email']}\n")
            log.write(f"  Nombre: {existing['name']} {existing['last_name']}\n")
            log.write(f"  Rol en clínica: {existing['role_in_clinic'] or 'N/A'}\n")
            log.write("\n=== COMPLETADO (sin cambios) ===\n")
            return

        # Crear usuario
        user_id = generate_id()
        user_clinic_id = generate_id()
        now = datetime.now(timezone.utc)

        record_metadata = {
            "source": "migration",
            "is_migration_user": True,
            "created_for": "data_migration",
            "clinic_id": CLINIC_ID,
        }

        # 1. Crear usuario en app_user
        cursor.execute(
            """
            INSERT INTO app_user (
                id, cognito_sub, email, email_verified,
                name, last_name, user_type, role_base,
                record_status, record_metadata,
                created_at, updated_at,
                last_active_clinic_id
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s
            )
            """,
            (
                user_id,
                f"migration-{user_id}",  # cognito_sub placeholder
                user_email,
                True,
                user_name,
                user_last_name,
                "SYSTEM",
                "clinic_owner",  # role_base
                "ACTIVE",
                json.dumps(record_metadata),
                now,
                now,
                CLINIC_ID  # last_active_clinic_id
            )
        )

        # 2. Vincular usuario a la clínica con rol clinic_owner
        cursor.execute(
            """
            INSERT INTO user_clinic (
                id, user_id, clinic_id, role_in_clinic,
                joined_at, record_status, record_metadata,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            """,
            (
                user_clinic_id,
                user_id,
                CLINIC_ID,
                "clinic_owner",  # role_in_clinic
                now,
                "ACTIVE",
                json.dumps({"source": "migration"}),
                now,
                now
            )
        )

        conn.commit()

        print(f"\nUsuario de migración creado exitosamente!")
        print()
        print(f"  ID:              {user_id}")
        print(f"  Email:           {user_email}")
        print(f"  Nombre:          {user_name} {user_last_name}")
        print(f"  Tipo:            SYSTEM")
        print(f"  Rol en clínica:  clinic_owner")
        print()
        print("Este usuario será utilizado automáticamente por los scripts")
        print("que requieren un created_by_user_id (ej: insert_nota.py)")
        print(f"\nLog guardado en: {logs_dir}")

        log.write(f"[OK] Usuario creado: {user_id}\n")
        log.write(f"  Email: {user_email}\n")
        log.write(f"  Nombre: {user_name} {user_last_name}\n")
        log.write(f"  Tipo: SYSTEM\n")
        log.write(f"  Rol en clínica: clinic_owner\n")
        log.write(f"[OK] Vinculado a clínica: {CLINIC_ID}\n")
        log.write("\n=== COMPLETADO ===\n")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        log.write(f"\n[ERROR] {e}\n")
        raise
    finally:
        cursor.close()
        conn.close()
        log.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Crea usuario de migración para una clínica")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    args = parser.parse_args()
    create_migration_user(args.clinic_folder)
