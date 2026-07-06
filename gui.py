#!/usr/bin/env python3
"""
Interfaz gráfica — Restolibra (PyQt5)
"""
import os
import sys
import subprocess
from datetime import date

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QFrame,
    QSplitter, QStackedWidget, QFormLayout, QDialog, QDialogButtonBox,
    QMessageBox, QScrollArea, QSizePolicy, QSpacerItem, QGridLayout,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap

import database as db
import pdf_generator as pdf_gen
import config_manager
from arca_gui import ARCAConfigPage
from gui_facturas import FacturasPage, NuevaFacturaPage

# ── Estilos ───────────────────────────────────────────────────────────────────

STYLESHEET = """
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: #0f172a;
}

/* Sidebar */
#sidebar {
    background-color: #1e293b;
    min-width: 210px;
    max-width: 210px;
}
#sidebar QLabel#app_title {
    color: white;
    font-size: 17px;
    font-weight: bold;
    padding: 28px 20px 4px 20px;
    background: transparent;
}
#sidebar QLabel#app_sub {
    color: #94a3b8;
    font-size: 11px;
    padding: 0 20px 20px 20px;
    background: transparent;
}
#sidebar QPushButton {
    background-color: transparent;
    color: #cbd5e1;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 13px;
}
#sidebar QPushButton:hover {
    background-color: #334155;
    color: white;
}
#sidebar QPushButton[active="true"] {
    background-color: #2563eb;
    color: white;
    font-weight: bold;
}

/* Área de contenido */
#content_area {
    background-color: #f1f5f9;
}

/* Título de sección */
QLabel#page_title {
    font-size: 20px;
    font-weight: bold;
    color: #0f172a;
}

/* Tarjetas */
QFrame#card {
    background-color: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}
QLabel#card_title {
    font-size: 13px;
    font-weight: bold;
    color: #0f172a;
    padding: 0;
}

/* Campos */
QLineEdit, QComboBox {
    border: 1px solid #d1d5db;
    border-radius: 5px;
    padding: 7px 10px;
    background: white;
    font-size: 13px;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #2563eb;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

/* Tabla */
QTableWidget {
    background-color: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    outline: none;
}
QTableWidget::item {
    padding: 8px 10px;
}
QTableWidget::item:selected {
    background-color: #2563eb;
    color: white;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-weight: bold;
    font-size: 11px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}

/* Botones */
QPushButton#btn_primary {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: bold;
}
QPushButton#btn_primary:hover { background-color: #1d4ed8; }

QPushButton#btn_success {
    background-color: #16a34a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: bold;
}
QPushButton#btn_success:hover { background-color: #15803d; }

QPushButton#btn_secondary {
    background-color: #e2e8f0;
    color: #334155;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
}
QPushButton#btn_secondary:hover { background-color: #cbd5e1; }

QPushButton#btn_danger {
    background-color: #dc2626;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
}
QPushButton#btn_danger:hover { background-color: #b91c1c; }

QPushButton#btn_muted {
    background-color: #64748b;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
}
QPushButton#btn_muted:hover { background-color: #475569; }

/* Separador */
QFrame#separator {
    background-color: #334155;
    max-height: 1px;
    margin: 0 16px;
}

/* Scroll */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #f1f5f9;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def make_btn(text, style="primary", parent=None):
    btn = QPushButton(text, parent)
    btn.setObjectName(f"btn_{style}")
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def make_label(text, bold=False, size=13, color=None):
    lbl = QLabel(text)
    f = lbl.font()
    f.setPointSize(size)
    if bold:
        f.setBold(True)
    lbl.setFont(f)
    if color:
        lbl.setStyleSheet(f"color: {color};")
    return lbl


def open_pdf(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform == "linux":
        # En WSL2 usar explorer.exe; en Linux nativo usar xdg-open
        import shutil
        if shutil.which("explorer.exe"):
            subprocess.Popen(["explorer.exe", path])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", path])
        elif shutil.which("wslview"):
            subprocess.Popen(["wslview", path])
        # Si no hay ninguno disponible, no hacemos nada (el PDF igual se guardó)
    else:
        os.startfile(path)


# ── Diálogo de Cliente ────────────────────────────────────────────────────────

class ClientDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        title = "Editar Cliente" if existing else "Nuevo Cliente"
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setModal(True)
        self.result_data = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        fields = [
            ("Nombre / Razón Social *", "name",     True),
            ("Domicilio",               "address",  False),
            ("CUIT / DNI",              "cuit_dni", False),
            ("Email",                   "email",    False),
            ("Teléfono",                "phone",    False),
        ]
        self._fields = {}
        for label, key, required in fields:
            le = QLineEdit()
            le.setText((existing or {}).get(key) or "")
            le.setPlaceholderText("Obligatorio" if required else "Opcional")
            form.addRow(label, le)
            self._fields[key] = le

        layout.addLayout(form)
        layout.addSpacing(8)

        btns = QHBoxLayout()
        cancel = make_btn("Cancelar", "secondary")
        save   = make_btn("Guardar",  "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _save(self):
        name = self._fields["name"].text().strip()
        if not name:
            QMessageBox.warning(self, "Atención", "El nombre es obligatorio.")
            return
        self.result_data = tuple(
            self._fields[k].text().strip()
            for k in ("name", "address", "cuit_dni", "email", "phone")
        )
        self.accept()


# ── Página: Remitos ───────────────────────────────────────────────────────────

class RemitosPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._all = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        # Cabecera
        hdr = QHBoxLayout()
        title = QLabel("Remitos")
        title.setObjectName("page_title")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        # Barra de búsqueda
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Buscar:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Número, cliente u observaciones...")
        self._search.setMaximumWidth(320)
        self._search.textChanged.connect(self._filter)
        bar.addWidget(self._search)
        bar.addStretch()
        root.addLayout(bar)

        # Tabla
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Número", "Fecha", "Cliente", "Total"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().resizeSection(0, 160)
        self._table.horizontalHeader().resizeSection(1, 110)
        self._table.horizontalHeader().resizeSection(3, 130)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("alternate-background-color: #f8fafc;")
        self._table.doubleClicked.connect(self._open_pdf)
        root.addWidget(self._table)

        # Botones
        btns = QHBoxLayout()
        b_open   = make_btn("Abrir PDF",       "primary")
        b_regen  = make_btn("Re-generar PDF",   "muted")
        b_edit   = make_btn("Editar",           "secondary")
        b_delete = make_btn("Eliminar",         "danger")
        b_open.clicked.connect(self._open_pdf)
        b_regen.clicked.connect(self._regen_pdf)
        b_edit.clicked.connect(self._editar)
        b_delete.clicked.connect(self._eliminar)
        btns.addWidget(b_open)
        btns.addWidget(b_regen)
        btns.addWidget(b_edit)
        btns.addWidget(b_delete)
        btns.addStretch()
        root.addLayout(btns)

    def refresh(self):
        self._all = db.get_all_remitos()
        self._populate(self._all)

    def _populate(self, remitos):
        self._table.setRowCount(0)
        for r in remitos:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r["number"]))
            self._table.setItem(row, 1, QTableWidgetItem(r["date"]))
            self._table.setItem(row, 2, QTableWidgetItem(r["client_name"]))
            total_item = QTableWidgetItem(f"$ {r['total']:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 3, total_item)
            self._table.item(row, 0).setData(Qt.UserRole, r["id"])
        self._table.setRowHeight(row, 34) if remitos else None

    def _filter(self, q):
        q = q.lower()
        filtered = [r for r in self._all
                    if q in r["number"].lower()
                    or q in r["client_name"].lower()
                    or q in (r.get("observations") or "").lower()] if q else self._all
        self._populate(filtered)

    def _selected_remito(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Seleccione un remito.")
            return None
        rid = self._table.item(row, 0).data(Qt.UserRole)
        return db.get_remito(rid)

    def _open_pdf(self):
        r = self._selected_remito()
        if not r:
            return
        if r.get("pdf_path") and os.path.exists(r["pdf_path"]):
            open_pdf(r["pdf_path"])
        else:
            reply = QMessageBox.question(self, "PDF no encontrado",
                                          "El archivo no existe. ¿Generar uno nuevo?")
            if reply == QMessageBox.Yes:
                path = pdf_gen.generate_pdf(r)
                db.update_remito_pdf_path(r["id"], path)
                open_pdf(path)

    def _regen_pdf(self):
        r = self._selected_remito()
        if not r:
            return
        path = pdf_gen.generate_pdf(r)
        db.update_remito_pdf_path(r["id"], path)
        reply = QMessageBox.question(self, "PDF regenerado",
                                      f"PDF guardado en:\n{path}\n\n¿Abrir?")
        if reply == QMessageBox.Yes:
            open_pdf(path)

    def _editar(self):
        r = self._selected_remito()
        if not r:
            return
        self.app.pages["nuevo_remito"].load_for_edit(r)
        self.app.show_page("nuevo_remito")

    def _eliminar(self):
        r = self._selected_remito()
        if not r:
            return
        reply = QMessageBox.question(self, "Confirmar eliminación",
                                      f"¿Está seguro de que desea eliminar el remito {r['number']}?")
        if reply == QMessageBox.Yes:
            db.delete_remito(r["id"])
            self.refresh()
            QMessageBox.information(self, "Eliminado", f"Remito {r['number']} eliminado exitosamente.")


# ── Página: Nuevo Remito ──────────────────────────────────────────────────────

class NuevoRemitoPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._items = []
        self._clients_data = []
        self._edit_id = None
        self._title_label = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_label = QLabel("Nuevo Remito")
        self._title_label.setObjectName("page_title")
        self._title_label.setContentsMargins(28, 24, 28, 12)
        outer.addWidget(self._title_label)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("content_area")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 8, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(self._build_cliente())
        layout.addWidget(self._build_datos())
        layout.addWidget(self._build_items())
        layout.addWidget(self._build_obs())

        # Totales
        totales_row = QHBoxLayout()
        totales_row.addStretch()
        totales_w = self._build_totales()
        totales_row.addWidget(totales_w)
        layout.addLayout(totales_row)

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()
        b_cancel = make_btn("Cancelar",             "secondary")
        b_save   = make_btn("Guardar y Generar PDF", "success")
        b_cancel.clicked.connect(self._cancel)
        b_save.clicked.connect(self._guardar)
        btns.addWidget(b_cancel)
        btns.addWidget(b_save)
        layout.addLayout(btns)

    def load_for_edit(self, remito):
        """Carga un remito existente en el formulario para edición."""
        self._edit_id = remito["id"]
        self._title_label.setText("Editar Remito")

        # Pre-cargar cliente
        self.refresh()
        idx = self._client_combo.findData(remito["client_id"])
        if idx >= 0:
            self._client_combo.setCurrentIndex(idx)

        # Pre-cargar datos
        self._date_edit.setText(remito["date"])
        self._obs_edit.setText(remito.get("observations") or "")

        # Pre-cargar tasa de IVA
        tax_pct = int(remito["tax_rate"] * 100)
        tax_text = f"{tax_pct}%"
        idx = self._tax_combo.findText(tax_text)
        if idx >= 0:
            self._tax_combo.setCurrentIndex(idx)

        # Pre-cargar items
        self._items.clear()
        self._items_table.setRowCount(0)
        for item in remito["items"]:
            self._items.append(item)
            row = self._items_table.rowCount()
            self._items_table.insertRow(row)
            self._items_table.setItem(row, 0, QTableWidgetItem(item["description"]))
            qty_item = QTableWidgetItem(f"{item['qty']:g}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(row, 1, qty_item)
            for col, val in [(2, f"$ {item['unit_price']:,.2f}"), (3, f"$ {item['subtotal']:,.2f}")]:
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._items_table.setItem(row, col, it)

        self._update_totals()

    def _card(self, title):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(12)
        lbl = QLabel(title)
        lbl.setObjectName("card_title")
        v.addWidget(lbl)
        return card, v

    def _build_cliente(self):
        card, layout = self._card("Cliente")

        row = QHBoxLayout()
        row.addWidget(QLabel("Cliente *"))
        self._client_combo = QComboBox()
        self._client_combo.setMinimumWidth(300)
        self._client_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(self._client_combo)
        row.addSpacing(8)
        b_new = make_btn("+ Nuevo cliente", "primary")
        b_new.clicked.connect(self._new_client)
        row.addWidget(b_new)
        row.addStretch()
        layout.addLayout(row)

        self._cli_lbl_nombre    = QLabel()
        self._cli_lbl_domicilio = QLabel()
        self._cli_lbl_cuit      = QLabel()
        self._cli_lbl_email     = QLabel()
        self._cli_lbl_telefono  = QLabel()

        cols_row = QHBoxLayout()
        cols_row.setSpacing(16)

        left_w  = QWidget()
        right_w = QWidget()
        left_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_v  = QVBoxLayout(left_w)
        right_v = QVBoxLayout(right_w)
        left_v.setContentsMargins(0, 0, 0, 0)
        right_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(4)
        right_v.setSpacing(4)

        for lbl_txt, lbl_val in [
            ("Cliente",    self._cli_lbl_nombre),
            ("Domicilio",  self._cli_lbl_domicilio),
            ("CUIT / DNI", self._cli_lbl_cuit),
        ]:
            r = QHBoxLayout()
            r.setSpacing(6)
            lbl = make_label(lbl_txt, size=10, color="#64748b")
            lbl.setFixedWidth(80)
            r.addWidget(lbl)
            r.addWidget(lbl_val, 1)
            left_v.addLayout(r)

        for lbl_txt, lbl_val in [
            ("Email",    self._cli_lbl_email),
            ("Teléfono", self._cli_lbl_telefono),
        ]:
            r = QHBoxLayout()
            r.setSpacing(6)
            lbl = make_label(lbl_txt, size=10, color="#64748b")
            lbl.setFixedWidth(80)
            r.addWidget(lbl)
            r.addWidget(lbl_val, 1)
            right_v.addLayout(r)

        right_v.addStretch()
        cols_row.addWidget(left_w)
        cols_row.addWidget(right_w)
        layout.addLayout(cols_row)

        self._client_combo.currentIndexChanged.connect(self._update_client_info)
        return card

    def _update_client_info(self):
        cid = self._client_combo.currentData()
        c = db.get_client(cid) if cid else None
        self._cli_lbl_nombre.setText(c["name"]        or "" if c else "")
        self._cli_lbl_domicilio.setText(c["address"]  or "" if c else "")
        self._cli_lbl_cuit.setText(c["cuit_dni"]      or "" if c else "")
        self._cli_lbl_email.setText(c["email"]        or "" if c else "")
        self._cli_lbl_telefono.setText(c["phone"]     or "" if c else "")

    def _build_datos(self):
        card, layout = self._card("Datos del remito")

        row = QHBoxLayout()
        row.addWidget(QLabel("Fecha *"))
        self._date_edit = QLineEdit(date.today().isoformat())
        self._date_edit.setFixedWidth(130)
        self._date_edit.setPlaceholderText("YYYY-MM-DD")
        row.addWidget(self._date_edit)
        row.addSpacing(24)
        row.addWidget(QLabel("IVA"))
        self._tax_combo = QComboBox()
        self._tax_combo.addItems(["21%", "10.5%", "0%"])
        self._tax_combo.setFixedWidth(90)
        self._tax_combo.currentTextChanged.connect(lambda _: self._update_totals())
        row.addWidget(self._tax_combo)
        row.addStretch()
        layout.addLayout(row)
        return card

    def _build_items(self):
        card, layout = self._card("Items")

        # Fila de entrada
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        col = QVBoxLayout()
        col.addWidget(make_label("Descripción", size=10, color="#64748b"))
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Descripción del ítem...")
        self._desc_edit.returnPressed.connect(self._add_item)
        col.addWidget(self._desc_edit)
        input_row.addLayout(col, 3)

        col2 = QVBoxLayout()
        col2.addWidget(make_label("Cantidad", size=10, color="#64748b"))
        self._qty_edit = QLineEdit("1")
        self._qty_edit.setFixedWidth(80)
        self._qty_edit.returnPressed.connect(self._add_item)
        col2.addWidget(self._qty_edit)
        input_row.addLayout(col2)

        col3 = QVBoxLayout()
        col3.addWidget(make_label("Precio Unit.", size=10, color="#64748b"))
        self._price_edit = QLineEdit()
        self._price_edit.setPlaceholderText("0.00")
        self._price_edit.setFixedWidth(130)
        self._price_edit.returnPressed.connect(self._add_item)
        col3.addWidget(self._price_edit)
        input_row.addLayout(col3)

        b_add = make_btn("Agregar", "primary")
        b_add.clicked.connect(self._add_item)
        input_row.addWidget(b_add, 0, Qt.AlignBottom)
        layout.addLayout(input_row)

        # Tabla de ítems
        self._items_table = QTableWidget()
        self._items_table.setColumnCount(4)
        self._items_table.setHorizontalHeaderLabels(
            ["Descripción", "Cant.", "Precio Unit.", "Subtotal"])
        self._items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._items_table.horizontalHeader().resizeSection(1, 80)
        self._items_table.horizontalHeader().resizeSection(2, 130)
        self._items_table.horizontalHeader().resizeSection(3, 130)
        self._items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setAlternatingRowColors(True)
        self._items_table.setStyleSheet("alternate-background-color: #f8fafc;")
        self._items_table.setMinimumHeight(160)
        layout.addWidget(self._items_table)

        b_del = make_btn("Eliminar seleccionado", "danger")
        b_del.clicked.connect(self._remove_item)
        del_row = QHBoxLayout()
        del_row.addStretch()
        del_row.addWidget(b_del)
        layout.addLayout(del_row)
        return card

    def _build_obs(self):
        card, layout = self._card("Observaciones (opcional)")
        self._obs_edit = QLineEdit()
        self._obs_edit.setPlaceholderText("Notas adicionales...")
        layout.addWidget(self._obs_edit)
        return card

    def _build_totales(self):
        w = QFrame()
        w.setObjectName("card")
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(6)
        v.setAlignment(Qt.AlignRight)

        self._lbl_sub = QLabel()
        self._lbl_iva = QLabel()
        self._lbl_tot = QLabel()
        self._lbl_tot.setStyleSheet("color: #2563eb; font-size: 16px; font-weight: bold;")

        for lbl in (self._lbl_sub, self._lbl_iva, self._lbl_tot):
            lbl.setAlignment(Qt.AlignRight)
            v.addWidget(lbl)

        self._update_totals()
        return w

    # ── Lógica ──

    def refresh(self):
        clients = db.get_all_clients()
        self._clients_data = clients
        current = self._client_combo.currentText()
        self._client_combo.clear()
        for c in clients:
            self._client_combo.addItem(c["name"], c["id"])
        if current:
            idx = self._client_combo.findText(current)
            if idx >= 0:
                self._client_combo.setCurrentIndex(idx)

    def _tax_rate(self):
        return {"21%": 0.21, "10.5%": 0.105, "0%": 0.0}.get(
            self._tax_combo.currentText(), 0.21)

    def _update_totals(self):
        subtotal   = sum(i["subtotal"] for i in self._items)
        tax_rate   = self._tax_rate()
        tax_label  = self._tax_combo.currentText()
        tax_amount = round(subtotal * tax_rate, 2)
        total      = round(subtotal + tax_amount, 2)

        self._lbl_sub.setText(f"Subtotal:    $ {subtotal:>12,.2f}")
        self._lbl_iva.setText(f"IVA {tax_label}:   $ {tax_amount:>12,.2f}")
        self._lbl_tot.setText(f"TOTAL:       $ {total:>12,.2f}")

    def _add_item(self):
        desc  = self._desc_edit.text().strip()
        q_str = self._qty_edit.text().strip().replace(",", ".")
        p_str = self._price_edit.text().strip().replace(",", ".")

        if not desc:
            QMessageBox.warning(self, "Atención", "Ingrese una descripción.")
            self._desc_edit.setFocus()
            return
        try:
            qty   = float(q_str)
            price = float(p_str)
            if qty <= 0 or price < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Atención",
                                "Cantidad y precio deben ser números válidos (mayores a 0).")
            return

        subtotal = round(qty * price, 2)
        self._items.append({"description": desc, "qty": qty,
                             "unit_price": price, "subtotal": subtotal})

        row = self._items_table.rowCount()
        self._items_table.insertRow(row)
        self._items_table.setItem(row, 0, QTableWidgetItem(desc))
        qty_item = QTableWidgetItem(f"{qty:g}")
        qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._items_table.setItem(row, 1, qty_item)
        for col, val in [(2, f"$ {price:,.2f}"), (3, f"$ {subtotal:,.2f}")]:
            it = QTableWidgetItem(val)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(row, col, it)

        self._desc_edit.clear()
        self._qty_edit.setText("1")
        self._price_edit.clear()
        self._desc_edit.setFocus()
        self._update_totals()

    def _remove_item(self):
        row = self._items_table.currentRow()
        if row < 0:
            return
        self._items_table.removeRow(row)
        self._items.pop(row)
        self._update_totals()

    def _new_client(self):
        dlg = ClientDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            cid = db.create_client(*dlg.result_data)
            self.refresh()
            idx = self._client_combo.findData(cid)
            if idx >= 0:
                self._client_combo.setCurrentIndex(idx)

    def _cancel(self):
        self._reset()
        self.app.show_page("remitos")

    def _reset(self):
        self._items.clear()
        self._items_table.setRowCount(0)
        self._desc_edit.clear()
        self._qty_edit.setText("1")
        self._price_edit.clear()
        self._obs_edit.clear()
        self._date_edit.setText(date.today().isoformat())
        self._tax_combo.setCurrentIndex(0)
        self._edit_id = None
        self._title_label.setText("Nuevo Remito")
        self._update_totals()

    def _guardar(self):
        if not self._items:
            QMessageBox.warning(self, "Atención", "Agregue al menos un ítem.")
            return

        if self._client_combo.count() == 0:
            QMessageBox.warning(self, "Atención", "Seleccione un cliente.")
            return

        cid = self._client_combo.currentData()
        client = db.get_client(cid)
        if not client:
            QMessageBox.critical(self, "Error", "Cliente no encontrado.")
            return

        date_str = self._date_edit.text().strip()
        try:
            date.fromisoformat(date_str)
        except ValueError:
            QMessageBox.warning(self, "Atención",
                                "Fecha inválida. Use el formato YYYY-MM-DD.")
            return

        tax_rate   = self._tax_rate()
        subtotal   = round(sum(i["subtotal"] for i in self._items), 2)
        tax_amount = round(subtotal * tax_rate, 2)
        total      = round(subtotal + tax_amount, 2)

        if self._edit_id:
            # Modo edición: actualizar remito existente
            db.update_remito(
                remito_id=self._edit_id,
                date=date_str,
                client_id=client["id"],
                client_name=client["name"],
                client_address=client.get("address", ""),
                client_cuit=client.get("cuit_dni", ""),
                client_email=client.get("email", ""),
                client_phone=client.get("phone", ""),
                items=self._items,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=total,
                observations=self._obs_edit.text().strip(),
            )
            remito_data = db.get_remito(self._edit_id)
            pdf_path = pdf_gen.generate_pdf(remito_data)
            db.update_remito_pdf_path(self._edit_id, pdf_path)
            reply = QMessageBox.question(
                self, "Remito actualizado",
                f"Remito actualizado exitosamente.\n\n¿Abrir el PDF?",
            )
            if reply == QMessageBox.Yes:
                open_pdf(pdf_path)
        else:
            # Modo creación: crear nuevo remito
            number = db.get_next_remito_number()
            remito_id = db.create_remito(
                number=number, date=date_str,
                client_id=client["id"],
                client_name=client["name"],
                client_address=client.get("address", ""),
                client_cuit=client.get("cuit_dni", ""),
                client_email=client.get("email", ""),
                client_phone=client.get("phone", ""),
                items=self._items, subtotal=subtotal,
                tax_rate=tax_rate, tax_amount=tax_amount,
                total=total, observations=self._obs_edit.text().strip(),
            )

            remito_data = db.get_remito(remito_id)
            pdf_path = pdf_gen.generate_pdf(remito_data)
            db.update_remito_pdf_path(remito_id, pdf_path)

            reply = QMessageBox.question(
                self, "Remito generado",
                f"Remito {number} guardado exitosamente.\n\n¿Abrir el PDF?",
            )
            if reply == QMessageBox.Yes:
                open_pdf(pdf_path)

        self._reset()
        self.app.show_page("remitos")
        self.app.pages["remitos"].refresh()


# ── Página: Clientes ──────────────────────────────────────────────────────────

class ClientesPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        title = QLabel("Clientes")
        title.setObjectName("page_title")
        hdr.addWidget(title)
        hdr.addStretch()
        b_new = make_btn("+ Nuevo", "primary")
        b_new.clicked.connect(self._nuevo)
        hdr.addWidget(b_new)
        root.addLayout(hdr)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Nombre / Razón Social", "CUIT / DNI", "Teléfono", "Email"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().resizeSection(1, 150)
        self._table.horizontalHeader().resizeSection(2, 130)
        self._table.horizontalHeader().resizeSection(3, 210)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("alternate-background-color: #f8fafc;")
        self._table.doubleClicked.connect(self._editar)
        root.addWidget(self._table)

        btns = QHBoxLayout()
        b_edit = make_btn("Editar",    "muted")
        b_del  = make_btn("Eliminar",  "danger")
        b_edit.clicked.connect(self._editar)
        b_del.clicked.connect(self._eliminar)
        btns.addWidget(b_edit)
        btns.addWidget(b_del)
        btns.addStretch()
        root.addLayout(btns)

    def refresh(self):
        self._clients = db.get_all_clients()
        self._table.setRowCount(0)
        for c in self._clients:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(c["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(c["cuit_dni"] or "-"))
            self._table.setItem(row, 2, QTableWidgetItem(c["phone"] or "-"))
            self._table.setItem(row, 3, QTableWidgetItem(c["email"] or "-"))
            self._table.item(row, 0).setData(Qt.UserRole, c["id"])

    def _selected_client(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Seleccione un cliente.")
            return None
        cid = self._table.item(row, 0).data(Qt.UserRole)
        return db.get_client(cid)

    def _nuevo(self):
        dlg = ClientDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            db.create_client(*dlg.result_data)
            self.refresh()

    def _editar(self):
        client = self._selected_client()
        if not client:
            return
        dlg = ClientDialog(self, existing=client)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            name, address, cuit, email, phone = dlg.result_data
            db.update_client(client["id"], name=name, address=address,
                             cuit_dni=cuit, email=email, phone=phone)
            self.refresh()

    def _eliminar(self):
        client = self._selected_client()
        if not client:
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar a {client['name']}?\nEsta acción no se puede deshacer."
        )
        if reply == QMessageBox.Yes:
            try:
                db.delete_client(client["id"])
                self.refresh()
            except ValueError as e:
                QMessageBox.critical(self, "No se puede eliminar", str(e))


# ── Página: Presupuestos ─────────────────────────────────────────────────────

class PresupuestosPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._all = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        # Cabecera
        hdr = QHBoxLayout()
        title = QLabel("Presupuestos")
        title.setObjectName("page_title")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        # Barra de búsqueda
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Buscar:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Número, cliente u observaciones...")
        self._search.setMaximumWidth(320)
        self._search.textChanged.connect(self._filter)
        bar.addWidget(self._search)
        bar.addStretch()
        root.addLayout(bar)

        # Tabla
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Número", "Fecha", "Cliente", "Estado", "Válido hasta", "Total"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().resizeSection(0, 160)
        self._table.horizontalHeader().resizeSection(1, 110)
        self._table.horizontalHeader().resizeSection(3, 100)
        self._table.horizontalHeader().resizeSection(4, 110)
        self._table.horizontalHeader().resizeSection(5, 130)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("alternate-background-color: #f8fafc;")
        self._table.doubleClicked.connect(self._open_pdf)
        root.addWidget(self._table)

        # Botones
        btns = QHBoxLayout()
        b_open     = make_btn("Abrir PDF",          "primary")
        b_regen    = make_btn("Re-generar PDF",     "muted")
        b_aprobar  = make_btn("Aprobar",            "success")
        b_rechazar = make_btn("Rechazar",           "muted")
        b_convert  = make_btn("Convertir a Remito", "success")
        b_edit     = make_btn("Editar",             "secondary")
        b_delete   = make_btn("Eliminar",           "danger")
        b_open.clicked.connect(self._open_pdf)
        b_regen.clicked.connect(self._regen_pdf)
        b_aprobar.clicked.connect(self._aprobar)
        b_rechazar.clicked.connect(self._rechazar)
        b_convert.clicked.connect(self._convert_to_remito)
        b_edit.clicked.connect(self._editar)
        b_delete.clicked.connect(self._eliminar)
        btns.addWidget(b_open)
        btns.addWidget(b_regen)
        btns.addWidget(b_aprobar)
        btns.addWidget(b_rechazar)
        btns.addWidget(b_convert)
        btns.addWidget(b_edit)
        btns.addWidget(b_delete)
        btns.addStretch()
        root.addLayout(btns)

    def refresh(self):
        self._all = db.get_all_presupuestos()
        self._populate(self._all)

    def _populate(self, presupuestos):
        self._table.setRowCount(0)
        for p in presupuestos:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(p["number"]))
            self._table.setItem(row, 1, QTableWidgetItem(p["date"]))
            self._table.setItem(row, 2, QTableWidgetItem(p["client_name"]))

            status_item = QTableWidgetItem(p["status"].capitalize())
            status_color = {"Aceptado": "#16a34a", "Rechazado": "#dc2626", "Pendiente": "#f59e0b"}.get(
                p["status"].capitalize(), "#64748b")
            status_item.setForeground(QColor(status_color))
            self._table.setItem(row, 3, status_item)

            self._table.setItem(row, 4, QTableWidgetItem(p["valid_until"]))

            total_item = QTableWidgetItem(f"$ {p['total']:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 5, total_item)
            self._table.item(row, 0).setData(Qt.UserRole, p["id"])
        if presupuestos:
            self._table.setRowHeight(len(presupuestos) - 1, 34)

    def _filter(self, q):
        q = q.lower()
        filtered = [p for p in self._all
                    if q in p["number"].lower()
                    or q in p["client_name"].lower()
                    or q in (p.get("observations") or "").lower()] if q else self._all
        self._populate(filtered)

    def _selected_presupuesto(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atención", "Seleccione un presupuesto.")
            return None
        pid = self._table.item(row, 0).data(Qt.UserRole)
        return db.get_presupuesto(pid)

    def _open_pdf(self):
        p = self._selected_presupuesto()
        if not p:
            return
        if p.get("pdf_path") and os.path.exists(p["pdf_path"]):
            open_pdf(p["pdf_path"])
        else:
            reply = QMessageBox.question(self, "PDF no encontrado",
                                          "El archivo no existe. ¿Generar uno nuevo?")
            if reply == QMessageBox.Yes:
                path = pdf_gen.generate_pdf_presupuesto(p)
                db.update_presupuesto_pdf_path(p["id"], path)
                open_pdf(path)

    def _regen_pdf(self):
        p = self._selected_presupuesto()
        if not p:
            return
        path = pdf_gen.generate_pdf_presupuesto(p)
        db.update_presupuesto_pdf_path(p["id"], path)
        reply = QMessageBox.question(self, "PDF regenerado",
                                      f"PDF guardado en:\n{path}\n\n¿Abrir?")
        if reply == QMessageBox.Yes:
            open_pdf(path)

    def _aprobar(self):
        p = self._selected_presupuesto()
        if not p:
            return
        if p["status"] == "aceptado":
            QMessageBox.information(self, "Atención", "El presupuesto ya está aceptado.")
            return
        db.update_presupuesto_status(p["id"], "aceptado")
        self.refresh()

    def _rechazar(self):
        p = self._selected_presupuesto()
        if not p:
            return
        if p["status"] == "rechazado":
            QMessageBox.information(self, "Atención", "El presupuesto ya está rechazado.")
            return
        db.update_presupuesto_status(p["id"], "rechazado")
        self.refresh()

    def _convert_to_remito(self):
        p = self._selected_presupuesto()
        if not p:
            return
        if p["status"] != "aceptado":
            reply = QMessageBox.question(
                self, "Presupuesto no aprobado",
                f"El presupuesto está en estado '{p['status']}'.\n"
                "¿Aprobarlo y convertirlo a remito ahora?",
            )
            if reply != QMessageBox.Yes:
                return
            db.update_presupuesto_status(p["id"], "aceptado")
            p = db.get_presupuesto(p["id"])

        reply = QMessageBox.question(self, "Confirmar conversión",
                                      f"¿Convertir el presupuesto {p['number']} a remito?")
        if reply != QMessageBox.Yes:
            return

        # Crear remito
        remito_number = db.get_next_remito_number()
        remito_id = db.create_remito(
            number=remito_number,
            date=p["date"],
            client_id=p["client_id"],
            client_name=p["client_name"],
            client_address=p.get("client_address", ""),
            client_cuit=p.get("client_cuit", ""),
            client_email=p.get("client_email", ""),
            client_phone=p.get("client_phone", ""),
            items=p["items"],
            subtotal=p["subtotal"],
            tax_rate=p["tax_rate"],
            tax_amount=p["tax_amount"],
            total=p["total"],
            observations=p.get("observations", ""),
        )

        # Generar PDF del remito
        remito_data = db.get_remito(remito_id)
        pdf_path = pdf_gen.generate_pdf(remito_data)
        db.update_remito_pdf_path(remito_id, pdf_path)

        # Registrar en presupuesto
        db.update_presupuesto_remito_id(p["id"], remito_id)

        QMessageBox.information(self, "Conversión exitosa",
                                f"Presupuesto convertido a remito {remito_number}.\n\nPDF guardado en:\n{pdf_path}")
        self.refresh()
        self.app.pages["remitos"].refresh()

    def _editar(self):
        p = self._selected_presupuesto()
        if not p:
            return
        self.app.pages["nuevo_presupuesto"].load_for_edit(p)
        self.app.show_page("nuevo_presupuesto")

    def _eliminar(self):
        p = self._selected_presupuesto()
        if not p:
            return
        reply = QMessageBox.question(self, "Confirmar eliminación",
                                      f"¿Está seguro de que desea eliminar el presupuesto {p['number']}?")
        if reply == QMessageBox.Yes:
            db.delete_presupuesto(p["id"])
            self.refresh()
            QMessageBox.information(self, "Eliminado", f"Presupuesto {p['number']} eliminado exitosamente.")


# ── Página: Nuevo Presupuesto ────────────────────────────────────────────────

class NuevoPresupuestoPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._items = []
        self._clients_data = []
        self._edit_id = None
        self._title_label = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_label = QLabel("Nuevo Presupuesto")
        self._title_label.setObjectName("page_title")
        self._title_label.setContentsMargins(28, 24, 28, 12)
        outer.addWidget(self._title_label)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("content_area")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 8, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(self._build_cliente())
        layout.addWidget(self._build_datos())
        layout.addWidget(self._build_items())
        layout.addWidget(self._build_obs())

        # Totales
        totales_row = QHBoxLayout()
        totales_row.addStretch()
        totales_w = self._build_totales()
        totales_row.addWidget(totales_w)
        layout.addLayout(totales_row)

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()
        b_cancel = make_btn("Cancelar",             "secondary")
        b_save   = make_btn("Guardar y Generar PDF", "success")
        b_cancel.clicked.connect(self._cancel)
        b_save.clicked.connect(self._guardar)
        btns.addWidget(b_cancel)
        btns.addWidget(b_save)
        layout.addLayout(btns)

    def _card(self, title):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(12)
        lbl = QLabel(title)
        lbl.setObjectName("card_title")
        v.addWidget(lbl)
        return card, v

    def _build_cliente(self):
        card, layout = self._card("Cliente")

        row = QHBoxLayout()
        row.addWidget(QLabel("Cliente *"))
        self._client_combo = QComboBox()
        self._client_combo.setMinimumWidth(300)
        self._client_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(self._client_combo)
        row.addSpacing(8)
        b_new = make_btn("+ Nuevo cliente", "primary")
        b_new.clicked.connect(self._new_client)
        row.addWidget(b_new)
        row.addStretch()
        layout.addLayout(row)

        self._cli_lbl_nombre    = QLabel()
        self._cli_lbl_domicilio = QLabel()
        self._cli_lbl_cuit      = QLabel()
        self._cli_lbl_email     = QLabel()
        self._cli_lbl_telefono  = QLabel()

        cols_row = QHBoxLayout()
        cols_row.setSpacing(16)

        left_w  = QWidget()
        right_w = QWidget()
        left_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_v  = QVBoxLayout(left_w)
        right_v = QVBoxLayout(right_w)
        left_v.setContentsMargins(0, 0, 0, 0)
        right_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(4)
        right_v.setSpacing(4)

        for lbl_txt, lbl_val in [
            ("Cliente",    self._cli_lbl_nombre),
            ("Domicilio",  self._cli_lbl_domicilio),
            ("CUIT / DNI", self._cli_lbl_cuit),
        ]:
            r = QHBoxLayout()
            r.setSpacing(6)
            lbl = make_label(lbl_txt, size=10, color="#64748b")
            lbl.setFixedWidth(80)
            r.addWidget(lbl)
            r.addWidget(lbl_val, 1)
            left_v.addLayout(r)

        for lbl_txt, lbl_val in [
            ("Email",    self._cli_lbl_email),
            ("Teléfono", self._cli_lbl_telefono),
        ]:
            r = QHBoxLayout()
            r.setSpacing(6)
            lbl = make_label(lbl_txt, size=10, color="#64748b")
            lbl.setFixedWidth(80)
            r.addWidget(lbl)
            r.addWidget(lbl_val, 1)
            right_v.addLayout(r)

        right_v.addStretch()
        cols_row.addWidget(left_w)
        cols_row.addWidget(right_w)
        layout.addLayout(cols_row)

        self._client_combo.currentIndexChanged.connect(self._update_client_info)
        return card

    def _update_client_info(self):
        cid = self._client_combo.currentData()
        c = db.get_client(cid) if cid else None
        self._cli_lbl_nombre.setText(c["name"]        or "" if c else "")
        self._cli_lbl_domicilio.setText(c["address"]  or "" if c else "")
        self._cli_lbl_cuit.setText(c["cuit_dni"]      or "" if c else "")
        self._cli_lbl_email.setText(c["email"]        or "" if c else "")
        self._cli_lbl_telefono.setText(c["phone"]     or "" if c else "")

    def _build_datos(self):
        card, layout = self._card("Datos del presupuesto")

        row = QHBoxLayout()
        row.addWidget(QLabel("Fecha *"))
        self._date_edit = QLineEdit(date.today().isoformat())
        self._date_edit.setFixedWidth(130)
        self._date_edit.setPlaceholderText("YYYY-MM-DD")
        row.addWidget(self._date_edit)

        row.addSpacing(24)
        row.addWidget(QLabel("Válido hasta *"))
        from datetime import datetime, timedelta
        default_valid = (datetime.now() + timedelta(days=30)).isoformat()[:10]
        self._valid_until_edit = QLineEdit(default_valid)
        self._valid_until_edit.setFixedWidth(130)
        self._valid_until_edit.setPlaceholderText("YYYY-MM-DD")
        row.addWidget(self._valid_until_edit)

        row.addSpacing(24)
        row.addWidget(QLabel("IVA"))
        self._tax_combo = QComboBox()
        self._tax_combo.addItems(["21%", "10.5%", "0%"])
        self._tax_combo.setFixedWidth(90)
        self._tax_combo.currentTextChanged.connect(lambda _: self._update_totals())
        row.addWidget(self._tax_combo)
        row.addStretch()
        layout.addLayout(row)
        return card

    def _build_items(self):
        card, layout = self._card("Items")

        # Fila de entrada
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        col = QVBoxLayout()
        col.addWidget(make_label("Descripción", size=10, color="#64748b"))
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Descripción del ítem...")
        self._desc_edit.returnPressed.connect(self._add_item)
        col.addWidget(self._desc_edit)
        input_row.addLayout(col, 3)

        col2 = QVBoxLayout()
        col2.addWidget(make_label("Cantidad", size=10, color="#64748b"))
        self._qty_edit = QLineEdit("1")
        self._qty_edit.setFixedWidth(80)
        self._qty_edit.returnPressed.connect(self._add_item)
        col2.addWidget(self._qty_edit)
        input_row.addLayout(col2)

        col3 = QVBoxLayout()
        col3.addWidget(make_label("Precio Unit.", size=10, color="#64748b"))
        self._price_edit = QLineEdit()
        self._price_edit.setPlaceholderText("0.00")
        self._price_edit.setFixedWidth(130)
        self._price_edit.returnPressed.connect(self._add_item)
        col3.addWidget(self._price_edit)
        input_row.addLayout(col3)

        b_add = make_btn("Agregar", "primary")
        b_add.clicked.connect(self._add_item)
        input_row.addWidget(b_add, 0, Qt.AlignBottom)
        layout.addLayout(input_row)

        # Tabla de ítems
        self._items_table = QTableWidget()
        self._items_table.setColumnCount(4)
        self._items_table.setHorizontalHeaderLabels(
            ["Descripción", "Cant.", "Precio Unit.", "Subtotal"])
        self._items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._items_table.horizontalHeader().resizeSection(1, 80)
        self._items_table.horizontalHeader().resizeSection(2, 130)
        self._items_table.horizontalHeader().resizeSection(3, 130)
        self._items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setAlternatingRowColors(True)
        self._items_table.setStyleSheet("alternate-background-color: #f8fafc;")
        self._items_table.setMinimumHeight(160)
        layout.addWidget(self._items_table)

        b_del = make_btn("Eliminar seleccionado", "danger")
        b_del.clicked.connect(self._remove_item)
        del_row = QHBoxLayout()
        del_row.addStretch()
        del_row.addWidget(b_del)
        layout.addLayout(del_row)
        return card

    def _build_obs(self):
        card, layout = self._card("Observaciones (opcional)")
        self._obs_edit = QLineEdit()
        self._obs_edit.setPlaceholderText("Notas adicionales...")
        layout.addWidget(self._obs_edit)
        return card

    def _build_totales(self):
        w = QFrame()
        w.setObjectName("card")
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(6)
        v.setAlignment(Qt.AlignRight)

        self._lbl_sub = QLabel()
        self._lbl_iva = QLabel()
        self._lbl_tot = QLabel()
        self._lbl_tot.setStyleSheet("color: #2563eb; font-size: 16px; font-weight: bold;")

        for lbl in (self._lbl_sub, self._lbl_iva, self._lbl_tot):
            lbl.setAlignment(Qt.AlignRight)
            v.addWidget(lbl)

        self._update_totals()
        return w

    # ── Lógica ──

    def load_for_edit(self, presupuesto):
        """Carga un presupuesto existente en el formulario para edición."""
        self._edit_id = presupuesto["id"]
        self._title_label.setText("Editar Presupuesto")

        # Pre-cargar cliente
        self.refresh()
        idx = self._client_combo.findData(presupuesto["client_id"])
        if idx >= 0:
            self._client_combo.setCurrentIndex(idx)

        # Pre-cargar datos
        self._date_edit.setText(presupuesto["date"])
        self._valid_until_edit.setText(presupuesto["valid_until"])
        self._obs_edit.setText(presupuesto.get("observations") or "")

        # Pre-cargar tasa de IVA
        tax_pct = int(presupuesto["tax_rate"] * 100)
        tax_text = f"{tax_pct}%"
        idx = self._tax_combo.findText(tax_text)
        if idx >= 0:
            self._tax_combo.setCurrentIndex(idx)

        # Pre-cargar items
        self._items.clear()
        self._items_table.setRowCount(0)
        for item in presupuesto["items"]:
            self._items.append(item)
            row = self._items_table.rowCount()
            self._items_table.insertRow(row)
            self._items_table.setItem(row, 0, QTableWidgetItem(item["description"]))
            qty_item = QTableWidgetItem(f"{item['qty']:g}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(row, 1, qty_item)
            for col, val in [(2, f"$ {item['unit_price']:,.2f}"), (3, f"$ {item['subtotal']:,.2f}")]:
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._items_table.setItem(row, col, it)

        self._update_totals()

    def refresh(self):
        clients = db.get_all_clients()
        self._clients_data = clients
        current = self._client_combo.currentText()
        self._client_combo.clear()
        for c in clients:
            self._client_combo.addItem(c["name"], c["id"])
        if current:
            idx = self._client_combo.findText(current)
            if idx >= 0:
                self._client_combo.setCurrentIndex(idx)

    def _tax_rate(self):
        return {"21%": 0.21, "10.5%": 0.105, "0%": 0.0}.get(
            self._tax_combo.currentText(), 0.21)

    def _update_totals(self):
        subtotal   = sum(i["subtotal"] for i in self._items)
        tax_rate   = self._tax_rate()
        tax_label  = self._tax_combo.currentText()
        tax_amount = round(subtotal * tax_rate, 2)
        total      = round(subtotal + tax_amount, 2)

        self._lbl_sub.setText(f"Subtotal:    $ {subtotal:>12,.2f}")
        self._lbl_iva.setText(f"IVA {tax_label}:   $ {tax_amount:>12,.2f}")
        self._lbl_tot.setText(f"TOTAL:       $ {total:>12,.2f}")

    def _add_item(self):
        desc  = self._desc_edit.text().strip()
        q_str = self._qty_edit.text().strip().replace(",", ".")
        p_str = self._price_edit.text().strip().replace(",", ".")

        if not desc:
            QMessageBox.warning(self, "Atención", "Ingrese una descripción.")
            self._desc_edit.setFocus()
            return
        try:
            qty   = float(q_str)
            price = float(p_str)
            if qty <= 0 or price < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Atención",
                                "Cantidad y precio deben ser números válidos (mayores a 0).")
            return

        subtotal = round(qty * price, 2)
        self._items.append({"description": desc, "qty": qty,
                             "unit_price": price, "subtotal": subtotal})

        row = self._items_table.rowCount()
        self._items_table.insertRow(row)
        self._items_table.setItem(row, 0, QTableWidgetItem(desc))
        qty_item = QTableWidgetItem(f"{qty:g}")
        qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._items_table.setItem(row, 1, qty_item)
        for col, val in [(2, f"$ {price:,.2f}"), (3, f"$ {subtotal:,.2f}")]:
            it = QTableWidgetItem(val)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._items_table.setItem(row, col, it)

        self._desc_edit.clear()
        self._qty_edit.setText("1")
        self._price_edit.clear()
        self._desc_edit.setFocus()
        self._update_totals()

    def _remove_item(self):
        row = self._items_table.currentRow()
        if row < 0:
            return
        self._items_table.removeRow(row)
        self._items.pop(row)
        self._update_totals()

    def _new_client(self):
        dlg = ClientDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            cid = db.create_client(*dlg.result_data)
            self.refresh()
            idx = self._client_combo.findData(cid)
            if idx >= 0:
                self._client_combo.setCurrentIndex(idx)

    def _cancel(self):
        self._reset()
        self.app.show_page("presupuestos")

    def _reset(self):
        self._items.clear()
        self._items_table.setRowCount(0)
        self._desc_edit.clear()
        self._qty_edit.setText("1")
        self._price_edit.clear()
        self._obs_edit.clear()
        self._date_edit.setText(date.today().isoformat())
        from datetime import datetime, timedelta
        self._valid_until_edit.setText((datetime.now() + timedelta(days=30)).isoformat()[:10])
        self._tax_combo.setCurrentIndex(0)
        self._edit_id = None
        self._title_label.setText("Nuevo Presupuesto")
        self._update_totals()

    def _guardar(self):
        if not self._items:
            QMessageBox.warning(self, "Atención", "Agregue al menos un ítem.")
            return

        if self._client_combo.count() == 0:
            QMessageBox.warning(self, "Atención", "Seleccione un cliente.")
            return

        cid = self._client_combo.currentData()
        client = db.get_client(cid)
        if not client:
            QMessageBox.critical(self, "Error", "Cliente no encontrado.")
            return

        date_str = self._date_edit.text().strip()
        valid_until = self._valid_until_edit.text().strip()
        try:
            date.fromisoformat(date_str)
            date.fromisoformat(valid_until)
        except ValueError:
            QMessageBox.warning(self, "Atención",
                                "Fechas inválidas. Use el formato YYYY-MM-DD.")
            return

        tax_rate   = self._tax_rate()
        subtotal   = round(sum(i["subtotal"] for i in self._items), 2)
        tax_amount = round(subtotal * tax_rate, 2)
        total      = round(subtotal + tax_amount, 2)

        if self._edit_id:
            # Modo edición: actualizar presupuesto existente
            presupuesto_data = db.get_presupuesto(self._edit_id)
            db.update_presupuesto(
                presupuesto_id=self._edit_id,
                date=date_str,
                valid_until=valid_until,
                status=presupuesto_data["status"],
                client_id=client["id"],
                client_name=client["name"],
                client_address=client.get("address", ""),
                client_cuit=client.get("cuit_dni", ""),
                client_email=client.get("email", ""),
                client_phone=client.get("phone", ""),
                items=self._items,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=total,
                observations=self._obs_edit.text().strip(),
            )
            presupuesto_data = db.get_presupuesto(self._edit_id)
            pdf_path = pdf_gen.generate_pdf_presupuesto(presupuesto_data)
            db.update_presupuesto_pdf_path(self._edit_id, pdf_path)
            reply = QMessageBox.question(
                self, "Presupuesto actualizado",
                f"Presupuesto actualizado exitosamente.\n\n¿Abrir el PDF?",
            )
            if reply == QMessageBox.Yes:
                open_pdf(pdf_path)
        else:
            # Modo creación: crear nuevo presupuesto
            number = db.get_next_presupuesto_number()
            presupuesto_id = db.create_presupuesto(
                number=number, date=date_str, valid_until=valid_until,
                client_id=client["id"],
                client_name=client["name"],
                client_address=client.get("address", ""),
                client_cuit=client.get("cuit_dni", ""),
                client_email=client.get("email", ""),
                client_phone=client.get("phone", ""),
                items=self._items, subtotal=subtotal,
                tax_rate=tax_rate, tax_amount=tax_amount,
                total=total, observations=self._obs_edit.text().strip(),
            )

            presupuesto_data = db.get_presupuesto(presupuesto_id)
            pdf_path = pdf_gen.generate_pdf_presupuesto(presupuesto_data)
            db.update_presupuesto_pdf_path(presupuesto_id, pdf_path)

            reply = QMessageBox.question(
                self, "Presupuesto generado",
                f"Presupuesto {number} guardado exitosamente.\n\n¿Abrir el PDF?",
            )
            if reply == QMessageBox.Yes:
                open_pdf(pdf_path)

        self._reset()
        self.app.show_page("presupuestos")
        self.app.pages["presupuestos"].refresh()


# ── Página: Configuración ─────────────────────────────────────────────────────

class ConfiguracionPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._logo_path = ""
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title = QLabel("Configuración")
        title.setObjectName("page_title")
        title.setContentsMargins(28, 24, 28, 12)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("content_area")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 8, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(self._build_empresa())
        layout.addWidget(self._build_logo())
        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        b_save = make_btn("Guardar configuración", "success")
        b_save.clicked.connect(self._guardar)
        btns.addWidget(b_save)
        layout.addLayout(btns)

    def _card(self, title):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(12)
        lbl = QLabel(title)
        lbl.setObjectName("card_title")
        v.addWidget(lbl)
        return card, v

    def _build_empresa(self):
        card, layout = self._card("Datos de la empresa")

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 140)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(2, 24)
        grid.setColumnMinimumWidth(3, 140)
        grid.setColumnStretch(4, 1)

        self._f_nombre    = QLineEdit()
        self._f_direccion = QLineEdit()
        self._f_cuit      = QLineEdit()
        self._f_telefono  = QLineEdit()
        self._f_email     = QLineEdit()
        self._f_iibb      = QLineEdit()

        for row, (lbl_a, w_a, lbl_b, w_b) in enumerate([
            ("Nombre / Razón social *", self._f_nombre,    "CUIT",     self._f_cuit),
            ("Dirección",               self._f_direccion, "Teléfono", self._f_telefono),
            ("Email",                   self._f_email,     "IIBB",     self._f_iibb),
        ]):
            grid.addWidget(QLabel(lbl_a), row, 0)
            grid.addWidget(w_a,           row, 1)
            grid.addWidget(QLabel(lbl_b), row, 3)
            grid.addWidget(w_b,           row, 4)

        layout.addLayout(grid)
        return card

    def _build_logo(self):
        card, layout = self._card("Logo de la empresa")

        hint = QLabel("Se imprimirá en el encabezado de remitos, presupuestos y facturas. "
                       "Formatos admitidos: PNG, JPG.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(20)

        self._logo_preview = QLabel("Sin logo")
        self._logo_preview.setFixedSize(200, 80)
        self._logo_preview.setAlignment(Qt.AlignCenter)
        self._logo_preview.setStyleSheet(
            "border: 1px dashed #475569; border-radius: 6px; color: #64748b;"
        )
        row.addWidget(self._logo_preview)

        col = QVBoxLayout()
        col.setSpacing(8)
        b_pick  = make_btn("Seleccionar imagen…", "primary")
        b_clear = make_btn("Quitar logo",          "secondary")
        b_pick.clicked.connect(self._pick_logo)
        b_clear.clicked.connect(self._clear_logo)
        col.addWidget(b_pick)
        col.addWidget(b_clear)
        col.addStretch()
        row.addLayout(col)
        row.addStretch()

        layout.addLayout(row)
        return card

    def _pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar logo", "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._logo_path = path
            self._set_preview(path)

    def _clear_logo(self):
        self._logo_path = ""
        self._logo_preview.setPixmap(QPixmap())
        self._logo_preview.setText("Sin logo")

    def _set_preview(self, path):
        if path and os.path.exists(path):
            px = QPixmap(path).scaled(
                self._logo_preview.width() - 4,
                self._logo_preview.height() - 4,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._logo_preview.setPixmap(px)
        else:
            self._logo_preview.setPixmap(QPixmap())
            self._logo_preview.setText("Sin logo")

    def refresh(self):
        cfg = config_manager.load()
        self._f_nombre.setText(cfg.get("empresa_nombre",    ""))
        self._f_direccion.setText(cfg.get("empresa_direccion", ""))
        self._f_cuit.setText(cfg.get("empresa_cuit",        ""))
        self._f_telefono.setText(cfg.get("empresa_telefono",  ""))
        self._f_email.setText(cfg.get("empresa_email",       ""))
        self._f_iibb.setText(cfg.get("empresa_iibb",         ""))
        self._logo_path = cfg.get("logo_path", "")
        self._set_preview(self._logo_path)

    def _guardar(self):
        nombre = self._f_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atención", "El nombre de la empresa es obligatorio.")
            self._f_nombre.setFocus()
            return
        config_manager.save({
            "empresa_nombre":    nombre,
            "empresa_direccion": self._f_direccion.text().strip(),
            "empresa_cuit":      self._f_cuit.text().strip(),
            "empresa_telefono":  self._f_telefono.text().strip(),
            "empresa_email":     self._f_email.text().strip(),
            "empresa_iibb":      self._f_iibb.text().strip(),
            "logo_path":         self._logo_path,
        })
        QMessageBox.information(self, "Guardado", "Configuración guardada correctamente.")


# ── Ventana principal ─────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Restolibra")
        self.resize(1150, 740)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        lbl_title = QLabel("Restolibra")
        lbl_title.setObjectName("app_title")
        lbl_sub = QLabel("compulibra")
        lbl_sub.setObjectName("app_sub")
        sb_layout.addWidget(lbl_title)
        sb_layout.addWidget(lbl_sub)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        sb_layout.addWidget(sep)
        sb_layout.addSpacing(8)

        self._nav_btns = {}
        nav_items = [
            ("remitos",           "  Remitos"),
            ("nuevo_remito",      "  Nuevo Remito"),
            ("presupuestos",      "  Presupuestos"),
            ("nuevo_presupuesto", "  Nuevo Presupuesto"),
            ("facturas",          "  Facturas"),
            ("nueva_factura",     "  Nueva Factura"),
            ("clientes",          "  Clientes"),
            ("arca_config",       "  Certificado ARCA"),
            ("configuracion",     "  Configuración"),
        ]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("sidebar_nav")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.show_page(k))
            sb_layout.addWidget(btn)
            self._nav_btns[key] = btn

        sb_layout.addStretch()
        main_layout.addWidget(self._sidebar)

        # Contenido con stack
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")
        main_layout.addWidget(self._stack)

        self.pages = {}
        for key, PageClass in [
            ("remitos",           RemitosPage),
            ("nuevo_remito",      NuevoRemitoPage),
            ("presupuestos",      PresupuestosPage),
            ("nuevo_presupuesto", NuevoPresupuestoPage),
            ("facturas",          FacturasPage),
            ("nueva_factura",     NuevaFacturaPage),
            ("clientes",          ClientesPage),
            ("arca_config",       ARCAConfigPage),
            ("configuracion",     ConfiguracionPage),
        ]:
            page = PageClass(self)
            self.pages[key] = page
            self._stack.addWidget(page)

        self.show_page("remitos")

    def show_page(self, name):
        for key, btn in self._nav_btns.items():
            btn.setProperty("active", key == name)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        page = self.pages[name]
        self._stack.setCurrentWidget(page)
        if hasattr(page, "refresh"):
            page.refresh()


if __name__ == "__main__":
    db.init_db()
    os.makedirs(pdf_gen.PDF_DIR, exist_ok=True)
    os.makedirs(pdf_gen.PRESUPUESTOS_PDF_DIR, exist_ok=True)
    os.makedirs("facturas_pdf", exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
