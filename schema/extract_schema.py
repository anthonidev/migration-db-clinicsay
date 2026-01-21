import os
import sys
import subprocess
from urllib.parse import urlparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import step, success, error, info

load_dotenv()


def parse_database_url(url: str) -> dict:
    """Parsea la DATABASE_URL y retorna los componentes."""
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


def minify_sql(file_path: str):
    """Elimina comentarios y lineas en blanco del archivo SQL."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            cleaned_lines.append(stripped)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned_lines))


def extract_schema() -> str:
    """Extrae el schema de la base de datos PostgreSQL y lo guarda en un archivo .sql"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL no encontrada en .env")

    step("Parseando DATABASE_URL...")
    db_config = parse_database_url(database_url)
    info(f"Base de datos: [cyan]{db_config['database']}[/cyan] en {db_config['host']}:{db_config['port']}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "clinicsay_schema.sql")

    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    cmd = [
        "pg_dump",
        "-h", db_config["host"],
        "-p", str(db_config["port"]),
        "-U", db_config["user"],
        "-d", db_config["database"],
        "-s",
        "--no-owner",
        "--no-privileges",
        "-f", output_path,
    ]

    try:
        step("Ejecutando pg_dump...")
        subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

        step("Minificando archivo SQL...")
        minify_sql(output_path)

        success(f"Schema extraído en: [cyan]{output_path}[/cyan]")
        return output_path

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error al extraer el schema: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError(
            "pg_dump no encontrado. Asegúrate de tener PostgreSQL instalado "
            "y que pg_dump esté en el PATH del sistema."
        )


if __name__ == "__main__":
    extract_schema()
