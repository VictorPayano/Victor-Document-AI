import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from services.document_catalog import DocumentCatalog, IndexacionCancelada


class DocumentCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.base = Path(self.temporal.name)
        self.raiz = self.base / "Personas"
        self.catalogo = DocumentCatalog(self.base / "catalogo.db")

    def tearDown(self):
        self.temporal.cleanup()

    @staticmethod
    def _crear(ruta, contenido=b"pdf", fecha=None):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
        if fecha:
            marca = datetime.fromisoformat(fecha).timestamp()
            os.utime(ruta, (marca, marca))
        return ruta

    def test_indexa_metricas_y_busqueda_sin_abrir_documentos(self):
        self._crear(
            self.raiz / "Ana" / "Banco" / "Facturas" / "2024" / "2024-05-03_luz.pdf"
        )
        self._crear(
            self.raiz / "Beto" / "Seguro" / "2023" / "documento.pdf",
            fecha="2023-11-10T10:00:00",
        )

        self.assertEqual(self.catalogo.indexar(self.raiz), 2)
        metricas = self.catalogo.metricas(self.raiz)
        self.assertEqual(metricas["total"], 2)
        self.assertEqual(metricas["sin_fecha"], 1)
        self.assertEqual(self.catalogo.personas(self.raiz), ["Ana", "Beto"])

        resultados = self.catalogo.buscar(self.raiz, {
            "persona": "Ana",
            "instancia_1": "Banco",
            "instancia_2": "Facturas",
            "instancia_3": "",
            "ano": "2024",
            "meses": ["05"],
        })
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0][0], "2024-05-03")
        self.assertEqual(resultados[0][2], "Banco → Facturas")

    def test_actualiza_y_elimina_registros_que_ya_no_existen(self):
        antiguo = self._crear(self.raiz / "Ana" / "Banco" / "2024" / "antiguo.pdf")
        self.catalogo.indexar(self.raiz)
        antiguo.unlink()
        nuevo = self._crear(self.raiz / "Ana" / "Banco" / "2025" / "nuevo.pdf")

        self.catalogo.indexar(self.raiz)
        resultados = self.catalogo.buscar(self.raiz, {
            "persona": "", "instancia_1": "", "instancia_2": "",
            "instancia_3": "", "ano": "", "meses": [],
        })
        self.assertEqual([item[3] for item in resultados], [nuevo])

    def test_agrega_un_documento_nuevo_sin_reindexar_el_nas(self):
        archivo = self._crear(
            self.raiz / "Clara" / "Gemeente" / "2026" / "2026-07-14_carta.pdf"
        )
        self.assertTrue(self.catalogo.agregar_documento(archivo, self.raiz))
        self.assertEqual(self.catalogo.total(self.raiz), 1)

    def test_cancelacion_conserva_los_lotes_ya_guardados(self):
        for numero in range(3):
            self._crear(self.raiz / "Ana" / "Banco" / "2024" / f"{numero}.pdf")
        cancelar = False

        def progreso(_total, _nombre):
            nonlocal cancelar
            cancelar = True

        with self.assertRaises(IndexacionCancelada):
            self.catalogo.indexar(
                self.raiz,
                progreso=progreso,
                cancelado=lambda: cancelar,
                tamano_lote=1,
            )
        self.assertGreaterEqual(self.catalogo.total(self.raiz), 1)


if __name__ == "__main__":
    unittest.main()
