from pathlib import Path
import tempfile
import uuid

import fitz
from PySide6.QtCore import Qt, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QImage, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaDevices, QMediaRecorder
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QInputDialog,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.personas_window import PersonasWindow
from services.family_database import FamilyDatabase
from services.family_report import FamilyReport
from services.voice_search import VoiceSearch


class FamilyVoiceWorker(QObject):
    completed = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    @Slot()
    def run(self):
        try:
            self.completed.emit(VoiceSearch().transcribir(self.audio_path))
        except Exception as error:
            self.error.emit(f"{type(error).__name__}: {error}")


class DatosFamiliaresWindow(QMainWindow):
    """Consultas de fichas familiares, separado de la búsqueda de documentos."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Datos familiares")
        self.resize(950, 650)
        self.database = FamilyDatabase()
        self.reporter = FamilyReport(self.database)
        self.person_result = None
        self.voice_thread = None
        self.waiting_for_audio = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        title = QLabel("Consultar datos familiares")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(title)
        note = QLabel("Consulta datos guardados en la ficha familiar. Esta ventana no busca PDFs ni envía datos a la IA.")
        note.setWordWrap(True)
        layout.addWidget(note)

        question_row = QHBoxLayout()
        self.question = QLineEdit()
        self.question.setPlaceholderText("Ej.: email de Victor, cuentas bancarias de Indira, número fiscal de Luis")
        self.question.returnPressed.connect(self.consult)
        consult_button = QPushButton("Consultar")
        self.voice_button = QPushButton("🎤 Consultar por voz")
        consult_button.clicked.connect(self.consult)
        self.voice_button.clicked.connect(self.record_voice)
        question_row.addWidget(self.question, 1)
        question_row.addWidget(consult_button)
        question_row.addWidget(self.voice_button)
        layout.addLayout(question_row)

        quick = QGroupBox("Consulta rápida")
        quick_layout = QGridLayout(quick)
        self.people = QComboBox()
        self.load_people()
        quick_layout.addWidget(QLabel("Persona:"), 0, 0)
        quick_layout.addWidget(self.people, 0, 1, 1, 4)
        for index, (label, request) in enumerate((
            ("Email", "email"), ("Teléfono", "teléfono"), ("Número fiscal", "número fiscal"),
            ("Cuentas bancarias", "cuentas bancarias"), ("Seguros", "seguros"), ("Servicios", "servicios"),
            ("Dirección", "dirección"), ("Ficha básica", "datos de"),
        )):
            button = QPushButton(label)
            button.clicked.connect(lambda _, value=request: self.quick_consult(value))
            quick_layout.addWidget(button, 1 + index // 4, index % 4)
        layout.addWidget(quick)

        report_actions = QGroupBox("Guardar o compartir resultado")
        report_layout = QHBoxLayout(report_actions)
        view_report = QPushButton("Ver informe completo")
        save_report = QPushButton("Guardar informe en PDF…")
        print_report = QPushButton("Imprimir informe")
        email_report = QPushButton("Enviar informe por email")
        view_report.clicked.connect(self.view_report)
        save_report.clicked.connect(self.save_report)
        print_report.clicked.connect(self.print_report)
        email_report.clicked.connect(self.email_report)
        report_layout.addWidget(view_report)
        report_layout.addWidget(save_report)
        report_layout.addWidget(print_report)
        report_layout.addWidget(email_report)
        layout.addWidget(report_actions)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("El resultado aparecerá aquí.")
        layout.addWidget(self.result, 1)
        self.open_person_button = QPushButton("Abrir ficha completa de la persona")
        self.open_person_button.setEnabled(False)
        self.open_person_button.clicked.connect(self.open_person)
        layout.addWidget(self.open_person_button)

    def load_people(self):
        self.people.clear()
        self.people.addItem("Selecciona una persona", None)
        for person in self.database.people():
            name = " ".join(value for value in (person.get("given_names"), person.get("surname")) if value).strip()
            self.people.addItem(name or person["folder_name"], person["id"])

    def quick_consult(self, request):
        person_id = self.people.currentData()
        if person_id is None:
            self.result.setPlainText("Selecciona una persona primero.")
            return
        person = self.database.get_person(person_id)
        self.question.setText(f"Dame {request} de {person['folder_name']}")
        self.consult()

    def consult(self):
        question = self.question.text().strip()
        self.person_result = self.database.person_in_question(question)
        self.result.setPlainText(self.database.consult(question))
        self.open_person_button.setEnabled(self.person_result is not None)

    def record_voice(self):
        if self.voice_thread is not None:
            return
        if hasattr(self, "recorder") and self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.waiting_for_audio = True
            self.voice_button.setEnabled(False)
            self.voice_button.setText("Procesando voz…")
            self.recorder.stop()
            return
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            QMessageBox.warning(self, "Consulta por voz", "No se detectó ningún micrófono disponible.")
            return
        folder = Path(tempfile.gettempdir()) / "Victor Document AI" / "voz"
        folder.mkdir(parents=True, exist_ok=True)
        self.voice_audio = folder / f"consulta_{uuid.uuid4().hex}.m4a"
        self.capture_session = QMediaCaptureSession(self)
        self.audio_input = QAudioInput(device, self)
        self.recorder = QMediaRecorder(self)
        self.capture_session.setAudioInput(self.audio_input)
        self.capture_session.setRecorder(self.recorder)
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self.voice_audio)))
        self.recorder.recorderStateChanged.connect(self.voice_recorder_state)
        self.recorder.errorOccurred.connect(self.voice_recorder_error)
        self.recorder.record()
        self.voice_button.setText("⏹ Terminar y consultar")
        self.result.setPlainText("Habla ahora. Di, por ejemplo: 'dame el email de Victor'.\nPulsa de nuevo el micrófono al terminar.")

    def voice_recorder_state(self, state):
        if self.waiting_for_audio and state == QMediaRecorder.RecorderState.StoppedState:
            self.waiting_for_audio = False
            self.transcribe_voice()

    def voice_recorder_error(self, _error, message):
        self.reset_voice()
        QMessageBox.warning(
            self,
            "Consulta por voz",
            f"No se pudo acceder al micrófono.\n\n{message}\n\n"
            "Comprueba Configuración de Windows > Privacidad y seguridad > Micrófono.",
        )

    def transcribe_voice(self):
        if not self.voice_audio.exists() or self.voice_audio.stat().st_size == 0:
            self.reset_voice()
            QMessageBox.warning(self, "Consulta por voz", "No se recibió audio del micrófono.")
            return
        self.voice_progress = QProgressDialog("Transcribiendo la consulta…", None, 0, 0, self)
        self.voice_progress.setWindowModality(Qt.WindowModal)
        self.voice_progress.setCancelButton(None)
        self.voice_progress.show()
        self.voice_thread = QThread(self)
        self.voice_worker = FamilyVoiceWorker(self.voice_audio)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.completed.connect(self.apply_voice_question)
        self.voice_worker.completed.connect(self.voice_thread.quit)
        self.voice_worker.completed.connect(self.voice_worker.deleteLater)
        self.voice_worker.error.connect(self.voice_error)
        self.voice_worker.error.connect(self.voice_thread.quit)
        self.voice_worker.error.connect(self.voice_worker.deleteLater)
        self.voice_thread.finished.connect(self.voice_thread.deleteLater)
        self.voice_thread.finished.connect(self.clean_voice)
        self.voice_thread.start()

    def apply_voice_question(self, text):
        self.question.setText(text)
        self.consult()

    def voice_error(self, message):
        QMessageBox.warning(self, "Consulta por voz", message)

    def clean_voice(self):
        if getattr(self, "voice_progress", None) is not None:
            self.voice_progress.close()
        if getattr(self, "voice_audio", None) is not None:
            self.voice_audio.unlink(missing_ok=True)
        self.voice_thread = None
        self.voice_worker = None
        self.reset_voice()

    def reset_voice(self):
        self.voice_button.setEnabled(True)
        self.voice_button.setText("🎤 Consultar por voz")

    def open_person(self):
        if self.person_result is None:
            return
        self.person_window = PersonasWindow(self.person_result["id"])
        self.person_window.show()

    def report_person(self):
        if self.general_query_available():
            return None
        if self.person_result is not None:
            return self.person_result
        person_id = self.people.currentData()
        return self.database.get_person(person_id) if person_id is not None else None

    def general_query_available(self):
        return self.result.toPlainText().strip().startswith("Consulta general")

    def build_report(self, path=None):
        person = self.report_person()
        if person is not None:
            return self.reporter.create(person["id"], path) if path else self.reporter.temporary(person["id"])
        if self.general_query_available():
            question = self.question.text().strip()
            result = self.result.toPlainText()
            return self.reporter.create_query(question, result, path) if path else self.reporter.temporary_query(question, result)
        return None

    def save_report(self):
        person = self.report_person()
        if person is None and not self.general_query_available():
            QMessageBox.information(self, "Informe", "Consulta una persona o realiza una consulta general primero.")
            return
        safe_name = "consulta_general" if person is None else "_".join((person.get("given_names") or person["folder_name"]).split())
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe completo", f"informe_{safe_name}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        try:
            self.build_report(path)
        except Exception as error:
            QMessageBox.critical(self, "Informe", str(error))
            return
        QMessageBox.information(self, "Informe", f"Informe guardado en:\n{path}")

    def view_report(self):
        person = self.report_person()
        if person is None and not self.general_query_available():
            QMessageBox.information(self, "Informe", "Consulta una persona o realiza una consulta general primero.")
            return
        try:
            pdf = self.build_report()
        except Exception as error:
            QMessageBox.critical(self, "Informe", str(error))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf))):
            QMessageBox.warning(self, "Informe", "Windows no pudo abrir la vista previa del PDF.")

    def print_report(self):
        person = self.report_person()
        if person is None and not self.general_query_available():
            QMessageBox.information(self, "Informe", "Consulta una persona o realiza una consulta general primero.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Seleccionar impresora para el informe")
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.print_pdf(self.build_report(), printer)
        except Exception as error:
            QMessageBox.critical(self, "Imprimir informe", str(error))

    def email_report(self):
        person = self.report_person()
        if person is None and not self.general_query_available():
            QMessageBox.information(self, "Informe", "Consulta una persona o realiza una consulta general primero.")
            return
        recipient, accepted = QInputDialog.getText(
            self, "Enviar informe por email", "Correo del destinatario (puedes dejarlo vacío):"
        )
        if not accepted:
            return
        try:
            pdf = self.build_report()
            draft = self.reporter.create_email_draft(pdf, recipient.strip())
        except Exception as error:
            QMessageBox.critical(self, "Enviar informe", str(error))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(draft))):
            QMessageBox.warning(self, "Enviar informe", "No se pudo abrir el borrador de email.")

    @staticmethod
    def print_pdf(path, printer):
        document = fitz.open(path)
        images = []
        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                images.append(QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format_RGB888).copy())
        finally:
            document.close()
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("No se pudo iniciar la impresora seleccionada.")
        try:
            for index, image in enumerate(images):
                area = painter.viewport()
                scaled = image.scaled(area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawImage(area.x() + (area.width() - scaled.width()) // 2, area.y() + (area.height() - scaled.height()) // 2, scaled)
                if index < len(images) - 1:
                    printer.newPage()
        finally:
            painter.end()
