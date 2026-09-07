# Restolibra — Guía de Operaciones

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
11. [Website de marketing (restolibra.com.ar)](#website-de-marketing-restolibracomar)
12. [Estructura de directorios](#estructura-de-directorios)

---

## Entornos dev y producción

El sistema maneja dos entornos completamente separados que corren en el mismo servidor.

| | Desarrollo | Producción |
|---|---|---|
| Rama git | `develop` | `main` |
| Puerto | `8073` | uno por instancia, desde `8071` |
| Contenedor Docker | `restolibra-dev` | `restolibra-<slug>` |
| docker-compose | `docker-compose.yml` (raíz del repo) | `clientes/<slug>/docker-compose.yml`, generado por `nuevo_cliente.py` |
| Base de datos | PostgreSQL en el sidecar `restolibra-postgres` | PostgreSQL, un sidecar por instancia |
| Código | Volumen montado (`./:/app`, hot-reload) | **Copiado en la imagen** — sólo monta `./data:/app/data` |
| Badge en UI | `DEV` amarillo en sidebar | Sin badge |

> 🔴 **`docker-compose.prod.yml` no existe**, y producción no es "un" entorno:
> son las instancias de cliente bajo `clientes/<slug>/`, cada una con su
> contenedor, su puerto y su sidecar de PostgreSQL. Ver "Alta de un cliente
> nuevo".
>
> 🔴 **Ninguna instancia usa SQLite.** La familia corre sólo PostgreSQL desde el
> 2026-08-12; los `.db` que aparecen más abajo en algunos nombres de archivo son
> del camino viejo.

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
cd /root/restolibra
docker compose up -d --build    # usa docker-compose.yml → puerto 8073
```

### Promover cambios a producción

> 🔴 **`scripts/deploy-prod.sh` NO EXISTE, y no es que se perdió: se borró a
> propósito** el 2026-07-01 (commit `ccb3137`), junto con
> `docker-compose.prod.yml`, al deprecar el deploy de un solo tenant. Esta
> sección lo siguió documentando durante casi dos meses y mandó a una sesión a
> buscarlo. Producción **son instancias de cliente** bajo `clientes/<slug>/`,
> gestionadas con `panel_admin.py` igual que cualquier otra.

El deploy a producción es `panel_admin.py actualizar`, **desde el VPS**:

> 🔴 **El intérprete es el del venv, no el `python3` del sistema.** Los scripts
> de `scripts/` son wrappers finos sobre `libracore.provisioning` y lo importan
> al arrancar: con `python3` pelado mueren en
> `ModuleNotFoundError: No module named 'libracore'` **antes de hacer nada**.
> El venv es `/root/restolibra/.venv-scripts` (gitignored, se crea en el VPS —
> ver `ONBOARDING_CLIENTES.md`). Esta guía invocaba los scripts con el `python3`
> del sistema en sus 24 ejemplos, y mandó una sesión de deploy contra ese error
> el 2026-09-01.

> ✅ **Renombrado el 2026-09-07.** Hasta esa fecha el resto de esta guía decía
> `contalibra` en casi todos lados —era la copia del archivo de Contalibra que
> llegó con el fork y nunca se había renombrado—, con puertos, contenedores y
> base de datos del otro producto. En la misma pasada se corrigieron las tres
> afirmaciones que el rename habría dejado bien escritas y falsas: la tabla de
> entornos, el "funciona sin reconstruir la imagen" y la sección de backup.

```bash
cd /root/restolibra
# Primero, ver qué se va a construir sin construir nada:
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar --dry-run

# El deploy real: construye una imagen nueva y mueve a ella las instancias.
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar            # todas las que estén corriendo
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar <slug>     # una sola
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
├── /root/restolibra/          ← código fuente del sistema (este repo)
│   ├── app/                   ← aplicación FastAPI (`app/web/app.py` es el entry point)
│   ├── frontend/              ← SPA React/Vite (se hornea en la imagen)
│   ├── scripts/               ← herramientas de administración
│   └── clientes/              ← un subdirectorio por cliente
│       ├── mitienda/
│       │   ├── docker-compose.yml   ← app + su sidecar PostgreSQL
│       │   ├── cliente.json   ← metadatos del cliente
│       │   └── data/          ← montado en /app/data dentro del contenedor
│       │       ├── backups/   ← los ZIP de respaldo
│       │       ├── config.json
│       │       ├── logos/
│       │       └── arca_certs/
│       └── otrocomercio/
│           └── ...
└── nginx-proxy-manager        ← proxy inverso con SSL automático
```

**Principio clave**: cada instancia de cliente es **autónoma** — su propio
contenedor, su propio puerto, su propio sidecar PostgreSQL y su propio `data/`.
No comparten nada entre sí.

🔴 **El código de una instancia vive DENTRO de su imagen.** Su compose monta
sólo `./data:/app/data`. El bind mount `./:/app` con hot-reload es exclusivo de
`restolibra-dev`. Para que a un cliente le llegue un cambio de código hay que
**reconstruir**, que es lo que hace `panel_admin.py actualizar`.

---

## Setup inicial del servidor

Solo se hace una vez cuando se instala el sistema en un VPS nuevo.

### 1. Clonar el repositorio

```bash
cd /root
git clone <url-del-repo> restolibra
cd restolibra
```

### 2. Construir la imagen Docker

```bash
docker build -t restolibra:latest .
```

Esto tarda 2-3 minutos la primera vez (descarga Python 3.12-slim e instala
dependencias). Las siguientes veces es mucho más rápido por caché.

### 3. Configurar Nginx Proxy Manager (opcional pero recomendado)

Si vas a usar dominios con SSL automático:

```bash
./.venv-scripts/bin/python3 scripts/npm_setup.py
```

El script pregunta la URL de NPM (típicamente `http://localhost:81`), las
credenciales de su panel admin, y el `forward_host` (normalmente `172.17.0.1`
que es el gateway Docker). Guarda la config en `scripts/.npm_config.json`
(excluido del repo).

---

## Alta de un cliente nuevo

```bash
cd /root/restolibra
./.venv-scripts/bin/python3 scripts/nuevo_cliente.py
```

El script es interactivo y guía paso a paso:

```
============================================================
  RESTOLIBRA — Alta de nuevo cliente
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
  Contenedor:  restolibra-la-panaderia-del-centro
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
(https://admin.restolibra.com.ar), sección Plan de cada cliente. Ya no existe
una pantalla de auto-gestión de módulos dentro del sistema del cliente.

```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py
# → opción 2 (info) para ver el slug exacto
```

---

## Gestión diaria con panel_admin.py

```bash
cd /root/restolibra
./.venv-scripts/bin/python3 scripts/panel_admin.py           # menú interactivo
./.venv-scripts/bin/python3 scripts/panel_admin.py listar    # lista rápida desde CLI
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
cd /root/restolibra

# 1. Traer los cambios del repo
git pull

# 2. Reiniciar todos los contenedores activos
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar
```

> 🔴 **`actualizar` RECONSTRUYE, y tiene que hacerlo.** Hasta el 2026-09-07
> esta guía decía que *"funciona sin reconstruir la imagen porque
> `/root/<producto>` está montado como volumen en `/app` dentro de cada
> contenedor"*. **Eso es cierto sólo para `restolibra-dev`.** El compose que
> `nuevo_cliente.py` genera para una instancia de cliente monta únicamente
> `./data:/app/data`: el código va **dentro de la imagen**, así que un `git pull`
> sin rebuild no le cambia una línea al cliente.
>
> Y `cmd_actualizar` tampoco construye desde el checkout: arma un `git worktree`
> limpio del ref (`contexto_de_build`), justamente para que la rama en la que
> quedó el checkout del VPS no decida qué código se le despliega a un cliente.
>
> El corolario operativo es el de siempre: **rebuild, nunca `restart`**. Un
> `restart` deja el contenedor `healthy` sirviendo el código viejo.

### Si cambiaron las dependencias (pyproject.toml)

Cuando agregaste o actualizaste paquetes Python:

```bash
cd /root/restolibra

# 1. Traer los cambios
git pull

# 2. Reconstruir la imagen (instala las nuevas dependencias)
docker build -t restolibra:latest .

# 3. Reiniciar todos los contenedores con la nueva imagen
./.venv-scripts/bin/python3 scripts/panel_admin.py actualizar
```

### Actualizar un solo cliente (sin afectar a los demás)

```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py restart mitienda

# O con docker directamente:
docker compose -f clientes/mitienda/docker-compose.yml restart
```

### Verificar que todo quedó bien

```bash
# Ver estado de todos los contenedores
./.venv-scripts/bin/python3 scripts/panel_admin.py listar

# Ver logs de un cliente específico si hay problemas
./.venv-scripts/bin/python3 scripts/panel_admin.py logs mitienda
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
./.venv-scripts/bin/python3 scripts/panel_admin.py backup mitienda
```

Genera **un** archivo: el ZIP de respaldo en
`clientes/mitienda/data/backups/`, con el dump de PostgreSQL (`pg_dump -Fc`)
más el resto de `data/` adentro.

> 🔴 **Ya no son "dos archivos", y el cambio importa.** Este producto configura
> `backup_zip=True` en `scripts/panel_admin.py`, así que el backup del panel y
> del cron arma **el mismo ZIP que la pantalla de Backups** del cliente: un solo
> artefacto, una sola retención, y lo que se respalda de noche es exactamente lo
> que el cliente puede listar, bajar y restaurar solo.
>
> El camino viejo —un `tar.gz` de `data/` más un `.db` suelto en
> `clientes/<slug>/backups/`— dejaba el dump de PostgreSQL **afuera** del tar.
> Medido el 2026-08-12 sobre las nueve instancias del VPS: en cinco de los seis
> productos el tar nocturno traía `.db` de SQLite congelados en el corte a
> PostgreSQL y ningún dump. Los datos no corrían riesgo —el dump estaba al
> lado— pero el archivo que parecía el backup de la instancia no lo era.
>
> `crear_backup` va seguido de `verificar_backup`: que el comando no falle no
> alcanza para dar el respaldo por bueno.

### Restaurar una instancia

**El camino vigente es la pantalla del cliente**: `/config` → pestaña **Datos /
Backup**. Lista los ZIP de `data/backups/`, deja bajar uno y restaurar desde un
ZIP previo, y hace un respaldo automático del estado actual antes de pisar nada.
Es `build_backup_router` de LibraCore (`libracore.respaldo.restaurar_backup`),
montado en `/api/config/backups` desde el 2026-08-12.

> 🔴 **`panel_admin.py restore-db` y `list-backups` NO sirven para este
> producto.** Los dos hacen `glob("*.db")` sobre `clientes/<slug>/backups/`, que
> es el directorio y el formato de la era SQLite. Con `backup_zip=True` los
> respaldos son ZIP y viven en `clientes/<slug>/data/backups/`, así que esos dos
> comandos imprimen *"Sin backups de DB"* contra una instancia perfectamente
> respaldada. **Ese "no hay nada" no es un diagnóstico**: es el comando mirando
> el lugar equivocado.
>
> Hasta el 2026-09-07 esta sección los documentaba como el procedimiento normal,
> con un nombre de archivo `<producto>_YYYYMMDD_HHMMSS.db` que ya no existe.

---

## Proxy y SSL (Nginx Proxy Manager)

### Setup inicial (una sola vez)

```bash
./.venv-scripts/bin/python3 scripts/npm_setup.py
```

### Al crear un cliente nuevo

Si NPM está configurado, `nuevo_cliente.py` ofrece crear el proxy
automáticamente al final del proceso.

### Crear proxy manualmente para un cliente existente

```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py
# → opción pa (crear proxy NPM)
```

O desde CLI:
```bash
./.venv-scripts/bin/python3 scripts/panel_admin.py npm-crear mitienda
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
./.venv-scripts/bin/python3 scripts/panel_admin.py estado mitienda

# Poner en modo aviso (acceso con banner amarillo)
./.venv-scripts/bin/python3 scripts/panel_admin.py pausar mitienda
→ Mensaje para el cliente: Regularizá tu suscripción para evitar la suspensión.

# Suspender acceso completo
./.venv-scripts/bin/python3 scripts/panel_admin.py suspender mitienda
→ Mensaje para el cliente: Servicio suspendido por falta de pago. Contactar a soporte.

# Reactivar
./.venv-scripts/bin/python3 scripts/panel_admin.py activar mitienda
```

El cambio de estado es inmediato — no requiere reiniciar el contenedor.
También se puede gestionar desde dentro del sistema web en `/config` → pestaña **Servicio**.

---

## Website de marketing (restolibra.com.ar)

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
cd /root/restolibra/website

# Construir la imagen
docker build -t restolibra-web:latest .

# Levantar el contenedor
docker compose up -d

# Verificar que está corriendo
docker ps | grep restolibra-web
```

El contenedor escucha en el puerto **8069** y se conecta a la red `stack_stack-net` para que NPM pueda hacer proxy.

### Configurar proxy en Nginx Proxy Manager

1. En NPM, crear un nuevo Proxy Host:
   - **Domain Names:** `restolibra.com.ar`, `www.restolibra.com.ar`
   - **Forward Hostname/IP:** `restolibra-web` (nombre del contenedor)
   - **Forward Port:** `80`
   - **SSL:** habilitar con Let's Encrypt

2. Configurar también el subdominio `docs.restolibra.com.ar` si se desea separar la documentación (opcional — actualmente está bajo `/docs/` en el mismo dominio).

### Actualizar el website

El website es completamente estático. Cualquier cambio de HTML/CSS requiere **reconstruir la imagen**:

```bash
cd /root/restolibra/website

# Traer los últimos cambios del repo
git pull

# Reconstruir y reiniciar
docker compose build
docker compose up -d

# Verificar
docker logs restolibra-web --tail 20
```

No hay reinicio en caliente — siempre se reconstruye porque el contenido se copia durante el `docker build`.

### Rollback del website

Si la nueva versión tiene problemas:

```bash
cd /root/restolibra/website

# Ver historial de imágenes
docker images | grep restolibra-web

# Si tenés una imagen anterior con otro tag:
docker compose down
docker tag restolibra-web:<tag-anterior> restolibra-web:latest
docker compose up -d
```

Para evitar problemas, antes de reconstruir en producción podés hacer:

```bash
docker tag restolibra-web:latest restolibra-web:backup
docker compose build
docker compose up -d
```

Así si algo falla, hacés `docker tag restolibra-web:backup restolibra-web:latest` y levantás la versión anterior.

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
docker logs restolibra-web --tail 50
```

---

## Estructura de directorios

```
/root/restolibra/
├── app/                        ← aplicación FastAPI
│   ├── web/app.py              ← entry point, middleware, rutas
│   ├── web/auth.py             ← autenticación con cookies
│   ├── web/api/                ← un archivo por módulo (la API de la SPA)
│   ├── web/routers/            ← routers montados desde los motores
│   ├── db_*.py                 ← capa de datos (varios son shims de los motores)
│   └── main.py                 ← CLI interactivo de remitos/presupuestos
├── frontend/                   ← SPA React/Vite (se hornea en la imagen)
├── scripts/
│   ├── nuevo_cliente.py        ← alta de cliente nuevo
│   ├── panel_admin.py          ← gestión de todos los clientes
│   ├── npm_api.py              ← cliente HTTP para NPM
│   ├── npm_setup.py            ← configuración de NPM
│   └── .npm_config.json        ← credenciales NPM (excluido del repo)
├── clientes/                   ← datos de clientes (excluido del repo)
│   └── <slug>/
│       ├── docker-compose.yml  ← app + sidecar PostgreSQL de esa instancia
│       ├── cliente.json        ← nombre, puerto, credenciales admin
│       └── data/               ← montado en /app/data
│           ├── config.json     ← configuración de la empresa
│           ├── logos/
│           ├── arca_certs/
│           └── backups/        ← los ZIP de respaldo (panel, cron y pantalla)
├── migrations/                 ← cadena Alembic propia (`alembic_version_restolibra`)
├── admin/                      ← backoffice de superadmin
├── plans.py                    ← planes y módulos por plan
├── Dockerfile
├── pyproject.toml             ← dependencias y metadata del paquete
├── OPERACIONES.md              ← este archivo
└── website/                    ← website de marketing (restolibra.com.ar)
    ├── Dockerfile
    ├── nginx.conf
    ├── docker-compose.yml
    └── public/
        ├── index.html          ← landing page
        ├── css/style.css
        └── docs/               ← documentación pública
```
