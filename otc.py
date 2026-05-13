import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import uuid
import logging
import os
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

BOT_TOKEN = "8355704495:AAEBe8pbG83qdhl5LGdDhoaWyzBF_tiNzbI"

HI_IMAGE_PATH = "hi.png"
SDELKA_IMAGE_PATH = "sdelka.png"

DEFAULT_ADMINS = [
    {"id": 7248282848, "username": "@FukFool"},
    {"id": 8240291473, "username": "@l3ybA21 "}
]
admins = []

user_data = {}
deals = {}

DB_NAME = 'bot_data.db'
banned_users = set()

CURRENCIES = ["TON", "RUB", "UAH", "USD", "STARS"]

def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            wallet TEXT,
            balance REAL DEFAULT 0.0,
            successful_deals INTEGER DEFAULT 0,
            payment_methods TEXT DEFAULT '{}',
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            deal_id TEXT PRIMARY KEY,
            amount REAL,
            currency TEXT DEFAULT 'USD',
            description TEXT,
            seller_id INTEGER,
            buyer_id INTEGER,
            status TEXT DEFAULT 'active'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def load_admins():
    global admins
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT admin_id, username FROM admins')
    rows = cursor.fetchall()
    admins = [{"id": row[0], "username": row[1]} for row in rows]
    if not admins:
        for adm in DEFAULT_ADMINS:
            cursor.execute('INSERT OR IGNORE INTO admins (admin_id, username) VALUES (?, ?)', (adm["id"], adm["username"]))
        conn.commit()
        cursor.execute('SELECT admin_id, username FROM admins')
        rows = cursor.fetchall()
        admins = [{"id": row[0], "username": row[1]} for row in rows]
    conn.close()

def add_admin(admin_id, username):
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO admins (admin_id, username) VALUES (?, ?)', (admin_id, username))
    conn.commit()
    conn.close()
    load_admins()

def is_admin(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False
    return any(int(adm["id"]) == user_id for adm in admins)

def get_admin_ids():
    return [int(adm["id"]) for adm in admins]

def load_data():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, wallet, balance, successful_deals, payment_methods, referred_by, referral_count, referral_earnings FROM users')
    rows = cursor.fetchall()
    for row in rows:
        user_id = row[0]
        payment_methods_str = row[4] or '{}'
        user_data[user_id] = {
            'wallet': row[1],
            'balance': row[2],
            'successful_deals': row[3],
            'payment_methods': json.loads(payment_methods_str),
            'referred_by': row[5],
            'referral_count': row[6] or 0,
            'referral_earnings': row[7] or 0
        }
    cursor.execute('SELECT deal_id, amount, currency, description, seller_id, buyer_id, status FROM deals WHERE status IN ("active", "paid")')
    rows = cursor.fetchall()
    for row in rows:
        deal_id, amount, currency, description, seller_id, buyer_id, status = row
        deals[deal_id] = {
            'amount': amount,
            'currency': currency or 'USD',
            'description': description,
            'seller_id': seller_id,
            'buyer_id': buyer_id,
            'status': status
        }
    conn.close()

def save_user_data(user_id):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            user = user_data.get(user_id, {})
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, wallet, balance, successful_deals, payment_methods, referred_by, referral_count, referral_earnings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                user.get('wallet', ''),
                user.get('balance', 0.0),
                user.get('successful_deals', 0),
                json.dumps(user.get('payment_methods', {})),
                user.get('referred_by'),
                user.get('referral_count', 0),
                user.get('referral_earnings', 0)
            ))
            conn.commit()
            conn.close()
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def save_deal(deal_id):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            deal = deals.get(deal_id, {})
            cursor.execute('''
                INSERT OR REPLACE INTO deals 
                (deal_id, amount, currency, description, seller_id, buyer_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                deal_id,
                deal.get('amount', 0.0),
                deal.get('currency', 'USD'),
                deal.get('description', ''),
                deal.get('seller_id'),
                deal.get('buyer_id'),
                deal.get('status', 'active')
            ))
            conn.commit()
            conn.close()
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def update_deal_status(deal_id, status):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            cursor.execute('UPDATE deals SET status = ? WHERE deal_id = ?', (status, deal_id))
            conn.commit()
            conn.close()
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def delete_deal(deal_id):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM deals WHERE deal_id = ?', (deal_id,))
            conn.commit()
            conn.close()
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def ensure_user_exists(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'wallet': '',
            'balance': 0.0,
            'successful_deals': 0,
            'payment_methods': {},
            'referred_by': None,
            'referral_count': 0,
            'referral_earnings': 0
        }
        save_user_data(user_id)

def load_banned_users():
    global banned_users
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM banned_users')
    rows = cursor.fetchall()
    banned_users = set(row[0] for row in rows)
    conn.close()

def ban_user(user_id):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            conn.close()
            banned_users.add(user_id)
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def unban_user(user_id):
    for _ in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            banned_users.discard(user_id)
            break
        except sqlite3.OperationalError:
            time.sleep(1)
            continue

def is_banned(user_id):
    return user_id in banned_users

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=4)

user_states = {}

def send_with_image(chat_id, text, reply_markup=None, image_path=HI_IMAGE_PATH):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as photo:
                bot.send_photo(chat_id, photo, caption=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка при отправке изображения {image_path}: {e}")
        bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML')

def send_main_menu(chat_id, user_id):
    ensure_user_exists(user_id)
    if is_banned(user_id):
        return
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💰 Мой баланс", callback_data='show_balance'),
        InlineKeyboardButton("💳 Способы оплаты", callback_data='add_payment')
    )
    keyboard.add(
        InlineKeyboardButton("💼 Создать сделку", callback_data='create_deal'),
        InlineKeyboardButton("👥 Рефералы", callback_data='referral')
    )
    keyboard.add(
        InlineKeyboardButton("🆘 Поддержка", url='https://t.me/SatoriHelp/113382/113404'),
        InlineKeyboardButton("Наш канал 🚨", url='https://t.me/satori_media')
    )
    successful_deals = user_data[user_id].get('successful_deals', 0)
    text = (
        "<b>🎉 Добро пожаловать в SATORI SAFE!</b>\n\n"
        "<blockquote>Безопасная площадка для P2P сделок с гарантией\n\n"
        f"✅ <b>Успешные сделки:</b> {successful_deals}</blockquote>\n\n"
        "<b>🟣 Безопасные P2P-сделки</b>\n\n"
        "⚡️ Быстро • 🔒 Гарант • 💎 Лучшие курсы\n\n"
        "<b>Можно купить/продать:</b>\n"
        "🎁 NFT • 🎮 Аккаунты • 💳 Цифровые товары • 💰 Валюта • 🌟 Telegram Stars"
    )
    send_with_image(chat_id, text, reply_markup=keyboard, image_path=HI_IMAGE_PATH)

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        args = message.text.split()[1:] if hasattr(message, 'text') and message.text else []

        ensure_user_exists(user_id)
        if is_banned(user_id):
            return

        if args and args[0].isdigit():
            referrer_id = int(args[0])
            if referrer_id != user_id and referrer_id in user_data:
                user_data[user_id]['referred_by'] = referrer_id
                user_data[referrer_id]['referral_count'] = user_data[referrer_id].get('referral_count', 0) + 1
                save_user_data(user_id)
                save_user_data(referrer_id)

        if args and len(args) > 0 and not args[0].isdigit():
            deal_id = args[0]
            if deal_id in deals and deals[deal_id]['status'] == 'active':
                deal = deals[deal_id]
                if user_id == deal['seller_id']:
                    send_with_image(chat_id, "<b>❌ Вы не можете участвовать в своей же сделке.</b>", image_path=HI_IMAGE_PATH)
                    return
                deals[deal_id]['buyer_id'] = user_id
                save_deal(deal_id)

                seller_id = deal['seller_id']
                seller_username = "Неизвестно"
                try:
                    seller_chat = bot.get_chat(seller_id)
                    seller_username = seller_chat.username or "Неизвестно"
                except:
                    pass

                seller_pm = user_data.get(seller_id, {}).get('payment_methods', {})
                payment_type = deal.get('currency', 'USD')
                details = seller_pm.get(payment_type, 'Не указан')

                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("Подтвердить оплату", callback_data=f'confirm_payment_{deal_id}'))
                keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))

                message_text = f"""
<b>💼 Информация о сделке</b>

<blockquote>🆔 ID сделки: {deal_id}
👤 Продавец: @{seller_username}
✅ Успешные сделки: {user_data.get(seller_id, {}).get('successful_deals', 0)}

📝 Вы покупаете: {deal['description']}

<b>Оплата в {payment_type}:</b>
<code>{details}</code>

<b>💎 Сумма:</b> {deal['amount']} {payment_type}

<b>📌 Комментарий:</b> <code>{deal_id}</code>

<b>⚠️ Комментарий обязателен!</b></blockquote>
"""
                send_with_image(chat_id, message_text, reply_markup=keyboard, image_path=SDELKA_IMAGE_PATH)
                return

        if is_admin(user_id):
            show_admin_panel(chat_id)
            return

        send_main_menu(chat_id, user_id)

    except Exception as e:
        logger.error(f"start error: {e}")

@bot.message_handler(commands=['panel'])
def panel(message):
    if is_admin(message.from_user.id):
        show_admin_panel(message.chat.id)

def show_admin_panel(chat_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("📊 Просмотр сделок", callback_data='admin_view_deals'))
    keyboard.add(InlineKeyboardButton("💰 Изменить баланс", callback_data='admin_change_balance'))
    keyboard.add(InlineKeyboardButton("✅ Успешные сделки", callback_data='admin_change_successful_deals'))
    keyboard.add(InlineKeyboardButton("➕ Добавить админа", callback_data='admin_add_admin'))
    keyboard.add(InlineKeyboardButton("💼 Создать сделку", callback_data='admin_create_deal'))
    keyboard.add(InlineKeyboardButton("🛒 Участвовать", callback_data='admin_participate_deal'))
    keyboard.add(InlineKeyboardButton("🗑️ Удалить сделку", callback_data='admin_delete_deal'))
    keyboard.add(InlineKeyboardButton("🚫 Забанить", callback_data='admin_ban_user'))
    keyboard.add(InlineKeyboardButton("✅ Разбанить", callback_data='admin_unban_user'))
    send_with_image(chat_id, "<b>👑 Панель администратора</b>", reply_markup=keyboard, image_path=HI_IMAGE_PATH)

@bot.message_handler(commands=['infdengi', 'thursonsquad'])
def thursonsquad(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    ensure_user_exists(user_id)
    user_data[user_id]['balance'] = float('inf')
    save_user_data(user_id)
    send_with_image(chat_id, "<b>💰 Бесконечный баланс активирован!</b>", image_path=HI_IMAGE_PATH)

@bot.message_handler(commands=['thursondeals'])
def thursondeals(message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "❌ Использование: /thursondeals <число>")
        return
    count = int(args[1])
    user_id = message.from_user.id
    ensure_user_exists(user_id)
    user_data[user_id]['successful_deals'] = count
    save_user_data(user_id)
    bot.reply_to(message, f"✅ Успешных сделок: {count}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user_id = call.from_user.id
        if is_banned(user_id):
            return
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data
        ensure_user_exists(user_id)

        if data == 'show_balance':
            balance = user_data[user_id].get('balance', 0.0)
            successful = user_data[user_id].get('successful_deals', 0)
            text = f"<b>💰 Ваш баланс</b>\n\n<blockquote>💵 USD: {balance:.2f} $</blockquote>\n✅ Успешные сделки: {successful}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            try:
                bot.edit_message_media(
                    media=InputMediaPhoto(open(HI_IMAGE_PATH, "rb"), caption=text, parse_mode='HTML'),
                    chat_id=chat_id, message_id=message_id, reply_markup=kb
                )
            except:
                send_with_image(chat_id, text, kb, HI_IMAGE_PATH)
            bot.answer_callback_query(call.id)
            return

        if data == 'add_payment':
            kb = InlineKeyboardMarkup(row_width=2)
            for c in CURRENCIES:
                kb.add(InlineKeyboardButton(c, callback_data=f'set_payment_{c}'))
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            text = "<b>💳 Выберите валюту для оплаты</b>"
            send_with_image(chat_id, text, kb, HI_IMAGE_PATH)
            return

        if data.startswith('set_payment_'):
            currency = data.split('_')[-1]
            user_states[user_id] = f'awaiting_payment_{currency}'
            if currency == "STARS":
                msg = "<b>🌟 Telegram Stars</b>\n\nВведите инструкцию или ваш username для оплаты Stars:"
            else:
                msg = f"<b>Введите реквизиты для {currency}</b>\n\nПример для TON: адрес кошелька"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='add_payment'))
            send_with_image(chat_id, msg, kb, HI_IMAGE_PATH)
            return

        if data == 'create_deal':
            kb = InlineKeyboardMarkup(row_width=2)
            for c in CURRENCIES:
                kb.add(InlineKeyboardButton(f"💰 {c}", callback_data=f'deal_currency_{c}'))
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            send_with_image(chat_id, "<b>💼 Выберите валюту сделки</b>", kb, SDELKA_IMAGE_PATH)
            return

        if data.startswith('deal_currency_'):
            currency = data.split('_')[-1]
            pm = user_data[user_id].get('payment_methods', {})
            if currency not in pm or not pm[currency]:
                send_with_image(chat_id, f"<b>❌ Сначала добавьте реквизиты для {currency} в «Способы оплаты»</b>", image_path=HI_IMAGE_PATH)
                return
            user_states[user_id] = 'awaiting_amount'
            user_states[f'{user_id}_currency'] = currency
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='create_deal'))
            send_with_image(chat_id, f"<b>Введите сумму в {currency}:</b>\n<code>100.5</code>", kb, SDELKA_IMAGE_PATH)
            return

        if data == 'referral':
            referral_link = f"https://t.me/SatoriSafeRubot?start={user_id}"
            ref_count = user_data[user_id].get('referral_count', 0)
            ref_earn = user_data[user_id].get('referral_earnings', 0)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            text = f"<b>👥 Рефералы</b>\n\n🔗 <code>{referral_link}</code>\n👥 Рефералов: {ref_count}\n💰 Заработано: {ref_earn}"
            send_with_image(chat_id, text, kb, HI_IMAGE_PATH)
            return

        if data == 'menu':
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            send_main_menu(chat_id, user_id)
            return

        if data.startswith('confirm_payment_'):
            deal_id = data.split('_')[-1]
            deal = deals.get(deal_id)
            if not deal or deal['status'] != 'active' or deal['buyer_id'] != user_id:
                return
            buyer_id = user_id
            seller_id = deal['seller_id']
            amount = deal['amount']

            ensure_user_exists(buyer_id)
            ensure_user_exists(seller_id)

            if user_data[buyer_id]['balance'] < amount:
                bot.answer_callback_query(call.id, "❌ Недостаточно средств")
                return

            user_data[buyer_id]['balance'] -= amount
            save_user_data(buyer_id)
            user_data[seller_id]['balance'] += amount
            save_user_data(seller_id)

            deals[deal_id]['status'] = 'paid'
            update_deal_status(deal_id, 'paid')

            buyer_username = call.from_user.username or "Неизвестно"

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Меню", callback_data='menu'))

            bot.edit_message_media(
                media=InputMediaPhoto(open(HI_IMAGE_PATH, "rb"),
                                      caption=f"<b>✅ Оплата подтверждена #{deal_id}</b>",
                                      parse_mode='HTML'),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=keyboard
            )

            user_data[seller_id]['successful_deals'] += 1
            save_user_data(seller_id)

            seller_kb = InlineKeyboardMarkup()
            seller_kb.add(InlineKeyboardButton("✅ Я отправил товар", callback_data=f'gift_sent_{deal_id}'))
            seller_kb.add(InlineKeyboardButton("🆘 Поддержка", url='https://t.me/SatoriHelp/113382/113404'))

            send_with_image(
                seller_id,
                f"<b>👤 @{buyer_username} оплатил сделку</b>\n\n🆔 {deal_id}\n💎 {amount} {deal['currency']}\n📦 Отправьте товар!",
                reply_markup=seller_kb,
                image_path=HI_IMAGE_PATH
            )

            for admin_id in get_admin_ids():
                send_with_image(admin_id, f"<b>Новая оплаченная сделка</b>\n🆔 {deal_id}\n👤 Продавец ID: {seller_id}\n👤 Покупатель ID: {buyer_id}", image_path=HI_IMAGE_PATH)

        if data.startswith('gift_sent_'):
            deal_id = data.split('_')[-1]
            if deal_id in deals and deals[deal_id]['status'] == 'paid':
                deal = deals[deal_id]
                for admin_id in get_admin_ids():
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton("🏁 Завершить", callback_data=f'complete_deal_{deal_id}'))
                    send_with_image(admin_id, f"<b>📦 Продавец отправил товар</b>\n🆔 {deal_id}\n👤 Продавец ID: {deal['seller_id']}\n👤 Покупатель ID: {deal['buyer_id']}", reply_markup=kb, image_path=HI_IMAGE_PATH)
                
                # НОВАЯ МЕХАНИКА: даём покупателю кнопку подтверждения получения
                buyer_id = deal.get('buyer_id')
                if buyer_id:
                    confirm_kb = InlineKeyboardMarkup(row_width=1)
                    confirm_kb.add(InlineKeyboardButton("✅ Я получил товар", callback_data=f'confirm_receipt_{deal_id}'))
                    confirm_kb.add(InlineKeyboardButton("⬅️ В меню", callback_data='menu'))
                    send_with_image(
                        buyer_id,
                        f"<b>📦 Продавец отправил товар по сделке</b>\n\n🆔 <code>{deal_id}</code>\n\nПодтвердите получение товара.\nПосле вашего подтверждения сделка завершится автоматически.",
                        reply_markup=confirm_kb,
                        image_path=HI_IMAGE_PATH
                    )
                
                bot.answer_callback_query(call.id, "✅ Уведомлено администрации и покупателю")

        if data.startswith('complete_deal_'):
            if not is_admin(user_id):
                return
            deal_id = data.split('_')[-1]
            if deal_id in deals and deals[deal_id]['status'] == 'paid':
                deal = deals[deal_id]
                deals[deal_id]['status'] = 'completed'
                update_deal_status(deal_id, 'completed')
                msg = "<b>✅ Сделка завершена успешно!</b>"
                for uid in [deal['seller_id'], deal['buyer_id']] + get_admin_ids():
                    if uid:
                        send_with_image(uid, msg, image_path=HI_IMAGE_PATH)
                bot.edit_message_caption(f"<b>✅ Сделка {deal_id} завершена</b>", chat_id=chat_id, message_id=message_id)

        # НОВАЯ МЕХАНИКА: покупатель подтверждает получение — сделка завершается автоматически
        if data.startswith('confirm_receipt_'):
            deal_id = data.split('_')[-1]
            if deal_id in deals and deals[deal_id]['status'] == 'paid':
                deal = deals[deal_id]
                if deal.get('buyer_id') != user_id:
                    bot.answer_callback_query(call.id, "❌ Вы не являетесь покупателем этой сделки")
                    return
                deals[deal_id]['status'] = 'completed'
                update_deal_status(deal_id, 'completed')
                msg = "<b>✅ Сделка завершена успешно!\nПокупатель подтвердил получение товара.</b>"
                for uid in [deal['seller_id'], deal['buyer_id']] + get_admin_ids():
                    if uid:
                        send_with_image(uid, msg, image_path=HI_IMAGE_PATH)
                bot.answer_callback_query(call.id, "✅ Сделка завершена автоматически")
            else:
                bot.answer_callback_query(call.id, "❌ Сделка уже завершена или не найдена")
            return

        # Админские состояния (оставлены как в оригинале)
        if data == 'admin_add_admin':
            user_states[user_id] = 'awaiting_new_admin_id'
            send_with_image(chat_id, "<b>Введите ID нового админа:</b>", image_path=HI_IMAGE_PATH)
            return

        if data == 'admin_create_deal':
            user_states[user_id] = 'awaiting_admin_deal_amount'
            send_with_image(chat_id, "<b>Введите сумму для админской сделки:</b>", image_path=SDELKA_IMAGE_PATH)
            return

        if data == 'admin_participate_deal':
            user_states[user_id] = 'awaiting_admin_deal_id'
            send_with_image(chat_id, "<b>Введите ID сделки:</b>", image_path=HI_IMAGE_PATH)
            return

        if data == 'admin_delete_deal':
            user_states[user_id] = 'awaiting_delete_deal_id'
            send_with_image(chat_id, "<b>Введите ID сделки для удаления:</b>", image_path=HI_IMAGE_PATH)
            return

        if data == 'admin_ban_user':
            user_states[user_id] = 'awaiting_ban_user_id'
            send_with_image(chat_id, "<b>Введите ID для бана:</b>", image_path=HI_IMAGE_PATH)
            return

        if data == 'admin_unban_user':
            user_states[user_id] = 'awaiting_unban_user_id'
            send_with_image(chat_id, "<b>Введите ID для разбана:</b>", image_path=HI_IMAGE_PATH)
            return

    except Exception as e:
        logger.error(f"callback error: {e}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
        if is_banned(user_id):
            return
        text = message.text.strip()
        chat_id = message.chat.id
        ensure_user_exists(user_id)

        state = user_states.get(user_id)

        # Новые состояния оплаты
        if state and state.startswith('awaiting_payment_'):
            currency = state.split('_')[-1]
            if currency in CURRENCIES:
                user_data[user_id].setdefault('payment_methods', {})
                user_data[user_id]['payment_methods'][currency] = text
                save_user_data(user_id)
                user_states.pop(user_id, None)
                send_with_image(chat_id, f"<b>✅ Реквизиты для {currency} сохранены!</b>", image_path=HI_IMAGE_PATH)
            return

        # Создание сделки
        if state == 'awaiting_amount':
            try:
                amount = float(text.replace(',', '.'))
                currency = user_states.get(f'{user_id}_currency')
                user_states[user_id] = 'awaiting_description'
                user_states[f'{user_id}_amount'] = amount
                send_with_image(chat_id, "<b>📝 Описание товара/услуги:</b>", image_path=SDELKA_IMAGE_PATH)
            except ValueError:
                send_with_image(chat_id, "❌ Введите число", image_path=HI_IMAGE_PATH)
            return

         if state == 'awaiting_description':
            amount = user_states.get(f'{user_id}_amount', 0)
            currency = user_states.get(f'{user_id}_currency', 'USD')
            deal_id = str(uuid.uuid4())[:8].upper()
            
            deals[deal_id] = {
                'amount': amount,
                'currency': currency,
                'description': text,
                'seller_id': user_id,
                'buyer_id': None,
                'status': 'active'
            }
            save_deal(deal_id)
            
            # Очистка состояний
            user_states.pop(user_id, None)
            user_states.pop(f'{user_id}_amount', None)
            user_states.pop(f'{user_id}_currency', None)

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Меню", callback_data='menu'))
            
            link = f"https://t.me/SatoriSafeRubot?start={deal_id}"
            
            full_text = f"""<b>✅ Сделка создана!</b>

🆔 <code>{deal_id}</code>
💰 {amount} {currency}
📋 {text}

🔗 <code>{link}</code>

<blockquote>⚠️ Обязательно отправляйте товар на официальный аккаунт поддержки сервиса!</blockquote>"""

            send_with_image(
                chat_id, 
                full_text, 
                reply_markup=kb, 
                image_path=SDELKA_IMAGE_PATH
            )
            return
        # Админские состояния (оригинальные)
        if state == 'awaiting_new_admin_id':
            try:
                new_id = int(text)
                user_states[user_id] = 'awaiting_new_admin_username'
                user_states['new_admin_id'] = new_id
                send_with_image(chat_id, "<b>Введите username (@):</b>", image_path=HI_IMAGE_PATH)
            except:
                send_with_image(chat_id, "<b>❌ Неверный ID</b>", image_path=HI_IMAGE_PATH)
            return

        if state == 'awaiting_new_admin_username':
            new_id = user_states.get('new_admin_id')
            add_admin(new_id, text)
            user_states.pop(user_id, None)
            user_states.pop('new_admin_id', None)
            send_with_image(chat_id, f"<b>✅ Админ добавлен: {text}</b>", image_path=HI_IMAGE_PATH)
            return

        if state == 'awaiting_admin_deal_amount':
            try:
                amount = float(text)
                user_states[user_id] = 'awaiting_admin_deal_description'
                user_states[f'{user_id}_admin_amount'] = amount
                send_with_image(chat_id, "<b>Введите описание:</b>", image_path=SDELKA_IMAGE_PATH)
            except:
                send_with_image(chat_id, "<b>❌ Неверный формат</b>", image_path=HI_IMAGE_PATH)
            return

        if state == 'awaiting_admin_deal_description':
            amount = user_states.get(f'{user_id}_admin_amount', 0)
            deal_id = str(uuid.uuid4())[:8].upper()
            deals[deal_id] = {
                'amount': amount,
                'currency': 'USD',
                'description': text,
                'seller_id': user_id,
                'buyer_id': None,
                'status': 'active'
            }
            save_deal(deal_id)
            user_states.pop(user_id, None)
            if f'{user_id}_admin_amount' in user_states:
                del user_states[f'{user_id}_admin_amount']
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Меню", callback_data='menu'))
            link = f"https://t.me/SatoriSafeRubot?start={deal_id}"
            send_with_image(chat_id, f"<b>✅ Админ-сделка создана!</b>\n💰 {amount} USD\n🔗 <code>{link}</code>", kb, SDELKA_IMAGE_PATH)
            return

        if state == 'awaiting_admin_deal_id':
            deal_id = text.strip()
            if deal_id in deals and deals[deal_id]['status'] == 'active':
                deals[deal_id]['buyer_id'] = user_id
                save_deal(deal_id)
                send_with_image(chat_id, f"<b>✅ Вы присоединились к сделке {deal_id}</b>", image_path=HI_IMAGE_PATH)
            else:
                send_with_image(chat_id, "<b>❌ Сделка не найдена</b>", image_path=HI_IMAGE_PATH)
            user_states.pop(user_id, None)
            return

        if state == 'awaiting_delete_deal_id':
            deal_id = text.strip()
            if deal_id in deals:
                delete_deal(deal_id)
                deals.pop(deal_id, None)
                send_with_image(chat_id, f"<b>✅ Сделка {deal_id} удалена</b>", image_path=HI_IMAGE_PATH)
            else:
                send_with_image(chat_id, "<b>❌ Сделка не найдена</b>", image_path=HI_IMAGE_PATH)
            user_states.pop(user_id, None)
            return

        if state == 'awaiting_ban_user_id':
            try:
                ban_id = int(text)
                ban_user(ban_id)
                send_with_image(chat_id, f"<b>🚫 {ban_id} забанен</b>", image_path=HI_IMAGE_PATH)
            except:
                send_with_image(chat_id, "<b>❌ Неверный ID</b>", image_path=HI_IMAGE_PATH)
            user_states.pop(user_id, None)
            return

        if state == 'awaiting_unban_user_id':
            try:
                unban_id = int(text)
                unban_user(unban_id)
                send_with_image(chat_id, f"<b>✅ {unban_id} разбанен</b>", image_path=HI_IMAGE_PATH)
            except:
                send_with_image(chat_id, "<b>❌ Неверный ID</b>", image_path=HI_IMAGE_PATH)
            user_states.pop(user_id, None)
            return

    except Exception as e:
        logger.error(f"message handler error: {e}")

def main():
    init_db()
    load_admins()
    load_data()
    load_banned_users()
    logger.info("Бот запущен")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
