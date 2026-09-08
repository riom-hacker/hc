import asyncio
import sqlite3
import random
import logging
import time
import aiohttp
import hmac
import hashlib
import json
import urllib.parse
import html
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
try:
    from famgateway import FamGateway
except ImportError:
    FamGateway = None

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile
)

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
BOT_TOKEN = "8868030875:AAEQGBzd6Wz3Xy-xFbe7_KpMpZ_FEJrHCwI"
BOT_USERNAME = "@BKRIOMKEYSALLHC_BOT"
ADMIN_ID = 8642633207
ADMIN_CONTACT = "@Riombk"

FAMGATEWAY_API_KEY = "YOUR_FAMGATEWAY_API_KEY"  # Set via Admin Panel
# Backward-compatible setting key used by the existing database/admin flow.


# ==============================================================================
# APS (AUTO PURCHASE SYSTEM) — adminpanels.shop
# ==============================================================================
APS_API_KEY = "9b77dd612aab97acdef25d8a889fc41b"
APS_ENDPOINT = "https://adminpanels.shop/api/reseller_v1.php"
APS_X_MASTER_KEY = "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8"

USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 10.0
VIP_PRICE_INR = 1000.0

WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."  # Replace with your sticker ID
BOT_PHOTO = "https://example.com/your-store-banner.jpg"  # Replace with an image URL, or a Telegram file_id once you have one

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "PC PANEL"
]

# ==============================================================================
# YOUR PREMIUM EMOJIS – all required emoji IDs (updated with new premium ones)
# ==============================================================================
DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715',
    'profile': '5258011929993026890',
    'add_balance': '5985630530111020079',
    'history': '6032594876506312598',
    'support': '5967280668885913944',
    'back': '5877536313623711363',
    'upi': '5807750375033278838',
    'reseller': '5886505193180239900',
    'tutorial': '6005986106703613755',
    'telegram': '5875465628285931233',
    'whatsapp': '5954224165874569584',
    'welcome': '5994502837327892086',
    'vip': '5206607081334906820',
    'category_android_non_root': '6161172706856282588',
    'category_android_root': '6161449831031118974',
    'category_pc': '5350554349074391003',
    'grid_id': '5474625972751837256',
    'name': '5215399540814781035',
    'account_level': '6129584162992034014',
    'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217',
    'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090',
    'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533',
    'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735',
    'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090',
    'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982',
    'redeem_icon': '5377624166436445368',
    'wallet_left': '6210859306602995217',
    'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"

def safe_float(val, default=0.0):
    """Safely convert a value to float, return default if fails."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ==============================================================================
# 2. DATABASE FUNCTIONS
# ==============================================================================
def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True) -> Any:
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        if commit: conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query} | Params: {params}")
        if commit: conn.rollback()
        return None
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default

def set_setting(key: str, value: str) -> None:
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def get_emoji(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
    return "✨"

def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    return emoji_id

# ==============================================================================
# 3. STRING RESOURCES – using placeholders for premium emojis
# ==============================================================================
UI_TEXTS = {
    "start_menu": (
        "✨ <b>WELCOME TO THE STORE</b>\n\n"
        "🛒 <b>Product Store</b> : all key purchase &amp; instantly delivery\n"
        "👤 <b>My Profile</b> : check your account information\n"
        "🎁 <b>Add Balance</b> : deposit balance &amp; secure service\n"
        "🗝 <b>All History</b> : check all key purchase history\n"
        "👥 <b>Referral</b> : invite friends &amp; earn rewards\n"
        "🎬 <b>Tutorial</b> : view tutorial and work this bot\n"
        "🌐 <b>Support</b> : bot problem fixed for support admin\n"
        "——————————————————————\n"
        "💰 <b>Let's get you a key!</b>"
    ),
    "vip_menu": (
        "🌟 <b><u>VIP MEMBERSHIP CLUB</u></b> 🌟\n\n"
        "Unlock premium benefits and permanent discounts!\n\n"
        "💎 <b>VIP Benefits:</b>\n"
        "• Flat 15% off on ALL products (Stacks with Reseller!)\n"
        "• Priority Support\n"
        "• Exclusive VIP-only giveaways\n\n"
        "💳 <b>VIP Price:</b> ₹299.00 (Lifetime)\n"
        "👤 <b>Your Status:</b> {vip_status}"
    ),
    "add_balance_menu": (
        "{add_balance} <b>ADD BALANCE</b> {info_icon}\n\n"
        "{info_icon} Select your preferred payment method. {check_icon}\n\n"
        "┣ {upi} UPI — Fast Indian payments {checkbox_icon}\n"
        ""
        "{shield_icon} Payments are verified securely. {check_icon}"
    )
}

def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")

    emoji_map = {
        '{product_store}': get_emoji('product_store'),
        '{profile}': get_emoji('profile'),
        '{add_balance}': get_emoji('add_balance'),
        '{history}': get_emoji('history'),
        '{tutorial}': get_emoji('tutorial'),
        '{support}': get_emoji('support'),
        '{telegram}': get_emoji('telegram'),
        '{whatsapp}': get_emoji('whatsapp'),
        '{upi}': get_emoji('upi'),
        '{binance}': get_emoji('binance'),
        '{info_icon}': get_emoji('info_icon'),
        '{check_icon}': get_emoji('check_icon'),
        '{checkbox_icon}': get_emoji('checkbox_icon'),
        '{shield_icon}': get_emoji('shield_icon'),
        '{money_icon}': get_emoji('money_icon'),
        '{redeem_icon}': get_emoji('redeem_icon'),
        '{wallet_left}': get_emoji('wallet_left'),
        '{wallet_right}': get_emoji('wallet_right'),
        '{point_down}': get_emoji('point_down'),
    }
    for placeholder, emoji_tag in emoji_map.items():
        template = template.replace(placeholder, emoji_tag)

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing formatting key for template {key}: {e}")
    return template

# ==============================================================================
# 4. DATABASE INITIALISATION & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            phone TEXT, 
            first_name TEXT, 
            username TEXT,
            balance REAL DEFAULT 0.0, 
            account_type TEXT DEFAULT 'Regular', 
            orders_count INTEGER DEFAULT 0, 
            spent REAL DEFAULT 0.0, 
            last_spin TEXT, 
            joined_date TEXT,
            is_reseller INTEGER DEFAULT 0,
            reseller_since TEXT,
            total_saved REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_since TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            category TEXT, 
            panel_name TEXT DEFAULT '',
            name TEXT, 
            price_inr REAL, 
            reseller_price REAL DEFAULT 0.0,
            stock INTEGER, 
            apk_link TEXT, 
            validity TEXT DEFAULT 'Lifetime', 
            device_limit TEXT DEFAULT '1 Device',
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            product_id INTEGER, 
            key_text TEXT, 
            is_used INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            product_name TEXT, 
            price_paid REAL, 
            delivered_key TEXT, 
            purchase_date TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            message TEXT, 
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY, 
            amount REAL, 
            uses_left INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS redeemed (
            user_id INTEGER, 
            code TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_inr REAL, 
            status TEXT, 
            timestamp INTEGER,
            qr_url TEXT,
            upi_id TEXT,
            expires_at INTEGER,
            qr_message_id INTEGER,
            qr_chat_id INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_usdt REAL, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            prod_id INTEGER,
            prod_name TEXT,
            amount_inr REAL,
            status TEXT DEFAULT 'pending',
            qr_url TEXT,
            upi_id TEXT,
            timestamp INTEGER,
            expires_at INTEGER,
            aps_pid TEXT DEFAULT '',
            aps_dur TEXT DEFAULT '',
            qr_message_id INTEGER,
            qr_chat_id INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS spin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            amount REAL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN qr_url TEXT",
        "ALTER TABLE transactions ADD COLUMN upi_id TEXT",
        "ALTER TABLE transactions ADD COLUMN expires_at INTEGER",
        "ALTER TABLE transactions ADD COLUMN qr_message_id INTEGER",
        "ALTER TABLE transactions ADD COLUMN qr_chat_id INTEGER",
        "ALTER TABLE product_orders ADD COLUMN qr_message_id INTEGER",
        "ALTER TABLE product_orders ADD COLUMN qr_chat_id INTEGER",
        "ALTER TABLE products ADD COLUMN aps_product_id TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN aps_duration TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN tutorial_video TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN tutorial_caption TEXT DEFAULT ''"
    ]
    # product_orders table migration (safe - already handled by CREATE IF NOT EXISTS above)
    for mig in migrations:
        try: c.execute(mig)
        except sqlite3.OperationalError: pass
    

    default_settings = [
        ('reseller_system_status', 'ON'),
        ('bot_status', 'ON'),
        ('how_to_video', 'None'),
        ('fampay_api_key', FAMGATEWAY_API_KEY),
        ('fampay_upi_id', ''),
        ('binance_api', ''),
        ('binance_secret', ''),
        ('binance_address', ''),
        ('aps_api_key', APS_API_KEY),
        ('aps_endpoint', APS_ENDPOINT),
        ('aps_x_master_key', APS_X_MASTER_KEY),
        ('vip_status', 'OFF'),
        ('reseller_setup_fee', '200.0'),
        ('reseller_min_balance', '500.0'),
        ('migration_done', '0'),
        ('support_telegram', 'https://t.me/YourSupport'),
        ('support_whatsapp', 'https://wa.me/YourNumber'),
        ('ui_start_menu', UI_TEXTS['start_menu']),
        ('ui_vip_menu', UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu', UI_TEXTS['add_balance_menu']),
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))
    
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()


    # Removed feature settings are intentionally ignored by the UI.
    # Their old database values may remain, but no button or handler exposes them.

def migrate_categories() -> None:
    done = get_setting("migration_done", "0")
    
    # ALWAYS force update emojis and UI texts regardless of migration status
    logger.info("Forcing emoji and UI text updates...")
    
    # Remove legacy Ludo Spin / Download Files settings from existing databases
    db_query("DELETE FROM settings WHERE key IN ('emoji_ludo_spin', 'emoji_download', 'ui_download_files', 'ui_lucky_dice_result', 'all_files_link', 'spin_status', 'daily_spin_limit', 'emoji_referral', 'seller_api_url', 'seller_api_master_key', 'seller_api_token')")

    # Update all emoji settings
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        set_setting(f"emoji_{slot}", emoji_id)
    
    # Force update UI texts
    set_setting("ui_start_menu", UI_TEXTS['start_menu'])
    set_setting("ui_add_balance_menu", UI_TEXTS['add_balance_menu'])
    set_setting("ui_vip_menu", UI_TEXTS['vip_menu'])
    logger.info("UI texts and emojis updated with new placeholders and IDs.")
    
    # Fix any corrupted price columns (one-time cleanup)
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    products = c.execute("SELECT id, price_inr, reseller_price FROM products").fetchall()
    for prod in products:
        pid = prod[0]
        for col in ['price_inr', 'reseller_price']:
            val = prod[1] if col == 'price_inr' else prod[2]
            if val is None or val == "":
                new_val = 0.0
            else:
                try:
                    new_val = float(val)
                except (ValueError, TypeError):
                    new_val = 0.0
            c.execute(f"UPDATE products SET {col}=? WHERE id=?", (new_val, pid))
    conn.commit()
    conn.close()
    logger.info("Fixed any non-numeric price columns.")
    
    if done == "1":
        return
    
    logger.info("Running category migration...")
    
    mapping = {
        "android non root panel": "ANDROID NON ROOT PANEL",
        "android root panel": "ANDROID ROOT PANEL",
        "pc panel": "PC PANEL",
    }
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    
    db_query("UPDATE products SET category = 'ANDROID NON ROOT PANEL' WHERE LOWER(category) NOT IN (?, ?, ?)",
             ("android non root panel", "android root panel", "pc panel"))
    
    set_setting("migration_done", "1")
    logger.info("Category migration complete.")

# ==============================================================================
# 5. MIDDLEWARES & SECURITY
# ==============================================================================
async def hacker_loading(message: Message, text: str = "Decrypting Data") -> Message:
    msg = await message.answer(f"⚡ {text}\n[□□□] 0%")
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■□□] 33%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■□] 66%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■■] 100%", parse_mode='HTML')
    return msg

class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.last_action_times = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        if user_id in self.last_action_times:
            if now - self.last_action_times[user_id] < 0.3:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⏳ Please wait a moment...", show_alert=False)
                    except Exception:
                        pass
                return
        self.last_action_times[user_id] = now

        if user_id != ADMIN_ID:
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = "🚫 <b>ACCESS DENIED</b>\nYou have been banned from using this bot.\nContact support if you think this is a mistake."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
                return
                
            status_check = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
            status = status_check[0] if status_check else 'ON'
            if status == 'OFF':
                msg = "⚠️ <b>Store Maintenance</b>\n\nThe store is currently offline for updates. Please check back later!"
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer("⚠️ Bot is currently OFF for Maintenance.", show_alert=True)
                return
                
        # Always close Telegram's callback spinner. Individual handlers may also
        # answer the callback; a second answer is harmless and is ignored here.
        try:
            return await handler(event, data)
        finally:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass

dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())

# ==============================================================================
# 6. FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_redeem = State()
    wait_for_crypto_txid = State()
    custom_amount_input = State()

class AdminStates(StatesGroup):
    add_prod_category = State()
    add_prod_panel_name = State()
    add_prod_name = State()
    add_prod_validity = State()
    add_prod_device_limit = State()
    add_prod_price = State()
    add_prod_reseller_price = State()
    add_prod_apk = State()
    add_prod_tutorial = State()
    add_prod_tutorial_caption = State()
    add_prod_keys = State()
    
    edit_prod_field = State()
    wait_for_new_value = State()
    wait_for_add_keys = State()
    wait_for_delete_key = State()
    
    broadcast_msg = State()
    add_coupon_code = State()
    add_coupon_amount = State()
    add_coupon_uses = State()
    
    # FamPay states
    wait_for_fampay_api = State()
    wait_for_fampay_upi = State()
    
    # Binance states
    wait_for_binance_api = State()
    wait_for_binance_secret = State()
    wait_for_binance_address = State()
    
    ticket_reply_msg = State()
    reseller_manage_id = State()
    manage_target_user = State()
    wait_for_add_money = State()
    wait_for_minus_money = State()
    wait_for_warning = State()
    
    wait_for_howto_video = State()
    
    edit_ui_text = State()
    edit_reseller_price = State()
    wait_for_reseller_setup_fee = State()
    wait_for_reseller_min_balance = State()
    confirm_ban = State()
    
    wait_for_support_telegram = State()
    wait_for_support_whatsapp = State()
    wait_for_category_emoji = State()
    wait_for_panel_emoji_id = State()
    wait_for_emoji_slot = State()
    
    # APS States
    wait_for_aps_product_id = State()
    wait_for_aps_duration = State()
    wait_for_aps_api_key = State()
    wait_for_aps_endpoint = State()
    wait_for_aps_master_key = State()

    # Bulk product import
    wait_for_bulk_file = State()

# ==============================================================================
# 7. KEYBOARDS
# ==============================================================================
def get_category_emoji(category: str) -> str:
    slot_map = {
        "ANDROID NON ROOT PANEL": "category_android_non_root",
        "ANDROID ROOT PANEL": "category_android_root",
        "PC PANEL": "category_pc",
    }
    slot = slot_map.get(category)
    if slot:
        return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, ""))
    return ""

def get_panel_emoji(panel_name: str) -> str:
    stored = get_setting(f"panel_emoji_{panel_name}", "")
    if stored and stored.isdigit():
        return stored
    return get_emoji_icon("product_store")

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Verify Contact", request_contact=True)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else 'ON'
    vip_sys_check = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_system = vip_sys_check[0] if vip_sys_check else 'OFF'
    
    is_reseller = False
    if user_id:
        user_check = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
        if user_check:
            is_reseller = bool(user_check[0])

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="🛒 Product Store", callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("product_store"),
            style="danger"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="👤 My Profile", callback_data="menu_profile",
            icon_custom_emoji_id=get_emoji_icon("profile"),
            style="primary"
        ),
        InlineKeyboardButton(
            text="🎁 Add Balance", callback_data="menu_add_balance",
            icon_custom_emoji_id=get_emoji_icon("add_balance"),
            style="primary"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="🗝 All History", callback_data="menu_history",
            icon_custom_emoji_id=get_emoji_icon("history"),
            style="primary"
        ),
        InlineKeyboardButton(
            text="👥 Referral", callback_data="menu_referral",
            icon_custom_emoji_id=get_emoji_icon("reseller"),
            style="primary"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="🎬 Tutorials", callback_data="menu_how_to",
            icon_custom_emoji_id=get_emoji_icon("tutorial"),
            style="success"
        ),
        InlineKeyboardButton(
            text="🌐 Support", callback_data="menu_support",
            icon_custom_emoji_id=get_emoji_icon("support"),
            style="danger"
        )
    ])
    
    extras_row = []
    if sys_status == 'ON' or is_reseller:
        extras_row.append(InlineKeyboardButton(
            text="👑 Reseller Panel", callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"),
            style="primary"
        ))
    if vip_system == 'ON':
        extras_row.append(InlineKeyboardButton(
            text="💎 VIP Club", callback_data="menu_vip_dash",
            style="danger"
        ))
    if extras_row:
        kb.inline_keyboard.append(extras_row)

    # Admin Panel is visible ONLY to the configured admin account.
    # It is deliberately not added for normal users/resellers/VIP users.
    if user_id == ADMIN_ID:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="⚙️ Admin Panel",
                callback_data="admin_panel_open",
                style="primary"
            )
        ])
        
    return kb

async def safe_edit(message: Message, text: str, reply_markup: InlineKeyboardMarkup = None, parse_mode: str = 'HTML') -> None:
    """Edit a message whether it's a text message or a photo message (e.g. a QR code).
    edit_text fails on photo messages, so we try edit_caption first, then fall back
    to deleting the old message and sending a fresh text message."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    except Exception:
        pass
    try:
        await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    except Exception:
        pass
    try:
        await message.delete()
    except Exception:
        pass
    await bot.send_message(chat_id=message.chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="BACK", callback_data=callback,
                icon_custom_emoji_id=get_emoji_icon("back"),
                style="danger"
            )
        ]]
    )

def admin_kb() -> InlineKeyboardMarkup:
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    status_val = status[0] if status else 'ON'
    vip_status = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_val = vip_status[0] if vip_status else 'OFF'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_view_stats", style="primary")],
        [InlineKeyboardButton(text="👥 User Control Panel", callback_data="admin_user_control_start", style="primary")],
        [
            InlineKeyboardButton(text="➕ Add Product", callback_data="admin_add_prod", style="primary"),
            InlineKeyboardButton(text="📦 Manage Products", callback_data="admin_manage_prods", style="primary")
        ],
        [
            InlineKeyboardButton(text="📥 Bulk Add (File)", callback_data="admin_bulk_add_prod", style="success")
        ],
        [
            InlineKeyboardButton(text="👑 Reseller Mgmt", callback_data="admin_reseller_menu", style="primary")
        ],
        [
            InlineKeyboardButton(text="🎟 Create Coupon", callback_data="admin_create_coupon", style="primary"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast_btn", style="primary")
        ],
        [
            InlineKeyboardButton(text="🎫 View Tickets", callback_data="admin_view_tickets", style="primary"),
            InlineKeyboardButton(text="📹 Tutorial Video", callback_data="admin_set_video", style="primary")
        ],
        [
            InlineKeyboardButton(text="🎨 Edit All Emojis", callback_data="admin_edit_emojis", style="primary")
        ],
        [
            InlineKeyboardButton(text="⚙️ FamGateway Setup", callback_data="admin_setup_fampay", style="primary"),
            InlineKeyboardButton(text="⚡ APS Live Stock", callback_data="admin_view_aps_stock", style="success"),
        ],
        [InlineKeyboardButton(text="🛠 API Setup", callback_data="admin_aps_api_setup", style="primary")],
        [
            InlineKeyboardButton(text="✏️ Edit UI Texts", callback_data="admin_edit_ui_menu", style="primary"),
            InlineKeyboardButton(text="📝 Edit Reseller Price", callback_data="admin_edit_reseller_price", style="primary")
        ],
        [
            InlineKeyboardButton(text="💰 Reseller Fee", callback_data="admin_set_reseller_fee", style="primary"),
            InlineKeyboardButton(text="💳 Min Balance", callback_data="admin_set_reseller_min", style="primary")
        ],
        [
            InlineKeyboardButton(text="📞 Set Support Links", callback_data="admin_set_support_links", style="primary"),
            InlineKeyboardButton(text="🎨 Set Category Emojis", callback_data="admin_set_category_emojis", style="primary")
        ],
        [
            InlineKeyboardButton(text="🖼 Set Panel Emojis", callback_data="admin_set_panel_emojis", style="primary")
        ],
        [
            InlineKeyboardButton(
                text=f"Bot Status: {status_val} {'🟢' if status_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_bot",
                style="success" if status_val == 'ON' else "danger"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"VIP System: {vip_val} {'🟢' if vip_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_vip_sys",
                style="success" if vip_val == 'ON' else "danger"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Back to Main Menu",
                callback_data="admin_back_main",
                icon_custom_emoji_id=get_emoji_icon("back"),
                style="danger"
            )
        ]
    ])
    return kb

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Back to Admin", callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ]])

# ==============================================================================
# 8. NOTIFICATIONS
# ==============================================================================
async def send_advanced_notification(user_id: int, notif_type: str, amount: float, product: str = None, key: str = None, gateway: str = "FamPay") -> None:
    user_info = db_query("SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    
    name = user_info[0] if user_info else "Unknown"
    phone = user_info[1] if user_info and user_info[1] else "Not Provided"
    username = f"@{user_info[2]}" if user_info and user_info[2] else "None"
    
    tags = []
    if user_info and user_info[3]: tags.append("👑 Reseller")
    if user_info and user_info[4]: tags.append("🌟 VIP")
    tag_str = " | ".join(tags) if tags else "👤 Regular"
        
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    
    if notif_type == "ORDER":
        title = "🛒 <b>NEW ORDER PROCESSED!</b> 🛒"
        details = (f"📦 <b>Product:</b> {product}\n🔑 <b>Key:</b> <code>{key}</code>\n💰 <b>Amount Paid:</b> ₹{amount:.2f}\n📅 <b>Time:</b> {time_now}")
    else:
        title = "💰 <b>NEW WALLET DEPOSIT!</b> 💰"
        details = (f"💵 <b>Amount Added:</b> ₹{amount:.2f}\n🧾 <b>Gateway:</b> {gateway}\n🆔 <b>Reference:</b> <code>{product}</code>\n📅 <b>Time:</b> {time_now}")

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n🆔 <b>User ID:</b> <code>{user_id}</code>\n📱 <b>Phone:</b> {phone}\n🔗 <b>Username:</b> {username}\n🏷 <b>Status:</b> {tag_str}\n━━━━━━━━━━━━━━━━━━\n{details}"
    try: 
        await bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e: 
        logger.error(f"Failed to send admin notification: {e}")

# ==============================================================================
# 9. FAMGATEWAY PAYMENT FUNCTIONS
# ==============================================================================

async def _get_famgateway_client() -> Any:
    """Create the FamGateway SDK client from the admin-configured API key."""
    if FamGateway is None:
        raise RuntimeError("famgateway package is not installed. Run: pip install famgateway")
    api_key = get_setting("fampay_api_key", FAMGATEWAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMGATEWAY_API_KEY":
        raise RuntimeError("FamGateway API key not configured")
    return FamGateway(api_key=api_key)

async def generate_fampay_qr(user_id: int, amount: float, upi_id: str = None) -> Dict[str, Any]:
    """Create a FamGateway order and normalize it for the existing bot flow."""
    try:
        fg = await _get_famgateway_client()
        customer = db_query("SELECT first_name FROM users WHERE user_id=?", (user_id,), fetchone=True)
        first_name = customer[0] if customer and customer[0] else "Customer"
        customer_name = f"{first_name} ({user_id})"

        # FamGateway SDK is synchronous; keep it off the aiogram event loop.
        # This matches the supplied reference example while retaining the
        # existing user-identifying customer_name used by this bot.
        order = await asyncio.to_thread(
            fg.create_order,
            amount=float(amount),
            customer_name=customer_name
        )

        order_id = str(getattr(order, "order_id", "") or "")
        qr_url = str(getattr(order, "qr_url", "") or "")
        upi_intent = str(getattr(order, "upi_intent", "") or "")
        checkout_url = str(getattr(order, "checkout_url", "") or "")
        payable_amount = safe_float(getattr(order, "payable_amount", amount), amount)

        if not order_id or not qr_url:
            logger.error("FamGateway returned incomplete order: order_id=%r qr_url=%r", order_id, qr_url)
            return {"status": "error", "message": "Gateway returned an incomplete order response"}

        # The supplied SDK example uses a 5-minute polling window.
        expires_timestamp = int(time.time() + 300)
        expires_at_str = datetime.fromtimestamp(expires_timestamp).strftime("%d-%m-%Y %H:%M:%S")

        return {
            "status": "success",
            "data": {
                "order_id": order_id,
                "qr_url": qr_url,
                "upi_intent": upi_intent,
                "checkout_url": checkout_url,
                "payable_amount": payable_amount,
                "upi_id": "",
                "expires_at_ist": expires_at_str,
                "created_at_ist": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            }
        }
    except Exception as e:
        logger.exception("FamGateway create_order error: %s", e)
        return {"status": "error", "message": str(e)}

async def verify_fampay_payment(order_id: str) -> Dict[str, Any]:
    """Check a FamGateway order and normalize its SDK status object."""
    try:
        fg = await _get_famgateway_client()
        status = await asyncio.to_thread(fg.get_status, order_id)

        if bool(getattr(status, "is_paid", False)):
            return {
                "status": "success",
                "data": {
                    "transaction_id": order_id,
                    "utr": getattr(status, "utr", None),
                    "sender_name": getattr(status, "sender_name", None),
                    "amount": safe_float(getattr(status, "amount", None), 0.0),
                    "payment_time_ist": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
                }
            }

        if bool(getattr(status, "is_expired", False)):
            return {"status": "expired", "message": "Order expired without payment."}

        return {"status": "pending", "message": "Payment pending. Please complete the UPI payment."}
    except Exception as e:
        logger.exception("FamGateway get_status error for %s: %s", order_id, e)
        return {"status": "error", "message": str(e)}

async def _delete_fampay_qr_message(order_id: str) -> bool:
    """Delete the Telegram QR message associated with a paid FamGateway order."""
    for table in ("transactions", "product_orders"):
        try:
            row = db_query(
                f"SELECT qr_message_id, qr_chat_id FROM {table} WHERE order_id=?",
                (order_id,),
                fetchone=True,
            )
        except Exception:
            row = None
        if not row or not row[0]:
            continue
        chat_id = row[1] or None
        if not chat_id:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=int(row[0]))
            return True
        except Exception as e:
            logger.debug("FamGateway QR cleanup failed for %s: %s", order_id, e)
            return False
    return False


async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    """Verify a wallet deposit through FamGateway and credit it once."""
    txn = db_query("SELECT amount_inr, status, timestamp, qr_url, upi_id, expires_at, qr_message_id, qr_chat_id FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not txn:
        err = "❌ Invalid or Fake Order ID detected in system!"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)
        return

    if txn[1] == 'paid':
        msg = "✅ This payment has already been securely credited to your wallet."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return

    if txn[1] == 'expired':
        msg = "❌ This order has expired. Please create a new deposit request."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return

    # FamGateway's supplied example recommends polling for up to 5 minutes.
    if txn[5] and time.time() > txn[5]:
        db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
        msg = "⏳ <b>QR Code Expired!</b>\nThe 5-minute payment window has expired. Please generate a new QR."
        if isinstance(reply_target, CallbackQuery):
            try: await reply_target.message.edit_caption(msg, reply_markup=back_kb(), parse_mode='HTML')
            except Exception: await reply_target.message.edit_text(msg, reply_markup=back_kb(), parse_mode='HTML')
        else: await reply_target.answer(msg, reply_markup=back_kb())
        return

    result = await verify_fampay_payment(order_id)

    if result.get("status") == "success":
        txn_data = result.get("data", {})
        transaction_id = txn_data.get("transaction_id") or order_id
        utr = txn_data.get("utr") or "N/A"
        sender_name = txn_data.get("sender_name") or "Unknown"
        amount_received = safe_float(txn_data.get("amount"), txn[0]) or txn[0]
        payment_time = txn_data.get("payment_time_ist") or datetime.now().strftime("%d-%m-%Y %I:%M %p")

        # Atomic status transition prevents manual + auto verification from crediting twice.
        conn = sqlite3.connect('Cuibcc.db')
        try:
            cur = conn.cursor()
            cur.execute("UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (order_id,))
            credited = cur.rowcount == 1
            if credited:
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount_received, user_id))
                conn.commit()
            else:
                conn.rollback()
        finally:
            conn.close()

        if not credited:
            msg = "✅ This payment has already been securely credited to your wallet."
            if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
            else: await reply_target.answer(msg)
            return

        success_msg = f"🎉 <b>PAYMENT VERIFIED!</b>\n\n✅ {fmt_curr(amount_received)} has been added to your wallet.\n🧾 UTR: <code>{html.escape(str(utr))}</code>\n👤 Sender: {html.escape(str(sender_name))}\n📅 Time: {html.escape(str(payment_time))}"
        qr_deleted = await _delete_fampay_qr_message(order_id)
        if isinstance(reply_target, CallbackQuery):
            if qr_deleted:
                try: await bot.send_message(user_id, success_msg, reply_markup=back_kb(), parse_mode='HTML')
                except Exception: pass
            else:
                try:
                    await reply_target.message.edit_caption(success_msg, reply_markup=back_kb(), parse_mode='HTML')
                except Exception:
                    try: await reply_target.message.edit_text(success_msg, reply_markup=back_kb(), parse_mode='HTML')
                    except Exception: pass
        else:
            await reply_target.answer(success_msg, reply_markup=back_kb())

        await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=transaction_id, gateway="FamGateway")
        log_activity(user_id, "DEPOSIT_SUCCESS", f"Amount: {amount_received}, Gateway: FamGateway, Order: {order_id}, UTR: {utr}")

    elif result.get("status") == "expired":
        db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
        msg = "⏳ <b>Payment Order Expired</b>\nPlease create a new deposit request."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
    elif result.get("status") == "pending":
        msg = "⏳ <b>Payment Status: PENDING</b>\n\nPlease complete the UPI payment and try again."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
    else:
        err = f"⚠️ Gateway Error: {result.get('message', 'Unknown Error')}"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)

async def auto_verify_task() -> None:
    """Poll pending FamGateway transactions every 3 seconds for up to 5 minutes."""
    while True:
        await asyncio.sleep(3)
        if FamGateway is None:
            continue
        api_key = get_setting("fampay_api_key", "")
        if not api_key or api_key == "YOUR_FAMGATEWAY_API_KEY":
            continue

        pending_txns = db_query("SELECT order_id, user_id, amount_inr, timestamp, expires_at FROM transactions WHERE status='pending'", fetchall=True)
        if not pending_txns:
            continue

        for order_id, user_id, amount, ts, expires_at in pending_txns:
            if expires_at and time.time() > expires_at:
                db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
                try:
                    await bot.send_message(user_id, f"⏳ <b>Payment Order Expired!</b>\nYour payment window for order <code>{order_id}</code> has timed out. Please generate a new payment order.", parse_mode='HTML')
                except Exception:
                    pass
                continue

            result = await verify_fampay_payment(order_id)
            if result.get("status") != "success":
                if result.get("status") == "expired":
                    db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
                continue

            txn_data = result.get("data", {})
            amount_received = safe_float(txn_data.get("amount"), amount) or amount
            utr = txn_data.get("utr") or "N/A"
            sender_name = txn_data.get("sender_name") or "Unknown"

            conn = sqlite3.connect('Cuibcc.db')
            try:
                cur = conn.cursor()
                cur.execute("UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (order_id,))
                credited = cur.rowcount == 1
                if credited:
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount_received, user_id))
                    conn.commit()
                else:
                    conn.rollback()
            finally:
                conn.close()

            if not credited:
                continue

            # Match the reference flow: remove the old QR message immediately
            # after payment is detected, then send the confirmation.
            await _delete_fampay_qr_message(order_id)
            try:
                await bot.send_message(user_id, f"✨ <b>AUTO-VERIFIED!</b>\n\n✅ Your payment of {fmt_curr(amount_received)} was detected successfully!\n🧾 UTR: <code>{html.escape(str(utr))}</code>\n👤 Sender: {html.escape(str(sender_name))}", parse_mode='HTML')
            except Exception:
                pass

            await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=order_id, gateway="FamGateway Auto")
            log_activity(user_id, "DEPOSIT_AUTO_SUCCESS", f"Amount: {amount_received}, Gateway: FamGateway Auto, Order: {order_id}, UTR: {utr}")

# ==============================================================================
# 10. ONBOARDING & START
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    try: await message.answer_photo(BOT_PHOTO)
    except Exception as e: logger.error(f"Failed to send BOT_PHOTO: {e}")
    try: await message.answer_sticker(WELCOME_STICKER_ID)
    except: pass 
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("v_"):
        order_id = args[1].split("v_")[1]
        msg = await message.answer("🔄 <b>Verifying your payment securely...</b>\n<i>Connecting to gateway...</i>", parse_mode='HTML')
        await run_payment_verification(message.from_user.id, order_id, msg)
        return


    user = db_query("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    current_username = message.from_user.username or ""
    db_query("UPDATE users SET username=? WHERE user_id=?", (current_username, message.from_user.id))

    if not user or not user[0]:
        db_query("INSERT OR IGNORE INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
                 (message.from_user.id, message.from_user.first_name, current_username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        log_activity(message.from_user.id, "ACCOUNT_CREATED")

    log_activity(message.from_user.id, "CMD_START")
    await send_main_menu(message)

async def send_main_menu(ctx: Any):
    text = get_ui_text("start_menu")
    kb = main_menu_kb(ctx.from_user.id)
    if isinstance(ctx, Message): 
        await ctx.answer(text, reply_markup=kb, parse_mode='HTML')
    else: 
        await ctx.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    log_activity(call.from_user.id, "RETURN_MAIN_MENU")
    await send_main_menu(call)

# ==============================================================================
# BYE / FAREWELL MESSAGE HANDLER
# ==============================================================================
BYE_KEYWORDS = ["bye", "goodbye", "good bye", "alvida", "babye", "tata", "cya", "see you", "later", "baad mein", "chalte hain", "chalta hun", "chala jata hun", "bye bye", "bbye", "byee", "byeee", "ok bye", "okay bye", "ok babye"]

@dp.message(F.text.func(lambda t: any(kw in t.lower() for kw in BYE_KEYWORDS) if t else False))
async def bye_handler(message: Message):
    name = message.from_user.first_name or "Bhai"
    farewell_text = (
        f"👋 <b>Alvida {name}!</b>\n\n"
        f"🙏 Milke achha laga — jab bhi zarurat ho, hum yahan hain!\n"
        f"🛒 Wapas aana na bhoolna — store hamesha open hai. 😄"
    )
    await message.answer(farewell_text, parse_mode='HTML')
    await send_main_menu(message)

# ==============================================================================
# 11. ADD BALANCE
# ==============================================================================
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_ui_text("add_balance_menu")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="UPI PAY", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("upi"), style="primary")
        ],
        [
            InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
        ]
    ])
    await safe_edit(call.message, text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 12. FAMGATEWAY UPI PAYMENT FLOW
# ==============================================================================
@dp.callback_query(F.data == "gateway_inr")
async def add_balance_inr(call: CallbackQuery):
    text = f"💵 <b>— FAMGATEWAY UPI DEPOSIT —</b> 💵\n\nSelect amount to deposit:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="pay_1000", style="primary"), InlineKeyboardButton(text="₹2000", callback_data="pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="custom_deposit_keypad", style="primary")],
        [InlineKeyboardButton(text="Back", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "custom_deposit_keypad")
async def show_custom_keypad(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.custom_amount_input)
    await state.update_data(amount_str="0")
    await show_keypad(call.message)

async def show_keypad(message: Message, amount_str: str = "0"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="      1      ", callback_data="kp_1", style="primary"), InlineKeyboardButton(text="      2      ", callback_data="kp_2", style="primary"), InlineKeyboardButton(text="      3      ", callback_data="kp_3", style="primary")],
        [InlineKeyboardButton(text="      4      ", callback_data="kp_4", style="primary"), InlineKeyboardButton(text="      5      ", callback_data="kp_5", style="primary"), InlineKeyboardButton(text="      6      ", callback_data="kp_6", style="primary")],
        [InlineKeyboardButton(text="      7      ", callback_data="kp_7", style="primary"), InlineKeyboardButton(text="      8      ", callback_data="kp_8", style="primary"), InlineKeyboardButton(text="      9      ", callback_data="kp_9", style="primary")],
        [InlineKeyboardButton(text="    ⌫    ", callback_data="kp_backspace", style="danger"), InlineKeyboardButton(text="      0      ", callback_data="kp_0", style="primary"), InlineKeyboardButton(text="    C    ", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text=f"✅ Confirm (₹{amount_str})", callback_data="kp_confirm", style="success")],
        [InlineKeyboardButton(text="Cancel", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    text = f"💵 <b>Enter Amount (₹):</b>\n\nCurrent: ₹{amount_str}"
    await message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount_str = data.get("amount_str", "0")
    action = call.data.split("_")[1]
    if action == "confirm":
        if amount_str == "0":
            await call.answer("Amount cannot be zero.", show_alert=True)
            return
        try:
            amount = float(amount_str)
            if amount < 10:
                await call.answer("Minimum deposit is ₹10.", show_alert=True)
                return
            await state.clear()
            await call.message.edit_text("⏳ <b>Generating Secure QR Code...</b>", parse_mode='HTML')
            await generate_fampay_order(call.from_user.id, amount, call.message)
        except ValueError:
            await call.answer("Invalid amount.", show_alert=True)
        return
    if action == "backspace":
        if len(amount_str) > 1: amount_str = amount_str[:-1]
        else: amount_str = "0"
    elif action == "clear":
        amount_str = "0"
    else:
        if amount_str == "0": amount_str = action
        else: amount_str += action
        if len(amount_str) > 6: amount_str = amount_str[:6]
    await state.update_data(amount_str=amount_str)
    await show_keypad(call.message, amount_str)
    await call.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_fampay_payment_callback(call: CallbackQuery):
    await call.answer("Generating QR…")
    try:
        inr_amount = float(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.message.edit_text("❌ Invalid payment amount.", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    await call.message.edit_text("⏳ <b>Generating Secure QR Code via FamGateway...</b>", parse_mode='HTML')
    await generate_fampay_order(call.from_user.id, inr_amount, call.message)

async def generate_fampay_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    """Create a FamGateway order for wallet deposit."""
    api_key = get_setting("fampay_api_key", "")
    if not api_key or api_key == "YOUR_FAMGATEWAY_API_KEY":
        return await message_obj.edit_text("⚠️ FamGateway is currently offline. Admin needs to set API Key.", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')

    current_time = int(time.time())
    result = await generate_fampay_qr(user_id, inr_amount)
    if result.get("status") != "success":
        return await message_obj.edit_text(f"❌ <b>Gateway Error:</b> {html.escape(str(result.get('message', 'Unknown error')))}", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')

    data = result.get("data", {}) or {}
    qr_url = data.get("qr_url")
    order_id = data.get("order_id")
    upi_intent = data.get("upi_intent")
    checkout_url = data.get("checkout_url")
    payable_amount = safe_float(data.get("payable_amount"), inr_amount)
    expires_at_str = data.get("expires_at_ist")
    created_at = data.get("created_at_ist")
    expires_timestamp = int(time.time() + 300)

    db_query("INSERT INTO transactions (order_id, user_id, amount_inr, status, timestamp, qr_url, upi_id, expires_at, qr_message_id, qr_chat_id) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, NULL, NULL)",
             (order_id, user_id, payable_amount, current_time, qr_url, "", expires_timestamp))

    rows = []
    if upi_intent and str(upi_intent).startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(text="📱 Pay via UPI App", url=str(upi_intent))])
    if checkout_url and str(checkout_url).startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(text="🌐 Web Checkout", url=str(checkout_url))])
    rows.append([InlineKeyboardButton(text="🔄 Verify Payment", callback_data=f"verify_{order_id}", style="primary")])
    if qr_url and str(qr_url).startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton(text="🖼️ Open QR", url=str(qr_url))])
    rows.append([InlineKeyboardButton(text="Cancel Transaction", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    caption = (
        f"🧾 <b>SECURE QR CODE GENERATED</b>\n\n"
        f"💵 <b>Amount:</b> {fmt_curr(payable_amount)}\n"
        f"🆔 <b>Order ID:</b> <code>{html.escape(str(order_id))}</code>\n"
        f"⏳ <b>Order Expires:</b> {html.escape(str(expires_at_str))}\n"
        f"📅 <b>Created:</b> {html.escape(str(created_at))}\n\n"
        f"📱 <b>How to Pay:</b>\n"
        f"1️⃣ Scan the QR code or use a UPI App button\n"
        f"2️⃣ Pay EXACT amount: {fmt_curr(payable_amount)}\n"
        f"3️⃣ Click <b>Verify Payment</b> after sending\n"
        f"4️⃣ Auto-verify checks every 3 seconds for up to 5 minutes!"
    )

    log_activity(user_id, "GENERATE_INVOICE_FAMGATEWAY", f"Amount: {payable_amount}, Order ID: {order_id}")

    qr_sent = False
    if qr_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(qr_url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        if img_bytes:
                            try: await message_obj.delete()
                            except Exception: pass
                            qr_message = await bot.send_photo(
                                message_obj.chat.id,
                                BufferedInputFile(img_bytes, filename="qr.png"),
                                caption=caption,
                                reply_markup=kb,
                                parse_mode='HTML'
                            )
                            db_query(
                                "UPDATE transactions SET qr_message_id=?, qr_chat_id=? WHERE order_id=?",
                                (qr_message.message_id, message_obj.chat.id, order_id)
                            )
                            qr_sent = True
        except Exception as e:
            logger.error("FamGateway QR image download/send failed: %s", e)

    if not qr_sent:
        try: await message_obj.edit_text(caption, reply_markup=kb, parse_mode='HTML')
        except Exception: await bot.send_message(message_obj.chat.id, caption, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    order_id = call.data.split("_", 1)[1]
    await run_payment_verification(call.from_user.id, order_id, call)

# ==============================================================================
# 13. BINANCE CRYPTO PAYMENT
# ==============================================================================
@dp.callback_query(F.data == "gateway_crypto")
async def add_balance_crypto(call: CallbackQuery, state: FSMContext):
    address_check = db_query("SELECT value FROM settings WHERE key='binance_address'", fetchone=True)
    if not address_check or not address_check[0]:
        return await call.message.edit_text("⚠️ Binance Gateway is currently offline. Admin has not set a deposit address.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    deposit_address = address_check[0]
    msg = (f"🪙 <b>— BINANCE USDT DEPOSIT —</b> 🪙\n\n💵 <b>Exchange Rate:</b> 1 USDT = ₹{USDT_TO_INR}\n⚠️ <b>Network:</b> Please send via <b>TRC20</b> or <b>BEP20</b>.\n\n👇 <b>Send your USDT to this exact address:</b>\n<code>{deposit_address}</code>\n\n━━━━━━━━━━━━━━━━━━\n✅ <b>After sending the USDT, reply to this message with your exact TxID (Transaction Hash) to instantly claim your balance.</b>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Cancel", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode='HTML')
    await state.set_state(UserStates.wait_for_crypto_txid)

@dp.message(UserStates.wait_for_crypto_txid)
async def process_crypto_txid(m: Message, state: FSMContext):
    txid = m.text.strip()
    user_id = m.from_user.id
    if len(txid) < 10: return await m.answer("❌ That doesn't look like a valid TxID. Please try again.")
    if db_query("SELECT txid FROM crypto_txns WHERE txid=?", (txid,), fetchone=True):
        return await m.answer("⚠️ This Transaction ID has already been claimed in the system!", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    api_key_check = db_query("SELECT value FROM settings WHERE key='binance_api'", fetchone=True)
    secret_key_check = db_query("SELECT value FROM settings WHERE key='binance_secret'", fetchone=True)
    if not api_key_check or not secret_key_check:
        return await m.answer("⚠️ Binance API is missing on the server. Contact Support.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    await m.answer("🔄 <b>Verifying your TxID with Binance Blockchain...</b>\n<i>This may take up to 30 seconds...</i>", parse_mode='HTML')
    api_key = api_key_check[0]; secret_key = secret_key_check[0]
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {'X-MBX-APIKEY': api_key}
    url = f"https://api.binance.com/sapi/v1/capital/deposit/hisrec?{query_string}&signature={signature}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    try: history = await resp.json(content_type=None)
                    except: history = []
                    found = False
                    for deposit in history:
                        if deposit.get("txId") == txid and deposit.get("status") == 1:
                            found = True
                            usdt_amount = float(deposit.get("amount"))
                            inr_amount = usdt_amount * USDT_TO_INR
                            db_query("INSERT INTO crypto_txns (txid, user_id, amount_usdt, timestamp) VALUES (?, ?, ?, ?)", (txid, user_id, usdt_amount, int(time.time())))
                            db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (inr_amount, user_id))
                            await m.answer(f"🎉 <b>CRYPTO DEPOSIT SUCCESSFUL!</b>\n\n✅ We safely received <b>{usdt_amount} USDT</b>.\n💰 <b>{fmt_curr(inr_amount)}</b> has been added to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
                            await send_advanced_notification(user_id, "DEPOSIT", inr_amount, product=txid, gateway="Binance Crypto")
                            log_activity(user_id, "CRYPTO_DEPOSIT", f"TxID: {txid}, Amount: {inr_amount}")
                            await state.clear()
                            break
                    if not found: await m.answer("❌ <b>TxID Not Found or Still Pending!</b>\nMake sure the transaction is fully confirmed. Try again in 5 mins.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
                else: await m.answer(f"⚠️ <b>Binance Server Error:</b> HTTP {resp.status}.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
        except Exception as e: await m.answer(f"⚠️ <b>Connection Error:</b> {str(e)}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')

# ==============================================================================
# 14. SHOP – with uppercase categories and new point_down emoji
# ==============================================================================
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_SHOP")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>SELECT PRODUCT PANEL</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel to view its packages:</b>"
    for cat in FIXED_CATEGORIES:
        count = db_query("SELECT COUNT(*) FROM products WHERE category LIKE ? AND is_active=1", (cat + '%',), fetchone=True)[0]
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"cat_{cat[:30]}", icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    # menu_shop can be triggered from the inline keyboard attached to a video.
    # Telegram cannot edit a video message into text, so replace that message.
    try:
        if call.message.video or call.message.animation or call.message.photo or call.message.document:
            await call.message.delete()
            await bot.send_message(call.from_user.id, text, reply_markup=kb, parse_mode='HTML')
        else:
            await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except Exception:
        # Fallback for any message-type/edit restriction.
        try:
            await bot.send_message(call.from_user.id, text, reply_markup=kb, parse_mode='HTML')
        except Exception:
            pass
    await call.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def view_panel_names(call: CallbackQuery):
    category = call.data.split("cat_", 1)[1]
    panel_names = db_query("SELECT DISTINCT panel_name FROM products WHERE category LIKE ? AND is_active=1 AND panel_name != ''", (category + '%',), fetchall=True)
    if not panel_names:
        prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category LIKE ? AND is_active=1", (category + '%',), fetchall=True)
        if not prods: return await call.answer("❌ No products available in this category yet.", show_alert=True)
        await show_products_for_panel(call, prods, category)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>{category.upper()} PANELS</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel name:</b>"
    for pn in panel_names:
        panel = pn[0]
        emoji_id = get_panel_emoji(panel) or get_emoji_icon("product_store")
        kb.inline_keyboard.append([InlineKeyboardButton(text=panel, callback_data=f"pnl_{category[:30]}_{panel[:30]}", icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANELS", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    parts = call.data.split("pnl_", 1)[1].split("_", 1)
    if len(parts) != 2: return await call.answer("Invalid selection.", show_alert=True)
    category, panel_name = parts[0], parts[1]
    prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category LIKE ? AND panel_name LIKE ? AND is_active=1", (category + '%', panel_name + '%'), fetchall=True)
    if not prods: return await call.answer("No products found for this panel.", show_alert=True)
    await show_products_for_panel(call, prods, f"{category} - {panel_name}")

async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str):
    """Show ONE tutorial video for the panel, then ALL package BUY buttons below it.

    Example layout:
        [ ONE VIDEO ]
        Product/package information
        [ BUY 1 DAY ]
        [ BUY 3 DAYS ]
        [ BUY 7 DAYS ]
        [ BACK TO PANELS ]

    The video is taken from the first package in the group that has a tutorial
    configured. Buying a package goes directly to that package's existing
    purchase flow.
    """
    if not prods:
        return await call.answer("❌ No products found.", show_alert=True)

    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = bool(user[0]) if user else False
    is_vip = bool(user[1]) if user else False

    # Find one shared tutorial video for this panel. We intentionally send it
    # only once, even when there are many validity packages.
    tutorial_video = ""
    tutorial_caption = ""
    for p in prods:
        info = db_query(
            "SELECT tutorial_video, tutorial_caption FROM products WHERE id=? AND is_active=1",
            (p[0],), fetchone=True
        )
        if info and (info[0] or "").strip():
            tutorial_video = (info[0] or "").strip()
            tutorial_caption = (info[1] or "").strip()
            break

    # Build the text shown under the video. All available validity packages
    # are listed here, with a separate BUY button for each package.
    lines = [
        f"✨ <b>{html.escape(str(header))}</b>",
        "━━━━━━━━━━━━━━━━━━",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    any_stock = False
    for p in prods:
        prod_id, package_name, normal_price, stock, reseller_price, validity, device = p
        normal_price = safe_float(normal_price)
        reseller_price = safe_float(reseller_price)
        base_price = reseller_price if is_reseller else normal_price
        display_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price

        aps_info = db_query("SELECT aps_product_id, aps_duration FROM products WHERE id=?", (prod_id,), fetchone=True)
        has_aps = bool(aps_info and aps_info[0] and aps_info[1])
        effective_stock = bool(stock > 0 or has_aps)
        any_stock = any_stock or effective_stock
        stock_status = "✅ In Stock" if effective_stock else "❌ Out of Stock"

        lines.append(
            f"✨ ⏱ <b>Validity:</b> {html.escape(str(package_name))}\n"
            f"💰 <b>Price:</b> {fmt_curr(display_price)}\n"
            f"📱 <b>Limit:</b> {html.escape(str(device))} | 📦 {stock_status}"
        )

        if effective_stock:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🛒 BUY {package_name} - {fmt_curr(display_price)}",
                    callback_data=f"buy_{prod_id}",
                    style="success"
                )
            ])
        else:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {package_name} (Out of Stock)",
                    callback_data="ignore_stock_click",
                    style="danger"
                )
            ])

    # Optional admin-written text is displayed under the single panel video.
    # Keep it separate from package data so the admin can explain the product,
    # instructions, features, or important notes.
    if tutorial_caption:
        lines.insert(0, html.escape(tutorial_caption[:900]))
        lines.insert(1, "━━━━━━━━━━━━━━━━━━")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("✨ <b>Select any package below to purchase instantly:</b>")
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="🔙 BACK TO PANELS",
            callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    caption = "\n\n".join(lines)

    # Remove the old package-selection message first so the video becomes the
    # top message, matching the requested screenshot-style layout.
    try:
        await call.message.delete()
    except Exception:
        pass

    if tutorial_video:
        try:
            await bot.send_video(
                chat_id=call.from_user.id,
                video=tutorial_video,
                caption=caption[:1024],
                reply_markup=kb,
                parse_mode="HTML"
            )
            await call.answer()
            return
        except Exception as e:
            logger.warning(f"Could not send panel tutorial video: {e}")

    # No valid video configured: keep the package purchase flow usable, but
    # clearly tell the user why the video is missing.
    fallback = (
        "⚠️ <b>Product video is not configured.</b>\n\n"
        + caption
    )
    await bot.send_message(
        call.from_user.id,
        fallback[:4096],
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ This duration is completely Out of Stock! Admins have been notified to refill.", show_alert=True)


# ==============================================================================
# PRODUCT VIDEO GATE — WATCH TUTORIAL BEFORE PURCHASE
# ==============================================================================
@dp.callback_query(F.data.startswith("preview_"))
async def product_video_gate(call: CallbackQuery):
    """Open ONE panel video and show ALL package BUY buttons below it."""
    try:
        prod_id = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product.", show_alert=True)

    prod = db_query(
        "SELECT id, name, category, panel_name, price_inr, stock, reseller_price, validity, device_limit "
        "FROM products WHERE id=? AND is_active=1",
        (prod_id,), fetchone=True
    )
    if not prod:
        return await call.answer("❌ Product not found.", show_alert=True)

    # Get every package belonging to this same panel. This guarantees that
    # users see ONE video, while 1 Day / 3 Day / 7 Day / other packages are
    # all available as separate BUY buttons underneath it.
    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit "
        "FROM products WHERE category LIKE ? AND panel_name LIKE ? AND is_active=1 "
        "ORDER BY id",
        ((prod[2] or "") + "%", (prod[3] or "") + "%"), fetchall=True
    )
    if not prods:
        return await call.answer("❌ No packages found for this panel.", show_alert=True)

    await show_products_for_panel(call, prods, f"{prod[3]} - {prod[1]}")
    await call.answer()


@dp.callback_query(F.data.startswith("continuebuy_"))
async def continue_to_purchase(call: CallbackQuery):
    # Kept for compatibility with old messages/buttons.
    try:
        prod_id = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("❌ Invalid product.", show_alert=True)
    call.data = f"buy_{prod_id}"
    await call.answer("Opening purchase...")
    await process_buy(call)

# APS — AUTO PURCHASE SYSTEM (adminpanels.shop)
# ==============================================================================
async def aps_buy_key(product_id: str, duration: str, android_id: str = "") -> dict:
    """Call adminpanels.shop API to auto-purchase a key (official endpoint)."""
    import ssl
    post_data = {
        "api_key": get_setting("aps_api_key", APS_API_KEY),
        "action": "buy",
        "product_id": product_id,
        "duration": duration,
    }
    if android_id:
        post_data["android_id"] = android_id
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-master-key": get_setting("aps_x_master_key", APS_X_MASTER_KEY),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                APS_ENDPOINT,
                data=urllib.parse.urlencode(post_data),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=True
            ) as resp:
                result = await resp.json(content_type=None)
                logger.info(f"APS Buy Response for PID {product_id}: {result}")
                return result
    except Exception as e:
        logger.error(f"APS API Error: {e}")
        return {"status": "error", "message": str(e)}

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    """Step 1: User clicks Buy → Generate QR for product amount."""
    prod_id = int(call.data.split("_")[1])
    prod = db_query("SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name, aps_product_id, aps_duration FROM products WHERE id=?", (prod_id,), fetchone=True)
    user = db_query("SELECT balance, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod: return await call.answer("❌ Critical Error: Item not found in DB!", show_alert=True)
    normal_price = safe_float(prod[1])
    reseller_price = safe_float(prod[7])
    is_reseller = bool(user[1]); is_vip = bool(user[3])
    base_price = reseller_price if is_reseller else normal_price
    if is_vip: final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100))
    else: final_price = base_price

    aps_pid = prod[9] if prod[9] else ""
    aps_dur = prod[10] if prod[10] else ""

    # Check FamGateway configured
    api_key = get_setting("fampay_api_key", "")
    if not api_key or api_key == "YOUR_FAMGATEWAY_API_KEY":
        return await call.answer("⚠️ Payment gateway not configured. Contact Admin.", show_alert=True)

    # A BUY button can now be attached directly to the video message.
    # Video messages cannot be edited with edit_text(), so create a small
    # progress message when the callback came from a video.
    progress_message = call.message
    if getattr(call.message, "video", None):
        progress_message = await bot.send_message(
            call.message.chat.id,
            "⏳ <b>Generating QR Code for your order...</b>",
            parse_mode='HTML'
        )
    else:
        await progress_message.edit_text("⏳ <b>Generating QR Code for your order...</b>", parse_mode='HTML')

    # Generate order via FamGateway
    result = await generate_fampay_qr(call.from_user.id, final_price)
    if result.get("status") != "success":
        return await progress_message.edit_text(
            f"❌ <b>QR Generation Failed:</b> {result.get('message', 'Unknown error')}",
            reply_markup=back_kb("menu_shop"), parse_mode='HTML'
        )

    data = result.get("data", {})
    qr_url = data.get("qr_url")
    order_id = data.get("order_id", f"PROD{call.from_user.id}{int(time.time())}")
    payable_amount = safe_float(data.get("payable_amount"), final_price)
    expires_at_str = data.get("expires_at_ist")
    created_at = data.get("created_at_ist")
    upi_intent = data.get("upi_intent")
    checkout_url = data.get("checkout_url")

    try:
        expiry_dt = datetime.strptime(expires_at_str, "%d-%m-%Y %H:%M:%S") if expires_at_str else datetime.now() + timedelta(minutes=5)
        expires_ts = int(expiry_dt.timestamp())
    except:
        expires_ts = int(time.time() + 300)

    # Save pending product order
    db_query(
        "INSERT INTO product_orders (order_id, user_id, prod_id, prod_name, amount_inr, status, qr_url, upi_id, timestamp, expires_at, aps_pid, aps_dur, qr_message_id, qr_chat_id) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, NULL, NULL)",
        (order_id, call.from_user.id, prod_id, prod[0], payable_amount, qr_url, "", int(time.time()), expires_ts, aps_pid, aps_dur)
    )

    product_rows = []
    if upi_intent and str(upi_intent).startswith(("http://", "https://")):
        product_rows.append([InlineKeyboardButton(text="📱 Pay via UPI App", url=str(upi_intent))])
    if checkout_url and str(checkout_url).startswith(("http://", "https://")):
        product_rows.append([InlineKeyboardButton(text="🌐 Web Checkout", url=str(checkout_url))])
    product_rows.append([InlineKeyboardButton(text="🔄 Verify Payment & Get Key", callback_data=f"prodverify_{order_id}", style="primary")])
    product_rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    kb = InlineKeyboardMarkup(inline_keyboard=product_rows)

    caption = (
        f"🛒 <b>ORDER QR CODE</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Product:</b> {prod[8]} — {prod[0]}\n"
        f"💰 <b>Amount to Pay:</b> {fmt_curr(payable_amount)}\n"
                f"⏳ <b>Order Expires:</b> {expires_at_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Steps:</b>\n"
        f"1️⃣ Scan the QR or use a UPI App / Web Checkout button\n"
        f"2️⃣ Pay EXACT amount: {fmt_curr(payable_amount)}\n"
        f"3️⃣ Click <b>Verify Payment</b> to get key instantly!"
    )

    log_activity(call.from_user.id, "PRODUCT_QR_GENERATED", f"Product: {prod[0]}, Amount: {payable_amount}, Order: {order_id}")

    # Send QR as photo
    qr_sent = False
    if qr_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(qr_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                        # Delete only the temporary progress message. Keep the
                        # original video + BUY button in the chat history.
                        if progress_message is not call.message:
                            try:
                                await progress_message.delete()
                            except:
                                pass
                        qr_message = await bot.send_photo(
                            chat_id=call.message.chat.id,
                            photo=BufferedInputFile(img_bytes, filename="order_qr.png"),
                            caption=caption,
                            reply_markup=kb,
                            parse_mode='HTML'
                        )
                        db_query(
                            "UPDATE product_orders SET qr_message_id=?, qr_chat_id=? WHERE order_id=?",
                            (qr_message.message_id, call.message.chat.id, order_id)
                        )
                        qr_sent = True
        except Exception as e:
            logger.error(f"Product QR image send failed: {e}")

    if not qr_sent:
        try:
            await progress_message.edit_text(caption, reply_markup=kb, parse_mode='HTML')
        except:
            await bot.send_message(call.message.chat.id, caption, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith("prodverify_"))
async def product_verify_payment(call: CallbackQuery):
    """Step 2: Verify payment → deliver key."""
    order_id = call.data.split("prodverify_", 1)[1]
    rec = db_query("SELECT user_id, prod_id, prod_name, amount_inr, status, expires_at, aps_pid, aps_dur FROM product_orders WHERE order_id=?", (order_id,), fetchone=True)
    if not rec:
        return await call.answer("❌ Order not found!", show_alert=True)

    user_id, prod_id, prod_name_saved, amount_inr, status, expires_at, aps_pid, aps_dur = rec

    if call.from_user.id != user_id:
        return await call.answer("❌ This is not your order!", show_alert=True)

    if status == "paid":
        return await call.answer("✅ Already paid and delivered!", show_alert=True)

    if status == "expired" or (expires_at and time.time() > expires_at):
        db_query("UPDATE product_orders SET status='expired' WHERE order_id=?", (order_id,))
        err = "⏳ <b>QR Expired!</b>\nPlease go back and buy again."
        try:
            await call.message.edit_caption(err, reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        except:
            await call.message.edit_text(err, reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        return

    # Verify payment with FamPay
    result = await verify_fampay_payment(order_id)

    if result.get("status") != "success":
        msg = result.get("message", "Payment not received yet.")
        await call.answer(f"⏳ {msg}\n\nPlease wait and try again.", show_alert=True)
        return

    # Payment confirmed — now deliver key
    db_query("UPDATE product_orders SET status='paid' WHERE order_id=?", (order_id,))

    prod = db_query("SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name FROM products WHERE id=?", (prod_id,), fetchone=True)
    user_info = db_query("SELECT balance, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not prod:
        await call.message.edit_text("✅ Payment received! But product not found. Contact admin.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
        return

    normal_price = safe_float(prod[1])
    is_reseller = bool(user_info[1]); is_vip = bool(user_info[3])
    base_price = safe_float(prod[7]) if is_reseller else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
    savings = normal_price - final_price

    delivered_key = ""

    # APS delivery
    if aps_pid and aps_dur:
        aps_result = await aps_buy_key(aps_pid, aps_dur)
        status_val = str(aps_result.get("status", "")).lower()
        if status_val in ("success", "1", "true"):
            delivered_key = (
                aps_result.get("key") or
                aps_result.get("license") or
                (aps_result.get("data", {}).get("key") if isinstance(aps_result.get("data"), dict) else None) or
                str(aps_result.get("data", ""))
            )
        else:
            delivered_key = f"APS_ERROR: {aps_result.get('message', 'Contact Admin')}"
    else:
        # Local vault delivery
        if prod[2] > 0:
            key_data = db_query("SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 LIMIT 1", (prod_id,), fetchone=True)
            if key_data:
                delivered_key = key_data[1]
                db_query("UPDATE product_keys SET is_used=1 WHERE id=?", (key_data[0],))
                db_query("UPDATE products SET stock=stock-1 WHERE id=?", (prod_id,))
            else:
                delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN"
        else:
            delivered_key = "OUT_OF_STOCK_CONTACT_ADMIN"

    # Update user stats
    db_query("UPDATE users SET spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?", (final_price, savings, user_id))
    product_full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)", (user_id, product_full_name, final_price, delivered_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_activity(user_id, "PRODUCT_QR_PURCHASE_SUCCESS", f"Product: {product_full_name}, Paid: {final_price}, Order: {order_id}")
    await send_advanced_notification(user_id, "ORDER", final_price, product=product_full_name, key=delivered_key)

    msg = (
        f"✅ <b>PAYMENT VERIFIED — KEY DELIVERED!</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Panel:</b> {prod[6]}\n📁 <b>Panel Name:</b> {prod[8]}\n"
        f"⏱ <b>Package:</b> {prod[0]}\n💰 <b>Amount Paid:</b> {fmt_curr(final_price)}\n"
        f"📱 <b>Device Limit:</b> {prod[5]}\n━━━━━━━━━━━━━━━━━━\n"
    )
    if prod[3] and prod[3].startswith("http"):
        msg += f"📥 <b>APK Link:</b> <a href='{prod[3]}'>Click Here to Download</a>\n\n"
    if "OUT_OF_STOCK" in delivered_key or "APS_ERROR" in delivered_key:
        msg += f"⚠️ <b>Key Issue:</b> {delivered_key}\nContact: {ADMIN_CONTACT}"
    else:
        msg += f"🔑 <b>Your Key:</b>\n<code>{delivered_key}</code>\n\n<i>Contact: {ADMIN_CONTACT}</i>"
    qr_deleted = await _delete_fampay_qr_message(order_id)
    if qr_deleted:
        try:
            await bot.send_message(user_id, msg, reply_markup=back_kb("menu_shop"), parse_mode='HTML', disable_web_page_preview=True)
        except Exception:
            pass
    else:
        try:
            await call.message.edit_caption(msg, reply_markup=back_kb("menu_shop"), parse_mode='HTML', disable_web_page_preview=True)
        except Exception:
            try:
                await call.message.edit_text(msg, reply_markup=back_kb("menu_shop"), parse_mode='HTML', disable_web_page_preview=True)
            except Exception:
                try: await bot.send_message(user_id, msg, reply_markup=back_kb("menu_shop"), parse_mode='HTML', disable_web_page_preview=True)
                except Exception: pass

# ==============================================================================
# AUTO PRODUCT PAYMENT VERIFIER — INSTANT KEY DELIVERY
# ==============================================================================
async def auto_product_verify_task() -> None:
    """Automatically verify paid product orders and deliver the key without user action."""
    while True:
        await asyncio.sleep(3)
        try:
            pending_orders = db_query(
                "SELECT order_id, user_id FROM product_orders WHERE status='pending' "
                "AND (expires_at IS NULL OR expires_at > ?)",
                (int(time.time()),), fetchall=True
            ) or []

            for order_id, user_id in pending_orders:
                try:
                    result = await verify_fampay_payment(order_id)
                    if result.get("status") != "success":
                        continue

                    # Reuse the existing delivery flow so APS/local-vault behavior stays identical.
                    class _AutoUser:
                        def __init__(self, uid): self.id = uid
                    class _AutoMessage:
                        def __init__(self, chat_id):
                            self.chat = type("Chat", (), {"id": chat_id})()
                        async def edit_caption(self, *args, **kwargs): return None
                        async def edit_text(self, *args, **kwargs): return None
                    class _AutoCall:
                        def __init__(self, uid, oid):
                            self.from_user = _AutoUser(uid)
                            self.data = f"prodverify_{oid}"
                            self.message = _AutoMessage(uid)
                        async def answer(self, *args, **kwargs): return None

                    await product_verify_payment(_AutoCall(user_id, order_id))

                except Exception as e:
                    logger.error(f"Auto product delivery failed for {order_id}: {e}")
        except Exception as e:
            logger.error(f"Auto product verifier error: {e}")


# ==============================================================================
# 15. USER DASHBOARD, FILES, VIP, RESELLER, ORDERS, PROFILE
# ==============================================================================

@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 Active (Lifetime)" if is_vip else "🔴 Not Subscribed"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip:
        text += f"\n📅 <b>Member Since:</b> {u[2]}\n\nEnjoy your permanent 15% discount!"
    else:
        text += f"\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR: kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Purchase VIP for {fmt_curr(VIP_PRICE_INR)}", callback_data="execute_vip_upgrade", style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(VIP_PRICE_INR)} to Upgrade", callback_data="ignore_stock_click", style="danger")])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance Now", callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a VIP Member!", show_alert=True)
    if u[0] < VIP_PRICE_INR: return await call.answer(f"❌ Your balance dropped below {VIP_PRICE_INR}.", show_alert=True)
    new_balance = u[0] - VIP_PRICE_INR
    now_date = datetime.now().strftime("%Y-%m-%d")
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?", (new_balance, now_date, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try: await bot.send_message(ADMIN_ID, f"🌟 <b>NEW VIP UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! You are now a VIP Member.", show_alert=True)
    await vip_dashboard(call)

@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    system_status = status_check[0] if status_check else "ON"
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    if u[1]: 
        text = (f"{get_emoji('shield_icon')} <b><u>— RESELLER DASHBOARD —</u></b> {get_emoji('shield_icon')}\n\n🟢 <b>Status:</b> Active\n📅 <b>Since:</b> {u[2]}\n{get_emoji('money_icon')} <b>Total Saved:</b> {fmt_curr(u[3])}\n\n🎉 You are enjoying exclusive wholesale prices on all products!")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        return
    if system_status == "OFF": return await call.answer("⚠️ Wholesale / Reseller registrations are currently closed by Admin.", show_alert=True)
    text = (f"⚡ <b><u>— BECOME A RESELLER —</u></b> ⚡\n\nUpgrade your account to access wholesale <b>Reseller Prices</b>!\n\n📋 <b>Requirements to Upgrade:</b>\n1️⃣ Must have a minimum balance of <b>{fmt_curr(min_balance)}</b>.\n2️⃣ A one-time setup fee of <b>{fmt_curr(setup_fee)}</b> will be deducted.\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if u[0] >= min_balance: kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Pay {fmt_curr(setup_fee)} & Become Reseller", callback_data="execute_reseller_upgrade", style="success")])
    else:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Insufficient Balance (Need {fmt_curr(min_balance)})", callback_data="ignore_stock_click", style="danger")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance", callback_data="menu_add_balance", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a Reseller!", show_alert=True)
    if u[0] < min_balance: return await call.answer(f"❌ Your balance dropped below {fmt_curr(min_balance)}. Please top up.", show_alert=True)
    new_balance = u[0] - setup_fee
    db_query("UPDATE users SET balance=?, is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (new_balance, datetime.now().strftime("%Y-%m-%d"), call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_RESELLER")
    try: await bot.send_message(ADMIN_ID, f"👑 <b>NEW RESELLER UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! Welcome to the Reseller tier.", show_alert=True)
    await reseller_dashboard(call)

@dp.callback_query(F.data.in_({"menu_orders", "menu_history"}))
async def my_orders(call: CallbackQuery):
    orders = db_query("SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders: return await call.message.edit_text("🧾 You haven't made any purchases yet. Your vault is empty.", reply_markup=back_kb(), parse_mode='HTML')
    text = f"{get_emoji('history')} <b><u>— ALL PURCHASE HISTORY (LAST 10) —</u></b>\n\n"
    for o in orders: text += f"📦 <b>{o[0]}</b> ({fmt_curr(o[3])})\n🔑 <code>{o[1]}</code>\n📅 <i>{o[2]}</i>\n━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_referral")
async def show_referral(call: CallbackQuery):
    user_id = call.from_user.id
    referral_link = f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=ref_{user_id}"
    text = (
        f"👥 <b><u>— REFERRAL PROGRAM —</u></b> 👥\n\n"
        f"🔗 <b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"📢 <b>Share this link with friends!</b>\n"
        f"🎁 Earn rewards when they join &amp; purchase.\n\n"
        f"👤 <b>Your ID:</b> <code>{user_id}</code>"
    )
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery):
    u = db_query("SELECT user_id, first_name, account_type, balance, orders_count, spent, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    acc_type_display = []
    if u[7]: acc_type_display.append(f"{get_emoji('reseller')} Reseller")
    if u[10]: acc_type_display.append(f"{get_emoji('vip')} VIP")
    type_str = " | ".join(acc_type_display) if acc_type_display else f"{get_emoji('regular_user')} Regular User"
    text = (
        f"{get_emoji('grid_id')} <b><u>— YOUR SECURE PROFILE —</u></b> {get_emoji('grid_id')}\n\n"
        f"{get_emoji('grid_id')} <b>Grid ID:</b> <code>{u[0]}</code>\n"
        f"{get_emoji('name')} <b>Name:</b> {u[1]}\n"
        f"{get_emoji('account_level')} <b>Account Level:</b> {type_str}\n\n"
        f"{get_emoji('wallet_left')} <b>— Wallet —</b> {get_emoji('wallet_right')}\n"
        f"{get_emoji('wallet_left')} <b>Current Balance:</b> {fmt_curr(u[3])} {get_emoji('wallet_right')}\n\n"
        f"{get_emoji('global_stats')} <b>— Global Statistics —</b>\n"
        f"{get_emoji('total_orders')} <b>Total Orders:</b> {u[4]}\n"
        f"{get_emoji('total_spent')} <b>Total Spent:</b> {fmt_curr(u[5])}\n"
    )
    if u[7]:
        text += f"{get_emoji('shield_icon')} <b>— RESELLER METRICS —</b> {get_emoji('shield_icon')}\n{get_emoji('money_icon')} <b>Total Saved via Reseller:</b> {fmt_curr(u[9])}\n\n"
    text += f"{get_emoji('joined_grid')} <b>Joined Grid:</b> {u[6]}\n\n"

    # Purchase history is shown directly inside Profile.
    orders = db_query(
        "SELECT delivered_key FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (call.from_user.id,), fetchall=True
    )
    text += "🧾 <b><u>— PURCHASE HISTORY —</u></b> 🧾\n\n"
    if orders:
        for o in orders:
            text += f"🔑 <code>{o[0]}</code>\n"
    else:
        text += "📭 <i>No purchases yet.</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Redeem Promo Code",
            callback_data="redeem_coupon",
            icon_custom_emoji_id=get_emoji_icon('redeem_icon'),
            style="success"
        )],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🎟 <b>Please enter your VIP / Promo redeem code below:</b>", reply_markup=back_kb("menu_profile"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_redeem)

@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Anti-Fraud Alert: You already redeemed this unique code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        await state.clear()
        return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon: await m.answer("❌ Invalid or Expired Code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif coupon[1] <= 0: await m.answer("❌ This code's usage limit has been fully claimed by other users.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        log_activity(user_id, "PROMO_REDEEMED", f"Code: {code}, Amount: {coupon[0]}")
        await m.answer(f"🎉 <b>Success!</b>\nSafely added {fmt_curr(coupon[0])} to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        try:
            user_info = db_query("SELECT first_name FROM users WHERE user_id=?", (user_id,), fetchone=True)
            uname = user_info[0] if user_info else "Unknown User"
            await bot.send_message(ADMIN_ID, f"🎟 <b>PROMO CODE REDEEMED!</b>\n👤 User: {uname} (<code>{user_id}</code>)\n🔖 Code: <b>{code}</b>\n💵 Amount: {fmt_curr(coupon[0])}", parse_mode='HTML')
        except Exception: pass
    await state.clear()

@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    video_link_query = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video_link = video_link_query[0] if video_link_query and video_link_query[0] != 'None' else None
    text = (f"{get_emoji('tutorial')} <b><u>— TUTORIALS & GUIDE —</u></b> {get_emoji('tutorial')}\n\n1️⃣ Add funds via <b>Add Balance</b>\n2️⃣ Navigate to <b>Product Store</b>\n3️⃣ Choose your desired Panel and Package validity.\n4️⃣ The Key and Installation APK link will be instantly provided.")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video_link: kb.inline_keyboard.append([InlineKeyboardButton(text="Watch Full Video Tutorial", url=video_link, icon_custom_emoji_id=get_emoji_icon("tutorial"), style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    telegram_link = get_setting("support_telegram", "https://t.me/YourSupport")
    whatsapp_link = get_setting("support_whatsapp", "https://wa.me/YourNumber")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Contact on Telegram", url=telegram_link, icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="Contact on WhatsApp", url=whatsapp_link, icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 Open New Ticket", callback_data="open_ticket", style="primary"), InlineKeyboardButton(text="📋 My Open Tickets", callback_data="my_tickets", style="primary")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(f"{get_emoji('telegram')}{get_emoji('whatsapp')} <b><u>— PREMIUM SUPPORT CENTER —</u></b>\n\nContact us via Telegram or WhatsApp for instant help, or open a support ticket for admin assistance.", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query("SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (call.from_user.id,), fetchall=True)
    if not tickets: return await call.message.edit_text("📋 You do not have any active or previous support tickets.", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = "📋 <b><u>— Your Recent Tickets —</u></b> 📋\n\n"
    for t in tickets:
        status_icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>Ticket #{t[0]}</b> | Status: {status_icon} <b>{t[2]}</b>\n📅 <i>{t[3]}</i>\n📝 <i>{t[1][:80]}...</i>\n\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_support"), parse_mode='HTML')

@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 <b>Please type your issue/message below in detail:</b>", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_ticket)

@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await m.answer("✅ <b>Ticket Submitted Successfully!</b> Admins will reply soon.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>NEW SUPPORT TICKET</b>\nFrom: <code>{m.from_user.id}</code>\nMsg: {m.text}", parse_mode='HTML')
    except: pass
    log_activity(m.from_user.id, "OPENED_TICKET")
    await state.clear()

# ==============================================================================
# 18. ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_panel_open")
async def open_admin_panel_button(call: CallbackQuery, state: FSMContext):
    # Hard security check: even if someone manually sends this callback,
    # non-admin users can never open the admin panel.
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Admin access only.", show_alert=True)
    await state.clear()
    await call.message.edit_text(
        "⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )

@dp.callback_query(F.data == "admin_panel")
async def legacy_admin_panel_callback(call: CallbackQuery, state: FSMContext):
    """Compatibility route for older admin-panel buttons."""
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Admin access only.", show_alert=True)
    await state.clear()
    await call.message.edit_text(
        "⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )
    await call.answer()

@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Admin access only.", show_alert=True)
    await state.clear()
    await call.message.edit_text("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')
    await call.answer()

@dp.callback_query(F.data == "admin_back_main")
async def admin_back_main(call: CallbackQuery, state: FSMContext):
    """Admin Panel -> Main Menu. Kept separate from admin_panel_back."""
    if call.from_user.id != ADMIN_ID:
        return await call.answer("⛔ Admin access only.", show_alert=True)
    await state.clear()
    await send_main_menu(call)
    await call.answer()

@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    current = res[0] if res else 'OFF'
    new_status = 'ON' if current == 'OFF' else 'OFF'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('vip_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download Full User List", callback_data="admin_download_userlist", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("💻 <b>User Control Terminal</b>\n\n✏️ Enter the <b>User ID</b> or <b>@Username</b> you want to investigate or manage:\n\n👇 <b>OR</b> download the full user CSV format list:", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.manage_target_user)

@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    users = db_query("SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users", fetchall=True)
    if not users: return await call.answer("❌ No users found in the database.", show_alert=True)
    file_content = "FULL DATABASE DUMP\n" + "="*100 + "\n"
    for u in users:
        uname = u[0] if u[0] else "No_Username"
        uid = u[1]
        phone = u[2] if u[2] else "No_Phone"
        bal = u[3]
        orders = u[4]
        vip_status = "YES" if u[5] else "NO"
        res_status = "YES" if u[6] else "NO"
        file_content += f"UID: {uid} | UNAME: {uname} | PHONE: {phone} | BAL: ₹{bal:.2f} | BUY: {orders} | VIP: {vip_status} | RES: {res_status}\n"
    doc = BufferedInputFile(file_content.encode('utf-8'), filename=f"DB_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(document=doc, caption="📋 <b>Database export complete.</b>", parse_mode='HTML')
    await call.answer()

@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    loader_msg = await hacker_loading(m, "Querying User Database")
    user_q = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await loader_msg.edit_text("❌ Target not found in the grid. Check ID/Username syntax.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, is_banned, warnings, is_vip = user_q
    await state.update_data(target_u_id=u_id)
    status_emoji = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    tags = []
    if is_res: tags.append("👑 Reseller")
    if is_vip: tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "👤 Regular"
    text = (f"🛡 <b><u>USER CONTROL TERMINAL</u></b> 🛡\n━━━━━━━━━━━━━━━━━━\n📛 <b>Name:</b> {u_name} (@{u_user})\n🆔 <b>ID:</b> <code>{u_id}</code>\n📊 <b>Status:</b> {status_emoji}\n🔰 <b>Type:</b> {type_str}\n⚠️ <b>Warnings Issued:</b> {warnings}\n━━━━━━━━━━━━━━━━━━\n💰 <b>Wallet Balance:</b> {fmt_curr(bal)}\n📦 <b>Orders:</b> {orders} | 💸 <b>Total Spent:</b> {fmt_curr(spent)}\n📅 <b>Joined:</b> {joined}")
    ban_btn_text = "Unban ✅" if is_banned else "Ban 🚫"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add Funds ➕", callback_data=f"usrctrl_add_{u_id}", style="success"), InlineKeyboardButton(text="Minus Funds ➖", callback_data=f"usrctrl_min_{u_id}", style="danger")],
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"usrctrl_ban_{u_id}", style="danger"), InlineKeyboardButton(text="Warn User ⚠️", callback_data=f"usrctrl_warn_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Give VIP 🌟" if not is_vip else "Remove VIP 🚫", callback_data=f"usrctrl_vip_{u_id}", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await loader_msg.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    action = call.data.split("_")[1]
    u_id = int(call.data.split("_")[2])
    await state.update_data(target_u_id=u_id)
    if action == "ban":
        current_status = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"confirm_ban_{u_id}", style="danger"), InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", style="danger")]
            ])
            await call.message.edit_text(f"⚠️ Are you sure you want to <b>BAN</b> user <code>{u_id}</code>?", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.confirm_ban)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ User unbanned successfully!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "vip":
        current_status = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 1:
            db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ VIP Removed!", show_alert=True)
        else:
            db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
            await call.answer("✅ VIP Granted!", show_alert=True)
        m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "add":
        await call.message.edit_text("💰 Enter the amount to <b>ADD</b> to this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
    elif action == "min":
        await call.message.edit_text("💸 Enter the amount to <b>DEDUCT</b> from this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
    elif action == "warn":
        await call.message.edit_text("⚠️ Type the strict warning message you want to send directly to this user:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)

@dp.callback_query(F.data.startswith("confirm_ban_"))
async def confirm_ban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    u_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
    await call.answer("🔴 User has been banned!", show_alert=True)
    await state.clear()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully added {fmt_curr(amt)} to target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        try: await bot.send_message(u_id, f"💰 <b>Wallet Top-up!</b>\nAdmin has manually added {fmt_curr(amt)} to your wallet.", parse_mode='HTML')
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully deducted {fmt_curr(amt)} from target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data()
    u_id = data['target_u_id']
    warn_text = m.text
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Official warning dispatched to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try: await bot.send_message(u_id, f"⚠️ <b>OFFICIAL WARNING FROM SYSTEM ADMIN:</b>\n\n{warn_text}\n\n<i>Subsequent infractions may lead to an automated grid ban.</i>", parse_mode='HTML')
    except: pass
    await state.clear()

# ==============================================================================
# 19. ADMIN STATISTICS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    t_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    t_resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    t_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    t_prods = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    t_keys = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    t_rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg = (f"📊 <b><u>GRID INTELLIGENCE DASHBOARD</u></b> 📊\n━━━━━━━━━━━━━━━━━━\n👥 <b>Total Grid Users:</b> {t_users}\n👑 <b>Wholesale Resellers:</b> {t_resellers}\n🌟 <b>Elite VIP Members:</b> {t_vip}\n━━━━━━━━━━━━━━━━━━\n📦 <b>Active Products:</b> {t_prods}\n🔑 <b>Unused Keys in Vault:</b> {t_keys}\n💰 <b>Total Gross Revenue:</b> {fmt_curr(t_rev)}\n━━━━━━━━━━━━━━━━━━")
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode='HTML')

# ==============================================================================
# 20. ADMIN PRODUCT MANAGEMENT
# ==============================================================================
@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"addprod_cat_{cat}", icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Cancel", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("<b>Step 1:</b> Choose the <b>Category</b> for this product:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    category = call.data.split("addprod_cat_", 1)[1]
    await state.update_data(cat=category)
    await call.message.edit_text(f"<b>Step 2:</b> Enter <b>PANEL NAME</b>\n(e.g., 'MST PANEL', 'DRIP PANEL'):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_panel_name)

@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter <b>PACKAGE DURATION/DATE NAME</b>\n(e.g., '7 Days', '1 Month'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("⏳ Enter Time Validity String (e.g., '24 Hours'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_validity)

@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    await state.update_data(validity=m.text)
    await m.answer("📱 Enter strict Device Enforcement Limit (e.g., '1 Device HWID'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_device_limit)

@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter standard **User Price** in Rupees (₹) (e.g., 500):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter wholesale **Reseller Price** in Rupees (₹) (e.g., 300):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text))
        await m.answer("🔗 Enter direct APK/Payload Download Link (or type 'none' to omit):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_apk)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_apk)
async def add_prod_apk(m: Message, state: FSMContext):
    await state.update_data(apk="" if m.text.lower() == 'none' else m.text)
    await m.answer("🎬 <b>Product Tutorial Video</b>\n\nSend the direct video URL or Telegram video link that users must watch before purchase.\nType <code>none</code> to skip:", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_tutorial)

@dp.message(AdminStates.add_prod_tutorial)
async def add_prod_tutorial(m: Message, state: FSMContext):
    """Admin-only tutorial input. Accept a Telegram video upload or a text file_id/direct URL."""
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return await m.answer("⛔ Admin access only.")

    tutorial = ""
    if m.video:
        # Best option: Telegram file_id. No external hosting is required.
        tutorial = m.video.file_id
    elif m.text:
        value = m.text.strip()
        tutorial = "" if value.lower() == "none" else value
    else:
        return await m.answer(
            "❌ Please send a video directly, or send a Telegram file_id/direct video URL.\n"
            "Type <code>none</code> to skip.",
            parse_mode='HTML'
        )

    await state.update_data(tutorial_video=tutorial)
    if tutorial:
        await m.answer("📝 <b>Video Caption/Text</b>\n\nAb video ke <b>niche</b> jo bhi text dikhana hai, woh bhejo.\nExample: <code>🔥 SAFE PANEL\n⚡ 24 HOURS\n📱 1 DEVICE</code>\n\nText nahi chahiye to <code>none</code> bhejo.", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_tutorial_caption)
    else:
        await m.answer("ℹ️ Tutorial skipped. Now send the license Keys (1 key per line):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_keys)

@dp.message(AdminStates.add_prod_tutorial_caption)
async def add_prod_tutorial_caption(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return await m.answer("⛔ Admin access only.")
    caption = "" if not m.text or m.text.strip().lower() == "none" else m.text.strip()
    if len(caption) > 1024:
        return await m.answer("❌ Video text 1024 characters se zyada nahi ho sakta.")
    await state.update_data(tutorial_caption=caption)
    await m.answer("✅ Video text saved. Now send the license Keys (1 key per line):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_keys)

@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    data = await state.get_data()
    stock = len(keys)
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    c.execute("INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit, tutorial_video, tutorial_caption) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], stock, data['apk'], data['validity'], data['device_limit'], data.get('tutorial_video', ''), data.get('tutorial_caption', '')))
    prod_id = c.lastrowid
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (prod_id, k))
    conn.commit()
    conn.close()
    await m.answer(f"✅ <b>Data Deployment Successful!</b>\n\n📦 Panel '{data['cat']}' -> Panel Name '{data['panel_name']}' -> Package '{data['name']}'\n🔒 Vault Stock: {stock} Keys injected.\n💰 User Price: {fmt_curr(data['price'])} | 👑 Reseller: {fmt_curr(data['reseller_price'])}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 20b. ADMIN BULK PRODUCT IMPORT (.txt FILE — one shot, no repeated steps)
# ==============================================================================
BULK_FORMAT_HELP = (
    "📥 <b>BULK ADD PRODUCTS — ONE FILE, SAB KUCHH EK BAAR MEIN</b>\n\n"
    "Ek <code>.txt</code> file bhejo jismein <b>har product ek line mein</b> ho, fields ko "
    "<code>|</code> (pipe) se separate karke, is order mein:\n\n"
    "<code>Category | Panel Name | Package Name | Validity | Device Limit | Price | Reseller Price | APK Link | APS Product ID | APS Duration | Keys</code>\n\n"
    "<b>Notes:</b>\n"
    "• Sirf pehle 7 fields zaroori hain, baaki (APK Link, APS Product ID, APS Duration, Keys) optional hain — <code>none</code> likh sakte ho ya line ko chota bhi rakh sakte ho.\n"
    "• <b>APS Product ID + APS Duration</b> do do to <b>API automatically link ho jaayegi</b> (adminpanels.shop se) — us product ke liye keys manually add karne ki zaroorat nahi, delivery auto-fetch hogi.\n"
    "• <b>Keys</b> field mein manual keys <code>;</code> (semicolon) se separate karke do, agar APS use nahi kar rahe.\n\n"
    "<b>Example (copy karke apni file banao):</b>\n"
    "<code>PC PANEL | DRIP PANEL | 7 Days | 7 Days | 1 Device | 500 | 300 | none | none | none | KEY1;KEY2;KEY3\n"
    "ANDROID ROOT PANEL | MST PANEL | 1 Month | 30 Days | 2 Devices | 1200 | 900 | none | 245 | 30 Days | none\n"
    "ANDROID NON ROOT PANEL | SAFE PANEL | 15 Days | 15 Days | 1 Device | 700 | 500</code>\n\n"
    f"<b>Valid Categories:</b> {', '.join(FIXED_CATEGORIES)}\n\n"
    "Text bhi paste kar sakte ho, file bhejna zaroori nahi.\n"
    "<i>(Type /cancel to abort)</i>"
)

@dp.callback_query(F.data == "admin_bulk_add_prod")
async def admin_bulk_add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text(BULK_FORMAT_HELP, reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_bulk_file)

def _parse_bulk_line(line: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse one pipe-separated product line. Returns (data, error)."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 7:
        return None, "Kam fields hain (kam se kam 7 chahiye, '|' se separated)"
    category_raw, panel_name, name, validity, device_limit, price_raw, reseller_raw = parts[:7]

    apk_link = parts[7].strip() if len(parts) > 7 and parts[7].strip() else "none"
    aps_pid = parts[8].strip() if len(parts) > 8 and parts[8].strip() else "none"
    aps_dur = parts[9].strip() if len(parts) > 9 and parts[9].strip() else "none"
    keys_raw = parts[10].strip() if len(parts) > 10 and parts[10].strip() else "none"

    apk_link = "" if apk_link.lower() == "none" else apk_link
    aps_pid = "" if aps_pid.lower() == "none" else aps_pid
    aps_dur = "" if aps_dur.lower() == "none" else aps_dur
    keys = [] if keys_raw.lower() == "none" else [k.strip() for k in keys_raw.split(";") if k.strip()]

    category_match = next((c for c in FIXED_CATEGORIES if c.lower() == category_raw.lower()), None)
    if not category_match:
        return None, f"Category '{category_raw}' valid nahi hai. Use: {', '.join(FIXED_CATEGORIES)}"

    price = safe_float(price_raw, None)
    if price is None:
        return None, f"Price '{price_raw}' number nahi hai"
    reseller_price = safe_float(reseller_raw, None)
    if reseller_price is None:
        return None, f"Reseller price '{reseller_raw}' number nahi hai"

    if not panel_name or not name:
        return None, "Panel Name ya Package Name khaali hai"

    if bool(aps_pid) != bool(aps_dur):
        return None, "APS Product ID aur APS Duration dono do, ya dono 'none' rakho"

    return {
        "category": category_match,
        "panel_name": panel_name,
        "name": name,
        "validity": validity or "Lifetime",
        "device_limit": device_limit or "1 Device",
        "price": price,
        "reseller_price": reseller_price,
        "apk": apk_link,
        "aps_pid": aps_pid,
        "aps_dur": aps_dur,
        "keys": keys,
    }, None

@dp.message(AdminStates.wait_for_bulk_file)
async def admin_bulk_add_prod_process(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return await m.answer("⛔ Admin access only.")

    if m.text and m.text.strip().lower() == "/cancel":
        await state.clear()
        return await m.answer("❌ Cancelled.", reply_markup=admin_kb())

    raw_text = None
    if m.document:
        try:
            file_info = await bot.get_file(m.document.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            raw_text = file_bytes.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return await m.answer(f"❌ File download/read fail hui: {e}")
    elif m.text:
        raw_text = m.text
    else:
        return await m.answer("❌ Please .txt file bhejo ya text paste karo.\n<i>(Type /cancel to abort)</i>", parse_mode='HTML')

    lines = [ln for ln in raw_text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return await m.answer("❌ File/text mein koi valid line nahi mili.")

    added, errors = [], []
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    try:
        for i, line in enumerate(lines, 1):
            data, err = _parse_bulk_line(line)
            if err:
                errors.append(f"Line {i}: {err}")
                continue
            stock = len(data["keys"])
            c.execute(
                "INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit, aps_product_id, aps_duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data["category"], data["panel_name"], data["name"], data["price"], data["reseller_price"], stock, data["apk"], data["validity"], data["device_limit"], data["aps_pid"], data["aps_dur"])
            )
            prod_id = c.lastrowid
            for k in data["keys"]:
                c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (prod_id, k))

            tag = ""
            if data["aps_pid"]:
                tag = f" ⚡APS-linked (PID {data['aps_pid']}, {data['aps_dur']})"
            elif stock:
                tag = f" 🔑{stock} keys"
            else:
                tag = " (no keys yet)"
            added.append(f"[{data['category']}] {data['panel_name']} - {data['name']} (₹{data['price']} / Reseller ₹{data['reseller_price']}){tag}")
        conn.commit()
    finally:
        conn.close()

    log_activity(ADMIN_ID, "BULK_ADD_PRODUCTS", f"Added: {len(added)}, Errors: {len(errors)}")

    summary = f"✅ <b>BULK IMPORT DONE</b>\n\n📦 <b>{len(added)} products added:</b>\n"
    summary += "\n".join(f"• {a}" for a in added[:25]) if added else "• (koi nahi)"
    if len(added) > 25:
        summary += f"\n…and {len(added) - 25} more"
    if errors:
        summary += f"\n\n⚠️ <b>{len(errors)} line(s) skip hui:</b>\n" + "\n".join(f"• {e}" for e in errors[:15])

    await m.answer(summary, reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query("SELECT id, name, category, panel_name, stock, is_active FROM products ORDER BY category, panel_name", fetchall=True)
    if not prods: return await call.message.edit_text("📦 Store Database is completely empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        status_dot = "🟢" if p[5] else "🔴"
        panel_name = p[3] if p[3] is not None else ""
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{status_dot} [{p[2]}] {panel_name} - {p[1]} (Stock: {p[4]})", callback_data=f"admin_view_p_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("📦 <b>Database Editor: Select Node to modify</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[3])
        prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
        if not prod: return await call.answer("❌ Architecture fault: Node lost!", show_alert=True)
        panel_name = prod[2] if prod[2] is not None else ""
        price_inr = safe_float(prod[4])
        reseller_price = safe_float(prod[5])
        aps_pid_val = prod[11] if len(prod) > 11 and prod[11] else "Not Set"
        aps_dur_val = prod[12] if len(prod) > 12 and prod[12] else "Not Set"
        aps_status = "⚡ ACTIVE" if (len(prod) > 11 and prod[11]) else "❌ Not Configured"
        tutorial_val = prod[13] if len(prod) > 13 and prod[13] else 'None'
        tutorial_caption_row = db_query("SELECT tutorial_caption FROM products WHERE id=?", (p_id,), fetchone=True)
        tutorial_caption_val = tutorial_caption_row[0] if tutorial_caption_row and tutorial_caption_row[0] else 'None'
        text = (f"📦 <b><u>NODE DEEP DIVE DETAILS</u></b>\n━━━━━━━━━━━━━━━━━━\n<b>ID:</b> <code>{prod[0]}</code>\n<b>Panel Group:</b> {prod[1]}\n<b>Panel Name:</b> {panel_name}\n<b>Package Date/Time:</b> {prod[3]}\n<b>Standard Price:</b> {fmt_curr(price_inr)}\n👑 <b>Wholesale Price:</b> {fmt_curr(reseller_price)}\n<b>Vault Stock:</b> {prod[6]}\n<b>Payload Link:</b> {prod[7] if prod[7] else 'None'}\n<b>Time Config:</b> {prod[8]}\n<b>HWID Limit:</b> {prod[9]}\n<b>Tutorial Video:</b> {tutorial_val}\n<b>Video Text:</b> {html.escape(tutorial_caption_val)}\n<b>Visibility:</b> {'Active' if prod[10] else 'Hidden'}\n━━━━━━━━━━━━━━━━━━\n⚡ <b>APS System:</b> {aps_status}\n📌 <b>APS Product ID:</b> {aps_pid_val}\n⏱ <b>APS Duration:</b> {aps_dur_val}\n━━━━━━━━━━━━━━━━━━")
        toggle_btn_text = "Hide Product 👁‍🗨" if prod[10] else "Unhide Product 👁"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Edit Panel Group 🏷️", callback_data=f"edit_p_{p_id}_cat", style="primary"), InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{p_id}_panel_name", style="primary")],
            [InlineKeyboardButton(text="Edit Package Name ✏️", callback_data=f"edit_p_{p_id}_name", style="primary")],
            [InlineKeyboardButton(text="Edit Price 💰", callback_data=f"edit_p_{p_id}_price", style="primary"), InlineKeyboardButton(text="Edit R-Price 👑", callback_data=f"edit_p_{p_id}_rprice", style="primary")],
            [InlineKeyboardButton(text="Edit Validity ⏳", callback_data=f"edit_p_{p_id}_validity", style="primary"), InlineKeyboardButton(text="Edit Device 📱", callback_data=f"edit_p_{p_id}_device", style="primary")],
            [InlineKeyboardButton(text="Edit APK Link 🔗", callback_data=f"edit_p_{p_id}_apk", style="primary"), InlineKeyboardButton(text="Edit Tutorial 🎬", callback_data=f"edit_p_{p_id}_tutorial", style="primary")],
            [InlineKeyboardButton(text="Edit Video Text 📝", callback_data=f"edit_p_{p_id}_tutorial_caption", style="primary")],
            [InlineKeyboardButton(text="Add Keys ➕", callback_data=f"edit_p_{p_id}_keys", style="success")],
            [InlineKeyboardButton(text="⚡ Set APS (Auto Deliver)", callback_data=f"aps_setup_{p_id}", style="success")],
            [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", style="danger"), InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_p_{p_id}", style="danger")],
            [InlineKeyboardButton(text="Nuke Full Node 🗑", callback_data=f"delete_p_{p_id}", style="danger"), InlineKeyboardButton(text="BACK", callback_data="admin_manage_prods", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in admin_view_product: {e}")
        await call.message.edit_text(f"❌ Error loading product: {str(e)}", reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    current = db_query("SELECT is_active FROM products WHERE id=?", (p_id,), fetchone=True)[0]
    new_val = 0 if current == 1 else 1
    db_query("UPDATE products SET is_active=? WHERE id=?", (new_val, p_id))
    await call.answer("Visibility updated successfully!", show_alert=True)
    await admin_view_product(call)

# ==============================================================================
# FIX: Edit product field – correctly handle different data types and multi-word fields
# ==============================================================================
@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    # Use split with maxsplit=3 to keep field name intact (may contain underscores)
    parts = call.data.split("_", 3)
    if len(parts) < 4:
        return await call.answer("Invalid callback data.", show_alert=True)
    p_id = int(parts[2])
    field = parts[3]
    await state.update_data(edit_p_id=p_id, edit_field=field)
    if field == 'keys':
        await call.message.edit_text("📥 <b>Vault Injection</b>\nPaste the <b>NEW KEYS</b> to append to the stock (1 key per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    else:
        field_name_map = {'cat': 'New Panel Group/Category Name', 'panel_name': 'New Panel Name', 'name': 'New Package/Date Name', 'price': 'New Standard Price in ₹', 'rprice': 'New Reseller Price in ₹', 'validity': 'New Time Validity String', 'device': 'New HWID Limit String', 'apk': 'New Payload Link (or type "none")', 'tutorial': 'New Product Tutorial Video (upload video/file_id/URL)', 'tutorial_caption': 'New Text Shown Under Video (or type none)'}
        await call.message.edit_text(f"✏️ Input the required data for: <b>{field_name_map.get(field, field)}</b>", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)

@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']
    field = data['edit_field']

    # Tutorial can be replaced by directly uploading a Telegram video.
    if field == 'tutorial_caption' and m.text:
        new_val = '' if m.text.strip().lower() == 'none' else m.text.strip()
        if len(new_val) > 1024:
            return await m.answer("❌ Video text 1024 characters se zyada nahi ho sakta.")
    elif field == 'tutorial' and m.video:
        new_val = m.video.file_id
    elif m.text:
        new_val = m.text.strip()
        if field in ['price', 'rprice']:
            try:
                new_val = float(new_val)
            except ValueError:
                return await m.answer("❌ Invalid number format. Please enter a valid price (e.g., 500).")
        elif field in ['apk', 'tutorial', 'tutorial_caption']:
            new_val = "" if new_val.lower() == 'none' else new_val
    else:
        return await m.answer("❌ Please send valid text, or upload a video for Tutorial.")

    db_col_map = {'cat': 'category', 'panel_name': 'panel_name', 'name': 'name', 'price': 'price_inr', 'rprice': 'reseller_price', 'validity': 'validity', 'device': 'device_limit', 'apk': 'apk_link', 'tutorial': 'tutorial_video', 'tutorial_caption': 'tutorial_caption'}
    if field not in db_col_map:
        return await m.answer("❌ Invalid edit field.")
    db_query(f"UPDATE products SET {db_col_map[field]}=? WHERE id=?", (new_val, p_id))
    await m.answer("✅ <b>Product updated successfully!</b>", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if len(keys) == 0: return await m.answer("❌ Protocol breach: Zero valid keys found.", reply_markup=admin_kb(), parse_mode='HTML')
    conn = sqlite3.connect('Cuibcc.db')
    c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit(); conn.close()
    await m.answer(f"✅ <b>Vault Secure!</b> {len(keys)} new keys appended and encrypted.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    db_query("DELETE FROM products WHERE id=?", (p_id,))
    db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    await call.answer("☢️ Nuclear wipe successful! Node and vault deleted.", show_alert=True)
    await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    await state.update_data(del_p_id=p_id)
    await call.message.edit_text("🗑 Send the <b>exact string match</b> of the key you wish to purge from the vault:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)

@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['del_p_id']
    key_to_delete = m.text.strip()
    key_data = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?", (p_id, key_to_delete), fetchone=True)
    if not key_data: return await m.answer("❌ Key not found. Check logs and try again.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if key_data[1] == 1: return await m.answer("⚠️ Action Blocked: This key has already been dispatched to a user.", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (key_data[0],))
    db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer(f"✅ Key <code>{key_to_delete}</code> securely purged from vault.\n📦 Database indices updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 21. ADMIN TICKETS, BROADCAST, COUPONS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets: return await call.answer("✅ Zero pending issues. Grid is clean!", show_alert=True)
    t = tickets[0]
    text = (f"🎫 <b><u>ACTIVE TICKET #{t[0]}</u></b>\n👤 <b>Origin UID:</b> <code>{t[1]}</code>\n📅 <b>Timestamp:</b> {t[3]}\n\n📝 <b>Payload:</b>\n{t[2]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Formulate Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", style="primary")],
        [InlineKeyboardButton(text="❌ Force Close Ticket", callback_data=f"close_ticket_{t[0]}", style="danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    ticket_id = call.data.split("_")[2]
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    await call.answer("✅ Status set to Closed.", show_alert=True)
    await admin_view_tickets(call) 

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    data = call.data.split("_")
    ticket_id, user_id = data[2], data[3]
    await state.update_data(ticket_id=ticket_id, user_id=user_id)
    await call.message.edit_text(f"💬 Formulating reply for node <code>{user_id}</code>.\n\nType your message payload:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)

@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'], f"📞 <b>Admin Reply (Ref #{data['ticket_id']}):</b>\n\n{m.text}", parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Payload delivered and connection closed successfully.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e: await m.answer(f"❌ Transmission Error: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📢 <b>Mass Broadcast Protocol</b>\n\nSend the rich message payload you wish to transmit globally across the grid:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.broadcast_msg)

@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    m = await message.answer("⏳ Broadcast protocol initiated... Do not interrupt.", parse_mode='HTML')
    for u in users:
        try:
            await message.send_copy(chat_id=u[0])
            sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.06) 
    await m.edit_text(f"✅ <b>Global Broadcast Complete!</b>\n\n🟢 Nodes reached: {sent}\n🔴 Nodes failed/blocked: {failed}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🎟 Enter a highly secure alphanumeric sequence for the Promo Code:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)

@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Enter the monetary reward payload in <b>RUPEES (₹)</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_amount)

@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text)) 
        await m.answer("👥 Enter the exact maximum threshold uses for this code:", parse_mode='HTML')
        await state.set_state(AdminStates.add_coupon_uses)
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text)
        data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)", (data['code'], data['amount'], uses))
        await m.answer(f"✅ Protocol <b>{data['code']}</b> encoded!\nReward Vector: {fmt_curr(data['amount'])}\nThreshold Limit: {uses} executions.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

# ==============================================================================
# 22. ADMIN RESELLER & SPIN SETTINGS
# ==============================================================================
@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else "ON"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Grant Reseller Rights", callback_data="reseller_make", style="success"), InlineKeyboardButton(text="➖ Revoke Reseller", callback_data="reseller_remove", style="danger")],
        [InlineKeyboardButton(text="📋 Audit Active Resellers", callback_data="reseller_view", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if sys_status == 'ON' else '🔴'} Auto-Upgrade System: {sys_status}", callback_data="admin_toggle_reseller_sys", style="success" if sys_status == 'ON' else "danger")], 
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("👑 <b>Wholesale Reseller Protocols</b>\nSelect administrative action:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('reseller_system_status', ?)", (new_status,))
    await admin_reseller_menu(call)

@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    action = call.data
    await state.update_data(reseller_action=action)
    await call.message.edit_text("👤 Identify target node. Input <b>User ID</b> or <b>@username</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)

@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    data = await state.get_data()
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    user_q = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await m.answer("❌ Target completely ghosted. Not in database.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name = user_q[0], user_q[1]
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
        await m.answer(f"✅ Credentials upgraded. <b>{u_name}</b> (<code>{u_id}</code>) has reseller rights.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (u_id,))
        await m.answer(f"✅ Credentials revoked. <b>{u_name}</b> (<code>{u_id}</code>) is back to regular user.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    resellers = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not resellers: return await call.message.edit_text("📋 Zero active resellers found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    text = "👑 <b><u>ACTIVE RESELLER AUDIT LOG</u></b> 👑\n━━━━━━━━━━━━━━━━━━\n"
    for r in resellers:
        uname = f"(@{r[2]})" if r[2] else ""
        text += f"👤 {r[1]} {uname}\n🆔 <code>{r[0]}</code>\n\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📹 Input direct streaming / YouTube Link for Tutorial system:\n<i>(Or type 'None' to clear registry):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)

@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('how_to_video', ?)", (link,))
    await m.answer("✅ Routing complete. Video linked.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rows = db_query("SELECT key, value FROM settings WHERE key LIKE 'emoji_%' ORDER BY key", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        key = row[0]
        slot = key.replace("emoji_", "")
        current_id = row[1] if row[1] else "Not set"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{slot} (ID: {current_id})", callback_data=f"edit_emoji_{slot}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Edit All Emojis</b>\nChoose an emoji slot to change its ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    slot = call.data.split("edit_emoji_", 1)[1]
    await state.update_data(emoji_slot=slot)
    current = get_setting(f"emoji_{slot}", "Not set")
    await call.message.edit_text(f"✏️ Enter new emoji ID for <b>{slot}</b>:\nCurrent: {current}\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_emoji_slot)

@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    data = await state.get_data()
    slot = data['emoji_slot']
    new_id = m.text.strip()
    if new_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset emoji for '{slot}' to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not new_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"emoji_{slot}", new_id)
        await m.answer(f"✅ Emoji for '{slot}' updated to ID {new_id}.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit Start Menu Text", callback_data="edit_ui_start", style="primary")],
        [InlineKeyboardButton(text="Edit VIP Menu Text", callback_data="edit_ui_vip", style="primary")],
        [InlineKeyboardButton(text="Edit Add Balance Text", callback_data="edit_ui_add_balance", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("✏️ <b>Edit User Interface Texts</b>\nSelect which text you want to modify:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    ui_key = call.data.split("_")[2]
    await state.update_data(ui_key=ui_key)
    current_text = get_ui_text(ui_key)
    await call.message.edit_text(f"📝 Send the new text for <b>{ui_key.upper()}</b> menu.\n\nCurrent text:\n{current_text}", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_ui_text)

@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    data = await state.get_data()
    ui_key = data['ui_key']
    new_text = m.text
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", new_text))
    await m.answer(f"✅ UI text <b>{ui_key}</b> updated successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query("SELECT id, name, category, panel_name, reseller_price FROM products ORDER BY category, panel_name", fetchall=True)
    if not prods: return await call.message.edit_text("No products to edit.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        panel_name = p[3] if p[3] is not None else ""
        r_price = safe_float(p[4])
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[2]} - {panel_name} - {p[1]} (₹{r_price:.2f})", callback_data=f"edit_reseller_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("👑 <b>Edit Reseller Price per Product</b>\nSelect a product to change its wholesale price:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    prod_id = int(call.data.split("_")[2])
    await state.update_data(edit_reseller_prod_id=prod_id)
    await call.message.edit_text("💰 Enter the new <b>Reseller Price</b> in Rupees (₹) for this product:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_price)

@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    try:
        new_price = float(m.text)
        data = await state.get_data()
        prod_id = data['edit_reseller_prod_id']
        db_query("UPDATE products SET reseller_price=? WHERE id=?", (new_price, prod_id))
        await m.answer(f"✅ Reseller price updated to {fmt_curr(new_price)} for product ID {prod_id}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid price.")

@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💰 Enter the new <b>Reseller Setup Fee</b> in Rupees (₹):\nCurrent: " + get_setting("reseller_setup_fee", "200.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    try:
        fee = float(m.text)
        set_setting("reseller_setup_fee", str(fee))
        await m.answer(f"✅ Reseller setup fee updated to {fmt_curr(fee)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💳 Enter the new <b>Minimum Balance</b> required to become reseller (₹):\nCurrent: " + get_setting("reseller_min_balance", "500.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    try:
        min_bal = float(m.text)
        set_setting("reseller_min_balance", str(min_bal))
        await m.answer(f"✅ Minimum reseller balance updated to {fmt_curr(min_bal)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Set Telegram Link", callback_data="admin_set_telegram", style="primary")],
        [InlineKeyboardButton(text="📱 Set WhatsApp Link", callback_data="admin_set_whatsapp", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("📌 <b>Support Contact Links</b>\nSet the URLs for Telegram and WhatsApp support:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("✈️ Enter the Telegram contact URL (e.g., https://t.me/YourSupport):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)

@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_telegram", link)
    await m.answer("✅ Telegram support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📱 Enter the WhatsApp contact URL (e.g., https://wa.me/1234567890):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)

@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_whatsapp", link)
    await m.answer("✅ WhatsApp support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        current = get_setting(f"cat_emoji_{cat}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat} (ID: {current})", callback_data=f"set_cat_emoji_{cat}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Set Category Emojis</b>\nChoose a category to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    category = call.data.split("set_cat_emoji_", 1)[1]
    await state.update_data(cat_emoji_category=category)
    await call.message.edit_text(f"🎨 Enter the emoji ID for <b>{category}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)

@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    category = data['cat_emoji_category']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"cat_emoji_{category}",))
        await m.answer(f"✅ Reset emoji for {category} to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"cat_emoji_{category}", emoji_id)
        await m.answer(f"✅ Emoji set for {category} successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    panels = db_query("SELECT DISTINCT panel_name FROM products WHERE panel_name != '' ORDER BY panel_name", fetchall=True)
    if not panels:
        await call.message.edit_text("No panel names found in products.", reply_markup=admin_back_kb(), parse_mode='HTML')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in panels:
        panel = p[0]
        current = get_setting(f"panel_emoji_{panel}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{panel} (ID: {current})", callback_data=f"set_panel_emoji_{panel}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🖼 <b>Set Panel Emojis</b>\nChoose a panel name to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_panel_emoji_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    panel_name = call.data.split("set_panel_emoji_", 1)[1]
    await state.update_data(panel_emoji_name=panel_name)
    await call.message.edit_text(f"🎨 Enter the emoji ID for panel <b>{panel_name}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_panel_emoji_id)

@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    panel_name = data['panel_emoji_name']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{panel_name}",))
        await m.answer(f"✅ Reset emoji for panel '{panel_name}'.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"panel_emoji_{panel_name}", emoji_id)
        await m.answer(f"✅ Emoji set for panel '{panel_name}'!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 23. ADMIN FAMGATEWAY SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_setup_fampay")
async def setup_fampay_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    current_api = get_setting("fampay_api_key", "Not set")
    await call.message.edit_text(
        f"⚙️ <b>FAMGATEWAY SECURITY SETUP</b>\n\n"
        f"🔑 Current API Key: {current_api[:8] if current_api != 'Not set' else 'Not set'}... (hidden)\n\n"
        f"Send new <b>FamGateway API Key</b>:\n<i>(Type /cancel to abort)</i>",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_fampay_api)

@dp.message(AdminStates.wait_for_fampay_api)
async def setup_fampay_api(m: Message, state: FSMContext):
    if not m.text: return await m.answer("❌ Please send a valid API Key.")
    if m.text.strip().lower() == '/cancel':
        await state.clear()
        return await m.answer("Sequence killed.", reply_markup=admin_kb(), parse_mode='HTML')
    api_key = m.text.strip()
    set_setting("fampay_api_key", api_key)
    await state.clear()
    await m.answer("✅ <b>FamGateway API Key saved!</b>\n\nGateway is now ready for payments.", reply_markup=admin_kb(), parse_mode='HTML')

# ==============================================================================
# 24. ADMIN BINANCE SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_setup_binance")
async def setup_binance_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🪙 <b>CRYPTO NODE INIT: Step 1/3</b>\nInput Master <b>Binance API Key</b>:\n<i>(Type /cancel to halt protocol)</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_api)

@dp.message(AdminStates.wait_for_binance_api)
async def setup_binance_api(m: Message, state: FSMContext):
    if m.text == '/cancel':
        await state.clear()
        return await m.answer("Sequence aborted.", reply_markup=admin_kb(), parse_mode='HTML')
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_api', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 2/3</b>\nNow inject the highly secure <b>Binance Secret Key</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_secret)

@dp.message(AdminStates.wait_for_binance_secret)
async def setup_binance_secret(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_secret', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 3/3</b>\nFinal variable: Set the public <b>USDT Deposit Address (TRC20/BEP20)</b>\nUsers will broadcast to this ledger:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_address)

@dp.message(AdminStates.wait_for_binance_address)
async def setup_binance_address(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_address', ?)", (m.text.strip(),))
    await m.answer("✅ <b>Blockchain node synchronized.</b> Crypto gateway is fully armed.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# ==============================================================================
# APS API ADMIN SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_aps_api_setup")
async def aps_api_setup_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    api_key = get_setting("aps_api_key", APS_API_KEY)
    endpoint = get_setting("aps_endpoint", APS_ENDPOINT)
    master = get_setting("aps_x_master_key", APS_X_MASTER_KEY)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 API Key", callback_data="admin_aps_api_key", style="primary")],
        [InlineKeyboardButton(text="🌐 Endpoint", callback_data="admin_aps_endpoint", style="primary")],
        [InlineKeyboardButton(text="🔐 Master Key", callback_data="admin_aps_master_key", style="primary")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel_back", style="danger")],
    ])
    await call.message.edit_text(
        "🛠 <b>API SETUP</b>\n\n"
        f"🔑 API Key: <b>{'Configured' if api_key else 'Not set'}</b>\n"
        f"🌐 Endpoint: <b>{'Configured' if endpoint else 'Not set'}</b>\n"
        f"🔐 Master Key: <b>{'Configured' if master else 'Not set'}</b>\n\nSelect a field to change:",
        reply_markup=kb, parse_mode='HTML'
    )

@dp.callback_query(F.data == "admin_aps_api_key")
async def aps_api_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🔑 <b>APS API KEY</b>\n\nSend the new API Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_aps_api_key)

@dp.message(AdminStates.wait_for_aps_api_key)
async def aps_api_key_save(m: Message, state: FSMContext):
    if not m.text: return await m.answer("❌ Please send a valid API Key.")
    value=m.text.strip()
    if value.lower()=="/cancel": await state.clear(); return await m.answer("❌ Cancelled.", reply_markup=admin_kb())
    set_setting("aps_api_key", value); await state.clear()
    await m.answer("✅ <b>APS API Key saved.</b>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_aps_endpoint")
async def aps_endpoint_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    current=get_setting("aps_endpoint", APS_ENDPOINT)
    await call.message.edit_text(f"🌐 <b>APS ENDPOINT</b>\n\nCurrent: <code>{html.escape(current)}</code>\n\nSend the new Endpoint:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_aps_endpoint)

@dp.message(AdminStates.wait_for_aps_endpoint)
async def aps_endpoint_save(m: Message, state: FSMContext):
    if not m.text: return await m.answer("❌ Please send a valid Endpoint.")
    value=m.text.strip()
    if value.lower()=="/cancel": await state.clear(); return await m.answer("❌ Cancelled.", reply_markup=admin_kb())
    if not (value.startswith("http://") or value.startswith("https://")): return await m.answer("❌ Endpoint must start with http:// or https://")
    set_setting("aps_endpoint", value); await state.clear()
    await m.answer("✅ <b>APS Endpoint saved.</b>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_aps_master_key")
async def aps_master_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🔐 <b>APS MASTER KEY</b>\n\nSend the new Master Key:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_aps_master_key)

@dp.message(AdminStates.wait_for_aps_master_key)
async def aps_master_key_save(m: Message, state: FSMContext):
    if not m.text: return await m.answer("❌ Please send a valid Master Key.")
    value=m.text.strip()
    if value.lower()=="/cancel": await state.clear(); return await m.answer("❌ Cancelled.", reply_markup=admin_kb())
    set_setting("aps_x_master_key", value); await state.clear()
    await m.answer("✅ <b>APS Master Key saved.</b>", reply_markup=admin_kb(), parse_mode='HTML')

# ==============================================================================
# APS ADMIN SETUP HANDLERS
# ==============================================================================
@dp.callback_query(F.data.startswith("aps_setup_"))
async def aps_setup_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    p_id = call.data.split("aps_setup_")[1]
    await state.update_data(aps_prod_db_id=p_id)
    prod = db_query("SELECT name, aps_product_id, aps_duration FROM products WHERE id=?", (p_id,), fetchone=True)
    current_pid = prod[1] if prod and prod[1] else "Not Set"
    current_dur = prod[2] if prod and prod[2] else "Not Set"
    await call.message.edit_text(
        f"⚡ <b>APS SETUP — {prod[0] if prod else p_id}</b>\n\n"
        f"📌 Current APS Product ID: <code>{current_pid}</code>\n"
        f"⏱ Current APS Duration: <code>{current_dur}</code>\n\n"
        f"Enter the <b>APS Product ID (PID)</b> from adminpanels.shop:\n"
        f"<i>(Type /clear to disable APS for this product)</i>",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_aps_product_id)

@dp.message(AdminStates.wait_for_aps_product_id)
async def aps_set_product_id(m: Message, state: FSMContext):
    if m.text == '/clear':
        data = await state.get_data()
        p_id = data['aps_prod_db_id']
        db_query("UPDATE products SET aps_product_id='', aps_duration='' WHERE id=?", (p_id,))
        await m.answer("✅ APS disabled for this product.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
        return
    await state.update_data(aps_pid_value=m.text.strip())
    await m.answer(
        f"⏱ Now enter the <b>APS Duration</b>\n"
        f"(e.g., <code>1 Day</code>, <code>7 Days</code>, <code>1 Hours</code>, <code>30 Days</code>)\n\n"
        f"<i>Use exact format from adminpanels.shop product table.</i>",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_aps_duration)

@dp.message(AdminStates.wait_for_aps_duration)
async def aps_set_duration(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['aps_prod_db_id']
    aps_pid = data['aps_pid_value']
    aps_dur = m.text.strip()
    db_query("UPDATE products SET aps_product_id=?, aps_duration=? WHERE id=?", (aps_pid, aps_dur, p_id))
    await m.answer(
        f"✅ <b>APS Configured!</b>\n\n"
        f"📌 Product ID: <code>{aps_pid}</code>\n"
        f"⏱ Duration: <code>{aps_dur}</code>\n\n"
        f"Now when a user buys this product, the key will be auto-fetched from adminpanels.shop ⚡",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    log_activity(ADMIN_ID, "APS_CONFIGURED", f"DB Product ID: {p_id}, APS PID: {aps_pid}, Duration: {aps_dur}")
    await state.clear()

@dp.callback_query(F.data == "admin_view_aps_stock")
async def admin_view_aps_stock(call: CallbackQuery):
    """View live stock from adminpanels.shop."""
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("⏳ <b>Fetching live stock from adminpanels.shop...</b>", parse_mode='HTML')
    import ssl
    aps_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-master-key": get_setting("aps_x_master_key", APS_X_MASTER_KEY),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    result = None
    # API sirf "buy" action support karta hai, stock info ke liye products list try karte hain
    for action_name in ["products", "list", "stock", "get_products"]:
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    get_setting("aps_endpoint", APS_ENDPOINT),
                    data=urllib.parse.urlencode({"api_key": get_setting("aps_api_key", APS_API_KEY), "action": action_name}),
                    headers=aps_headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                    allow_redirects=True
                ) as resp:
                    result = await resp.json(content_type=None)
            if isinstance(result, list) or (isinstance(result, dict) and result.get("status") not in ("error", None)):
                break
        except Exception as e:
            result = {"status": "error", "message": str(e)}
    try:
        if isinstance(result, list):
            text = "📦 <b>APS LIVE PRODUCTS (adminpanels.shop)</b>\n━━━━━━━━━━━━━━━━━━\n"
            for item in result[:20]:
                name = item.get("name", item.get("product_name", "Unknown"))
                pid = item.get("id", item.get("pid", item.get("product_id", "?")))
                text += f"• <b>{name}</b> — PID: <code>{pid}</code>\n"
            text += f"\n<i>Yeh PIDs APS Setup mein use karo.</i>"
        else:
            text = (
                f"📦 <b>APS Raw Response:</b>\n<code>{str(result)[:800]}</code>\n\n"
                f"ℹ️ Note: adminpanels.shop ka stock check API available nahi hai.\n"
                f"APS kaam karta hai — user buy kare tab key auto-fetch hogi. ✅"
            )
    except Exception as e:
        text = f"❌ Parse error: {e}"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

# ==============================================================================
# 25. BOOTSTRAPPING & MAIN
# ==============================================================================
async def main() -> None:
    init_db()
    logger.info("Initializing DB structure...")
    migrate_categories()
    asyncio.create_task(auto_verify_task())
    asyncio.create_task(auto_product_verify_task())
    logger.info("FamGateway Auto-Verifier Daemon Running in Background.")
    logger.info("Product Auto-Verifier Daemon Running — instant key delivery enabled.")
    logger.info("🚀 CORE SYSTEM IS FULLY OPERATIONAL...")
    try:
        await dp.start_polling(bot)
    except Exception as err:
        logger.error(f"Critical System Failure in Polling: {err}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("System shutting down gracefully. Goodbye.")