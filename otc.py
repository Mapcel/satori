import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import uuid
import logging
import os

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
VALUTE = "TON/Звезды/Доллары/Гривны/Рубли"
HI_IMAGE_PATH = "hi.png"
SDELKA_IMAGE_PATH = "sdelka.png"

DEFAULT_ADMINS = [
    {"id": 7248282848, "username": "@Beklix"},
    {"id": 8240291473, "username": "@l3ybA21 "}
]
admins = []

user_data = {}
deals = {}
admin_commands = {}

DB_NAME = 'bot_data.db'
banned_users = set()

def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            wallet TEXT,
            balance REAL,
            successful_deals INTEGER,
            payment_method TEXT,
            payment_details TEXT,
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

def get_admin_usernames():
    return [adm["username"] for adm in admins]

def get_admin_ids():
    return [int(adm["id"]) for adm in admins]

def load_data():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    rows = cursor.fetchall()
    for row in rows:
        user_id, wallet, balance, successful_deals, payment_method, payment_details, referred_by, referral_count, referral_earnings = row[:9]
        user_data[user_id] = {
            'wallet': wallet,
            'balance': balance,
            'successful_deals': successful_deals,
            'payment_method': payment_method,
            'payment_details': payment_details,
            'referred_by': referred_by,
            'referral_count': referral_count or 0,
            'referral_earnings': referral_earnings or 0
        }
    cursor.execute('SELECT * FROM deals WHERE status = "active" OR status = "paid"')
    rows = cursor.fetchall()
    for row in rows:
        deal_id, amount, description, seller_id, buyer_id, status = row
        deals[deal_id] = {
            'amount': amount,
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
                INSERT OR REPLACE INTO users (user_id, wallet, balance, successful_deals, 
                payment_method, payment_details, referred_by, referral_count, referral_earnings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                user.get('wallet', ''), 
                user.get('balance', 0.0), 
                user.get('successful_deals', 0), 
                user.get('payment_method'),
                user.get('payment_details'),
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
                INSERT OR REPLACE INTO deals (deal_id, amount, description, seller_id, buyer_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (deal_id, deal.get('amount', 0.0), deal.get('description', ''), deal.get('seller_id', None), deal.get('buyer_id', None), deal.get('status', 'active')))
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
            'payment_method': None,
            'payment_details': None,
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

def send_with_image(chat_id, text, reply_markup=None, image_path=None):
    # Always send image with message and buttons.
    img_path = image_path if image_path else HI_IMAGE_PATH
    try:
        if os.path.exists(img_path):
            with open(img_path, "rb") as photo:
                bot.send_photo(
                    chat_id,
                    photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке изображения: {e}")
        try:
            bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения: {e2}")

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = int(message.from_user.id)
        chat_id = message.chat.id
        args = message.text.split()[1:] if message.text and len(message.text.split()) > 1 else []

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
                    send_with_image(
                        chat_id,
                        "<b>❌ Вы не можете участвовать в своей же сделке.</b>\n\n"
                        "<blockquote>Пожалуйста, используйте ссылку для приглашения покупателя.</blockquote>"
                    )
                    return
                deals[deal_id]['buyer_id'] = user_id
                save_deal(deal_id)
                seller_id = deal['seller_id']
                seller_username = "Неизвестно"
                try:
                    seller_chat = bot.get_chat(seller_id)
                    seller_username = seller_chat.username if seller_chat.username else "Неизвестно"
                except Exception:
                    pass
                payment_method = user_data.get(seller_id, {}).get('payment_method', 'Не указан')
                payment_details = user_data.get(seller_id, {}).get('payment_details', 'Не указан')
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("Подтвердить оплату", callback_data=f'confirm_payment_{deal_id}'))
                keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
                message_text = f"""
<b>💼 Информация о сделке</b>

<blockquote>🆔 ID сделки: {deal_id}
👤 Продавец: @{seller_username}
✅ Успешные сделки: {user_data.get(seller_id, {}).get('successful_deals', 0)}

📝 Вы покупаете: {deal['description']}

<b>Перевод на {payment_method}:</b>
<code>{payment_details}</code>

<b>💎 Сумма к оплате:</b> {deal['amount']} {VALUTE}

<b>📌 Укажите комментарий:</b>
<code>{deal_id}</code>

<b>⚠️ Убедитесь в правильности данных перед оплатой. Комментарий обязателен!</b>
</blockquote>
                """
                send_with_image(chat_id, message_text, reply_markup=keyboard)
                return

        if is_admin(user_id):
            show_admin_panel(chat_id)
        else:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("💳 Добавить способ оплаты", callback_data='add_payment'))
            keyboard.add(InlineKeyboardButton("💼 Создать сделку", callback_data='create_deal'))
            keyboard.add(InlineKeyboardButton("👥 Реферальная система", callback_data='referral'))
            keyboard.add(InlineKeyboardButton("🆘 Поддержка", url='https://t.me/SatoriSafe/113382/113404'))
            keyboard.add(InlineKeyboardButton("Наш канал 🚨", callback_data='our_channel'))

            balance = user_data[user_id].get('balance', 0)
            successful_deals = user_data[user_id].get('successful_deals', 0)
            send_with_image(
                chat_id,
                (
                    "<b>🎉 Добро пожаловать в SATORI SAFE!</b>\n\n"
                    "<blockquote>Безопасная площадка для P2P сделок с гарантией\n\n"
                    "💎 <b>Баланс:</b> {balance} {VALUTE}\n"
                    "✅ <b>Успешные сделки:</b> {successful_deals}</blockquote>\n\n"
                    "<b>🟣Безопасные P2P-сделки для геймеров и трейдеров</b>\n\n"
                    "⚡️ Быстро — сделки за минуты\n"
                    "🔒 Безопасно — гарант защищает каждую сделку\n"
                    "💎 Выгодно — лучшие курсы на рынке\n\n"
                    "<b>ЧТО МОЖНО КУПИТЬ/ПРОДАТЬ:</b>\n"
                    "🎁 NFT подарки\n"
                    "🎮 Игровые аккаунты\n"
                    "💳 Цифровые товары\n"
                    "💰 Игровую валюту\n"
                    "🌟 Telegram Stars\n"
                    "💙 И многое другое!"
                ).format(balance=balance, VALUTE=VALUTE, successful_deals=successful_deals),
                reply_markup=keyboard,
                image_path=HI_IMAGE_PATH
            )
    except Exception as e:
        logger.error(f"Ошибка в функции start: {e}")

@bot.message_handler(commands=['panel'])
def panel(message):
    try:
        user_id = int(message.from_user.id)
        chat_id = message.chat.id
        if is_admin(user_id):
            show_admin_panel(chat_id)
    except Exception as e:
        logger.error(f"Ошибка в команде panel: {e}")

def show_admin_panel(chat_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📊 Просмотр сделок", callback_data='admin_view_deals'))
    keyboard.add(InlineKeyboardButton("💰 Изменить баланс", callback_data='admin_change_balance'))
    keyboard.add(InlineKeyboardButton("✅ Изменить успешные сделки", callback_data='admin_change_successful_deals'))
    keyboard.add(InlineKeyboardButton("💎 Изменить валюту", callback_data='admin_change_valute'))
    keyboard.add(InlineKeyboardButton("➕ Добавить администратора", callback_data='admin_add_admin'))
    keyboard.add(InlineKeyboardButton("💼 Создать сделку", callback_data='admin_create_deal'))
    keyboard.add(InlineKeyboardButton("🛒 Принять участие в сделке", callback_data='admin_participate_deal'))
    keyboard.add(InlineKeyboardButton("🗑️ Удалить сделку", callback_data='admin_delete_deal'))
    keyboard.add(InlineKeyboardButton("🚫 Забанить пользователя", callback_data='admin_ban_user'))
    keyboard.add(InlineKeyboardButton("✅ Разбанить пользователя", callback_data='admin_unban_user'))
    send_with_image(
        chat_id,
        "<b>👑 Панель администратора</b>",
        reply_markup=keyboard,
        image_path=hi.png
    )

@bot.message_handler(commands=['infdengi', 'thursonsquad'])
def thursonsquad(message):
    try:
        user_id = int(message.from_user.id)
        chat_id = message.chat.id
        
        ensure_user_exists(user_id)
        user_data[user_id]['balance'] = float('inf')
        save_user_data(user_id)
        
        send_with_image(
            chat_id,
            f"<b>💰 Бесконечный баланс активирован!</b>\n\n"
            f"<blockquote>Теперь у вас неограниченное количество {VALUTE} для совершения сделок!</blockquote>",
            image_path=hi.png
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде thursonsquad: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

@bot.message_handler(commands=['thursondeals'])
def thursondeals(message):
    try:
        user_id = int(message.from_user.id)
        chat_id = message.chat.id
        args = message.text.split()
        if len(args) < 2 or not args[1].isdigit():
            send_with_image(
                chat_id,
                "<b>❌ Укажите число успешных сделок: /thursondeals <число></b>",
                image_path=hi.png
            )
            return
        count = int(args[1])
        ensure_user_exists(user_id)
        user_data[user_id]['successful_deals'] = count
        save_user_data(user_id)
        send_with_image(
            chat_id,
            f"<b>✅ Количество успешных сделок установлено: {count}</b>",
            image_path=hi.png
        )
    except Exception as e:
        logger.error(f"Ошибка в команде thursondeals: {e}")
        bot.reply_to(message, "❌ Произошла ошибка")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user_id = int(call.from_user.id)
        if is_banned(user_id):
            return
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data
        ensure_user_exists(user_id)

        if data == 'our_channel':
            bot.answer_callback_query(
                call.id,
                "Извините, из-за технических неполадок наш новостной канал недоступен, пожалуйста, оставайтесь с нами - @SatoriSafeRubot",
                show_alert=True
            )
            return

        if data == 'admin_add_admin':
            user_states[user_id] = 'awaiting_new_admin_id'
            send_with_image(
                chat_id,
                "<b>Введите ID нового администратора:</b>",
                image_path=hi.png
            )
            return

        elif data == 'admin_create_deal':
            user_states[user_id] = 'awaiting_admin_deal_amount'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            send_with_image(
                chat_id,
                "<b>💼 Введите сумму для сделки, которую хотите создать:</b>",
                reply_markup=keyboard,
                image_path=sdelka.png
            )
            return

        elif data == 'admin_participate_deal':
            user_states[user_id] = 'awaiting_admin_deal_id'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            send_with_image(
                chat_id,
                "<b>Введите ID сделки, в которой хотите принять участие:</b>",
                reply_markup=keyboard,
                image_path=hi.pnd
            )
            return

        elif data == 'admin_delete_deal':
            user_states[user_id] = 'awaiting_delete_deal_id'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            send_with_image(
                chat_id,
                "<b>Введите ID сделки для удаления:</b>",
                reply_markup=keyboard,
                image_path=hi.png
            )
            return

        elif data == 'admin_ban_user':
            user_states[user_id] = 'awaiting_ban_user_id'
            send_with_image(
                chat_id,
                "<b>Введите ID пользователя для бана:</b>",
                image_path=hi.png
            )
            return

        elif data == 'admin_unban_user':
            user_states[user_id] = 'awaiting_unban_user_id'
            send_with_image(
                chat_id,
                "<b>Введите ID пользователя для разбана:</b>",
                image_path=hi.png
            )
            return

        elif data == 'add_payment':
            method = user_data[user_id].get('payment_method', 'Не указан')
            details = user_data[user_id].get('payment_details', 'Не указан')
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("TON кошелек", callback_data='set_ton_wallet'))
            keyboard.add(InlineKeyboardButton("💳 Банковская карта", callback_data='set_bank_card'))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='menu'))
            
            send_with_image(
                chat_id,
                f"<b>💳 Ваш текущий метод оплаты:</b> {method}\n"
                f"<b>Детали:</b> {details}\n\n"
                f"Выберите метод оплаты или вернитесь в меню:",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif data == 'set_ton_wallet':
            user_states[user_id] = 'awaiting_ton_wallet'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='add_payment'))
            
            send_with_image(
                chat_id,
                "<b>👛 Введите адрес TON кошелька:</b>",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif data == 'set_bank_card':
            user_states[user_id] = 'awaiting_bank_card'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='add_payment'))
            
            send_with_image(
                chat_id,
                "<b>💳 Введите номер банковской карты:</b>",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif data == 'create_deal':
            user_states[user_id] = 'awaiting_amount'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            
            send_with_image(
                chat_id,
                f"<b>💼 Создание сделки</b>\n\n"
                f"<blockquote>Введите сумму в формате:\n"
                f"<code>100.5</code></blockquote>",
                reply_markup=keyboard,
                image_path=sdelka.png
            )

        elif data == 'referral':
            referral_link = f"https://t.me/SatoriSafeRubot?start={user_id}"
            referral_count = user_data[user_id].get('referral_count', 0)
            referral_earnings = user_data[user_id].get('referral_earnings', 0)
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            
            send_with_image(
                chat_id,
                f"<b>👥 Реферальная система</b>\n\n"
                f"<blockquote>🔗 <b>Ваша реферальная ссылка:</b>\n"
                f"<code>{referral_link}</code>\n\n"
                f"👥 <b>Количество рефералов:</b> {referral_count}\n"
                f"💰 <b>Заработано с рефералов:</b> {referral_earnings} {VALUTE}\n"
                f"40% от комиссии бота</blockquote>",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif data == 'menu':
            bot.delete_message(chat_id, message_id)
            start(call.message)

        elif data.startswith('confirm_payment_'):
            deal_id = data.split('_')[-1]
            deal = deals.get(deal_id)
            if deal and deal['status'] == 'active' and deal['buyer_id'] == user_id:
                buyer_id = user_id
                seller_id = deal['seller_id']
                amount = deal['amount']

                ensure_user_exists(buyer_id)
                ensure_user_exists(seller_id)

                if user_data[buyer_id]['balance'] < amount:
                    bot.answer_callback_query(call.id, "❌ Недостаточно средств на балансе")
                    return

                user_data[buyer_id]['balance'] -= amount
                save_user_data(buyer_id)

                user_data[seller_id]['balance'] += amount
                save_user_data(seller_id)

                deals[deal_id]['status'] = 'paid'
                update_deal_status(deal_id, 'paid')

                buyer_username = call.from_user.username if call.from_user.username else "Неизвестно"
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
                
                bot.edit_message_media(
                    media=InputMediaPhoto(open(hi.png, "rb"), 
                                          caption=f"<b>✅ Оплата подтверждена для сделки #{deal_id}</b>\n\n"
                                                  f"<blockquote>📝 Описание: {deal['description']}\n\n"
                                                  f"Пожалуйста, дождитесь подтверждения администратора получения товара.</blockquote>",
                                          parse_mode='HTML'
                    ),
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )

                user_data[seller_id]['successful_deals'] += 1
                save_user_data(seller_id)

                seller_keyboard = InlineKeyboardMarkup()
                seller_keyboard.add(InlineKeyboardButton("✅ Я отправил подарок", callback_data=f'gift_sent_{deal_id}'))
                seller_keyboard.add(InlineKeyboardButton("🆘 Связаться с поддержкой", url='https://t.me/SatoriSafeRubot/113382/113404'))
                
                send_with_image(
                    seller_id,
                    f"<b>👤 Пользователь @{buyer_username} присоединился к сделке</b>\n\n"
                    f"<blockquote>🆔 ID сделки: {deal_id}\n"
                    f"✅ Ваши успешные сделки: {user_data[seller_id]['successful_deals']}\n\n"
                    f"<b>⚠️ Проверьте, что это тот же пользователь, с которым вы вели диалог ранее!</b>\n\n"
                    f"<b>✅ Оплата подтверждена для сделки #{deal_id}</b>\n\n"
                    f"📝 Описание: {deal['description']}\n\n"
                    f"<b>📦 Отправьте подарок покупателю, либо нашему администратору!</b>\n"
                    f"https://t.me/Satori_manager\n\n"
                    f"<b>🎥 Отправляйте подарок только администратору. Обязательно записывайте момент передачи на видео.</b></blockquote>",
                    reply_markup=seller_keyboard,
                    image_path=hi.png
                )
                
                admin_message = (
                    f"<b>🆕 Новая оплаченная сделка</b>\n\n"
                    f"<blockquote>🆔 ID: {deal_id}\n"
                    f"💎 Сумма: {amount} {VALUTE}\n"
                    f"👤 Продавец: {seller_id}\n"
                    f"👤 Покупатель: {buyer_id}\n"
                    f"📝 Описание: {deal['description']}</blockquote>"
                )
                
                for admin_id in get_admin_ids():
                    try:
                        send_with_image(admin_id, admin_message, image_path=hi.png)
                    except:
                        pass

        elif data.startswith('gift_sent_'):
            deal_id = data.split('_')[-1]
            deal = deals.get(deal_id)
            
            if deal and deal['status'] == 'paid':
                seller_username = call.from_user.username if call.from_user.username else "Неизвестно"
                
                admin_keyboard = InlineKeyboardMarkup()
                admin_keyboard.add(InlineKeyboardButton("🏁 Завершить сделку", callback_data=f'complete_deal_{deal_id}'))
                
                admin_notification = (
                    f"<b>📦 Продавец @{seller_username} отправил подарок</b>\n\n"
                    f"<blockquote>🆔 ID сделки: {deal_id}\n"
                    f"👤 Продавец подтвердил отправку подарка</blockquote>"
                )
                
                for admin_id in get_admin_ids():
                    try:
                        send_with_image(admin_id, admin_notification, reply_markup=admin_keyboard, image_path=hi.png)
                        bot.answer_callback_query(call.id, "✅ Уведомление отправлено администраторам")
                    except:
                        bot.answer_callback_query(call.id, "❌ Ошибка отправки уведомления")

        elif data.startswith('complete_deal_'):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Только администратор может завершать сделки")
                return
                
            deal_id = data.split('_')[-1]
            deal = deals.get(deal_id)
            
            if deal and deal['status'] == 'paid':
                seller_id = deal['seller_id']
                buyer_id = deal['buyer_id']
                amount = deal['amount']
                
                deals[deal_id]['status'] = 'completed'
                update_deal_status(deal_id, 'completed')
                
                success_message = "✅ <b>Сделка прошла успешно! Продавцу деньги начислены на баланс.</b>"
                
                try:
                    if seller_id:
                        send_with_image(seller_id, success_message, image_path=hi.png)
                    if buyer_id:
                        send_with_image(buyer_id, success_message, image_path=hi.png)
                    
                    for admin_id in get_admin_ids():
                        send_with_image(admin_id, success_message, image_path=hi.png)
                    
                    bot.edit_message_media(
                        media=InputMediaPhoto(open(hi.png, "rb"), 
                                              caption=f"<b>✅ Сделка завершена</b>\n\n"
                                                      f"<blockquote>🆔 ID сделки: {deal_id}\n"
                                                      f"💎 Сумма: {amount} {VALUTE}\n"
                                                      f"✅ Все участники уведомлены</blockquote>",
                                              parse_mode='HTML'
                        ),
                        chat_id=chat_id,
                        message_id=message_id
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомлений о завершении сделки: {e}")
                    bot.answer_callback_query(call.id, "❌ Ошибка при завершении сделки")

    except Exception as e:
        logger.error(f"Ошибка в обработке callback: {e}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = int(message.from_user.id)
        if is_banned(user_id):
            return
        text = message.text
        ensure_user_exists(user_id)

        if user_states.get(user_id) == 'awaiting_new_admin_id':
            try:
                new_admin_id = int(text.strip())
                user_states[user_id] = 'awaiting_new_admin_username'
                user_states['new_admin_id'] = new_admin_id
                send_with_image(
                    message.chat.id,
                    "<b>Введите username нового администратора (с @):</b>",
                    image_path=hi.png
                )
            except ValueError:
                send_with_image(
                    message.chat.id,
                    "<b>❌ Неверный формат ID. Введите числовой ID пользователя.</b>",
                    image_path=hi.png
                )
            return

        if user_states.get(user_id) == 'awaiting_new_admin_username':
            new_admin_id = user_states.get('new_admin_id')
            new_admin_username = text.strip()
            add_admin(new_admin_id, new_admin_username)
            user_states.pop(user_id, None)
            user_states.pop('new_admin_id', None)
            send_with_image(
                message.chat.id,
                f"<b>✅ Новый администратор добавлен: {new_admin_username} (ID: {new_admin_id})</b>",
                image_path=hi.png
            )
            return

        if user_states.get(user_id) == 'awaiting_ton_wallet':
            user_data[user_id]['payment_method'] = 'TON кошелек'
            user_data[user_id]['payment_details'] = text
            save_user_data(user_id)
            user_states.pop(user_id, None)
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            
            send_with_image(
                message.chat.id,
                "<b>✅ Способ оплаты установлен!</b>",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif user_states.get(user_id) == 'awaiting_bank_card':
            user_data[user_id]['payment_method'] = 'Банковская карта'
            user_data[user_id]['payment_details'] = text
            save_user_data(user_id)
            user_states.pop(user_id, None)
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            
            send_with_image(
                message.chat.id,
                "<b>✅ Способ оплаты установлен!</b>",
                reply_markup=keyboard,
                image_path=hi.png
            )

        elif user_states.get(user_id) == 'awaiting_amount':
            try:
                amount = float(text)
                user_states[user_id] = 'awaiting_description'
                user_states[f'{user_id}_amount'] = amount
                
                send_with_image(
                    message.chat.id,
                    "<b>📝 Укажите, что вы предлагаете в этой сделке:</b>\n\n"
                    "<blockquote><b>Пример:</b>\n"
                    "10 Кепок и Пепе...</blockquote>",
                    image_path=sdelka.png
                )
            except ValueError:
                bot.reply_to(message, "❌ Неверный формат. Введите число")

        elif user_states.get(user_id) == 'awaiting_description':
            deal_id = str(uuid.uuid4())
            amount = user_states.get(f'{user_id}_amount', 0)
            
            deals[deal_id] = {
                'amount': amount,
                'description': text,
                'seller_id': user_id,
                'buyer_id': None,
                'status': 'active'
            }
            save_deal(deal_id)
            
            user_states.pop(user_id, None)
            user_states.pop(f'{user_id}_amount', None)
           
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            
            deal_link = f"https://t.me/SatoriSafeRubot?start={deal_id}"
            
            send_with_image(
                message.chat.id,
                f"<b>✅ Сделка успешно создана!</b>\n\n"
                f"<blockquote>💎 <b>Сумма:</b> {amount} {VALUTE}\n"
                f"📝 <b>Описание:</b> {text}\n"
                f"🔗 <b>Ссылка для покупателя:</b>\n"
                f"<code>{deal_link}</code></blockquote>",
                reply_markup=keyboard,
                image_path=sdelka.png
            )

        if user_states.get(user_id) == 'awaiting_admin_deal_amount':
            try:
                amount = float(text)
                user_states[user_id] = 'awaiting_admin_deal_description'
                user_states[f'{user_id}_admin_amount'] = amount
                send_with_image(
                    message.chat.id,
                    "<b>📝 Введите описание для сделки:</b>",
                    image_path=sdelka.png
                )
            except ValueError:
                send_with_image(message.chat.id, "<b>❌ Неверный формат. Введите число</b>", image_path=sdelka.png)
            return

        if user_states.get(user_id) == 'awaiting_admin_deal_description':
            deal_id = str(uuid.uuid4())
            amount = user_states.get(f'{user_id}_admin_amount', 0)
            deals[deal_id] = {
                'amount': amount,
                'description': text,
                'seller_id': user_id,
                'buyer_id': None,
                'status': 'active'
            }
            save_deal(deal_id)
            user_states.pop(user_id, None)
            user_states.pop(f'{user_id}_admin_amount', None)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data='menu'))
            deal_link = f"https://t.me/SatoriSafeRubot?start={deal_id}"
            send_with_image(
                message.chat.id,
                f"<b>✅ Сделка успешно создана администратором!</b>\n\n"
                f"<blockquote>💎 <b>Сумма:</b> {amount} {VALUTE}\n"
                f"📝 <b>Описание:</b> {text}\n"
                f"🔗 <b>Ссылка для покупателя:</b>\n"
                f"<code>{deal_link}</code></blockquote>",
                reply_markup=keyboard,
                image_path=sdelka.png
            )
            return

        if user_states.get(user_id) == 'awaiting_admin_deal_id':
            deal_id = text.strip()
            if deal_id in deals and deals[deal_id]['status'] == 'active':
                deals[deal_id]['buyer_id'] = user_id
                save_deal(deal_id)
                send_with_image(
                    message.chat.id,
                    f"<b>✅ Вы успешно присоединились к сделке {deal_id} как покупатель!</b>",
                    image_path=hi.png
                )
            else:
                send_with_image(
                    message.chat.id,
                    f"<b>❌ Сделка с ID {deal_id} не найдена или неактивна.</b>",
                    image_path=hi.png
                )
            user_states.pop(user_id, None)
            return

        if user_states.get(user_id) == 'awaiting_delete_deal_id':
            deal_id = text.strip()
            if deal_id in deals:
                delete_deal(deal_id)
                deals.pop(deal_id, None)
                send_with_image(
                    message.chat.id,
                    f"<b>✅ Сделка {deal_id} удалена!</b>",
                    image_path=hi.png
                )
            else:
                send_with_image(
                    message.chat.id,
                    f"<b>❌ Сделка с ID {deal_id} не найдена.</b>",
                    image_path=hi.png
                )
            user_states.pop(user_id, None)
            return

        if user_states.get(user_id) == 'awaiting_ban_user_id':
            try:
                ban_id = int(text.strip())
                ban_user(ban_id)
                send_with_image(
                    message.chat.id,
                    f"<b>🚫 Пользователь {ban_id} забанен!</b>",
                    image_path=hi.png
                )
            except Exception:
                send_with_image(
                    message.chat.id,
                    "<b>❌ Неверный формат ID. Введите числовой ID пользователя.</b>",
                    image_path=hi.png
                )
            user_states.pop(user_id, None)
            return

        if user_states.get(user_id) == 'awaiting_unban_user_id':
            try:
                unban_id = int(text.strip())
                unban_user(unban_id)
                send_with_image(
                    message.chat.id,
                    f"<b>✅ Пользователь {unban_id} разбанен!</b>",
                    image_path=hi.png
                )
            except Exception:
                send_with_image(
                    message.chat.id,
                    "<b>❌ Неверный формат ID. Введите числовой ID пользователя.</b>",
                    image_path=hi.png
                )
            user_states.pop(user_id, None)
            return

    except Exception as e:
        logger.error(f"Ошибка в обработке сообщения: {e}")

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
            logger.error(f"Ошибка polling: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
