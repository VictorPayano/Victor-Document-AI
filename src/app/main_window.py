from inventory.discovery import Descubrimiento
from core.system import Sistema

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem
)

from PySide6.QtCore import Qt

from app.persona_window import PersonaWindow
from app.entrada_window import EntradaWindow

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # ============================
        # Ventana principal
        # ============================

        self.setWindowTitle("Victor Document AI")
        self.resize(1200, 700)
        self.move(300, 100)

        # ============================
        # Widget central
        # ============================

        central = QWidget()

        central.setStyleSheet("""
            background-color:#E8F5E9;
        """)

        self.setCentralWidget(central)

        layout_principal = QHBoxLayout()

        central.setLayout(layout_principal)

        # ============================
        # Menú lateral
        # ============================

        menu = QListWidget()

        menu.setFixedWidth(220)

        menu.setStyleSheet("""
            QListWidget{
                background:#D32F2F;
                color:white;
                font-size:18px;
                border:none;
            }

            QListWidget::item{
                padding:10px;
            }

            QListWidget::item:selected{
                background:#B71C1C;
            }
        """)

        menu.addItem("📥 Entrada")
        menu.addItem("🏠 Dashboard")
        menu.addItem("👤 Personas")
        menu.addItem("🏢 Empresas")
        menu.addItem("📄 Documentos")
        menu.addItem("📂 Biblioteca")
        menu.addItem("🤖 IA")
        menu.addItem("🔍 Buscar")
        menu.addItem("⚙ Configuración")   

        self.menu = menu

        self.menu.itemClicked.connect(self.menu_click)

        layout_principal.addWidget(menu)

        # ============================
        # Panel derecho
        # ============================

        panel = QVBoxLayout()

        titulo = QLabel("Bienvenido a Victor Document AI")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        panel.addWidget(titulo)

        # ============================
        # Tabla
        # ============================

        self.tabla = QTableWidget()

        self.tabla.setColumnCount(2)

        self.tabla.setHorizontalHeaderLabels([
            "Persona",
            "Documentos"
        ])

        self.tabla.horizontalHeader().setStretchLastSection(True)

        self.tabla.cellDoubleClicked.connect(self.abrir_persona)

        panel.addWidget(self.tabla)

        # ============================
        # Botón
        # ============================

        self.boton = QPushButton("Descubrir entidades")

        self.boton.setMinimumHeight(40)

        self.boton.clicked.connect(self.descubrir_entidades)

        panel.addWidget(self.boton)

        layout_principal.addLayout(panel)

        # ============================
        # Barra inferior
        # ============================

        barra = QStatusBar()

        barra.showMessage("Sistema listo.")

        self.setStatusBar(barra)

    # ===================================
    # Descubrir entidades
    # ===================================

    def descubrir_entidades(self):

        descubrimiento = Descubrimiento(Sistema.BIBLIOTECA)

        personas = descubrimiento.detectar_personas()

        print("Personas encontradas:", len(personas))

        self.tabla.setRowCount(len(personas))

        for fila, persona in enumerate(personas):

            print(persona.nombre)

            self.tabla.setItem(
                fila,
                0,
                QTableWidgetItem(persona.nombre)
            )

            self.tabla.setItem(
                fila,
                1,
                QTableWidgetItem(str(persona.total_documentos))
            )

    # ===================================
    # Abrir ventana de persona
    # ===================================

    def abrir_persona(self, fila, columna):

        nombre = self.tabla.item(fila, 0).text()

        self.ventana_persona = PersonaWindow(nombre)

        self.ventana_persona.show()

    
    # ===================================
    # Menú
    # ===================================

    def menu_click(self, item):

        texto = item.text()

        if texto == "📥 Entrada":
            self.abrir_entrada()

    def abrir_entrada(self):

        self.ventana_entrada = EntradaWindow()

        self.ventana_entrada.show()