"""Qué cuenta como núcleo, y qué dice el aviso cuando alguien lo toca.

Estas pruebas no hablan con git: `nucleo_modificado` sí, pero lo que hay que
fijar aquí es la **clasificación** —esto es framework, esto es tuyo— y que el
hook no se ponga a hablar cuando no debe. Un hook ruidoso se desactiva a los
dos días y entonces no protege de nada.
"""

import json
import tempfile
import unittest
from pathlib import Path

from motor import aportaciones, entorno

ROOT = aportaciones.ROOT


class BaseSinConfig(unittest.TestCase):
    """Sin el `config.local.json` real: si no, la suite pasa o falla según
    tenga o no marcada como mantenedora la máquina de quien la ejecuta."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aportaciones_"))
        self._original = entorno.FICHERO_CONFIG
        entorno.FICHERO_CONFIG = self.tmp / "config.local.json"

    def tearDown(self):
        entorno.FICHERO_CONFIG = self._original

    def marcar_mantenedor(self):
        entorno.FICHERO_CONFIG.write_text(
            json.dumps({"mantenedor": True}), encoding="utf-8")


class TestClasificacion(BaseSinConfig):

    def test_el_codigo_del_motor_es_nucleo(self):
        self.assertTrue(aportaciones.es_del_nucleo(ROOT / "motor" / "salidas.py"))

    def test_las_migraciones_y_el_catalogo_del_repo_son_nucleo(self):
        self.assertTrue(aportaciones.es_del_nucleo(ROOT / "migraciones" / "001_nucleo.sql"))
        self.assertTrue(aportaciones.es_del_nucleo(ROOT / "catalogo" / "cualquiera.json"))

    def test_los_skills_son_nucleo(self):
        # Son el diferencial del proyecto y se distribuyen con él: una mejora
        # ahí interesa tanto como una del motor.
        self.assertTrue(
            aportaciones.es_del_nucleo(ROOT / ".claude" / "skills" / "definir-carga" / "SKILL.md"))

    def test_la_documentacion_de_la_raiz_es_nucleo(self):
        self.assertTrue(aportaciones.es_del_nucleo(ROOT / "README.md"))
        self.assertTrue(aportaciones.es_del_nucleo(ROOT / "CLAUDE.md"))

    def test_la_capa_propia_no_es_nucleo(self):
        # Es el caso que justifica todo el módulo: escribir aquí es lo normal
        # y no debe avisar de nada.
        self.assertFalse(
            aportaciones.es_del_nucleo(ROOT / "propio" / "migraciones" / "010_tarea.sql"))
        self.assertFalse(aportaciones.es_del_nucleo(ROOT / "propio" / "catalogo" / "tarea.json"))

    def test_los_datos_y_las_salidas_no_son_nucleo(self):
        self.assertFalse(aportaciones.es_del_nucleo(ROOT / "datos" / "almacen.duckdb"))
        self.assertFalse(aportaciones.es_del_nucleo(ROOT / "export" / "ventas.xlsx"))
        self.assertFalse(aportaciones.es_del_nucleo(ROOT / "entrada" / "banco" / "marzo.csv"))

    def test_un_fichero_de_fuera_del_repositorio_no_es_nucleo(self):
        # El asistente puede estar escribiendo en cualquier sitio de la
        # máquina, y eso no es asunto de este módulo.
        self.assertFalse(aportaciones.es_del_nucleo(self.tmp / "cualquier_cosa.py"))

    def test_un_fichero_suelto_en_la_raiz_no_declarado_no_es_nucleo(self):
        # Un borrador o unas notas en la raíz no son el framework.
        self.assertFalse(aportaciones.es_del_nucleo(ROOT / "notas_sueltas.md"))

    def test_sin_ruta_no_es_nucleo(self):
        self.assertFalse(aportaciones.es_del_nucleo(None))
        self.assertFalse(aportaciones.es_del_nucleo(""))


class TestHook(BaseSinConfig):

    def payload(self, ruta) -> str:
        return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(ruta)}})

    def test_avisa_al_escribir_en_el_nucleo(self):
        mensaje = aportaciones.mensaje_para_hook(self.payload(ROOT / "motor" / "salidas.py"))
        self.assertIn("núcleo de Tolva", mensaje)
        # Las dos salidas posibles tienen que estar planteadas, porque el aviso
        # sirve igual para el error (esto iba a propio/) que para la aportación.
        self.assertIn("propio/", mensaje)
        self.assertIn("rama aparte", mensaje)

    def test_calla_al_escribir_en_la_capa_propia(self):
        self.assertIsNone(
            aportaciones.mensaje_para_hook(self.payload(ROOT / "propio" / "cargas" / "x.json")))

    def test_calla_para_el_mantenedor(self):
        self.marcar_mantenedor()
        self.assertIsNone(
            aportaciones.mensaje_para_hook(self.payload(ROOT / "motor" / "salidas.py")))

    def test_un_payload_ilegible_no_dice_nada(self):
        # Un hook que se pone a hablar por un payload que no reconoce es ruido,
        # y el resumen de fin de sesión ya cubre el caso por otra vía.
        for basura in ("", "no soy json", "[]", "null", json.dumps({"tool_input": {}})):
            self.assertIsNone(aportaciones.mensaje_para_hook(basura))


class TestAviso(BaseSinConfig):

    def test_sin_nada_tocado_no_hay_aviso(self):
        estado = {"sin_confirmar": [], "sin_enviar": [], "rama": "main"}
        self.assertIsNone(aportaciones.aviso_de_nucleo(estado))

    def test_avisa_de_lo_sin_confirmar_y_de_lo_sin_enviar(self):
        estado = {"sin_confirmar": ["motor/salidas.py"],
                  "sin_enviar": ["cargas/demo.json"], "rama": "aporte/formatos"}
        aviso = aportaciones.aviso_de_nucleo(estado)
        self.assertIn("2 fichero(s)", aviso)
        self.assertIn("motor/salidas.py", aviso)

    def test_en_la_rama_principal_recuerda_ramificar(self):
        # El argumento que hace que la gente lo mande de verdad no es el altruismo,
        # es que sin rama el próximo 'git pull' les da un conflicto.
        en_main = aportaciones.aviso_de_nucleo(
            {"sin_confirmar": ["motor/salidas.py"], "sin_enviar": [], "rama": "main"})
        self.assertIn("rama principal", en_main)
        en_rama = aportaciones.aviso_de_nucleo(
            {"sin_confirmar": ["motor/salidas.py"], "sin_enviar": [], "rama": "aporte/x"})
        self.assertNotIn("rama principal", en_rama)

    def test_el_mantenedor_no_recibe_aviso(self):
        self.marcar_mantenedor()
        estado = {"sin_confirmar": ["motor/salidas.py"], "sin_enviar": [], "rama": "main"}
        self.assertIsNone(aportaciones.aviso_de_nucleo(estado))


if __name__ == "__main__":
    unittest.main()
