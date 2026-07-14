import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressDialog,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from services.family_database import FamilyDatabase
from services.profile_extractor import ProfileExtractor
from app.camera_capture_dialog import CameraCaptureDialog


FIELD_LABELS = {
    "email": "Email", "phone": "Teléfono", "type": "Tipo", "primary": "Principal (sí/no)",
    "note": "Nota", "service_type": "Servicio", "company": "Compañía", "client_number": "N.º cliente",
    "contract_number": "N.º contrato", "username": "Usuario", "monthly_price": "Precio mensual",
    "billing_day": "Día de cobro", "payment_method": "Método de pago", "start_date": "Fecha inicio",
    "end_date": "Fecha vencimiento", "insurance_type": "Seguro", "policy_number": "N.º póliza",
    "monthly_payment": "Pago mensual", "status": "Estado", "bank": "Banco", "iban": "IBAN",
    "account_type": "Tipo de cuenta", "holder": "Titular", "card_type": "Tipo de tarjeta",
    "last_four": "Últimos 4 dígitos", "document_type": "Tipo de documento",
    "document_number": "N.º documento", "issuing_country": "País de emisión", "issue_date": "Fecha emisión",
    "expiry_date": "Fecha vencimiento", "file_path": "Ruta del archivo", "brand": "Marca",
    "model": "Modelo", "registration": "Matrícula", "year": "Año", "colour": "Color", "vin": "VIN",
    "fuel": "Combustible", "apk_until": "APK hasta", "relative_name": "Familiar",
    "relationship_type": "Relación",
}
FIELD_LABELS.update({"concept": "Concepto", "detail": "Detalle"})

BASIC_FIELDS = (
    "given_names", "surname", "date_of_birth", "tax_number", "reference_notes",
    "address", "postcode", "city", "country", "note",
)

BASIC_LABELS = {
    "given_names": "Nombre(s)", "surname": "Apellido", "date_of_birth": "Fecha de nacimiento",
    "tax_number": "Número fiscal", "reference_notes": "Referencia segura", "address": "Dirección",
    "postcode": "Código postal", "city": "Ciudad", "country": "País", "note": "Notas",
}


class ExtractionWorker(QObject):
    completed = Signal(dict)
    error = Signal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    @Slot()
    def run(self):
        try:
            self.completed.emit(ProfileExtractor().extract(self.file_path))
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class RelationDialog(QDialog):
    def __init__(self, title, fields, values=None, parent=None, relation_key=None, document_folder=None, field_labels=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 420)
        self.inputs = {}
        self.relation_key = relation_key
        self.document_folder = document_folder
        self.field_labels = field_labels or {}
        self.extraction_thread = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        values = values or {}
        for field in fields:
            edit = QPlainTextEdit() if field == "note" else QLineEdit()
            if field == "note":
                edit.setMaximumHeight(80)
                edit.setPlainText(values.get(field, ""))
            else:
                edit.setText(values.get(field, ""))
            self.inputs[field] = edit
            form.addRow(f"{self.field_labels.get(field, FIELD_LABELS.get(field, field))}:", edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.extract_button = None
        if self.relation_key:
            extract_button = QPushButton("Extraer desde documento…")
            extract_button.clicked.connect(self.extract_into_form)
            self.extract_button = extract_button
            buttons.addButton(extract_button, QDialogButtonBox.ActionRole)
            camera_button = QPushButton("Usar cámara…")
            camera_button.clicked.connect(self.capture_into_form)
            buttons.addButton(camera_button, QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)

    def extract_into_form(self):
        if self.extraction_thread is not None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir documento para completar este formulario",
            str(self.document_folder or ""),
            "Documentos (*.pdf *.jpg *.jpeg *.png)",
        )
        if not path:
            return
        self.start_extraction(Path(path))

    def capture_into_form(self):
        camera = CameraCaptureDialog(self)
        if camera.exec() == QDialog.Accepted and camera.captured_path:
            self.start_extraction(camera.captured_path)

    def start_extraction(self, path):
        if self.extraction_thread is not None:
            return
        self.extract_button.setEnabled(False)
        self.extraction_progress = QProgressDialog(
            "Leyendo el documento para este formulario…", None, 0, 0, self
        )
        self.extraction_progress.setWindowModality(Qt.WindowModal)
        self.extraction_progress.setCancelButton(None)
        self.extraction_progress.show()
        self.extraction_thread = QThread(self)
        self.extraction_worker = ExtractionWorker(Path(path))
        self.extraction_worker.moveToThread(self.extraction_thread)
        self.extraction_thread.started.connect(self.extraction_worker.run)
        self.extraction_worker.completed.connect(self.apply_extraction)
        self.extraction_worker.completed.connect(self.extraction_thread.quit)
        self.extraction_worker.completed.connect(self.extraction_worker.deleteLater)
        self.extraction_worker.error.connect(self.show_extraction_error)
        self.extraction_worker.error.connect(self.extraction_thread.quit)
        self.extraction_worker.error.connect(self.extraction_worker.deleteLater)
        self.extraction_thread.finished.connect(self.extraction_thread.deleteLater)
        self.extraction_thread.finished.connect(self.clean_extraction)
        self.extraction_thread.start()

    def apply_extraction(self, data):
        if getattr(self, "extraction_progress", None) is not None:
            self.extraction_progress.close()
        rows = data.get(self.relation_key, []) if self.relation_key else []
        if not rows and self.relation_key == "bank_accounts":
            # Una tarjeta bancaria puede al menos aportar banco/titular/tipo.
            cards = data.get("cards", [])
            rows = [{
                "bank": card.get("bank", ""),
                "account_type": card.get("card_type", ""),
                "holder": card.get("holder", ""),
                "status": card.get("status", ""),
                "note": card.get("note", ""),
            } for card in cards]
        if not rows:
            QMessageBox.information(
                self,
                "Extraer desde documento",
                "No se detectaron datos para este formulario. Puedes rellenarlo manualmente o probar otra pestaña.",
            )
            return
        row = rows[0]
        for field, widget in self.inputs.items():
            value = str(row.get(field, "") or "")
            if not value:
                continue
            if isinstance(widget, QPlainTextEdit):
                widget.setPlainText(value)
            else:
                widget.setText(value)

    def show_extraction_error(self, message):
        if getattr(self, "extraction_progress", None) is not None:
            self.extraction_progress.close()
        QMessageBox.critical(self, "Extraer desde documento", message)

    def clean_extraction(self):
        self.extraction_thread = None
        self.extraction_worker = None
        self.extraction_progress = None
        if self.extract_button is not None:
            self.extract_button.setEnabled(True)

    def values(self):
        return {
            field: widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()
            for field, widget in self.inputs.items()
        }


class ExtractionReviewDialog(QDialog):
    """Revisión editable: nada se escribe en la ficha hasta pulsar Guardar."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Revisar datos extraídos")
        self.resize(1100, 760)
        self.basic_inputs = {}
        self.related_tables = {}
        layout = QVBoxLayout(self)
        warning = QLabel("Revisa y corrige todos los campos. Puedes editar, añadir o borrar filas antes de guardar.")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        tabs = QTabWidget()

        basic_page = QWidget()
        basic_form = QFormLayout(basic_page)
        basic = data.get("basic") if isinstance(data.get("basic"), dict) else {}
        for field in BASIC_FIELDS:
            widget = QPlainTextEdit() if field == "note" else QLineEdit()
            if field == "note":
                widget.setMaximumHeight(70)
                widget.setPlainText(str(basic.get(field, "") or ""))
            else:
                widget.setText(str(basic.get(field, "") or ""))
            self.basic_inputs[field] = widget
            basic_form.addRow(f"{BASIC_LABELS[field]}:", widget)
        tabs.addTab(basic_page, "Datos básicos")

        for key, (title, fields) in FamilyDatabase.RELATED.items():
            page = QWidget()
            page_layout = QVBoxLayout(page)
            table = QTableWidget(0, len(fields))
            table.setHorizontalHeaderLabels([FIELD_LABELS.get(field, field) for field in fields])
            table.horizontalHeader().setStretchLastSection(True)
            for row in data.get(key, []) if isinstance(data.get(key), list) else []:
                self._add_row(table, fields, row if isinstance(row, dict) else {})
            page_layout.addWidget(table)
            actions = QHBoxLayout()
            add = QPushButton("Añadir fila")
            delete = QPushButton("Eliminar fila")
            add.clicked.connect(lambda _, target=table, values=fields: self._add_row(target, values, {}))
            delete.clicked.connect(lambda _, target=table: self._delete_row(target))
            actions.addWidget(add)
            actions.addWidget(delete)
            actions.addStretch()
            page_layout.addLayout(actions)
            tabs.addTab(page, title)
            self.related_tables[key] = (table, fields)
        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _add_row(table, fields, values):
        row_index = table.rowCount()
        table.insertRow(row_index)
        for column, field in enumerate(fields):
            table.setItem(row_index, column, QTableWidgetItem(str(values.get(field, "") or "")))
        table.resizeColumnsToContents()

    @staticmethod
    def _delete_row(table):
        if table.currentRow() >= 0:
            table.removeRow(table.currentRow())

    def values(self):
        basic = {
            field: widget.toPlainText().strip() if isinstance(widget, QPlainTextEdit) else widget.text().strip()
            for field, widget in self.basic_inputs.items()
        }
        result = {"basic": basic}
        for key, (table, fields) in self.related_tables.items():
            rows = []
            for row in range(table.rowCount()):
                values = {field: table.item(row, column).text().strip() if table.item(row, column) else ""
                          for column, field in enumerate(fields)}
                if any(values.values()):
                    rows.append(values)
            result[key] = rows
        return result


class TabConfigDialog(QDialog):
    """Visibilidad por persona y catálogo de pestañas adicionales."""

    def __init__(self, database, person_id, parent=None):
        super().__init__(parent)
        self.database = database
        self.person_id = person_id
        self.setWindowTitle("Configurar pestañas de la ficha")
        self.resize(480, 540)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Marca las pestañas que quieres usar para esta persona."))
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        add = QPushButton("Añadir pestaña")
        rename = QPushButton("Renombrar")
        fields = QPushButton("Gestionar campos")
        delete = QPushButton("Eliminar pestaña creada")
        add.clicked.connect(self.add_tab)
        rename.clicked.connect(self.rename_tab)
        fields.clicked.connect(self.manage_fields)
        delete.clicked.connect(self.delete_tab)
        actions.addWidget(add)
        actions.addWidget(rename)
        actions.addWidget(fields)
        actions.addWidget(delete)
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for key, (title, _) in FamilyDatabase.RELATED.items():
            self.add_item(key, title)
        for tab in self.database.custom_tabs():
            self.add_item(f"custom:{tab['id']}", tab["name"])

    def add_item(self, key, title):
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, key)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if self.database.tab_visible(self.person_id, key) else Qt.Unchecked)
        self.list.addItem(item)

    def add_tab(self):
        name, accepted = QInputDialog.getText(self, "Nueva pestaña", "Nombre, por ejemplo Trabajo o Pensión:")
        if not accepted:
            return
        try:
            self.database.add_custom_tab(name)
        except Exception as error:
            QMessageBox.warning(self, "Pestañas", str(error))
            return
        self.refresh()

    def rename_tab(self):
        item = self.list.currentItem()
        if item is None or not str(item.data(Qt.UserRole)).startswith("custom:"):
            QMessageBox.information(self, "Pestañas", "Solo se pueden renombrar las pestañas creadas por ti.")
            return
        name, accepted = QInputDialog.getText(self, "Renombrar pestaña", "Nuevo nombre:", text=item.text())
        if accepted:
            try:
                self.database.rename_custom_tab(int(str(item.data(Qt.UserRole)).split(":", 1)[1]), name)
            except Exception as error:
                QMessageBox.warning(self, "Pestañas", str(error))
            self.refresh()

    def delete_tab(self):
        item = self.list.currentItem()
        if item is None or not str(item.data(Qt.UserRole)).startswith("custom:"):
            QMessageBox.information(self, "Pestañas", "Solo se pueden eliminar las pestañas creadas por ti.")
            return
        if QMessageBox.question(self, "Eliminar pestaña", f"¿Eliminar '{item.text()}' y sus datos en todas las fichas?") != QMessageBox.Yes:
            return
        self.database.delete_custom_tab(int(str(item.data(Qt.UserRole)).split(":", 1)[1]))
        self.refresh()

    def manage_fields(self):
        item = self.list.currentItem()
        if item is None or not str(item.data(Qt.UserRole)).startswith("custom:"):
            QMessageBox.information(self, "Campos", "Selecciona una pestaña creada por ti para gestionar sus campos.")
            return
        tab_id = int(str(item.data(Qt.UserRole)).split(":", 1)[1])
        dialog = CustomFieldsDialog(self.database, tab_id, item.text(), self)
        dialog.exec()

    def save_visibility(self):
        for row in range(self.list.count()):
            item = self.list.item(row)
            self.database.set_tab_visibility(self.person_id, item.data(Qt.UserRole), item.checkState() == Qt.Checked)


class CustomFieldsDialog(QDialog):
    def __init__(self, database, tab_id, tab_name, parent=None):
        super().__init__(parent)
        self.database = database
        self.tab_id = tab_id
        self.setWindowTitle(f"Campos de {tab_name}")
        self.resize(430, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Crea los campos que necesites. El orden actual se usará en el formulario y el informe."))
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        add = QPushButton("Añadir campo")
        rename = QPushButton("Renombrar")
        delete = QPushButton("Eliminar campo")
        add.clicked.connect(self.add_field)
        rename.clicked.connect(self.rename_field)
        delete.clicked.connect(self.delete_field)
        actions.addWidget(add)
        actions.addWidget(rename)
        actions.addWidget(delete)
        layout.addLayout(actions)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for field in self.database.custom_tab_fields(self.tab_id):
            item = QListWidgetItem(field["name"])
            item.setData(Qt.UserRole, field["id"])
            self.list.addItem(item)

    def add_field(self):
        name, accepted = QInputDialog.getText(self, "Añadir campo", "Nombre del campo:")
        if accepted:
            try:
                self.database.add_custom_field(self.tab_id, name)
            except Exception as error:
                QMessageBox.warning(self, "Campos", str(error))
            self.refresh()

    def rename_field(self):
        item = self.list.currentItem()
        if item is None:
            return
        name, accepted = QInputDialog.getText(self, "Renombrar campo", "Nuevo nombre:", text=item.text())
        if accepted:
            try:
                self.database.rename_custom_field(item.data(Qt.UserRole), name)
            except Exception as error:
                QMessageBox.warning(self, "Campos", str(error))
            self.refresh()

    def delete_field(self):
        item = self.list.currentItem()
        if item is None:
            return
        if QMessageBox.question(self, "Eliminar campo", f"¿Eliminar el campo '{item.text()}'? También se borrará su contenido guardado.") != QMessageBox.Yes:
            return
        self.database.delete_custom_field(item.data(Qt.UserRole))
        self.refresh()


class PersonasWindow(QMainWindow):
    """Ficha familiar y vínculo con la carpeta de documentos de cada persona."""

    def __init__(self, person_id=None):
        super().__init__()
        self.settings = Settings()
        self.ruta_personas = self.settings.destino / "Personas"
        self.database = FamilyDatabase()
        self.current_person_id = person_id
        self.tables = {}
        self.tab_pages = {}
        self.custom_tables = {}
        self.extraction_thread = None

        self.setWindowTitle("Victor Document AI - Personas")
        self.resize(1500, 900)
        self.setMinimumSize(1150, 680)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("Personas y ficha familiar")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_people_panel())
        splitter.addWidget(self._create_profile_panel())
        splitter.setSizes([330, 1150])
        layout.addWidget(splitter, 1)

        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)
        self.refresh_people()

    def _create_people_panel(self):
        panel = QGroupBox("Personas")
        layout = QVBoxLayout(panel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar persona...")
        self.search.textChanged.connect(self.refresh_people)
        layout.addWidget(self.search)
        self.people_list = QListWidget()
        self.people_list.currentItemChanged.connect(self.select_person)
        self.people_list.itemDoubleClicked.connect(lambda _: self.open_folder())
        layout.addWidget(self.people_list, 1)

        buttons = QHBoxLayout()
        new_button = QPushButton("Nueva persona")
        folder_button = QPushButton("Abrir carpeta")
        new_button.clicked.connect(self.new_person)
        folder_button.clicked.connect(self.open_folder)
        buttons.addWidget(new_button)
        buttons.addWidget(folder_button)
        layout.addLayout(buttons)

        import_button = QPushButton("Importar datos de Access…")
        import_button.clicked.connect(self.import_access)
        layout.addWidget(import_button)
        return panel

    def _create_profile_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        profile = QGroupBox("Datos básicos")
        form = QFormLayout(profile)
        self.folder_name = QComboBox()
        self.folder_name.setEditable(True)
        self.given_names = QLineEdit()
        self.surname = QLineEdit()
        self.date_of_birth = QLineEdit()
        self.tax_number = QLineEdit()
        self.reference_notes = QLineEdit()
        self.address = QLineEdit()
        self.postcode = QLineEdit()
        self.city = QLineEdit()
        self.country = QLineEdit()
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(70)
        form.addRow("Carpeta de documentos:", self.folder_name)
        form.addRow("Nombre(s):", self.given_names)
        form.addRow("Apellido:", self.surname)
        form.addRow("Fecha de nacimiento:", self.date_of_birth)
        form.addRow("Número fiscal:", self.tax_number)
        form.addRow("Referencia segura:", self.reference_notes)
        form.addRow("Dirección:", self.address)
        form.addRow("Código postal:", self.postcode)
        form.addRow("Ciudad:", self.city)
        form.addRow("País:", self.country)
        form.addRow("Notas:", self.note)
        layout.addWidget(profile)

        save_button = QPushButton("Guardar ficha")
        extract_button = QPushButton("Autorrellenar desde documento…")
        camera_button = QPushButton("Usar cámara…")
        config_tabs_button = QPushButton("Configurar pestañas…")
        save_button.clicked.connect(self.save_person)
        extract_button.clicked.connect(self.extract_document)
        camera_button.clicked.connect(self.capture_document)
        config_tabs_button.clicked.connect(self.configure_tabs)
        profile_actions = QHBoxLayout()
        profile_actions.addWidget(save_button)
        profile_actions.addWidget(extract_button)
        profile_actions.addWidget(camera_button)
        profile_actions.addWidget(config_tabs_button)
        layout.addLayout(profile_actions)

        self.tabs = QTabWidget()
        for key, (title, fields) in FamilyDatabase.RELATED.items():
            page = self._create_relation_tab(key, title, fields)
            self.tab_pages[key] = page
            self.tabs.addTab(page, title)
        self.files_page = self._create_files_tab()
        self.tabs.addTab(self.files_page, "Archivos archivados")
        layout.addWidget(self.tabs, 1)
        return panel

    def _create_relation_tab(self, key, title, fields):
        page = QWidget()
        layout = QVBoxLayout(page)
        table = QTableWidget(0, len(fields))
        table.setHorizontalHeaderLabels([FIELD_LABELS.get(field, field) for field in fields])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.itemDoubleClicked.connect(lambda _, relation=key: self.edit_relation(relation))
        layout.addWidget(table)
        self.tables[key] = table
        buttons = QHBoxLayout()
        add_button = QPushButton("Añadir")
        edit_button = QPushButton("Editar")
        delete_button = QPushButton("Eliminar")
        extract_button = QPushButton("Extraer desde documento…")
        camera_button = QPushButton("Usar cámara…")
        add_button.clicked.connect(lambda _, relation=key: self.edit_relation(relation))
        edit_button.clicked.connect(lambda _, relation=key: self.edit_relation(relation))
        delete_button.clicked.connect(lambda _, relation=key: self.delete_relation(relation))
        extract_button.clicked.connect(self.extract_document)
        camera_button.clicked.connect(self.capture_document)
        buttons.addWidget(add_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(extract_button)
        buttons.addWidget(camera_button)
        layout.addLayout(buttons)
        return page

    def _create_files_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.files_table = QTableWidget(0, 2)
        self.files_table.setHorizontalHeaderLabels(["Archivo", "Ruta"])
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.files_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.itemDoubleClicked.connect(self.open_archived_file)
        extract_button = QPushButton("Extraer datos del archivo seleccionado")
        camera_button = QPushButton("Usar cámara para nuevo documento")
        extract_button.clicked.connect(self.extract_selected_file)
        camera_button.clicked.connect(self.capture_document)
        layout.addWidget(QLabel("Archivos encontrados en la carpeta de la persona. Doble clic para abrir."))
        layout.addWidget(self.files_table)
        layout.addWidget(extract_button)
        layout.addWidget(camera_button)
        return page

    def _create_custom_tab(self, tab):
        page = QWidget()
        layout = QVBoxLayout(page)
        fields = self.database.custom_tab_fields(tab["id"])
        table = QTableWidget(0, len(fields))
        table.setHorizontalHeaderLabels([field["name"] for field in fields])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        tab_id = tab["id"]
        table.itemDoubleClicked.connect(lambda _, value=tab_id: self.edit_custom_entry(value))
        layout.addWidget(table)
        buttons = QHBoxLayout()
        add = QPushButton("Añadir")
        edit = QPushButton("Editar")
        delete = QPushButton("Eliminar")
        add.clicked.connect(lambda _, value=tab_id: self.edit_custom_entry(value))
        edit.clicked.connect(lambda _, value=tab_id: self.edit_custom_entry(value))
        delete.clicked.connect(lambda _, value=tab_id: self.delete_custom_entry(value))
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addWidget(delete)
        layout.addLayout(buttons)
        self.custom_tables[tab_id] = (table, fields)
        return page

    def configure_tabs(self):
        if not self.current_person_id:
            QMessageBox.information(self, "Pestañas", "Guarda primero la ficha de la persona.")
            return
        dialog = TabConfigDialog(self.database, self.current_person_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        dialog.save_visibility()
        self.update_tabs()
        self.load_related()

    def update_tabs(self):
        if not hasattr(self, "tabs"):
            return
        for page in list(getattr(self, "custom_pages", {}).values()):
            index = self.tabs.indexOf(page)
            if index >= 0:
                self.tabs.removeTab(index)
        self.custom_pages = {}
        self.custom_tables = {}
        files_index = self.tabs.indexOf(self.files_page)
        if files_index >= 0:
            self.tabs.removeTab(files_index)
        for key, page in self.tab_pages.items():
            index = self.tabs.indexOf(page)
            if index >= 0:
                visible = self.database.tab_visible(self.current_person_id, key) if self.current_person_id else True
                self.tabs.setTabVisible(index, visible)
        for tab in self.database.custom_tabs():
            key = f"custom:{tab['id']}"
            page = self._create_custom_tab(tab)
            self.custom_pages[tab["id"]] = page
            index = self.tabs.addTab(page, tab["name"])
            self.tabs.setTabVisible(index, self.database.tab_visible(self.current_person_id, key) if self.current_person_id else True)
        self.tabs.addTab(self.files_page, "Archivos archivados")

    def load_custom_entries(self):
        for tab_id, (table, fields) in self.custom_tables.items():
            rows = self.database.custom_entries(self.current_person_id, tab_id)
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column, field in enumerate(fields):
                    item = QTableWidgetItem(row.get(field["field_key"], ""))
                    if column == 0:
                        item.setData(Qt.UserRole, row["id"])
                    table.setItem(row_index, column, item)
            table.resizeColumnsToContents()

    def edit_custom_entry(self, tab_id):
        if not self.current_person_id:
            return
        table, fields = self.custom_tables[tab_id]
        row = table.currentRow()
        entry_id, values = None, {}
        if row >= 0:
            entry_id = table.item(row, 0).data(Qt.UserRole)
            values = {field["field_key"]: table.item(row, column).text() for column, field in enumerate(fields)}
        tab = next((item for item in self.database.custom_tabs() if item["id"] == tab_id), None)
        field_keys = tuple(field["field_key"] for field in fields)
        labels = {field["field_key"]: field["name"] for field in fields}
        dialog = RelationDialog(tab["name"] if tab else "Pestaña", field_keys, values, self, field_labels=labels)
        if dialog.exec() == QDialog.Accepted:
            self.database.save_custom_entry(self.current_person_id, tab_id, dialog.values(), entry_id)
            self.load_custom_entries()

    def delete_custom_entry(self, tab_id):
        table, _fields = self.custom_tables[tab_id]
        row = table.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar el registro seleccionado?") != QMessageBox.Yes:
            return
        self.database.delete_custom_entry(self.current_person_id, tab_id, table.item(row, 0).data(Qt.UserRole))
        self.load_custom_entries()

    def folders(self):
        try:
            return sorted((folder.name for folder in self.ruta_personas.iterdir() if folder.is_dir()), key=str.casefold)
        except OSError:
            return []

    def refresh_people(self):
        self.database.sync_folders(self.ruta_personas)
        selected_id = self.current_person_id
        query = self.search.text().strip().casefold() if hasattr(self, "search") else ""
        people = self.database.people()
        self.people_list.blockSignals(True)
        self.people_list.clear()
        for person in people:
            text = " ".join(item for item in (person["given_names"], person["surname"]) if item).strip()
            text = text or person["folder_name"]
            if query and query not in text.casefold() and query not in person["folder_name"].casefold():
                continue
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, person["id"])
            item.setToolTip(f"Carpeta: {person['folder_name']}")
            self.people_list.addItem(item)
            if person["id"] == selected_id:
                self.people_list.setCurrentItem(item)
        self.people_list.blockSignals(False)
        if selected_id and self.people_list.currentItem():
            self.select_person(self.people_list.currentItem())
        elif self.people_list.count() and self.current_person_id is None:
            self.people_list.setCurrentRow(0)
        self.lbl_status.setText(f"{self.people_list.count()} ficha(s) de persona.")

    def select_person(self, item, _previous=None):
        if item is None:
            return
        person = self.database.get_person(item.data(Qt.UserRole))
        if not person:
            return
        self.current_person_id = person["id"]
        self.set_form_values(person)
        self.load_related()

    def set_form_values(self, person):
        self.folder_name.blockSignals(True)
        self.folder_name.clear()
        self.folder_name.addItems(self.folders())
        if self.folder_name.findText(person["folder_name"]) < 0:
            self.folder_name.addItem(person["folder_name"])
        self.folder_name.setCurrentText(person["folder_name"])
        self.folder_name.blockSignals(False)
        for field in ("given_names", "surname", "date_of_birth", "tax_number", "reference_notes", "address", "postcode", "city", "country"):
            getattr(self, field).setText(person.get(field, "") or "")
        self.note.setPlainText(person.get("note", "") or "")

    def new_person(self):
        self.current_person_id = None
        self.people_list.clearSelection()
        self.set_form_values({"folder_name": "", "note": ""})
        for field in ("given_names", "surname", "date_of_birth", "tax_number", "reference_notes", "address", "postcode", "city", "country"):
            getattr(self, field).clear()
        self.note.clear()
        self.clear_related()
        self.lbl_status.setText("Nueva ficha: indica al menos la carpeta y el nombre, después guarda.")

    def save_person(self):
        values = {
            "folder_name": self.folder_name.currentText(), "given_names": self.given_names.text(),
            "surname": self.surname.text(), "date_of_birth": self.date_of_birth.text(),
            "tax_number": self.tax_number.text(), "reference_notes": self.reference_notes.text(),
            "address": self.address.text(), "postcode": self.postcode.text(), "city": self.city.text(),
            "country": self.country.text(), "note": self.note.toPlainText(),
        }
        try:
            folder = self.ruta_personas / values["folder_name"].strip()
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
            self.current_person_id = self.database.save_person(values, self.current_person_id)
        except (OSError, ValueError, sqlite3.IntegrityError) as error:
            QMessageBox.warning(self, "Ficha de persona", str(error))
            return
        self.refresh_people()
        self.lbl_status.setText("Ficha guardada y vinculada a su carpeta de documentos.")

    def load_related(self):
        if not self.current_person_id:
            self.clear_related()
            return
        self.update_tabs()
        for key, (_, fields) in FamilyDatabase.RELATED.items():
            table = self.tables[key]
            rows = self.database.related(key, self.current_person_id)
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, field in enumerate(fields):
                    item = QTableWidgetItem(row.get(field, ""))
                    if column_index == 0:
                        item.setData(Qt.UserRole, row["id"])
                    table.setItem(row_index, column_index, item)
            table.resizeColumnsToContents()
        self.load_custom_entries()
        self.load_archived_files()

    def clear_related(self):
        for table in self.tables.values():
            table.setRowCount(0)
        for table, _fields in self.custom_tables.values():
            table.setRowCount(0)
        self.files_table.setRowCount(0)

    def edit_relation(self, key):
        if not self.current_person_id:
            QMessageBox.information(self, "Ficha de persona", "Guarda primero la ficha de la persona.")
            return
        table = self.tables[key]
        row_index = table.currentRow()
        record_id, values = None, {}
        if row_index >= 0:
            record_id = table.item(row_index, 0).data(Qt.UserRole)
            fields = FamilyDatabase.RELATED[key][1]
            values = {field: table.item(row_index, index).text() for index, field in enumerate(fields)}
        title, fields = FamilyDatabase.RELATED[key]
        person = self.database.get_person(self.current_person_id) if self.current_person_id else None
        document_folder = self.ruta_personas / person["folder_name"] if person else self.ruta_personas
        dialog = RelationDialog(title, fields, values, self, key, document_folder)
        if dialog.exec() != QDialog.Accepted:
            return
        self.database.save_related(key, self.current_person_id, dialog.values(), record_id)
        self.load_related()

    def delete_relation(self, key):
        if not self.current_person_id:
            return
        table = self.tables[key]
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Ficha de persona", "Selecciona primero un registro.")
            return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar el registro seleccionado?") != QMessageBox.Yes:
            return
        self.database.delete_related(key, self.current_person_id, table.item(row, 0).data(Qt.UserRole))
        self.load_related()

    def load_archived_files(self):
        self.files_table.setRowCount(0)
        person = self.database.get_person(self.current_person_id)
        if not person:
            return
        folder = self.ruta_personas / person["folder_name"]
        try:
            files = sorted((item for item in folder.rglob("*") if item.is_file()), key=lambda item: str(item).casefold())
        except OSError:
            files = []
        self.files_table.setRowCount(len(files))
        for row, file in enumerate(files):
            name = QTableWidgetItem(file.name)
            name.setData(Qt.UserRole, str(file))
            self.files_table.setItem(row, 0, name)
            self.files_table.setItem(row, 1, QTableWidgetItem(str(file.relative_to(folder))))
        self.files_table.resizeColumnsToContents()

    def open_folder(self):
        if not self.current_person_id:
            return
        person = self.database.get_person(self.current_person_id)
        if person:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ruta_personas / person["folder_name"])))

    def open_archived_file(self, _item):
        row = self.files_table.currentRow()
        path = self.files_table.item(row, 0).data(Qt.UserRole) if row >= 0 else None
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def extract_document(self):
        if not self.current_person_id:
            QMessageBox.information(self, "Autorrellenar", "Guarda primero la ficha de la persona.")
            return
        person = self.database.get_person(self.current_person_id)
        start_folder = str(self.ruta_personas / person["folder_name"])
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir documento para extraer datos",
            start_folder,
            "Documentos (*.pdf *.jpg *.jpeg *.png)",
        )
        if path:
            self.start_extraction(Path(path))

    def extract_selected_file(self):
        row = self.files_table.currentRow()
        path = self.files_table.item(row, 0).data(Qt.UserRole) if row >= 0 else None
        if not path:
            QMessageBox.information(self, "Autorrellenar", "Selecciona un archivo archivado primero.")
            return
        self.start_extraction(Path(path))

    def capture_document(self):
        if not self.current_person_id:
            QMessageBox.information(self, "Usar cámara", "Guarda primero la ficha de la persona.")
            return
        camera = CameraCaptureDialog(self)
        if camera.exec() == QDialog.Accepted and camera.captured_path:
            self.start_extraction(camera.captured_path)

    def start_extraction(self, file_path):
        if self.extraction_thread is not None:
            return
        self.extraction_progress = QProgressDialog(
            "Leyendo el documento y preparando los campos para revisar…", None, 0, 0, self
        )
        self.extraction_progress.setWindowModality(Qt.WindowModal)
        self.extraction_progress.setCancelButton(None)
        self.extraction_progress.show()
        self.extraction_thread = QThread(self)
        self.extraction_worker = ExtractionWorker(file_path)
        self.extraction_worker.moveToThread(self.extraction_thread)
        self.extraction_thread.started.connect(self.extraction_worker.run)
        self.extraction_worker.completed.connect(self.review_extraction)
        self.extraction_worker.completed.connect(self.extraction_thread.quit)
        self.extraction_worker.completed.connect(self.extraction_worker.deleteLater)
        self.extraction_worker.error.connect(self.extraction_error)
        self.extraction_worker.error.connect(self.extraction_thread.quit)
        self.extraction_worker.error.connect(self.extraction_worker.deleteLater)
        self.extraction_thread.finished.connect(self.extraction_thread.deleteLater)
        self.extraction_thread.finished.connect(self.clean_extraction)
        self.extraction_thread.start()

    def review_extraction(self, data):
        self.extraction_progress.close()
        review = ExtractionReviewDialog(data, self)
        if review.exec() != QDialog.Accepted or not self.current_person_id:
            return
        values = review.values()
        person = self.database.get_person(self.current_person_id)
        merged = dict(person)
        for field, value in values["basic"].items():
            if value:
                merged[field] = value
        try:
            self.database.save_person(merged, self.current_person_id)
            for key, rows in values.items():
                if key == "basic":
                    continue
                for row in rows:
                    self.database.save_related(key, self.current_person_id, row)
        except Exception as error:
            QMessageBox.critical(self, "Autorrellenar", f"No se pudieron guardar los datos revisados:\n{error}")
            return
        self.refresh_people()
        self.load_related()
        self.lbl_status.setText("Datos revisados y guardados desde el documento.")

    def extraction_error(self, message):
        self.extraction_progress.close()
        QMessageBox.critical(self, "Autorrellenar desde documento", message)

    def clean_extraction(self):
        self.extraction_thread = None
        self.extraction_worker = None
        self.extraction_progress = None

    def import_access(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar datos de Access", "", "Base de Access (*.accdb *.mdb)")
        if not path:
            return
        if QMessageBox.question(
            self,
            "Importar desde Access",
            "Se copiarán los datos a la ficha local. El archivo de Access no se modificará.\n\n"
            "Por seguridad, las contraseñas no se importan. ¿Continuar?",
        ) != QMessageBox.Yes:
            return
        try:
            imported = self.database.import_access(path, self.ruta_personas)
        except Exception as error:
            QMessageBox.critical(self, "Importar desde Access", f"No se pudo completar la importación:\n{error}")
            return
        self.current_person_id = None
        self.refresh_people()
        QMessageBox.information(self, "Importar desde Access", f"Importación terminada: {imported} ficha(s) actualizada(s).")
