import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


TOKEN = os.getenv("TOKEN")

# PRODOTTI
products = {
    1: {"name": "Kinder Cards", "price": 1.00, "stock": 30},
    2: {"name": "Ringo Cheesecake Booom", "price": 1.00, "stock": 24},
    3: {"name": "NESQUIK Maxi Choco", "price": 1.00, "stock": 20},
    4: {"name": "Baiocchi Pistacchio", "price": 1.00, "stock": 24},
    5: {"name": "Kinder Duo", "price": 1.00, "stock": 12},
    6: {"name": "Bisco Cioc", "price": 1.00, "stock": 18},
}

carts = {}

# CREA CARRELLO UTENTE
def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}
    return carts[user_id]


# MENU
def build_menu(cart):
    keyboard = []

    for pid, p in products.items():
        qty = cart.get(pid, 0)
        text = p["name"] + " (" + str(p["stock"]) + ")"

        if qty > 0:
            text = text + " 🛒" + str(qty)

        keyboard.append([
            InlineKeyboardButton("➕ " + text, callback_data="add_" + str(pid)),
            InlineKeyboardButton("➖", callback_data="remove_" + str(pid))
        ])

    keyboard.append([
        InlineKeyboardButton("🛒 APRI CARRELLO", callback_data="cart")
    ])

    return InlineKeyboardMarkup(keyboard)


# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = get_cart(update.effective_user.id)

    await update.message.reply_text(
        "🍫 PIANO BAR BOT\n\nSeleziona prodotti:",
        reply_markup=build_menu(cart)
    )


# BOTTONI
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    cart = get_cart(user_id)

    data = query.data

    # ➕ AGGIUNGI
    if data.startswith("add_"):
        pid = int(data.split("_")[1])

        if products[pid]["stock"] <= 0:
            await query.answer("❌ Esaurito")
            return

        cart[pid] = cart.get(pid, 0) + 1
        products[pid]["stock"] -= 1

        await query.edit_message_reply_markup(reply_markup=build_menu(cart))

    # ➖ RIMUOVI
    elif data.startswith("remove_"):
        pid = int(data.split("_")[1])

        if cart.get(pid, 0) > 0:
            cart[pid] = cart.get(pid, 0) - 1
            products[pid]["stock"] += 1

            if cart[pid] <= 0:
                del cart[pid]

        await query.edit_message_reply_markup(reply_markup=build_menu(cart))

    # 🛒 CARRELLO
    elif data == "cart":
        text = "🛒 CARRELLO\n\n"
        total = 0
        keyboard = []

        if len(cart) == 0:
            text = text + "Carrello vuoto"
            keyboard = [
                [InlineKeyboardButton("⬅️ Torna al menu", callback_data="back")]
            ]
        else:
            for pid in cart:
                qty = cart[pid]
                product = products[pid]
                subtotal = product["price"] * qty
                total = total + subtotal

                text = text + product["name"] + " x" + str(qty) + "\n= " + str(round(subtotal, 2)) + "€\n\n"

            text = text + "💰 TOTALE: " + str(round(total, 2)) + "€"

            paypal_link = "https://www.paypal.me/" + "giuseppepapangelo" + "/" + str(round(total, 2))

            keyboard = [
                [InlineKeyboardButton("💳 Paga PayPal", url=paypal_link)],
                [InlineKeyboardButton("🗑 Svuota carrello", callback_data="clear")],
                [InlineKeyboardButton("⬅️ Torna al menu", callback_data="back")]
            ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 🗑 SVUOTA
    elif data == "clear":
        for pid in cart:
            products[pid]["stock"] = products[pid]["stock"] + cart[pid]

        carts[user_id] = {}

        await query.edit_message_text(
            "🗑 Carrello svuotato",
            reply_markup=build_menu(get_cart(user_id))
        )

    # 🔙 BACK
    elif data == "back":
        await query.edit_message_text(
            "🍫 PIANO BAR BOT\n\nSeleziona prodotti:",
            reply_markup=build_menu(get_cart(user_id))
        )


# MAIN
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("BOT AVVIATO")

    app.run_polling()


if __name__ == "__main__":
    main()