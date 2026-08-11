# syntax=docker/dockerfile:1

# Stage separado para el frontend (React+Vite, migracion documentada en
# wiki/entities/restolibra.md): node no hace falta en la imagen final,
# solo el resultado del build (frontend/dist). Mismo patron que
# gestiolibra/Dockerfile.
#
# frontend/package.json referencia libra-ui (paquete de frontend
# compartido, sumado a Restolibra en la migracion documentada en
# wiki/entities/libra-ui.md) via git+https, mismo motivo que
# libracore/libracommerce en el stage de Python: funciona tambien en dev
# local en WSL sin identidad SSH propia. Este stage node:20-slim es
# independiente del stage de Python de mas abajo, asi que necesita su
# propia copia de git+openssh-client + deploy key de solo lectura
# (id_ed25519_libra_ui en el VPS). Mount SSH con id propio (no el
# "default" generico) -- mismo patron que libracore/libracommerce mas
# abajo: docker_build_ssh_args() (libracore >= v0.23.0) le pasa a este id
# su propia key dedicada, sin ambiguedad de que identidad ofrece GitHub.
FROM node:20-slim AS frontend-build
WORKDIR /frontend
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*
RUN mkdir -p -m 0700 /root/.ssh && ssh-keyscan github.com >> /root/.ssh/known_hosts 2>/dev/null
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=ssh,id=libra-ui,target=/tmp/ssh-libra-ui.sock \
    SSH_AUTH_SOCK=/tmp/ssh-libra-ui.sock \
    sh -c 'git config --global url."ssh://git@github.com/marianocappucci/libra-ui.git".insteadOf "https://github.com/marianocappucci/libra-ui.git" && \
           npm ci'
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# `postgresql-client` trae `pg_dump` y `pg_restore`, que es lo que usa
# `libracore.respaldo` cuando la instancia corre sobre PostgreSQL. Sin ellos la
# pantalla de Backup deja de andar -- con un error explicito, no en silencio,
# pero deja de andar. En una instancia SQLite no se usan.
#
# 🔴 Va en la etapa FINAL, no en la del build del frontend: un paquete
# instalado en un stage que se descarta se ve igual de bien en el Dockerfile y
# no esta en la imagen. Paso el 2026-08-10 y lo agarro `command -v pg_dump`
# adentro del contenedor, no el diff.
#
# 🔴 La version del cliente tiene que ser >= la del servidor. python:3.12-slim
# es Debian 13 (trixie) y su `postgresql-client` es 17, contra sidecar 16.
# Alcanza. Si el servidor sube por encima, hay que agregar el repo de PGDG.
RUN apt-get update && apt-get install -y --no-install-recommends openssl git openssh-client postgresql-client && rm -rf /var/lib/apt/lists/*

# Las tres dependencias privadas se declaran en pyproject.toml con
# git+https (asi anda el dev local en WSL, sin identidad SSH propia) y acá
# se reescriben a git+ssh, cada una con su alias, su socket y su clave. Las
# claves llegan por --mount=type=ssh y se descartan con la capa: ninguna
# queda en la imagen. docker_build_ssh_args() (libracore) arma los --ssh.
#
# Por qué un alias por repo y no un SSH_AUTH_SOCK global: `pip install .`
# resuelve LAS TRES en un solo comando, y esa variable apunta a un socket
# a la vez. GitHub además asocia la conexión a la PRIMERA deploy key válida
# que se le ofrece, así que un agente con las tres autentica como el primer
# repo y los otros dos fallan con "Repository not found" (verificado en el
# VPS al preparar P7).
#
# `IdentityAgent` fija de qué socket sale la identidad; `IdentitiesOnly`
# por sí solo NO alcanza — sin un `IdentityFile` explícito ssh ofrece los
# paths default (id_rsa/id_ecdsa/…), que no existen en la imagen, y nunca
# le pregunta al agente. El `IdentityFile` apunta a la clave PÚBLICA (no es
# secreta, se hornea a propósito) sólo para que ssh sepa qué fingerprint
# pedirle a ese agente. Mismo patrón que gestiolibra/Dockerfile.
RUN mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts 2>/dev/null \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG7oB3H2Rd+xsO/qCUk5aCA14/5GaQFMSh1U0ErJjG55 vps-donweb-libracore-deploy-key\n' > /root/.ssh/id_libracore.pub \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO04BM5s9T3h96pW91Bu9rf64DDztmJgxT9cN1pjsLla deploy-key-libracommerce-readonly\n' > /root/.ssh/id_libracommerce.pub \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID0FOGgyaywQLO6J583j9+MG71a13oNpXoxOAAcV9Cbp vps-donweb-libraauth-deploy-readonly\n' > /root/.ssh/id_libraauth.pub \
    && printf 'Host github-libracore\n  HostName github.com\n  User git\n  HostKeyAlias github.com\n  IdentityFile /root/.ssh/id_libracore.pub\n  IdentityAgent /tmp/ssh-libracore.sock\n  IdentitiesOnly yes\n\nHost github-libracommerce\n  HostName github.com\n  User git\n  HostKeyAlias github.com\n  IdentityFile /root/.ssh/id_libracommerce.pub\n  IdentityAgent /tmp/ssh-libracommerce.sock\n  IdentitiesOnly yes\n\nHost github-libraauth\n  HostName github.com\n  User git\n  HostKeyAlias github.com\n  IdentityFile /root/.ssh/id_libraauth.pub\n  IdentityAgent /tmp/ssh-libraauth.sock\n  IdentitiesOnly yes\n' > /root/.ssh/config \
    && chmod 600 /root/.ssh/config /root/.ssh/id_libracore.pub /root/.ssh/id_libracommerce.pub /root/.ssh/id_libraauth.pub

COPY . .
# Horneado FUERA de /app a proposito (mismo motivo que gestiolibra
# ADR-022): docker-compose.yml de dev montea ./:/app entero para el
# --reload de Python, lo que taparia cualquier build copiado dentro de
# /app con el checkout del host (que no tiene frontend/dist, es un
# artefacto gitignoreado). Copiarlo fuera del arbol bind-monteado evita el
# problema de raiz, sin volumenes anonimos (que solo se siembran del build
# la primera vez y quedan congelados despues).
COPY --from=frontend-build /frontend/dist /opt/frontend-dist

# `pip install .` despues del COPY: instala el paquete `app` y resuelve las
# tres privadas en un solo comando. El insteadOf se desarma en el mismo RUN
# para no dejar la reescritura en la config global de la imagen.
RUN --mount=type=ssh,id=libracore,target=/tmp/ssh-libracore.sock \
    --mount=type=ssh,id=libracommerce,target=/tmp/ssh-libracommerce.sock \
    --mount=type=ssh,id=libraauth,target=/tmp/ssh-libraauth.sock \
    git config --global url."ssh://git@github-libracore/marianocappucci/libracore.git".insteadOf "https://github.com/marianocappucci/libracore.git" \
    && git config --global url."ssh://git@github-libracommerce/marianocappucci/libracommerce.git".insteadOf "https://github.com/marianocappucci/libracommerce.git" \
    && git config --global url."ssh://git@github-libraauth/marianocappucci/libraauth.git".insteadOf "https://github.com/marianocappucci/libraauth.git" \
    && pip install --no-cache-dir . \
    && git config --global --unset url."ssh://git@github-libracore/marianocappucci/libracore.git".insteadOf \
    && git config --global --unset url."ssh://git@github-libracommerce/marianocappucci/libracommerce.git".insteadOf \
    && git config --global --unset url."ssh://git@github-libraauth/marianocappucci/libraauth.git".insteadOf

EXPOSE 8000

CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
