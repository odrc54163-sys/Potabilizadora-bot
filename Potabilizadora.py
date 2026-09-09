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
TELEFONO_ADMIN = "0412-9511145"
PAGO_MOVIL_BANCO = "Banco Venezuela"
PAGO_MOVIL_TELEFONO = "0412-9513015"
PAGO_MOVIL_CEDULA = "18.912.986"

# PRECIO UNITARIO
PRECIO_UNITARIO = 800

# Almacenamiento temporal de datos de los usuarios en memoria
user_data_store = {}


# --- SERVIDOR WEB FALSO PARA RENDER Y UPTIMEROBOT ---
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
    tz = pytz.timezone("America/Caracas")
    ahora = datetime.now(tz)
    dia_semana = ahora.weekday()  # Lunes = 0, Domingo = 6
    hora_actual = ahora.time()

    if dia_semana == 6:
        return False

    hora_inicio = datetime.strptime("08:00", "%H:%M").time()
    hora_fin = datetime.strptime("17:30", "%H:%M").time()

    return hora_inicio <= hora_actual <= hora_fin


async def cancelar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        user_data_store.pop(user_id, None)
    
    await update.message.reply_text(
        "❌ *Has cancelado el pedido actual.*\n\n"
        "Puedes iniciar uno nuevo en cualquier momento enviando /start.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


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

    user_data_store[user_id] = {}

    teclado = [
        [
            InlineKeyboardButton(
                "💧 Recarga de Botellón", callback_data="op_recarga"
            )
        ],
        [
            InlineKeyboardButton(
                "🧊 Botellón Nuevo", callback_data="op_nuevo"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    bienvenida = (
        f"¡Hola *{user.first_name}*! 👋\n\n"
        "Bienvenido al sistema de pedidos de la *Potabilizadora Gual España* 💧.\n\n"
        "Por favor, selecciona el tipo de servicio que necesitas:\n\n"
        "💡 *Nota:* Puedes cancelar tu pedido en cualquier momento enviando el comando /cancelar."
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

    # 1. PASO: CANTIDAD
    if paso == "cantidad":
        texto = update.message.text
        if not texto or not texto.isdigit() or int(texto) <= 0:
            await update.message.reply_text(
                "⚠️ Por favor, ingresa un número válido de unidades (ejemplo: 2).\n"
                "También puedes cancelar escribiendo /cancelar.",
                parse_mode="Markdown"
            )
            return

        cantidad = int(texto)
        total_a_pagar = cantidad * PRECIO_UNITARIO
        user_data_store[user_id]["cantidad"] = str(cantidad)
        user_data_store[user_id]["total"] = total_a_pagar
        user_data_store[user_id]["paso"] = "nombre"
            
        await update.message.reply_text(
            f"🔢 Son {cantidad} unidades, el total a pagar es *{total_a_pagar} Bs*.\n\n"
            "👤 Por favor, dime tu *Nombre y Apellido* para registrar el pedido:\n\n"
            "*(Recuerda que puedes usar /cancelar para abortar en cualquier momento)*",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )

    # 2. PASO: NOMBRE Y APELLIDO
    elif paso == "nombre":
        texto = update.message.text
        if not texto or len(texto.strip()) < 3:
            await update.message.reply_text(
                "⚠️ Por favor, ingresa un nombre y apellido válido.",
                parse_mode="Markdown"
            )
            return

        user_data_store[user_id]["nombre_cliente"] = texto.strip()
        user_data_store[user_id]["paso"] = "telefono"

        teclado_contacto = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Compartir mi Número de Teléfono", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await update.message.reply_text(
            "📞 Ahora, por favor comparte tu número de teléfono presionando el botón de abajo o escríbelo:",
            reply_markup=teclado_contacto,
            parse_mode="Markdown"
        )

    # 3. PASO: TELÉFONO
    elif paso == "telefono":
        if update.message.contact:
            telefono = update.message.contact.phone_number
        elif update.message.text:
            telefono = update.message.text.strip()
        else:
            return

        user_data_store[user_id]["telefono_cliente"] = telefono
        user_data_store[user_id]["paso"] = "direccion"

        teclado_ubicacion = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Compartir mi Ubicación Actual", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await update.message.reply_text(
            "📍 Excelente. Ahora presiona el botón de abajo para enviar tu *ubicación exacta* o escribe una referencia:",
            reply_markup=teclado_ubicacion,
            parse_mode="Markdown"
        )

    # 4. PASO: DIRECCIÓN
    elif paso == "direccion":
        if update.message.location:
            lat = update.message.location.latitude
            lon = update.message.location.longitude
            user_data_store[user_id]["lat"] = lat
            user_data_store[user_id]["lon"] = lon
            user_data_store[user_id]["tiene_ubicacion_gps"] = True
            user_data_store[user_id]["direccion_texto"] = "Ubicación GPS compartida"
        elif update.message.text:
            user_data_store[user_id]["direccion_texto"] = f"Referencia escrita: {update.message.text}"
            user_data_store[user_id]["tiene_ubicacion_gps"] = False
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
        ]
        reply_markup = InlineKeyboardMarkup(teclado_pago)
        
        total = user_data_store[user_id]["total"]
        await update.message.reply_text(
            "💳 ¿Cuál será tu *método de pago*?\n"
            f"Total a cancelar: *{total} Bs*",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "Selecciona una opción o escribe /cancelar si deseas anular el pedido:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    # 5. PASO: ESPERANDO FOTO DE COMPROBANTE DE PAGO MÓVIL
    elif paso == "esperando_capture":
        if update.message.photo:
            foto_file_id = update.message.photo[-1].file_id
            user_data_store[user_id]["capture_id"] = foto_file_id
            
            # Enviar pedido completo al grupo con la foto y ubicación si la hay
            await enviar_pedido_con_foto_al_grupo(user_id, context)
            
            await update.message.reply_text(
                "✅ *¡Comprobante recibido y pedido enviado con éxito!*\n\n"
                "La administración verificará tu pago en breve. ¡Gracias por preferirnos! 💧✨",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove()
            )
            user_data_store.pop(user_id, None)
        else:
            await update.message.reply_text(
                "⚠️ Por favor, envía la *foto del comprobante (capture)* de tu pago móvil para continuar, o escribe /cancelar para anular.",
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
        user_data_store[user_id]["tipo_pedido"] = "Recarga"
    elif data_tipo == "op_nuevo":
        user_data_store[user_id]["tipo_pedido"] = "Botellón Nuevo"

    user_data_store[user_id]["paso"] = "cantidad"
    await query.edit_message_text(
        text=(
            f"📦 Has seleccionado: *{user_data_store[user_id]['tipo_pedido']}*.\n\n"
            "🔢 ¿Cuántas unidades deseas solicitar? (Escribe el número en el chat o usa /cancelar):"
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

    # 1. Si selecciona Pago Móvil, mostramos datos y pedimos foto del capture
    if data_pago == "pago_movil":
        user_data_store[user_id]["metodo_pago"] = "Pago Móvil"
        user_data_store[user_id]["paso"] = "esperando_capture"
        total = user_data_store[user_id].get("total", 0)
        
        datos_pm = (
            "📱 *DATOS PARA PAGO MÓVIL* 📱\n\n"
            f"🏦 *Banco:* {PAGO_MOVIL_BANCO}\n"
            f"📞 *Teléfono:* `{PAGO_MOVIL_TELEFONO}`\n"
            f"🆔 *Cédula:* `{PAGO_MOVIL_CEDULA}`\n"
            f"💰 *Monto exacto:* `{total} Bs`\n\n"
            "📸 *Por favor, envía por aquí la foto del comprobante (capture) de tu pago* para procesar tu pedido.\n\n"
            "*(Puedes cancelar enviando /cancelar)*"
        )
        
        await query.edit_message_text(text=datos_pm, parse_mode="Markdown")
        return

    # 2. Si selecciona Efectivo
    if data_pago == "pago_efectivo":
        user_data_store[user_id]["metodo_pago"] = "Efectivo"
        await enviar_pedido_texto_al_grupo(user_id, context, "Efectivo")
        
        await query.edit_message_text(
            text=(
                "🎉 *¡Pedido registrado con éxito!*\n\n"
                "💵 Has seleccionado pago en *Efectivo* al recibir. ¡Pronto despacharemos tu pedido! 🚚💧"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        user_data_store.pop(user_id, None)
        return


def obtener_teclado_admin(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Pago Verificado", callback_data=f"verificado_{user_id}"),
            InlineKeyboardButton("⚠️ Pago Falso", callback_data=f"pagofalso_{user_id}")
        ],
        [
            InlineKeyboardButton("🛵 En camino", callback_data=f"encamino_{user_id}"),
            InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{user_id}")
        ]
    ])


async def enviar_pedido_texto_al_grupo(user_id, context, metodo):
    datos = user_data_store.get(user_id, {})
    nombre = datos.get("nombre_cliente", "Sin nombre")
    telefono = datos.get("telefono_cliente", "Sin teléfono")
    tipo = datos.get("tipo_pedido", "Pedido")
    cantidad = datos.get("cantidad", "1")
    total = datos.get("total", 0)
    
    user_obj = await context.bot.get_chat(user_id)
    alias = f"@{user_obj.username}" if user_obj.username else "Sin alias"

    mensaje_grupo = (
        f"🚨 *NUEVO PEDIDO DE AGUA* 🚨\n\n"
        f"👤 *Cliente:* {nombre}\n"
        f"💬 *Alias:* {alias}\n"
        f"📞 *Teléfono:* `{telefono}`\n"
        f"📦 *Pedido:* {cantidad}x {tipo}\n"
        f"💵 *Total a pagar:* {total:,.2f} BS\n"
        f"💳 *Método de pago:* {metodo}\n\n"
        f"📌 *Estado:* ⏳ Pendiente"
    )

    sent_msg = await context.bot.send_message(
        chat_id=GRUPO_ID, text=mensaje_grupo, reply_markup=obtener_teclado_admin(user_id), parse_mode="Markdown"
    )

    # Enviar ubicación si la tiene guardada
    if datos.get("tiene_ubicacion_gps"):
        await context.bot.send_location(
            chat_id=GRUPO_ID,
            latitude=datos.get("lat"),
            longitude=datos.get("lon")
        )
    else:
        ref_texto = datos.get("direccion_texto", "Sin referencia")
        await context.bot.send_message(
            chat_id=GRUPO_ID,
            text=f"📍 *Referencia de entrega:*\n{ref_texto}",
            parse_mode="Markdown"
        )


async def enviar_pedido_con_foto_al_grupo(user_id, context):
    datos = user_data_store.get(user_id, {})
    nombre = datos.get("nombre_cliente", "Sin nombre")
    telefono = datos.get("telefono_cliente", "Sin teléfono")
    tipo = datos.get("tipo_pedido", "Pedido")
    cantidad = datos.get("cantidad", "1")
    total = datos.get("total", 0)
    capture_id = datos.get("capture_id")
    
    user_obj = await context.bot.get_chat(user_id)
    alias = f"@{user_obj.username}" if user_obj.username else "Sin alias"

    caption_grupo = (
        f"🚨 *NUEVO PEDIDO DE AGUA* 🚨\n\n"
        f"👤 *Cliente:* {nombre}\n"
        f"💬 *Alias:* {alias}\n"
        f"📞 *Teléfono:* `{telefono}`\n"
        f"📦 *Pedido:* {cantidad}x {tipo}\n"
        f"💵 *Total a pagar:* {total:,.2f} BS\n"
        f"💳 *Método de pago:* Pago Móvil\n\n"
        f"📌 *Estado:* ⏳ Pendiente por verificar pago"
    )

    await context.bot.send_photo(
        chat_id=GRUPO_ID,
        photo=capture_id,
        caption=caption_grupo,
        reply_markup=obtener_teclado_admin(user_id),
        parse_mode="Markdown"
    )

    # Enviar ubicación si la tiene guardada
    if datos.get("tiene_ubicacion_gps"):
        await context.bot.send_location(
            chat_id=GRUPO_ID,
            latitude=datos.get("lat"),
            longitude=datos.get("lon")
        )
    else:
        ref_texto = datos.get("direccion_texto", "Sin referencia")
        await context.bot.send_message(
            chat_id=GRUPO_ID,
            text=f"📍 *Referencia de entrega:*\n{ref_texto}",
            parse_mode="Markdown"
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
        
        try:
            nuevo_teclado = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🛵 En camino", callback_data=f"encamino_{cliente_id}"),
                    InlineKeyboardButton("✅ Entregado", callback_data=f"entregado_{cliente_id}")
                ]
            ])
            if query.message.photo:
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\n✅ *PAGO VERIFICADO*",
                    reply_markup=nuevo_teclado,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    text=query.message.text + "\n\n✅ *PAGO VERIFICADO*",
                    reply_markup=nuevo_teclado,
                    parse_mode="Markdown"
                )
        except Exception:
            pass

    elif accion == "pagofalso":
        mensaje_cliente = (
            "🚨 *¡ATENCIÓN: PAGO NO VÁLIDO / FALSO!* 🚨\n\n"
            "Lamentablemente, el comprobante o pago enviado no pudo ser verificado o presenta inconsistencias.\n\n"
            "Por favor, comunícate directamente con la administración para solventar la situación a través del siguiente número:\n\n"
            f"📞 *Administradora:* `{TELEFONO_ADMIN}`"
        )
        await context.bot.send_message(
            chat_id=cliente_id, text=mensaje_cliente, parse_mode="Markdown"
        )
        
        try:
            if query.message.photo:
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\n❌ *PAGO RECHAZADO (FALSO)*",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    text=query.message.text + "\n\n❌ *PAGO RECHAZADO (FALSO)*",
                    parse_mode="Markdown"
                )
        except Exception:
            pass

    elif accion == "encamino":
        mensaje_cliente = (
            "🛵 *¡Su pedido va en camino!* 💧\n\n"
            "El motorizado ya se dirige hacia su ubicación. Por favor, **manténgase atento a su teléfono** y a la puerta. ¡Gracias por su compra! 🚰"
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
        try:
            if query.message.photo:
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\n✅ *PEDIDO COMPLETADO*",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    text=query.message.text + "\n\n✅ *PEDIDO COMPLETADO*",
                    parse_mode="Markdown"
                )
        except Exception:
            pass


def main():
    hilo_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
    hilo_web.start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", mostrar_bienvenida_o_cerrado))
    application.add_handler(CommandHandler("cancelar", cancelar_pedido))
    application.add_handler(CallbackQueryHandler(callback_eleccion, pattern="^op_.*"))
    application.add_handler(CallbackQueryHandler(callback_pago, pattern="^pago_.*"))
    application.add_handler(
        CallbackQueryHandler(
            callback_acciones_admin,
            pattern="^(verificado|pagofalso|encamino|entregado)_.*",
        )
    )
    application.add_handler(MessageHandler((filters.TEXT | filters.LOCATION | filters.CONTACT | filters.PHOTO) & ~filters.COMMAND, manejar_mensajes))

    print("Bot actualizado con los nuevos campos de nombre, teléfono, ubicación en mapa y formato mejorado...")
    application.run_polling()


if __name__ == "__main__":
    main()
