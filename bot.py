import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading

TOKEN = "7394722114:AAEcxc3HKVxAtUoYFEMzm_K1kKvTuTQ7MLM"
NOWPAYMENTS_API_KEY = "319RDCY-V5AMDRP-ND9TYR8-X3YNWWT"
bot = telebot.TeleBot(TOKEN)

user_data = {}
ADMIN_IDS = [7839114402, 7768881599]

prefix_prices = {
    "+39": 5.0,
    "+1": 3.0,
    "+44": 4.0,
    "+7": 6.0,
    "+62": 2.5,
    "+212": 3.5,
    "+880": 4.0,
}

def generate_ltc_address(user_id, amount):
    url = "https://api.nowpayments.io/v1/payment"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}
    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "pay_currency": "ltc",
        "ipn_callback_url": "https://your-callback-url.com",
        "order_id": f"user_{user_id}_{int(time.time())}",
        "order_description": f"Ricarica di {amount}€"
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        result = response.json()
        return result.get("pay_address"), result.get("payment_id")
    return None, None

def check_payment(user_id, payment_id, amount):
    url = f"https://api.nowpayments.io/v1/payment/{payment_id}"
    headers = {"x-api-key": NOWPAYMENTS_API_KEY}
    
    for _ in range(288):  # 288 iterazioni da 5 minuti (totale: 24 ore)
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            payment_data = response.json()
            print(payment_data)  # Debug: stampa la risposta API
            
            payment_status = payment_data.get("payment_status")
            price_currency = payment_data.get("price_currency", "EUR")
            
            if price_currency != "EUR":
                paid_amount = payment_data.get("price_amount", 0)  # Usa l'importo in EUR
            else:
                paid_amount = payment_data.get("paid_amount", 0)

            if payment_status == "finished":
                user_data[user_id]["balance"] += paid_amount
                bot.send_message(user_id, f"✅ Il tuo pagamento di {paid_amount}€ è stato ricevuto con successo!\n💰 Il tuo saldo attuale è: {user_data[user_id]['balance']}€.")
                return
            elif payment_status == "partial_payment":
                bot.send_message(user_id, f"⚠️ Pagamento parziale. Hai inviato {paid_amount}€, ne mancano {amount - paid_amount}€.")
        
        time.sleep(300)  # Aspetta 5 minuti prima del prossimo controllo
    
    bot.send_message(user_id, "⏳ Non è stato ricevuto un pagamento entro 24 ore. Contatta il supporto se hai pagato.")

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛍 Compra", callback_data="compra"))
    markup.add(InlineKeyboardButton("💳 Ricarica saldo", callback_data="ricarica"))
    bot.send_message(message.chat.id, "✨ Benvenuto! Usa i pulsanti per gestire gli acquisti.", reply_markup=markup)
    
    if message.chat.id not in user_data:
        user_data[message.chat.id] = {"balance": 0, "waiting_for_amount": False}

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    if call.data == "compra":
        markup = InlineKeyboardMarkup()
        for prefix in prefix_prices:
            markup.add(InlineKeyboardButton(prefix, callback_data=f"prefix_{prefix}"))
        bot.send_message(chat_id, "📞 Scegli il prefisso VoIP:", reply_markup=markup)
    
    elif call.data.startswith("prefix_"):
        prefix = call.data.split("_")[1]
        price = prefix_prices.get(prefix, 0)
        
        if user_data[chat_id]["balance"] >= price:
            user_data[chat_id]["balance"] -= price
            bot.delete_message(chat_id, call.message.message_id)
            bot.send_message(chat_id, f"✅ VoIP {prefix} acquistato con successo!\n💰 Saldo rimanente: {user_data[chat_id]['balance']}€")
        else:
            bot.send_message(chat_id, "❌ Saldo insufficiente. Ricarica con /ricarica.")
    
    elif call.data == "ricarica":
        user_data[chat_id]["waiting_for_amount"] = True
        bot.send_message(chat_id, "💵 Inserisci l'importo da ricaricare (minimo 3€):")

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get("waiting_for_amount", False))
def handle_amount(message):
    chat_id = message.chat.id
    try:
        amount = float(message.text)
        if amount < 1:
            bot.send_message(chat_id, "⚠️ L'importo deve essere almeno 3€.")
            return
        
        ltc_address, payment_id = generate_ltc_address(chat_id, amount)
        if ltc_address:
            bot.send_message(chat_id, f"💰 Invia {amount}€ in LTC a questo indirizzo:\n{ltc_address}", parse_mode="Markdown")
            threading.Thread(target=check_payment, args=(chat_id, payment_id, amount)).start()
        else:
            bot.send_message(chat_id, "❌ Errore nella generazione dell'indirizzo di pagamento.")
    
    except ValueError:
        bot.send_message(chat_id, "❌ Inserisci un numero valido.")
    
    user_data[chat_id]["waiting_for_amount"] = False

@bot.message_handler(commands=['balance'])
def balance(message):
    saldo = user_data.get(message.chat.id, {}).get("balance", 0)
    bot.send_message(message.chat.id, f"💰 Saldo attuale: {saldo}€")

bot.polling(none_stop=True)
