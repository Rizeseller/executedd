import os
import sqlite3
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging
from datetime import datetime, timedelta

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE = "bot_database.sqlite"
SUPER_ADMIN = 7839114402
PENDING_REQUESTS = {}

def setup_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

def add_admin(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def notify_admins(context, message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    conn.close()
    for admin in admins:
        context.bot.send_message(chat_id=admin[0], text=message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "[N/A]"

    if user_id in PENDING_REQUESTS:
        await update.message.reply_text("Hai già richiesto l'accesso. Attendi una risposta.")
        return

    PENDING_REQUESTS[user_id] = username
    await update.message.reply_text(
        "⏰ La tua richiesta per unirti al canale è stata mandata. "
        "Un amministratore ti approverà/rifiuterà il prima possibile."
    )
    notify_admins(
        context,
        f"❗️@{username} ({user_id}) ha richiesto di unirsi al canale."
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usa il comando con: /admin {UserID}")
        return

    user_id = context.args[0]
    if user_id.isdigit():
        add_admin(int(user_id))
        await update.message.reply_text(f"L'utente {user_id} è stato aggiunto come amministratore.")
    else:
        await update.message.reply_text("ID utente non valido.")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usa il comando con: /approve {UserID}")
        return

    user_id = int(context.args[0]) if context.args[0].isdigit() else None
    if user_id not in PENDING_REQUESTS:
        await update.message.reply_text("Richiesta non trovata.")
        return

    username = PENDING_REQUESTS.pop(user_id)
    invite_link = f"https://t.me/joinchat/{datetime.now().timestamp()}"  # Simulazione
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ La tua richiesta è stata approvata.\n\n📎 > {invite_link}"
    )
    notify_admins(context, f"🚨@{username} ({user_id}) è stato approvato.")

async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usa il comando con: /deny {UserID} {motivo opzionale}")
        return

    user_id = int(context.args[0]) if context.args[0].isdigit() else None
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo specificato."

    if user_id not in PENDING_REQUESTS:
        await update.message.reply_text("Richiesta non trovata.")
        return

    username = PENDING_REQUESTS.pop(user_id)
    await context.bot.send_message(
        chat_id=user_id,
        text=f"❌ La tua richiesta è stata rifiutata.\n\n❓ Motivo: {reason}"
    )
    notify_admins(context, f"🚨 La richiesta di @{username} ({user_id}) è stata rifiutata.")

async def approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    for user_id, username in list(PENDING_REQUESTS.items()):
        invite_link = f"https://t.me/joinchat/{datetime.now().timestamp()}"  # Simulazione
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ La tua richiesta è stata approvata.\n\n📎 > {invite_link}"
        )
        notify_admins(context, f"🚨@{username} ({user_id}) è stato approvato.")
        del PENDING_REQUESTS[user_id]

    notify_admins(context, "⚡️ Tutte le richieste sono state approvate.")

if __name__ == "__main__":
    setup_database()
    app = ApplicationBuilder().token("7203175973:AAGGPJnAezqG6iaXYrX_chmreYwBxUYwbwI").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("deny", deny))
    app.add_handler(CommandHandler("approveall", approve_all))

    app.run_polling()
