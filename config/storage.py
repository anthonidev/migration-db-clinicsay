"""
Cliente de almacenamiento S3 para subir archivos.

Soporta:
- Bucket GENERAL: archivos mutables (fotos de perfil, etc.)
- Bucket WORM: archivos inmutables (consentimientos firmados, evidencias)

Configuración via .env:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- OBJECT_STORAGE_S3_BUCKET_GENERAL
- OBJECT_STORAGE_S3_BUCKET_WORM
- OBJECT_STORAGE_S3_ENDPOINT (opcional)
"""

import os
import mimetypes
from typing import Literal
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


@dataclass
class StorageConfig:
    """Configuración de almacenamiento S3."""
    access_key_id: str
    secret_access_key: str
    region: str
    bucket_general: str
    bucket_worm: str
    endpoint_url: str | None = None
    force_path_style: bool = False


def get_storage_config() -> StorageConfig:
    """Obtiene la configuración de S3 desde variables de entorno."""
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.getenv("AWS_REGION", "eu-west-3").strip()
    bucket_general = os.getenv("OBJECT_STORAGE_S3_BUCKET_GENERAL", "").strip()
    bucket_worm = os.getenv("OBJECT_STORAGE_S3_BUCKET_WORM", "").strip()
    endpoint = os.getenv("OBJECT_STORAGE_S3_ENDPOINT", "").strip() or None
    force_path = os.getenv("OBJECT_STORAGE_S3_FORCE_PATH_STYLE", "false").lower() == "true"

    if not access_key:
        raise ValueError("AWS_ACCESS_KEY_ID no configurado en .env")
    if not secret_key:
        raise ValueError("AWS_SECRET_ACCESS_KEY no configurado en .env")
    if not bucket_general:
        raise ValueError("OBJECT_STORAGE_S3_BUCKET_GENERAL no configurado en .env")
    if not bucket_worm:
        raise ValueError("OBJECT_STORAGE_S3_BUCKET_WORM no configurado en .env")

    return StorageConfig(
        access_key_id=access_key,
        secret_access_key=secret_key,
        region=region,
        bucket_general=bucket_general,
        bucket_worm=bucket_worm,
        endpoint_url=endpoint,
        force_path_style=force_path,
    )


class S3Client:
    """Cliente para operaciones S3."""

    def __init__(self, config: StorageConfig | None = None):
        self.config = config or get_storage_config()
        self._client = None

    @property
    def client(self):
        """Lazy initialization del cliente S3."""
        if self._client is None:
            boto_config = Config(
                region_name=self.config.region,
                s3={"addressing_style": "path" if self.config.force_path_style else "auto"},
            )
            self._client = boto3.client(
                "s3",
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region,
                endpoint_url=self.config.endpoint_url,
                config=boto_config,
            )
        return self._client

    def get_bucket(self, bucket_type: Literal["general", "worm"]) -> str:
        """Obtiene el nombre del bucket según el tipo."""
        if bucket_type == "worm":
            return self.config.bucket_worm
        return self.config.bucket_general

    def upload_file(
        self,
        file_path: str,
        key: str,
        bucket_type: Literal["general", "worm"] = "general",
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Sube un archivo a S3.

        Args:
            file_path: Ruta local del archivo
            key: Key (path) en S3, ej: "consents/evidence/uuid.pdf"
            bucket_type: "general" o "worm"
            content_type: MIME type (auto-detectado si no se especifica)
            metadata: Metadata adicional para el objeto

        Returns:
            URL del archivo subido (s3://bucket/key format)

        Raises:
            FileNotFoundError: Si el archivo no existe
            ClientError: Si hay error de S3
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        bucket = self.get_bucket(bucket_type)

        # Auto-detectar content type
        if content_type is None:
            content_type, _ = mimetypes.guess_type(file_path)
            content_type = content_type or "application/octet-stream"

        extra_args = {
            "ContentType": content_type,
        }
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        self.client.upload_file(
            Filename=file_path,
            Bucket=bucket,
            Key=key,
            ExtraArgs=extra_args,
        )

        return f"s3://{bucket}/{key}"

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        bucket_type: Literal["general", "worm"] = "general",
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """
        Sube bytes directamente a S3.

        Args:
            data: Bytes a subir
            key: Key (path) en S3
            bucket_type: "general" o "worm"
            content_type: MIME type
            metadata: Metadata adicional

        Returns:
            URL del archivo subido
        """
        bucket = self.get_bucket(bucket_type)

        extra_args = {
            "ContentType": content_type,
        }
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            **extra_args,
        )

        return f"s3://{bucket}/{key}"

    def file_exists(self, key: str, bucket_type: Literal["general", "worm"] = "general") -> bool:
        """Verifica si un archivo existe en S3."""
        bucket = self.get_bucket(bucket_type)
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def get_public_url(self, key: str, bucket_type: Literal["general", "worm"] = "general") -> str:
        """
        Genera la URL pública del archivo.
        Nota: El bucket debe tener permisos públicos configurados.
        """
        bucket = self.get_bucket(bucket_type)
        region = self.config.region
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    def generate_presigned_url(
        self,
        key: str,
        bucket_type: Literal["general", "worm"] = "general",
        expiration: int = 3600,
    ) -> str:
        """
        Genera una URL firmada temporal para acceso al archivo.

        Args:
            key: Key del archivo en S3
            bucket_type: "general" o "worm"
            expiration: Tiempo de expiración en segundos (default: 1 hora)

        Returns:
            URL firmada temporal
        """
        bucket = self.get_bucket(bucket_type)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )

    def delete_file(self, key: str, bucket_type: Literal["general", "worm"] = "general") -> bool:
        """
        Elimina un archivo de S3.
        Nota: Los archivos en bucket WORM pueden tener restricciones de borrado.

        Returns:
            True si se eliminó correctamente
        """
        bucket = self.get_bucket(bucket_type)
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def test_connection(self) -> tuple[bool, str]:
        """
        Prueba la conexión a S3.

        Returns:
            Tuple (success, message)
        """
        try:
            # Verificar acceso a los buckets configurados (no requiere ListAllMyBuckets)
            for bucket_type in ["general", "worm"]:
                bucket = self.get_bucket(bucket_type)
                try:
                    self.client.head_bucket(Bucket=bucket)
                except ClientError as e:
                    error_code = e.response["Error"]["Code"]
                    if error_code == "404":
                        return False, f"Bucket '{bucket}' no existe"
                    elif error_code == "403":
                        return False, f"Sin acceso al bucket '{bucket}'"
                    raise

            return True, "Conexión exitosa a S3"

        except ClientError as e:
            return False, f"Error de S3: {e.response['Error']['Message']}"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"


# Instancia global para uso conveniente
_storage_client: S3Client | None = None


def get_storage_client() -> S3Client:
    """Obtiene la instancia global del cliente S3."""
    global _storage_client
    if _storage_client is None:
        _storage_client = S3Client()
    return _storage_client


# =============================================================================
# Funciones de conveniencia para estructura de keys
# =============================================================================

def consent_evidence_key(consent_instance_id: str) -> str:
    """
    Genera el key para un PDF de evidencia de consentimiento.
    Estructura: consents/evidence/{consentInstanceId}.pdf
    """
    return f"consents/evidence/{consent_instance_id}.pdf"


def consent_signature_key(consent_instance_id: str, timestamp: str) -> str:
    """
    Genera el key para una imagen de firma de consentimiento.
    Estructura: consents/signatures/{consentInstanceId}/{timestamp}.png
    """
    return f"consents/signatures/{consent_instance_id}/{timestamp}.png"


def professional_photo_key(clinic_id: str, professional_id: str, extension: str = "jpg") -> str:
    """
    Genera el key para una foto de perfil de profesional.
    Estructura: professionals/{clinicId}/{professionalId}/profile.{ext}
    """
    return f"professionals/{clinic_id}/{professional_id}/profile.{extension}"


def equipment_photo_key(clinic_id: str, equipment_id: str, extension: str = "jpg") -> str:
    """
    Genera el key para una foto de equipo.
    Estructura: equipment/{clinicId}/{equipmentId}/photo.{ext}
    """
    return f"equipment/{clinic_id}/{equipment_id}/photo.{extension}"


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing S3 connection...")
    try:
        client = get_storage_client()
        success, message = client.test_connection()
        if success:
            print(f"[OK] {message}")
            print(f"  Bucket General: {client.config.bucket_general}")
            print(f"  Bucket WORM: {client.config.bucket_worm}")
            print(f"  Region: {client.config.region}")
        else:
            print(f"[ERROR] {message}")
    except Exception as e:
        print(f"[ERROR] {e}")
