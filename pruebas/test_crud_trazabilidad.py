"""Invariantes de catálogo en las escrituras del CLI y encadenado de ejecuciones.

Antes esto se probaba sobre `ticket` e `idea`. Ahora el sujeto es el dominio
de ejemplo (`ejemplos/`), y no por gusto: mientras la batería del framework
dependiera de dos procesos de negocio concretos, esos procesos no se podían
sacar del núcleo. Lo que se comprueba aquí no es la librería, es que un
invariante declarado en una ficha rige venga la escritura de donde venga, y
que la vida de un registro queda encadenada en `_ejecuciones`.

Del CRUD en sí se ocupa `test_registros.py`.
"""

import json

from motor import ejecuciones, registros, validaciones
from pruebas.base import PruebaConAlmacen


class BaseCrud(PruebaConAlmacen):
    def setUp(self):
        super().setUp()
        # La migración de ejemplo siembra ventas; lo que cuenta cada prueba es
        # lo que ella misma escribe, no el material de partida.
        self.ventas_iniciales = self.escalar("SELECT count(*) FROM demo_venta")

    def crear_venta(self, **extra):
        campos = dict(
            demo_cliente="Ateneo Mercantil", demo_libro="El jardín de arena",
            fecha="2026-07-01", unidades="2", importe="39.00", canal="tienda",
        )
        campos.update(extra)
        return registros.crear(self.con, "demo_venta", campos)

    def ventas_nuevas(self):
        return self.escalar("SELECT count(*) FROM demo_venta") - self.ventas_iniciales


class PruebaCrud(BaseCrud):
    def test_alta_resuelve_las_referencias_por_nombre(self):
        venta_id, _ = self.crear_venta()
        self.assertEqual(
            self.escalar("SELECT count(*) FROM demo_venta WHERE id = ?", [venta_id]), 1
        )

    def test_resolucion_no_distingue_mayusculas(self):
        venta_id, _ = self.crear_venta(demo_cliente="ateneo mercantil")
        self.assertIsNotNone(venta_id)

    def test_referencia_inexistente_falla(self):
        with self.assertRaises(ValueError):
            self.crear_venta(demo_cliente="No Existe")

    def test_valor_fuera_de_la_lista_del_catalogo_falla(self):
        with self.assertRaises(ValueError):
            self.crear_venta(canal="telepatia")

    def test_editar_y_borrar(self):
        venta_id, _ = self.crear_venta()
        registros.editar(self.con, "demo_venta", venta_id, {"importe": "99.0"})
        self.assertEqual(
            self.escalar("SELECT importe FROM demo_venta WHERE id = ?", [venta_id]), 99.0
        )
        registros.borrar(self.con, "demo_venta", venta_id)
        self.assertEqual(self.ventas_nuevas(), 0)

    def test_editar_inexistente_falla(self):
        with self.assertRaises(ValueError):
            registros.editar(
                self.con, "demo_venta", "00000000-0000-0000-0000-000000000000",
                {"importe": "1.0"},
            )

    def test_una_referencia_opcional_puede_quedarse_vacia(self):
        venta_id, _ = self.crear_venta(demo_cliente="")
        self.assertIsNone(
            self.escalar("SELECT demo_cliente_id FROM demo_venta WHERE id = ?", [venta_id])
        )


class PruebaInvariantesDeCatalogo(BaseCrud):
    def test_stop_del_catalogo_revierte_la_escritura(self):
        """Un invariante declarado en una ficha rige también para el CLI.

        La ficha se copia a la capa propia del temporal en vez de tocar la de
        ejemplos: en caso de mismo nombre gana la propia, así que la prueba
        sustituye la ficha sin escribir en el repo.
        """
        from motor import catalogo

        ficha = catalogo.cargar_entidad("demo_venta")
        ficha["validaciones"] = [{
            "nombre": "importe_maximo", "tipo": "stop",
            "sql": "SELECT id, importe FROM demo_venta WHERE importe > 100",
            "mensaje": "importe por encima del máximo permitido",
        }]
        (self.carpeta_propia("catalogo") / "demo_venta.json").write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaises(validaciones.StopError):
            self.crear_venta(importe="500.0")
        self.assertEqual(self.ventas_nuevas(), 0)

        # El intento fallido queda registrado aunque la fila no se escribiera.
        self.assertEqual(
            self.escalar(
                "SELECT count(*) FROM _ejecuciones "
                "WHERE carga = 'demo_venta.crear' AND estado = 'ERROR'"
            ),
            1,
        )


class PruebaTrazabilidad(BaseCrud):
    def test_creacion_sella_ejecucion_en_la_fila(self):
        venta_id, _ = self.crear_venta()
        ejecucion = self.escalar("SELECT ejecucion_id FROM demo_venta WHERE id = ?", [venta_id])
        self.assertIsNotNone(ejecucion)
        self.assertEqual(
            self.filas("SELECT carga, tipo FROM _ejecuciones WHERE id = ?", [ejecucion]),
            [("demo_venta.crear", "cli")],
        )

    def test_toda_ejecucion_tiene_principal_y_la_creacion_se_apunta_a_si_misma(self):
        venta_id, _ = self.crear_venta()
        ejecucion = self.escalar("SELECT ejecucion_id FROM demo_venta WHERE id = ?", [venta_id])
        self.assertEqual(
            self.escalar("SELECT ejecucion_id_principal FROM _ejecuciones WHERE id = ?", [ejecucion]),
            ejecucion,
        )
        self.assertEqual(
            self.escalar("SELECT count(*) FROM _ejecuciones WHERE ejecucion_id_principal IS NULL"), 0
        )

    def test_editar_no_toca_la_fila_y_se_encadena(self):
        venta_id, _ = self.crear_venta()
        creacion = self.escalar("SELECT ejecucion_id FROM demo_venta WHERE id = ?", [venta_id])
        registros.editar(self.con, "demo_venta", venta_id, {"importe": "30.0"})
        registros.editar(self.con, "demo_venta", venta_id, {"canal": "web"})

        self.assertEqual(
            self.escalar("SELECT ejecucion_id FROM demo_venta WHERE id = ?", [venta_id]), creacion
        )
        columnas, filas = ejecuciones.historial(self.con, creacion)
        operaciones = [f[columnas.index("operacion")] for f in filas]
        self.assertEqual(
            operaciones, ["demo_venta.crear", "demo_venta.editar", "demo_venta.editar"]
        )

    def test_borrar_cierra_la_cadena_del_registro(self):
        venta_id, _ = self.crear_venta()
        creacion = self.escalar("SELECT ejecucion_id FROM demo_venta WHERE id = ?", [venta_id])
        registros.borrar(self.con, "demo_venta", venta_id)
        _, filas = ejecuciones.historial(self.con, creacion)
        self.assertEqual(len(filas), 2)

    def test_fila_sin_ejecucion_previa_no_inventa_cadena(self):
        """Las filas anteriores al registro de ejecuciones tienen ejecucion_id
        nulo, y a una modificación posterior no se le inventa una creación."""
        self.con.execute(
            "INSERT INTO demo_venta (fecha, unidades, importe, canal, ejecucion_id) "
            "VALUES (DATE '2020-01-01', 1, 5.0, 'tienda', NULL)"
        )
        venta_id = self.escalar(
            "SELECT id FROM demo_venta WHERE ejecucion_id IS NULL AND fecha = DATE '2020-01-01'"
        )
        self.assertIsNone(ejecuciones.principal_de(self.con, "demo_venta", venta_id))
        registros.editar(self.con, "demo_venta", venta_id, {"canal": "web"})
        ultima = self.escalar("SELECT max(id) FROM _ejecuciones")
        self.assertEqual(
            self.escalar("SELECT ejecucion_id_principal FROM _ejecuciones WHERE id = ?", [ultima]),
            ultima,
        )
