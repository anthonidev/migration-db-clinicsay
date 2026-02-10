# Migration-DB - Sistema de Migración de Clínicas

## Qué es este proyecto

Sistema CLI para migrar datos de clínicas desde sistemas externos hacia la plataforma Clinicsay. Cada migración sigue el flujo: **archivo fuente → JSON normalizado → base de datos PostgreSQL**.

## Stack

- **Python 3.12+** con psycopg2, boto3, PyYAML, Rich
- **PostgreSQL 17** (conexión via `DATABASE_URL` en `.env`)
- **AWS Cognito** para autenticación de usuarios
- **AWS S3** para almacenamiento de archivos (consentimientos, documentos)
- **IDs**: ULID (26 chars, base32, ordenable cronológicamente) via `config.utils.generate_id()`

## Estructura del proyecto

```
app.py                    # Menú principal CLI (punto de entrada)
config/
  database.py             # Conexión PostgreSQL (get_db_config, get_cursor, execute_query)
  storage.py              # Cliente S3 (buckets GENERAL y WORM)
  utils.py                # generate_id() con ULID
ui/
  console.py              # UI con Rich (print_header, info, success, error, ask, confirm)
schema/
  extract_schema.py       # Extrae schema con pg_dump (optimizado para contexto AI)
  clinicsay_schema.sql    # Schema extraído de la BD
docs/
  sync_docs.py            # Sincroniza docs desde PATH_DOCS
  schema.prisma           # Schema de Prisma (limpio, sin comentarios)
  DOMAIN/                 # Documentación de dominio del sistema Clinicsay
clinics/
  init_clinic.py          # Inicializa carpeta de clínica nueva
  generate_queries.py     # Genera queries.py con IDs de la clínica
  validate_and_insert.py  # Valida config.yaml e inserta org/company/clinic/site en BD
  run_commands.py         # Motor de ejecución de comandos (menú + autopilot)
  global_commands/        # Scripts compartidos entre todas las clínicas
    create_migration_user.py
    create_cognito_user.py
    clean_migrated_data.py
    clean_files.py
  {clinic_name}/          # Carpeta por clínica (ej: senses/)
    config.yaml           # Configuración de la clínica
    commands.yaml         # Pipeline de comandos de migración
    queries.py            # IDs y funciones de consulta (auto-generado)
    fuente/               # Archivos CSV/Excel origen
    sources/              # Archivos fuente adicionales
    migrations/           # Scripts de extracción e inserción
    processed/            # JSONs normalizados listos para insertar
    logs/                 # Logs de ejecución por script
    scripts/              # Scripts SQL generados
```

## Flujo de migración

1. **Inicializar clínica**: `init_clinic.py` crea la estructura de carpetas con config.yaml y commands.yaml
2. **Configurar**: Llenar config.yaml con datos de la organización, company, clínica, sites
3. **Validar e insertar**: `validate_and_insert.py` crea las entidades base en la BD
4. **Generar queries**: `generate_queries.py` crea queries.py con los IDs de la clínica
5. **Crear usuario de migración**: Script global que crea app_user + user_clinic de tipo SYSTEM
6. **Migrar datos**: Para cada entidad, el flujo es:
   - **Extraer**: Lee archivo fuente (CSV) → normaliza → genera JSON en `processed/`
   - **Insertar**: Lee JSON de `processed/` → inserta en la BD → genera log en `logs/`
7. **Verificar**: Los comandos muestran estado (done/pending) basado en archivos en processed/ y logs/

## Convenciones de código

### Scripts de migración

Cada entidad tiene un par de scripts en `migrations/`:
- `extract_{entidad}.py` - Función principal: `extract_{entidad}()` - Lee fuente, genera JSON
- `insert_{entidad}.py` - Función principal: `insert_{entidad}()` - Lee JSON, inserta en BD

Los scripts locales importan desde `queries.py` de la clínica:
```python
from queries import CLINIC_ID, SITE_IDS, COMPANY_ID
```

### Scripts globales (`global_commands/`)

Reciben `clinic_folder: str` como primer parámetro y cargan queries dinámicamente:
```python
def load_clinic_queries(clinic_folder: str):
    clinic_dir = os.path.join(CLINICS_DIR, clinic_folder)
    queries_path = os.path.join(clinic_dir, "queries.py")
    spec = importlib.util.spec_from_file_location("queries", queries_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### commands.yaml

```yaml
commands:
  - name: "Nombre del comando"
    category: "1. Categoría"
    script: "migrations/extract_ejemplo.py"   # path relativo a la clínica
    function: "extract_ejemplo"                # función a ejecutar
    description: "Descripción"

  - name: "Comando global"
    category: "1. Configuración"
    type: "global"                             # resuelve desde global_commands/
    script: "create_migration_user.py"
    function: "create_migration_user"
```

Flags opcionales: `skip_autopilot: true`, `skip_status: true`

### Base de datos

- Usar `config.database` para conexiones: `get_cursor()`, `execute_query()`, `execute_insert()`
- Todas las tablas usan `id text NOT NULL` con ULID
- Campos comunes: `record_status`, `record_metadata` (jsonb), `created_at`, `updated_at`
- `record_metadata` incluye `{"source": "migration"}` para datos migrados

### UI

Usar funciones de `ui/` para toda salida al usuario:
- `print_header()`, `print_subheader()` para secciones
- `info()`, `success()`, `warning()`, `error()`, `step()` para mensajes
- `ask()`, `confirm()` para input del usuario

## Contexto de dominio

- `docs/DOMAIN/` contiene la documentación del sistema Clinicsay organizada por módulo
- `docs/schema.prisma` tiene el schema de Prisma del sistema (modelos y relaciones)
- `schema/clinicsay_schema.sql` tiene el schema SQL real de la BD (tablas, tipos, FKs)
- Estos archivos son la referencia para entender la estructura de datos destino

## Orden de dependencias en la BD

Las entidades deben insertarse respetando foreign keys:
1. Organization → Company → Clinic → Site
2. Profesionales, Pacientes (independientes entre sí)
3. Catálogo (Service → Category → Treatment)
4. Salas, Disponibilidad, Comisiones
5. Care Plans, Agenda
6. Notas, Presupuestos, Facturación
7. Tareas, Automatización, Caja

## Idioma

El código, comentarios y UI están en español.
