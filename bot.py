import os
import telebot
import ffmpeg
import uuid
import json
import logging
import psycopg
from elevenlabs.client import ElevenLabs
from elevenlabs import save, VoiceSettings
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from lib import *

logging.basicConfig(filename='audiobot.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

callback_data_store = {}

config = json.loads(open("config.json").read())
msgs = json.loads(open("messages.json", encoding="utf8").read())

client = ElevenLabs(api_key=config['elevenlabs'], timeout=100000)

db = psycopg.connect(host=config['db']['host'], user=config['db']['user'], password=config['db']['password'], dbname=config['db']['dbname'])

bot = telebot.TeleBot(config['tg'])

def get_voice(id):
    voices = config['voices']
    for voice in voices:
        if voice['id'] == id:
            return voice
    return None

def generate_keyboard(text):
    voices = config['voices']
    keyboard = []
    unique_id = str(uuid.uuid4())
    callback_data_store[unique_id] = text

    row = []
    for i, voice in enumerate(voices):
        button = InlineKeyboardButton(voice["display_name"], callback_data=voice["id"] + unique_id)
        row.append(button)
        if len(row) == 2 or i == len(voices) - 1:
            keyboard.append(row)
            row = []
    return InlineKeyboardMarkup(keyboard)

def tastiera(message):
    lang = message.from_user.language_code
    guide = config['guide'] if lang == "it" else config['guideEN']
    messages = msgs['it'] if lang == "it" else msgs['en']
    return InlineKeyboardMarkup([[InlineKeyboardButton(text=messages['guide'], url=guide),
                                  InlineKeyboardButton(text=messages['contact'], url='https://t.me/m/m7MjReLaNmRh')]])

def gen_audio(text, voice, model):
    audio = client.generate(text=text, voice=voice, model=model)
    name = str(uuid.uuid4())
    save(audio, name + ".mp3")
    ffmpeg.input(name + ".mp3").output(name + ".ogg", codec='libopus').run()
    os.remove(name + ".mp3")
    return name + ".ogg"

@bot.message_handler(commands=['start'])
def start(message):
    ID = message.chat.id
    log(message, "ha avviato il bot")
    if get_user(ID, db) is None:
        create_user(message)
    else:
        update_user(message)
    bot.send_message(ID, "Benvenuto!", reply_markup=tastiera(message))

@bot.message_handler(commands=['setquota', 'addquota', 'getinfo', 'users', 'tokensADMIN', 'sendmsg', 'redeem', 'genlicense', 'getlicense'])
def admin_commands(message):
    if message.chat.id not in config['admins']:
        return
    bot.send_message(message.chat.id, "Comando amministrativo ricevuto!")

@bot.message_handler(func=lambda message: True)
def gen(message):
    try:
        ID = message.chat.id
        if get_user(ID, db) is None:
            create_user(message)
        else:
            update_user(message)
        msg = message.text
        if msg.startswith("/"):
            return
        remaining = get_quota(ID, db) - get_usage(ID, db)
        if remaining < len(msg):
            bot.send_message(ID, "⚠️Caratteri insufficienti")
            return
        keyboard = generate_keyboard(msg)
        bot.send_message(ID, "Scegli una voce:", reply_markup=keyboard)
    except Exception as e:
        print(e)

@bot.callback_query_handler(func=lambda call: True)
def voice_selected(call):
    try:
        voice_id = call.data[0]
        msg = callback_data_store[call.data[1:]]
        del callback_data_store[call.data[1:]]
        mm = bot.send_message(call.message.chat.id, "Generazione in corso...")
        voice = get_voice(voice_id)
        file = gen_audio(msg, voice['name'], voice['model'])
        with open(file, 'rb') as audio:
            bot.send_audio(call.message.chat.id, audio)
        os.remove(file)
        bot.delete_message(call.message.chat.id, mm.message_id)
    except Exception as e:
        print(e)

bot.polling()
