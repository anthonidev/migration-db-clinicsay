"""
Resetea la contraseña de un usuario en AWS Cognito.

Recibe un email, verifica que el usuario exista en Cognito,
y establece una nueva contraseña permanente.

IMPORTANTE:
- El usuario ya debe existir en Cognito
- No envía email de verificación
- Establece la contraseña como permanente
"""
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Paths
CLINICS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CLINICS_DIR)

sys.path.insert(0, ROOT_DIR)

# Cargar variables de entorno
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from ui import (
    print_header,
    print_key_value,
    info,
    success,
    error,
    warning,
    ask,
    confirm,
)

# AWS Cognito config
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-3")


def check_cognito_user_exists(cognito_client, email: str) -> dict | None:
    """Verifica si el usuario existe en Cognito."""
    try:
        response = cognito_client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email
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


def reset_cognito_password():
    """Resetea la contraseña de un usuario en Cognito."""
    print_header("Reset Password - Cognito")

    # Verificar configuración de AWS
    if not COGNITO_USER_POOL_ID:
        error("Falta COGNITO_USER_POOL_ID en .env")
        return

    # Pedir email
    email = ask("Email del usuario").strip()
    if not email:
        error("Debe ingresar un email")
        return

    # Contraseña por defecto
    new_password = "Clinicsay_2026"
    info(f"Contraseña: {new_password}")

    info(f"User Pool: {COGNITO_USER_POOL_ID}")
    info(f"Región: {AWS_REGION}")

    try:
        # Conectar a Cognito
        cognito_client = boto3.client(
            "cognito-idp",
            region_name=AWS_REGION
        )

        # Verificar que el usuario existe
        info("Verificando usuario en Cognito...")
        existing_user = check_cognito_user_exists(cognito_client, email)

        if not existing_user:
            error(f"No existe usuario con email '{email}' en Cognito")
            return

        print_key_value({
            "Email": email,
            "Sub": existing_user["sub"],
            "Status": existing_user["status"],
        })

        # Confirmar
        if not confirm("¿Resetear la contraseña de este usuario?"):
            info("Operación cancelada")
            return

        # Resetear contraseña
        info("Reseteando contraseña...")
        cognito_client.admin_set_user_password(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
            Password=new_password,
            Permanent=True
        )

        success(f"Contraseña reseteada para: {email}")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        error(f"Error de Cognito: [{error_code}] {error_msg}")

    except Exception as e:
        error(f"{e}")
