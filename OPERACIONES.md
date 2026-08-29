# Contalibra — Guía de Operaciones

Guía de referencia para gestionar el servidor, dar de alta clientes nuevos y
desplegar actualizaciones del sistema.

---

## Índice

1. [Arquitectura](#arquitectura)
2. [Entornos dev y producción](#entornos-dev-y-producción)
3. [Setup inicial del servidor](#setup-inicial-del-servidor)
4. [Alta de un cliente nuevo](#alta-de-un-cliente-nuevo)
5. [Gestión diaria con panel_admin.py](#gestión-diaria-con-panel_adminpy)
6. [Desplegar una actualización](#desplegar-una-actualización)
7. [Cuándo reconstruir la imagen vs solo reiniciar](#cuándo-reconstruir-la-imagen-vs-solo-reiniciar)
8. [Backup y restauración](#backup-y-restauración)
9. [Proxy y SSL (Nginx Proxy Manager)](#proxy-y-ssl-nginx-proxy-manager)
10. [Gestión del estado del servicio](#gestión-del-estado-del-servicio)
11. [Website de marketing (contalibra.com.ar)](#website-de-marketing-contalibracomar)
12. [Estructura de directorios](#estructura-de-directorios)

---

## Entornos dev y producción

El sistema maneja dos entornos completamente separados que corren en el mismo servidor.

| | Desarrollo | Producción |
|---|---|---|
| Rama git | `develop` | `main` |
| Puerto | `8071` | `8070` |
| Contenedor Docker | `contalibra-dev` | `contalibra` |
| docker-compose | `docker-compose.yml` | `docker-compose.prod.yml` |
| Base de datos | `./dev-data/contalibra.db` | `./contalibra.db` |
| Código | Volumen montado (hot-reload) | Copiado en la imagen |
| Badge en UI | `DEV` amarillo en sidebar | Sin badge |

### Flujo de trabajo diario

Todo el trabajo se hace en la rama `develop`. Los cambios se pushean libremente.

```bash
git checkout develop       # siempre trabajar en develop
# ... editar código ...
git add -A
git commit -m "descripcion"
git push origin develop
```

### Arrancar entorno de desarrollo

```bash
cd /root/contalibra
docker compose up -d --build    # usa docker-compose.yml → puerto 8071
```

### Promover cambios a producción

> 🔴 **`scripts/deploy-prod.sh` NO EXISTE, y no es que se perdió: se borró a
> propósito** el 2026-07-01 (commit `ccb3137`), junto con
> `docker-compose.prod.yml`, al deprecar el deploy de un solo tenant. Esta
> sección lo siguió documentando durante casi dos meses y mandó a una sesión a
> buscarlo. Producción **son instancias de cliente** bajo `clientes/<slug>/`,
> gestionadas con `panel_admin.py` igual que cualquier otra.

El deploy a producción es `panel_admin.py actualizar`, **desde el VPS**:

> ⚠️ El resto de esta guía dice `contalibra` en casi todos lados: es una copia
> del archivo de Contalibra que llegó con el fork y nunca se renombró. Los
> comandos de **esta** sección son los de Restolibra.

```bash
cd /root/restolibra
# Primero, ver qué se va a construir sin construir nada:
python3 scripts/panel_admin.py actualizar --dry-run

# El deploy real: construye una imagen nueva y mueve a ella las instancias.
python3 scripts/panel_admin.py actualizar            # todas las que estén corriendo
python3 scripts/panel_admin.py actualizar <slug>     # una sola
```

Lo que hace:

1. Construye la imagen desde **`main`** — o sea lo promovido, no lo que el
   checkout tenga puesto. El checkout lo comparten el build de dev y el de
   cada cliente; atarle el deploy convertiría a la rama que necesita dev en la
   que decide qué se le despliega al cliente.
2. Corre las migraciones declaradas en `configure(migraciones=...)` **antes de
   mover cada instancia**, con el compose ya pineado a la imagen nueva.
3. Repinea el compose de cada cliente y lo reinicia. Un cliente que no esté
   corriendo **se saltea sin repinear**, así que arrancarlo más tarde no lo
   salta a código que no se desplegó para él.

Antes de correrlo, en el checkout local:

1. Bumpear `app/version.py` en `develop` y agregar la entrada al CHANGELOG.
2. Promover `develop → main` con un Pull Request.
3. Taguear `vX.Y.Z` sobre `main`.

> ⚠️ **La versión vive en `app/version.py`, no en `version.py`.** Esta guía
> decía lo segundo y ese archivo no existe.

> ⚠️ **El exit code de `actualizar` fue mentira hasta el 2026-08-17**: devolvía
> 0 aunque el build fallara. Ya está arreglado, pero la forma de verificar un
> deploy sigue siendo **comparar la imagen del contenedor contra la que se
> construyó**, no leer el código de salida.

### Versionado

La versión del sistema se define en `version.py`:

```python
VERSION = "1.2.0"
```

Se muestra en el sidebar de la UI. Cada deploy a producción debe tener su propio tag git (`v1.2.0`, `v1.3.0`, etc.) y su entrada en `CHANGELOG.md`.

---

## Arquitectura

```
VPS
├── /root/contalibra/          ← código fuente del sistema (este repo)
│   ├── web/                   ← aplicación FastAPI
│   ├── scripts/               ← herramientas de administración
│   └── clientes/              ← un subdirectorio por cliente
│       ├── mitienda/
│       │   ├── docker-compose.yml
│       │   ├── cliente.json   ← metadatos del cliente
│       │   ├── backups/       ← backups automáticos de la DB
│       │   └── data/          ← montado en /app/data dentro del contenedor
│       │       ├── contalibra.db
│       │       ├── config.json
│       │       ├── logos/
│       │       └── arca_certs/
│       └── otrocomercio/
│           └── ...
└── nginx-proxy-manager        ← proxy inverso con SSL automático
```

**Principio clave**: el directorio `/root/contalibra` completo se monta como
volumen en `/app` dentro de cada contenedor. Esto significa que **los cambios
de código se aplican sin reconstruir la imagen** — solo se necesita reiniciar
el contenedor. La imagen Docker solo necesita reconstruirse cuando cambian las
dependencias Python (`pyproject.toml`).

Cada cliente tiene su propia base de datos SQLite aislada, sin ningún
componente compartido entre instancias.

---

## Setup inicial del servidor

Solo se hace una vez cuando se instala el sistema en un VPS nuevo.

### 1. Clonar el repositorio

```bash
cd /root
git clone <url-del-repo> contalibra
cd contalibra
```

### 2. Construir la imagen Docker

```bash
docker build -t contalibra:latest .
```

Esto tarda 2-3 minutos la primera vez (descarga Python 3.12-slim e instala
dependencias). Las siguientes veces es mucho más rápido por caché.

### 3. Configurar Nginx Proxy Manager (opcional pero recomendado)

Si vas a usar dominios con SSL automático:

```bash
python3 scripts/npm_setup.py
```

El script pregunta la URL de NPM (típicamente `http://localhost:81`), las
credenciales de su panel admin, y el `forward_host` (normalmente `172.17.0.1`
que es el gateway Docker). Guarda la config en `scripts/.npm_config.json`
(excluido del repo).

---

## Alta de un cliente nuevo

```bash
cd /root/contalibra
python3 scripts/nuevo_cliente.py
```

El script es interactivo y guía paso a paso:

```
============================================================
  CONTALIBRA — Alta de nuevo cliente
============================================================
Nombre del comercio / empresa: La Panadería del Centro
Identificador (slug) [la-panaderia-del-centro]:        ← Enter para aceptar
Dominio (ej: mitienda.com, Enter para omitir): panaderia.midominio.com
Puerto HTTP [8071]:                                    ← autodetecta el siguiente libre
Usuario admin [admin]:
Contraseña admin (Enter = generar):                    ← deja vacío para generar una segura
Nombre completo del admin [La Panadería del Centro]:
```

Luego muestra un resumen y pide confirmación:

```
------------------------------------------------------------
  Comercio:    La Panadería del Centro
  Slug:        la-panaderia-del-centro
  Contenedor:  contalibra-la-panaderia-del-centro
  Puerto:      8071
  Dominio:     panaderia.midominio.com
  Admin:       admin / xK9mP2nQrT4w
------------------------------------------------------------
¿Confirmar? [S/n]:
```

Al confirmar:
1. Crea `clientes/la-panaderia-del-centro/` con toda la estructura de directorios
2. Genera `docker-compose.yml` con el puerto asignado y las credenciales
3. Crea `data/config.json` inicial
4. Levanta el contenedor (`docker compose up -d`)
5. Si NPM está configurado, ofrece crear el proxy con SSL automáticamente

**Al finalizar muestra las credenciales — guardalas, no se vuelven a mostrar.**

### Acceso inmediato

```
URL local:  http://localhost:8071
Dominio:    https://panaderia.midominio.com   (si configuraste el proxy)
```

El cliente ya puede entrar y completar los datos de su empresa en
`/config` → pestaña "Empresa".

### Habilitar módulos

Los módulos se asignan según el plan del cliente desde el backoffice
(https://admin.contalibra.com.ar), sección Plan de cada cliente. Ya no existe
una pantalla de auto-gestión de módulos dentro del sistema del cliente.

```bash
python3 scripts/panel_admin.py
# → opción 2 (info) para ver el slug exacto
```

---

## Gestión diaria con panel_admin.py

```bash
cd /root/contalibra
python3 scripts/panel_admin.py           # menú interactivo
python3 scripts/panel_admin.py listar    # lista rápida desde CLI
```

### Menú disponible

| Opción | Comando CLI | Descripción |
|--------|-------------|-------------|
| `1` | `listar` | Lista todos los clientes con estado del contenedor |
| `2` | `info <slug>` | Detalle de un cliente: URL, puerto, credenciales |
| `3` | `start <slug>` | Inicia el contenedor |
| `4` | `stop <slug>` | Detiene el contenedor |
| `5` | `restart <slug>` | Reinicia el contenedor |
| `6` | `logs <slug>` | Muestra logs en tiempo real (Ctrl+C para salir) |
| `7` | `backup <slug>` | Backup completo (tar.gz) + copia de la DB |
| `rb` | `restore-db <slug>` | Restaura la DB desde un backup |
| `lb` | `list-backups <slug>` | Lista backups de DB disponibles |
| `sa` | `activar <slug>` | Activa el servicio (acceso normal) |
| `sp` | `pausar <slug>` | Pausa (muestra banner de aviso, sin cortar acceso) |
| `ss` | `suspender <slug>` | Suspende (bloquea el acceso completamente) |
| `se` | `estado <slug>` | Muestra el estado actual del servicio |

---

## Desplegar una actualización

### Flujo normal (cambios de código o templates)

Cuando modificás Python, HTML, CSS o cualquier archivo del sistema y lo
verificaste localmente:

```bash
cd /root/contalibra

# 1. Traer los cambios del repo
git pull

# 2. Reiniciar todos los contenedores activos
python3 scripts/panel_admin.py actualizar
```

**¿Por qué funciona sin reconstruir la imagen?**
El directorio `/root/contalibra` está montado como volumen en `/app` dentro
de cada contenedor. Al reiniciar, uvicorn levanta con el código nuevo que
ya está en disco.

### Si cambiaron las dependencias (pyproject.toml)

Cuando agregaste o actualizaste paquetes Python:

```bash
cd /root/contalibra

# 1. Traer los cambios
git pull

# 2. Reconstruir la imagen (instala las nuevas dependencias)
docker build -t contalibra:latest .

# 3. Reiniciar todos los contenedores con la nueva imagen
python3 scripts/panel_admin.py actualizar
```

### Actualizar un solo cliente (sin afectar a los demás)

```bash
python3 scripts/panel_admin.py restart mitienda

# O con docker directamente:
docker compose -f clientes/mitienda/docker-compose.yml restart
```

### Verificar que todo quedó bien

```bash
# Ver estado de todos los contenedores
python3 scripts/panel_admin.py listar

# Ver logs de un cliente específico si hay problemas
python3 scripts/panel_admin.py logs mitienda
```

---

## Cuándo reconstruir la imagen vs solo reiniciar

| Cambio realizado | ¿Reconstruir imagen? | ¿Reiniciar contenedores? |
|------------------|----------------------|--------------------------|
| Código Python (`.py`) | No | Sí |
| Templates HTML (`.html`) | No | Sí |
| CSS / JS | No | Sí |
| `pyproject.toml` (nuevas dependencias) | **Sí** | Sí (después del build) |
| `Dockerfile` | **Sí** | Sí (después del build) |
| Variables de entorno en `docker-compose.yml` | No | Sí |

---

## Backup y restauración

### Backup manual desde el panel admin

```bash
python3 scripts/panel_admin.py backup mitienda
```

Genera dos archivos:
- `clientes/mitienda_backup_YYYYMMDD_HHMMSS.tar.gz` — todo el directorio `data/`
- `clientes/mitienda/backups/contalibra_YYYYMMDD_HHMMSS.db` — solo la DB

### Restaurar la DB de un cliente

```bash
# Interactivo (muestra lista de backups disponibles):
python3 scripts/panel_admin.py restore-db mitienda

# Pasando el archivo directamente:
python3 scripts/panel_admin.py restore-db mitienda contalibra_20260512_143022.db
```

El proceso: para el contenedor → backup automático del estado actual → restaura → reinicia.

### Ver backups disponibles

```bash
python3 scripts/panel_admin.py list-backups mitienda
```

### El cliente también puede hacer backup/restore

Desde el sistema web: `/config` → pestaña **Datos / Backup**. Puede descargar
la DB y restaurar desde un archivo `.db` previo. Siempre se hace backup
automático antes de cualquier restauración.

---

## Proxy y SSL (Nginx Proxy Manager)

### Setup inicial (una sola vez)

```bash
python3 scripts/npm_setup.py
```

### Al crear un cliente nuevo

Si NPM está configurado, `nuevo_cliente.py` ofrece crear el proxy
automáticamente al final del proceso.

### Crear proxy manualmente para un cliente existente

```bash
python3 scripts/panel_admin.py
# → opción pa (crear proxy NPM)
```

O desde CLI:
```bash
python3 scripts/panel_admin.py npm-crear mitienda
```

### Prerequisito de DNS

Antes de crear el proxy SSL, el dominio del cliente debe apuntar a la IP del
VPS (registro A en su proveedor DNS). Si el dominio no resuelve todavía,
Let's Encrypt fallará al emitir el certificado.

---

## Gestión del estado del servicio

Para corte por falta de pago u otras situaciones:

```bash
# Mostrar estado actual
python3 scripts/panel_admin.py estado mitienda

# Poner en modo aviso (acceso con banner amarillo)
python3 scripts/panel_admin.py pausar mitienda
→ Mensaje para el cliente: Regularizá tu suscripción para evitar la suspensión.

# Suspender acceso completo
python3 scripts/panel_admin.py suspender mitienda
→ Mensaje para el cliente: Servicio suspendido por falta de pago. Contactar a soporte.

# Reactivar
python3 scripts/panel_admin.py activar mitienda
```

El cambio de estado es inmediato — no requiere reiniciar el contenedor.
También se puede gestionar desde dentro del sistema web en `/config` → pestaña **Servicio**.

---

## Website de marketing (contalibra.com.ar)

El website de marketing es un contenedor nginx estático independiente del sistema de clientes.
Se encuentra en `website/` dentro del repositorio.

### Estructura del website

```
website/
├── Dockerfile              ← FROM nginx:1.27-alpine
├── nginx.conf              ← configuración del servidor web
├── docker-compose.yml      ← definición del contenedor
└── public/
    ├── index.html          ← landing page principal
    ├── css/
    │   └── style.css       ← estilos compartidos
    └── docs/               ← documentación pública
        ├── index.html
        ├── primeros-pasos.html
        ├── empresa.html
        ├── usuarios.html
        ├── configuracion.html
        ├── ventas.html
        ├── caja-turnos.html
        ├── facturacion.html
        ├── productos-stock.html
        └── reportes.html
```

### Deploy inicial (primera vez)

```bash
cd /root/contalibra/website

# Construir la imagen
docker build -t contalibra-web:latest .

# Levantar el contenedor
docker compose up -d

# Verificar que está corriendo
docker ps | grep contalibra-web
```

El contenedor escucha en el puerto **8069** y se conecta a la red `stack_stack-net` para que NPM pueda hacer proxy.

### Configurar proxy en Nginx Proxy Manager

1. En NPM, crear un nuevo Proxy Host:
   - **Domain Names:** `contalibra.com.ar`, `www.contalibra.com.ar`
   - **Forward Hostname/IP:** `contalibra-web` (nombre del contenedor)
   - **Forward Port:** `80`
   - **SSL:** habilitar con Let's Encrypt

2. Configurar también el subdominio `docs.contalibra.com.ar` si se desea separar la documentación (opcional — actualmente está bajo `/docs/` en el mismo dominio).

### Actualizar el website

El website es completamente estático. Cualquier cambio de HTML/CSS requiere **reconstruir la imagen**:

```bash
cd /root/contalibra/website

# Traer los últimos cambios del repo
git pull

# Reconstruir y reiniciar
docker compose build
docker compose up -d

# Verificar
docker logs contalibra-web --tail 20
```

No hay reinicio en caliente — siempre se reconstruye porque el contenido se copia durante el `docker build`.

### Rollback del website

Si la nueva versión tiene problemas:

```bash
cd /root/contalibra/website

# Ver historial de imágenes
docker images | grep contalibra-web

# Si tenés una imagen anterior con otro tag:
docker compose down
docker tag contalibra-web:<tag-anterior> contalibra-web:latest
docker compose up -d
```

Para evitar problemas, antes de reconstruir en producción podés hacer:

```bash
docker tag contalibra-web:latest contalibra-web:backup
docker compose build
docker compose up -d
```

Así si algo falla, hacés `docker tag contalibra-web:backup contalibra-web:latest` y levantás la versión anterior.

### Agregar o editar páginas de documentación

1. Editá o creá el archivo HTML en `website/public/docs/`.
2. Si es una página nueva, agregá el link en el sidebar de todas las otras páginas de docs.
3. Reconstruí el contenedor como se indica en "Actualizar el website".

### Verificar que el website está funcionando

```bash
# Desde el VPS
curl -I http://localhost:8069/

# Respuesta esperada: HTTP/1.1 200 OK

# Ver logs de nginx
docker logs contalibra-web --tail 50
```

---

## Estructura de directorios

```
/root/contalibra/
├── web/                        ← aplicación FastAPI
│   ├── app.py                  ← entry point, middleware, rutas
│   ├── auth.py                 ← autenticación con cookies
│   ├── routers/                ← un archivo por módulo
│   └── templates/              ← templates Jinja2
├── scripts/
│   ├── nuevo_cliente.py        ← alta de cliente nuevo
│   ├── panel_admin.py          ← gestión de todos los clientes
│   ├── npm_api.py              ← cliente HTTP para NPM
│   ├── npm_setup.py            ← configuración de NPM
│   └── .npm_config.json        ← credenciales NPM (excluido del repo)
├── clientes/                   ← datos de clientes (excluido del repo)
│   └── <slug>/
│       ├── docker-compose.yml
│       ├── cliente.json        ← nombre, puerto, credenciales admin
│       ├── backups/            ← backups de DB
│       └── data/               ← montado en /app/data
│           ├── contalibra.db   ← base de datos SQLite
│           ├── config.json     ← configuración de la empresa
│           ├── logos/
│           ├── arca_certs/
│           └── backups/        ← backups automáticos (web)
├── database.py                 ← capa de datos
├── config_manager.py           ← lectura/escritura de config.json
├── pdf_generator.py            ← PDFs A4 (facturas, remitos, etc.)
├── ticket_generator.py         ← PDFs angostos para ticketeadoras
├── Dockerfile
├── pyproject.toml             ← dependencias y metadata del paquete
├── OPERACIONES.md              ← este archivo
└── website/                    ← website de marketing (contalibra.com.ar)
    ├── Dockerfile
    ├── nginx.conf
    ├── docker-compose.yml
    └── public/
        ├── index.html          ← landing page
        ├── css/style.css
        └── docs/               ← documentación pública
```
