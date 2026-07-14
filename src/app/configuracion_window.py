import json
import os
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings


class ConfiguracionWindow(QMainWindow):

    ARCHIVOS_APRENDIZAJE = ("learning.json", "person_aliases.json", "instance_choices.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Configuración")
        self.resize(850, 600)
        self.settings = Settings()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        titulo = QLabel("Configuración")
        titulo.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(titulo)

        rutas = QGroupBox("Carpetas")
        formulario = QFormLayout(rutas)
        self.txt_origen = QLineEdit(str(self.settings.origen))
        self.txt_destino = QLineEdit(str(self.settings.destino))
        for campo in (self.txt_origen, self.txt_destino):
            campo.setReadOnly(True)
        btn_origen = QPushButton("Cambiar…")
        btn_destino = QPushButton("Cambiar…")
        btn_origen.clicked.connect(lambda: self.elegir_carpeta(self.txt_origen, "Seleccionar origen"))
        btn_destino.clicked.connect(lambda: self.elegir_carpeta(self.txt_destino, "Seleccionar destino"))
        fila_origen = QHBoxLayout()
        fila_origen.addWidget(self.txt_origen, 1)
        fila_origen.addWidget(btn_origen)
        fila_destino = QHBoxLayout()
        fila_destino.addWidget(self.txt_destino, 1)
        fila_destino.addWidget(btn_destino)
        formulario.addRow("Origen:", fila_origen)
        formulario.addRow("Destino NAS:", fila_destino)
        layout.addWidget(rutas)

        procesamiento = QGroupBox("OCR e impresión")
        formulario_procesamiento = QFormLayout(procesamiento)
        self.cmb_ocr = QComboBox()
        self.cmb_ocr.addItems(["nld+spa+eng", "nld+eng", "nld", "spa+eng"])
        self.cmb_ocr.setCurrentText(self.settings.ocr_idioma)
        self.cmb_impresora = QComboBox()
        self.cmb_impresora.addItem("Predeterminada del sistema", "")
        for impresora in QPrinterInfo.availablePrinterNames():
            self.cmb_impresora.addItem(impresora, impresora)
        indice = self.cmb_impresora.findData(self.settings.impresora)
        self.cmb_impresora.setCurrentIndex(indice if indice >= 0 else 0)
        formulario_procesamiento.addRow("Idiomas OCR:", self.cmb_ocr)
        formulario_procesamiento.addRow("Impresora preferida:", self.cmb_impresora)
        layout.addWidget(procesamiento)

        ia = QGroupBox("IA y aprendizaje local")
        ia_layout = QVBoxLayout(ia)
        self.lbl_api = QLabel()
        self.lbl_aprendizaje = QLabel()
        self.btn_abrir_datos = QPushButton("Abrir carpeta de datos")
        self.btn_reiniciar = QPushButton("Restablecer aprendizaje")
        self.btn_abrir_datos.clicked.connect(self.abrir_carpeta_datos)
        self.btn_reiniciar.clicked.connect(self.restablecer_aprendizaje)
        ia_layout.addWidget(self.lbl_api)
        ia_layout.addWidget(self.lbl_aprendizaje)
        ia_layout.addWidget(self.btn_abrir_datos)
        ia_layout.addWidget(self.btn_reiniciar)
        layout.addWidget(ia)

        self.btn_guardar = QPushButton("Guardar configuración")
        self.btn_guardar.clicked.connect(self.guardar)
        layout.addWidget(self.btn_guardar)
        layout.addStretch()
        self.actualizar_estado()

    def elegir_carpeta(self, campo, titulo):
        carpeta = QFileDialog.getExistingDirectory(self, titulo, campo.text())
        if carpeta:
            campo.setText(carpeta)

    def guardar(self):
        self.settings.set_origen(self.txt_origen.text())
        self.settings.set_destino(self.txt_destino.text())
        self.settings.set_ocr_idioma(self.cmb_ocr.currentText())
        self.settings.set_impresora(self.cmb_impresora.currentData() or "")
        QMessageBox.information(self, "Configuración", "La configuración se guardó correctamente.")

    def actualizar_estado(self):
        proyecto = Path(__file__).resolve().parents[2]
        clave_disponible = bool(os.environ.get("OPENAI_API_KEY"))
        archivo_env = proyecto / ".env"
        if not clave_disponible and archivo_env.exists():
            try:
                clave_disponible = "OPENAI_API_KEY=" in archivo_env.read_text(encoding="utf-8")
            except OSError:
                pass
        self.lbl_api.setText(
            "OpenAI API: configurada" if clave_disponible else "OpenAI API: no configurada"
        )

        datos = self.settings.ruta_config.parent
        total = 0
        for nombre in self.ARCHIVOS_APRENDIZAJE:
            ruta = datos / nombre
            try:
                contenido = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
                total += len(contenido) if isinstance(contenido, dict) else 0
            except (OSError, json.JSONDecodeError):
                pass
        self.lbl_aprendizaje.setText(f"Aprendizajes locales guardados: {total}")

    def abrir_carpeta_datos(self):
        carpeta = self.settings.ruta_config.parent
        carpeta.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

    def restablecer_aprendizaje(self):
        respuesta = QMessageBox.question(
            self,
            "Restablecer aprendizaje",
            "¿Eliminar todos los alias, rutas e instancias aprendidas?\n\n"
            "No se modificarán documentos, carpetas ni el catálogo de instancias.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return
        for nombre in self.ARCHIVOS_APRENDIZAJE:
            ruta = self.settings.ruta_config.parent / nombre
            try:
                ruta.unlink(missing_ok=True)
            except OSError as error:
                QMessageBox.warning(self, "Aprendizaje", f"No se pudo eliminar {nombre}: {error}")
        self.actualizar_estado()
