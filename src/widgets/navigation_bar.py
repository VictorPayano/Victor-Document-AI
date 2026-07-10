from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QLabel,
    QHBoxLayout,
)


class NavigationBar(QWidget):

    def __init__(self):

        super().__init__()

        layout = QHBoxLayout()

        # ==========================
        # Botón Atrás
        # ==========================

        self.boton_atras = QPushButton("⬅ Atrás")

        layout.addWidget(self.boton_atras)

        # ==========================
        # Botón Inicio
        # ==========================

        self.boton_inicio = QPushButton("🏠 Inicio")

        layout.addWidget(self.boton_inicio)

        # ==========================
        # Ruta
        # ==========================

        self.ruta = QLabel("")

        layout.addWidget(self.ruta)

        layout.addStretch()

        self.setLayout(layout)

    # =====================================

    def set_ruta(self, texto):

        self.ruta.setText("📍 " + texto)