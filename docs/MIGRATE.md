# Guía de Migración de Datos - ClinicSay Backend

> **Última actualización:** 2025-01-21
> **Propósito:** Documentar el orden y dependencias para migración de datos entre ambientes o desde sistemas legacy.

---

## Tabla de Contenidos

1. [Introducción](#1-introducción)
2. [Arquitectura de Datos](#2-arquitectura-de-datos)
3. [Orden de Migración por Niveles](#3-orden-de-migración-por-niveles)
4. [Diagrama de Dependencias](#4-diagrama-de-dependencias)
5. [Detalle de Tablas por Nivel](#5-detalle-de-tablas-por-nivel)
6. [Constraints y Validaciones](#6-constraints-y-validaciones)
7. [Patrones de Datos](#7-patrones-de-datos)
8. [Scripts y Comandos](#8-scripts-y-comandos)
9. [Checklist de Migración](#9-checklist-de-migración)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Introducción

### 1.1 Propósito de este Documento

Este documento sirve como guía definitiva para:

- **Migración de datos** desde sistemas legacy a ClinicSay
- **Sincronización entre ambientes** (dev → staging → production)
- **Restauración de backups** con integridad referencial
- **Seeding inicial** de nuevos ambientes

### 1.2 Principios Fundamentales

1. **Integridad Referencial:** Las foreign keys DEBEN existir antes de insertar registros dependientes
2. **Idempotencia:** Las migraciones deben poder ejecutarse múltiples veces sin duplicar datos
3. **Soft Delete:** El sistema usa `recordStatus` para borrado lógico, no físico
4. **Multi-tenant:** Toda data está aislada por `Organization` → `Clinic`

### 1.3 Clasificación de Modelos

Cada tabla en el schema tiene una clasificación (`@model-class`):

| Clase | Descripción | Ejemplo |
|-------|-------------|---------|
| `ENTITY` | Entidad de dominio con ciclo de vida propio | Organization, Patient, Clinic |
| `AGGREGATE_PART` | Sub-entidad que pertenece a un padre (cascade delete) | PatientPhone, PackDefinitionItem |
| `JOIN_TABLE` | Tabla de relación M:N pura | RolePermission |
| `SYSTEM` | Tablas de framework/sistema | _prisma_migrations |

---

## 2. Arquitectura de Datos

### 2.1 Jerarquía Multi-Tenant

```
┌─────────────────────────────────────────────────────────────────┐
│                        PLATFORM LEVEL                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Permission  │  │     User     │  │RolePermission│           │
│  │  (catalog)   │  │  (Cognito)   │  │  (mapping)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORGANIZATION LEVEL                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Organization                         │   │
│  │         (tenant raíz - aísla toda la data)               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                    │                      │                     │
│                    ▼                      ▼                     │
│           ┌──────────────┐       ┌──────────────┐               │
│           │    Clinic    │       │   Company    │               │
│           │ (operación)  │       │ (facturación)│               │
│           └──────────────┘       └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CLINIC LEVEL                             │
│  ┌────────┐ ┌─────────┐ ┌─────────────────┐ ┌──────────────-┐   │
│  │  Site  │ │ Patient │ │ ConsentTemplate │ │ PackDefinition│   │
│  └────────┘ └─────────┘ └─────────────────┘ └──────────────-┘   │
│  ┌────────┐ ┌─────────┐ ┌─────────────────┐ ┌──────────────┐    │
│  │Service │ │   Tag   │ │  Professional   │ │PaymentMethod │    │
│  └────────┘ └─────────┘ └─────────────────┘ └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SITE LEVEL                              │
│  ┌────────┐ ┌───────────┐ ┌────────┐ ┌─────────┐ ┌───────────┐  │
│  │  Room  │ │ Equipment │ │ Supply │ │ Product │ │ Treatment │  │
│  └────────┘ └───────────┘ └────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSACTIONAL LEVEL                          │
│  ┌─────────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │ ConsentInstance │ │ PackInstance │ │      CarePlan         │ │
│  └─────────────────┘ └──────────────┘ └───────────────────────┘ │
│  ┌─────────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │  ScheduleBlock  │ │    Budget    │ │   BillingDocument     │ │
│  └─────────────────┘ └──────────────┘ └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo de Datos Típico

```
1. Usuario se autentica (Cognito → User)
2. Usuario pertenece a Organization
3. Organization tiene Clinic(s) y Company(s)
4. Clinic tiene Site(s) donde opera
5. Site tiene recursos (Room, Equipment, etc.)
6. Patient se registra en Clinic/Site
7. Patient firma ConsentInstance (de ConsentTemplate)
8. Patient tiene CarePlan con PlannedSessions
9. ScheduleBlock representa citas agendadas
10. BillingDocument registra facturación
```

---

## 3. Orden de Migración por Niveles

### Resumen Visual

```
┌─────────────────────────────────────────────────────────────────┐
│ NIVEL 0: RAÍZ (sin dependencias)                                │
│ Permission → Organization → User                                │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 1: CORE (depende de Nivel 0)                              │
│ RolePermission → Clinic → Company → UserContextTracking         │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 2: SECUNDARIO (depende de Nivel 1)                        │
│ Site → Patient → Professional → Service → ConsentTemplate...    │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 3: TERCIARIO (depende de Nivel 2)                         │
│ Room → Equipment → Supply → Product → Treatment → Category...   │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 4: AGGREGATE PARTS (depende de Nivel 2-3)                 │
│ PatientPhone → PatientEmail → PackDefinitionItem...             │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 5: TRANSACCIONAL (depende de múltiples niveles)           │
│ ConsentInstance → PackInstance → CarePlan → ScheduleBlock...    │
├─────────────────────────────────────────────────────────────────┤
│ NIVEL 6: SUB-TRANSACCIONAL (depende de Nivel 5)                 │
│ ConsentInstanceEvidence → PlannedSession → BlockParticipant...  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Diagrama de Dependencias

### 4.1 Dependencias Principales

```
Permission ─────────────────────────────────────────────────────┐
                                                                ▼
Organization ──┬──► Clinic ──┬──► Site ──┬──► Room            RolePermission
               │             │           ├──► Equipment
               │             │           ├──► Supply
               │             │           ├──► Product
               │             │           └──► Treatment ◄── Service
               │             │                              ◄── Category
               │             │
               │             ├──► Patient ──┬──► PatientPhone
               │             │              ├──► PatientEmail
               │             │              ├──► PatientContact
               │             │              ├──► PackInstance ◄── PackDefinition
               │             │              ├──► CarePlan ──► PlannedSession
               │             │              └──► ConsentInstance ◄── ConsentTemplate
               │             │                   ├──► ConsentInstanceEvidence
               │             │                   ├──► ConsentInstanceSigner
               │             │                   └──► ConsentInstanceSignature
               │             │
               │             ├──► Professional ◄── User (opcional)
               │             ├──► ConsentTemplate
               │             ├──► PackDefinition ──► PackDefinitionItem
               │             ├──► Service ──► Category (self-referencing)
               │             ├──► Tag
               │             ├──► PaymentMethod
               │             ├──► AuthorizedSignatory
               │             ├──► SchedulingPolicy
               │             ├──► AvailabilityTemplate ──► AvailabilityException
               │             ├──► ScheduleBlock ──► BlockParticipant
               │             │                  ──► ScheduleHistoryEntry
               │             ├──► BillingSequence
               │             ├──► BillingClient
               │             └──► BudgetProposal ──► Budget
               │
               └──► Company ──┬──► SiteBillingLine ◄── Site
                              └──► PartnerAgreement

User ──────────┬──► UserContextTracking
               ├──► UserContextSuspension
               ├──► UserPermissionOverride
               └──► Professional (link opcional)
```

### 4.2 Relaciones de Cascade Delete

Cuando se elimina un registro padre, estos hijos se eliminan automáticamente:

| Padre | Hijos (CASCADE) |
|-------|-----------------|
| Organization | Clinic, Company |
| Clinic | Site, Patient, Professional, Service, ConsentTemplate, PackDefinition, Tag, etc. |
| Site | Room, Equipment, Supply, Product, Treatment |
| Patient | PatientPhone, PatientEmail, PatientContact |
| ConsentInstance | ConsentInstanceEvidence, ConsentInstanceSigner, ConsentInstanceSignature |
| PackDefinition | PackDefinitionItem |
| CarePlan | PlannedSession |
| ScheduleBlock | BlockParticipant, ScheduleHistoryEntry |
| AvailabilityTemplate | AvailabilityException |
| BillingDocument | BillingItem |

---

## 5. Detalle de Tablas por Nivel

### Nivel 0: Tablas Raíz (Sin Dependencias)

#### Permission
```
Propósito: Catálogo de permisos del sistema
Dependencias: Ninguna
Migrar: PRIMERO (reference data)
Comando: npm run migrate:refdata

Campos clave:
- key: String (UNIQUE) - Identificador del permiso (ej: "patients.read")
- name: String - Nombre legible
- description: String - Descripción del permiso
```

#### Organization
```
Propósito: Entidad tenant raíz que aísla toda la data
Dependencias: Ninguna
Migrar: Después de Permission

Campos clave:
- id: UUID
- name: String - Nombre de la organización
- recordStatus: RecordStatus (ACTIVE por defecto)
- createdAt, updatedAt: DateTime
```

#### User
```
Propósito: Usuarios de la plataforma (sincronizados desde Cognito)
Dependencias: Ninguna
Migrar: Después de Organization

Campos clave:
- id: UUID
- cognitoSub: String (UNIQUE) - ID de Cognito
- email: String
- firstName, lastName: String
- recordStatus: RecordStatus
```

---

### Nivel 1: Entidades Core

#### RolePermission
```
Propósito: Mapeo entre roles y permisos
Dependencias: Permission (FK: permissionKey)
Migrar: Después de Permission

Campos clave:
- id: UUID
- roleBase: String - Rol base (ej: "clinic_admin", "clinic_professional")
- permissionKey: String (FK → Permission.key)
- UNIQUE: (roleBase, permissionKey)
```

#### Clinic
```
Propósito: Clínica operativa dentro de una organización
Dependencias: Organization (FK: organizationId)
Migrar: Después de Organization

Campos clave:
- id: UUID
- organizationId: UUID (FK, CASCADE)
- name: String
- recordStatus: RecordStatus
- Relación: 1 Organization → N Clinics
```

#### Company
```
Propósito: Entidad de facturación (puede ser la clínica misma, aseguradora, etc.)
Dependencias: Organization (FK: organizationId)
Migrar: Después de Organization

Campos clave:
- id: UUID
- organizationId: UUID (FK, CASCADE)
- name: String
- companyType: String (ISSUER, CORPORATE_PAYER, INSURANCE_PAYER, etc.)
- taxId: String (opcional)
- recordStatus: RecordStatus
```

#### UserContextTracking
```
Propósito: Rastrea el contexto activo del usuario (qué clínica/site está usando)
Dependencias: User (FK: userId)
Migrar: Después de User

Campos clave:
- id: UUID
- userId: UUID (FK, CASCADE)
- activeClinicId: UUID (opcional)
- activeSiteId: UUID (opcional)
- activeOrganizationId: UUID (opcional)
```

---

### Nivel 2: Entidades Secundarias

#### Site
```
Propósito: Sede física donde opera la clínica
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- name: String
- address: String (opcional)
- timezone: String (ej: "America/Lima")
- recordStatus: RecordStatus
```

#### Patient
```
Propósito: Paciente registrado en la clínica
Dependencias: Clinic (FK: clinicId), Site (FK: siteId, opcional)
Migrar: Después de Clinic y Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, opcional)
- firstName, lastName: String
- documentType, documentNumber: String
- birthDate: DateTime (opcional)
- patientSchedulingStatus: String (SCHEDULABLE, NOT_SCHEDULABLE, etc.)
- recordStatus: RecordStatus
```

#### Professional
```
Propósito: Profesional que trabaja en la clínica
Dependencias: Clinic (FK: clinicId), User (opcional, link)
Migrar: Después de Clinic y User

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- userId: UUID (opcional - si el profesional tiene cuenta de usuario)
- firstName, lastName: String
- employmentType: EmploymentType (INTERNAL, FREELANCER, CONTRACTOR, VISITING)
- licenseNumber: String (opcional)
- recordStatus: RecordStatus
```

#### Service
```
Propósito: Servicio médico ofrecido por la clínica
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- name: String
- description: String (opcional)
- recordStatus: RecordStatus
```

#### ConsentTemplate
```
Propósito: Plantilla de consentimiento informado
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- title: String
- content: String (HTML/Markdown)
- version: String
- consentTemplateStatus: String (DRAFT, PUBLISHED, ARCHIVED)
- recordStatus: RecordStatus
```

#### PackDefinition
```
Propósito: Definición de paquete de servicios/tratamientos
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- name: String
- description: String (opcional)
- totalSessions: Int
- price: Decimal
- packDefinitionStatus: String (ACTIVE, INACTIVE)
- recordStatus: RecordStatus
```

#### Tag
```
Propósito: Etiquetas para categorizar pacientes, servicios, etc.
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- name: String
- slug: String
- color: String (opcional)
- UNIQUE: (clinicId, slug)
```

#### PaymentMethod
```
Propósito: Métodos de pago configurados por la clínica
Dependencias: Clinic (FK: clinicId)
Migrar: Después de Clinic

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- paymentMethodType: String (CASH, CARD, TRANSFER, etc.)
- name: String
- isActive: Boolean
- UNIQUE: (clinicId, paymentMethodType, name)
```

#### PartnerAgreement
```
Propósito: Acuerdos con empresas partner (aseguradoras, corporativos)
Dependencias: Clinic (FK: clinicId), Company (FK: partnerCompanyId), Site (opcional)
Migrar: Después de Clinic y Company

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- partnerCompanyId: UUID (FK → Company)
- siteId: UUID (FK, opcional)
- agreementType: String
- discountPercentage: Decimal (opcional)
- partnerAgreementStatus: String (DRAFT, ACTIVE, SUSPENDED, TERMINATED)
```

#### BillingClient
```
Propósito: Cliente de facturación (puede ser paciente, empresa, etc.)
Dependencias: Clinic (FK: clinicId), Patient (opcional), PartnerAgreement (opcional)
Migrar: Después de Clinic, Patient, PartnerAgreement

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, opcional)
- partnerAgreementId: UUID (FK, opcional)
- name: String
- taxId: String (opcional)
```

#### SiteBillingLine
```
Propósito: Configuración de facturación por sede
Dependencias: Site (FK: siteId), Company (FK: companyId)
Migrar: Después de Site y Company

Campos clave:
- id: UUID
- siteId: UUID (FK)
- companyId: UUID (FK → Company)
- isDefault: Boolean
```

---

### Nivel 3: Entidades Terciarias

#### Room
```
Propósito: Sala/consultorio dentro de una sede
Dependencias: Clinic (FK: clinicId), Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, CASCADE)
- name: String
- capacity: Int (opcional)
- recordStatus: RecordStatus
```

#### Equipment
```
Propósito: Equipamiento médico de la sede
Dependencias: Clinic (FK: clinicId), Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, CASCADE)
- name: String
- serialNumber: String (opcional)
- recordStatus: RecordStatus
```

#### Supply
```
Propósito: Insumos/materiales de la sede
Dependencias: Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- siteId: UUID (FK, CASCADE)
- name: String
- quantity: Int
- unit: String
- UNIQUE: (siteId, name)
```

#### Product
```
Propósito: Productos vendibles de la sede
Dependencias: Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- siteId: UUID (FK, CASCADE)
- name: String
- price: Decimal
- stockQuantity: Int
- UNIQUE: (siteId, name)
```

#### Treatment
```
Propósito: Tratamiento específico ofrecido en la sede
Dependencias: Site (FK: siteId), Service (FK: serviceId, opcional), Category (FK: categoryId, opcional)
Migrar: Después de Site, Service, Category

Campos clave:
- id: UUID
- siteId: UUID (FK, CASCADE)
- serviceId: UUID (FK, opcional)
- categoryId: UUID (FK, opcional)
- name: String
- treatmentType: TreatmentType (SINGLE_SESSION, MULTI_SESSION, PROGRAM, GROUP)
- duration: Int (minutos)
- price: Decimal
- treatmentVisibility: TreatmentVisibility (INTERNAL_ONLY, PATIENT_APP, HIDDEN)
```

#### Category
```
Propósito: Categoría de servicios (puede ser jerárquica)
Dependencias: Clinic (FK: clinicId), Service (FK: serviceId, opcional), Category (FK: parentId, self-ref opcional)
Migrar: Después de Service (migrar padres antes que hijos)

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- serviceId: UUID (FK, opcional)
- parentId: UUID (FK → Category, self-reference, opcional)
- name: String
- level: Int (0 = raíz, 1 = hijo, etc.)
```

#### AuthorizedSignatory
```
Propósito: Persona autorizada a firmar documentos
Dependencias: Clinic (FK: clinicId), Site (FK: siteId, opcional), User (referencia)
Migrar: Después de Clinic, Site, User

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, opcional)
- userId: UUID (referencia, no FK estricta)
- name: String
- title: String
- signatureImageUrl: String (opcional)
- authorizedSignatoryStatus: String (ACTIVE, INACTIVE)
```

#### BillingSequence
```
Propósito: Secuencia de numeración para documentos de facturación
Dependencias: Clinic (FK: clinicId), Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK)
- documentType: String (INVOICE, RECEIPT, CREDIT_NOTE)
- professionalId: UUID (opcional)
- year: Int
- lastNumber: Int
- UNIQUE: (siteId, documentType, professionalId, year)
```

---

### Nivel 4: Aggregate Parts

#### PatientPhone
```
Propósito: Teléfonos del paciente (puede tener múltiples)
Dependencias: Clinic (FK: clinicId), Patient (FK: patientId)
Migrar: Después de Patient
Cascade: Se elimina si se elimina Patient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- phoneNumber: String
- phoneType: String (MOBILE, HOME, WORK)
- isPrimary: Boolean
```

#### PatientEmail
```
Propósito: Emails del paciente
Dependencias: Clinic (FK: clinicId), Patient (FK: patientId)
Migrar: Después de Patient
Cascade: Se elimina si se elimina Patient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- email: String
- isPrimary: Boolean
```

#### PatientContact
```
Propósito: Contactos de emergencia/familiares del paciente
Dependencias: Clinic (FK: clinicId), Patient (FK: patientId)
Migrar: Después de Patient
Cascade: Se elimina si se elimina Patient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- name: String
- relationship: String
- phoneNumber: String
```

#### PackDefinitionItem
```
Propósito: Items que componen un paquete
Dependencias: PackDefinition (FK: packDefinitionId)
Migrar: Después de PackDefinition
Cascade: Se elimina si se elimina PackDefinition

Campos clave:
- id: UUID
- packDefinitionId: UUID (FK, CASCADE)
- treatmentId: UUID (FK → Treatment, opcional)
- name: String
- quantity: Int
- unitPrice: Decimal
```

---

### Nivel 5: Entidades Transaccionales

#### ConsentInstance
```
Propósito: Instancia de consentimiento firmado por un paciente
Dependencias: Clinic, Patient, ConsentTemplate, Site (opcional)
Migrar: Después de Patient y ConsentTemplate

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- templateId: UUID (FK → ConsentTemplate)
- siteId: UUID (FK, opcional)
- consentInstanceStatus: String (PENDING, SIGNED, REVOKED, EXPIRED)
- signedAt: DateTime (opcional)
```

#### PackInstance
```
Propósito: Paquete adquirido por un paciente
Dependencias: Clinic, Patient, PackDefinition
Migrar: Después de Patient y PackDefinition

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- packDefinitionId: UUID (FK)
- usedSessions: Int
- packInstanceStatus: String (ACTIVE, COMPLETED, CANCELLED, EXPIRED)
```

#### CarePlan
```
Propósito: Plan de tratamiento del paciente
Dependencias: Clinic (FK: clinicId), Patient (FK: patientId)
Migrar: Después de Patient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- name: String
- startDate: DateTime
- endDate: DateTime (opcional)
- carePlanStatus: String (DRAFT, ACTIVE, COMPLETED, CANCELLED)
```

#### BudgetProposal
```
Propósito: Propuesta de presupuesto para el paciente
Dependencias: Clinic, Patient, Site (opcional)
Migrar: Después de Patient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- patientId: UUID (FK, CASCADE)
- siteId: UUID (FK, opcional)
- totalAmount: Decimal
- budgetProposalStatus: String (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED)
```

#### Budget
```
Propósito: Presupuesto aprobado
Dependencias: Clinic, CarePlan (opcional), BudgetProposal (opcional)
Migrar: Después de CarePlan y BudgetProposal

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- carePlanId: UUID (FK, opcional)
- proposalId: UUID (FK → BudgetProposal, opcional)
- totalAmount: Decimal
- budgetStatus: String (ACTIVE, COMPLETED, CANCELLED)
```

#### ScheduleBlock
```
Propósito: Bloque de agenda (cita, bloqueo, evento)
Dependencias: Clinic (FK: clinicId), Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, CASCADE)
- startTime: DateTime
- endTime: DateTime
- blockType: String (APPOINTMENT, BLOCK, BREAK, etc.)
- scheduleBlockStatus: String (SCHEDULED, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW)
```

#### SchedulingPolicy
```
Propósito: Reglas de scheduling para la clínica/sede
Dependencias: Clinic (FK: clinicId), Site (FK: siteId, opcional)
Migrar: Después de Clinic y Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, opcional)
- name: String
- isHard: Boolean (constraint dura vs suave)
- priority: Int
```

#### AvailabilityTemplate
```
Propósito: Plantilla de disponibilidad de recursos
Dependencias: Clinic (FK: clinicId), Site (FK: siteId)
Migrar: Después de Site

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, CASCADE)
- name: String
- resourceType: String (PROFESSIONAL, ROOM, EQUIPMENT)
- resourceId: UUID
```

#### BillingDocument
```
Propósito: Documento de facturación (factura, boleta, nota de crédito)
Dependencias: Clinic, Site (opcional), Patient (opcional), BillingClient
Migrar: Después de BillingClient

Campos clave:
- id: UUID
- clinicId: UUID (FK, CASCADE)
- siteId: UUID (FK, opcional)
- patientId: UUID (FK, opcional)
- billingClientId: UUID (FK → BillingClient)
- documentType: String (INVOICE, RECEIPT, CREDIT_NOTE)
- documentNumber: String
- totalAmount: Decimal
- billingDocumentStatus: String (DRAFT, ISSUED, PAID, CANCELLED, VOIDED)
```

---

### Nivel 6: Sub-entidades Transaccionales

#### ConsentInstanceEvidence
```
Propósito: Evidencia del consentimiento (archivos, fotos, etc.)
Dependencias: ConsentInstance (FK: consentInstanceId)
Cascade: Se elimina si se elimina ConsentInstance

Campos clave:
- id: UUID
- consentInstanceId: UUID (FK, CASCADE)
- evidenceType: String (SIGNATURE, PHOTO, DOCUMENT)
- fileUrl: String
- capturedAt: DateTime
```

#### ConsentInstanceSigner
```
Propósito: Firmante del consentimiento (puede ser paciente o representante)
Dependencias: ConsentInstance (FK: consentInstanceId)
Cascade: Se elimina si se elimina ConsentInstance

Campos clave:
- id: UUID
- consentInstanceId: UUID (FK, CASCADE)
- signerType: String (PATIENT, LEGAL_REPRESENTATIVE, WITNESS)
- name: String
- documentNumber: String (opcional)
```

#### ConsentInstanceSignature
```
Propósito: Firma digital del firmante
Dependencias: ConsentInstance, ConsentInstanceSigner
Cascade: Se elimina si se elimina ConsentInstance

Campos clave:
- id: UUID
- consentInstanceId: UUID (FK, CASCADE)
- signerId: UUID (FK → ConsentInstanceSigner, CASCADE)
- signatureData: String (base64 o URL)
- signedAt: DateTime
```

#### PlannedSession
```
Propósito: Sesión planificada dentro de un CarePlan
Dependencias: CarePlan (FK: carePlanId)
Cascade: Se elimina si se elimina CarePlan

Campos clave:
- id: UUID
- carePlanId: UUID (FK, CASCADE)
- sessionNumber: Int
- plannedDate: DateTime (opcional)
- plannedSessionStatus: String (PLANNED, SCHEDULED, COMPLETED, CANCELLED)
```

#### BlockParticipant
```
Propósito: Participante en un bloque de agenda
Dependencias: ScheduleBlock (FK: blockId)
Cascade: Se elimina si se elimina ScheduleBlock

Campos clave:
- id: UUID
- blockId: UUID (FK → ScheduleBlock, CASCADE)
- participantType: String (PATIENT, PROFESSIONAL, ROOM, EQUIPMENT)
- participantId: UUID
```

#### ScheduleHistoryEntry
```
Propósito: Historial de cambios en un bloque de agenda (audit trail)
Dependencias: ScheduleBlock (FK: blockId)
Cascade: Se elimina si se elimina ScheduleBlock

Campos clave:
- id: UUID
- blockId: UUID (FK → ScheduleBlock, CASCADE)
- action: String (CREATED, UPDATED, CANCELLED, etc.)
- changedBy: UUID (userId)
- changedAt: DateTime
- previousState: Json (opcional)
- newState: Json (opcional)
```

#### AvailabilityException
```
Propósito: Excepción a la plantilla de disponibilidad
Dependencias: AvailabilityTemplate (FK: templateId)
Cascade: Se elimina si se elimina AvailabilityTemplate

Campos clave:
- id: UUID
- templateId: UUID (FK → AvailabilityTemplate, CASCADE)
- exceptionType: String (UNAVAILABLE, MODIFIED_HOURS)
- startDate: DateTime
- endDate: DateTime
- reason: String (opcional)
```

#### BillingItem
```
Propósito: Línea de detalle en un documento de facturación
Dependencias: BillingDocument (FK: documentId)
Cascade: Se elimina si se elimina BillingDocument

Campos clave:
- id: UUID
- documentId: UUID (FK → BillingDocument, CASCADE)
- description: String
- quantity: Int
- unitPrice: Decimal
- totalPrice: Decimal
- treatmentId: UUID (FK → Treatment, opcional)
```

---

## 6. Constraints y Validaciones

### 6.1 Unique Constraints

| Tabla | Campos | Descripción |
|-------|--------|-------------|
| User | `cognitoSub` | Un usuario por identidad Cognito |
| Permission | `key` | Clave única de permiso |
| RolePermission | `(roleBase, permissionKey)` | Sin duplicados rol-permiso |
| Tag | `(clinicId, slug)` | Slug único por clínica |
| Supply | `(siteId, name)` | Nombre único por sede |
| Product | `(siteId, name)` | Nombre único por sede |
| PaymentMethod | `(clinicId, paymentMethodType, name)` | Método único por tipo y nombre |
| BillingSequence | `(siteId, documentType, professionalId, year)` | Secuencia única por contexto |

### 6.2 Validaciones Pre-Insert

Antes de insertar registros, verificar:

```typescript
// 1. FK existe
const organization = await prisma.organization.findUnique({ where: { id: clinicData.organizationId } });
if (!organization) throw new Error('Organization not found');

// 2. Unique constraint no violado
const existingTag = await prisma.tag.findUnique({
  where: { clinicId_slug: { clinicId, slug } }
});
if (existingTag) throw new Error('Tag slug already exists');

// 3. recordStatus válido
if (!['ACTIVE', 'INACTIVE', 'ARCHIVED', 'DELETED'].includes(data.recordStatus)) {
  throw new Error('Invalid recordStatus');
}
```

### 6.3 Enums del Sistema

```typescript
// RecordStatus - Estado de ciclo de vida
enum RecordStatus {
  ACTIVE = 'ACTIVE',       // Normal, operativo
  INACTIVE = 'INACTIVE',   // Temporalmente inactivo
  ARCHIVED = 'ARCHIVED',   // Archivado (soft delete)
  DELETED = 'DELETED'      // Deprecado, usar ARCHIVED
}

// EmploymentType - Tipo de empleo de profesional
enum EmploymentType {
  INTERNAL = 'INTERNAL',
  FREELANCER = 'FREELANCER',
  CONTRACTOR = 'CONTRACTOR',
  VISITING = 'VISITING'
}

// TreatmentType - Tipo de tratamiento
enum TreatmentType {
  SINGLE_SESSION = 'SINGLE_SESSION',
  MULTI_SESSION = 'MULTI_SESSION',
  PROGRAM = 'PROGRAM',
  GROUP = 'GROUP'
}

// TreatmentVisibility - Visibilidad del tratamiento
enum TreatmentVisibility {
  INTERNAL_ONLY = 'INTERNAL_ONLY',
  PATIENT_APP = 'PATIENT_APP',
  HIDDEN = 'HIDDEN'
}
```

---

## 7. Patrones de Datos

### 7.1 Record Lifecycle Pattern

Todas las entidades (`@model-class ENTITY`) siguen este patrón:

```typescript
interface EntityFields {
  // Identificador
  id: string;                    // UUID v4

  // Lifecycle
  recordStatus: RecordStatus;    // ACTIVE | INACTIVE | ARCHIVED | DELETED
  recordMetadata: Json | null;   // Metadata adicional del ciclo de vida

  // Business status (específico por entidad)
  [entity]Status: string;        // ej: patientSchedulingStatus, carePlanStatus

  // Timestamps
  createdAt: DateTime;           // Auto-generado
  updatedAt: DateTime;           // Auto-actualizado
}
```

### 7.2 Soft Delete

```typescript
// CORRECTO: Soft delete
await prisma.patient.update({
  where: { id: patientId },
  data: {
    recordStatus: 'ARCHIVED',
    recordMetadata: {
      archivedAt: new Date().toISOString(),
      archivedBy: userId,
      reason: 'Patient requested data removal'
    }
  }
});

// INCORRECTO: Hard delete (evitar)
await prisma.patient.delete({ where: { id: patientId } });
```

### 7.3 Consultas con Filtro de Status

```typescript
// Listar solo registros activos
const patients = await prisma.patient.findMany({
  where: {
    clinicId,
    recordStatus: 'ACTIVE'
  }
});

// Incluir archivados (para reportes históricos)
const allPatients = await prisma.patient.findMany({
  where: {
    clinicId,
    recordStatus: { in: ['ACTIVE', 'ARCHIVED'] }
  }
});
```

---

## 8. Scripts y Comandos

### 8.1 Reference Data (Catálogos)

```bash
# Migrar reference data (Permission, RolePermission)
npm run migrate:refdata

# Validar que reference data está completa
npm run validate:refdata
```

### 8.2 Schema Migrations (Prisma)

```bash
# Crear nueva migración
npm run db:migrate:dev -- --name descripcion_del_cambio

# Aplicar migraciones pendientes
npm run db:migrate:deploy

# Reset completo (CUIDADO: borra datos)
npm run db:reset
```

### 8.3 Seeds de Demo

```bash
# Seed de datos demo (solo dev/test)
npm run seed:demo

# Ver estructura del seed
ls scripts/seeds/demo/
```

### 8.4 Verificación de Integridad

```bash
# Verificar tipos y schema
npm run typecheck

# Verificar arquitectura
npm run check:architecture

# Verificar paridad TDD
npm run check:tdd:parity

# Ejecutar todos los checks
npm run check
```

---

## 9. Checklist de Migración

### Pre-Migración

- [ ] Backup completo de la base de datos destino
- [ ] Verificar que schema Prisma está sincronizado (`npm run db:migrate:deploy`)
- [ ] Reference data migrada (`npm run migrate:refdata`)
- [ ] Mapeo de IDs legacy → UUIDs nuevos preparado
- [ ] Scripts de transformación de datos validados

### Migración por Nivel

#### Nivel 0: Raíz
- [ ] Permission (ya debe existir via refdata)
- [ ] Organization
- [ ] User (sincronizar con Cognito)

#### Nivel 1: Core
- [ ] RolePermission (ya debe existir via refdata)
- [ ] Clinic (validar organizationId existe)
- [ ] Company (validar organizationId existe)
- [ ] UserContextTracking

#### Nivel 2: Secundario
- [ ] Site (validar clinicId existe)
- [ ] Patient (validar clinicId, siteId)
- [ ] Professional (validar clinicId)
- [ ] Service (validar clinicId)
- [ ] ConsentTemplate (validar clinicId)
- [ ] PackDefinition (validar clinicId)
- [ ] Tag (validar clinicId, verificar unique slug)
- [ ] PaymentMethod (validar clinicId)
- [ ] PartnerAgreement (validar clinicId, partnerCompanyId)
- [ ] BillingClient (validar clinicId)
- [ ] SiteBillingLine (validar siteId, companyId)

#### Nivel 3: Terciario
- [ ] Room (validar clinicId, siteId)
- [ ] Equipment (validar clinicId, siteId)
- [ ] Supply (validar siteId, verificar unique name)
- [ ] Product (validar siteId, verificar unique name)
- [ ] Category (migrar padres primero, luego hijos)
- [ ] Treatment (validar siteId, serviceId, categoryId)
- [ ] AuthorizedSignatory (validar clinicId, siteId)
- [ ] BillingSequence (validar clinicId, siteId)

#### Nivel 4: Aggregate Parts
- [ ] PatientPhone (validar patientId)
- [ ] PatientEmail (validar patientId)
- [ ] PatientContact (validar patientId)
- [ ] PackDefinitionItem (validar packDefinitionId)

#### Nivel 5: Transaccional
- [ ] ConsentInstance (validar patientId, templateId)
- [ ] PackInstance (validar patientId, packDefinitionId)
- [ ] CarePlan (validar patientId)
- [ ] BudgetProposal (validar patientId)
- [ ] Budget (validar carePlanId o proposalId)
- [ ] ScheduleBlock (validar siteId)
- [ ] SchedulingPolicy (validar clinicId)
- [ ] AvailabilityTemplate (validar siteId)
- [ ] BillingDocument (validar billingClientId)

#### Nivel 6: Sub-transaccional
- [ ] ConsentInstanceEvidence (validar consentInstanceId)
- [ ] ConsentInstanceSigner (validar consentInstanceId)
- [ ] ConsentInstanceSignature (validar consentInstanceId, signerId)
- [ ] PlannedSession (validar carePlanId)
- [ ] BlockParticipant (validar blockId)
- [ ] ScheduleHistoryEntry (validar blockId)
- [ ] AvailabilityException (validar templateId)
- [ ] BillingItem (validar documentId)

### Post-Migración

- [ ] Verificar conteos de registros migrados vs origen
- [ ] Ejecutar queries de validación de integridad referencial
- [ ] Probar flujos críticos en la aplicación
- [ ] Verificar que no hay huérfanos (registros sin padre)
- [ ] Documentar cualquier dato que no pudo migrarse

---

## 10. Troubleshooting

### Error: Foreign Key Constraint Failed

```
Error: Foreign key constraint failed on the field: `clinicId`
```

**Causa:** Intentando insertar registro con FK que no existe.

**Solución:** Verificar orden de migración. El registro padre debe existir antes de insertar el hijo.

```typescript
// Verificar que existe antes de insertar
const clinic = await prisma.clinic.findUnique({ where: { id: clinicId } });
if (!clinic) {
  console.error(`Clinic ${clinicId} not found, skipping patient`);
  return;
}
```

### Error: Unique Constraint Violation

```
Error: Unique constraint failed on the constraint: `Tag_clinicId_slug_key`
```

**Causa:** Intentando insertar registro duplicado.

**Solución:** Usar upsert en lugar de create.

```typescript
await prisma.tag.upsert({
  where: { clinicId_slug: { clinicId, slug } },
  update: { name, color }, // Actualizar si existe
  create: { clinicId, slug, name, color } // Crear si no existe
});
```

### Error: Invalid Enum Value

```
Error: Invalid value for argument `recordStatus`. Expected RecordStatus.
```

**Causa:** Valor de enum no reconocido.

**Solución:** Mapear valores legacy a enums válidos.

```typescript
const statusMap: Record<string, string> = {
  'active': 'ACTIVE',
  'inactive': 'INACTIVE',
  'deleted': 'ARCHIVED', // Legacy 'deleted' → 'ARCHIVED'
  '1': 'ACTIVE',
  '0': 'INACTIVE'
};

const recordStatus = statusMap[legacyStatus] || 'ACTIVE';
```

### Error: Orphaned Records

**Síntoma:** Registros hijos sin padre válido después de migración.

**Diagnóstico:**
```sql
-- Encontrar pacientes huérfanos
SELECT p.id, p."clinicId"
FROM "Patient" p
LEFT JOIN "Clinic" c ON p."clinicId" = c.id
WHERE c.id IS NULL;
```

**Solución:** Limpiar huérfanos o reasignar a clínica válida.

### Performance: Migración Lenta

**Causa:** Inserts uno por uno en tablas grandes.

**Solución:** Usar `createMany` con batches.

```typescript
const BATCH_SIZE = 1000;
const patients = [...]; // Array grande

for (let i = 0; i < patients.length; i += BATCH_SIZE) {
  const batch = patients.slice(i, i + BATCH_SIZE);
  await prisma.patient.createMany({
    data: batch,
    skipDuplicates: true
  });
  console.log(`Migrated ${i + batch.length} / ${patients.length} patients`);
}
```

---

## Apéndice: Ubicaciones de Archivos

| Recurso | Ubicación |
|---------|-----------|
| Schema Prisma | `prisma/schema.prisma` |
| Migraciones SQL | `prisma/migrations/` |
| Reference Data | `scripts/migrations/refdata/` |
| Seeds Demo | `scripts/seeds/demo/` |
| Documentación DDD | `docs/REFERENCES/DDD.md` |
| Documentación Repos | `docs/REFERENCES/REPOSITORIES.md` |
| Runbook Migraciones | `docs/REFERENCES/RUNBOOK-MIGRATIONS.md` |

---

*Documento generado para facilitar migraciones de datos en ClinicSay Backend.*
