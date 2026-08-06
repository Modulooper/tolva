"""Batería de pruebas de ClaudETL.

    python -m unittest discover -s pruebas -t .

Todas corren contra un almacén temporal recién migrado: ninguna toca
`datos/almacen.duckdb` ni `datos/documentos/`.
"""
