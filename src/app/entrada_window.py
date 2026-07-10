from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
)

from PySide6.QtCore import Qt


class EntradaWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Entrada")

        self.resize(900, 600)

        self.ruta_entrada = Path("D:/Entrada")

        # ==========================
        # Ventana
        # ==========================

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout()

        contenedor = QHBoxLayout()

        layout.addLayout(contenedor)  

        # ==========================
        # Título
        # ==========================

        titulo = QLabel("📥 Bandeja de Entrada")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        # ==========================
        # Lista
        # ==========================

        self.lista = QListWidget()

        self.lista.currentItemChanged.connect(self.documento_seleccionado)

        contenedor.addWidget(self.lista, 1)

        central.setLayout(layout)

        self.cargar_documentos()

        panel = QGroupBox("Información del documento")

        panel_layout = QVBoxLayout()

        self.lbl_nombre = QLabel("Nombre:")

        self.lbl_ruta = QLabel("Ruta:")

        self.lbl_tamano = QLabel("Tamaño:")

        self.lbl_fecha = QLabel("Fecha:")

        panel_layout.addWidget(self.lbl_nombre)
        panel_layout.addWidget(self.lbl_ruta)
        panel_layout.addWidget(self.lbl_tamano)
        panel_layout.addWidget(self.lbl_fecha)

        panel.setLayout(panel_layout)

        contenedor.addWidget(panel, 2)

 
    # ====================================

    def cargar_documentos(self):

        self.lista.clear()

        if not self.ruta_entrada.exists():

            self.lista.addItem("La carpeta D:\\Entrada no existe.")

            return

        pdfs = sorted(self.ruta_entrada.glob("*.pdf"))

        if len(pdfs) == 0:

            self.lista.addItem("No hay documentos.")

            return

        for pdf in pdfs:

            self.lista.addItem("📄 " + pdf.name)

        # ====================================

    def documento_seleccionado(self, actual, anterior):

        if actual is None:
            return

        nombre = actual.text().replace("📄 ", "")

        archivo = self.ruta_entrada / nombre

        if not archivo.exists():
            return

        tamano = round(archivo.stat().st_size / 1024, 1)

        fecha = datetime.fromtimestamp(
            archivo.stat().st_mtime
        ).strftime("%d-%m-%Y %H:%M")

        self.lbl_nombre.setText(f"Nombre: {archivo.name}")
        self.lbl_ruta.setText(f"Ruta: {archivo}")
        self.lbl_tamano.setText(f"Tamaño: {tamano} KB")
        self.lbl_fecha.setText(f"Fecha: {fecha}")        

            