import telebot
from telebot.types import Message
import mysql.connector
import time
import threading

# Variabile per il token del bot
BOT_TOKEN = ""  # Da impostare nelle variabili della VPS
bot = telebot.TeleBot(BOT_TOKEN)

# Dati di connessione al database MySQL
DB_CONFIG = {
    "host": "mysql.railway.internal",
    "user": "root",
    "password": "BpwzWzXkJkSAdmoYdWdSfLRVobOHYQNa",
    "database": "railway",
    "port": 3306
}

SUPER_ADMIN = 7839114402
PENDING_REQUESTS = {}  # Dizionario temporaneo per gestire le richieste

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def add_admin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO admins (user_id) VALUES (%s)", (user_id,))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def notify_admins(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    conn.close()
    for admin in admins:
        bot.send_message(admin[0], message)

def generate_temp_link():
    return f"https://t.me/joinchat/{int(time.time())}"  # Simulazione del link

@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "[N/A]"

    if user_id in PENDING_REQUESTS:
        bot.reply_to(message, "Hai già richiesto l'accesso. Attendi una risposta.")
        return

    PENDING_REQUESTS[user_id] = username
    bot.reply_to(message, "\u23F0 La tua richiesta per unirti al canale è stata mandata. Un amministratore ti approverà/rifiuterà il prima possibile.")
    notify_admins(f"❗️@{username} ({user_id}) ha richiesto di unirsi al canale.")

@bot.message_handler(commands=['admin'])
def handle_admin(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return

    try:
        _, identifier = message.text.split(maxsplit=1)
        add_admin(identifier)
        bot.reply_to(message, f"@{identifier} è stato aggiunto come amministratore.")
    except Exception as e:
        bot.reply_to(message, "Errore nell'aggiunta dell'amministratore.")

@bot.message_handler(commands=['approve'])
def handle_approve(message: Message):
    try:
        _, identifier = message.text.split(maxsplit=1)
        user_id = int(identifier) if identifier.isdigit() else None

        if user_id is None:
            for uid, uname in PENDING_REQUESTS.items():
                if uname == identifier:
                    user_id = uid
                    break

        if user_id not in PENDING_REQUESTS:
            bot.reply_to(message, "Richiesta non trovata.")
            return

        username = PENDING_REQUESTS.pop(user_id)
        temp_link = generate_temp_link()
        bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {temp_link}")
        notify_admins(f"🚨@{username} ({user_id}) è stato approvato.")
    except Exception as e:
        bot.reply_to(message, "Errore durante l'approvazione.")

@bot.message_handler(commands=['deny'])
def handle_deny(message: Message):
    try:
        _, identifier, *reason = message.text.split()
        reason = " ".join(reason) if reason else "Nessun motivo specificato."
        user_id = int(identifier) if identifier.isdigit() else None

        if user_id is None:
            for uid, uname in PENDING_REQUESTS.items():
                if uname == identifier:
                    user_id = uid
                    break

        if user_id not in PENDING_REQUESTS:
            bot.reply_to(message, "Richiesta non trovata.")
            return

        username = PENDING_REQUESTS.pop(user_id)
        bot.send_message(user_id, f"❌ La tua richiesta è stata rifiutata.\n\n❓ Motivo: {reason}")
        notify_admins(f"🚨 La richiesta di @{username} ({user_id}) è stata rifiutata.")
    except Exception as e:
        bot.reply_to(message, "Errore durante il rifiuto.")

@bot.message_handler(commands=['approveall'])
def handle_approve_all(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        for user_id, username in list(PENDING_REQUESTS.items()):
            temp_link = generate_temp_link()
            bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {temp_link}")
            notify_admins(f"🚨@{username} ({user_id}) è stato approvato.")
            del PENDING_REQUESTS[user_id]

        notify_admins("⚡️ Tutte le richieste sono state approvate.")
    except Exception as e:
        bot.reply_to(message, "Errore durante l'approvazione di massa.")

def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()
    bot.infinity_polling()
