import os
import json
import gspread
import requests as req

from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials

TOKEN = os.getenv("TOKEN")
PAYPAL_USER = os.getenv("PAYPAL_USER")
SHEET_ID = os.getenv("SHEET_ID")
RENDER_URL = os.getenv("RENDER_URL")
PORT = int(os.getenv("PORT", 10000))
API = f"https://api.telegram.org/bot{TOKEN}"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.getenv("GOOGLE_CREDS_JSON")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet_products = client.open_by_key(SHEET_ID).worksheet("PRODUCTS")
sheet_sales = client.open_by_key(SHEET_ID).worksheet("SALES")

carts = {}
cart_message_ids = {}  # salva l'id del messaggio carrello per ogni utente
flask_app = Flask(__name__)


# ── Telegram helpers ──────────────────────────────────────────────

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = req.post(f"{API}/sendMessage", data=data)
    return r.json()


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    req.post(f"{API}/editMessageText", data=data)


def delete_message(chat_id, message_id):
    req.post(f"{API}/deleteMessage", data={"chat_id": chat_id, "message_id": message_id})


def answer_callback(callback_id, text=""):
    req.post(f"{API}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text})


# ── Google Sheets helpers ─────────────────────────────────────────

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
        product, qty, price, total
    ])


def get_cart(user_id):
    if user_id not in carts:
        carts[user_id] = {}
    return carts[user_id]


# ── Cart helpers ──────────────────────────────────────────────────

def build_cart_text(cart, products):
    if not cart:
        return "🛒 *CARRELLO*\n\nIl carrello è vuoto"
    total = 0
    text = "🛒 *CARRELLO*\n\n"
    for pid, qty in cart.items():
        p = products[pid]
        subtotal = p["price"] * qty
        total += subtotal
        text += f"• *{p['name']}* x{qty} = {subtotal:.2f}€\n"
    text += f"\n💰 *Totale: {total:.2f}€*"
    return text, total


def build_cart_keyboard(total):
    return {
        "inline_keyboard": [
            [{"text": f"💳 Paga con PayPal {total:.2f}€", "callback_data": f"paypal_{int(total*100)}"}],
            [{"text": "🔙 Torna al catalogo", "callback_data": "catalogo"}]
        ]
    }


def update_cart_message(chat_id, user_id, products):
    cart = get_cart(user_id)
    result = build_cart_text(cart, products)

    if isinstance(result, tuple):
        text, total = result
        keyboard = build_cart_keyboard(total)
    else:
        text = result
        keyboard = {"inline_keyboard": [[{"text": "🔙 Torna al catalogo", "callback_data": "catalogo"}]]}

    # Aggiorna o crea il messaggio carrello
    if user_id in cart_message_ids:
        edit_message(chat_id, cart_message_ids[user_id], text, keyboard)
    else:
        r = send_message(chat_id, text, keyboard)
        if r.get("ok"):
            cart_message_ids[user_id] = r["result"]["message_id"]


# ── Handlers ──────────────────────────────────────────────────────

def handle_start(chat_id, user_id):
    try:
        # Resetta il messaggio carrello salvato
        if user_id in cart_message_ids:
            del cart_message_ids[user_id]

        products = get_products()
        text = "🛍️ *CATALOGO*\n\n"
        keyboard = {"inline_keyboard": []}

        for pid, p in products.items():
            text += f"*{p['name']}*\n💰 {p['price']}€ | 📦 Stock: {p['stock']}\n\n"
            keyboard["inline_keyboard"].append([
                {"text": f"➕ {p['name']}", "callback_data": f"add_{pid}"},
                {"text": "➖ Rimuovi", "callback_data": f"remove_{pid}"}
            ])

        keyboard["inline_keyboard"].append([
            {"text": "🛒 Vedi Carrello", "callback_data": "cart"}
        ])

        send_message(chat_id, text, keyboard)
        print("Catalogo inviato!", flush=True)
    except Exception as e:
        print(f"ERRORE handle_start: {e}", flush=True)
        send_message(chat_id, f"Errore: {e}")


def handle_callback(callback_query):
    query_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    user_id = callback_query["from"]["id"]
    data = callback_query["data"]
    cart = get_cart(user_id)
    products = get_products()

    if data.startswith("add_"):
        pid = int(data.split("_")[1])
        if products[pid]["stock"] <= 0:
            answer_callback(query_id, "Prodotto esaurito ❌")
            return
        cart[pid] = cart.get(pid, 0) + 1
        update_stock(pid, products[pid]["stock"] - 1)
        answer_callback(query_id, f"✅ {products[pid]['name']} aggiunto!")
        update_cart_message(chat_id, user_id, products)

    elif data.startswith("remove_"):
        pid = int(data.split("_")[1])
        if cart.get(pid, 0) > 0:
            cart[pid] -= 1
            update_stock(pid, products[pid]["stock"] + 1)
            if cart[pid] <= 0:
                del cart[pid]
            answer_callback(query_id, "Rimosso dal carrello")
            update_cart_message(chat_id, user_id, products)
        else:
            answer_callback(query_id, "Non hai questo prodotto nel carrello ❌")

    elif data == "cart":
        answer_callback(query_id)
        update_cart_message(chat_id, user_id, products)

    elif data.startswith("paypal_"):
        answer_callback(query_id)
        total = int(data.split("_")[1]) / 100
        paypal_url = f"https://www.paypal.me/{PAYPAL_USER}/{total:.2f}"
        # Manda link PayPal e messaggio conferma separato
        send_message(chat_id, 
            f"💳 *Clicca qui per pagare {total:.2f}€ su PayPal:*\n{paypal_url}\n\n"
            f"Dopo aver pagato clicca il bottone qui sotto 👇",
            {"inline_keyboard": [
                [{"text": "✅ Ho pagato → Conferma Ordine", "callback_data": "confirm"}]
            ]}
        )

    elif data == "confirm":
        answer_callback(query_id)
        if not cart:
            answer_callback(query_id, "Il carrello è vuoto ❌")
            return
        total = 0
        for pid, qty in cart.items():
            p = products[pid]
            subtotal = p["price"] * qty
            total += subtotal
            save_sale(p["name"], qty, p["price"], subtotal)
        carts[user_id] = {}
        if user_id in cart_message_ids:
            del cart_message_ids[user_id]
        edit_message(chat_id, message_id, f"✅ *Ordine confermato!*\n\nTotale: {total:.2f}€\n\nGrazie mille! 🎉")

    elif data == "catalogo":
        answer_callback(query_id)
        handle_start(chat_id, user_id)


# ── Flask routes ──────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return "Bot attivo ✅", 200


@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)

        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")
            if text == "/start":
                handle_start(chat_id, user_id)

        elif "callback_query" in update:
            handle_callback(update["callback_query"])

    except Exception as e:
        print(f"ERRORE: {e}", flush=True)

    return jsonify({"ok": True})


print("BOT AVVIATO ✅")

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)