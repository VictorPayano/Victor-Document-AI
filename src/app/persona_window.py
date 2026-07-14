from pathlib import Path
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QListWidget,
    QLabel
)

from core.system import Sistema
from core.settings import Settings
from explorer.explorer import Explorer
from widgets.navigation_bar import NavigationBar


class PersonaWindow(QMainWindow):

    def __init__(self, nombre):

        super().__init__()

        self.nombre = nombre

        self.setWindowTitle(nombre)

        self.resize(900, 600)

        # ==========================
        # Explorer
        # ==========================

        self.explorer = Explorer()

        self.ruta_inicio = Settings().destino / "Personas" / nombre

        self.ruta_actual = self.ruta_inicio

        self.historial = []

        # ==========================
        # Ventana
        # ==========================

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout()

        # ==========================
        # Título
        # ==========================

        self.titulo = QLabel(nombre)

        self.titulo.setAlignment(Qt.AlignCenter)

        self.titulo.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        layout.addWidget(self.titulo)

        # ==========================
        # Barra navegación
        # ==========================

        self.navigation = NavigationBar()

        layout.addWidget(self.navigation)

        # ==========================
        # Lista
        # ==========================

        self.lista = QListWidget()

        self.lista.itemDoubleClicked.connect(self.abrir_elemento)

        layout.addWidget(self.lista)

        central.setLayout(layout)

        # ==========================
        # Eventos
        # ==========================

        self.navigation.boton_inicio.clicked.connect(
            self.ir_inicio
        )

        self.navigation.boton_atras.clicked.connect(
            self.ir_atras
        )

        # ==========================
        # Primera carga
        # ==========================

        self.cargar_carpeta(self.ruta_inicio)

    # ======================================================

    def cargar_carpeta(self, ruta):

        ruta = Path(ruta)

        if ruta != self.ruta_actual:

            self.historial.append(self.ruta_actual)

        self.ruta_actual = ruta

        self.navigation.set_ruta(ruta.name)

        self.lista.clear()

        elementos = self.explorer.abrir(ruta)

        for elemento in elementos:

            if elemento["tipo"] == "carpeta":

                texto = "📂 " + elemento["nombre"]

            else:

                texto = "📄 " + elemento["nombre"]

            self.lista.addItem(texto)

    # ======================================================

    def abrir_elemento(self, item):

        nombre = item.text()[2:].strip()

        ruta = self.ruta_actual / nombre

        if ruta.is_dir():

            self.cargar_carpeta(ruta)

            return

        if ruta.exists():

            os.startfile(str(ruta))

    # ======================================================

    def ir_inicio(self):

        self.historial.clear()

        self.cargar_carpeta(self.ruta_inicio)

    # ======================================================

    def ir_atras(self):

        if not self.historial:

            return

        ruta = self.historial.pop()

        self.ruta_actual = ruta

        self.navigation.set_ruta(ruta.name)

        self.lista.clear()

        elementos = self.explorer.abrir(ruta)

        for elemento in elementos:

            if elemento["tipo"] == "carpeta":

                self.lista.addItem("📂 " + elemento["nombre"])

            else:

                self.lista.addItem("📄 " + elemento["nombre"])
