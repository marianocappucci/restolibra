"""
Módulo para generar certificados y CSR para ARCA de forma automatizada.
Reutilizable para múltiples empresas.
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime


def generar_clave_privada(output_path: str, bits: int = 2048) -> tuple[bool, str]:
    """
    Genera una clave privada RSA.

    Args:
        output_path: Ruta donde guardar clave.key
        bits: Tamaño de la clave (2048 por defecto)

    Returns:
        (éxito, mensaje)
    """
    try:
        cmd = ["openssl", "genrsa", "-out", output_path, str(bits)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, f"✓ Clave privada generada en: {output_path}"
    except subprocess.CalledProcessError as e:
        return False, f"✗ Error generando clave: {e.stderr}"
    except FileNotFoundError:
        return False, "✗ OpenSSL no está instalado. Instálalo e intenta nuevamente."


def generar_csr(
    clave_path: str,
    output_path: str,
    pais: str = "AR",
    empresa: str = "Mi Empresa",
    sistema: str = "sistema",
    cuit: str = "20000000000"
) -> tuple[bool, str]:
    """
    Genera un Certificate Signing Request (CSR).

    Args:
        clave_path: Ruta a clave.key
        output_path: Ruta donde guardar pedido.csr
        pais: País (default: AR)
        empresa: Nombre de la empresa (O=)
        sistema: Nombre descriptivo del sistema (CN=)
        cuit: CUIT sin guiones (para serialNumber)

    Returns:
        (éxito, mensaje)
    """
    # Validar que clave existe
    if not os.path.exists(clave_path):
        return False, f"✗ Clave privada no encontrada en: {clave_path}"

    # Validar CUIT (debe tener 11 dígitos)
    if not cuit.isdigit() or len(cuit) != 11:
        return False, f"✗ CUIT inválido. Debe tener 11 dígitos sin guiones."

    # Construir el subject
    subject = f"/C={pais}/O={empresa}/CN={sistema}/serialNumber=CUIT {cuit}"

    try:
        cmd = [
            "openssl", "req", "-new",
            "-key", clave_path,
            "-subj", subject,
            "-out", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, f"✓ CSR generado en: {output_path}"
    except subprocess.CalledProcessError as e:
        return False, f"✗ Error generando CSR: {e.stderr}"
    except FileNotFoundError:
        return False, "✗ OpenSSL no está instalado."


def generar_certificados_completos(
    directorio: str,
    empresa: str,
    cuit: str,
    sistema: str = None,
    pais: str = "AR"
) -> dict:
    """
    Genera clave privada + CSR en un directorio (completo).

    Args:
        directorio: Carpeta donde guardar (se crea si no existe)
        empresa: Nombre de la empresa
        cuit: CUIT sin guiones (11 dígitos)
        sistema: Nombre del sistema (default: usa el nombre de empresa)
        pais: Código de país (default: AR)

    Returns:
        Dict con:
        - 'éxito': bool
        - 'clave_path': str (ruta a clave.key)
        - 'csr_path': str (ruta a pedido.csr)
        - 'mensajes': list de strings
        - 'error': str (si hay error)
    """

    if sistema is None:
        sistema = empresa.lower().replace(" ", "_")

    # Crear directorio si no existe
    Path(directorio).mkdir(parents=True, exist_ok=True)

    # Rutas de salida
    clave_path = os.path.join(directorio, "clave.key")
    csr_path = os.path.join(directorio, "pedido.csr")

    mensajes = []

    # Paso 1: Generar clave privada
    exito, msg = generar_clave_privada(clave_path)
    mensajes.append(msg)
    if not exito:
        return {
            'éxito': False,
            'clave_path': None,
            'csr_path': None,
            'mensajes': mensajes,
            'error': msg
        }

    # Paso 2: Generar CSR
    exito, msg = generar_csr(
        clave_path=clave_path,
        output_path=csr_path,
        pais=pais,
        empresa=empresa,
        sistema=sistema,
        cuit=cuit
    )
    mensajes.append(msg)
    if not exito:
        return {
            'éxito': False,
            'clave_path': clave_path,
            'csr_path': None,
            'mensajes': mensajes,
            'error': msg
        }

    return {
        'éxito': True,
        'clave_path': clave_path,
        'csr_path': csr_path,
        'mensajes': mensajes,
        'error': None
    }


def generar_carpeta_empresa(
    base_dir: str,
    empresa: str,
    cuit: str,
    sistema: str = None,
    ambiente: str = "homologacion"
) -> dict:
    """
    Genera certificados en una carpeta organizada por empresa.

    Estructura:
    base_dir/
    ├── empresa_1/
    │   ├── clave.key
    │   ├── pedido.csr
    │   └── config.json        ← NUEVO
    ├── empresa_2/
    │   ├── clave.key
    │   ├── pedido.csr
    │   └── config.json

    Args:
        base_dir: Directorio base (default: certs/)
        empresa: Nombre de la empresa
        cuit: CUIT sin guiones
        sistema: Nombre descriptivo (optional)
        ambiente: "homologacion" o "produccion" (default: homologacion)

    Returns:
        Dict con rutas y estado
    """

    # Crear nombre de carpeta seguro (sin espacios, caracteres especiales)
    nombre_carpeta = f"{empresa.lower().replace(' ', '_')}_{cuit}"
    directorio_empresa = os.path.join(base_dir, nombre_carpeta)

    resultado = generar_certificados_completos(
        directorio=directorio_empresa,
        empresa=empresa,
        cuit=cuit,
        sistema=sistema
    )

    # Guardar metadatos en config.json
    if resultado['éxito']:
        config_data = {
            "empresa": empresa,
            "cuit": cuit,
            "sistema": sistema or empresa.lower().replace(" ", "_"),
            "ambiente": ambiente,
            "fecha_generacion": datetime.now().isoformat(),
            "clave_path": resultado['clave_path'],
            "csr_path": resultado['csr_path'],
            "notas": f"Generado automáticamente. Subir CSR a ARCA en ambiente: {ambiente}"
        }

        config_path = os.path.join(directorio_empresa, "config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            resultado['config_path'] = config_path
            resultado['mensajes'].append(f"✓ Configuración guardada en: {config_path}")
        except Exception as e:
            resultado['mensajes'].append(f"⚠ Advertencia: No se pudo guardar config.json: {str(e)}")

    return resultado


def leer_csr(csr_path: str) -> tuple[bool, str]:
    """
    Lee el contenido del CSR para mostrar al usuario.

    Returns:
        (éxito, contenido o error)
    """
    try:
        with open(csr_path, 'r') as f:
            contenido = f.read()
        return True, contenido
    except FileNotFoundError:
        return False, f"✗ Archivo no encontrado: {csr_path}"
    except Exception as e:
        return False, f"✗ Error leyendo archivo: {str(e)}"


def crear_instrucciones_upload(
    empresa: str,
    cuit: str,
    csr_path: str
) -> str:
    """
    Genera instrucciones claras para subir el CSR a ARCA.
    """

    instrucciones = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    PRÓXIMOS PASOS - SUBIR CSR A ARCA                       ║
╚════════════════════════════════════════════════════════════════════════════╝

✓ Certificados generados para: {empresa}
✓ CUIT: {cuit}
✓ Ubicación: {csr_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 PASOS PARA COMPLETAR EN ARCA:

1. Ingresa a https://www.arca.gob.ar con tu clave fiscal

2. Busca: "Administración de Certificados Digitales"

3. Click en "Crear Nuevo Alias"
   - Nombre: {empresa.lower().replace(' ', '_')}_{cuit}
   - Subir archivo: {csr_path}
   - Confirma

4. Espera a que ARCA firme el certificado (minutos a horas)

5. Cuando esté listo:
   - Ve a "Mis Certificados"
   - Descarga el archivo .crt
   - Guárdalo en la misma carpeta

6. IMPORTANTE - Asociar a WSFE:
   - Ve a "Administrador de Relaciones de Clave Fiscal"
   - Nueva Relación
   - Selecciona: ARCA → Webservices → Factura Electrónica (wsfe)
   - Elige tu certificado (alias)
   - Confirma

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANTE:
   • Archivo CSR: {os.path.basename(csr_path)}
   • Clave privada: clave.key (GUARDA BIEN, no la compartas)
   • Una vez descargado el certificado (.crt), colócalo en la misma carpeta

Una vez tengas el .crt, vuelve a la app y carga el certificado.

"""
    return instrucciones
