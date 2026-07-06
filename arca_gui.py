"""
Página GUI para generar y cargar certificados ARCA.
"""

import os
import glob
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFormLayout, QMessageBox, QScrollArea, QFrame, QTextEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSpinBox,
    QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

import arca_setup
import database as db


def make_btn(label, style="primary"):
    """Helper para crear botones con estilo."""
    btn = QPushButton(label)
    btn.setCursor(Qt.PointingHandCursor)

    styles = {
        "primary": "background-color: #2563eb; color: white; padding: 8px 16px; border-radius: 5px; font-weight: bold; border: none;",
        "success": "background-color: #16a34a; color: white; padding: 8px 16px; border-radius: 5px; font-weight: bold; border: none;",
        "danger": "background-color: #dc2626; color: white; padding: 8px 16px; border-radius: 5px; font-weight: bold; border: none;",
        "secondary": "background-color: #6b7280; color: white; padding: 8px 16px; border-radius: 5px; border: none;",
        "muted": "background-color: #d1d5db; color: #374151; padding: 8px 16px; border-radius: 5px; border: none;",
    }
    btn.setStyleSheet(styles.get(style, styles["primary"]))
    return btn


class ARCAConfigPage(QWidget):
    """Página para generar y cargar certificados ARCA."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        # Título
        title = QLabel("Configuración ARCA")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        root.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_generar_tab(), "Generar Certificado")
        tabs.addTab(self._build_cargar_tab(), "Cargar Certificado")
        tabs.addTab(self._build_ver_configurados_tab(), "Ver Certificados Cargados")
        root.addWidget(tabs)

    def _build_generar_tab(self):
        """Tab para generar nuevos certificados."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        # Descripción
        desc = QLabel(
            "Genera automáticamente una clave privada y CSR.\n"
            "Luego sube el CSR a ARCA para obtener el certificado."
        )
        desc.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(desc)

        # Card: Datos
        card1, form1 = self._card("Datos de la Empresa")
        layout.addWidget(card1)

        self._empresa_edit = QLineEdit()
        self._empresa_edit.setPlaceholderText("Ej: compulibra")
        form1.addRow("Nombre Empresa *", self._empresa_edit)

        self._cuit_gen_edit = QLineEdit()
        self._cuit_gen_edit.setPlaceholderText("Ej: 20289933604 (sin guiones)")
        self._cuit_gen_edit.setMaximumWidth(300)
        form1.addRow("CUIT *", self._cuit_gen_edit)

        self._sistema_edit = QLineEdit()
        self._sistema_edit.setPlaceholderText("Ej: sistemas_remitos (opcional)")
        form1.addRow("Nombre del Sistema", self._sistema_edit)

        # Card: Directorio y Ambiente
        card2, form2 = self._card("Ubicación y Ambiente")
        layout.addWidget(card2)

        self._directorio_edit = QLineEdit()
        self._directorio_edit.setText("certs/")
        form2.addRow("Directorio", self._directorio_edit)

        info = QLabel("Se guardará en: <directorio>/<empresa>_<cuit>/")
        info.setStyleSheet("color: #64748b; font-size: 11px;")
        form2.addRow("", info)

        self._ambiente_gen_combo = QComboBox()
        self._ambiente_gen_combo.addItems(["homologacion", "produccion"])
        self._ambiente_gen_combo.setMaximumWidth(300)
        form2.addRow("Ambiente ARCA *", self._ambiente_gen_combo)

        ambiente_info = QLabel(
            "Selecciona el ambiente donde subirás el CSR en ARCA.\n"
            "Esto se guarda en config.json para referencia."
        )
        ambiente_info.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        form2.addRow("", ambiente_info)

        # Botones
        btns_layout = QHBoxLayout()
        b_generar = make_btn("Generar Certificado", "success")
        b_generar.clicked.connect(self._generar)
        btns_layout.addWidget(b_generar)
        btns_layout.addStretch()
        layout.addLayout(btns_layout)

        # Resultado
        card3, form3 = self._card("Resultado")
        layout.addWidget(card3)

        self._resultado_text = QTextEdit()
        self._resultado_text.setReadOnly(True)
        self._resultado_text.setMinimumHeight(250)
        self._resultado_text.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 5px; "
            "font-family: 'Courier New', monospace; font-size: 11px;"
        )
        form3.addRow(self._resultado_text)

        layout.addStretch()
        return widget

    def _build_cargar_tab(self):
        """Tab para cargar certificados generados."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        desc = QLabel(
            "Carga un certificado ya generado y descargado de ARCA.\n"
            "Esto registra el certificado en la aplicación para usar en facturación."
        )
        desc.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(desc)

        # Card: Selección
        card1, form1 = self._card("Datos del Certificado")
        layout.addWidget(card1)

        self._carga_empresa_edit = QLineEdit()
        self._carga_empresa_edit.setPlaceholderText("Ej: compulibra")
        form1.addRow("Nombre Empresa *", self._carga_empresa_edit)

        self._carga_cuit_edit = QLineEdit()
        self._carga_cuit_edit.setPlaceholderText("Ej: 20289933604")
        self._carga_cuit_edit.setMaximumWidth(300)
        form1.addRow("CUIT *", self._carga_cuit_edit)

        self._punto_venta_spin = QSpinBox()
        self._punto_venta_spin.setMinimum(1)
        self._punto_venta_spin.setMaximum(9999)
        self._punto_venta_spin.setValue(1)
        form1.addRow("Punto de Venta (ARCA) *", self._punto_venta_spin)

        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText("Nombre del alias en ARCA (Ej: sistemaremitos_2024)")
        form1.addRow("Alias (opcional)", self._alias_edit)

        # Card: Rutas
        card2, form2 = self._card("Rutas de los Archivos")
        layout.addWidget(card2)

        btn_row = QHBoxLayout()
        self._clave_edit = QLineEdit()
        self._clave_edit.setPlaceholderText("Ruta a clave.key")
        self._clave_edit.setReadOnly(True)
        btn_row.addWidget(self._clave_edit)
        b_browse_clave = make_btn("...", "secondary")
        b_browse_clave.setMaximumWidth(50)
        b_browse_clave.clicked.connect(self._browse_clave)
        btn_row.addWidget(b_browse_clave)
        form2.addRow("Clave Privada *", btn_row)

        btn_row2 = QHBoxLayout()
        self._cert_edit = QLineEdit()
        self._cert_edit.setPlaceholderText("Ruta a certificado.crt")
        self._cert_edit.setReadOnly(True)
        btn_row2.addWidget(self._cert_edit)
        b_browse_cert = make_btn("...", "secondary")
        b_browse_cert.setMaximumWidth(50)
        b_browse_cert.clicked.connect(self._browse_cert)
        btn_row2.addWidget(b_browse_cert)
        form2.addRow("Certificado (.crt) *", btn_row2)

        # Card: Ambiente
        card3, form3 = self._card("Configuración")
        layout.addWidget(card3)

        self._ambiente_combo = QComboBox()
        self._ambiente_combo.addItems(["homologacion", "produccion"])
        form3.addRow("Ambiente *", self._ambiente_combo)

        # Botones
        btns_layout = QHBoxLayout()
        b_cargar = make_btn("Cargar y Guardar", "success")
        b_cargar.clicked.connect(self._cargar_certificado)
        btns_layout.addWidget(b_cargar)
        btns_layout.addStretch()
        layout.addLayout(btns_layout)

        layout.addStretch()
        return widget

    def _build_ver_configurados_tab(self):
        """Tab para ver certificados ya cargados."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)

        desc = QLabel("Certificados cargados y disponibles para usar:")
        desc.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(desc)

        # Tabla
        self._tabla_certs = QTableWidget()
        self._tabla_certs.setColumnCount(5)
        self._tabla_certs.setHorizontalHeaderLabels(
            ["Empresa", "CUIT", "Punto Venta", "Ambiente", "Alias"]
        )
        self._tabla_certs.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tabla_certs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tabla_certs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tabla_certs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tabla_certs.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._tabla_certs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabla_certs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla_certs.setAlternatingRowColors(True)
        self._tabla_certs.verticalHeader().setVisible(False)
        layout.addWidget(self._tabla_certs)

        # Botones
        btns_layout = QHBoxLayout()
        b_refresh = make_btn("Actualizar", "secondary")
        b_refresh.clicked.connect(self._refrescar_tabla_certs)
        b_eliminar = make_btn("Eliminar Seleccionado", "danger")
        b_eliminar.clicked.connect(self._eliminar_cert_seleccionado)
        btns_layout.addWidget(b_refresh)
        btns_layout.addWidget(b_eliminar)
        btns_layout.addStretch()
        layout.addLayout(btns_layout)

        layout.addStretch()
        self._refrescar_tabla_certs()
        return widget

    def _card(self, title):
        """Crea una tarjeta con título."""
        card = QFrame()
        card.setStyleSheet(
            "background-color: white; border: 1px solid #e2e8f0; border-radius: 8px;"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(12)

        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f172a;")
        v.addWidget(lbl)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)
        v.addLayout(form)

        return card, form

    def _generar(self):
        """Genera clave y CSR."""
        empresa = self._empresa_edit.text().strip()
        cuit = self._cuit_gen_edit.text().strip().replace("-", "").replace(" ", "")
        sistema = self._sistema_edit.text().strip() or None
        directorio = self._directorio_edit.text().strip()
        ambiente = self._ambiente_gen_combo.currentText()

        # Validaciones
        if not empresa:
            QMessageBox.warning(self, "Atención", "Ingresa el nombre de la empresa.")
            self._empresa_edit.setFocus()
            return

        if not cuit or not cuit.isdigit() or len(cuit) != 11:
            QMessageBox.warning(self, "Atención", "CUIT inválido (11 dígitos).")
            self._cuit_gen_edit.setFocus()
            return

        # Generar
        resultado = arca_setup.generar_carpeta_empresa(
            base_dir=directorio,
            empresa=empresa,
            cuit=cuit,
            sistema=sistema,
            ambiente=ambiente
        )

        mensaje = "\n".join(resultado['mensajes'])

        if resultado['éxito']:
            instrucciones = arca_setup.crear_instrucciones_upload(
                empresa=empresa,
                cuit=cuit,
                csr_path=resultado['csr_path']
            )
            mensaje += instrucciones
            self._resultado_text.setText(mensaje)
            QMessageBox.information(
                self,
                "✓ Certificado Generado",
                f"Clave y CSR listos en:\n{os.path.dirname(resultado['csr_path'])}\n\n"
                f"Sube el CSR a ARCA, descarga el .crt y luego ve a 'Cargar Certificado'."
            )
        else:
            self._resultado_text.setText(f"❌ ERROR:\n{resultado['error']}")
            QMessageBox.critical(self, "Error", f"Error: {resultado['error']}")

    def _browse_clave(self):
        """Abre diálogo para seleccionar clave.key."""
        from PyQt5.QtWidgets import QFileDialog
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar clave.key", "certs/", "Key Files (*.key);;All Files (*)"
        )
        if ruta:
            self._clave_edit.setText(ruta)

    def _browse_cert(self):
        """Abre diálogo para seleccionar certificado.crt."""
        from PyQt5.QtWidgets import QFileDialog
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar certificado.crt", "certs/", "Certificate Files (*.crt);;All Files (*)"
        )
        if ruta:
            self._cert_edit.setText(ruta)

    def _cargar_certificado(self):
        """Carga un certificado en la BD."""
        empresa = self._carga_empresa_edit.text().strip()
        cuit = self._carga_cuit_edit.text().strip().replace("-", "")
        punto_venta = self._punto_venta_spin.value()
        clave_path = self._clave_edit.text().strip()
        cert_path = self._cert_edit.text().strip()
        ambiente = self._ambiente_combo.currentText()
        alias = self._alias_edit.text().strip() or ""

        # Validaciones
        if not empresa:
            QMessageBox.warning(self, "Atención", "Ingresa nombre de empresa.")
            return
        if not cuit or len(cuit) != 11:
            QMessageBox.warning(self, "Atención", "CUIT inválido.")
            return
        if not clave_path or not os.path.exists(clave_path):
            QMessageBox.warning(self, "Atención", "Clave privada no encontrada.")
            return
        if not cert_path or not os.path.exists(cert_path):
            QMessageBox.warning(self, "Atención", "Certificado no encontrado.")
            return

        # Guardar en BD
        try:
            db.crear_arca_config(
                empresa=empresa,
                cuit=cuit,
                punto_venta=punto_venta,
                clave_path=clave_path,
                certificado_path=cert_path,
                ambiente=ambiente,
                alias=alias
            )
            QMessageBox.information(
                self, "✓ Certificado Cargado",
                f"Certificado de {empresa} guardado correctamente.\n\n"
                f"Ya puedes usar este certificado para facturación."
            )
            self._refrescar_tabla_certs()
            # Limpiar campos
            self._carga_empresa_edit.clear()
            self._carga_cuit_edit.clear()
            self._clave_edit.clear()
            self._cert_edit.clear()
            self._alias_edit.clear()
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar: {str(e)}")

    def _refrescar_tabla_certs(self):
        """Actualiza la tabla de certificados cargados."""
        self._tabla_certs.setRowCount(0)
        try:
            configs = db.obtener_todas_arca_configs()
            for config in configs:
                row = self._tabla_certs.rowCount()
                self._tabla_certs.insertRow(row)
                self._tabla_certs.setItem(row, 0, QTableWidgetItem(config["empresa"]))
                self._tabla_certs.setItem(row, 1, QTableWidgetItem(config["cuit"]))
                self._tabla_certs.setItem(row, 2, QTableWidgetItem(str(config["punto_venta"])))
                self._tabla_certs.setItem(row, 3, QTableWidgetItem(config["ambiente"]))
                self._tabla_certs.setItem(row, 4, QTableWidgetItem(config["alias"] or "-"))
                self._tabla_certs.item(row, 0).setData(Qt.UserRole, config["id"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tabla: {str(e)}")

    def _eliminar_cert_seleccionado(self):
        """Elimina el certificado seleccionado."""
        row = self._tabla_certs.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Selecciona un certificado.")
            return

        empresa = self._tabla_certs.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar certificado de {empresa}?"
        )
        if reply == QMessageBox.Yes:
            try:
                db.eliminar_arca_config(empresa)
                self._refrescar_tabla_certs()
                QMessageBox.information(self, "Eliminado", f"Certificado de {empresa} eliminado.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar: {str(e)}")
