"""
Sistema de ejecución de comandos por clínica.
Lee commands.yaml de cada clínica y permite ejecutar sus scripts.
"""

import os
import sys
import importlib.util
import time
import glob as glob_module

import yaml
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

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
    confirm,
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


def get_command_status(clinic_folder: str, command: dict) -> str:
    """
    Determina el estado de ejecución de un comando.
    Retorna: 'done', 'pending', 'skip' (para comandos sin tracking)

    Lógica:
    - Scripts de extracción: verifica si existe el JSON en processed/
    - Scripts de inserción: verifica si existe log en logs/
    - Scripts especiales: verificación específica
    - Scripts con skip_status: retorna 'skip'
    """
    # Si el comando tiene skip_status, no mostrar estado
    if command.get("skip_status"):
        return "skip"

    clinic_path = os.path.join(CLINICS_DIR, clinic_folder)
    script_name = command.get("script", "")
    function_name = command.get("function", "")

    # Caso especial: generar queries
    if script_name == "__generate_queries__":
        queries_file = os.path.join(clinic_path, "queries.py")
        return "done" if os.path.exists(queries_file) else "pending"

    # Determinar si es script de extracción o inserción
    is_extract = "extract" in script_name.lower() or "extract" in function_name.lower()
    is_insert = "insert" in script_name.lower() or "insert" in function_name.lower()
    is_create = "create" in script_name.lower() or "create" in function_name.lower()
    is_update = "update" in script_name.lower() or "update" in function_name.lower()

    if is_extract:
        # Para scripts de extracción, verificar si existe el JSON de salida
        # Mapeo de scripts a archivos de salida
        output_files = {
            "extract_professionals": "professionals.json",
            "extract_patients": "patients.json",
            "extract_paciente_ficha": "paciente_ficha.json",
            "extract_cuestionario": "cuestionario.json",
            "extract_consent_templates": "consent_templates.json",
            "extract_consent": "consents.json",
            "extract_consents": "consents.json",
            "extract_catalog": "catalog.json",
            "extract_room": "rooms.json",
            "extract_rooms": "rooms.json",
            "extract_care_plan": "care_plans.json",
            "extract_care_plans": "care_plans.json",
            "extract_schedule": "schedules.json",
            "extract_schedules": "schedules.json",
            "extract_nota": "notas.json",
            "extract_notas": "notas.json",
            "extract_budget": "budgets.json",
            "extract_budgets": "budgets.json",
            "extract_billing": "billing.json",
            "extract_billing_historical": "billing_historical.json",
            "extract_task": "tasks.json",
            "extract_tasks": "tasks.json",
            "extract_cash": "cash.json",
        }

        output_file = output_files.get(function_name)
        if output_file:
            processed_path = os.path.join(clinic_path, "processed", output_file)
            return "done" if os.path.exists(processed_path) else "pending"

    if is_insert or is_create or is_update:
        # Para scripts de inserción/creación/actualización, verificar logs
        # Extraer nombre base del script para buscar logs
        log_patterns = {
            "insert_professionals": "insert_professionals_2*.log",
            "insert_patients": "insert_patients_2*.log",
            "insert_paciente_ficha": "insert_paciente_ficha_2*.log",
            "insert_cuestionario": "insert_cuestionario_2*.log",
            "insert_consent_templates": "insert_consent_templates_2*.log",
            "insert_consent": "insert_consent_2*.log",
            "insert_consents": "insert_consent_2*.log",
            "insert_catalog": "insert_catalog_2*.log",
            "insert_room": "insert_room_2*.log",
            "insert_rooms": "insert_room_2*.log",
            "insert_care_plan": "insert_care_plan_2*.log",
            "insert_care_plans": "insert_care_plan_2*.log",
            "insert_schedule": "insert_schedule_2*.log",
            "insert_schedules": "insert_schedule_2*.log",
            "insert_nota": "insert_nota_2*.log",
            "insert_notas": "insert_nota_2*.log",
            "insert_budget": "insert_budget_2*.log",
            "insert_budgets": "insert_budget_2*.log",
            "insert_billing": "insert_billing_2*.log",
            "insert_billing_historical": "insert_billing_historical_2*.log",
            "insert_task": "insert_task_2*.log",
            "insert_tasks": "insert_task_2*.log",
            "insert_cash": "insert_cash_2*.log",
            "create_migration_user": "create_migration_user_2*.log",
            "update_treatment_sessions": "update_treatment_sessions_2*.log",
        }

        log_pattern = log_patterns.get(function_name)
        if log_pattern:
            logs_path = os.path.join(clinic_path, "logs", log_pattern)
            matching_logs = glob_module.glob(logs_path)
            return "done" if matching_logs else "pending"

        # Caso especial para create_migration_user: verificar si existe el usuario
        if function_name == "create_migration_user":
            # Simplemente verificar si hay algún log o si queries.py existe
            return "pending"  # Mejor dejarlo pendiente para que se pueda verificar

    return "pending"


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


def create_autopilot_table(commands: list, current_idx: int, statuses: dict, clinic_folder: str = None) -> Table:
    """Crea tabla de progreso para el piloto automático."""
    table = Table(
        title="[bold cyan]PILOTO AUTOMÁTICO[/bold cyan]",
        show_header=True,
        header_style="bold white",
        border_style="cyan",
        expand=True
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Comando", style="white")
    table.add_column("Pre-Estado", justify="center", width=12)
    table.add_column("Estado", justify="center", width=12)

    for i, cmd in enumerate(commands):
        num = str(i + 1)
        name = cmd["name"]
        status = statuses.get(i, "pending")

        # Pre-estado (verificación de archivos)
        if clinic_folder:
            pre_status = get_command_status(clinic_folder, cmd)
            if pre_status == "done":
                pre_status_text = "[green]✓[/green]"
            elif pre_status == "skip":
                pre_status_text = "[dim]─[/dim]"
            else:
                pre_status_text = "[dim]○[/dim]"
        else:
            pre_status_text = "[dim]-[/dim]"

        if status == "completed":
            status_text = "[green]✓ Completado[/green]"
            name_style = "[green]" + name + "[/green]"
        elif status == "running":
            status_text = "[yellow]► Ejecutando[/yellow]"
            name_style = "[bold yellow]" + name + "[/bold yellow]"
        elif status == "failed":
            status_text = "[red]✗ Error[/red]"
            name_style = "[red]" + name + "[/red]"
        else:  # pending
            status_text = "[dim]○ Pendiente[/dim]"
            name_style = "[dim]" + name + "[/dim]"

        table.add_row(num, name_style, pre_status_text, status_text)

    return table


def run_autopilot(clinic: dict):
    """Ejecuta todos los comandos secuencialmente con visualización de progreso."""
    all_commands = load_commands(clinic["commands_path"])

    # Filtrar comandos que tienen skip_autopilot
    commands = [cmd for cmd in all_commands if not cmd.get("skip_autopilot")]
    skipped_count = len(all_commands) - len(commands)

    if not commands:
        warning("No hay comandos configurados para esta clínica")
        return

    console.print()
    print_header(f"PILOTO AUTOMÁTICO - {clinic['name']}")
    console.print()
    console.print(f"[cyan]Se ejecutarán {len(commands)} comandos secuencialmente.[/cyan]")
    if skipped_count > 0:
        console.print(f"[dim]({skipped_count} comandos de utilidad excluidos)[/dim]")
    console.print()

    if not confirm("¿Desea continuar?"):
        warning("Piloto automático cancelado")
        return

    statuses = {}  # índice -> "pending" | "running" | "completed" | "failed"
    failed_commands = []

    console.print()

    # Mostrar tabla inicial
    table = create_autopilot_table(commands, -1, statuses, clinic["folder"])
    console.print(table)
    console.print()

    for i, cmd in enumerate(commands):
        # Actualizar estado a running
        statuses[i] = "running"

        # Limpiar y mostrar tabla actualizada
        console.print()
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold yellow]► Ejecutando ({i+1}/{len(commands)}): {cmd['name']}[/bold yellow]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")
        console.print()

        try:
            result = run_script(clinic["folder"], cmd)
            if result:
                statuses[i] = "completed"
                success(f"Completado: {cmd['name']}")
            else:
                statuses[i] = "failed"
                failed_commands.append(cmd['name'])
                error(f"Falló: {cmd['name']}")
        except KeyboardInterrupt:
            statuses[i] = "failed"
            failed_commands.append(cmd['name'])
            console.print()
            warning("Comando interrumpido por el usuario")

            if not confirm("¿Desea continuar con el siguiente comando?"):
                warning("Piloto automático detenido")
                break
        except Exception as e:
            statuses[i] = "failed"
            failed_commands.append(cmd['name'])
            error(f"Error en {cmd['name']}: {e}")

        console.print()

    # Mostrar resumen final
    console.print()
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")
    console.print("[bold cyan]RESUMEN FINAL[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")
    console.print()

    table = create_autopilot_table(commands, -1, statuses, clinic["folder"])
    console.print(table)

    console.print()
    completed = sum(1 for s in statuses.values() if s == "completed")
    failed = sum(1 for s in statuses.values() if s == "failed")
    pending = len(commands) - completed - failed

    console.print(f"[green]✓ Completados: {completed}[/green]")
    console.print(f"[red]✗ Fallidos: {failed}[/red]")
    console.print(f"[dim]○ Pendientes: {pending}[/dim]")

    if failed_commands:
        console.print()
        warning("Comandos con errores:")
        for cmd_name in failed_commands:
            console.print(f"  [red]- {cmd_name}[/red]")


def select_command(clinic: dict) -> dict | None:
    """Permite seleccionar un comando de la clínica."""
    commands = load_commands(clinic["commands_path"])

    if not commands:
        warning("No hay comandos configurados para esta clínica")
        return None

    grouped = group_commands_by_category(commands)

    print_subheader(f"Comandos - {clinic['name']}")

    # Contar ejecutados
    total_done = 0
    total_commands = len(commands)

    # Construir opciones del menú con estado
    options = []
    command_map = {}
    idx = 1

    for category, cmds in grouped.items():
        for cmd in cmds:
            status = get_command_status(clinic["folder"], cmd)
            if status == "done":
                total_done += 1
                status_icon = "[green]✓[/green]"
                label = f"{status_icon} {cmd['name']}"
            elif status == "skip":
                # Comandos de utilidad sin tracking de estado
                status_icon = "[dim]─[/dim]"
                label = f"{status_icon} {cmd['name']}"
                total_commands -= 1  # No contar en el total
            else:
                status_icon = "[dim]○[/dim]"
                label = f"{status_icon} {cmd['name']}"

            options.append({
                "key": str(idx),
                "label": label,
                "group": category,
            })
            command_map[str(idx)] = cmd
            idx += 1

    # Mostrar progreso
    console.print(f"\n[cyan]Progreso: {total_done}/{total_commands} ejecutados[/cyan]")

    # Opción de piloto automático
    options.append({
        "key": "A",
        "label": "[bold yellow]PILOTO AUTOMÁTICO[/bold yellow] (ejecutar todos)",
        "group": "Sistema"
    })
    options.append({"key": "0", "label": "Volver", "group": "Sistema"})

    print_menu(title="Seleccionar Comando", options=options)

    while True:
        try:
            choice = ask("Seleccione un comando").strip().upper()

            if choice == "0":
                return None

            if choice == "A":
                return {"__autopilot__": True}

            if choice in command_map:
                return command_map[choice]

            # Try lowercase
            if choice.lower() in command_map:
                return command_map[choice.lower()]

            warning("Opción inválida")
        except ValueError:
            warning("Ingrese un número o 'A' para piloto automático")


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

            # Verificar si es piloto automático
            if command.get("__autopilot__"):
                run_autopilot(clinic)
                console.print()
                ask("Presiona Enter para continuar")
                continue

            # Ejecutar comando individual
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
