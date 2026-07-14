from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings


class BibliotecaWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Biblioteca")
        self.resize(1050, 720)
        self.raiz = Settings().destino / "Personas"

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        titulo = QLabel("Biblioteca documental")
        titulo.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(titulo)

        barra = QHBoxLayout()
        self.lbl_ruta = QLabel(str(self.raiz))
        btn_actualizar = QPushButton("Actualizar")
        btn_abrir = QPushButton("Abrir en Explorer")
        btn_actualizar.clicked.connect(self.cargar_raiz)
        btn_abrir.clicked.connect(self.abrir_elemento)
        barra.addWidget(self.lbl_ruta, 1)
        barra.addWidget(btn_actualizar)
        barra.addWidget(btn_abrir)
        layout.addLayout(barra)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabel("Personas, instancias y documentos")
        self.arbol.itemExpanded.connect(self.cargar_hijos)
        self.arbol.itemDoubleClicked.connect(self.abrir_elemento)
        layout.addWidget(self.arbol, 1)
        self.lbl_estado = QLabel()
        layout.addWidget(self.lbl_estado)
        self.cargar_raiz()

    def cargar_raiz(self):
        self.arbol.clear()
        if not self.raiz.exists():
            self.lbl_estado.setText("No se encontró la carpeta Personas en el NAS configurado.")
            return
        self.agregar_hijos(None, self.raiz)
        self.lbl_estado.setText("Abre una carpeta para cargar su contenido.")

    def agregar_hijos(self, padre, ruta):
        try:
            elementos = sorted(
                ruta.iterdir(), key=lambda elemento: (not elemento.is_dir(), elemento.name.lower())
            )
        except OSError as error:
            self.lbl_estado.setText(f"No se pudo leer el NAS: {error}")
            return
        for elemento in elementos:
            item = QTreeWidgetItem([elemento.name])
            item.setData(0, Qt.UserRole, str(elemento))
            if elemento.is_dir():
                item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            if padre is None:
                self.arbol.addTopLevelItem(item)
            else:
                padre.addChild(item)

    def cargar_hijos(self, item):
        if item.data(0, Qt.UserRole + 1):
            return
        ruta = Path(item.data(0, Qt.UserRole))
        if ruta.is_dir():
            self.agregar_hijos(item, ruta)
        item.setData(0, Qt.UserRole + 1, True)

    def abrir_elemento(self, item=None, columna=0):
        item = item or self.arbol.currentItem()
        if item is None:
            return
        ruta = Path(item.data(0, Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))
