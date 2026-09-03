import logging
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TOKEN = "8925935497:AAGyMsnC_ryQV4SKv1KEHq8W2U6A9ketPws"
GRUPO_ID = -1004303277305
TELEFONO_ADMIN = "+58 412-XXXXXXXX"  # <--- Cambia esto por el número de contacto de la administración si deseas

# Zona horaria local (ej. Caracas, Venezuela)
LOCAL_TZ = pytz.timezone('America/Caracas')

user_data_store = {}
# Almacén de estadísticas del día
estadisticas_dia = {
    "dinero_total": 0.0,
    "viajes_realizados": 0,
    "historial_viajes": []  # Guardará los registros de cada pedido completado con su hora
}

PRECIO_RECARGA = 800.0  # Ajusta aquí el precio de la recarga
PRECIO_BOTELLON_NUEVO = 2500.0  # Ajusta aquí el precio del botellón nuevo con envase

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id] = {"paso": "eleccion"}
    
    keyboard = [
        [InlineKeyboardButton("🔄 Recarga de agua", callback_data="op_recarga")],
        [InlineKeyboardButton("🧴 Botellón nuevo (con envase)", callback_data="op_nuevo")],
        [InlineKeyboardButton("📦 Ambos (Recarga + Envase nuevo)", callback_data="op_ambos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💧 **¡Bienvenido a Potabilizadora Gual España!** 💧\n\n"
        "Por favor, selecciona qué deseas solicitar:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_callback_eleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {}

    data_tipo = query.data
    if data_tipo == "op_recarga":
        user_data_store[user_id]["tipo_pedido"] = "Recarga"
    elif data_tipo == "op_nuevo":
        user_data_store[user_id]["tipo_pedido"] = "Botellón Nuevo"
    elif data_tipo == "op_ambos":
        user_data_store[user_id]["tipo_pedido"] = "Recarga y Botellón Nuevo"

    user_data_store[user_id]["paso"] = "cantidad"
    await query.edit_message_text(
        f"Has seleccionado: *{user_data_store[user_id]['tipo_pedido']}*.\n\n"
        "🔢 ¿Cuántas unidades deseas solicitar?",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data_store or "paso" not in user_data_store[user_id]:
        await start(update, context)
        return

    paso = user_data_store[user_id].get("paso")

    if paso == "cantidad":
        try:
            cantidad = int(text)
            if cantidad <= 0:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("⚠️ Por favor, introduce un número válido mayor a 0:")
            return

        user_data_store[user_id]["cantidad"] = cantidad
        tipo = user_data_store[user_id]["tipo_pedido"]
        
        # Calcular monto automático
        if tipo == "Recarga":
            monto = cantidad * PRECIO_RECARGA
        elif tipo == "Botellón Nuevo":
            monto = cantidad * PRECIO_BOTELLON_NUEVO
        else: # Ambos (asumimos 1 y 1 o calculo base)
            monto = cantidad * (PRECIO_RECARGA + PRECIO_BOTELLON_NUEVO)
            
        user_data_store[user_id]["monto_calculado"] = monto
        user_data_store[user_id]["paso"] = "nombre"

        await update.message.reply_text(
            f"💰 El monto total a pagar es: *{monto:,.2f} BS*.\n\n"
            "👤 Ahora escribe tu **nombre y apellido**:",
            parse_mode="Markdown"
        )
        return

    if paso == "nombre":
        user_data_store[user_id]["nombre"] = text
        user_data_store[user_id]["paso"] = "telefono"
        await update.message.reply_text("📞 Por favor, escribe tu **número de teléfono** de contacto:", parse_mode="Markdown")
        return

    if paso == "telefono":
        user_data_store[user_id]["telefono"] = text
        user_data_store[user_id]["paso"] = "ubicacion"
        
        # Botón para compartir ubicación GPS real
        location_keyboard = [[KeyboardButton("📍 Compartir ubicación GPS exacta", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, one_time_keyboard=True, resize_keyboard=True)

        await update.message.reply_text(
            "📍 Para que el motorizado llegue sin problemas, por favor presiona el botón de abajo para **compartir tu ubicación GPS exacta**:",
            reply_markup=reply_markup
        )
        return

    if paso == "comprobante":
        await update.message.reply_text("📸 Por favor, adjunta la **foto o captura del pago móvil** para completar tu pedido.", parse_mode="Markdown")
        return

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store or user_data_store[user_id].get("paso") != "ubicacion":
        return

    location = update.message.location
    user_data_store[user_id]["lat"] = location.latitude
    user_data_store[user_id]["lon"] = location.longitude
    user_data_store[user_id]["paso"] = "comprobante"

    monto = user_data_store[user_id]["monto_calculado"]

    await update.message.reply_text(
        f"✅ ¡Ubicación recibida con éxito!\n\n"
        f"💳 **Datos para el pago:**\n"
        f"Monto a transferir: *{monto:,.2f} BS*\n"
        f"(Realiza tu pago móvil y envía la foto del comprobante por aquí) 📸",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove() # Quita el botón de ubicación del chat
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data_store.get(user_id, {})

    if data.get("paso") != "comprobante":
        await update.message.reply_text("⚠️ Por favor completa los pasos anteriores antes de enviar el comprobante.")
        return

    nombre = data.get("nombre")
    telefono = data.get("telefono")
    tipo = data.get("tipo_pedido")
    cantidad = data.get("cantidad")
    monto = data.get("monto_calculado")
    lat = data.get("lat")
    lon = data.get("lon")

    username = update.effective_user.username
    alias_telegram = f"@{username}" if username else "Sin alias de Telegram"

    caption = (
        f"🚨 **NUEVO PEDIDO DE AGUA** 🚨\n\n"
        f"👤 **Cliente:** {nombre}\n"
        f"💬 **Alias:** {alias_telegram}\n"
        f"📞 **Teléfono:** {telefono}\n"
        f"📦 **Pedido:** {cantidad}x {tipo}\n"
        f"💵 **Monto:** {monto:,.2f} BS\n\n"
        f"📌 **Estado:** ⏳ *Pendiente por verificar pago*"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Pago Válido (En camino)", callback_data=f"encamino_{user_id}_{monto}"),
            InlineKeyboardButton("❌ Pago Falso", callback_data=f"pagofalso_{user_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    photo_file_id = update.message.photo[-1].file_id

    # Enviar foto al grupo
    await context.bot.send_photo(
        chat_id=GRUPO_ID,
        photo=photo_file_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    # Enviar ubicación GPS al grupo si está disponible
    if lat and lon:
        await context.bot.send_location(
            chat_id=GRUPO_ID,
            latitude=lat,
            longitude=lon
        )

    await update.message.reply_text(
        "🎉 **¡Comprobante enviado con éxito!**\n\n"
        "✨ Estamos verificando tu pago. En breve te notificaremos el estado de tu despacho. 🛵💨",
        parse_mode="Markdown"
    )

    user_data_store.pop(user_id, None)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    partes = query.data.split("_")
    action = partes[0]
    target_user_id = int(partes[1])
    original_caption = query.message.caption or ""

    if action == "encamino":
        monto_pedido = float(partes[2])
        
        updated_caption = original_caption.replace(
            "📌 **Estado:** ⏳ *Pendiente por verificar pago*",
            "📌 **Estado:** 🚚 *¡Pago verificado! Pedido en camino*"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{target_user_id}_{monto_pedido}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_caption(caption=updated_caption, parse_mode="Markdown", reply_markup=reply_markup)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🛵💨 **¡Pago verificado con éxito!** Tu pedido de la Potabilizadora Gual España va en camino.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"No se pudo notificar al usuario: {e}")

    elif action == "pagofalso":
        updated_caption = original_caption.replace(
            "📌 **Estado:** ⏳ *Pendiente por verificar pago*",
            "📌 **Estado:** ❌ *Rechazado - Pago Falso/Inválido*"
        )

        await query.edit_message_caption(caption=updated_caption, parse_mode="Markdown", reply_markup=None)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"⚠️ **Atención:** Su comprobante no pudo ser verificado o el pago no se reflejó.\n\n"
                     f"Por favor, comuníquese directamente con la administración al número: *{TELEFONO_ADMIN}* para solventar su pedido.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"No se pudo notificar al usuario de pago falso: {e}")

    elif action == "entregado":
        monto_pedido = float(partes[2])
        hora_actual_str = datetime.now(LOCAL_TZ).strftime('%H:%M:%S')

        # Registrar estadísticas del día
        estadisticas_dia["dinero_total"] += monto_pedido
        estadisticas_dia["viajes_realizados"] += 1
        estadisticas_dia["historial_viajes"].append(f"• Pedido entregado a las {hora_actual_str} ({monto_pedido:,.2f} BS)")

        updated_caption = original_caption.replace(
            "📌 **Estado:** 🚚 *¡Pago verificado! Pedido en camino*",
            "📌 **Estado:** ✅ *¡Pedido Entregado con Éxito!*"
        )

        await query.edit_message_caption(caption=updated_caption, parse_mode="Markdown", reply_markup=None)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 **¡Tu pedido ha sido entregado con éxito!**\n\nGracias por confiar en Potabilizadora Gual España. 💧✨",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"No se pudo notificar la entrega: {e}")

async def cmd_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dinero = estadisticas_dia["dinero_total"]
    viajes = estadisticas_dia["viajes_realizados"]
    historial = "\n".join(estadisticas_dia["historial_viajes"]) if estadisticas_dia["historial_viajes"] else "No hay viajes registrados aún hoy."

    texto_stats = (
        f"📊 **ESTADÍSTICAS DEL DÍA** 📊\n\n"
        f"💵 **Dinero total reunido:** {dinero:,.2f} BS\n"
        f"🛵 **Total de viajes realizados:** {viajes}\n\n"
        f"⏰ **Detalle de horarios de viajes:**\n{historial}"
    )
    await update.message.reply_text(texto_stats, parse_mode="Markdown")

async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estadisticas_dia["dinero_total"] = 0.0
    estadisticas_dia["viajes_realizados"] = 0
    estadisticas_dia["historial_viajes"] = []

    await update.message.reply_text("🔄 **Estadísticas reiniciadas con éxito.** Todo listo para el nuevo día.", parse_mode="Markdown")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("estadisticas", cmd_estadisticas))
    application.add_handler(CommandHandler("reiniciar", cmd_reiniciar))
    application.add_handler(CallbackQueryHandler(handle_callback_eleccion, pattern="^op_"))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Iniciando el bot completo de Potabilizadora Gual España...")
    application.run_polling()

if __name__ == "__main__":
    main()
