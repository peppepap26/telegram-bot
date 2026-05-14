import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

PAYPAL_USER = "@giuseppepapangelo"

products = {
    1: {
        "name": "Kinder Cards",
        "price": 1.00,
        "stock": 30,
        "img": "https://i.imgur.com/1.jpg"
    },
    2: {
        "name": "Ringo Cheesecake Booom",
        "price": 1.00,
        "stock": 24,
        "img": "https://i.imgur.com/2.jpg"
    },
    3: {
        "name": "NESQUIK Maxi Choco",
        "price": 1.00,
        "stock": 20,
        "img": "https://i.imgur.com/3.jpg"
    },
    4: {
        "name": "Baiocchi Pistacchio",
        "price": 1.00,
        "stock": 24,
        "img": "https://i.imgur.com/4.jpg"
    },
    5: {
        "name": "Kinder Duo",
        "price": 1.00,
        "stock": 12,
        "img": "https://i.imgur.com/5.jpg"
    },
    6: {
        "name": "Bisco Cioc",
        "price": 1.00,
        "stock": 18,
        "img": "https://i.imgur.com/6.jpg"
    },
}

carts = {}

def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}
    return carts[user_id]


def product_keyboard(pid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Aggiungi", callback_data=f"add_{pid}"),
            InlineKeyboardButton("➖ Rimuovi", callback_data=f"remove_{pid}")
        ],
        [
            InlineKeyboardButton("🛒 Carrello", callback_data="cart")
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for pid, p in products.items():
        await update.message.reply_photo(
            photo=p["img"],
            caption=f"{p['name']}\n💰 {p['price']}€\n📦 Stock: {p['stock']}",
            reply_markup=product_keyboard(pid)
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    cart = get_cart(user_id)
    data = query.data

    if data.startswith("add_"):
        pid = int(data.split("_")[1])

        if products[pid]["stock"] <= 0:
            await query.answer("Esaurito")
            return

        cart[pid] = cart.get(pid, 0) + 1
        products[pid]["stock"] -= 1

        await query.answer("Aggiunto")

    elif data.startswith("remove_"):
        pid = int(data.split("_")[1])

        if cart.get(pid, 0) > 0:
            cart[pid] -= 1
            products[pid]["stock"] += 1

            if cart[pid] <= 0:
                del cart[pid]

        await query.answer("Rimosso")

    elif data == "cart":

    total = 0

    if not cart:
        text = "🛒 CARRELLO\n\nIl carrello è vuoto"
    else:
        text = "🛒 CARRELLO\n\n"

        for pid, qty in cart.items():
            p = products[pid]
            subtotal = p["price"] * qty
            total += subtotal

            text += f"{p['name']} x{qty} = {subtotal:.2f}€\n"

        text += f"\n💰 TOTALE: {total:.2f}€"

    paypal = f"https://www.paypal.me/giuseppepapangelo/{total:.2f}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Paga PayPal", url=paypal)],
        [InlineKeyboardButton("⬅️ Torna", callback_data="back")]
    ])

    await query.edit_message_text(text=text, reply_markup=keyboard)


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("BOT AVVIATO")

    app.run_polling()


if __name__ == "__main__":
    main()