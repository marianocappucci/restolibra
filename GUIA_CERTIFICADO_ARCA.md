# Guía: Generar y Configurar Certificado en ARCA

## PASO 1: Generar la Clave Privada y CSR (en tu PC)

Abre una terminal en Linux/Mac o PowerShell en Windows y ejecuta:

### 1.1 Generar clave privada (2048 bits):
```bash
openssl genrsa -out clave.key 2048
```

**Resultado**: Se crea `clave.key` (guardá bien este archivo)

### 1.2 Generar el CSR (Certificate Signing Request):

Reemplaza los valores con tu información:

```bash
openssl req -new \
-key clave.key \
-subj "/C=AR/O=compulibra/CN=sistemas_remitos/serialNumber=CUIT 20289933604" \
-out pedido.csr
```

**Campos a personalizar**:
- `O=compulibra` → Nombre de tu empresa
- `CN=sistemas_remitos` → Nombre descriptivo del sistema (puedes cambiar)
- `serialNumber=CUIT 20289933604` → Tu CUIT SIN GUIONES

**Resultado**: Se crea `pedido.csr` (esto es lo que subirás a ARCA)

---

## PASO 2: Ingresar a ARCA y Subir el CSR

### 2.1 Acceder al portal

1. Abre https://www.arca.gob.ar
2. Ingresa con tu **clave fiscal** (nivel 3 o superior)
3. Una vez adentro, busca: **"Administración de Certificados Digitales"**

### 2.2 Crear un nuevo certificado

En ese servicio:

1. Click en **"Crear Nuevo Alias"** (o similar)
2. Dale un nombre descriptivo al certificado
   - Ej: `sistemaremitos_2024`
3. En el campo de archivo, sube `pedido.csr` (el que generaste)
4. Confirma

**Estado esperado**: El certificado quedará en estado "Pendiente de Firma" o similar

### 2.3 ARCA firma el certificado

ARCA tardará algunos minutos a horas:
- Valida el CSR
- Genera el certificado
- Lo deja disponible para descargar

Verifica en "Mis Certificados" cuando cambie el estado a **"Activo"** o "Disponible"

---

## PASO 3: Descargar el Certificado

Una vez activo:

1. Ve a **"Mis Certificados"**
2. Busca el alias que creaste
3. Click en **Descargar** (o el botón correspondiente)
4. Se descargará un archivo: `alias.crt`

**Ahora tienes**:
- `clave.key` (clave privada — CONFIDENCIAL)
- `alias.crt` (certificado público)

---

## PASO 4: Asociar al Webservice WSFE

Esto es **MUY IMPORTANTE** — sin esto no funciona la facturación.

### 4.1 Ir a "Administrador de Relaciones de Clave Fiscal"

1. En el menú de ARCA
2. Busca **"Administrador de Relaciones de Clave Fiscal"**

### 4.2 Crear nueva relación

1. Click en **"Crear Nueva Relación"** (o similar)
2. Busca y selecciona:
   - **Entidad**: ARCA
   - **Servicio**: Webservices
   - **Operación**: Factura Electrónica (WSFE / wsfe)
3. Selecciona el **certificado** (alias que creaste)
4. Confirma

**Resultado**: Tu certificado ahora está habilitado para usar el webservice de Facturación Electrónica

---

## PASO 5: Guardar los Archivos en tu Proyecto

Una vez descargados, copialos al proyecto:

```bash
# En tu proyecto remitos/
mkdir -p certs/
cp clave.key certs/
cp alias.crt certs/
```

**Estructura final**:
```
remitos/
├── certs/
│   ├── clave.key      (clave privada)
│   └── alias.crt      (certificado)
├── gui.py
├── database.py
└── ...
```

---

## PASO 6: Crear Clave Protegida para Python (Opcional pero Recomendado)

Si quieres proteger la clave con contraseña:

```bash
openssl pkcs8 -in clave.key -out clave.pem -topk8 -v2 des3
```

Te pedirá contraseña, ingrésala.

**Resultado**: `clave.pem` (clave protegida)

---

## ⚠️ Certificados de Homologación vs Producción

**IMPORTANTE**: ARCA tiene dos ambientes diferentes.

Necesitarás **DOS certificados**:

### Certificado de HOMOLOGACIÓN (testing)
- Se crea en el entorno de homologación de ARCA
- URL: https://wswhomo.afip.gov.ar
- Se usa para probar

### Certificado de PRODUCCIÓN
- Se crea en el entorno de producción
- URL: https://servicios1.afip.gov.ar
- Se usa cuando estés seguro de que funciona todo

**Procedimiento**: Repite los PASOS 1-5 en CADA entorno.

---

## Verificación

Para verificar que el certificado es válido:

```bash
openssl x509 -in alias.crt -text -noout
```

Debería mostrar:
- Subject: con tu O (empresa) y CN
- Validity: fechas de validez
- Public Key: la clave pública

---

## 📋 Checklist Antes de Programar

Completá esto para confirmar que todo está listo:

- [ ] Generé `clave.key` localmente
- [ ] Generé y subí `pedido.csr` a ARCA
- [ ] Descargué el certificado `alias.crt` desde ARCA
- [ ] El certificado está en estado "Activo" en ARCA
- [ ] Asocié el certificado a WSFE en "Administrador de Relaciones"
- [ ] Copié `clave.key` y `alias.crt` a la carpeta `certs/` del proyecto
- [ ] Tengo el CUIT, punto de venta y alias del certificado anotados

**Una vez todo esté listo, avisame y empezamos con el código.**

---

## Notas de Seguridad

⚠️ **IMPORTANTE**:
- `clave.key` es tu identidad digital — **NO la compartas, no la versionés en Git**
- Agregá `certs/` a `.gitignore`
- El certificado tiene validez limitada (generalmente 1 año) — guarda la fecha de vencimiento

```bash
# .gitignore
certs/
*.key
*.pem
```

---

## Servicio de Consulta de Padrón (Consultar CUIT de cliente)

El botón **"Consultar ARCA"** en el alta de clientes usa el webservice **`ws_sr_padron_a13`** (Padrón Alcance 13).

> ⚠️ ARCA discontinuó el Padrón Alcance 4 (`ws_sr_padron_a4`). El servicio vigente es el **Alcance 13**.

### Habilitar el servicio para tu certificado

1. Ingresá a **https://www.arca.gob.ar** con tu clave fiscal
2. Andá a **Administrador de Relaciones de Clave Fiscal**
3. Click en **Nueva Relación**
4. Completá:
   - **Entidad**: ARCA
   - **Servicio**: ws_sr_padron_a13 — Consulta a Padrón Alcance 13
   - **Representado**: tu CUIT
   - **Certificado**: el alias que ya creaste
5. Confirmá

Una vez delegado, el botón "Consultar ARCA" en el formulario de clientes va a completar automáticamente nombre, domicilio y condición frente al IVA.

### Datos que devuelve

| Campo | Fuente en A13 |
|-------|--------------|
| Nombre / Razón Social | nodo nombre / apellido / razonSocial |
| Domicilio fiscal | nodo domicilio con tipoDomicilio=FISCAL |
| Condición IVA | nodo categoriaMonotributo o impuesto (id 32/33/34) |
| Estado clave | nodo estadoClave (ACTIVO / INACTIVO) |
