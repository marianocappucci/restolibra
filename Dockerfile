# syntax=docker/dockerfile:1

# Stage separado para el frontend (React+Vite, migracion documentada en
# wiki/entities/restolibra.md): node no hace falta en la imagen final,
# solo el resultado del build (frontend/dist). Mismo patron que Contalibra.
#
# frontend/package.json referencia libra-ui (paquete de frontend
# compartido, sumado a Restolibra en la migracion documentada en
# wiki/entities/libra-ui.md) via git+https, mismo motivo que
# libracore/libracommerce en el stage de Python. Este stage node:20-slim
# es independiente del stage de Python de mas abajo, asi que necesita su
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

RUN apt-get update && apt-get install -y --no-install-recommends openssl git openssh-client && rm -rf /var/lib/apt/lists/*

# LibraCore (paquete interno privado) se instala via git+ssh — requiere el
# mount de tipo ssh en build time (--ssh default=<key>), la clave nunca
# queda en ninguna capa de la imagen. Ver wiki/entities/libracore.md.
RUN mkdir -p -m 0700 /root/.ssh && ssh-keyscan github.com >> /root/.ssh/known_hosts 2>/dev/null

COPY requirements.txt .
# libracore y libracommerce (P8) son repos privados DISTINTOS, cada uno con
# su propia deploy key. GitHub asocia la conexión SSH a la PRIMERA deploy
# key válida que se le ofrece: un agente cargado con ambas autentica como
# el primer repo y el segundo falla con "Repository not found" (mismo
# hallazgo que P7 de Contalibra, ver wiki/entities/contalibra.md). Por eso
# cada dependencia privada se instala en su propio paso, con su propia
# clave, vía dos sockets de BuildKit separados. `requirements.txt` sigue
# siendo la única fuente de verdad de las versiones.
RUN --mount=type=ssh,id=libracore,target=/tmp/ssh-core.sock \
    SSH_AUTH_SOCK=/tmp/ssh-core.sock \
    sh -c 'grep "^libracore" requirements.txt > /tmp/req-core.txt && \
           pip install --no-cache-dir -r /tmp/req-core.txt'
RUN --mount=type=ssh,id=libracommerce,target=/tmp/ssh-commerce.sock \
    SSH_AUTH_SOCK=/tmp/ssh-commerce.sock \
    sh -c 'grep "^libracommerce" requirements.txt > /tmp/req-commerce.txt && \
           pip install --no-cache-dir -r /tmp/req-commerce.txt'
RUN sh -c 'grep -v "^libracore" requirements.txt | grep -v "^libracommerce" > /tmp/req-pub.txt && \
           pip install --no-cache-dir -r /tmp/req-pub.txt'

COPY . .
# Horneado FUERA de /app a proposito (mismo motivo que Contalibra): el
# docker-compose.yml de dev montea ./:/app entero para el --reload de
# Python, lo que taparia cualquier build copiado dentro de /app con el
# checkout del host (que no tiene frontend/dist, es un artefacto
# gitignoreado). Copiarlo fuera del arbol bind-monteado evita el problema
# de raiz.
COPY --from=frontend-build /frontend/dist /opt/frontend-dist

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
