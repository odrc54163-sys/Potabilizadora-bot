import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

user_data_store = {}

SALUDO_INICIAL = (
    "💧 **¡Hola! Bienvenido al sistema de pedidos de Potabilizadora Gual España!** 💧\n\n"
    "👤 Por favor, escribe tu **nombre y apellido** para iniciar tu pedido:"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id] = {"paso": "nombre"}
    await update.message.reply_text(SALUDO_INICIAL, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data_store or "paso" not in user_data_store[user_id]:
        user_data_store[user_id] = {"paso": "nombre"}
        await update.message.reply_text(SALUDO_INICIAL, parse_mode="Markdown")
        return

    paso_actual = user_data_store[user_id].get("paso")

    if paso_actual == "nombre":
        user_data_store[user_id]["nombre"] = text
        user_data_store[user_id]["paso"] = "telefono"
        await update.message.reply_text("📞 Por favor, escribe tu **número de teléfono** de contacto:", parse_mode="Markdown")
        return

    if paso_actual == "telefono":
        user_data_store[user_id]["telefono"] = text
        user_data_store[user_id]["paso"] = "ubicacion"
        await update.message.reply_text("📍 Escribe tu **dirección de entrega o ubicación exacta**:", parse_mode="Markdown")
        return

    if paso_actual == "ubicacion":
        user_data_store[user_id]["ubicacion"] = text
        user_data_store[user_id]["paso"] = "recargas"
        await update.message.reply_text("🔄 **¿Cuántas RECARGAS de botellón deseas solicitar?**\n(Si no necesitas recargas, escribe `0`)", parse_mode="Markdown")
        return

    if paso_actual == "recargas":
        user_data_store[user_id]["recargas"] = text
        user_data_store[user_id]["paso"] = "botellones_nuevos"
        await update.message.reply_text("🧴 **¿Cuántos BOTELLONES NUEVOS (con envase) deseas solicitar?**\n(Si no necesitas botellones nuevos, escribe `0`)", parse_mode="Markdown")
        return

    if paso_actual == "botellones_nuevos":
        user_data_store[user_id]["botellones_nuevos"] = text
        user_data_store[user_id]["paso"] = "monto"
        await update.message.reply_text("💵 Escribe el **monto total transferido/pagado** (ejemplo: `15.00` o `500 BS`):", parse_mode="Markdown")
        return

    if paso_actual == "monto":
        user_data_store[user_id]["monto"] = text
        user_data_store[user_id]["paso"] = "comprobante"
        await update.message.reply_text("💳 **¡Excelente!** Por último, envía la **foto o captura del comprobante de pago** para procesar tu pedido. 📸", parse_mode="Markdown")
        return

    if paso_actual == "comprobante":
        await update.message.reply_text("📸 Por favor, adjunta la **foto o capture** de la transferencia para completar tu pedido.", parse_mode="Markdown")
        return

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data_store.get(user_id, {})

    if data.get("paso") != "comprobante":
        user_data_store[user_id] = {"paso": "nombre"}
        await update.message.reply_text("⚠️ Para procesar tu pedido adecuadamente, primero necesitamos tus datos.\n\n" + SALUDO_INICIAL, parse_mode="Markdown")
        return

    nombre = data.get("nombre", "No especificado")
    telefono = data.get("telefono", "No especificado")
    ubicacion = data.get("ubicacion", "No especificada")
    recargas = data.get("recargas", "0")
    botellones_nuevos = data.get("botellones_nuevos", "0")
    monto = data.get("monto", "No especificado")
    
    username = update.effective_user.username
    alias_telegram = f"@{username}" if username else "Sin alias"

    caption = (
        f"🚨 **NUEVO PEDIDO RECIBIDO** 🚨\n\n"
        f"👤 **Cliente:** {nombre}\n"
        f"💬 **Alias Telegram:** {alias_telegram}\n"
        f"📞 **Teléfono:** {telefono}\n"
        f"📍 **Ubicación:** {ubicacion}\n\n"
        f"🛒 **DETALLE DEL PEDIDO:**\n"
        f"🔄 **Recargas:** {recargas}\n"
        f"🧴 **Botellones Nuevos:** {botellones_nuevos}\n"
        f"💵 **Monto Pagado:** {monto}\n\n"
        f"📌 **Estado:** ⏳ *Pendiente por revisar*"
    )

    keyboard = [
        [
            InlineKeyboardButton("🚚 En camino", callback_data=f"encamino_{user_id}"),
            InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{user_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    photo_file_id = update.message.photo[-1].file_id
    await context.bot.send_photo(
        chat_id=GRUPO_ID,
        photo=photo_file_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    await update.message.reply_text(
        "🎉 **¡Comprobante recibido con éxito!**\n\n"
        "✨ Tu pedido ha sido enviado al equipo de despacho. Te notificaremos por aquí cuando vaya en camino. 🛵💨",
        parse_mode="Markdown"
    )

    user_data_store.pop(user_id, None)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, target_user_id = query.data.split("_")
    original_caption = query.message.caption or ""

    if action == "encamino":
        updated_caption = original_caption.replace(
            "📌 **Estado:** ⏳ *Pendiente por revisar*",
            "📌 **Estado:** 🚚 *¡Pedido en camino!*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{target_user_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_caption(
            caption=updated_caption,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        try:
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text="🛵💨 **¡Buenas noticias!** Tu pedido de la Potabilizadora Gual España va **en camino** a tu ubicación.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"No se pudo notificar al usuario {target_user_id}: {e}")

    elif action == "entregado":
        updated_caption = original_caption.replace(
            "📌 **Estado:** ⏳ *Pendiente por revisar*",
            "📌 **Estado:** ✅ *¡Pedido Entregado!*"
        ).replace(
            "📌 **Estado:** 🚚 *¡Pedido en camino!*",
            "📌 **Estado:** ✅ *¡Pedido Entregado!*"
        )

        await query.edit_message_caption(
            caption=updated_caption,
            parse_mode="Markdown",
            reply_markup=None
        )

        try:
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text="🎉 **¡Tu pedido ha sido entregado con éxito!**\n\nGracias por confiar en Potabilizadora Gual España. ¡Que disfrutes de tu agua purificada! 💧✨",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"No se pudo notificar al usuario {target_user_id}: {e}")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("Iniciando el bot de pedidos de Potabilizadora Gual España...")
    application.run_polling()

if __name__ == "__main__":
    main()
