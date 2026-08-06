"""Instalación desde cero: migraciones, esquema y catálogo del repo."""

import duckdb

from motor import cargas, catalogo, db
from pruebas.base import ROOT, PruebaConAlmacen


class PruebaInstalacion(PruebaConAlmacen):
    def test_todas_las_migraciones_aplican_desde_cero(self):
        esperadas = sorted(p.name for p in (ROOT / "migraciones").glob("*.sql"))
        self.assertEqual(self.migraciones_aplicadas, esperadas)

    def test_migrar_es_idempotente(self):
        self.assertEqual(db.migrar(self.db_path), [])

    def test_esquema_igual_al_del_almacen_incremental(self):
        """El camino desde cero y el incremental deben llegar al mismo sitio.

        Si divergen, una instalación nueva se comporta distinto que la del
        usuario que lleva meses migrando, y eso no avisa por ningún lado.

        Compara solo las tablas del núcleo: el almacén real puede tener además
        las de la capa propia (`propio/migraciones`), que esta instalación
        limpia no aplica a propósito. Lo que se exige es que **cada tabla del
        núcleo tenga exactamente las mismas columnas en los dos caminos**.
        """
        if not db.DB_PATH.exists():
            self.skipTest("no hay almacén incremental con el que comparar")

        def columnas_por_tabla(con):
            filas = con.execute(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns"
            ).fetchall()
            por_tabla = {}
            for tabla, columna, tipo, nullable in filas:
                por_tabla.setdefault(tabla, set()).add((columna, tipo, nullable))
            return por_tabla

        vivo = duckdb.connect(str(db.DB_PATH), read_only=True)
        try:
            nuevo, existente = columnas_por_tabla(self.con), columnas_por_tabla(vivo)
            faltan = sorted(set(nuevo) - set(existente))
            self.assertEqual(faltan, [], f"la instalación limpia crea tablas que no están en el almacén real: {faltan}")
            for tabla, columnas in nuevo.items():
                with self.subTest(tabla=tabla):
                    self.assertEqual(columnas, existente[tabla])
        finally:
            vivo.close()

    def test_tablas_de_sistema_presentes(self):
        tablas = {
            f[0]
            for f in self.filas(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            )
        }
        for esperada in (
            "_ejecuciones", "_rechazos", "_decisiones", "_migraciones",
            "_consultas", "_validaciones_disparadas", "_documentos",
            "_ejecucion_documento",
        ):
            self.assertIn(esperada, tablas)

    def test_arranca_vacio(self):
        self.assertEqual(self.escalar("SELECT count(*) FROM ticket"), 0)
        self.assertEqual(self.escalar("SELECT count(*) FROM idea"), 0)

    def test_catalogos_del_repo_validan(self):
        for nombre in catalogo.listar_entidades():
            with self.subTest(entidad=nombre):
                catalogo.cargar_entidad(nombre)

    def test_cargas_del_repo_validan_contra_el_esquema(self):
        for ruta in sorted((ROOT / "cargas").glob("*.json")):
            with self.subTest(carga=ruta.stem):
                definicion = cargas.cargar(str(ruta))
                self.assertEqual(cargas.validar(definicion, self.con), [])

    def test_cada_migracion_deja_su_decision(self):
        """Toda migración debe explicarse: es la regla del repo.

        Salvo la de arranque, que no puede insertar en `_decisiones` porque es
        justamente la que crea esa tabla.
        """
        arranque = {"001_nucleo.sql"}
        con_decision = {
            f[0] for f in self.filas("SELECT DISTINCT migracion_asociada FROM _decisiones")
        }
        sin_decision = [
            p.name
            for p in sorted((ROOT / "migraciones").glob("*.sql"))
            if p.name not in con_decision and p.name not in arranque
        ]
        self.assertEqual(sin_decision, [], f"migraciones sin _decisiones: {sin_decision}")
