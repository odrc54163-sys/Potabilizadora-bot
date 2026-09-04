import logging
from datetime import datetime, time
import os
import threading
from flask import Flask
import pytz
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = "8925935497:AAGyMsnC_ryQV4SKv1KEHq8W2U6A9ketPws"
GRUPO_ID = -1004303277305
TELEFONO_ADMIN = "+58 412-9511145"

# ==========================================
# DATOS DE PAGO MÓVIL CONFIGURADOS
# ==========================================
BANCO_PAGO = "Banco de Venezuela"
TELEFONO_PAGO = "0412-3953015"
CEDULA_RIF_PAGO = "18.912.986"

# Zona horaria local (Venezuela)
LOCAL_TZ = pytz.timezone("America/Caracas")

user_data_store = {}
estadisticas_dia = {
    "dinero_total": 0.0,
    "viajes_realizados": 0,
    "historial_viajes": [],
}

PRECIO_RECARGA = 800.0
PRECIO_BOTELLON_NUEVO = 5000.0

# ==========================================
# SERVIDOR WEB MINI (FLASK) PARA MANTENERSE DESPIERTO EN RENDER
# ==========================================
app = Flask(__name__)


@app.route("/")
def home():
  return "¡El bot de la Potabilizadora Gual España está activo 24/7!"


def run_web():
  # Render asigna un puerto automáticamente a través de variables de entorno
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def verificar_horario():
  """Verifica si la potabilizadora está abierta según el día y la hora."""
  ahora = datetime.now(LOCAL_TZ)
  dia_semana = ahora.weekday()  # Lunes = 0, Domingo = 6
  hora_actual = ahora.time()

  # Si es domingo (6), está cerrado todo el día
  if dia_semana == 6:
    return False, "Domingos: Cerrado todo el día"

  # Lunes a Sábado (0 a 5) de 8:00 AM a 5:30 PM (17:30)
  hora_apertura = time(8, 0)
  hora_cierre = time(17, 30)

  if hora_apertura <= hora_actual <= hora_cierre:
    return True, "Abierto"
  else:
    return (
        False,
        (
            "Fuera de horario (Laboramos de Lunes a Sábado de 8:00 AM a 5:30"
            " PM)"
        ),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  abierto, motivo = verificar_horario()
  if not abierto:
    await update.message.reply_text(
        f"🚫 **¡Lo sentimos, potabilizadora Cerrada en este momento!** 🚫\n\n"
        f"⏱️ **Horario de atención:**\n"
        f"• Lunes a Sábado: 8:00 AM - 5:30 PM\n"
        f"• Domingos: Cerrado todo el día\n\n"
        f"💬 **Motivo:** {motivo}.\n\n"
        f"✨ Te esperamos en nuestro horario habitual de trabajo para atender"
        f" tu pedido con gusto. 💧🚶‍♂️",
        parse_mode="Markdown",
    )
    return

  user_id = update.effective_user.id
  user_data_store[user_id] = {"paso": "eleccion"}

  keyboard = [
      [
          InlineKeyboardButton(
              "🔄 Recarga (800 BS)", callback_data="op_recarga"
          )
      ],
      [
          InlineKeyboardButton(
              "🧴 Botellón Nuevo (5.000 BS)", callback_data="op_nuevo"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  await update.message.reply_text(
      "💧 **¡Bienvenido a Potabilizadora Gual España!** 💧\n\n"
      "Por favor, selecciona qué deseas solicitar:\n\n"
      "💡 *Escribe* `/cancelar` *en cualquier momento si deseas anular tu"
      " solicitud.*",
      parse_mode="Markdown",
      reply_markup=reply_markup,
  )


async def cancelar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id in user_data_store:
    user_data_store.pop(user_id, None)

  await update.message.reply_text(
      "❌ **Pedido cancelado con éxito.**\n\n"
      "Si deseas iniciar uno nuevo más tarde, escribe /start. ¡Feliz día! 💧",
      parse_mode="Markdown",
      reply_markup=ReplyKeyboardRemove(),
  )


async def handle_callback_eleccion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  abierto, _ = verificar_horario()
  if not abierto:
    await update.callback_query.answer(
        "⚠️ Horario de atención finalizado", show_alert=True
    )
    await update.callback_query.edit_message_text(
        "🚫 **El horario de atención ha finalizado.** Ya no se pueden procesar"
        " solicitudes por hoy.",
        parse_mode="Markdown",
    )
    return

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

  user_data_store[user_id]["paso"] = "cantidad"
  await query.edit_message_text(
      f"Has seleccionado: *{user_data_store[user_id]['tipo_pedido']}*.\n\n"
      "🔢 ¿Cuántas unidades deseas solicitar?\n"
      "*(Recuerda que puedes escribir /cancelar si deseas anular)*",
      parse_mode="Markdown",
  )


async def handle_callback_pago(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()
  user_id = query.from_user.id

  if user_id not in user_data_store:
    return

  data_pago = query.data
  if data_pago == "pay_movil":
    user_data_store[user_id]["metodo_pago"] = "Pago Móvil"
  elif data_pago == "pay_efectivo":
    user_data_store[user_id]["metodo_pago"] = "Efectivo"

  user_data_store[user_id]["paso"] = "nombre"
  await query.edit_message_text(
      f"Has seleccionado pagar con:"
      f" *{user_data_store[user_id]['metodo_pago']}*.\n\n"
      "👤 Ahora escribe tu **nombre y apellido**:",
      parse_mode="Markdown",
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
      await update.message.reply_text(
          "⚠️ Por favor, introduce un número válido mayor a 0 (o escribe"
          " /cancelar):"
      )
      return

    user_data_store[user_id]["cantidad"] = cantidad
    tipo = user_data_store[user_id]["tipo_pedido"]

    if tipo == "Recarga":
      monto = cantidad * PRECIO_RECARGA
    else:
      monto = cantidad * PRECIO_BOTELLON_NUEVO

    user_data_store[user_id]["monto_calculado"] = monto
    user_data_store[user_id]["paso"] = "metodo_pago"

    keyboard = [
        [InlineKeyboardButton("💳 Pago Móvil", callback_data="pay_movil")],
        [InlineKeyboardButton("💵 Efectivo", callback_data="pay_efectivo")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💰 El monto total a pagar es: *{monto:,.2f} BS*.\n\n"
        "💳 ¿Con qué deseas pagar?",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )
    return

  if paso == "nombre":
    user_data_store[user_id]["nombre"] = text
    user_data_store[user_id]["paso"] = "telefono"
    await update.message.reply_text(
        "📞 Por favor, escribe tu **número de teléfono** de contacto:",
        parse_mode="Markdown",
    )
    return

  if paso == "telefono":
    user_data_store[user_id]["telefono"] = text
    user_data_store[user_id]["paso"] = "ubicacion"

    location_keyboard = [[
        KeyboardButton(
            "📍 Compartir ubicación GPS exacta", request_location=True
        )
    ]]
    reply_markup = ReplyKeyboardMarkup(
        location_keyboard, one_time_keyboard=True, resize_keyboard=True
    )

    await update.message.reply_text(
        "📍 Para que el motorizado llegue sin problemas, presiona el botón de"
        " abajo para **compartir tu ubicación GPS exacta**:",
        reply_markup=reply_markup,
    )
    return

  if paso == "comprobante":
    await update.message.reply_text(
        "📸 Por favor, adjunta la **foto o captura del pago móvil** para"
        " completar tu pedido.",
        parse_mode="Markdown",
    )
    return


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if (
      user_id not in user_data_store
      or user_data_store[user_id].get("paso") != "ubicacion"
  ):
    return

  location = update.message.location
  user_data_store[user_id]["lat"] = location.latitude
  user_data_store[user_id]["lon"] = location.longitude

  metodo = user_data_store[user_id].get("metodo_pago")
  monto = user_data_store[user_id]["monto_calculado"]
  nombre = user_data_store[user_id]["nombre"]
  telefono = user_data_store[user_id]["telefono"]
  tipo = user_data_store[user_id]["tipo_pedido"]
  cantidad = user_data_store[user_id]["cantidad"]
  lat = location.latitude
  lon = location.longitude

  username = update.effective_user.username
  alias_telegram = f"@{username}" if username else "Sin alias de Telegram"

  if metodo == "Pago Móvil":
    user_data_store[user_id]["paso"] = "comprobante"
    await update.message.reply_text(
        f"✅ ¡Ubicación recibida con éxito!\n\n"
        f"💳 **DATOS PARA EL PAGO MÓVIL:**\n"
        f"🏦 **Banco:** {BANCO_PAGO}\n"
        f"📱 **Teléfono:** {TELEFONO_PAGO}\n"
        f"🆔 **Cédula/RIF:** {CEDULA_RIF_PAGO}\n"
        f"💵 **Monto exacto:** *{monto:,.2f} BS*\n\n"
        f"Realiza tu pago y **envía la foto del comprobante por aquí**. 📸",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
  else:
    caption = (
        f"🚨 **NUEVO PEDIDO DE AGUA** 🚨\n\n"
        f"👤 **Cliente:** {nombre}\n"
        f"💬 **Alias:** {alias_telegram}\n"
        f"📞 **Teléfono:** {telefono}\n"
        f"📦 **Pedido:** {cantidad}x {tipo}\n"
        f"💵 **Total a pagar:** *{monto:,.2f} BS*\n"
        f"💳 **Método de pago:** Efectivo 💵\n\n"
        f"📌 **Estado:** ⏳ *Pendiente por despacho*"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🛵 En camino", callback_data=f"encamino_{user_id}_{monto}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Entregado", callback_data=f"entregado_{user_id}_{monto}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=GRUPO_ID,
        text=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    await context.bot.send_location(
        chat_id=GRUPO_ID, latitude=lat, longitude=lon
    )

    await update.message.reply_text(
        "🎉 **¡Pedido registrado con éxito!**\n\n"
        "✨ Pagarás en efectivo al recibir tu pedido. El motorizado va en"
        " camino o será despachado pronto. 🛵💨",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data_store.pop(user_id, None)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  data = user_data_store.get(user_id, {})

  if data.get("paso") != "comprobante":
    await update.message.reply_text(
        "⚠️ Por favor completa los pasos anteriores antes de enviar el"
        " comprobante."
    )
    return

  nombre = data.get("nombre")
  telefono = data.get("telefono")
  tipo = data.get("tipo_pedido")
  cantidad = data.get("cantidad")
  monto = data.get("monto_calculado")
  metodo = data.get("metodo_pago", "Pago Móvil")
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
      f"💵 **Total a pagar:** *{monto:,.2f} BS*\n"
      f"💳 **Método de pago:** {metodo}\n\n"
      f"📌 **Estado:** ⏳ *Pendiente por verificar pago*"
  )

  keyboard = [
      [
          InlineKeyboardButton(
              "🛵 En camino", callback_data=f"encamino_{user_id}_{monto}"
          )
      ],
      [
          InlineKeyboardButton(
              "✅ Entregado", callback_data=f"entregado_{user_id}_{monto}"
          )
      ],
      [
          InlineKeyboardButton(
              "❌ Pago Falso", callback_data=f"pagofalso_{user_id}"
          )
      ],
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

  if lat and lon:
    await context.bot.send_location(
        chat_id=GRUPO_ID, latitude=lat, longitude=lon
    )

  await update.message.reply_text(
      "🎉 **¡Comprobante enviado con éxito!**\n\n"
      "✨ Estamos verificando tu pago. En breve te notificaremos el estado de"
      " tu despacho. 🛵💨",
      parse_mode="Markdown",
  )

  user_data_store.pop(user_id, None)


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  partes = query.data.split("_")
  action = partes[0]
  target_user_id = int(partes[1])
  original_caption = query.message.caption or query.message.text or ""

  if action == "encamino":
    monto_pedido = float(partes[2])

    updated_caption = original_caption.replace(
        "📌 **Estado:** ⏳ *Pendiente por verificar pago*",
        "📌 **Estado:** 🚚 *¡Pedido en camino!*",
    ).replace(
        "📌 **Estado:** ⏳ *Pendiente por despacho*",
        "📌 **Estado:** 🚚 *¡Pedido en camino!*",
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Entregado",
                callback_data=f"entregado_{target_user_id}_{monto_pedido}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Pago Falso", callback_data=f"pagofalso_{target_user_id}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query.message.photo:
      await query.edit_message_caption(
          caption=updated_caption,
          parse_mode="Markdown",
          reply_markup=reply_markup,
      )
    else:
      await query.edit_message_text(
          text=updated_caption, parse_mode="Markdown", reply_markup=reply_markup
      )

    try:
      await context.bot.send_message(
          chat_id=target_user_id,
          text="🛵💨 **¡Tu pedido va en camino!** Prepárate para recibirlo.",
          parse_mode="Markdown",
      )
    except Exception as e:
      logging.error(f"No se pudo notificar al usuario: {e}")

  elif action == "entregado":
    monto_pedido = float(partes[2])
    hora_actual_str = datetime.now(LOCAL_TZ).strftime("%H:%M:%S")

    estadisticas_dia["dinero_total"] += monto_pedido
    estadisticas_dia["viajes_realizados"] += 1
    estadisticas_dia["historial_viajes"].append(
        f"• Pedido entregado a las {hora_actual_str} ({monto_pedido:,.2f} BS)"
    )

    updated_caption = (
        original_caption.replace(
            "📌 **Estado:** ⏳ *Pendiente por verificar pago*",
            "📌 **Estado:** ✅ *¡Pedido Entregado con Éxito!*",
        )
        .replace(
            "📌 **Estado:** ⏳ *Pendiente por despacho*",
            "📌 **Estado:** ✅ *¡Pedido Entregado con Éxito!*",
        )
        .replace(
            "📌 **Estado:** 🚚 *¡Pedido en camino!*",
            "📌 **Estado:** ✅ *¡Pedido Entregado con Éxito!*",
        )
    )

    if query.message.photo:
      await query.edit_message_caption(
          caption=updated_caption, parse_mode="Markdown", reply_markup=None
      )
    else:
      await query.edit_message_text(
          text=updated_caption, parse_mode="Markdown", reply_markup=None
      )

    try:
      await context.bot.send_message(
          chat_id=target_user_id,
          text=(
              "🎉 **¡Tu pedido ha sido entregado con éxito!**\n\nGracias por"
              " confiar en Potabilizadora Gual España. 💧✨"
          ),
          parse_mode="Markdown",
      )
    except Exception as e:
      logging.error(f"No se pudo notificar la entrega: {e}")

  elif action == "pagofalso":
    updated_caption = original_caption.replace(
        "📌 **Estado:** ⏳ *Pendiente por verificar pago*",
        "📌 **Estado:** ❌ *Rechazado - Pago Falso/Inválido*",
    ).replace(
        "📌 **Estado:** 🚚 *¡Pedido en camino!*",
        "📌 **Estado:** ❌ *Rechazado - Pago Falso/Inválido*",
    )

    if query.message.photo:
      await query.edit_message_caption(
          caption=updated_caption, parse_mode="Markdown", reply_markup=None
      )
    else:
      await query.edit_message_text(
          text=updated_caption, parse_mode="Markdown", reply_markup=None
      )

    try:
      await context.bot.send_message(
          chat_id=target_user_id,
          text=(
              "⚠️ **Atención:** Su comprobante no pudo ser verificado o el pago"
              f" no se reflejó.\n\nPor favor, comuníquese directamente con la"
              f" administración al número: *{TELEFONO_ADMIN}* para solventar"
              " su pedido."
          ),
          parse_mode="Markdown",
      )
    except Exception as e:
      logging.error(f"No se pudo notificar al usuario de pago falso: {e}")


async def enviar_reporte_automatico(context: ContextTypes.DEFAULT_TYPE):
  """Función que se ejecuta automáticamente a las 6:30 PM para enviar las estadísticas al grupo."""
  dinero = estadisticas_dia["dinero_total"]
  viajes = estadisticas_dia["viajes_realizados"]
  historial = (
      "\n".join(estadisticas_dia["historial_viajes"])
      if estadisticas_dia["historial_viajes"]
      else "No hay viajes registrados hoy."
  )

  texto_stats = (
      f"📊 **REPORTE AUTOMÁTICO DE CIERRE (6:30 PM)** 📊\n\n"
      f"💵 **Dinero total reunido:** {dinero:,.2f} BS\n"
      f"🛵 **Total de viajes realizados:** {viajes}\n\n"
      f"⏰ **Detalle de horarios de viajes:**\n{historial}"
  )
  try:
    await context.bot.send_message(
        chat_id=GRUPO_ID, text=texto_stats, parse_mode="Markdown"
    )
  except Exception as e:
    logging.error(f"No se pudo enviar el reporte automático: {e}")


async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
  estadisticas_dia["dinero_total"] = 0.0
  estadisticas_dia["viajes_realizados"] = 0
  estadisticas_dia["historial_viajes"] = []

  await update.message.reply_text(
      "🔄 **Estadísticas reiniciadas con éxito.** Todo listo para el nuevo día.",
      parse_mode="Markdown",
  )


def main():
  # ==========================================
  # INICIAR EL SERVIDOR WEB FLASK EN UN HILO APARTADO
  # ==========================================
  t = threading.Thread(target=run_web)
  t.daemon = True
  t.start()

  application = Application.builder().token(TOKEN).build()

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("cancelar", cancelar_pedido))
  application.add_handler(CommandHandler("reiniciar", cmd_reiniciar))

  application.add_handler(
      CallbackQueryHandler(handle_callback_eleccion, pattern="^op_")
  )
  application.add_handler(
      CallbackQueryHandler(handle_callback_pago, pattern="^pay_")
  )
  application.add_handler(CallbackQueryHandler(handle_buttons))
  application.add_handler(MessageHandler(filters.LOCATION, handle_location))
  application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
  application.add_handler(
      MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text)
  )

  job_queue = application.job_queue
  job_queue.run_daily(
      enviar_reporte_automatico, time=time(hour=18, minute=30, tzinfo=LOCAL_TZ)
  )

  print(
      "Iniciando bot con servidor web Flask integrado para evitar suspensiones"
      " en la nube..."
  )
  application.run_polling()


if __name__ == "__main__":
  main()
