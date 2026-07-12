
from services.pipeline import Pipeline
from core.settings import Settings
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
     QPushButton,
     QFormLayout,
     QFileDialog
)


class EntradaWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Victor Document AI - Entrada")
        self.resize(1100,700)
        self.settings = Settings()
        self.ruta_entrada = self.settings.origen
        self.ruta_destino = self.settings.destino

        central=QWidget()
        self.setCentralWidget(central)

        principal=QVBoxLayout(central)

        titulo=QLabel("📥 Bandeja de Entrada")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:28px;font-weight:bold;")
        principal.addWidget(titulo)

        cuerpo=QHBoxLayout()
        principal.addLayout(cuerpo)

        self.lista=QListWidget()
        self.lista.currentItemChanged.connect(self.documento_seleccionado)
        cuerpo.addWidget(self.lista,2)

        derecha=QVBoxLayout()
        cuerpo.addLayout(derecha,3)

        info=QGroupBox("Información del documento")
        form=QFormLayout()
        self.lbl_nombre=QLabel("-")
        self.lbl_ruta=QLabel("-")
        self.lbl_tamano=QLabel("-")
        self.lbl_fecha=QLabel("-")
        form.addRow("Nombre:",self.lbl_nombre)
        form.addRow("Ruta:",self.lbl_ruta)
        form.addRow("Tamaño:",self.lbl_tamano)
        form.addRow("Fecha:",self.lbl_fecha)
        info.setLayout(form)
        derecha.addWidget(info)

        ia=QGroupBox("🤖 IA")
        iaform=QFormLayout()
        self.lbl_tipo=QLabel("Sin analizar")
        self.lbl_empresa=QLabel("-")
        self.lbl_persona=QLabel("-")
        self.lbl_destino=QLabel("-")
        iaform.addRow("Categoría:",self.lbl_tipo)
        iaform.addRow("Empresa:",self.lbl_empresa)
        iaform.addRow("Persona:",self.lbl_persona)
        iaform.addRow("Destino:",self.lbl_destino)
        ia.setLayout(iaform)
        derecha.addWidget(ia)

        self.btn_analizar=QPushButton("🤖 Analizar")
        self.btn_aceptar=QPushButton("✔ Aceptar")
        self.btn_origen=QPushButton("📂 Cambiar origen")
        self.btn_destino=QPushButton("📁 Cambiar destino")
        self.pipeline = Pipeline()
        self.btn_origen.clicked.connect(self.cambiar_origen)
        self.btn_destino.clicked.connect(self.cambiar_destino)
        self.btn_analizar.clicked.connect(self.analizar_documento)
        self.btn_aceptar.clicked.connect(self.aceptar_documento)

        derecha.addWidget(self.btn_origen)
        derecha.addWidget(self.btn_destino)
        derecha.addWidget(self.btn_analizar)
        derecha.addWidget(self.btn_aceptar)
        derecha.addStretch()

        self.cargar_documentos()
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def cargar_documentos(self):
        print("Ruta actual:", self.ruta_entrada)
        print("Existe:", self.ruta_entrada.exists())

        self.lista.clear()

        if not self.ruta_entrada.exists():
            self.lista.addItem("La carpeta D:\\Entrada no existe.")
            return
        for archivo in sorted(self.ruta_entrada.iterdir()):
            print(archivo.name, archivo.is_file(), archivo.suffix)
            if archivo.is_file():
                self.lista.addItem("📄 " + archivo.name)


    def documento_seleccionado(self, actual, anterior):
        if actual is None:
            return
        archivo=self.ruta_entrada/actual.text().replace("📄 ","")
        if not archivo.exists():
            return
        self.lbl_nombre.setText(archivo.name)
        self.lbl_ruta.setText(str(archivo))
        self.lbl_tamano.setText(f"{round(archivo.stat().st_size/1024,1)} KB")
        self.lbl_fecha.setText(datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%d-%m-%Y %H:%M"))

    def analizar_documento(self):

        item = self.lista.currentItem()

        if item is None:
            return

        archivo = self.ruta_entrada / item.text().replace("📄 ", "")

        resultado = self.pipeline.procesar(archivo)

        self.lbl_tipo.setText(resultado["categoria"])
        self.lbl_empresa.setText(resultado["empresa"])
        self.lbl_persona.setText(resultado["persona"])
        self.lbl_destino.setText(resultado["destino"])


    def cambiar_origen(self):
        carpeta = QFileDialog.getExistingDirectory(self,"Seleccionar carpeta de origen",str(self.ruta_entrada))
        if carpeta:
            self.settings.set_origen(carpeta)
            self.ruta_entrada=self.settings.origen
            self.cargar_documentos()

    def cambiar_destino(self):
        carpeta = QFileDialog.getExistingDirectory(self,"Seleccionar carpeta de destino",str(self.ruta_destino))
        if carpeta:
            self.settings.set_destino(carpeta)
            self.ruta_destino=self.settings.destino

    def aceptar_documento(self):

        item = self.lista.currentItem()

        if item is None:
            return

        archivo = self.ruta_entrada / item.text().replace("📄 ", "")

        destino = self.lbl_destino.text()

        if destino == "-" or destino == "":
            return

        self.pipeline.aceptar(
            archivo,
            destino
    )

        self.cargar_documentos()

        if self.lista.count():
            self.lista.setCurrentRow(0)

        self.lbl_tipo.setText("Sin analizar")
        self.lbl_empresa.setText("-")
        self.lbl_persona.setText("-")
        self.lbl_destino.setText("-")
