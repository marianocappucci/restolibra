"""
Páginas GUI para gestión de facturas electrónicas ARCA.
"""

import os
import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QTextEdit, QMessageBox, QDialog, QFileDialog, QHeaderView,
    QDialogButtonBox
)
from PyQt5.QtCore import Qt, QDate

import database as db
from pdf_factura import generar_pdf_factura
from facturacion_arca import obtener_cae


class FacturasPage(QWidget):
    """Página para listar facturas emitidas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Encabezado con botones
        header_layout = QHBoxLayout()

        header_layout.addWidget(QLabel("Facturas Emitidas"))
        header_layout.addStretch()

        btn_nueva = QPushButton("Nueva Factura")
        btn_nueva.clicked.connect(lambda: self.main_window.show_page("nueva_factura"))
        header_layout.addWidget(btn_nueva)

        btn_recargar = QPushButton("Recargar")
        btn_recargar.clicked.connect(self.refresh)
        header_layout.addWidget(btn_recargar)

        layout.addLayout(header_layout)

        # Búsqueda
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Por número, cliente o observaciones...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(8)
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Tipo", "Número", "Fecha", "Cliente", "Total", "CAE", "Acciones"
        ])
        self.tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.tabla)

        self.setLayout(layout)

    def refresh(self):
        """Recarga la lista de facturas."""
        facturas = db.get_all_facturas()
        self._mostrar_facturas(facturas)

    def on_search(self):
        """Búsqueda en tiempo real."""
        query = self.search_input.text()
        if query:
            facturas = db.search_facturas(query)
        else:
            facturas = db.get_all_facturas()
        self._mostrar_facturas(facturas)

    def _mostrar_facturas(self, facturas):
        """Carga las facturas en la tabla."""
        self.tabla.setRowCount(len(facturas))

        tipo_nombres = {1: "Fac. A", 6: "Fac. B", 3: "NC A", 8: "NC B"}

        for row, factura in enumerate(facturas):
            # ID
            self.tabla.setItem(row, 0, QTableWidgetItem(str(factura['id'])))

            # Tipo
            tipo_nombre = tipo_nombres.get(factura['tipo'], str(factura['tipo']))
            self.tabla.setItem(row, 1, QTableWidgetItem(tipo_nombre))

            # Número
            numero = f"{str(factura['punto_venta']).zfill(4)}-{str(factura['numero']).zfill(8)}"
            self.tabla.setItem(row, 2, QTableWidgetItem(numero))

            # Fecha
            fecha = factura['fecha']
            if len(fecha) == 8:
                fecha = f"{fecha[6:8]}/{fecha[4:6]}/{fecha[0:4]}"
            self.tabla.setItem(row, 3, QTableWidgetItem(fecha))

            # Cliente
            self.tabla.setItem(row, 4, QTableWidgetItem(factura.get('cliente_razon', '')))

            # Total
            self.tabla.setItem(row, 5, QTableWidgetItem(f"${factura['total']:.2f}"))

            # CAE
            cae = factura.get('cae', '')
            self.tabla.setItem(row, 6, QTableWidgetItem(cae if cae else "PENDIENTE"))

            # Acciones
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(2, 2, 2, 2)

            btn_ver = QPushButton("Ver")
            btn_ver.setMaximumWidth(50)
            btn_ver.clicked.connect(lambda checked, fid=factura['id']: self._ver_factura(fid))

            btn_eliminar = QPushButton("Eliminar")
            btn_eliminar.setMaximumWidth(70)
            btn_eliminar.clicked.connect(lambda checked, fid=factura['id']: self._eliminar_factura(fid))

            btn_layout.addWidget(btn_ver)
            btn_layout.addWidget(btn_eliminar)
            btn_layout.addStretch()

            widget = QWidget()
            widget.setLayout(btn_layout)
            self.tabla.setCellWidget(row, 7, widget)

    def _ver_factura(self, factura_id):
        """Abre y muestra la factura."""
        factura = db.get_factura(factura_id)
        if not factura:
            QMessageBox.warning(self, "Error", "Factura no encontrada")
            return

        # Por ahora, solo mostrar mensaje con los datos
        msg = f"""
Factura #{factura['numero']}
Fecha: {factura['fecha']}
Cliente: {factura['cliente_razon']}
Total: ${factura['total']:.2f}
CAE: {factura.get('cae', 'PENDIENTE')}
"""
        QMessageBox.information(self, "Detalles de Factura", msg)

    def _eliminar_factura(self, factura_id):
        """Elimina una factura."""
        resp = QMessageBox.question(
            self,
            "Confirmar",
            "¿Eliminar esta factura?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp == QMessageBox.Yes:
            db.delete_factura(factura_id)
            self.refresh()


class NuevaFacturaPage(QWidget):
    """Página para crear nuevas facturas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.config = db.obtener_arca_config("compulibra")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Encabezado
        layout.addWidget(QLabel("Nueva Factura Electrónica"))

        # Formulario
        form_layout = QVBoxLayout()

        # Tipo de comprobante
        form_layout.addWidget(QLabel("Tipo de Comprobante:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Factura A", "Factura B", "Nota de Crédito A", "Nota de Crédito B"])
        form_layout.addWidget(self.combo_tipo)

        # Cliente
        form_layout.addWidget(QLabel("Cliente:"))
        self.combo_cliente = QComboBox()
        self._cargar_clientes()
        form_layout.addWidget(self.combo_cliente)

        # Fecha
        form_layout.addWidget(QLabel("Fecha:"))
        self.date_factura = QDateEdit()
        self.date_factura.setDate(QDate.currentDate())
        form_layout.addWidget(self.date_factura)

        # Items (simplificado - un solo item por ahora)
        form_layout.addWidget(QLabel("Descripción del Item:"))
        self.input_descripcion = QLineEdit()
        form_layout.addWidget(self.input_descripcion)

        form_layout.addWidget(QLabel("Cantidad:"))
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setValue(1)
        form_layout.addWidget(self.spin_cantidad)

        form_layout.addWidget(QLabel("Precio Unitario:"))
        self.double_precio = QDoubleSpinBox()
        self.double_precio.setPrefix("$")
        self.double_precio.setDecimals(2)
        form_layout.addWidget(self.double_precio)

        # Total (calculado automáticamente)
        form_layout.addWidget(QLabel("Total:"))
        self.label_total = QLabel("$0.00")
        self.label_total.setStyleSheet("font-weight: bold; font-size: 14px;")
        form_layout.addWidget(self.label_total)

        # Observaciones
        form_layout.addWidget(QLabel("Observaciones:"))
        self.text_observaciones = QTextEdit()
        self.text_observaciones.setMaximumHeight(80)
        form_layout.addWidget(self.text_observaciones)

        layout.addLayout(form_layout)

        # Botones
        btn_layout = QHBoxLayout()

        btn_emitir = QPushButton("Emitir Factura (obtener CAE)")
        btn_emitir.clicked.connect(self._emitir_factura)
        btn_layout.addWidget(btn_emitir)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(lambda: self.main_window.show_page("facturas"))
        btn_layout.addWidget(btn_cancelar)

        layout.addLayout(btn_layout)

        # Conectar cambios para actualizar totales
        self.spin_cantidad.valueChanged.connect(self._actualizar_total)
        self.double_precio.valueChanged.connect(self._actualizar_total)

    def _cargar_clientes(self):
        """Carga lista de clientes en el combo."""
        clientes = db.get_all_clients()
        for cliente in clientes:
            self.combo_cliente.addItem(cliente['name'], cliente['id'])

    def _actualizar_total(self):
        """Actualiza el total mostrado."""
        cantidad = self.spin_cantidad.value()
        precio = self.double_precio.value()
        subtotal = cantidad * precio
        iva = subtotal * 0.21
        total = subtotal + iva

        self.label_total.setText(f"${total:.2f}")

    def _emitir_factura(self):
        """Emite la factura en ARCA y obtiene el CAE."""
        if not self.config:
            QMessageBox.critical(self, "Error", "No hay configuración ARCA cargada")
            return

        if not self.input_descripcion.text():
            QMessageBox.warning(self, "Error", "Debes ingresar una descripción")
            return

        if self.double_precio.value() <= 0:
            QMessageBox.warning(self, "Error", "El precio debe ser mayor a 0")
            return

        try:
            # Datos de la factura
            cliente_id = self.combo_cliente.currentData()
            cliente = db.get_client(cliente_id)

            tipo_map = {0: 1, 1: 6, 2: 3, 3: 8}  # Combobox indices to tipo codes
            tipo = tipo_map[self.combo_tipo.currentIndex()]

            fecha = self.date_factura.date().toString("yyyyMMdd")
            cantidad = self.spin_cantidad.value()
            precio = self.double_precio.value()
            subtotal = cantidad * precio
            iva = subtotal * 0.21
            total = subtotal + iva

            items = [{
                'descripcion': self.input_descripcion.text(),
                'cantidad': cantidad,
                'precio': precio
            }]

            # Obtener el próximo número
            # (En una implementación real, esto iría a ARCA)
            proximo_numero = self._obtener_proximo_numero_local(tipo)

            # Intenta emitir (esto requiere que el certificado esté correctamente inscrito en ARCA)
            QMessageBox.information(
                self,
                "Factura Preparada",
                f"La factura está lista para emitir.\n\n"
                f"Nota: Para obtener el CAE realmente, tu certificado debe estar inscrito en ARCA.\n"
                f"Número de factura: {self.config['punto_venta']}-{proximo_numero}\n"
                f"Total: ${total:.2f}"
            )

            # Crear en base de datos
            factura_id = db.create_factura(
                tipo=tipo,
                punto_venta=self.config['punto_venta'],
                numero=proximo_numero,
                fecha=fecha,
                cliente_cuit=cliente['cuit_dni'] if cliente else "",
                cliente_razon=cliente['name'] if cliente else "Sin cliente",
                cliente_iva_cond=1,  # RI por defecto
                items=items,
                subtotal=subtotal,
                iva_amount=iva,
                total=total,
                observaciones=self.text_observaciones.toPlainText()
            )

            # Generar PDF
            empresa_datos = {
                'nombre': "COMPULIBRA S.A.",
                'cuit': self.config['cuit'],
                'iibb': "N/A",
                'direccion': "Av. Siempre Viva 123",
                'telefono': "(011) 1234-5678",
                'email': "info@compulibra.com.ar"
            }

            factura_datos = {
                'tipo': tipo,
                'punto_venta': self.config['punto_venta'],
                'numero': proximo_numero,
                'fecha': fecha,
                'cliente_razon': cliente['name'] if cliente else "Sin cliente",
                'cliente_cuit': cliente['cuit_dni'] if cliente else "",
                'items': items,
                'subtotal': subtotal,
                'iva_amount': iva,
                'total': total,
                'cae': '',  # Se llenará cuando obtenga el CAE
                'cae_vto': '',
                'observaciones': self.text_observaciones.toPlainText()
            }

            # Crear carpeta para facturas si no existe
            os.makedirs("facturas_pdf", exist_ok=True)

            pdf_path = f"facturas_pdf/factura_{self.config['punto_venta']}_{proximo_numero}.pdf"
            generar_pdf_factura(empresa_datos, factura_datos, pdf_path)

            db.update_factura_pdf_path(factura_id, pdf_path)

            QMessageBox.information(self, "Éxito", f"Factura creada:\n{pdf_path}")

            # Volver a listado
            self.main_window.show_page("facturas")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error emitiendo factura:\n{str(e)}")

    def _obtener_proximo_numero_local(self, tipo):
        """Obtiene el próximo número local (sin conectarse a ARCA)."""
        facturas = db.get_all_facturas()
        numeros = [f['numero'] for f in facturas if f['tipo'] == tipo]
        if numeros:
            return max(numeros) + 1
        return 1
