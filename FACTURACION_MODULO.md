# Módulo de Facturación Electrónica ARCA

## Estado Actual

El módulo de facturación electrónica está **completamente estructurado y listo para usar** una vez que el certificado digital esté correctamente inscrito en ARCA.

## Componentes Implementados

### 1. Base de Datos (`database.py`)
- ✅ Tabla `facturas` creada en `init_db()`
- ✅ CRUD funciones:
  - `create_factura()` - Crear nueva factura
  - `get_all_facturas()` - Listar todas
  - `get_factura(id)` - Obtener una
  - `update_factura_cae()` - Actualizar CAE después de ARCA
  - `update_factura_pdf_path()` - Guardar PDF
  - `search_facturas()` - Búsqueda
  - `delete_factura()` - Eliminar

### 2. Core de Facturación (`facturacion_arca.py`)
- ✅ `AutenticacionARCA` - Maneja WSAA
- ✅ `FacturacionARCA` - Maneja WSFEV1
- ✅ `obtener_cae()` - Función de conveniencia

**Características:**
- Autenticación con certificado digital
- Obtención de Token y Sign
- Creación de facturas (tipos A, B, NC A, NC B)
- Solicitud de CAE
- Manejo de errores ARCA

### 3. Generación de PDF (`pdf_factura.py`)
- ✅ `FacturaPDF` - Clase personalizada
- ✅ Formato legal ARCA con:
  - Encabezado empresa
  - Datos de factura
  - Tabla de items
  - Caja CAE y vencimiento
  - Código QR ARCA
  - Totales y observaciones

### 4. Interfaz Gráfica (`gui_facturas.py`)
- ✅ `FacturasPage` - Lista de facturas emitidas
  - Búsqueda en tiempo real
  - Botones Ver/Eliminar
  - Recargar lista
  
- ✅ `NuevaFacturaPage` - Crear nueva factura
  - Selector de tipo (A/B/NC)
  - Selector de cliente
  - Entrada de items
  - Cálculo automático de totales
  - Botón "Emitir Factura (obtener CAE)"

### 5. Integración en GUI Principal (`gui.py`)
- ✅ Importadas las páginas
- ✅ Añadidas a navegación (4 botones nuevos)
- ✅ Creada carpeta `facturas_pdf/` al iniciar

## Flujo de Uso

### Paso 1: Configuración del Certificado
1. Ir a "Certificado ARCA" en la aplicación
2. Tab "Generar Certificado":
   - Ingresar nombre empresa, CUIT, nombre sistema
   - Generar CSR
3. Tab "Cargar Certificado":
   - Subir CSR a ARCA (manual en arca.gob.ar)
   - Esperar a que ARCA lo firme
   - Descargar .crt firmado
   - Cargar en la app (certificado + clave)
   - Ambiente: homologacion (para pruebas)

### Paso 2: Test de Conexión
```bash
python diagnostic_arca.py   # Ver estado del certificado
python test_arca.py         # Prueba de conexión
```

### Paso 3: Emitir Facturas
1. Click en "Nueva Factura"
2. Seleccionar tipo (A, B, etc)
3. Seleccionar cliente
4. Ingresar descripción, cantidad, precio
5. Click "Emitir Factura (obtener CAE)"
   - Si el certificado está ok: obtiene CAE
   - Si no: muestra error de ARCA

### Paso 4: Verificar en "Facturas"
- Ver listado de todas las facturas emitidas
- Estado del CAE (PENDIENTE o número)
- Descargar PDF con código QR

## ⚠️ ESTADO DEL CERTIFICADO ACTUAL

**Problema:** El certificado actual (`sistema_facturacion_3e19dd5ee9329945.crt`) no está inscrito correctamente en ARCA.

**Error al conectar:**
```
ns1:cms.cert.untrusted: Certificado no emitido por AC de confianza
```

**Solución requerida:**
1. El certificado debe completar proceso en https://www.arca.gob.ar:
   - Administración de Certificados Digitales
   - Crear nuevo alias con el CSR
   - Esperar firma de ARCA
   - Descargar certificado .crt firmado
   - Reemplazar archivo local
   - Asociar a WSFE en "Administrador de Relaciones"

2. Una vez inscrito, ejecutar:
   ```bash
   python test_arca.py
   ```

## Tipos de Comprobante Disponibles

| Código | Tipo | Uso |
|--------|------|-----|
| 1 | Factura A | Responsable Inscripto |
| 6 | Factura B | Monotributista/Consumidor |
| 3 | Nota de Crédito A | Devolución/Descuento RI |
| 8 | Nota de Crédito B | Devolución/Descuento Mono |

## Estructura de Datos Guardados

### Tabla `facturas`
```sql
id              INTEGER PRIMARY KEY
tipo            INTEGER         -- 1,6,3,8
punto_venta     INTEGER         -- 0001 típicamente
numero          INTEGER         -- Correlativo
fecha           TEXT            -- YYYYMMDD
cliente_cuit    TEXT            -- XX-XXXXXXXX-X
cliente_razon   TEXT            -- Nombre empresa
cliente_iva_cond INTEGER         -- 1=RI, 5=CF, etc
items           TEXT (JSON)     -- [{descripcion, cantidad, precio}]
subtotal        REAL            -- Sin IVA
iva_amount      REAL            -- IVA 21%
total           REAL            -- Subtotal + IVA
concepto        INTEGER         -- 1=Productos, 2=Servicios, 3=Ambos
cae             TEXT            -- Código de ARCA
cae_vto         TEXT            -- Vencimiento CAE
observaciones   TEXT            -- Notas
pdf_path        TEXT            -- Ruta al PDF
created_at      TEXT            -- Timestamp
```

## Métodos Principales

### AutenticacionARCA
```python
from facturacion_arca import AutenticacionARCA

auth = AutenticacionARCA("compulibra")
auth.conectar()
token, sign = auth.obtener_credentials()
```

### FacturacionARCA
```python
from facturacion_arca import FacturacionARCA

fact = FacturacionARCA("compulibra")
fact.conectar(token, sign)

resultado = fact.crear_factura(
    tipo=1,  # Factura A
    numero=1,
    fecha="20260409",
    cliente_cuit="30-12345678-9",
    cliente_razon="Cliente S.A.",
    cliente_iva_cond=1,  # RI
    items=[{
        'descripcion': 'Servicio',
        'cantidad': 1,
        'precio': 100
    }],
    subtotal=100,
    iva_amount=21,
    total=121
)

print(f"CAE: {resultado['cae']}")
print(f"Vence: {resultado['cae_vto']}")
```

### Generar PDF
```python
from pdf_factura import generar_pdf_factura

empresa = {
    'nombre': 'COMPULIBRA S.A.',
    'cuit': '20-28993360-4',
    'iibb': 'N/A',
    'direccion': 'Av. Siempre Viva 123',
    'telefono': '(011) 1234-5678',
    'email': 'info@compulibra.com.ar'
}

factura = {
    'tipo': 1,
    'punto_venta': 1,
    'numero': 1,
    'fecha': '20260409',
    'cliente_razon': 'Cliente S.A.',
    'cliente_cuit': '30-12345678-9',
    'items': [...],
    'subtotal': 100,
    'iva_amount': 21,
    'total': 121,
    'cae': '12345678901234',
    'cae_vto': '20260509',
    'observaciones': ''
}

generar_pdf_factura(empresa, factura, 'factura.pdf')
```

## Dependencias Requeridas

```bash
pip install pyafipws      # WSAA + WSFEV1
pip install qrcode        # Código QR en PDF
pip install fpdf2         # Ya disponible
```

## Próximos Pasos

1. ✅ Estructura completada
2. ⏳ **AHORA:** Completar inscripción del certificado en ARCA
3. ⏳ Ejecutar `python test_arca.py` para verificar
4. ⏳ Emitir primera factura de prueba en homologación
5. ⏳ Validar CAE en https://www.arca.gob.ar
6. ⏳ Cambiar ambiente a producción
7. ⏳ Emitir facturas reales

## Troubleshooting

### Error: "Certificado no emitido por AC de confianza"
- El certificado no está inscrito en ARCA
- Ejecutar `python diagnostic_arca.py` para ver estado
- Ir a ARCA y completar proceso de firma

### Error: "Imposible abrir /path/to/cert.crt"
- Verificar rutas en configuración
- Certificado debe ser archivo .crt (X509)
- Clave debe ser archivo .key (PEM)

### Error: "Token/Sign vacío"
- WSAA no autenticó correctamente
- Verificar CUIT y paths
- Revisar permisos de lectura de archivos

## Ambiente de Pruebas

**Homologación (Pruebas):**
- URL WSAA: serviciosjava2.afip.gov.ar
- URL WSFEV1: wswhomo.afip.gov.ar
- CAE ficticio: puede usarse para pruebas
- No genera movimientos impositivos

**Producción:**
- URL WSAA: wsaa.afip.gov.ar
- URL WSFEV1: servicios1.afip.gov.ar
- CAE real: genera movimientos
- ⚠️ No iniciar hasta no estar 100% seguro

## Notas de Seguridad

1. **Clave privada:** Nunca compartir `clave.key`
2. **Certificado:** Guardar copia segura
3. **CAE:** Confidencial, incluido en PDF
4. **Ambiente:** Completar pruebas en homologación antes de ir a producción
5. **Backup:** Hacer backup regular de la BD

## Contacto y Soporte

Para consultas sobre ARCA/AFIP:
- https://www.arca.gob.ar
- https://www.afip.gob.ar
- Manual técnico: Consultar en sitios oficiales
