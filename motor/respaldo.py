"""Respaldos fechados del estado: parquet, no una copia del `.duckdb`.

Un respaldo tiene que seguir siendo legible el día que se necesita, que por
definición es un mal día. De ahí las tres decisiones de este módulo:

**Parquet y no una copia del fichero.** `EXPORT DATABASE` deja los datos en
parquet más un `schema.sql` y un `load.sql`, o sea que el respaldo es
autocontenido y se restaura con un `IMPORT DATABASE`. Medido sobre el almacén
real: 190,8 MB de `.duckdb` contra 8,9 MB de parquet+zstd, en 0,3 s. Pero lo
que decide no es el tamaño, es que el formato de fichero de DuckDB puede
cambiar entre versiones mayores —por eso `requirements.txt` fija `<2.0`— y un
binario de 200 MB que dentro de tres años no abre no es un respaldo. Parquet
lo lee cualquier cosa, incluido Excel o Power BI si hace falta rescatar una
tabla suelta sin montar nada.

**Los documentos van fuera del snapshot, en un espejo incremental.** Están
direccionados por su SHA-256, así que son inmutables: meterlos dentro de cada
copia guardaría N veces los mismos bytes. Van una sola vez a
`<respaldo>/documentos/`, con la misma estructura que el almacén vivo, y cada
snapshot los referencia por hash desde su `_documentos.parquet`.

**La retención no los toca nunca.** Los snapshots caducan; los documentos no.
Son los ficheros de origen y los justificantes, lo único genuinamente
irrecuperable —el resto se puede volver a cargar desde ellos—, y borrarlos
para ahorrar disco sería justo el error que el sistema entero existe para
evitar. Crecen despacio y de forma acotada, porque un fichero repetido no
ocupa dos veces.

La restauración **no se automatiza**, y es deliberado: `IMPORT DATABASE` sobre
un almacén con datos lo pisa. El manifiesto de cada snapshot lleva escritos
los pasos, y el gatillo lo aprieta una persona. Es el mismo criterio que
`db init`, que no mueve nada, y que la purga de documentos, que no se ejecuta
sola.
"""

import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

import duckdb

from . import entorno, rutas

# 'AAAAMMDD-HHMMSS': ordenable alfabéticamente, que es lo que permite tratar
# la lista de snapshots como una serie temporal sin parsear nada para ordenar.
FORMATO_SELLO = "%Y%m%d-%H%M%S"
LONGITUD_SELLO = 15

# Abuelo-padre-hijo. Cubre el caso feo, que no es perder el trabajo de ayer
# sino darse cuenta dentro de un mes de que algo se corrompió hace tres
# semanas: con solo N copias recientes, para entonces ya no hay a dónde volver.
RETENCION = {"diarios": 7, "semanales": 8, "mensuales": 12}

PASOS_RESTAURACION = [
    "Este respaldo se restaura a un almacén NUEVO, nunca encima de uno con datos.",
    "  1. python -m motor.cli db restaurar <este snapshot> --a restaurado.duckdb",
    "     (importa y verifica las filas contra el bloque 'filas' de este manifiesto)",
    "  2. Copia 'documentos/' —está en la RAÍZ del respaldo, no dentro del snapshot—",
    "     a la carpeta que diga `db rutas`, y 'propio/' al repositorio.",
    "  3. El 'config.local.json' de al lado es informativo: dice dónde vivía cada",
    "     cosa en la máquina original. En otra máquina esas rutas no existen.",
    "  4. Solo entonces, y a mano, sustituye el almacén vivo por el restaurado.",
]


def base_respaldo(cfg: dict = None) -> Path:
    """La carpeta de respaldos, o None si nadie la ha configurado."""
    return entorno.ruta("respaldo", cfg)


def snapshots(base) -> list:
    """Los snapshots que hay, del más antiguo al más reciente.

    Se filtra por forma del nombre y no por «todo lo que sea un directorio»:
    la carpeta de respaldos contiene también `documentos/`, que no es un
    snapshot y que la retención no debe ni mirar.
    """
    base = Path(base)
    if not base.is_dir():
        return []
    return sorted(
        hijo for hijo in base.iterdir()
        if hijo.is_dir() and _es_sello(hijo.name)
    )


def _es_sello(nombre: str) -> bool:
    try:
        datetime.strptime(nombre[:LONGITUD_SELLO], FORMATO_SELLO)
    except ValueError:
        return False
    return True


def _cubos(nombre: str) -> tuple:
    """(día, semana, mes) del snapshot, como claves de agrupación."""
    fecha = datetime.strptime(nombre[:LONGITUD_SELLO], FORMATO_SELLO)
    anyo_iso, semana_iso, _ = fecha.isocalendar()
    return fecha.strftime("%Y%m%d"), f"{anyo_iso}-W{semana_iso:02d}", fecha.strftime("%Y%m")


def a_conservar(nombres, diarios: int, semanales: int, mensuales: int) -> set:
    """Qué snapshots sobreviven a la retención abuelo-padre-hijo.

    De cada cubo temporal se conserva **el más reciente**, y se conservan los
    N cubos más recientes de cada tipo. Un mismo snapshot puede ser a la vez
    el diario de hoy, el semanal de esta semana y el mensual de este mes: eso
    no gasta tres plazas, gasta una, y es lo que hace que el esquema se
    estabilice en vez de crecer.
    """
    ordenados = sorted(nombres, reverse=True)
    conservados = set()
    for indice, cuantos in enumerate((diarios, semanales, mensuales)):
        cubos_vistos = []
        for nombre in ordenados:
            cubo = _cubos(nombre)[indice]
            if cubo in cubos_vistos:
                continue
            if len(cubos_vistos) >= cuantos:
                break
            cubos_vistos.append(cubo)
            conservados.add(nombre)
    return conservados


def _borrar_arbol(carpeta) -> bool:
    """Borrado que aguanta lo que hay donde vive un respaldo. Dice si lo logró.

    El sitio bueno para un respaldo es una carpeta sincronizada, y ahí el
    borrado falla de dos maneras conocidas: un fichero marcado de solo lectura
    (se arregla con chmod y reintento) y un handle abierto por el cliente de
    sincronización, que da «acceso denegado» y no se arregla con nada — es el
    mismo comportamiento que describe motor/entorno.py para el almacén.

    Por eso devuelve un booleano en vez de propagar: que no se pueda podar una
    copia vieja no es un fallo del respaldo, y la próxima pasada lo reintenta.
    """
    def reintentar(funcion, ruta, _excepcion):
        try:
            os.chmod(ruta, stat.S_IWRITE)
            funcion(ruta)
        except OSError:
            pass

    try:
        shutil.rmtree(carpeta, onexc=reintentar)
    except OSError:
        pass
    return not Path(carpeta).exists()


def aplicar_retencion(base, diarios: int = None, semanales: int = None,
                      mensuales: int = None) -> dict:
    """Poda los snapshots que sobran. Devuelve qué se fue y qué se resistió.

    Solo toca directorios con forma de sello. `documentos/` no entra aquí ni
    por accidente: ver el docstring del módulo.
    """
    diarios = RETENCION["diarios"] if diarios is None else diarios
    semanales = RETENCION["semanales"] if semanales is None else semanales
    mensuales = RETENCION["mensuales"] if mensuales is None else mensuales

    existentes = snapshots(base)
    conservados = a_conservar([s.name for s in existentes], diarios, semanales, mensuales)
    resultado = {"borrados": [], "no_borrados": []}
    for snapshot in existentes:
        if snapshot.name in conservados:
            continue
        clave = "borrados" if _borrar_arbol(snapshot) else "no_borrados"
        resultado[clave].append(snapshot.name)
    return resultado


def _espejar_documentos(origen, destino) -> dict:
    """Copia al espejo los documentos que aún no estén. Incremental de verdad.

    La comprobación es por existencia de la ruta, no por contenido, y es
    correcta justo porque el nombre del fichero **es** su hash: si está, es
    ese. Comparar bytes sería gastar E/S para confirmar lo que el nombre ya
    garantiza.
    """
    origen = Path(origen)
    resumen = {"copiados": 0, "ya_estaban": 0, "bytes_copiados": 0}
    if not origen.is_dir():
        return resumen

    destino = Path(destino)
    for fichero in origen.rglob("*"):
        if not fichero.is_file():
            continue
        copia = destino / fichero.relative_to(origen)
        if copia.is_file():
            resumen["ya_estaban"] += 1
            continue
        copia.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fichero, copia)
        resumen["copiados"] += 1
        resumen["bytes_copiados"] += fichero.stat().st_size
    return resumen


def _filas_por_tabla(con) -> dict:
    """Cuántas filas tiene cada tabla base, para poder verificar una
    restauración sin fiarse de que «parece que están todas»."""
    tablas = [
        f[0] for f in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY 1"
        ).fetchall()
    ]
    return {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tablas}


def resolver_snapshot(referencia=None, base=None):
    """El snapshot al que se refiere `referencia`: un nombre, una ruta, o el
    más reciente si no se dice nada.

    Se acepta el nombre suelto porque en una recuperación uno tiene delante la
    salida de `db respaldos`, no rutas absolutas.
    """
    base = base_respaldo() if base is None else Path(base)
    if referencia:
        candidata = Path(referencia)
        if not candidata.is_dir() and base is not None:
            candidata = base / referencia
        if not candidata.is_dir():
            raise ValueError(f"no encuentro el snapshot '{referencia}'")
        return candidata

    if base is None:
        raise ValueError(
            "no hay respaldo configurado y no has dicho qué snapshot restaurar"
        )
    existentes = snapshots(base)
    if not existentes:
        raise ValueError(f"no hay ningún snapshot en '{base}'")
    return existentes[-1]


def restaurar(snapshot, destino) -> dict:
    """Importa un snapshot a un almacén **nuevo** y lo verifica.

    Deliberadamente NO toca el almacén vivo, y se niega a escribir sobre un
    fichero que ya exista: `IMPORT DATABASE` sobre una base con datos la pisa,
    y el momento de recuperar es justo cuando menos margen hay para un error
    irreversible. Lo que sí automatiza es la verificación, que es la parte que
    todo el mundo se salta y la única que distingue una copia de una
    suposición.

    Devuelve el resumen con los descuadres, si los hay. Que los haya no es una
    excepción: es un resultado, y hay que poder verlo entero para saber qué
    tabla falla.
    """
    snapshot = Path(snapshot)
    destino = Path(destino)
    if destino.exists():
        raise ValueError(
            f"'{destino}' ya existe; restaura siempre a un fichero nuevo "
            "(IMPORT DATABASE pisa lo que haya)"
        )
    origen = snapshot / "almacen"
    if not (origen / "schema.sql").is_file():
        raise ValueError(f"'{snapshot}' no parece un snapshot: no hay almacen/schema.sql")

    manifiesto = {}
    fichero_manifiesto = snapshot / "manifiesto.json"
    if fichero_manifiesto.is_file():
        try:
            manifiesto = json.loads(fichero_manifiesto.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifiesto = {}

    destino.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(destino))
    try:
        con.execute(f"IMPORT DATABASE '{origen.as_posix()}'")
        filas = _filas_por_tabla(con)
        vistas = [
            f[0] for f in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'VIEW' ORDER BY 1"
            ).fetchall()
        ]
    finally:
        con.close()

    esperadas = manifiesto.get("filas", {})
    descuadres = [
        {"tabla": tabla, "esperadas": cuantas, "restauradas": filas.get(tabla)}
        for tabla, cuantas in esperadas.items()
        if filas.get(tabla) != cuantas
    ]
    faltan = sorted(set(esperadas) - set(filas))
    return {
        "snapshot": snapshot,
        "destino": destino,
        "manifiesto": manifiesto,
        "filas": filas,
        "vistas": vistas,
        "descuadres": descuadres,
        "tablas_ausentes": faltan,
        "verificado": bool(esperadas) and not descuadres and not faltan,
    }


def _conectar_para_leer(db_path: Path):
    """Solo lectura si se puede, normal si no.

    Se pide `read_only` porque respaldar no puede ser jamás lo que corrompa el
    almacén. Pero DuckDB no admite dos configuraciones distintas contra el
    mismo fichero **en el mismo proceso**: si quien llama ya tiene una conexión
    de escritura abierta, pedir solo lectura revienta. Desde la CLI no pasa
    nunca —cada comando es su propio proceso—, así que insistir dejaría el
    módulo inusable desde un script a cambio de nada.
    """
    try:
        return duckdb.connect(str(db_path), read_only=True)
    except duckdb.Error:
        return duckdb.connect(str(db_path))


def _carpeta_libre(base: Path, sello: str) -> Path:
    """El sello tiene resolución de segundo. Dos respaldos en el mismo segundo
    no deberían pasar, pero si pasan es peor perder uno que llevar sufijo."""
    candidata = base / sello
    intento = 2
    while candidata.exists():
        candidata = base / f"{sello}-{intento}"
        intento += 1
    return candidata


def respaldar(db_path=None, base=None, momento: datetime = None, documentos_dir=None,
              diarios: int = None, semanales: int = None, mensuales: int = None) -> dict:
    """Escribe un snapshot y aplica la retención. Devuelve el resumen.

    Levanta ValueError si no hay respaldo configurado o si no hay almacén que
    respaldar: las dos cosas son errores de instalación, no incidencias que
    haya que tragarse en silencio.
    """
    # Importados aquí y leídos como atributo de módulo, no al importar: es la
    # costura que usa el resto del repo para redirigir el almacén y los
    # documentos (ver pruebas/base.py). Congelarlos como valor por defecto de
    # un argumento haría que una prueba respaldase los documentos reales.
    from . import db as db_modulo
    from . import documentos as documentos_modulo

    base = base_respaldo() if base is None else Path(base)
    if base is None:
        raise ValueError(
            "no hay respaldo configurado; fíjalo con "
            "`db init --respaldo <carpeta>` (ver `db rutas`)"
        )

    db_path = Path(db_modulo.DB_PATH if db_path is None else db_path)
    if not db_path.is_file():
        raise ValueError(f"no hay almacén que respaldar en '{db_path}'")

    momento = datetime.now() if momento is None else momento
    base.mkdir(parents=True, exist_ok=True)
    carpeta = _carpeta_libre(base, momento.strftime(FORMATO_SELLO))
    carpeta.mkdir()

    con = _conectar_para_leer(db_path)
    try:
        destino_almacen = carpeta / "almacen"
        con.execute(
            f"EXPORT DATABASE '{destino_almacen.as_posix()}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        filas = _filas_por_tabla(con)
        migraciones = [
            f[0] for f in con.execute(
                "SELECT nombre_fichero FROM _migraciones ORDER BY nombre_fichero"
            ).fetchall()
        ]
    finally:
        con.close()

    # La capa propia entra en el respaldo aunque sea diminuta: son las
    # migraciones y las fichas de catálogo, y sin ellas el parquet son datos
    # sin modelo. Además está fuera del git del núcleo, así que puede no tener
    # ninguna otra copia en ningún sitio.
    copiado_propio = False
    if rutas.PROPIO_DIR.is_dir():
        shutil.copytree(rutas.PROPIO_DIR, carpeta / "propio")
        copiado_propio = True

    # La configuración de la máquina entra como **informativa**, no como algo
    # que restaurar a ciegas: en otra máquina esas rutas no existen. Pero es el
    # único sitio donde queda escrito dónde decidiste poner cada cosa, y sin
    # ella una recuperación empieza por intentar acordarse. Ocupa dos líneas.
    copiada_config = False
    if entorno.FICHERO_CONFIG.is_file():
        shutil.copy2(entorno.FICHERO_CONFIG, carpeta / entorno.FICHERO_CONFIG.name)
        copiada_config = True

    if documentos_dir is None:
        documentos_dir = documentos_modulo.DOCUMENTOS_DIR
    documentos = _espejar_documentos(documentos_dir, base / "documentos")

    manifiesto = {
        "creado": momento.isoformat(timespec="seconds"),
        "duckdb": duckdb.__version__,
        "almacen_origen": str(db_path),
        "bytes_almacen_origen": db_path.stat().st_size,
        "bytes_respaldo": sum(
            f.stat().st_size for f in carpeta.rglob("*") if f.is_file()
        ),
        "migraciones": migraciones,
        "filas": filas,
        "propio": copiado_propio,
        "config_local": copiada_config,
        "documentos": documentos,
        "restaurar": PASOS_RESTAURACION,
    }
    (carpeta / "manifiesto.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # El tamaño se recalcula: el manifiesto también ocupa, y un respaldo que
    # miente sobre lo que ocupa es un respaldo que descuadra al auditarlo.
    manifiesto["bytes_respaldo"] = sum(
        f.stat().st_size for f in carpeta.rglob("*") if f.is_file()
    )

    # La poda va después de escribir y de que el snapshot esté completo, y su
    # fallo no puede tumbar el respaldo: llegados aquí la copia ya está hecha
    # y es buena. Que no se haya podido borrar una copia vieja se cuenta, no
    # se lanza — si no, el hook de fin de sesión acabaría reportando un
    # respaldo fallido que en realidad existe y sirve.
    retencion = aplicar_retencion(base, diarios, semanales, mensuales)
    return {
        "carpeta": carpeta,
        "manifiesto": manifiesto,
        "borrados_por_retencion": retencion["borrados"],
        "no_borrados_por_retencion": retencion["no_borrados"],
        "snapshots": len(snapshots(base)),
    }
