#!/usr/bin/env python3
"""
Script de diagnóstico para verificar el estado del certificado ARCA
"""

import os
import sys
from datetime import datetime
import database as db

# Importar openssl para inspeccionar
import subprocess

def inspect_certificate(cert_path):
    """Inspecciona un certificado X509"""
    print("\n" + "="*70)
    print("INSPECCIÓN DEL CERTIFICADO")
    print("="*70 + "\n")

    if not os.path.exists(cert_path):
        print(f"❌ Certificado no encontrado: {cert_path}")
        return False

    print(f"✓ Archivo encontrado: {cert_path}\n")

    # Mostrar detalles
    cmd = ["openssl", "x509", "-in", cert_path, "-text", "-noout"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        lines = result.stdout.split('\n')

        # Extraer información importante
        for i, line in enumerate(lines):
            if 'Subject:' in line or 'Issuer:' in line:
                print(line)
            if 'Not Before:' in line or 'Not After' in line:
                print(line)
            if 'Serial Number:' in line:
                print(line)

        print("\n✓ Certificado es válido en formato X509")
        return True
    else:
        print(f"❌ Error al inspeccionar: {result.stderr}")
        return False


def verify_certificate_chain(cert_path):
    """Intenta verificar la cadena de certificados"""
    print("\n" + "="*70)
    print("VERIFICACIÓN DE CADENA DE CERTIFICADOS")
    print("="*70 + "\n")

    cmd = ["openssl", "verify", cert_path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(f"Comando: {' '.join(cmd)}")
    print(f"Resultado: {result.stdout if result.stdout else result.stderr}")

    if "error 20 at 0 depth lookup" in result.stderr or "unable to get local issuer certificate" in result.stderr:
        print("\n⚠️  PROBLEMA: Falta el certificado de la CA que emitió este certificado")
        print("    Esto es normal si el certificado fue emitido por AFIP en homologación.")
        print("    Debes:")
        print("    1. Ir a https://www.arca.gob.ar")
        print("    2. Buscar 'Administración de Certificados Digitales'")
        print("    3. Crear un nuevo alias con tu CSR")
        print("    4. Esperar a que ARCA firme el certificado")
        print("    5. Descargar el certificado .crt firmado por ARCA")
        print("    6. Reemplazar este archivo con el descargado")
        return False
    else:
        print("✓ Certificado verificado correctamente")
        return True


def check_arca_enrollment():
    """Verifica si el certificado está registrado en ARCA"""
    print("\n" + "="*70)
    print("ESTADO DE REGISTRO EN ARCA")
    print("="*70 + "\n")

    config = db.obtener_arca_config("compulibra")
    if not config:
        print("❌ No hay configuración ARCA guardada")
        return False

    print(f"✓ Configuración encontrada:")
    print(f"  Empresa: {config['empresa']}")
    print(f"  CUIT: {config['cuit']}")
    print(f"  Punto de venta: {config['punto_venta']}")
    print(f"  Ambiente: {config['ambiente']}")

    # Mostrar instrucciones
    print("\n📋 PASOS REQUERIDOS EN ARCA:")
    print("""
1. Ingresa a https://www.arca.gob.ar con tu clave fiscal
2. Ve a "Administración de Certificados Digitales"
3. Crea un nuevo alias (nombre: compulibra_20289933604)
4. Sube el archivo CSR: /home/usuario/proyectos/contalibra/certs/compulibra_20289933604/pedido.csr
5. ARCA procesará y firmará tu certificado (puede tomar minutos a horas)
6. Una vez listo, descarga el archivo .crt
7. Colócalo en: /home/usuario/proyectos/contalibra/certs/compulibra_20289933604/
8. Reemplaza el actual: sistema_facturacion_3e19dd5ee9329945.crt

IMPORTANTE - Asociar a WSFE:
1. Ve a "Administrador de Relaciones de Clave Fiscal"
2. Nueva Relación
3. Selecciona: ARCA → Webservices → Factura Electrónica (wsfe)
4. Elige tu certificado (alias)
5. Confirma

Luego podrás ejecutar nuevamente este script.
    """)

    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__) or '.')
    db.init_db()

    cert_path = "/home/usuario/proyectos/contalibra/certs/compulibra_20289933604/sistema_facturacion_3e19dd5ee9329945.crt"

    print("\n" + "="*70)
    print("DIAGNÓSTICO DE CONFIGURACIÓN ARCA")
    print("="*70)

    # Paso 1: Inspeccionar certificado
    if not inspect_certificate(cert_path):
        sys.exit(1)

    # Paso 2: Verificar cadena
    chain_ok = verify_certificate_chain(cert_path)

    # Paso 3: Mostrar estado de registro
    check_arca_enrollment()

    if not chain_ok:
        print("\n" + "="*70)
        print("⚠️  PRÓXIMOS PASOS REQUERIDOS")
        print("="*70)
        print("""
El certificado no está completamente verificado por ARCA.

Debes completar el proceso de enrollment en ARCA:
1. Sube el CSR a ARCA
2. Espera a que lo firmen
3. Descarga el certificado .crt firmado
4. Reemplázalo en tu carpeta de certs
5. Luego podrás usar facturación electrónica

Una vez completado, vuelve a ejecutar:
  python test_arca.py
        """)
