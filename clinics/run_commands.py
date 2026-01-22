"""
Sistema de ejecución de comandos por clínica.
Lee commands.yaml de cada clínica y permite ejecutar sus scripts.
"""

import os
import sys
import importlib.util

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import (
    console,
    print_header,
    print_subheader,
    print_menu,
    print_table,
    info,
    success,
    warning,
    error,
    step,
    ask,
)

CLINICS_DIR = os.path.dirname(os.path.abspath(__file__))


def list_clinics_with_commands() -> list[dict]:
    """Lista clínicas que tienen commands.yaml."""
    clinics = []
    for item in os.listdir(CLINICS_DIR):
        item_path = os.path.join(CLINICS_DIR, item)
        commands_path = os.path.join(item_path, "commands.yaml")
        config_path = os.path.join(item_path, "config.yaml")

        if os.path.isdir(item_path) and os.path.exists(commands_path):
            # Obtener nombre de la clínica desde config.yaml
            clinic_name = item
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                        clinic_name = config.get("clinic", {}).get("name", item)
                except:
                    pass

            clinics.append({
                "folder": item,
                "name": clinic_name,
                "commands_path": commands_path,
            })

    return sorted(clinics, key=lambda x: x["name"])


def load_commands(commands_path: str) -> list[dict]:
    """Carga los comandos desde commands.yaml."""
    with open(commands_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("commands", [])


def group_commands_by_category(commands: list[dict]) -> dict[str, list[dict]]:
    """Agrupa comandos por categoría."""
    groups = {}
    for cmd in commands:
        category = cmd.get("category", "General")
        if category not in groups:
            groups[category] = []
        groups[category].append(cmd)
    return groups


def run_script(clinic_folder: str, command: dict) -> bool:
    """Ejecuta un script de comando."""
    script_path = command.get("script", "")
    function_name = command.get("function")

    # Caso especial: generar queries
    if script_path == "__generate_queries__":
        from clinics.generate_queries import generate_queries
        generate_queries(clinic_folder)
        return True

    # Construir path completo
    full_path = os.path.join(CLINICS_DIR, clinic_folder, script_path)

    if not os.path.exists(full_path):
        error(f"Script no encontrado: {full_path}")
        return False

    try:
        # Cargar módulo dinámicamente
        spec = importlib.util.spec_from_file_location("command_module", full_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["command_module"] = module
        spec.loader.exec_module(module)

        # Ejecutar función si se especifica, sino ejecutar como script
        if function_name and hasattr(module, function_name):
            func = getattr(module, function_name)
            func()
        else:
            # El script ya se ejecutó al cargarlo si tiene if __name__ == "__main__"
            pass

        return True

    except Exception as e:
        error(f"Error al ejecutar: {e}")
        import traceback
        traceback.print_exc()
        return False


def select_clinic() -> dict | None:
    """Permite seleccionar una clínica."""
    clinics = list_clinics_with_commands()

    if not clinics:
        warning("No hay clínicas con comandos configurados")
        info("Cree un archivo commands.yaml en la carpeta de la clínica")
        return None

    print_subheader("Clínicas disponibles")

    options = []
    for i, clinic in enumerate(clinics, 1):
        options.append({
            "key": str(i),
            "label": clinic["name"],
            "group": "Clínicas",
        })
    options.append({"key": "0", "label": "Volver", "group": "Sistema"})

    print_menu(title="Seleccionar Clínica", options=options)

    while True:
        try:
            choice = ask("Seleccione una clínica")

            if choice == "0":
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(clinics):
                return clinics[idx]

            warning("Número inválido")
        except ValueError:
            warning("Ingrese un número")


def select_command(clinic: dict) -> dict | None:
    """Permite seleccionar un comando de la clínica."""
    commands = load_commands(clinic["commands_path"])

    if not commands:
        warning("No hay comandos configurados para esta clínica")
        return None

    grouped = group_commands_by_category(commands)

    print_subheader(f"Comandos - {clinic['name']}")

    # Construir opciones del menú
    options = []
    command_map = {}
    idx = 1

    for category, cmds in grouped.items():
        for cmd in cmds:
            options.append({
                "key": str(idx),
                "label": cmd["name"],
                "group": category,
            })
            command_map[str(idx)] = cmd
            idx += 1

    options.append({"key": "0", "label": "Volver", "group": "Sistema"})

    print_menu(title="Seleccionar Comando", options=options)

    # Mostrar descripciones
    console.print()
    console.print("[dim]Descripciones:[/dim]")
    for key, cmd in command_map.items():
        desc = cmd.get("description", "Sin descripción")
        console.print(f"  [cyan]{key}[/cyan]. {desc}")

    while True:
        try:
            choice = ask("Seleccione un comando")

            if choice == "0":
                return None

            if choice in command_map:
                return command_map[choice]

            warning("Opción inválida")
        except ValueError:
            warning("Ingrese un número")


def run_clinic_commands():
    """Flujo principal para ejecutar comandos de clínica."""
    while True:
        print_header("COMANDOS DE CLÍNICA")

        # Seleccionar clínica
        clinic = select_clinic()
        if not clinic:
            return

        while True:
            console.print()

            # Seleccionar comando
            command = select_command(clinic)
            if not command:
                break

            # Ejecutar comando
            console.print()
            step(f"Ejecutando: [cyan]{command['name']}[/cyan]")
            console.print()

            try:
                run_script(clinic["folder"], command)
            except KeyboardInterrupt:
                console.print()
                warning("Comando interrumpido")
            except Exception as e:
                error(f"Error: {e}")

            console.print()
            ask("Presiona Enter para continuar")


if __name__ == "__main__":
    run_clinic_commands()
