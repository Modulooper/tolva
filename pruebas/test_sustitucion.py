"""Sustitución de variables en el SQL de una carga.

Casi todas estas pruebas existen por la misma razón: la forma fácil de hacer
esto es pegar cadenas, y la forma fácil rompe en cuanto un valor lleva una
comilla o el SQL lleva un `$` que no era una variable. Cada caso raro de aquí
es un fallo que aparecería lejos de su causa.
"""

import unittest

from motor import sustitucion


class PruebaDeteccion(unittest.TestCase):
    def test_encuentra_las_variables_en_orden(self):
        self.assertEqual(
            sustitucion.nombres_usados("SELECT $a, $b FROM t WHERE c = $a"),
            ["a", "b", "a"],
        )

    def test_no_toca_lo_que_hay_dentro_de_comillas_simples(self):
        self.assertEqual(sustitucion.nombres_usados("SELECT 'cuesta $v_total euros'"), [])

    def test_una_comilla_escapada_no_cierra_el_literal(self):
        """'O''Donnell' es un solo literal: si se creyera cerrado en la comilla
        del medio, el `$v_x` de después se tomaría por variable."""
        self.assertEqual(
            sustitucion.nombres_usados("SELECT 'O''Donnell $v_x', $v_y"), ["v_y"]
        )

    def test_no_toca_los_identificadores_entrecomillados(self):
        self.assertEqual(sustitucion.nombres_usados('SELECT "col $v_x" FROM t'), [])

    def test_no_toca_las_cadenas_con_comillas_de_dolar(self):
        """`$$texto$$` es un literal de DuckDB, no dos variables."""
        self.assertEqual(sustitucion.nombres_usados("SELECT $$hola $v_x$$"), [])
        self.assertEqual(sustitucion.nombres_usados("SELECT $tag$hola $v_x$tag$"), [])

    def test_no_toca_los_comentarios(self):
        self.assertEqual(sustitucion.nombres_usados("SELECT 1 -- ojo con $v_x\n"), [])
        self.assertEqual(sustitucion.nombres_usados("SELECT /* $v_x */ 1"), [])

    def test_no_confunde_un_marcador_posicional(self):
        """`$1` es de DuckDB y un dígito no puede empezar un nombre."""
        self.assertEqual(sustitucion.nombres_usados("SELECT $1, $v_x"), ["v_x"])


class PruebaResolucion(unittest.TestCase):
    def test_sin_variables_no_cambia_nada(self):
        self.assertEqual(sustitucion.resolver("SELECT 1", {}), ("SELECT 1", []))

    def test_enlaza_en_vez_de_interpolar(self):
        sql, valores = sustitucion.resolver(
            "SELECT * FROM t WHERE id = $ejecucion_id", {"ejecucion_id": 42}
        )
        self.assertEqual(sql, "SELECT * FROM t WHERE id = ?")
        self.assertEqual(valores, [42])

    def test_repetida_se_enlaza_las_veces_que_aparece(self):
        """Un marcador por aparición: si se dedujera, el número de valores no
        cuadraría con el de `?` y el fallo saldría en el driver."""
        sql, valores = sustitucion.resolver("SELECT $a WHERE b = $a", {"a": 7})
        self.assertEqual(sql.count("?"), 2)
        self.assertEqual(valores, [7, 7])

    def test_conserva_intacto_lo_que_no_se_sustituye(self):
        sql, valores = sustitucion.resolver(
            "SELECT 'literal $v_x', $$dolar $v_y$$, $v_z -- $v_w",
            {"v_z": 1, "v_x": 2, "v_y": 3, "v_w": 4},
        )
        self.assertEqual(valores, [1])
        self.assertIn("'literal $v_x'", sql)
        self.assertIn("$$dolar $v_y$$", sql)
        self.assertIn("-- $v_w", sql)

    def test_variable_desconocida_falla_diciendo_cuales_hay(self):
        with self.assertRaises(sustitucion.VariableDesconocida) as capturado:
            sustitucion.resolver("SELECT $v_inventada", {"ejecucion_id": 1})
        mensaje = str(capturado.exception)
        self.assertIn("$v_inventada", mensaje)
        self.assertIn("$ejecucion_id", mensaje)


class PruebaContexto(unittest.TestCase):
    def test_las_tres_familias_de_nombres(self):
        contexto = sustitucion.contexto_de(
            ejecucion_id=9, carga="ventas",
            parametros={"tienda": "abc"}, variables={"total": 100},
        )
        self.assertEqual(contexto["ejecucion_id"], 9)
        self.assertEqual(contexto["p_tienda"], "abc")
        self.assertEqual(contexto["v_total"], 100)

    def test_lo_no_aportado_no_aparece(self):
        """Mejor 'variable no definida' que un nulo silencioso: si $promovidas
        aún no existe en ese momento del ciclo, hay que decirlo."""
        self.assertNotIn("promovidas", sustitucion.contexto_de(ejecucion_id=1))


class PruebaContraDuckDB(unittest.TestCase):
    """Que DuckDB acepte de verdad lo que sale de aquí, con sus tipos."""

    def setUp(self):
        import duckdb

        self.con = duckdb.connect(":memory:")

    def tearDown(self):
        self.con.close()

    def test_un_valor_con_comilla_no_rompe_el_sql(self):
        """El caso que justifica todo el módulo."""
        cursor = sustitucion.ejecutar(
            self.con, "SELECT $v_nombre AS n", {"v_nombre": "O'Donnell"}
        )
        self.assertEqual(cursor.fetchone()[0], "O'Donnell")

    def test_los_tipos_viajan_sin_serializarse(self):
        from datetime import date

        cursor = sustitucion.ejecutar(
            self.con,
            "SELECT $v_fecha AS f, $v_num AS n, $v_nulo AS z",
            {"v_fecha": date(2026, 3, 1), "v_num": 12.5, "v_nulo": None},
        )
        self.assertEqual(cursor.fetchone(), (date(2026, 3, 1), 12.5, None))


if __name__ == "__main__":
    unittest.main()
