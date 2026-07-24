# syntax=docker/dockerfile:1

# Stage separado para el frontend (React+Vite, migracion documentada en
# wiki/entities/restolibra.md): node no hace falta en la imagen final,
# solo el resultado del build (frontend/dist). Mismo patron que Contalibra.
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
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
RUN --mount=type=ssh pip install --no-cache-dir -r requirements.txt

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
