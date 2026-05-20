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
flask_app = Flask(__name__)


# ── Telegram helpers ──────────────────────────────────────────────

def send_photo(chat_id, photo, caption, reply_markup=None):
    data = {"chat_id": chat_id, "photo": photo, "caption": caption}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    req.post(f"{API}/sendPhoto", data=data)


def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    req.post(f"{API}/sendMessage", data=data)


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    req.post(f"{API}/editMessageText", data=data)


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


# ── Keyboard builders ─────────────────────────────────────────────

def product_keyboard(pid):
    return {
        "inline_keyboard": [
            [
                {"text": "➕ Aggiungi", "callback_data": f"add_{pid}"},
                {"text": "➖ Rimuovi", "callback_data": f"remove_{pid}"}
            ],
            [{"text": "🛒 Carrello", "callback_data": "cart"}]
        ]
    }


def cart_keyboard(total):
    return {
        "inline_keyboard": [
            [{"text": "💳 Paga PayPal", "url": f"https://www.paypal.me/{PAYPAL_USER}/{total:.2f}"}],
            [{"text": "✅ Conferma Ordine", "callback_data": "confirm"}]
        ]
    }


# ── Handlers ──────────────────────────────────────────────────────

def handle_start(chat_id):
    try:
        print("Leggo prodotti da Google Sheets...", flush=True)
        products = get_products()
        print(f"Prodotti trovati: {products}", flush=True)
        for pid, p in products.items():
            print(f"Invio prodotto {pid}...", flush=True)
            send_photo(
                chat_id,
                p["img"],
                f"{p['name']}\n💰 {p['price']}€\n📦 Stock: {p['stock']}",
                product_keyboard(pid)
            )
            print(f"Prodotto {pid} inviato!", flush=True)
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
        answer_callback(query_id, "Aggiunto al carrello ✅")

    elif data.startswith("remove_"):
        pid = int(data.split("_")[1])
        if cart.get(pid, 0) > 0:
            cart[pid] -= 1
            update_stock(pid, products[pid]["stock"] + 1)
            if cart[pid] <= 0:
                del cart[pid]
        answer_callback(query_id, "Rimosso dal carrello")

    elif data == "cart":
        answer_callback(query_id)
        total = 0
        if not cart:
            text = "🛒 CARRELLO\n\nIl carrello è vuoto"
            edit_message(chat_id, message_id, text)
        else:
            text = "🛒 CARRELLO\n\n"
            for pid, qty in cart.items():
                p = products[pid]
                subtotal = p["price"] * qty
                total += subtotal
                text += f"{p['name']} x{qty} = {subtotal:.2f}€\n"
            text += f"\nTotale: {total:.2f}€"
            edit_message(chat_id, message_id, text, cart_keyboard(total))

    elif data == "confirm":
        answer_callback(query_id)
        total = 0
        for pid, qty in cart.items():
            p = products[pid]
            subtotal = p["price"] * qty
            total += subtotal
            save_sale(p["name"], qty, p["price"], subtotal)
        carts[user_id] = {}
        edit_message(chat_id, message_id, f"✅ Ordine confermato!\n\nTotale: {total:.2f}€")


# ── Flask routes ──────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return "Bot attivo ✅", 200


@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        print(f"UPDATE RICEVUTO: {update}", flush=True)

        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            print(f"MESSAGGIO: {text} da {chat_id}", flush=True)
            if text == "/start":
                handle_start(chat_id)

        elif "callback_query" in update:
            handle_callback(update["callback_query"])

    except Exception as e:
        print(f"ERRORE: {e}", flush=True)

    return jsonify({"ok": True})


print("BOT AVVIATO ✅")

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)