import logging
from datetime import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Configuración de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# CONFIGURACIÓN DEL NEGOCIO (EDITA AQUÍ)
# ==========================================
TOKEN = "8925935497:AAGw8QL04CJAL02A7WXprALSKHnn9zqDRXs"
ID_GRUPO_TRABAJO = -1004303277305  # Pon aquí el ID de tu grupo (con el signo -)

# PRECIOS EN BOLÍVARES
PRECIO_RECARGA = 800
PRECIO_BOTELLON_NUEVO = 5000

# DATOS DE PAGO MÓVIL
BANCO = "Banco Venezuela"
CEDULA = "18912986"
TELEFONO = "0412-3953015"

# Zona horaria de Venezuela
ZONA_HORARIA = pytz.timezone('America/Caracas')

# Estados de la conversación
SELECCIONAR_PRODUCTO, NOMBRE, UBICACION, COMPROBANTE = range(4)


def esta_en_horario() -> bool:
    """Verifica si la consulta está dentro del horario (Lunes a Sábado: 8:00 AM - 5:30 PM)"""
    ahora = datetime.now(ZONA_HORARIA)
    dia_semana = ahora.weekday()  # 0: Lunes, 5: Sábado, 6: Domingo
    hora_actual = ahora.time()
    
    # 0 a 5 es Lunes a Sábado
    if 0 <= dia_semana <= 5:
        hora_inicio = datetime.strptime("08:00", "%H:%M").time()
        hora_fin = datetime.strptime("17:30", "%H:%M").time()
        return hora_inicio <= hora_actual <= hora_fin
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicio del bot y menú de productos"""
    # Verificar horario comercial
    if not esta_en_horario():
        mensaje_cerrado = (
            "🔴 *POTABILIZADORA CERRADA*\n\n"
            "¡Hola! En este momento no nos encontramos laborando.\n\n"
            "🕒 *Horario de atención:*\n"
            "Lunes a Sábado: 8:00 AM - 5:30 PM\n\n"
            "Por favor, escríbenos dentro de nuestro horario de trabajo para tomar tu pedido. ¡Gracias por preferirnos! 💧"
        )
        await update.message.reply_text(mensaje_cerrado, parse_mode='Markdown')
        return ConversationHandler.END

    # Menú de selección
    keyboard = [
        [
            InlineKeyboardButton(f"💧 Recarga ({PRECIO_RECARGA} Bs)", callback_data="prod_recarga"),
            InlineKeyboardButton(f"🛢️ Botellón Nuevo ({PRECIO_BOTELLON_NUEVO} Bs)", callback_data="prod_botellon")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 ¡Bienvenido al Servicio de Entrega de Agua Potable!\n\n"
        "Por favor, selecciona el producto que deseas solicitar:",
        reply_markup=reply_markup
    )
    return SELECCIONAR_PRODUCTO


async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "prod_recarga":
        context.user_data['producto'] = "Recarga de Botellón"
        context.user_data['precio'] = PRECIO_RECARGA
    else:
        context.user_data['producto'] = "Botellón Nuevo + Agua"
        context.user_data['precio'] = PRECIO_BOTELLON_NUEVO

    await query.edit_message_text(
        f"✅ Seleccionaste: *{context.user_data['producto']}* ({context.user_data['precio']} Bs)\n\n"
        "✍️ Por favor, escribe tu *Nombre y Apellido* para el registro de la entrega:",
        parse_mode='Markdown'
    )
    return NOMBRE


async def pedir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre_cliente = update.message.text
    context.user_data['nombre'] = nombre_cliente

    # Crear botón para compartir ubicación GPS fácilmente
    boton_ubicacion = KeyboardButton(text="📍 Enviar mi Ubicación GPS", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[boton_ubicacion]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        f"Excelente {nombre_cliente}.\n\n"
        "📍 Toca el botón de abajo para compartir tu ubicación GPS exacta para el motorizado:",
        reply_markup=reply_markup
    )
    return UBICACION


async def pedir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Guardar objeto de ubicación GPS
    context.user_data['ubicacion'] = update.message.location

    mensaje_pago = (
        "💳 *DATOS PARA PAGO MÓVIL*\n\n"
        f"📌 *Banco:* {BANCO}\n"
        f"📌 *Cédula / RIF:* {CEDULA}\n"
        f"📌 *Teléfono:* {TELEFONO}\n"
        f"💰 *Monto a Pagar:* {context.user_data['precio']} Bs\n\n"
        "📸 Una vez realizado el pago, envía la *foto o capture del comprobante* por este chat."
    )
    
    await update.message.reply_text(
        mensaje_pago,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True) # Ocultar teclado de ubicación
    )
    return COMPROBANTE


async def recibir_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    foto_id = update.message.photo[-1].file_id

    # Ficha del pedido para el grupo de trabajo
    ficha_pedido = (
        "🚨 *¡NUEVO PEDIDO DE AGUA!* 🚨\n\n"
        f"👤 *Cliente:* {context.user_data['nombre']}\n"
        f"📲 *Telegram User:* @{user.username if user.username else 'Sin alias'}\n"
        f"📦 *Producto:* {context.user_data['producto']}\n"
        f"💵 *Monto:* {context.user_data['precio']} Bs\n\n"
        "📌 *Adjunto comprobante de pago y ubicación GPS para la entrega.*"
    )

    try:
        # 1. Enviar comprobante de pago al grupo
        await context.bot.send_photo(
            chat_id=ID_GRUPO_TRABAJO,
            photo=foto_id,
            caption=ficha_pedido,
            parse_mode='Markdown'
        )

        # 2. Enviar la ubicación GPS al grupo
        loc = context.user_data['ubicacion']
        await context.bot.send_location(
            chat_id=ID_GRUPO_TRABAJO,
            latitude=loc.latitude,
            longitude=loc.longitude
        )

        # Confirmación al cliente
        await update.message.reply_text(
            "✅ *¡Pedido registrado con éxito!*\n\n"
            "Hemos recibido tu comprobante y tu ubicación. El equipo de administración procesará tu entrega a la brevedad.\n\n"
            "¡Gracias por tu compra! 💧",
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Error al enviar al grupo: {e}")
        await update.message.reply_text(
            "⚠️ Hubo un detalle al notificar al equipo, pero tu registro fue guardado. Nos comunicaremos contigo a la brevedad."
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Pedido cancelado. Escribe /start cuando desees realizar un nuevo pedido.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECCIONAR_PRODUCTO: [CallbackQueryHandler(seleccionar_producto)],
            NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedir_nombre)],
            UBICACION: [MessageHandler(filters.LOCATION, pedir_ubicacion)],
            COMPROBANTE: [MessageHandler(filters.PHOTO, recibir_comprobante)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)

    print("Bot de la Potabilizadora ejecutándose correctamente...")
    app.run_polling()


if __name__ == '__main__':
    main()
