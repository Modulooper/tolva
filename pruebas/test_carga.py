"""Motor ETL: mapping, operaciones, rechazos, singularidad, hall, stops y salidas."""

from motor import cargas, motor_etl
from pruebas.base import PruebaConAlmacen

CSV_VENTAS = (
    "fecha;producto;importe;sobrante\n"
    "05/08/2026;Teclado;1.234,50;x\n"
    "06/08/2026;Ratón;19,50;y\n"
)

CAMPOS_VENTA = {
    "fecha": ("date", True),
    "producto": ("varchar", True),
    "importe": ("double", True),
    "origen_carga": ("varchar", True),
    "extra_fields": ("varchar", False),
    "ejecucion_id": ("integer", False),
}


class BaseCarga(PruebaConAlmacen):
    def preparar_venta(self, **extra_definicion):
        self.con.execute(
            """CREATE TABLE venta (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fecha DATE NOT NULL, producto VARCHAR NOT NULL, importe DOUBLE NOT NULL,
                origen_carga VARCHAR NOT NULL, extra_fields VARCHAR, ejecucion_id BIGINT)"""
        )
        self.escribir_catalogo(self.ficha_catalogo("venta", CAMPOS_VENTA))
        definicion = {
            "nombre": "ventas",
            "patron": "*.csv",
            "formato": "csv",
            "delimitador": ";",
            "encoding": "utf-8",
            "fila_cabecera": 1,
            "tabla_destino": "venta",
            "mapping": [
                {"origen": "fecha", "destino": "fecha",
                 "operaciones": [{"tipo": "date_format", "formatos": ["%d/%m/%Y"]}]},
                {"origen": "producto", "destino": "producto", "operaciones": [{"tipo": "trim"}]},
                {"origen": "importe", "destino": "importe",
                 "operaciones": [{"tipo": "cast", "tipo_destino": "double", "formato_numerico": "es"}]},
                {"destino": "origen_carga", "operaciones": [{"tipo": "const", "valor": "ventas"}]},
            ],
            **extra_definicion,
        }
        nombre = self.escribir_carga(definicion)
        self.escribir_csv("ventas", "ventas_agosto.csv", CSV_VENTAS)
        return nombre

    def ejecutar(self, nombre, **kwargs):
        return motor_etl.ejecutar_carga(nombre, db_path=self.db_path, **kwargs)


class PruebaCargaBasica(BaseCarga):
    def test_carga_mapea_tipos_y_formato_numerico_espanol(self):
        self.ejecutar(self.preparar_venta())
        filas = self.filas("SELECT producto, importe FROM venta ORDER BY producto")
        self.assertEqual(len(filas), 2)
        self.assertEqual(dict(filas)["Teclado"], 1234.50)

    def test_columnas_no_declaradas_van_a_extra_fields(self):
        self.ejecutar(self.preparar_venta())
        extra = self.escalar("SELECT extra_fields FROM venta LIMIT 1")
        self.assertIn("sobrante", extra)

    def test_ejecucion_id_se_sella_en_cada_fila(self):
        self.ejecutar(self.preparar_venta())
        self.assertEqual(self.escalar("SELECT count(DISTINCT ejecucion_id) FROM venta"), 1)
        self.assertIsNotNone(self.escalar("SELECT ejecucion_id FROM venta LIMIT 1"))

    def test_fila_invalida_se_rechaza_sin_tumbar_la_carga(self):
        nombre = self.preparar_venta()
        self.escribir_csv("ventas", "ventas_agosto.csv", CSV_VENTAS + "no-es-fecha;Monitor;10,00;z\n")
        resultado = self.ejecutar(nombre)
        fichero = resultado["ficheros"][0]
        self.assertEqual(fichero["estado"], "OK")
        self.assertEqual(fichero["filas_rechazadas"], 1)
        self.assertEqual(self.escalar("SELECT count(*) FROM venta"), 2)
        self.assertEqual(self.escalar("SELECT campo_implicado FROM _rechazos"), "fecha")

    def test_mismo_hash_se_omite_y_forzar_lo_recarga(self):
        nombre = self.preparar_venta()
        self.ejecutar(nombre)
        segunda = self.ejecutar(nombre)
        self.assertEqual(segunda["ficheros"][0]["estado"], "OMITIDO")
        tercera = self.ejecutar(nombre, forzar=True)
        self.assertEqual(tercera["ficheros"][0]["estado"], "OK")

    def test_dry_run_no_escribe(self):
        nombre = self.preparar_venta()
        resultado = motor_etl.dry_run_carga(nombre, db_path=self.db_path)
        self.assertEqual(resultado["ficheros"][0]["filas_ok"], 2)
        self.assertEqual(self.escalar("SELECT count(*) FROM venta"), 0)

    def test_operacion_no_registrada_se_rechaza_al_validar(self):
        nombre = self.preparar_venta()
        definicion = cargas.cargar(nombre)
        definicion["mapping"][1]["operaciones"] = [{"tipo": "inventada"}]
        errores = cargas.validar(definicion, self.con)
        self.assertTrue(any("vocabulario" in e for e in errores), errores)

    def test_campo_fuera_del_catalogo_se_rechaza(self):
        nombre = self.preparar_venta()
        definicion = cargas.cargar(nombre)
        definicion["mapping"].append(
            {"destino": "columna_fantasma", "operaciones": [{"tipo": "const", "valor": 1}]}
        )
        self.assertNotEqual(cargas.validar(definicion, self.con), [])


class PruebaSingularidad(BaseCarga):
    def test_sin_singularidad_es_acumulativa(self):
        nombre = self.preparar_venta()
        self.ejecutar(nombre)
        self.ejecutar(nombre, forzar=True)
        self.assertEqual(self.escalar("SELECT count(*) FROM venta"), 4)

    def test_con_singularidad_sustituye_solo_su_porcion(self):
        nombre = self.preparar_venta(campos_singularidad=["fecha", "producto"])
        self.ejecutar(nombre)
        self.escribir_csv("ventas", "ventas_agosto.csv",
                          "fecha;producto;importe;sobrante\n05/08/2026;Teclado;99,00;x\n")
        self.ejecutar(nombre, forzar=True)
        importes = dict(self.filas("SELECT producto, importe FROM venta"))
        self.assertEqual(importes["Teclado"], 99.0)   # sustituido
        self.assertEqual(importes["Ratón"], 19.5)     # intacto

    def test_singularidad_fuera_del_mapping_se_rechaza(self):
        nombre = self.preparar_venta(campos_singularidad=["no_existe"])
        errores = cargas.validar(cargas.cargar(nombre), self.con)
        self.assertTrue(any("singularidad" in e for e in errores), errores)


class PruebaHall(BaseCarga):
    def test_transformacion_produce_las_filas_finales(self):
        self.con.execute(
            """CREATE TABLE hall_venta (
                fecha DATE, producto VARCHAR, importe DOUBLE,
                origen_carga VARCHAR, extra_fields VARCHAR, ejecucion_id BIGINT)"""
        )
        self.escribir_catalogo(self.ficha_catalogo("hall_venta", {
            "fecha": ("date", False), "producto": ("varchar", False),
            "importe": ("double", False), "origen_carga": ("varchar", False),
            "extra_fields": ("varchar", False), "ejecucion_id": ("integer", False),
        }))
        nombre = self.preparar_venta(
            tabla_hall="hall_venta",
            # Filtra por importe: solo el Teclado supera el umbral.
            transformacion_sql=(
                "SELECT fecha, producto, importe * 2 AS importe, origen_carga, "
                "extra_fields, ejecucion_id FROM hall_venta WHERE importe > 100"
            ),
        )
        self.ejecutar(nombre)
        filas = self.filas("SELECT producto, importe FROM venta")
        self.assertEqual(filas, [("Teclado", 2469.0)])
        self.assertEqual(self.escalar("SELECT count(*) FROM hall_venta"), 2)

    def test_hall_sin_transformacion_se_rechaza(self):
        nombre = self.preparar_venta(tabla_hall="hall_venta")
        errores = cargas.validar(cargas.cargar(nombre), self.con)
        self.assertTrue(any("transformacion_sql" in e for e in errores), errores)


class PruebaStopsYAlarmas(BaseCarga):
    def test_stop_aborta_y_no_escribe_en_destino(self):
        nombre = self.preparar_venta(validaciones=[{
            "nombre": "importes_altos", "tipo": "stop",
            "sql": "SELECT producto, importe FROM _entrante WHERE importe > 1000",
            "mensaje": "hay importes desorbitados",
        }])
        resultado = self.ejecutar(nombre)
        self.assertEqual(resultado["ficheros"][0]["estado"], "ERROR")
        self.assertEqual(self.escalar("SELECT count(*) FROM venta"), 0)
        # Pero la ejecución sí queda registrada, para poder investigarla.
        self.assertEqual(self.escalar("SELECT count(*) FROM _ejecuciones WHERE estado = 'ERROR'"), 1)

    def test_alarma_avisa_pero_deja_pasar(self):
        nombre = self.preparar_venta(validaciones=[{
            "nombre": "importes_altos", "tipo": "alarma",
            "sql": "SELECT producto FROM _entrante WHERE importe > 1000",
            "mensaje": "revisa los importes altos",
        }])
        resultado = self.ejecutar(nombre)
        self.assertEqual(resultado["ficheros"][0]["estado"], "OK")
        self.assertEqual(self.escalar("SELECT count(*) FROM venta"), 2)
        disparada = self.filas("SELECT nombre, tipo, afectadas FROM _validaciones_disparadas")
        self.assertEqual(disparada, [("importes_altos", "alarma", 1)])

    def test_validacion_no_ejecutable_es_error_duro(self):
        nombre = self.preparar_venta(validaciones=[{
            "nombre": "rota", "tipo": "stop",
            "sql": "SELECT * FROM tabla_que_no_existe",
            "mensaje": "no debería llegar a dispararse",
        }])
        with self.assertRaises(Exception):
            self.ejecutar(nombre)


class PruebaSalidas(BaseCarga):
    def test_salida_csv_se_genera_al_terminar(self):
        nombre = self.preparar_venta(salidas=[{
            "nombre": "resumen",
            "fichero": "%Y%m%d_{carga}_resumen.csv",
            "sql": "SELECT producto, importe FROM venta ORDER BY producto",
        }])
        resultado = self.ejecutar(nombre)
        generadas = resultado["ficheros"][0].get("salidas", [])
        self.assertEqual(len(generadas), 1)
        ruta = list(self.export_dir.glob("*_ventas_resumen.csv"))
        self.assertEqual(len(ruta), 1, f"no se generó la salida en {self.export_dir}")
        self.assertIn("Teclado", ruta[0].read_text(encoding="utf-8"))
