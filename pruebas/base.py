"""Andamiaje común de las pruebas.

Cada prueba corre contra un almacén **nuevo** en un directorio temporal, con
su propio catálogo, sus cargas y su almacén de documentos. Nada toca
`datos/almacen.duckdb` ni `datos/documentos/`: si una prueba borra o purga,
solo se lleva por delante su propia copia.

El catálogo real se copia al temporal en vez de inventarse uno: así las
pruebas también comprueban que las fichas que hay en el repo son válidas y
siguen casando con el esquema que crean las migraciones.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from motor import cargas, catalogo, db, documentos, rutas, salidas

ROOT = Path(__file__).resolve().parent.parent


class PruebaConAlmacen(unittest.TestCase):
    """Almacén migrado desde cero y aislado, uno por prueba."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="claudetl_pruebas_"))
        self.catalogo_dir = self.tmp / "catalogo"
        self.cargas_dir = self.tmp / "cargas"
        self.entrada_dir = self.tmp / "entrada"
        self.export_dir = self.tmp / "export"
        self.documentos_dir = self.tmp / "documentos"

        shutil.copytree(ROOT / "catalogo", self.catalogo_dir)
        for carpeta in (self.cargas_dir, self.entrada_dir, self.export_dir):
            carpeta.mkdir(parents=True, exist_ok=True)

        # La capa propia apunta al temporal y arranca sin existir: las pruebas
        # que la necesiten crean sus carpetas con `carpeta_propia()`.
        self.propio_dir = self.tmp / "propio"

        self._originales = {
            (catalogo, "CATALOGO_DIR"): catalogo.CATALOGO_DIR,
            (cargas, "CARGAS_DIR"): cargas.CARGAS_DIR,
            (documentos, "DOCUMENTOS_DIR"): documentos.DOCUMENTOS_DIR,
            (salidas, "EXPORT_DIR"): salidas.EXPORT_DIR,
            (rutas, "PROPIO_DIR"): rutas.PROPIO_DIR,
        }
        catalogo.CATALOGO_DIR = self.catalogo_dir
        cargas.CARGAS_DIR = self.cargas_dir
        documentos.DOCUMENTOS_DIR = self.documentos_dir
        salidas.EXPORT_DIR = self.export_dir
        rutas.PROPIO_DIR = self.propio_dir

        # Migrar DESPUÉS de redirigir la capa propia: si no, la suite aplicaría
        # las migraciones privadas de quien tenga el repo, y dejaría de probar
        # el framework para probar su instalación concreta.
        #
        # Con el dominio de ejemplo (`ejemplos/`): la suite necesita tablas
        # sobre las que probar, y antes usaba `ticket` e `idea`. Eso ataba el
        # framework a dos procesos de negocio concretos y es lo que impedía
        # sacarlos del núcleo. El material de prueba es ahora la librería
        # inventada, que no es de nadie.
        self.db_path = self.tmp / "almacen.duckdb"
        self.migraciones_aplicadas = db.migrar(self.db_path, con_ejemplos=True)

        self.con = db.conectar(self.db_path)

    def tearDown(self):
        try:
            self.con.close()
        finally:
            for (modulo, atributo), valor in self._originales.items():
                setattr(modulo, atributo, valor)
            shutil.rmtree(self.tmp, ignore_errors=True)

    # --- utilidades ---------------------------------------------------

    def escribir_csv(self, nombre_carpeta: str, nombre_fichero: str, contenido: str) -> Path:
        carpeta = self.entrada_dir / nombre_carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / nombre_fichero
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def carpeta_propia(self, nombre: str):
        """Crea y devuelve `propio/<nombre>` en el temporal."""
        carpeta = self.propio_dir / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta

    def escribir_carga(self, definicion: dict) -> str:
        """Guarda la definición y devuelve su nombre.

        La `descripcion` es obligatoria en el esquema real; aquí se rellena
        por defecto para que cada prueba declare solo lo que está probando.
        Las pruebas de la propia descripción la pasan explícitamente.
        """
        definicion.setdefault(
            "descripcion",
            "Carga de prueba del andamiaje: no describe nada real, solo "
            "satisface el mínimo del esquema.",
        )
        definicion.setdefault("carpeta", str(self.entrada_dir / definicion["nombre"]))
        ruta = self.cargas_dir / f"{definicion['nombre']}.json"
        ruta.write_text(json.dumps(definicion, ensure_ascii=False, indent=2), encoding="utf-8")
        return definicion["nombre"]

    def escribir_catalogo(self, entidad: dict) -> None:
        ruta = self.catalogo_dir / f"{entidad['entidad']}.json"
        ruta.write_text(json.dumps(entidad, ensure_ascii=False, indent=2), encoding="utf-8")

    def ficha_catalogo(self, entidad: str, campos: dict, **extra) -> dict:
        """Ficha mínima: {nombre_campo: (tipo, obligatorio)}."""
        return {
            "entidad": entidad,
            "tabla": entidad,
            "descripcion": f"Tabla de prueba {entidad}.",
            "campos": {
                nombre: {
                    "tipo": tipo,
                    "obligatorio": obligatorio,
                    "descripcion": nombre,
                    "sinonimos": [],
                }
                for nombre, (tipo, obligatorio) in campos.items()
            },
            "relaciones": [],
            **extra,
        }

    def filas(self, sql: str, parametros=None):
        return self.con.execute(sql, parametros or []).fetchall()

    def escalar(self, sql: str, parametros=None):
        return self.con.execute(sql, parametros or []).fetchone()[0]
