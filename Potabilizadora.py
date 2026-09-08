import logging
from datetime import datetime
import os
import pytz
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
    ContextTypes,
    filters,
)

# Configuración de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# CONFIGURACIÓN DE CREDENCIALES
TOKEN = "8925935497:AAGKVr_kAF4VCyZUAVlWwMNfqVcBRnJ7"
GRUPO_ID = -1004303277305
TELEFONO_ADMIN = "+58 412-9511145"

# Almacenamiento temporal de datos de los usuarios en memoria
user_data_store = {}


def verificar_horario():
    """Verifica si la potabilizadora está en horario laboral (Lunes a Sábado de 8:00 AM a 5:30 PM, Hora de Venezuela)."""
    tz = pytz.timezone("America/Caracas")
    ahora = datetime.now(tz)
    dia_semana = ahora.weekday()  # Lunes = 0, Domingo = 6
    hora_actual = ahora.time()

    # Si es domingo (6), está cerrado
    if dia_semana == 6:
        return False

    # Lunes a Sábado de 8:00 AM a 5:30 PM (17:30)
    hora_inicio = datetime.strptime("08:00", "%H%M" if False else "%H:%M").time()
    hora_fin = datetime.strptime("17:30", "%H:%M").time()

    return hora_inicio <= hora_actual <= hora_fin


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start para iniciar el bot y verificar horarios."""
    if not verificar_horario():
        mensaje_cerrado = (
            "🚨 *¡POTABILIZADORA CERRADA!* 🚨\n\n"
            "🕒 *Horarios de atención:*\n"
            "📅 Lunes a Sábado: 8:00 AM - 5:30 PM\n"
            "📅 Domingos: Cerrado todo el día\n\n"
            "💬 *Motivo:* Fuera de horario de atención.\n\n"
            "✨ Te esperamos en nuestro horario habitual para atender tu pedido con gusto. 💧🏃‍♂️"
        )
        await update.message.reply_text(mensaje_cerrado, parse_mode="Markdown")
        return

    user = update.effective_user
    user_id = user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {}

    teclado = [
        [
            InlineKeyboardButton(
                "💧 Recarga de Botellón", callback_data="op_recarga"
            )
        ],
        [
            InlineKeyboardButton(
                "🧊 Botellón Nuevo (Con Envase)", callback_data="op_nuevo"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    bienvenida = (
        f"¡Hola *{user.first_name}*! 👋\n\n"
        "Bienvenido al sistema de pedidos de la *Potabilizadora Gual España* 💧.\n\n"
        "Por favor, selecciona el tipo de servicio que necesitas:"
    )
    await update.message.reply_text(
        bienvenida, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def callback_eleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del tipo de producto."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {}

    data_tipo = query.data

    if data_tipo == "op_recarga":
        user_data_store[user_id]["tipo_pedido"] = "Recarga de Botellón"
    elif data_tipo == "op_nuevo":
        user_data_store[user_id]["tipo_pedido"] = (
            "Botellón Nuevo (Con Envase)"
        )

    user_data_store[user_id]["paso"] = "cantidad"
    await query.edit_message_text(
        text=(
            f"📦 Has seleccionado: *{user_data_store[user_id]['tipo_pedido']}*.\n\n"
            "🔢 ¿Cuántas unidades deseas solicitar?\n\n"
            "*(Recuerda que puedes escribir /cancelar si deseas anular)*"
        ),
        parse_mode="Markdown",
    )


async def manejar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los textos ingresados por el usuario (cantidad, dirección, etc.)."""
    user_id = update.effective_user.id
    texto = update.message.text

    if user_id not in user_data_store or "paso" not in user_data_store[user_id]:
        return

    paso = user_data_store[user_id]["paso"]

    if paso == "cantidad":
        user_data_store[user_id]["cantidad"] = texto
        user_data_store[user_id]["paso"] = "direccion"
        await update.message.reply_text(
            "📍 Perfecto. Ahora, por favor envíame tu *dirección de entrega* detallada o comparte tu ubicación:",
            parse_mode="Markdown",
        )

    elif paso == "direccion":
        user_data_store[user_id]["direccion"] = texto
        user_data_store[user_id]["paso"] = "pago"

        teclado_pago = [
            [
                InlineKeyboardButton(
                    "💵 Efectivo (Pago al recibir)", callback_data="pago_efectivo"
                )
            ],
            [
                InlineKeyboardButton(
                    "📱 Pago Móvil", callback_data="pago_movil"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(teclado_pago)
        await update.message.reply_text(
            "💳 ¿Cuál será tu *método de pago*?",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def callback_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el método de pago seleccionado y genera el resumen para el grupo."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data_store:
        return

    data_pago = query.data
    metodo = (
        "Efectivo" if data_pago == "pago_efectivo" else "Pago Móvil"
    )
    user_data_store[user_id]["metodo_pago"] = metodo

    datos = user_data_store[user_id]
    tipo = datos.get("tipo_pedido", "Pedido")
    cantidad = datos.get("cantidad", "1")
    direccion = datos.get("direccion", "Sin dirección")

    # Mensaje detallado que llega al grupo de administración con botón de verificar
    mensaje_grupo = (
        f"🚨 *¡NUEVO PEDIDO RECIBIDO!* 🚨\n\n"
        f"👤 *Cliente:* {query.from_user.full_name}\n"
        f"📦 *Producto:* {tipo}\n"
        f"🔢 *Cantidad:* {cantidad}\n"
        f"📍 *Dirección:* {direccion}\n"
        f"💵 *Método de pago:* {metodo}\n"
        f"📌 *Estado:* 🟡 Pendiente por verificación"
    )

    teclado_admin = [
        [
            InlineKeyboardButton(
                "💳 Pago Verificado",
                callback_data=f"verificado_{user_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🛵 En camino", callback_data=f"encamino_{user_id}"
            ),
            InlineKeyboardButton(
                "✅ Entregado", callback_data=f"entregado_{user_id}"
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(teclado_admin)

    # Enviar al grupo de administración
    await context.bot.send_message(
        chat_id=GRUPO_ID, text=mensaje_grupo, reply_markup=reply_markup, parse_mode="Markdown"
    )

    # Confirmación al cliente en privado
    await query.edit_message_text(
        text=(
            "🎉 *¡Comprobante enviado con éxito!*\n\n"
            "✨ Estamos verificando tu pedido. En breve te notificaremos el estado de tu despacho. 🚚💧"
        ),
        parse_mode="Markdown",
    )

    user_data_store.pop(user_id, None)


async def callback_acciones_admin(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Maneja las acciones del panel de administración (Verificado, En camino, Entregado)."""
    query = update.callback_query
    await query.answer()

    data = query.data
    accion, cliente_id_str = data.split("_")
    cliente_id = int(cliente_id_str)

    if accion == "verificado":
        mensaje_cliente = (
            "✅ *¡Su pago ha sido verificado con éxito!*\n\n"
            "Pronto le enviaremos su pedido (recarga o botellón nuevo, según lo que haya solicitado). ¡Gracias por preferirnos! 💧✨"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛵 En camino",
                            callback_data=f"encamino_{cliente_id}",
                        ),
                        InlineKeyboardButton(
                            "✅ Entregado",
                            callback_data=f"entregado_{cliente_id}",
                        ),
                    ]
                ]
            )
        )

    elif accion == "encamino":
        mensaje_cliente = (
            "🛵 *¡Su pedido va en camino!*\n\n"
            "El motorizado se dirige hacia su ruta. Por favor, manténgase atento a su teléfono por si el repartidor no logra localizarle. 📞💧"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )

    elif accion == "entregado":
        mensaje_cliente = (
            "🎉 *¡Pedido Entregado!*\n\n"
            "Muchísimas gracias por su compra y por confiar en la **Potabilizadora Gual España**. ¡Esperamos verle pronto! 💧🚰"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )
        await query.edit_message_text(
            text=query.message.text + "\n\n✅ *PEDIDO COMPLETADO*",
            parse_mode="Markdown",
        )


def main():
    """Función principal para ejecutar el bot."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(
            callback_eleccion, pattern="^op_.*"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            callback_pago, pattern="^pago_.*"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            callback_acciones_admin,
            pattern="^(verificado|encamino|entregado)_.*",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_texto)
    )

    print("Bot de la Potabilizadora Gual España iniciado correctamente...")
    application.run_polling()


if __name__ == "__main__":
    main()
