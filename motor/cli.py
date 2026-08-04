"""CLI: db migrar/consultar | etl validar/dry-run/ejecutar/estado."""

import argparse
import sys

import duckdb

from . import cargas, db, motor_etl


def _imprimir_tabla(columnas, filas) -> None:
    if not columnas:
        print("OK (sin resultado tabular)")
        return
    filas_str = [[str(v) if v is not None else "" for v in fila] for fila in filas]
    anchos = [len(c) for c in columnas]
    for fila in filas_str:
        for i, val in enumerate(fila):
            anchos[i] = max(anchos[i], len(val))
    print("  ".join(c.ljust(anchos[i]) for i, c in enumerate(columnas)))
    print("  ".join("-" * a for a in anchos))
    for fila in filas_str:
        print("  ".join(val.ljust(anchos[i]) for i, val in enumerate(fila)))
    print(f"({len(filas)} filas)")


def _cmd_db_migrar(_args: argparse.Namespace) -> int:
    try:
        aplicadas = db.migrar()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not aplicadas:
        print("No hay migraciones pendientes.")
    else:
        for nombre in aplicadas:
            print(f"Aplicada: {nombre}")
    return 0


def _cmd_db_consultar(args: argparse.Namespace) -> int:
    try:
        columnas, filas = db.consultar(args.sql)
    except duckdb.Error as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _imprimir_tabla(columnas, filas)
    return 0


def _cmd_etl_validar(args: argparse.Namespace) -> int:
    try:
        definicion = cargas.cargar(args.carga)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    con = db.conectar()
    try:
        errores = cargas.validar(definicion, con)
    finally:
        con.close()
    if errores:
        for error in errores:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: definición válida")
    return 0


def _cmd_etl_dry_run(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.dry_run_carga(args.carga)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for fr in resultado["ficheros"]:
        print(
            f"{fr['fichero']}: leídas={fr['filas_leidas']} "
            f"ok={fr['filas_ok']} rechazadas={fr['filas_rechazadas']}"
        )
        if fr["columnas_extra"]:
            print(f"  columnas no declaradas: {fr['columnas_extra']}")
        for fila in fr["muestra_validas"]:
            print(f"  OK: {fila}")
        for num_fila, motivo, campo, raw in fr["muestra_rechazos"]:
            print(f"  RECHAZO fila {num_fila} [{campo}]: {motivo} -- {raw}")
    if not resultado["ficheros"]:
        print("No hay ficheros que coincidan con el patrón.")
    return 0


def _cmd_etl_ejecutar(args: argparse.Namespace) -> int:
    try:
        resultado = motor_etl.ejecutar_carga(args.carga, forzar=args.forzar)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for fr in resultado["ficheros"]:
        if fr["estado"] == "OMITIDO":
            print(f"{fr['fichero']}: OMITIDO ({fr['motivo']})")
        else:
            print(
                f"{fr['fichero']}: {fr['estado']} "
                f"(leídas={fr['filas_leidas']} ok={fr['filas_ok']} rechazadas={fr['filas_rechazadas']})"
            )
    if not resultado["ficheros"]:
        print("No hay ficheros que coincidan con el patrón.")
    return 0


def _cmd_etl_estado(_args: argparse.Namespace) -> int:
    columnas, filas = db.consultar(
        "SELECT id, carga, fichero, fecha, filas_leidas, filas_ok, filas_rechazadas, estado "
        "FROM _ejecuciones ORDER BY fecha DESC LIMIT 20"
    )
    _imprimir_tabla(columnas, filas)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="motor")
    subparsers = parser.add_subparsers(dest="namespace", required=True)

    db_parser = subparsers.add_parser("db", help="Operaciones sobre el almacén DuckDB")
    db_sub = db_parser.add_subparsers(dest="command", required=True)
    db_sub.add_parser("migrar", help="Aplica migraciones pendientes")
    consultar_parser = db_sub.add_parser("consultar", help="Ejecuta SQL y muestra el resultado")
    consultar_parser.add_argument("sql")

    etl_parser = subparsers.add_parser("etl", help="Operaciones sobre cargas ETL")
    etl_sub = etl_parser.add_subparsers(dest="command", required=True)
    validar_parser = etl_sub.add_parser("validar", help="Valida una definición de carga")
    validar_parser.add_argument("carga")
    dry_run_parser = etl_sub.add_parser("dry-run", help="Ejecuta sin escribir en el almacén")
    dry_run_parser.add_argument("carga")
    ejecutar_parser = etl_sub.add_parser("ejecutar", help="Ejecuta una carga")
    ejecutar_parser.add_argument("carga")
    ejecutar_parser.add_argument("--forzar", action="store_true", help="Reprocesa aunque el hash ya esté OK")
    etl_sub.add_parser("estado", help="Últimas ejecuciones registradas")

    args = parser.parse_args(argv)

    if args.namespace == "db":
        if args.command == "migrar":
            return _cmd_db_migrar(args)
        if args.command == "consultar":
            return _cmd_db_consultar(args)

    if args.namespace == "etl":
        if args.command == "validar":
            return _cmd_etl_validar(args)
        if args.command == "dry-run":
            return _cmd_etl_dry_run(args)
        if args.command == "ejecutar":
            return _cmd_etl_ejecutar(args)
        if args.command == "estado":
            return _cmd_etl_estado(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
