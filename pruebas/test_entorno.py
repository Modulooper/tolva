"""Dónde viven los datos: precedencia, fichero de configuración y avisos."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from motor import db, documentos, entorno, export, salidas


class BaseEntorno(unittest.TestCase):
    """Sin variables de entorno heredadas ni el config.local.json real: si no,
    la suite pasa o falla según cómo tenga configurada su máquina quien la
    ejecute, que es justo lo que no debe pasar."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="entorno_"))
        self.config = self.tmp / "config.local.json"
        self._original = entorno.FICHERO_CONFIG
        entorno.FICHERO_CONFIG = self.config
        variables = {v for v, _ in entorno.AJUSTES.values()}
        self._entorno = mock.patch.dict(
            os.environ, {k: v for k, v in os.environ.items() if k not in variables}, clear=True
        )
        self._entorno.start()

    def tearDown(self):
        self._entorno.stop()
        entorno.FICHERO_CONFIG = self._original


class PruebaPrecedencia(BaseEntorno):
    def test_sin_nada_valen_los_valores_por_defecto(self):
        self.assertEqual(entorno.ruta("datos"), entorno.ROOT / "datos")
        self.assertEqual(entorno.ruta("export"), entorno.ROOT / "export")
        self.assertEqual(entorno.origen("datos"), "valor por defecto")

    def test_los_documentos_cuelgan_del_almacen_si_no_se_dicen(self):
        """Mover el almacén tiene que mover los documentos con él: si no, la
        trazabilidad apunta a ficheros que no están donde dice la ficha."""
        entorno.escribir_config({"datos": "/sitio/nuevo"}, self.config)
        self.assertEqual(entorno.ruta("documentos"), Path("/sitio/nuevo/documentos"))

    def test_pero_los_documentos_se_pueden_separar(self):
        entorno.escribir_config({"datos": "/a", "documentos": "/b"}, self.config)
        self.assertEqual(entorno.ruta("documentos"), Path("/b"))

    def test_el_fichero_gana_al_valor_por_defecto(self):
        entorno.escribir_config({"datos": "/del/fichero"}, self.config)
        self.assertEqual(entorno.ruta("datos"), Path("/del/fichero"))
        self.assertEqual(entorno.origen("datos"), "config.local.json")

    def test_la_variable_gana_al_fichero(self):
        """La variable es para lo puntual: lanzar contra otro almacén sin
        tocar la configuración de la máquina."""
        entorno.escribir_config({"datos": "/del/fichero"}, self.config)
        with mock.patch.dict(os.environ, {"TOLVA_DATOS": "/de/la/variable"}):
            self.assertEqual(entorno.ruta("datos"), Path("/de/la/variable"))
            self.assertIn("TOLVA_DATOS", entorno.origen("datos"))

    def test_el_export_es_independiente_del_almacen(self):
        """Es la razón de que sean tres ajustes y no uno: sus requisitos son
        opuestos. El almacén fuera de la sincronización, el export a menudo
        dentro."""
        entorno.escribir_config({"datos": "/local"}, self.config)
        self.assertEqual(entorno.ruta("export"), entorno.ROOT / "export")


class PruebaFicheroDeConfig(BaseEntorno):
    def test_un_fichero_que_no_existe_no_es_un_error(self):
        self.assertEqual(entorno.config(self.config), {})

    def test_un_fichero_roto_se_ignora_en_vez_de_tumbarlo_todo(self):
        """Una coma de más en un fichero opcional no puede dejar sin arrancar
        todos los comandos; `db rutas` ya enseña de dónde sale cada valor."""
        self.config.write_text("{esto no es json", encoding="utf-8")
        self.assertEqual(entorno.config(self.config), {})
        self.assertEqual(entorno.ruta("datos"), entorno.ROOT / "datos")

    def test_escribir_conserva_lo_que_no_se_toca(self):
        entorno.escribir_config({"datos": "/a", "export": "/e"}, self.config)
        entorno.escribir_config({"datos": "/b"}, self.config)
        guardado = json.loads(self.config.read_text(encoding="utf-8"))
        # Comparado como rutas y no como texto: al guardar se normaliza el
        # separador, así que en Windows "/b" queda escrito como "\\b".
        self.assertEqual(
            {clave: Path(valor) for clave, valor in guardado.items()},
            {"datos": Path("/b"), "export": Path("/e")},
        )

    def test_un_valor_vacio_devuelve_el_ajuste_a_su_defecto(self):
        entorno.escribir_config({"export": "/e"}, self.config)
        entorno.escribir_config({"export": ""}, self.config)
        self.assertNotIn("export", json.loads(self.config.read_text(encoding="utf-8")))

    def test_un_ajuste_inventado_falla(self):
        with self.assertRaises(ValueError):
            entorno.escribir_config({"almacen_secreto": "/x"}, self.config)


class PruebaAvisoDeSincronizacion(BaseEntorno):
    def test_detecta_un_ancestro_sincronizado(self):
        """El sospechoso casi nunca es el último tramo, sino una carpeta de
        más arriba: `C:/Users/x/OneDrive - empresa/repo/datos`."""
        ruta = Path.home() / "OneDrive - empresa" / "repo" / "datos"
        self.assertEqual(entorno.carpeta_sincronizada(ruta), "OneDrive - empresa")

    def test_reconoce_varios_clientes(self):
        for carpeta in ("Dropbox", "Google Drive", "iCloud Drive", "Nextcloud"):
            with self.subTest(carpeta=carpeta):
                self.assertIsNotNone(
                    entorno.carpeta_sincronizada(Path.home() / carpeta / "datos")
                )

    def test_una_ruta_limpia_no_avisa(self):
        self.assertIsNone(entorno.carpeta_sincronizada(Path.home() / "datos_locales"))

    def test_avisa_del_almacen(self):
        entorno.escribir_config({"datos": str(Path.home() / "OneDrive" / "d")}, self.config)
        aviso = entorno.aviso_de_sincronizacion()
        self.assertIn("datos", aviso)
        self.assertIn("db init", aviso)  # un aviso que no dice qué hacer es ruido

    def test_no_avisa_del_export(self):
        """Que las exportaciones estén en una carpeta compartida suele ser
        justo lo que se busca: se abren desde Excel, puede que desde otra
        máquina, y si se corrompe una se regenera."""
        entorno.escribir_config({
            "datos": str(Path.home() / "local"),
            "documentos": str(Path.home() / "local" / "docs"),
            "export": str(Path.home() / "OneDrive" / "export"),
        }, self.config)
        self.assertIsNone(entorno.aviso_de_sincronizacion())


class PruebaDbInit(BaseEntorno):
    """El comando, no solo la función que escribe."""

    def _init(self, *argv):
        from motor import cli

        with contextlib.redirect_stdout(io.StringIO()):
            return cli.main(["db", "init", *argv])

    def test_fijar_un_ajuste_no_desconfigura_los_demas(self):
        """Fue un fallo de verdad: `db init` mandaba None por cada ajuste no
        indicado y `escribir_config` lee un valor presente y vacío como
        'devuélvelo a su defecto'. Fijar el respaldo devolvía el almacén a la
        carpeta del repo sin decir nada — el susto de 'se han perdido los
        datos' del docstring de este módulo, servido por el propio comando."""
        self.assertEqual(self._init("--datos", "/local"), 0)
        self.assertEqual(self._init("--respaldo", "/copias"), 0)
        guardado = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(
            {clave: Path(valor) for clave, valor in guardado.items()},
            {"datos": Path("/local"), "respaldo": Path("/copias")},
        )

    def test_cada_ajuste_tiene_su_bandera(self):
        """Las banderas se derivan de AJUSTES; añadir uno y olvidar cablearlo
        daba un 'no has indicado ninguna ruta' habiéndola indicado."""
        for clave in entorno.AJUSTES:
            with self.subTest(ajuste=clave):
                self.assertEqual(self._init(f"--{clave}", "/x"), 0)
                self.assertIn(clave, entorno.config(self.config))

    def test_sin_banderas_no_escribe_nada(self):
        self.assertEqual(self._init(), 1)
        self.assertFalse(self.config.exists())

    def test_una_ruta_vacia_si_limpia_el_ajuste(self):
        """Indicarlo vacío es indicarlo: es la vía para volver al defecto."""
        self._init("--datos", "/local")
        self._init("--datos", "")
        self.assertNotIn("datos", entorno.config(self.config))


class PruebaCableado(unittest.TestCase):
    """Que los módulos usen de verdad lo que dice `entorno`."""

    def test_cada_modulo_cuelga_del_ajuste_que_le_toca(self):
        self.assertEqual(db.DB_PATH.parent, entorno.ruta("datos"))
        self.assertEqual(documentos.DOCUMENTOS_DIR, entorno.ruta("documentos"))
        self.assertEqual(salidas.EXPORT_DIR, entorno.ruta("export"))
        self.assertEqual(export.EXPORT_DIR, entorno.ruta("export"))


if __name__ == "__main__":
    unittest.main()
