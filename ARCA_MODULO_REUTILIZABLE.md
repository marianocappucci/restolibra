# Módulo de Facturación Electrónica ARCA — Documentación Reutilizable

Documentación completa del sistema de facturación electrónica integrado con ARCA/AFIP.
Apto para reutilizar en cualquier sistema Python/FastAPI propio.

---

## Índice

1. [Arquitectura General](#1-arquitectura-general)
2. [Procedimiento de Certificados](#2-procedimiento-de-certificados)
3. [Módulo WSAA — Autenticación](#3-módulo-wsaa--autenticación)
4. [Módulo WSFE — Facturación](#4-módulo-wsfe--facturación)
5. [Generación de PDF](#5-generación-de-pdf)
6. [Esquema de Base de Datos](#6-esquema-de-base-de-datos)
7. [Integración en el Router Web](#7-integración-en-el-router-web)
8. [Tipos de Comprobantes](#8-tipos-de-comprobantes)
9. [Reglas de Negocio Críticas](#9-reglas-de-negocio-críticas)
10. [Dependencias y Docker](#10-dependencias-y-docker)
11. [Verificación y Debug](#11-verificación-y-debug)
12. [Checklist de Setup Nuevo Sistema](#12-checklist-de-setup-nuevo-sistema)

---

## 1. Arquitectura General

```
[Usuario Web] → [FastAPI Router] → [WSAA] → token+sign
                                 → [WSFE] → CAE
                                 → [DB SQLite] ← guarda factura + CAE
                                 → [pdf_generator] → PDF físico
```

### Archivos del módulo

| Archivo | Responsabilidad |
|---------|----------------|
| `arca_wsaa.py` | Autenticación WSAA: genera TRA, firma con openssl smime, obtiene token+sign |
| `arca_wsfe.py` | WSFE: solicitar CAE (`FECAESolicitar`), último número (`FECompUltimoAutorizado`) |
| `pdf_generator.py` | Generación de PDF con fpdf2 — diseño moderno con teal y QR ARCA |
| `database.py` | CRUD facturas, tabla `arca_config` |
| `web/routers/facturas.py` | Endpoints FastAPI: crear, ver, PDF, reintentar CAE, NC, ND |

---

## 2. Procedimiento de Certificados

### 2.1 Generar clave privada y CSR

```bash
# Clave privada RSA 2048 bits
openssl genrsa -out clave_privada.key 2048

# CSR — reemplazar O y serialNumber con los datos reales
openssl req -new \
  -key clave_privada.key \
  -subj "/C=AR/O=NombreEmpresa/CN=nombre_sistema/serialNumber=CUIT 20XXXXXXXXX0" \
  -out pedido.csr
```

**Campos del subject:**
- `O` = Razón social de la empresa
- `CN` = Nombre descriptivo del sistema (libre)
- `serialNumber` = `CUIT ` + CUIT sin guiones (ej: `CUIT 20289933604`)

### 2.2 Portal ARCA — Crear certificado

1. Ingresar a https://www.arca.gob.ar con clave fiscal nivel 3+
2. **Administración de Certificados Digitales** → Crear Nuevo Alias
3. Subir `pedido.csr`, asignar nombre descriptivo
4. Esperar que el estado pase a "Activo" (minutos/horas)
5. Descargar el `.crt` resultante

### 2.3 Asociar al Webservice WSFE

1. **Administrador de Relaciones de Clave Fiscal**
2. Nueva relación: Entidad=ARCA, Servicio=Webservices, Operación=`wsfe`
3. Seleccionar el certificado creado

### 2.4 Validar antes de usar

```bash
# Ver fechas de validez
openssl x509 -in certificado.crt -noout -subject -dates

# Verificar que la clave corresponde al certificado
openssl x509 -in certificado.crt -pubkey -noout > /tmp/pub_cert.pem
openssl pkey -in clave_privada.key -pubout > /tmp/pub_key.pem
diff /tmp/pub_cert.pem /tmp/pub_key.pem  # debe ser vacío (sin diff)

# Test de firma (debe terminar con exit 0)
echo "test" > /tmp/test.txt
openssl smime -sign \
  -in /tmp/test.txt \
  -signer certificado.crt \
  -inkey clave_privada.key \
  -outform DER -nodetach -md sha1 \
  -out /tmp/firma.der
echo "Exit code: $?"
```

### 2.5 Archivos a guardar con seguridad

```
arca_certs/
├── clave_privada.key   ← CONFIDENCIAL — nunca en git
└── certificado.crt     ← Público pero proteger
```

Agregar a `.gitignore`:
```
arca_certs/
*.key
*.pem
```

---

## 3. Módulo WSAA — Autenticación

**Archivo:** `arca_wsaa.py`

### Flujo de autenticación

```
1. Generar TRA (Ticket de Requerimiento de Acceso) — XML con UniqueId + tiempos
2. Firmar TRA con openssl smime (SHA1, DER, nodetach)
3. Enviar CMS firmado al endpoint WSAA via SOAP
4. Recibir loginCmsReturn → extraer token y sign
```

### URLs

```python
WSAA_URL = {
    "homologacion": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
    "produccion":   "https://wsaa.afip.gov.ar/ws/services/LoginCms",
}
```

### Firma del TRA — detalle crítico

La firma usa `openssl smime` con parámetros específicos requeridos por ARCA:

```python
subprocess.run([
    "openssl", "smime", "-sign",
    "-in",      tra_file,       # XML del TRA
    "-signer",  cert_path,      # .crt — va PRIMERO
    "-inkey",   key_path,       # .key — va SEGUNDO
    "-outform", "DER",
    "-nodetach",                # contenido embebido (requerido por ARCA)
    "-md",      "sha1",         # SHA1 (no SHA256) — requerido por ARCA
])
```

⚠️ **Importante**: el orden es `cert_path` primero, `key_path` segundo.

### Uso

```python
import arca_wsaa

ta = await arca_wsaa.autenticar(
    cert_path  = "/ruta/certificado.crt",
    key_path   = "/ruta/clave_privada.key",
    ambiente   = "produccion",   # o "homologacion"
    servicio   = "wsfe",
)
# ta = {"token": "...", "sign": "...", "expiracion": "..."}
```

### Token válido por ~12 horas

El token de WSAA tiene larga duración. En producción se puede cachear en sesión/memoria y reutilizarlo; solo regenerar si hay error de autenticación.

---

## 4. Módulo WSFE — Facturación

**Archivo:** `arca_wsfe.py`

### URLs

```python
WSFE_URL = {
    "homologacion": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
    "produccion":   "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
}
```

### SSL — Problema conocido con ARCA

Los servidores de ARCA usan parámetros DH legacy. Sin configuración especial httpx falla.
Solución implementada:

```python
import ssl

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.set_ciphers("ALL:@SECLEVEL=0")
    return ctx

# Usar en cada llamada:
async with httpx.AsyncClient(verify=_ssl_ctx(), timeout=30) as client:
    ...
```

### Obtener último número autorizado

```python
ultimo = await arca_wsfe.ultimo_numero_autorizado(
    punto_venta  = 5,
    tipo         = 11,            # código de tipo de comprobante
    empresa_cuit = "20-28993360-4",
    token        = ta["token"],
    sign         = ta["sign"],
    ambiente     = "produccion",
)
numero = ultimo + 1
```

⚠️ Siempre obtener el número de ARCA (no de la DB local) para evitar duplicados.

### Solicitar CAE

```python
cae_data = await arca_wsfe.solicitar_cae(
    factura      = factura_dict,   # ver estructura abajo
    empresa_cuit = "20-28993360-4",
    token        = ta["token"],
    sign         = ta["sign"],
    ambiente     = "produccion",
)
# cae_data = {"cae": "86195016627137", "cae_vto": "20260521"}
```

### Estructura del dict `factura` para WSFE

```python
factura = {
    "tipo":           11,           # código ARCA (ver tabla tipos)
    "punto_venta":    5,
    "numero":         1,            # número obtenido de ultimo_numero_autorizado + 1
    "fecha":          "2026-05-12", # YYYY-MM-DD
    "concepto":       2,            # 1=Productos, 2=Servicios, 3=Ambos
    "cliente_cuit":   "30-12345678-9",
    "subtotal":       100000.0,
    "iva_amount":     0.0,          # 0 para Factura C / monotributistas
    "total":          100000.0,
    # Solo si concepto == 2 o 3:
    "fch_serv_desde": "2026-05-01",
    "fch_serv_hasta": "2026-05-31",
    "fch_vto_pago":   "2026-06-15",
    # Solo para NC/ND — referencia al comprobante original:
    "cbte_asoc_tipo": 11,
    "cbte_asoc_pv":   5,
    "cbte_asoc_nro":  1,
}
```

### Lógica de importes según tipo

```python
_TIPOS_C = {11, 12, 13}  # Factura C, ND-C, NC-C

if tipo in _TIPOS_C:
    # Factura C: todo el importe va como ImpNeto, IVA = 0
    imp_neto = total
    imp_iva  = 0
    imp_opex = 0
    # NO incluir bloque <Iva> de alícuotas
elif iva_rate > 0:
    # Factura A/B con IVA: neto + IVA separados
    imp_neto = subtotal
    imp_iva  = iva_amount
    imp_opex = 0
    # SÍ incluir bloque <Iva><AlicIva><Id>...</Id>...
else:
    # Factura A/B sin IVA: todo como operación exenta
    imp_neto = 0
    imp_iva  = 0
    imp_opex = subtotal
```

### IDs de alícuotas IVA

```python
_IVA_ID = {0: 3, 10: 4, 10.5: 4, 21: 5, 27: 6}
```

### Verificar un comprobante ya emitido (FECompConsultar)

```python
body = f'''<FECompConsultar xmlns="{_NS}">
  {_auth(token, sign, cuit)}
  <FeCompConsReq>
    <CbteTipo>{tipo}</CbteTipo>
    <PtoVta>{pv}</PtoVta>
    <CbteNro>{nro}</CbteNro>
  </FeCompConsReq>
</FECompConsultar>'''
resp = await _soap(url, "FECompConsultar", body)
cae = resp.find('.//{http://ar.gov.afip.dif.FEV1/}CodAutorizacion').text
```

⚠️ El tag correcto es `<FeCompConsReq>` (no `<FeConsReq>` que da error).

---

## 5. Generación de PDF

**Archivo:** `pdf_generator.py`  
**Librería:** `fpdf2>=2.7.9`

### Diseño moderno (implementado 2026-05)

- **Paleta:** teal `(44,122,123)`, oscuro `(28,28,28)`, notas azul `(224,237,244)`
- **Cabecera:** logo (izq) o nombre empresa | caja oscura con letra + título + código + sub-box PV/N°/Fecha (der)
- **Emisor|Cliente:** dos columnas con header teal
- **Tabla ítems:** header teal, título bold + detalle italic, filas alternadas
- **Totales:** caja notas (izq) + Subtotal/IVA/Otros/Total con fila oscura (der)
- **Footer factura:** CAE/CAI + QR ARCA/AFIP

### Clases disponibles

```python
from pdf_generator import (
    generate_pdf_factura,       # Facturas A/B/C + NC + ND
    generate_pdf_presupuesto,   # Presupuestos
    generate_pdf,               # Remitos
)
```

### Nota sobre logo

Si hay logo cargado, **no** se muestra el nombre de la empresa en la cabecera
(solo en el bloque EMISOR). El nombre solo aparece en texto si no hay logo.

### QR ARCA

El QR se genera automáticamente cuando hay CAE. Formato AFIP estándar:

```python
data = {
    "ver": 1, "fecha": "YYYY-MM-DD",
    "cuit": 20289933604,
    "ptoVta": 5, "tipoCmp": 11, "nroCmp": 1,
    "importe": 100000.0, "moneda": "PES", "ctz": 1,
    "tipoDocRec": 80,  # 80=CUIT, 99=consumidor final
    "nroDocRec": 30123456789,
    "tipoCodAut": "E",
    "codAut": 86195016627137,  # CAE como entero
}
url = "https://www.afip.gob.ar/fe/qr/?p=" + base64.b64encode(json.dumps(data).encode()).decode()
```

---

## 6. Esquema de Base de Datos

### Tabla `facturas`

```sql
CREATE TABLE facturas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            INTEGER NOT NULL,      -- código ARCA (11=FC, 13=NC-C, etc.)
    punto_venta     INTEGER NOT NULL,
    numero          INTEGER NOT NULL,
    fecha           TEXT NOT NULL,         -- YYYY-MM-DD
    cliente_cuit    TEXT,
    cliente_razon   TEXT,
    cliente_iva_cond INTEGER,
    cliente_domicilio TEXT,
    items           TEXT,                  -- JSON
    subtotal        REAL,
    iva_amount      REAL,
    total           REAL,
    concepto        INTEGER DEFAULT 1,     -- 1=Prod, 2=Serv, 3=Ambos
    cae             TEXT,                  -- 14 dígitos, NULL si pendiente
    cae_vto         TEXT,                  -- YYYYMMDD
    observaciones   TEXT,
    pdf_path        TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    -- Campos para NC/ND:
    cbte_asoc_tipo  INTEGER,
    cbte_asoc_pv    INTEGER,
    cbte_asoc_nro   INTEGER,
    -- Campos de período de servicio:
    fch_serv_desde  TEXT,
    fch_serv_hasta  TEXT,
    fch_vto_pago    TEXT
);
```

### Tabla `arca_config`

```sql
CREATE TABLE arca_config (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa          TEXT DEFAULT 'default',
    cuit             TEXT NOT NULL,
    punto_venta      INTEGER NOT NULL,
    clave_path       TEXT NOT NULL,        -- ruta a .key
    certificado_path TEXT NOT NULL,        -- ruta a .crt
    ambiente         TEXT DEFAULT 'homologacion',  -- o 'produccion'
    activo           INTEGER DEFAULT 1,
    alias            TEXT,
    created_at       TEXT,
    updated_at       TEXT
);
```

---

## 7. Integración en el Router Web

### Patrón de flujo completo al crear una factura

```python
# 1. Cargar config ARCA
arca_cfg = db.obtener_todas_arca_configs()
arca = arca_cfg[0] if arca_cfg else None

# 2. Autenticar y obtener número correlativo de ARCA
ta = None
if arca and arca.get("certificado_path") and arca.get("clave_path"):
    try:
        ta = await arca_wsaa.autenticar(
            arca["certificado_path"], arca["clave_path"], arca["ambiente"]
        )
        ultimo = await arca_wsfe.ultimo_numero_autorizado(
            punto_venta, tipo, arca["cuit"],
            ta["token"], ta["sign"], arca["ambiente"],
        )
        numero = ultimo + 1
    except Exception:
        ta = None
        numero = db.get_next_factura_numero(punto_venta, tipo)  # fallback local
else:
    numero = db.get_next_factura_numero(punto_venta, tipo)

# 3. Guardar en DB (sin CAE aún)
factura_id = db.create_factura(...)
factura = db.get_factura(factura_id)

# 4. Solicitar CAE
if ta and arca:
    try:
        cae_data = await arca_wsfe.solicitar_cae(
            factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"]
        )
        db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
        factura = db.get_factura(factura_id)
    except Exception as e:
        pass  # Factura guardada sin CAE — se puede reintentar

# 5. Generar PDF
pdf_path = pdf_gen.generate_pdf_factura(factura)
db.update_factura_pdf_path(factura_id, pdf_path)
```

### Endpoint de reintento de CAE

Útil cuando ARCA no responde en el momento de emisión:

```python
@router.post("/facturas/{factura_id}/solicitar-cae")
async def solicitar_cae_endpoint(factura_id: int):
    factura = db.get_factura(factura_id)
    arca = db.obtener_todas_arca_configs()[0]
    ta = await arca_wsaa.autenticar(arca["certificado_path"], arca["clave_path"], arca["ambiente"])
    cae_data = await arca_wsfe.solicitar_cae(factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"])
    db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
    # Regenerar PDF con CAE
    pdf_path = pdf_gen.generate_pdf_factura(db.get_factura(factura_id))
    db.update_factura_pdf_path(factura_id, pdf_path)
```

---

## 8. Tipos de Comprobantes

| Código | Nombre | Letra |
|--------|--------|-------|
| 1  | Factura A | A |
| 6  | Factura B | B |
| 11 | Factura C | C |
| 2  | Nota de Débito A | A |
| 7  | Nota de Débito B | B |
| 12 | Nota de Débito C | C |
| 3  | Nota de Crédito A | A |
| 8  | Nota de Crédito B | B |
| 13 | Nota de Crédito C | C |

### Quién emite qué

| Condición emisor | Tipo a emitir |
|-----------------|---------------|
| Monotributista | Factura C (11), NC-C (13), ND-C (12) |
| Responsable Inscripto a Consumidor Final | Factura B (6) |
| Responsable Inscripto a Responsable Inscripto | Factura A (1) |

### Condiciones IVA receptor (códigos ARCA)

```python
{1: "Responsable Inscripto", 6: "Monotributista", 4: "IVA Exento",
 5: "Consumidor Final", 3: "No Alcanzado"}
```

---

## 9. Reglas de Negocio Críticas

### Factura C — IVA siempre 0

```python
# Para tipo in {11, 12, 13}: ImpNeto = ImpTotal, ImpIVA = 0
# NO incluir bloque <Iva> en el XML de FECAESolicitar
```

### Número correlativo — siempre desde ARCA

```python
# CORRECTO: consultar ultimo autorizado en ARCA y sumar 1
numero = await arca_wsfe.ultimo_numero_autorizado(...) + 1

# INCORRECTO: usar MAX(numero) de la DB local
# (puede desfasarse si se emitieron facturas desde otro sistema)
```

### Concepto 2/3 — fechas de servicio obligatorias

```python
# Si concepto == 2 (Servicios) o 3 (Ambos):
# WSFE exige FchServDesde, FchServHasta, FchVtoPago
# Si no se proveen, usar la fecha de la factura como fallback
fch_desde = factura.get("fch_serv_desde") or factura["fecha"]
```

### NC/ND — referencia al comprobante original obligatoria

```python
# El bloque CbtesAsoc es requerido por ARCA para NC y ND:
cbte_asoc = {
    "cbte_asoc_tipo": 11,   # tipo del comprobante original
    "cbte_asoc_pv":   5,
    "cbte_asoc_nro":  3,
}
```

### SSL legacy en servidores ARCA

```python
# Los servidores WSFE usan DH parameters legacy.
# Sin esto, httpx/requests falla con SSL handshake error:
ctx = ssl.create_default_context()
ctx.set_ciphers("ALL:@SECLEVEL=0")
async with httpx.AsyncClient(verify=ctx) as client:
    ...
```

### SOAPAction para WSFE

```python
# Correcto: el namespace va en el header SOAPAction
"SOAPAction": f'"{_NS}{action}"'
# Donde _NS = "http://ar.gov.afip.dif.FEV1/"
# Y action es el nombre del método, ej: "FECAESolicitar"
```

---

## 10. Dependencias y Docker

### `requirements.txt`

```
fpdf2>=2.7.9
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
jinja2>=3.1.4
httpx>=0.27.0
cryptography>=42.0.0
qrcode>=7.4.2
python-multipart>=0.0.9
aiofiles>=23.2.1
```

### `Dockerfile` mínimo

```dockerfile
FROM python:3.12-slim

# openssl es necesario para firmar el TRA del WSAA
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

⚠️ `openssl` como binario del sistema es **requerido** en runtime — la firma del TRA lo usa via `subprocess`.

---

## 11. Verificación y Debug

### Verificar CAE de una factura ya emitida

```python
# Script de verificación directa contra WSFE producción
import asyncio
import arca_wsaa, arca_wsfe
import xml.etree.ElementTree as ET

_NS = "http://ar.gov.afip.dif.FEV1/"

async def verificar_comprobante(tipo, pv, nro):
    ta = await arca_wsaa.autenticar("certificado.crt", "clave_privada.key", "produccion")
    url = arca_wsfe.WSFE_URL["produccion"]
    body = (
        f'<FECompConsultar xmlns="{_NS}">'
        f'<Auth><Token>{ta["token"]}</Token><Sign>{ta["sign"]}</Sign>'
        f'<Cuit>20289933604</Cuit></Auth>'
        f'<FeCompConsReq>'  # ← tag correcto (no FeConsReq)
        f'<CbteTipo>{tipo}</CbteTipo><PtoVta>{pv}</PtoVta><CbteNro>{nro}</CbteNro>'
        f'</FeCompConsReq></FECompConsultar>'
    )
    resp = await arca_wsfe._soap(url, "FECompConsultar", body)
    cae   = resp.find(f'.//{{{_NS}}}CodAutorizacion')
    total = resp.find(f'.//{{{_NS}}}ImpTotal')
    print(f"CAE: {cae.text if cae is not None else 'NO ENCONTRADO'}")
    print(f"Total: {total.text if total is not None else '-'}")

asyncio.run(verificar_comprobante(11, 5, 1))
```

### Diagnóstico de certificado

```python
import arca_wsaa
errores = arca_wsaa.validar_archivos("certificado.crt", "clave_privada.key")
if errores:
    print("Errores:", errores)
else:
    info = arca_wsaa.info_certificado("certificado.crt")
    print(f"Vence: {info['vencimiento']} ({info['dias_restantes']} días)")
```

### Ver facturas en el portal ARCA

Para ver las facturas emitidas en el portal de ARCA:
- **URL:** https://www.arca.gob.ar
- **Sección:** Mis servicios → Comprobantes en Línea → **Consultar comprobantes emitidos**
- Filtrar por punto de venta, tipo y fecha

Las facturas con CAE válido SIEMPRE están en ARCA aunque no aparezcan en pantalla inmediatamente. Usar `FECompConsultar` para confirmar.

---

## 12. Checklist de Setup Nuevo Sistema

```
CERTIFICADOS
[ ] Generar clave_privada.key (openssl genrsa 2048)
[ ] Generar pedido.csr con CUIT correcto en serialNumber
[ ] Subir CSR en ARCA → Administración de Certificados Digitales
[ ] Descargar certificado.crt una vez activo
[ ] Asociar certificado a WSFE en Administrador de Relaciones
[ ] Validar con: openssl smime -sign ... (debe salir exit 0)
[ ] Guardar archivos en directorio seguro, fuera del git

CÓDIGO
[ ] Copiar arca_wsaa.py y arca_wsfe.py al nuevo proyecto
[ ] Instalar dependencias: fpdf2, httpx, cryptography, qrcode
[ ] Asegurarse que openssl está disponible en el sistema/Docker
[ ] Copiar pdf_generator.py (ajustar rutas de directorios de salida)

BASE DE DATOS
[ ] Crear tabla facturas (ver esquema sección 6)
[ ] Crear tabla arca_config (ver esquema sección 6)
[ ] Insertar fila en arca_config con CUIT, punto_venta, rutas y ambiente

CONFIGURACIÓN
[ ] Crear punto de venta en ARCA (si no existe)
[ ] Confirmar ambiente: 'homologacion' para pruebas, 'produccion' para real
[ ] Verificar CUIT en arca_config coincide con el del certificado

PRUEBA FUNCIONAL
[ ] Emitir factura de prueba en homologación (importe $1)
[ ] Verificar CAE retornado con FECompConsultar
[ ] Verificar PDF generado con CAE y QR correctos
[ ] Pasar a producción solo cuando todo funcione en homo
```

---

## Notas Adicionales

- El certificado de producción **vence en 2 años** (ej: emitido 11/05/2026 → vence 10/05/2028).
  Agendar renovación con 30 días de anticipación.
- Los tokens WSAA tienen TTL largo (~12hs). En producción conviene cachearlos en memoria.
- Si ARCA no responde al momento de emitir, guardar la factura con `cae=NULL` y ofrecer
  un botón "Reintentar CAE" en la interfaz.
- El número de comprobante **siempre** debe obtenerse de `FECompUltimoAutorizado + 1`,
  nunca de la base de datos local.
- Para verificar si una factura ya existe en ARCA antes de re-emitir: usar `FECompConsultar`.
