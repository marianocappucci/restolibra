#!/usr/bin/env python3
"""
Configuración de la conexión a Nginx Proxy Manager.
Uso: python3 scripts/npm_setup.py

Guarda la config en scripts/.npm_config.json (excluido del repo).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from npm_api import NPMClient, save_config, load_config, CONFIG_FILE


def main():
    print("=" * 55)
    print("  CONTALIBRA — Configuración Nginx Proxy Manager")
    print("=" * 55)

    existing = load_config() or {}

    def ask(msg, default=""):
        suffix = f" [{default}]" if default else ""
        val = input(f"{msg}{suffix}: ").strip()
        return val if val else default

    print("""
NPM corre típicamente en http://localhost:81
Si NPM está en Docker junto a Contalibra usá su IP o nombre de servicio.
""")

    npm_url   = ask("URL de Nginx Proxy Manager", existing.get("npm_url", "http://localhost:81"))
    npm_email = ask("Email admin de NPM",         existing.get("npm_email", "admin@example.com"))
    npm_pass  = ask("Contraseña admin de NPM",    existing.get("npm_password", ""))

    print("""
forward_host es la IP/hostname al que NPM enruta el tráfico hacia los
contenedores Contalibra. Opciones comunes:
  172.17.0.1        → gateway Docker (NPM en contenedor, clientes en bridge)
  host.docker.internal → alternativa en algunos setups
  <IP LAN del servidor> → si NPM corre fuera de Docker
""")
    forward_host = ask("forward_host", existing.get("forward_host", "172.17.0.1"))

    le_email = ask("Email para Let's Encrypt (SSL)",
                   existing.get("le_email", npm_email))

    print("\n[*] Probando conexión a NPM ...")
    client = NPMClient(npm_url, npm_email, npm_pass)
    if not client.ping():
        print("[ERROR] No se pudo conectar. Verificá URL, email y contraseña.")
        sys.exit(1)
    print("[OK] Conexión exitosa.")

    save_config({
        "npm_url":      npm_url,
        "npm_email":    npm_email,
        "npm_password": npm_pass,
        "forward_host": forward_host,
        "le_email":     le_email,
    })
    print(f"[OK] Config guardada en {CONFIG_FILE}")
    print("\nAhora podés usar el proxy automático al crear clientes con:")
    print("  python3 scripts/nuevo_cliente.py")


if __name__ == "__main__":
    main()
