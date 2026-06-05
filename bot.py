"""
bot.py — Bot de Telegram para la tienda de camisetas.

Gestiona pedidos completos: selección de producto, talla, personalización,
resumen, datos de envío, pago por PayPal y notificaciones admin.

Uso:
    python bot.py

Requiere:
    pip install python-telegram-bot==20.7
"""

import json
import logging
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
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

# ── Configuración ────────────────────────────────────────────────────────────
BOT_TOKEN     = "8904389544:AAGzBLce1zDXjtfY0JJ8FDVX8pBQDz0p1XE"
ADMIN_CHAT_ID = 0                     # ← pon tu chat id aquí
PAYPAL_USER   = "tu.paypal@email.com" # ← paypal.me/usuario o email
BOT_USERNAME  = "tu_bot"             # ← username del bot sin @

# ── Precios de personalización ───────────────────────────────────────────────
PRECIO_BASE           = 18.0   # sin personalización
PRECIO_NOMBRE_NUMERO  = 21.0   # con nombre y número
PRECIO_CON_PARCHES    = 22.0   # con nombre, número y parches
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Estados del ConversationHandler ─────────────────────────────────────────
(
    ESPERANDO_PRODUCTO_ID,
    ESPERANDO_CONFIRMACION_PRODUCTO,
    ESPERANDO_TALLA,
    ESPERANDO_PERSONALIZACION,
    ESPERANDO_NOMBRE_DORSAL,
    ESPERANDO_NUMERO_DORSAL,
    ESPERANDO_OTRO_PRODUCTO,
    ESPERANDO_DATOS_ENVIO,
    ESPERANDO_REFERENCIA_PAYPAL,
) = range(9)

# ── Datos de carrito en memoria ──────────────────────────────────────────────
# { chat_id: { "items": [...], "producto_actual": {...} } }
carritos: dict[int, dict] = {}


def get_carrito(chat_id: int) -> dict:
    if chat_id not in carritos:
        carritos[chat_id] = {"items": [], "producto_actual": None}
    return carritos[chat_id]


def limpiar_carrito(chat_id: int):
    carritos[chat_id] = {"items": [], "producto_actual": None}


# ── Helpers de texto ─────────────────────────────────────────────────────────

def formato_producto(p: dict) -> str:
    tallas = json.loads(p.get("tallas", '["S","M","L","XL","XXL"]'))
    tallas_txt = ", ".join(tallas)
    return (
        f"*{p['nombre']}*\n"
        f"Precio desde: *{PRECIO_BASE:.0f} €*\n"
        f"Tallas disponibles: {tallas_txt}\n"
        f"ID: `#{p['id']}`"
    )


def formato_resumen_carrito(items: list[dict]) -> str:
    if not items:
        return "_Carrito vacío_"
    lineas = []
    total = 0.0
    for i, item in enumerate(items, 1):
        precio_item = item["precio_unitario"] * item["cantidad"]
        total += precio_item
        pers = ""
        if item.get("personalizado"):
            tipo = item.get("tipo_personalizacion", "")
            parches_txt = " + parches" if tipo == "nombre_numero_parches" else ""
            pers = f" | Dorsal: {item.get('nombre_dorsal','')} #{item.get('numero_dorsal','')}{parches_txt}"
        lineas.append(
            f"{i}. *{item['nombre_producto']}* — Talla {item['talla']}"
            f"{pers} × {item['cantidad']} = {precio_item:.2f} €"
        )
    lineas.append(f"\n💰 *Total: {total:.2f} €*")
    return "\n".join(lineas)


def calcular_total(items: list[dict]) -> float:
    return sum(it["precio_unitario"] * it["cantidad"] for it in items)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db.init_db()
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)

    # Detectar si viene con parámetro producto_ID
    args = context.args or []
    producto_id = None
    if args:
        param = args[0]
        if param.startswith("producto_"):
            try:
                producto_id = int(param.split("_", 1)[1])
            except (ValueError, IndexError):
                producto_id = None

    bienvenida = (
        "👕 *Bienvenido a la tienda de camisetas*\n\n"
        "Aquí puedes hacer tu pedido fácilmente.\n"
        "Te guiaré paso a paso.\n\n"
    )

    if producto_id is not None:
        producto = db.get_producto(producto_id)
        if producto:
            get_carrito(chat_id)["producto_actual"] = producto
            await update.message.reply_text(bienvenida, parse_mode=ParseMode.MARKDOWN)
            return await _mostrar_producto_y_confirmar(update, context, producto)
        else:
            await update.message.reply_text(
                bienvenida + f"⚠️ El producto #{producto_id} no está disponible.\n"
                "Por favor escribe el *ID del producto* que quieres pedir:",
                parse_mode=ParseMode.MARKDOWN,
            )
            return ESPERANDO_PRODUCTO_ID

    await update.message.reply_text(
        bienvenida + "Por favor escribe el *ID del producto* que quieres pedir:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_PRODUCTO_ID


# ── Paso 1: recibir ID de producto ────────────────────────────────────────────

async def recibir_producto_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text.strip().lstrip("#")
    try:
        producto_id = int(texto)
    except ValueError:
        await update.message.reply_text(
            "⚠️ Por favor escribe solo el número del ID del producto."
        )
        return ESPERANDO_PRODUCTO_ID

    producto = db.get_producto(producto_id)
    if not producto:
        await update.message.reply_text(
            f"❌ No encontré el producto con ID *#{producto_id}*.\n"
            "Comprueba el catálogo y escribe otro ID:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ESPERANDO_PRODUCTO_ID

    chat_id = update.effective_chat.id
    get_carrito(chat_id)["producto_actual"] = producto
    return await _mostrar_producto_y_confirmar(update, context, producto)


async def _mostrar_producto_y_confirmar(
    update: Update, context: ContextTypes.DEFAULT_TYPE, producto: dict
) -> int:
    """Muestra la ficha del producto y pide confirmación."""
    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sí, lo quiero", callback_data="confirmar_producto"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido"),
        ]
    ])

    texto = formato_producto(producto) + "\n\n¿Quieres añadir este producto?"
    foto_path = producto.get("foto_path", "")

    try:
        if foto_path and Path(foto_path).exists():
            with open(foto_path, "rb") as f:
                await update.effective_message.reply_photo(
                    photo=f,
                    caption=texto,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=teclado,
                )
        else:
            await update.effective_message.reply_text(
                texto,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=teclado,
            )
    except TelegramError as e:
        logger.warning("Error enviando foto: %s", e)
        await update.effective_message.reply_text(
            texto,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=teclado,
        )

    return ESPERANDO_CONFIRMACION_PRODUCTO


# ── Paso 2: confirmar producto ────────────────────────────────────────────────

async def confirmar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar_pedido":
        return await _cancelar_conversacion(update, context)

    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    producto = carrito.get("producto_actual")
    if not producto:
        await query.edit_message_text("⚠️ Error interno. Usa /start para comenzar.")
        return ConversationHandler.END

    tallas = json.loads(producto.get("tallas", '["S","M","L","XL","XXL"]'))
    botones = [[InlineKeyboardButton(t, callback_data=f"talla_{t}")] for t in tallas]
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido")])

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=chat_id,
        text="👕 ¿Qué talla quieres?",
        reply_markup=InlineKeyboardMarkup(botones),
    )
    return ESPERANDO_TALLA


# ── Paso 3: elegir talla ──────────────────────────────────────────────────────

async def elegir_talla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar_pedido":
        return await _cancelar_conversacion(update, context)

    talla = query.data.replace("talla_", "")
    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    carrito["talla_actual"] = talla

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"Talla seleccionada: *{talla}*\n\n"
            f"¿Quieres personalización?"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"Sin personalización ({PRECIO_BASE:.0f}€)",
                callback_data="pers_sin"
            )],
            [InlineKeyboardButton(
                f"Con nombre y número (+3€, total {PRECIO_NOMBRE_NUMERO:.0f}€)",
                callback_data="pers_nombre_numero"
            )],
            [InlineKeyboardButton(
                f"Con nombre, número y parches (+4€, total {PRECIO_CON_PARCHES:.0f}€)",
                callback_data="pers_con_parches"
            )],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_pedido")],
        ]),
    )
    return ESPERANDO_PERSONALIZACION


# ── Paso 4: personalización ───────────────────────────────────────────────────

async def elegir_personalizacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)

    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "pers_sin":
        carrito["personalizado_actual"] = False
        carrito["tipo_personalizacion_actual"] = "sin_personalizacion"
        carrito["nombre_dorsal_actual"] = ""
        carrito["numero_dorsal_actual"] = ""
        return await _agregar_item_al_carrito(update, context)
    elif query.data in ("pers_nombre_numero", "pers_con_parches"):
        carrito["personalizado_actual"] = True
        if query.data == "pers_nombre_numero":
            carrito["tipo_personalizacion_actual"] = "nombre_numero"
        else:
            carrito["tipo_personalizacion_actual"] = "nombre_numero_parches"
        await context.bot.send_message(
            chat_id=chat_id,
            text="✏️ Escribe el *nombre* que quieres en el dorsal:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ESPERANDO_NOMBRE_DORSAL
    else:
        # fallback
        carrito["personalizado_actual"] = False
        carrito["tipo_personalizacion_actual"] = "sin_personalizacion"
        carrito["nombre_dorsal_actual"] = ""
        carrito["numero_dorsal_actual"] = ""
        return await _agregar_item_al_carrito(update, context)


async def recibir_nombre_dorsal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre_dorsal = update.message.text.strip()
    chat_id = update.effective_chat.id
    get_carrito(chat_id)["nombre_dorsal_actual"] = nombre_dorsal

    await update.message.reply_text(
        f"Nombre: *{nombre_dorsal}*\n\nAhora escribe el *número* del dorsal:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_NUMERO_DORSAL


async def recibir_numero_dorsal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    numero_dorsal = update.message.text.strip()
    chat_id = update.effective_chat.id
    get_carrito(chat_id)["numero_dorsal_actual"] = numero_dorsal

    return await _agregar_item_al_carrito(update, context)


async def _agregar_item_al_carrito(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Añade el producto actual al carrito y pregunta si quiere otro."""
    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    producto = carrito["producto_actual"]

    tipo_pers = carrito.get("tipo_personalizacion_actual", "sin_personalizacion")
    if tipo_pers == "nombre_numero":
        precio_unitario = PRECIO_NOMBRE_NUMERO
    elif tipo_pers == "nombre_numero_parches":
        precio_unitario = PRECIO_CON_PARCHES
    else:
        precio_unitario = PRECIO_BASE

    item = {
        "producto_id": producto["id"],
        "nombre_producto": producto["nombre"],
        "talla": carrito.get("talla_actual", ""),
        "personalizado": carrito.get("personalizado_actual", False),
        "tipo_personalizacion": tipo_pers,
        "nombre_dorsal": carrito.get("nombre_dorsal_actual", ""),
        "numero_dorsal": carrito.get("numero_dorsal_actual", ""),
        "cantidad": 1,
        "precio_unitario": precio_unitario,
    }
    carrito["items"].append(item)

    # Limpiar datos temporales del item
    for k in ("producto_actual", "talla_actual", "personalizado_actual",
               "tipo_personalizacion_actual", "nombre_dorsal_actual", "numero_dorsal_actual"):
        carrito.pop(k, None)

    resumen = formato_resumen_carrito(carrito["items"])

    msg = (
        f"✅ Producto añadido al carrito.\n\n"
        f"*Tu carrito:*\n{resumen}\n\n"
        f"¿Quieres añadir otro producto?"
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Añadir otro", callback_data="otro_si"),
            InlineKeyboardButton("🛒 Finalizar", callback_data="otro_no"),
        ]
    ])

    if update.callback_query:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=teclado,
        )
    else:
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=teclado,
        )

    return ESPERANDO_OTRO_PRODUCTO


# ── Paso 5: ¿otro producto? ───────────────────────────────────────────────────

async def otro_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    chat_id = update.effective_chat.id

    if query.data == "otro_si":
        await context.bot.send_message(
            chat_id=chat_id,
            text="Escribe el *ID del siguiente producto* que quieres añadir:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ESPERANDO_PRODUCTO_ID
    else:
        return await _pedir_datos_envio(update, context)


async def _pedir_datos_envio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    resumen = formato_resumen_carrito(carrito["items"])
    total = calcular_total(carrito["items"])

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*Resumen de tu pedido:*\n{resumen}\n\n"
            f"Por favor escribe tu *nombre completo y dirección de envío* "
            f"en un solo mensaje.\n\n"
            f"_Ejemplo: Juan García López, Calle Mayor 10, 2ºA, 28001 Madrid_"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_DATOS_ENVIO


# ── Paso 6: datos de envío ────────────────────────────────────────────────────

async def recibir_datos_envio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    datos = update.message.text.strip()
    if len(datos) < 10:
        await update.message.reply_text(
            "⚠️ Por favor escribe tu nombre completo y dirección completa."
        )
        return ESPERANDO_DATOS_ENVIO

    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    carrito["datos_envio"] = datos
    total = calcular_total(carrito["items"])

    await update.message.reply_text(
        f"📦 *Datos de envío registrados.*\n\n"
        f"💳 *Instrucciones de pago:*\n"
        f"El total de tu pedido es *{total:.2f} €*.\n\n"
        f"Realiza el pago a través de PayPal:\n"
        f"👉 *paypal.me/{PAYPAL_USER}*\n\n"
        f"O mediante transferencia a: `{PAYPAL_USER}`\n\n"
        f"⚠️ Indica tu nombre completo en el *concepto/nota* del pago.\n\n"
        f"Una vez realizado el pago, escribe aquí el *ID de transacción o "
        f"referencia de PayPal*:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_REFERENCIA_PAYPAL


# ── Paso 7: referencia PayPal → guardar pedido ───────────────────────────────

async def recibir_referencia_paypal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    paypal_ref = update.message.text.strip()
    if len(paypal_ref) < 3:
        await update.message.reply_text(
            "⚠️ Por favor escribe la referencia o ID de transacción de PayPal."
        )
        return ESPERANDO_REFERENCIA_PAYPAL

    chat_id = update.effective_chat.id
    user = update.effective_user
    carrito = get_carrito(chat_id)
    items = carrito["items"]
    datos_envio = carrito.get("datos_envio", "")
    total = calcular_total(items)

    # Separar nombre y dirección (primer separador coma)
    partes = datos_envio.split(",", 1)
    nombre_cliente = partes[0].strip()
    direccion = partes[1].strip() if len(partes) > 1 else datos_envio

    try:
        pedido_id = db.crear_pedido(
            usuario_tg=user.id,
            username_tg=user.username or "",
            nombre_cliente=nombre_cliente,
            direccion=direccion,
            total=total,
            paypal_ref=paypal_ref,
        )
        for item in items:
            db.agregar_item_pedido(
                pedido_id=pedido_id,
                producto_id=item["producto_id"],
                talla=item["talla"],
                personalizado=item["personalizado"],
                tipo_personalizacion=item.get("tipo_personalizacion", "sin_personalizacion"),
                nombre_dorsal=item.get("nombre_dorsal", ""),
                numero_dorsal=item.get("numero_dorsal", ""),
                cantidad=item["cantidad"],
                precio_unitario=item["precio_unitario"],
            )
    except Exception as e:
        logger.error("Error guardando pedido: %s", e)
        await update.message.reply_text(
            "❌ Hubo un error al guardar tu pedido. Por favor contacta con nosotros."
        )
        return ConversationHandler.END

    limpiar_carrito(chat_id)

    await update.message.reply_text(
        f"✅ *Pedido #{pedido_id} registrado correctamente.*\n\n"
        f"Estado: ⏳ Pendiente de pago\n"
        f"Total: *{total:.2f} €*\n"
        f"Referencia PayPal: `{paypal_ref}`\n\n"
        f"Te avisaremos en cuanto confirmemos el pago. ¡Gracias!",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Notificar al admin
    await _notificar_admin_nuevo_pedido(context, pedido_id, user, total, items, paypal_ref)

    return ConversationHandler.END


async def _notificar_admin_nuevo_pedido(
    context: ContextTypes.DEFAULT_TYPE,
    pedido_id: int,
    user,
    total: float,
    items: list[dict],
    paypal_ref: str,
):
    if not ADMIN_CHAT_ID:
        return
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    resumen = "\n".join(
        f"  • {it['nombre_producto']} T:{it['talla']}"
        + (f" ({it['nombre_dorsal']} #{it['numero_dorsal']})" if it.get("personalizado") else "")
        for it in items
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🛒 *Nuevo pedido #{pedido_id}*\n"
                f"Cliente: {user.full_name} ({username})\n"
                f"Total: *{total:.2f} €*\n"
                f"PayPal ref: `{paypal_ref}`\n\n"
                f"Productos:\n{resumen}\n\n"
                f"Usa /pedido {pedido_id} para ver el detalle completo."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al admin: %s", e)


# ── Cancelar conversación ─────────────────────────────────────────────────────

async def _cancelar_conversacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)
    msg = "❌ Pedido cancelado. Usa /start cuando quieras hacer un nuevo pedido."
    if update.callback_query:
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat_id, text=msg)
    else:
        await update.effective_message.reply_text(msg)
    return ConversationHandler.END


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _cancelar_conversacion(update, context)


# ── /mispedidos ───────────────────────────────────────────────────────────────

async def cmd_mispedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    user_id = update.effective_user.id
    pedidos = db.get_pedidos_usuario(user_id)

    if not pedidos:
        await update.message.reply_text(
            "No tienes pedidos registrados. Usa /start para hacer tu primer pedido."
        )
        return

    lines = ["*Tus pedidos:*\n"]
    for p in pedidos[:10]:
        estado = db.estado_label(p["estado"])
        lines.append(
            f"📦 *Pedido #{p['id']}* — {estado}\n"
            f"   Total: {p['total']:.2f} € | Fecha: {p['created_at'][:10]}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Comandos de admin ─────────────────────────────────────────────────────────

def _es_admin(update: Update) -> bool:
    return update.effective_chat.id == ADMIN_CHAT_ID


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    db.init_db()
    pedidos = db.get_pedidos_pendientes()
    if not pedidos:
        await update.message.reply_text("No hay pedidos pendientes de pago.")
        return
    lines = [f"*Pedidos pendientes de pago ({len(pedidos)}):*\n"]
    for p in pedidos:
        lines.append(
            f"🔸 *#{p['id']}* — {p['nombre_cliente']} — {p['total']:.2f} €\n"
            f"   Ref PayPal: `{p['paypal_ref']}` | {p['created_at'][:16]}"
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    db.init_db()

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
    estado = db.estado_label(pedido["estado"])

    items_txt = []
    for it in items:
        pers = ""
        if it.get("personalizado"):
            pers = f" — Dorsal: {it['nombre_dorsal']} #{it['numero_dorsal']}"
        items_txt.append(
            f"  • {it['nombre_producto']} × {it['cantidad']} | T:{it['talla']}"
            f"{pers} | {it['precio_unitario']:.2f} €/u"
        )

    await update.message.reply_text(
        f"*Pedido #{pedido_id}*\n"
        f"Estado: {estado}\n"
        f"Cliente: {pedido['nombre_cliente']}\n"
        f"Username TG: @{pedido['username_tg'] or '—'} (ID: {pedido['usuario_tg']})\n"
        f"Dirección: {pedido['direccion']}\n"
        f"Total: {pedido['total']:.2f} €\n"
        f"Ref PayPal: `{pedido['paypal_ref']}`\n"
        f"Fecha: {pedido['created_at']}\n"
        f"Notas: {pedido['notas'] or '—'}\n\n"
        f"*Productos:*\n" + "\n".join(items_txt),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    db.init_db()

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
    await update.message.reply_text(f"✅ Pedido #{pedido_id} marcado como *En proceso*.", parse_mode=ParseMode.MARKDOWN)

    # Notificar al cliente
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=(
                f"✅ *Pago confirmado.*\n\n"
                f"Tu pedido *#{pedido_id}* está ahora en proceso. "
                f"Te avisaremos cuando sea enviado. ¡Gracias por tu compra! 🙏"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al cliente (pedido %d): %s", pedido_id, e)
        await update.message.reply_text("⚠️ No se pudo notificar al cliente (posiblemente bloqueó el bot).")


async def cmd_enviado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    db.init_db()

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /enviado {id} [tracking_opcional]")
        return

    pedido_id = int(args[0])
    tracking = " ".join(args[1:]) if len(args) > 1 else ""

    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return

    notas = f"Tracking: {tracking}" if tracking else ""
    db.actualizar_estado_pedido(pedido_id, "enviado", notas)
    await update.message.reply_text(
        f"🚚 Pedido #{pedido_id} marcado como *Enviado*."
        + (f"\nTracking: `{tracking}`" if tracking else ""),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Notificar al cliente
    tracking_msg = f"\n📍 Número de seguimiento: `{tracking}`" if tracking else ""
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=(
                f"🚚 *¡Tu pedido #{pedido_id} ha sido enviado!*\n"
                f"{tracking_msg}\n\n"
                f"Pronto llegará a tu dirección. ¡Gracias por tu compra! 🎉"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al cliente (pedido %d): %s", pedido_id, e)
        await update.message.reply_text("⚠️ No se pudo notificar al cliente.")


async def cmd_cancelar_pedido_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    db.init_db()

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /cancelar {id} [motivo_opcional]")
        return

    pedido_id = int(args[0])
    motivo = " ".join(args[1:]) if len(args) > 1 else ""

    pedido = db.get_pedido(pedido_id)
    if not pedido:
        await update.message.reply_text(f"❌ Pedido #{pedido_id} no encontrado.")
        return

    notas = f"Cancelado: {motivo}" if motivo else "Cancelado por admin"
    db.actualizar_estado_pedido(pedido_id, "cancelado", notas)
    await update.message.reply_text(f"❌ Pedido #{pedido_id} marcado como *Cancelado*.", parse_mode=ParseMode.MARKDOWN)

    # Notificar al cliente
    motivo_msg = f"\nMotivo: {motivo}" if motivo else ""
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=(
                f"❌ *Tu pedido #{pedido_id} ha sido cancelado.*"
                f"{motivo_msg}\n\n"
                f"Si tienes dudas, contacta con nosotros. Lo sentimos."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al cliente (pedido %d): %s", pedido_id, e)
        await update.message.reply_text("⚠️ No se pudo notificar al cliente.")


# ── Mensaje de ayuda por defecto ──────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Comandos disponibles:*\n\n"
        "/start — Iniciar un nuevo pedido\n"
        "/mispedidos — Ver tus pedidos\n"
        "/cancelar — Cancelar el pedido en curso\n\n"
        "_Para hacer un pedido, visita nuestro catálogo o usa /start._",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Mensaje inesperado durante conversación ───────────────────────────────────

async def mensaje_inesperado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ No entendí ese mensaje en este momento.\n"
        "Sigue las instrucciones anteriores o usa /cancelar para empezar de nuevo."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler para el flujo de pedido
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
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
                CallbackQueryHandler(
                    elegir_personalizacion,
                    pattern="^(pers_sin|pers_nombre_numero|pers_con_parches|cancelar_pedido)$"
                ),
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
            ESPERANDO_REFERENCIA_PAYPAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_referencia_paypal),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            MessageHandler(filters.COMMAND, mensaje_inesperado),
            MessageHandler(filters.TEXT, mensaje_inesperado),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    # Comandos fuera de conversación
    app.add_handler(CommandHandler("mispedidos", cmd_mispedidos))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))

    # Comandos de admin
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("pedido", cmd_pedido))
    app.add_handler(CommandHandler("confirmar", cmd_confirmar))
    app.add_handler(CommandHandler("enviado", cmd_enviado))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar_pedido_admin))

    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
