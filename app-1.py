#  ╭───𓆩🛡️𓆪───╮
#  👨‍💻 𝘿𝙚𝙫: @Hamo_fun
# =========================================================
#  🔥 نسخة مطوّرة:
#     - أزرار ملونة (Bot API 9.4: style + icon_custom_emoji_id)
#     - نظام شحن أيام تشغيل بنجوم تليجرام (Telegram Stars)
#     - نظام دعوة أصدقاء (رابط دعوة + مكافأة أيام مجانية)
#     - ميزة "تواصل مع المطور" (رسائل ثنائية الاتجاه)
#     - لوحة إعدادات كاملة للمطور (تتحكم في كل الأسعار والمكافآت)
# =========================================================
import telebot
import subprocess
import os
import zipfile
import shutil
import re
import random
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
from logging import StreamHandler
import threading
import sys
import atexit
import requests
import json
import html
import ast
import hashlib
from flask import Flask
from threading import Thread

# ---------------- Flask Keep-Alive ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is hosted by ATr"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Configuration ---
TOKEN = os.environ.get('BOT_TOKEN', '').strip()
OWNER_ID = int(os.environ.get('OWNER_ID', 7885527604))
YOUR_USERNAME = '@Hamo_fun'
UPDATE_CHANNEL = 'https://t.me/U_Y_All'
VODAFONE_CASH_NUMBER = '01032569732'
FORCE_SUBSCRIBE_CHANNEL_ID = '@U_Y_All'

# Absolute Paths for Directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
MAIN_BOT_LOG_PATH = os.path.join(IROTECH_DIR, 'main_bot_log.log')

# --- Per-bot virtual environments / dependency limits ---
VENV_DIR_NAME = ".venv"
REQUIREMENTS_FILENAME = "requirements.txt"
DEFAULT_INSTALL_TIMEOUT = 300  # 5 minutes
DEFAULT_MAX_VENV_MB = 500
MAX_REQUIREMENTS_LINES = 200
BLACKLISTED_PACKAGES = {
    "pyautogui", "pynput", "keyboard", "mouse", "scapy",
    "mitmproxy", "netfilterqueue", "impacket", "paramiko",
}

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)
BOT_USERNAME = None  # يتم تعبئته تلقائيًا عند بدء التشغيل (bot.get_me().username)

# --- Data Structures ---
bot_scripts = {}
user_files = {}
user_pagination_state = {}
admin_pagination_state = {}
upload_mode = {}          # user_id -> 'py' or 'zip' (آخر زر رفع دوس عليه)
restart_state = {}        # script_key -> {'attempts': int, 'timer': Timer, 'last_ok_time': datetime}
module_fix_attempts = {}  # script_key -> عدد محاولات إصلاح المكتبات الناقصة تلقائيًا
pending_entry_choice = {} # user_id -> بيانات مشروع ZIP بينتظر اختيار المستخدم لملف نقطة التشغيل

# --- خريطة تحويل اسم المكتبة وقت الاستيراد لاسم حزمة pip (لو مختلف) ---
IMPORT_TO_PIP_PACKAGE = {
    'telegram': 'python-telegram-bot',
    'cv2': 'opencv-python',
    'PIL': 'pillow',
    'yaml': 'pyyaml',
    'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv',
    'Crypto': 'pycryptodome',
    'sklearn': 'scikit-learn',
    'discord': 'discord.py',
    'telebot': 'pytelegrambotapi',
    'dateutil': 'python-dateutil',
    'jwt': 'pyjwt',
    'serial': 'pyserial',
    'usb': 'pyusb',
    'MySQLdb': 'mysqlclient',
    'OpenSSL': 'pyopenssl',
}

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MAIN_BOT_LOG_PATH, encoding='utf-8'),
        StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =========================================================
# 🎨 نظام الأزرار الملونة (Bot API 9.4)
# ---------------------------------------------------------
# تليجرام ضاف حديثًا حقلين جدد لأي زر (إنلاين أو زر لوحة مفاتيح):
#   style                -> "primary" أزرق / "success" أخضر / "danger" أحمر
#   icon_custom_emoji_id -> آيدي إيموجي مميز (بريميوم) يتحط جنب نص الزر
# المكتبة (pyTelegramBotAPI) ممكن تكون لسه مضافتش الحقلين دول رسميًا لكلاس
# InlineKeyboardButton بتاعها، لكن الحل بسيط: تليجرام مش شايف/مهتم بالمكتبة
# أصلاً، هو بس بيقرأ الـ JSON النهائي. فبنعمل كلاس صغير يورّث من الكلاس
# الأصلي ويضيف الحقلين يدويًا في to_dict(). كده هيشتغل مهما كانت نسخة
# المكتبة المثبتة، من غير ما ننتظر تحديث رسمي منهم.
# =========================================================
STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"

class CButton(types.InlineKeyboardButton):
    """زر إنلاين يدعم التلوين (style) وأيقونة إيموجي مميزة (icon_custom_emoji_id)."""
    def __init__(self, text, callback_data=None, url=None, style=None,
                 icon_custom_emoji_id=None, **kwargs):
        super().__init__(text=text, callback_data=callback_data, url=url, **kwargs)
        self.style = style
        self.icon_custom_emoji_id = icon_custom_emoji_id

    def to_dict(self):
        d = super().to_dict()
        if self.style:
            d['style'] = self.style
        if self.icon_custom_emoji_id:
            d['icon_custom_emoji_id'] = self.icon_custom_emoji_id
        return d


class CReplyButton(types.KeyboardButton):
    """زر لوحة مفاتيح عادي (Reply Keyboard) يدعم نفس التلوين."""
    def __init__(self, text, style=None, icon_custom_emoji_id=None, **kwargs):
        super().__init__(text=text, **kwargs)
        self.style = style
        self.icon_custom_emoji_id = icon_custom_emoji_id

    def to_dict(self):
        d = super().to_dict()
        if self.style:
            d['style'] = self.style
        if self.icon_custom_emoji_id:
            d['icon_custom_emoji_id'] = self.icon_custom_emoji_id
        return d

# --- ReplyKeyboardMarkup Layouts (نص الزر، لون الزر) ---
MAIN_MENU_BUTTONS_LAYOUT = [
    [("🤖 بوتاتي", STYLE_PRIMARY), ("➕ رفع بوت", STYLE_SUCCESS)],
    [("📦 رفع ZIP", STYLE_DANGER), ("💎 الاشتراكات", STYLE_SUCCESS)],
    [("📊 إحصائياتي", STYLE_PRIMARY), ("🎫 الدعم", STYLE_DANGER)],
    [("📖 الدليل", STYLE_PRIMARY), ("📜 القواعد", STYLE_SUCCESS)],
    [("🎁 دعوة الأصدقاء", STYLE_PRIMARY), ("📢 قناتي", STYLE_PRIMARY)],
    [("🎰 تجميع نقاط", STYLE_SUCCESS), ("❄️ تجميد الاشتراك مؤقتاً", STYLE_DANGER)],
]
ADMIN_EXTRA_ROW = [("👑 لوحة تحكم المطور", STYLE_DANGER), ("⚙️ إعدادات البوت", STYLE_PRIMARY)]


def get_user_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    layout = list(MAIN_MENU_BUTTONS_LAYOUT)
    if user_id == OWNER_ID:
        layout = layout + [ADMIN_EXTRA_ROW]
    for row in layout:
        markup.row(*[CReplyButton(text, style=style) for text, style in row])
    return markup

# --- Database Setup ---
DB_LOCK = threading.Lock()

def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT, status TEXT, bot_token_id TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_env_vars
                     (user_id INTEGER, file_name TEXT, key TEXT, value TEXT,
                      PRIMARY KEY (user_id, file_name, key))''')
        # ترقية جدول active_users لو كان من نسخة قديمة وناقصه أعمدة
        for col, col_def in [
            ('referred_by', 'INTEGER'),
            ('referral_credited', 'INTEGER DEFAULT 0'),
            ('hosting_expiry', 'TEXT'),
            ('join_date', 'TEXT'),
            ('frozen', 'INTEGER DEFAULT 0'),
            ('frozen_remaining', 'TEXT'),
            ('frozen_bots', 'TEXT'),
            ('points', 'INTEGER DEFAULT 0'),
            ('last_daily_gift', 'TEXT'),
            ('last_weekly_gift', 'TEXT'),
            ('last_wheel_spin', 'TEXT'),
            ('channel_sub_bonus_claimed', 'INTEGER DEFAULT 0'),
        ]:
            if not _column_exists(c, 'active_users', col):
                try:
                    c.execute(f'ALTER TABLE active_users ADD COLUMN {col} {col_def}')
                except sqlite3.OperationalError:
                    pass
        # ترقية جدول user_files لإضافة عدادات الإعادات/الكراشات
        for col, col_def in [
            ('restart_count', 'INTEGER DEFAULT 0'),
            ('crash_count', 'INTEGER DEFAULT 0'),
        ]:
            if not _column_exists(c, 'user_files', col):
                try:
                    c.execute(f'ALTER TABLE user_files ADD COLUMN {col} {col_def}')
                except sqlite3.OperationalError:
                    pass
        conn.commit()
        conn.close()

def load_data():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, file_name, file_type, status, bot_token_id FROM user_files')
        for user_id, file_name, file_type, status, bot_token_id in c.fetchall():
            user_files.setdefault(user_id, []).append((file_name, file_type, status, bot_token_id))
        conn.close()

# --- الإعدادات القابلة للتعديل من لوحة المطور ---
DEFAULT_SETTINGS = {
    'day_price_stars': '2',
    'week_price_stars': '10',
    'month_price_stars': '30',
    'day_price_egp': '15',
    'week_price_egp': '60',
    'month_price_egp': '200',
    'referral_reward_days': '1',
    'max_bots_per_user': '3',
    'max_file_size_mb': '20',
    'max_restart_attempts': '5',
    'auto_fix_modules': '1',
    'maintenance_mode': '0',
    'require_approval': '0',
    # --- نظام تجميع النقاط ---
    'points_per_day': '100',
    'daily_gift_points': '10',
    'weekly_gift_points': '50',
    'wheel_min_points': '10',
    'wheel_max_points': '1000',
    'referral_points_reward': '50',
    'channel_sub_points_bonus': '20',
    'install_timeout_seconds': str(DEFAULT_INSTALL_TIMEOUT),
    'max_venv_size_mb': str(DEFAULT_MAX_VENV_MB),
    'max_zip_uncompressed_mb': '100',
    'max_zip_files': '1000',
    'max_log_kb': '2048',
    'broadcast_delay_ms': '60',
    'payment_history_limit': '10',
}
SETTINGS = {}

def load_settings():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT key, value FROM settings')
        rows = dict(c.fetchall())
        conn.close()
    for k, v in DEFAULT_SETTINGS.items():
        SETTINGS[k] = rows.get(k, v)

def set_setting(key, value):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
    SETTINGS[key] = str(value)

def add_user_to_db(user_id, referred_by=None):
    """يضيف المستخدم لو مش موجود. بيرجع True لو ده أول ظهور له في القاعدة."""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id FROM active_users WHERE user_id = ?', (user_id,))
        exists = c.fetchone()
        if not exists:
            c.execute(
                'INSERT INTO active_users (user_id, referred_by, referral_credited, hosting_expiry, join_date) '
                'VALUES (?, ?, 0, NULL, ?)',
                (user_id, referred_by, datetime.now().isoformat())
            )
            conn.commit()
        conn.close()
    return exists is None

def update_user_file_db(user_id, file_name, file_type, status, bot_token_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, status, bot_token_id) VALUES (?, ?, ?, ?, ?)',
                  (user_id, file_name, file_type, status, bot_token_id))
        conn.commit()
        conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        conn.commit()
        conn.close()

def get_all_user_files_from_db():
    all_files = []
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, file_name, file_type, status, bot_token_id FROM user_files')
        for user_id, file_name, file_type, status, bot_token_id in c.fetchall():
            all_files.append({
                'user_id': user_id,
                'file_name': file_name,
                'file_type': file_type,
                'status': status,
                'bot_token_id': bot_token_id
            })
        conn.close()
    return all_files

# --- Bot Environment Variables (متغيرات البيئة لكل بوت مرفوع) ---
def get_bot_env_vars(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT key, value FROM bot_env_vars WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        rows = dict(c.fetchall())
        conn.close()
    return rows

def set_bot_env_var(user_id, file_name, key, value):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO bot_env_vars (user_id, file_name, key, value) VALUES (?, ?, ?, ?)',
                  (user_id, file_name, key, value))
        conn.commit()
        conn.close()

def delete_bot_env_var(user_id, file_name, key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM bot_env_vars WHERE user_id = ? AND file_name = ? AND key = ?', (user_id, file_name, key))
        conn.commit()
        conn.close()

def bump_file_counter(user_id, file_name, column):
    """يزود عداد (restart_count أو crash_count) لملف معين بواحد."""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(f'UPDATE user_files SET {column} = COALESCE({column}, 0) + 1 WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        conn.commit()
        conn.close()

def get_file_counters(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT restart_count, crash_count FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        row = c.fetchone()
        conn.close()
    return row if row else (0, 0)

# --- Hosting / Referral Helpers ---
def get_user_record(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, referred_by, referral_credited, hosting_expiry, join_date, frozen FROM active_users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
    return row

def get_hosting_expiry(user_id):
    row = get_user_record(user_id)
    if row and row[3]:
        try:
            return datetime.fromisoformat(row[3])
        except ValueError:
            return None
    return None

def has_active_hosting(user_id):
    if user_id == OWNER_ID:
        return True
    expiry = get_hosting_expiry(user_id)
    return expiry is not None and expiry > datetime.now()

def add_hosting_days(user_id, days):
    current = get_hosting_expiry(user_id)
    base = current if (current and current > datetime.now()) else datetime.now()
    new_expiry = base + timedelta(days=days)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('UPDATE active_users SET hosting_expiry = ? WHERE user_id = ?', (new_expiry.isoformat(), user_id))
        conn.commit()
        conn.close()
    return new_expiry

def is_frozen(user_id):
    row = get_user_record(user_id)
    return bool(row and row[5] if row and len(row) > 5 else False)

def freeze_subscription(user_id):
    """يجمّد رصيد التشغيل المتبقي (يوقف كل بوتاته مؤقتًا من غير ما يستهلك الوقت)."""
    expiry = get_hosting_expiry(user_id)
    if not expiry or expiry <= datetime.now():
        return False, "⛔ معندكش رصيد تشغيل شغّال عشان تجمده."
    if is_frozen(user_id):
        return False, "ℹ️ رصيدك مجمد بالفعل."

    remaining_seconds = (expiry - datetime.now()).total_seconds()

    running_files = []
    for file_name, file_type, status, bot_token_id in user_files.get(user_id, []):
        if status == 'approved' and is_bot_running(user_id, file_name):
            script_key = f"{user_id}_{file_name}"
            if script_key in bot_scripts:
                kill_process_tree(bot_scripts[script_key])
                del bot_scripts[script_key]
            running_files.append(file_name)

    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            'UPDATE active_users SET frozen = 1, frozen_remaining = ?, frozen_bots = ?, hosting_expiry = NULL WHERE user_id = ?',
            (str(remaining_seconds), json.dumps(running_files), user_id)
        )
        conn.commit()
        conn.close()
    return True, remaining_seconds

def unfreeze_subscription(user_id):
    row = get_user_record(user_id)
    if not row:
        return False, "❌ لا يوجد رصيد مجمد."
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT frozen, frozen_remaining, frozen_bots FROM active_users WHERE user_id = ?', (user_id,))
        r = c.fetchone()
        conn.close()
    if not r or not r[0]:
        return False, "ℹ️ رصيدك مش مجمد أصلًا."

    remaining_seconds = float(r[1] or 0)
    frozen_bots = json.loads(r[2]) if r[2] else []
    new_expiry = datetime.now() + timedelta(seconds=remaining_seconds)

    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            'UPDATE active_users SET frozen = 0, frozen_remaining = NULL, frozen_bots = NULL, hosting_expiry = ? WHERE user_id = ?',
            (new_expiry.isoformat(), user_id)
        )
        conn.commit()
        conn.close()

    for file_name in frozen_bots:
        user_folder = get_user_folder(user_id)
        script_path = os.path.join(user_folder, file_name)
        if os.path.exists(script_path):
            threading.Thread(target=run_script, args=(script_path, user_id, user_folder, file_name, user_id)).start()

    return True, new_expiry

def get_referral_stats(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM active_users WHERE referred_by = ?', (user_id,))
        total = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM active_users WHERE referred_by = ? AND referral_credited = 1', (user_id,))
        credited = c.fetchone()[0]
        conn.close()
    return credited, total

def credit_referral_if_needed(user_id):
    """يمنح صاحب رابط الدعوة مكافأة أيام مجانية أول مرة يتأكد فيها اشتراك المدعو."""
    row = get_user_record(user_id)
    if not row:
        return
    _, referred_by, credited, _, _, _ = row
    if referred_by and not credited:
        reward_days = int(SETTINGS.get('referral_reward_days', 1))
        reward_points = int(SETTINGS.get('referral_points_reward', 50))
        add_hosting_days(referred_by, reward_days)
        add_points(referred_by, reward_points)
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('UPDATE active_users SET referral_credited = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
        try:
            bot.send_message(
                referred_by,
                f"🎁 مبروك! حد اشترك من رابط دعوتك، اتضاف لحسابك <b>{reward_days}</b> يوم تشغيل مجاني ⭐ "
                f"و<b>{reward_points}</b> نقطة 💎",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify referrer {referred_by}: {e}")

# =========================================================
# 💎 نظام النقاط (تجميع نقاط + تحويلها لأيام تشغيل)
# كل القيم (نقاط الهدايا/العجلة/الإحالة/سعر تحويل النقطة) قابلة للتعديل
# في أي وقت من «⚙️ إعدادات البوت» بدون لمس الكود.
# =========================================================
POINTS_TIME_COLUMNS = {'last_daily_gift', 'last_weekly_gift', 'last_wheel_spin'}

def get_points(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT points FROM active_users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
    return row[0] if row and row[0] is not None else 0

def add_points(user_id, amount):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('UPDATE active_users SET points = COALESCE(points, 0) + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()

def deduct_points(user_id, amount):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('UPDATE active_users SET points = COALESCE(points, 0) - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()

def get_points_state(user_id):
    """يرجع (last_daily_gift, last_weekly_gift, last_wheel_spin, channel_sub_bonus_claimed)."""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            'SELECT last_daily_gift, last_weekly_gift, last_wheel_spin, channel_sub_bonus_claimed '
            'FROM active_users WHERE user_id = ?', (user_id,)
        )
        row = c.fetchone()
        conn.close()
    return row if row else (None, None, None, 0)

def set_points_timestamp(user_id, column, value):
    if column not in POINTS_TIME_COLUMNS:
        raise ValueError("عمود غير مسموح به.")
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(f'UPDATE active_users SET {column} = ? WHERE user_id = ?', (value, user_id))
        conn.commit()
        conn.close()

def mark_channel_sub_bonus_claimed(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('UPDATE active_users SET channel_sub_bonus_claimed = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

def check_cooldown(last_iso, hours):
    """يرجع (مسموح؟, وقت الإتاحة الجاية لو لسه مسموح)."""
    if not last_iso:
        return True, None
    try:
        last_dt = datetime.fromisoformat(last_iso)
    except ValueError:
        return True, None
    next_allowed = last_dt + timedelta(hours=hours)
    if datetime.now() >= next_allowed:
        return True, None
    return False, next_allowed

def format_remaining(target_dt):
    remaining = target_dt - datetime.now()
    total_seconds = max(0, int(remaining.total_seconds()))
    h, rem = divmod(total_seconds, 3600)
    m, _ = divmod(rem, 60)
    return f"{h} ساعة و{m} دقيقة"

init_db()
load_data()
load_settings()

# Advanced persistence: payments, admin audit and bans.
def init_advanced_db():
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); c=conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS payment_transactions (charge_id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,method TEXT NOT NULL,package TEXT,days INTEGER DEFAULT 0,amount TEXT,currency TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,raw_payload TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS admin_audit (id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id INTEGER,action TEXT NOT NULL,target_user_id INTEGER,details TEXT,created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY,reason TEXT,created_at TEXT NOT NULL)")
        conn.commit(); conn.close()
def record_admin_action(action,target_user_id=None,details=''):
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); conn.execute('INSERT INTO admin_audit(admin_id,action,target_user_id,details,created_at) VALUES(?,?,?,?,?)',(OWNER_ID,action,target_user_id,str(details)[:1000],datetime.now().isoformat())); conn.commit(); conn.close()
def payment_exists(charge_id):
    if not charge_id:return False
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); row=conn.execute('SELECT 1 FROM payment_transactions WHERE charge_id=?',(charge_id,)).fetchone(); conn.close()
    return row is not None
def record_payment(charge_id,user_id,method,package,days,amount,currency,status='paid',raw_payload=''):
    if not charge_id:return False
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False)
        try:
            conn.execute('INSERT INTO payment_transactions VALUES(?,?,?,?,?,?,?,?,?,?)',(charge_id,user_id,method,package,days,str(amount),currency,status,datetime.now().isoformat(),str(raw_payload)[:2000])); conn.commit(); return True
        except sqlite3.IntegrityError:return False
        finally:conn.close()
def get_payment_history(user_id,limit=None):
    limit=max(1,min(50,int(limit or SETTINGS.get('payment_history_limit',10))))
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); rows=conn.execute('SELECT method,package,days,amount,currency,status,created_at FROM payment_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?',(user_id,limit)).fetchall(); conn.close()
    return rows
def is_banned(user_id):
    if user_id==OWNER_ID:return False
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); row=conn.execute('SELECT 1 FROM banned_users WHERE user_id=?',(user_id,)).fetchone(); conn.close()
    return row is not None
def set_ban(user_id,banned=True,reason=''):
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False)
        if banned:conn.execute('INSERT OR REPLACE INTO banned_users VALUES(?,?,?)',(user_id,str(reason)[:500],datetime.now().isoformat()))
        else:conn.execute('DELETE FROM banned_users WHERE user_id=?',(user_id,))
        conn.commit();conn.close()
    record_admin_action('ban' if banned else 'unban',user_id,reason)
def get_subscription_summary():
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False)
        total=conn.execute('SELECT COUNT(*) FROM active_users').fetchone()[0]; active=conn.execute('SELECT COUNT(*) FROM active_users WHERE hosting_expiry IS NOT NULL AND hosting_expiry > ?',(datetime.now().isoformat(),)).fetchone()[0]; frozen=conn.execute('SELECT COUNT(*) FROM active_users WHERE frozen=1').fetchone()[0]; payments=conn.execute("SELECT COUNT(*) FROM payment_transactions WHERE status='paid'").fetchone()[0]; stars=conn.execute("SELECT COALESCE(SUM(CASE WHEN currency='XTR' AND status='paid' THEN CAST(amount AS INTEGER) ELSE 0 END),0) FROM payment_transactions").fetchone()[0]; conn.close()
    return total,active,frozen,payments,stars
init_advanced_db()

# --- Helper Functions for Script Management ---
def safe_upload_filename(file_name):
    """يرجع اسم ملف آمن من اسم الملف القادم من Telegram."""
    name = os.path.basename((file_name or '').replace('\\', '/')).strip()
    if not name or name in {'.', '..'}:
        raise ValueError('اسم الملف غير صالح.')
    # امنع أسماء الملفات التي قد تتسبب في الكتابة خارج مجلد المستخدم.
    if any(ch in name for ch in ('\x00', '\n', '\r')):
        raise ValueError('اسم الملف يحتوي على محارف غير مسموحة.')
    return name

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def _as_user(message, real_from_user):
    """يظبط message.from_user ليكون المستخدم الحقيقي بدل حساب البوت،
    مفيد لما بنعيد استخدام هاندلر رسالة عادي جوه رد فعل على زر (callback)."""
    try:
        message.from_user = real_from_user
    except Exception:
        pass
    return message

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if not script_info or not script_info.get('process'):
        return False

    try:
        proc = psutil.Process(script_info['process'].pid)
        is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        if not is_running:
            _cleanup_stale_script_entry(script_key, script_info)
        return is_running
    except psutil.NoSuchProcess:
        _cleanup_stale_script_entry(script_key, script_info)
        return False
    except Exception as e:
        logger.error(f"Error checking process status for {script_key}: {e}", exc_info=True)
        return False

def _cleanup_stale_script_entry(script_key, script_info):
    if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
        try: script_info['log_file'].close()
        except Exception as log_e: logger.error(f"Error closing log file for stale script {script_key}: {log_e}")
    if script_key in bot_scripts: del bot_scripts[script_key]

def kill_process_tree(process_info):
    pid = None
    if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
        try: process_info['log_file'].close()
        except Exception as log_e: logger.error(f"Error closing log file during termination for {process_info.get('script_key', 'N/A')}: {log_e}")

    process = process_info.get('process')
    if not process or not hasattr(process, 'pid'):
        return

    pid = process.pid
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        for child in children:
            try: child.terminate()
            except (psutil.NoSuchProcess, Exception) as e:
                try: child.kill()
                except Exception as e2: logger.error(f"Failed to kill child process {child.pid} forcefully: {e2}")

        psutil.wait_procs(children, timeout=1)

        try:
            parent.terminate()
            parent.wait(timeout=1)
        except psutil.TimeoutExpired:
            parent.kill()
        except (psutil.NoSuchProcess, Exception) as e:
            try: parent.kill()
            except Exception as e2: logger.error(f"Failed to kill main process {pid} forcefully: {e2}")

    except psutil.NoSuchProcess: pass
    except Exception as e:
        logger.error(f"Unexpected error during process tree termination for PID {pid}: {e}", exc_info=True)

def run_script(script_path, script_owner_id, user_folder, file_name, chat_id_for_reply):
    script_key = f"{script_owner_id}_{file_name}"

    if not os.path.exists(script_path):
        bot.send_message(chat_id_for_reply, f"❌ خطأ: لم يتم العثور على السكربت '{file_name}' في '{script_path}'!")
        return

    if not has_active_hosting(script_owner_id):
        bot.send_message(
            chat_id_for_reply,
            "⛔ انتهى رصيد التشغيل بتاعك. اشحن أيام جديدة من زر «💎 الاشتراكات» عشان تقدر تشغّل بوتاتك."
        )
        return

    if is_bot_running(script_owner_id, file_name):
        bot.send_message(chat_id_for_reply, f"ℹ️ سكربت '{file_name}' قيد التشغيل بالفعل.")
        return

    log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    log_file = None; process = None

    try: log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
    except Exception as e:
        bot.send_message(chat_id_for_reply, f"❌ فشل في فتح ملف السجل '{log_file_path}': {e}", parse_mode='Markdown')
        return

    try:
        startupinfo = None; creationflags = 0
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # كل بوت يستخدم Python interpreter من بيئته الافتراضية الخاصة.
        project_root = os.path.dirname(script_path) or user_folder
        venv_dir = get_bot_venv_dir(project_root)
        python_executable = get_venv_python(venv_dir)
        if not os.path.isfile(python_executable):
            bot.send_message(chat_id_for_reply, "❌ بيئة البوت غير جاهزة. ارفع requirements.txt أو أعد تجهيز البوت.")
            log_file.close()
            return

        # حقن متغيرات البيئة المخصصة (زي BOT_TOKEN) المضافة من صفحة إعدادات البوت
        run_env = os.environ.copy()
        run_env.update(get_bot_env_vars(script_owner_id, file_name))
        run_env["PYTHONUNBUFFERED"] = "1"

        # نشغّل السكربت من داخل مجلده هو عشان المشاريع متعددة الملفات تلاقي مواردها النسبية صح
        run_cwd = project_root

        process = subprocess.Popen(
            [python_executable, script_path], cwd=run_cwd, stdout=log_file, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE, startupinfo=startupinfo, creationflags=creationflags,
            encoding='utf-8', errors='ignore', env=run_env,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        bot_scripts[script_key] = {
            'process': process, 'log_file': log_file, 'file_name': file_name,
            'chat_id': chat_id_for_reply,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(), 'user_folder': user_folder, 'script_path': script_path, 'type': 'py', 'script_key': script_key
        }
        bot.send_message(chat_id_for_reply, f"✅ تم بدء سكربت بايثون '{file_name}'! (PID: {process.pid})")
    except FileNotFoundError:
        if log_file and not log_file.closed: log_file.close()
        bot.send_message(chat_id_for_reply, f"❌ خطأ: لم يتم العثور على مترجم بايثون '{sys.executable}'.", parse_mode='Markdown')
        if script_key in bot_scripts: del bot_scripts[script_key]
    except Exception as e:
        if log_file and not log_file.closed: log_file.close()
        bot.send_message(chat_id_for_reply, f"❌ خطأ في بدء سكربت بايثون '{file_name}': {str(e)}", parse_mode='Markdown')
        if process and process.poll() is None:
            kill_process_tree({'process': process, 'log_file': log_file, 'script_key': script_key})
        if script_key in bot_scripts: del bot_scripts[script_key]

# --- Auto-fix Helpers (إصلاح غلطات الاستضافة الشائعة تلقائيًا) ---
def extract_missing_module(log_content):
    match = re.search(r"ModuleNotFoundError:\s*No module named ['\"]([\w\.]+)['\"]", log_content)
    if match:
        return match.group(1).split('.')[0]
    return None

def extract_error_reason(log_content):
    """يطلع آخر سطر خطأ واضح من السجل بدل ما يبعت اللوج كله."""
    if not log_content or not log_content.strip():
        return "لا توجد تفاصيل في السجل (السكربت اتوقف من غير ما يكتب حاجة)."
    lines = [l for l in log_content.strip().splitlines() if l.strip()]
    for line in reversed(lines):
        if re.search(r'\b\w*Error\b|\bException\b', line):
            return line.strip()[:400]
    return lines[-1].strip()[:400]

def get_bot_venv_dir(project_dir):
    """مسار البيئة الافتراضية الخاصة بالمشروع."""
    return os.path.join(os.path.abspath(project_dir), VENV_DIR_NAME)


def get_venv_python(venv_dir):
    """يرجع مسار Python داخل venv على ويندوز/لينكس."""
    if os.name == 'nt':
        return os.path.join(venv_dir, 'Scripts', 'python.exe')
    return os.path.join(venv_dir, 'bin', 'python')


def get_venv_pip(venv_dir):
    if os.name == 'nt':
        return os.path.join(venv_dir, 'Scripts', 'pip.exe')
    return os.path.join(venv_dir, 'bin', 'pip')


def _requirements_path(base_dir, entry_relpath=None):
    candidates = []
    if entry_relpath:
        entry_dir = os.path.join(base_dir, os.path.dirname(entry_relpath))
        candidates.append(os.path.join(entry_dir, REQUIREMENTS_FILENAME))
    candidates.append(os.path.join(base_dir, REQUIREMENTS_FILENAME))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _requirements_are_allowed(req_path):
    """فحص بسيط لأسماء الحزم قبل تشغيل pip."""
    try:
        text = open(req_path, 'r', encoding='utf-8', errors='ignore').read()
    except OSError as exc:
        return False, f"تعذر قراءة requirements.txt: {exc}"
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if len(lines) > MAX_REQUIREMENTS_LINES:
        return False, f"عدد أسطر requirements.txt أكبر من الحد ({MAX_REQUIREMENTS_LINES})."
    for line in lines:
        if line.startswith(('-r ', '--requirement ', '-e ', '--editable ')):
            return False, "الروابط أو ملفات requirements المتداخلة غير مسموحة لأسباب أمنية."
        # اسم الحزمة قبل إصدارها أو extras
        match = re.match(r'^([A-Za-z0-9_.-]+)', line)
        if not match:
            return False, f"صيغة غير مفهومة في requirements.txt: {line[:100]}"
        package = match.group(1).lower().replace('_', '-')
        if package in {x.lower().replace('_', '-') for x in BLACKLISTED_PACKAGES}:
            return False, f"المكتبة غير مسموح بها: {package}"
    return True, None


def _directory_size_bytes(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def create_venv_and_install(project_dir, entry_relpath=None, notify_chat_id=None):
    """ينشئ venv مستقلًا ويثبت requirements.txt بمهلة وحد أقصى للحجم.
    يرجع (found_requirements, success, details).
    """
    req_path = _requirements_path(project_dir, entry_relpath)
    venv_dir = get_bot_venv_dir(project_dir)
    if not req_path:
        # حتى بدون requirements ننشئ venv لضمان عدم استخدام مكتبات السيرفر العامة.
        try:
            if not os.path.isfile(get_venv_python(venv_dir)):
                subprocess.run([sys.executable, '-m', 'venv', venv_dir], capture_output=True, text=True, timeout=120, check=True)
            return False, True, "لا يوجد requirements.txt؛ تم إنشاء البيئة الافتراضية."
        except Exception as exc:
            return False, False, f"فشل إنشاء البيئة الافتراضية: {exc}"

    allowed, reason = _requirements_are_allowed(req_path)
    if not allowed:
        return True, False, reason

    timeout = int(SETTINGS.get('install_timeout_seconds', DEFAULT_INSTALL_TIMEOUT))
    max_mb = int(SETTINGS.get('max_venv_size_mb', DEFAULT_MAX_VENV_MB))
    try:
        if notify_chat_id:
            bot.send_message(notify_chat_id, "🧰 جاري إنشاء بيئة Python منفصلة للبوت...", parse_mode='HTML')
        if not os.path.isfile(get_venv_python(venv_dir)):
            subprocess.run([sys.executable, '-m', 'venv', venv_dir], capture_output=True, text=True, timeout=120, check=True)
        pip_cmd = [get_venv_python(venv_dir), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', '-r', req_path]
        if notify_chat_id:
            bot.send_message(notify_chat_id, f"📦 جاري تثبيت المكتبات (مهلة قصوى: {timeout // 60} دقائق)...", parse_mode='HTML')
        result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=timeout)
        details = (result.stdout[-1500:] + '\n' + result.stderr[-1500:]).strip()
        if result.returncode != 0:
            return True, False, details or 'pip انتهى بخطأ غير معروف.'
        size_mb = _directory_size_bytes(venv_dir) / (1024 * 1024)
        if size_mb > max_mb:
            shutil.rmtree(venv_dir, ignore_errors=True)
            return True, False, f"حجم البيئة بعد التثبيت {size_mb:.1f}MB وتجاوز الحد {max_mb}MB."
        return True, True, f"تم التثبيت بنجاح؛ حجم البيئة {size_mb:.1f}MB."
    except subprocess.TimeoutExpired:
        shutil.rmtree(venv_dir, ignore_errors=True)
        return True, False, f"انتهت مهلة التثبيت بعد {timeout} ثانية."
    except Exception as exc:
        return True, False, str(exc)


def auto_install_package(module_name, project_dir=None):
    """يثبت المكتبة الناقصة داخل venv الخاص بالبوت، وليس على السيرفر العام."""
    package_name = IMPORT_TO_PIP_PACKAGE.get(module_name, module_name)
    if package_name.lower().replace('_', '-') in {x.lower().replace('_', '-') for x in BLACKLISTED_PACKAGES}:
        return False, 'المكتبة محظورة.'
    try:
        if not project_dir:
            return False, 'لم يتم تحديد مجلد المشروع.'
        venv_dir = get_bot_venv_dir(project_dir)
        if not os.path.isfile(get_venv_python(venv_dir)):
            subprocess.run([sys.executable, '-m', 'venv', venv_dir], capture_output=True, text=True, timeout=120, check=True)
        result = subprocess.run(
            [get_venv_python(venv_dir), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', package_name],
            capture_output=True, text=True,
            timeout=int(SETTINGS.get('install_timeout_seconds', DEFAULT_INSTALL_TIMEOUT))
        )
        return result.returncode == 0, (result.stdout[-700:] + result.stderr[-700:])
    except subprocess.TimeoutExpired:
        return False, 'انتهت مهلة التثبيت.'
    except Exception as exc:
        return False, str(exc)


# توافق مع الاستدعاءات القديمة داخل المشروع
install_requirements_if_present = create_venv_and_install

def schedule_restart(script_info, delay_seconds):
    def _do_restart():
        threading.Thread(target=run_script, args=(
            os.path.join(script_info['user_folder'], script_info['file_name']),
            script_info['script_owner_id'],
            script_info['user_folder'],
            script_info['file_name'],
            script_info['chat_id']
        )).start()
    timer = threading.Timer(delay_seconds, _do_restart)
    timer.daemon = True
    timer.start()

# --- Script Monitoring ---
def monitor_scripts():
    while True:
        keys_to_check = list(bot_scripts.keys())
        for script_key in keys_to_check:
            if script_key not in bot_scripts:
                continue
            script_info = bot_scripts[script_key]
            owner_id = script_info['script_owner_id']

            # لو رصيد التشغيل خلص، وقف السكربت وبلغ صاحبه
            if not has_active_hosting(owner_id):
                kill_process_tree(script_info)
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
                try:
                    bot.send_message(
                        owner_id,
                        f"⛔ تم إيقاف سكربت '{script_info['file_name']}' تلقائيًا لانتهاء رصيد التشغيل.\n"
                        "اشحن أيام جديدة من زر «💎 الاشتراكات» عشان يشتغل تاني."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify expiry stop to {owner_id}: {e}")
                continue

            process = script_info['process']

            # لو البوت شغال بثبات لأكتر من 60 ثانية، اعتبره "استقر" وصفّر عداد المحاولات
            uptime = (datetime.now() - script_info['start_time']).total_seconds()
            if uptime > 60 and script_key in restart_state:
                restart_state[script_key]['attempts'] = 0
                module_fix_attempts[script_key] = 0

            if process.poll() is not None:
                exit_code = process.poll()
                log_file_path = os.path.join(script_info['user_folder'], f"{os.path.splitext(script_info['file_name'])[0]}.log")
                log_content = ""
                if os.path.exists(log_file_path):
                    try:
                        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
                    except Exception as e:
                        logger.error(f"Error reading log for stopped script: {e}")

                kill_process_tree(script_info)
                if script_key in bot_scripts:
                    del bot_scripts[script_key]

                bump_file_counter(script_info['script_owner_id'], script_info['file_name'], 'crash_count')
                reason = html.escape(extract_error_reason(log_content))
                missing_module = extract_missing_module(log_content)
                missing_module_safe = html.escape(missing_module) if missing_module else None

                # 🔧 إصلاح تلقائي: مكتبة ناقصة (ModuleNotFoundError)
                fix_attempts = module_fix_attempts.get(script_key, 0)
                if missing_module and SETTINGS.get('auto_fix_modules', '1') == '1' and fix_attempts < 3:
                    module_fix_attempts[script_key] = fix_attempts + 1
                    try:
                        bot.send_message(
                            script_info['chat_id'],
                            f"🔧 اكتشفنا مكتبة ناقصة (<code>{missing_module_safe}</code>) في بوت '{script_info['file_name']}'، "
                            "جارٍ تثبيتها تلقائيًا...",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify auto-fix start: {e}")

                    success, _log = auto_install_package(missing_module, os.path.dirname(script_info.get('script_path', '')) or script_info.get('user_folder'))
                    if success:
                        try:
                            bot.send_message(script_info['chat_id'], f"✅ تم تثبيت المكتبة بنجاح، جارٍ إعادة تشغيل البوت...")
                        except Exception:
                            pass
                        bump_file_counter(script_info['script_owner_id'], script_info['file_name'], 'restart_count')
                        schedule_restart(script_info, 2)
                        continue
                    else:
                        try:
                            bot.send_message(script_info['chat_id'], f"❌ فشل التثبيت التلقائي للمكتبة <code>{missing_module_safe}</code>. تأكد من اسمها الصحيح.", parse_mode='HTML')
                        except Exception:
                            pass

                # ⏱️ نظام إعادة التشغيل بالتراجع الأسي + حد أقصى للمحاولات
                state = restart_state.setdefault(script_key, {'attempts': 0})
                state['attempts'] += 1
                attempts = state['attempts']
                max_attempts = int(SETTINGS.get('max_restart_attempts', 5))

                if attempts > max_attempts:
                    try:
                        bot.send_message(
                            script_info['chat_id'],
                            f"⛔ بوت '{script_info['file_name']}' توقف نهائيًا بعد {max_attempts} محاولات فاشلة.\n"
                            f"🔍 السبب:\n❌ {reason}\n\n"
                            "راجع كودك أو اضغط «▶ تشغيل» يدويًا من «🤖 بوتاتي» بعد الإصلاح، أو تواصل مع «🎫 الدعم».",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send final-stop notification: {e}")
                    restart_state[script_key] = {'attempts': 0}
                    continue

                backoff_seconds = min(20 * (2 ** (attempts - 1)), 300)
                bump_file_counter(script_info['script_owner_id'], script_info['file_name'], 'restart_count')

                try:
                    bot.send_message(
                        script_info['chat_id'],
                        f"🔄 بوت '{script_info['file_name']}' — إعادة تشغيل خلال {backoff_seconds} ث\n"
                        f"↩️ المحاولة {attempts} من {max_attempts}\n\n"
                        f"🔍 السبب:\n❌ {reason}",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to send script stop notification to user {script_info['chat_id']}: {e}")

                schedule_restart(script_info, backoff_seconds)

        time.sleep(10)

threading.Thread(target=monitor_scripts, daemon=True).start()

# --- Force Subscribe Check ---
def is_subscribed(user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = bot.get_chat_member(FORCE_SUBSCRIBE_CHANNEL_ID, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except telebot.apihelper.ApiException as e:
        logger.error(f"Error checking channel membership for {FORCE_SUBSCRIBE_CHANNEL_ID} for user {user_id}: {e}")
        return False

def send_force_subscribe_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(CButton(
        "📢 اشترك في القناة",
        url=f"https://t.me/{FORCE_SUBSCRIBE_CHANNEL_ID.replace('@', '')}",
        style=STYLE_PRIMARY
    ))
    bot.send_message(
        chat_id,
        f"عليك الاشتراك في قناة المطور {FORCE_SUBSCRIBE_CHANNEL_ID} لكي تتمكن من استخدام البوت.",
        reply_markup=markup
    )

def check_subscription_wrapper(handler_function):
    def wrapper(message):
        if is_banned(message.from_user.id):
            bot.reply_to(message, '⛔ حسابك موقوف عن استخدام الاستضافة. تواصل مع المطور إذا كنت تعتقد أن هذا بالخطأ.')
            return
        if message.from_user.id == OWNER_ID:
            handler_function(message)
            return
        if not is_subscribed(message.from_user.id):
            send_force_subscribe_message(message.chat.id)
            return
        credit_referral_if_needed(message.from_user.id)
        handler_function(message)
    return wrapper

# --- Get Bot ID from Token ---
def get_bot_id_from_token(token_string):
    try:
        parts = token_string.split(':')
        if len(parts) > 0:
            return parts[0]
    except Exception:
        pass
    return None

# --- Message Handlers ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id

    referred_by = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith('ref_'):
        try:
            ref_id = int(parts[1].replace('ref_', ''))
            if ref_id != user_id:
                referred_by = ref_id
        except ValueError:
            pass

    add_user_to_db(user_id, referred_by)

    if not is_subscribed(user_id):
        send_force_subscribe_message(message.chat.id)
        return

    credit_referral_if_needed(user_id)

    markup = get_user_keyboard(user_id)
    if user_id == OWNER_ID:
        bot.send_message(message.chat.id, "أهلاً بك يا مطور! 👑 اختر من لوحة التحكم:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "أهلاً بك! 👋 اختر من القائمة الرئيسية:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📢 قناتي")
def send_update_channel_handler(message):
    bot.reply_to(message, f"تفضل بزيارة قناتي لآخر التحديثات: {UPDATE_CHANNEL}")

@bot.message_handler(func=lambda message: message.text == "➕ رفع بوت")
@check_subscription_wrapper
def upload_py_instruction(message):
    if SETTINGS.get('maintenance_mode') == '1' and message.from_user.id != OWNER_ID:
        bot.reply_to(message, "🛠️ المنصة تحت الصيانة حاليًا، جرب تاني بعد شوية.")
        return
    if message.from_user.id != OWNER_ID and not has_active_hosting(message.from_user.id):
        bot.reply_to(message, "⛔ لازم يكون عندك رصيد تشغيل (اشتراك) شغال عشان ترفع بوت. اشحن من زر «💎 الاشتراكات».")
        return
    max_bots = int(SETTINGS.get('max_bots_per_user', 3))
    current_count = len(user_files.get(message.from_user.id, []))
    if message.from_user.id != OWNER_ID and current_count >= max_bots:
        bot.reply_to(message, f"⛔ وصلت للحد الأقصى المسموح به من البوتات ({max_bots}). احذف بوت قديم أو تواصل مع الدعم لزيادة الحد.")
        return
    upload_mode[message.from_user.id] = 'py'
    last_line = "⏳ هيتراجع من المطور قبل ما يشتغل." if SETTINGS.get('require_approval') == '1' else "🚀 هيشتغل تلقائيًا على طول من غير ما يحتاج موافقة."
    bot.reply_to(
        message,
        "📤 <b>رفع بوت (ملف Python واحد)</b>\n\n"
        "ابعت ملف <code>.py</code> بتاع بوتك دلوقتي.\n"
        f"📏 الحد الأقصى للحجم: {SETTINGS.get('max_file_size_mb', 20)} MB\n"
        "🔒 هيتعمل فحص أمان تلقائي للكود قبل القبول.\n"
        f"{last_line}",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == "📦 رفع ZIP")
@check_subscription_wrapper
def upload_zip_instruction(message):
    if SETTINGS.get('maintenance_mode') == '1' and message.from_user.id != OWNER_ID:
        bot.reply_to(message, "🛠️ المنصة تحت الصيانة حاليًا، جرب تاني بعد شوية.")
        return
    if message.from_user.id != OWNER_ID and not has_active_hosting(message.from_user.id):
        bot.reply_to(message, "⛔ لازم يكون عندك رصيد تشغيل (اشتراك) شغال عشان ترفع بوت. اشحن من زر «💎 الاشتراكات».")
        return
    max_bots = int(SETTINGS.get('max_bots_per_user', 3))
    current_count = len(user_files.get(message.from_user.id, []))
    if message.from_user.id != OWNER_ID and current_count >= max_bots:
        bot.reply_to(message, f"⛔ وصلت للحد الأقصى المسموح به من البوتات ({max_bots}). احذف بوت قديم أو تواصل مع الدعم لزيادة الحد.")
        return
    upload_mode[message.from_user.id] = 'zip'
    last_line = "⏳ هيتراجع من المطور قبل ما يشتغل." if SETTINGS.get('require_approval') == '1' else "🚀 هيشتغل تلقائيًا على طول من غير ما يحتاج موافقة."
    bot.reply_to(
        message,
        "📦 <b>رفع بوت متعدد الملفات (ZIP)</b>\n\n"
        "أرسل ملف <code>.zip</code> يحتوي على مجلد البوت كاملاً.\n\n"
        "📌 يُكتشف تلقائيًا:\n"
        "• الملف الرئيسي (main.py / bot.py / app.py / run.py / start.py / index.py)\n"
        "• لو فيه أكتر من ملف محتمل، هسألك تختار\n"
        "• جميع المكتبات من ملف requirements.txt (لو موجود) بتتثبت تلقائيًا\n"
        "• الأكواد الضارة تُرفض تلقائيًا\n\n"
        f"📏 الحد الأقصى: {SETTINGS.get('max_file_size_mb', 20)} MB\n"
        f"{last_line}",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == "🤖 بوتاتي")
@check_subscription_wrapper
def list_user_files(message):
    user_id = message.from_user.id
    files = user_files.get(user_id, [])

    if not files:
        bot.reply_to(message, "ليس لديك أي ملفات مرفوعة حالياً.")
        return

    files_per_page = 5
    total_files = len(files)
    total_pages = (total_files + files_per_page - 1) // files_per_page if total_files > 0 else 0
    current_page = user_pagination_state.get(user_id, {}).get('current_page', 1)

    if total_files == 0: current_page = 0
    elif current_page > total_pages: current_page = total_pages
    elif current_page < 1: current_page = 1

    start_idx = (current_page - 1) * files_per_page
    end_idx = start_idx + files_per_page
    paginated_files = files[start_idx:end_idx]

    user_pagination_state[user_id] = {
        'current_page': current_page,
        'total_pages': total_pages,
        'files': files
    }

    expiry = get_hosting_expiry(user_id)
    expiry_line = f"⏳ رصيد التشغيل شغّال لحد: {expiry.strftime('%Y-%m-%d %H:%M')}\n" if (expiry and expiry > datetime.now()) else "⛔ معندكش رصيد تشغيل شغّال دلوقتي.\n"

    response = f"ملفاتك المرفوعة (الصفحة {current_page}/{total_pages}):\n{expiry_line}\n"
    if not paginated_files:
        response += "لا توجد ملفات في هذه الصفحة."
        markup = types.InlineKeyboardMarkup()
        if total_pages > 1:
            if current_page > 1:
                markup.add(CButton("⬅️ السابق", callback_data=f"user_prev_page_{user_id}", style=STYLE_PRIMARY))
            if current_page < total_pages:
                markup.add(CButton("التالي ➡️", callback_data=f"user_next_page_{user_id}", style=STYLE_PRIMARY))
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    for idx, (file_name, file_type, status, bot_token_id) in enumerate(paginated_files):
        script_key = f"{user_id}_{file_name}"
        is_running = is_bot_running(user_id, file_name) and status == 'approved'

        status_emoji = "⏳ معلق" if status == 'pending' else \
                       "✅ موافق عليه" if status == 'approved' else \
                       "❌ مرفوض" if status == 'rejected' else "❓ غير معروف"

        running_status_emoji = "🟢 يعمل" if is_running else "🔴 متوقف"

        bot_id_display = f" (معرف البوت: `{bot_token_id}`)" if bot_token_id else ""
        response += f"{start_idx + idx + 1}. `{file_name}` ({file_type}) - {status_emoji} - {running_status_emoji}{bot_id_display}\n"

        if status == 'approved':
            start_stop_text = "■ إيقاف" if is_running else "▶ تشغيل"
            start_stop_style = STYLE_DANGER if is_running else STYLE_SUCCESS
            markup.add(
                CButton(f"{start_stop_text} {file_name}", callback_data=f"toggle_{script_key}", style=start_stop_style),
                CButton(f"📋 تفاصيل {file_name}", callback_data=f"detail_{script_key}", style=STYLE_PRIMARY)
            )
        else:
            markup.add(CButton(f"🗑️ حذف {file_name}", callback_data=f"delete_{script_key}", style=STYLE_DANGER))

    if total_pages > 1:
        pagination_buttons = []
        if current_page > 1:
            pagination_buttons.append(CButton("⬅️ السابق", callback_data=f"user_prev_page_{user_id}", style=STYLE_PRIMARY))
        if current_page < total_pages:
            pagination_buttons.append(CButton("التالي ➡️", callback_data=f"user_next_page_{user_id}", style=STYLE_PRIMARY))
        if pagination_buttons:
            markup.add(*pagination_buttons)

    bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "👑 لوحة تحكم المطور")
def developer_panel(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "عذراً، هذه المنطقة مخصصة للمطور فقط.")
        return
    show_dev_hub(message.chat.id)


def show_dev_hub(chat_id, message_id=None):
    approval_state = "🟢 مطلوبة" if SETTINGS.get('require_approval') == '1' else "🔴 مش مطلوبة (تشغيل تلقائي فور الرفع)"
    text = (
        "👑 <b>لوحة تحكم المطور</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"✅ الموافقة اليدوية على الملفات: {approval_state}\n"
        "(تقدر تغيّرها من «⚙️ إعدادات البوت»)\n\n"
        "اختار من القائمة:"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(CButton("👥 كل المستخدمين وملفاتهم", callback_data="dev_hub_files", style=STYLE_PRIMARY))
    markup.add(CButton("📊 الإحصائيات", callback_data="dev_hub_stats", style=STYLE_PRIMARY))
    markup.add(CButton("🎁 إدارة الاشتراكات", callback_data="dev_subscriptions", style=STYLE_SUCCESS))
    markup.add(CButton("🎁 منح اشتراك لمستخدم", callback_data="dev_hub_grant", style=STYLE_SUCCESS))
    markup.add(CButton("⚙️ إعدادات البوت", callback_data="dev_hub_settings", style=STYLE_PRIMARY))
    markup.add(CButton("📢 بث رسالة لكل المستخدمين", callback_data="broadcast_start", style=STYLE_DANGER))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)
        except telebot.apihelper.ApiException:
            bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'dev_hub_files')
def handle_dev_hub_files(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    display_all_user_files(OWNER_ID, 1, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'dev_hub_settings')
def handle_dev_hub_settings(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    show_settings_panel(OWNER_ID, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'dev_hub_stats')
def handle_dev_hub_stats(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    text = build_admin_stats_text()
    markup = types.InlineKeyboardMarkup()
    markup.add(CButton("🔙 رجوع للوحة التحكم", callback_data="dev_hub_back", style=STYLE_PRIMARY))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
    except telebot.apihelper.ApiException:
        bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'dev_hub_back')
def handle_dev_hub_back(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    show_dev_hub(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'dev_hub_grant')
def handle_dev_hub_grant(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        OWNER_ID,
        "🎁 ابعت آيدي المستخدم وعدد الأيام اللي عايز تمنحهاله، بالصيغة:\n"
        "<code>USER_ID DAYS</code>\n"
        "مثال: <code>7885527604 7</code>",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, handle_grant_subscription_input)


def handle_grant_subscription_input(message):
    parts = (message.text or "").strip().split()
    if len(parts) != 2 or not parts[0].lstrip('-').isdigit() or not parts[1].isdigit():
        bot.reply_to(message, "❌ الصيغة غلط. ابعت: USER_ID DAYS (مثال: 7885527604 7)")
        return
    target_id = int(parts[0])
    days = int(parts[1])
    if days <= 0:
        bot.reply_to(message, "❌ عدد الأيام لازم يكون أكبر من صفر.")
        return
    add_user_to_db(target_id)
    new_expiry = add_hosting_days(target_id, days)
    bot.reply_to(
        message,
        f"✅ تم منح <code>{days}</code> يوم للمستخدم <code>{target_id}</code>.\n"
        f"⏳ رصيده شغال لحد: <b>{new_expiry.strftime('%Y-%m-%d %H:%M')}</b>",
        parse_mode='HTML'
    )
    try:
        bot.send_message(
            target_id,
            f"🎁 مبروك! المطور منحك <b>{days}</b> يوم رصيد تشغيل هدية.\n"
            f"⏳ رصيدك شغال لحد: <b>{new_expiry.strftime('%Y-%m-%d %H:%M')}</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        bot.reply_to(message, f"⚠️ تم المنح بس فشل إرسال إشعار للمستخدم: {e}")

# =========================================================
# ⭐ نظام شحن أيام التشغيل بنجوم تليجرام (Telegram Stars / XTR)
# =========================================================
@bot.message_handler(func=lambda message: message.text == "💎 الاشتراكات")
@check_subscription_wrapper
def stars_menu(message):
    if is_frozen(message.from_user.id):
        bot.reply_to(message, "❄️ رصيدك مجمد حاليًا. فك التجميد الأول من زر «❄️ تجميد الاشتراك مؤقتاً».")
        return
    day_price = SETTINGS.get('day_price_stars', '2')
    week_price = SETTINGS.get('week_price_stars', '10')
    month_price = SETTINGS.get('month_price_stars', '30')
    day_price_egp = SETTINGS.get('day_price_egp', '15')
    week_price_egp = SETTINGS.get('week_price_egp', '60')
    month_price_egp = SETTINGS.get('month_price_egp', '200')
    expiry = get_hosting_expiry(message.from_user.id)
    status_txt = (f"⏳ رصيدك الحالي شغّال لحد: <b>{expiry.strftime('%Y-%m-%d %H:%M')}</b>"
                  if (expiry and expiry > datetime.now()) else "⛔ معندكش رصيد تشغيل شغّال دلوقتي.")

    markup = types.InlineKeyboardMarkup()
    markup.add(CButton(f"📅 يوم واحد - {day_price}⭐", callback_data="buy_day", style=STYLE_PRIMARY))
    markup.add(CButton(f"🗓️ أسبوع كامل - {week_price}⭐", callback_data="buy_week", style=STYLE_SUCCESS))
    markup.add(CButton(f"🗓️ شهر كامل - {month_price}⭐", callback_data="buy_month", style=STYLE_SUCCESS))
    markup.add(CButton(f"📅 يوم واحد - {day_price_egp} ج (فودافون كاش)", callback_data="vfcash_day", style=STYLE_PRIMARY))
    markup.add(CButton(f"🗓️ أسبوع - {week_price_egp} ج (فودافون كاش)", callback_data="vfcash_week", style=STYLE_SUCCESS))
    markup.add(CButton(f"🗓️ شهر - {month_price_egp} ج (فودافون كاش)", callback_data="vfcash_month", style=STYLE_SUCCESS))
    markup.add(CButton('🧾 سجل عمليات الدفع', callback_data='my_payment_history', style=STYLE_PRIMARY))
    bot.reply_to(
        message,
        f"💎 <b>الاشتراكات - شحن أيام التشغيل</b>\n\n{status_txt}\n\n"
        "اختار طريقة الدفع والباقة اللي تناسبك:\n"
        "⭐ بنجوم تليجرام (فوري وتلقائي)\n"
        f"📲 أو فودافون كاش على الرقم <code>{VODAFONE_CASH_NUMBER}</code> (بيتراجع من المطور)",
        reply_markup=markup, parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data in ('buy_day', 'buy_week', 'buy_month'))
def handle_buy_callback(call):
    if not is_subscribed(call.from_user.id):
        send_force_subscribe_message(call.message.chat.id)
        bot.answer_callback_query(call.id, "عليك الاشتراك في القناة أولاً.")
        return

    days_map = {'buy_day': 1, 'buy_week': 7, 'buy_month': 30}
    price_key_map = {'buy_day': 'day_price_stars', 'buy_week': 'week_price_stars', 'buy_month': 'month_price_stars'}
    title_map = {'buy_day': 'يوم تشغيل واحد', 'buy_week': 'أسبوع تشغيل كامل', 'buy_month': 'شهر تشغيل كامل'}
    days = days_map[call.data]
    price = int(SETTINGS.get(price_key_map[call.data], days))
    title = title_map[call.data]
    payload = f"hosting_{days}_{call.from_user.id}"

    bot.answer_callback_query(call.id)
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"⭐ {title}",
            description=f"شحن {days} {'يوم' if days == 1 else 'أيام'} تشغيل لبوتاتك على المنصة.",
            invoice_payload=payload,
            provider_token="",  # نجوم تليجرام (XTR) مش محتاجة provider token
            currency="XTR",
            prices=[types.LabeledPrice(label=title, amount=price)]
        )
    except Exception as e:
        logger.error(f"Failed to send invoice: {e}", exc_info=True)
        bot.send_message(call.message.chat.id, f"❌ حصل خطأ أثناء إنشاء فاتورة الدفع: {e}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payload = message.successful_payment.invoice_payload
    charge_id = getattr(message.successful_payment, 'telegram_payment_charge_id', '') or hashlib.sha256((payload + str(message.message_id)).encode()).hexdigest()
    if payment_exists(charge_id):
        bot.send_message(message.chat.id, 'ℹ️ العملية دي اتسجلت قبل كده، ومش هيتضاف رصيد مرتين.')
        return
    try:
        _, days_str, user_id_str = payload.split('_'); days=int(days_str); user_id=int(user_id_str)
    except Exception: days,user_id=0,message.from_user.id
    if days > 0:
        if not record_payment(charge_id,user_id,'Telegram Stars',f'{days} يوم',days,message.successful_payment.total_amount,'XTR','paid',payload):
            bot.send_message(message.chat.id, 'ℹ️ العملية دي اتسجلت بالفعل.'); return
        new_expiry = add_hosting_days(user_id, days)
        bot.send_message(
            message.chat.id,
            f"✅ تم شحن رصيدك بنجاح! تم إضافة {days} {'يوم' if days == 1 else 'أيام'}.\n"
            f"رصيدك شغّال لحد: <b>{new_expiry.strftime('%Y-%m-%d %H:%M')}</b>",
            parse_mode='HTML'
        )
        try:
            bot.send_message(
                OWNER_ID,
                f"💰 عملية شحن جديدة!\nالمستخدم: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                f"المدة: {days} يوم\nالنجوم: {message.successful_payment.total_amount}⭐",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify owner of payment: {e}")

# =========================================================
# 📲 الدفع بفودافون كاش (تحويل يدوي + مراجعة المطور)
# =========================================================
pending_vfcash_claims = {}  # user_id -> {'days': int, 'price': str, 'package': str}

VFCASH_PACKAGES = {
    'vfcash_day':   {'days': 1,  'price_key': 'day_price_egp',   'title': 'يوم تشغيل واحد'},
    'vfcash_week':  {'days': 7,  'price_key': 'week_price_egp',  'title': 'أسبوع تشغيل كامل'},
    'vfcash_month': {'days': 30, 'price_key': 'month_price_egp', 'title': 'شهر تشغيل كامل'},
}

@bot.callback_query_handler(func=lambda call: call.data in VFCASH_PACKAGES)
def handle_vfcash_package_choice(call):
    if not is_subscribed(call.from_user.id):
        send_force_subscribe_message(call.message.chat.id)
        bot.answer_callback_query(call.id, "عليك الاشتراك في القناة أولاً.")
        return

    pkg = VFCASH_PACKAGES[call.data]
    price = SETTINGS.get(pkg['price_key'], '0')
    pending_vfcash_claims[call.from_user.id] = {'days': pkg['days'], 'price': price, 'package': pkg['title']}

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"📲 <b>الدفع بفودافون كاش — {pkg['title']}</b>\n\n"
        f"1️⃣ حوّل مبلغ <b>{price} جنيه</b> على رقم فودافون كاش:\n<code>{VODAFONE_CASH_NUMBER}</code>\n\n"
        "2️⃣ بعد التحويل، ابعت هنا صورة إيصال التحويل (أو رسالة تأكيد التحويل).\n"
        "3️⃣ المطور هيراجع الإيصال ويفعّل رصيدك في أقرب وقت.",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, receive_vfcash_proof)


def receive_vfcash_proof(message):
    user_id = message.from_user.id
    claim = pending_vfcash_claims.get(user_id)
    if not claim:
        bot.reply_to(message, "❌ ملقتش طلب شحن فودافون كاش شغال ليك. ابدأ تاني من زر «💎 الاشتراكات».")
        return

    header = (
        "📲 <b>إثبات دفع فودافون كاش جديد</b>\n"
        f"المستخدم: <a href='tg://user?id={user_id}'>{message.from_user.first_name or 'لا يوجد اسم'}</a> (<code>{user_id}</code>)\n"
        f"اليوزر: @{message.from_user.username or 'غير متوفر'}\n"
        f"الباقة: {claim['package']} ({claim['days']} يوم)\n"
        f"المبلغ المفروض: {claim['price']} جنيه\n"
        f"رقم التحويل: <code>{VODAFONE_CASH_NUMBER}</code>"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        CButton("✅ تأكيد واستلام", callback_data=f"vfok_{user_id}_{claim['days']}", style=STYLE_SUCCESS),
        CButton("❌ رفض", callback_data=f"vfno_{user_id}", style=STYLE_DANGER)
    )
    try:
        bot.send_message(OWNER_ID, header, parse_mode='HTML', reply_markup=markup)
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "✅ استلمنا الإيصال، هيتراجع من المطور وهيتفعّل رصيدك بمجرد التأكيد.")
    except Exception as e:
        logger.error(f"Failed to forward vfcash proof: {e}")
        bot.reply_to(message, "❌ حصل خطأ وإحنا بنبعت الإيصال، حاول تاني.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('vfok_'))
def handle_vfcash_confirm(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    try:
        _, target_id_str, days_str = call.data.split('_')
        target_id = int(target_id_str)
        days = int(days_str)
    except Exception:
        bot.answer_callback_query(call.id, "خطأ في بيانات الطلب.")
        return

    claim = pending_vfcash_claims.pop(target_id, None)
    add_user_to_db(target_id)
    new_expiry = add_hosting_days(target_id, days)
    payment_key = f"vfcash:{target_id}:{call.message.message_id}:{days}"
    if claim:
        record_payment(payment_key, target_id, 'Vodafone Cash', claim.get('package', f'{days} يوم'), days, claim.get('price', '0'), 'EGP', 'paid', 'manual_confirmation')

    bot.answer_callback_query(call.id, "✅ تم التفعيل.")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, f"✅ تم تفعيل {days} يوم للمستخدم <code>{target_id}</code>.", parse_mode='HTML')
    try:
        bot.send_message(
            target_id,
            f"✅ تم تأكيد تحويلك وتفعيل <b>{days}</b> يوم رصيد تشغيل.\n"
            f"⏳ رصيدك شغّال لحد: <b>{new_expiry.strftime('%Y-%m-%d %H:%M')}</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to notify user of vfcash confirmation: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('vfno_'))
def handle_vfcash_reject(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    target_id = int(call.data.split('_', 1)[1])
    pending_vfcash_claims.pop(target_id, None)

    bot.answer_callback_query(call.id, "❌ تم الرفض.")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    try:
        bot.send_message(
            target_id,
            "❌ للأسف مقدرناش نأكد تحويلك بفودافون كاش. تواصل مع «🎫 الدعم» لو فيه استفسار."
        )
    except Exception as e:
        logger.error(f"Failed to notify user of vfcash rejection: {e}")

# =========================================================
# 🎁 نظام دعوة الأصدقاء
# =========================================================
@bot.message_handler(func=lambda message: message.text == "🎁 دعوة الأصدقاء")
@check_subscription_wrapper
def referral_menu(message):
    user_id = message.from_user.id
    username = BOT_USERNAME or "your_bot"
    link = f"https://t.me/{username}?start=ref_{user_id}"
    credited, total = get_referral_stats(user_id)
    reward = SETTINGS.get('referral_reward_days', '1')
    reward_points = SETTINGS.get('referral_points_reward', '50')
    bot.reply_to(
        message,
        f"🎁 <b>نظام دعوة الأصدقاء</b>\n\n"
        f"ابعت الرابط ده لأصحابك، وكل واحد يدخل يشترك بيه، هتاخد <b>{reward}</b> يوم تشغيل مجاني ⭐ "
        f"و<b>{reward_points}</b> نقطة 💎 (تقدر تحولها لاحقًا لأيام إضافية من «🎰 تجميع نقاط»)\n\n"
        f"🔗 رابطك: {link}\n\n"
        f"👥 عدد اللي دخلوا برابطك: {total}\n"
        f"✅ عدد اللي اتحسبلك منهم: {credited}",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

# =========================================================
# 🎰 نظام تجميع النقاط (عجلة الحظ + هدايا + اشتراك + تحويل لأيام)
# كل الأرقام هنا بتتقرأ من SETTINGS، فتقدر تغيّرها في أي وقت من
# «⚙️ إعدادات البوت» بدون ما تلمس الكود خالص.
# =========================================================

def build_points_menu(user_id):
    points = get_points(user_id)
    points_per_day = max(1, int(SETTINGS.get('points_per_day', 100)))
    days_equiv = points // points_per_day

    text = (
        "🎰 <b>تجميع النقاط</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"💎 رصيدك الحالي: <b>{points}</b> نقطة (≈ {days_equiv} يوم تشغيل)\n"
        f"💱 كل <b>{points_per_day}</b> نقطة = يوم تشغيل واحد\n\n"
        "اختر طريقة لجمع نقاط:\n"
        f"🎡 عجلة الحظ: {SETTINGS.get('wheel_min_points')}-{SETTINGS.get('wheel_max_points')} نقطة (مرة يوميًا)\n"
        f"🎁 الهدية اليومية: +{SETTINGS.get('daily_gift_points')} نقطة\n"
        f"🎉 الهدية الأسبوعية: +{SETTINGS.get('weekly_gift_points')} نقطة\n"
        f"📢 الاشتراك بالقنوات: +{SETTINGS.get('channel_sub_points_bonus')} نقطة (مرة واحدة بس)\n"
        f"🤝 دعوة صديق: +{SETTINGS.get('referral_points_reward')} نقطة لكل صديق يشترك\n"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(CButton("🎡 عجلة الحظ", callback_data="pts_wheel", style=STYLE_SUCCESS))
    markup.add(
        CButton("🎁 الهدية اليومية", callback_data="pts_daily", style=STYLE_SUCCESS),
        CButton("🎉 الهدية الأسبوعية", callback_data="pts_weekly", style=STYLE_SUCCESS)
    )
    markup.add(CButton("📢 الاشتراك بالقنوات", callback_data="pts_sub", style=STYLE_PRIMARY))
    markup.add(CButton("🤝 دعوة صديق", callback_data="pts_ref", style=STYLE_PRIMARY))
    markup.add(CButton("🔄 تحويل نقاطي لأيام تشغيل", callback_data="pts_redeem", style=STYLE_DANGER))
    markup.add(CButton("🔃 تحديث الرصيد", callback_data="pts_refresh", style=STYLE_PRIMARY))
    return text, markup

def show_points_menu(chat_id, user_id, message_id=None):
    text, markup = build_points_menu(user_id)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)
        except telebot.apihelper.ApiException as e:
            if "message is not modified" not in str(e):
                bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🎰 تجميع نقاط")
@check_subscription_wrapper
def points_menu_handler(message):
    show_points_menu(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_refresh')
def handle_pts_refresh(call):
    bot.answer_callback_query(call.id, "✅ تم التحديث.")
    show_points_menu(call.message.chat.id, call.from_user.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_daily')
def handle_pts_daily(call):
    user_id = call.from_user.id
    last_daily, _, _, _ = get_points_state(user_id)
    allowed, next_time = check_cooldown(last_daily, 24)
    if not allowed:
        bot.answer_callback_query(call.id, f"⏳ استنى {format_remaining(next_time)} عشان تاخد الهدية اليومية تاني.", show_alert=True)
        return
    amount = int(SETTINGS.get('daily_gift_points', 10))
    add_points(user_id, amount)
    set_points_timestamp(user_id, 'last_daily_gift', datetime.now().isoformat())
    bot.answer_callback_query(call.id, f"🎁 مبروك! خدت {amount} نقطة هدية يومية.", show_alert=True)
    show_points_menu(call.message.chat.id, user_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_weekly')
def handle_pts_weekly(call):
    user_id = call.from_user.id
    _, last_weekly, _, _ = get_points_state(user_id)
    allowed, next_time = check_cooldown(last_weekly, 24 * 7)
    if not allowed:
        bot.answer_callback_query(call.id, f"⏳ استنى {format_remaining(next_time)} عشان تاخد الهدية الأسبوعية تاني.", show_alert=True)
        return
    amount = int(SETTINGS.get('weekly_gift_points', 50))
    add_points(user_id, amount)
    set_points_timestamp(user_id, 'last_weekly_gift', datetime.now().isoformat())
    bot.answer_callback_query(call.id, f"🎉 مبروك! خدت {amount} نقطة هدية أسبوعية.", show_alert=True)
    show_points_menu(call.message.chat.id, user_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_wheel')
def handle_pts_wheel(call):
    user_id = call.from_user.id
    _, _, last_wheel, _ = get_points_state(user_id)
    allowed, next_time = check_cooldown(last_wheel, 24)
    if not allowed:
        bot.answer_callback_query(call.id, f"⏳ استنى {format_remaining(next_time)} عشان تلعب عجلة الحظ تاني.", show_alert=True)
        return
    min_p = int(SETTINGS.get('wheel_min_points', 10))
    max_p = int(SETTINGS.get('wheel_max_points', 1000))
    if min_p > max_p:
        min_p, max_p = max_p, min_p
    won = random.randint(min_p, max_p)
    add_points(user_id, won)
    set_points_timestamp(user_id, 'last_wheel_spin', datetime.now().isoformat())
    bot.answer_callback_query(call.id, f"🎡 العجلة دارت... مبروك! ربحت {won} نقطة 🎉", show_alert=True)
    show_points_menu(call.message.chat.id, user_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_sub')
def handle_pts_sub(call):
    user_id = call.from_user.id
    _, _, _, already_claimed = get_points_state(user_id)
    if already_claimed:
        bot.answer_callback_query(call.id, "ℹ️ خدت مكافأة الاشتراك دي قبل كده.", show_alert=True)
        return
    if not is_subscribed(user_id):
        bot.answer_callback_query(
            call.id,
            f"🚫 لازم تشترك في القناة {FORCE_SUBSCRIBE_CHANNEL_ID} الأول عشان تاخد المكافأة.",
            show_alert=True
        )
        return
    amount = int(SETTINGS.get('channel_sub_points_bonus', 20))
    add_points(user_id, amount)
    mark_channel_sub_bonus_claimed(user_id)
    bot.answer_callback_query(call.id, f"📢 تم التأكد من اشتراكك! خدت {amount} نقطة.", show_alert=True)
    show_points_menu(call.message.chat.id, user_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'pts_ref')
def handle_pts_ref(call):
    user_id = call.from_user.id
    username = BOT_USERNAME or "your_bot"
    link = f"https://t.me/{username}?start=ref_{user_id}"
    reward_points = SETTINGS.get('referral_points_reward', '50')
    reward_days = SETTINGS.get('referral_reward_days', '1')
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"🤝 <b>دعوة صديق</b>\n\n"
        f"ابعت الرابط ده لأصحابك، وكل واحد يدخل يشترك، هتاخد <b>{reward_points}</b> نقطة 💎 "
        f"و<b>{reward_days}</b> يوم تشغيل مجاني ⭐\n\n"
        f"🔗 رابطك: {link}",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

@bot.callback_query_handler(func=lambda call: call.data == 'pts_redeem')
def handle_pts_redeem(call):
    user_id = call.from_user.id
    points = get_points(user_id)
    points_per_day = max(1, int(SETTINGS.get('points_per_day', 100)))
    days = points // points_per_day
    if days < 1:
        bot.answer_callback_query(
            call.id,
            f"❌ لسه معندكش نقاط كفاية. محتاج {points_per_day} نقطة على الأقل لتحويل يوم واحد (رصيدك: {points}).",
            show_alert=True
        )
        return
    cost = days * points_per_day
    deduct_points(user_id, cost)
    new_expiry = add_hosting_days(user_id, days)
    bot.answer_callback_query(call.id, f"✅ تم تحويل {cost} نقطة إلى {days} يوم تشغيل!", show_alert=True)
    try:
        bot.send_message(
            call.message.chat.id,
            f"🔄 تم تحويل <b>{cost}</b> نقطة إلى <b>{days}</b> يوم تشغيل.\n"
            f"⏳ رصيدك شغّال لحد: <b>{new_expiry.strftime('%Y-%m-%d %H:%M')}</b>",
            parse_mode='HTML'
        )
    except Exception:
        pass
    show_points_menu(call.message.chat.id, user_id, call.message.message_id)

# =========================================================
# 📊 إحصائياتي (شخصية للمستخدم / لوحة عامة للمطور)
# =========================================================
def build_admin_stats_text():
    all_files = get_all_user_files_from_db()
    total_bots = len(all_files)
    approved = sum(1 for f in all_files if f['status'] == 'approved')
    pending = sum(1 for f in all_files if f['status'] == 'pending')
    rejected = sum(1 for f in all_files if f['status'] == 'rejected')
    running_now = len(bot_scripts)
    total_users = len(set(f['user_id'] for f in all_files))

    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM active_users')
        total_started_bot = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM active_users WHERE hosting_expiry IS NOT NULL AND hosting_expiry > ?", (datetime.now().isoformat(),))
        active_subs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM active_users WHERE frozen = 1")
        frozen_count = c.fetchone()[0]
        conn.close()

    try:
        cpu_percent = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(BASE_DIR)
        sys_line = (f"🖥️ السيرفر: CPU {cpu_percent}% | RAM {ram.percent}% "
                    f"({ram.used // (1024*1024)}MB/{ram.total // (1024*1024)}MB) | "
                    f"تخزين {disk.percent}%\n")
    except Exception:
        sys_line = ""

    return (
        "👑 <b>لوحة إحصائيات المطور</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"👥 إجمالي المستخدمين اللي بدأوا البوت: <b>{total_started_bot}</b>\n"
        f"💎 مشتركين برصيد شغال دلوقتي: <b>{active_subs}</b>\n"
        f"❄️ مجمدين الاشتراك: <b>{frozen_count}</b>\n"
        f"📁 مستخدمين رفعوا بوتات: <b>{total_users}</b>\n\n"
        f"🤖 إجمالي البوتات المرفوعة: <b>{total_bots}</b>\n"
        f"  ✅ موافق عليها: {approved} | ⏳ معلقة: {pending} | ❌ مرفوضة: {rejected}\n"
        f"🟢 شغالة دلوقتي فعليًا: <b>{running_now}</b>\n\n"
        f"{sys_line}"
    )


@bot.message_handler(func=lambda message: message.text == "📊 إحصائياتي")
@check_subscription_wrapper
def stats_handler(message):
    user_id = message.from_user.id

    if user_id == OWNER_ID:
        bot.reply_to(message, build_admin_stats_text(), parse_mode='HTML')
        return

    files = user_files.get(user_id, [])
    total = len(files)
    approved = sum(1 for f in files if f[2] == 'approved')
    running = sum(1 for f in files if f[2] == 'approved' and is_bot_running(user_id, f[0]))
    pending = sum(1 for f in files if f[2] == 'pending')

    total_ram = 0.0
    for file_name, file_type, status, bot_token_id in files:
        script_key = f"{user_id}_{file_name}"
        if script_key in bot_scripts:
            try:
                proc = psutil.Process(bot_scripts[script_key]['process'].pid)
                total_ram += proc.memory_info().rss / (1024 * 1024)
            except Exception:
                pass

    expiry = get_hosting_expiry(user_id)
    if is_frozen(user_id):
        status_txt = "❄️ الاشتراك مجمد مؤقتًا"
    elif expiry and expiry > datetime.now():
        remaining = expiry - datetime.now()
        status_txt = f"✅ شغال لحد {expiry.strftime('%Y-%m-%d %H:%M')} (متبقي {remaining.days} يوم {remaining.seconds // 3600} ساعة)"
    else:
        status_txt = "⛔ مفيش رصيد شغال"

    credited, total_refs = get_referral_stats(user_id)
    row = get_user_record(user_id)
    join_date_txt = ""
    if row and row[4]:
        try:
            join_date_txt = datetime.fromisoformat(row[4]).strftime('%Y-%m-%d')
        except Exception:
            join_date_txt = ""

    text = (
        "📊 <b>إحصائياتي</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🤖 عدد بوتاتك: <b>{total}</b> (✅ {approved} | ⏳ {pending})\n"
        f"🟢 شغالة دلوقتي: <b>{running}</b>\n"
        f"🧠 استهلاك الرام الكلي: <b>{total_ram:.1f} MB</b>\n\n"
        f"💎 حالة الاشتراك: {status_txt}\n\n"
        f"🎁 دعوات ناجحة: <b>{credited}</b> من أصل {total_refs}\n"
        f"📅 تاريخ الانضمام: {join_date_txt or 'غير معروف'}"
    )
    bot.reply_to(message, text, parse_mode='HTML')

# =========================================================
# 📖 الدليل و 📜 القواعد
# =========================================================
@bot.message_handler(func=lambda message: message.text == "📖 الدليل")
@check_subscription_wrapper
def guide_handler(message):
    text = (
        "📖 <b>دليل استخدام المنصة</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "1️⃣ اشحن رصيد تشغيل من زر «💎 الاشتراكات».\n"
        "2️⃣ ارفع بوتك: ملف بايثون واحد من «➕ رفع بوت»، أو مجلد كامل مضغوط من «📦 رفع ZIP».\n"
        "3️⃣ استنى موافقة المطور، هتوصلك رسالة تأكيد.\n"
        "4️⃣ بعد الموافقة، البوت هيشتغل تلقائيًا وتقدر تديره من «🤖 بوتاتي» (تشغيل / إيقاف / سجل / إعدادات).\n"
        "5️⃣ لو بوتك محتاج توكن أو متغيرات بيئة، ضيفها من صفحة تفاصيل البوت ← «⚙️ الإعدادات».\n"
        "6️⃣ مش هتستخدم رصيدك؟ جمده مؤقتًا من «❄️ تجميد الاشتراك مؤقتاً» وارجع فكّه أي وقت.\n\n"
        "❓ لأي استفسار، دوس «🎫 الدعم»."
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📜 القواعد")
@check_subscription_wrapper
def rules_handler(message):
    max_size = SETTINGS.get('max_file_size_mb', '20')
    max_bots = SETTINGS.get('max_bots_per_user', '3')
    text = (
        "📜 <b>قواعد الاستضافة</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "✅ مسموح: أي بوت تليجرام شرعي ومكتباته العادية.\n"
        "🚫 محظور تمامًا:\n"
        "  • Malware / فيروسات أو أكواد ضارة\n"
        "  • محاولات اختراق الخادم\n"
        "  • Keyloggers أو أي أداة تجسس\n"
        "  • تعدين عملات، هجمات DDoS، أو سبام جماعي\n\n"
        f"📏 الحد الأقصى لحجم الملف: {max_size} MB\n"
        f"🤖 الحد الأقصى لعدد البوتات لكل مستخدم: {max_bots}\n\n"
        "⚠️ أي مخالفة بتؤدي لحذف البوت وحظر الحساب فورًا بدون استرجاع الرصيد."
    )
    bot.reply_to(message, text, parse_mode='HTML')

# =========================================================
# ❄️ تجميد / فك تجميد الاشتراك مؤقتاً
# =========================================================
@bot.message_handler(func=lambda message: message.text == "❄️ تجميد الاشتراك مؤقتاً")
@check_subscription_wrapper
def freeze_handler(message):
    user_id = message.from_user.id
    if is_frozen(user_id):
        ok, result = unfreeze_subscription(user_id)
        if ok:
            bot.reply_to(message, f"✅ تم فك التجميد! رصيدك شغّال تاني لحد: <b>{result.strftime('%Y-%m-%d %H:%M')}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, result)
        return

    ok, result = freeze_subscription(user_id)
    if ok:
        hours = int(result // 3600)
        bot.reply_to(
            message,
            f"❄️ تم تجميد رصيدك بنجاح ({hours} ساعة متبقية محفوظة).\n"
            "تم إيقاف بوتاتك مؤقتًا ولن يُستهلك رصيدك لحد ما تفك التجميد بنفس الزر.",
            parse_mode='HTML'
        )
    else:
        bot.reply_to(message, result)

# =========================================================
# 📩 تواصل مع المطور (رسائل ثنائية الاتجاه)
# =========================================================
@bot.message_handler(func=lambda message: message.text == "🎫 الدعم")
@check_subscription_wrapper
def contact_dev_start(message):
    if message.from_user.id == OWNER_ID:
        bot.reply_to(message, "انت المطور أصلاً يا كبير 😄")
        return
    msg = bot.reply_to(message, "✍️ اكتب رسالتك دلوقتي وهتوصل للمطور على طول (تقدر تبعت نص أو صورة أو ملف):")
    bot.register_next_step_handler(msg, forward_message_to_dev)

def forward_message_to_dev(message):
    user = message.from_user
    header = (
        f"📩 <b>رسالة جديدة من مستخدم</b>\n"
        f"الاسم: {user.first_name or ''} {user.last_name or ''}\n"
        f"اليوزر: @{user.username or 'لا يوجد'}\n"
        f"الآيدي: <code>{user.id}</code>"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(CButton("↩️ رد على الرسالة", callback_data=f"replyto_{user.id}", style=STYLE_PRIMARY))
    try:
        bot.send_message(OWNER_ID, header, parse_mode='HTML', reply_markup=markup)
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "✅ اتبعتت رسالتك للمطور، هيرد عليك في أقرب وقت.")
    except Exception as e:
        logger.error(f"Failed to forward message to dev: {e}")
        bot.reply_to(message, "❌ حصل خطأ وإحنا بنبعت رسالتك، حاول تاني.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('replyto_'))
def handle_reply_to_user(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    target_user_id = int(call.data.split('_', 1)[1])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(OWNER_ID, f"✍️ اكتب ردك على المستخدم <code>{target_user_id}</code>:", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: send_dev_reply(m, target_user_id))

def send_dev_reply(message, target_user_id):
    try:
        bot.send_message(target_user_id, f"📬 <b>رد من المطور:</b>\n\n{message.text}", parse_mode='HTML')
        bot.reply_to(message, "✅ اتبعت الرد بنجاح.")
    except Exception as e:
        bot.reply_to(message, f"❌ فشل إرسال الرد: {e}")

# =========================================================
# ⚙️ لوحة إعدادات المطور (تتحكم في كل الأسعار والمكافآت)
# =========================================================
@bot.message_handler(func=lambda message: message.text == "⚙️ إعدادات البوت")
def settings_panel(message):
    if message.from_user.id != OWNER_ID:
        return
    show_settings_panel(message.chat.id)

SETTINGS_LABELS = {
    'day_price_stars': ('📅 سعر اليوم (نجوم)', '⭐'),
    'week_price_stars': ('🗓️ سعر الأسبوع (نجوم)', '⭐'),
    'month_price_stars': ('🗓️ سعر الشهر (نجوم)', '⭐'),
    'day_price_egp': ('📅 سعر اليوم (فودافون كاش)', 'جنيه'),
    'week_price_egp': ('🗓️ سعر الأسبوع (فودافون كاش)', 'جنيه'),
    'month_price_egp': ('🗓️ سعر الشهر (فودافون كاش)', 'جنيه'),
    'referral_reward_days': ('🎁 مكافأة الدعوة', 'يوم'),
    'max_bots_per_user': ('🤖 حد البوتات لكل مستخدم', 'بوت'),
    'max_file_size_mb': ('📏 حد حجم الملف', 'MB'),
    'max_restart_attempts': ('🔁 حد محاولات إعادة التشغيل', 'محاولة'),
    'points_per_day': ('💱 سعر تحويل النقاط', 'نقطة = يوم تشغيل'),
    'daily_gift_points': ('🎁 نقاط الهدية اليومية', 'نقطة'),
    'weekly_gift_points': ('🎉 نقاط الهدية الأسبوعية', 'نقطة'),
    'wheel_min_points': ('🎡 أقل نقاط في عجلة الحظ', 'نقطة'),
    'wheel_max_points': ('🎡 أعلى نقاط في عجلة الحظ', 'نقطة'),
    'referral_points_reward': ('🤝 نقاط الإحالة', 'نقطة'),
    'channel_sub_points_bonus': ('📢 نقاط الاشتراك بالقناة', 'نقطة'),
    'install_timeout_seconds': ('⏱️ مهلة تثبيت المكتبات', 'ثانية'),
    'max_venv_size_mb': ('💾 أقصى حجم لبيئة البوت', 'MB'),
    'max_zip_uncompressed_mb': ('📦 أقصى حجم ZIP بعد الفك', 'MB'),
    'max_zip_files': ('📁 أقصى عدد ملفات داخل ZIP', 'ملف'),
    'max_log_kb': ('📝 أقصى حجم للسجل', 'KB'),
    'broadcast_delay_ms': ('📢 تأخير البث بين الرسائل', 'ms'),
    'payment_history_limit': ('💳 عدد عمليات سجل الدفع', 'عملية'),
}
TOGGLE_SETTINGS_LABELS = {
    'auto_fix_modules': '🔧 الإصلاح التلقائي للمكتبات الناقصة',
    'maintenance_mode': '🛠️ وضع الصيانة',
    'require_approval': '✅ الموافقة اليدوية على الملفات المرفوعة',
}

def show_settings_panel(chat_id, message_id=None):
    lines = ["⚙️ <b>لوحة إعدادات المطور المتقدمة</b>", "━━━━━━━━━━━━━━━", "💰 <b>الأسعار والمكافآت</b>"]
    markup = types.InlineKeyboardMarkup()
    for key in ['day_price_stars', 'week_price_stars', 'month_price_stars',
                'day_price_egp', 'week_price_egp', 'month_price_egp', 'referral_reward_days']:
        label, unit = SETTINGS_LABELS[key]
        lines.append(f"{label}: <b>{SETTINGS.get(key)}</b> {unit}")
        markup.add(CButton(f"✏️ {label}", callback_data=f"set_{key}", style=STYLE_PRIMARY))

    lines.append("\n🛠️ <b>حدود المنصة</b>")
    for key in ['max_bots_per_user', 'max_file_size_mb', 'max_restart_attempts']:
        label, unit = SETTINGS_LABELS[key]
        lines.append(f"{label}: <b>{SETTINGS.get(key)}</b> {unit}")
        markup.add(CButton(f"✏️ {label}", callback_data=f"set_{key}", style=STYLE_PRIMARY))

    lines.append("\n🚀 <b>الأداء والموارد</b>")
    for key in ['install_timeout_seconds','max_venv_size_mb','max_zip_uncompressed_mb','max_zip_files','max_log_kb','broadcast_delay_ms','payment_history_limit']:
        label,unit=SETTINGS_LABELS[key]; lines.append(f"{label}: <b>{SETTINGS.get(key)}</b> {unit}"); markup.add(CButton(f"✏️ {label}",callback_data=f"set_{key}",style=STYLE_PRIMARY))

    lines.append("\n💎 <b>نظام النقاط</b>")
    for key in ['points_per_day', 'daily_gift_points', 'weekly_gift_points',
                'wheel_min_points', 'wheel_max_points', 'referral_points_reward',
                'channel_sub_points_bonus']:
        label, unit = SETTINGS_LABELS[key]
        lines.append(f"{label}: <b>{SETTINGS.get(key)}</b> {unit}")
        markup.add(CButton(f"✏️ {label}", callback_data=f"set_{key}", style=STYLE_PRIMARY))

    lines.append("\n🔀 <b>مفاتيح تشغيل/إيقاف</b>")
    for key, label in TOGGLE_SETTINGS_LABELS.items():
        state = "🟢 مفعّل" if SETTINGS.get(key) == '1' else "🔴 معطّل"
        lines.append(f"{label}: {state}")
        markup.add(CButton(f"🔀 {label}", callback_data=f"togset_{key}", style=STYLE_DANGER if SETTINGS.get(key) == '1' else STYLE_SUCCESS))

    markup.add(CButton("📢 بث رسالة لكل المستخدمين", callback_data="broadcast_start", style=STYLE_DANGER))
    markup.add(CButton("♻️ استعادة الإعدادات الافتراضية", callback_data="reset_settings", style=STYLE_DANGER))

    text = "\n".join(lines)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)
        except telebot.apihelper.ApiException:
            bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_'))
def handle_setting_edit(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    key = call.data[len('set_'):]
    label = SETTINGS_LABELS.get(key, (key,))[0]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(OWNER_ID, f"✍️ ابعت القيمة الجديدة (رقم صحيح) لـ {label}:", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: apply_setting_change(m, key))

def apply_setting_change(message, key):
    value = message.text.strip()
    if not value.isdigit():
        bot.reply_to(message, "❌ لازم تبعت رقم صحيح.")
        return
    set_setting(key, value)
    bot.reply_to(message, f"✅ تم تحديث الإعداد بنجاح.")
    show_settings_panel(OWNER_ID)

@bot.callback_query_handler(func=lambda call: call.data.startswith('togset_'))
def handle_toggle_setting(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    key = call.data[len('togset_'):]
    new_value = '0' if SETTINGS.get(key) == '1' else '1'
    set_setting(key, new_value)
    bot.answer_callback_query(call.id, "✅ تم التحديث.")
    show_settings_panel(OWNER_ID, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'reset_settings')
def handle_reset_settings(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    for k, v in DEFAULT_SETTINGS.items():
        set_setting(k, v)
    bot.answer_callback_query(call.id, "✅ تم استعادة الإعدادات الافتراضية.")
    show_settings_panel(OWNER_ID, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'broadcast_start')
def handle_broadcast_start(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك.")
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(OWNER_ID, "📢 ابعت الرسالة اللي عايز تبثها لكل المستخدمين:")
    bot.register_next_step_handler(msg, handle_broadcast_send)

def handle_broadcast_send(message):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id FROM active_users')
        all_user_ids = [row[0] for row in c.fetchall()]
        conn.close()

    sent, failed = 0, 0
    status_msg = bot.reply_to(message, f"📢 جارٍ الإرسال لـ {len(all_user_ids)} مستخدم...")
    for uid in all_user_ids:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
        time.sleep(0.05)
    try:
        bot.edit_message_text(f"✅ تم البث! نجح: {sent} | فشل: {failed}", status_msg.chat.id, status_msg.message_id)
    except Exception:
        bot.send_message(message.chat.id, f"✅ تم البث! نجح: {sent} | فشل: {failed}")

# --- Upload Handling ---
@bot.message_handler(content_types=['document'])
@check_subscription_wrapper
def handle_document(message):
    user_id = message.from_user.id
    file_info = message.document
    try:
        file_name = safe_upload_filename(file_info.file_name)
    except ValueError as exc:
        bot.reply_to(message, f"❌ {exc}")
        return
    file_id = file_info.file_id
    file_extension = os.path.splitext(file_name)[1].lower()

    if file_extension not in ['.py', '.zip']:
        bot.reply_to(
            message,
            "❌ نوع الملف غير مدعوم.\nيرجى إرسال ملف بايثون (`.py`) أو ملف مضغوط (`.zip`).",
            parse_mode="Markdown"
        )
        return

    if user_id != OWNER_ID and not has_active_hosting(user_id):
        bot.reply_to(
            message,
            "⛔ لازم يكون عندك رصيد تشغيل (اشتراك) شغال عشان ترفع وتشغّل بوت.\n"
            "اشحن من زر «💎 الاشتراكات»، أو استنى المطور يمنحك اشتراك هدية."
        )
        return

    expected_mode = upload_mode.get(user_id)
    if expected_mode is None:
        bot.reply_to(message, "ℹ️ اختار الأول «➕ رفع بوت» أو «📦 رفع ZIP» من القائمة الرئيسية، وبعدها ابعت الملف.")
        return
    if expected_mode == 'py' and file_extension != '.py':
        bot.reply_to(message, "❌ اخترت «➕ رفع بوت» ده مخصص لملف .py بس. لو معاك مجلد كامل استخدم زر «📦 رفع ZIP».")
        return
    if expected_mode == 'zip' and file_extension != '.zip':
        bot.reply_to(message, "❌ اخترت «📦 رفع ZIP» ده مخصص لملف .zip بس. لو معاك ملف واحد استخدم زر «➕ رفع بوت».")
        return

    max_size_bytes = int(SETTINGS.get('max_file_size_mb', 20)) * 1024 * 1024
    if file_info.file_size and file_info.file_size > max_size_bytes:
        bot.reply_to(message, f"❌ حجم الملف أكبر من المسموح ({SETTINGS.get('max_file_size_mb', 20)} MB).")
        return

    upload_mode.pop(user_id, None)
    bot.reply_to(message, "جارٍ تنزيل ملفك... ⏳")
    user_folder = get_user_folder(user_id)
    local_file_path = os.path.join(user_folder, file_name)

    try:
        file_path_on_telegram = bot.get_file(file_id).file_path
        downloaded_file_content = bot.download_file(file_path_on_telegram)

        with open(local_file_path, 'wb') as f:
            f.write(downloaded_file_content)

        bot_id_from_token = None
        needs_bot_token_env = False
        py_contents = []

        if file_extension == '.py':
            try:
                with open(local_file_path, 'r', encoding='utf-8', errors='ignore') as f_py:
                    content = f_py.read()
                    py_contents.append(content)
                    token_match = re.search(r'(?:bot|Bot|BOT|token|Token|TOKEN)\s*=\s*[\'"]([0-9]{9}:[a-zA-Z0-9_-]{35})[\'"]', content)
                    if token_match:
                        bot_id_from_token = get_bot_id_from_token(token_match.group(1))
            except Exception as e:
                logger.warning(f"Failed to extract token from .py file {file_name}: {e}")
        elif file_extension == '.zip':
            try:
                with zipfile.ZipFile(local_file_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        if os.path.isabs(member) or ".." in member:
                            raise ValueError("مسار غير آمن داخل الملف المضغوط.")
                        if member.endswith('.py'):
                            with zip_ref.open(member, 'r') as py_file_in_zip:
                                content = py_file_in_zip.read().decode('utf-8', errors='ignore')
                                py_contents.append(content)
                                if not bot_id_from_token:
                                    token_match = re.search(r'(?:bot|Bot|BOT|token|Token|TOKEN)\s*=\s*[\'"]([0-9]{9}:[a-zA-Z0-9_-]{35})[\'"]', content)
                                    if token_match:
                                        bot_id_from_token = get_bot_id_from_token(token_match.group(1))
            except zipfile.BadZipFile:
                if os.path.exists(local_file_path): os.remove(local_file_path)
                bot.reply_to(message, "❌ ملف الـ ZIP تالف أو مش صالح.")
                return
            except ValueError as ve:
                if os.path.exists(local_file_path): os.remove(local_file_path)
                bot.reply_to(message, f"❌ رُفض الملف: {ve}")
                return
            except Exception as e:
                logger.warning(f"Failed to extract token from .zip file {file_name}: {e}")

        full_code = "\n".join(py_contents)

        # 🔒 فحص ساكن سريع قبل قبول الملف.
        def static_security_scan(code):
            blocked_imports={'pyautogui','pynput','keyboard','mouse','scapy','mitmproxy','netfilterqueue','impacket'}
            blocked_calls={'os.system','os.popen','subprocess.run','subprocess.Popen','subprocess.call','subprocess.check_call','subprocess.check_output'}
            try: tree=ast.parse(code)
            except SyntaxError as exc: return False,f'خطأ صياغة Python: {exc}'
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    bad=next((a.name.split('.')[0] for a in node.names if a.name.split('.')[0] in blocked_imports),None)
                    if bad:return False,f'استيراد غير مسموح: {bad}'
                elif isinstance(node,ast.ImportFrom) and node.module and node.module.split('.')[0] in blocked_imports:return False,f'استيراد غير مسموح: {node.module}'
                elif isinstance(node,ast.Call):
                    if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name):
                        name=f'{node.func.value.id}.{node.func.attr}'
                        if name in blocked_calls:return False,f'استدعاء نظام غير مسموح: {name}'
                    if isinstance(node.func,ast.Name) and node.func.id in {'eval','exec','compile'}:return False,f'استخدام غير مسموح: {node.func.id}'
            return True,None
        scan_ok,scan_reason=static_security_scan(full_code)
        if not scan_ok:
            try: os.remove(local_file_path)
            except OSError: pass
            bot.reply_to(message,f"❌ تم رفض الملف في فحص الأمان.\n<code>{html.escape(scan_reason)}</code>",parse_mode='HTML'); return

        # 🔑 التأكد لو الكود محتاج BOT_TOKEN من متغيرات البيئة ومفيش توكن جاهز في الكود
        if not bot_id_from_token and re.search(r'os\.(environ\.get|getenv)\(\s*[\'"]BOT_TOKEN[\'"]', full_code):
            needs_bot_token_env = True

        current_user_files = user_files.setdefault(user_id, [])
        found_existing = False
        for i, (fname, ftype, fstatus, f_bot_id) in enumerate(current_user_files):
            if fname == file_name:
                current_user_files[i] = (file_name, file_extension, 'pending', bot_id_from_token)
                found_existing = True
                break
        if not found_existing:
            current_user_files.append((file_name, file_extension, 'pending', bot_id_from_token))

        update_user_file_db(user_id, file_name, file_extension, 'pending', bot_id_from_token)

        bot_id_text = f"\nمعرف البوت المستخرج: <code>{bot_id_from_token}</code>" if bot_id_from_token else ""
        token_warning_text = "\n⚠️ الكود بيقرأ BOT_TOKEN من متغيرات البيئة، هيتطلب من المستخدم إدخاله." if needs_bot_token_env else ""
        require_approval = SETTINGS.get('require_approval', '0') == '1'

        if require_approval:
            bot.reply_to(
                message,
                "✅ تم استلام ملفك بنجاح. سيتم مراجعته من قبل المطور قريباً.\n"
                "سوف تتلقى إشعاراً عند الموافقة أو الرفض."
            )
            developer_message_text = (
                f"📥 ملف جديد للتحقق!\n"
                f"المستخدم: <a href='tg://user?id={user_id}'>{message.from_user.first_name or 'لا يوجد اسم'}</a> (<code>{user_id}</code>)\n"
                f"اسم الملف: <code>{file_name}</code>\n"
                f"نوع الملف: <code>{file_extension}</code>\n"
                f"يوزر البوت الذي تم رفعه: @{message.from_user.username or 'غير متوفر'}"
                f"{bot_id_text}{token_warning_text}"
            )
            markup = types.InlineKeyboardMarkup()
            callback_key = f"{user_id}_{file_name}"
            markup.add(
                CButton("✅ موافقة", callback_data=f"approve_{callback_key}", style=STYLE_SUCCESS),
                CButton("❌ رفض", callback_data=f"reject_{callback_key}", style=STYLE_DANGER)
            )
            with open(local_file_path, 'rb') as doc_file:
                bot.send_document(OWNER_ID, doc_file, caption=developer_message_text, parse_mode='HTML', reply_markup=markup)
        else:
            bot.reply_to(
                message,
                "✅ تم استلام ملفك بنجاح، مفيش موافقة يدوية مطلوبة دلوقتي.\n"
                "جارٍ تجهيز وتشغيل بوتك تلقائيًا... ⏳"
            )
            if user_id != OWNER_ID:
                try:
                    info_text = (
                        f"📥 ملف جديد اترفع وبيشتغل تلقائيًا (من غير موافقة يدوية)\n"
                        f"المستخدم: <a href='tg://user?id={user_id}'>{message.from_user.first_name or 'لا يوجد اسم'}</a> (<code>{user_id}</code>)\n"
                        f"اسم الملف: <code>{file_name}</code> ({file_extension})"
                        f"{bot_id_text}{token_warning_text}"
                    )
                    bot.send_message(OWNER_ID, info_text, parse_mode='HTML')
                except Exception:
                    pass
            threading.Thread(
                target=process_approved_file,
                args=(user_id, file_name, file_extension, bot_id_from_token, message.chat.id)
            ).start()

    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء تنزيل الملف أو معالجته: {e}")
        logger.error(f"General error processing uploaded file for user {user_id}: {e}", exc_info=True)

def _receive_bot_token_and_run(message, file_path, user_id, file_name, user_folder):
    token = message.text.strip() if message.text else ""
    if not re.match(r'^\d{6,12}:[a-zA-Z0-9_-]{30,50}$', token):
        msg = bot.reply_to(message, "❌ التوكن ده مش شكله صحيح. ابعت توكن صالح من @BotFather:")
        bot.register_next_step_handler(msg, lambda m: _receive_bot_token_and_run(m, file_path, user_id, file_name, user_folder))
        return
    set_bot_env_var(user_id, file_name, 'BOT_TOKEN', token)
    bot.reply_to(message, f"✅ تم حفظ التوكن، جارٍ تشغيل بوتك '{file_name}'...")
    threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, user_id)).start()

# =========================================================
# ✅ المعالجة المشتركة بعد قبول ملف (تلقائيًا أو بموافقة يدوية)
# =========================================================
def _register_and_run_py(user_id, file_name, file_path, notify_chat_id):
    """يتأكد لو الملف محتاج BOT_TOKEN من متغيرات البيئة، ولو مش محتاج يشغّله على طول."""
    user_folder = get_user_folder(user_id)
    needs_token = False
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_check:
            code_check = f_check.read()
        if re.search(r'os\.(environ\.get|getenv)\(\s*[\'"]BOT_TOKEN[\'"]', code_check) and 'BOT_TOKEN' not in get_bot_env_vars(user_id, file_name):
            needs_token = True
    except Exception as e:
        logger.warning(f"Failed BOT_TOKEN pre-check for {file_name}: {e}")

    if needs_token:
        msg = bot.send_message(
            notify_chat_id,
            f"🔑 بوتك <code>{file_name}</code> بيحتاج توكن (BOT_TOKEN) عشان يشتغل.\n"
            "ابعت توكن البوت دلوقتي (من @BotFather):",
            parse_mode='HTML'
        )
        bot.register_next_step_handler(
            msg,
            lambda m, fp=file_path, uid=user_id, fn=file_name, uf=user_folder: _receive_bot_token_and_run(m, fp, uid, fn, uf)
        )
    else:
        
        def _prepare_then_run():
            found, success, details = create_venv_and_install(os.path.dirname(file_path), os.path.basename(file_path), notify_chat_id)
            if not success:
                bot.send_message(notify_chat_id, f"❌ فشل تجهيز مكتبات البوت: <code>{html.escape(str(details)[:1200])}</code>", parse_mode='HTML')
                return
            if found:
                bot.send_message(notify_chat_id, "✅ تم تثبيت المكتبات بنجاح، جارٍ تشغيل البوت...", parse_mode='HTML')
            run_script(file_path, user_id, user_folder, file_name, notify_chat_id)
        threading.Thread(target=_prepare_then_run, daemon=True).start()


def _finalize_zip_entry(user_id, extract_dir, safe_base, entry_relpath, bot_token_id, notify_chat_id):
    """بعد ما اتحدد ملف نقطة التشغيل (تلقائي أو باختيار المستخدم): يسجله كملف معتمد،
    يثبت requirements.txt لو موجود، وبعدين يشغّله."""
    entry_name = f"{safe_base}/{entry_relpath}".replace(os.sep, '/')
    user_folder = get_user_folder(user_id)
    script_path = os.path.join(user_folder, entry_name)

    user_files.setdefault(user_id, []).append((entry_name, '.py', 'approved', bot_token_id))
    update_user_file_db(user_id, entry_name, '.py', 'approved', bot_token_id)

    found, success, _log_tail = create_venv_and_install(extract_dir, entry_relpath, notify_chat_id)
    if found:
        if success:
            bot.send_message(notify_chat_id, "📦 تم تثبيت المكتبات من requirements.txt بنجاح.", parse_mode='HTML')
        else:
            bot.send_message(
                notify_chat_id,
                "⚠️ حصلت مشكلة في تثبيت بعض المكتبات من requirements.txt، هحاول أصلحها تلقائيًا لو البوت كراش بسببها.",
                parse_mode='HTML'
            )

    bot.send_message(
        notify_chat_id,
        f"✅ تم فك الضغط وتحديد نقطة التشغيل: <code>{entry_relpath}</code>\nجارٍ تشغيل البوت الآن...",
        parse_mode='HTML'
    )
    _register_and_run_py(user_id, entry_name, script_path, notify_chat_id)


def process_approved_file(user_id, file_name, file_extension, bot_token_id, notify_chat_id):
    """المسار المشترك بعد قبول ملف، سواء تلقائي أو بموافقة يدوية من المطور:
    - .py: يتأكد من التوكن (لو محتاج) ويشغّله.
    - .zip: يفك الضغط في مجلد مخصص، يكتشف نقطة التشغيل تلقائيًا (main.py/bot.py/app.py..)،
      يثبت requirements.txt لو موجود، ثم يشغّل. لو فيه أكتر من ملف .py محتمل، بيسأل المستخدم يختار."""
    user_folder = get_user_folder(user_id)
    file_path = os.path.join(user_folder, file_name)

    if file_extension == '.py':
        user_files[user_id] = [
            (f_name, f_type, 'approved', bot_token_id) if f_name == file_name else (f_name, f_type, st, bid)
            for f_name, f_type, st, bid in user_files.get(user_id, [])
        ]
        update_user_file_db(user_id, file_name, file_extension, 'approved', bot_token_id)
        _register_and_run_py(user_id, file_name, file_path, notify_chat_id)
        return

    # --- .zip: فك الضغط في مجلد مخصص باسم مشتق من اسم الملف ---
    safe_base = re.sub(r'[^A-Za-z0-9_\-]+', '_', os.path.splitext(file_name)[0])[:40] or 'bot'
    extract_dir = os.path.join(user_folder, safe_base)
    # عند رفع نسخة ZIP جديدة بنفس الاسم، احذف سجلات نقطة التشغيل القديمة
    # المرتبطة بنفس مجلد المشروع حتى لا تظهر بوتات مكررة داخل «بوتاتي».
    old_project_entries = [
        f[0] for f in user_files.get(user_id, [])
        if f[0] == file_name or f[0].startswith(safe_base + '/')
    ]
    for old_entry in old_project_entries:
        remove_user_file_db(user_id, old_entry)
    user_files[user_id] = [
        f for f in user_files.get(user_id, [])
        if f[0] not in old_project_entries
    ]
    try:
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)  # تحديث لمشروع ZIP سابق بنفس الاسم
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            infos=zip_ref.infolist(); max_files=int(SETTINGS.get('max_zip_files',1000)); max_bytes=int(SETTINGS.get('max_zip_uncompressed_mb',100))*1024*1024
            if len(infos)>max_files: raise ValueError(f'عدد الملفات داخل ZIP أكبر من الحد ({max_files}).')
            total=0
            for info in infos:
                member=info.filename
                if os.path.isabs(member) or '..' in member.replace('\\','/').split('/'): raise ValueError(f"مسار غير آمن داخل الملف المضغوط: {member}")
                total+=max(0,info.file_size)
                if total>max_bytes: raise ValueError(f"الحجم بعد فك الضغط يتجاوز الحد ({max_bytes//(1024*1024)} MB).")
            zip_ref.extractall(extract_dir)
        if os.path.exists(file_path):
            os.remove(file_path)
    except zipfile.BadZipFile:
        bot.send_message(notify_chat_id, "❌ فشل فك ضغط ملف ZIP الخاص بك. يبدو أنه تالف.", parse_mode='HTML')
        remove_user_file_db(user_id, file_name)
        user_files[user_id] = [f for f in user_files.get(user_id, []) if f[0] != file_name]
        return
    except ValueError as ve:
        bot.send_message(notify_chat_id, f"❌ فشل فك الضغط: {ve}", parse_mode='HTML')
        remove_user_file_db(user_id, file_name)
        user_files[user_id] = [f for f in user_files.get(user_id, []) if f[0] != file_name]
        return
    except Exception as e:
        bot.send_message(notify_chat_id, f"❌ حدث خطأ أثناء فك ضغط ملف ZIP الخاص بك: {e}", parse_mode='HTML')
        return

    entry_relpath, all_py_files = find_zip_entry_point(extract_dir)

    # امسح سجل ملف الـ ZIP القديم قبل ما نسجل نقطة التشغيل الجديدة بدل منه
    remove_user_file_db(user_id, file_name)
    user_files[user_id] = [f for f in user_files.get(user_id, []) if f[0] != file_name]

    if not all_py_files:
        bot.send_message(notify_chat_id, "❌ الملف المضغوط ده مفيهوش أي ملف بايثون (.py). راجع المحتوى وارفعه تاني.", parse_mode='HTML')
        shutil.rmtree(extract_dir, ignore_errors=True)
        return

    if entry_relpath is None:
        # أكتر من ملف .py محتمل ومفيش اسم واضح زي main.py/bot.py — نسأل المستخدم يختار
        pending_entry_choice[user_id] = {
            'extract_dir': extract_dir, 'safe_base': safe_base,
            'candidates': all_py_files, 'bot_token_id': bot_token_id,
            'notify_chat_id': notify_chat_id,
        }
        markup = types.InlineKeyboardMarkup()
        for idx, rel in enumerate(all_py_files[:15]):
            markup.add(CButton(f"📄 {rel}", callback_data=f"pickentry_{user_id}_{idx}", style=STYLE_PRIMARY))
        bot.send_message(
            notify_chat_id,
            "📦 تم فك ضغط ملفك، لكن فيه أكتر من ملف بايثون ومقدرتش أحدد الملف الرئيسي تلقائيًا.\n"
            "اختار الملف اللي المفروض يبدأ بيه البوت (نقطة التشغيل):",
            reply_markup=markup
        )
        return

    _finalize_zip_entry(user_id, extract_dir, safe_base, entry_relpath, bot_token_id, notify_chat_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('pickentry_'))
def handle_pick_entry(call):
    try:
        _, user_id_str, idx_str = call.data.split('_', 2)
        target_user_id = int(user_id_str)
        idx = int(idx_str)
    except Exception:
        bot.answer_callback_query(call.id, "خطأ في البيانات.")
        return
    if call.from_user.id != target_user_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    state = pending_entry_choice.get(target_user_id)
    if not state or idx >= len(state['candidates']):
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية هذا الاختيار، جرّب ترفع الملف تاني.")
        return
    entry_relpath = state['candidates'][idx]
    bot.answer_callback_query(call.id, "✅ تم الاختيار، جارٍ التشغيل...")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    del pending_entry_choice[target_user_id]
    _finalize_zip_entry(
        target_user_id, state['extract_dir'], state['safe_base'],
        entry_relpath, state['bot_token_id'], state['notify_chat_id']
    )

# --- Callback Handlers for Approval/Rejection ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_approval_callbacks(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك بهذه العملية.")
        return

    action, callback_key = call.data.split('_', 1)

    user_id_str, file_name = callback_key.split('_', 1)
    target_user_id = int(user_id_str)

    file_data_entry = None
    if target_user_id in user_files:
        for i, (f_name, f_type, f_status, bot_id) in enumerate(user_files[target_user_id]):
            if f_name == file_name:
                file_data_entry = {'user_id': target_user_id, 'file_name': f_name, 'file_type': f_type, 'status': f_status, 'bot_token_id': bot_id}
                break

    if not file_data_entry or file_data_entry['status'] != 'pending':
        bot.answer_callback_query(call.id, "لم يتم العثور على هذا الملف المعلق أو تمت معالجته بالفعل.")
        original_caption = call.message.caption or ""
        if "📥 ملف جديد للتحقق!" in original_caption:
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"تمت معالجة الطلب لـ <code>{file_name}</code> (للمستخدم <code>{target_user_id}</code>) بالفعل أو لم يعد متاحاً.",
                parse_mode='HTML',
                reply_markup=None
            )
        return

    user_id = file_data_entry['user_id']
    file_name = file_data_entry['file_name']
    file_path = os.path.join(get_user_folder(user_id), file_name)
    file_extension = file_data_entry['file_type']
    bot_token_id = file_data_entry['bot_token_id']

    if action == 'approve':
        status = 'approved'
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=f"✅ تم الموافقة على ملف <code>{file_name}</code> للمستخدم <a href='tg://user?id={user_id}'>{user_id}</a>.",
            parse_mode='HTML',
            reply_markup=None
        )
        try:
            bot.send_message(user_id, f"✅ تهانينا! تمت الموافقة على ملفك <code>{file_name}</code>. جارٍ تشغيله/فك ضغطه...", parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send approval notification to user {user_id}: {e}")
            bot.send_message(OWNER_ID, f"⚠️ فشل إرسال إشعار الموافقة للمستخدم {user_id} لـ {file_name}: {e}", parse_mode='HTML')

        threading.Thread(target=process_approved_file, args=(user_id, file_name, file_extension, bot_token_id, user_id)).start()

    elif action == 'reject':
        status = 'rejected'
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=f"❌ تم رفض ملف <code>{file_name}</code> للمستخدم <a href='tg://user?id={user_id}'>{user_id}</a>.",
            parse_mode='HTML',
            reply_markup=None
        )
        try:
            bot.send_message(user_id, f"❌ نعتذر، تم رفض ملفك <code>{file_name}</code>.", parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send rejection notification to user {user_id}: {e}")
            bot.send_message(OWNER_ID, f"⚠️ فشل إرسال إشعار الرفض للمستخدم {user_id} لـ {file_name}: {e}", parse_mode='HTML')

        if user_id in user_files:
            user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
        remove_user_file_db(user_id, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)

    bot.answer_callback_query(call.id, f"تم معالجة الطلب: {status}.")


# =========================================================
# 📋 صفحة تفاصيل البوت (لوحة تحكم متقدمة لكل بوت على حدة)
# =========================================================
def show_bot_detail(chat_id, owner_id, file_name, message_id=None):
    is_running = is_bot_running(owner_id, file_name)
    user_folder = get_user_folder(owner_id)
    script_path = os.path.join(user_folder, file_name)
    script_key = f"{owner_id}_{file_name}"

    ram_txt = "0.0 MB"
    uptime_txt = "غير شغال"
    if is_running and script_key in bot_scripts:
        info = bot_scripts[script_key]
        try:
            proc = psutil.Process(info['process'].pid)
            ram_txt = f"{proc.memory_info().rss / (1024*1024):.1f} MB"
        except Exception:
            pass
        uptime = datetime.now() - info['start_time']
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        uptime_txt = f"{h}س {m}د {s}ث"

    code_size_kb = f"{(os.path.getsize(script_path) / 1024):.1f}" if os.path.exists(script_path) else "0"
    restart_count, crash_count = get_file_counters(owner_id, file_name)
    env_vars = get_bot_env_vars(owner_id, file_name)

    text = (
        f"📋 <b>تفاصيل البوت: {file_name}</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"الحالة: {'🟢 يعمل' if is_running else '🔴 متوقف'}\n"
        f"⏱️ وقت التشغيل: {uptime_txt}\n"
        f"🧠 الرام: {ram_txt}\n"
        f"🔁 إعادات: {restart_count or 0} | 💥 كراشات: {crash_count or 0}\n"
        f"📦 حجم الكود: {code_size_kb} KB\n"
        f"🔑 متغيرات بيئة محفوظة: {len(env_vars)}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        CButton("■ إيقاف" if is_running else "▶ تشغيل", callback_data=f"toggle_{script_key}", style=STYLE_DANGER if is_running else STYLE_SUCCESS),
        CButton("🔄 إعادة تشغيل", callback_data=f"restartbot_{script_key}", style=STYLE_PRIMARY)
    )
    markup.add(
        CButton("📄 السجل", callback_data=f"log_{script_key}", style=STYLE_PRIMARY),
        CButton("⚙️ الإعدادات", callback_data=f"envmenu_{script_key}", style=STYLE_PRIMARY)
    )
    markup.add(
        CButton("📤 تحديث الكود", callback_data=f"updatecode_{script_key}", style=STYLE_DANGER),
        CButton("🗑️ حذف البوت", callback_data=f"delete_{script_key}", style=STYLE_DANGER)
    )
    markup.add(CButton("🔙 رجوع", callback_data="back_to_files_list", style=STYLE_PRIMARY))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=markup)
        except telebot.apihelper.ApiException:
            bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('detail_'))
def handle_bot_detail(call):
    script_key_full = call.data[len('detail_'):]
    owner_id_str, file_name = script_key_full.split('_', 1)
    owner_id = int(owner_id_str)
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    bot.answer_callback_query(call.id)
    show_bot_detail(call.message.chat.id, owner_id, file_name, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_files_list')
def handle_back_to_files_list(call):
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    list_user_files(_as_user(call.message, call.from_user))

@bot.callback_query_handler(func=lambda call: call.data.startswith('restartbot_'))
def handle_restart_bot(call):
    script_key_full = call.data[len('restartbot_'):]
    owner_id_str, file_name = script_key_full.split('_', 1)
    owner_id = int(owner_id_str)
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    script_key = f"{owner_id}_{file_name}"
    bot.answer_callback_query(call.id, "🔄 جارٍ إعادة التشغيل...")
    if script_key in bot_scripts:
        kill_process_tree(bot_scripts[script_key])
        del bot_scripts[script_key]
    user_folder = get_user_folder(owner_id)
    script_path = os.path.join(user_folder, file_name)
    threading.Thread(target=run_script, args=(script_path, owner_id, user_folder, file_name, call.message.chat.id)).start()
    time.sleep(1)
    show_bot_detail(call.message.chat.id, owner_id, file_name, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('envmenu_'))
def handle_env_menu(call):
    script_key_full = call.data[len('envmenu_'):]
    owner_id_str, file_name = script_key_full.split('_', 1)
    owner_id = int(owner_id_str)
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    bot.answer_callback_query(call.id)
    env_vars = get_bot_env_vars(owner_id, file_name)
    lines = [f"⚙️ <b>متغيرات البيئة لـ {file_name}</b>", "━━━━━━━━━━━━━━━"]
    markup = types.InlineKeyboardMarkup()
    if not env_vars:
        lines.append("لا توجد متغيرات محفوظة حاليًا.")
    for k, v in env_vars.items():
        masked = (v[:3] + "***" + v[-2:]) if len(v) > 6 else "***"
        lines.append(f"🔑 <code>{k}</code> = <code>{masked}</code>")
        markup.add(CButton(f"🗑️ حذف {k}", callback_data=f"envdel_{owner_id}::{file_name}::{k}", style=STYLE_DANGER))
    markup.add(CButton("➕ إضافة / تعديل متغير", callback_data=f"envadd_{owner_id}_{file_name}", style=STYLE_SUCCESS))
    markup.add(CButton("🔙 رجوع لتفاصيل البوت", callback_data=f"detail_{owner_id}_{file_name}", style=STYLE_PRIMARY))
    text = "\n".join(lines)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
    except telebot.apihelper.ApiException:
        bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('envadd_'))
def handle_env_add(call):
    parts = call.data[len('envadd_'):].split('_', 1)
    owner_id = int(parts[0]); file_name = parts[1]
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "✍️ ابعت المتغير بالصيغة: <code>KEY=VALUE</code>\nمثال: <code>BOT_TOKEN=123456:abcDEF</code>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: _save_env_var(m, owner_id, file_name))

def _save_env_var(message, owner_id, file_name):
    text = message.text.strip() if message.text else ""
    if '=' not in text:
        bot.reply_to(message, "❌ الصيغة غلط. استخدم: KEY=VALUE")
        return
    key, value = text.split('=', 1)
    key = key.strip(); value = value.strip()
    if not key:
        bot.reply_to(message, "❌ اسم المتغير مينفعش يبقى فاضي.")
        return
    set_bot_env_var(owner_id, file_name, key, value)
    bot.reply_to(message, f"✅ تم حفظ <code>{key}</code>. أعد تشغيل البوت من صفحة التفاصيل عشان يتفعّل.", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('envdel_'))
def handle_env_del(call):
    parts = call.data[len('envdel_'):].split('::')
    owner_id = int(parts[0]); file_name = parts[1]; key = parts[2]
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    delete_bot_env_var(owner_id, file_name, key)
    bot.answer_callback_query(call.id, f"🗑️ تم حذف {key}.")
    handle_env_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('updatecode_'))
def handle_update_code(call):
    script_key_full = call.data[len('updatecode_'):]
    owner_id_str, file_name = script_key_full.split('_', 1)
    owner_id = int(owner_id_str)
    if call.from_user.id != owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن.")
        return
    bot.answer_callback_query(call.id)
    approval_note = "وهيحتاج موافقة المطور تاني قبل ما يشتغل." if SETTINGS.get('require_approval') == '1' else "وهيشتغل تلقائيًا على طول من غير ما يحتاج موافقة."
    if '/' in file_name:
        text = (
            "📤 بوتك ده جزء من مشروع ZIP متعدد الملفات.\n"
            "عشان تحدّثه، ارفع ملف الـ ZIP الجديد (بنفس اسم الملف الأصلي أو أي اسم) من «📦 رفع ZIP»، "
            f"وهيستبدل النسخة القديمة تلقائيًا {approval_note}"
        )
    else:
        text = (
            f"📤 ابعت نسخة .py الجديدة بنفس اسم الملف <code>{file_name}</code> عن طريق «➕ رفع بوت»، "
            f"{approval_note}"
        )
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')

# --- Callback Handlers for User File Management (Toggle/Delete/Log) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('toggle_', 'delete_', 'log_')))
def handle_file_action_callbacks(call):
    action_type, script_key_full = call.data.split('_', 1)

    try:
        script_owner_id_str, file_name = script_key_full.split('_', 1)
        script_owner_id = int(script_owner_id_str)
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "خطأ في مفتاح السكربت (تنسيق غير صالح).")
        return

    if call.from_user.id != script_owner_id and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "لا تملك الإذن للتحكم في هذا السكربت.")
        return

    if call.from_user.id != OWNER_ID and not is_subscribed(call.from_user.id):
        send_force_subscribe_message(call.message.chat.id)
        bot.answer_callback_query(call.id, "عليك الاشتراك في القناة أولاً.")
        return

    file_status = 'unknown'
    if script_owner_id in user_files:
        for f_name, _, status, _ in user_files[script_owner_id]:
            if f_name == file_name:
                file_status = status
                break

    if action_type == 'toggle':
        if file_status != 'approved':
            bot.answer_callback_query(call.id, f"لا يمكن تشغيل/إيقاف هذا الملف. حالته هي: {file_status}")
            return

        script_key = f"{script_owner_id}_{file_name}"
        if is_bot_running(script_owner_id, file_name):
            if script_key in bot_scripts:
                bot.answer_callback_query(call.id, f"جارٍ إيقاف '{file_name}'...")
                kill_process_tree(bot_scripts[script_key])
                del bot_scripts[script_key]
                bot.send_message(call.message.chat.id, f"■ تم إيقاف سكربت '{file_name}'.")
            else:
                bot.answer_callback_query(call.id, "السكربت ليس قيد التشغيل أو تمت إزالة بالفعل.")
        else:
            if script_owner_id != OWNER_ID and not has_active_hosting(script_owner_id):
                bot.answer_callback_query(call.id, "⛔ رصيد التشغيل خلص. اشحن أيام جديدة الأول.")
                return
            user_folder = get_user_folder(script_owner_id)
            script_path = os.path.join(user_folder, file_name)
            if os.path.exists(script_path):
                bot.answer_callback_query(call.id, f"جارٍ تشغيل '{file_name}'...")
                threading.Thread(
                    target=run_script,
                    args=(script_path, script_owner_id, user_folder, file_name, call.message.chat.id)
                ).start()
            else:
                bot.answer_callback_query(call.id, f"❌ لم يتم العثور على الملف '{file_name}'. ربما تم حذفه.")
                _remove_file_from_cache_and_db(script_owner_id, file_name)

    elif action_type == 'delete':
        if is_bot_running(script_owner_id, file_name):
            bot.answer_callback_query(call.id, f"يرجى إيقاف '{file_name}' أولاً قبل الحذف.")
            return

        user_folder = get_user_folder(script_owner_id)
        script_path = os.path.join(user_folder, file_name)

        try:
            if '/' in file_name:
                # بوت مستخرج من ZIP — نحذف مجلد المشروع كامل مش بس ملف نقطة التشغيل
                project_dir = os.path.join(user_folder, file_name.split('/', 1)[0])
                if os.path.isdir(project_dir):
                    shutil.rmtree(project_dir, ignore_errors=True)
                _remove_file_from_cache_and_db(script_owner_id, file_name)
                bot.answer_callback_query(call.id, f"✅ تم حذف '{file_name}' بنجاح.")
                bot.send_message(call.message.chat.id, f"🗑️ تم حذف مشروع البوت '{file_name}' بالكامل.")
            elif os.path.exists(script_path):
                os.remove(script_path)
                log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
                if os.path.exists(log_file_path):
                    os.remove(log_file_path)

                _remove_file_from_cache_and_db(script_owner_id, file_name)

                bot.answer_callback_query(call.id, f"✅ تم حذف '{file_name}' بنجاح.")
                bot.send_message(call.message.chat.id, f"🗑️ تم حذف سكربت '{file_name}'.")
            else:
                bot.answer_callback_query(call.id, f"❌ لم يتم العثور على الملف '{file_name}'. ربما تم حذفه بالفعل.")
                _remove_file_from_cache_and_db(script_owner_id, file_name)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ خطأ في حذف الملف: {e}")
            logger.error(f"Error deleting file {script_path} for user {script_owner_id}: {e}", exc_info=True)

    elif action_type == 'log':
        user_folder = get_user_folder(script_owner_id)
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")

        if not os.path.exists(log_file_path):
            bot.answer_callback_query(call.id, "❌ لا يوجد ملف سجل لهذا السكربت بعد.")
            bot.send_message(call.message.chat.id, f"لا يوجد ملف سجل للسكربت `{file_name}`. قد لا يكون قد تم تشغيله بعد أو لم يكتب أي شيء في السجل.", parse_mode='Markdown')
            return

        bot.answer_callback_query(call.id, f"جارٍ جلب سجل '{file_name}'...")
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            if not log_content.strip():
                bot.send_message(call.message.chat.id, f"ملف سجل `{file_name}` فارغ. لم يكتب السكربت أي شيء في السجل بعد.", parse_mode='Markdown')
                return

            max_length_per_message = 4000
            if len(log_content) > max_length_per_message:
                parts = [log_content[i:i+max_length_per_message] for i in range(0, len(log_content), max_length_per_message)]
                for i, chunk in enumerate(parts):
                    bot.send_message(call.message.chat.id, f"📜 سجل '{file_name}' (جزء {i+1} من {len(parts)}):\n\n{chunk}")
                    time.sleep(0.5)
            else:
                bot.send_message(call.message.chat.id, f"📜 سجل '{file_name}':\n\n{log_content}")

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ حدث خطأ أثناء قراءة ملف السجل: {e}")
            logger.error(f"Error reading log file {log_file_path} for user {script_owner_id}: {e}", exc_info=True)

    if call.from_user.id == OWNER_ID:
        admin_state = admin_pagination_state.get(OWNER_ID, {})
        if admin_state.get('page_type') == 'user_specific' and admin_state.get('target_user_id') == script_owner_id:
            display_user_files_for_admin(OWNER_ID, script_owner_id, admin_state['current_page'], call.message.message_id)
        else:
            display_all_user_files(OWNER_ID, admin_state.get('current_page', 1), call.message.message_id)
    else:
        list_user_files(_as_user(call.message, call.from_user))

def _remove_file_from_cache_and_db(user_id, file_name):
    if user_id in user_files:
        user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
    remove_user_file_db(user_id, file_name)

# --- Admin Pagination and Navigation ---
def display_all_user_files(chat_id, page_number, message_id=None):
    files_per_page = 5
    all_files_data = get_all_user_files_from_db()

    user_file_groups = {}
    for file_info in all_files_data:
        user_id = file_info['user_id']
        if user_id not in user_file_groups:
            user_file_groups[user_id] = []
        user_file_groups[user_id].append(file_info)

    users_with_files = list(user_file_groups.items())

    total_users_with_files = len(users_with_files)
    total_pages = (total_users_with_files + files_per_page - 1) // files_per_page if total_users_with_files > 0 else 0

    current_page = page_number
    if total_users_with_files == 0: current_page = 0
    elif current_page > total_pages: current_page = total_pages
    elif current_page < 1: current_page = 1

    start_idx = (current_page - 1) * files_per_page
    end_idx = start_idx + files_per_page
    paginated_users_with_files = users_with_files[start_idx:end_idx]

    admin_pagination_state[OWNER_ID] = {
        'current_page': current_page,
        'total_pages': total_pages,
        'page_type': 'all_users_overview'
    }

    response = f"👑 لوحة تحكم المطور - جميع المستخدمين (الصفحة {current_page}/{total_pages}):\n\n"
    if not paginated_users_with_files:
        response += "لا توجد ملفات مرفوعة من المستخدمين حتى الآن."
    else:
        for user_id, files_list in paginated_users_with_files:
            expiry = get_hosting_expiry(user_id)
            expiry_emoji = "🟢" if (expiry and expiry > datetime.now()) else "🔴"
            response += f"👤 المستخدم: <a href='tg://user?id={user_id}'>{user_id}</a> {expiry_emoji} - عدد الملفات: {len(files_list)}\n"
            for file_info in files_list[:2]:
                status_emoji = "⏳" if file_info['status'] == 'pending' else \
                               "✅" if file_info['status'] == 'approved' else "❌"
                bot_id_display = f" (<code>{file_info['bot_token_id']}</code>)" if file_info['bot_token_id'] else ""
                response += f"  - `{file_info['file_name']}` {status_emoji}{bot_id_display}\n"
            if len(files_list) > 2:
                response += f"  ...و {len(files_list) - 2} ملفات أخرى.\n"
            response += "\n"

    markup = types.InlineKeyboardMarkup()
    for user_id, _ in paginated_users_with_files:
        markup.add(CButton(f"عرض ملفات المستخدم {user_id}", callback_data=f"admin_view_user_files_{user_id}_page_1", style=STYLE_PRIMARY))

    pagination_buttons = []
    if current_page > 1:
        pagination_buttons.append(CButton("⬅️ السابق", callback_data="admin_prev_page_all_users", style=STYLE_PRIMARY))
    if current_page < total_pages:
        pagination_buttons.append(CButton("التالي ➡️", callback_data="admin_next_page_all_users", style=STYLE_PRIMARY))
    if pagination_buttons:
        markup.add(*pagination_buttons)

    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=response,
                parse_mode='HTML',
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except telebot.apihelper.ApiException as e:
            if "message is not modified" not in str(e):
                bot.send_message(chat_id, response, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)
    else:
        bot.send_message(chat_id, response, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

def display_user_files_for_admin(admin_chat_id, target_user_id, page_number, message_id=None):
    files_per_page = 5
    files = user_files.get(target_user_id, [])

    total_files = len(files)
    total_pages = (total_files + files_per_page - 1) // files_per_page if total_files > 0 else 0
    current_page = page_number

    if total_files == 0: current_page = 0
    elif current_page > total_pages: current_page = total_pages
    elif current_page < 1: current_page = 1

    start_idx = (current_page - 1) * files_per_page
    end_idx = start_idx + files_per_page
    paginated_files = files[start_idx:end_idx]

    admin_pagination_state[OWNER_ID] = {
        'current_page': current_page,
        'total_pages': total_pages,
        'target_user_id': target_user_id,
        'page_type': 'user_specific'
    }

    expiry = get_hosting_expiry(target_user_id)
    expiry_line = f"⏳ رصيد التشغيل شغّال لحد: {expiry.strftime('%Y-%m-%d %H:%M')}\n" if (expiry and expiry > datetime.now()) else "⛔ معندوش رصيد تشغيل شغّال.\n"

    response = f"👑 ملفات المستخدم <a href='tg://user?id={target_user_id}'>{target_user_id}</a> (الصفحة {current_page}/{total_pages}):\n{expiry_line}\n"
    if not paginated_files:
        response += "لا توجد ملفات لهذا المستخدم في هذه الصفحة."

    markup = types.InlineKeyboardMarkup()
    for idx, (file_name, file_type, status, bot_token_id) in enumerate(paginated_files):
        script_key = f"{target_user_id}_{file_name}"
        is_running = is_bot_running(target_user_id, file_name) and status == 'approved'

        status_emoji = "⏳ معلق" if status == 'pending' else \
                       "✅ موافق عليه" if status == 'approved' else \
                       "❌ مرفوض" if status == 'rejected' else "❓ غير معروف"

        running_status_emoji = "🟢 يعمل" if is_running else "🔴 متوقف"

        bot_id_display = f" (معرف البوت: <code>{bot_token_id}</code>)" if bot_token_id else ""
        response += f"{start_idx + idx + 1}. `{file_name}` ({file_type}) - {status_emoji} - {running_status_emoji}{bot_id_display}\n"

        if status == 'approved':
            start_stop_text = "■ إيقاف" if is_running else "▶ تشغيل"
            start_stop_style = STYLE_DANGER if is_running else STYLE_SUCCESS
            markup.add(
                CButton(f"{start_stop_text} {file_name}", callback_data=f"toggle_{script_key}", style=start_stop_style),
                CButton(f"🗑️ حذف {file_name}", callback_data=f"delete_{script_key}", style=STYLE_DANGER),
                CButton(f"📄 سجل {file_name}", callback_data=f"log_{script_key}", style=STYLE_PRIMARY)
            )
        else:
            markup.add(CButton(f"🗑️ حذف {file_name}", callback_data=f"delete_{script_key}", style=STYLE_DANGER))

    pagination_buttons = []
    if current_page > 1:
        pagination_buttons.append(CButton("⬅️ السابق", callback_data=f"admin_view_user_files_{target_user_id}_page_{current_page - 1}", style=STYLE_PRIMARY))
    if current_page < total_pages:
        pagination_buttons.append(CButton("التالي ➡️", callback_data=f"admin_view_user_files_{target_user_id}_page_{current_page + 1}", style=STYLE_PRIMARY))
    if pagination_buttons:
        markup.add(*pagination_buttons)

    markup.add(CButton("🔙 العودة لجميع المستخدمين", callback_data="admin_back_to_all_users", style=STYLE_DANGER))

    try:
        bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=message_id,
            text=response,
            parse_mode='HTML',
            reply_markup=markup,
            disable_web_page_preview=True
        )
    except telebot.apihelper.ApiException as e:
        if "message is not modified" not in str(e):
            bot.send_message(admin_chat_id, response, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('user_prev_page_', 'user_next_page_')))
def handle_user_pagination(call):
    action_type, user_id_str, _ = call.data.split('_', 2)
    user_id = int(user_id_str)

    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "لا تملك الإذن للتنقل في صفحات مستخدم آخر.")
        return

    if not is_subscribed(user_id):
        send_force_subscribe_message(call.message.chat.id)
        bot.answer_callback_query(call.id, "عليك الاشتراك في القناة أولاً.")
        return

    current_state = user_pagination_state.get(user_id)
    if not current_state:
        bot.answer_callback_query(call.id, "خطأ: لم يتم العثور على حالة التصفح.")
        list_user_files(_as_user(call.message, call.from_user))
        return

    current_page = current_state['current_page']
    total_pages = current_state['total_pages']

    if 'prev' in action_type:
        new_page = max(1, current_page - 1)
    else:
        new_page = min(total_pages, current_page + 1)

    if new_page == current_page:
        bot.answer_callback_query(call.id, "لا توجد صفحات أخرى.")
        return

    user_pagination_state[user_id]['current_page'] = new_page
    bot.answer_callback_query(call.id)
    list_user_files(_as_user(call.message, call.from_user))

@bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_prev_page_', 'admin_next_page_', 'admin_view_user_files_', 'admin_back_to_all_users')))
def handle_admin_pagination(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "غير مصرح لك بهذه العملية.")
        return

    admin_id = OWNER_ID
    current_admin_state = admin_pagination_state.get(admin_id)

    if call.data == 'admin_back_to_all_users':
        bot.answer_callback_query(call.id, "جارٍ العودة لجميع المستخدمين...")
        display_all_user_files(admin_id, 1, call.message.message_id)
        return

    if call.data.startswith('admin_view_user_files_'):
        parts = call.data.split('_')
        target_user_id = int(parts[3])
        page_number = int(parts[5])

        admin_pagination_state[OWNER_ID] = {
            'current_page': page_number,
            'target_user_id': target_user_id,
            'page_type': 'user_specific'
        }

        bot.answer_callback_query(call.id, f"عرض ملفات المستخدم {target_user_id} صفحة {page_number}...")
        display_user_files_for_admin(admin_id, target_user_id, page_number, call.message.message_id)
        return

    if not current_admin_state:
        bot.answer_callback_query(call.id, "خطأ: لم يتم العثور على حالة التصفح للمطور.")
        display_all_user_files(admin_id, 1, call.message.message_id)
        return

    page_type = current_admin_state['page_type']
    current_page = current_admin_state['current_page']

    files_per_page = 5
    total_items = 0
    if page_type == 'all_users_overview':
        all_files_data = get_all_user_files_from_db()
        user_file_groups = {}
        for file_info in all_files_data:
            user_id = file_info['user_id']
            if user_id not in user_file_groups:
                user_file_groups[user_id] = []
            user_file_groups[user_id].append(file_info)
        total_items = len(list(user_file_groups.items()))
    elif page_type == 'user_specific':
        target_user_id = current_admin_state.get('target_user_id')
        if target_user_id:
            files = user_files.get(target_user_id, [])
            total_items = len(files)

    total_pages = (total_items + files_per_page - 1) // files_per_page if total_items > 0 else 0

    action_type = call.data.split('_')[1]

    if 'prev' in action_type:
        new_page = max(1, current_page - 1)
    else:
        new_page = min(total_pages, current_page + 1)

    if new_page == current_page:
        bot.answer_callback_query(call.id, "لا توجد صفحات أخرى.")
        return

    bot.answer_callback_query(call.id)
    if page_type == 'all_users_overview':
        display_all_user_files(admin_id, new_page, call.message.message_id)
    elif page_type == 'user_specific':
        target_user_id = current_admin_state.get('target_user_id')
        if target_user_id:
            display_user_files_for_admin(admin_id, target_user_id, new_page, call.message.message_id)

# =========================================================
# 👑 مركز المطور المتقدم + 🧾 سجل الدفع + 👥 إدارة الحسابات
# =========================================================
def _admin_only(x): return getattr(getattr(x,'from_user',None),'id',None)==OWNER_ID

@bot.callback_query_handler(func=lambda call: call.data=='dev_subscriptions')
def dev_subscriptions(call):
    if not _admin_only(call): bot.answer_callback_query(call.id,'غير مصرح لك.'); return
    total,active,frozen,payments,stars=get_subscription_summary(); text=f'💎 <b>مركز الاشتراكات والمدفوعات</b>\n━━━━━━━━━━━━━━━\n👥 المستخدمون: <b>{total}</b>\n🟢 فعالة: <b>{active}</b>\n❄️ مجمدة: <b>{frozen}</b>\n💳 عمليات ناجحة: <b>{payments}</b>\n⭐ النجوم المسجلة: <b>{stars}</b>'
    m=types.InlineKeyboardMarkup(); m.add(CButton('🎁 منح/تمديد',callback_data='dev_hub_grant',style=STYLE_SUCCESS)); m.add(CButton('👤 إدارة مستخدم',callback_data='dev_user_manage',style=STYLE_PRIMARY)); m.add(CButton('🧾 آخر المدفوعات',callback_data='dev_payments',style=STYLE_PRIMARY)); m.add(CButton('🔙 لوحة المطور',callback_data='dev_hub_back',style=STYLE_DANGER)); bot.edit_message_text(text,call.message.chat.id,call.message.message_id,parse_mode='HTML',reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data=='my_payment_history')
def my_payment_history(call):
    if is_banned(call.from_user.id): bot.answer_callback_query(call.id,'الحساب موقوف.'); return
    rows=get_payment_history(call.from_user.id); lines=['🧾 <b>آخر عمليات الدفع</b>','━━━━━━━━━━━━━━━']
    if not rows: lines.append('لا توجد عمليات دفع مسجلة حتى الآن.')
    for method,pkg,days,amount,currency,status,created in rows: lines.append(f'• {pkg or "اشتراك"} — {amount} {currency} — {method} — {created[:16].replace("T"," ")}')
    m=types.InlineKeyboardMarkup(); m.add(CButton('🔙 الاشتراكات',callback_data='my_subscription_back',style=STYLE_PRIMARY)); bot.edit_message_text('\n'.join(lines),call.message.chat.id,call.message.message_id,parse_mode='HTML',reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data=='my_subscription_back')
def my_subscription_back(call):
    if is_banned(call.from_user.id): return
    expiry=get_hosting_expiry(call.from_user.id); status=f'⏳ فعال حتى <b>{expiry.strftime("%Y-%m-%d %H:%M")}</b>' if expiry and expiry>datetime.now() else '⛔ لا يوجد رصيد تشغيل فعال'
    m=types.InlineKeyboardMarkup(); m.add(CButton('📅 يوم',callback_data='buy_day',style=STYLE_PRIMARY)); m.add(CButton('🗓️ أسبوع',callback_data='buy_week',style=STYLE_SUCCESS)); m.add(CButton('🗓️ شهر',callback_data='buy_month',style=STYLE_SUCCESS)); m.add(CButton('🧾 سجل عمليات الدفع',callback_data='my_payment_history',style=STYLE_PRIMARY)); bot.edit_message_text(f'💎 <b>اشتراكات الاستضافة</b>\n\n{status}\n\nاختار الباقة:',call.message.chat.id,call.message.message_id,parse_mode='HTML',reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data=='dev_user_manage')
def dev_user_manage(call):
    if not _admin_only(call): bot.answer_callback_query(call.id,'غير مصرح لك.'); return
    msg=bot.send_message(OWNER_ID,'👤 ابعت USER_ID لإدارة الحساب:\n<code>123456789</code>',parse_mode='HTML'); bot.register_next_step_handler(msg,admin_user_lookup); bot.answer_callback_query(call.id)

def admin_user_lookup(message):
    if message.from_user.id!=OWNER_ID:return
    raw=(message.text or '').strip()
    if not raw.isdigit(): bot.reply_to(message,'❌ ابعت User ID رقمي فقط.'); return
    uid=int(raw); add_user_to_db(uid); expiry=get_hosting_expiry(uid); points=get_points(uid); status='🟢 فعال' if expiry and expiry>datetime.now() else ('❄️ مجمد' if is_frozen(uid) else '🔴 منتهي')
    text=f'👤 <b>إدارة المستخدم</b>\n━━━━━━━━━━━━━━━\n🆔 <code>{uid}</code>\n{status}\n⏳ {expiry.strftime("%Y-%m-%d %H:%M") if expiry else "—"}\n💎 النقاط: <b>{points}</b>\n🚫 محظور: <b>{"نعم" if is_banned(uid) else "لا"}</b>'
    m=types.InlineKeyboardMarkup(); m.add(CButton('➕ 1 يوم',callback_data=f'admin_addday_{uid}_1',style=STYLE_SUCCESS),CButton('➕ 7 أيام',callback_data=f'admin_addday_{uid}_7',style=STYLE_SUCCESS)); m.add(CButton('➕ 30 يوم',callback_data=f'admin_addday_{uid}_30',style=STYLE_SUCCESS)); m.add(CButton('❄️/🔥 تجميد/فك',callback_data=f'admin_freeze_{uid}',style=STYLE_PRIMARY)); m.add(CButton('🚫 حظر/رفع الحظر',callback_data=f'admin_ban_{uid}',style=STYLE_DANGER)); bot.send_message(OWNER_ID,text,parse_mode='HTML',reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('admin_addday_','admin_freeze_','admin_ban_')))
def admin_user_action(call):
    if not _admin_only(call): bot.answer_callback_query(call.id,'غير مصرح لك.'); return
    parts=call.data.split('_'); uid=int(parts[2])
    if parts[1]=='addday': days=int(parts[3]); add_user_to_db(uid); exp=add_hosting_days(uid,days); record_admin_action('grant_days',uid,f'{days} days'); text=f'✅ تم إضافة <b>{days}</b> يوم للمستخدم <code>{uid}</code>.\n⏳ حتى {exp.strftime("%Y-%m-%d %H:%M")}.'
    elif parts[1]=='freeze': ok,res=(unfreeze_subscription(uid) if is_frozen(uid) else freeze_subscription(uid)); text='✅ تم تنفيذ العملية.' if ok else f'⚠️ {res}'
    else: banned=not is_banned(uid); set_ban(uid,banned,'إجراء من المطور'); text=f'🚫 حالة الحظر الآن: {"محظور" if banned else "غير محظور"}.'
    bot.answer_callback_query(call.id,'تم'); bot.send_message(OWNER_ID,text,parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data=='dev_payments')
def dev_payments(call):
    if not _admin_only(call): bot.answer_callback_query(call.id,'غير مصرح لك.'); return
    with DB_LOCK:
        conn=sqlite3.connect(DATABASE_PATH,check_same_thread=False); rows=conn.execute('SELECT user_id,method,package,amount,currency,created_at FROM payment_transactions WHERE status="paid" ORDER BY created_at DESC LIMIT 15').fetchall(); conn.close()
    lines=['🧾 <b>آخر 15 عملية ناجحة</b>','━━━━━━━━━━━━━━━']
    if not rows: lines.append('لا توجد عمليات بعد.')
    for uid,method,pkg,amount,currency,created in rows: lines.append(f'• <code>{uid}</code> | {pkg} | {amount} {currency} | {method} | {created[:16].replace("T"," ")}')
    m=types.InlineKeyboardMarkup(); m.add(CButton('🔙 الاشتراكات',callback_data='dev_subscriptions',style=STYLE_PRIMARY)); bot.edit_message_text('\n'.join(lines),call.message.chat.id,call.message.message_id,parse_mode='HTML',reply_markup=m)

# --- Cleanup on Exit ---
def cleanup():
    script_keys_to_stop = list(bot_scripts.keys())
    for key in script_keys_to_stop:
        if key in bot_scripts:
            script_info_to_kill = bot_scripts[key]
            kill_process_tree(script_info_to_kill)
            if key in bot_scripts:
                del bot_scripts[key]
atexit.register(cleanup)

# --- Main Execution ---
if __name__ == '__main__':
    if not TOKEN:
        logger.error('BOT_TOKEN غير مضبوط. أضف التوكن في متغير البيئة BOT_TOKEN ثم أعد التشغيل.')
        raise SystemExit('BOT_TOKEN is required')
    try:
        BOT_USERNAME = bot.get_me().username
        logger.info(f"Bot username resolved: @{BOT_USERNAME}")
    except Exception as e:
        logger.error(f"Failed to fetch bot username, referral links will use a placeholder: {e}")
        BOT_USERNAME = "your_bot"

    keep_alive()
    bot.infinity_polling()

#  ╭───𓆩🛡️𓆪───╮
#  👨‍💻 𝘿𝙚𝙫: @avetaar
#   📢 𝘾𝙝: @EgyCodes
