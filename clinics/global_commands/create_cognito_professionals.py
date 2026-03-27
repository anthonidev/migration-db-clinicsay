"""
Crea usuarios de Cognito para los profesionales activos de la clínica.

Para cada profesional activo con email:
  1. Crea app_user en la BD
  2. Crea usuario en AWS Cognito (sin email de verificación)
  3. Crea user_clinic con rol clinic_professional
  4. Actualiza professional.user_id con el ID del app_user

Usa la contraseña genérica de config.yaml (migration.cognito_password).

Tablas impactadas: app_user, user_clinic, professional
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

import boto3
import psycopg2
import yaml
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Paths
CLINICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT_DIR = os.path.dirname(CLINICS_DIR)

sys.path.insert(0, ROOT_DIR)

# Cargar variables de entorno
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from config.database import get_db_config
from config.utils import generate_id

# AWS Cognito config
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-3")


def load_clinic_queries(clinic_folder: str):
    """Carga queries.py de la clínica dinámicamente."""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    queries_path = os.path.join(clinic_dir, "queries.py")
    spec = importlib.util.spec_from_file_location("queries", queries_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_logging(clinic_folder: str):
    """Configura el archivo de log."""
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"create_cognito_professionals_{timestamp}.log")
    return open(log_file, "w", encoding="utf-8")


def load_migration_config(clinic_folder: str) -> dict:
    """Carga la configuración de migración desde config.yaml."""
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    config_path = os.path.join(clinic_dir, "config.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró config.yaml en {clinic_dir}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    migration = config.get("migration", {})
    if not migration.get("cognito_password"):
        raise ValueError("Falta 'migration.cognito_password' en config.yaml")

    return {
        "password": migration.get("cognito_password"),
    }


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


def get_active_professionals(cursor, clinic_id: str) -> list[dict]:
    """Obtiene los profesionales activos de la clínica."""
    cursor.execute(
        """
        SELECT id, name, last_name, email, user_id
        FROM professional
        WHERE clinic_id = %s
          AND record_status = 'ACTIVE'
        ORDER BY name, last_name
        """,
        (clinic_id,),
    )
    return cursor.fetchall()


def check_existing_user(cursor, email: str) -> dict | None:
    """Verifica si ya existe un app_user con ese email."""
    cursor.execute(
        "SELECT id, cognito_sub FROM app_user WHERE email = %s",
        (email,),
    )
    return cursor.fetchone()


def check_cognito_user_exists(cognito_client, email: str) -> dict | None:
    """Verifica si el usuario ya existe en Cognito."""
    try:
        response = cognito_client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
        )
        sub = None
        for attr in response.get("UserAttributes", []):
            if attr["Name"] == "sub":
                sub = attr["Value"]
                break
        return {
            "username": response["Username"],
            "sub": sub,
            "status": response["UserStatus"],
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "UserNotFoundException":
            return None
        raise


def create_cognito_user(cognito_client, email: str, name: str, last_name: str, password: str) -> str:
    """Crea usuario en Cognito y retorna el sub."""
    response = cognito_client.admin_create_user(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": name},
            {"Name": "family_name", "Value": last_name},
        ],
        MessageAction="SUPPRESS",
    )

    sub = None
    for attr in response["User"].get("Attributes", []):
        if attr["Name"] == "sub":
            sub = attr["Value"]
            break

    cognito_client.admin_set_user_password(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        Password=password,
        Permanent=True,
    )

    return sub


def create_cognito_professionals_main(clinic_folder: str):
    """Función principal para crear usuarios Cognito de profesionales."""
    log = None

    # Cargar queries y config
    queries = load_clinic_queries(clinic_folder)
    CLINIC_ID = queries.CLINIC_ID

    try:
        migration_config = load_migration_config(clinic_folder)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return

    password = migration_config["password"]

    if not COGNITO_USER_POOL_ID:
        print("ERROR: Falta COGNITO_USER_POOL_ID en .env")
        return

    log = setup_logging(clinic_folder)
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")
    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("CREAR USUARIOS COGNITO - PROFESIONALES")
        print("=" * 60)

        log.write(f"Crear usuarios Cognito profesionales - {datetime.now().isoformat()}\n")
        log.write(f"Clinic ID: {CLINIC_ID}\n")
        log.write(f"User Pool: {COGNITO_USER_POOL_ID}\n")
        log.write("-" * 60 + "\n\n")

        # 1. Obtener profesionales activos
        print("\n--- Obteniendo profesionales activos ---")
        professionals = get_active_professionals(cursor, CLINIC_ID)
        print(f"  Profesionales activos: {len(professionals)}")
        log.write(f"Profesionales activos: {len(professionals)}\n\n")

        # Filtrar los que tienen email
        profs_with_email = [p for p in professionals if p["email"]]
        profs_without_email = [p for p in professionals if not p["email"]]

        if profs_without_email:
            print(f"\n  Sin email (se omiten):")
            for p in profs_without_email:
                print(f"    - {p['name']} {p['last_name']}")
                log.write(f"[SKIP] {p['name']} {p['last_name']} - sin email\n")

        print(f"\n  Con email: {len(profs_with_email)}")

        # 2. Conectar a Cognito
        print("\n--- Conectando a AWS Cognito ---")
        cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
        print(f"  User Pool: {COGNITO_USER_POOL_ID}")
        print(f"  Región: {AWS_REGION}")
        log.write(f"[OK] Conexión a Cognito establecida\n\n")

        # 3. Procesar cada profesional
        print(f"\n--- Creando usuarios ({len(profs_with_email)}) ---")
        log.write("=== PROCESAMIENTO ===\n")

        now = datetime.now(timezone.utc)
        created = 0
        existing = 0
        errors = 0

        for p in profs_with_email:
            prof_name = f"{p['name']} {p['last_name']}"
            email = p["email"]

            try:
                # Verificar si ya tiene user_id asignado
                if p["user_id"]:
                    print(f"  [SKIP] {prof_name} - ya tiene user_id ({p['user_id'][:8]}...)")
                    log.write(f"[SKIP] {prof_name} ({email}) - ya tiene user_id: {p['user_id']}\n")
                    existing += 1
                    continue

                # Verificar si ya existe app_user con ese email
                existing_user = check_existing_user(cursor, email)

                if existing_user:
                    user_id = existing_user["id"]
                    cognito_sub = existing_user["cognito_sub"]
                    print(f"  [EXISTS] {prof_name} - app_user ya existe ({user_id[:8]}...)")
                    log.write(f"[EXISTS] {prof_name} ({email}) - app_user: {user_id}\n")
                else:
                    # Crear app_user
                    user_id = generate_id()
                    cognito_sub = f"pending-{user_id}"

                    record_metadata = {
                        "source": "migration",
                        "professional_id": p["id"],
                    }

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
                            cognito_sub,
                            email,
                            True,
                            p["name"],
                            p["last_name"],
                            "PROFESSIONAL",
                            "clinic_professional",
                            "ACTIVE",
                            json.dumps(record_metadata),
                            now,
                            now,
                            CLINIC_ID,
                        ),
                    )
                    log.write(f"[OK] app_user creado: {user_id} ({email})\n")

                # Crear user_clinic si no existe
                cursor.execute(
                    "SELECT id FROM user_clinic WHERE user_id = %s AND clinic_id = %s",
                    (user_id, CLINIC_ID),
                )
                if not cursor.fetchone():
                    user_clinic_id = generate_id()
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
                            "clinic_professional",
                            now,
                            "ACTIVE",
                            json.dumps({"source": "migration"}),
                            now,
                            now,
                        ),
                    )
                    log.write(f"  user_clinic creado: {user_clinic_id} (clinic_professional)\n")

                # Actualizar professional.user_id
                cursor.execute(
                    "UPDATE professional SET user_id = %s, updated_at = %s WHERE id = %s",
                    (user_id, now, p["id"]),
                )
                log.write(f"  professional.user_id actualizado\n")

                # Crear/verificar usuario en Cognito
                existing_cognito = check_cognito_user_exists(cognito_client, email)

                if existing_cognito:
                    cognito_sub = existing_cognito["sub"]
                    # Actualizar contraseña
                    cognito_client.admin_set_user_password(
                        UserPoolId=COGNITO_USER_POOL_ID,
                        Username=email,
                        Password=password,
                        Permanent=True,
                    )
                    log.write(f"  Cognito: ya existe (sub={cognito_sub}), contraseña actualizada\n")
                else:
                    cognito_sub = create_cognito_user(
                        cognito_client, email, p["name"], p["last_name"], password
                    )
                    log.write(f"  Cognito: creado (sub={cognito_sub})\n")

                # Actualizar cognito_sub real en app_user
                cursor.execute(
                    "UPDATE app_user SET cognito_sub = %s, updated_at = %s WHERE id = %s",
                    (cognito_sub, now, user_id),
                )

                conn.commit()
                created += 1
                print(f"  [OK] {prof_name} ({email})")

            except ClientError as e:
                conn.rollback()
                errors += 1
                error_msg = f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                print(f"  [ERROR] {prof_name}: {error_msg}")
                log.write(f"[ERROR] {prof_name} ({email}): {error_msg}\n")

            except Exception as e:
                conn.rollback()
                errors += 1
                print(f"  [ERROR] {prof_name}: {e}")
                log.write(f"[ERROR] {prof_name} ({email}): {e}\n")

        # Resumen
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"  Profesionales activos: {len(professionals)}")
        print(f"  Sin email (omitidos): {len(profs_without_email)}")
        print(f"  Creados: {created}")
        print(f"  Ya existentes: {existing}")
        if errors:
            print(f"  Errores: {errors}")
        print(f"  Password: (definida en config.yaml)")
        print(f"  Rol: clinic_professional")
        print(f"\nLog: {logs_dir}")

        log.write(f"\n=== COMPLETADO ===\n")
        log.write(f"Creados: {created}\n")
        log.write(f"Existentes: {existing}\n")
        log.write(f"Errores: {errors}\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        if log:
            log.write(f"\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        raise

    finally:
        cursor.close()
        conn.close()
        if log:
            log.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Crea usuarios Cognito para profesionales")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    args = parser.parse_args()
    create_cognito_professionals_main(args.clinic_folder)
