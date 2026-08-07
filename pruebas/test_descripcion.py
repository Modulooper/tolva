"""Descripción obligatoria de las cargas y salida del CLI en consola cp1252."""

import json
import pathlib

from motor import cargas, diagrama
from pruebas.base import ROOT, PruebaConAlmacen

DESCRIPCION_VALIDA = (
    "Extracto mensual del banco para llevar el libro y conciliarlo contra "
    "facturas. Cada fila es un apunte tal cual lo da el banco."
)


class PruebaDescripcionCarga(PruebaConAlmacen):
    def definicion_minima(self, **extra):
        definicion = {
            "nombre": "prueba",
            "descripcion": DESCRIPCION_VALIDA,
            "patron": "*.csv",
            "formato": "csv",
            "delimitador": ";",
            "fila_cabecera": 1,
            "tabla_destino": "demo_venta",
            "mapping": [{"destino": "canal", "operaciones": [{"tipo": "const", "valor": "tienda"}]}],
        }
        definicion.update(extra)
        definicion.setdefault("carpeta", str(self.entrada_dir / "prueba"))
        return definicion

    def test_sin_descripcion_no_valida(self):
        definicion = self.definicion_minima()
        del definicion["descripcion"]
        errores = cargas.validar(definicion, self.con)
        self.assertTrue(any("descripcion" in e for e in errores), errores)

    def test_descripcion_de_rotulo_no_vale(self):
        """El mínimo existe para cortar los 'Carga de bancos'."""
        errores = cargas.validar(self.definicion_minima(descripcion="Carga de bancos"), self.con)
        self.assertTrue(any("descripcion" in e for e in errores), errores)

    def test_descripcion_suficiente_valida(self):
        self.assertEqual(cargas.validar(self.definicion_minima(), self.con), [])


class PruebaDescripcionesDelRepo(PruebaConAlmacen):
    def test_las_cargas_del_repo_explican_para_que_se_hacen(self):
        for ruta in sorted((ROOT / "cargas").glob("*.json")):
            with self.subTest(carga=ruta.stem):
                definicion = json.loads(ruta.read_text(encoding="utf-8"))
                descripcion = definicion.get("descripcion", "")
                self.assertGreaterEqual(len(descripcion), 40)
                # Un rótulo repite el nombre; una descripción útil dice más.
                self.assertNotEqual(descripcion.strip().lower(), definicion["nombre"].lower())

    def test_cargas_declaradas_las_devuelve_todas(self):
        declaradas = diagrama.cargas_declaradas()
        nombres = {n for n, _, _ in declaradas}
        self.assertEqual(nombres, {p.stem for p in cargas.CARGAS_DIR.glob("*.json")})
        for _, destino, descripcion in declaradas:
            self.assertTrue(destino)
            self.assertTrue(descripcion)


class PruebaSalidaEnConsolaWindows(PruebaConAlmacen):
    """La consola de Windows va en cp1252: un carácter fuera de esa tabla no
    degrada la salida, aborta el comando con UnicodeEncodeError. Se coló una
    flecha U+2192 en `db diagrama` y lo dejó con exit 1."""

    def test_ningun_print_del_motor_saca_caracteres_fuera_de_cp1252(self):
        """Solo mira líneas con `print(`: un U+FFFD dentro de un literal que
        sirve para *limpiar* ese carácter (esquema.py) no se imprime nunca, y
        marcarlo sería ruido. Lo que rompe es lo que sale por consola."""
        ofensores = []
        for fichero in sorted((ROOT / "motor").glob("*.py")):
            for numero, linea in enumerate(fichero.read_text(encoding="utf-8").splitlines(), 1):
                if "print(" not in linea:
                    continue
                for caracter in set(linea):
                    if ord(caracter) > 127:
                        try:
                            caracter.encode("cp1252")
                        except UnicodeEncodeError:
                            ofensores.append(f"{fichero.name}:{numero} U+{ord(caracter):04X}")
        self.assertEqual(ofensores, [], f"no representables en cp1252: {ofensores}")

    def test_las_descripciones_del_repo_son_imprimibles(self):
        for ruta in sorted((ROOT / "cargas").glob("*.json")):
            with self.subTest(carga=ruta.stem):
                definicion = json.loads(ruta.read_text(encoding="utf-8"))
                definicion["descripcion"].encode("cp1252")
