import re
import mimetypes
import shutil
import tempfile
import unicodedata
import uuid
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import fitz
from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaRecorder,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QInputDialog,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from services.document_catalog import DocumentCatalog
from services.instance_store import InstanceStore
from services.voice_search import VoiceSearch


class VozWorker(QObject):
    finalizado = Signal(str)
    error = Signal(str)

    def __init__(self, archivo_audio):
        super().__init__()
        self.archivo_audio = archivo_audio

    @Slot()
    def ejecutar(self):
        try:
            self.finalizado.emit(VoiceSearch().transcribir(self.archivo_audio))
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class BuscarWindow(QMainWindow):

    MESES = (
        ("Todos los meses", ""),
        ("Enero", "01"), ("Febrero", "02"), ("Marzo", "03"),
        ("Abril", "04"), ("Mayo", "05"), ("Junio", "06"),
        ("Julio", "07"), ("Agosto", "08"), ("Septiembre", "09"),
        ("Octubre", "10"), ("Noviembre", "11"), ("Diciembre", "12"),
    )
    MESES_VOZ = {
        "01": ("enero", "januari", "january"),
        "02": ("febrero", "februari", "february"),
        "03": ("marzo", "maart", "march"),
        "04": ("abril", "april"),
        "05": ("mayo", "mei", "may"),
        "06": ("junio", "juni", "june"),
        "07": ("julio", "juli", "july"),
        "08": ("agosto", "augustus", "august"),
        "09": ("septiembre", "september"),
        "10": ("octubre", "oktober", "october"),
        "11": ("noviembre", "november"),
        "12": ("diciembre", "december"),
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Buscar documentos")
        self.resize(1500, 850)
        self.setMinimumSize(1100, 650)
        self.settings = Settings()
        self.raiz_personas = self.settings.destino / "Personas"
        self.documentos_catalogo = DocumentCatalog()
        self.hilo_voz = None
        self.archivo_voz = None
        self.esperando_audio = False
        self.catalogo = InstanceStore()
        if not self.catalogo.listar():
            self.catalogo.importar_desde_personas(self.raiz_personas)

        central = QWidget()
        self.setCentralWidget(central)
        principal = QVBoxLayout(central)

        titulo = QLabel("Buscar documentos")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 26px; font-weight: bold;")
        principal.addWidget(titulo)

        filtros = QGroupBox("Filtros")
        formulario = QFormLayout(filtros)
        self.cmb_persona = QComboBox()
        self.cmb_instancia_1 = QComboBox()
        self.cmb_instancia_2 = QComboBox()
        self.cmb_instancia_3 = QComboBox()
        self.cmb_ano = QComboBox()
        self.cmb_microfono = QComboBox()
        self.cargar_microfonos()
        self.btn_meses = QToolButton()
        self.btn_meses.setPopupMode(QToolButton.InstantPopup)
        self.menu_meses = QMenu(self)
        self.acciones_mes = []
        for nombre, valor in self.MESES[1:]:
            accion = QAction(nombre, self, checkable=True)
            accion.setData(valor)
            accion.toggled.connect(self.actualizar_etiqueta_meses)
            self.menu_meses.addAction(accion)
            self.acciones_mes.append(accion)
        self.btn_meses.setMenu(self.menu_meses)
        self.actualizar_etiqueta_meses()
        self.btn_buscar = QPushButton("Buscar")
        self.btn_limpiar = QPushButton("Limpiar filtros")
        self.btn_voz = QPushButton("🎤 Buscar por voz")
        if not self.dispositivos_audio:
            self.btn_voz.setEnabled(False)
        self.btn_buscar.clicked.connect(self.buscar)
        self.btn_limpiar.clicked.connect(self.limpiar_filtros)
        self.btn_voz.clicked.connect(self.grabar_voz)
        self.cmb_instancia_1.currentTextChanged.connect(self.cambiar_instancia_1)
        self.cmb_instancia_2.currentTextChanged.connect(self.cambiar_instancia_2)
        formulario.addRow("Persona:", self.cmb_persona)
        formulario.addRow("Instancia:", self.cmb_instancia_1)
        formulario.addRow("Subinstancia:", self.cmb_instancia_2)
        formulario.addRow("Sub/subinstancia:", self.cmb_instancia_3)
        formulario.addRow("Año:", self.cmb_ano)
        formulario.addRow("Meses:", self.btn_meses)
        formulario.addRow("Micrófono:", self.cmb_microfono)
        botones = QHBoxLayout()
        botones.addWidget(self.btn_buscar)
        botones.addWidget(self.btn_limpiar)
        botones.addWidget(self.btn_voz)
        formulario.addRow(botones)
        principal.addWidget(filtros)

        divisor = QSplitter(Qt.Horizontal)
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Email", "Fecha", "Persona", "Instancias", "Documento"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.itemSelectionChanged.connect(self.actualizar_vista_previa)
        self.tabla.cellDoubleClicked.connect(self.abrir_documento)
        divisor.addWidget(self.tabla)

        previa = QGroupBox("Vista previa")
        previa_layout = QVBoxLayout(previa)
        self.lbl_vista_previa = QLabel("Selecciona un documento de los resultados.")
        self.lbl_vista_previa.setAlignment(Qt.AlignCenter)
        self.lbl_vista_previa.setWordWrap(True)
        previa_layout.addWidget(self.lbl_vista_previa)
        acciones = QHBoxLayout()
        self.btn_guardar_copia = QPushButton("Guardar una copia")
        self.btn_imprimir = QPushButton("Imprimir")
        self.btn_correo = QPushButton("Preparar email")
        self.btn_guardar_copia.clicked.connect(self.guardar_copia)
        self.btn_imprimir.clicked.connect(self.imprimir_documento)
        self.btn_correo.clicked.connect(self.preparar_correo)
        for boton in (self.btn_guardar_copia, self.btn_imprimir, self.btn_correo):
            boton.setEnabled(False)
            acciones.addWidget(boton)
        previa_layout.addLayout(acciones)
        divisor.addWidget(previa)
        divisor.setSizes([900, 600])
        principal.addWidget(divisor, 1)

        self.lbl_estado = QLabel("Elige los filtros y pulsa Buscar.")
        principal.addWidget(self.lbl_estado)
        self.cargar_filtros()

    @staticmethod
    def cargar_combo(combo, valores, etiqueta_todos="Todos"):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(etiqueta_todos, "")
        for valor in valores:
            combo.addItem(valor, valor)
        combo.blockSignals(False)

    def cargar_filtros(self):
        personas = self.documentos_catalogo.personas(self.raiz_personas)
        self.cargar_combo(self.cmb_persona, personas, "Todas las personas")
        self.cargar_combo(self.cmb_instancia_1, self.catalogo.listar(), "Todas las instancias")
        self.cargar_combo(self.cmb_instancia_2, [], "Todas las subinstancias")
        self.cargar_combo(self.cmb_instancia_3, [], "Todas las sub/subinstancias")
        anos = [str(ano) for ano in range(datetime.now().year, 2015, -1)]
        self.cargar_combo(self.cmb_ano, anos, "Todos los años")
        self.actualizar_etiqueta_meses()
        if self.documentos_catalogo.tiene_indice(self.raiz_personas):
            self.lbl_estado.setText("Elige los filtros y pulsa Buscar.")
        else:
            self.lbl_estado.setText(
                "El catálogo todavía no está completo. Abre Dashboard y pulsa "
                "“Indexar/actualizar NAS”."
            )

    def cambiar_instancia_1(self):
        instancia = self.cmb_instancia_1.currentData() or ""
        self.cargar_combo(
            self.cmb_instancia_2,
            self.catalogo.hijos(instancia),
            "Todas las subinstancias",
        )
        self.cargar_combo(self.cmb_instancia_3, [], "Todas las sub/subinstancias")

    def cambiar_instancia_2(self):
        instancia = self.cmb_instancia_1.currentData() or ""
        subinstancia = self.cmb_instancia_2.currentData() or ""
        self.cargar_combo(
            self.cmb_instancia_3,
            self.catalogo.hijos(instancia, subinstancia),
            "Todas las sub/subinstancias",
        )

    def limpiar_filtros(self):
        for combo in (
            self.cmb_persona,
            self.cmb_instancia_1,
            self.cmb_instancia_2,
            self.cmb_instancia_3,
            self.cmb_ano,
        ):
            combo.setCurrentIndex(0)
        for accion in self.acciones_mes:
            accion.blockSignals(True)
            accion.setChecked(False)
            accion.blockSignals(False)
        self.actualizar_etiqueta_meses()
        self.tabla.setRowCount(0)
        self.lbl_vista_previa.setPixmap(QPixmap())
        self.lbl_vista_previa.setText("Selecciona un documento de los resultados.")
        self.lbl_estado.setText("Filtros limpiados.")
        self.actualizar_botones_documento()

    def buscar(self):
        filtros = {
            "persona": self.cmb_persona.currentData() or "",
            "instancia_1": self.cmb_instancia_1.currentData() or "",
            "instancia_2": self.cmb_instancia_2.currentData() or "",
            "instancia_3": self.cmb_instancia_3.currentData() or "",
            "ano": self.cmb_ano.currentData() or "",
            "meses": self.meses_seleccionados(),
        }
        resultados = self.buscar_en_raiz(self.raiz_personas, filtros)
        self.mostrar_resultados(resultados)

    def grabar_voz(self):
        if self.hilo_voz is not None:
            return
        if hasattr(self, "grabadora") and self.grabadora.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.esperando_audio = True
            self.btn_voz.setEnabled(False)
            self.btn_voz.setText("Procesando voz…")
            self.grabadora.stop()
            return

        indice_dispositivo = self.cmb_microfono.currentData()
        if indice_dispositivo is None or indice_dispositivo >= len(self.dispositivos_audio):
            QMessageBox.warning(
                self,
                "Búsqueda por voz",
                "No hay ningún micrófono disponible. Conecta uno y comprueba "
                "Configuración de Windows > Privacidad y seguridad > Micrófono.",
            )
            return

        carpeta = Path(tempfile.gettempdir()) / "Victor Document AI" / "voz"
        carpeta.mkdir(parents=True, exist_ok=True)
        self.archivo_voz = carpeta / f"busqueda_{uuid.uuid4().hex}.m4a"
        self.captura_audio = QMediaCaptureSession(self)
        self.entrada_audio = QAudioInput(self.dispositivos_audio[indice_dispositivo], self)
        self.grabadora = QMediaRecorder(self)
        self.captura_audio.setAudioInput(self.entrada_audio)
        self.captura_audio.setRecorder(self.grabadora)
        self.grabadora.setOutputLocation(QUrl.fromLocalFile(str(self.archivo_voz)))
        self.grabadora.recorderStateChanged.connect(self.estado_grabadora)
        self.grabadora.errorOccurred.connect(self.error_grabadora)
        self.grabadora.record()
        self.btn_voz.setText("⏹ Terminar y buscar")
        self.lbl_estado.setText("Habla ahora. Pulsa de nuevo el micrófono al terminar.")

    def estado_grabadora(self, estado):
        if self.esperando_audio and estado == QMediaRecorder.RecorderState.StoppedState:
            self.esperando_audio = False
            self.transcribir_voz()

    def cargar_microfonos(self):
        """Muestra los dispositivos que Qt puede utilizar para grabar."""
        self.dispositivos_audio = QMediaDevices.audioInputs()
        self.cmb_microfono.clear()
        dispositivo_predeterminado = QMediaDevices.defaultAudioInput()
        indice_predeterminado = 0
        for indice, dispositivo in enumerate(self.dispositivos_audio):
            self.cmb_microfono.addItem(dispositivo.description(), indice)
            if dispositivo.id() == dispositivo_predeterminado.id():
                indice_predeterminado = indice
        if self.dispositivos_audio:
            self.cmb_microfono.setCurrentIndex(indice_predeterminado)
        else:
            self.cmb_microfono.addItem("No se detectó ningún micrófono", None)

    def error_grabadora(self, _error, mensaje):
        detalle = mensaje or "Windows no permitió iniciar la grabación."
        self.restablecer_voz(f"Error del micrófono: {detalle}")
        QMessageBox.warning(
            self,
            "Búsqueda por voz",
            f"No se pudo acceder al micrófono.\n\n{detalle}\n\n"
            "En Windows, activa: Configuración > Privacidad y seguridad > "
            "Micrófono > Permitir que las aplicaciones de escritorio accedan al micrófono.",
        )

    def transcribir_voz(self):
        if self.archivo_voz is None or not self.archivo_voz.exists() or self.archivo_voz.stat().st_size == 0:
            self.restablecer_voz("No se recibió audio del micrófono.")
            return
        self.progreso_voz = QProgressDialog("Transcribiendo la orden de voz…", None, 0, 0, self)
        self.progreso_voz.setWindowModality(Qt.WindowModal)
        self.progreso_voz.setCancelButton(None)
        self.progreso_voz.show()
        self.hilo_voz = QThread(self)
        self.worker_voz = VozWorker(self.archivo_voz)
        self.worker_voz.moveToThread(self.hilo_voz)
        self.hilo_voz.started.connect(self.worker_voz.ejecutar)
        self.worker_voz.finalizado.connect(self.aplicar_voz)
        self.worker_voz.finalizado.connect(self.hilo_voz.quit)
        self.worker_voz.finalizado.connect(self.worker_voz.deleteLater)
        self.worker_voz.error.connect(self.error_voz)
        self.worker_voz.error.connect(self.hilo_voz.quit)
        self.worker_voz.error.connect(self.worker_voz.deleteLater)
        self.hilo_voz.finished.connect(self.hilo_voz.deleteLater)
        self.hilo_voz.finished.connect(self.limpiar_voz)
        self.hilo_voz.start()

    def aplicar_voz(self, texto):
        texto_normalizado = self.normalizar_texto(texto)
        self.seleccionar_desde_voz(self.cmb_persona, texto_normalizado)
        self.seleccionar_desde_voz(self.cmb_instancia_1, texto_normalizado)
        self.seleccionar_desde_voz(self.cmb_instancia_2, texto_normalizado)
        self.seleccionar_desde_voz(self.cmb_instancia_3, texto_normalizado)

        coincidencia_ano = re.search(r"\b(20\d{2})\b", texto_normalizado)
        if coincidencia_ano:
            indice = self.cmb_ano.findData(coincidencia_ano.group(1))
            if indice >= 0:
                self.cmb_ano.setCurrentIndex(indice)

        palabras_voz = set(texto_normalizado.split())
        for accion in self.acciones_mes:
            accion.setChecked(
                any(nombre in palabras_voz for nombre in self.MESES_VOZ[accion.data()])
            )
        self.lbl_estado.setText(f"Orden reconocida: {texto}")
        self.buscar()

    def seleccionar_desde_voz(self, combo, texto):
        opciones = []
        for indice in range(1, combo.count()):
            valor = combo.itemData(indice)
            if valor:
                opciones.append((self.normalizar_texto(valor), indice))
        for valor, indice in sorted(opciones, key=lambda opcion: len(opcion[0]), reverse=True):
            if valor and valor in texto:
                combo.setCurrentIndex(indice)
                return True
        return False

    @staticmethod
    def normalizar_texto(texto):
        texto = unicodedata.normalize("NFD", texto.lower())
        texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
        return " ".join(re.findall(r"[a-z0-9]+", texto))

    def error_voz(self, mensaje):
        QMessageBox.warning(self, "Búsqueda por voz", mensaje)

    def limpiar_voz(self):
        if hasattr(self, "progreso_voz") and self.progreso_voz is not None:
            self.progreso_voz.close()
        if self.archivo_voz is not None:
            try:
                self.archivo_voz.unlink(missing_ok=True)
            except OSError:
                pass
        self.archivo_voz = None
        self.hilo_voz = None
        self.worker_voz = None
        self.btn_voz.setEnabled(True)
        self.btn_voz.setText("🎤 Buscar por voz")

    def restablecer_voz(self, mensaje):
        self.lbl_estado.setText(mensaje)
        self.btn_voz.setEnabled(True)
        self.btn_voz.setText("🎤 Buscar por voz")

    def buscar_en_raiz(self, raiz_personas, filtros):
        return self.documentos_catalogo.buscar(raiz_personas, filtros)

    def meses_seleccionados(self):
        return [accion.data() for accion in self.acciones_mes if accion.isChecked()]

    def actualizar_etiqueta_meses(self):
        seleccionados = [accion.text() for accion in self.acciones_mes if accion.isChecked()]
        if not seleccionados:
            self.btn_meses.setText("Todos los meses")
        elif len(seleccionados) == 1:
            self.btn_meses.setText(seleccionados[0])
        else:
            self.btn_meses.setText(f"{len(seleccionados)} meses seleccionados")

    @staticmethod
    def fecha_documento(archivo):
        coincidencia = re.search(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)", archivo.name)
        if coincidencia:
            return coincidencia.group(1)
        return datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%Y-%m-%d")

    def mostrar_resultados(self, resultados):
        self.tabla.setRowCount(len(resultados))
        for fila, (fecha, persona, instancias, archivo) in enumerate(resultados):
            casilla = QTableWidgetItem()
            casilla.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            casilla.setCheckState(Qt.Unchecked)
            casilla.setData(Qt.UserRole, str(archivo))
            self.tabla.setItem(fila, 0, casilla)
            valores = (fecha, persona, instancias, archivo.name)
            for columna, valor in enumerate(valores, start=1):
                item = QTableWidgetItem(valor)
                item.setData(Qt.UserRole, str(archivo))
                self.tabla.setItem(fila, columna, item)
        if len(resultados) >= 2000:
            self.lbl_estado.setText(
                "Mostrando los primeros 2.000 documentos. Añade filtros para acotar la búsqueda."
            )
        else:
            self.lbl_estado.setText(f"{len(resultados)} documento(s) encontrado(s).")
        if resultados:
            self.tabla.selectRow(0)
        self.actualizar_botones_documento()

    def archivo_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        return Path(item.data(Qt.UserRole)) if item is not None else None

    def abrir_documento(self, fila, columna):
        archivo = self.archivo_seleccionado()
        if archivo is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(archivo)))

    def actualizar_vista_previa(self):
        archivo = self.archivo_seleccionado()
        if archivo is None:
            self.actualizar_botones_documento()
            return
        try:
            if archivo.suffix.lower() == ".pdf":
                documento = fitz.open(archivo)
                pagina = documento[0]
                pix = pagina.get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
                imagen = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                documento.close()
                pixmap = QPixmap.fromImage(imagen)
            else:
                pixmap = QPixmap(str(archivo))
            self.lbl_vista_previa.setText("")
            self.lbl_vista_previa.setPixmap(pixmap.scaled(
                self.lbl_vista_previa.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))
        except (OSError, RuntimeError, IndexError):
            self.lbl_vista_previa.setPixmap(QPixmap())
            self.lbl_vista_previa.setText("No se pudo generar la vista previa.")
        self.actualizar_botones_documento()

    def actualizar_botones_documento(self):
        disponible = self.archivo_seleccionado() is not None
        for boton in (self.btn_guardar_copia, self.btn_imprimir, self.btn_correo):
            boton.setEnabled(disponible)

    def guardar_copia(self):
        archivo = self.archivo_seleccionado()
        if archivo is None:
            return
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar una copia del documento",
            str(Path.home() / "Documents" / archivo.name),
            f"Documento original (*{archivo.suffix});;Todos los archivos (*.*)",
        )
        if not destino:
            return
        try:
            shutil.copy2(archivo, destino)
            QMessageBox.information(self, "Copia guardada", "La copia se guardó correctamente.")
        except OSError as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))

    def imprimir_documento(self):
        archivo = self.archivo_seleccionado()
        if archivo is None:
            return

        impresora = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialogo = QPrintDialog(impresora, self)
        dialogo.setWindowTitle("Seleccionar impresora")
        if dialogo.exec() != QDialog.Accepted:
            return
        try:
            self.imprimir_archivo(archivo, impresora)
            self.lbl_estado.setText("El documento se envió a la impresora seleccionada.")
        except OSError as error:
            QMessageBox.critical(self, "No se pudo imprimir", str(error))

    @staticmethod
    def imprimir_archivo(archivo, impresora):
        archivo = Path(archivo)
        if archivo.suffix.lower() == ".pdf":
            documento = fitz.open(archivo)
            imagenes = []
            try:
                for pagina in documento:
                    pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    imagenes.append(
                        QImage(
                            pix.samples,
                            pix.width,
                            pix.height,
                            pix.stride,
                            QImage.Format_RGB888,
                        ).copy()
                    )
            finally:
                documento.close()
        else:
            imagenes = [QImage(str(archivo))]

        if not imagenes or any(imagen.isNull() for imagen in imagenes):
            raise OSError("El documento no se pudo preparar para impresión.")

        pintor = QPainter()
        if not pintor.begin(impresora):
            raise OSError("No se pudo iniciar la impresora seleccionada.")
        try:
            for indice, imagen in enumerate(imagenes):
                area = pintor.viewport()
                escalada = imagen.scaled(area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = area.x() + (area.width() - escalada.width()) // 2
                y = area.y() + (area.height() - escalada.height()) // 2
                pintor.drawImage(x, y, escalada)
                if indice < len(imagenes) - 1:
                    impresora.newPage()
        finally:
            pintor.end()

    def preparar_correo(self):
        archivos = self.archivos_marcados() or ([self.archivo_seleccionado()] if self.archivo_seleccionado() else [])
        if not archivos:
            return
        destinatario, confirmado = QInputDialog.getText(
            self,
            "Preparar email",
            "Correo del destinatario (puedes dejarlo vacío):",
        )
        if not confirmado:
            return
        try:
            borrador = self.crear_borrador_correo(archivos, destinatario)
        except OSError as error:
            QMessageBox.critical(self, "No se pudo preparar el email", str(error))
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(borrador))):
            QMessageBox.warning(
                self,
                "Abrir email",
                "No se pudo abrir el borrador. Configura una aplicación de correo para archivos .eml.",
            )
            return
        self.lbl_estado.setText(
            f"Se abrió un borrador con {len(archivos)} documento(s) adjunto(s). Revisa y envía el correo."
        )

    def archivos_marcados(self):
        archivos = []
        for fila in range(self.tabla.rowCount()):
            casilla = self.tabla.item(fila, 0)
            if casilla is not None and casilla.checkState() == Qt.Checked:
                archivos.append(Path(casilla.data(Qt.UserRole)))
        return archivos

    @staticmethod
    def crear_borrador_correo(archivos, destinatario=""):
        archivos = [Path(archivo) for archivo in archivos]
        mensaje = EmailMessage()
        asunto = archivos[0].name if len(archivos) == 1 else f"{len(archivos)} documentos"
        mensaje["Subject"] = f"Documentos: {asunto}"
        if destinatario.strip():
            mensaje["To"] = destinatario.strip()
        mensaje.set_content("Adjunto encontrarás los documentos solicitados.")
        for archivo in archivos:
            tipo_mime, _ = mimetypes.guess_type(archivo.name)
            tipo_principal, subtipo = (tipo_mime or "application/octet-stream").split("/", 1)
            mensaje.add_attachment(
                archivo.read_bytes(),
                maintype=tipo_principal,
                subtype=subtipo,
                filename=archivo.name,
            )
        carpeta = Path(tempfile.gettempdir()) / "Victor Document AI" / "emails"
        carpeta.mkdir(parents=True, exist_ok=True)
        borrador = carpeta / f"documento_{uuid.uuid4().hex}.eml"
        borrador.write_bytes(bytes(mensaje))
        return borrador
