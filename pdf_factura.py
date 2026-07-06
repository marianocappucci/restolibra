"""
Generador de PDF para facturas electrónicas con formato legal ARCA.

Incluye encabezado, tabla de items, caja de datos ARCA con CAE, y código QR.
"""

import os
from datetime import datetime
from fpdf import FPDF
import qrcode
import io
import config_manager


class FacturaPDF(FPDF):
    """Clase para generar PDFs de facturas electrónicas con formato ARCA."""

    def __init__(self, empresa_datos, factura_datos):
        """
        Args:
            empresa_datos: dict con keys: nombre, cuit, iibb, direccion, telefono, email
            factura_datos: dict con keys: tipo, numero, fecha, cliente_*, items, cae, etc
        """
        super().__init__()
        self.empresa = empresa_datos
        self.factura = factura_datos
        self.add_page()
        self.set_font("Helvetica", size=10)

    def encabezado(self):
        """Dibuja el encabezado con datos de la empresa."""
        tipo_nombres = {
            1: "FACTURA A",
            6: "FACTURA B",
            3: "NOTA DE CRÉDITO A",
            8: "NOTA DE CRÉDITO B"
        }
        tipo_txt = tipo_nombres.get(self.factura.get('tipo'), 'DOCUMENTO')

        # Logo (si existe)
        logo_path = config_manager.load().get("logo_path", "")
        y = 10
        if logo_path and os.path.exists(logo_path):
            self.image(logo_path, x=10, y=y, h=20)
            y += 22

        # Título centrado
        self.set_y(y)
        self.set_font("Helvetica", "B", size=14)
        self.cell(0, 8, tipo_txt, ln=True, align='C')

        # Línea separadora
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(1)

        # Datos de la empresa
        self.set_font("Helvetica", "B", size=11)
        self.cell(0, 6, self.empresa['nombre'], ln=True)

        self.set_font("Helvetica", size=9)
        self.cell(0, 5, f"CUIT: {self.empresa['cuit']}", ln=True)
        self.cell(0, 5, f"I.I.B.B.: {self.empresa.get('iibb', 'N/A')}", ln=True)
        self.cell(0, 5, f"Dirección: {self.empresa.get('direccion', '')}", ln=True)
        self.cell(0, 5, f"Teléfono: {self.empresa.get('telefono', '')}", ln=True)
        self.cell(0, 5, f"Email: {self.empresa.get('email', '')}", ln=True)

    def datos_factura(self):
        """Dibuja los datos de emisión de la factura."""
        y_inicio = self.get_y()

        # Columna izquierda: Punto de venta y número
        self.set_font("Helvetica", "B", size=10)
        self.set_xy(10, y_inicio)
        self.cell(40, 6, "Punto Venta:", ln=False)
        self.set_font("Helvetica", size=10)
        self.cell(20, 6, str(self.factura.get('punto_venta', 0)).zfill(4), ln=True)

        self.set_font("Helvetica", "B", size=10)
        self.set_xy(10, self.get_y())
        self.cell(40, 6, "Nro. Comprobante:", ln=False)
        self.set_font("Helvetica", size=10)
        self.cell(20, 6, str(self.factura.get('numero', 0)).zfill(8), ln=True)

        # Columna derecha: Fecha
        self.set_xy(150, y_inicio)
        self.set_font("Helvetica", "B", size=10)
        self.cell(30, 6, "Fecha:", ln=False)
        self.set_font("Helvetica", size=10)
        fecha_str = self.factura.get('fecha', '')
        if len(fecha_str) == 8:
            fecha_str = f"{fecha_str[6:8]}/{fecha_str[4:6]}/{fecha_str[0:4]}"
        self.cell(20, 6, fecha_str, ln=True)

    def datos_cliente(self):
        """Dibuja los datos del cliente."""
        self.set_font("Helvetica", "B", size=10)
        self.cell(0, 5, "DATOS DEL CLIENTE:", ln=True)

        self.set_font("Helvetica", size=9)
        self.cell(30, 5, "Razón Social:", ln=False)
        self.set_font("Helvetica", size=9)
        self.cell(0, 5, self.factura.get('cliente_razon', ''), ln=True)

        self.set_font("Helvetica", "B", size=9)
        self.cell(30, 5, "CUIT:", ln=False)
        self.set_font("Helvetica", size=9)
        self.cell(0, 5, self.factura.get('cliente_cuit', ''), ln=True)

        # Línea separadora
        self.line(10, self.get_y(), 200, self.get_y())

    def items_tabla(self):
        """Dibuja la tabla de items."""
        # Encabezados
        self.set_font("Helvetica", "B", size=9)
        self.set_fill_color(230, 230, 230)

        col_widths = [80, 20, 25, 30]  # Descripción, Cantidad, Precio Unit, Subtotal
        headers = ["Descripción", "Cantidad", "P. Unit", "Subtotal"]

        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=1, align='C', fill=True)
        self.ln()

        # Items
        self.set_font("Helvetica", size=9)
        for item in self.factura.get('items', []):
            desc = item.get('descripcion', '')[:40]  # Truncar si es muy largo
            cant = item.get('cantidad', 1)
            precio = item.get('precio', 0)
            subtotal = cant * precio

            self.cell(col_widths[0], 6, desc, border=1)
            self.cell(col_widths[1], 6, f"{cant}", border=1, align='R')
            self.cell(col_widths[2], 6, f"${precio:.2f}", border=1, align='R')
            self.cell(col_widths[3], 6, f"${subtotal:.2f}", border=1, align='R')
            self.ln()

        # Línea separadora
        self.line(10, self.get_y(), 200, self.get_y())

    def totales(self):
        """Dibuja subtotal, IVA y total."""
        self.set_font("Helvetica", size=9)

        subtotal = self.factura.get('subtotal', 0)
        iva = self.factura.get('iva_amount', 0)
        total = self.factura.get('total', 0)

        # Alineados a la derecha
        self.cell(140, 6, "Subtotal:", ln=False, align='R')
        self.cell(30, 6, f"${subtotal:.2f}", ln=True, align='R')

        self.cell(140, 6, "IVA (21%):", ln=False, align='R')
        self.cell(30, 6, f"${iva:.2f}", ln=True, align='R')

        # Total en grande
        self.set_font("Helvetica", "B", size=11)
        self.cell(140, 7, "TOTAL:", ln=False, align='R')
        self.cell(30, 7, f"${total:.2f}", ln=True, align='R', border=1)

    def caja_arca(self):
        """Dibuja la caja de datos ARCA (CAE, vencimiento, etc)."""
        self.ln(5)

        # Marco
        self.set_line_width(2)
        self.rect(10, self.get_y(), 190, 25)
        self.set_line_width(0.4)

        y_caja = self.get_y()

        # Línea vertical divisoria
        self.line(95, y_caja, 95, y_caja + 25)

        # Columna izquierda: CAE
        self.set_xy(15, y_caja + 2)
        self.set_font("Helvetica", "B", size=8)
        self.cell(0, 4, "CAE:", ln=True)

        self.set_font("Helvetica", size=12)
        cae = self.factura.get('cae', '')
        self.cell(0, 6, cae if cae else "PENDIENTE", ln=True)

        # Columna derecha: Vencimiento
        self.set_xy(105, y_caja + 2)
        self.set_font("Helvetica", "B", size=8)
        self.cell(0, 4, "Vencimiento CAE:", ln=True)

        self.set_font("Helvetica", size=10)
        vto = self.factura.get('cae_vto', '')
        if vto and len(vto) == 8:
            vto = f"{vto[6:8]}/{vto[4:6]}/{vto[0:4]}"
        self.cell(0, 6, vto if vto else "PENDIENTE", ln=True)

        # Mover cursor debajo de la caja
        self.set_y(y_caja + 25)

    def codigo_qr(self):
        """Dibuja el código QR ARCA (si hay CAE)."""
        cae = self.factura.get('cae', '')
        if not cae:
            return

        self.ln(5)

        # Generar datos para QR: formato ARCA
        # https://www.afip.gob.ar/fe/consultas/manual_construir_qr.pdf
        cuit_empresa = self.empresa.get('cuit', '').replace("-", "")
        punto_venta = str(self.factura.get('punto_venta', 0)).zfill(4)
        numero = str(self.factura.get('numero', 0)).zfill(8)
        fecha = self.factura.get('fecha', '')
        total = f"{self.factura.get('total', 0):.2f}"

        # Datos del QR (formato: https://www.afip.gob.ar/...)
        qr_data = f"https://www.afip.gob.ar/fe/qr/?p={cuit_empresa}|{punto_venta}|{numero}|{fecha}|{total}|{cae}"

        # Generar QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Convertir a imagen en memoria
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Guardar temporalmente
        qr_path = "/tmp/qr_temp.png"
        qr_img.save(qr_path)

        # Insertar en PDF
        self.image(qr_path, x=15, y=self.get_y(), w=30, h=30)
        self.set_xy(50, self.get_y())
        self.set_font("Helvetica", size=8)
        self.cell(0, 10, "Código QR ARCA", ln=True)

        # Limpiar
        if os.path.exists(qr_path):
            os.remove(qr_path)

    def observaciones(self):
        """Dibuja observaciones si las hay."""
        obs = self.factura.get('observaciones', '')
        if obs:
            self.ln(2)
            self.set_font("Helvetica", "B", size=9)
            self.cell(0, 5, "Observaciones:", ln=True)
            self.set_font("Helvetica", size=8)
            self.multi_cell(0, 4, obs)

    def generar(self, output_path):
        """Genera el PDF completo."""
        self.encabezado()
        self.ln(3)

        self.datos_factura()
        self.ln(3)

        self.datos_cliente()
        self.ln(3)

        self.items_tabla()
        self.ln(2)

        self.totales()

        self.caja_arca()

        self.codigo_qr()

        self.ln(3)
        self.observaciones()

        # Pie de página
        self.ln(5)
        self.set_font("Helvetica", size=7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, "Documento emitido por sistema de Facturación Electrónica - ARCA", align='C')

        # Guardar
        self.output(output_path)
        return output_path


def generar_pdf_factura(empresa_datos, factura_datos, output_path):
    """
    Función de conveniencia para generar un PDF de factura.

    Args:
        empresa_datos: dict con datos de la empresa
        factura_datos: dict con datos de la factura
        output_path: ruta donde guardar el PDF

    Returns:
        ruta del archivo generado
    """
    pdf = FacturaPDF(empresa_datos, factura_datos)
    return pdf.generar(output_path)
