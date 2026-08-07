"""CRUD genérico dirigido por el catálogo (`motor/registros.py`).

Lo que hay que fijar aquí no es solo que el CRUD funcione, sino que funcione
**sin que el núcleo conozca la entidad**: es la única forma de que un proceso
viva entero en la capa propia y no venga de serie en la instalación de nadie.
Por eso la prueba central crea una entidad que existe solo en `propio/`.
"""

import json
from datetime import date

from motor import db, registros
from pruebas.base import PruebaConAlmacen

FICHA_ENCARGO = {
    "entidad": "encargo",
    "tabla": "encargo",
    "descripcion": (
        "Entidad que solo existe en la capa propia de esta prueba: sirve para "
        "comprobar que el CRUD genérico no necesita nada en el núcleo."
    ),
    "campos": {
        "id": {"tipo": "uuid", "obligatorio": True, "sistema": True,
               "descripcion": "Identificador interno.", "sinonimos": []},
        "demo_cliente_id": {"tipo": "uuid", "obligatorio": True,
                            "descripcion": "Para quién es el encargo.", "sinonimos": []},
        "texto": {"tipo": "varchar", "obligatorio": True,
                  "descripcion": "Qué hay que hacer.", "sinonimos": ["Asunto"]},
        "estado": {"tipo": "varchar", "obligatorio": True, "descripcion": "En qué punto está.",
                   "sinonimos": [], "validacion": {"lista_valores": ["abierto", "cerrado"]}},
        "fecha": {"tipo": "date", "obligatorio": True, "descripcion": "Cuándo se apuntó.",
                  "sinonimos": []},
        "horas": {"tipo": "double", "obligatorio": False, "descripcion": "Dedicación real.",
                  "sinonimos": []},
        "ejecucion_id": {"tipo": "integer", "obligatorio": False, "sistema": True,
                         "descripcion": "Ejecución que lo creó.", "sinonimos": []},
        "created_at": {"tipo": "timestamp", "obligatorio": True, "sistema": True,
                       "descripcion": "Alta.", "sinonimos": []},
        "updated_at": {"tipo": "timestamp", "obligatorio": True, "sistema": True,
                       "descripcion": "Última modificación.", "sinonimos": []},
    },
    "relaciones": [
        {"campo": "demo_cliente_id", "entidad_destino": "demo_cliente",
         "campo_destino": "id", "tipo": "N:1"},
    ],
}

DDL_ENCARGO = """
CREATE TABLE encargo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demo_cliente_id UUID NOT NULL REFERENCES demo_cliente(id),
    texto VARCHAR NOT NULL,
    estado VARCHAR NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'cerrado')),
    fecha DATE NOT NULL DEFAULT current_date,
    horas DOUBLE,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    ejecucion_id BIGINT
);
"""


class PruebaEntidadDeLaCapaPropia(PruebaConAlmacen):
    """Una entidad que el framework no conoce: ni módulo, ni subcomando."""

    def setUp(self):
        super().setUp()
        (self.carpeta_propia("migraciones") / "900_encargo.sql").write_text(
            DDL_ENCARGO, encoding="utf-8"
        )
        (self.carpeta_propia("catalogo") / "encargo.json").write_text(
            json.dumps(FICHA_ENCARGO, ensure_ascii=False), encoding="utf-8"
        )
        # La capa propia se descubre al migrar, así que hace falta un almacén
        # nuevo: el de `setUp` se creó cuando `propio/` aún no existía.
        self.con.close()
        self.db_path = self.tmp / "con_capa_propia.duckdb"
        db.migrar(self.db_path, con_ejemplos=True)
        self.con = db.conectar(self.db_path)

    def crear(self, **valores):
        valores.setdefault("demo_cliente", "Ateneo Mercantil")
        valores.setdefault("texto", "Revisar el informe")
        return registros.crear(self.con, "encargo", valores)

    def test_alta_sin_una_linea_de_codigo_en_el_nucleo(self):
        fila_id, _ = self.crear()
        self.assertEqual(self.escalar("SELECT count(*) FROM encargo WHERE id = ?", [fila_id]), 1)

    def test_la_referencia_se_resuelve_por_nombre(self):
        """El alias `demo_cliente` viene de la relación, no de código a medida."""
        fila_id, _ = self.crear(demo_cliente="ateneo mercantil")
        self.assertEqual(
            self.escalar("SELECT demo_cliente_id FROM encargo WHERE id = ?", [fila_id]),
            self.escalar("SELECT id FROM demo_cliente WHERE nombre = 'Ateneo Mercantil'"),
        )

    def test_el_id_en_crudo_tambien_vale_como_referencia(self):
        cliente_id = self.escalar(
            "SELECT CAST(id AS VARCHAR) FROM demo_cliente WHERE nombre = 'Ateneo Mercantil'"
        )
        fila_id, _ = self.crear(demo_cliente_id=cliente_id)
        self.assertIsNotNone(fila_id)

    def test_referencia_inexistente_falla_con_mensaje_legible(self):
        with self.assertRaises(ValueError) as capturado:
            self.crear(demo_cliente="Fulano")
        self.assertIn("demo_cliente", str(capturado.exception))

    def test_el_texto_del_cli_se_convierte_segun_el_tipo_de_la_ficha(self):
        fila_id, _ = self.crear(fecha="2026-08-05", horas="1,5")
        fila = self.filas("SELECT fecha, horas FROM encargo WHERE id = ?", [fila_id])[0]
        self.assertEqual(fila, (date(2026, 8, 5), 1.5))

    def test_valor_fuera_de_lista_valores_falla_antes_del_check(self):
        with self.assertRaises(ValueError) as capturado:
            self.crear(estado="en_curso")
        self.assertIn("abierto", str(capturado.exception))

    def test_campo_no_declarado_falla(self):
        with self.assertRaises(registros.CampoDesconocido):
            self.crear(prioridad="alta")

    def test_los_campos_de_sistema_no_se_escriben_a_mano(self):
        with self.assertRaises(registros.CampoDesconocido):
            self.crear(ejecucion_id=1)

    def test_un_sinonimo_de_la_ficha_vale_como_campo(self):
        fila_id, _ = registros.crear(
            self.con, "encargo",
            {"demo_cliente": "Ateneo Mercantil", "Asunto": "Llamar al gestor"}
        )
        self.assertEqual(
            self.escalar("SELECT texto FROM encargo WHERE id = ?", [fila_id]), "Llamar al gestor"
        )

    # --- listado --------------------------------------------------------

    def test_el_listado_muestra_el_nombre_de_la_referencia_no_el_id(self):
        self.crear()
        columnas, filas = registros.listar(self.con, "encargo")
        self.assertIn("demo_cliente", columnas)
        self.assertNotIn("demo_cliente_id", columnas)
        self.assertEqual(filas[0][columnas.index("demo_cliente")], "Ateneo Mercantil")

    def test_el_listado_oculta_los_campos_de_sistema(self):
        self.crear()
        columnas, _ = registros.listar(self.con, "encargo")
        self.assertNotIn("ejecucion_id", columnas)
        self.assertNotIn("created_at", columnas)

    def test_filtro_por_igualdad(self):
        self.crear(texto="Uno")
        self.crear(texto="Dos", estado="cerrado")
        _, filas = registros.listar(self.con, "encargo", [("estado", "=", "cerrado")])
        self.assertEqual(len(filas), 1)

    def test_filtro_con_operador_de_comparacion(self):
        self.crear(fecha="2026-08-01")
        self.crear(fecha="2026-09-01")
        _, filas = registros.listar(self.con, "encargo", [("fecha", "<=", "2026-08-15")])
        self.assertEqual(len(filas), 1)

    def test_filtro_por_el_nombre_de_la_referencia(self):
        self.crear()
        _, filas = registros.listar(
            self.con, "encargo", [("demo_cliente", "=", "ATENEO MERCANTIL")]
        )
        self.assertEqual(len(filas), 1)

    # --- edición y borrado ----------------------------------------------

    def test_editar_cambia_solo_lo_indicado(self):
        fila_id, _ = self.crear(texto="Original")
        registros.editar(self.con, "encargo", fila_id, {"estado": "cerrado", "horas": "2"})
        fila = self.filas(
            "SELECT texto, estado, horas FROM encargo WHERE id = ?", [fila_id]
        )[0]
        self.assertEqual(fila, ("Original", "cerrado", 2.0))

    def test_editar_con_valor_vacio_deja_el_campo_a_nulo(self):
        fila_id, _ = self.crear(horas="3")
        registros.editar(self.con, "encargo", fila_id, {"horas": ""})
        self.assertIsNone(self.escalar("SELECT horas FROM encargo WHERE id = ?", [fila_id]))

    def test_editar_una_fila_que_no_existe_falla(self):
        with self.assertRaises(ValueError):
            registros.editar(self.con, "encargo", "no-existe", {"estado": "cerrado"})

    def test_borrar(self):
        fila_id, _ = self.crear()
        registros.borrar(self.con, "encargo", fila_id)
        self.assertEqual(self.escalar("SELECT count(*) FROM encargo"), 0)

    # --- trazabilidad ----------------------------------------------------

    def test_el_alta_sella_su_ejecucion_en_la_fila(self):
        fila_id, _ = self.crear()
        ejecucion_id = self.escalar("SELECT ejecucion_id FROM encargo WHERE id = ?", [fila_id])
        self.assertIsNotNone(ejecucion_id)
        self.assertEqual(
            self.escalar("SELECT carga FROM _ejecuciones WHERE id = ?", [ejecucion_id]),
            "encargo.crear",
        )

    def test_editar_no_toca_el_ejecucion_id_y_se_encadena_a_el(self):
        fila_id, _ = self.crear()
        creacion = self.escalar("SELECT ejecucion_id FROM encargo WHERE id = ?", [fila_id])
        registros.editar(self.con, "encargo", fila_id, {"estado": "cerrado"})
        self.assertEqual(
            self.escalar("SELECT ejecucion_id FROM encargo WHERE id = ?", [fila_id]), creacion
        )
        encadenadas = self.filas(
            "SELECT carga FROM _ejecuciones WHERE ejecucion_id_principal = ? ORDER BY id",
            [creacion],
        )
        self.assertEqual([c for (c,) in encadenadas], ["encargo.crear", "encargo.editar"])

    def test_el_borrado_queda_registrado_encadenado(self):
        fila_id, _ = self.crear()
        creacion = self.escalar("SELECT ejecucion_id FROM encargo WHERE id = ?", [fila_id])
        registros.borrar(self.con, "encargo", fila_id)
        self.assertIn(
            ("encargo.borrar",),
            self.filas(
                "SELECT carga FROM _ejecuciones WHERE ejecucion_id_principal = ?", [creacion]
            ),
        )

    # --- ayuda -----------------------------------------------------------

    def test_describir_lista_los_campos_escribibles_y_no_los_de_sistema(self):
        _, filas = registros.describir(self.con, "encargo")
        nombres = [f[0] for f in filas]
        self.assertEqual(
            nombres, ["demo_cliente_id", "texto", "estado", "fecha", "horas"]
        )
        self.assertIn("demo_cliente.nombre", filas[nombres.index("demo_cliente_id")][3])


class PruebaSobreDimensiones(PruebaConAlmacen):
    """El mismo CRUD sirve para una dimensión, sin caso especial."""

    def test_da_de_alta_una_dimension(self):
        fila_id, _ = registros.crear(self.con, "demo_cliente", {
            "nombre": "Casa del Lector", "ciudad": "Madrid", "activo": "si",
        })
        fila = self.filas(
            "SELECT nombre, ciudad, activo FROM demo_cliente WHERE id = ?", [fila_id]
        )[0]
        self.assertEqual(fila, ("Casa del Lector", "Madrid", True))

    def test_respeta_la_lista_de_valores_del_catalogo(self):
        with self.assertRaises(ValueError):
            registros.crear(self.con, "demo_libro", {
                "titulo": "Un título", "autor": "Alguien",
                "genero": "manual de instrucciones", "precio": "10",
            })

    def test_una_referencia_se_resuelve_por_la_etiqueta_declarada(self):
        """demo_libro se identifica por `titulo`, no por `nombre`: la ficha lo
        declara con `etiqueta` y el motor lo respeta en vez de asumir."""
        fila_id, _ = registros.crear(self.con, "demo_venta", {
            "demo_libro": "Once maneras de callar", "unidades": "1", "importe": "14.90",
        })
        self.assertEqual(
            self.escalar(
                "SELECT l.titulo FROM demo_venta v JOIN demo_libro l ON l.id = v.demo_libro_id "
                "WHERE v.id = ?", [fila_id]
            ),
            "Once maneras de callar",
        )

    def test_una_entidad_que_no_esta_en_el_catalogo_falla(self):
        with self.assertRaises(FileNotFoundError):
            registros.crear(self.con, "no_existe", {"texto": "x"})
