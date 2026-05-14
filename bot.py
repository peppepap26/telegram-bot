import os
import gspread

from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")

PAYPAL_USER = "giuseppepapangelo"

SHEET_ID = "1eGDRwUnvveDIYuasMHSbQk8qNpT94nQ_AYNnVWiNS_Q"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "creds.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)

sheet_products = client.open_by_key(SHEET_ID).worksheet("PRODUCTS")
sheet_sales = client.open_by_key(SHEET_ID).worksheet("SALES")

carts = {}


def get_products():
    rows = sheet_products.get_all_records()

    products = {}

    for row in rows:
        products[int(row["id"])] = {
            "name": row["name"],
            "price": float(row["price"]),
            "stock": int(row["stock"]),
            "img": row["image"]
        }

    return products


def update_stock(pid, stock):
    cell = sheet_products.find(str(pid))

    if cell:
        sheet_products.update_cell(cell.row, 4, stock)


def save_sale(product, qty, price, total):
    from datetime import datetime

    sheet_sales.append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        product,
        qty,
        price,
        total
    ])


def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}

    return carts[user_id]


def product_keyboard(pid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Aggiungi",
                callback_data=f"add_{pid}"
            ),
            InlineKeyboardButton(
                "➖ Rimuovi",
                callback_data=f"remove_{pid}"
            )
        ],
        [
            InlineKeyboardButton(
                "🛒 Carrello",
                callback_data="cart"
            )
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_products()

    for pid, p in products.items():
        await update.message.reply_photo(
            photo=p["img"],
            caption=(
                f"{p['name']}\n"
                f"💰 {p['price']}€\n"
                f"📦 Stock: {p['stock']}"
            ),
            reply_markup=product_keyboard(pid)
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    cart = get_cart(user_id)

    data = query.data

    products = get_products()

    if data.startswith("add_"):

        pid = int(data.split("_")[1])

        if products[pid]["stock"] <= 0:
            await query.answer("Prodotto esaurito")
            return

        cart[pid] = cart.get(pid, 0) + 1

        new_stock = products[pid]["stock"] - 1

        update_stock(pid, new_stock)

        await query.answer("Aggiunto al carrello")

    elif data.startswith("remove_"):

        pid = int(data.split("_")[1])

        if cart.get(pid, 0) > 0:

            cart[pid] -= 1

            new_stock = products[pid]["stock"] + 1

            update_stock(pid, new_stock)

            if cart[pid] <= 0:
                del cart[pid]

        await query.answer("Rimosso dal carrello")

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

                text += (
                    f"{p['name']} x{qty} = "
                    f"{subtotal:.2f}€\n"
                )

        paypal = (
            f"https://www.paypal.me/"
            f"{PAYPAL_USER}/{total:.2f}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "💳 Paga PayPal",
                    url=paypal
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Conferma Ordine",
                    callback_data="confirm"
                )
            ]
        ])

        await query.edit_message_text(
            text=text,
            reply_markup=keyboard
        )

    elif data == "confirm":

        total = 0

        for pid, qty in cart.items():

            p = products[pid]

            subtotal = p["price"] * qty

            total += subtotal

            save_sale(
                p["name"],
                qty,
                p["price"],
                subtotal
            )

        carts[user_id] = {}

        await query.edit_message_text(
            text=(
                "✅ Ordine confermato\n\n"
                f"Totale pagato: {total:.2f}€"
            )
        )


def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("BOT AVVIATO")

    app.run_polling()


if __name__ == "__main__":
    main()