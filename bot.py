import telebot
import mysql.connector
from telebot.types import Message
from datetime import datetime, timedelta

# Variabili di configurazione
BOT_TOKEN = ""  # Da impostare nelle variabili della VPS
CHANNEL_ID = "-1002297768070"  # ID del canale
SUPREME_ADMIN = 7839114402  # ID del capo supremo

bot = telebot.TeleBot(BOT_TOKEN)

# Configurazione database
db_config = {
    "host": "mysql.railway.internal",
    "user": "root",
    "password": "BpwzWzXkJkSAdmoYdWdSfLRVobOHYQNa",
    "database": "railway",
    "port": 3306
}

# Connessione al database
def get_db_connection():
    return mysql.connector.connect(**db_config)

def execute_query(query, params=()):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    conn.commit()
    return cursor.fetchall()

# Inizializzazione database
execute_query("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    request_time DATETIME,
    approved BOOLEAN DEFAULT FALSE
);
""")
execute_query("""
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255)
);
""")

# Funzione per verificare se un utente è admin
def is_admin(user_id):
    result = execute_query("SELECT * FROM admins WHERE user_id = %s", (user_id,))
    return len(result) > 0 or user_id == SUPREME_ADMIN

# Funzione per aggiungere admin
def add_admin(user_id, username):
    execute_query("REPLACE INTO admins (user_id, username) VALUES (%s, %s)", (user_id, username))

# Comando /start
@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Anonimo"
    
    # Controlla se c'è già una richiesta pendente
    result = execute_query("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if result:
        bot.reply_to(message, "Hai già una richiesta in sospeso.")
        return

    # Inserisce la richiesta nel database
    execute_query("INSERT INTO users (user_id, username, request_time) VALUES (%s, %s, %s)",
                  (user_id, username, datetime.now()))

    bot.reply_to(message, "⏰ La tua richiesta per unirti al canale è stata mandata. Un amministratore ti approverà/rifiuterà il prima possibile.")

    # Notifica agli admin
    admins = execute_query("SELECT user_id FROM admins")
    for admin in admins:
        bot.send_message(admin['user_id'], f"❗️{username} ({user_id}) ha richiesto di unirsi al canale.")

# Comando /admin (solo per il capo supremo)
@bot.message_handler(commands=['admin'])
def admin_handler(message: Message):
    if message.from_user.id != SUPREME_ADMIN:
        bot.reply_to(message, "Non hai i permessi per eseguire questo comando.")
        return

    try:
        _, identifier = message.text.split(maxsplit=1)
        user_id = int(identifier) if identifier.isdigit() else None
        username = identifier if not user_id else None

        if user_id:
            add_admin(user_id, None)
            bot.reply_to(message, f"L'utente con ID {user_id} è stato aggiunto come amministratore.")
        elif username:
            add_admin(None, username)
            bot.reply_to(message, f"L'utente {username} è stato aggiunto come amministratore.")
        else:
            bot.reply_to(message, "Formato non valido. Usa: /admin {username} oppure {userID}")
    except ValueError:
        bot.reply_to(message, "Formato non valido. Usa: /admin {username} oppure {userID}")

# Comando /approve
@bot.message_handler(commands=['approve'])
def approve_handler(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Non hai i permessi per eseguire questo comando.")
        return

    try:
        _, identifier = message.text.split(maxsplit=1)
        user_id = int(identifier) if identifier.isdigit() else None
        
        result = execute_query("SELECT * FROM users WHERE user_id = %s AND approved = FALSE", (user_id,))
        if not result:
            bot.reply_to(message, "Nessuna richiesta in sospeso per questo utente.")
            return

        # Genera link temporaneo
        link = bot.create_chat_invite_link(CHANNEL_ID, member_limit=1, expire_date=int((datetime.now() + timedelta(seconds=60)).timestamp()))

        # Aggiorna stato utente
        execute_query("UPDATE users SET approved = TRUE WHERE user_id = %s", (user_id,))
        username = result[0]['username']

        # Notifica
        bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {link.invite_link}")

        admins = execute_query("SELECT user_id FROM admins")
        for admin in admins:
            bot.send_message(admin['user_id'], f"🚨 {username} è stato approvato.")
    except ValueError:
        bot.reply_to(message, "Formato non valido. Usa: /approve {userID}")

# Comando /deny
@bot.message_handler(commands=['deny'])
def deny_handler(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Non hai i permessi per eseguire questo comando.")
        return

    try:
        args = message.text.split(maxsplit=2)
        identifier = args[1]
        motivo = args[2] if len(args) > 2 else "Nessun motivo specificato."
        user_id = int(identifier) if identifier.isdigit() else None

        result = execute_query("SELECT * FROM users WHERE user_id = %s AND approved = FALSE", (user_id,))
        if not result:
            bot.reply_to(message, "Nessuna richiesta in sospeso per questo utente.")
            return

        username = result[0]['username']

        # Rimuove richiesta
        execute_query("DELETE FROM users WHERE user_id = %s", (user_id,))

        # Notifica
        bot.send_message(user_id, f"❌ La tua richiesta è stata rifiutata.\n\n❓ Motivo: {motivo}")
        admins = execute_query("SELECT user_id FROM admins")
        for admin in admins:
            bot.send_message(admin['user_id'], f"🚨 La richiesta di {username} è stata rifiutata.")
    except ValueError:
        bot.reply_to(message, "Formato non valido. Usa: /deny {userID} {motivo}")

# Comando /approveall
@bot.message_handler(commands=['approveall'])
def approve_all_handler(message: Message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Non hai i permessi per eseguire questo comando.")
        return

    pending_users = execute_query("SELECT * FROM users WHERE approved = FALSE")
    if not pending_users:
        bot.reply_to(message, "Non ci sono richieste in sospeso.")
        return

    for user in pending_users:
        user_id = user['user_id']
        username = user['username']

        # Genera link temporaneo
        link = bot.create_chat_invite_link(CHANNEL_ID, member_limit=1, expire_date=int((datetime.now() + timedelta(seconds=60)).timestamp()))

        # Aggiorna stato utente
        execute_query("UPDATE users SET approved = TRUE WHERE user_id = %s", (user_id,))

        # Notifica
        bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {link.invite_link}")

    admins = execute_query("SELECT user_id FROM admins")
    for admin in admins:
        bot.send_message(admin['user_id'], "⚡️ Tutte le richieste sono state approvate.")

# Avvia il bot
bot.polling(none_stop=True)
