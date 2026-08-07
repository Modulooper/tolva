"""Diagrama del modelo generado del catálogo."""

import json

from motor import catalogo, diagrama
from pruebas.base import PruebaConAlmacen


class PruebaDiagrama(PruebaConAlmacen):
    def test_incluye_todas_las_entidades_del_catalogo(self):
        salida = diagrama.mermaid()
        self.assertTrue(salida.startswith("erDiagram"))
        for nombre in catalogo.listar_entidades():
            with self.subTest(entidad=nombre):
                self.assertIn(f"    {catalogo.cargar_entidad(nombre)['tabla']} {{", salida)

    def test_solo_las_relaciones_declaradas_marcan_clave_ajena(self):
        """Deducir la FK del sufijo '_id' da falsos positivos.

        El caso real que lo motivó era `previ_transporte.oracle_carrier_id`,
        un código del sistema de origen que no apunta a ninguna tabla. Vive en
        la capa propia, así que aquí se reproduce con una ficha sintética: una
        prueba del framework no puede depender de la carga de nadie.
        """
        self.escribir_catalogo(self.ficha_catalogo("albaran", {
            "id": ("uuid", True),
            "demo_cliente_id": ("uuid", True),         # sí tiene relación declarada
            "carrier_externo_id": ("integer", False),  # código ajeno, no es FK
        }, relaciones=[
            {"campo": "demo_cliente_id", "entidad_destino": "demo_cliente",
             "campo_destino": "id", "tipo": "N:1"},
        ]))

        salida = diagrama.mermaid()
        self.assertIn("string demo_cliente_id FK", salida)
        self.assertIn("int carrier_externo_id", salida)
        self.assertNotIn("carrier_externo_id FK", salida)

    def test_cardinalidad_segun_obligatoriedad(self):
        self.escribir_catalogo(self.ficha_catalogo("albaran", {
            "id": ("uuid", True),
            "demo_cliente_id": ("uuid", True),
        }, relaciones=[
            {"campo": "demo_cliente_id", "entidad_destino": "demo_cliente",
             "campo_destino": "id", "tipo": "N:1"},
        ]))
        salida = diagrama.mermaid(con_ejemplos=True)
        self.assertIn("albaran }|--|| demo_cliente : demo_cliente_id", salida)     # obligatoria
        self.assertIn("demo_venta }o--|| demo_cliente : demo_cliente_id", salida)  # opcional

    def test_el_dominio_de_ejemplo_no_sale_en_el_diagrama_por_defecto(self):
        """El diagrama es del modelo, no del material de prueba."""
        self.assertNotIn("demo_venta", diagrama.mermaid())
        self.assertIn("demo_venta", diagrama.mermaid(con_ejemplos=True))

    def test_campos_de_sistema_solo_con_completo(self):
        self.assertNotIn("created_at", diagrama.mermaid(con_ejemplos=True))
        self.assertIn("created_at", diagrama.mermaid(completo=True, con_ejemplos=True))

    def test_instalacion_limpia_no_tiene_desajustes(self):
        self.assertEqual(diagrama.desajustes(self.con), [])

    def test_detecta_tabla_sin_ficha_de_catalogo(self):
        self.con.execute("CREATE TABLE huerfana (id INTEGER)")
        avisos = diagrama.desajustes(self.con)
        self.assertTrue(any("huerfana" in a for a in avisos), avisos)

    def test_detecta_campo_del_catalogo_que_no_existe_en_la_tabla(self):
        # La ficha retocada va a la capa propia, que gana por nombre sobre la
        # de `ejemplos/`: así no hay que tocar la del repo.
        ficha = catalogo.cargar_entidad("demo_cliente")
        ficha["campos"]["inventado"] = {
            "tipo": "varchar", "obligatorio": False, "descripcion": "no existe", "sinonimos": []
        }
        (self.carpeta_propia("catalogo") / "demo_cliente.json").write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8"
        )
        avisos = diagrama.desajustes(self.con)
        self.assertTrue(any("demo_cliente.inventado" in a for a in avisos), avisos)

    def test_resumen_trae_la_descripcion_del_catalogo(self):
        resumen = dict((t, d) for t, d, _ in diagrama.resumen(con_ejemplos=True))
        self.assertIn("libros", resumen["demo_cliente"])
