"""
bot.py — Bot de Telegram para la tienda de camisetas.
"""

import json
import logging
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
BOT_USERNAME  = os.environ.get("BOT_USERNAME", "tu_bot")

PRECIO_BASE           = 18.0
PRECIO_NOMBRE_NUMERO  = 21.0
PRECIO_CON_PARCHES    = 22.0

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

# ── Carrito en memoria ───────────────────────────────────────────────────────
carritos: dict[int, dict] = {}

def get_carrito(chat_id: int) -> dict:
    if chat_id not in carritos:
        carritos[chat_id] = {"items": [], "producto_actual": None}
    return carritos[chat_id]

def limpiar_carrito(chat_id: int):
    carritos[chat_id] = {"items": [], "producto_actual": None}


# ── Teclado principal (siempre visible) ─────────────────────────────────────

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Nuevo pedido"), KeyboardButton("🛍 Mi carrito")],
        [KeyboardButton("📦 Mis pedidos"),  KeyboardButton("❓ Ayuda")],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


# ── Helpers de texto ─────────────────────────────────────────────────────────

def formato_producto(p: dict) -> str:
    tallas = json.loads(p.get("tallas", '["S","M","L","XL","XXL"]'))
    return (
        f"*{p['nombre']}*\n"
        f"Precio desde: *{PRECIO_BASE:.0f} €*\n"
        f"Tallas disponibles: {', '.join(tallas)}\n"
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


def formato_pedido_completo(pedido: dict, items: list[dict]) -> str:
    estado = db.estado_label(pedido["estado"])
    items_txt = []
    for it in items:
        pers = ""
        if it.get("personalizado"):
            tipo = it.get("tipo_personalizacion", "")
            parches_txt = " + parches" if tipo == "nombre_numero_parches" else ""
            pers = f"\n     ✏️ Dorsal: *{it['nombre_dorsal']} #{it['numero_dorsal']}*{parches_txt}"
        items_txt.append(
            f"  • {it['nombre_producto']} — Talla *{it['talla']}*"
            f" × {it['cantidad']} — {it['precio_unitario']:.2f} €/u{pers}"
        )
    return (
        f"📦 *Pedido #{pedido['id']}*\n"
        f"Estado: {estado}\n"
        f"Fecha: {pedido['created_at'][:16]}\n\n"
        f"👤 *Cliente:* {pedido['nombre_cliente']}\n"
        f"📍 *Dirección:* {pedido['direccion']}\n"
        f"💳 *Ref PayPal:* `{pedido['paypal_ref']}`\n\n"
        f"*Productos:*\n" + "\n".join(items_txt) + f"\n\n"
        f"💰 *Total: {pedido['total']:.2f} €*"
        + (f"\n📝 Notas: {pedido['notas']}" if pedido.get("notas") else "")
    )


# ── Menú principal ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db.init_db()
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)

    args = context.args or []
    producto_id = None
    if args and args[0].startswith("producto_"):
        try:
            producto_id = int(args[0].split("_", 1)[1])
        except (ValueError, IndexError):
            pass

    bienvenida = (
        "👕 *Bienvenido a la tienda de camisetas*\n\n"
        "Usa los botones del menú o /ayuda para ver las opciones disponibles.\n\n"
    )

    if producto_id is not None:
        producto = db.get_producto(producto_id)
        if producto:
            get_carrito(chat_id)["producto_actual"] = producto
            await update.message.reply_text(
                bienvenida, parse_mode=ParseMode.MARKDOWN, reply_markup=MENU_KEYBOARD
            )
            return await _mostrar_producto_y_confirmar(update, context, producto)
        else:
            await update.message.reply_text(
                bienvenida + f"⚠️ El producto #{producto_id} no está disponible.\n"
                "Escribe el *ID del producto* que quieres pedir:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MENU_KEYBOARD,
            )
            return ESPERANDO_PRODUCTO_ID

    await update.message.reply_text(
        bienvenida + "Escribe el *ID del producto* que quieres pedir "
        "o pulsa *🛒 Nuevo pedido*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU_KEYBOARD,
    )
    return ESPERANDO_PRODUCTO_ID


async def menu_nuevo_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botón 🛒 Nuevo pedido desde el menú."""
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)
    await update.message.reply_text(
        "Escribe el *ID del producto* que quieres pedir\n"
        "_(puedes verlo en el catálogo)_:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_PRODUCTO_ID


async def menu_mi_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón 🛍 Mi carrito — muestra el carrito activo."""
    chat_id = update.effective_chat.id
    carrito = get_carrito(chat_id)
    items = carrito.get("items", [])

    if not items:
        await update.message.reply_text(
            "🛍 Tu carrito está vacío.\n\nUsa *🛒 Nuevo pedido* para empezar.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    resumen = formato_resumen_carrito(items)
    total = calcular_total(items)

    await update.message.reply_text(
        f"🛍 *Tu carrito actual:*\n\n{resumen}\n\n"
        f"Tienes {len(items)} producto(s) por *{total:.2f} €*.\n\n"
        f"Continúa con /start para finalizar el pedido o añadir más productos.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def menu_mis_pedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón 📦 Mis pedidos — historial del cliente."""
    user_id = update.effective_user.id
    pedidos = db.get_pedidos_usuario(user_id)

    if not pedidos:
        await update.message.reply_text(
            "No tienes pedidos registrados todavía.\n\nUsa *🛒 Nuevo pedido* para hacer tu primer pedido.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"*Tus últimos pedidos ({min(len(pedidos),10)}):*\n"]
    for p in pedidos[:10]:
        estado = db.estado_label(p["estado"])
        lines.append(
            f"📦 *Pedido #{p['id']}* — {estado}\n"
            f"   Total: {p['total']:.2f} € · {p['created_at'][:10]}"
        )
    lines.append("\n_Usa /pedido {número} para ver el detalle de un pedido._")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_ver_pedido_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El cliente puede ver el detalle de uno de sus pedidos con /pedido {id}."""
    user_id = update.effective_user.id
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Uso: /pedido {número de pedido}")
        return

    pedido_id = int(args[0])
    pedido = db.get_pedido(pedido_id)
    if not pedido or pedido["usuario_tg"] != user_id:
        await update.message.reply_text("❌ Pedido no encontrado o no es tuyo.")
        return

    items = db.get_items_pedido(pedido_id)
    await update.message.reply_text(
        formato_pedido_completo(pedido, items),
        parse_mode=ParseMode.MARKDOWN,
    )


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
                    photo=f, caption=texto,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                )
        else:
            portada_id = producto.get("portada_id")
            if portada_id:
                foto_bytes = db.get_foto_datos(portada_id)
                if foto_bytes:
                    await update.effective_message.reply_photo(
                        photo=foto_bytes, caption=texto,
                        parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                    )
                else:
                    await update.effective_message.reply_text(
                        texto, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                    )
            else:
                await update.effective_message.reply_text(
                    texto, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
                )
    except TelegramError as e:
        logger.warning("Error enviando foto: %s", e)
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
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
    get_carrito(chat_id)["talla_actual"] = talla

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Talla seleccionada: *{talla}*\n\n¿Quieres personalización?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"Sin personalización ({PRECIO_BASE:.0f}€)", callback_data="pers_sin"
            )],
            [InlineKeyboardButton(
                f"Con nombre y número ({PRECIO_NOMBRE_NUMERO:.0f}€)", callback_data="pers_nombre_numero"
            )],
            [InlineKeyboardButton(
                f"Con nombre, número y parches ({PRECIO_CON_PARCHES:.0f}€)", callback_data="pers_con_parches"
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
        carrito.update({
            "personalizado_actual": False,
            "tipo_personalizacion_actual": "sin_personalizacion",
            "nombre_dorsal_actual": "",
            "numero_dorsal_actual": "",
        })
        return await _agregar_item_al_carrito(update, context)
    elif query.data in ("pers_nombre_numero", "pers_con_parches"):
        carrito["personalizado_actual"] = True
        carrito["tipo_personalizacion_actual"] = (
            "nombre_numero" if query.data == "pers_nombre_numero" else "nombre_numero_parches"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="✏️ Escribe el *nombre* que quieres en el dorsal:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ESPERANDO_NOMBRE_DORSAL
    else:
        carrito.update({
            "personalizado_actual": False,
            "tipo_personalizacion_actual": "sin_personalizacion",
            "nombre_dorsal_actual": "",
            "numero_dorsal_actual": "",
        })
        return await _agregar_item_al_carrito(update, context)


async def recibir_nombre_dorsal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre_dorsal = update.message.text.strip()
    get_carrito(update.effective_chat.id)["nombre_dorsal_actual"] = nombre_dorsal
    await update.message.reply_text(
        f"Nombre: *{nombre_dorsal}*\n\nAhora escribe el *número* del dorsal:",
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
    precio_unitario = {
        "nombre_numero": PRECIO_NOMBRE_NUMERO,
        "nombre_numero_parches": PRECIO_CON_PARCHES,
    }.get(tipo_pers, PRECIO_BASE)

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
            chat_id=chat_id, text=msg,
            parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    else:
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=teclado,
        )
    return ESPERANDO_OTRO_PRODUCTO


# ── Paso 5: ¿otro producto? ───────────────────────────────────────────────────

async def otro_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "otro_si":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
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

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*Resumen de tu pedido:*\n{resumen}\n\n"
            f"Por favor escribe tu *nombre completo y dirección de envío* en un solo mensaje.\n\n"
            f"_Ejemplo: Juan García López, Calle Mayor 10 2ºA, 28001 Madrid_"
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
        f"⚠️ Indica tu nombre en el *concepto/nota* del pago.\n\n"
        f"Una vez realizado, escribe aquí el *ID de transacción de PayPal*:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ESPERANDO_REFERENCIA_PAYPAL


# ── Paso 7: referencia PayPal → guardar pedido ───────────────────────────────

async def recibir_referencia_paypal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        f"Estado: ⏳ Pendiente de verificación de pago\n"
        f"Total: *{total:.2f} €*\n"
        f"Referencia PayPal: `{paypal_ref}`\n\n"
        f"Verificaremos el pago y te avisaremos en cuanto esté confirmado. ¡Gracias! 🙏",
        parse_mode=ParseMode.MARKDOWN,
    )

    await _notificar_admin_nuevo_pedido(context, pedido_id, user, nombre_cliente, direccion, total, items, paypal_ref)
    return ConversationHandler.END


async def _notificar_admin_nuevo_pedido(
    context: ContextTypes.DEFAULT_TYPE,
    pedido_id: int,
    user,
    nombre_cliente: str,
    direccion: str,
    total: float,
    items: list[dict],
    paypal_ref: str,
):
    if not ADMIN_CHAT_ID:
        return

    username = f"@{user.username}" if user.username else f"ID:{user.id}"

    items_txt = []
    for it in items:
        pers = ""
        if it.get("personalizado"):
            tipo = it.get("tipo_personalizacion", "")
            parches_txt = " + parches" if tipo == "nombre_numero_parches" else ""
            pers = f" ✏️ {it['nombre_dorsal']} #{it['numero_dorsal']}{parches_txt}"
        items_txt.append(
            f"  • {it['nombre_producto']} T:{it['talla']} × {it['cantidad']} — {it['precio_unitario']:.2f}€{pers}"
        )

    texto = (
        f"🛒 *NUEVO PEDIDO #{pedido_id}*\n\n"
        f"👤 *Cliente:* {nombre_cliente}\n"
        f"   Telegram: {username} (ID: `{user.id}`)\n"
        f"📍 *Dirección:* {direccion}\n\n"
        f"🛍 *Productos:*\n" + "\n".join(items_txt) + "\n\n"
        f"💰 *Total: {total:.2f} €*\n"
        f"💳 *Ref PayPal:* `{paypal_ref}`\n\n"
        f"⚠️ Verifica el pago en PayPal antes de confirmar."
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar pago", callback_data=f"admin_confirmar_{pedido_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_rechazar_{pedido_id}"),
        ]
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=texto,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=teclado,
        )
    except TelegramError as e:
        logger.warning("No se pudo notificar al admin: %s", e)


# ── Callbacks de admin (confirmar/rechazar desde notificación) ────────────────

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
            await query.edit_message_text(f"❌ Pedido #{pedido_id} no encontrado.")
            return

        db.actualizar_estado_pedido(pedido_id, "en_proceso")

        # Editar el mensaje del admin
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(
            query.message.text + f"\n\n✅ *PAGO CONFIRMADO* por el admin.",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Notificar al cliente
        try:
            await context.bot.send_message(
                chat_id=pedido["usuario_tg"],
                text=(
                    f"✅ *¡Pago confirmado!*\n\n"
                    f"Tu pedido *#{pedido_id}* está ahora en proceso.\n"
                    f"Te avisaremos cuando sea enviado. ¡Gracias por tu compra! 🎉"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError as e:
            logger.warning("No se pudo notificar al cliente: %s", e)

    elif data.startswith("admin_rechazar_"):
        pedido_id = int(data.split("_")[-1])
        pedido = db.get_pedido(pedido_id)
        if not pedido:
            await query.edit_message_text(f"❌ Pedido #{pedido_id} no encontrado.")
            return

        db.actualizar_estado_pedido(pedido_id, "cancelado", "Pago no verificado")

        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(
            query.message.text + f"\n\n❌ *PEDIDO RECHAZADO* por el admin.",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            await context.bot.send_message(
                chat_id=pedido["usuario_tg"],
                text=(
                    f"❌ *No pudimos verificar tu pago para el pedido #{pedido_id}.*\n\n"
                    f"Por favor revisa la referencia enviada o contacta con nosotros."
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramError as e:
            logger.warning("No se pudo notificar al cliente: %s", e)


# ── Cancelar conversación ─────────────────────────────────────────────────────

async def _cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    limpiar_carrito(chat_id)
    msg = "❌ Pedido cancelado. Usa *🛒 Nuevo pedido* cuando quieras volver a empezar."
    if update.callback_query:
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _cancelar_conversacion(update, context)


# ── Comandos de admin (por texto) ─────────────────────────────────────────────

def _es_admin(update: Update) -> bool:
    return update.effective_chat.id == ADMIN_CHAT_ID


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return
    pedidos = db.get_pedidos_pendientes()
    if not pedidos:
        await update.message.reply_text("No hay pedidos pendientes de pago.")
        return
    lines = [f"*Pedidos pendientes ({len(pedidos)}):*\n"]
    for p in pedidos:
        lines.append(
            f"🔸 *#{p['id']}* — {p['nombre_cliente']} — {p['total']:.2f} €\n"
            f"   Ref PayPal: `{p['paypal_ref']}` | {p['created_at'][:16]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_pedido_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: ver detalle de cualquier pedido."""
    if not _es_admin(update):
        # Cliente: ver su propio pedido
        await cmd_ver_pedido_cliente(update, context)
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
    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar pago", callback_data=f"admin_confirmar_{pedido_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_rechazar_{pedido_id}"),
        ],
        [InlineKeyboardButton("🚚 Marcar enviado", callback_data=f"admin_enviado_{pedido_id}")],
    ]) if pedido["estado"] in ("pendiente_pago", "en_proceso") else None

    await update.message.reply_text(
        formato_pedido_completo(pedido, items)
        + f"\n\n👤 TG: @{pedido['username_tg'] or '—'} (ID: `{pedido['usuario_tg']}`)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=teclado,
    )


async def cmd_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos.")
        return
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
    await update.message.reply_text(f"✅ Pedido #{pedido_id} confirmado.", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=f"✅ *¡Pago confirmado!*\n\nTu pedido *#{pedido_id}* está en proceso. ¡Gracias! 🎉",
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError:
        pass


async def cmd_enviado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos.")
        return
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
    await update.message.reply_text(
        f"🚚 Pedido #{pedido_id} marcado como enviado."
        + (f"\nTracking: `{tracking}`" if tracking else ""),
        parse_mode=ParseMode.MARKDOWN,
    )
    tracking_msg = f"\n📍 Seguimiento: `{tracking}`" if tracking else ""
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=f"🚚 *¡Tu pedido #{pedido_id} ha sido enviado!*{tracking_msg}\n\n¡Gracias por tu compra! 🎉",
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError:
        pass


async def cmd_cancelar_pedido_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _es_admin(update):
        await update.message.reply_text("⛔ No tienes permisos.")
        return
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
    await update.message.reply_text(f"❌ Pedido #{pedido_id} cancelado.", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(
            chat_id=pedido["usuario_tg"],
            text=f"❌ *Tu pedido #{pedido_id} ha sido cancelado.*\n\n{motivo}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramError:
        pass


# ── Ayuda ─────────────────────────────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Menú de la tienda:*\n\n"
        "🛒 *Nuevo pedido* — Iniciar un pedido\n"
        "🛍 *Mi carrito* — Ver tu carrito actual\n"
        "📦 *Mis pedidos* — Ver historial de pedidos\n\n"
        "*Comandos:*\n"
        "/pedido {nº} — Ver detalle de un pedido\n"
        "/cancelar — Cancelar el pedido en curso\n\n"
        "_Para pedir, pulsa 🛒 Nuevo pedido o visita el catálogo._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MENU_KEYBOARD,
    )


async def mensaje_inesperado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Sigue las instrucciones o usa /cancelar para empezar de nuevo."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    db.seed_demo_if_empty()

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.Regex("^🛒 Nuevo pedido$"), menu_nuevo_pedido),
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
            MessageHandler(filters.Regex("^(📦 Mis pedidos|🛍 Mi carrito|❓ Ayuda)$"), mensaje_inesperado),
            MessageHandler(filters.COMMAND, mensaje_inesperado),
            MessageHandler(filters.TEXT, mensaje_inesperado),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    # Menú fuera de conversación
    app.add_handler(MessageHandler(filters.Regex("^📦 Mis pedidos$"), menu_mis_pedidos))
    app.add_handler(MessageHandler(filters.Regex("^🛍 Mi carrito$"), menu_mi_carrito))
    app.add_handler(MessageHandler(filters.Regex("^❓ Ayuda$"), cmd_ayuda))

    # Comandos
    app.add_handler(CommandHandler("mispedidos", menu_mis_pedidos))
    app.add_handler(CommandHandler("pedido", cmd_pedido_admin))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))

    # Admin
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("confirmar", cmd_confirmar))
    app.add_handler(CommandHandler("enviado", cmd_enviado))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar_pedido_admin))

    # Callbacks de botones inline del admin
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_(confirmar|rechazar|enviado)_"))

    logger.info("Bot iniciado.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
