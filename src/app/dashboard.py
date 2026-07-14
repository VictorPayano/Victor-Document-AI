import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from services.document_catalog import DocumentCatalog, IndexacionCancelada


class CatalogIndexWorker(QObject):
    progreso = Signal(int, str)
    finalizado = Signal(int)
    cancelado = Signal(int)
    error = Signal(str)

    def __init__(self, raiz_personas, ruta_catalogo):
        super().__init__()
        self.raiz_personas = Path(raiz_personas)
        self.ruta_catalogo = Path(ruta_catalogo)
        self._cancelar = threading.Event()

    def cancelar(self):
        self._cancelar.set()

    @Slot()
    def ejecutar(self):
        try:
            catalogo = DocumentCatalog(self.ruta_catalogo)
            total = catalogo.indexar(
                self.raiz_personas,
                progreso=lambda actual, nombre: self.progreso.emit(actual, nombre),
                cancelado=self._cancelar.is_set,
            )
            self.finalizado.emit(total)
        except IndexacionCancelada as error:
            self.cancelado.emit(error.total)
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class DashboardWindow(QMainWindow):

    abrir_entrada = Signal()
    abrir_buscar = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Dashboard")
        self.resize(1100, 720)
        self.settings = Settings()
        self.raiz_personas = self.settings.destino / "Personas"
        self.catalogo = DocumentCatalog()
        self.hilo_indexado = None
        self.worker_indexado = None
        self.progreso_indexado = None
        self.cerrar_al_terminar = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        titulo = QLabel("Dashboard")
        titulo.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(titulo)

        metricas = QGroupBox("Resumen")
        cuadricula = QGridLayout(metricas)
        self.tarjetas = {}
        for indice, (clave, titulo_tarjeta) in enumerate((
            ("pendientes", "Pendientes en Entrada"),
            ("hoy", "Guardados hoy"),
            ("semana", "Guardados esta semana"),
            ("mes", "Guardados este mes"),
            ("total", "Documentos archivados"),
            ("sin_fecha", "Archivados sin fecha"),
        )):
            tarjeta = QLabel(f"{titulo_tarjeta}\n—")
            tarjeta.setAlignment(Qt.AlignCenter)
            tarjeta.setStyleSheet("border: 1px solid #b0bec5; padding: 15px; font-size: 16px;")
            cuadricula.addWidget(tarjeta, indice // 3, indice % 3)
            self.tarjetas[clave] = tarjeta
        layout.addWidget(metricas)

        personas = QGroupBox("Personas con más documentos")
        personas_layout = QVBoxLayout(personas)
        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Persona", "Documentos"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        personas_layout.addWidget(self.tabla)
        layout.addWidget(personas, 1)

        acciones = QHBoxLayout()
        self.btn_actualizar = QPushButton("Actualizar métricas")
        self.btn_indexar = QPushButton("Indexar/actualizar NAS")
        self.btn_entrada = QPushButton("Abrir Entrada")
        self.btn_buscar = QPushButton("Buscar documentos")
        self.btn_actualizar.clicked.connect(self.actualizar)
        self.btn_indexar.clicked.connect(self.iniciar_indexacion)
        self.btn_entrada.clicked.connect(self.abrir_entrada.emit)
        self.btn_buscar.clicked.connect(self.abrir_buscar.emit)
        acciones.addWidget(self.btn_actualizar)
        acciones.addWidget(self.btn_indexar)
        acciones.addWidget(self.btn_entrada)
        acciones.addWidget(self.btn_buscar)
        acciones.addStretch()
        layout.addLayout(acciones)

        self.lbl_estado = QLabel()
        layout.addWidget(self.lbl_estado)

        # Esta actualización solo consulta SQLite; nunca recorre el NAS completo.
        self.actualizar()

    def _contar_entrada(self):
        extensiones = DocumentCatalog.EXTENSIONES
        try:
            return sum(
                1 for archivo in self.settings.origen.iterdir()
                if archivo.is_file() and archivo.suffix.lower() in extensiones
            )
        except OSError:
            return 0

    def actualizar(self):
        try:
            datos = self.catalogo.metricas(self.raiz_personas)
            datos["pendientes"] = self._contar_entrada()
            self.mostrar_metricas(datos)
            if datos["ultima_indexacion"]:
                fecha = datos["ultima_indexacion"].replace("T", " ")
                self.lbl_estado.setText(
                    f"Métricas del catálogo local. Última indexación completa: {fecha}."
                )
            else:
                self.lbl_estado.setText(
                    "El NAS todavía no está indexado. Pulsa “Indexar/actualizar NAS”; "
                    "puedes cancelar el proceso cuando quieras."
                )
        except Exception as error:
            self.mostrar_error(f"{type(error).__name__}: {error}")

    def iniciar_indexacion(self):
        if self.hilo_indexado is not None:
            return

        self.btn_indexar.setEnabled(False)
        self.progreso_indexado = QProgressDialog(
            "Preparando el catálogo del NAS…",
            "Cancelar",
            0,
            0,
            self,
        )
        self.progreso_indexado.setWindowTitle("Indexando documentos")
        self.progreso_indexado.setWindowModality(Qt.WindowModal)
        self.progreso_indexado.setMinimumDuration(0)
        self.progreso_indexado.canceled.connect(self.cancelar_indexacion)
        self.progreso_indexado.show()

        self.lbl_estado.setText(
            "Indexando el NAS en segundo plano. Los documentos no se modificarán."
        )
        self.hilo_indexado = QThread(self)
        self.worker_indexado = CatalogIndexWorker(
            self.raiz_personas,
            self.catalogo.ruta,
        )
        self.worker_indexado.moveToThread(self.hilo_indexado)
        self.hilo_indexado.started.connect(self.worker_indexado.ejecutar)
        self.worker_indexado.progreso.connect(self.mostrar_progreso)
        self.worker_indexado.finalizado.connect(self.finalizar_indexacion)
        self.worker_indexado.finalizado.connect(self.hilo_indexado.quit)
        self.worker_indexado.cancelado.connect(self.indexacion_cancelada)
        self.worker_indexado.cancelado.connect(self.hilo_indexado.quit)
        self.worker_indexado.error.connect(self.error_indexacion)
        self.worker_indexado.error.connect(self.hilo_indexado.quit)
        self.hilo_indexado.finished.connect(self.worker_indexado.deleteLater)
        self.hilo_indexado.finished.connect(self.hilo_indexado.deleteLater)
        self.hilo_indexado.finished.connect(self.limpiar_indexacion)
        self.hilo_indexado.start()

    def cancelar_indexacion(self):
        if self.worker_indexado is not None:
            self.worker_indexado.cancelar()
            self.lbl_estado.setText("Cancelando la indexación de forma segura…")

    def mostrar_progreso(self, actual, nombre):
        if self.progreso_indexado is not None:
            self.progreso_indexado.setLabelText(
                f"{actual:,} documentos registrados\n{nombre}"
            )

    def finalizar_indexacion(self, total):
        if self.progreso_indexado is not None:
            self.progreso_indexado.close()
        self.actualizar()
        self.lbl_estado.setText(
            f"Indexación completada: {total:,} documentos registrados."
        )

    def indexacion_cancelada(self, total):
        if self.progreso_indexado is not None:
            self.progreso_indexado.close()
        self.actualizar()
        self.lbl_estado.setText(
            f"Indexación cancelada. Se conservaron {total:,} registros parciales; "
            "puedes continuar más tarde."
        )

    def error_indexacion(self, mensaje):
        if self.progreso_indexado is not None:
            self.progreso_indexado.close()
        self.lbl_estado.setText(f"No se pudo indexar el NAS: {mensaje}")

    def mostrar_metricas(self, datos):
        etiquetas = {
            "pendientes": "Pendientes en Entrada",
            "hoy": "Guardados hoy",
            "semana": "Guardados esta semana",
            "mes": "Guardados este mes",
            "total": "Documentos archivados",
            "sin_fecha": "Archivados sin fecha",
        }
        for clave, etiqueta in etiquetas.items():
            self.tarjetas[clave].setText(f"{etiqueta}\n{datos[clave]:,}")
        self.tabla.setRowCount(len(datos["personas"]))
        for fila, (persona, total) in enumerate(datos["personas"]):
            self.tabla.setItem(fila, 0, QTableWidgetItem(persona))
            self.tabla.setItem(fila, 1, QTableWidgetItem(f"{total:,}"))

    def mostrar_error(self, mensaje):
        self.lbl_estado.setText(f"No se pudieron calcular las métricas: {mensaje}")

    def limpiar_indexacion(self):
        self.btn_indexar.setEnabled(True)
        self.hilo_indexado = None
        self.worker_indexado = None
        self.progreso_indexado = None
        if self.cerrar_al_terminar:
            self.cerrar_al_terminar = False
            self.close()

    def closeEvent(self, event):
        if self.hilo_indexado is not None:
            self.cerrar_al_terminar = True
            self.cancelar_indexacion()
            event.ignore()
            return
        super().closeEvent(event)
