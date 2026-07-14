
from services.pipeline import Pipeline
from services.analysis_cache import AnalysisCache
from services.instance_store import InstanceStore
from services.analyzer_text import AnalyzerText
from services.extractor import Extractor
from services.translator import Translator
from services.translation_pdf import guardar_traduccion_pdf as exportar_traduccion_pdf
from services.document_manager import DocumentoDuplicadoError
from services.windows_scanner import ScannerCancelled, WindowsScanner
from send2trash import send2trash
from core.settings import Settings
from pathlib import Path
from datetime import datetime
import shutil

from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QAction,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
     QMainWindow,
     QWidget,
     QLabel,
     QListWidget,
     QListWidgetItem,
     QVBoxLayout,
     QHBoxLayout,
     QGroupBox,
     QPushButton,
     QFormLayout,
     QGridLayout,
     QFileDialog,
     QProgressDialog,
     QMessageBox,
     QPlainTextEdit,
     QComboBox,
     QTabWidget,
     QLineEdit,
     QMenu
)

import fitz


class AnalisisWorker(QObject):

    finalizado = Signal(dict)
    error = Signal(str)

    def __init__(self, pipeline, archivo):
        super().__init__()
        self.pipeline = pipeline
        self.archivo = archivo

    @Slot()
    def ejecutar(self):
        try:
            self.finalizado.emit(self.pipeline.procesar(self.archivo))
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class TranslationWorker(QObject):

    finalizado = Signal(str)
    error = Signal(str)

    def __init__(self, archivo, idioma_destino):
        super().__init__()
        self.archivo = archivo
        self.idioma_destino = idioma_destino

    @Slot()
    def ejecutar(self):
        try:
            traduccion = Translator().traducir(self.archivo, self.idioma_destino)
            self.finalizado.emit(traduccion)
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class ScannerWorker(QObject):

    finalizado = Signal(str)
    cancelado = Signal()
    error = Signal(str)

    @Slot()
    def ejecutar(self):
        try:
            self.finalizado.emit(str(WindowsScanner().scan_to_pdf()))
        except ScannerCancelled:
            self.cancelado.emit()
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class DateIndexWorker(QObject):

    progreso = Signal(int, int, str)
    finalizado = Signal(int)

    def __init__(self, archivos, ruta_cache):
        super().__init__()
        self.archivos = archivos
        self.ruta_cache = ruta_cache

    @Slot()
    def ejecutar(self):

        extractor = Extractor()
        analizador = AnalyzerText()
        cache = AnalysisCache(self.ruta_cache)
        extensiones = {".pdf", ".jpg", ".jpeg", ".png"}

        for indice, archivo in enumerate(self.archivos, start=1):
            fecha = "Sin fecha"
            if archivo.suffix.lower() in extensiones:
                try:
                    texto = extractor.extraer(archivo)
                    fecha = analizador.extraer_fecha(texto) or "Sin fecha"
                except Exception:
                    pass

            cache.guardar_fecha(archivo, fecha)
            self.progreso.emit(indice, len(self.archivos), archivo.name)

        self.finalizado.emit(len(self.archivos))


class PersonIndexWorker(QObject):

    progreso = Signal(int, int, str)
    finalizado = Signal(int)

    def __init__(self, archivos, ruta_cache):
        super().__init__()
        self.archivos = archivos
        self.ruta_cache = ruta_cache

    @Slot()
    def ejecutar(self):

        extractor = Extractor()
        analizador = AnalyzerText()
        cache = AnalysisCache(self.ruta_cache)
        extensiones = {".pdf", ".jpg", ".jpeg", ".png"}

        for indice, archivo in enumerate(self.archivos, start=1):
            persona = "Desconocido"
            if archivo.suffix.lower() in extensiones:
                try:
                    texto = extractor.extraer(archivo)
                    persona = analizador.extraer_destinatario(texto) or "Desconocido"
                except Exception:
                    pass

            cache.guardar_persona(archivo, persona)
            self.progreso.emit(indice, len(self.archivos), archivo.name)

        self.finalizado.emit(len(self.archivos))



class EntradaWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Victor Document AI - Entrada")
        self.resize(1600, 900)
        self.setMinimumSize(1250, 750)
        self.settings = Settings()
        self.ruta_entrada = self.settings.origen
        self.ruta_destino = self.settings.destino
        self.hilo_analisis = None
        self.worker_analisis = None
        self.progreso_analisis = None
        self.resultado_actual = None
        self.destino_manual = False
        self.destino_personalizado = False
        self.archivo_actual = None
        self.hilo_traduccion = None
        self.worker_traduccion = None
        self.progreso_traduccion = None
        self.hilo_escaneo = None
        self.worker_escaneo = None
        self.progreso_escaneo = None
        self.traduccion_actual = ""
        self.idioma_traduccion_actual = "español"
        self.pixmap_vista_previa = None
        self.cache_analisis = AnalysisCache()
        self.catalogo_instancias = InstanceStore()
        self.documentos = []
        self.hilo_indexado = None
        self.worker_indexado = None
        self.progreso_indexado = None
        self.hilo_personas = None
        self.worker_personas = None
        self.progreso_personas = None

        central=QWidget()
        self.setCentralWidget(central)

        principal=QVBoxLayout(central)

        titulo=QLabel("📥 Bandeja de Entrada")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:28px;font-weight:bold;")
        principal.addWidget(titulo)

        cuerpo=QHBoxLayout()
        principal.addLayout(cuerpo)

        panel_archivos=QWidget()
        panel_archivos.setMinimumWidth(240)
        panel_archivos.setMaximumWidth(320)
        izquierda=QVBoxLayout(panel_archivos)
        cuerpo.addWidget(panel_archivos)

        self.lista=QListWidget()
        self.lista.currentItemChanged.connect(self.documento_seleccionado)
        self.lista.itemDoubleClicked.connect(self.abrir_documento)
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self.mostrar_menu_archivo)
        self.filtro_fecha=QComboBox()
        self.filtro_fecha.currentIndexChanged.connect(self.mostrar_documentos_filtrados)
        self.filtro_persona=QComboBox()
        self.filtro_persona.currentIndexChanged.connect(self.mostrar_documentos_filtrados)
        izquierda.addWidget(QLabel("Organizar por fecha"))
        izquierda.addWidget(self.filtro_fecha)
        izquierda.addWidget(QLabel("Organizar por persona"))
        izquierda.addWidget(self.filtro_persona)
        izquierda.addWidget(self.lista, 1)

        panel_previa=QWidget()
        previa_columna=QVBoxLayout(panel_previa)
        cuerpo.addWidget(panel_previa, 2)
        vista_previa=QGroupBox("Vista previa")
        vista_layout=QVBoxLayout()
        self.lbl_vista_previa=QLabel("Selecciona un PDF o una imagen para ver su primera página.")
        self.lbl_vista_previa.setAlignment(Qt.AlignCenter)
        self.lbl_vista_previa.setWordWrap(True)
        self.lbl_vista_previa.setMinimumHeight(420)
        vista_layout.addWidget(self.lbl_vista_previa, 1)
        vista_previa.setLayout(vista_layout)
        previa_columna.addWidget(vista_previa, 1)

        derecha=QVBoxLayout()
        cuerpo.addLayout(derecha,3)

        info=QGroupBox("Información del documento")
        form=QFormLayout()
        self.lbl_nombre=QLabel("-")
        self.lbl_ruta=QLabel("-")
        self.lbl_tamano=QLabel("-")
        self.lbl_fecha=QLabel("-")
        self.txt_nombre_guardar=QLineEdit()
        self.txt_nombre_guardar.setPlaceholderText("Nombre con el que se guardará el documento")
        form.addRow("Nombre:",self.lbl_nombre)
        form.addRow("Ruta:",self.lbl_ruta)
        form.addRow("Tamaño:",self.lbl_tamano)
        form.addRow("Fecha:",self.lbl_fecha)
        form.addRow("Guardar como:",self.txt_nombre_guardar)
        info.setLayout(form)
        derecha.addWidget(info)

        ia=QGroupBox("🤖 IA")
        iaform=QFormLayout()
        self.lbl_tipo=QLabel("Sin analizar")
        self.lbl_empresa=QLabel("-")
        self.lbl_persona=QLabel("-")
        self.lbl_fecha_documento=QLabel("-")
        self.lbl_confianza=QLabel("-")
        self.lbl_destino=QLabel("-")
        iaform.addRow("Categoría:",self.lbl_tipo)
        iaform.addRow("Empresa:",self.lbl_empresa)
        iaform.addRow("Persona:",self.lbl_persona)
        iaform.addRow("Fecha carta:",self.lbl_fecha_documento)
        iaform.addRow("Confianza:",self.lbl_confianza)
        iaform.addRow("Destino:",self.lbl_destino)
        ia.setLayout(iaform)
        derecha.addWidget(ia)

        destino_manual=QGroupBox("Revisar y guardar")
        destino_form=QFormLayout()
        self.cmb_persona=QComboBox()
        self.cmb_instancia_1=QComboBox()
        self.cmb_instancia_2=QComboBox()
        self.cmb_instancia_3=QComboBox()
        self.cmb_ano=QComboBox()
        for campo in (
            self.cmb_persona,
            self.cmb_instancia_1,
            self.cmb_instancia_2,
            self.cmb_instancia_3,
        ):
            campo.setEditable(True)
            campo.setInsertPolicy(QComboBox.NoInsert)
            campo.currentTextChanged.connect(self.actualizar_destino_manual)
        self.cmb_persona.currentTextChanged.connect(self.cambiar_persona_guardado)
        self.cmb_instancia_1.currentTextChanged.connect(self.cambiar_instancia_1)
        self.cmb_instancia_2.currentTextChanged.connect(self.cambiar_instancia_2)
        self.cmb_ano.currentTextChanged.connect(self.actualizar_destino_manual)
        self.lbl_destino_manual=QLabel("Selecciona persona, instancia y año.")
        self.lbl_destino_manual.setWordWrap(True)
        destino_form.addRow("Persona:", self.cmb_persona)
        destino_form.addRow("Instancia 1:", self.cmb_instancia_1)
        destino_form.addRow("Instancia 2:", self.cmb_instancia_2)
        destino_form.addRow("Instancia 3:", self.cmb_instancia_3)
        destino_form.addRow("Año:", self.cmb_ano)
        destino_form.addRow("Ruta final:", self.lbl_destino_manual)
        destino_manual.setLayout(destino_form)
        derecha.addWidget(destino_manual)

        contenido_texto=QTabWidget()

        texto_ocr=QWidget()
        texto_layout=QVBoxLayout()
        self.txt_resultado=QPlainTextEdit()
        self.txt_resultado.setReadOnly(True)
        self.txt_resultado.setPlaceholderText("El texto del documento aparecerá aquí tras analizarlo.")
        self.txt_resultado.setMinimumHeight(180)
        texto_layout.addWidget(self.txt_resultado)
        texto_ocr.setLayout(texto_layout)
        contenido_texto.addTab(texto_ocr, "Texto OCR")

        traduccion=QWidget()
        traduccion_layout=QVBoxLayout()
        self.txt_traduccion=QPlainTextEdit()
        self.txt_traduccion.setReadOnly(True)
        self.txt_traduccion.setPlaceholderText("La traducción aparecerá aquí.")
        self.txt_traduccion.setMinimumHeight(180)
        traduccion_layout.addWidget(self.txt_traduccion)
        self.idioma_destino=QComboBox()
        self.idioma_destino.addItems(["español", "holandés", "inglés", "francés"])
        self.btn_traducir=QPushButton("Traducir documento")
        self.btn_guardar_traduccion=QPushButton("Guardar traducción en PDF")
        self.btn_guardar_traduccion.setEnabled(False)
        self.btn_traducir.clicked.connect(self.traducir_documento)
        self.btn_guardar_traduccion.clicked.connect(self.guardar_traduccion_pdf)
        traduccion_layout.addWidget(self.idioma_destino)
        traduccion_layout.addWidget(self.btn_traducir)
        traduccion_layout.addWidget(self.btn_guardar_traduccion)
        traduccion.setLayout(traduccion_layout)
        contenido_texto.addTab(traduccion, "Traducción")
        derecha.addWidget(contenido_texto, 1)

        self.btn_analizar=QPushButton("🤖 Analizar")
        self.btn_aceptar=QPushButton("✔ Guardar y siguiente")
        self.btn_elegir_destino=QPushButton("📍 Elegir destino del documento")
        self.btn_indexar_fechas=QPushButton("📅 Indexar fechas pendientes")
        self.btn_indexar_personas=QPushButton("👤 Indexar personas pendientes")
        self.btn_escanear=QPushButton("📠 Escanear a PDF…")
        self.pipeline = Pipeline()
        self.btn_elegir_destino.clicked.connect(self.elegir_destino_documento)
        self.btn_indexar_fechas.clicked.connect(self.indexar_fechas_pendientes)
        self.btn_indexar_personas.clicked.connect(self.indexar_personas_pendientes)
        self.btn_escanear.clicked.connect(self.escanear_a_pdf)
        self.btn_analizar.clicked.connect(self.analizar_documento)
        self.btn_aceptar.clicked.connect(self.aceptar_documento)
        self.atajo_guardar_enter = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.atajo_guardar_enter.setContext(Qt.WidgetWithChildrenShortcut)
        self.atajo_guardar_enter.activated.connect(self.guardar_y_siguiente_con_enter)
        self.atajo_guardar_numerico = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.atajo_guardar_numerico.setContext(Qt.WidgetWithChildrenShortcut)
        self.atajo_guardar_numerico.activated.connect(self.guardar_y_siguiente_con_enter)

        acciones=QGroupBox("Acciones")
        acciones_layout=QGridLayout()
        acciones_layout.addWidget(self.btn_escanear, 0, 0, 1, 2)
        acciones_layout.addWidget(self.btn_indexar_fechas, 1, 0)
        acciones_layout.addWidget(self.btn_indexar_personas, 1, 1)
        acciones_layout.addWidget(self.btn_elegir_destino, 2, 0, 1, 2)
        acciones_layout.addWidget(self.btn_analizar, 3, 0)
        acciones_layout.addWidget(self.btn_aceptar, 3, 1)
        acciones.setLayout(acciones_layout)
        previa_columna.addWidget(acciones)

        self.actualizar_listas_guardado()

        self.cargar_documentos()
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def cargar_documentos(self):
        print("Ruta actual:", self.ruta_entrada)
        print("Existe:", self.ruta_entrada.exists())

        if not self.ruta_entrada.exists():
            self.documentos = []
            self.lista.clear()
            self.lista.addItem("La carpeta D:\\Entrada no existe.")
            return

        self.documentos = sorted(
            (archivo for archivo in self.ruta_entrada.iterdir() if archivo.is_file()),
            key=lambda archivo: archivo.name.lower(),
        )
        self.actualizar_filtro_fecha()
        self.actualizar_filtro_persona()
        self.mostrar_documentos_filtrados()

    def actualizar_filtro_fecha(self):

        seleccion = self.filtro_fecha.currentData()
        grupos = {}
        pendientes = 0

        for archivo in self.documentos:
            fecha = self.cache_analisis.obtener_fecha(archivo)
            if not fecha or fecha == "Sin fecha":
                pendientes += 1
                continue
            grupos.setdefault(fecha[:7], 0)
            grupos[fecha[:7]] += 1

        self.filtro_fecha.blockSignals(True)
        self.filtro_fecha.clear()
        self.filtro_fecha.addItem(f"Todos ({len(self.documentos)})", "todos")
        self.filtro_fecha.addItem(f"Pendientes por fecha ({pendientes})", "pendientes")

        for fecha, total in sorted(grupos.items(), reverse=True):
            ano, mes = fecha.split("-")
            self.filtro_fecha.addItem(
                f"{self.nombre_mes(int(mes))} {ano} ({total})",
                fecha,
            )

        indice = self.filtro_fecha.findData(seleccion)
        self.filtro_fecha.setCurrentIndex(indice if indice >= 0 else 0)
        self.filtro_fecha.blockSignals(False)

    def mostrar_documentos_filtrados(self):

        filtro_fecha = self.filtro_fecha.currentData() or "todos"
        filtro_persona = self.filtro_persona.currentData() or "todas"
        self.lista.clear()

        for archivo in self.documentos:
            fecha = self.cache_analisis.obtener_fecha(archivo)
            persona = self.cache_analisis.obtener_persona(archivo)

            if filtro_fecha == "pendientes" and fecha and fecha != "Sin fecha":
                continue
            if filtro_fecha not in {"todos", "pendientes"}:
                if not fecha or not fecha.startswith(filtro_fecha):
                    continue
            if filtro_persona != "todas" and persona != filtro_persona:
                continue

            item = QListWidgetItem("📄 " + archivo.name)
            item.setData(Qt.UserRole, str(archivo))
            self.lista.addItem(item)

    def actualizar_filtro_persona(self):

        seleccion = self.filtro_persona.currentData()
        totales = {}
        desconocidos = 0

        for archivo in self.documentos:
            persona = self.cache_analisis.obtener_persona(archivo)
            if not persona:
                continue
            if persona == "Desconocido":
                desconocidos += 1
            else:
                totales[persona] = totales.get(persona, 0) + 1

        self.filtro_persona.blockSignals(True)
        self.filtro_persona.clear()
        self.filtro_persona.addItem("Todas las personas", "todas")
        for persona in sorted(totales, key=str.lower):
            self.filtro_persona.addItem(f"{persona} ({totales[persona]})", persona)
        self.filtro_persona.addItem(f"Desconocido ({desconocidos})", "Desconocido")

        indice = self.filtro_persona.findData(seleccion)
        self.filtro_persona.setCurrentIndex(indice if indice >= 0 else 0)
        self.filtro_persona.blockSignals(False)

    @staticmethod
    def nombre_mes(mes):

        return (
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        )[mes - 1]

    def actualizar_listas_guardado(self):

        persona_actual = self.cmb_persona.currentText()
        instancia_actual = self.cmb_instancia_1.currentText()
        ano_actual = self.cmb_ano.currentText()
        raiz_personas = self.settings.destino / "Personas"
        personas = []
        if not self.catalogo_instancias.listar():
            self.catalogo_instancias.importar_desde_personas(raiz_personas)
        instancias = self.catalogo_instancias.listar()

        try:
            carpetas_persona = [
                carpeta for carpeta in raiz_personas.iterdir() if carpeta.is_dir()
            ]
            personas = sorted((carpeta.name for carpeta in carpetas_persona), key=str.lower)
        except OSError:
            pass

        self._cargar_combo(self.cmb_persona, personas, persona_actual)
        self._cargar_combo(self.cmb_instancia_1, instancias, instancia_actual)
        anos = [str(ano) for ano in range(max(datetime.now().year, 2026), 2015, -1)]
        self._cargar_combo(self.cmb_ano, anos, ano_actual)
        self.actualizar_instancias_anidadas()

    @staticmethod
    def _cargar_combo(combo, valores, valor_actual):

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        combo.addItems(valores)
        combo.setCurrentText(valor_actual)
        combo.blockSignals(False)

    def actualizar_destino_manual(self):

        persona = self.cmb_persona.currentText().strip()
        instancias = [
            self.cmb_instancia_1.currentText().strip(),
            self.cmb_instancia_2.currentText().strip(),
            self.cmb_instancia_3.currentText().strip(),
        ]
        ano = self.cmb_ano.currentText().strip()

        if not (persona and instancias[0] and ano):
            self.lbl_destino_manual.setText("Selecciona persona, instancia y año.")
            return

        destino = self.settings.destino / "Personas" / persona
        for instancia in instancias:
            if instancia:
                destino /= instancia
        destino /= ano
        self.lbl_destino_manual.setText(str(destino))
        self.lbl_destino.setText(str(destino))
        self.destino_manual = True
        self.destino_personalizado = False

    def destino_manual_seleccionado(self):

        persona = self.cmb_persona.currentText().strip()
        instancias = [
            self.cmb_instancia_1.currentText().strip(),
            self.cmb_instancia_2.currentText().strip(),
            self.cmb_instancia_3.currentText().strip(),
        ]
        ano = self.cmb_ano.currentText().strip()
        if not (persona and instancias[0] and ano):
            return None

        destino = self.settings.destino / "Personas" / persona
        for instancia in instancias:
            if instancia:
                destino /= instancia
        return destino / ano

    def actualizar_instancias_anidadas(self):

        persona = self.cmb_persona.currentText().strip()
        instancia_1 = self.cmb_instancia_1.currentText().strip()
        instancia_2 = self.cmb_instancia_2.currentText().strip()
        actual_2 = self.cmb_instancia_2.currentText()
        actual_3 = self.cmb_instancia_3.currentText()

        opciones_2 = self.subcarpetas_instancia(persona, instancia_1)
        self._cargar_combo(self.cmb_instancia_2, opciones_2, actual_2)

        opciones_3 = self.subcarpetas_instancia(persona, instancia_1, instancia_2)
        self._cargar_combo(self.cmb_instancia_3, opciones_3, actual_3)

    def cambiar_persona_guardado(self):

        persona = self.cmb_persona.currentText().strip()
        instancia_1 = self.cmb_instancia_1.currentText().strip()
        opciones_2 = self.subcarpetas_instancia(persona, instancia_1)
        self._cargar_combo(self.cmb_instancia_2, opciones_2, "")
        self._cargar_combo(self.cmb_instancia_3, [], "")
        self.actualizar_destino_manual()

    def cambiar_instancia_1(self):

        persona = self.cmb_persona.currentText().strip()
        instancia_1 = self.cmb_instancia_1.currentText().strip()
        opciones_2 = self.subcarpetas_instancia(persona, instancia_1)
        self._cargar_combo(self.cmb_instancia_2, opciones_2, "")
        self._cargar_combo(self.cmb_instancia_3, [], "")
        self.actualizar_destino_manual()

    def cambiar_instancia_2(self):

        persona = self.cmb_persona.currentText().strip()
        instancia_1 = self.cmb_instancia_1.currentText().strip()
        instancia_2 = self.cmb_instancia_2.currentText().strip()
        opciones_3 = self.subcarpetas_instancia(persona, instancia_1, instancia_2)
        self._cargar_combo(self.cmb_instancia_3, opciones_3, "")
        self.actualizar_destino_manual()

    def subcarpetas_instancia(self, persona, instancia_1, instancia_2=None):

        if not instancia_1:
            return []

        if instancia_2:
            return self.catalogo_instancias.hijos(instancia_1, instancia_2)
        return self.catalogo_instancias.hijos(instancia_1)

    def archivo_de_item(self, item):

        ruta = item.data(Qt.UserRole)
        if ruta:
            return Path(ruta)
        return self.ruta_entrada / item.text().replace("📄 ", "")


    def documento_seleccionado(self, actual, anterior):
        if actual is None:
            return
        archivo = self.archivo_de_item(actual)
        if not archivo.exists():
            return
        self.limpiar_resultado()
        self.lbl_nombre.setText(archivo.name)
        self.lbl_ruta.setText(str(archivo))
        self.lbl_tamano.setText(f"{round(archivo.stat().st_size/1024,1)} KB")
        self.lbl_fecha.setText(datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%d-%m-%Y %H:%M"))
        self.txt_nombre_guardar.setText(archivo.name)
        self.mostrar_vista_previa(archivo)
        self.archivo_actual = archivo

    def mostrar_vista_previa(self, archivo):

        try:
            if archivo.suffix.lower() == ".pdf":
                with fitz.open(archivo) as pdf:
                    pagina = pdf[0]
                    pix = pagina.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                    imagen = QImage(
                        pix.samples,
                        pix.width,
                        pix.height,
                        pix.stride,
                        QImage.Format_RGB888,
                    ).copy()
                    vista = QPixmap.fromImage(imagen)
            else:
                vista = QPixmap(str(archivo))

            if vista.isNull():
                self.pixmap_vista_previa = None
                self.lbl_vista_previa.setPixmap(QPixmap())
                self.lbl_vista_previa.setText("No se puede generar una vista previa de este archivo.")
                return

            self.pixmap_vista_previa = vista
            self.lbl_vista_previa.setText("")
            self.actualizar_vista_previa()
        except (OSError, RuntimeError, ValueError):
            self.pixmap_vista_previa = None
            self.lbl_vista_previa.setPixmap(QPixmap())
            self.lbl_vista_previa.setText("No se puede generar una vista previa de este archivo.")

    def actualizar_vista_previa(self):

        if self.pixmap_vista_previa is None:
            return

        ancho = max(1, self.lbl_vista_previa.width() - 20)
        alto = max(1, self.lbl_vista_previa.height() - 20)
        self.lbl_vista_previa.setPixmap(self.pixmap_vista_previa.scaled(
            ancho,
            alto,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        ))

    def resizeEvent(self, event):

        super().resizeEvent(event)
        self.actualizar_vista_previa()

    def abrir_documento(self, item):

        archivo = self.archivo_de_item(item)

        if not archivo.is_file():
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(archivo))):
            QMessageBox.warning(
                self,
                "No se pudo abrir",
                "Windows no pudo abrir el documento seleccionado.",
            )

    def mostrar_menu_archivo(self, posicion):

        item = self.lista.itemAt(posicion)
        if item is None:
            return

        archivo = self.archivo_de_item(item)
        if not archivo.is_file():
            return

        menu = QMenu(self)
        accion_eliminar = QAction("Enviar a la Papelera", self)
        menu.addAction(accion_eliminar)
        accion = menu.exec(self.lista.mapToGlobal(posicion))

        if accion is accion_eliminar:
            self.eliminar_documento(archivo)

    def eliminar_documento(self, archivo):

        respuesta = QMessageBox.question(
            self,
            "Enviar a la Papelera",
            f"¿Quieres enviar este archivo a la Papelera?\n\n{archivo.name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return

        try:
            send2trash(str(archivo))
        except OSError:
            respuesta = QMessageBox.question(
                self,
                "Eliminación permanente",
                "El NAS no permite enviar este archivo a la Papelera. "
                "¿Quieres eliminarlo definitivamente?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if respuesta != QMessageBox.Yes:
                return
            try:
                archivo.unlink()
            except OSError as error:
                QMessageBox.critical(self, "No se pudo eliminar", str(error))
                return

        self.cargar_documentos()
        self.pixmap_vista_previa = None
        self.lbl_vista_previa.setPixmap(QPixmap())
        self.lbl_vista_previa.setText("Selecciona un PDF o una imagen para ver su primera página.")
        self.limpiar_resultado()

    def escanear_a_pdf(self):
        """Abre el selector WIA de Windows y permite guardar el PDF localmente."""
        if self.hilo_escaneo is not None:
            return
        self.progreso_escaneo = QProgressDialog(
            "Selecciona el escáner y realiza el escaneo en la ventana de Windows…",
            None,
            0,
            0,
            self,
        )
        self.progreso_escaneo.setWindowModality(Qt.WindowModal)
        self.progreso_escaneo.setCancelButton(None)
        self.progreso_escaneo.show()
        self.btn_escanear.setEnabled(False)
        self.hilo_escaneo = QThread(self)
        self.worker_escaneo = ScannerWorker()
        self.worker_escaneo.moveToThread(self.hilo_escaneo)
        self.hilo_escaneo.started.connect(self.worker_escaneo.ejecutar)
        self.worker_escaneo.finalizado.connect(self.guardar_pdf_escaneado)
        self.worker_escaneo.finalizado.connect(self.hilo_escaneo.quit)
        self.worker_escaneo.finalizado.connect(self.worker_escaneo.deleteLater)
        self.worker_escaneo.cancelado.connect(self.escaneo_cancelado)
        self.worker_escaneo.cancelado.connect(self.hilo_escaneo.quit)
        self.worker_escaneo.cancelado.connect(self.worker_escaneo.deleteLater)
        self.worker_escaneo.error.connect(self.error_escaneo)
        self.worker_escaneo.error.connect(self.hilo_escaneo.quit)
        self.worker_escaneo.error.connect(self.worker_escaneo.deleteLater)
        self.hilo_escaneo.finished.connect(self.hilo_escaneo.deleteLater)
        self.hilo_escaneo.finished.connect(self.limpiar_escaneo)
        self.hilo_escaneo.start()

    def guardar_pdf_escaneado(self, temporal):
        if self.progreso_escaneo is not None:
            self.progreso_escaneo.close()
        nombre = f"escaneo_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        ruta_inicial = str(Path.home() / "Documents" / nombre)
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar PDF escaneado",
            ruta_inicial,
            "Documento PDF (*.pdf)",
        )
        origen = Path(temporal)
        if not destino:
            origen.unlink(missing_ok=True)
            return
        destino = Path(destino)
        if destino.suffix.lower() != ".pdf":
            destino = destino.with_suffix(".pdf")
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
            origen.unlink(missing_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "Escanear a PDF", f"No se pudo guardar el PDF:\n{error}")
            return
        if destino.parent == self.ruta_entrada:
            self.cargar_documentos()
        QMessageBox.information(
            self,
            "Escanear a PDF",
            f"PDF guardado en:\n{destino}\n\nPuedes guardarlo localmente, en una memoria USB o en el NAS cuando quieras.",
        )

    def escaneo_cancelado(self):
        if self.progreso_escaneo is not None:
            self.progreso_escaneo.close()
        self.statusBar().showMessage("Escaneo cancelado.", 4000)

    def error_escaneo(self, mensaje):
        if self.progreso_escaneo is not None:
            self.progreso_escaneo.close()
        QMessageBox.critical(self, "Escanear a PDF", mensaje)

    def limpiar_escaneo(self):
        self.btn_escanear.setEnabled(True)
        self.hilo_escaneo = None
        self.worker_escaneo = None
        self.progreso_escaneo = None

    def indexar_fechas_pendientes(self):

        if self.hilo_indexado is not None or self.hilo_personas is not None:
            return

        archivos = [
            archivo for archivo in self.documentos
            if self.cache_analisis.obtener_fecha(archivo) in (None, "Sin fecha")
        ]
        if not archivos:
            QMessageBox.information(
                self,
                "Fechas indexadas",
                "No hay documentos pendientes de indexar.",
            )
            return

        self.progreso_indexado = QProgressDialog(
            "Preparando OCR de fechas...",
            None,
            0,
            len(archivos),
            self,
        )
        self.progreso_indexado.setWindowTitle("Indexando fechas")
        self.progreso_indexado.setWindowModality(Qt.WindowModal)
        self.progreso_indexado.setCancelButton(None)
        self.progreso_indexado.show()

        self.lista.setEnabled(False)
        self.btn_indexar_fechas.setEnabled(False)
        self.btn_analizar.setEnabled(False)
        self.btn_aceptar.setEnabled(False)

        self.hilo_indexado = QThread(self)
        self.worker_indexado = DateIndexWorker(archivos, self.cache_analisis.ruta)
        self.worker_indexado.moveToThread(self.hilo_indexado)
        self.hilo_indexado.started.connect(self.worker_indexado.ejecutar)
        self.worker_indexado.progreso.connect(self.actualizar_progreso_indexado)
        self.worker_indexado.finalizado.connect(self.finalizar_indexado)
        self.worker_indexado.finalizado.connect(self.hilo_indexado.quit)
        self.worker_indexado.finalizado.connect(self.worker_indexado.deleteLater)
        self.hilo_indexado.finished.connect(self.hilo_indexado.deleteLater)
        self.hilo_indexado.finished.connect(self.limpiar_indexado)
        self.hilo_indexado.start()

    def actualizar_progreso_indexado(self, actual, total, nombre):

        if self.progreso_indexado is not None:
            self.progreso_indexado.setMaximum(total)
            self.progreso_indexado.setValue(actual)
            self.progreso_indexado.setLabelText(
                f"Indexando {actual}/{total}: {nombre}"
            )

    def finalizar_indexado(self, total):

        if self.progreso_indexado is not None:
            self.progreso_indexado.close()

        self.cache_analisis = AnalysisCache()
        self.actualizar_filtro_fecha()
        self.mostrar_documentos_filtrados()
        QMessageBox.information(
            self,
            "Fechas indexadas",
            f"Se analizaron {total} documento(s). Ya puedes filtrar por año y mes.",
        )

    def limpiar_indexado(self):

        self.lista.setEnabled(True)
        self.btn_indexar_fechas.setEnabled(True)
        self.btn_analizar.setEnabled(True)
        self.btn_aceptar.setEnabled(True)
        self.hilo_indexado = None
        self.worker_indexado = None
        self.progreso_indexado = None

    def indexar_personas_pendientes(self):

        if self.hilo_personas is not None or self.hilo_indexado is not None:
            return

        archivos = [
            archivo for archivo in self.documentos
            if self.cache_analisis.obtener_persona(archivo) is None
        ]
        if not archivos:
            QMessageBox.information(
                self,
                "Personas indexadas",
                "No hay documentos pendientes de reconocer.",
            )
            return

        self.progreso_personas = QProgressDialog(
            "Preparando OCR de destinatarios...",
            None,
            0,
            len(archivos),
            self,
        )
        self.progreso_personas.setWindowTitle("Indexando personas")
        self.progreso_personas.setWindowModality(Qt.WindowModal)
        self.progreso_personas.setCancelButton(None)
        self.progreso_personas.show()

        self.lista.setEnabled(False)
        self.btn_indexar_personas.setEnabled(False)
        self.btn_indexar_fechas.setEnabled(False)
        self.btn_analizar.setEnabled(False)
        self.btn_aceptar.setEnabled(False)

        self.hilo_personas = QThread(self)
        self.worker_personas = PersonIndexWorker(
            archivos,
            self.cache_analisis.ruta,
        )
        self.worker_personas.moveToThread(self.hilo_personas)
        self.hilo_personas.started.connect(self.worker_personas.ejecutar)
        self.worker_personas.progreso.connect(self.actualizar_progreso_personas)
        self.worker_personas.finalizado.connect(self.finalizar_indexado_personas)
        self.worker_personas.finalizado.connect(self.hilo_personas.quit)
        self.worker_personas.finalizado.connect(self.worker_personas.deleteLater)
        self.hilo_personas.finished.connect(self.hilo_personas.deleteLater)
        self.hilo_personas.finished.connect(self.limpiar_indexado_personas)
        self.hilo_personas.start()

    def actualizar_progreso_personas(self, actual, total, nombre):

        if self.progreso_personas is not None:
            self.progreso_personas.setMaximum(total)
            self.progreso_personas.setValue(actual)
            self.progreso_personas.setLabelText(
                f"Buscando destinatario {actual}/{total}: {nombre}"
            )

    def finalizar_indexado_personas(self, total):

        if self.progreso_personas is not None:
            self.progreso_personas.close()

        self.cache_analisis = AnalysisCache()
        self.actualizar_filtro_fecha()
        self.actualizar_filtro_persona()
        self.mostrar_documentos_filtrados()
        QMessageBox.information(
            self,
            "Personas indexadas",
            f"Se revisaron {total} documento(s).",
        )

    def limpiar_indexado_personas(self):

        self.lista.setEnabled(True)
        self.btn_indexar_personas.setEnabled(True)
        self.btn_indexar_fechas.setEnabled(True)
        self.btn_analizar.setEnabled(True)
        self.btn_aceptar.setEnabled(True)
        self.hilo_personas = None
        self.worker_personas = None
        self.progreso_personas = None

    def analizar_documento(self):

        if self.hilo_analisis is not None:
            return

        item = self.lista.currentItem()

        if item is None:
            return

        archivo = self.archivo_de_item(item)

        self.progreso_analisis = QProgressDialog(
            "Analizando documento...",
            None,
            0,
            0,
            self
        )
        self.progreso_analisis.setWindowTitle("Analizando")
        self.progreso_analisis.setWindowModality(Qt.WindowModal)
        self.progreso_analisis.setCancelButton(None)
        self.progreso_analisis.show()

        self.lista.setEnabled(False)
        self.btn_analizar.setEnabled(False)
        self.btn_aceptar.setEnabled(False)
        self.btn_elegir_destino.setEnabled(False)

        self.hilo_analisis = QThread(self)
        self.worker_analisis = AnalisisWorker(self.pipeline, archivo)
        self.worker_analisis.moveToThread(self.hilo_analisis)

        self.hilo_analisis.started.connect(self.worker_analisis.ejecutar)
        self.worker_analisis.finalizado.connect(self.mostrar_resultado)
        self.worker_analisis.finalizado.connect(self.hilo_analisis.quit)
        self.worker_analisis.finalizado.connect(self.worker_analisis.deleteLater)
        self.worker_analisis.error.connect(self.mostrar_error_analisis)
        self.worker_analisis.error.connect(self.hilo_analisis.quit)
        self.worker_analisis.error.connect(self.worker_analisis.deleteLater)
        self.hilo_analisis.finished.connect(self.hilo_analisis.deleteLater)
        self.hilo_analisis.finished.connect(self.limpiar_analisis)
        self.hilo_analisis.start()

    def mostrar_resultado(self, resultado):

        if self.progreso_analisis is not None:
            self.progreso_analisis.close()

        self.lbl_tipo.setText(resultado["categoria"])
        self.lbl_empresa.setText(resultado["empresa"])
        self.lbl_persona.setText(resultado["persona"])
        self.lbl_fecha_documento.setText(resultado.get("fecha", "-"))
        self.lbl_confianza.setText(f"{resultado.get('confianza', 0)}%")
        self.lbl_destino.setText(resultado["destino"])
        self.txt_resultado.setPlainText(resultado.get("texto", ""))
        self.resultado_actual = resultado
        self.destino_manual = False
        self.destino_personalizado = False

        fecha = resultado.get("fecha")
        if self.archivo_actual is not None:
            self.cache_analisis.guardar_fecha(self.archivo_actual, fecha or "Sin fecha")
            persona = resultado.get("persona")
            self.cache_analisis.guardar_persona(
                self.archivo_actual,
                persona if persona and persona != "Destinatario no identificado" else "Desconocido",
            )
            self.actualizar_filtro_fecha()
            self.actualizar_filtro_persona()

        persona = resultado.get("persona")
        instancia = resultado.get("empresa")
        instancia_1_aprendida = resultado.get("instancia_1")
        if persona and persona != "Destinatario no identificado":
            self.cmb_persona.setCurrentText(persona)
        if instancia_1_aprendida:
            self.cmb_instancia_1.setCurrentText(instancia_1_aprendida)
            self.cmb_instancia_2.setCurrentText(resultado.get("instancia_2", ""))
            self.cmb_instancia_3.setCurrentText(resultado.get("instancia_3", ""))
        elif instancia and instancia != "Entidad no identificada":
            self.cmb_instancia_1.setCurrentText(instancia)
            self.cmb_instancia_2.setCurrentText("")
            self.cmb_instancia_3.setCurrentText("")
        if fecha and fecha != "Sin fecha":
            self.cmb_ano.setCurrentText(fecha[:4])
        self.actualizar_destino_manual()

        if fecha and fecha != "Sin fecha" and self.archivo_actual is not None:
            self.txt_nombre_guardar.setText(
                f"{fecha}_{self.archivo_actual.stem}{self.archivo_actual.suffix}"
            )

    def mostrar_error_analisis(self, mensaje):

        if self.progreso_analisis is not None:
            self.progreso_analisis.close()

        QMessageBox.critical(self, "Error al analizar", mensaje)

    def limpiar_analisis(self):

        self.lista.setEnabled(True)
        self.btn_analizar.setEnabled(True)
        self.btn_aceptar.setEnabled(True)
        self.btn_elegir_destino.setEnabled(True)
        self.hilo_analisis = None
        self.worker_analisis = None
        self.progreso_analisis = None

    def limpiar_resultado(self):

        self.lbl_tipo.setText("Sin analizar")
        self.lbl_empresa.setText("-")
        self.lbl_persona.setText("-")
        self.lbl_fecha_documento.setText("-")
        self.lbl_confianza.setText("-")
        self.lbl_destino.setText("-")
        self.txt_resultado.clear()
        self.txt_nombre_guardar.clear()
        self.resultado_actual = None
        self.destino_manual = False
        self.destino_personalizado = False
        self.cmb_persona.setCurrentText("")
        self.cmb_instancia_1.setCurrentText("")
        self.cmb_instancia_2.setCurrentText("")
        self.cmb_instancia_3.setCurrentText("")
        self.cmb_ano.setCurrentText("")
        self.lbl_destino_manual.setText("Selecciona persona, instancia y año.")
        self.traduccion_actual = ""
        self.txt_traduccion.clear()
        self.btn_guardar_traduccion.setEnabled(False)


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

    def elegir_destino_documento(self):

        carpeta = QFileDialog.getExistingDirectory(
            self,
            "Elegir dónde guardar este documento",
            str(self.ruta_destino),
        )
        if not carpeta:
            return False

        self.lbl_destino.setText(carpeta)
        self.destino_manual = True
        self.destino_personalizado = True
        return True

    def traducir_documento(self):

        if self.archivo_actual is None or self.hilo_traduccion is not None:
            return

        self.progreso_traduccion = QProgressDialog(
            "Traduciendo el documento original...",
            None,
            0,
            0,
            self,
        )
        self.progreso_traduccion.setWindowTitle("Traduciendo")
        self.progreso_traduccion.setWindowModality(Qt.WindowModal)
        self.progreso_traduccion.setCancelButton(None)
        self.progreso_traduccion.show()
        self.btn_traducir.setEnabled(False)
        self.idioma_destino.setEnabled(False)
        self.lista.setEnabled(False)

        self.hilo_traduccion = QThread(self)
        self.idioma_traduccion_actual = self.idioma_destino.currentText()
        self.worker_traduccion = TranslationWorker(
            self.archivo_actual,
            self.idioma_traduccion_actual,
        )
        self.worker_traduccion.moveToThread(self.hilo_traduccion)
        self.hilo_traduccion.started.connect(self.worker_traduccion.ejecutar)
        self.worker_traduccion.finalizado.connect(self.mostrar_traduccion)
        self.worker_traduccion.finalizado.connect(self.hilo_traduccion.quit)
        self.worker_traduccion.finalizado.connect(self.worker_traduccion.deleteLater)
        self.worker_traduccion.error.connect(self.mostrar_error_traduccion)
        self.worker_traduccion.error.connect(self.hilo_traduccion.quit)
        self.worker_traduccion.error.connect(self.worker_traduccion.deleteLater)
        self.hilo_traduccion.finished.connect(self.hilo_traduccion.deleteLater)
        self.hilo_traduccion.finished.connect(self.limpiar_traduccion)
        self.hilo_traduccion.start()

    def mostrar_traduccion(self, traduccion):

        if self.progreso_traduccion is not None:
            self.progreso_traduccion.close()

        self.traduccion_actual = traduccion
        self.txt_traduccion.setPlainText(traduccion)
        self.btn_guardar_traduccion.setEnabled(True)

    def mostrar_error_traduccion(self, mensaje):

        if self.progreso_traduccion is not None:
            self.progreso_traduccion.close()

        QMessageBox.critical(self, "Error al traducir", mensaje)

    def limpiar_traduccion(self):

        self.btn_traducir.setEnabled(True)
        self.idioma_destino.setEnabled(True)
        self.lista.setEnabled(True)
        self.hilo_traduccion = None
        self.worker_traduccion = None
        self.progreso_traduccion = None

    def guardar_traduccion_pdf(self):

        if not self.traduccion_actual:
            return

        nombre = f"traduccion_{self.archivo_actual.stem}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar traducción",
            str(self.ruta_destino / nombre),
            "Archivos PDF (*.pdf)",
        )
        if not ruta:
            return

        exportar_traduccion_pdf(
            ruta,
            self.archivo_actual.name,
            self.idioma_traduccion_actual,
            self.traduccion_actual,
        )
        QMessageBox.information(self, "Traducción guardada", "El PDF está listo para imprimir.")

    def aceptar_documento(self):

        item = self.lista.currentItem()

        if item is None:
            return

        archivo = self.archivo_de_item(item)

        destino_estandar = self.destino_manual_seleccionado()
        if destino_estandar is not None and not self.destino_personalizado:
            destino = str(destino_estandar)
            self.lbl_destino.setText(destino)
            self.destino_manual = True
        else:
            destino = self.lbl_destino.text()

        if destino == "-" or destino == "":
            if not self.elegir_destino_documento():
                return
            destino = self.lbl_destino.text()

        nombre = self.txt_nombre_guardar.text().strip() or archivo.name

        try:
            self.pipeline.aceptar(
                archivo,
                destino,
                self.ruta_destino,
                nombre,
            )
        except DocumentoDuplicadoError as error:
            QMessageBox.information(
                self,
                "Documento duplicado",
                "No se guardó una segunda copia porque ya existe un documento idéntico en esta ruta:\n\n"
                f"{error.existente}",
            )
            return

        if self.destino_manual and self.resultado_actual is not None:
            self.pipeline.aprender_destino(
                self.resultado_actual,
                destino,
                self.cmb_persona.currentText(),
                {
                    "instancia_1": self.cmb_instancia_1.currentText(),
                    "instancia_2": self.cmb_instancia_2.currentText(),
                    "instancia_3": self.cmb_instancia_3.currentText(),
                },
            )

        if destino_estandar is not None and not self.destino_personalizado:
            self.catalogo_instancias.agregar_ruta(
                self.cmb_instancia_1.currentText(),
                self.cmb_instancia_2.currentText(),
                self.cmb_instancia_3.currentText(),
            )
            self.actualizar_listas_guardado()
    

        self.cargar_documentos()

        if self.lista.count():
            self.lista.setCurrentRow(0)

        self.limpiar_resultado()

    def guardar_y_siguiente_con_enter(self):

        if self.btn_aceptar.isEnabled() and self.hilo_analisis is None:
            self.aceptar_documento()
