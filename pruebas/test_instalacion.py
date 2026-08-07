"""Instalación desde cero: migraciones, esquema y catálogo del repo."""

import duckdb

from motor import cargas, catalogo, db
from pruebas.base import ROOT, PruebaConAlmacen


class PruebaInstalacion(PruebaConAlmacen):
    def test_todas_las_migraciones_aplican_desde_cero(self):
        """El núcleo primero y los ejemplos después, todos y en ese orden."""
        nucleo = sorted(p.name for p in (ROOT / "migraciones").glob("*.sql"))
        ejemplos = sorted(p.name for p in (ROOT / "ejemplos" / "migraciones").glob("*.sql"))
        self.assertEqual(self.migraciones_aplicadas, nucleo + ejemplos)

    def test_migrar_es_idempotente(self):
        self.assertEqual(db.migrar(self.db_path, con_ejemplos=True), [])

    def test_sin_pedirlos_los_ejemplos_no_se_instalan(self):
        """Datos dummy que nadie pidió son datos dummy que alguien confundirá
        con reales. La capa `ejemplos/` es opt-in."""
        limpio = self.tmp / "sin_ejemplos.duckdb"
        aplicadas = db.migrar(limpio)
        self.assertEqual(aplicadas, sorted(p.name for p in (ROOT / "migraciones").glob("*.sql")))
        con = db.conectar(limpio)
        try:
            demo = con.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE starts_with(table_name, 'demo')"
            ).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(demo, 0)

    def test_el_nucleo_no_crea_ninguna_tabla_de_negocio(self):
        """Lo que recibe un tercero al instalar es framework y nada más.

        Ni una sola tabla de negocio: ni tickets, ni ideas, ni siquiera
        persona/cliente/proyecto, que estuvieron aquí hasta el hito 26 y eran
        un modelo de consultoría metido de serie en la instalación de
        cualquiera. El framework opina sobre cómo se declaran, se cargan y se
        rastrean las entidades, no sobre cuáles son.
        """
        limpio = self.tmp / "solo_nucleo.duckdb"
        db.migrar(limpio)
        con = db.conectar(limpio)
        try:
            tablas = {
                f[0] for f in con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main' AND NOT starts_with(table_name, '_')"
                ).fetchall()
            }
        finally:
            con.close()
        self.assertEqual(tablas, set())

    def test_esquema_igual_al_del_almacen_incremental(self):
        """El camino desde cero y el incremental deben llegar al mismo sitio.

        Si divergen, una instalación nueva se comporta distinto que la del
        usuario que lleva meses migrando, y eso no avisa por ningún lado.

        Compara solo las tablas del núcleo: el almacén real puede tener además
        las de la capa propia (`propio/migraciones`), que esta instalación
        limpia no aplica a propósito. Lo que se exige es que **cada tabla del
        núcleo tenga exactamente las mismas columnas en los dos caminos**.

        El dominio de ejemplo también queda fuera, y por el motivo contrario:
        esta instalación sí lo aplica y el almacén real puede no tenerlo, o
        haberlo tenido y haberlo soltado. Es opt-in, así que su ausencia no es
        una divergencia.
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

        de_ejemplo = {
            catalogo.cargar_entidad(n)["tabla"]
            for n in catalogo.listar_entidades(con_ejemplos=True)
            if catalogo.es_ejemplo(n)
        }

        def es_comparable(tabla):
            return not any(tabla.startswith(t) for t in de_ejemplo)

        vivo = duckdb.connect(str(db.DB_PATH), read_only=True)
        try:
            nuevo = {t: c for t, c in columnas_por_tabla(self.con).items() if es_comparable(t)}
            existente = columnas_por_tabla(vivo)
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

    def test_el_dominio_de_ejemplo_arranca_con_sus_datos_dummy(self):
        """Un ejemplo vacío no enseña nada: los datos van en la migración."""
        self.assertGreater(self.escalar("SELECT count(*) FROM demo_venta"), 0)
        self.assertGreater(self.escalar("SELECT count(*) FROM demo_libro"), 0)

    def test_catalogos_del_repo_validan(self):
        for nombre in catalogo.listar_entidades(con_ejemplos=True):
            with self.subTest(entidad=nombre):
                catalogo.cargar_entidad(nombre)

    def test_cargas_del_repo_validan_contra_el_esquema(self):
        rutas_carga = sorted((ROOT / "cargas").glob("*.json")) + sorted(
            (ROOT / "ejemplos" / "cargas").glob("*.json")
        )
        for ruta in rutas_carga:
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
        del_repo = sorted((ROOT / "migraciones").glob("*.sql")) + sorted(
            (ROOT / "ejemplos" / "migraciones").glob("*.sql")
        )
        sin_decision = [
            p.name
            for p in del_repo
            if p.name not in con_decision and p.name not in arranque
        ]
        self.assertEqual(sin_decision, [], f"migraciones sin _decisiones: {sin_decision}")
