import logging
from datetime import datetime
import os
import pytz
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
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

# Configuración de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# CONFIGURACIÓN DE CREDENCIALES
TOKEN = "8925935497:AAEGyl40GCpChO-zBCArrSNLioD5dOUNKfY"
GRUPO_ID = -1004303277305

# 📌 TUS DATOS REALES DE PAGO MÓVIL Y ADMINISTRACIÓN
TELEFONO_ADMIN = "0412-9513015"
PAGO_MOVIL_BANCO = "Banco Venezuela"
PAGO_MOVIL_TELEFONO = "0412-9513015"
PAGO_MOVIL_CEDULA = "18.912.986"

# Almacenamiento temporal de datos de los usuarios en memoria
user_data_store = {}


# --- SERVIDOR WEB FALSO PARA COMPLACER A RENDER Y UPTIMEROBOT ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot de Potabilizadora Gual Espana activo y operando!")

    def log_message(self, format, *args):
        pass


def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()
# ------------------------------------------------------------------


def verificar_horario():
    """Verifica si la potabilizadora está en horario laboral (Lunes a Sábado de 8:00 AM a 5:30 PM, Hora de Venezuela)."""
    tz = pytz.timezone("America/Caracas")
    ahora = datetime.now(tz)
    dia_semana = ahora.weekday()  # Lunes = 0, Domingo = 6
    hora_actual = ahora.time()

    if dia_semana == 6:
        return False

    hora_inicio = datetime.strptime("08:00", "%H:%M").time()
    hora_fin = datetime.strptime("17:30", "%H:%M").time()

    return hora_inicio <= hora_actual <= hora_fin


async def mostrar_bienvenida_o_cerrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data_store or "paso" not in user_data_store[user_id]:
        await mostrar_bienvenida_o_cerrado(update, context)
        return

    paso = user_data_store[user_id]["paso"]

    if paso == "cantidad":
        if update.message.text:
            user_data_store[user_id]["cantidad"] = update.message.text
            user_data_store[user_id]["paso"] = "direccion"
            
            teclado_ubicacion = ReplyKeyboardMarkup(
                [[KeyboardButton("📍 Compartir mi Ubicación Actual", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await update.message.reply_text(
                "📍 ¡Perfecto!\n\n"
                "Ahora, por favor presiona el botón de abajo para enviar tu ubicación exacta o escribe una referencia:",
                reply_markup=teclado_ubicacion,
                parse_mode="Markdown"
            )

    elif paso == "direccion":
        if update.message.location:
            lat = update.message.location.latitude
            lon = update.message.location.longitude
            user_data_store[user_id]["direccion"] = f"Ubicación GPS: [Google Maps](https://maps.google.com/?q={lat},{lon})"
        elif update.message.text:
            user_data_store[user_id]["direccion"] = f"Dirección escrita: {update.message.text}"
        else:
            return

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
            [
                InlineKeyboardButton(
                    "⚠️ Reportar Pago / Incidencia", callback_data="pago_falso"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(teclado_pago)
        
        await update.message.reply_text(
            "💳 ¿Cuál será tu *método de pago*?",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "Selecciona una opción:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def callback_eleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data_store:
        user_data_store[user_id] = {}

    data_tipo = query.data

    if data_tipo == "op_recarga":
        user_data_store[user_id]["tipo_pedido"] = "Recarga de Botellón"
    elif data_tipo == "op_nuevo":
        user_data_store[user_id]["tipo_pedido"] = "Botellón Nuevo (Con Envase)"

    user_data_store[user_id]["paso"] = "cantidad"
    await query.edit_message_text(
        text=(
            f"📦 Has seleccionado: *{user_data_store[user_id]['tipo_pedido']}*.\n\n"
            "🔢 ¿Cuántas unidades deseas solicitar?"
        ),
        parse_mode="Markdown",
    )


async def callback_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data_store:
        return

    data_pago = query.data

    # 1. Si selecciona Pago Móvil, mostramos los datos bancarios exactos al usuario
    if data_pago == "pago_movil":
        user_data_store[user_id]["metodo_pago"] = "Pago Móvil"
        
        datos_pm = (
            "📱 *DATOS PARA PAGO MÓVIL* 📱\n\n"
            f"🏦 *Banco:* {PAGO_MOVIL_BANCO}\n"
            f"📞 *Teléfono:* `{PAGO_MOVIL_TELEFONO}`\n"
            f"🆔 *Cédula:* `{PAGO_MOVIL_CEDULA}`\n\n"
            "✨ Realiza tu pago y recuerda notificar o enviar el capture a la administración."
        )
        
        await enviar_pedido_al_grupo(query, user_id, context, "Pago Móvil")
        
        await query.edit_message_text(text=datos_pm, parse_mode="Markdown")
        user_data_store.pop(user_id, None)
        return

    # 2. Si selecciona Reporte de Pago / Incidencia
    if data_pago == "pago_falso":
        await query.edit_message_text(
            text=(
                "🚨 *¡Atención!* 🚨\n\n"
                "Se ha detectado un inconveniente o reporte con el pago.\n"
                "Por favor, comunícate directamente con la administradora para verificar tu situación.\n\n"
                f"📞 *Administradora:* `{TELEFONO_ADMIN}`"
            ),
            parse_mode="Markdown"
        )
        user_data_store.pop(user_id, None)
        return

    # 3. Si selecciona Efectivo
    if data_pago == "pago_efectivo":
        user_data_store[user_id]["metodo_pago"] = "Efectivo"
        await enviar_pedido_al_grupo(query, user_id, context, "Efectivo")
        
        await query.edit_message_text(
            text=(
                "🎉 *¡Pedido registrado con éxito!*\n\n"
                "💵 Has seleccionado pago en *Efectivo* al recibir. ¡Pronto despacharemos tu pedido! 🚚💧"
            ),
            parse_mode="Markdown",
        )
        user_data_store.pop(user_id, None)
        return


async def enviar_pedido_al_grupo(query, user_id, context, metodo):
    datos = user_data_store.get(user_id, {})
    tipo = datos.get("tipo_pedido", "Pedido")
    cantidad = datos.get("cantidad", "1")
    direccion = datos.get("direccion", "Sin dirección")

    mensaje_grupo = (
        f"🚨 *¡NUEVO PEDIDO RECIBIDO!* 🚨\n\n"
        f"👤 *Cliente:* {query.from_user.full_name}\n"
        f"📦 *Producto:* {tipo}\n"
        f"🔢 *Cantidad:* {cantidad}\n"
        f"📍 *Entrega:* {direccion}\n"
        f"💵 *Método de pago:* {metodo}\n"
        f"📌 *Estado:* 🟡 Pendiente por verificación"
    )

    teclado_admin = [
        [
            InlineKeyboardButton(
                "💳 Pago Verificado", callback_data=f"verificado_{user_id}"
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

    await context.bot.send_message(
        chat_id=GRUPO_ID, text=mensaje_grupo, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=False
    )


async def callback_acciones_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    accion, cliente_id_str = data.split("_")
    cliente_id = int(cliente_id_str)

    if accion == "verificado":
        mensaje_cliente = (
            "✅ *¡Su pago ha sido verificado con éxito!*\n\n"
            "Pronto le enviaremos su pedido. ¡Gracias por preferirnos! 💧✨"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛵 En camino", callback_data=f"encamino_{cliente_id}"
                        ),
                        InlineKeyboardButton(
                            "✅ Entregado", callback_data=f"entregado_{cliente_id}"
                        ),
                    ]
                ]
            )
        )

    elif accion == "encamino":
        mensaje_cliente = (
            "🛵 *¡Su pedido va en camino!*\n\n"
            "El motorizado se dirige hacia su ruta. Por favor, manténgase atento. 📞💧"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )

    elif accion == "entregado":
        mensaje_cliente = (
            "🎉 *¡Pedido Entregado!*\n\n"
            "Muchísimas gracias por su compra en la **Potabilizadora Gual España**. ¡Esperamos verle pronto! 💧🚰"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )
        await query.edit_message_text(
            text=query.message.text + "\n\n✅ *PEDIDO COMPLETADO*",
            parse_mode="Markdown",
        )


def main():
    hilo_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
    hilo_web.start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", mostrar_bienvenida_o_cerrado))
    application.add_handler(CallbackQueryHandler(callback_eleccion, pattern="^op_.*"))
    application.add_handler(CallbackQueryHandler(callback_pago, pattern="^(pago_.*|pago_falso)$"))
    application.add_handler(
        CallbackQueryHandler(
            callback_acciones_admin,
            pattern="^(verificado|encamino|entregado)_.*",
        )
    )
    application.add_handler(MessageHandler((filters.TEXT | filters.LOCATION) & ~filters.COMMAND, manejar_mensajes))

    print("Bot completo configurado con tus datos reales de Pago Móvil...")
    application.run_polling()


if __name__ == "__main__":
    main()
