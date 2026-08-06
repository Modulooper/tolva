"""CRUD del CLI, invariantes de catálogo y encadenado de ejecuciones."""

import json
from datetime import date

from motor import ejecuciones, ideas, tickets, validaciones
from pruebas.base import PruebaConAlmacen


class BaseCrud(PruebaConAlmacen):
    def setUp(self):
        super().setUp()
        self.con.execute("INSERT INTO persona (nombre) VALUES ('Nacho')")
        self.con.execute("INSERT INTO cliente (nombre) VALUES ('Interno')")

    def crear_ticket(self, **extra):
        campos = dict(
            cliente="Interno", persona="Nacho", concepto="viajes",
            importe=20.5, fecha=date(2026, 8, 5),
        )
        campos.update(extra)
        return tickets.crear(self.con, **campos)


class PruebaCrud(BaseCrud):
    def test_alta_resuelve_cliente_y_persona_por_nombre(self):
        ticket_id, _ = self.crear_ticket()
        self.assertEqual(self.escalar("SELECT count(*) FROM ticket WHERE id = ?", [ticket_id]), 1)

    def test_resolucion_no_distingue_mayusculas(self):
        ticket_id, _ = self.crear_ticket(cliente="interno")
        self.assertIsNotNone(ticket_id)

    def test_cliente_inexistente_falla(self):
        with self.assertRaises(ValueError):
            self.crear_ticket(cliente="No Existe")

    def test_concepto_fuera_de_la_lista_falla(self):
        with self.assertRaises(ValueError):
            self.crear_ticket(concepto="submarinismo")

    def test_concepto_otros_es_valido(self):
        """El catálogo y el CHECK de la tabla deben coincidir (migración 006)."""
        ticket_id, _ = self.crear_ticket(concepto="otros")
        self.assertIsNotNone(ticket_id)

    def test_editar_y_borrar(self):
        ticket_id, _ = self.crear_ticket()
        tickets.editar(self.con, ticket_id, importe=99.0)
        self.assertEqual(self.escalar("SELECT importe FROM ticket WHERE id = ?", [ticket_id]), 99.0)
        tickets.borrar(self.con, ticket_id)
        self.assertEqual(self.escalar("SELECT count(*) FROM ticket"), 0)

    def test_editar_inexistente_falla(self):
        with self.assertRaises(ValueError):
            tickets.editar(self.con, "00000000-0000-0000-0000-000000000000", importe=1.0)

    def test_idea_sin_cliente_es_valida(self):
        idea_id, _ = ideas.crear(self.con, persona="Nacho", texto="una idea suelta")
        self.assertIsNone(self.escalar("SELECT cliente_id FROM idea WHERE id = ?", [idea_id]))


class PruebaInvariantesDeCatalogo(BaseCrud):
    def test_stop_del_catalogo_revierte_la_escritura(self):
        """Un invariante declarado en /catalogo rige también para el CLI."""
        ficha = json.loads((self.catalogo_dir / "ticket.json").read_text(encoding="utf-8"))
        ficha["validaciones"] = [{
            "nombre": "importe_maximo", "tipo": "stop",
            "sql": "SELECT id, importe FROM ticket WHERE importe > 100",
            "mensaje": "importe por encima del máximo permitido",
        }]
        (self.catalogo_dir / "ticket.json").write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaises(validaciones.StopError):
            self.crear_ticket(importe=500.0)
        self.assertEqual(self.escalar("SELECT count(*) FROM ticket"), 0)

        # El intento fallido queda registrado aunque la fila no se escribiera.
        self.assertEqual(
            self.escalar("SELECT count(*) FROM _ejecuciones WHERE carga = 'ticket.crear' AND estado = 'ERROR'"),
            1,
        )


class PruebaTrazabilidad(BaseCrud):
    def test_creacion_sella_ejecucion_en_la_fila(self):
        ticket_id, _ = self.crear_ticket()
        ejecucion = self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id])
        self.assertIsNotNone(ejecucion)
        self.assertEqual(
            self.filas("SELECT carga, tipo FROM _ejecuciones WHERE id = ?", [ejecucion]),
            [("ticket.crear", "cli")],
        )

    def test_toda_ejecucion_tiene_principal_y_la_creacion_se_apunta_a_si_misma(self):
        ticket_id, _ = self.crear_ticket()
        ejecucion = self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id])
        self.assertEqual(
            self.escalar("SELECT ejecucion_id_principal FROM _ejecuciones WHERE id = ?", [ejecucion]),
            ejecucion,
        )
        self.assertEqual(self.escalar("SELECT count(*) FROM _ejecuciones WHERE ejecucion_id_principal IS NULL"), 0)

    def test_editar_no_toca_la_fila_y_se_encadena(self):
        ticket_id, _ = self.crear_ticket()
        creacion = self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id])
        tickets.editar(self.con, ticket_id, importe=30.0)
        tickets.editar(self.con, ticket_id, descripcion="corregido")

        self.assertEqual(self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id]), creacion)
        columnas, filas = ejecuciones.historial(self.con, creacion)
        operaciones = [f[columnas.index("operacion")] for f in filas]
        self.assertEqual(operaciones, ["ticket.crear", "ticket.editar", "ticket.editar"])

    def test_borrar_cierra_la_cadena_del_registro(self):
        ticket_id, _ = self.crear_ticket()
        creacion = self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id])
        tickets.borrar(self.con, ticket_id)
        _, filas = ejecuciones.historial(self.con, creacion)
        self.assertEqual(len(filas), 2)

    def test_fila_sin_ejecucion_previa_no_inventa_cadena(self):
        """Las filas anteriores a la migración 013 tienen ejecucion_id nulo."""
        self.con.execute(
            "INSERT INTO idea (persona_id, texto, ejecucion_id) "
            "SELECT id, 'idea antigua', NULL FROM persona LIMIT 1"
        )
        idea_id = self.escalar("SELECT id FROM idea")
        self.assertIsNone(ejecuciones.principal_de(self.con, "idea", idea_id))
        ideas.editar(self.con, idea_id, estado="hecha")
        ultima = self.escalar("SELECT max(id) FROM _ejecuciones")
        self.assertEqual(
            self.escalar("SELECT ejecucion_id_principal FROM _ejecuciones WHERE id = ?", [ultima]),
            ultima,
        )
