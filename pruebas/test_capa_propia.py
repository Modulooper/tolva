"""Núcleo y capa propia: resolución de rutas y orden de migraciones."""

import json

from motor import cargas, catalogo, db, rutas
from pruebas.base import PruebaConAlmacen

DESCRIPCION = (
    "Carga que vive en la capa propia y no debe salir nunca del repositorio "
    "privado de quien la definió."
)


class PruebaResolucion(PruebaConAlmacen):
    def test_sin_capa_propia_solo_se_ve_el_nucleo(self):
        self.assertFalse(self.propio_dir.exists())
        self.assertEqual(rutas.carpetas("catalogo", self.catalogo_dir), [self.catalogo_dir])

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
        ficha = catalogo.cargar_entidad("ticket")
        ficha["descripcion"] = "Version adaptada en la capa propia."
        (self.carpeta_propia("catalogo") / "ticket.json").write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8"
        )
        self.assertEqual(
            catalogo.cargar_entidad("ticket")["descripcion"],
            "Version adaptada en la capa propia.",
        )
        # Y no aparece dos veces en el listado.
        self.assertEqual(catalogo.listar_entidades().count("ticket"), 1)

    def test_una_carga_propia_se_resuelve_por_nombre(self):
        definicion = {
            "nombre": "propia",
            "descripcion": DESCRIPCION,
            "carpeta": str(self.entrada_dir / "propia"),
            "patron": "*.csv",
            "formato": "csv",
            "delimitador": ";",
            "fila_cabecera": 1,
            "tabla_destino": "ticket",
            "mapping": [{"destino": "concepto", "operaciones": [{"tipo": "const", "valor": "otros"}]}],
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
        # 000 correría antes que 001_nucleo y la tabla ticket no existiría.
        (propias / "000_depende_del_nucleo.sql").write_text(
            "CREATE TABLE gasto_propio AS SELECT * FROM ticket WHERE false;", encoding="utf-8"
        )
        aplicadas = db.migrar(self.tmp / "otro.duckdb")
        self.assertEqual(aplicadas[-1], "000_depende_del_nucleo.sql")
        self.assertEqual(aplicadas[0], "001_nucleo.sql")

    def test_el_nucleo_no_referencia_tablas_de_la_capa_propia(self):
        """Si una migración del framework altera una tabla de negocio, la
        instalación limpia de cualquier otro se rompe. Pasó con
        `ALTER TABLE previ_transporte` dentro de 012_validaciones.sql."""
        from pruebas.base import ROOT

        propias = {
            ruta.stem.split("_", 1)[1]
            for ruta in (ROOT / "propio" / "migraciones").glob("*.sql")
        } if (ROOT / "propio" / "migraciones").is_dir() else set()

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
