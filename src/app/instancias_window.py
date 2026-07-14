from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QInputDialog,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from services.instance_store import InstanceStore


class InstanciasWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Instancias")
        self.resize(900, 650)
        self.catalogo = InstanceStore()
        if not self.catalogo.listar():
            self.catalogo.importar_desde_personas(Settings().destino / "Personas")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        titulo = QLabel("Catálogo de instancias")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(titulo)

        explicacion = QLabel(
            "Define la estructura común: Instancia → Subinstancia → Sub/subinstancia. "
            "No depende de las carpetas de cada persona."
        )
        explicacion.setWordWrap(True)
        layout.addWidget(explicacion)

        editor = QGroupBox("Añadir o completar una ruta")
        formulario = QFormLayout(editor)
        self.cmb_instancia_1 = QComboBox()
        self.cmb_instancia_2 = QComboBox()
        self.cmb_instancia_3 = QComboBox()
        for campo in (self.cmb_instancia_1, self.cmb_instancia_2, self.cmb_instancia_3):
            campo.setEditable(True)
            campo.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_instancia_1.currentTextChanged.connect(self.cambiar_instancia_1)
        self.cmb_instancia_2.currentTextChanged.connect(self.cambiar_instancia_2)
        formulario.addRow("Instancia:", self.cmb_instancia_1)
        formulario.addRow("Subinstancia:", self.cmb_instancia_2)
        formulario.addRow("Sub/subinstancia:", self.cmb_instancia_3)
        self.btn_guardar = QPushButton("Guardar en catálogo")
        self.btn_guardar.clicked.connect(self.guardar_ruta)
        self.atajo_guardar_enter = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.atajo_guardar_enter.setContext(Qt.WidgetWithChildrenShortcut)
        self.atajo_guardar_enter.activated.connect(self.guardar_ruta)
        self.atajo_guardar_numerico = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.atajo_guardar_numerico.setContext(Qt.WidgetWithChildrenShortcut)
        self.atajo_guardar_numerico.activated.connect(self.guardar_ruta)
        self.btn_limpiar_campos = QPushButton("Limpiar campos")
        self.btn_limpiar_campos.clicked.connect(self.limpiar_campos)
        botones_editor = QHBoxLayout()
        botones_editor.addWidget(self.btn_guardar)
        botones_editor.addWidget(self.btn_limpiar_campos)
        formulario.addRow(botones_editor)
        layout.addWidget(editor)

        acciones = QHBoxLayout()
        self.btn_importar = QPushButton("Importar estructura actual de Personas")
        self.btn_importar.clicked.connect(self.importar_desde_personas)
        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.clicked.connect(self.actualizar)
        acciones.addWidget(self.btn_importar)
        acciones.addWidget(self.btn_actualizar)
        acciones.addStretch()
        layout.addLayout(acciones)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabel("Instancias configuradas")
        self.arbol.setContextMenuPolicy(Qt.CustomContextMenu)
        self.arbol.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        layout.addWidget(self.arbol, 1)

        self.lbl_estado = QLabel()
        layout.addWidget(self.lbl_estado)
        self.actualizar()

    @staticmethod
    def cargar_combo(combo, valores, valor_actual=""):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        combo.addItems(valores)
        combo.setCurrentText(valor_actual)
        combo.blockSignals(False)

    def actualizar(self):
        instancia = self.cmb_instancia_1.currentText()
        subinstancia = self.cmb_instancia_2.currentText()
        subsubinstancia = self.cmb_instancia_3.currentText()
        self.catalogo = InstanceStore()
        self.cargar_combo(self.cmb_instancia_1, self.catalogo.listar(), instancia)
        self.cargar_combo(self.cmb_instancia_2, self.catalogo.hijos(instancia), subinstancia)
        self.cargar_combo(
            self.cmb_instancia_3,
            self.catalogo.hijos(instancia, subinstancia),
            subsubinstancia,
        )
        self.cargar_arbol()

    def cambiar_instancia_1(self):
        instancia = self.cmb_instancia_1.currentText().strip()
        self.cargar_combo(self.cmb_instancia_2, self.catalogo.hijos(instancia))
        self.cargar_combo(self.cmb_instancia_3, [])

    def cambiar_instancia_2(self):
        instancia = self.cmb_instancia_1.currentText().strip()
        subinstancia = self.cmb_instancia_2.currentText().strip()
        self.cargar_combo(
            self.cmb_instancia_3,
            self.catalogo.hijos(instancia, subinstancia),
        )

    def guardar_ruta(self):
        cambio = self.catalogo.agregar_ruta(
            self.cmb_instancia_1.currentText(),
            self.cmb_instancia_2.currentText(),
            self.cmb_instancia_3.currentText(),
        )
        if not cambio:
            QMessageBox.information(self, "Instancias", "La ruta ya existe o está vacía.")
        self.actualizar()

    def limpiar_campos(self):
        self.cmb_instancia_1.setCurrentIndex(0)
        self.cmb_instancia_2.setCurrentIndex(0)
        self.cmb_instancia_3.setCurrentIndex(0)

    def importar_desde_personas(self):
        raiz = Settings().destino / "Personas"
        cambio = self.catalogo.importar_desde_personas(raiz)
        self.actualizar()
        mensaje = (
            "Se importaron las instancias y subinstancias encontradas."
            if cambio else "No había rutas nuevas para importar."
        )
        QMessageBox.information(self, "Instancias", mensaje)

    def cargar_arbol(self):
        self.arbol.clear()
        total = 0
        for instancia in self.catalogo.instancias:
            self.agregar_nodo(None, instancia)
            total += 1
        self.arbol.expandAll()
        self.lbl_estado.setText(f"{total} instancia(s) principal(es) en el catálogo.")

    def agregar_nodo(self, padre, nodo, ruta=()):
        ruta = (*ruta, nodo["nombre"])
        item = QTreeWidgetItem([nodo["nombre"]])
        item.setData(0, Qt.UserRole, ruta)
        if padre is None:
            self.arbol.addTopLevelItem(item)
        else:
            padre.addChild(item)
        for hijo in nodo["hijos"]:
            self.agregar_nodo(item, hijo, ruta)

    def mostrar_menu_contextual(self, posicion):
        item = self.arbol.itemAt(posicion)
        if item is None:
            return

        menu = QMenu(self)
        accion_renombrar = QAction("Renombrar…", self)
        accion_eliminar = QAction("Eliminar del catálogo", self)
        menu.addAction(accion_renombrar)
        menu.addAction(accion_eliminar)
        accion = menu.exec(self.arbol.mapToGlobal(posicion))
        if accion is accion_renombrar:
            self.renombrar_ruta(item.data(0, Qt.UserRole))
        elif accion is accion_eliminar:
            self.eliminar_ruta(item.data(0, Qt.UserRole))

    def renombrar_ruta(self, ruta):
        nombre_actual = ruta[-1]
        nuevo_nombre, confirmado = QInputDialog.getText(
            self,
            "Renombrar instancia",
            "Nuevo nombre:",
            text=nombre_actual,
        )
        if not confirmado:
            return

        try:
            cambio = self.catalogo.renombrar_ruta(*ruta, nuevo_nombre=nuevo_nombre)
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo renombrar", str(error))
            return

        if cambio:
            self.actualizar()

    def eliminar_ruta(self, ruta):
        ruta_texto = " → ".join(ruta)
        respuesta = QMessageBox.question(
            self,
            "Eliminar del catálogo",
            f"¿Eliminar '{ruta_texto}' del catálogo?\n\n"
            "Si contiene subinstancias, también se eliminarán del catálogo. "
            "Las carpetas y documentos del NAS no se modificarán.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return

        self.catalogo.eliminar_ruta(*ruta)
        self.actualizar()
