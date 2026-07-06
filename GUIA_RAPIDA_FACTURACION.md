# Guía Rápida: Facturación Electrónica ARCA

## Inicio Rápido

### 1️⃣ Verificar Setup (1 minuto)
```bash
python setup_facturacion.py
```
Debe mostrar: ✅ 5/7 verificaciones exitosas

### 2️⃣ Ver Estado del Certificado (1 minuto)
```bash
python diagnostic_arca.py
```
Debe mostrar estado y pasos necesarios.

### 3️⃣ Completar Inscripción en ARCA (Manual - 10 minutos)

**Si el certificado NO está inscrito (verás error "Certificado no emitido por AC de confianza"):**

1. Abrir: https://www.arca.gob.ar
2. Ingresar con tu clave fiscal
3. Ir a: **Administración de Certificados Digitales**
4. Click: **Crear Nuevo Alias**
   - **Nombre:** compulibra_20289933604
   - **Archivo:** `/certs/compulibra_20289933604/pedido.csr`
5. Esperar a que ARCA procese (minutos/horas)
6. Una vez listo, ir a: **Mis Certificados**
7. Descargar archivo `.crt`
8. Guardar en: `/certs/compulibra_20289933604/`
   (Reemplaza: `sistema_facturacion_3e19dd5ee9329945.crt`)
9. Ir a: **Administrador de Relaciones de Clave Fiscal**
10. **Nueva Relación:**
    - ARCA → Webservices → **Factura Electrónica (wsfe)**
    - Seleccionar tu certificado (alias)
    - Confirmar

### 4️⃣ Verificar Conexión (1 minuto)
```bash
python test_arca.py
```
Debe obtener un CAE de prueba.

### 5️⃣ Usar la Aplicación
```bash
python gui.py
```

**Navegar a:**
- **Facturas** → Ver listado de todas
- **Nueva Factura** → Emitir nueva
  1. Seleccionar tipo (A, B, NC)
  2. Seleccionar cliente
  3. Ingresar ítem
  4. Click "Emitir Factura (obtener CAE)"

---

## Flujo Completo de Emisión

```
1. Click "Nueva Factura" en la app
   ↓
2. Seleccionar cliente y tipo
   ↓
3. Ingresar descripción, cantidad, precio
   ↓
4. Click "Emitir Factura"
   ↓
5. APP REALIZA AUTOMÁTICAMENTE:
   • Conecta a WSAA con tu certificado
   • Obtiene Token + Sign
   • Se conecta a WSFEV1
   • Crea factura
   • Solicita CAE
   ↓
6. RESULTADO:
   • Guardada en base de datos
   • PDF generado con CAE + QR
   • Guardado en facturas_pdf/
   ↓
7. Ver en "Facturas" → CAE ✓
```

---

## Errores Comunes y Soluciones

### ❌ "Certificado no emitido por AC de confianza"
**Causa:** Certificado no inscrito en ARCA  
**Solución:** Completa los pasos 3 arriba

### ❌ "Imposible abrir /path/to/cert.crt"
**Causa:** Path incorrecto o archivo no existe  
**Solución:** Verifica ruta en la app → Certificado ARCA

### ❌ "No se obtuvo ticket de acceso"
**Causa:** WSAA rechaza certificado  
**Solución:** Verifica que está inscrito y válido en ARCA

### ❌ "Puerto no disponible"
**Causa:** Otra instancia de la app está corriendo  
**Solución:** Cierra otras instancias

---

## Datos Importantes

### Ubicaciones de Archivos
| Archivo | Ubicación |
|---------|-----------|
| Base datos | `remitos.db` |
| Clave privada | `certs/compulibra_20289933604/clave.key` |
| Certificado | `certs/compulibra_20289933604/sistema_facturacion_*.crt` |
| PDFs facturas | `facturas_pdf/` |

### Configuración Cargada
- **Empresa:** compulibra
- **CUIT:** 20289933604
- **Punto de Venta:** 5
- **Ambiente:** homologacion (pruebas)

### Cambiar a Producción
En la app → Certificado ARCA → Cargar Certificado → Ambiente: produccion

---

## Tipos de Comprobante

| Código | Tipo | Uso |
|--------|------|-----|
| **1** | Factura A | Responsable Inscripto |
| **6** | Factura B | Monotributista/Consumidor |
| **3** | Nota de Crédito A | Devolución/Descuento RI |
| **8** | Nota de Crédito B | Devolución/Descuento Mono |

---

## Contacto y Soporte

### ARCA/AFIP
- **Sitio:** https://www.arca.gob.ar
- **Información:** https://www.afip.gob.ar
- **Webservices:** https://www.afip.gob.ar/fe/

### Local
- **Documentación:** FACTURACION_MODULO.md
- **Diagnóstico:** python diagnostic_arca.py
- **Test:** python test_arca.py

---

## Checklist Final

Antes de emitir la primera factura real:

- [ ] Verificar setup: `python setup_facturacion.py`
- [ ] Ver diagnóstico: `python diagnostic_arca.py`
- [ ] Certificado inscrito en ARCA (5/7 en setup)
- [ ] Probar conexión: `python test_arca.py`
- [ ] Emitir factura de prueba
- [ ] Validar CAE en https://www.arca.gob.ar
- [ ] Cambiar a producción si aplica
- [ ] Documentar punto de venta en ARCA

---

## Más Información

- **Guía Técnica Completa:** FACTURACION_MODULO.md
- **Resumen de Implementación:** IMPLEMENTACION_FACTURACION.md
- **Código Fuente:** facturacion_arca.py, pdf_factura.py, gui_facturas.py

---

**¡Listo para emitir facturas electrónicas! 🚀**
