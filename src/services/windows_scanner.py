"""Captura una página con un escáner WIA de Windows y la convierte a PDF."""

import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from PIL import Image


class ScannerCancelled(Exception):
    pass


class WindowsScanner:
    def scan_to_pdf(self):
        folder = Path(tempfile.gettempdir()) / "Victor Document AI" / "scanner"
        folder.mkdir(parents=True, exist_ok=True)
        image_path = folder / f"scan_{uuid.uuid4().hex}.jpg"
        pdf_path = folder / f"scan_{uuid.uuid4().hex}.pdf"
        script = r'''
$ErrorActionPreference = 'Stop'
$output = $env:VICTOR_DOCUMENT_AI_SCAN_IMAGE
try {
  $dialog = New-Object -ComObject WIA.CommonDialog
  # El diálogo estándar permite seleccionar el escáner y sus opciones.
  $image = $dialog.ShowAcquireImage(1, 1, 0, $null, $true, $true, $false)
  if ($null -eq $image) { exit 2 }
  $image.SaveFile($output)
  if (-not (Test-Path -LiteralPath $output)) { throw 'El escáner no devolvió una imagen.' }
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
'''
        environment = os.environ.copy()
        environment["VICTOR_DOCUMENT_AI_SCAN_IMAGE"] = str(image_path)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=600,
        )
        if result.returncode == 2:
            raise ScannerCancelled("Escaneo cancelado.")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Windows no pudo iniciar el escáner WIA.")
        try:
            with Image.open(image_path) as image:
                image.convert("RGB").save(pdf_path, "PDF", resolution=200.0)
        except Exception as error:
            raise RuntimeError(f"No se pudo convertir el escaneo a PDF: {error}") from error
        finally:
            image_path.unlink(missing_ok=True)
        return pdf_path
