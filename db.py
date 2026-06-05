"""
db.py — Configuración y utilidades de base de datos PostgreSQL (Supabase).
"""

import os
import json
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Parámetros de conexión por defecto (pooler Supabase, compatible con IPv4)
_DB_PARAMS = {
    "host": os.environ.get("PGHOST", "aws-0-eu-west-1.pooler.supabase.com"),
    "options": "-c search_path=public",
    "port": int(os.environ.get("PGPORT", "5432")),
    "dbname": os.environ.get("PGDATABASE", "postgres"),
    "user": os.environ.get("PGUSER", "postgres.qgjhkjxqblmtnrpmtgpf"),
    "password": os.environ.get("PGPASSWORD", "Aslombas7b.,"),
    "sslmode": "require",
}


def get_connection():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = psycopg2.connect(cursor_factory=psycopg2.extras.RealDictCursor, **_DB_PARAMS)
    return conn


def init_db():
    conn = get_connection()
    try:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id          SERIAL PRIMARY KEY,
                nombre      TEXT    NOT NULL UNIQUE,
                precio      FLOAT   NOT NULL DEFAULT 0.0,
                foto_path   TEXT    NOT NULL DEFAULT '',
                yupoo_url   TEXT    NOT NULL DEFAULT '',
                tallas      TEXT    NOT NULL DEFAULT '["S","M","L","XL","XXL"]',
                activo      INTEGER NOT NULL DEFAULT 1,
                liga        TEXT    NOT NULL DEFAULT '',
                equipo      TEXT    NOT NULL DEFAULT ''
            )
        """)

        c.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS liga TEXT NOT NULL DEFAULT ''")
        c.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS equipo TEXT NOT NULL DEFAULT ''")

        c.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id              SERIAL PRIMARY KEY,
                usuario_tg      BIGINT  NOT NULL,
                username_tg     TEXT    NOT NULL DEFAULT '',
                nombre_cliente  TEXT    NOT NULL DEFAULT '',
                direccion       TEXT    NOT NULL DEFAULT '',
                estado          TEXT    NOT NULL DEFAULT 'pendiente_pago'
                                CHECK(estado IN ('pendiente_pago','en_proceso','enviado','cancelado')),
                total           FLOAT   NOT NULL DEFAULT 0.0,
                paypal_ref      TEXT    NOT NULL DEFAULT '',
                created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                notas           TEXT    NOT NULL DEFAULT ''
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS pedido_items (
                id                   SERIAL PRIMARY KEY,
                pedido_id            INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                producto_id          INTEGER NOT NULL REFERENCES productos(id),
                talla                TEXT    NOT NULL DEFAULT '',
                personalizado        INTEGER NOT NULL DEFAULT 0,
                tipo_personalizacion TEXT    NOT NULL DEFAULT 'sin_personalizacion'
                                     CHECK(tipo_personalizacion IN ('sin_personalizacion','nombre_numero','nombre_numero_parches')),
                nombre_dorsal        TEXT    NOT NULL DEFAULT '',
                numero_dorsal        TEXT    NOT NULL DEFAULT '',
                cantidad             INTEGER NOT NULL DEFAULT 1,
                precio_unitario      FLOAT   NOT NULL DEFAULT 0.0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS fotos_producto (
                id          SERIAL PRIMARY KEY,
                producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                datos       BYTEA   NOT NULL,
                nombre      TEXT    NOT NULL DEFAULT '',
                es_portada  INTEGER NOT NULL DEFAULT 0,
                orden       INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.commit()
        print("[db] Base de datos Supabase inicializada.")
    finally:
        conn.close()


# ── Helpers para productos ──────────────────────────────────────────────────

def get_producto(producto_id: int) -> dict | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT p.*,
                   COALESCE(p.liga,'') AS liga,
                   COALESCE(p.equipo,'') AS equipo,
                   fp.id AS portada_id
            FROM productos p
            LEFT JOIN fotos_producto fp
                   ON fp.producto_id = p.id AND fp.es_portada = 1
            WHERE p.id = %s AND p.activo = 1
        """, (producto_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_producto_admin(producto_id: int) -> dict | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT p.*,
                   COALESCE(p.liga,'') AS liga,
                   COALESCE(p.equipo,'') AS equipo,
                   fp.id AS portada_id
            FROM productos p
            LEFT JOIN fotos_producto fp
                   ON fp.producto_id = p.id AND fp.es_portada = 1
            WHERE p.id = %s
        """, (producto_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_todos_productos(solo_activos: bool = True) -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        if solo_activos:
            c.execute("""
                SELECT p.id, p.nombre, p.precio, p.foto_path, p.yupoo_url,
                       p.tallas, p.activo,
                       COALESCE(p.liga,'') AS liga, COALESCE(p.equipo,'') AS equipo,
                       fp.id AS portada_id
                FROM productos p
                LEFT JOIN fotos_producto fp
                       ON fp.producto_id = p.id AND fp.es_portada = 1
                WHERE p.activo = 1
                ORDER BY p.nombre
            """)
        else:
            c.execute("""
                SELECT p.id, p.nombre, p.precio, p.foto_path, p.yupoo_url,
                       p.tallas, p.activo,
                       COALESCE(p.liga,'') AS liga, COALESCE(p.equipo,'') AS equipo,
                       fp.id AS portada_id
                FROM productos p
                LEFT JOIN fotos_producto fp
                       ON fp.producto_id = p.id AND fp.es_portada = 1
                ORDER BY p.nombre
            """)
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def tallas_producto(producto_id: int) -> list[str]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT tallas FROM productos WHERE id = %s", (producto_id,))
        row = c.fetchone()
        return json.loads(row["tallas"]) if row else []
    finally:
        conn.close()


# ── Helpers para fotos ──────────────────────────────────────────────────────

def guardar_foto(producto_id: int, datos_bytes: bytes, nombre: str, es_portada: bool = False) -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        if es_portada:
            c.execute("UPDATE fotos_producto SET es_portada = 0 WHERE producto_id = %s", (producto_id,))
        c.execute(
            "INSERT INTO fotos_producto (producto_id, datos, nombre, es_portada) VALUES (%s, %s, %s, %s) RETURNING id",
            (producto_id, psycopg2.Binary(datos_bytes), nombre, 1 if es_portada else 0)
        )
        new_id = c.fetchone()["id"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def get_fotos_producto(producto_id: int) -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, producto_id, nombre, es_portada, orden "
            "FROM fotos_producto WHERE producto_id = %s "
            "ORDER BY es_portada DESC, orden ASC",
            (producto_id,)
        )
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def get_foto_datos(foto_id: int) -> bytes | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT datos FROM fotos_producto WHERE id = %s", (foto_id,))
        row = c.fetchone()
        if not row:
            return None
        datos = row["datos"]
        return bytes(datos) if datos else None
    finally:
        conn.close()


def set_portada(foto_id: int, producto_id: int):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE fotos_producto SET es_portada = 0 WHERE producto_id = %s", (producto_id,))
        c.execute("UPDATE fotos_producto SET es_portada = 1 WHERE id = %s", (foto_id,))
        conn.commit()
    finally:
        conn.close()


def eliminar_foto(foto_id: int):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM fotos_producto WHERE id = %s", (foto_id,))
        conn.commit()
    finally:
        conn.close()


def get_portada(producto_id: int) -> dict | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, producto_id, nombre, es_portada, orden "
            "FROM fotos_producto WHERE producto_id = %s AND es_portada = 1 LIMIT 1",
            (producto_id,)
        )
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO pedidos (usuario_tg, username_tg, nombre_cliente,
                                 direccion, total, paypal_ref, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (usuario_tg, username_tg, nombre_cliente, direccion, total, paypal_ref, notas),
        )
        new_id = c.fetchone()["id"]
        conn.commit()
        return new_id
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO pedido_items
                (pedido_id, producto_id, talla, personalizado, tipo_personalizacion,
                 nombre_dorsal, numero_dorsal, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (pedido_id, producto_id, talla, 1 if personalizado else 0,
             tipo_personalizacion, nombre_dorsal, numero_dorsal, cantidad, precio_unitario),
        )
        conn.commit()
    finally:
        conn.close()


def get_pedido(pedido_id: int) -> dict | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pedidos WHERE id = %s", (pedido_id,))
        row = c.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        return d
    finally:
        conn.close()


def get_items_pedido(pedido_id: int) -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT pi.*, p.nombre AS nombre_producto
            FROM pedido_items pi
            JOIN productos p ON p.id = pi.producto_id
            WHERE pi.pedido_id = %s
            """,
            (pedido_id,),
        )
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def get_pedidos_usuario(usuario_tg: int) -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM pedidos WHERE usuario_tg = %s ORDER BY created_at DESC",
            (usuario_tg,),
        )
        rows = c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result
    finally:
        conn.close()


def get_pedidos_pendientes() -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pedidos WHERE estado = 'pendiente_pago' ORDER BY created_at ASC")
        rows = c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result
    finally:
        conn.close()


def get_todos_pedidos_admin() -> list[dict]:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pedidos ORDER BY created_at DESC LIMIT 50")
        rows = c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result
    finally:
        conn.close()


def actualizar_estado_pedido(pedido_id: int, nuevo_estado: str, notas: str = ""):
    estados_validos = {"pendiente_pago", "en_proceso", "enviado", "cancelado"}
    if nuevo_estado not in estados_validos:
        raise ValueError(f"Estado inválido: {nuevo_estado}")
    conn = get_connection()
    try:
        c = conn.cursor()
        if notas:
            c.execute(
                "UPDATE pedidos SET estado = %s, notas = %s WHERE id = %s",
                (nuevo_estado, notas, pedido_id),
            )
        else:
            c.execute(
                "UPDATE pedidos SET estado = %s WHERE id = %s",
                (nuevo_estado, pedido_id),
            )
        conn.commit()
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS cnt FROM productos")
        if c.fetchone()["cnt"] > 0:
            return
        demos = [
            ("Camiseta Real Madrid 25/26 Local",    18.0, "", "https://baike5555.x.yupoo.com/albums/123", '["S","M","L","XL","XXL"]', "La Liga",        "Real Madrid"),
            ("Camiseta Barcelona 25/26 Local",       18.0, "", "https://baike5555.x.yupoo.com/albums/124", '["S","M","L","XL","XXL"]', "La Liga",        "FC Barcelona"),
            ("Camiseta Manchester City 25/26 Local", 18.0, "", "https://baike5555.x.yupoo.com/albums/125", '["S","M","L","XL","XXL"]', "Premier League", "Manchester City"),
            ("Camiseta PSG 25/26 Local",             18.0, "", "https://baike5555.x.yupoo.com/albums/126", '["S","M","L","XL","XXL"]', "Ligue 1",        "PSG"),
            ("Camiseta Brasil 2026 Local",           18.0, "", "https://baike5555.x.yupoo.com/albums/127", '["S","M","L","XL","XXL"]', "Selecciones",    "Brasil"),
            ("Camiseta Argentina 2026 Local",        18.0, "", "https://baike5555.x.yupoo.com/albums/128", '["S","M","L","XL","XXL"]', "Selecciones",    "Argentina"),
        ]
        for nombre, precio, foto, yupoo_url, tallas, liga, equipo in demos:
            c.execute(
                "INSERT INTO productos (nombre, precio, foto_path, yupoo_url, tallas, liga, equipo) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (nombre) DO NOTHING",
                (nombre, precio, foto, yupoo_url, tallas, liga, equipo)
            )
        conn.commit()
        print("[db] Productos de demo insertados.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
