import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui import (
    console,
    print_header,
    print_subheader,
    print_panel,
    print_tree,
    print_rule,
    info,
    success,
    warning,
    error,
    ask,
)

CLINICS_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_YAML = '''# ============================================================
# CONFIGURACIÓN INICIAL DE CLÍNICA
# ============================================================
# Complete todos los campos marcados como REQUERIDO
# Los campos opcionales pueden dejarse vacíos o eliminarse
#
# EJEMPLO: Clínica "Salud Total" en Madrid, España
# ============================================================

# ------------------------------------------------------------
# PASO 1: ORGANIZATION (Holding/Grupo Empresarial)
# ------------------------------------------------------------
# Representa la cuenta principal del cliente en Clinicsay.
# Una organización agrupa una o varias clínicas.

organization:
  # REQUERIDO: Nombre comercial de la organización
  name: ""                              # Ej: "Grupo Salud Total"

  # Opcional: Razón social legal
  legal_name: ""                        # Ej: "Grupo Salud Total S.L."

  # REQUERIDO: Código ISO del país principal
  home_country: ""                      # Ej: "ES" (España), "PE" (Perú), "MX" (México)

  # REQUERIDO: Zona horaria principal
  home_timezone: ""                     # Ej: "Europe/Madrid", "America/Lima"

  # Opcional: Tipo de plan SaaS
  plan_type: "professional"             # basic | professional | enterprise

  # Estado inicial (no modificar)
  organization_status: "ONBOARDING"     # ONBOARDING | OPERATIONAL

# ------------------------------------------------------------
# PASO 2: COMPANY (Entidad Legal/Fiscal)
# ------------------------------------------------------------
# Empresa que emite facturas. Mínimo necesitas una de tipo CLINIC_ISSUER.

company:
  # REQUERIDO: Nombre comercial
  name: ""                              # Ej: "Clínica Salud Total"

  # REQUERIDO: Razón social legal
  legal_name: ""                        # Ej: "Clínica Salud Total S.L."

  # REQUERIDO: Tipo de identificador fiscal
  # España: CIF, NIF, NIE
  # Perú: RUC | México: RFC | Colombia: NIT | Chile: RUT
  tax_id_type: ""                       # Ej: "CIF"

  # REQUERIDO: Número de identificador fiscal
  tax_id_number: ""                     # Ej: "B12345678"

  # REQUERIDO: Domicilio fiscal
  address_fiscal: ""                    # Ej: "Calle Gran Vía 45, 28013 Madrid, España"

  # REQUERIDO: País de registro fiscal (código ISO)
  country: ""                           # Ej: "ES"

  # Tipo de empresa (no modificar para clínica emisora)
  type: "CLINIC_ISSUER"

  # --- Representante Legal ---
  # REQUERIDO: Nombre completo del representante legal
  legal_rep_name: ""                    # Ej: "María García López"

  # REQUERIDO: Tipo de documento del representante
  # España: DNI, NIE | Perú: DNI | México: INE, CURP | Internacional: PASSPORT
  legal_rep_id_type: ""                 # Ej: "DNI"

  # REQUERIDO: Número de documento del representante
  legal_rep_id_number: ""               # Ej: "12345678A"

  # REQUERIDO: Cargo del representante
  legal_rep_position: ""                # Ej: "Administrador Único", "Gerente General"

# ------------------------------------------------------------
# PASO 3: CLINIC (Tenant Operativo)
# ------------------------------------------------------------
# La clínica es el tenant operativo principal.
# Cada clínica tiene su propio catálogo, pacientes y agenda.

clinic:
  # REQUERIDO: Nombre de la clínica
  name: ""                              # Ej: "Clínica Salud Total Madrid"

  # Opcional: Descripción
  description: ""                       # Ej: "Centro médico integral especializado"

  # Opcional: Teléfono principal
  phone: ""                             # Ej: "+34 91 123 4567"

  # Opcional: Email de contacto
  email: ""                             # Ej: "info@saludtotal.es"

  # REQUERIDO: País de la clínica (código ISO)
  country: ""                           # Ej: "ES"

  # REQUERIDO: Zona horaria de operación
  timezone: ""                          # Ej: "Europe/Madrid"

  # REQUERIDO: Moneda por defecto
  # EUR (Euro) | PEN (Sol) | USD (Dólar) | MXN (Peso MX) | CLP (Peso CL) | COP (Peso CO)
  default_currency: ""                  # Ej: "EUR"

  # Política de compartición de datos entre sedes
  data_sharing_policy: "ISOLATED"       # ISOLATED | SHARED

  # Estado inicial (no modificar)
  clinic_status: "ONBOARDING"           # ONBOARDING | ACTIVE

# ------------------------------------------------------------
# PASO 4: SITES (Sedes/Sucursales)
# ------------------------------------------------------------
# Sedes físicas donde se atiende a pacientes.
# Una clínica puede tener múltiples sedes.
# Agregue más sedes copiando el bloque completo.

sites:
  - # REQUERIDO: Nombre de la sede
    name: ""                            # Ej: "Sede Centro"

    # Opcional: Teléfono de la sede
    phone: ""                           # Ej: "+34 91 123 4567"

    # Opcional: Email de la sede
    email: ""                           # Ej: "centro@saludtotal.es"

    # REQUERIDO: Zona horaria de la sede
    timezone: ""                        # Ej: "Europe/Madrid"

    # Estado inicial (no modificar)
    site_status: "ACTIVE"

    # --- Dirección ---
    address:
      # REQUERIDO: País (código ISO)
      country: ""                       # Ej: "ES"

      # REQUERIDO: Región/Comunidad/Estado
      region: ""                        # Ej: "Comunidad de Madrid"

      # REQUERIDO: Ciudad
      city: ""                          # Ej: "Madrid"

      # Opcional: Distrito/Barrio
      district: ""                      # Ej: "Centro"

      # Opcional: Código postal
      postal_code: ""                   # Ej: "28013"

      # REQUERIDO: Calle y número
      street_line1: ""                  # Ej: "Calle Gran Vía 45"

      # Opcional: Piso, oficina, referencia
      street_line2: ""                  # Ej: "2º Planta, Oficina B"

    # --- Líneas de Facturación ---
    # Define qué empresa emite facturas para esta sede.
    # Por defecto usa la Company principal del config.
    # Al menos una línea debe tener is_default: true
    billing_lines:
      - name: "Línea Principal"         # Nombre de la línea
        description: ""                 # Descripción opcional
        is_default: true                # ¿Es la línea por defecto?

# ------------------------------------------------------------
# PASO 5: PAYMENT METHODS (Métodos de Pago)
# ------------------------------------------------------------
# Métodos de pago disponibles para los pacientes.
# Configura los métodos que acepta la clínica.
# Tipos: CASH, CARD_PRESENT, CARD_NOT_PRESENT, BANK_TRANSFER,
#        WALLET, CHECK, INSURANCE, CORPORATE, FINANCING,
#        GIFT_CARD, INTERNAL_BALANCE, OTHER

payment_methods:
  - # Efectivo
    name: "Efectivo"
    payment_method_type: "CASH"
    requires_reference: false         # ¿Requiere número de referencia?
    allows_refunds: true              # ¿Permite devoluciones?
    is_online_method: false           # ¿Es método de pago online?
    sort_order: 1                     # Orden en la UI

  - # Tarjeta (presencial - TPV)
    name: "Tarjeta"
    payment_method_type: "CARD_PRESENT"
    requires_reference: false
    allows_refunds: true
    is_online_method: false
    sort_order: 2

  - # Transferencia bancaria
    name: "Transferencia"
    payment_method_type: "BANK_TRANSFER"
    requires_reference: true          # Requiere número de referencia
    allows_refunds: true
    is_online_method: false
    sort_order: 3

# ============================================================
# EJEMPLO COMPLETO: CLÍNICA "SALUD TOTAL" EN ESPAÑA
# ============================================================
#
# organization:
#   name: "Grupo Salud Total"
#   legal_name: "Grupo Salud Total S.L."
#   home_country: "ES"
#   home_timezone: "Europe/Madrid"
#   plan_type: "professional"
#   organization_status: "ONBOARDING"
#
# company:
#   name: "Clínica Salud Total"
#   legal_name: "Clínica Salud Total S.L."
#   tax_id_type: "CIF"
#   tax_id_number: "B12345678"
#   address_fiscal: "Calle Gran Vía 45, 28013 Madrid, España"
#   country: "ES"
#   type: "CLINIC_ISSUER"
#   legal_rep_name: "María García López"
#   legal_rep_id_type: "DNI"
#   legal_rep_id_number: "12345678A"
#   legal_rep_position: "Administrador Único"
#
# clinic:
#   name: "Clínica Salud Total Madrid"
#   description: "Centro médico integral especializado en atención primaria"
#   phone: "+34 91 123 4567"
#   email: "info@saludtotal.es"
#   country: "ES"
#   timezone: "Europe/Madrid"
#   default_currency: "EUR"
#   data_sharing_policy: "ISOLATED"
#   clinic_status: "ONBOARDING"
#
# sites:
#   - name: "Sede Centro"
#     phone: "+34 91 123 4567"
#     email: "centro@saludtotal.es"
#     timezone: "Europe/Madrid"
#     site_status: "ACTIVE"
#     address:
#       country: "ES"
#       region: "Comunidad de Madrid"
#       city: "Madrid"
#       district: "Centro"
#       postal_code: "28013"
#       street_line1: "Calle Gran Vía 45"
#       street_line2: "2º Planta"
#     billing_lines:
#       - name: "Línea Principal"
#         is_default: true
#
#   - name: "Sede Norte"
#     phone: "+34 91 987 6543"
#     email: "norte@saludtotal.es"
#     timezone: "Europe/Madrid"
#     site_status: "ACTIVE"
#     address:
#       country: "ES"
#       region: "Comunidad de Madrid"
#       city: "Madrid"
#       district: "Chamartín"
#       postal_code: "28036"
#       street_line1: "Paseo de la Castellana 150"
#       street_line2: "Bajo A"
#     billing_lines:
#       - name: "Línea Principal"
#         is_default: true
#
# payment_methods:
#   - name: "Efectivo"
#     payment_method_type: "CASH"
#     sort_order: 1
#   - name: "Tarjeta"
#     payment_method_type: "CARD_PRESENT"
#     sort_order: 2
#   - name: "Transferencia"
#     payment_method_type: "BANK_TRANSFER"
#     requires_reference: true
#     sort_order: 3
# ============================================================
'''


def validate_clinic_name(name: str) -> bool:
    """Valida que el nombre sea minúsculas y sin espacios."""
    pattern = r'^[a-z0-9_-]+$'
    return bool(re.match(pattern, name))


def create_clinic_folder(name: str) -> str:
    """Crea la carpeta de la clínica con el archivo de configuración."""
    clinic_path = os.path.join(CLINICS_DIR, name)

    if os.path.exists(clinic_path):
        raise ValueError(f"La clínica '{name}' ya existe")

    # Crear estructura de carpetas
    os.makedirs(clinic_path)
    os.makedirs(os.path.join(clinic_path, "fuente"))
    os.makedirs(os.path.join(clinic_path, "scripts"))
    os.makedirs(os.path.join(clinic_path, "logs"))

    # Crear archivo de configuración
    config_path = os.path.join(clinic_path, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE_YAML)

    return config_path


def init_clinic():
    """Flujo principal de inicialización de clínica."""
    print_header("INICIALIZAR NUEVA CLÍNICA")

    print_subheader("Reglas para el nombre")

    console.print("  [cyan]•[/cyan] Solo minúsculas (a-z)")
    console.print("  [cyan]•[/cyan] Solo números (0-9)")
    console.print("  [cyan]•[/cyan] Guiones (-) y guiones bajos (_) permitidos")
    console.print("  [cyan]•[/cyan] Sin espacios ni caracteres especiales")
    console.print()
    console.print("  [dim]Ejemplos válidos: saludtotal, clinica_dental, mi-clinica-123[/dim]")
    console.print()

    while True:
        name = ask("Nombre de la clínica").strip().lower()

        if not name:
            warning("El nombre no puede estar vacío")
            continue

        if not validate_clinic_name(name):
            warning("Nombre inválido. Use solo minúsculas, números, - o _")
            continue

        try:
            config_path = create_clinic_folder(name)
            break
        except ValueError as e:
            error(str(e))
            continue

    # Mostrar éxito
    console.print()
    success("Clínica creada exitosamente")

    # Mostrar estructura creada
    print_subheader("Estructura creada")

    structure = {
        "config.yaml": "[yellow]← Complete este archivo[/yellow]",
        "fuente/": "Archivos de datos origen",
        "scripts/": "Scripts SQL generados",
        "logs/": "Logs de ejecución",
    }

    print_tree(f"clinics/{name}", structure)

    # Siguientes pasos
    print_subheader("Siguientes pasos")

    console.print(f"  [cyan]1.[/cyan] Abra el archivo: [green]clinics/{name}/config.yaml[/green]")
    console.print("  [cyan]2.[/cyan] Complete todos los campos marcados como [yellow]REQUERIDO[/yellow]")
    console.print("  [cyan]3.[/cyan] Use el ejemplo de 'saludtotal' como guía")
    console.print("  [cyan]4.[/cyan] Ejecute la opción [green]Validar e insertar configuración[/green]")
    console.print()

    return name


if __name__ == "__main__":
    init_clinic()
