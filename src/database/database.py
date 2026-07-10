import sqlite3
from pathlib import Path


class BaseDatos:

    def __init__(self):

        self.ruta = Path("data/database/victor_document_ai.db")

        self.conexion = sqlite3.connect(self.ruta)

        self.cursor = self.conexion.cursor()

    def crear_tablas(self):

        # =========================
        # PERSONAS
        # =========================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS personas (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT NOT NULL,

            apellido TEXT,

            nombre_completo TEXT,

            fecha_nacimiento TEXT,

            tipo_persona TEXT,

            activo INTEGER DEFAULT 1,

            notas TEXT

        )
        """)

        # =========================
        # CATEGORIAS
        # =========================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT UNIQUE

        )
        """)

        # =========================
        # EMPRESAS
        # =========================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT UNIQUE

        )
        """)

        # =========================
        # CONFIGURACION
        # =========================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (

            clave TEXT PRIMARY KEY,

            valor TEXT

        )
        """)
        # =========================
        # ENTIDADES
        # =========================

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS entidades (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre_original TEXT NOT NULL,

            nombre_normalizado TEXT NOT NULL,

            tipo TEXT DEFAULT 'DESCONOCIDO',

            grupo TEXT,

            importar INTEGER DEFAULT 1,

            activo INTEGER DEFAULT 1,

            notas TEXT,

            UNIQUE(nombre_normalizado)

        )
        """)
        self.conexion.commit()

        print("✅ Base de datos preparada.")

    def cerrar(self):

        self.conexion.close()