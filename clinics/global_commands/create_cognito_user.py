"""
Crea un usuario en AWS Cognito para el usuario de migración.

Este script actualiza el usuario de migración existente en app_user
con un cognito_sub real, permitiendo que pueda autenticarse en la aplicación.

IMPORTANTE:
- Requiere que el usuario de migración ya exista en app_user
- No envía email de verificación
- Usa la contraseña definida en config.yaml

Tabla impactada: app_user (actualiza cognito_sub)
"""
import importlib.util
import json
import os
import sys
from datetime import datetime

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
    log_file = os.path.join(logs_dir, f"create_cognito_user_{timestamp}.log")
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
    if not migration.get("user_email"):
        raise ValueError("Falta 'migration.user_email' en config.yaml")
    if not migration.get("cognito_password"):
        raise ValueError("Falta 'migration.cognito_password' en config.yaml")

    return {
        "email": migration.get("user_email"),
        "name": migration.get("user_name", "Sistema"),
        "last_name": migration.get("user_last_name", "Migración"),
        "password": migration.get("cognito_password"),
    }


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


def get_migration_user(cursor, email: str) -> dict | None:
    """Obtiene el usuario de migración de la base de datos."""
    cursor.execute(
        """
        SELECT id, email, name, last_name, cognito_sub, record_metadata
        FROM app_user
        WHERE email = %s
        """,
        (email,)
    )
    return cursor.fetchone()


def check_cognito_user_exists(cognito_client, email: str) -> dict | None:
    """Verifica si el usuario ya existe en Cognito."""
    try:
        response = cognito_client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email
        )
        # Obtener el sub del usuario
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
    """
    Crea un usuario en Cognito y retorna el sub.

    - No envía email de verificación
    - Establece contraseña permanente
    - Marca email como verificado
    """
    # 1. Crear usuario sin enviar email
    response = cognito_client.admin_create_user(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": name},
            {"Name": "family_name", "Value": last_name},
        ],
        MessageAction="SUPPRESS",  # No enviar email
    )

    # Obtener el sub del usuario creado
    sub = None
    for attr in response["User"].get("Attributes", []):
        if attr["Name"] == "sub":
            sub = attr["Value"]
            break

    # 2. Establecer contraseña permanente
    cognito_client.admin_set_user_password(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        Password=password,
        Permanent=True
    )

    return sub


def update_user_cognito_sub(cursor, user_id: str, cognito_sub: str):
    """Actualiza el cognito_sub del usuario en la base de datos."""
    cursor.execute(
        """
        UPDATE app_user
        SET cognito_sub = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (cognito_sub, user_id)
    )


def create_cognito_user_main(clinic_folder: str):
    """Función principal para crear usuario en Cognito."""
    log = None

    try:
        # Cargar configuración
        migration_config = load_migration_config(clinic_folder)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return

    user_email = migration_config["email"]
    user_name = migration_config["name"]
    user_last_name = migration_config["last_name"]
    user_password = migration_config["password"]
    logs_dir = os.path.join(CLINICS_DIR, clinic_folder, "logs")

    # Verificar configuración de AWS
    if not COGNITO_USER_POOL_ID:
        print("ERROR: Falta COGNITO_USER_POOL_ID en .env")
        return

    print("=" * 60)
    print("CREAR USUARIO EN AWS COGNITO")
    print("=" * 60)
    print(f"\nConfiguración:")
    print(f"  Email:         {user_email}")
    print(f"  Nombre:        {user_name} {user_last_name}")
    print(f"  User Pool:     {COGNITO_USER_POOL_ID}")
    print(f"  Región:        {AWS_REGION}")
    print(f"\n*** NO SE ENVIARÁ EMAIL DE VERIFICACIÓN ***")

    # Confirmar
    print("\n¿Estás seguro de crear este usuario en Cognito?")
    print("Escribe 'CONFIRMAR' para continuar:")
    confirmation = input().strip()

    if confirmation != "CONFIRMAR":
        print("\nOperación cancelada.")
        return

    log = setup_logging(clinic_folder)
    log.write(f"Crear usuario Cognito - {datetime.now().isoformat()}\n")
    log.write(f"Email: {user_email}\n")
    log.write(f"User Pool: {COGNITO_USER_POOL_ID}\n")
    log.write("-" * 60 + "\n\n")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Verificar que existe el usuario en la BD
        print("\n--- Verificando usuario en base de datos ---")
        db_user = get_migration_user(cursor, user_email)

        if not db_user:
            print(f"ERROR: No existe usuario con email '{user_email}' en app_user")
            print("Ejecute primero 'Crear usuario de migración'")
            log.write(f"[ERROR] Usuario no existe en BD: {user_email}\n")
            return

        print(f"  Usuario encontrado: {db_user['id'][:8]}...")
        print(f"  Cognito sub actual: {db_user['cognito_sub']}")
        log.write(f"[OK] Usuario encontrado en BD: {db_user['id']}\n")
        log.write(f"  Cognito sub actual: {db_user['cognito_sub']}\n")

        # 2. Crear cliente de Cognito
        print("\n--- Conectando a AWS Cognito ---")
        cognito_client = boto3.client(
            "cognito-idp",
            region_name=AWS_REGION
        )
        print("  Conexión establecida")
        log.write("[OK] Conexión a Cognito establecida\n")

        # 3. Verificar si ya existe en Cognito
        print("\n--- Verificando usuario en Cognito ---")
        existing_cognito = check_cognito_user_exists(cognito_client, user_email)

        if existing_cognito:
            print(f"  Usuario ya existe en Cognito:")
            print(f"    Sub:    {existing_cognito['sub']}")
            print(f"    Status: {existing_cognito['status']}")

            log.write(f"[EXISTS] Usuario ya existe en Cognito\n")
            log.write(f"  Sub: {existing_cognito['sub']}\n")
            log.write(f"  Status: {existing_cognito['status']}\n")

            # Actualizar contraseña del usuario existente
            print(f"\n  Actualizando contraseña...")
            cognito_client.admin_set_user_password(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=user_email,
                Password=user_password,
                Permanent=True
            )
            print(f"  [OK] Contraseña actualizada")
            log.write(f"[OK] Contraseña actualizada\n")

            # Actualizar cognito_sub en BD si es diferente
            if db_user['cognito_sub'] != existing_cognito['sub']:
                print(f"\n  Actualizando cognito_sub en base de datos...")
                update_user_cognito_sub(cursor, db_user['id'], existing_cognito['sub'])
                conn.commit()
                print(f"  [OK] cognito_sub actualizado")
                log.write(f"[OK] cognito_sub actualizado en BD\n")
            else:
                print(f"\n  cognito_sub ya está sincronizado")
                log.write(f"[OK] cognito_sub ya sincronizado\n")

            log.write("\n=== COMPLETADO ===\n")
            print(f"\nLog guardado en: {logs_dir}")
            return

        # 4. Crear usuario en Cognito
        print("\n--- Creando usuario en Cognito ---")
        cognito_sub = create_cognito_user(
            cognito_client,
            user_email,
            user_name,
            user_last_name,
            user_password
        )
        print(f"  [OK] Usuario creado")
        print(f"  Sub: {cognito_sub}")
        log.write(f"[OK] Usuario creado en Cognito\n")
        log.write(f"  Sub: {cognito_sub}\n")

        # 5. Actualizar cognito_sub en la BD
        print("\n--- Actualizando base de datos ---")
        update_user_cognito_sub(cursor, db_user['id'], cognito_sub)
        conn.commit()
        print(f"  [OK] cognito_sub actualizado en app_user")
        log.write(f"[OK] cognito_sub actualizado en BD\n")

        # Resumen
        print("\n" + "=" * 60)
        print("USUARIO COGNITO CREADO EXITOSAMENTE")
        print("=" * 60)
        print(f"\n  Email:       {user_email}")
        print(f"  Cognito Sub: {cognito_sub}")
        print(f"  Status:      CONFIRMED")
        print(f"\nEl usuario puede autenticarse con:")
        print(f"  Email:    {user_email}")
        print(f"  Password: (definida en config.yaml)")
        print(f"\nLog guardado en: {logs_dir}")

        log.write("\n" + "=" * 60 + "\n")
        log.write("RESUMEN\n")
        log.write("=" * 60 + "\n")
        log.write(f"Email: {user_email}\n")
        log.write(f"Cognito Sub: {cognito_sub}\n")
        log.write(f"Status: CONFIRMED\n")
        log.write("\n=== COMPLETADO ===\n")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        print(f"\nERROR DE COGNITO: [{error_code}] {error_msg}")
        if log:
            log.write(f"\n[ERROR] Cognito: [{error_code}] {error_msg}\n")
        raise

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        if log:
            log.write(f"\n[ERROR] {e}\n")
        raise

    finally:
        cursor.close()
        conn.close()
        if log:
            log.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Crea usuario Cognito para una clínica")
    parser.add_argument("clinic_folder", help="Nombre de la carpeta de la clínica")
    args = parser.parse_args()
    create_cognito_user_main(args.clinic_folder)
