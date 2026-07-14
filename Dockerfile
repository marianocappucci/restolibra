# syntax=docker/dockerfile:1
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

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
