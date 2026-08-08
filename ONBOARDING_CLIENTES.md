# Guía de onboarding — Cliente nuevo en Restolibra

Esta guía es para vos, Mariano. Describe el proceso completo para dar de alta a un cliente
nuevo de Restolibra —restaurantes, bares y locales de comida con delivery— desde la
contratación hasta que está operando.

> **Qué es Restolibra y qué no.** Es Contalibra —el ERP con facturación ARCA, POS, caja, stock,
> tesorería y MercadoPago— **más la operación gastronómica**: salón y mesas, comandas de cocina
> y barra (KDS), reservas, recetas, y el split de pedidos en salón / barra / takeaway /
> delivery. Si el cliente no necesita nada de eso, el producto es Contalibra.

---

## Resumen del proceso

1. Recopilar datos del cliente
2. Levantar la instancia
3. Primer acceso
4. Configurar datos de la empresa
5. Configurar el salón: mesas, sectores y comandas
6. Cargar carta, recetas y stock
7. Aplicar el plan contratado
8. Configurar integraciones (ARCA, MercadoPago, email)
9. Crear los usuarios
10. Handoff: primer servicio con el cliente

---

## 1. Datos a recopilar antes de empezar

| Dato | Para qué sirve |
|------|----------------|
| Razón social / nombre comercial | Aparece en facturas, presupuestos, remitos |
| Slug | Nombre corto sin espacios: define `clientes/<slug>/` y el subdominio |
| CUIT | Facturación ARCA y consulta de clientes |
| Domicilio fiscal | Aparece en comprobantes |
| Condición ante IVA | Determina tipo de comprobante (A, B o C) |
| Inicio de actividades | Dato de AFIP para comprobantes |
| Logo (PNG/JPG, fondo blanco) | Aparece en los PDF |
| Email de contacto | Campo empresa y envíos SMTP |
| Plan contratado | Define qué módulos habilitar |
| **Plano del salón** | Cuántas mesas, cómo se numeran y en qué sectores |
| **Carta** | Productos con precio; si es larga, pedirla en Excel |
| **Qué sale por cocina y qué por barra** | Define a qué pantalla de comandas va cada ítem |
| ¿Necesita facturación electrónica? | Si sí: certificado ARCA o guiarlo para generarlo |
| ¿Necesita MercadoPago QR? | Si sí: Access Token, User ID, POS ID |
| ¿Toma reservas? | Para mostrarle el módulo en el handoff |
| Usuario y contraseña del admin | Comunicar por WhatsApp, no por email |

---

## 2. Levantar la instancia

Cada cliente corre en su propio contenedor, aislado en `clientes/<slug>/`, todos compartiendo
la imagen `restolibra:latest`. El código nunca se copia por cliente: sólo se crean datos y
configuración propios.

### Setup único del servidor

`nuevo_cliente.py` y `panel_admin.py` son wrappers finos sobre `libracore.provisioning`, y el
Python del sistema del VPS no tiene `pip` por política de Debian (PEP 668). Por eso corren con
un venv dedicado en `/root/restolibra/.venv-scripts`, **gitignored — no se versiona y no llega
por `git pull`**. Si hay que recrearlo:

```bash
apt-get install -y python3-venv
python3 -m venv /root/restolibra/.venv-scripts
/root/restolibra/.venv-scripts/bin/pip install \
  "libracore @ git+ssh://git@github-libracore/marianocappucci/libracore.git@<TAG>"
```

Dos cosas que no son obvias:

- **`<TAG>` es el pin que declara el `pyproject.toml` de *este* repo**, no un número común a
  la familia. Cada producto pinea su propia versión de LibraCore, y el venv del host tiene que
  espejar la suya: si queda atrás, el CLI opera con un motor distinto del que corre la
  instancia. Ya frenó un deploy de Contalibra por eso.
- **La URL va por SSH (`git+ssh://git@github-libracore/…`), no por HTTPS.** En este VPS el
  `https://` del `pyproject.toml` falla: la autenticación es por deploy key con alias en
  `~/.ssh/config`. `httpx` y el resto de las dependencias entran solas con LibraCore.

### Alta de un cliente nuevo

En el servidor, desde `/root/restolibra`:

```bash
./.venv-scripts/bin/python3 scripts/nuevo_cliente.py
```

El wizard pide nombre, slug, puerto, dominio, plan y credenciales de admin; crea
`clientes/<slug>/` (compose + `data/` con base, config, certificados ARCA y PDFs aislados),
buildea la imagen si falta, levanta el contenedor y —si hay dominio— crea el proxy y el
certificado en Nginx Proxy Manager.

### Gestión del día a día

```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py            # menú interactivo
./.venv-scripts/bin/python3 scripts/panel_admin.py listar     # instancias, puerto y estado
./.venv-scripts/bin/python3 scripts/panel_admin.py info <slug>
./.venv-scripts/bin/python3 scripts/panel_admin.py backup <slug>
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar [slug...]   # sin args = todas
./.venv-scripts/bin/python3 scripts/panel_admin.py pausar <slug>          # banner, sin cortar acceso
./.venv-scripts/bin/python3 scripts/panel_admin.py suspender <slug>       # corta el acceso
```

Lo mismo por navegador desde el backoffice, en **https://admin.restolibra.com.ar**.

### DNS y dominio

- El wildcard `*.restolibra.com.ar` ya apunta al VPS: **no hay que tocar DNS** por cliente.
- El subdominio es `<slug>.restolibra.com.ar`, y el proxy + SSL los crea el alta.
- Para gestionarlos a mano: `panel_admin.py npm-crear | npm-eliminar | npm-listar`.

> ⚠️ **Al dar de baja una instancia, el proxy no se va solo.** `eliminar` baja el contenedor y
> borra el directorio, nada más. Correr **`npm-eliminar <slug>` antes**, porque después no
> queda `cliente.json` de donde leer el dominio — y ese comando depende de que el campo
> `domain` esté cargado ahí.

---

## 3. Primer acceso

```
URL: https://<slug>.restolibra.com.ar
Usuario: el que definiste en el alta
Contraseña: la que definiste — comunicarla por WhatsApp
```

---

## 4. Datos de la empresa

En **Configuración → Empresa**:

- [ ] Razón social
- [ ] CUIT (sin guiones)
- [ ] Domicilio fiscal, localidad y provincia
- [ ] Teléfono y email de contacto
- [ ] Condición ante IVA
- [ ] Inicio de actividades
- [ ] Logo

Guardar y verificar que aparezcan bien en un PDF de prueba.

---

## 5. El salón: mesas, sectores y comandas

Este es el paso propio de Restolibra, y el que decide si el servicio funciona o no:

- [ ] Cargar los **sectores** del local (salón, barra, terraza, delivery)
- [ ] Cargar las **mesas** con la misma numeración que usa el personal — si en el local la mesa
      es la 12, en el sistema tiene que ser la 12
- [ ] Definir **qué ítems salen por cocina y cuáles por barra**: es lo que rutea cada comanda a
      la pantalla correcta
- [ ] Abrir el **KDS** en la pantalla de cocina y verificar que llegue una comanda de prueba

> **Probarlo con el local vacío, antes de abrir.** Una comanda que se rutea mal se descubre en
> pleno servicio, y ahí no hay tiempo de configurar nada.

---

## 6. Carta, recetas y stock

- [ ] Cargar la **carta** con precios (si es larga, pedirla en Excel)
- [ ] Cargar **insumos y recetas** si va a descontar stock por plato vendido
- [ ] Cargar el **stock inicial** (plan Premium)
- [ ] Verificar que un producto se encuentre rápido desde el POS

---

## 7. Plan y módulos

| Plan | Precio | Qué habilita |
|------|--------|--------------|
| Básico | $27.000 | **Operación gastronómica** (salón, mesas, comandas, KDS), ventas, caja y clientes |
| Estándar | $69.000 | Todo lo anterior + facturación, remitos, presupuestos, productos, listas de precio, cuenta corriente, egresos, proveedores, tesorería, libros IVA y reportes |
| Premium | $109.000 | Todo lo anterior + **stock** y **depósitos** |

> **La operación gastronómica no se gatea**: el módulo `restaurant` está en el plan Básico. Es
> el core del producto — un Restolibra sin salón sería Contalibra. Lo que escala por plan es la
> gestión administrativa y el inventario. La fuente de verdad es `plans.py` de este repo.

---

## 8. Integraciones

### 8a. ARCA / facturación electrónica (plan Estándar en adelante)

**Si el cliente ya tiene certificado:**

1. Pedir el `.key` (clave privada) y el `.crt` (certificado)
2. **Config → Integraciones → ARCA**: subir ambos, cargar CUIT y punto de venta
3. Seleccionar **Homologación** y hacer **Probar conexión** — tiene que mostrar el ticket WSAA
4. Recién ahí cambiar a **Producción** y guardar

**Si no lo tiene:** generar clave privada y CSR con OpenSSL (ver `GUIA_CERTIFICADO_ARCA.md`),
el cliente lo carga en AFIP con su Clave Fiscal en "Administración de Certificados Digitales",
descarga el `.crt` y se sigue desde el paso 2.

El punto de venta tiene que estar habilitado en AFIP como "Facturación electrónica — Web
Services". Si no lo tiene: "ABM de Puntos de Venta" → Nuevo → tipo Web Services.

### 8b. MercadoPago (si lo pide el cliente)

1. **Config → Integraciones → MercadoPago**
2. Completar Access Token (producción, empieza con `APP_USR-`), User ID, POS ID y Webhook
   Secret (la URL del webhook es `https://<dominio>/webhooks/mercadopago`)
3. **Probar conexión** — tiene que mostrar el nickname y el email de la cuenta
4. Guardar

### 8c. Email / SMTP

Para Gmail: el cliente activa verificación en dos pasos, genera una contraseña de aplicación en
`myaccount.google.com/apppasswords`, y esa es la que va en **Config → Integraciones → Email**
(`smtp.gmail.com`, puerto 587). Probar conexión antes de guardar.

También se puede configurar por instancia desde el backoffice, en `admin.restolibra.com.ar`.

---

## 9. Usuarios

| Rol | Puede hacer |
|-----|-------------|
| `admin` | Todo: configuración, usuarios, módulos, reportes, logs, backup |
| `operador` | Ventas, caja, clientes, productos. Sin configuración ni logs |
| `cajero` | Caja y cobros |
| `mozo` | Toma de pedidos en salón |

- [ ] Crear el `admin` para el dueño o encargado
- [ ] Crear un usuario por cada mozo y cajero
- [ ] Comunicar las credenciales de forma segura

---

## 10. Handoff con el cliente

Hacerlo **antes de un servicio real**, no durante:

1. **Ingresar** — URL, usuario, contraseña
2. **Abrir turno de caja**
3. **Abrir una mesa**, cargar un pedido y mandarlo a cocina
4. **Ver la comanda en el KDS** y marcarla lista
5. **Cerrar la mesa** y cobrar
6. **Cobrar con QR** (si tiene MercadoPago)
7. **Emitir una factura** de prueba (en homologación, si tiene ARCA)
8. **Cerrar el turno** y ver el resumen
9. **Reportes** del día
10. Mostrar **reservas** y cómo se cargan
11. Mostrar cómo hacer y restaurar un **backup**

Al terminar:

- [ ] Cambiar la contraseña del admin por una que defina el cliente
- [ ] Confirmar que el personal puede tomar un pedido sin ayuda
- [ ] Pasar ARCA a producción si corresponde
- [ ] Compartir el link a la documentación: `https://<dominio>/docs/`

---

## 11. Post-onboarding (primera semana)

- [ ] Contactarlo a los 2-3 días
- [ ] Preguntar específicamente por el KDS: es lo que más se ajusta después del primer servicio
- [ ] Verificar que el certificado ARCA siga funcionando, si factura
- [ ] Verificar que los webhooks de MP estén llegando, si tiene QR
- [ ] Recordarle descargar un backup manual

---

## Checklist resumen

```
DATOS
[ ] Razón social, CUIT, domicilio, IVA, logo recopilados
[ ] Plan definido
[ ] Plano del salón, carta y ruteo cocina/barra conseguidos

INSTANCIA
[ ] Levantada y accesible por HTTPS
[ ] Login funciona

CONFIGURACIÓN
[ ] Datos de la empresa completos y logo cargado
[ ] Sectores y mesas cargados con la numeración real
[ ] Ruteo cocina/barra definido y probado en el KDS
[ ] Carta cargada; recetas y stock si aplica
[ ] Plan aplicado y módulos correctos
[ ] ARCA configurada y probada en homologación (si aplica)
[ ] MercadoPago configurado y probado (si aplica)
[ ] Email SMTP configurado y probado (si aplica)

USUARIOS
[ ] admin creado
[ ] Mozos y cajeros creados

CAPACITACIÓN
[ ] Handoff hecho antes de un servicio real
[ ] El personal toma un pedido y cierra una mesa solo
[ ] ARCA en producción (si aplica)
[ ] Link a documentación compartido

POST-ONBOARDING
[ ] Seguimiento a los 3 días
[ ] KDS ajustado después del primer servicio
```

---

## Contacto de soporte

- WhatsApp: +54 9 11 2775-2983
- Email: hola@restolibra.com.ar
