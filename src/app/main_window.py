import json
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QStatusBar,
    QGridLayout,
    QGroupBox,
)

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from app.personas_window import PersonasWindow
from app.datos_familiares_window import DatosFamiliaresWindow
from app.entrada_window import EntradaWindow
from app.instancias_window import InstanciasWindow
from app.buscar_window import BuscarWindow
from app.dashboard import DashboardWindow
from app.configuracion_window import ConfiguracionWindow
from app.ia_window import IAWindow
from core.settings import Settings

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
        menu.addItem("📇 Datos familiares")
        menu.addItem("🏢 Instancias")
        menu.addItem("🔍 Buscar")
        menu.addItem("🤖 IA")
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

        mensaje = QLabel("Accesos rápidos y estado del sistema")
        mensaje.setAlignment(Qt.AlignCenter)
        mensaje.setStyleSheet("font-size:18px;")
        panel.addWidget(mensaje)

        resumen = QGroupBox("Hoy")
        cuadricula = QGridLayout(resumen)
        self.lbl_pendientes = self.crear_tarjeta("Pendientes en Entrada")
        self.lbl_ultimo = self.crear_tarjeta("Último documento guardado")
        self.lbl_sistema = self.crear_tarjeta("Estado del sistema")
        cuadricula.addWidget(self.lbl_pendientes, 0, 0)
        cuadricula.addWidget(self.lbl_ultimo, 0, 1)
        cuadricula.addWidget(self.lbl_sistema, 0, 2)
        panel.addWidget(resumen)

        accesos = QGroupBox("Acciones rápidas")
        accesos_layout = QGridLayout(accesos)
        btn_entrada = QPushButton("Abrir Entrada")
        btn_buscar = QPushButton("Buscar documentos")
        btn_personas = QPushButton("Ver Personas")
        btn_instancias = QPushButton("Ver Instancias")
        btn_chatgpt = QPushButton("💬 Abrir ChatGPT")
        btn_actualizar = QPushButton("Actualizar inicio")
        btn_entrada.clicked.connect(self.abrir_entrada)
        btn_buscar.clicked.connect(self.abrir_buscar)
        btn_personas.clicked.connect(self.abrir_personas)
        btn_instancias.clicked.connect(self.abrir_instancias)
        btn_chatgpt.clicked.connect(self.abrir_chatgpt)
        btn_actualizar.clicked.connect(self.actualizar_inicio)
        accesos_layout.addWidget(btn_entrada, 0, 0)
        accesos_layout.addWidget(btn_buscar, 0, 1)
        accesos_layout.addWidget(btn_personas, 1, 0)
        accesos_layout.addWidget(btn_instancias, 1, 1)
        accesos_layout.addWidget(btn_chatgpt, 2, 0)
        accesos_layout.addWidget(btn_actualizar, 2, 1)
        panel.addWidget(accesos)
        panel.addStretch()

        layout_principal.addLayout(panel)

        # ============================
        # Barra inferior
        # ============================

        barra = QStatusBar()

        barra.showMessage("Sistema listo.")

        self.setStatusBar(barra)
        self.actualizar_inicio()

    @staticmethod
    def crear_tarjeta(titulo):
        etiqueta = QLabel(f"{titulo}\n—")
        etiqueta.setAlignment(Qt.AlignCenter)
        etiqueta.setWordWrap(True)
        etiqueta.setMinimumHeight(95)
        etiqueta.setStyleSheet("border: 1px solid #b0bec5; padding: 12px; font-size: 16px;")
        return etiqueta

    def actualizar_inicio(self):
        settings = Settings()
        extensiones = {".pdf", ".jpg", ".jpeg", ".png"}
        try:
            pendientes = sum(
                1 for archivo in settings.origen.iterdir()
                if archivo.is_file() and archivo.suffix.lower() in extensiones
            )
            self.lbl_pendientes.setText(f"Pendientes en Entrada\n{pendientes}")
        except OSError:
            self.lbl_pendientes.setText("Pendientes en Entrada\nNo se pudo leer la carpeta")

        ruta_ultimo = settings.ruta_config.parent / "last_saved.json"
        try:
            ultimo = json.loads(ruta_ultimo.read_text(encoding="utf-8"))
            nombre = ultimo.get("nombre", "—")
            fecha = ultimo.get("guardado_en", "").replace("T", " ")
            self.lbl_ultimo.setText(f"Último documento guardado\n{nombre}\n{fecha}")
        except (OSError, json.JSONDecodeError):
            self.lbl_ultimo.setText("Último documento guardado\nAún no hay registro")

        proyecto = Path(__file__).resolve().parents[2]
        api_lista = bool(os.environ.get("OPENAI_API_KEY"))
        try:
            if not api_lista and (proyecto / ".env").exists():
                api_lista = "OPENAI_API_KEY=" in (proyecto / ".env").read_text(encoding="utf-8")
        except OSError:
            pass
        nas = "conectado" if settings.destino.exists() else "sin conexión"
        ia = "lista" if api_lista else "sin configurar"
        self.lbl_sistema.setText(f"Estado del sistema\nNAS: {nas}\nOCR: listo · IA: {ia}")

    # ===================================
    # Descubrir entidades
    # ===================================

    # ===================================
    # Menú
    # ===================================

    def menu_click(self, item):

        texto = item.text()

        if texto == "📥 Entrada":
            self.abrir_entrada()

        elif texto == "👤 Personas":
            self.abrir_personas()

        elif "Datos familiares" in texto:
            self.abrir_datos_familiares()

        elif texto == "🏢 Instancias":
            self.abrir_instancias()

        elif texto == "🔍 Buscar":
            self.abrir_buscar()

        elif "Dashboard" in texto:
            self.abrir_dashboard()

        elif "Configuraci" in texto:
            self.abrir_configuracion()

        elif texto.endswith("IA"):
            self.abrir_ia()

    def abrir_entrada(self):

        self.ventana_entrada = EntradaWindow()

        self.ventana_entrada.show()

    def abrir_personas(self):

        self.ventana_personas = PersonasWindow()
        self.ventana_personas.show()

    def abrir_datos_familiares(self):

        self.ventana_datos_familiares = DatosFamiliaresWindow()
        self.ventana_datos_familiares.show()

    def abrir_instancias(self):

        self.ventana_instancias = InstanciasWindow()
        self.ventana_instancias.show()

    def abrir_buscar(self):

        self.ventana_buscar = BuscarWindow()
        self.ventana_buscar.show()

    def abrir_dashboard(self):

        self.ventana_dashboard = DashboardWindow()
        self.ventana_dashboard.abrir_entrada.connect(self.abrir_entrada)
        self.ventana_dashboard.abrir_buscar.connect(self.abrir_buscar)
        self.ventana_dashboard.show()

    def abrir_configuracion(self):

        self.ventana_configuracion = ConfiguracionWindow()
        self.ventana_configuracion.show()

    def abrir_chatgpt(self):

        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))

    def abrir_ia(self):

        self.ventana_ia = IAWindow()
        self.ventana_ia.show()
