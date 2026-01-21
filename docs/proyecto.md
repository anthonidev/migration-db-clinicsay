# Proyecto de Migración - Clinicsay

## Descripción General

Clinicsay es un software de gestión de clínicas que ha lanzado una nueva versión. Este proyecto se encarga de migrar clínicas desde otros softwares hacia la nueva versión de Clinicsay.

## Características del Proyecto

- **Migración individual**: Cada clínica se migra por separado
- **Fuentes diversas**: CSV, Excel, PostgreSQL, otros
- **Scripts generados por agentes**: Cada clínica tendrá scripts personalizados según su fuente

## Estructura del Proyecto

```
migration-db/
├── app.py                          # Menu principal
├── CONFIGURACION-INICIAL.md        # Guía de setup de clínicas
├── .env                            # DATABASE_URL destino
│
├── schema/
│   ├── extract_schema.py           # Extractor de schema
│   └── clinicsay_schema.sql        # Schema destino (referencia)
│
├── clinicas/                       # Una carpeta por clínica
│   └── {nombre_clinica}/
│       ├── fuente/                 # Archivos origen (CSV, Excel, dumps)
│       ├── scripts/                # Scripts SQL generados
│       │   ├── 01_configuracion.sql
│       │   ├── 02_catalogo.sql
│       │   ├── 03_pacientes.sql
│       │   └── ...
│       ├── logs/                   # Logs de ejecución
│       └── config.json             # Metadata de la migración
│
├── docs/
│   ├── proyecto.md                 # Este archivo
│   └── DOMAIN/                     # Documentación de dominio
│
└── lib/                            # Librerías compartidas
    ├── readers/                    # Lectores de fuentes (CSV, Excel, PG)
    ├── generators/                 # Generadores de SQL
    └── validators/                 # Validadores de datos
```

## Fases de Migración por Clínica

### FASE 1: Configuración Inicial
Setup de la estructura organizacional. Se ejecuta UNA vez por clínica.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 1.1 | organization | Holding/grupo empresarial | Manual/config.json |
| 1.2 | company | Entidad legal (RUC, razón social) | Manual/config.json |
| 1.3 | clinic | Tenant operativo | Manual/config.json |
| 1.4 | site | Sedes físicas | Manual/config.json |
| 1.5 | room | Consultorios/salas | Lista simple |
| 1.6 | equipment | Equipos médicos | Lista simple |

**Output**: `scripts/01_configuracion.sql`

### FASE 2: Usuarios y Accesos
Personal de la clínica con acceso al sistema.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 2.1 | app_user | Usuarios del sistema | Lista de staff |
| 2.2 | clinic_membership | Relación usuario-clínica | Derivado |
| 2.3 | professional | Profesionales de salud | Lista de doctores |
| 2.4 | authorized_signatory | Firmantes autorizados | Manual |
| 2.5 | site_billing_line | Config facturación | Derivado |

**Output**: `scripts/02_usuarios.sql`

### FASE 3: Catálogo de Servicios
Tratamientos y precios que ofrece la clínica.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 3.1 | service | Líneas de negocio | Lista de servicios |
| 3.2 | category | Categorías | Agrupaciones |
| 3.3 | treatment | Tratamientos con precios | Tarifario/lista precios |

**Output**: `scripts/03_catalogo.sql`

### FASE 4: Pacientes
Base de datos de pacientes.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 4.1 | patient | Datos de pacientes | Excel/CSV principal |
| 4.2 | patient_contact | Contactos adicionales | Mismo archivo o separado |

**Output**: `scripts/04_pacientes.sql`

### FASE 5: Historial Clínico (Opcional)
Si la clínica tiene historial digitalizado.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 5.1 | care_plan | Planes de tratamiento | Sistema anterior |
| 5.2 | budget | Presupuestos | Sistema anterior |
| 5.3 | planned_session | Sesiones planificadas | Sistema anterior |

**Output**: `scripts/05_historial.sql`

### FASE 6: Citas (Opcional)
Si se quiere migrar agenda histórica o futura.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 6.1 | schedule_block | Citas agendadas | Agenda anterior |

**Output**: `scripts/06_citas.sql`

### FASE 7: Facturación (Opcional)
Si se quiere migrar historial de pagos.

| Paso | Tabla | Descripción | Fuente típica |
|------|-------|-------------|---------------|
| 7.1 | billing_document | Facturas/boletas | Sistema contable |
| 7.2 | payment | Pagos registrados | Sistema contable |

**Output**: `scripts/07_facturacion.sql`

## Flujo de Trabajo con Agentes

```
1. NUEVA CLÍNICA
   └── Crear carpeta clinicas/{nombre}/
   └── Colocar archivos en fuente/
   └── Crear config.json con metadata básica

2. ANÁLISIS (Agente)
   └── Leer archivos de fuente/
   └── Detectar estructura y columnas
   └── Mapear a schema destino
   └── Generar reporte de mapeo

3. GENERACIÓN (Agente)
   └── Por cada fase aplicable:
       └── Generar script SQL
       └── Validar sintaxis
       └── Guardar en scripts/

4. REVISIÓN (Humano)
   └── Revisar scripts generados
   └── Ajustar mapeos si es necesario
   └── Aprobar ejecución

5. EJECUCIÓN
   └── Ejecutar scripts en orden
   └── Guardar logs
   └── Validar resultados

6. VALIDACIÓN
   └── Ejecutar queries de verificación
   └── Comparar conteos origen vs destino
   └── Generar reporte final
```

## Archivo config.json por Clínica

```json
{
  "nombre": "Clinica Dental Miraflores",
  "pais": "PE",
  "timezone": "America/Lima",
  "moneda": "PEN",
  "fuentes": {
    "pacientes": "fuente/pacientes.xlsx",
    "tratamientos": "fuente/tarifario.csv",
    "doctores": "fuente/staff.xlsx"
  },
  "fases": ["configuracion", "usuarios", "catalogo", "pacientes"],
  "estado": "pendiente",
  "notas": ""
}
```

## Próximos Pasos

1. [ ] Crear estructura de carpetas base
2. [ ] Implementar opción de menú para crear nueva clínica
3. [ ] Implementar lectores de fuentes (CSV, Excel)
4. [ ] Implementar generador de FASE 1 (configuración inicial)
5. [ ] Probar con primera clínica real
