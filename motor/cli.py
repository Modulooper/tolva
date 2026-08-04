"""CLI mínima: db migrar | db consultar."""

import argparse
import sys

import duckdb

from . import db


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="motor")
    subparsers = parser.add_subparsers(dest="namespace", required=True)

    db_parser = subparsers.add_parser("db", help="Operaciones sobre el almacén DuckDB")
    db_sub = db_parser.add_subparsers(dest="command", required=True)
    db_sub.add_parser("migrar", help="Aplica migraciones pendientes")
    consultar_parser = db_sub.add_parser("consultar", help="Ejecuta SQL y muestra el resultado")
    consultar_parser.add_argument("sql")

    args = parser.parse_args(argv)

    if args.namespace == "db":
        if args.command == "migrar":
            return _cmd_db_migrar(args)
        if args.command == "consultar":
            return _cmd_db_consultar(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
