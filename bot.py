import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# TOKEN da Render (Environment Variables)
TOKEN = os.getenv("8740234622:AAETXRO3QCMR0pmvTpJ0vK93LhIGzzho9ho")

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

def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}
    return carts[user_id]


# MENU
def build_menu(cart):
    keyboard = []

    for pid, p in products.items():
        qty = cart.get(pid, 0)
        text = f"{p['name']} ({p['stock']})"

        if qty > 0:
            text += f" 🛒{qty}"

        keyboard.append([
            InlineKeyboardButton(f"➕ {text}", callback_data=f"add_{pid}"),
            InlineKeyboardButton("➖", callback_data=f"remove_{pid}")
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
            cart[pid] -= 1
            products[pid]["stock"] += 1

            if cart[pid] <= 0:
                del cart[pid]

        await query.edit_message_reply_markup(reply_markup=build_menu(cart))

    # 🛒 CARRELLO
    elif data == "cart":
        text = "🛒 CARRELLO\n\n"
        total = 0

        if not cart:
            text += "Carrello vuoto"
        else:
            for pid, qty in cart.items():
                p = products[pid]
                subtotal = p["price"] * qty
                total += subtotal

                text += f"{p['name']} x{qty}\n= {subtotal:.2f}€\n\n"

            text += f"💰 TOTALE: {total:.2f}€"

paypal = f"https://www.paypal.me/giuseppepapangelome/{total:.2f}"

        keyboard = [
            [InlineKeyboardButton("💳 Paga PayPal", url=paypal)],
            [InlineKeyboardButton("🗑 Svuota carrello", callback_data="clear")],
            [InlineKeyboardButton("⬅️ Torna al menu", callback_data="back")]
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # 🗑 SVUOTA
    elif data == "clear":
        for pid, qty in cart.items():
            products[pid]["stock"] += qty

        cart.clear()

        await query.edit_message_text(
            "🗑 Carrello svuotato",
            reply_markup=build_menu(cart)
        )

    # 🔙 BACK
    elif data == "back":
        await query.edit_message_text(
            "🍫 PIANO BAR BOT\n\nSeleziona prodotti:",
            reply_markup=build_menu(cart)
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