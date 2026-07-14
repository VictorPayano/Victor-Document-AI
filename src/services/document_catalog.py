"""Catálogo local y rápido de los documentos almacenados en el NAS."""

import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path


class IndexacionCancelada(Exception):
    """La indexación fue cancelada por el usuario."""

    def __init__(self, total):
        self.total = total
        super().__init__(f"Indexación cancelada después de {total} documentos.")


class DocumentCatalog:
    EXTENSIONES = {".pdf", ".jpg", ".jpeg", ".png"}
    PATRON_FECHA = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
    PATRON_ANO = re.compile(r"(?:19|20)\d{2}")

    def __init__(self, ruta=None):
        self.ruta = Path(ruta) if ruta else (
            Path(__file__).resolve().parents[2] / "data" / "document_catalog.db"
        )
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._crear_esquema()

    def _conectar(self):
        conexion = sqlite3.connect(self.ruta, timeout=30)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA journal_mode=WAL")
        conexion.execute("PRAGMA busy_timeout=30000")
        return conexion

    @contextmanager
    def _conexion(self):
        conexion = self._conectar()
        try:
            with conexion:
                yield conexion
        finally:
            conexion.close()

    def _crear_esquema(self):
        with self._conexion() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    path TEXT PRIMARY KEY,
                    root_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    person TEXT NOT NULL DEFAULT '',
                    instance_1 TEXT NOT NULL DEFAULT '',
                    instance_2 TEXT NOT NULL DEFAULT '',
                    instance_3 TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    document_date TEXT NOT NULL DEFAULT '',
                    date_from_name INTEGER NOT NULL DEFAULT 0,
                    size INTEGER NOT NULL DEFAULT 0,
                    modified_ns INTEGER NOT NULL DEFAULT 0,
                    seen_token TEXT NOT NULL DEFAULT '',
                    indexed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_root
                    ON documents(root_path);
                CREATE INDEX IF NOT EXISTS idx_documents_person
                    ON documents(root_path, person);
                CREATE INDEX IF NOT EXISTS idx_documents_filters
                    ON documents(root_path, person, instance_1, instance_2, instance_3, year);
                CREATE INDEX IF NOT EXISTS idx_documents_date
                    ON documents(root_path, document_date);

                CREATE TABLE IF NOT EXISTS catalog_roots (
                    root_path TEXT PRIMARY KEY,
                    last_indexed TEXT NOT NULL,
                    document_count INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    @staticmethod
    def _clave_ruta(ruta):
        return os.path.normcase(os.path.abspath(str(Path(ruta))))

    @classmethod
    def _fecha_nombre(cls, nombre):
        coincidencia = cls.PATRON_FECHA.search(nombre)
        if not coincidencia:
            return ""
        try:
            return datetime.strptime(coincidencia.group(1), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return ""

    @classmethod
    def _registro(cls, archivo, raiz, estadisticas, token):
        archivo = Path(archivo)
        raiz = Path(raiz)
        relativo = archivo.relative_to(raiz)
        partes = relativo.parts
        persona = partes[0] if len(partes) > 1 else ""
        carpetas = list(partes[1:-1]) if len(partes) > 2 else []

        ano = ""
        for indice in range(len(carpetas) - 1, -1, -1):
            if cls.PATRON_ANO.fullmatch(carpetas[indice]):
                ano = carpetas.pop(indice)
                break

        fecha_nombre = cls._fecha_nombre(archivo.name)
        fecha = fecha_nombre or datetime.fromtimestamp(estadisticas.st_mtime).date().isoformat()
        if not ano:
            ano = fecha[:4]
        instancias = (carpetas + ["", "", ""])[:3]

        return (
            cls._clave_ruta(archivo),
            cls._clave_ruta(raiz),
            archivo.name,
            archivo.suffix.lower(),
            persona,
            instancias[0],
            instancias[1],
            instancias[2],
            ano,
            fecha,
            1 if fecha_nombre else 0,
            estadisticas.st_size,
            estadisticas.st_mtime_ns,
            token,
            datetime.now().isoformat(timespec="seconds"),
        )

    @staticmethod
    def _guardar_lote(db, registros):
        db.executemany(
            """
            INSERT INTO documents (
                path, root_path, name, extension, person,
                instance_1, instance_2, instance_3, year,
                document_date, date_from_name, size, modified_ns,
                seen_token, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                root_path = excluded.root_path,
                name = excluded.name,
                extension = excluded.extension,
                person = excluded.person,
                instance_1 = excluded.instance_1,
                instance_2 = excluded.instance_2,
                instance_3 = excluded.instance_3,
                year = excluded.year,
                document_date = excluded.document_date,
                date_from_name = excluded.date_from_name,
                size = excluded.size,
                modified_ns = excluded.modified_ns,
                seen_token = excluded.seen_token,
                indexed_at = excluded.indexed_at
            """,
            registros,
        )

    @classmethod
    def _recorrer(cls, raiz, cancelado):
        pendientes = [Path(raiz)]
        while pendientes:
            if cancelado and cancelado():
                raise IndexacionCancelada(0)
            carpeta = pendientes.pop()
            try:
                with os.scandir(carpeta) as elementos:
                    for elemento in elementos:
                        if cancelado and cancelado():
                            raise IndexacionCancelada(0)
                        try:
                            if elemento.is_dir(follow_symlinks=False):
                                pendientes.append(Path(elemento.path))
                            elif (
                                elemento.is_file(follow_symlinks=False)
                                and Path(elemento.name).suffix.lower() in cls.EXTENSIONES
                            ):
                                yield Path(elemento.path), elemento.stat(follow_symlinks=False)
                        except OSError:
                            continue
            except OSError:
                continue

    def indexar(self, raiz, progreso=None, cancelado=None, tamano_lote=250):
        raiz = Path(raiz)
        if not raiz.is_dir():
            raise FileNotFoundError(f"No se encontró la carpeta de documentos: {raiz}")

        raiz_clave = self._clave_ruta(raiz)
        token = uuid.uuid4().hex
        total = 0
        guardados = 0
        lote = []

        try:
            with self._conexion() as db:
                for archivo, estadisticas in self._recorrer(raiz, cancelado):
                    if cancelado and cancelado():
                        raise IndexacionCancelada(total)
                    lote.append(self._registro(archivo, raiz, estadisticas, token))
                    total += 1
                    if len(lote) >= tamano_lote:
                        cantidad_lote = len(lote)
                        self._guardar_lote(db, lote)
                        db.commit()
                        guardados += cantidad_lote
                        lote.clear()
                    if progreso and (total == 1 or total % 25 == 0):
                        progreso(total, archivo.name)

                if lote:
                    cantidad_lote = len(lote)
                    self._guardar_lote(db, lote)
                    db.commit()
                    guardados += cantidad_lote

                if cancelado and cancelado():
                    raise IndexacionCancelada(total)

                db.execute(
                    "DELETE FROM documents WHERE root_path = ? AND seen_token <> ?",
                    (raiz_clave, token),
                )
                db.execute(
                    """
                    INSERT INTO catalog_roots(root_path, last_indexed, document_count)
                    VALUES (?, ?, ?)
                    ON CONFLICT(root_path) DO UPDATE SET
                        last_indexed = excluded.last_indexed,
                        document_count = excluded.document_count
                    """,
                    (raiz_clave, datetime.now().isoformat(timespec="seconds"), total),
                )
                db.commit()
        except IndexacionCancelada as error:
            raise IndexacionCancelada(guardados) from error

        if progreso:
            progreso(total, "Completado")
        return total

    def agregar_documento(self, archivo, raiz):
        archivo = Path(archivo)
        raiz = Path(raiz)
        try:
            estadisticas = archivo.stat()
            registro = self._registro(archivo, raiz, estadisticas, "guardado")
        except (OSError, ValueError):
            return False
        if archivo.suffix.lower() not in self.EXTENSIONES:
            return False
        with self._conexion() as db:
            self._guardar_lote(db, [registro])
        return True

    def tiene_indice(self, raiz):
        with self._conexion() as db:
            fila = db.execute(
                "SELECT 1 FROM catalog_roots WHERE root_path = ?",
                (self._clave_ruta(raiz),),
            ).fetchone()
        return fila is not None

    def total(self, raiz):
        with self._conexion() as db:
            fila = db.execute(
                "SELECT COUNT(*) AS total FROM documents WHERE root_path = ?",
                (self._clave_ruta(raiz),),
            ).fetchone()
        return fila["total"]

    def personas(self, raiz):
        with self._conexion() as db:
            filas = db.execute(
                """
                SELECT DISTINCT person FROM documents
                WHERE root_path = ? AND person <> ''
                ORDER BY person COLLATE NOCASE
                """,
                (self._clave_ruta(raiz),),
            ).fetchall()
        return [fila["person"] for fila in filas]

    def metricas(self, raiz):
        hoy = date.today()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        raiz_clave = self._clave_ruta(raiz)
        with self._conexion() as db:
            fila = db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN date_from_name = 1 AND document_date = ? THEN 1 ELSE 0 END) AS hoy,
                    SUM(CASE WHEN date_from_name = 1 AND document_date >= ? THEN 1 ELSE 0 END) AS semana,
                    SUM(CASE WHEN date_from_name = 1 AND substr(document_date, 1, 7) = ? THEN 1 ELSE 0 END) AS mes,
                    SUM(CASE WHEN date_from_name = 0 THEN 1 ELSE 0 END) AS sin_fecha
                FROM documents WHERE root_path = ?
                """,
                (hoy.isoformat(), inicio_semana.isoformat(), hoy.strftime("%Y-%m"), raiz_clave),
            ).fetchone()
            personas = db.execute(
                """
                SELECT person, COUNT(*) AS total
                FROM documents
                WHERE root_path = ? AND person <> ''
                GROUP BY person
                ORDER BY total DESC, person COLLATE NOCASE
                LIMIT 10
                """,
                (raiz_clave,),
            ).fetchall()
            indice = db.execute(
                "SELECT last_indexed FROM catalog_roots WHERE root_path = ?",
                (raiz_clave,),
            ).fetchone()

        return {
            "total": fila["total"] or 0,
            "hoy": fila["hoy"] or 0,
            "semana": fila["semana"] or 0,
            "mes": fila["mes"] or 0,
            "sin_fecha": fila["sin_fecha"] or 0,
            "personas": [(item["person"], item["total"]) for item in personas],
            "ultima_indexacion": indice["last_indexed"] if indice else "",
        }

    def buscar(self, raiz, filtros, limite=2000):
        condiciones = ["root_path = ?"]
        parametros = [self._clave_ruta(raiz)]
        columnas = {
            "persona": "person",
            "instancia_1": "instance_1",
            "instancia_2": "instance_2",
            "instancia_3": "instance_3",
            "ano": "year",
        }
        for filtro, columna in columnas.items():
            valor = filtros.get(filtro, "")
            if valor:
                condiciones.append(f"{columna} = ?")
                parametros.append(valor)

        meses = filtros.get("meses") or []
        if meses:
            marcadores = ", ".join("?" for _ in meses)
            condiciones.append(f"substr(document_date, 6, 2) IN ({marcadores})")
            parametros.extend(meses)

        consulta = f"""
            SELECT path, name, person, instance_1, instance_2, instance_3,
                   document_date
            FROM documents
            WHERE {' AND '.join(condiciones)}
            ORDER BY document_date DESC, name COLLATE NOCASE
            LIMIT ?
        """
        parametros.append(limite)
        with self._conexion() as db:
            filas = db.execute(consulta, parametros).fetchall()

        resultados = []
        for fila in filas:
            instancias = " → ".join(
                valor for valor in (
                    fila["instance_1"], fila["instance_2"], fila["instance_3"]
                ) if valor
            )
            resultados.append((
                fila["document_date"],
                fila["person"],
                instancias,
                Path(fila["path"]),
            ))
        return resultados
