"""Captura una foto desde la cámara para usarla como documento temporal."""

import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout


class CameraCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capturar documento con cámara")
        self.resize(850, 670)
        self.captured_path = None
        self.camera = None
        self.frame_received = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Coloca el documento bien iluminado y pulsa Tomar foto."))
        camera_row = QHBoxLayout()
        camera_row.addWidget(QLabel("Cámara:"))
        self.camera_combo = QComboBox()
        self.devices = QMediaDevices.videoInputs()
        default_device = QMediaDevices.defaultVideoInput()
        default_index = 0
        for index, device in enumerate(self.devices):
            self.camera_combo.addItem(device.description(), index)
            if device.id() == default_device.id():
                default_index = index
        self.camera_combo.setCurrentIndex(default_index)
        self.camera_combo.currentIndexChanged.connect(self.change_camera)
        camera_row.addWidget(self.camera_combo, 1)
        layout.addLayout(camera_row)
        self.video = QVideoWidget()
        self.video.videoSink().videoFrameChanged.connect(self.video_frame_received)
        layout.addWidget(self.video, 1)
        self.status = QLabel("Iniciando cámara…")
        layout.addWidget(self.status)
        self.capture_button = QPushButton("Tomar foto")
        self.capture_button.clicked.connect(self.capture)
        layout.addWidget(self.capture_button)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self.devices:
            self.capture_button.setEnabled(False)
            self.status.setText("No se detectó una cámara. Comprueba la privacidad de cámara de Windows.")
            return
        self.session = QMediaCaptureSession(self)
        self.image_capture = QImageCapture(self)
        self.session.setImageCapture(self.image_capture)
        self.session.setVideoOutput(self.video)
        self.image_capture.imageSaved.connect(self.image_saved)
        self.image_capture.errorOccurred.connect(self.capture_error)
        self.start_camera(default_index)

    def change_camera(self, index):
        if hasattr(self, "session"):
            self.start_camera(index)

    def start_camera(self, index):
        if not 0 <= index < len(self.devices):
            return
        self.stop_camera()
        if self.camera is not None:
            self.camera.deleteLater()
        device = self.devices[index]
        self.frame_received = False
        self.capture_button.setEnabled(True)
        self.camera = QCamera(device, self)
        self.camera.errorOccurred.connect(self.camera_error)
        self.session.setCamera(self.camera)
        self.camera.start()
        self.status.setText(f"Iniciando cámara: {device.description()}")
        QTimer.singleShot(3000, self.check_video)

    def video_frame_received(self, frame):
        if frame.isValid():
            self.frame_received = True
            if self.camera is not None and self.camera.isActive():
                self.status.setText(f"Cámara activa: {self.camera_combo.currentText()}")

    def check_video(self):
        if self.camera is not None and self.camera.isActive() and not self.frame_received:
            self.status.setText(
                "La cámara no entrega imagen. Prueba la otra cámara de la lista o revisa los permisos de Windows."
            )

    def camera_error(self, _error, message):
        self.status.setText(f"Error de cámara: {message or self.camera.errorString()}")
        self.capture_button.setEnabled(False)

    def capture(self):
        if self.camera is None:
            return
        folder = Path(tempfile.gettempdir()) / "Victor Document AI" / "camera"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"documento_{uuid.uuid4().hex}.jpg"
        self.capture_button.setEnabled(False)
        self.status.setText("Capturando imagen…")
        self.image_capture.captureToFile(str(path))

    def image_saved(self, _identifier, path):
        self.captured_path = Path(path)
        self.stop_camera()
        self.accept()

    def capture_error(self, _identifier, _error, message):
        self.capture_button.setEnabled(True)
        self.status.setText("No se pudo tomar la foto.")
        QMessageBox.warning(self, "Cámara", message or "Windows no permitió capturar la imagen.")

    def stop_camera(self):
        if self.camera is not None:
            self.camera.stop()

    def reject(self):
        self.stop_camera()
        super().reject()

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
