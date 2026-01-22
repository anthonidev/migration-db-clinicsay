import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import step, success, error, info, warning, confirm

load_dotenv()

# Tablas a preservar (no se limpian)
PRESERVED_TABLES = ["_prisma_migrations"]


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


def get_all_tables(cursor) -> list[str]:
    """Obtiene todas las tablas del schema public."""
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    return [row[0] for row in cursor.fetchall()]


def clean_database() -> None:
    """Limpia toda la data de la base de datos PostgreSQL."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL no encontrada en .env")

    step("Parseando DATABASE_URL...")
    db_config = parse_database_url(database_url)
    info(f"Base de datos: [cyan]{db_config['database']}[/cyan] en {db_config['host']}:{db_config['port']}")

    warning("[bold red]ADVERTENCIA: Esta operación eliminará TODOS los datos de la base de datos.[/bold red]")

    if not confirm("¿Estás seguro de que deseas continuar?"):
        info("Operación cancelada")
        return

    try:
        step("Conectando a la base de datos...")
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
        )
        conn.autocommit = False
        cursor = conn.cursor()

        step("Obteniendo lista de tablas...")
        tables = get_all_tables(cursor)
        tables_to_clean = [t for t in tables if t not in PRESERVED_TABLES]

        info(f"Se encontraron [cyan]{len(tables)}[/cyan] tablas, se limpiarán [cyan]{len(tables_to_clean)}[/cyan]")

        if PRESERVED_TABLES:
            preserved = [t for t in tables if t in PRESERVED_TABLES]
            if preserved:
                info(f"Tablas preservadas: [yellow]{', '.join(preserved)}[/yellow]")

        step("Deshabilitando triggers...")
        cursor.execute("SET session_replication_role = 'replica'")

        step("Limpiando tablas...")
        for table in tables_to_clean:
            cursor.execute(f'TRUNCATE TABLE public."{table}" CASCADE')

        step("Rehabilitando triggers...")
        cursor.execute("SET session_replication_role = 'origin'")

        conn.commit()
        success(f"Base de datos limpiada correctamente. Se limpiaron [cyan]{len(tables_to_clean)}[/cyan] tablas.")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        raise RuntimeError(f"Error de base de datos: {e}")


if __name__ == "__main__":
    clean_database()
