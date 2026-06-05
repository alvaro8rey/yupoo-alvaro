"""
importar_productos.py — Importa productos desde una carpeta de fotos descargadas de Yupoo.

Estructura esperada:
    fotos_yupoo/{catalogo}/{album}/   ← cada subcarpeta es un producto
    fotos_yupoo/{album}/              ← o directamente subcarpetas de productos

Uso:
    python importar_productos.py ./fotos_yupoo/baike5555
    python importar_productos.py ./fotos_yupoo/baike5555 --precio 25.99
    python importar_productos.py ./fotos_yupoo/baike5555 --tallas S M L XL
"""

import sys
import json
import argparse
from pathlib import Path

from db import init_db, get_connection

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_TALLAS = ["S", "M", "L", "XL", "XXL"]


def encontrar_primera_foto(carpeta: Path) -> str:
    """Devuelve la ruta a la primera imagen encontrada en la carpeta, o ''."""
    for ext in IMAGE_EXTENSIONS:
        fotos = sorted(carpeta.glob(f"*{ext}"))
        if fotos:
            return str(fotos[0].resolve())
    # Búsqueda case-insensitive
    for archivo in sorted(carpeta.iterdir()):
        if archivo.suffix.lower() in IMAGE_EXTENSIONS:
            return str(archivo.resolve())
    return ""


def producto_ya_existe(conn, nombre: str) -> bool:
    row = conn.execute(
        "SELECT id FROM productos WHERE nombre = ?", (nombre,)
    ).fetchone()
    return row is not None


def importar_desde_carpeta(
    carpeta_base: Path,
    precio_default: float = 0.0,
    tallas_default: list[str] = None,
    yupoo_url: str = "",
) -> tuple[int, int, int]:
    """
    Recorre subcarpetas de carpeta_base; cada subcarpeta es un producto.
    Devuelve (insertados, omitidos, errores).
    """
    if tallas_default is None:
        tallas_default = DEFAULT_TALLAS

    if not carpeta_base.exists():
        print(f"[ERROR] La carpeta no existe: {carpeta_base}")
        return 0, 0, 0

    subcarpetas = sorted([d for d in carpeta_base.iterdir() if d.is_dir()])
    if not subcarpetas:
        print(f"[AVISO] No se encontraron subcarpetas en: {carpeta_base}")
        return 0, 0, 0

    insertados = 0
    omitidos = 0
    errores = 0

    conn = get_connection()
    try:
        for carpeta in subcarpetas:
            nombre = carpeta.name.strip()
            if not nombre:
                continue

            try:
                if producto_ya_existe(conn, nombre):
                    print(f"  [OMITIDO]  '{nombre}' — ya existe en la BD")
                    omitidos += 1
                    continue

                foto_path = encontrar_primera_foto(carpeta)
                if not foto_path:
                    print(f"  [AVISO]    '{nombre}' — no se encontró ninguna foto; se insertará sin imagen")

                conn.execute(
                    """
                    INSERT INTO productos (nombre, precio, foto_path, yupoo_url, tallas)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        nombre,
                        precio_default,
                        foto_path,
                        yupoo_url,
                        json.dumps(tallas_default, ensure_ascii=False),
                    ),
                )
                conn.commit()
                print(f"  [OK]       '{nombre}' — foto: {foto_path or '(sin foto)'}")
                insertados += 1

            except Exception as exc:
                print(f"  [ERROR]    '{nombre}' — {exc}")
                errores += 1

    finally:
        conn.close()

    return insertados, omitidos, errores


def main():
    parser = argparse.ArgumentParser(
        description="Importa productos desde carpetas de fotos descargadas de Yupoo."
    )
    parser.add_argument(
        "carpeta",
        type=Path,
        help="Ruta a la carpeta que contiene subcarpetas de productos",
    )
    parser.add_argument(
        "--precio",
        type=float,
        default=0.0,
        help="Precio inicial para todos los productos (default: 0.0)",
    )
    parser.add_argument(
        "--tallas",
        nargs="+",
        default=DEFAULT_TALLAS,
        metavar="TALLA",
        help=f"Lista de tallas disponibles (default: {' '.join(DEFAULT_TALLAS)})",
    )
    parser.add_argument(
        "--yupoo-url",
        default="",
        help="URL de Yupoo para todos los productos importados",
    )
    parser.add_argument(
        "--recursivo",
        action="store_true",
        help="Si la carpeta contiene subcarpetas de catálogos, procesa cada una",
    )

    args = parser.parse_args()

    # Inicializar BD si no existe
    init_db()

    carpeta_base = args.carpeta.resolve()
    print(f"\nImportando desde: {carpeta_base}")
    print(f"Precio inicial:   {args.precio}€")
    print(f"Tallas:           {', '.join(args.tallas)}")
    print("-" * 50)

    if args.recursivo:
        # Tratar cada subcarpeta como un catálogo separado
        total_ins = total_omi = total_err = 0
        catalogos = sorted([d for d in carpeta_base.iterdir() if d.is_dir()])
        if not catalogos:
            print("[AVISO] No se encontraron subcarpetas de catálogos.")
        for catalogo in catalogos:
            print(f"\nCatálogo: {catalogo.name}")
            ins, omi, err = importar_desde_carpeta(
                catalogo, args.precio, args.tallas, args.yupoo_url
            )
            total_ins += ins
            total_omi += omi
            total_err += err
        ins, omi, err = total_ins, total_omi, total_err
    else:
        ins, omi, err = importar_desde_carpeta(
            carpeta_base, args.precio, args.tallas, args.yupoo_url
        )

    print("\n" + "=" * 50)
    print("RESUMEN DE IMPORTACIÓN")
    print("=" * 50)
    print(f"  Productos insertados: {ins}")
    print(f"  Productos omitidos:   {omi}  (ya existían)")
    print(f"  Errores:              {err}")
    print("=" * 50)

    if ins > 0:
        print(
            "\nRecuerda actualizar los precios en la base de datos:\n"
            "  sqlite3 tienda.db \"UPDATE productos SET precio = 25.99 WHERE precio = 0;\""
        )


if __name__ == "__main__":
    main()
