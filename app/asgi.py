"""Entrypoint ASGI de los contenedores: `uvicorn app.asgi:app`.

Mismo nombre y misma forma que `gestiolibra/app/asgi.py`, para que el
comando de arranque sea el mismo en toda la familia. Acá es un puente
delgado a proposito: la app real la construye `app/web/app.py`, que es el
modulo historico de este producto y no se toca.
"""
from app.web.app import app  # noqa: F401  (lo consume uvicorn por nombre)
