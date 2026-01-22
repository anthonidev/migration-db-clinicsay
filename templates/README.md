# Templates de Migración

Este directorio contiene templates YAML para facilitar la migración de datos a ClinicSay.

## Estructura de Carpetas

Los templates están organizados por niveles de dependencia según el orden de migración:

```
templates/
├── level0/          # Entidades raíz (sin dependencias)
├── level1/          # Entidades core (dependen de level0)
├── level2/          # Entidades secundarias (dependen de level1)
│   ├── professional.yaml
│   └── patient.yaml
├── level3/          # Entidades terciarias (dependen de level2)
├── level4/          # Aggregate parts (dependen de level2-3)
├── level5/          # Transaccionales (dependen de múltiples niveles)
├── level6/          # Sub-transaccionales (dependen de level5)
└── README.md
```

## Convenciones

| Convención | Descripción |
|------------|-------------|
| `{{nombre}}` | Placeholder - reemplazar con ID real (UUID) |
| `null` | Campo opcional, puede omitirse |
| `# REQUERIDO:` | Campo obligatorio |
| `# DEFAULT:` | Valor por defecto si se omite |
| `# Ej:` | Ejemplo de valor válido |

## Campos Auto-generados

Estos campos son manejados automáticamente y **NO deben incluirse** en los templates:

| Campo | Descripción |
|-------|-------------|
| `created_at` | Timestamp de creación |
| `updated_at` | Timestamp de última actualización |

---

## Level 2: Entidades Secundarias

### professional.yaml

**Descripción:** Profesionales clínicos o terapeutas que atienden pacientes (odontólogos, fisioterapeutas, psicólogos, médicos, etc.).

**Referencia:** [docs/DOMAIN/resources/professional.md](../docs/DOMAIN/resources/professional.md)

#### Dependencias

| Entidad | Campo | Requerido | Notas |
|---------|-------|-----------|-------|
| Clinic | `clinic_id` | Sí | Debe existir en tabla `clinic` |
| Site | `site_ids` | No | Array de UUIDs de sites de la misma clínica |
| User | `user_id` | No | Si el profesional tiene acceso al sistema |
| Company | `legal_entity_id` | No | Para freelancers que facturan independientemente |

#### Campos Requeridos

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `clinic_id` | UUID | ID de la clínica | `"3295df05-262c-..."` |
| `name` | string | Nombre del profesional | `"María"` |
| `last_name` | string | Apellido(s) | `"García López"` |
| `professional_type_id` | string | Tipo de profesional | `"doctor"`, `"physiotherapist"` |

#### Campos con Default

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `employment_type` | enum | `INTERNAL` | Tipo de relación laboral |
| `specialties` | string[] | `[]` | Lista de especialidades |
| `site_ids` | UUID[] | `[]` | Sites donde atiende |
| `scheduling_policy_ids` | UUID[] | `[]` | Políticas de agenda |
| `record_status` | enum | `ACTIVE` | Estado del registro |

#### Campos Opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Se genera automáticamente si es `null` |
| `profile_picture_url` | string | URL de foto de perfil |
| `color` | string | Color hex para agenda (`"#3B82F6"`) |
| `email` | string | Email de contacto |
| `phone` | string | Teléfono (`"+34 612 345 678"`) |
| `legal_entity_id` | UUID | Company para freelancers |
| `user_id` | UUID | Usuario si tiene acceso al sistema |
| `record_metadata` | object | Metadata de ciclo de vida |
| `metadata` | object | Datos adicionales personalizados |

#### Enums

**employment_type:**
```yaml
INTERNAL      # Empleado interno de la clínica (DEFAULT)
FREELANCER    # Profesional independiente (autónomo)
CONTRACTOR    # Contratista externo
VISITING      # Profesional visitante
```

**record_status:**
```yaml
ACTIVE        # Activo y operativo (DEFAULT)
INACTIVE      # Inactivo temporalmente
ARCHIVED      # Archivado (soft delete)
DELETED       # Deprecado, usar ARCHIVED
```

#### Ejemplo Mínimo

```yaml
professionals:
  - clinic_id: "{{clinic_id}}"
    name: "María"
    last_name: "García López"
    professional_type_id: "doctor"
```

#### Ejemplo Completo

```yaml
professionals:
  - clinic_id: "3295df05-262c-4290-80aa-f243dd92b842"
    name: "María"
    last_name: "García López"
    professional_type_id: "doctor"
    employment_type: "INTERNAL"
    specialties:
      - "Medicina General"
      - "Medicina Estética"
    site_ids:
      - "64716f87-e83c-47b1-8d55-7fd8ba3225fd"
    color: "#3B82F6"
    email: "maria.garcia@clinica.es"
    phone: "+34 612 345 678"
    record_status: "ACTIVE"
    metadata:
      license_number: "28/123456"
      certifications:
        - "Máster en Medicina Estética"
```

#### Reglas de Negocio

1. `site_ids` debe contener solo IDs de Sites válidos de la misma Clinic
2. Si `employment_type = FREELANCER` y factura independientemente, debe tener `legal_entity_id`
3. Si `user_id` no es null, el usuario debe existir en `app_user`
4. Professionals con `record_status = ARCHIVED` no aparecen en listados ni pueden asignarse a citas
5. El `color` ayuda a identificar visualmente al profesional en la agenda

#### Orden de Migración

1. Crear Sites si no existen
2. Crear User si el profesional tendrá acceso al sistema
3. Para freelancers, crear Company con `type = FREELANCER_LEGALENTITY`
4. Crear Professional

---

### patient.yaml

**Descripción:** Ficha maestra de pacientes atendidos por la clínica. Es la fuente de verdad para datos de identificación, demográficos, de contacto y estados operativos.

**Referencia:** [docs/DOMAIN/patients/patient.md](../docs/DOMAIN/patients/patient.md)

#### Dependencias

| Entidad | Campo | Requerido | Notas |
|---------|-------|-----------|-------|
| Clinic | `clinic_id` | Sí | Debe existir en tabla `clinic` |
| Site | `site_id` | Sí | Sede donde se registra el paciente |
| User | `created_by_user_id` | No | Usuario que creó el registro |
| User | `updated_by_user_id` | No | Usuario que actualizó el registro |

#### Campos Requeridos

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `clinic_id` | UUID | ID de la clínica | `"3295df05-262c-..."` |
| `site_id` | UUID | ID de la sede | `"64716f87-e83c-..."` |
| `first_name` | string | Nombre del paciente | `"María"` |
| `last_name` | string | Apellido(s) | `"García López"` |
| `id_document_type` | string | Tipo de documento | `"DNI"`, `"NIE"`, `"PASSPORT"` |
| `id_document_number` | string | Número de documento | `"12345678A"` |
| `id_document_number_normalized` | string | Documento normalizado (sin espacios, mayúsculas) | `"12345678A"` |
| `id_document_country` | string | País emisor del documento (ISO) | `"ES"`, `"PE"`, `"MX"` |
| `nationality_country` | string | País de nacionalidad (ISO) | `"ES"`, `"PE"`, `"MX"` |
| `gender_code` | string | Código de género | `"male"`, `"female"`, `"non_binary"` |

#### Campos con Default

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `record_status` | enum | `ACTIVE` | Estado del registro |
| `scheduling_status` | enum | `schedulable` | Estado para agenda |
| `has_accepted_terms` | boolean | `false` | Ha aceptado términos y condiciones |

#### Campos Opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Se genera automáticamente si es `null` |
| `birthday` | date | Fecha de nacimiento (`"1985-03-15"`) |
| `address` | object | Dirección completa (country, region, city, etc.) |
| `phones` | array | Lista de teléfonos (JSONB) |
| `emails` | array | Lista de emails (JSONB) |
| `acquisition_channel` | string | Canal de adquisición (`"web"`, `"referido"`) |
| `administrative_notes` | string | Notas administrativas internas |
| `record_metadata` | object | Metadata del ciclo de vida |
| `accepted_terms_version` | string | Versión de términos aceptados |
| `accepted_terms_at` | timestamp | Fecha de aceptación |
| `accepted_terms_source` | string | Fuente de aceptación |
| `accepted_terms_ip` | string | IP desde donde aceptó |
| `accepted_terms_user_agent` | string | User agent del navegador |
| `created_by_user_id` | UUID | Usuario que creó el registro |
| `updated_by_user_id` | UUID | Usuario que actualizó el registro |

#### Enums

**gender_code:**
```yaml
male            # Masculino
female          # Femenino
non_binary      # No binario
unknown         # Desconocido
not_applicable  # No aplica
```

**id_document_type (España):**
```yaml
DNI       # Documento Nacional de Identidad
NIE       # Número de Identidad de Extranjero
PASSPORT  # Pasaporte
```

**record_status:**
```yaml
ACTIVE    # Activo (DEFAULT)
INACTIVE  # Inactivo
ARCHIVED  # Archivado
DELETED   # Eliminado (soft delete)
```

**scheduling_status:**
```yaml
schedulable  # Puede agendar citas (DEFAULT)
blocked      # Bloqueado para agenda
```

#### Ejemplo Mínimo

```yaml
patients:
  - clinic_id: "{{clinic_id}}"
    site_id: "{{site_id}}"
    first_name: "Carlos"
    last_name: "Martínez Ruiz"
    id_document_type: "DNI"
    id_document_number: "87654321B"
    id_document_number_normalized: "87654321B"
    id_document_country: "ES"
    nationality_country: "ES"
    gender_code: "male"
```

#### Ejemplo Completo

```yaml
patients:
  - clinic_id: "3295df05-262c-4290-80aa-f243dd92b842"
    site_id: "64716f87-e83c-47b1-8d55-7fd8ba3225fd"
    first_name: "María"
    last_name: "García López"
    id_document_type: "DNI"
    id_document_number: "12345678A"
    id_document_number_normalized: "12345678A"
    id_document_country: "ES"
    nationality_country: "ES"
    gender_code: "female"
    birthday: "1985-03-15"
    record_status: "ACTIVE"
    scheduling_status: "schedulable"
    has_accepted_terms: false
    address:
      country: "ES"
      region: "Comunidad Valenciana"
      city: "Valencia"
      district: "Eixample"
      postal_code: "46004"
      street_line1: "Calle Colón 45"
      street_line2: "3º Puerta 2"
    phones:
      - number: "+34 612 345 678"
        type: "mobile"
        is_primary: true
    emails:
      - email: "maria.garcia@email.com"
        is_primary: true
    acquisition_channel: "web"
```

#### Reglas de Negocio

1. `id_document_number_normalized` debe ser único por `clinic_id` (evitar duplicados)
2. `site_id` debe existir y pertenecer a la misma `clinic_id`
3. Si `has_accepted_terms = true`, entonces `accepted_terms_version` y `accepted_terms_at` deben tener valor
4. Para migraciones grandes, usar tablas separadas `patient_phone` y `patient_email` en lugar de campos JSONB
5. Los pacientes con `scheduling_status = blocked` no pueden agendar citas

#### Orden de Migración

1. Crear Clinic (Level 1)
2. Crear Site (Level 2)
3. Crear Patient

---

## Índice de Templates

| Nivel | Template | Descripción | Estado |
|-------|----------|-------------|--------|
| 0 | - | Organization, User, Permission | Pendiente |
| 1 | - | Clinic, Company | Pendiente |
| 2 | `professional.yaml` | Profesionales clínicos | ✅ |
| 2 | `patient.yaml` | Pacientes de la clínica | ✅ |
| 2 | - | Site, Service, etc. | Pendiente |
| 3 | - | Room, Equipment, Treatment | Pendiente |
| 4 | - | PatientPhone, PatientEmail | Pendiente |
| 5 | - | CarePlan, ScheduleBlock | Pendiente |
| 6 | - | PlannedSession, BillingItem | Pendiente |
