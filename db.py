"""
db.py — Configuración y utilidades de base de datos SQLite para la tienda de camisetas.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "tienda.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Crea todas las tablas si no existen."""
    conn = get_connection()
    try:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT    NOT NULL UNIQUE,
                precio      REAL    NOT NULL DEFAULT 0.0,
                foto_path   TEXT    NOT NULL DEFAULT '',
                yupoo_url   TEXT    NOT NULL DEFAULT '',
                tallas      TEXT    NOT NULL DEFAULT '["S","M","L","XL","XXL"]',
                activo      INTEGER NOT NULL DEFAULT 1,
                liga        TEXT    NOT NULL DEFAULT '',
                equipo      TEXT    NOT NULL DEFAULT ''
            )
        """)

        # Safe migrations: add liga and equipo columns if they don't exist yet
        existing_cols = {row[1] for row in c.execute("PRAGMA table_info(productos)").fetchall()}
        if "liga" not in existing_cols:
            c.execute("ALTER TABLE productos ADD COLUMN liga TEXT NOT NULL DEFAULT ''")
        if "equipo" not in existing_cols:
            c.execute("ALTER TABLE productos ADD COLUMN equipo TEXT NOT NULL DEFAULT ''")

        c.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_tg      INTEGER NOT NULL,
                username_tg     TEXT    NOT NULL DEFAULT '',
                nombre_cliente  TEXT    NOT NULL DEFAULT '',
                direccion       TEXT    NOT NULL DEFAULT '',
                estado          TEXT    NOT NULL DEFAULT 'pendiente_pago'
                                CHECK(estado IN ('pendiente_pago','en_proceso','enviado','cancelado')),
                total           REAL    NOT NULL DEFAULT 0.0,
                paypal_ref      TEXT    NOT NULL DEFAULT '',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                notas           TEXT    NOT NULL DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS pedido_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                producto_id     INTEGER NOT NULL REFERENCES productos(id),
                talla                TEXT    NOT NULL DEFAULT '',
                personalizado        INTEGER NOT NULL DEFAULT 0,
                tipo_personalizacion TEXT    NOT NULL DEFAULT 'sin_personalizacion'
                                     CHECK(tipo_personalizacion IN ('sin_personalizacion','nombre_numero','nombre_numero_parches')),
                nombre_dorsal        TEXT    NOT NULL DEFAULT '',
                numero_dorsal        TEXT    NOT NULL DEFAULT '',
                cantidad             INTEGER NOT NULL DEFAULT 1,
                precio_unitario      REAL    NOT NULL DEFAULT 0.0
            )
        """)

        conn.commit()
        print(f"[db] Base de datos inicializada en: {DB_PATH}")
    finally:
        conn.close()


# ── Helpers para productos ──────────────────────────────────────────────────

def get_producto(producto_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM productos WHERE id = ? AND activo = 1", (producto_id,)
        ).fetchone()
    return dict(row) if row else None


def get_todos_productos(solo_activos: bool = True) -> list[dict]:
    with get_connection() as conn:
        if solo_activos:
            rows = conn.execute(
                "SELECT id, nombre, precio, foto_path, yupoo_url, tallas, activo, "
                "COALESCE(liga,'') AS liga, COALESCE(equipo,'') AS equipo "
                "FROM productos WHERE activo = 1 ORDER BY nombre"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, nombre, precio, foto_path, yupoo_url, tallas, activo, "
                "COALESCE(liga,'') AS liga, COALESCE(equipo,'') AS equipo "
                "FROM productos ORDER BY nombre"
            ).fetchall()
    return [dict(r) for r in rows]


def tallas_producto(producto_id: int) -> list[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT tallas FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
    if row is None:
        return []
    return json.loads(row["tallas"])


# ── Helpers para pedidos ────────────────────────────────────────────────────

def crear_pedido(
    usuario_tg: int,
    username_tg: str,
    nombre_cliente: str,
    direccion: str,
    total: float,
    paypal_ref: str,
    notas: str = "",
) -> int:
    """Inserta un pedido nuevo y devuelve su id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO pedidos (usuario_tg, username_tg, nombre_cliente,
                                 direccion, total, paypal_ref, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (usuario_tg, username_tg, nombre_cliente, direccion, total, paypal_ref, notas),
        )
        conn.commit()
        return cur.lastrowid


def agregar_item_pedido(
    pedido_id: int,
    producto_id: int,
    talla: str,
    personalizado: bool,
    tipo_personalizacion: str,
    nombre_dorsal: str,
    numero_dorsal: str,
    cantidad: int,
    precio_unitario: float,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pedido_items
                (pedido_id, producto_id, talla, personalizado, tipo_personalizacion,
                 nombre_dorsal, numero_dorsal, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pedido_id,
                producto_id,
                talla,
                1 if personalizado else 0,
                tipo_personalizacion,
                nombre_dorsal,
                numero_dorsal,
                cantidad,
                precio_unitario,
            ),
        )
        conn.commit()


def get_pedido(pedido_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pedidos WHERE id = ?", (pedido_id,)
        ).fetchone()
    return dict(row) if row else None


def get_items_pedido(pedido_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pi.*, p.nombre AS nombre_producto
            FROM pedido_items pi
            JOIN productos p ON p.id = pi.producto_id
            WHERE pi.pedido_id = ?
            """,
            (pedido_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pedidos_usuario(usuario_tg: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pedidos WHERE usuario_tg = ? ORDER BY created_at DESC",
            (usuario_tg,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pedidos_pendientes() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pedidos WHERE estado = 'pendiente_pago' ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_todos_pedidos_admin() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pedidos ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def actualizar_estado_pedido(pedido_id: int, nuevo_estado: str, notas: str = ""):
    estados_validos = {"pendiente_pago", "en_proceso", "enviado", "cancelado"}
    if nuevo_estado not in estados_validos:
        raise ValueError(f"Estado inválido: {nuevo_estado}")
    with get_connection() as conn:
        if notas:
            conn.execute(
                "UPDATE pedidos SET estado = ?, notas = ? WHERE id = ?",
                (nuevo_estado, notas, pedido_id),
            )
        else:
            conn.execute(
                "UPDATE pedidos SET estado = ? WHERE id = ?",
                (nuevo_estado, pedido_id),
            )
        conn.commit()


ESTADO_EMOJI = {
    "pendiente_pago": "⏳ Pendiente de pago",
    "en_proceso":     "🔄 En proceso",
    "enviado":        "🚚 Enviado",
    "cancelado":      "❌ Cancelado",
}


def estado_label(estado: str) -> str:
    return ESTADO_EMOJI.get(estado, estado)


# ── Bootstrap ───────────────────────────────────────────────────────────────

def seed_demo_if_empty():
    """Inserta productos de demo si la BD está vacía. Útil en Render."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    if count > 0:
        return
    demos = [
        ("Camiseta Real Madrid 25/26 Local",    18.0, "", "https://baike5555.x.yupoo.com/albums/123", '["S","M","L","XL","XXL"]', "La Liga",        "Real Madrid"),
        ("Camiseta Barcelona 25/26 Local",       18.0, "", "https://baike5555.x.yupoo.com/albums/124", '["S","M","L","XL","XXL"]', "La Liga",        "FC Barcelona"),
        ("Camiseta Manchester City 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/125", '["S","M","L","XL","XXL"]', "Premier League", "Manchester City"),
        ("Camiseta PSG 25/26 Local",             18.0, "", "https://baike5555.x.yupoo.com/albums/126", '["S","M","L","XL","XXL"]', "Ligue 1",        "PSG"),
        ("Camiseta Brasil 2026 Local",           18.0, "", "https://baike5555.x.yupoo.com/albums/127", '["S","M","L","XL","XXL"]', "Selecciones",    "Brasil"),
        ("Camiseta Argentina 2026 Local",        18.0, "", "https://baike5555.x.yupoo.com/albums/128", '["S","M","L","XL","XXL"]', "Selecciones",    "Argentina"),
    ]
    with get_connection() as conn:
        for nombre, precio, foto, yupoo_url, tallas, liga, equipo in demos:
            conn.execute(
                "INSERT OR IGNORE INTO productos (nombre, precio, foto_path, yupoo_url, tallas, liga, equipo) VALUES (?,?,?,?,?,?,?)",
                (nombre, precio, foto, yupoo_url, tallas, liga, equipo)
            )
        conn.commit()
    print("[db] Productos de demo insertados.")


if __name__ == "__main__":
    init_db()
