"""
=========================================================
            Victor Document AI
=========================================================

Autor: Victor Payano + ChatGPT
Versión: 0.1
"""

from core.system import Sistema
from inventory.scanner import Inventario
from database.database import BaseDatos
from inventory.discovery import Descubrimiento
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
def main():

    Sistema.mostrar_banner()

    print()

    if Sistema.comprobar_biblioteca():

        db = BaseDatos()

        db.crear_tablas()

        descubrimiento = Descubrimiento(Sistema.BIBLIOTECA)

        descubrimiento.detectar_personas()

        db.cerrar()

if __name__ == "__main__":

    app = QApplication([])

    ventana = MainWindow()

    ventana.show()

    app.exec()