from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
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
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from services.document_assistant import DocumentAssistant
from services.family_database import FamilyDatabase


class AsistenteWorker(QObject):
    finalizado = Signal(str)
    error = Signal(str)

    def __init__(self, archivo, tarea, idioma):
        super().__init__()
        self.archivo = archivo
        self.tarea = tarea
        self.idioma = idioma

    @Slot()
    def ejecutar(self):
        try:
            self.finalizado.emit(DocumentAssistant().consultar(self.archivo, self.tarea, self.idioma))
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class IAWindow(QMainWindow):

    TAREAS = (
        ("Resumen", "resumen"),
        ("Qué solicita / acciones", "acciones"),
        ("Preparar respuesta", "respuesta"),
        ("Traducir documento", "traduccion"),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - IA")
        self.resize(1100, 760)
        self.archivo = None
        self.hilo = None
        self.family_database = FamilyDatabase()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        titulo = QLabel("Asistente IA y ficha familiar")
        titulo.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(titulo)
        nota = QLabel("La IA analiza el documento original. Revisa siempre el resultado antes de tomar decisiones o enviarlo.")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        ficha = QGroupBox("Consultar ficha familiar (datos locales)")
        ficha_form = QFormLayout(ficha)
        self.pregunta_ficha = QLineEdit()
        self.pregunta_ficha.setPlaceholderText("Ej.: dame las cuentas bancarias de Victor")
        self.btn_consultar_ficha = QPushButton("Consultar ficha")
        self.btn_consultar_ficha.clicked.connect(self.consultar_ficha)
        fila_ficha = QHBoxLayout()
        fila_ficha.addWidget(self.pregunta_ficha, 1)
        fila_ficha.addWidget(self.btn_consultar_ficha)
        ficha_form.addRow("Pregunta:", fila_ficha)
        ficha_form.addRow(QLabel("La consulta se realiza en este equipo; los datos familiares no se envían a la IA."))
        layout.addWidget(ficha)

        opciones = QGroupBox("Documento y tarea")
        formulario = QFormLayout(opciones)
        self.lbl_archivo = QLabel("No se ha seleccionado un documento.")
        self.cmb_tarea = QComboBox()
        for etiqueta, valor in self.TAREAS:
            self.cmb_tarea.addItem(etiqueta, valor)
        self.cmb_idioma = QComboBox()
        self.cmb_idioma.addItems(["español", "holandés", "inglés", "francés"])
        btn_elegir = QPushButton("Elegir documento…")
        btn_elegir.clicked.connect(self.elegir_documento)
        fila = QHBoxLayout()
        fila.addWidget(self.lbl_archivo, 1)
        fila.addWidget(btn_elegir)
        formulario.addRow("Documento:", fila)
        formulario.addRow("Tarea:", self.cmb_tarea)
        formulario.addRow("Idioma de respuesta:", self.cmb_idioma)
        layout.addWidget(opciones)

        self.resultado = QPlainTextEdit()
        self.resultado.setReadOnly(True)
        self.resultado.setPlaceholderText("El resultado de la IA aparecerá aquí.")
        layout.addWidget(self.resultado, 1)

        acciones = QHBoxLayout()
        self.btn_ejecutar = QPushButton("Analizar con IA")
        self.btn_guardar = QPushButton("Guardar resultado")
        self.btn_ejecutar.setEnabled(False)
        self.btn_guardar.setEnabled(False)
        self.btn_ejecutar.clicked.connect(self.ejecutar)
        self.btn_guardar.clicked.connect(self.guardar_resultado)
        acciones.addWidget(self.btn_ejecutar)
        acciones.addWidget(self.btn_guardar)
        acciones.addStretch()
        layout.addLayout(acciones)

    def consultar_ficha(self):
        respuesta = self.family_database.consult(self.pregunta_ficha.text())
        self.resultado.setPlainText(respuesta)
        self.btn_guardar.setEnabled(True)

    def elegir_documento(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar documento",
            "",
            "Documentos (*.pdf *.jpg *.jpeg *.png)",
        )
        if ruta:
            self.archivo = Path(ruta)
            self.lbl_archivo.setText(self.archivo.name)
            self.btn_ejecutar.setEnabled(True)

    def ejecutar(self):
        if self.archivo is None or self.hilo is not None:
            return
        self.progreso = QProgressDialog("La IA está analizando el documento…", None, 0, 0, self)
        self.progreso.setWindowModality(Qt.WindowModal)
        self.progreso.setCancelButton(None)
        self.progreso.show()
        self.btn_ejecutar.setEnabled(False)
        self.hilo = QThread(self)
        self.worker = AsistenteWorker(
            self.archivo,
            self.cmb_tarea.currentData(),
            self.cmb_idioma.currentText(),
        )
        self.worker.moveToThread(self.hilo)
        self.hilo.started.connect(self.worker.ejecutar)
        self.worker.finalizado.connect(self.mostrar_resultado)
        self.worker.finalizado.connect(self.hilo.quit)
        self.worker.finalizado.connect(self.worker.deleteLater)
        self.worker.error.connect(self.mostrar_error)
        self.worker.error.connect(self.hilo.quit)
        self.worker.error.connect(self.worker.deleteLater)
        self.hilo.finished.connect(self.hilo.deleteLater)
        self.hilo.finished.connect(self.limpiar)
        self.hilo.start()

    def mostrar_resultado(self, resultado):
        self.progreso.close()
        self.resultado.setPlainText(resultado)
        self.btn_guardar.setEnabled(True)

    def mostrar_error(self, mensaje):
        self.progreso.close()
        QMessageBox.critical(self, "Asistente IA", mensaje)

    def limpiar(self):
        self.btn_ejecutar.setEnabled(self.archivo is not None)
        self.hilo = None
        self.worker = None
        self.progreso = None

    def guardar_resultado(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar resultado", "resultado_ia.txt", "Texto (*.txt)")
        if ruta:
            try:
                Path(ruta).write_text(self.resultado.toPlainText(), encoding="utf-8")
            except OSError as error:
                QMessageBox.critical(self, "Guardar resultado", str(error))
