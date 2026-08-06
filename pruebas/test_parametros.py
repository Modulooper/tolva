"""Parámetros de carga: obligatorios, listas cerradas, texto libre y avisos."""

import json

from motor import cargas, motor_etl, parametros
from pruebas.base import PruebaConAlmacen

CSV_PEDIDOS = "fecha;producto;importe\n05/08/2026;Teclado;49,90\n06/08/2026;Monitor;229,00\n"

CAMPOS_PEDIDO = {
    "tienda_id": ("uuid", True),
    "fecha": ("date", True),
    "producto": ("varchar", True),
    "importe": ("double", True),
    "comentario": ("varchar", False),
    "origen_carga": ("varchar", True),
    "extra_fields": ("varchar", False),
    "ejecucion_id": ("integer", False),
}


class BaseParametros(PruebaConAlmacen):
    def setUp(self):
        super().setUp()
        self.con.execute(
            "CREATE TABLE tienda (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), nombre VARCHAR NOT NULL)"
        )
        self.con.execute("INSERT INTO tienda (nombre) VALUES ('Gran Via'), ('Diagonal')")
        self.con.execute(
            """CREATE TABLE pedido (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tienda_id UUID NOT NULL, fecha DATE NOT NULL, producto VARCHAR NOT NULL,
                importe DOUBLE NOT NULL, comentario VARCHAR, origen_carga VARCHAR NOT NULL,
                extra_fields VARCHAR, ejecucion_id BIGINT)"""
        )
        self.escribir_catalogo(self.ficha_catalogo("tienda", {"nombre": ("varchar", True)}))
        self.escribir_catalogo(self.ficha_catalogo("pedido", CAMPOS_PEDIDO))
        self.escribir_csv("pedidos", "pedidos.csv", CSV_PEDIDOS)

    def definir(self, **extra):
        definicion = {
            "nombre": "pedidos",
            "patron": "*.csv",
            "formato": "csv",
            "delimitador": ";",
            "encoding": "utf-8",
            "fila_cabecera": 1,
            "tabla_destino": "pedido",
            "parametros": [
                {"nombre": "tienda", "obligatorio": True, "descripcion": "Tienda del fichero",
                 "valores_de": {"tabla": "tienda", "etiqueta": "nombre"}},
                {"nombre": "comentario", "obligatorio": False},
            ],
            "mapping": [
                {"origen": "fecha", "destino": "fecha",
                 "operaciones": [{"tipo": "date_format", "formatos": ["%d/%m/%Y"]}]},
                {"origen": "producto", "destino": "producto", "operaciones": [{"tipo": "trim"}]},
                {"origen": "importe", "destino": "importe",
                 "operaciones": [{"tipo": "cast", "tipo_destino": "double", "formato_numerico": "es"}]},
                {"destino": "tienda_id", "operaciones": [{"tipo": "parametro", "nombre": "tienda"}]},
                {"destino": "comentario", "operaciones": [{"tipo": "parametro", "nombre": "comentario"}]},
                {"destino": "origen_carga", "operaciones": [{"tipo": "const", "valor": "pedidos"}]},
            ],
            "campos_singularidad": ["tienda_id", "fecha", "producto"],
            **extra,
        }
        return self.escribir_carga(definicion)

    def ejecutar(self, nombre, valores, **kwargs):
        return motor_etl.ejecutar_carga(
            nombre, db_path=self.db_path, valores_parametros=valores, **kwargs
        )


class PruebaResolucion(BaseParametros):
    def test_falta_obligatorio_corta_antes_de_leer(self):
        nombre = self.definir()
        with self.assertRaises(parametros.ParametroInvalidoError):
            self.ejecutar(nombre, {})
        self.assertEqual(self.escalar("SELECT count(*) FROM _ejecuciones"), 0)

    def test_valor_fuera_de_la_lista_cerrada_falla_listando_opciones(self):
        nombre = self.definir()
        with self.assertRaises(parametros.ParametroInvalidoError) as ctx:
            self.ejecutar(nombre, {"tienda": "Callao"})
        self.assertIn("Diagonal", str(ctx.exception))

    def test_parametro_no_declarado_falla(self):
        nombre = self.definir()
        with self.assertRaises(parametros.ParametroInvalidoError):
            self.ejecutar(nombre, {"tienda": "Diagonal", "inventado": "x"})

    def test_lista_cerrada_resuelve_al_id_sin_distinguir_mayusculas(self):
        nombre = self.definir()
        self.ejecutar(nombre, {"tienda": "gran via"})
        self.assertEqual(
            self.filas("SELECT DISTINCT t.nombre FROM pedido p JOIN tienda t ON t.id = p.tienda_id"),
            [("Gran Via",)],
        )

    def test_opcional_ausente_queda_nulo(self):
        nombre = self.definir()
        self.ejecutar(nombre, {"tienda": "Diagonal"})
        self.assertIsNone(self.escalar("SELECT comentario FROM pedido LIMIT 1"))

    def test_texto_libre_llega_tal_cual(self):
        nombre = self.definir()
        self.ejecutar(nombre, {"tienda": "Diagonal", "comentario": "subida manual"})
        self.assertEqual(self.escalar("SELECT DISTINCT comentario FROM pedido"), "subida manual")


class PruebaSingularidadConParametros(BaseParametros):
    def test_recargar_una_tienda_no_pisa_a_la_otra(self):
        """El parámetro dentro de la singularidad aísla por tienda.

        Ojo a la semántica: se borran solo las combinaciones que **trae** el
        fichero. Un producto que estaba y ya no viene en la recarga se queda;
        para que desapareciera, la clave tendría que ser más gruesa.
        """
        nombre = self.definir()
        self.ejecutar(nombre, {"tienda": "Gran Via"})
        self.ejecutar(nombre, {"tienda": "Diagonal"}, forzar=True)
        self.assertEqual(self.escalar("SELECT count(*) FROM pedido"), 4)

        self.escribir_csv("pedidos", "pedidos.csv", "fecha;producto;importe\n05/08/2026;Teclado;99,00\n")
        self.ejecutar(nombre, {"tienda": "Gran Via"}, forzar=True)

        importes = {
            (fila[0], fila[1]): fila[2]
            for fila in self.filas(
                "SELECT t.nombre, p.producto, p.importe FROM pedido p "
                "JOIN tienda t ON t.id = p.tienda_id"
            )
        }
        self.assertEqual(importes[("Gran Via", "Teclado")], 99.0)    # sustituido
        self.assertEqual(importes[("Gran Via", "Monitor")], 229.0)   # no venía: intacto
        self.assertEqual(importes[("Diagonal", "Teclado")], 49.9)    # otra tienda: intacta
        self.assertEqual(importes[("Diagonal", "Monitor")], 229.0)


class PruebaValidacionYRegistro(BaseParametros):
    def test_avisa_si_el_obligatorio_no_entra_en_la_singularidad(self):
        nombre = self.definir(campos_singularidad=["fecha", "producto"])
        definicion = cargas.cargar(nombre)
        self.assertEqual(cargas.validar(definicion, self.con), [])
        avisos = cargas.avisos(definicion)
        self.assertEqual(len(avisos), 1)
        self.assertIn("tienda", avisos[0])

    def test_no_avisa_del_opcional(self):
        """Un comentario no identifica nada: no debe estar en la clave."""
        nombre = self.definir()
        self.assertEqual(cargas.avisos(cargas.cargar(nombre)), [])

    def test_sin_singularidad_no_avisa(self):
        nombre = self.definir(campos_singularidad=[])
        self.assertEqual(cargas.avisos(cargas.cargar(nombre)), [])

    def test_parametro_usado_pero_no_declarado_es_error(self):
        nombre = self.definir()
        definicion = cargas.cargar(nombre)
        definicion["parametros"] = [p for p in definicion["parametros"] if p["nombre"] != "comentario"]
        errores = cargas.validar(definicion, self.con)
        self.assertTrue(any("no está en 'parametros'" in e for e in errores), errores)

    def test_parametro_declarado_y_sin_usar_es_error(self):
        nombre = self.definir()
        definicion = cargas.cargar(nombre)
        definicion["parametros"].append({"nombre": "huerfano"})
        errores = cargas.validar(definicion, self.con)
        self.assertTrue(any("huerfano" in e for e in errores), errores)

    def test_se_guardan_las_dos_caras_del_valor_cerrado(self):
        """Renombrar la tienda mañana no debe dejar la ejecución ilegible."""
        nombre = self.definir()
        self.ejecutar(nombre, {"tienda": "Diagonal", "comentario": "nota"})
        registrado = json.loads(self.escalar(
            "SELECT parametros FROM _ejecuciones WHERE carga = 'pedidos' ORDER BY id DESC LIMIT 1"
        ))
        self.assertEqual(registrado["tienda"]["entrada"], "Diagonal")
        self.assertTrue(registrado["tienda"]["valor"])
        self.assertEqual(registrado["comentario"], "nota")

    def test_dry_run_tambien_resuelve_parametros(self):
        nombre = self.definir()
        resultado = motor_etl.dry_run_carga(
            nombre, db_path=self.db_path, valores_parametros={"tienda": "Diagonal"}
        )
        self.assertEqual(resultado["ficheros"][0]["filas_ok"], 2)
        self.assertEqual(self.escalar("SELECT count(*) FROM pedido"), 0)
