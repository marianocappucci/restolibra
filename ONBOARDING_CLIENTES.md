# Guía de onboarding — Cliente nuevo en Contalibra

Esta guía es para vos, Mariano. Describe el proceso completo para dar de alta a un cliente nuevo, desde la contratación hasta que el cliente está operando.

---

## Resumen del proceso

1. Recopilar datos del cliente
2. Levantar el servidor (VPS o Docker local)
3. Configurar la instancia del sistema
4. Configurar datos de la empresa
5. Configurar módulos según el plan contratado
6. Configurar integraciones (ARCA, MercadoPago, Email) según necesidad
7. Crear los usuarios del cliente
8. Hacer el handoff: primer ingreso con el cliente

---

## 1. Datos a recopilar antes de empezar

Antes de levantar la instancia, pedile al cliente:

| Dato | Para qué sirve |
|------|----------------|
| Razón social / nombre comercial | Aparece en facturas, presupuestos, remitos |
| CUIT | Facturación ARCA y consulta de clientes |
| Domicilio fiscal | Aparece en comprobantes |
| Condición ante IVA | Determina tipo de facturas (A, B o C) |
| Inicio de actividades | Dato de AFIP para comprobantes |
| Logo (PNG/JPG, fondo blanco) | Aparece en PDFs |
| Email de contacto | Para el campo empresa y para envíos SMTP |
| Plan contratado | Define qué módulos habilitar |
| ¿Necesita facturación electrónica? | Si sí: pedir certificado o guiarlo para generarlo |
| ¿Necesita MercadoPago QR? | Si sí: pedir Access Token, User ID, POS ID |
| ¿Necesita envío de email? | Si sí: pedir credenciales SMTP o ayudarlo con Gmail |
| Nombre de usuario admin | Para el primer acceso |
| Contraseña inicial | Comunicar de forma segura (WhatsApp, no email) |

---

## 2. Levantar el servidor

Cada cliente corre en su propio contenedor, aislado en `clientes/<slug>/`, todos compartiendo la misma imagen `contalibra:latest` (buildeada una sola vez desde este repo). El código nunca se copia por cliente — solo se crean datos y configuración propios.

### Setup único del servidor (ya hecho, dejar documentado)

`nuevo_cliente.py`/`panel_admin.py` usan `httpx` para hablar con la API de Nginx Proxy Manager (proxy + SSL automático). El Python del sistema en el VPS no tiene `pip` disponible por política de Debian (PEP 668), así que estos scripts corren con un venv dedicado en `/root/contalibra/.venv-scripts` (gitignored, no se versiona). Si hay que recrearlo en otro servidor:

```bash
apt-get install -y python3-pip python3-venv
python3 -m venv /root/contalibra/.venv-scripts
/root/contalibra/.venv-scripts/bin/pip install httpx
```

Todos los comandos de abajo se ejecutan con `.venv-scripts/bin/python3` en vez de `python3` a secas (o activá el venv con `source .venv-scripts/bin/activate`).

### Alta de un cliente nuevo

En el servidor (`/root/contalibra`):

```bash
./.venv-scripts/bin/python3 scripts/nuevo_cliente.py
```

El wizard interactivo pide nombre, slug, puerto, dominio y credenciales de admin; crea `clientes/<slug>/` (compose + `data/` con DB, config, certs y PDFs aislados), buildea la imagen si falta, levanta el contenedor y — si hay dominio y Nginx Proxy Manager configurado (`scripts/npm_setup.py`) — ofrece crear el proxy + certificado SSL automáticamente.

### Gestión del día a día

```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py            # menú interactivo
./.venv-scripts/bin/python3 scripts/panel_admin.py listar     # ver todos los clientes y su estado
./.venv-scripts/bin/python3 scripts/panel_admin.py backup <slug>
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar [slug...]   # rebuild imagen + restart (sin args = todos)
./.venv-scripts/bin/python3 scripts/panel_admin.py pausar <slug>          # banner de aviso, sin cortar acceso
./.venv-scripts/bin/python3 scripts/panel_admin.py suspender <slug>       # corta el acceso completo
```

Ver `--help` implícito (`panel_admin.py` sin comando muestra el menú con todas las opciones: logs, restore de DB, proxies NPM, etc.)

### DNS / Dominio

- Configurar el subdominio del cliente (ej: `nombre-cliente.contalibra.com.ar`)
- Apuntar el DNS al IP del servidor
- El proxy + SSL se gestionan automáticamente vía NPM desde `nuevo_cliente.py` / `panel_admin.py` (comandos `npm-crear` / `npm-eliminar` / `npm-listar`)

---

## 3. Primer acceso al sistema

```
URL: https://nombre-cliente.contalibra.com.ar
Usuario: admin (o el que hayas configurado)
Contraseña: la que definiste — comunicarla por WhatsApp
```

Verificar que el sistema cargue correctamente y que el login funcione.

---

## 4. Configurar datos de la empresa

Ir a **Configuración → Empresa** y completar:

- [ ] Razón social
- [ ] CUIT (sin guiones, ej: `20289933604`)
- [ ] Domicilio fiscal
- [ ] Localidad y provincia
- [ ] Teléfono y email de contacto
- [ ] Condición ante IVA
- [ ] Inicio de actividades
- [ ] Logo (subir el archivo PNG/JPG)

Guardar y verificar que los datos aparezcan correctamente en un PDF de prueba.

---

## 5. Configurar módulos según el plan

Ir a **Administración → Módulos** y activar/desactivar según el plan:

| Plan | Módulos a activar |
|------|-------------------|
| Básico | Ventas, Clientes, Caja y Turnos |
| Estándar | Todo Básico + Facturación, Remitos, Presupuestos, Productos, Reportes |
| Premium | Todo Estándar + Stock |

> Desactivar módulos que no correspondan al plan para mantener la interfaz limpia.

---

## 6. Configurar integraciones

### 6a. ARCA / Facturación electrónica (si el plan lo incluye)

**Opción A — El cliente ya tiene certificado:**
1. Pedir el archivo `.key` (clave privada) y `.crt` (certificado)
2. Ir a **Config → Integraciones → ARCA**
3. Subir ambos archivos, ingresar CUIT y punto de venta
4. Seleccionar ambiente **Homologación** primero para probar
5. Hacer clic en **Probar conexión** — debe mostrar el ticket WSAA válido
6. Si todo funciona, cambiar a **Producción** y guardar

**Opción B — El cliente no tiene certificado (guiarlo):**
1. Generar clave privada y CSR con OpenSSL (ver `GUIA_CERTIFICADO_ARCA.md`)
2. El cliente inicia sesión en AFIP con su Clave Fiscal
3. Va a "Administración de Certificados Digitales" y carga el CSR
4. Descarga el `.crt` resultante
5. Continuar desde el paso 2 de la Opción A

**Punto de venta:**
- El cliente debe tener habilitado un PV en AFIP del tipo "Facturación electrónica — Web Services"
- Si no tiene, guiarlo en AFIP: "ABM de Puntos de Venta" → Nuevo → tipo Web Services
- El número del PV que asigna AFIP es el que va en la configuración

### 6b. MercadoPago (si lo pide el cliente)

1. Ir a **Config → Integraciones → MercadoPago**
2. Completar:
   - **Access Token**: del panel de desarrolladores MP (producción, empieza con `APP_USR-`)
   - **User ID**: ID numérico de la cuenta MP del cliente
   - **POS ID**: External ID del punto de venta creado en "Tu negocio → Puntos de venta"
   - **Webhook Secret**: generarlo en MP → Webhooks con la URL `https://dominio/webhooks/mercadopago`
3. Hacer clic en **Probar conexión** — debe mostrar el nickname y email de la cuenta MP
4. Guardar

### 6c. Email / SMTP (si el cliente quiere enviar comprobantes por email)

**Para Gmail:**
1. El cliente activa la verificación en dos pasos en su cuenta Google
2. Va a `myaccount.google.com/apppasswords` y genera una contraseña para "Contalibra"
3. En **Config → Integraciones → Email** completar:
   - Servidor: `smtp.gmail.com`
   - Puerto: `587`
   - Usuario: email del cliente
   - Contraseña: la de 16 caracteres generada
4. Hacer clic en **Probar conexión** — debe mostrar "Conexión SMTP exitosa"
5. Guardar

---

## 7. Crear los usuarios

Ir a **Administración → Usuarios → Nuevo usuario**:

- [ ] Crear usuario **Administrador** para el dueño/encargado
- [ ] Crear usuarios **Operador** para el personal (cajeros, vendedores)
- [ ] Comunicar usuario y contraseña de cada uno de forma segura

**Roles:**
| Rol | Puede hacer |
|-----|-------------|
| Administrador | Todo: configuración, usuarios, módulos, reportes, logs, backup |
| Operador | Ventas, caja, clientes, productos. Sin acceso a configuración ni logs |

---

## 8. Carga inicial de datos

Si el cliente tiene productos/servicios, cargarlos antes de la capacitación:

- Ir a **Productos → Nuevo producto** y cargar al menos los principales
- Si tiene muchos productos, consultar si tiene un listado en Excel para importar
- Cargar los clientes frecuentes si los tiene (nombre, CUIT, email)

---

## 9. Handoff con el cliente

Hacer una sesión de capacitación (presencial o por videollamada) cubriendo en este orden:

1. **Ingresar al sistema** — URL, usuario, contraseña
2. **Abrir un turno de caja** y registrar una venta de prueba
3. **Emitir un presupuesto** y descargarlo en PDF
4. **Emitir una factura de prueba** (en homologación si tiene ARCA)
5. **Cobrar con QR** si tiene MercadoPago configurado
6. **Cerrar el turno** y ver el resumen
7. **Ver reportes** del día
8. Mostrar cómo **agregar un cliente** y **buscar en el historial**
9. Mostrar cómo **hacer y restaurar un backup**

Al terminar la sesión:
- [ ] Cambiar la contraseña del admin por una que defina el cliente
- [ ] Confirmar que el cliente puede ingresar sin ayuda
- [ ] Cambiar ARCA a ambiente **Producción** si corresponde
- [ ] Compartir link a la documentación: `https://dominio/docs/`

---

## 10. Post-onboarding (primera semana)

- [ ] Contactar al cliente a los 2-3 días para ver si surgieron dudas
- [ ] Verificar que el certificado ARCA esté funcionando si tiene facturación
- [ ] Verificar que los webhooks de MP estén recibiendo notificaciones si tiene QR
- [ ] Recordarle que descargue un backup manual la primera semana

---

## Checklist resumen

```
DATOS
[ ] Razón social, CUIT, domicilio, IVA, logo recopilados
[ ] Plan definido y módulos a activar identificados

SERVIDOR
[ ] Instancia levantada y accesible vía HTTPS
[ ] Login funciona correctamente

CONFIGURACIÓN
[ ] Datos de la empresa completos y logo cargado
[ ] Módulos activados según el plan
[ ] ARCA configurada y probada (si aplica)
[ ] MercadoPago configurado y probado (si aplica)
[ ] Email SMTP configurado y probado (si aplica)

USUARIOS
[ ] Usuario administrador creado
[ ] Usuarios operadores creados (si aplica)

DATOS INICIALES
[ ] Productos principales cargados
[ ] Clientes frecuentes cargados (si aplica)

CAPACITACIÓN
[ ] Sesión de handoff realizada
[ ] Cliente puede ingresar y operar solo
[ ] ARCA en producción (si aplica)
[ ] Link a documentación compartido

POST-ONBOARDING
[ ] Seguimiento a los 3 días hecho
[ ] Sin problemas reportados
```

---

## Contacto de soporte

- WhatsApp: +54 9 11 2775-2983
- Email: soporte@contalibra.com.ar
