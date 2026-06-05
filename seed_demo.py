"""Inserta productos de demo en la BD para pruebas."""
import db

db.init_db()

productos = [
    ("Camiseta Real Madrid 25/26 Local",      18.0, "", "https://baike5555.x.yupoo.com/albums/123", '["S","M","L","XL","XXL"]', "La Liga",        "Real Madrid"),
    ("Camiseta Barcelona 25/26 Local",         18.0, "", "https://baike5555.x.yupoo.com/albums/124", '["S","M","L","XL","XXL"]', "La Liga",        "FC Barcelona"),
    ("Camiseta Manchester City 25/26 Local",   18.0, "", "https://baike5555.x.yupoo.com/albums/125", '["S","M","L","XL","XXL"]', "Premier League", "Manchester City"),
    ("Camiseta PSG 25/26 Local",               18.0, "", "https://baike5555.x.yupoo.com/albums/126", '["S","M","L","XL","XXL"]', "Ligue 1",        "PSG"),
    ("Camiseta Brasil 2026 Local",             18.0, "", "https://baike5555.x.yupoo.com/albums/127", '["S","M","L","XL","XXL"]', "Selecciones",    "Brasil"),
    ("Camiseta Argentina 2026 Local",          18.0, "", "https://baike5555.x.yupoo.com/albums/128", '["S","M","L","XL","XXL"]', "Selecciones",    "Argentina"),
]

import sqlite3
conn = db.get_connection()
for nombre, precio, foto, yupoo_url, tallas, liga, equipo in productos:
    try:
        conn.execute(
            "INSERT INTO productos (nombre, precio, foto_path, yupoo_url, tallas, liga, equipo) VALUES (?,?,?,?,?,?,?)",
            (nombre, precio, foto, yupoo_url, tallas, liga, equipo)
        )
        print(f"  + {nombre}")
    except sqlite3.IntegrityError:
        # Update liga/equipo on existing rows so reruns stay in sync
        conn.execute(
            "UPDATE productos SET liga=?, equipo=? WHERE nombre=?",
            (liga, equipo, nombre)
        )
        print(f"  ~ actualizado: {nombre}")
conn.commit()
conn.close()
print("\nProductos de demo insertados/actualizados.")
