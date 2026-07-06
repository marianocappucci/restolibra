#!/usr/bin/env python3
"""
Script de prueba para conectar a ARCA y obtener CAE en homologación.
Usa WSAA para autenticación y WSFEv1 para facturación.
"""

import sys
import os
from datetime import datetime
import database as db

# Importar las clases correctas
try:
    from pyafipws.wsaa import WSAA
    from pyafipws.wsfev1 import WSFEv1
except ImportError as e:
    print(f"❌ Error al importar pyafipws: {e}")
    print("Instala con: pip install pyafipws")
    sys.exit(1)


def test_arca():
    """Prueba conexión a ARCA y obtiene CAE."""

    print("\n" + "="*70)
    print("TEST DE CONEXIÓN A ARCA - HOMOLOGACIÓN")
    print("="*70 + "\n")

    # Obtener configuración de ARCA
    config = db.obtener_arca_config("compulibra")

    if not config:
        print("❌ Error: No hay configuración ARCA cargada para 'compulibra'")
        print("   Ve a la app → Certificado ARCA → Cargar Certificado")
        return False

    print(f"✓ Configuración encontrada:")
    print(f"  - Empresa: {config['empresa']}")
    print(f"  - CUIT: {config['cuit']}")
    print(f"  - Punto de venta: {config['punto_venta']}")
    print(f"  - Ambiente: {config['ambiente']}")
    print()

    # Verificar que los archivos existan
    if not os.path.exists(config['clave_path']):
        print(f"❌ Error: Clave privada no encontrada en {config['clave_path']}")
        return False
    if not os.path.exists(config['certificado_path']):
        print(f"❌ Error: Certificado no encontrado en {config['certificado_path']}")
        return False

    print("✓ Archivos de certificado verificados\n")

    try:
        # PASO 1: Autenticar con WSAA
        print("━" * 70)
        print("PASO 1: Autenticación con WSAA")
        print("━" * 70 + "\n")

        wsaa = WSAA()
        wsaa.Cuit = config['cuit']
        wsaa.HOMO = True  # Homologación
        wsaa.LanzarExcepciones = True

        print("Autenticando con certificado...")
        print(f"  Certificado: {config['certificado_path']}")
        print(f"  Clave: {config['clave_path']}\n")
        try:
            ta = wsaa.Autenticar(
                service="wsfe",
                crt=config['certificado_path'],
                key=config['clave_path'],
                cache="",
                debug=True
            )
        except Exception as e:
            print(f"❌ Error en autenticación WSAA")
            print(f"   Error: {str(e)}")
            return False

        if not ta:
            print(f"❌ Error en autenticación WSAA")
            if hasattr(wsaa, 'ErrMsg'):
                print(f"   Error: {wsaa.ErrMsg}")
            return False

        token = wsaa.Token
        sign = wsaa.Sign

        print(f"✅ Token obtenido")
        print(f"   Token: {token[:50]}...")
        print(f"   Sign: {sign[:50]}...\n")

        # PASO 2: Usar WSFEv1 con el token
        print("━" * 70)
        print("PASO 2: Facturación con WSFEv1")
        print("━" * 70 + "\n")

        wsfev1 = WSFEv1()
        wsfev1.Cuit = config['cuit']
        wsfev1.HOMO = True  # Homologación
        wsfev1.LanzarExcepciones = True

        print("Conectando a WSFEv1...")
        wsfev1.Conectar(cache="")
        print("✓ Conectado\n")

        print("Configurando ticket de acceso...")
        wsfev1.SetTicketAcceso(token, sign)
        print("✓ Ticket configurado\n")

        # Obtener último número
        print("Consultando último número de comprobante...")
        last_number = wsfev1.CompUltimoAutorizado(
            config['punto_venta'],
            1  # Tipo de comprobante: 1 = Factura A
        )

        if not last_number:
            print(f"❌ Error obteniendo último número")
            print(f"   Error: {wsfev1.ErrMsg}")
            return False

        print(f"✓ Último número: {last_number}\n")

        # Crear factura de prueba
        print("Preparando factura de prueba...")
        nuevo_numero = int(last_number) + 1
        fecha = int(datetime.now().strftime("%Y%m%d"))

        print(f"  - Tipo: Factura A")
        print(f"  - Punto de venta: {config['punto_venta']}")
        print(f"  - Número: {nuevo_numero}")
        print(f"  - Fecha: {fecha}")
        print(f"  - Total: $100.00\n")

        # Crear la factura
        print("Creando factura...")
        wsfev1.CrearFactura(
            tipo_cbte=1,  # Factura A
            punto_vta=config['punto_venta'],
            cbte_nro=nuevo_numero,
            imp_total=100.00,
            imp_neto=82.64,
            imp_iva=17.36,
            imp_otros_tributos=0,
            fecha_cbte=fecha,
            fecha_venc_pago=fecha,
            tipo_doc=80,  # CUIT
            nro_doc=20000000001,  # Cliente de prueba
            concepto=1,  # Productos
            tipo_expo=0
        )

        # Agregar IVA
        print("Agregando detalles de IVA...")
        wsfev1.AgregarIVA(
            alicuota=21.0,
            base_imponible=82.64
        )

        # Solicitar CAE
        print("Solicitando CAE...\n")
        cae = wsfev1.CAESolicitar()

        if not cae:
            print(f"❌ Error obteniendo CAE")
            print(f"   Error: {wsfev1.ErrMsg}")
            if hasattr(wsfev1, 'Errores') and wsfev1.Errores:
                print(f"   Detalles:")
                for error in wsfev1.Errores:
                    print(f"     - {error}")
            return False

        vto_cae = wsfev1.VtoCAE if hasattr(wsfev1, 'VtoCAE') else "Sin info"

        print("="*70)
        print("✅ ÉXITO - CAE OBTENIDO")
        print("="*70)
        print(f"\nCAE: {cae}")
        print(f"Vencimiento: {vto_cae}")
        print(f"\n✓ Certificado funciona correctamente")
        print(f"✓ Conexión a ARCA verificada")
        print(f"\nAhora estás listo para integrar facturación en la app.\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Asegurarse de estar en el directorio correcto
    os.chdir(os.path.dirname(__file__) or '.')

    # Inicializar BD
    db.init_db()

    # Ejecutar test
    éxito = test_arca()
    sys.exit(0 if éxito else 1)
