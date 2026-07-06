#!/usr/bin/env python3
"""
Script de setup y verificación del módulo de facturación ARCA.
Ejecutar para verificar que todo está correctamente configurado.
"""

import os
import sys
import importlib.util
from datetime import datetime

def check_python_version():
    """Verifica versión de Python."""
    print("\n" + "="*70)
    print("1. VERSIÓN DE PYTHON")
    print("="*70)

    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} (se requiere 3.8+)")
        return False


def check_dependencies():
    """Verifica dependencias requeridas."""
    print("\n" + "="*70)
    print("2. DEPENDENCIAS")
    print("="*70)

    deps = {
        'PyQt5': 'Interfaz gráfica',
        'fpdf2': 'Generación de PDF',
        'pyafipws': 'Facturación ARCA',
        'qrcode': 'Códigos QR',
        'sqlite3': 'Base de datos',
    }

    all_ok = True
    for module, description in deps.items():
        try:
            __import__(module)
            print(f"✓ {module:15} - {description}")
        except ImportError:
            print(f"❌ {module:15} - {description} [FALTA]")
            all_ok = False

    if not all_ok:
        print("\nInstala dependencias faltantes con:")
        print("  pip install pyafipws qrcode fpdf2 PyQt5")

    return all_ok


def check_modules():
    """Verifica módulos locales."""
    print("\n" + "="*70)
    print("3. MÓDULOS LOCALES")
    print("="*70)

    modules = {
        'database.py': 'Base de datos',
        'facturacion_arca.py': 'Core facturación',
        'pdf_factura.py': 'Generador PDF',
        'gui_facturas.py': 'Interfaz facturas',
        'arca_setup.py': 'Setup certificado',
        'arca_gui.py': 'GUI certificado',
        'gui.py': 'GUI principal',
    }

    all_ok = True
    for filename, description in modules.items():
        if os.path.exists(filename):
            print(f"✓ {filename:25} - {description}")
        else:
            print(f"❌ {filename:25} - {description} [NO ENCONTRADO]")
            all_ok = False

    return all_ok


def check_database():
    """Verifica estado de la base de datos."""
    print("\n" + "="*70)
    print("4. BASE DE DATOS")
    print("="*70)

    try:
        import database as db

        if not os.path.exists(db.DB_PATH):
            print(f"⚠️  Base de datos no existe: {db.DB_PATH}")
            print("   Inicializando...")
            db.init_db()

        print(f"✓ Base de datos: {db.DB_PATH}")

        # Verificar tablas
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['clients', 'remitos', 'presupuestos', 'facturas', 'arca_config']
        all_present = True

        for table in required_tables:
            if table in tables:
                print(f"  ✓ Tabla '{table}'")
            else:
                print(f"  ❌ Tabla '{table}' [FALTA]")
                all_present = False

        conn.close()
        return all_present

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def check_arca_config():
    """Verifica configuración ARCA."""
    print("\n" + "="*70)
    print("5. CONFIGURACIÓN ARCA")
    print("="*70)

    try:
        import database as db

        config = db.obtener_arca_config("compulibra")

        if not config:
            print("⚠️  No hay configuración ARCA cargada")
            print("\n   Pasos para cargar:")
            print("   1. Ejecutar la aplicación: python gui.py")
            print("   2. Ir a 'Certificado ARCA'")
            print("   3. Generar CSR o cargar existente")
            print("   4. Completar proceso en https://www.arca.gob.ar")
            return False

        print(f"✓ Empresa: {config['empresa']}")
        print(f"✓ CUIT: {config['cuit']}")
        print(f"✓ Punto de venta: {config['punto_venta']}")
        print(f"✓ Ambiente: {config['ambiente']}")

        # Verificar archivos
        print("\nArchivos de certificado:")

        cert_ok = True
        for key in ['certificado_path', 'clave_path']:
            path = config[key]
            if os.path.exists(path):
                size = os.path.getsize(path)
                print(f"  ✓ {os.path.basename(path)} ({size} bytes)")
            else:
                print(f"  ❌ {os.path.basename(path)} [NO ENCONTRADO]")
                print(f"     Ruta: {path}")
                cert_ok = False

        return cert_ok

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def check_certificate_status():
    """Verifica estado del certificado."""
    print("\n" + "="*70)
    print("6. ESTADO DEL CERTIFICADO")
    print("="*70)

    try:
        import subprocess
        import database as db

        config = db.obtener_arca_config("compulibra")
        if not config:
            print("❌ No hay configuración ARCA")
            return False

        cert_path = config['certificado_path']
        if not os.path.exists(cert_path):
            print(f"❌ Certificado no encontrado: {cert_path}")
            return False

        # Inspeccionar certificado
        cmd = ["openssl", "x509", "-in", cert_path, "-text", "-noout"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Error al inspeccionar: {result.stderr}")
            return False

        # Extraer información
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Issuer:' in line or 'Subject:' in line:
                print(line.strip())
            if 'Not Before:' in line or 'Not After' in line:
                print(line.strip())

        # Verificar cadena
        print("\nVerificación de cadena:")
        cmd = ["openssl", "verify", cert_path]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ Certificado verificado")
            return True
        else:
            if "unable to get local issuer certificate" in result.stderr:
                print("⚠️  Certificado no completamente verificado por ARCA")
                print("\n   Estado: PENDIENTE INSCRIPCIÓN EN ARCA")
                print("   Pasos:")
                print("   1. Ir a https://www.arca.gob.ar")
                print("   2. Administración de Certificados Digitales")
                print("   3. Crear nuevo alias con tu CSR")
                print("   4. Esperar a que ARCA firme")
                print("   5. Descargar .crt firmado")
                print("   6. Reemplazar archivo local")
                print("   7. Ejecutar nuevamente este script")
                return False
            else:
                print(f"❌ {result.stderr}")
                return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def check_directories():
    """Verifica directorios necesarios."""
    print("\n" + "="*70)
    print("7. DIRECTORIOS")
    print("="*70)

    dirs = {
        'remitos_pdf': 'PDFs de remitos',
        'presupuestos_pdf': 'PDFs de presupuestos',
        'facturas_pdf': 'PDFs de facturas',
        'certs': 'Certificados',
    }

    all_ok = True
    for dirname, description in dirs.items():
        if os.path.isdir(dirname):
            files = len(os.listdir(dirname))
            print(f"✓ {dirname:20} - {description} ({files} archivos)")
        else:
            print(f"⚠️  {dirname:20} - {description} [CREAR]")
            try:
                os.makedirs(dirname, exist_ok=True)
                print(f"   → Creada")
            except Exception as e:
                print(f"   ❌ Error al crear: {str(e)}")
                all_ok = False

    return all_ok


def print_summary(results):
    """Imprime resumen final."""
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nVerificaciones pasadas: {passed}/{total}")

    if passed == total:
        print("\n✅ SISTEMA COMPLETAMENTE CONFIGURADO")
        print("\nPuedes iniciar:")
        print("  python gui.py")
    else:
        print("\n⚠️  FALTAN CONFIGURACIONES")
        failed = [k for k, v in results.items() if not v]
        print(f"\nVerifica los siguientes puntos:")
        for name in failed:
            print(f"  - {name}")


def main():
    """Ejecuta todas las verificaciones."""
    print("\n" + "="*70)
    print("VERIFICACIÓN DEL SISTEMA DE FACTURACIÓN ARCA")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        'Python': check_python_version(),
        'Dependencias': check_dependencies(),
        'Módulos': check_modules(),
        'BD': check_database(),
        'Config ARCA': check_arca_config(),
        'Certificado': check_certificate_status(),
        'Directorios': check_directories(),
    }

    print_summary(results)

    print("\n" + "="*70)
    print("\nPara más información:")
    print("  - Documentación: FACTURACION_MODULO.md")
    print("  - Test conexión: python test_arca.py")
    print("  - Diagnóstico: python diagnostic_arca.py")
    print("="*70 + "\n")

    # Return exit code based on results
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
