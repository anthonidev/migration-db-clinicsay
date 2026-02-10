import os
import re
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
    """Optimiza el schema SQL para uso como contexto, eliminando ruido."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Líneas que no aportan como contexto
    SKIP_PREFIXES = (
        "SET ", "SELECT ", "\\restrict", "\\unrestrict", "COMMENT ON", "CREATE EXTENSION",
        "CREATE FUNCTION", "CREATE INDEX", "CREATE UNIQUE INDEX",
        "ALTER TABLE ONLY public._prisma_migrations",
        "--",
    )

    cleaned = []
    skip_block = False
    skip_table = False

    for line in lines:
        stripped = line.strip()

        # Saltar vacías
        if not stripped:
            continue

        # Saltar prefijos innecesarios
        if stripped.startswith(SKIP_PREFIXES):
            # Si es CREATE FUNCTION, saltar hasta el final del bloque
            if stripped.startswith("CREATE FUNCTION"):
                skip_block = True
            continue

        # Saltar bloque de función (hasta ;)
        if skip_block:
            if stripped.endswith(";"):
                skip_block = False
            continue

        # Saltar tabla _prisma_migrations
        if stripped.startswith("CREATE TABLE public._prisma_migrations"):
            skip_table = True
            continue
        if skip_table:
            if stripped == ");":
                skip_table = False
            continue

        # Saltar constraints que no son FOREIGN KEY (PRIMARY KEY, UNIQUE, CHECK)
        if stripped.startswith("ALTER TABLE") and "ADD CONSTRAINT" in stripped:
            if "FOREIGN KEY" not in stripped:
                continue

        # Eliminar prefijo public. repetitivo
        stripped = stripped.replace("public.", "")

        # Eliminar defaults repetitivos comunes
        stripped = stripped.replace(" DEFAULT CURRENT_TIMESTAMP NOT NULL", " NOT NULL")
        stripped = stripped.replace(" DEFAULT 'ACTIVE'::\"RecordStatus\" NOT NULL", " NOT NULL")

        # Eliminar casting de enums en defaults (ej: 'PENDING'::"Status")
        stripped = re.sub(r" DEFAULT '[^']+'::\"[^\"]+\" NOT NULL", " NOT NULL", stripped)

        cleaned.append(stripped)

    # Colapsar ALTER TABLE + ADD CONSTRAINT en una sola línea
    merged = []
    i = 0
    while i < len(cleaned):
        if cleaned[i].startswith("ALTER TABLE") and "ADD CONSTRAINT" not in cleaned[i]:
            if i + 1 < len(cleaned) and cleaned[i + 1].startswith("ADD CONSTRAINT"):
                merged.append(cleaned[i] + " " + cleaned[i + 1])
                i += 2
                continue
        merged.append(cleaned[i])
        i += 1
    cleaned = merged

    # Colapsar enums multilínea en una sola línea
    # CREATE TYPE "X" AS ENUM (\n'A',\n'B'\n); -> CREATE TYPE "X" AS ENUM ('A','B');
    result = "\n".join(cleaned)
    result = re.sub(
        r"(CREATE TYPE [^\n]+ AS ENUM \()\n([^;]+?)\n(\);)",
        lambda m: m.group(1) + m.group(2).replace("\n", "") + m.group(3),
        result
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(result)


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
