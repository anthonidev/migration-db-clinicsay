import sys
from ui import (
    console,
    print_banner,
    print_menu,
    print_separator,
    info,
    success,
    error,
    ask,
    clear,
)


def show_menu():
    """Muestra el menu principal."""
    clear()
    print_banner(subtitle="Sistema de Migración de Datos")

    print_menu(
        title="Menú Principal",
        options=[
            {"key": "1", "label": "Extraer schema de la base de datos", "group": "Schema"},
            {"key": "2", "label": "Inicializar nueva clínica", "group": "Clínicas"},
            {"key": "3", "label": "Validar e insertar configuración", "group": "Clínicas"},
            {"key": "4", "label": "Generar queries de clínica", "group": "Clínicas"},
            {"key": "5", "label": "Ejecutar comandos de clínica", "group": "Migración"},
            {"key": "6", "label": "Sincronizar documentación", "group": "Documentación"},
            {"key": "0", "label": "Salir", "group": "Sistema"},
        ]
    )


def extract_schema_option():
    """Opcion para extraer el schema."""
    from schema.extract_schema import extract_schema

    info("Extrayendo schema de la base de datos...")
    try:
        output_path = extract_schema()
        success(f"Schema guardado en: {output_path}")
    except Exception as e:
        error(f"{e}")



def init_clinic_option():
    """Opcion para inicializar una nueva clínica."""
    from clinics.init_clinic import init_clinic

    try:
        init_clinic()
    except KeyboardInterrupt:
        console.print()
        info("Operación cancelada")
    except Exception as e:
        error(f"{e}")


def validate_insert_option():
    """Opcion para validar e insertar configuración."""
    from clinics.validate_and_insert import validate_and_insert

    try:
        validate_and_insert()
    except KeyboardInterrupt:
        console.print()
        info("Operación cancelada")
    except Exception as e:
        error(f"{e}")


def generate_queries_option():
    """Opcion para generar queries de una clínica."""
    from clinics.generate_queries import generate_queries

    try:
        generate_queries()
    except KeyboardInterrupt:
        console.print()
        info("Operación cancelada")
    except Exception as e:
        error(f"{e}")


def run_commands_option():
    """Opcion para ejecutar comandos de una clínica."""
    from clinics.run_commands import run_clinic_commands

    try:
        run_clinic_commands()
    except KeyboardInterrupt:
        console.print()
        info("Operación cancelada")
    except Exception as e:
        error(f"{e}")


def sync_docs_option():
    """Opcion para sincronizar documentación."""
    from docs.sync_docs import sync_docs

    try:
        sync_docs()
    except KeyboardInterrupt:
        console.print()
        info("Operación cancelada")
    except Exception as e:
        error(f"{e}")


def main():
    """Funcion principal del menu."""
    while True:
        show_menu()

        try:
            option = ask("Selecciona una opción")
        except KeyboardInterrupt:
            console.print("\n")
            info("Saliendo...")
            sys.exit(0)

        if option == "1":
            extract_schema_option()
            ask("Presiona Enter para continuar")
        elif option == "2":
            init_clinic_option()
            ask("Presiona Enter para continuar")
        elif option == "3":
            validate_insert_option()
            ask("Presiona Enter para continuar")
        elif option == "4":
            generate_queries_option()
            ask("Presiona Enter para continuar")
        elif option == "5":
            run_commands_option()
        elif option == "6":
            sync_docs_option()
            ask("Presiona Enter para continuar")
        elif option == "0":
            info("¡Hasta luego!")
            sys.exit(0)
        else:
            error("Opción no válida")
            ask("Presiona Enter para continuar")


if __name__ == "__main__":
    main()
