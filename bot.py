import telebot
import mysql.connector
from datetime import datetime, timedelta
import time

# Dati di connessione al bot
API_TOKEN = '7203175973:AAGGPJnAezqG6iaXYrX_chmreYwBxUYwbwI'
bot = telebot.TeleBot(API_TOKEN)

# Dati di connessione al database
db_config = {
    'user': 'root',
    'password': 'BpwzWzXkJkSAdmoYdWdSfLRVobOHYQNa',
    'host': 'mysql.railway.internal',
    'database': 'railway',
    'port': 3306
}

# Connessione al database MySQL
def connect_db():
    return mysql.connector.connect(**db_config)

# Funzione per inviare un messaggio agli amministratori
def notify_admins(message):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    connection.close()

    for admin in admins:
        bot.send_message(admin[0], message)

# Aggiungi un amministratore (solo per il capo supremo)
@bot.message_handler(commands=['admin'])
def add_admin(message):
    if message.from_user.id == 7839114402:  # Solo il capo supremo può aggiungere amministratori
        username_or_id = message.text.split()[1]
        connection = connect_db()
        cursor = connection.cursor()
        
        if username_or_id.isdigit():
            user_id = int(username_or_id)
            cursor.execute("INSERT INTO admins (user_id) VALUES (%s)", (user_id,))
        else:
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (username_or_id,))
            user = cursor.fetchone()
            if user:
                cursor.execute("INSERT INTO admins (user_id) VALUES (%s)", (user[0],))
            else:
                bot.reply_to(message, "Utente non trovato.")
                return
        
        connection.commit()
        connection.close()
        bot.reply_to(message, "Amministratore aggiunto con successo.")

# Gestione della richiesta di unione al canale
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Controlla se l'utente ha già richiesto l'accesso
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM requests WHERE user_id = %s", (user_id,))
    existing_request = cursor.fetchone()
    
    if existing_request:
        bot.reply_to(message, "Hai già inviato una richiesta di adesione e sei in attesa di approvazione.")
        connection.close()
        return
    
    # Invia la richiesta di unione
    cursor.execute("INSERT INTO requests (user_id, username, timestamp) VALUES (%s, %s, %s)", 
                   (user_id, username, datetime.now()))
    connection.commit()
    connection.close()
    
    bot.reply_to(message, " ⏰ La tua richiesta per unirti al canale è stata mandata. Un amministratore ti approverà/rifiuterà il prima possibile.")
    
    # Notifica agli amministratori
    notify_admins(f"❗️{username} ({user_id}) ha richiesto di unirsi al canale.")

# Gestione dell'approvazione
@bot.message_handler(commands=['approve'])
def approve(message):
    if message.from_user.id != 7839114402:  # Solo il capo supremo può approvare
        bot.reply_to(message, "Non hai i permessi per eseguire questa azione.")
        return
    
    # Estrai l'ID o username dell'utente
    parts = message.text.split()
    username_or_id = parts[1]
    user_id = None
    
    # Trova l'ID dell'utente
    connection = connect_db()
    cursor = connection.cursor()
    
    if username_or_id.isdigit():
        user_id = int(username_or_id)
    else:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username_or_id,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
    
    if not user_id:
        bot.reply_to(message, "Utente non trovato.")
        connection.close()
        return
    
    # Verifica che l'utente abbia richiesto l'accesso
    cursor.execute("SELECT * FROM requests WHERE user_id = %s", (user_id,))
    request = cursor.fetchone()
    
    if not request:
        bot.reply_to(message, "Nessuna richiesta trovata per questo utente.")
        connection.close()
        return
    
    # Crea il link temporaneo
    link = f"https://t.me/joinchat/{-1002297768070}?invite_code={user_id}"
    
    # Invia il link all'utente
    bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {link}")
    
    # Notifica gli amministratori
    notify_admins(f"🚨 {username_or_id} è stato approvato.")
    
    # Elimina la richiesta
    cursor.execute("DELETE FROM requests WHERE user_id = %s", (user_id,))
    connection.commit()
    connection.close()

# Gestione del rifiuto
@bot.message_handler(commands=['deny'])
def deny(message):
    if message.from_user.id != 7839114402:  # Solo il capo supremo può rifiutare
        bot.reply_to(message, "Non hai i permessi per eseguire questa azione.")
        return
    
    # Estrai l'ID o username dell'utente
    parts = message.text.split()
    username_or_id = parts[1]
    user_id = None
    reason = 'Nessun motivo fornito.'
    
    if len(parts) > 2:
        reason = ' '.join(parts[2:])
    
    # Trova l'ID dell'utente
    connection = connect_db()
    cursor = connection.cursor()
    
    if username_or_id.isdigit():
        user_id = int(username_or_id)
    else:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username_or_id,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
    
    if not user_id:
        bot.reply_to(message, "Utente non trovato.")
        connection.close()
        return
    
    # Verifica che l'utente abbia richiesto l'accesso
    cursor.execute("SELECT * FROM requests WHERE user_id = %s", (user_id,))
    request = cursor.fetchone()
    
    if not request:
        bot.reply_to(message, "Nessuna richiesta trovata per questo utente.")
        connection.close()
        return
    
    # Invia la notifica di rifiuto
    bot.send_message(user_id, f"❌ La tua richiesta è stata rifiutata.\n\n❓ motivo: {reason}")
    
    # Notifica gli amministratori
    notify_admins(f"🚨 La richiesta di {username_or_id} è stata rifiutata.\nMotivo: {reason}")
    
    # Elimina la richiesta
    cursor.execute("DELETE FROM requests WHERE user_id = %s", (user_id,))
    connection.commit()
    connection.close()

# Comando /approveall per approvare tutte le richieste
@bot.message_handler(commands=['approveall'])
def approve_all(message):
    if message.from_user.id != 7839114402:  # Solo il capo supremo può approvare tutte le richieste
        bot.reply_to(message, "Non hai i permessi per eseguire questa azione.")
        return
    
    connection = connect_db()
    cursor = connection.cursor()
    
    cursor.execute("SELECT user_id, username FROM requests")
    requests = cursor.fetchall()
    
    for request in requests:
        user_id, username = request
        # Crea il link temporaneo
        link = f"https://t.me/joinchat/{-1002297768070}?invite_code={user_id}"
        bot.send_message(user_id, f"✅ La tua richiesta è stata approvata.\n\n📎 > {link}")
        
        # Notifica gli amministratori
        notify_admins(f"🚨 {username} è stato approvato.")
        
        # Elimina la richiesta
        cursor.execute("DELETE FROM requests WHERE user_id = %s", (user_id,))
    
    connection.commit()
    connection.close()
    
    bot.reply_to(message, "⚡️ Tutte le richieste sono state approvate.")

# Avvio del bot
bot.polling(none_stop=True)
