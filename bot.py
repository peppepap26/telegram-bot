import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
PAYPAL_USER = os.getenv("PAYPAL_USER")
SHEET_ID = os.getenv("SHEET_ID")

creds_json = json.loads(os.getenv("GOOGLE_CREDS"))

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_json, scopes=scope)
client = gspread.authorize(creds)

sheet_products = client.open_by_key(SHEET_ID).worksheet("PRODUCTS")
sheet_sales = client.open_by_key(SHEET_ID).worksheet("SALES")

# ---------------- CART ----------------
carts = {}

def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}
    return carts[user_id]

# ---------------- PRODUCTS LOAD ----------------
def load_products():
    rows = sheet_products.get_all_records()
    products = {}

    for r in rows:
        products[int(r["id"])] = {
            "name": r["name"],
            "price": float(r["price"]),
            "stock": int(r["stock"]),
            "img": r["img"]
        }

    return products

# ---------------- KEYBOARD ----------------
def product_keyboard(pid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Aggiungi", callback_data=f"add_{pid}"),
            InlineKeyboardButton("➖ Rimuovi", callback_data=f"remove_{pid}")
        ],
        [InlineKeyboardButton("🛒 Carrello", callback_data="cart")]
    ])

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_products()

    for pid, p in products.items():
        await update.message.reply_photo(
            photo=p["img"],
            caption=f"{p['name']}\n💰 {p['price']}€\n📦 Stock: {p['stock']}",
            reply_markup=product_keyboard(pid)
        )

# ---------------- BUTTONS ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    cart = get_cart(user_id)
    data = query.data

    products = load_products()

    # ADD
    if data.startswith("add_"):
        pid = int(data.split("_")[1])
        p = products[pid]

        if p["stock"] <= 0:
            await query.answer("Esaurito")
            return

        cart[pid] = cart.get(pid, 0) + 1

        sheet_products.update_cell(pid + 1, 4, p["stock"] - 1)

        await query.answer("Aggiunto")

    # REMOVE
    elif data.startswith("remove_"):
        pid = int(data.split("_")[1])

        if cart.get(pid, 0) > 0:
            cart[pid] -= 1
            p = products[pid]

            sheet_products.update_cell(pid + 1, 4, p["stock"] + 1)

            if cart[pid] == 0:
                del cart[pid]

        await query.answer("Rimosso")

    # CART
    elif data == "cart":

        total = 0
        user_id = query.from_user.id

        if not cart:
            text = "🛒 CARRELLO\n\nVuoto"
        else:
            text = "🛒 CARRELLO\n\n"

            for pid, qty in cart.items():
                p = products[pid]
                subtotal = p["price"] * qty
                total += subtotal

                text += f"{p['name']} x{qty} = {subtotal:.2f}€\n"

                # SAVE SALE ON SHEET
                sheet_sales.append_row([
                    str(datetime.datetime.now()),
                    user_id,
                    p["name"],
                    qty,
                    p["price"],
                    subtotal
                ])

        paypal = f"https://www.paypal.me/{PAYPAL_USER}/{total:.2f}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 PayPal", url=paypal)],
            [InlineKeyboardButton("⬅️ Torna", callback_data="back")]
        ])

        await query.edit_message_text(text, reply_markup=keyboard)

    # BACK
    elif data == "back":
        await start(update, context)

# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("BOT AVVIATO")
    app.run_polling()

if __name__ == "__main__":
    main()