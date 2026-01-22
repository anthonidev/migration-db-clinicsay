# Configuración Inicial de Clínica - Guía de Setup

Esta guía detalla **paso por paso** qué tablas de la base de datos deben llenarse para configurar una nueva clínica, desde cero hasta estar lista para operar.

## Prerequisitos

- Base de datos Postgres desplegada y accesible
- Schema de base de datos creado con todas las tablas necesarias
- Datos de referencia/catálogos del sistema cargados

---

## Paso 1: Organization (Holding/Grupo Empresarial)

**Tabla:** `organization`

**Descripción:** Representa la cuenta principal del cliente. Una organización agrupa una o varias clínicas bajo el mismo holding o grupo empresarial.

**Campos obligatorios:**

| Campo                 | Tipo      | Descripción                         | Ejemplo                |
| --------------------- | --------- | ----------------------------------- | ---------------------- |
| `id`                  | UUID      | Identificador único                 | auto-generado          |
| `name`                | String    | Nombre comercial de la organización | "Grupo Dental Sonrisa" |
| `organization_status` | String    | Estado de la organización           | "ACTIVE", "ONBOARDING" |
| `record_status`       | String    | Estado del registro                 | "ACTIVE"               |
| `created_at`          | Timestamp | Fecha de creación                   | timestamp actual       |
| `updated_at`          | Timestamp | Fecha de última actualización       | timestamp actual       |

**Campos opcionales:**

| Campo             | Tipo   | Descripción                            | Ejemplo                               |
| ----------------- | ------ | -------------------------------------- | ------------------------------------- |
| `legal_name`      | String | Razón social legal                     | "Grupo Dental Sonrisa S.A.C."         |
| `home_country`    | String | Código ISO país principal              | "PE", "MX", "CL", "CO"                |
| `home_timezone`   | String | Zona horaria principal                 | "America/Lima", "America/Mexico_City" |
| `plan_type`       | String | Tipo de plan SaaS contratado           | "basic", "professional", "enterprise" |
| `owner_user_id`   | UUID   | ID del usuario propietario             | referencia a `app_user.id`            |
| `metadata`        | JSON   | Metadata adicional                     | `{}`                                  |
| `record_metadata` | JSON   | Metadata de ciclo de vida del registro | `{}`                                  |

**Valores válidos para `organization_status`:**

- `ONBOARDING` - En proceso de configuración inicial
- `ACTIVE` - Organización activa y operativa
- `SUSPENDED` - Suspendida temporalmente
- `TERMINATED` - Contrato terminado

**Resultado:** Se crea la entidad legal máxima que agrupa todas las clínicas del cliente.

---

## Paso 2: Company (Entidades Legales/Fiscales)

**Tabla:** `company`

**Descripción:** Empresas que emiten facturas, pagan servicios, o son partners. Mínimo necesitas una de tipo `CLINIC_ISSUER` (emisor de facturas).

**Datos requeridos:**

```sql
INSERT INTO company (
  id,                          -- UUID generado
  organization_id,             -- UUID de la organization creada en Paso 1
  name,                        -- "Clínica Dental Miraflores"
  legal_name,                  -- "Clínica Dental Miraflores S.A.C."
  tax_id_type,                 -- "RUT", "NIT", "RFC", "DNI", etc.
  tax_id_number,               -- "20123456789"
  address_fiscal,              -- "Av. Larco 345, Miraflores, Lima"
  country,                     -- "PE"
  type,                        -- "CLINIC_ISSUER" (emisor de facturas)
  legal_rep_name,              -- "Juan Pérez García"
  legal_rep_id_type,           -- "DNI", "CE", "PASSPORT"
  legal_rep_id_number,         -- "12345678"
  legal_rep_position,          -- "Gerente General"
  record_status,               -- "ACTIVE" (default)
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<organization_id>',  -- Reemplazar con ID del Paso 1
  'Clínica Dental Miraflores',
  'Clínica Dental Miraflores S.A.C.',
  'RUT',
  '20123456789',
  'Av. Larco 345, Miraflores, Lima, Perú',
  'PE',
  'CLINIC_ISSUER',
  'Juan Pérez García',
  'DNI',
  '12345678',
  'Gerente General',
  'ACTIVE',
  NOW(),
  NOW()
);
```

**Tipos de Company disponibles:**

- `CLINIC_ISSUER` - Empresa que emite facturas (OBLIGATORIO)
- `CORPORATE_PAYER` - Empresa que paga por empleados
- `INSURANCE_PAYER` - Aseguradora que cubre tratamientos
- `LAB_PARTNER` - Laboratorio asociado
- `FRANCHISE_PARTNER` - Franquicia
- `OTHER` - Otras entidades

**Resultado:** Se crea la entidad legal que emitirá facturas/recibos a pacientes.

---

## Paso 3: Clinic (Tenant Operativo)

**Tabla:** `clinic`

**Descripción:** La clínica es el tenant operativo principal. Cada clínica tiene su propio catálogo de servicios, base de pacientes, agenda y facturación independiente.

**Campos obligatorios:**

| Campo                 | Tipo      | Descripción                       | Ejemplo                        |
| --------------------- | --------- | --------------------------------- | ------------------------------ |
| `id`                  | UUID      | Identificador único               | auto-generado                  |
| `organization_id`     | UUID      | ID de la organización padre       | referencia a `organization.id` |
| `name`                | String    | Nombre de la clínica              | "Clínica Dental Miraflores"    |
| `data_sharing_policy` | String    | Política de compartición de datos | "ISOLATED" o "SHARED"          |
| `clinic_status`       | String    | Estado operativo de la clínica    | "ACTIVE"                       |
| `record_status`       | String    | Estado del registro               | "ACTIVE"                       |
| `created_at`          | Timestamp | Fecha de creación                 | timestamp actual               |
| `updated_at`          | Timestamp | Fecha de última actualización     | timestamp actual               |

**Campos opcionales:**

| Campo                       | Tipo   | Descripción                 | Ejemplo                                         |
| --------------------------- | ------ | --------------------------- | ----------------------------------------------- |
| `description`               | String | Descripción de la clínica   | "Clínica especializada en odontología integral" |
| `phone`                     | String | Teléfono principal          | "+51999888777"                                  |
| `email`                     | String | Email de contacto           | "contacto@clinicamiraflores.com"                |
| `country`                   | String | Código ISO del país         | "PE", "MX", "CL", "CO"                          |
| `timezone`                  | String | Zona horaria de operación   | "America/Lima", "America/Mexico_City"           |
| `default_currency`          | String | Moneda por defecto          | "PEN", "USD", "MXN", "CLP", "COP"               |
| `default_issuer_company_id` | UUID   | Empresa emisora por defecto | referencia a `company.id` (tipo CLINIC_ISSUER)  |
| `metadata`                  | JSON   | Metadata adicional          | `{}`                                            |
| `record_metadata`           | JSON   | Metadata de ciclo de vida   | `{}`                                            |

**Valores válidos para `clinic_status`:**

- `ACTIVE` - Clínica operativa
- `SUSPENDED` - Suspendida temporalmente
- `TERMINATED` - Contrato terminado

**Valores válidos para `data_sharing_policy`:**

- `ISOLATED` - Datos completamente aislados entre clínicas (recomendado)
- `SHARED` - Datos compartidos entre clínicas de la misma organización

**Valores válidos para `default_currency`:**

- `PEN` - Sol Peruano
- `USD` - Dólar Estadounidense
- `MXN` - Peso Mexicano
- `CLP` - Peso Chileno
- `COP` - Peso Colombiano
- `ARS` - Peso Argentino
- `EUR` - Euro

**Resultado:** Se crea la clínica operativa lista para tener sedes, recursos y pacientes.

---

## Paso 4: Site (Sedes/Sucursales)

**Tabla:** `site`

**Descripción:** Sedes físicas donde se atiende a pacientes. Una clínica puede tener múltiples sedes operando simultáneamente.

**Campos obligatorios:**

| Campo           | Tipo      | Descripción                     | Ejemplo                               |
| --------------- | --------- | ------------------------------- | ------------------------------------- |
| `id`            | UUID      | Identificador único             | auto-generado                         |
| `clinic_id`     | UUID      | ID de la clínica padre          | referencia a `clinic.id`              |
| `name`          | String    | Nombre de la sede               | "Sede Miraflores", "Sede San Isidro"  |
| `address`       | JSON      | Dirección estructurada completa | ver estructura abajo                  |
| `timezone`      | String    | Zona horaria de la sede         | "America/Lima", "America/Mexico_City" |
| `site_status`   | String    | Estado operativo de la sede     | "ACTIVE"                              |
| `record_status` | String    | Estado del registro             | "ACTIVE"                              |
| `created_at`    | Timestamp | Fecha de creación               | timestamp actual                      |
| `updated_at`    | Timestamp | Fecha de última actualización   | timestamp actual                      |

**Campos opcionales:**

| Campo             | Tipo   | Descripción                  | Ejemplo                  |
| ----------------- | ------ | ---------------------------- | ------------------------ |
| `phone`           | String | Teléfono de la sede          | "+51999888777"           |
| `email`           | String | Email de contacto de la sede | "miraflores@clinica.com" |
| `metadata`        | JSON   | Metadata adicional           | `{}`                     |
| `record_metadata` | JSON   | Metadata de ciclo de vida    | `{}`                     |

**Estructura del campo `address` (JSON):**

```json
{
  "country": "PE", // Código ISO país
  "region": "Lima", // Departamento/Estado/Provincia
  "city": "Lima", // Ciudad
  "postalCode": "15074", // Código postal
  "street": "Av. Larco", // Nombre de calle/avenida
  "streetNumber": "345", // Número de puerta
  "floor": "2do piso", // Piso (opcional)
  "apartment": "", // Departamento/Oficina (opcional)
  "reference": "Frente al parque Kennedy" // Referencia (opcional)
}
```

**Valores válidos para `site_status`:**

- `ACTIVE` - Sede operativa y atendiendo
- `INACTIVE` - Sede cerrada temporalmente
- `UNDER_CONSTRUCTION` - Sede en construcción/remodelación
- `CLOSED` - Sede cerrada permanentemente

**Notas importantes:**

- Cada sede puede tener su propia zona horaria (útil para clínicas con sedes en diferentes regiones)
- La dirección estructurada en JSON permite búsquedas y validaciones consistentes
- **Crear un registro por cada sede física** que la clínica opera

**Resultado:** Se crean las ubicaciones físicas donde operará la clínica.

---

## Paso 5: Room (Salas/Consultorios)

**Tabla:** `room`

**Descripción:** Salas, boxes o consultorios disponibles en cada sede.

**Datos requeridos:**

```sql
INSERT INTO room (
  id,                          -- UUID generado
  site_id,                     -- UUID del site (Paso 4)
  clinic_id,                   -- UUID de la clinic (Paso 3)
  name,                        -- "Consultorio 1"
  room_type,                   -- "CONSULTATION", "PROCEDURE", "SURGERY", etc.
  capacity,                    -- 1, 2, 3... (personas que caben)
  room_status,                 -- "ACTIVE" (default)
  record_status,               -- "ACTIVE" (default)
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<site_id>',
  '<clinic_id>',
  'Consultorio 1',
  'CONSULTATION',
  1,
  'ACTIVE',
  'ACTIVE',
  NOW(),
  NOW()
);
```

**Tipos de Room disponibles:**

- `CONSULTATION` - Consultorio general
- `PROCEDURE` - Sala de procedimientos
- `SURGERY` - Quirófano
- `TREATMENT` - Sala de tratamiento
- `RECOVERY` - Sala de recuperación
- `IMAGING` - Sala de imágenes/rayos
- `OTHER` - Otros

**Repetir para cada sala/box de la sede**.

**Resultado:** Se registran los espacios físicos disponibles para atender.

---

## Paso 6: Equipment (Equipamiento)

**Tabla:** `equipment`

**Descripción:** Equipos médicos/odontológicos disponibles en cada sede.

**Datos requeridos:**

```sql
INSERT INTO equipment (
  id,                          -- UUID generado
  site_id,                     -- UUID del site (Paso 4)
  clinic_id,                   -- UUID de la clinic (Paso 3)
  name,                        -- "Rayos X Digital"
  equipment_type,              -- "IMAGING", "LASER", "ULTRASOUND", etc.
  model,                       -- "Planmeca ProMax 3D" (opcional)
  manufacturer,                -- "Planmeca" (opcional)
  serial_number,               -- "PM123456" (opcional)
  equipment_status,            -- "ACTIVE" (default)
  record_status,               -- "ACTIVE" (default)
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<site_id>',
  '<clinic_id>',
  'Rayos X Digital',
  'IMAGING',
  'Planmeca ProMax 3D',
  'Planmeca',
  'PM123456',
  'ACTIVE',
  'ACTIVE',
  NOW(),
  NOW()
);
```

**Tipos de Equipment disponibles:**

- `IMAGING` - Equipos de imagen (RX, TAC, etc.)
- `LASER` - Láser CO2, diodo, etc.
- `ULTRASOUND` - Ultrasonido
- `DENTAL_UNIT` - Unidad dental
- `AUTOCLAVE` - Autoclave/esterilizador
- `OTHER` - Otros equipos

**Repetir para cada equipo relevante**.

**Resultado:** Se registran los equipos disponibles para procedimientos especializados.

---

## Paso 7: User (Usuarios del Sistema)

**Tabla:** `app_user`

**Descripción:** Usuarios que tendrán acceso al sistema. El primer usuario debe ser un `clinic_owner`.

**IMPORTANTE:** Los usuarios se crean típicamente vía Cognito + API. Este SQL es solo referencia.

**Estructura esperada:**

```sql
INSERT INTO app_user (
  id,                          -- UUID generado
  cognito_sub,                 -- Sub de Cognito (único)
  email,                       -- "admin@clinicamiraflores.com"
  email_verified,              -- true/false
  name,                        -- "María"
  last_name,                   -- "González"
  user_type,                   -- "clinic_staff"
  role_base,                   -- "clinic_owner", "clinic_admin", etc.
  record_status,               -- "ACTIVE" (default)
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<cognito_sub>',  -- Proviene de AWS Cognito
  'admin@clinicamiraflores.com',
  true,
  'María',
  'González',
  'clinic_staff',
  'clinic_owner',
  'ACTIVE',
  NOW(),
  NOW()
);
```

**Roles disponibles:**

- `platform_root` - Acceso total a la plataforma
- `clinic_owner` - Dueño de la clínica (acceso total a su clínica)
- `clinic_admin` - Administrador de clínica
- `clinic_professional` - Profesional de salud
- `clinic_secretary` - Recepción/Agenda
- `clinic_billing` - Facturación
- `clinic_readonly` - Solo lectura

**Resultado:** Se crea el primer usuario administrador de la clínica.

---

## Paso 8: ClinicMembership (Relación Usuario-Clínica)

**Tabla:** `clinic_membership`

**Descripción:** Vincula usuarios con clínicas y define su rol en cada clínica.

**Datos requeridos:**

```sql
INSERT INTO clinic_membership (
  id,                          -- UUID generado
  clinic_id,                   -- UUID de la clinic (Paso 3)
  user_id,                     -- UUID del user (Paso 7)
  role,                        -- "owner", "admin", "professional", etc.
  clinic_membership_status,    -- "ACTIVE" (default)
  record_status,               -- "ACTIVE" (default)
  joined_at,                   -- NOW()
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<clinic_id>',
  '<user_id>',
  'owner',
  'ACTIVE',
  'ACTIVE',
  NOW(),
  NOW(),
  NOW()
);
```

**Roles de ClinicMembership:**

- `owner` - Propietario
- `admin` - Administrador
- `professional` - Profesional
- `secretary` - Secretaria/Recepción
- `billing` - Facturación
- `readonly` - Solo lectura

**Repetir para cada usuario adicional**.

**Resultado:** Se vincula el usuario a la clínica con su rol específico.

---

## Paso 9: Professional (Profesionales de Salud)

**Tabla:** `professional`

**Descripción:** Profesionales de salud que atienden pacientes (médicos, odontólogos, enfermeras, fisioterapeutas, psicólogos, etc.).

**Campos obligatorios:**

| Campo                 | Tipo        | Descripción                     | Ejemplo                  |
| --------------------- | ----------- | ------------------------------- | ------------------------ |
| `id`                  | UUID        | Identificador único             | auto-generado            |
| `clinic_id`           | UUID        | ID de la clínica                | referencia a `clinic.id` |
| `name`                | String      | Nombre completo del profesional | "Dr. Carlos Ramírez"     |
| `id_type`             | String      | Tipo de documento de identidad  | "DNI", "CE", "PASSPORT"  |
| `id_number`           | String      | Número de documento             | "87654321"               |
| `site_ids`            | Array[UUID] | IDs de sedes donde trabaja      | `["uuid1", "uuid2"]`     |
| `professional_status` | String      | Estado del profesional          | "ACTIVE"                 |
| `record_status`       | String      | Estado del registro             | "ACTIVE"                 |
| `created_at`          | Timestamp   | Fecha de creación               | timestamp actual         |
| `updated_at`          | Timestamp   | Fecha de última actualización   | timestamp actual         |

**Campos opcionales:**

| Campo             | Tipo   | Descripción                                              | Ejemplo                                              |
| ----------------- | ------ | -------------------------------------------------------- | ---------------------------------------------------- |
| `user_id`         | UUID   | ID del usuario si tiene acceso al sistema                | referencia a `app_user.id` (null si no tiene acceso) |
| `email`           | String | Email profesional                                        | "carlos.ramirez@clinica.com"                         |
| `phone`           | String | Teléfono de contacto                                     | "+51988777666"                                       |
| `specialty`       | String | Especialidad principal                                   | "Endodoncia", "Pediatría", "Fisioterapia"            |
| `license_number`  | String | Número de licencia/colegiatura                           | "COP123456", "CMP12345"                              |
| `biography`       | Text   | Biografía del profesional                                | texto largo                                          |
| `metadata`        | JSON   | Metadata adicional (sub-especialidades, certificaciones) | `{"certifications": ["ISO9001"]}`                    |
| `record_metadata` | JSON   | Metadata de ciclo de vida                                | `{}`                                                 |

**Valores válidos para `id_type`:**

- `DNI` - Documento Nacional de Identidad
- `CE` - Carné de Extranjería
- `PASSPORT` - Pasaporte
- `RUT` - RUT (Chile)
- `CC` - Cédula de Ciudadanía (Colombia)
- `CURP` - CURP (México)

**Valores válidos para `professional_status`:**

- `ACTIVE` - Activo y disponible para atender
- `INACTIVE` - Inactivo temporalmente
- `ON_LEAVE` - De licencia/vacaciones
- `TERMINATED` - Ya no trabaja en la clínica

**Notas importantes:**

- El campo `site_ids` es un **array de UUIDs** que indica en qué sedes trabaja el profesional
- Un profesional puede trabajar en múltiples sedes simultáneamente
- `user_id` puede ser `null` si el profesional no requiere acceso al sistema (ej: profesionales externos)
- Si `user_id` no es null, debe existir un `clinic_membership` correspondiente
- **Crear un registro por cada profesional** que atienda en la clínica

**Resultado:** Se registran los profesionales que podrán ser asignados a citas en la agenda.

---

## Paso 10: AuthorizedSignatory (Firmantes Autorizados)

**Tabla:** `authorized_signatory`

**Descripción:** Personas autorizadas para firmar documentos legales (director médico, representante legal).

**Datos requeridos:**

```sql
INSERT INTO authorized_signatory (
  id,                          -- UUID generado
  clinic_id,                   -- UUID de la clinic (Paso 3)
  name,                        -- "Dr. Juan Pérez García"
  id_type,                     -- "DNI", "CE", "PASSPORT"
  id_number,                   -- "12345678"
  position,                    -- "Director Médico"
  signatory_type,              -- "MEDICAL_DIRECTOR", "LEGAL_REP", etc.
  authorized_signatory_status, -- "ACTIVE" (default)
  record_status,               -- "ACTIVE" (default)
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  '<clinic_id>',
  'Dr. Juan Pérez García',
  'DNI',
  '12345678',
  'Director Médico',
  'MEDICAL_DIRECTOR',
  'ACTIVE',
  'ACTIVE',
  NOW(),
  NOW()
);
```

**Tipos de Signatory:**

- `MEDICAL_DIRECTOR` - Director médico
- `LEGAL_REPRESENTATIVE` - Representante legal
- `CLINICAL_MANAGER` - Gerente clínico
- `OTHER` - Otros autorizados

**Resultado:** Se registran los firmantes para documentos de consentimiento, recetas, etc.

---

## Paso 11: SiteBillingLine (Configuración de Facturación por Sede)

**Tabla:** `site_billing_line`

**Descripción:** Define qué empresa emite facturas/recibos para cada sede. Permite que diferentes sedes de una misma clínica emitan bajo diferentes razones sociales.

**Campos obligatorios:**

| Campo               | Tipo      | Descripción                               | Ejemplo                                        |
| ------------------- | --------- | ----------------------------------------- | ---------------------------------------------- |
| `id`                | UUID      | Identificador único                       | auto-generado                                  |
| `site_id`           | UUID      | ID de la sede                             | referencia a `site.id`                         |
| `issuer_company_id` | UUID      | ID de la empresa emisora                  | referencia a `company.id` (tipo CLINIC_ISSUER) |
| `is_default`        | Boolean   | ¿Es el emisor por defecto para esta sede? | true/false                                     |
| `record_status`     | String    | Estado del registro                       | "ACTIVE"                                       |
| `created_at`        | Timestamp | Fecha de creación                         | timestamp actual                               |
| `updated_at`        | Timestamp | Fecha de última actualización             | timestamp actual                               |

**Campos opcionales:**

| Campo             | Tipo | Descripción               | Ejemplo |
| ----------------- | ---- | ------------------------- | ------- |
| `metadata`        | JSON | Metadata adicional        | `{}`    |
| `record_metadata` | JSON | Metadata de ciclo de vida | `{}`    |

**Notas importantes:**

- Cada sede debe tener **al menos una** `site_billing_line` con `is_default = true`
- Puede haber múltiples billing lines por sede (diferentes empresas emisoras para diferentes casos)
- Solo una puede tener `is_default = true` por sede
- Útil cuando:
  - Una sede opera bajo razón social diferente (franquicia, alianza)
  - Diferentes tipos de facturación requieren diferentes emisores
  - Compliance fiscal exige emisores específicos por jurisdicción
- **Crear un registro por cada combinación sede-emisor**

**Casos de uso típicos:**

| Caso                                 | Configuración                                  |
| ------------------------------------ | ---------------------------------------------- |
| Sede única                           | 1 billing line con default = true              |
| Múltiples sedes, mismo emisor        | 1 billing line por sede, mismo company_id      |
| Múltiples sedes, diferentes emisores | 1 billing line por sede, diferentes company_id |
| Sede con múltiples emisores          | 2+ billing lines, solo 1 con default = true    |

**Resultado:** Se configura qué empresa emite facturas en cada sede.

---

---

## Resumen de Orden de Ejecución

El orden de inserción es crítico debido a las relaciones de clave foránea (foreign keys):

```
1. organization           → Holding/grupo empresarial
   ↓
2. company                → Entidad legal emisora (tipo CLINIC_ISSUER)
   ↓
3. clinic                 → Tenant operativo (requiere organization + company)
   ↓
4. site                   → Sedes físicas (requiere clinic)
   ↓
5. room                   → Consultorios/salas (requiere site + clinic)
   ↓
6. equipment              → Equipos médicos (requiere site + clinic)
   ↓
7. app_user               → Usuarios del sistema (integración con auth)
   ↓
8. clinic_membership      → Relación usuario-clínica (requiere user + clinic)
   ↓
9. professional           → Profesionales de salud (requiere clinic, opcional user, requiere site_ids)
   ↓
10. authorized_signatory   → Firmantes autorizados (requiere clinic)
    ↓
11. site_billing_line      → Configuración de facturación (requiere site + company)
```

**Dependencias clave:**

- `clinic` depende de `organization` + `company`
- `site` depende de `clinic`
- `room` y `equipment` dependen de `site` + `clinic`
- `clinic_membership` depende de `app_user` + `clinic`
- `professional` depende de `clinic` y array de `site_ids`
- `site_billing_line` depende de `site` + `company`

---

## Datos de Catálogo (Opcional en Setup Inicial)

Estas tablas se pueden llenar después del setup básico, pero son necesarias antes de empezar a agendar:

### Service (Líneas de Negocio)

```sql
INSERT INTO service (id, clinic_id, name, description, record_status)
VALUES (gen_random_uuid(), '<clinic_id>', 'Odontología', 'Servicios odontológicos', 'ACTIVE');
```

### Category (Categorías de Servicio)

```sql
INSERT INTO category (id, service_id, clinic_id, name, description, record_status)
VALUES (gen_random_uuid(), '<service_id>', '<clinic_id>', 'Endodoncia', 'Tratamientos de conducto', 'ACTIVE');
```

### Treatment (Tratamientos)

```sql
INSERT INTO treatment (
  id, clinic_id, category_id, name, description,
  duration_minutes, base_price, currency, record_status
)
VALUES (
  gen_random_uuid(), '<clinic_id>', '<category_id>',
  'Tratamiento de Conducto Unirradicular',
  'Endodoncia simple de un canal',
  60, 350.00, 'PEN', 'ACTIVE'
);
```

---

## Validación Post-Setup

Después de completar todos los pasos, ejecuta estas queries de validación:

### 1. Verificar Jerarquía Organizacional

```sql
-- Verificar organización
SELECT id, name, organization_status, home_country
FROM organization
WHERE record_status = 'ACTIVE';

-- Verificar clínicas por organización
SELECT c.name as clinic_name, o.name as organization_name,
       c.clinic_status, c.default_currency
FROM clinic c
JOIN organization o ON c.organization_id = o.id
WHERE c.record_status = 'ACTIVE';

-- Verificar companies emisoras
SELECT name, legal_name, type, tax_id_type, tax_id_number, country
FROM company
WHERE record_status = 'ACTIVE' AND type = 'CLINIC_ISSUER';
```

### 2. Verificar Infraestructura de Sedes

```sql
-- Sedes por clínica
SELECT s.name as sede, c.name as clinica, s.site_status, s.timezone
FROM site s
JOIN clinic c ON s.clinic_id = c.id
WHERE s.record_status = 'ACTIVE'
ORDER BY c.name, s.name;

-- Rooms por sede
SELECT r.name as sala, r.room_type, s.name as sede, r.capacity
FROM room r
JOIN site s ON r.site_id = s.id
WHERE r.record_status = 'ACTIVE'
ORDER BY s.name, r.name;

-- Equipment por sede
SELECT e.name as equipo, e.equipment_type, s.name as sede
FROM equipment e
JOIN site s ON e.site_id = s.id
WHERE e.record_status = 'ACTIVE'
ORDER BY s.name, e.name;
```

### 3. Verificar Configuración de Usuarios

```sql
-- Usuarios con acceso por clínica
SELECT u.email, u.name, u.last_name, u.role_base,
       cm.role as clinic_role, c.name as clinic_name
FROM app_user u
JOIN clinic_membership cm ON u.id = cm.user_id
JOIN clinic c ON cm.clinic_id = c.id
WHERE u.record_status = 'ACTIVE' AND cm.clinic_membership_status = 'ACTIVE'
ORDER BY c.name, u.email;

-- Verificar que cada clínica tiene al menos un owner
SELECT c.name as clinic_name, COUNT(*) as owner_count
FROM clinic c
JOIN clinic_membership cm ON c.id = cm.clinic_id
WHERE cm.role = 'owner' AND cm.clinic_membership_status = 'ACTIVE'
GROUP BY c.name
HAVING COUNT(*) = 0;  -- Debería retornar 0 filas
```

### 4. Verificar Profesionales

```sql
-- Profesionales por clínica
SELECT p.name, p.specialty, p.professional_status,
       c.name as clinic_name,
       array_length(p.site_ids, 1) as num_sedes
FROM professional p
JOIN clinic c ON p.clinic_id = c.id
WHERE p.record_status = 'ACTIVE'
ORDER BY c.name, p.name;

-- Profesionales con usuario de sistema
SELECT p.name as profesional, u.email, p.specialty
FROM professional p
LEFT JOIN app_user u ON p.user_id = u.id
WHERE p.record_status = 'ACTIVE';
```

### 5. Verificar Firmantes Autorizados

```sql
-- Firmantes por clínica
SELECT c.name as clinic_name,
       a.name as signatory_name,
       a.position,
       a.signatory_type,
       a.authorized_signatory_status
FROM authorized_signatory a
JOIN clinic c ON a.clinic_id = c.id
WHERE a.record_status = 'ACTIVE'
ORDER BY c.name, a.signatory_type;

-- Verificar que cada clínica tiene director médico
SELECT c.name as clinic_name
FROM clinic c
LEFT JOIN authorized_signatory a
  ON c.id = a.clinic_id
  AND a.signatory_type = 'MEDICAL_DIRECTOR'
  AND a.authorized_signatory_status = 'ACTIVE'
WHERE a.id IS NULL AND c.clinic_status = 'ACTIVE';  -- Debería retornar 0 filas
```

### 6. Verificar Configuración de Facturación

```sql
-- Billing lines por sede
SELECT s.name as sede, c.name as emisor, sbl.is_default
FROM site_billing_line sbl
JOIN site s ON sbl.site_id = s.id
JOIN company c ON sbl.issuer_company_id = c.id
WHERE sbl.record_status = 'ACTIVE'
ORDER BY s.name;

-- Verificar que cada sede tiene billing line default
SELECT s.name as sede
FROM site s
LEFT JOIN site_billing_line sbl
  ON s.id = sbl.site_id
  AND sbl.is_default = true
  AND sbl.record_status = 'ACTIVE'
WHERE sbl.id IS NULL AND s.site_status = 'ACTIVE';  -- Debería retornar 0 filas
```

### 7. Verificar Catálogo (si ya se configuró)

```sql
-- Servicios y categorías
SELECT s.name as servicio, c.name as categoria, cl.name as clinica
FROM category c
JOIN service s ON c.service_id = s.id
JOIN clinic cl ON c.clinic_id = cl.id
WHERE c.record_status = 'ACTIVE'
ORDER BY cl.name, s.name, c.name;

-- Tratamientos por categoría
SELECT t.name as tratamiento, c.name as categoria,
       t.duration_minutes, t.base_price, t.currency
FROM treatment t
JOIN category c ON t.category_id = c.id
WHERE t.record_status = 'ACTIVE'
ORDER BY c.name, t.name;
```

### Checklist de Validación

Después de ejecutar las queries anteriores, verificar:

- [ ] Existe al menos 1 organización activa
- [ ] Existe al menos 1 company de tipo CLINIC_ISSUER
- [ ] Existe al menos 1 clínica activa con default_issuer_company_id configurado
- [ ] Cada clínica tiene al menos 1 sede activa
- [ ] Cada sede tiene al menos 1 room
- [ ] Cada sede tiene site_billing_line con is_default = true
- [ ] Existe al menos 1 usuario con role_base = 'clinic_owner'
- [ ] Cada clínica tiene al menos 1 clinic_membership con role = 'owner'
- [ ] Cada clínica tiene al menos 1 professional activo
- [ ] Cada clínica tiene al menos 1 authorized_signatory de tipo MEDICAL_DIRECTOR
- [ ] (Opcional) Cada clínica tiene al menos 1 service con categories y treatments

---

## Siguiente Paso: Migración de Datos

Una vez completada la configuración inicial, puedes proceder a:

1. **Migrar pacientes** → tabla `patient`
2. **Migrar historial médico** → tablas de care-management
3. **Migrar citas** → tabla `schedule_block`
4. **Migrar documentos de facturación** → tabla `billing_document`

Cada migración debe respetar las relaciones foreign key con las entidades configuradas en este setup.

---

## Notas Importantes

- **UUIDs:** Todos los IDs se generan con `gen_random_uuid()` o mediante la aplicación
- **Timestamps:** `created_at` y `updated_at` se manejan automáticamente por Prisma
- **Record Status:** Siempre usar `'ACTIVE'` para registros en uso
- **JSON Fields:** Campos como `address`, `metadata`, `record_metadata` usan formato `jsonb`
- **Arrays:** Campos como `site_ids` en Professional usan arrays de PostgreSQL

---

## Contacto y Soporte

Para dudas sobre la configuración inicial, consultar:

- Documentación de dominio: `docs/REFERENCES/DOMAIN/`
- Runbook de bootstrap: `docs/REFERENCES/RUNBOOK-BOOTSTRAP.md`
- Schema de Prisma: `prisma/schema.prisma`
