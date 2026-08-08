"""Dónde viven los datos y el aviso de carpeta sincronizada."""

import os
import unittest
from pathlib import Path
from unittest import mock

from motor import db, documentos, entorno


class PruebaCarpetaDeDatos(unittest.TestCase):
    def test_por_defecto_cuelga_del_repositorio(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(entorno.datos_dir(), entorno.ROOT / "datos")

    def test_la_variable_de_entorno_la_mueve(self):
        with mock.patch.dict(os.environ, {entorno.VARIABLE: "/otro/sitio"}):
            self.assertEqual(entorno.datos_dir(), Path("/otro/sitio"))

    def test_el_almacen_y_los_documentos_cuelgan_de_la_misma_carpeta(self):
        """Mover los datos tiene que mover las dos cosas. Si el almacén se va
        y los documentos se quedan, la trazabilidad apunta a ficheros que no
        están donde dice la ficha."""
        self.assertEqual(db.DB_PATH.parent, documentos.DOCUMENTOS_DIR.parent)


class PruebaAvisoDeSincronizacion(unittest.TestCase):
    def test_detecta_un_ancestro_sincronizado(self):
        """El sospechoso casi nunca es el último tramo: es una carpeta de más
        arriba, como `C:/Users/x/OneDrive - empresa/repo/datos`."""
        ruta = Path.home() / "OneDrive - empresa" / "repo" / "datos"
        self.assertEqual(entorno.carpeta_sincronizada(ruta), "OneDrive - empresa")

    def test_reconoce_varios_clientes(self):
        for carpeta in ("Dropbox", "Google Drive", "iCloud Drive", "Nextcloud"):
            with self.subTest(carpeta=carpeta):
                self.assertIsNotNone(
                    entorno.carpeta_sincronizada(Path.home() / carpeta / "datos")
                )

    def test_una_ruta_limpia_no_avisa(self):
        ruta = Path.home() / "datos_locales" / "almacen"
        self.assertIsNone(entorno.carpeta_sincronizada(ruta))
        self.assertIsNone(entorno.aviso_de_sincronizacion(ruta))

    def test_el_aviso_dice_como_arreglarlo(self):
        """Un aviso que no dice qué hacer solo genera ruido."""
        aviso = entorno.aviso_de_sincronizacion(Path.home() / "OneDrive" / "datos")
        self.assertIn("OneDrive", aviso)
        self.assertIn(entorno.VARIABLE, aviso)

    def test_el_motor_no_imprime_el_aviso(self):
        """Lo devuelve para que lo imprima el CLI: el motor no escribe en
        consola, y así una carga programada no ensucia su log."""
        self.assertIsInstance(entorno.aviso_de_sincronizacion(Path("/limpio")), type(None))


if __name__ == "__main__":
    unittest.main()
