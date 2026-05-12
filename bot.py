import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import os

TOKEN = os.getenv("BOT_TOKEN")

products = {

    1: {
        "name": "Kinder Cards",
        "price": 1.00,
        "stock": 30,
        "image": "kinder_cards.jpg"
    },

    2: {
        "name": "Ringo Cheesecake Booom",
        "price": 1.00,
        "stock": 24,
        "image": "ringo_cheesecake.jpg"
    },

    3: {
        "name": "NESQUIK Maxi Choco",
        "price": 1.00,
        "stock": 20,
        "image": "nesquik.jpg"
    },

    4: {
        "name": "Baiocchi Pistacchio",
        "price": 1.00,
        "stock": 24,
        "image": "baiocchi_pistacchio.jpg"
    },

    5: {
        "name": "Kinder Duo",
        "price": 1.00,
        "stock": 12,
        "image": "kinder_duo.jpg"
    },

    6: {
        "name": "Bisco Cioc",
        "price": 1.00,
        "stock": 18,
        "image": "bisco_cioc.jpg"
    }

}


carts = {}


def get_cart(user_id):

    if user_id not in carts:
        carts[user_id] = {}

    return carts[user_id]


def get_total(cart):

    total = 0

    for pid, qty in cart.items():

        total += products[pid]["price"] * qty

    return total


def build_menu(cart):

    keyboard = []

    total = get_total(cart)

    for pid, p in products.items():

        qty = cart.get(pid, 0)

        text = f"{p['name']}"

        if qty > 0:
            text += f" 🛒{qty}"

        text += f" ({p['stock']})"

        keyboard.append([

            InlineKeyboardButton(
                f"➕ {text}",
                callback_data=f"add_{pid}"
            ),

            InlineKeyboardButton(
                "➖",
                callback_data=f"remove_{pid}"
            )

        ])

    keyboard.append([

        InlineKeyboardButton(
            f"🛒 CARRELLO • {total:.2f}€",
            callback_data="cart"
        )

    ])

    return InlineKeyboardMarkup(keyboard)


# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cart = get_cart(update.effective_user.id)

    await update.message.reply_photo(

        photo=open("kinder_cards.jpg", "rb"),

        caption=(
            "🍫 PIANO BAR POS\n\n"
            "Sistema cassa rapido"
        ),

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

        product = products[pid]

        if product["stock"] <= 0:

            await query.answer(
                "❌ Prodotto esaurito",
                show_alert=True
            )

            return

        cart[pid] = cart.get(pid, 0) + 1

        product["stock"] -= 1

        total = get_total(cart)

        text = (
            f"🍫 PIANO BAR POS\n\n"
            f"✅ Aggiunto:\n"
            f"{product['name']}\n\n"
            f"💰 Totale: {total:.2f}€"
        )

        await query.edit_message_media(

            media=InputMediaPhoto(
                media=open(product["image"], "rb"),
                caption=text
            ),

            reply_markup=build_menu(cart)
        )


    # ➖ RIMUOVI
    elif data.startswith("remove_"):

        pid = int(data.split("_")[1])

        if cart.get(pid, 0) > 0:

            cart[pid] -= 1

            products[pid]["stock"] += 1

            if cart[pid] <= 0:
                del cart[pid]

        total = get_total(cart)

        await query.edit_message_caption(

            caption=(
                "🍫 PIANO BAR POS\n\n"
                f"💰 Totale: {total:.2f}€"
            ),

            reply_markup=build_menu(cart)
        )


    # 🛒 CARRELLO
    elif data == "cart":

        text = "🛒 CARRELLO\n\n"

        total = get_total(cart)

        if not cart:

            text += "Carrello vuoto"

        else:

            for pid, qty in cart.items():

                p = products[pid]

                subtotal = p["price"] * qty

                text += (
                    f"{p['name']} x{qty}\n"
                    f"= {subtotal:.2f}€\n\n"
                )

            text += f"💰 TOTALE: {total:.2f}€"

        paypal = f"https://www.paypal.me/giuseppepapangelo/{total:.2f}"

        keyboard = [

            [
                InlineKeyboardButton(
                    "💳 PAYPAL",
                    url=paypal
                )
            ],

            [
                InlineKeyboardButton(
                    "🗑 SVUOTA",
                    callback_data="clear"
                )
            ],

            [
                InlineKeyboardButton(
                    "⬅️ MENU",
                    callback_data="back"
                )
            ]

        ]

        await query.edit_message_caption(

            caption=text,

            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    # 🗑 SVUOTA
    elif data == "clear":

        for pid, qty in cart.items():

            products[pid]["stock"] += qty

        cart.clear()

        await query.edit_message_caption(

            caption="🗑 Carrello svuotato",

            reply_markup=build_menu(cart)
        )


    # 🔙 MENU
    elif data == "back":

        total = get_total(cart)

        await query.edit_message_caption(

            caption=(
                "🍫 PIANO BAR POS\n\n"
                f"💰 Totale: {total:.2f}€"
            ),

            reply_markup=build_menu(cart)
        )


# AVVIO
def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("POS AVVIATO")

    app.run_polling()


if __name__ == "__main__":
    main()