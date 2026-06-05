"""Inserta productos de demo en la BD para pruebas."""
import db

db.init_db()

productos = [
    ("Camiseta Real Madrid 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/123", '["S","M","L","XL","XXL"]'),
    ("Camiseta Barcelona 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/124", '["S","M","L","XL","XXL"]'),
    ("Camiseta Manchester City 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/125", '["S","M","L","XL","XXL"]'),
    ("Camiseta PSG 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/126", '["S","M","L","XL","XXL"]'),
    ("Camiseta Brasil 2026 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/127", '["S","M","L","XL","XXL"]'),
    ("Camiseta Argentina 2026 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/128", '["S","M","L","XL","XXL"]'),
]

import sqlite3
conn = db.get_connection()
for nombre, precio, foto, yupoo_url, tallas in productos:
    try:
        conn.execute(
            "INSERT INTO productos (nombre, precio, foto_path, yupoo_url, tallas) VALUES (?,?,?,?,?)",
            (nombre, precio, foto, yupoo_url, tallas)
        )
        print(f"  ✓ {nombre}")
    except sqlite3.IntegrityError:
        print(f"  - ya existe: {nombre}")
conn.commit()
conn.close()
print("\nProductos de demo insertados.")
