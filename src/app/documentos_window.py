from app.buscar_window import BuscarWindow


class DocumentosWindow(BuscarWindow):
    """Registro global: reutiliza los filtros y acciones del buscador."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Victor Document AI - Documentos")
        self.btn_buscar.setText("Cargar documentos")
        self.lbl_estado.setText(
            "Usa los filtros o pulsa Cargar documentos para ver el registro archivado."
        )
