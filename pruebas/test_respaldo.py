"""Respaldos: qué se copia, qué se conserva y si de verdad se puede restaurar."""

import json
import os
import stat
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import duckdb

from motor import documentos, entorno, respaldo
from pruebas.base import PruebaConAlmacen
from pruebas.test_entorno import BaseEntorno


class PruebaAjusteRespaldo(BaseEntorno):
    """El único ajuste opt-in de los cuatro."""

    def test_sin_configurar_no_hay_ruta_ni_se_finge_que_la_hay(self):
        """Un 'valor por defecto' aquí haría creer que se está respaldando."""
        self.assertIsNone(entorno.ruta("respaldo"))
        self.assertEqual(entorno.origen("respaldo"), "sin configurar")

    def test_los_otros_tres_siguen_teniendo_defecto(self):
        for clave in ("datos", "documentos", "export"):
            with self.subTest(ajuste=clave):
                self.assertIsNotNone(entorno.ruta(clave))
                self.assertEqual(entorno.origen(clave), "valor por defecto")

    def test_se_configura_como_cualquier_otro(self):
        entorno.escribir_config({"respaldo": str(Path.home() / "OneDrive" / "R")}, self.config)
        self.assertEqual(entorno.ruta("respaldo"), Path.home() / "OneDrive" / "R")
        self.assertEqual(entorno.origen("respaldo"), "config.local.json")

    def test_la_variable_de_entorno_tambien(self):
        with mock.patch.dict(os.environ, {"TOLVA_RESPALDO": "/de/la/variable"}):
            self.assertEqual(entorno.ruta("respaldo"), Path("/de/la/variable"))


class PruebaAvisoDeRespaldo(BaseEntorno):
    """El aviso es el inverso al de los datos: aquí OneDrive es la respuesta
    buena, no el problema."""

    def _configurar(self, datos, respaldo_en):
        entorno.escribir_config(
            {"datos": str(datos), "documentos": str(datos), "respaldo": str(respaldo_en)},
            self.config,
        )

    def test_sincronizado_esta_a_salvo(self):
        """Justo la ruta que en `datos` dispararía un OJO."""
        self._configurar(Path.home() / "local", Path.home() / "OneDrive - x" / "Respaldo")
        self.assertTrue(entorno.respaldo_a_salvo())
        self.assertIsNone(entorno.aviso_de_respaldo())

    def test_otro_disco_tambien_basta(self):
        """No todo el mundo tiene sincronización, y otro disco ya cubre el
        fallo más probable."""
        self._configurar(Path("C:/datos"), Path("D:/respaldo"))
        if Path("C:/datos").drive == Path("D:/respaldo").drive:
            self.skipTest("sin noción de unidad en esta plataforma")
        self.assertTrue(entorno.respaldo_a_salvo())

    def test_mismo_disco_y_sin_sincronizar_avisa(self):
        self._configurar(Path.home() / "datos", Path.home() / "datos_copia")
        self.assertFalse(entorno.respaldo_a_salvo())
        aviso = entorno.aviso_de_respaldo()
        self.assertIn("no sale ni de la máquina ni del", aviso)
        self.assertIn("db init", aviso)  # un aviso que no dice qué hacer es ruido

    def test_sin_configurar_avisa_de_otra_cosa(self):
        """No es el mismo problema «está mal puesto» que «no existe»."""
        aviso = entorno.aviso_de_respaldo()
        self.assertIn("no hay respaldo configurado", aviso)
        self.assertFalse(entorno.respaldo_a_salvo())


class PruebaRetencion(unittest.TestCase):
    """Abuelo-padre-hijo, sobre nombres sintéticos: la política se puede
    comprobar sin escribir un solo byte."""

    def test_conserva_el_mas_reciente_de_cada_dia(self):
        nombres = ["20260801-090000", "20260801-180000", "20260802-090000"]
        conservados = respaldo.a_conservar(nombres, diarios=7, semanales=0, mensuales=0)
        self.assertEqual(conservados, {"20260801-180000", "20260802-090000"})

    def test_un_snapshot_puede_ocupar_las_tres_plazas_a_la_vez(self):
        """Es lo que hace que el esquema se estabilice en vez de crecer."""
        conservados = respaldo.a_conservar(["20260805-100000"], 7, 8, 12)
        self.assertEqual(conservados, {"20260805-100000"})

    def test_lo_viejo_sobrevive_por_la_via_semanal_y_mensual(self):
        """El objetivo del esquema: darse cuenta tarde de algo y aún tener a
        dónde volver.

        Con un respaldo diario durante ocho meses, lo que se conserva de enero
        no es enero entero: es **un** snapshot, el último del mes. Que es
        exactamente el trato — profundidad a cambio de resolución.
        """
        nombres = [
            f"2026{mes:02d}{dia:02d}-120000"
            for mes in range(1, 9)
            for dia in range(1, 29)
        ]
        conservados = respaldo.a_conservar(nombres, diarios=7, semanales=8, mensuales=12)

        self.assertIn("20260828-120000", conservados)   # el diario más reciente
        self.assertIn("20260128-120000", conservados)   # el mensual de enero
        de_enero = [n for n in conservados if n.startswith("202601")]
        self.assertEqual(de_enero, ["20260128-120000"])
        # Se estabiliza: 8 meses de copias diarias no son 224 carpetas.
        self.assertLessEqual(len(conservados), 7 + 8 + 12)

    def test_cuantos_cubos_se_conservan_es_lo_que_se_pide(self):
        nombres = [f"202608{dia:02d}-120000" for dia in range(1, 32)]
        conservados = respaldo.a_conservar(nombres, diarios=3, semanales=0, mensuales=0)
        self.assertEqual(
            conservados, {"20260831-120000", "20260830-120000", "20260829-120000"}
        )

    def test_sin_snapshots_no_se_rompe(self):
        self.assertEqual(respaldo.a_conservar([], 7, 8, 12), set())


class PruebaRespaldar(PruebaConAlmacen):
    def setUp(self):
        super().setUp()
        self.base = self.tmp / "respaldos"

    def _respaldar(self, dia=5, hora=12, **kwargs):
        return respaldo.respaldar(
            db_path=self.db_path,
            base=self.base,
            momento=datetime(2026, 8, dia, hora, 0, 0),
            documentos_dir=self.documentos_dir,
            **kwargs,
        )

    def test_el_snapshot_lleva_export_y_manifiesto(self):
        resultado = self._respaldar()
        carpeta = resultado["carpeta"]
        self.assertEqual(carpeta.name, "20260805-120000")
        # schema.sql y load.sql son lo que hace el export autocontenido.
        self.assertTrue((carpeta / "almacen" / "schema.sql").is_file())
        self.assertTrue((carpeta / "almacen" / "load.sql").is_file())
        self.assertTrue((carpeta / "manifiesto.json").is_file())
        self.assertTrue(list((carpeta / "almacen").glob("*.parquet")))

    def test_el_manifiesto_permite_verificar_una_restauracion(self):
        manifiesto = self._respaldar()["manifiesto"]
        self.assertEqual(manifiesto["duckdb"], duckdb.__version__)
        self.assertIn("_migraciones", manifiesto["filas"])
        self.assertEqual(
            manifiesto["filas"]["demo_venta"],
            self.escalar("SELECT count(*) FROM demo_venta"),
        )
        self.assertTrue(manifiesto["migraciones"])
        self.assertTrue(manifiesto["restaurar"])

    def test_el_respaldo_se_puede_restaurar_de_verdad(self):
        """Lo único que convierte una carpeta de ficheros en un respaldo.

        Un export que nadie ha importado nunca es una suposición: se importa a
        un almacén nuevo y se comparan las filas contra el original.
        """
        carpeta = self._respaldar()["carpeta"]
        restaurado = self.tmp / "restaurado.duckdb"
        con = duckdb.connect(str(restaurado))
        try:
            con.execute(f"IMPORT DATABASE '{(carpeta / 'almacen').as_posix()}'")
            for tabla in ("demo_venta", "demo_libro", "_migraciones", "_decisiones"):
                with self.subTest(tabla=tabla):
                    self.assertEqual(
                        con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0],
                        self.escalar(f"SELECT count(*) FROM {tabla}"),
                    )
        finally:
            con.close()

    def test_no_hay_respaldo_sin_configurar(self):
        with mock.patch.object(respaldo, "base_respaldo", return_value=None):
            with self.assertRaises(ValueError):
                respaldo.respaldar(db_path=self.db_path)

    def test_sin_almacen_falla_en_vez_de_dejar_una_carpeta_vacia(self):
        with self.assertRaises(ValueError):
            respaldo.respaldar(db_path=self.tmp / "no_existe.duckdb", base=self.base)

    def test_dos_respaldos_en_el_mismo_segundo_no_se_pisan(self):
        """El sello tiene resolución de segundo. Que dos caigan en el mismo no
        debería pasar, pero si pasa es peor perder uno en silencio que llevar
        sufijo.

        Y acto seguido la retención se lleva el primero, que también es lo
        correcto: son del mismo día, y de cada día se conserva el más reciente.
        """
        primero = self._respaldar()["carpeta"]
        segundo = self._respaldar()
        self.assertNotEqual(primero.name, segundo["carpeta"].name)
        self.assertEqual(segundo["borrados_por_retencion"], [primero.name])
        self.assertEqual(segundo["snapshots"], 1)

    def test_la_capa_propia_entra_en_el_respaldo(self):
        """Sin las migraciones y las fichas, el parquet son datos sin modelo.
        Y al estar fuera del git del núcleo puede no tener otra copia."""
        (self.carpeta_propia("catalogo") / "cosa.json").write_text("{}", encoding="utf-8")
        carpeta = self._respaldar()["carpeta"]
        self.assertTrue((carpeta / "propio" / "catalogo" / "cosa.json").is_file())

    def test_sin_capa_propia_no_pasa_nada(self):
        manifiesto = self._respaldar()["manifiesto"]
        self.assertFalse(manifiesto["propio"])


class PruebaRestaurar(PruebaConAlmacen):
    """La otra mitad. Un respaldo que nadie ha restaurado es una suposición."""

    def setUp(self):
        super().setUp()
        self.base = self.tmp / "respaldos"
        self.snapshot = respaldo.respaldar(
            db_path=self.db_path, base=self.base,
            momento=datetime(2026, 8, 5, 12, 0, 0),
            documentos_dir=self.documentos_dir,
        )["carpeta"]

    def test_restaura_y_verifica_contra_el_manifiesto(self):
        resultado = respaldo.restaurar(self.snapshot, self.tmp / "nuevo.duckdb")
        self.assertTrue(resultado["verificado"])
        self.assertEqual(resultado["descuadres"], [])
        self.assertEqual(
            resultado["filas"]["demo_venta"],
            self.escalar("SELECT count(*) FROM demo_venta"),
        )

    def test_las_vistas_de_consumo_tambien_vuelven(self):
        """Van en el schema.sql del export. Si no volvieran, el almacén
        restaurado tendría los datos pero no por dónde consumirlos."""
        vivas = {
            f[0] for f in self.filas(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'VIEW'"
            )
        }
        self.assertTrue(vivas, "el dominio de ejemplo debería traer vistas de consumo")
        resultado = respaldo.restaurar(self.snapshot, self.tmp / "con_vistas.duckdb")
        self.assertEqual(set(resultado["vistas"]), vivas)

    def test_se_niega_a_pisar_un_almacen_existente(self):
        """El momento de recuperar es justo cuando menos margen hay para un
        error irreversible, e IMPORT DATABASE pisa lo que haya."""
        with self.assertRaises(ValueError) as caso:
            respaldo.restaurar(self.snapshot, self.db_path)
        self.assertIn("ya existe", str(caso.exception))
        # Y el almacén vivo sigue intacto.
        self.assertGreater(self.escalar("SELECT count(*) FROM demo_venta"), 0)

    def test_un_descuadre_se_ve_en_vez_de_pasar_desapercibido(self):
        """Es lo único que distingue verificar de dar por bueno."""
        manifiesto = json.loads((self.snapshot / "manifiesto.json").read_text(encoding="utf-8"))
        manifiesto["filas"]["demo_venta"] += 7
        (self.snapshot / "manifiesto.json").write_text(
            json.dumps(manifiesto), encoding="utf-8"
        )
        resultado = respaldo.restaurar(self.snapshot, self.tmp / "descuadrado.duckdb")
        self.assertFalse(resultado["verificado"])
        self.assertEqual(len(resultado["descuadres"]), 1)
        self.assertEqual(resultado["descuadres"][0]["tabla"], "demo_venta")

    def test_una_carpeta_que_no_es_un_snapshot_se_rechaza(self):
        with self.assertRaises(ValueError):
            respaldo.restaurar(self.tmp, self.tmp / "x.duckdb")

    def test_sin_decir_cual_se_coge_el_mas_reciente(self):
        respaldo.respaldar(
            db_path=self.db_path, base=self.base,
            momento=datetime(2026, 8, 9, 12, 0, 0),
            documentos_dir=self.documentos_dir,
        )
        elegido = respaldo.resolver_snapshot(base=self.base)
        self.assertEqual(elegido.name, "20260809-120000")

    def test_se_puede_pedir_por_nombre_suelto(self):
        """En una recuperación uno tiene delante la salida de `db respaldos`,
        no rutas absolutas."""
        elegido = respaldo.resolver_snapshot("20260805-120000", base=self.base)
        self.assertEqual(elegido, self.snapshot)

    def test_un_snapshot_inventado_falla_claro(self):
        with self.assertRaises(ValueError):
            respaldo.resolver_snapshot("20990101-000000", base=self.base)

    def test_la_configuracion_de_la_maquina_va_dentro(self):
        """Informativa, pero es el único sitio donde queda escrito dónde
        vivía cada cosa.

        El fichero se redirige al temporal: apuntar al de verdad haría que la
        suite reescribiese la configuración de quien la ejecuta.
        """
        falso = self.tmp / "config.local.json"
        falso.write_text('{"datos": "/x"}', encoding="utf-8")
        with mock.patch.object(entorno, "FICHERO_CONFIG", falso):
            snapshot = respaldo.respaldar(
                db_path=self.db_path, base=self.base,
                momento=datetime(2026, 8, 7, 12, 0, 0),
                documentos_dir=self.documentos_dir,
            )["carpeta"]
        self.assertTrue((snapshot / "config.local.json").is_file())
        self.assertIn('"datos"', (snapshot / "config.local.json").read_text(encoding="utf-8"))


class PruebaEspejoDeDocumentos(PruebaConAlmacen):
    """Los documentos van fuera del snapshot y no se duplican."""

    def setUp(self):
        super().setUp()
        self.base = self.tmp / "respaldos"
        origen = self.documentos_dir / "ab"
        origen.mkdir(parents=True)
        (origen / "abcdef.csv").write_text("a;b\n1;2\n", encoding="utf-8")

    def _respaldar(self, dia):
        return respaldo.respaldar(
            db_path=self.db_path, base=self.base,
            momento=datetime(2026, 8, dia, 12, 0, 0),
            documentos_dir=self.documentos_dir,
        )

    def test_se_espejan_a_la_raiz_y_no_dentro_del_snapshot(self):
        resultado = self._respaldar(1)
        self.assertTrue((self.base / "documentos" / "ab" / "abcdef.csv").is_file())
        self.assertFalse((resultado["carpeta"] / "documentos").exists())
        self.assertEqual(resultado["manifiesto"]["documentos"]["copiados"], 1)

    def test_el_segundo_respaldo_no_los_vuelve_a_copiar(self):
        """Son inmutables por hash: si el fichero está, es ese. Duplicarlos en
        cada snapshot multiplicaría los mismos bytes por N."""
        self._respaldar(1)
        segundo = self._respaldar(2)
        self.assertEqual(segundo["manifiesto"]["documentos"]["copiados"], 0)
        self.assertEqual(segundo["manifiesto"]["documentos"]["ya_estaban"], 1)

    def test_la_retencion_no_toca_los_documentos(self):
        """Lo único genuinamente irrecuperable: el resto de tablas se puede
        volver a cargar desde ellos."""
        for dia in range(1, 6):
            self._respaldar(dia)
        respaldo.aplicar_retencion(self.base, diarios=1, semanales=0, mensuales=0)
        self.assertEqual(len(respaldo.snapshots(self.base)), 1)
        self.assertTrue((self.base / "documentos" / "ab" / "abcdef.csv").is_file())

    def test_el_espejo_no_cuenta_como_snapshot(self):
        self._respaldar(1)
        self.assertEqual([s.name for s in respaldo.snapshots(self.base)], ["20260801-120000"])


class PruebaRetencionAlRespaldar(PruebaConAlmacen):
    def test_respaldar_aplica_la_retencion_sobre_la_marcha(self):
        base = self.tmp / "respaldos"
        for dia in range(1, 5):
            resultado = respaldo.respaldar(
                db_path=self.db_path, base=base,
                momento=datetime(2026, 8, dia, 12, 0, 0),
                documentos_dir=self.documentos_dir,
                diarios=2, semanales=0, mensuales=0,
            )
        self.assertEqual(resultado["snapshots"], 2)
        self.assertEqual(
            [s.name for s in respaldo.snapshots(base)],
            ["20260803-120000", "20260804-120000"],
        )

    def test_lo_borrado_se_dice(self):
        """Una retención silenciosa se lee como 'no se ha borrado nada'."""
        base = self.tmp / "respaldos"
        for dia in (1, 2):
            resultado = respaldo.respaldar(
                db_path=self.db_path, base=base,
                momento=datetime(2026, 8, dia, 12, 0, 0),
                documentos_dir=self.documentos_dir,
                diarios=1, semanales=0, mensuales=0,
            )
        self.assertEqual(resultado["borrados_por_retencion"], ["20260801-120000"])


class PruebaCarpetaDeRespaldos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="respaldos_"))

    def test_solo_cuentan_los_directorios_con_forma_de_sello(self):
        for nombre in ("20260801-120000", "documentos", "notas", "20260802-120000"):
            (self.tmp / nombre).mkdir()
        (self.tmp / "suelto.txt").write_text("x", encoding="utf-8")
        self.assertEqual(
            [s.name for s in respaldo.snapshots(self.tmp)],
            ["20260801-120000", "20260802-120000"],
        )

    def test_una_carpeta_que_no_existe_no_es_un_error(self):
        self.assertEqual(respaldo.snapshots(self.tmp / "nada"), [])

    def test_borra_aunque_haya_ficheros_de_solo_lectura(self):
        """Donde debe vivir un respaldo —una carpeta sincronizada— es normal
        encontrarse atributos raros puestos por el cliente de sync."""
        viejo = self.tmp / "20260801-120000"
        viejo.mkdir()
        fichero = viejo / "parquet.parquet"
        fichero.write_text("x", encoding="utf-8")
        os.chmod(fichero, stat.S_IREAD)
        (self.tmp / "20260802-120000").mkdir()

        resultado = respaldo.aplicar_retencion(self.tmp, diarios=1, semanales=0, mensuales=0)
        self.assertEqual(resultado["borrados"], ["20260801-120000"])
        self.assertEqual(resultado["no_borrados"], [])

    def test_lo_que_no_se_puede_borrar_se_cuenta_en_vez_de_reventar(self):
        """Un handle abierto por OneDrive no se arregla con nada, pero tampoco
        puede tumbar un respaldo que ya está escrito y es bueno."""
        (self.tmp / "20260801-120000").mkdir()
        (self.tmp / "20260802-120000").mkdir()
        with mock.patch.object(respaldo, "_borrar_arbol", return_value=False):
            resultado = respaldo.aplicar_retencion(self.tmp, diarios=1, semanales=0, mensuales=0)
        self.assertEqual(resultado["borrados"], [])
        self.assertEqual(resultado["no_borrados"], ["20260801-120000"])


if __name__ == "__main__":
    unittest.main()
