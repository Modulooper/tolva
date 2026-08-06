"""Almacén de documentos, vínculos por ejecución, historial y purga."""

import json
from datetime import date, datetime

from motor import documentos, ejecuciones, historial, tickets
from pruebas.base import PruebaConAlmacen


class BaseDocumentos(PruebaConAlmacen):
    def setUp(self):
        super().setUp()
        self.con.execute("INSERT INTO persona (nombre) VALUES ('Nacho')")
        self.con.execute("INSERT INTO cliente (nombre) VALUES ('Interno')")
        self.billete = self.tmp / "billete.jpg"
        self.billete.write_bytes(b"foto del billete")
        self.pago = self.tmp / "pago.pdf"
        self.pago.write_bytes(b"justificante de pago")

    def crear_ticket(self, **extra):
        return tickets.crear(
            self.con, cliente="Interno", persona="Nacho", concepto="viajes",
            importe=20.5, fecha=date(2026, 8, 5), **extra,
        )


class PruebaArchivado(BaseDocumentos):
    def test_archivar_guarda_bytes_y_ficha(self):
        ejecucion = ejecuciones.registrar(self.con, "prueba")
        hash_doc = documentos.archivar(self.con, self.billete, ejecucion)
        ruta = documentos.ruta_almacen(hash_doc, ".jpg", self.documentos_dir)
        self.assertTrue(ruta.is_file())
        self.assertEqual(
            self.filas("SELECT nombre_original, bytes, estado FROM _documentos"),
            [("billete.jpg", 16, "disponible")],
        )

    def test_mismo_contenido_no_se_duplica(self):
        copia = self.tmp / "otro_nombre.jpg"
        copia.write_bytes(self.billete.read_bytes())
        for ruta in (self.billete, copia):
            documentos.archivar(self.con, ruta, ejecuciones.registrar(self.con, "prueba"))
        self.assertEqual(self.escalar("SELECT count(*) FROM _documentos"), 1)
        self.assertEqual(self.escalar("SELECT count(*) FROM _ejecucion_documento"), 2)

    def test_fichero_inexistente_falla(self):
        with self.assertRaises(ValueError):
            documentos.archivar(self.con, self.tmp / "no_existe.pdf", 1)

    def test_hash_es_el_mismo_que_identifica_la_ejecucion(self):
        self.assertEqual(documentos.hash_fichero(self.billete), documentos.hash_fichero(self.billete))
        self.assertNotEqual(documentos.hash_fichero(self.billete), documentos.hash_fichero(self.pago))


class PruebaDocumentosDeUnRegistro(BaseDocumentos):
    def test_documento_en_el_alta_y_otro_despues(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="justificante pago")

        columnas, filas = documentos.de_fila(self.con, "ticket", ticket_id)
        pares = [(f[columnas.index("nombre_original")], f[columnas.index("tag")]) for f in filas]
        self.assertEqual(pares, [("billete.jpg", "crear"), ("pago.pdf", "justificante pago")])

    def test_adjuntar_se_encadena_a_la_creacion(self):
        ticket_id, _ = self.crear_ticket()
        creacion = self.escalar("SELECT ejecucion_id FROM ticket WHERE id = ?", [ticket_id])
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago)
        _, filas = ejecuciones.historial(self.con, creacion)
        self.assertEqual(len(filas), 2)

    def test_adjuntar_a_registro_inexistente_falla(self):
        with self.assertRaises(ValueError):
            documentos.adjuntar(self.con, "ticket", "00000000-0000-0000-0000-000000000000", self.pago)

    def test_adjuntar_a_registro_sin_cadena_falla_con_mensaje_claro(self):
        self.con.execute(
            "INSERT INTO idea (persona_id, texto, ejecucion_id) "
            "SELECT id, 'idea antigua', NULL FROM persona LIMIT 1"
        )
        idea_id = self.escalar("SELECT id FROM idea")
        with self.assertRaises(ValueError) as ctx:
            documentos.adjuntar(self.con, "idea", idea_id, self.pago)
        self.assertIn("anterior al registro de ejecuciones", str(ctx.exception))


class PruebaHistorialYPurga(BaseDocumentos):
    def declarar_historial(self, proceso: str, politica):
        """Historial de una entidad del CLI, en su ficha de catálogo."""
        ruta = self.catalogo_dir / f"{proceso}.json"
        ficha = json.loads(ruta.read_text(encoding="utf-8"))
        ficha["historial"] = politica
        ruta.write_text(json.dumps(ficha, ensure_ascii=False), encoding="utf-8")

    def test_por_defecto_no_se_purga_nada(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        self.assertEqual(documentos.purgar(self.con, aplicar=False), [])

    def test_politica_por_numero_de_ficheros(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial("ticket", {"tipo": "ficheros", "cantidad": 1})

        purgables = documentos.purgar(self.con, aplicar=False)
        self.assertEqual([p[1] for p in purgables], ["billete.jpg"])  # el más antiguo

    def test_tags_exentos_se_conservan(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial(
            "ticket", {"tipo": "ficheros", "cantidad": 1, "tags_exentos": ["crear"]}
        )
        self.assertEqual(documentos.purgar(self.con, aplicar=False), [])

    def test_se_conserva_si_lo_conserva_otro_proceso(self):
        """La regla de seguridad: la decisión se toma sobre la unión."""
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial("ticket", {"tipo": "ficheros", "cantidad": 1})
        self.assertEqual(len(documentos.purgar(self.con, aplicar=False)), 1)

        # La misma foto pasa a colgar también de una idea, que conserva siempre.
        idea_ejecucion = ejecuciones.registrar(self.con, "idea.adjuntar")
        documentos.archivar(self.con, self.billete, idea_ejecucion, "respaldo")
        self.assertEqual(documentos.purgar(self.con, aplicar=False), [])

    def test_purgar_libera_bytes_y_conserva_la_ficha(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial("ticket", {"tipo": "ficheros", "cantidad": 1})

        purgados = documentos.purgar(self.con, aplicar=True)
        hash_doc = purgados[0][0]
        self.assertFalse((self.documentos_dir / hash_doc[:2] / f"{hash_doc}.jpg").is_file())
        self.assertEqual(
            self.filas("SELECT estado, fecha_purga IS NOT NULL FROM _documentos WHERE hash = ?", [hash_doc]),
            [("purgado", True)],
        )
        # Y la trazabilidad sobrevive: se sigue sabiendo de qué fichero venía.
        self.assertEqual(
            self.escalar("SELECT nombre_original FROM _documentos WHERE hash = ?", [hash_doc]),
            "billete.jpg",
        )

    def test_reponer_un_purgado_lo_reactiva(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial("ticket", {"tipo": "ficheros", "cantidad": 1})
        documentos.purgar(self.con, aplicar=True)

        documentos.archivar(self.con, self.billete, ejecuciones.registrar(self.con, "ticket.adjuntar"))
        self.assertEqual(
            self.filas("SELECT estado, fecha_purga FROM _documentos WHERE nombre_original = 'billete.jpg'"),
            [("disponible", None)],
        )

    def test_politica_por_anios(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        self.declarar_historial("ticket", {"tipo": "anios", "cantidad": 3})
        # Con "ahora" cuatro años por delante, el documento cae fuera.
        futuro = datetime.now().replace(year=datetime.now().year + 4)
        self.assertEqual(len(historial.purgables(self.con, ahora=futuro)), 1)
        self.assertEqual(historial.purgables(self.con), [])

    def test_purgar_queda_registrado_como_ejecucion(self):
        ticket_id, _ = self.crear_ticket(documento=self.billete)
        documentos.adjuntar(self.con, "ticket", ticket_id, self.pago, tag="posterior")
        self.declarar_historial("ticket", {"tipo": "ficheros", "cantidad": 1})
        documentos.purgar(self.con, aplicar=True)
        self.assertEqual(
            self.escalar("SELECT count(*) FROM _ejecuciones WHERE carga = 'documento.purgar' AND estado = 'OK'"),
            1,
        )
