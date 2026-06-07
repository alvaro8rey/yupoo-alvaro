"""
bot.py — Bot de Telegram para la tienda de camisetas.
"""

import json
import logging
import re
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

import db
import os

# ── Configuración ────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "8904389544:AAGzBLce1zDXjtfY0JJ8FDVX8pBQDz0p1XE")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
PAYPAL_USER   = os.environ.get("PAYPAL_USER", "tu.paypal@email.com")
BIZUM_NUMERO  = os.environ.get("BIZUM_NUMERO", "")
BOT_USERNAME  = os.environ.get("BOT_USERNAME", "tu_bot")
STORE_NAME    = os.environ.get("STORE_NAME", "Camisetas Premium")

PRECIO_BASE          = 18.0
PRECIO_NOMBRE_NUMERO = 21.0
PRECIO_CON_PARCHES   = 22.0

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Estados ──────────────────────────────────────────────────────────────────
(
    ESPERANDO_PRODUCTO_ID,
    ESPERANDO_CONFIRMACION_PRODUCTO,
    ESPERANDO_TALLA,
    ESPERANDO_PERSONALIZACION,
    ESPERANDO_NOMBRE_DORSAL,
    ESPERANDO_NUMERO_DORSAL,
    ESPERANDO_OTRO_PRODUCTO,
    ESPERANDO_DATOS_ENVIO,
    ESPERANDO_REFERENCIA_PAGO,
) = range(9)

# ── Carrito en memoria ───────────────────────────────────────────────────────
carritos: dict[int, dict] = {}

def get_carrito(chat_id: int) -> dict:
    if chat_id not in carritos:
        carritos[chat_id] = {"items": []}
    return carritos[chat_id]

def limpiar_carrito(chat_id: int):
    carritos[chat_id] = {"items": []}

# ── Teclado principal ─────────────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛍 Catálogo"),    KeyboardButton("🛒 Mi carrito")],
        [KeyboardButton("📦 Mis pedidos"), KeyboardButton("❓ Ayuda")],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def calcular_total(items: list[dict]) -> float:
    return sum(it["precio_unitario"] * it["cantidad"] for it in items)

def estado_emoji(estado: str) -> str:
    return {
        "pendiente_pago": "⏳",
        "en_proceso":     "🔄",
        "enviado":        "🚚",
        "cancelado":      "❌",
    }.get(estado, "•")

def estado_texto(estado: str) -> str:
    return {
        "pendiente_pago": "Pendiente de pago",
        "en_proceso":     "En proceso",
        "enviado":        "Enviado",
        "cancelado":      "Cancelado",
    }.get(estado, estado)

def precio_personalizacion(tipo: str) -> float:
    return {"nombre_numero": PRECIO_NOMBRE_NUMERO, "nombre_numero_parches": PRECIO_CON_PARCHES}.get(tipo, PRECIO_BASE)

def resumen_carrito_texto(items: list[dict]) -> str:
    if not items:
        return "_Tu carrito está vacío_"
    lineas = []
    for i, it in enumerate(items, 1):
        subtotal = it["precio_unitario"] * it["cantidad"]
        pers = ""
        if it.get("personalizado"):
            parches = " + parches" if it.get("tipo_personalizacion") == "nombre_numero_parches" else ""
            pers = f"\n   ✏️ {it.get('nombre_dorsal','')} #{it.get('numero_dorsal','')}{parches}"
        lineas.append(f"{i}. *{it['nombre_producto']}* · Talla {it['talla']} · {subtotal:.0f}€{pers}")
    total = calcular_total(items)
    lineas.append(f"\n💰 *Total: {total:.2f} €*")
    return "\n".join(lineas)

def texto_producto(p: dict) -> str:
    tallas = json.loads(p.get("tallas") or '["S","M","L","XL","XXL"]')
    liga = p.get("liga", "")
    equipo = p.get("equipo", "")
    cat = f"{liga} · {equipo}" if liga and equipo else liga or equipo
    return (
        f"👕 *{p['nombre']}*\n"
        + (f"🏆 {cat}\n" if cat else "")
        + f"\n💶 Desde *{PRECIO_BASE:.0f}€* sin personalizar\n"
        f"   Con nombre y número: *{PRECIO_NOMBRE_NUMERO:.0f}€*\n"
        f"   Con nombre, número y parches: *{PRECIO_CON_PARCHES:.0f}€*\n\n"
        f"📏 Tallas: {', '.join(tallas)}\n"
        f"🔖 Ref: `#{p['id']}`"
    )


TALLA_MAP = {'s':'S','m':'M','l':'L','xl':'XL','xxl':'XXL','xxxl':'XXXL'}
PERS_MAP  = {'0':'sin_personalizacion','1':'nombre_numero','2':'solo_parches','3':'nombre_numero_parches'}
PERS_LABEL = {
    'sin_personalizacion':   'Sin personalización',
    'nombre_numero':         'Nombre + número',
    'solo_parches':          'Solo parches',
    'nombre_numero_parches': 'Nombre + número + parches',
}
PERS_PRECIO = {'sin_personalizacion': None, 'nombre_numero': 21.0, 'solo_parches': 20.0, 'nombre_numero_parches': 24.0}


def _parsear_pedido_web(texto: str) -> tuple[list[dict], float]:
    """Parsea el mensaje pre-rellenado de la tienda y devuelve (items, total)."""
    items = []
    total = 0.0

    m = re.search(r'Total estimado[:\s*]+(\d+(?:[\.,]\d+)?)€', texto)
    if m:
        try:
            total = float(m.group(1).replace(',', '.'))
        except ValueError:
            pass

    # Cada producto empieza con *N. Nombre*
    blocks = re.split(r'\*\d+\.\s+', texto)
    for block in blocks[1:]:
        lines = block.strip().split('\n')
        nombre = lines[0].rstrip('*').strip()
        talla = ''
        pers = 'sin_personalizacion'
        nombre_dorsal = ''
        numero_dorsal = ''
        precio_item = 18.0
        parches_item = []

        for line in lines[1:]:
            limpia = line.strip().lstrip('•').strip()
            if limpia.startswith('Talla:'):
                talla = limpia[6:].strip()
            elif limpia.startswith('Dorsal:'):
                dorsal = limpia[7:].strip()
                if '/' in dorsal:
                    parts = dorsal.split('/', 1)
                    nombre_dorsal = parts[0].strip()
                    numero_dorsal = parts[1].strip()
            elif limpia.startswith('Precio:'):
                try:
                    precio_item = float(limpia[7:].replace('€', '').strip())
                except ValueError:
                    pass
            elif limpia.startswith('Parches:'):
                parches_item = [p.strip() for p in limpia[8:].split(',') if p.strip()]
                pers = 'nombre_numero_parches' if nombre_dorsal else 'solo_parches'
            elif 'nombre' in limpia.lower() and 'número' in limpia.lower() and 'parches' in limpia.lower():
                pers = 'nombre_numero_parches'
            elif 'nombre' in limpia.lower() and 'número' in limpia.lower():
                pers = 'nombre_numero'
            elif 'parches' in limpia.lower() and 'sin' not in limpia.lower():
                if pers == 'sin_personalizacion':
                    pers = 'solo_parches'

        try:
            prods = db.get_todos_productos(solo_activos=False)
            producto = next((p for p in prods if p['nombre'].lower() == nombre.lower()), None)
        except Exception:
            producto = None

        items.append({
            'producto_id':        producto['id'] if producto else 0,
            'nombre_producto':    nombre,
            'talla':              talla,
            'personalizado':      pers != 'sin_personalizacion',
            'tipo_personalizacion': pers,
            'nombre_dorsal':      nombre_dorsal,
            'numero_dorsal':      numero_dorsal,
            'parches':            parches_item,
            'cantidad':           1,
            'precio_unitario':    precio_item,
        })

    return items, total


async def _cargar_carrito_web(update: Update, context: ContextTypes.DEFAULT_TYPE, encoded: str) -> int:
    """Carga un carrito enviado desde la tienda web y lo mete en el carrito del bot."""
    chat_id = update.effective_chat.id
    user    = update.effective_user
    limpiar_carrito(chat_id)
    carrito = get_carrito(chat_id)

    items_ok = []
    for part in encoded.split('_'):
        fields = part.split('-', 2)
        if len(fields) != 3:
            continue
        try:
            pid   = int(fields[0])
            talla = TALLA_MAP.get(fields[1].lower(), fields[1].upper())
            pers  = PERS_MAP.get(fields[2], 'sin_personalizacion')
        except ValueError:
            continue
        producto = db.get_producto(pid)
        if not producto:
            continue
        precio_base = producto.get('precio') or PRECIO_BASE
        precio = PERS_PRECIO.get(pers) or precio_base
        items_ok.append({
            "producto":     producto,
            "talla":        talla,
            "personalizacion": pers,
            "precio":       precio,
            "cantidad":     1,
        })

    if not items_ok:
        await update.message.reply_text(
            "❌ No se pudo cargar el carrito. Inténtalo de nuevo desde la tienda.",
            reply_markup=MENU_KEYBOARD,
        )
        return ConversationHandler.END

    carrito["items"] = items_ok

    # Resumen
    lineas = []
    total  = 0.0
    for it in items_ok:
        p    = it["producto"]
        desc = PERS_LABEL[it["personalizacion"]]
        lineas.append(f"• *{p['nombre']}* — Talla {it['talla']}\n  _{desc}_ — {it['precio']:.0f}€")
        total += it["precio"]

    texto = (
        f"🛒 *Carrito importado desde la tienda*\n\n"
        + "\n\n".join(lineas)
        + f"\n\n*Total estimado: {total:.0f}€*\n\n"
        "¿Quieres finalizar el pedido? Introduce tu nombre completo y dirección de envío:"
    )
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_KEYBOARD)
    return ESPERANDO_DATOS_ENVIO


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db.init_db()
    chat_id = update.effective_chat.id
    user = update.effective_user
    limpiar_carrito(chat_id)

    # deep link
    args = context.args or []
    if args:
        payload = args[0]

        # Carrito desde la web: cart_ID-TALLA-PERS_ID-TALLA-PERS
        if payload.startswith("cart_"):
            return await _cargar_carrito_web(update, context, payload[5:])

        # Producto individual
        if payload.startswith("producto_"):
            try:
                pid = int(payload.split("_", 1)[1])
                producto = db.get_producto(pid)
                if producto:
                    get_carrito(chat_id)["producto_actual"] = producto
                    await update.message.reply_text(
                        f"👋 Hola, *{user.first_name}*! Te enviamos directamente a este producto:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=MENU_KEYBOARD,
                    )
                    return await _mostrar_producto_y_confirmar(update, context, producto)
            except (ValueError, IndexError):
                pass

    productos = db.get_todos_productos(solo_activos=True)
    n = len(productos)

    await update.message.reply_text(
        f"👋 ¡Hola, *{user.first_name}*! Bienvenido a *{STORE_NAME}* 👕\n\n"
        f"Tenemos *{n} modelos* disponibles con envío a toda España.\n\n"
        f"💶 Precios desde *{PRECIO_BASE:.0f}€*\n"
        f"✏️ Personalización de dorsales disponible\n"
        f"💳 Pago por PayPal" + (f" o Bizum" if BIZUM_NUMERO else "") + "\n\n"
        f"Usa el menú de abajo para navegar 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU_KEYBOARD,
    )
    return ConversationHandler.END


# ── Catálogo ──────────────────────────────────────────────────────────────────

async def menu_catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las ligas disponibles como botones."""
    productos = db.get_todos_productos(solo_activos=True)
    if not productos:
        await update.message.reply_text("No hay productos disponibles ahora mismo.")
        return

    # Agrupa por liga
    ligas: dict[str, int] = {}
    for p in productos:
        liga = p.get("liga") or "Sin categoría"
        ligas[liga] = ligas.get(liga, 0) + 1

    botones = []
    for liga, cnt in sorted(ligas.items()):
        botones.append([InlineKeyboardButton(f"🏆 {liga}  ({cnt})", callback_data=f"cat_liga_{liga}")])
    botones.append([InlineKeyboardButton("📋 Ver todos", callback_data="cat_todos")])

    await update.message.reply_text(
        f"🛍 *Catálogo — {len(productos)} productos*\n\nElige una liga o categoría:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def catalogo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cat_todos":
        productos = db.get_todos_productos(solo_activos=True)
        await _mostrar_lista_productos(query, context, productos, "Todos los productos")

    elif data.startswith("cat_liga_"):
        liga = data[len("cat_liga_"):]
        productos = db.get_todos_productos(solo_activos=True)
        equipos: dict[str, list] = {}
        for p in productos:
            if (p.get("liga") or "Sin categoría") == liga:
                eq = p.get("equipo") or "Otros"
                equipos.setdefault(eq, []).append(p)

        if len(equipos) == 1:
            prods = list(equipos.values())[0]
            await _mostrar_lista_productos(query, context, prods, liga)
        else:
            botones = []
            for eq, prods in sorted(equipos.items()):
                botones.append([InlineKeyboardButton(
                    f"⚽ {eq}  ({len(prods)})", callback_data=f"cat_equipo_{liga}|{eq}"
                )])
            botones.append([InlineKeyboardButton("◀️ Volver", callback_data="cat_volver_ligas")])
            await query.edit_message_text(
                f"🏆 *{liga}*\n\nElige un equipo:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(botones),
            )

    elif data.startswith("cat_equipo_"):
        partes = data[len("cat_equipo_"):].split("|", 1)
        liga, equipo = partes[0], partes[1]
        productos = [p for p in db.get_todos_productos(solo_activos=True)
                     if (p.get("liga") or "") == liga and (p.get("equipo") or "") == equipo]
        await _mostrar_lista_productos(query, context, productos, f"{equipo}")

    elif data == "cat_volver_ligas":
        productos = db.get_todos_productos(solo_activos=True)
        ligas: dict[str, int] = {}
        for p in productos:
            liga = p.get("liga") or "Sin categoría"
            ligas[liga] = ligas.get(liga, 0) + 1
        botones = []
        for liga, cnt in sorted(ligas.items()):
            botones.append([InlineKeyboardButton(f"🏆 {liga}  ({cnt})", callback_data=f"cat_liga_{liga}")])
        botones.append([InlineKeyboardButton("📋 Ver todos", callback_data="cat_todos")])
        await query.edit_message_text(
            f"🛍 *Catálogo*\n\nElige una liga:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(botones),
        )

    elif data.startswith("cat_ver_"):
        pid = int(data[len("cat_ver_"):])
        producto = db.get_producto(pid)
        if not producto:
            await query.edit_message_text("❌ Producto no disponible.")
            return
        chat_id = query.message.chat.id
        get_carrito(chat_id)["producto_actual"] = producto
        # Enviar como nuevo mensaje con foto
        await _mostrar_producto_y_confirmar_desde_catalogo(query, context, producto)


async def _mostrar_lista_productos(query, context, productos: list, titulo: str):
    if not productos:
        await query.edit_message_text("No hay productos en esta categoría.")
        return
    botones = []
    for p in productos:
        botones.append([InlineKeyboardButton(
            f"👕 {p['nombre']}  —  {p['precio']:.0f}€",
            callback_data=f"cat_ver_{p['id']}"
        )])
    botones.append([InlineKeyboardButton("◀️ Volver", callback_data="cat_volver_ligas")])
    await query.edit_message_text(
        f"👕 *{titulo}* — {len(productos)} modelo(s)\n\nElige un producto para ver más info:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def _mostrar_producto_y_confirmar_desde_catalogo(query, context, producto: dict):
    chat_id = query.message.chat.id
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Añadir al carrito", callback_data="confirmar_producto"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido"),
    ]])
    texto = texto_producto(producto) + "\n\n¿Lo añadimos al carrito?"
    portada_id = producto.get("portada_id")
    try:
        if portada_id:
            foto = db.get_foto_datos(portada_id)
            if foto:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=foto, caption=texto,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                )
                return
        await context.bot.send_message(
            chat_id=chat_id, text=texto,
            parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    except TelegramError as e:
        logger.warning("Error foto: %s", e)
        await context.bot.send_message(
            chat_id=chat_id, text=texto,
            parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )


# ── Carrito ───────────────────────────────────────────────────────────────────

async def menu_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = get_carrito(chat_id).get("items", [])

    if not items:
        await update.message.reply_text(
            "🛒 *Tu carrito está vacío*\n\nUsa *🛍 Catálogo* para ver los productos disponibles.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    resumen = resumen_carrito_texto(items)
    total = calcular_total(items)

    botones = []
    for i, it in enumerate(items):
        botones.append([InlineKeyboardButton(
            f"🗑 Quitar: {it['nombre_producto'][:30]}",
            callback_data=f"carrito_quitar_{i}"
        )])
    botones.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data="carrito_finalizar"),
        InlineKeyboardButton("🗑 Vaciar", callback_data="carrito_vaciar"),
    ])

    await update.message.reply_text(
        f"🛒 *Tu carrito* — {len(items)} producto(s)\n\n{resumen}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def carrito_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    carrito = get_carrito(chat_id)
    data = query.data

    if data == "carrito_vaciar":
        limpiar_carrito(chat_id)
        await query.edit_message_text("🗑 Carrito vaciado.")
        return

    elif data.startswith("carrito_quitar_"):
        idx = int(data.split("_")[-1])
        if 0 <= idx < len(carrito["items"]):
            quitado = carrito["items"].pop(idx)
            await query.answer(f"Quitado: {quitado['nombre_producto']}", show_alert=False)
        items = carrito["items"]
        if not items:
            await query.edit_message_text("🛒 Tu carrito está vacío.")
            return
        resumen = resumen_carrito_texto(items)
        botones = []
        for i, it in enumerate(items):
            botones.append([InlineKeyboardButton(
                f"🗑 Quitar: {it['nombre_producto'][:30]}",
                callback_data=f"carrito_quitar_{i}"
            )])
        botones.append([
            InlineKeyboardButton("✅ Finalizar pedido", callback_data="carrito_finalizar"),
            InlineKeyboardButton("🗑 Vaciar", callback_data="carrito_vaciar"),
        ])
        await query.edit_message_text(
            f"🛒 *Tu carrito* — {len(items)} producto(s)\n\n{resumen}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(botones),
        )

    elif data == "carrito_finalizar":
        if not carrito["items"]:
            await query.edit_message_text("Tu carrito está vacío.")
            return
        await query.edit_message_reply_markup(reply_markup=None)
        resumen = resumen_carrito_texto(carrito["items"])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"📦 *Resumen del pedido:*\n\n{resumen}\n\n"
                f"Escribe tu *nombre completo y dirección de envío* en un mensaje:\n\n"
                f"_Ej: Juan García, Calle Mayor 10 2ºA, 28001 Madrid_"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data["checkout_desde_carrito"] = True
        return ESPERANDO_DATOS_ENVIO


# ── Flujo de pedido ───────────────────────────────────────────────────────────

async def menu_nuevo_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entrada al flujo desde catálogo — inicia selección de producto."""
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)
    await menu_catalogo(update, context)
    return ConversationHandler.END


async def _mostrar_producto_y_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE, producto: dict) -> int:
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Añadir al carrito", callback_data="confirmar_producto"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido"),
    ]])
    texto = texto_producto(producto) + "\n\n¿Lo añadimos al carrito?"
    portada_id = producto.get("portada_id")
    try:
        if portada_id:
            foto = db.get_foto_datos(portada_id)
            if foto:
                await update.effective_message.reply_photo(
                    photo=foto, caption=texto,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                )
                return ESPERANDO_CONFIRMACION_PRODUCTO
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    except TelegramError as e:
        logger.warning("Error foto: %s", e)
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    return ESPERANDO_CONFIRMACION_PRODUCTO


async def recibir_producto_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text.strip().lstrip("#")
    try:
        pid = int(texto)
    except ValueError:
        await update.message.reply_text("⚠️ Escribe solo el número del ID del producto.")
        return ESPERANDO_PRODUCTO_ID

    producto = db.get_producto(pid)
    if not producto:
        await update.message.reply_text(
            f"❌ No encontré el producto *#{pid}*. Comprueba el catálogo:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ESPERANDO_PRODUCTO_ID

    get_carrito(update.effective_chat.id)["producto_actual"] = producto
    return await _mostrar_producto_y_confirmar(update, context, producto)


async def confirmar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar_pedido":
        return await _cancelar_conversacion(update, context)

    chat_id = query.message.chat.id
    carrito = get_carrito(chat_id)
    producto = carrito.get("producto_actual")
    if not producto:
        await query.edit_message_text("⚠️ Error. Usa /start.")
        return ConversationHandler.END

    tallas = json.loads(producto.get("tallas") or '["S","M","L","XL","XXL"]')
    botones = [[InlineKeyboardButton(t, callback_data=f"talla_{t}")] for t in tallas]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido")])

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"👕 *{producto['nombre']}*\n\n¿Qué talla quieres?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(botones),
    )
    return ESPERANDO_TALLA


async def elegir_talla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar_pedido":
        return await _cancelar_conversacion(update, context)

    talla = query.data.replace("talla_", "")
    get_carrito(query.message.chat.id)["talla_actual"] = talla

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"Talla: *{talla}* ✓\n\n¿Quieres personalización en el dorsal?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"❌ Sin personalización — {PRECIO_BASE:.0f}€", callback_data="pers_sin")],
            [InlineKeyboardButton(f"✏️ Nombre + número — {PRECIO_NOMBRE_NUMERO:.0f}€", callback_data="pers_nombre_numero")],
            [InlineKeyboardButton(f"✏️ Nombre + número + parches — {PRECIO_CON_PARCHES:.0f}€", callback_data="pers_con_parches")],
            [InlineKeyboardButton("🚫 Cancelar", callback_data="cancelar_pedido")],
        ]),
    )
    return ESPERANDO_PERSONALIZACION


async def elegir_personalizacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    chat_id = query.message.chat.id
    carrito = get_carrito(chat_id)

    if query.data == "cancelar_pedido":
        return await _cancelar_conversacion(update, context)

    if query.data == "pers_sin":
        carrito.update({"personalizado_actual": False, "tipo_personalizacion_actual": "sin_personalizacion",
                        "nombre_dorsal_actual": "", "numero_dorsal_actual": ""})
        return await _agregar_item_al_carrito(update, context)

    carrito["personalizado_actual"] = True
    carrito["tipo_personalizacion_actual"] = "nombre_numero" if query.data == "pers_nombre_numero" else "nombre_numero_parches"
    await context.bot.send_message(
        chat_id=chat_id,
        text="✏️ Escribe el *nombre* para el dorsal:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_NOMBRE_DORSAL


async def recibir_nombre_dorsal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    get_carrito(update.effective_chat.id)["nombre_dorsal_actual"] = update.message.text.strip().upper()
    await update.message.reply_text(
        f"Nombre: *{update.message.text.strip().upper()}* ✓\n\nAhora escribe el *número* del dorsal:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_NUMERO_DORSAL


async def recibir_numero_dorsal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    get_carrito(update.effective_chat.id)["numero_dorsal_actual"] = update.message.text.strip()
    return await _agregar_item_al_carrito(update, context)


async def _agregar_item_al_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    producto = carrito["producto_actual"]
    tipo_pers = carrito.get("tipo_personalizacion_actual", "sin_personalizacion")

    item = {
        "producto_id": producto["id"],
        "nombre_producto": producto["nombre"],
        "talla": carrito.get("talla_actual", ""),
        "personalizado": carrito.get("personalizado_actual", False),
        "tipo_personalizacion": tipo_pers,
        "nombre_dorsal": carrito.get("nombre_dorsal_actual", ""),
        "numero_dorsal": carrito.get("numero_dorsal_actual", ""),
        "cantidad": 1,
        "precio_unitario": precio_personalizacion(tipo_pers),
    }
    carrito["items"].append(item)
    for k in ("producto_actual", "talla_actual", "personalizado_actual",
              "tipo_personalizacion_actual", "nombre_dorsal_actual", "numero_dorsal_actual"):
        carrito.pop(k, None)

    resumen = resumen_carrito_texto(carrito["items"])
    total = calcular_total(carrito["items"])

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Seguir comprando", callback_data="otro_si"),
         InlineKeyboardButton("✅ Finalizar pedido", callback_data="otro_no")],
    ])
    msg = (
        f"✅ *¡Añadido al carrito!*\n\n"
        f"{resumen}\n\n"
        f"¿Quieres añadir otro producto o finalizar el pedido?"
    )
    if update.callback_query:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado)
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado)
    return ESPERANDO_OTRO_PRODUCTO


async def otro_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "otro_si":
        productos = db.get_todos_productos(solo_activos=True)
        ligas: dict[str, int] = {}
        for p in productos:
            liga = p.get("liga") or "Sin categoría"
            ligas[liga] = ligas.get(liga, 0) + 1
        botones = [[InlineKeyboardButton(f"🏆 {l}  ({c})", callback_data=f"cat_liga_{l}")] for l, c in sorted(ligas.items())]
        botones.append([InlineKeyboardButton("📋 Ver todos", callback_data="cat_todos")])
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="¿Qué producto quieres añadir?",
            reply_markup=InlineKeyboardMarkup(botones),
        )
        return ConversationHandler.END
    else:
        return await _pedir_datos_envio(update, context)


async def _pedir_datos_envio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    resumen = resumen_carrito_texto(get_carrito(chat_id)["items"])
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"📦 *Resumen del pedido:*\n\n{resumen}\n\n"
            f"Escribe tu *nombre completo y dirección de envío*:\n\n"
            f"_Ej: Juan García, Calle Mayor 10 2ºA, 28001 Madrid_"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_DATOS_ENVIO


async def recibir_datos_envio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    datos = update.message.text.strip()
    if len(datos) < 10:
        await update.message.reply_text("⚠️ Escribe tu nombre completo y dirección completa.")
        return ESPERANDO_DATOS_ENVIO

    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    carrito["datos_envio"] = datos
    total = carrito.get("total_web") or calcular_total(carrito["items"])

    pago_txt = f"• PayPal: *paypal.me/{PAYPAL_USER}*\n"
    if BIZUM_NUMERO:
        pago_txt += f"• Bizum: *{BIZUM_NUMERO}*\n"

    await update.message.reply_text(
        f"✅ *Dirección registrada.*\n\n"
        f"💳 *Instrucciones de pago*\n"
        f"Total a pagar: *{total:.2f} €*\n\n"
        f"{pago_txt}\n"
        f"⚠️ Pon tu nombre en el *concepto* del pago.\n\n"
        f"Una vez pagado, escribe aquí el *ID o referencia del pago*:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_REFERENCIA_PAGO


async def recibir_referencia_pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ref = update.message.text.strip()
    if len(ref) < 3:
        await update.message.reply_text("⚠️ Escribe la referencia o ID del pago.")
        return ESPERANDO_REFERENCIA_PAGO

    chat_id = update.effective_chat.id
    user = update.effective_user
    carrito = get_carrito(chat_id)
    items = carrito["items"]
    datos_envio = carrito.get("datos_envio", "")
    total = carrito.get("total_web") or calcular_total(items)
    notas = context.user_data.get("resumen_web", "")

    partes = datos_envio.split(",", 1)
    nombre_cliente = partes[0].strip()
    direccion = partes[1].strip() if len(partes) > 1 else datos_envio

    try:
        pedido_id = db.crear_pedido(
            usuario_tg=user.id, username_tg=user.username or "",
            nombre_cliente=nombre_cliente, direccion=direccion,
            total=total, paypal_ref=ref, notas=notas,
        )
        for item in items:
            if not item.get("producto_id"):
                continue
            db.agregar_item_pedido(
                pedido_id=pedido_id, producto_id=item["producto_id"],
                talla=item["talla"], personalizado=item["personalizado"],
                tipo_personalizacion=item.get("tipo_personalizacion", "sin_personalizacion"),
                nombre_dorsal=item.get("nombre_dorsal", ""), numero_dorsal=item.get("numero_dorsal", ""),
                cantidad=item["cantidad"], precio_unitario=item["precio_unitario"],
            )
    except Exception as e:
        logger.error("Error guardando pedido: %s", e)
        await update.message.reply_text("❌ Error al guardar el pedido. Contacta con nosotros.")
        return ConversationHandler.END

    limpiar_carrito(chat_id)

    confirmacion = (
        f"🎉 *¡Pedido #{pedido_id} recibido!*\n\n"
        f"📋 Resumen:\n"
        f"• Total: *{total:.2f} €*\n"
        f"• Referencia de pago: `{ref}`\n"
        f"• Estado: ⏳ Pendiente de verificación\n\n"
        f"Verificaremos el pago y te avisaremos enseguida.\n"
        f"Puedes seguir el estado en *📦 Mis pedidos*. ¡Gracias! 🙏"
    )

    # Recopilar fotos de portada de los productos del pedido
    fotos = []
    for item in items:
        pid = item.get("producto_id")
        if pid:
            try:
                portada = db.get_portada(pid)
                if portada:
                    datos = db.get_foto_datos(portada["id"])
                    if datos:
                        fotos.append(datos)
            except Exception:
                pass

    try:
        if len(fotos) == 1:
            await context.bot.send_photo(
                chat_id=chat_id, photo=fotos[0],
                caption=confirmacion, parse_mode=ParseMode.MARKDOWN,
            )
        elif len(fotos) > 1:
            from telegram import InputMediaPhoto
            media = [InputMediaPhoto(media=f) for f in fotos]
            media[0] = InputMediaPhoto(media=fotos[0], caption=confirmacion, parse_mode=ParseMode.MARKDOWN)
            await context.bot.send_media_group(chat_id=chat_id, media=media)
        else:
            await update.message.reply_text(confirmacion, parse_mode=ParseMode.MARKDOWN)
    except TelegramError as e:
        logger.warning("No se pudo enviar foto de confirmación: %s", e)
        await update.message.reply_text(confirmacion, parse_mode=ParseMode.MARKDOWN)

    await _notificar_admin(context, pedido_id, user, nombre_cliente, direccion, total, items, ref)
    return ConversationHandler.END


# ── Mis pedidos ───────────────────────────────────────────────────────────────

async def menu_mis_pedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pedidos = db.get_pedidos_usuario(user_id)

    if not pedidos:
        await update.message.reply_text(
            "📦 *Aún no tienes pedidos.*\n\nUsa *🛍 Catálogo* para ver los productos disponibles.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    botones = []
    for p in pedidos[:10]:
        em = estado_emoji(p["estado"])
        fecha = str(p["created_at"])[:10]
        botones.append([InlineKeyboardButton(
            f"{em} Pedido #{p['id']}  ·  {p['total']:.0f}€  ·  {fecha}",
            callback_data=f"pedido_ver_{p['id']}"
        )])

    await update.message.reply_text(
        f"📦 *Tus pedidos* ({min(len(pedidos), 10)} últimos)\n\nPulsa en uno para ver el detalle:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def pedido_detalle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("pedido_ver_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido or pedido["usuario_tg"] != user_id:
            await query.answer("Pedido no encontrado.", show_alert=True)
            return

        items = db.get_items_pedido(pedido_id)
        estado = estado_emoji(pedido["estado"]) + " " + estado_texto(pedido["estado"])

        items_txt = []
        for it in items:
            pers = ""
            if it.get("personalizado"):
                parches = " + parches" if it.get("tipo_personalizacion") == "nombre_numero_parches" else ""
                pers = f"\n   ✏️ {it['nombre_dorsal']} #{it['numero_dorsal']}{parches}"
            items_txt.append(f"• {it['nombre_producto']} · Talla {it['talla']} · {it['precio_unitario']:.0f}€{pers}")

        # Timeline de estado
        estados = ["pendiente_pago", "en_proceso", "enviado"]
        timeline = ""
        for i, est in enumerate(estados):
            if est == pedido["estado"]:
                timeline += f"▶️ *{estado_texto(est)}*\n"
            elif estados.index(est) < estados.index(pedido["estado"]) if pedido["estado"] in estados else False:
                timeline += f"✅ {estado_texto(est)}\n"
            else:
                timeline += f"⬜ {estado_texto(est)}\n"

        texto = (
            f"📦 *Pedido #{pedido_id}*\n"
            f"Fecha: {str(pedido['created_at'])[:16]}\n\n"
            f"📍 *Estado:*\n{timeline}\n"
            f"🛍 *Productos:*\n" + "\n".join(items_txt) + "\n\n"
            f"👤 {pedido['nombre_cliente']}\n"
            f"📮 {pedido['direccion']}\n"
            f"💰 Total: *{pedido['total']:.2f} €*\n"
            f"💳 Ref: `{pedido['paypal_ref']}`"
            + (f"\n📝 {pedido['notas']}" if pedido.get("notas") else "")
        )

        botones = []
        if pedido["estado"] == "pendiente_pago":
            botones.append([InlineKeyboardButton("❌ Solicitar cancelación", callback_data=f"pedido_cancelar_{pedido_id}")])
        botones.append([InlineKeyboardButton("◀️ Volver", callback_data="pedido_volver")])

        await query.edit_message_text(texto, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(botones))

    elif data.startswith("pedido_cancelar_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido or pedido["usuario_tg"] != user_id:
            return
        await query.edit_message_text(
            f"❓ *¿Seguro que quieres cancelar el pedido #{pedido_id}?*\n\n"
            f"Total: {pedido['total']:.2f} €",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sí, cancelar", callback_data=f"pedido_confirmar_cancelar_{pedido_id}"),
                 InlineKeyboardButton("◀️ No, volver", callback_data=f"pedido_ver_{pedido_id}")],
            ]),
        )

    elif data.startswith("pedido_confirmar_cancelar_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido or pedido["usuario_tg"] != user_id:
            return
        db.actualizar_estado_pedido(pedido_id, "cancelado", "Cancelado por el cliente")
        await query.edit_message_text(
            f"✅ Solicitud de cancelación enviada para el pedido *#{pedido_id}*.\n\n"
            f"Nos pondremos en contacto contigo si es necesario.",
            parse_mode=ParseMode.MARKDOWN,
        )
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ *Cancelación solicitada*\n\nPedido *#{pedido_id}* cancelado por el cliente @{query.from_user.username or query.from_user.id}.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except TelegramError:
                pass

    elif data == "pedido_volver":
        pedidos = db.get_pedidos_usuario(user_id)
        botones = []
        for p in pedidos[:10]:
            em = estado_emoji(p["estado"])
            fecha = str(p["created_at"])[:10]
            botones.append([InlineKeyboardButton(
                f"{em} Pedido #{p['id']}  ·  {p['total']:.0f}€  ·  {fecha}",
                callback_data=f"pedido_ver_{p['id']}"
            )])
        await query.edit_message_text(
            f"📦 *Tus pedidos*\n\nPulsa en uno para ver el detalle:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(botones),
        )


# ── Notificación al admin ─────────────────────────────────────────────────────

async def _notificar_admin(context, pedido_id, user, nombre_cliente, direccion, total, items, ref):
    if not ADMIN_CHAT_ID:
        return
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    items_txt = []
    for it in items:
        pers = ""
        if it.get("personalizado"):
            tipo = it.get("tipo_personalizacion", "")
            parches_list = it.get("parches") or []
            parches_str = (" 🏷 " + ", ".join(parches_list)) if parches_list else (" + parches" if "parches" in tipo else "")
            if tipo in ("nombre_numero", "nombre_numero_parches"):
                pers = f" ✏️ {it['nombre_dorsal']} #{it['numero_dorsal']}{parches_str}"
            else:
                pers = f"{parches_str}"
        yupoo = ""
        pid = it.get("producto_id")
        if pid:
            producto = db.get_producto_admin(pid)
            yupoo = f"\n    🔗 {producto['yupoo_url']}" if producto and producto.get("yupoo_url") else ""
        items_txt.append(f"  • {it['nombre_producto']} T:{it['talla']} × {it['cantidad']} — {it['precio_unitario']:.0f}€{pers}{yupoo}")

    texto = (
        f"🛒 *NUEVO PEDIDO #{pedido_id}*\n\n"
        f"👤 *{nombre_cliente}*\n"
        f"   Telegram: {username} (ID: `{user.id}`)\n"
        f"📍 {direccion}\n\n"
        f"🛍 *Productos:*\n" + "\n".join(items_txt) + "\n\n"
        f"💰 *Total: {total:.2f} €*\n"
        f"💳 *Ref pago:* `{ref}`\n\n"
        f"⚠️ Verifica el pago antes de confirmar."
    )
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar pago", callback_data=f"admin_confirmar_{pedido_id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_rechazar_{pedido_id}"),
    ]])
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=texto,
            parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al admin: %s", e)


# ── Callbacks admin ───────────────────────────────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message.chat.id != ADMIN_CHAT_ID:
        return
    data = query.data

    if data.startswith("admin_confirmar_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido:
            return
        db.actualizar_estado_pedido(pedido_id, "en_proceso")
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚚 Marcar enviado", callback_data=f"admin_enviado_{pedido_id}"),
        ]]))
        await query.edit_message_text(
            query.message.text + "\n\n✅ *PAGO CONFIRMADO*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚚 Marcar enviado", callback_data=f"admin_enviado_{pedido_id}"),
            ]])
        )
        try:
            await context.bot.send_message(
                chat_id=pedido["usuario_tg"],
                text=(
                    f"✅ *¡Pago confirmado!*\n\n"
                    f"Tu pedido *#{pedido_id}* está en proceso.\n"
                    f"Te avisamos cuando lo enviemos. ¡Gracias por tu compra! 🎉"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError:
            pass

    elif data.startswith("admin_rechazar_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido:
            return
        db.actualizar_estado_pedido(pedido_id, "cancelado", "Pago no verificado")
        await query.edit_message_text(
            query.message.text + "\n\n❌ *PEDIDO RECHAZADO*",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_message(
                chat_id=pedido["usuario_tg"],
                text=(
                    f"❌ *No pudimos verificar tu pago para el pedido #{pedido_id}.*\n\n"
                    f"Revisa la referencia enviada o contáctanos."
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError:
            pass

    elif data.startswith("admin_enviado_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido:
            return
        db.actualizar_estado_pedido(pedido_id, "enviado")
        await query.edit_message_text(
            query.message.text + "\n\n🚚 *MARCADO COMO ENVIADO*",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_message(
                chat_id=pedido["usuario_tg"],
                text=f"🚚 *¡Tu pedido #{pedido_id} ha sido enviado!*\n\nEn breve llegará a tu dirección. ¡Gracias! 🎉",
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError:
            pass


# ── Cancelar ──────────────────────────────────────────────────────────────────

async def _cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)
    msg = "❌ Pedido cancelado. Usa *🛍 Catálogo* para empezar de nuevo."
    if update.callback_query:
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _cancelar_conversacion(update, context)


# ── Admin comandos de texto ───────────────────────────────────────────────────

def _es_admin(update: Update) -> bool:
    return update.effective_chat.id == ADMIN_CHAT_ID


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ Sin permisos.")
        return
    pedidos = db.get_pedidos_pendientes()
    if not pedidos:
        await update.message.reply_text("No hay pedidos pendientes.")
        return
    lines = [f"*Pendientes ({len(pedidos)}):*\n"]
    for p in pedidos:
        lines.append(f"🔸 *#{p['id']}* — {p['nombre_cliente']} — {p['total']:.2f}€\n   Ref: `{p['paypal_ref']}` | {str(p['created_at'])[:16]}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_pedido_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        # Cliente: ver su propio pedido
        user_id = update.effective_user.id
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Uso: /pedido {número}")
            return
        pedido_id = int(args[0])
        pedido = db.get_pedido(pedido_id)
        if not pedido or pedido["usuario_tg"] != user_id:
            await update.message.reply_text("❌ Pedido no encontrado.")
            return
        items = db.get_items_pedido(pedido_id)
        estado = estado_emoji(pedido["estado"]) + " " + estado_texto(pedido["estado"])
        items_txt = [f"• {it['nombre_producto']} T:{it['talla']} {it['precio_unitario']:.0f}€" for it in items]
        await update.message.reply_text(
            f"📦 *Pedido #{pedido_id}*\nEstado: {estado}\nTotal: {pedido['total']:.2f}€\n\n" + "\n".join(items_txt),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /pedido {id}")
        return
    pedido_id = int(args[0])
    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return
    items = db.get_items_pedido(pedido_id)
    items_txt = [f"• {it['nombre_producto']} T:{it['talla']} × {it['cantidad']} — {it['precio_unitario']:.0f}€" for it in items]
    teclado = None
    if pedido["estado"] in ("pendiente_pago", "en_proceso"):
        teclado = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data=f"admin_confirmar_{pedido_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_rechazar_{pedido_id}"),
            InlineKeyboardButton("🚚 Enviado", callback_data=f"admin_enviado_{pedido_id}"),
        ]])
    await update.message.reply_text(
        f"📦 *Pedido #{pedido_id}*\n"
        f"Estado: {estado_emoji(pedido['estado'])} {estado_texto(pedido['estado'])}\n"
        f"Cliente: {pedido['nombre_cliente']}\n"
        f"TG: @{pedido['username_tg'] or '—'} (`{pedido['usuario_tg']}`)\n"
        f"Dirección: {pedido['direccion']}\n"
        f"Total: *{pedido['total']:.2f}€*\n"
        f"Ref: `{pedido['paypal_ref']}`\n"
        f"Fecha: {str(pedido['created_at'])[:16]}\n\n"
        + "\n".join(items_txt),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=teclado,
    )


async def cmd_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update): return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /confirmar {id}")
        return
    pedido_id = int(args[0])
    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return
    db.actualizar_estado_pedido(pedido_id, "en_proceso")
    await update.message.reply_text(f"✅ Pedido #{pedido_id} confirmado.")
    try:
        await context.bot.send_message(chat_id=pedido["usuario_tg"],
            text=f"✅ *¡Pago confirmado!*\n\nTu pedido *#{pedido_id}* está en proceso. ¡Gracias! 🎉",
            parse_mode=ParseMode.MARKDOWN)
    except TelegramError: pass


async def cmd_enviado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update): return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /enviado {id} [tracking]")
        return
    pedido_id = int(args[0])
    tracking = " ".join(args[1:]) if len(args) > 1 else ""
    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return
    db.actualizar_estado_pedido(pedido_id, "enviado", f"Tracking: {tracking}" if tracking else "")
    await update.message.reply_text(f"🚚 Pedido #{pedido_id} enviado." + (f"\nTracking: `{tracking}`" if tracking else ""), parse_mode=ParseMode.MARKDOWN)
    tracking_msg = f"\n📍 Seguimiento: `{tracking}`" if tracking else ""
    try:
        await context.bot.send_message(chat_id=pedido["usuario_tg"],
            text=f"🚚 *¡Tu pedido #{pedido_id} ha sido enviado!*{tracking_msg}\n\n¡Gracias por tu compra! 🎉",
            parse_mode=ParseMode.MARKDOWN)
    except TelegramError: pass


async def cmd_cancelar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update): return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /cancelar {id} [motivo]")
        return
    pedido_id = int(args[0])
    motivo = " ".join(args[1:]) if len(args) > 1 else "Cancelado por admin"
    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return
    db.actualizar_estado_pedido(pedido_id, "cancelado", motivo)
    await update.message.reply_text(f"❌ Pedido #{pedido_id} cancelado.")
    try:
        await context.bot.send_message(chat_id=pedido["usuario_tg"],
            text=f"❌ *Tu pedido #{pedido_id} ha sido cancelado.*\n\n{motivo}", parse_mode=ParseMode.MARKDOWN)
    except TelegramError: pass


# ── Ayuda ─────────────────────────────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"*{STORE_NAME}* — Ayuda\n\n"
        f"🛍 *Catálogo* — Navega y elige productos\n"
        f"🛒 *Mi carrito* — Ver y gestionar el carrito\n"
        f"📦 *Mis pedidos* — Historial y estado de pedidos\n\n"
        f"*Comandos:*\n"
        f"/pedido {{nº}} — Ver detalle de un pedido\n"
        f"/cancelar — Cancelar el pedido en curso\n\n"
        f"💶 Precios desde *{PRECIO_BASE:.0f}€* · Envío a toda España\n"
        f"💳 Pago por PayPal" + (f" o Bizum" if BIZUM_NUMERO else ""),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU_KEYBOARD,
    )


async def mensaje_inesperado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Sigue las instrucciones anteriores o usa /cancelar para empezar de nuevo."
    )


async def recibir_pedido_web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el mensaje pre-rellenado desde la tienda web y pide dirección de envío."""
    chat_id = update.effective_chat.id
    texto   = update.message.text or ""

    limpiar_carrito(chat_id)
    carrito = get_carrito(chat_id)

    items, total = _parsear_pedido_web(texto)

    if not items:
        await update.message.reply_text(
            "❌ No pude leer el pedido. Ve a la tienda e inténtalo de nuevo.",
            reply_markup=MENU_KEYBOARD,
        )
        return ConversationHandler.END

    carrito["items"]     = items
    carrito["total_web"] = total
    context.user_data["resumen_web"] = texto

    lineas = []
    for it in items:
        label = PERS_LABEL.get(it['tipo_personalizacion'], it['tipo_personalizacion'])
        lineas.append(f"• *{it['nombre_producto']}* — Talla {it['talla']}\n  _{label}_ — {it['precio_unitario']:.0f}€")

    await update.message.reply_text(
        "✅ *¡Pedido recibido desde la tienda!*\n\n"
        + "\n\n".join(lineas)
        + f"\n\n💰 *Total: {total:.0f}€*\n\n"
        "Escribe tu *nombre completo y dirección de envío*:\n\n"
        "_Ej: Juan García, Calle Mayor 10 2ºA, 28001 Madrid_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU_KEYBOARD,
    )
    return ESPERANDO_DATOS_ENVIO


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    db.seed_demo_if_empty()

    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.Regex(r'🛒.*Pedido desde la tienda'), recibir_pedido_web),
        ],
        states={
            ESPERANDO_PRODUCTO_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_producto_id),
            ],
            ESPERANDO_CONFIRMACION_PRODUCTO: [
                CallbackQueryHandler(confirmar_producto, pattern="^(confirmar_producto|cancelar_pedido)$"),
            ],
            ESPERANDO_TALLA: [
                CallbackQueryHandler(elegir_talla, pattern="^(talla_|cancelar_pedido)"),
            ],
            ESPERANDO_PERSONALIZACION: [
                CallbackQueryHandler(elegir_personalizacion, pattern="^(pers_sin|pers_nombre_numero|pers_con_parches|cancelar_pedido)$"),
            ],
            ESPERANDO_NOMBRE_DORSAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_dorsal),
            ],
            ESPERANDO_NUMERO_DORSAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_numero_dorsal),
            ],
            ESPERANDO_OTRO_PRODUCTO: [
                CallbackQueryHandler(otro_producto, pattern="^(otro_si|otro_no)$"),
            ],
            ESPERANDO_DATOS_ENVIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_datos_envio),
            ],
            ESPERANDO_REFERENCIA_PAGO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_referencia_pago),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            MessageHandler(filters.COMMAND, mensaje_inesperado),
            MessageHandler(filters.TEXT, mensaje_inesperado),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv)

    # Menú botones
    application.add_handler(MessageHandler(filters.Regex("^🛍 Catálogo$"), menu_catalogo))
    application.add_handler(MessageHandler(filters.Regex("^🛒 Mi carrito$"), menu_carrito))
    application.add_handler(MessageHandler(filters.Regex("^📦 Mis pedidos$"), menu_mis_pedidos))
    application.add_handler(MessageHandler(filters.Regex("^❓ Ayuda$"), cmd_ayuda))

    # Callbacks inline
    application.add_handler(CallbackQueryHandler(catalogo_callback, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(carrito_callback, pattern="^carrito_"))
    application.add_handler(CallbackQueryHandler(pedido_detalle_callback, pattern="^pedido_"))
    application.add_handler(CallbackQueryHandler(confirmar_producto, pattern="^(confirmar_producto|cancelar_pedido)$"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    # Comandos
    application.add_handler(CommandHandler("mispedidos", menu_mis_pedidos))
    application.add_handler(CommandHandler("pedido", cmd_pedido_admin))
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    application.add_handler(CommandHandler("help", cmd_ayuda))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CommandHandler("confirmar", cmd_confirmar))
    application.add_handler(CommandHandler("enviado", cmd_enviado))
    application.add_handler(CommandHandler("cancelar", cmd_cancelar_admin))

    logger.info("Bot iniciado.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
