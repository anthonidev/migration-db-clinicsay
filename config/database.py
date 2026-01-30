import os
from urllib.parse import urlparse
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_db_config(use_production: bool = False) -> dict:
    """
    Obtiene la configuración de la base de datos.

    Args:
        use_production: Si True, usa DATABASE_URL_PRD en lugar de DATABASE_URL
    """
    env_var = "DATABASE_URL_PRD" if use_production else "DATABASE_URL"
    url = os.getenv(env_var)
    if not url:
        raise ValueError(f"{env_var} no encontrada en .env")

    parsed = urlparse(url)
    database = parsed.path[1:] if parsed.path else ""
    if "?" in database:
        database = database.split("?")[0]

    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": database,
    }


@contextmanager
def get_connection():
    """Context manager para conexión a la base de datos."""
    config = get_db_config()
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        dbname=config["database"],
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit=True):
    """Context manager para cursor con diccionario."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()


def execute_query(query: str, params: tuple = None) -> list:
    """Ejecuta una query y retorna los resultados."""
    with get_cursor(commit=False) as cursor:
        cursor.execute(query, params)
        if cursor.description:
            return cursor.fetchall()
        return []


def execute_insert(query: str, params: tuple = None) -> None:
    """Ejecuta un INSERT/UPDATE/DELETE."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(query, params)


def execute_many(query: str, params_list: list) -> None:
    """Ejecuta múltiples INSERTs."""
    with get_cursor(commit=True) as cursor:
        cursor.executemany(query, params_list)


def execute_script(sql: str) -> None:
    """Ejecuta un script SQL completo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()


def test_connection() -> bool:
    """Prueba la conexión a la base de datos."""
    try:
        with get_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a la BD: {e}")
        return False
