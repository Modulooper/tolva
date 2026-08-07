"""Núcleo y capa propia: resolución de rutas y orden de migraciones."""

import json

from motor import cargas, catalogo, db, rutas
from pruebas.base import PruebaConAlmacen

DESCRIPCION = (
    "Carga que vive en la capa propia y no debe salir nunca del repositorio "
    "privado de quien la definió."
)


class PruebaResolucion(PruebaConAlmacen):
    def test_sin_capa_propia_solo_se_ve_el_nucleo_y_los_ejemplos(self):
        """Los ejemplos son una capa del repo y siempre están; la propia no."""
        self.assertFalse(self.propio_dir.exists())
        self.assertEqual(
            rutas.carpetas("catalogo", self.catalogo_dir),
            [self.catalogo_dir, rutas.EJEMPLOS_DIR / "catalogo"],
        )
        self.assertEqual(
            rutas.carpetas("catalogo", self.catalogo_dir, con_ejemplos=False), [self.catalogo_dir]
        )

    def test_la_capa_propia_suma_entidades_al_catalogo(self):
        nucleo = set(catalogo.listar_entidades())
        (self.carpeta_propia("catalogo") / "secreto.json").write_text(
            json.dumps(self.ficha_catalogo("secreto", {"nombre": ("varchar", True)})),
            encoding="utf-8",
        )
        self.assertEqual(set(catalogo.listar_entidades()) - nucleo, {"secreto"})
        self.assertEqual(catalogo.cargar_entidad("secreto")["tabla"], "secreto")

    def test_en_caso_de_mismo_nombre_gana_la_capa_propia(self):
        """Permite adaptar una ficha del núcleo sin bifurcar el repo."""
        ficha = catalogo.cargar_entidad("demo_cliente")
        ficha["descripcion"] = "Version adaptada en la capa propia."
        (self.carpeta_propia("catalogo") / "demo_cliente.json").write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8"
        )
        self.assertEqual(
            catalogo.cargar_entidad("demo_cliente")["descripcion"],
            "Version adaptada en la capa propia.",
        )
        # Y no aparece dos veces en el listado.
        self.assertEqual(catalogo.listar_entidades(con_ejemplos=True).count("demo_cliente"), 1)

    def test_una_carga_propia_se_resuelve_por_nombre(self):
        definicion = {
            "nombre": "propia",
            "descripcion": DESCRIPCION,
            "carpeta": str(self.entrada_dir / "propia"),
            "patron": "*.csv",
            "formato": "csv",
            "delimitador": ";",
            "fila_cabecera": 1,
            "tabla_destino": "demo_venta",
            "mapping": [{"destino": "canal", "operaciones": [{"tipo": "const", "valor": "tienda"}]}],
        }
        (self.carpeta_propia("cargas") / "propia.json").write_text(
            json.dumps(definicion, ensure_ascii=False), encoding="utf-8"
        )
        self.assertEqual(cargas.cargar("propia")["descripcion"], DESCRIPCION)
        self.assertIn(
            "propia", [r.stem for r in cargas.listar_definiciones()]
        )


class PruebaOrdenDeMigraciones(PruebaConAlmacen):
    def test_el_nucleo_se_aplica_antes_que_la_capa_propia(self):
        """Una migración propia puede apoyarse en tablas del framework;
        al revés nunca, así que el orden no es negociable."""
        propias = self.carpeta_propia("migraciones")
        # Nombre bajo a propósito: si el orden fuese alfabético global, este
        # 000 correría antes que 001_nucleo y _ejecuciones no existiría.
        (propias / "000_depende_del_nucleo.sql").write_text(
            "CREATE TABLE propia_del_nucleo AS SELECT * FROM _ejecuciones WHERE false;",
            encoding="utf-8",
        )
        aplicadas = db.migrar(self.tmp / "otro.duckdb")
        self.assertEqual(aplicadas[-1], "000_depende_del_nucleo.sql")
        self.assertEqual(aplicadas[0], "001_nucleo.sql")

    def test_la_capa_propia_real_se_instala_desde_cero(self):
        """Las demás pruebas redirigen `propio/` a un temporal, así que la capa
        propia de verdad no la aplica nadie hasta que alguien clona y migra.

        Se comprueba porque falló: al mover `ticket` al núcleo→propio, su
        migración pasó a crear la columna `ejecucion_id` que antes añadía un
        `ALTER` posterior, y `006_ticket_concepto_otros.sql` —que recrea la
        tabla para ampliar un CHECK— seguía declarando las nueve columnas de
        antes. En el almacén ya migrado no se nota: la migración está aplicada
        y no vuelve a correr. Solo revienta en la instalación limpia, que es
        justo la que nadie mira.
        """
        from pruebas.base import ROOT

        if not (ROOT / "propio" / "migraciones").is_dir():
            self.skipTest("no hay capa propia en este árbol")

        rutas.PROPIO_DIR = ROOT / "propio"
        try:
            db.migrar(self.tmp / "con_propio_real.duckdb", con_ejemplos=True)
        finally:
            rutas.PROPIO_DIR = self.propio_dir

    def test_git_no_versiona_nada_de_la_capa_propia(self):
        """La frontera no es el `.gitignore`, es el índice de git.

        `.gitignore` solo protege lo que git aún no sigue. Al mover una tabla
        del núcleo a `propio/` con `git mv`, el fichero se queda en el índice
        en su ruta nueva —ignorada o no— y el siguiente commit lo publica. Pasó
        con 13 ficheros (fichas de cliente, ticket, idea y movimientos
        bancarios) y se cazó a mano justo antes de commitear. Se arregla con
        `git rm --cached`, pero lo que hace falta es que salte solo.
        """
        import subprocess

        from pruebas.base import ROOT

        if not (ROOT / ".git").exists():
            self.skipTest("no es un repositorio git")

        try:
            salida = subprocess.run(
                ["git", "ls-files", "--cached", "propio/"],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git no disponible")
        if salida.returncode != 0:
            self.skipTest("git no pudo leer el índice")

        versionados = [l for l in salida.stdout.splitlines() if l.strip()]
        self.assertEqual(
            versionados, [],
            "hay ficheros de la capa propia en el índice de git: se publicarían "
            f"en el próximo commit. Sácalos con `git rm --cached`. {versionados}",
        )

    def test_el_nucleo_no_referencia_tablas_de_la_capa_propia(self):
        """Si una migración del framework altera una tabla de negocio, la
        instalación limpia de cualquier otro se rompe. Pasó con
        `ALTER TABLE previ_transporte` dentro de 012_validaciones.sql.

        Los nombres salen de las **fichas** de `propio/catalogo/`, no del
        nombre del fichero de migración: deducirlos del nombre solo acierta
        cuando la migración se llama como su tabla, y `000_dimensiones.sql`
        crea tres (persona, cliente, proyecto) sin llamarse como ninguna.
        """
        import json as _json

        from pruebas.base import ROOT

        fichas = ROOT / "propio" / "catalogo"
        propias = {
            _json.loads(ruta.read_text(encoding="utf-8"))["tabla"]
            for ruta in fichas.glob("*.json")
        } if fichas.is_dir() else set()

        if not propias:
            self.skipTest("no hay capa propia en este árbol")

        ofensores = []
        for ruta in sorted((ROOT / "migraciones").glob("*.sql")):
            sql = ruta.read_text(encoding="utf-8")
            # Solo el DDL: las menciones en el texto de _decisiones son prosa.
            ddl = "\n".join(l for l in sql.splitlines() if not l.strip().startswith(("--", "'")))
            for tabla in propias:
                if f"TABLE {tabla}" in ddl:
                    ofensores.append(f"{ruta.name} -> {tabla}")
        self.assertEqual(ofensores, [], f"el núcleo toca tablas propias: {ofensores}")
