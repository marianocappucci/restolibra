"""
Módulo de facturación electrónica integrado con ARCA (ex-AFIP).

Maneja autenticación con WSAA y solicitud de CAE con WSFEV1.
"""

import sys
import os
from datetime import datetime, timedelta
import database as db

try:
    from pyafipws.wsaa import WSAA
    from pyafipws.wsfev1 import WSFEv1
    PYAFIPWS_DISPONIBLE = True
except ImportError:
    PYAFIPWS_DISPONIBLE = False


class AutenticacionARCA:
    """Gestiona la autenticación con WSAA."""

    def __init__(self, empresa_name, timeout=30):
        self.empresa_name = empresa_name
        self.timeout = timeout
        self.config = db.obtener_arca_config(empresa_name)

        if not self.config:
            raise ValueError(f"Configuración ARCA no encontrada para: {empresa_name}")

        self.wsaa = None
        self.token = None
        self.sign = None

    def conectar(self):
        """Realiza la autenticación con WSAA y obtiene Token + Sign."""
        try:
            self.wsaa = WSAA()
            self.wsaa.Cuit = self.config['cuit']
            self.wsaa.HOMO = (self.config['ambiente'] == 'homologacion')
            self.wsaa.LanzarExcepciones = True

            # Autenticar
            ta = self.wsaa.Autenticar(
                service="wsfe",
                crt=self.config['certificado_path'],
                key=self.config['clave_path'],
                cache=""
            )

            if not ta:
                raise ValueError("No se obtuvo ticket de acceso de WSAA")

            self.token = self.wsaa.Token
            self.sign = self.wsaa.Sign

            return True

        except Exception as e:
            raise RuntimeError(f"Error en autenticación WSAA: {str(e)}")

    def obtener_credentials(self):
        """Retorna (token, sign) para usar en WSFEV1."""
        if not self.token or not self.sign:
            raise ValueError("No autenticado. Ejecuta conectar() primero.")
        return (self.token, self.sign)


class FacturacionARCA:
    """Gestiona la creación de facturas y obtención del CAE."""

    # Códigos de tipo de comprobante
    TIPO_FACTURA_A = 1
    TIPO_FACTURA_B = 6
    TIPO_NOTA_CREDITO_A = 3
    TIPO_NOTA_CREDITO_B = 8

    # Códigos de condición IVA
    CONDICION_IVA = {
        'RI': 1,      # Responsable Inscripto
        'Exento': 2,  # Exento
        'CF': 5,      # Consumidor Final
        'MISP': 4,    # Monotributista
    }

    # Códigos de concepto
    CONCEPTO_PRODUCTOS = 1
    CONCEPTO_SERVICIOS = 2
    CONCEPTO_AMBOS = 3

    def __init__(self, empresa_name):
        self.empresa_name = empresa_name
        self.config = db.obtener_arca_config(empresa_name)

        if not self.config:
            raise ValueError(f"Configuración ARCA no encontrada para: {empresa_name}")

        self.wsfev1 = None
        self.token = None
        self.sign = None

    def conectar(self, token, sign):
        """Conecta con WSFEV1 usando token y sign de WSAA."""
        try:
            self.wsfev1 = WSFEv1()
            self.wsfev1.Cuit = self.config['cuit']
            self.wsfev1.HOMO = (self.config['ambiente'] == 'homologacion')
            self.wsfev1.LanzarExcepciones = True

            # Conectar a WSFEV1
            self.wsfev1.Conectar(cache="")

            # Configurar ticket de acceso
            self.wsfev1.SetTicketAcceso(token, sign)

            self.token = token
            self.sign = sign

            return True

        except Exception as e:
            raise RuntimeError(f"Error conectando a WSFEV1: {str(e)}")

    def obtener_proximo_numero(self, tipo_comprobante):
        """Obtiene el próximo número de comprobante para el tipo dado."""
        try:
            num = self.wsfev1.CompUltimoAutorizado(
                self.config['punto_venta'],
                tipo_comprobante
            )
            if num:
                return int(num) + 1
            else:
                # Si no hay comprobantes previos, empieza en 1
                return 1
        except Exception as e:
            raise RuntimeError(f"Error obteniendo próximo número: {str(e)}")

    def crear_factura(self, tipo, numero, fecha, cliente_cuit, cliente_razon,
                      cliente_iva_cond, items, subtotal, iva_amount, total,
                      concepto=CONCEPTO_PRODUCTOS, observaciones=""):
        """
        Crea una factura en ARCA y obtiene el CAE.

        Args:
            tipo: Tipo de comprobante (1=Factura A, 6=Factura B, etc)
            numero: Número de comprobante
            fecha: Fecha en formato YYYYMMDD
            cliente_cuit: CUIT del cliente
            cliente_razon: Razón social del cliente
            cliente_iva_cond: Condición IVA (1=RI, 2=Exento, 5=CF, 4=MISP)
            items: Lista de dicts con keys: descripcion, cantidad, precio, iva
            subtotal: Monto neto
            iva_amount: Monto IVA
            total: Total de la factura
            concepto: 1=Productos, 2=Servicios, 3=Ambos
            observaciones: Observaciones

        Returns:
            dict con keys: cae, vto_cae, factura_id (DB)
        """
        try:
            # Crear factura en WSFEV1
            self.wsfev1.CrearFactura(
                tipo_cbte=tipo,
                punto_vta=self.config['punto_venta'],
                cbte_nro=numero,
                imp_total=total,
                imp_neto=subtotal,
                imp_iva=iva_amount,
                imp_otros_tributos=0,
                fecha_cbte=fecha,
                fecha_venc_pago=fecha,  # Por ahora mismo día
                tipo_doc=80,  # CUIT (80 para Argentina)
                nro_doc=int(cliente_cuit.replace("-", "")),
                concepto=concepto,
                tipo_expo=0,  # No exportación
                moneda_id='PES'  # Pesos argentinos
            )

            # Agregar IVA (21% es lo más común)
            self.wsfev1.AgregarIVA(
                alicuota=21.0,
                base_imponible=subtotal
            )

            # Solicitar CAE
            cae = self.wsfev1.CAESolicitar()

            if not cae:
                error_msg = ""
                if hasattr(self.wsfev1, 'ErrMsg'):
                    error_msg = self.wsfev1.ErrMsg
                if hasattr(self.wsfev1, 'Errores') and self.wsfev1.Errores:
                    for err in self.wsfev1.Errores:
                        error_msg += f"\n  - {err}"
                raise ValueError(f"No se obtuvo CAE: {error_msg}")

            # Obtener vencimiento del CAE
            vto_cae = ""
            if hasattr(self.wsfev1, 'VtoCAE'):
                vto_cae = self.wsfev1.VtoCAE

            # Guardar en base de datos
            factura_id = db.create_factura(
                tipo=tipo,
                punto_venta=self.config['punto_venta'],
                numero=numero,
                fecha=fecha,
                cliente_cuit=cliente_cuit,
                cliente_razon=cliente_razon,
                cliente_iva_cond=cliente_iva_cond,
                items=items,
                subtotal=subtotal,
                iva_amount=iva_amount,
                total=total,
                concepto=concepto,
                cae=cae,
                cae_vto=vto_cae,
                observaciones=observaciones
            )

            return {
                'cae': cae,
                'vto_cae': vto_cae,
                'factura_id': factura_id,
                'numero': numero
            }

        except Exception as e:
            raise RuntimeError(f"Error creando factura en ARCA: {str(e)}")


def obtener_cae(empresa_name, tipo, numero, fecha, cliente_cuit, cliente_razon,
                cliente_iva_cond, items, subtotal, iva_amount, total,
                concepto=1, observaciones=""):
    """
    Función de conveniencia: realiza toda la secuencia para obtener un CAE.

    Returns:
        dict con cae, vto_cae, factura_id
    """
    if not PYAFIPWS_DISPONIBLE:
        raise RuntimeError(
            "pyafipws no está instalado. Ejecutá: pip install pyafipws"
        )
    # Fase 1: Autenticación
    auth = AutenticacionARCA(empresa_name)
    auth.conectar()
    token, sign = auth.obtener_credentials()

    # Fase 2: Facturación
    fact = FacturacionARCA(empresa_name)
    fact.conectar(token, sign)

    resultado = fact.crear_factura(
        tipo=tipo,
        numero=numero,
        fecha=fecha,
        cliente_cuit=cliente_cuit,
        cliente_razon=cliente_razon,
        cliente_iva_cond=cliente_iva_cond,
        items=items,
        subtotal=subtotal,
        iva_amount=iva_amount,
        total=total,
        concepto=concepto,
        observaciones=observaciones
    )

    return resultado
