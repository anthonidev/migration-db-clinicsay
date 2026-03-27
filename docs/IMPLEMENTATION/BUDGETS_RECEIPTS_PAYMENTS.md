# Guía de Implementación: Budgets, Receipts y Payments

**Fecha de última actualización:** 2026-03-11
**Versión del schema:** Compatible con Clinicsay 2026-03-11

---

## 📋 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Estructura de Budget Items](#estructura-de-budget-items)
3. [Flujos de Creación: BUDGET_FIRST vs CARE_PLAN_FIRST](#flujos-de-creación)
4. [Relación Budget ↔ Care Plan](#relación-budget--care-plan)
5. [Relación Receipt ↔ Budget](#relación-receipt--budget)
6. [Relación Payment ↔ Receipt](#relación-payment--receipt)
7. [Tipos de Receipt Items](#tipos-de-receipt-items)
8. [Verificación Post-Migración](#verificación-post-migración)
9. [Checklist para Nuevas Clínicas](#checklist-para-nuevas-clínicas)

---

## Introducción

Esta guía documenta los estándares de implementación para la migración de presupuestos (budgets), planes de tratamiento (care plans), recibos (receipts) y pagos (payments) desde sistemas externos hacia Clinicsay.

### Actualizaciones importantes (2026-03-11)

- **Budget Items**: Nueva estructura con campos de IVA y descuentos
- **Receipt Items**: Corrección de tipos para items sin referencias
- **Relaciones bidireccionales**: Budget-Care Plan con soporte para ambos flujos
- **Vinculaciones completas**: Receipt → Budget → Care Plan → Payment

---

## Estructura de Budget Items

### Campos Obligatorios (2026-03-11)

Todos los `budget_items` deben incluir estos campos en su estructura JSONB:

```python
{
    # Campos básicos (existentes)
    "id": "01XXXXXXXXXXXXXXXXXXXXXXXXX",  # ULID
    "type": "TREATMENT",  # o "PRODUCT", "PACK"
    "treatmentId": "01KJXXX...",  # según type
    "packDefinitionId": None,
    "productId": None,
    "nameSnapshot": "Nombre del tratamiento",
    "quantity": 1,
    "unitPrice": 212.0,
    "currency": "EUR",
    "metadata": None,

    # Campos de IVA (nuevos 2026-03-11)
    "hasTax": False,              # ¿Tiene IVA aplicado?
    "taxRate": 0,                 # Porcentaje de IVA (0-100)
    "priceWithTax": 212.0,        # Precio unitario con IVA
    "priceWithoutTax": 212.0,     # Precio unitario sin IVA

    # Campos de descuento (nuevos 2026-03-11)
    "discountType": None,         # "PERCENTAGE" | "FIXED" | None
    "discountValue": 0,           # Valor del descuento (% o monto fijo)
    "discountAmount": 0,          # Monto total del descuento

    # Campos de totales por línea (nuevos 2026-03-11)
    "lineSubtotal": 4876.0,       # quantity × unitPrice
    "lineTaxAmount": 0,           # Monto de IVA para esta línea
    "lineTotal": 4876.0,          # lineSubtotal - discountAmount + lineTaxAmount
}
```

### Cálculos Requeridos

```python
# 1. Calcular subtotal de línea
line_subtotal = round(unit_price * quantity, 2)

# 2. Calcular descuento
if discount_type == "PERCENTAGE":
    discount_amount = round(line_subtotal * (discount_value / 100), 2)
elif discount_type == "FIXED":
    discount_amount = round(discount_value, 2)
else:
    discount_amount = 0

# 3. Calcular IVA
if has_tax:
    price_without_tax = round(unit_price / (1 + tax_rate / 100), 2)
    price_with_tax = unit_price
    line_tax_amount = round((line_subtotal - discount_amount) * (tax_rate / 100), 2)
else:
    price_without_tax = unit_price
    price_with_tax = unit_price
    line_tax_amount = 0

# 4. Calcular total de línea
line_total = round(line_subtotal - discount_amount + line_tax_amount, 2)
```

### Ejemplo: MZL (sin IVA ni descuentos)

```python
# Datos históricos sin IVA ni descuentos
line_subtotal = round(212.0 * 23, 2)  # 4876.0
discount_amount = 0
line_tax_amount = 0
line_total = line_subtotal  # 4876.0

budget_item = {
    "id": generate_id(),
    "type": "TREATMENT",
    "treatmentId": treatment_id,
    "nameSnapshot": "Empaste",
    "quantity": 23,
    "unitPrice": 212.0,
    "currency": "EUR",

    # Sin IVA en datos históricos
    "hasTax": False,
    "taxRate": 0,
    "priceWithTax": 212.0,
    "priceWithoutTax": 212.0,

    # Sin descuentos por línea
    "discountType": None,
    "discountValue": 0,
    "discountAmount": 0,

    # Totales
    "lineSubtotal": 4876.0,
    "lineTaxAmount": 0,
    "lineTotal": 4876.0,
}
```

### Ejemplo: Essential Dental (con descuentos)

```python
# Datos con descuento porcentual del 10%
unit_price_original = 380.0
cantidad = 1
descuento_pct = 10

line_subtotal = round(unit_price_original * cantidad, 2)  # 380.0
discount_amount = round(line_subtotal * (descuento_pct / 100), 2)  # 38.0
line_tax_amount = 0
line_total = round(line_subtotal - discount_amount, 2)  # 342.0

budget_item = {
    "id": generate_id(),
    "type": "TREATMENT",
    "treatmentId": treatment_id,
    "nameSnapshot": "Implante dental",
    "quantity": 1,
    "unitPrice": 380.0,
    "currency": "EUR",

    # Sin IVA
    "hasTax": False,
    "taxRate": 0,
    "priceWithTax": 380.0,
    "priceWithoutTax": 380.0,

    # Con descuento porcentual
    "discountType": "PERCENTAGE",
    "discountValue": 10,
    "discountAmount": 38.0,

    # Totales
    "lineSubtotal": 380.0,
    "lineTaxAmount": 0,
    "lineTotal": 342.0,
}
```

---

## Flujos de Creación

Existen dos flujos de creación para budgets y care plans:

### 1. BUDGET_FIRST (Ejemplo: MZL)

**Descripción**: Los presupuestos se crean primero, y estos generan automáticamente sus care plans asociados.

**Características**:
- El budget se crea independiente
- El care plan se genera a partir del budget
- El care plan apunta al budget que lo originó

**Relaciones**:
```python
# Budget
budget = {
    "id": budget_id,
    "care_plan_id": None,  # Budget NO apunta al care plan
    "creation_flow": "BUDGET_FIRST",
    # ... otros campos
}

# Care Plan
care_plan = {
    "id": care_plan_id,
    "linked_budget_id": budget_id,  # Care plan SÍ apunta al budget
    "creation_flow": "BUDGET_FIRST",
    # ... otros campos
}
```

**Cuándo usar**:
- Clínicas que crean presupuestos detallados antes de iniciar tratamientos
- Sistemas fuente donde el presupuesto es el registro principal
- Datos históricos donde budget es el origen del plan de tratamiento

### 2. CARE_PLAN_FIRST (Ejemplo: Essential Dental)

**Descripción**: Los care plans se crean primero (típicamente desde citas), y los presupuestos se vinculan después.

**Características**:
- El care plan se crea desde otras fuentes (ej: citas)
- El budget se crea posteriormente y se vincula al care plan existente
- El budget apunta al care plan que lo precede

**Relaciones**:
```python
# Care Plan
care_plan = {
    "id": care_plan_id,
    "linked_budget_id": None,  # Care plan NO apunta al budget
    "creation_flow": "CARE_PLAN_FIRST",
    # ... otros campos
}

# Budget
budget = {
    "id": budget_id,
    "care_plan_id": care_plan_id,  # Budget SÍ apunta al care plan
    "creation_flow": "CARE_PLAN_FIRST",
    # ... otros campos
}
```

**Cuándo usar**:
- Clínicas que registran tratamientos planificados desde agenda
- Care plans generados automáticamente desde citas
- Presupuestos que se crean como formalización posterior

---

## Relación Budget ↔ Care Plan

### Tabla Comparativa

| Aspecto | BUDGET_FIRST (MZL) | CARE_PLAN_FIRST (Essential) |
|---------|-------------------|---------------------------|
| **Origen** | Budget es el registro principal | Care plan desde citas/agenda |
| **budget.care_plan_id** | `NULL` | `care_plan.id` |
| **care_plan.linked_budget_id** | `budget.id` | `NULL` |
| **Flujo típico** | Presupuesto → Care Plan → Tratamiento | Cita → Care Plan → Presupuesto |

### Implementación: BUDGET_FIRST

```python
# 1. Crear budget
budget = {
    "id": budget_id,
    "care_plan_id": None,  # IMPORTANTE: NULL en BUDGET_FIRST
    "creation_flow": "BUDGET_FIRST",
    "budget_number": generate_budget_number(),
    "patient_id": patient_id,
    # ... otros campos
}

# 2. Crear care plan vinculado
care_plan = {
    "id": generate_id(),
    "patient_id": patient_id,
    "linked_budget_id": budget_id,  # IMPORTANTE: apunta al budget
    "creation_flow": "BUDGET_FIRST",
    # ... otros campos
}

# 3. Vincular en diccionarios para receipts posteriores
segodont_to_budget[id_segodont] = budget_id
segodont_to_care_plan[id_segodont] = care_plan["id"]
```

### Implementación: CARE_PLAN_FIRST

```python
# 1. Crear care plan (desde citas)
care_plan = {
    "id": care_plan_id,
    "patient_id": patient_id,
    "linked_budget_id": None,  # IMPORTANTE: NULL en CARE_PLAN_FIRST
    "creation_flow": "CARE_PLAN_FIRST",
    # ... otros campos
}

# 2. Crear budget vinculado
budget = {
    "id": budget_id,
    "care_plan_id": care_plan_id,  # IMPORTANTE: apunta al care plan
    "creation_flow": "CARE_PLAN_FIRST",
    "budget_number": generate_budget_number(),
    "patient_id": patient_id,
    # ... otros campos
}
```

### Scripts de Verificación

```sql
-- Para BUDGET_FIRST (MZL)
-- Verificar que:
-- 1. budget.care_plan_id = NULL
-- 2. care_plan.linked_budget_id = budget.id
-- 3. Ambos tienen creation_flow = 'BUDGET_FIRST'

SELECT
    COUNT(*) AS budgets_incorrectos
FROM budget b
WHERE b.metadata->>'source' = 'migration'
  AND (b.care_plan_id IS NOT NULL OR b.creation_flow != 'BUDGET_FIRST');

SELECT
    COUNT(*) AS care_plans_sin_budget
FROM care_plan cp
WHERE cp.metadata->>'source' = 'migration'
  AND (cp.linked_budget_id IS NULL OR cp.creation_flow != 'BUDGET_FIRST');
```

```sql
-- Para CARE_PLAN_FIRST (Essential)
-- Verificar que:
-- 1. care_plan.linked_budget_id = NULL
-- 2. budget.care_plan_id = care_plan.id
-- 3. Ambos tienen creation_flow = 'CARE_PLAN_FIRST'

SELECT
    COUNT(*) AS care_plans_incorrectos
FROM care_plan cp
WHERE cp.metadata->>'source' = 'migration'
  AND (cp.linked_budget_id IS NOT NULL OR cp.creation_flow != 'CARE_PLAN_FIRST');

SELECT
    COUNT(*) AS budgets_sin_care_plan
FROM budget b
WHERE b.metadata->>'source' = 'migration'
  AND (b.care_plan_id IS NULL OR b.creation_flow != 'CARE_PLAN_FIRST');
```

---

## Relación Receipt ↔ Budget

Los receipts (recibos/cobros) deben vincularse al budget que los originó usando `related_budget_id`.

### Implementación

```python
# 1. Durante creación de budgets/care plans, crear diccionario de vinculación
segodont_to_budget = {}  # id_segodont → budget_id

# Al crear cada planned_session desde presupuestos
if id_segodont:
    segodont_to_budget[id_segodont] = budget_id

# 2. Al crear receipts, buscar el budget correspondiente
related_budget_id = None

# Buscar en los registros del grupo de cobro
for row in cobro_group:
    seg = row.get("id_segodont", "").strip()
    if seg and seg in segodont_to_budget:
        related_budget_id = segodont_to_budget[seg]
        break

# 3. Asignar al receipt
receipt = {
    "id": receipt_id,
    "patient_id": patient_id,
    "related_care_plan_id": care_plan_id,
    "related_budget_id": related_budget_id,  # IMPORTANTE: vinculación
    # ... otros campos
}
```

### Campo de Vinculación en CSV

La vinculación se realiza mediante un campo común en los archivos fuente:

- **MZL**: `id_segodont` en presupuestos y cobros
- **Essential**: Equivalente según estructura de archivos fuente

### Verificación

```sql
-- Verificar vinculación receipt-budget
SELECT
    COUNT(*) AS total_receipts,
    COUNT(related_budget_id) AS con_budget,
    COUNT(*) - COUNT(related_budget_id) AS sin_budget
FROM receipt
WHERE metadata->>'source' = 'migration'
  AND clinic_id = 'CLINIC_ID_AQUI';

-- Verificar que budgets vinculados existen
SELECT COUNT(*) AS receipts_con_budget_invalido
FROM receipt r
LEFT JOIN budget b ON b.id = r.related_budget_id
WHERE r.related_budget_id IS NOT NULL
  AND b.id IS NULL
  AND r.metadata->>'source' = 'migration';
```

---

## Control de Montos en Receipts

Los receipts deben mantener control preciso de montos pagados y pendientes mediante los campos `amount_paid` y `amount_pending`.

### Campos Obligatorios

```python
receipt = {
    # ... otros campos
    "total": 150.0,              # Total del recibo
    "amount_paid": 150.0,        # Monto ya pagado
    "amount_pending": 0,         # Monto pendiente de pago
    "receipt_status": "PAID",    # PAID | PENDING
    "paid_at": fecha_pago,       # Fecha de pago (si está pagado)
}
```

### Reglas de Negocio

| Estado | amount_paid | amount_pending | paid_at | Fórmula |
|--------|-------------|----------------|---------|---------|
| **PAID** | = total | 0 | Fecha de pago | `amount_paid + amount_pending = total` |
| **PENDING** | 0 | = total | NULL | `amount_paid + amount_pending = total` |

### Implementación

```python
# Calcular campos según estado de pago
total_amount = round(total_cobro, 2)

if cobrado == "1":  # Pagado
    amount_paid = total_amount
    amount_pending = 0
    paid_at = fecha_cobro
    receipt_status = "PAID"
else:  # Pendiente
    amount_paid = 0
    amount_pending = total_amount
    paid_at = None
    receipt_status = "PENDING"

receipt = {
    "id": generate_id(),
    # ... otros campos
    "receipt_status": receipt_status,
    "total": total_amount,
    "amount_paid": amount_paid,
    "amount_pending": amount_pending,
    "paid_at": paid_at,
}
```

### Verificación

```sql
-- 1. Verificar receipts PAID
SELECT COUNT(*) AS incorrectos
FROM receipt
WHERE receipt_status = 'PAID'
  AND (amount_paid != total OR amount_pending != 0)
  AND metadata->>'source' = 'migration';
-- Esperado: 0

-- 2. Verificar receipts PENDING
SELECT COUNT(*) AS incorrectos
FROM receipt
WHERE receipt_status = 'PENDING'
  AND (amount_paid != 0 OR amount_pending != total)
  AND metadata->>'source' = 'migration';
-- Esperado: 0

-- 3. Verificar consistencia general
SELECT COUNT(*) AS inconsistentes
FROM receipt
WHERE (amount_paid + amount_pending) != total
  AND metadata->>'source' = 'migration';
-- Esperado: 0
```

---

## Relación Payment ↔ Receipt

Los payments pueden generarse desde dos fuentes:

1. **Billing Documents** (facturas): Con `payment_allocation`
2. **Receipts** (cobros directos): Con `receipt_id`, SIN `payment_allocation`

### Consistencia Receipt-Payment

Cuando un receipt está PAID y tiene un payment asociado:
- `receipt.amount_paid` debe ser igual a `payment.amount`
- `receipt.receipt_status` debe ser `"PAID"`
- `payment.receipt_id` debe apuntar al receipt
- `receipt.paid_at` debe coincidir con `payment.paid_at`

### Implementación: Payments desde Receipts

```python
# Al generar receipts, verificar si está pagado
cobrado = first_row.get("cobrado", "0").strip()

if cobrado == "1" and total_cobro > 0:
    fecha_cobro = parse_date(first_row.get("fecha"))
    forma_pago_cobro = first_row.get("forma_pago", "").strip()

    # Crear payment vinculado al receipt
    payment = {
        "id": generate_id(),
        "clinic_id": CLINIC_ID,
        "billing_client_id": bc_id,
        "amount": round(total_cobro, 2),
        "currency": "EUR",
        "payment_status": "CAPTURED",
        "paid_at": fecha_cobro,
        "refunded_amount": 0,
        "notes": None,
        "created_by_user_id": None,

        # IMPORTANTE: vinculación al receipt
        "receipt_id": receipt["id"],

        "metadata": {
            "source": "migration",
            "source_id_cobro": id_cobro,
            "forma_pago": forma_pago_cobro if forma_pago_cobro else None,
        },
        "record_status": "ACTIVE",
        "record_metadata": None,
        "created_at": fecha_cobro or now,
        "updated_at": now,
    }

    receipt_payments.append(payment)
```

### Combinar Payments de Ambas Fuentes

```python
# Al final del proceso de extracción
all_payments = []

# 1. Payments desde billing_documents (facturas)
all_payments.extend(fase4["payments"])

# 2. Payments desde receipts (cobros directos)
all_payments.extend(fase5["receipt_payments"])

# 3. Guardar todos juntos
return {
    # ... otras entidades
    "payments": all_payments,
}
```

### Características de Payments desde Receipts

- **Tienen** `receipt_id` poblado
- **NO tienen** `payment_allocation` (no se asignan a billing_documents)
- `payment_status` = `"CAPTURED"` (ya cobrado)
- `paid_at` = fecha del cobro en el CSV
- `amount` = total del receipt

### Verificación

```sql
-- Resumen de payments por origen
SELECT
    CASE
        WHEN receipt_id IS NOT NULL THEN 'Desde Receipts (cobros.csv)'
        ELSE 'Desde Billing Documents (facturas.csv)'
    END AS origen,
    COUNT(*) AS total_payments,
    SUM(amount) AS total_amount
FROM payment
WHERE metadata->>'source' = 'migration'
  AND clinic_id = 'CLINIC_ID_AQUI'
GROUP BY origen;

-- Verificar que NO hay payments duplicados (con receipt Y billing_document)
SELECT COUNT(*) AS payments_duplicados
FROM payment p
JOIN payment_allocation pa ON pa.payment_id = p.id
WHERE p.receipt_id IS NOT NULL
  AND p.metadata->>'source' = 'migration';

-- Esperado: 0
```

---

## Tipos de Receipt Items

Los `receipt_items` deben tener el tipo correcto según su contenido.

### Reglas de Tipo

```python
# Determinar tipo según referencias
if treatment_id:
    receipt_item_type = "TREATMENT"
elif product_id:
    receipt_item_type = "PRODUCT"
elif pack_definition_id:
    receipt_item_type = "PACK"
else:
    # Sin referencias = item personalizado
    receipt_item_type = "OTHER"
```

### Implementación

```python
# Crear receipt_item
receipt_item = {
    "id": generate_id(),
    "receipt_id": receipt["id"],

    # Tipo según contenido
    "receipt_item_type": "OTHER",  # Sin treatment/product/pack

    # Referencias (todas NULL si es OTHER)
    "treatment_id": None,
    "product_id": None,
    "pack_definition_id": None,

    # Resto de campos
    "schedule_block_id": sb_id,
    "description": concepto or "Item personalizado",
    "quantity": cantidad,
    "unit_price": precio_unitario,
    "line_discount": descuento_linea,
    "line_total": total_linea,
    "metadata": None,
    "record_status": "ACTIVE",
}
```

### Estructura SQL de INSERT

```sql
INSERT INTO receipt_item (
    id, receipt_id, receipt_item_type,
    treatment_id, product_id, pack_definition_id,
    schedule_block_id, description,
    quantity, unit_price, line_discount, line_total,
    metadata, record_status
) VALUES (
    %s, %s, %s,
    %s, %s, %s,
    %s, %s,
    %s, %s, %s, %s,
    %s, %s
)
```

---

## Verificación Post-Migración

### Scripts SQL Recomendados

Crear en `clinics/{clinic_name}/scripts/`:

1. **verify_budget_careplan_relation.sql**
   - Verifica relación budget-care_plan según flujo
   - Detecta inconsistencias en `linked_budget_id` o `care_plan_id`

2. **verify_receipt_budget_relation.sql**
   - Verifica que receipts con `related_budget_id` apunten a budgets válidos
   - Detecta receipts huérfanos sin budget

3. **verify_payment_receipt_relation.sql**
   - Verifica que payments con `receipt_id` apunten a receipts válidos
   - Detecta inconsistencias de montos
   - Detecta payments duplicados (con receipt Y billing_document)

### Ejemplo: verify_payment_receipt_relation.sql

```sql
-- Resumen de payments por origen
SELECT
    CASE
        WHEN receipt_id IS NOT NULL THEN 'Desde Receipts (cobros.csv)'
        ELSE 'Desde Billing Documents (facturas.csv)'
    END AS origen,
    COUNT(*) AS total_payments,
    SUM(amount) AS total_amount,
    AVG(amount) AS promedio_amount
FROM payment
WHERE metadata->>'source' = 'migration'
  AND clinic_id = '{CLINIC_ID}'
GROUP BY origen;

-- Verificar receipts vinculados son válidos
SELECT COUNT(*) AS payments_con_receipt_invalido
FROM payment p
LEFT JOIN receipt r ON r.id = p.receipt_id
WHERE p.receipt_id IS NOT NULL
  AND r.id IS NULL
  AND p.metadata->>'source' = 'migration'
  AND p.clinic_id = '{CLINIC_ID}';
-- Esperado: 0

-- Verificar consistencia de montos
SELECT COUNT(*) AS inconsistencias_monto
FROM receipt r
JOIN payment p ON p.receipt_id = r.id
WHERE r.total != p.amount
  AND r.metadata->>'source' = 'migration'
  AND r.clinic_id = '{CLINIC_ID}';
-- Esperado: 0

-- Payments duplicados (con receipt Y billing_document)
SELECT COUNT(*) AS payments_duplicados
FROM payment p
JOIN payment_allocation pa ON pa.payment_id = p.id
WHERE p.receipt_id IS NOT NULL
  AND p.metadata->>'source' = 'migration'
  AND p.clinic_id = '{CLINIC_ID}';
-- Esperado: 0
```

---

## Checklist para Nuevas Clínicas

### 1. Análisis Inicial

- [ ] Identificar si la clínica usa presupuestos (budgets)
- [ ] Identificar si la clínica usa recibos/cobros (receipts)
- [ ] Identificar si los pagos vienen de facturas, cobros, o ambos
- [ ] Determinar flujo de creación: BUDGET_FIRST o CARE_PLAN_FIRST
- [ ] Identificar campo de vinculación en archivos fuente (ej: id_segodont)

### 2. Estructura de Budget Items

- [ ] Agregar todos los campos obligatorios de 2026-03-11
- [ ] Implementar cálculos de IVA si los datos fuente lo incluyen
- [ ] Implementar cálculos de descuentos si los datos fuente lo incluyen
- [ ] Validar que `lineTotal = lineSubtotal - discountAmount + lineTaxAmount`
- [ ] Usar `hasTax: False` y `taxRate: 0` para datos históricos sin IVA

### 3. Relación Budget-Care Plan

**Si BUDGET_FIRST:**
- [ ] `budget.care_plan_id = NULL`
- [ ] `care_plan.linked_budget_id = budget.id`
- [ ] Ambos con `creation_flow = "BUDGET_FIRST"`

**Si CARE_PLAN_FIRST:**
- [ ] `care_plan.linked_budget_id = NULL`
- [ ] `budget.care_plan_id = care_plan.id`
- [ ] Ambos con `creation_flow = "CARE_PLAN_FIRST"`

### 4. Control de Montos en Receipts

- [ ] Implementar cálculo de `amount_paid` según estado del receipt
- [ ] Implementar cálculo de `amount_pending` según estado del receipt
- [ ] PAID: `amount_paid = total`, `amount_pending = 0`
- [ ] PENDING: `amount_paid = 0`, `amount_pending = total`
- [ ] Validar: `amount_paid + amount_pending = total` siempre
- [ ] `paid_at` solo si receipt está PAID, NULL si PENDING

### 5. Receipt Items

- [ ] Tipo `"TREATMENT"` si tiene `treatment_id`
- [ ] Tipo `"PRODUCT"` si tiene `product_id`
- [ ] Tipo `"PACK"` si tiene `pack_definition_id`
- [ ] Tipo `"OTHER"` si no tiene ninguna referencia
- [ ] Incluir campos `product_id` y `pack_definition_id` en INSERT

### 6. Vinculación Receipt-Budget

- [ ] Crear diccionario `segodont_to_budget` durante creación de budgets
- [ ] Poblar `receipt.related_budget_id` usando campo de vinculación
- [ ] Validar que budgets vinculados existen
- [ ] Verificar consistencia con `care_plan.linked_budget_id`

### 7. Vinculación Payment-Receipt

- [ ] Identificar si hay pagos directos (cobros.csv o similar)
- [ ] Generar payments con `receipt_id` para receipts pagados
- [ ] NO crear `payment_allocation` para payments de receipts
- [ ] Combinar payments de facturas y receipts en un solo array
- [ ] Validar que `payment.amount = receipt.amount_paid`
- [ ] Validar consistencia: receipt PAID → payment existe

### 8. Scripts de Verificación

- [ ] Crear `verify_budget_careplan_relation.sql`
- [ ] Crear `verify_receipt_budget_relation.sql` (si aplica)
- [ ] Crear `verify_payment_receipt_relation.sql` (si aplica)
- [ ] Crear `verify_receipt_amounts.sql` (si tiene receipts)
- [ ] Documentar orden de ejecución en README.md local

### 9. Documentación

- [ ] Actualizar `commands.yaml` con todos los comandos de migración
- [ ] Documentar flujo específico de la clínica en README local
- [ ] Incluir ejemplos de estructuras de datos en comentarios
- [ ] Documentar particularidades del sistema fuente

---

## Referencias

- **Schema SQL**: `schema/clinicsay_schema.sql`
- **Schema Prisma**: `docs/schema.prisma`
- **Documentación de dominio**: `docs/DOMAIN/`
- **Changelog global**: `CHANGELOG_2026-03-11.md`
- **Ejemplo BUDGET_FIRST**: `clinics/mzl/migrations/extract_care_plans.py`
- **Ejemplo CARE_PLAN_FIRST**: `clinics/essential/migrations/extract_budgets.py`
- **Scripts de verificación**: `clinics/mzl/scripts/`

---

**Última actualización**: 2026-03-11
**Mantenido por**: Equipo de Migración Clinicsay
