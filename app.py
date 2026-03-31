import telebot
import os
import shutil
import zipfile
import subprocess
import signal
import json
import uuid
import psutil
import time
import sys
import threading
import secrets
import string
from datetime import datetime
from telebot import types
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ==========================================
# CONFIGURATION
# ==========================================
# ⚠️ REPLACE WITH YOUR NEW BOT TOKEN AFTER REVOKING THE OLD ONE
API_TOKEN = '8730119226:AAHvEKzS2EX4RuZFlTLsaiSlnSJKIq5q2kw'
ADMIN_ID = 8379062893
CHANNEL_1 = "@exucodex"
CHANNEL_2 = "@Daka_vip_1"
WEB_URL = "https://your-custom-app.onrender.com"

# Server Folders
BOT_TEMPLATES_DIR = "bot_templates"
INSTANCES_DIR = "instances"
FLASK_TEMPLATES = "templates"
DB_FILE = "secure_database.json"
ALLOWED_EXTENSIONS = {'zip'}

# Create directories
os.makedirs(BOT_TEMPLATES_DIR, exist_ok=True)
os.makedirs(INSTANCES_DIR, exist_ok=True)
os.makedirs(FLASK_TEMPLATES, exist_ok=True)

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def style_bold(text):
    """Convert text to bold stylized font"""
    bold_map = {
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈',
        'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑',
        'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠', 'h': '𝐡', 'i': '𝐢',
        'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫',
        's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱', 'y': '𝐲', 'z': '𝐳',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗'
    }
    return ''.join(bold_map.get(c, c) for c in text)

# ==========================================
# DATABASE MANAGER
# ==========================================
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
            
            # Validate structure
            if "users" not in data:
                data["users"] = {}
            if "keys" not in data:
                data["keys"] = {}
            if "instances" not in data:
                data["instances"] = {}
            if "coupons" not in data:
                data["coupons"] = {}
            if "broadcasts" not in data:
                data["broadcasts"] = []
            
            return data
        except Exception as e:
            print(f"Error loading database: {e}")
            return create_new_db()
    return create_new_db()

def create_new_db():
    return {
        "keys": {},
        "users": {},
        "instances": {},
        "coupons": {},
        "broadcasts": []
    }

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ==========================================
# TELEGRAM SUBSCRIPTION LOGIC
# ==========================================
def check_subs(user_id):
    if user_id == ADMIN_ID:
        return True
    for ch in [CHANNEL_1, CHANNEL_2]:
        try:
            mem = bot.get_chat_member(ch, user_id)
            if mem.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception:
            return False
    return True

def join_keyboard():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(types.InlineKeyboardButton(style_bold("JOIN CHANNEL 1"), url=f"https://t.me/{CHANNEL_1.strip('@')}"))
    m.add(types.InlineKeyboardButton(style_bold("JOIN CHANNEL 2"), url=f"https://t.me/{CHANNEL_2.strip('@')}"))
    m.add(types.InlineKeyboardButton(style_bold("✅ VERIFY JOINS"), callback_data="verify_sub"))
    return m

def main_keyboard(is_admin=False, is_premium=False):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [style_bold("🔑 GENERATE ACCESS KEY")]
    if is_premium or is_admin:
        buttons.append(style_bold("💎 PREMIUM STATUS"))
    if is_admin:
        buttons.extend([
            style_bold("🛡️ ADMIN PANEL"),
            style_bold("📢 BROADCAST"),
            style_bold("🎫 CREATE COUPON"),
            style_bold("📊 STATS")
        ])
    m.add(*buttons)
    return m

def admin_panel_markup():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(
        types.InlineKeyboardButton(style_bold("👥 VIEW ALL USERS"), callback_data="admin_users"),
        types.InlineKeyboardButton(style_bold("🎫 MANAGE COUPONS"), callback_data="admin_coupons"),
        types.InlineKeyboardButton(style_bold("📢 SEND BROADCAST"), callback_data="admin_broadcast"),
        types.InlineKeyboardButton(style_bold("📊 SYSTEM STATS"), callback_data="admin_stats"),
        types.InlineKeyboardButton(style_bold("🧹 CLEAN INSTANCES"), callback_data="admin_clean"),
        types.InlineKeyboardButton(style_bold("📦 MANAGE TEMPLATES"), callback_data="admin_templates")
    )
    return m

def check_premium_status(user_id):
    try:
        db = load_db()
        user_data = db["users"].get(str(user_id))
        
        if user_data is None:
            return False
        
        if isinstance(user_data, dict):
            active_key = user_data.get("active_key")
            if active_key and active_key in db["keys"]:
                key_data = db["keys"][active_key]
                if isinstance(key_data, dict) and key_data.get("type") == "premium":
                    return True
        return False
    except Exception as e:
        print(f"Error checking premium status: {e}")
        return False

# ==========================================
# TELEGRAM BOT ROUTES
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    try:
        uid = message.chat.id
        if not check_subs(uid):
            txt = style_bold("⛔ ACCESS DENIED!") + "\n\n" + style_bold("You must join BOTH channels to use the Web Panel.")
            return bot.send_message(uid, txt, reply_markup=join_keyboard(), parse_mode="Markdown")
        
        db = load_db()
        is_premium = check_premium_status(uid)
        is_admin = (uid == ADMIN_ID)
        
        txt = style_bold("✅ SYSTEM VERIFIED") + " ✨\n\n"
        txt += style_bold("🤖 Welcome to EXU Deploy System!") + "\n\n"
        if is_premium:
            txt += style_bold("💎 PREMIUM USER") + " - Unlimited access (PERMANENT)\n"
        if is_admin:
            txt += style_bold("👑 ADMIN ACCESS") + " - Full control (PERMANENT)\n"
        txt += "\n" + style_bold("👇 Click below to generate your web panel access key.") + "\n"
        txt += style_bold("♾️ Your key will be PERMANENT and never expire!")
        
        bot.send_message(uid, txt, reply_markup=main_keyboard(is_admin, is_premium), parse_mode="Markdown")
    except Exception as e:
        print(f"Error in start_cmd: {e}")
        bot.send_message(message.chat.id, style_bold("System error. Please try again."))

@bot.callback_query_handler(func=lambda call: call.data == "verify_sub")
def verify_call(call):
    try:
        bot.answer_callback_query(call.id)
        if check_subs(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start_cmd(call.message)
        else:
            bot.send_message(call.message.chat.id, style_bold("❌ You have not joined BOTH channels yet!"))
    except Exception as e:
        print(f"Error in verify_call: {e}")

@bot.message_handler(func=lambda m: m.text == style_bold("🔑 GENERATE ACCESS KEY"))
def generate_web_key(message):
    try:
        uid = message.chat.id
        if not check_subs(uid):
            return start_cmd(message)
        
        db = load_db()
        user_key_info = db["users"].get(str(uid))
        
        if not isinstance(user_key_info, dict):
            user_key_info = {"active_key": None, "premium_until": None}
        
        old_key = user_key_info.get("active_key")
        is_premium = check_premium_status(uid)
        key_type = "premium" if is_premium else "normal"
        if uid == ADMIN_ID:
            key_type = "admin"
        
        new_key = uuid.uuid4().hex[:16].upper()
        
        db["keys"][new_key] = {
            "user": uid,
            "locked_ip": None,
            "type": key_type,
            "expires": None,
            "created_at": datetime.now().isoformat(),
            "permanent": True
        }
        
        if old_key and old_key in db["keys"]:
            del db["keys"][old_key]
        
        db["users"][str(uid)] = {"active_key": new_key, "premium_until": None}
        save_db(db)
        
        resp = (
            f"{style_bold('✅ PERMANENT KEY GENERATED')}\n\n"
            f"🔐 {style_bold('Your Access Key')}:\n`{new_key}`\n"
            f"🏷️ {style_bold('Type')}: {style_bold(key_type.upper())}\n"
            f"♾️ {style_bold('Validity')}: {style_bold('PERMANENT - Never Expires')}\n\n"
            f"🌐 {style_bold('Web Panel')}:\n{WEB_URL}\n\n"
            f"⚠️ {style_bold('Key locks to first IP. Do not share!')}\n"
            f"✅ {style_bold('This key is permanent and will never expire!')}"
        )
        bot.send_message(uid, resp, parse_mode="Markdown")
    except Exception as e:
        print(f"Error in generate_web_key: {e}")
        bot.send_message(message.chat.id, style_bold("Error generating key. Please try again."))

@bot.message_handler(func=lambda m: m.text == style_bold("💎 PREMIUM STATUS"))
def premium_status(message):
    try:
        uid = message.chat.id
        is_premium = check_premium_status(uid)
        
        if is_premium:
            txt = f"{style_bold('PREMIUM ACCESS')} 💎\n\n"
            txt += f"✅ {style_bold('Status')}: Active\n"
            txt += f"♾️ {style_bold('Validity')}: {style_bold('PERMANENT - Never Expires')}\n\n"
            txt += style_bold("You have permanent premium access!")
            txt += "\n\n" + style_bold("✓ Unlimited bot deployments")
            txt += "\n" + style_bold("✓ Priority support")
            txt += "\n" + style_bold("✓ All features unlocked")
        else:
            txt = f"{style_bold('PREMIUM STATUS')} 💎\n\n"
            txt += f"❌ {style_bold('You do not have premium access.')}\n\n"
            txt += style_bold("Contact admin to get a permanent premium coupon!")
        
        bot.send_message(uid, txt, parse_mode="Markdown")
    except Exception as e:
        print(f"Error in premium_status: {e}")
        bot.send_message(message.chat.id, style_bold("Error checking status."))

# ==========================================
# ADMIN COMMANDS
# ==========================================
@bot.message_handler(func=lambda m: m.text == style_bold("🛡️ ADMIN PANEL"))
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return bot.send_message(message.chat.id, style_bold("Unauthorized access!"))
    bot.send_message(ADMIN_ID, style_bold("🛡️ ADMIN CONTROL PANEL"), reply_markup=admin_panel_markup(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    if call.message.chat.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
        return
    
    action = call.data.replace("admin_", "")

    if action == "users":
        db = load_db()
        users_info = []
        for uid, data in db["users"].items():
            if isinstance(data, dict):
                active_key = data.get("active_key")
                key_data = db["keys"].get(active_key, {})
                key_type = key_data.get("type", "normal") if isinstance(key_data, dict) else "normal"
                permanent = key_data.get("permanent", True)
            else:
                key_type = "normal"
                permanent = True
            premium = check_premium_status(int(uid))
            perm_status = "♾️" if permanent else "⏰"
            users_info.append(f"{perm_status} 👤 {uid} | {key_type.upper()} | Premium: {'✅' if premium else '❌'}")
        
        if not users_info:
            text = style_bold("No users registered.")
        else:
            text = f"{style_bold('Total Users')}: {len(users_info)}\n{style_bold('(All keys are PERMANENT)')}\n\n" + "\n".join(users_info[-30:])
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif action == "coupons":
        db = load_db()
        coupons = db.get("coupons", {})
        if not coupons:
            text = style_bold("No coupons created yet.") + "\n\n" + style_bold("Use 'Create Coupon' to generate permanent premium keys.")
        else:
            text = style_bold("PERMANENT COUPONS") + " ♾️\n\n"
            for code, info in coupons.items():
                status = "Available" if not info.get("used_by") else f"Used by {info.get('used_by')}"
                text += f"🔑 `{code}` | {info.get('type').upper()} | {status}\n"
            text += f"\n{style_bold('Note: All coupons grant PERMANENT access!')}"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif action == "stats":
        db = load_db()
        total_keys = len(db["keys"])
        total_users = len(db["users"])
        total_instances = len(db["instances"])
        total_coupons = len(db.get("coupons", {}))
        total_templates = len([f for f in os.listdir(BOT_TEMPLATES_DIR) if f.endswith('.zip')])
        
        text = f"{style_bold('SYSTEM STATISTICS')}\n\n"
        text += f"🔑 {style_bold('Active Keys')}: {total_keys} (ALL PERMANENT)\n"
        text += f"👥 {style_bold('Registered Users')}: {total_users}\n"
        text += f"🤖 {style_bold('Running Instances')}: {total_instances}\n"
        text += f"🎫 {style_bold('Coupons Created')}: {total_coupons}\n"
        text += f"📦 {style_bold('Bot Templates')}: {total_templates}\n"
        text += f"💾 {style_bold('Memory')}: {psutil.virtual_memory().percent}%\n"
        text += f"⚡ {style_bold('CPU')}: {psutil.cpu_percent()}%\n\n"
        text += f"♾️ {style_bold('All keys are PERMANENT - never expire!')}"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif action == "clean":
        db = load_db()
        dead_instances = []
        for inst_id, info in list(db["instances"].items()):
            try:
                if isinstance(info, dict) and "pid" in info:
                    os.kill(info["pid"], 0)
            except:
                dead_instances.append(inst_id)
                del db["instances"][inst_id]
        
        save_db(db)
        bot.edit_message_text(f"{style_bold('Cleaned')} {len(dead_instances)} {style_bold('dead instances.')}", call.message.chat.id, call.message.message_id)

    elif action == "templates":
        templates = [f for f in os.listdir(BOT_TEMPLATES_DIR) if f.endswith('.zip')]
        if not templates:
            text = style_bold("No templates uploaded yet.") + "\n\n" + style_bold("Use the Web Panel to upload bot templates.")
        else:
            text = style_bold("📦 BOT TEMPLATES") + " ♾️\n\n"
            for tpl in templates:
                size = os.path.getsize(os.path.join(BOT_TEMPLATES_DIR, tpl))
                size_mb = round(size / 1024 / 1024, 2)
                text += f"📄 `{tpl}` | {size_mb}MB\n"
            text += f"\n{style_bold('Upload more via Web Panel > Admin > Templates')}"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif action == "broadcast":
        bot.edit_message_text(
            f"{style_bold('📢 SEND BROADCAST')}\n\n{style_bold('Send the message you want to broadcast to all users.')}\n\n{style_bold('Reply to this message with the broadcast content.')}", 
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, process_broadcast)

def process_broadcast(message):
    if message.chat.id != ADMIN_ID:
        return
    broadcast_text = message.text
    db = load_db()
    success = 0
    failed = 0
    for user_id in db["users"].keys():
        try:
            bot.send_message(int(user_id), f"{style_bold('📢 ANNOUNCEMENT FROM ADMIN')}\n\n{broadcast_text}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1

    bot.send_message(ADMIN_ID, f"✅ {style_bold('Broadcast complete!')}\n\n📨 {style_bold('Sent')}: {success}\n❌ {style_bold('Failed')}: {failed}")

@bot.message_handler(func=lambda m: m.text == style_bold("📢 BROADCAST"))
def broadcast_command(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(ADMIN_ID, style_bold("Send the message to broadcast to all users:"))
    bot.register_next_step_handler(message, process_broadcast)

@bot.message_handler(func=lambda m: m.text == style_bold("🎫 CREATE COUPON"))
def create_coupon_menu(message):
    if message.chat.id != ADMIN_ID:
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(style_bold("PREMIUM COUPON (PERMANENT)"), callback_data="coupon_premium"))
    markup.add(types.InlineKeyboardButton(style_bold("ADMIN COUPON (PERMANENT)"), callback_data="coupon_admin"))
    markup.add(types.InlineKeyboardButton(style_bold("❌ CANCEL"), callback_data="coupon_cancel"))
    bot.send_message(ADMIN_ID, style_bold("SELECT COUPON TYPE:"), reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("coupon_"))
def handle_coupon_creation(call):
    if call.message.chat.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
        return
    
    coupon_type = call.data.replace("coupon_", "")

    if coupon_type == "cancel":
        bot.edit_message_text(style_bold("Cancelled."), call.message.chat.id, call.message.message_id)
        return

    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))

    db = load_db()
    db["coupons"][code] = {
        "type": coupon_type,
        "used_by": None,
        "created_by": ADMIN_ID,
        "created_at": datetime.now().isoformat(),
        "permanent": True
    }
    save_db(db)

    bot.edit_message_text(
        f"✅ {style_bold('PERMANENT COUPON CREATED!')}\n\n"
        f"🔑 {style_bold('Code')}: `{code}`\n"
        f"🏷️ {style_bold('Type')}: {style_bold(coupon_type.upper())}\n"
        f"♾️ {style_bold('Validity')}: {style_bold('PERMANENT - Never Expires')}\n\n"
        f"{style_bold('User can redeem with')}: /redeem {code}\n\n"
        f"⚠️ {style_bold('This coupon grants PERMANENT access!')}",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == style_bold("📊 STATS"))
def stats_command(message):
    if message.chat.id != ADMIN_ID:
        return
    db = load_db()
    total_keys = len(db["keys"])
    total_users = len(db["users"])
    total_instances = len(db["instances"])
    total_templates = len([f for f in os.listdir(BOT_TEMPLATES_DIR) if f.endswith('.zip')])
    
    text = f"{style_bold('SYSTEM STATISTICS')}\n\n"
    text += f"🔑 {style_bold('Active Keys')}: {total_keys} (ALL PERMANENT)\n"
    text += f"👥 {style_bold('Users')}: {total_users}\n"
    text += f"🤖 {style_bold('Bots Running')}: {total_instances}\n"
    text += f"📦 {style_bold('Templates')}: {total_templates}\n"
    text += f"💾 {style_bold('RAM')}: {psutil.virtual_memory().percent}%\n"
    text += f"⚡ {style_bold('CPU')}: {psutil.cpu_percent()}%\n\n"
    text += f"♾️ {style_bold('All keys are PERMANENT and never expire!')}"

    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['redeem'])
def redeem_coupon(message):
    try:
        uid = message.chat.id
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(uid, style_bold("Usage: /redeem <COUPON_CODE>"))
            return
        
        coupon_code = parts[1].upper()
        
        db = load_db()
        coupon = db["coupons"].get(coupon_code)
        
        if not coupon:
            bot.send_message(uid, style_bold("Invalid coupon code!"))
            return
        
        if coupon.get("used_by"):
            bot.send_message(uid, f"{style_bold('Coupon already used by user')} {coupon['used_by']}!")
            return
        
        coupon_type = coupon["type"]
        coupon["used_by"] = uid
        
        if coupon_type == "premium":
            new_key = uuid.uuid4().hex[:16].upper()
            db["keys"][new_key] = {
                "user": uid,
                "locked_ip": None,
                "type": "premium",
                "expires": None,
                "created_at": datetime.now().isoformat(),
                "permanent": True
            }
            user_data = db["users"].get(str(uid))
            if not isinstance(user_data, dict):
                user_data = {"active_key": None, "premium_until": None}
            user_data["active_key"] = new_key
            user_data["premium_until"] = None
            db["users"][str(uid)] = user_data
            
            save_db(db)
            bot.send_message(uid, 
                f"✅ {style_bold('PERMANENT PREMIUM ACTIVATED!')}\n\n"
                f"🔑 {style_bold('Your Access Key')}: `{new_key}`\n"
                f"♾️ {style_bold('Validity')}: {style_bold('PERMANENT - Never Expires')}\n\n"
                f"🌐 {style_bold('Web Panel')}: {WEB_URL}\n\n"
                f"{style_bold('You now have permanent premium access!')}"
            )
        elif coupon_type == "admin":
            new_key = uuid.uuid4().hex[:16].upper()
            db["keys"][new_key] = {
                "user": uid,
                "locked_ip": None,
                "type": "admin",
                "expires": None,
                "created_at": datetime.now().isoformat(),
                "permanent": True
            }
            user_data = db["users"].get(str(uid))
            if not isinstance(user_data, dict):
                user_data = {"active_key": None, "premium_until": None}
            user_data["active_key"] = new_key
            db["users"][str(uid)] = user_data
            
            save_db(db)
            bot.send_message(uid, 
                f"👑 {style_bold('PERMANENT ADMIN ACCESS GRANTED!')}\n\n"
                f"🔑 {style_bold('Your Access Key')}: `{new_key}`\n"
                f"♾️ {style_bold('Validity')}: {style_bold('PERMANENT - Never Expires')}\n\n"
                f"{style_bold('You now have full admin privileges!')}"
            )
        
        save_db(db)
        bot.send_message(ADMIN_ID, f"🎫 {style_bold('PERMANENT Coupon')} `{coupon_code}` {style_bold('used by')} {uid}")
    except Exception as e:
        print(f"Error in redeem_coupon: {e}")
        bot.send_message(message.chat.id, style_bold("Error redeeming coupon."))

# ==========================================
# FLASK WEB API
# ==========================================
@app.route('/')
def serve_html():
    try:
        return render_template("index.html")
    except Exception as e:
        return f"Frontend HTML Not Found. Error: {e}", 500

@app.route('/api/login', methods=['POST'])
def api_login():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Missing Auth Key"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403

    client_ip = request.remote_addr
    key_data = db["keys"][req_key]

    if key_data["locked_ip"] is None:
        db["keys"][req_key]["locked_ip"] = client_ip
        save_db(db)
    elif key_data["locked_ip"] != client_ip:
        return jsonify({"error": "Key bound to another IP/Device"}), 403

    return jsonify({
        "success": True, 
        "message": "AUTHENTICATED", 
        "user_id": key_data["user"], 
        "type": key_data.get("type", "normal"),
        "permanent": True
    })

@app.route('/api/templates', methods=['GET'])
def get_zips():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    zips = [f for f in os.listdir(BOT_TEMPLATES_DIR) if f.endswith('.zip')]
    return jsonify(zips)

@app.route('/api/templates', methods=['POST'])
def upload_template():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if not filename.endswith('.zip'):
            filename += '.zip'
        filepath = os.path.join(BOT_TEMPLATES_DIR, filename)
        file.save(filepath)
        return jsonify({"success": True, "filename": filename})
    
    return jsonify({"error": "Invalid file type. Only .zip files allowed"}), 400

@app.route('/api/templates/<filename>', methods=['DELETE'])
def delete_template(filename):
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    filepath = os.path.join(BOT_TEMPLATES_DIR, filename)
    if os.path.exists(filepath) and filename.endswith('.zip'):
        os.remove(filepath)
        return jsonify({"success": True})
    
    return jsonify({"error": "Template not found"}), 404

@app.route('/api/mybots', methods=['GET'])
def get_user_bots():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403

    user = db["keys"][req_key]["user"]
    bots = {k: v for k, v in db["instances"].items() if v["user"] == user}
    return jsonify(bots)

@app.route('/api/sys_stats', methods=['GET'])
def sys_metrics():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    try:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return jsonify({"cpu": cpu, "ram": ram})
    except:
        return jsonify({"cpu": 0, "ram": 0})

@app.route('/api/deploy', methods=['POST'])
def execute_deploy():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403

    user = db["keys"][req_key]["user"]
    key_type = db["keys"][req_key].get("type", "normal")

    if key_type == "normal":
        user_bots = [k for k, v in db["instances"].items() if v["user"] == user]
        if len(user_bots) >= 3:
            return jsonify({"error": "Normal users limited to 3 bots. Upgrade to permanent premium!"}), 403

    data = request.json
    uid = data.get("uid")
    pw = data.get("password")
    tpl = data.get("template")

    if not all([uid, pw, tpl]):
        return jsonify({"error": "Missing Required Configuration"}), 400

    instance_uid = f"NODE_{uuid.uuid4().hex[:6].upper()}"
    path = os.path.join(INSTANCES_DIR, str(user), instance_uid)

    try:
        os.makedirs(path, exist_ok=True)
        template_path = os.path.join(BOT_TEMPLATES_DIR, tpl)
        with zipfile.ZipFile(template_path, 'r') as zip_ref:
            zip_ref.extractall(path)
        
        with open(os.path.join(path, "Bot.txt"), "w") as f:
            f.write(f"uid={uid}\npassword={pw}\n")
        
        log_f = open(os.path.join(path, "sys.log"), "a")
        proc = subprocess.Popen([sys.executable, "main.py"], cwd=path, stdout=log_f, stderr=log_f)
        
        db["instances"][instance_uid] = {
            "user": user,
            "pid": proc.pid,
            "target_uid": uid,
            "template": tpl,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_db(db)
        
        return jsonify({"success": True, "instance": instance_uid})

    except Exception as e:
        if os.path.exists(path):
            shutil.rmtree(path)
        return jsonify({"error": str(e)}), 500

@app.route('/api/stop/<inst_id>', methods=['DELETE'])
def wipe_instance(inst_id):
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403

    user = db["keys"][req_key]["user"]

    if inst_id not in db["instances"] or db["instances"][inst_id]["user"] != user:
        return jsonify({"error": "Instance invalid or not authorized"}), 403

    try:
        os.kill(db["instances"][inst_id]["pid"], signal.SIGTERM)
    except:
        pass

    folder = os.path.join(INSTANCES_DIR, str(user), inst_id)
    if os.path.exists(folder):
        shutil.rmtree(folder)

    del db["instances"][inst_id]
    save_db(db)

    return jsonify({"success": True})

# ==========================================
# ADMIN API ENDPOINTS
# ==========================================
@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    total_users = len(db["users"])
    total_keys = len(db["keys"])
    total_instances = len(db["instances"])
    premium_users = sum(1 for k in db["keys"].values() if k.get("type") == "premium")
    total_templates = len([f for f in os.listdir(BOT_TEMPLATES_DIR) if f.endswith('.zip')])
    
    return jsonify({
        "total_users": total_users,
        "active_keys": total_keys,
        "running_bots": total_instances,
        "premium_users": premium_users,
        "total_templates": total_templates
    })

@app.route('/api/admin/users', methods=['GET'])
def admin_users():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    users = []
    for uid, data in db["users"].items():
        if isinstance(data, dict):
            active_key = data.get("active_key")
            key_data = db["keys"].get(active_key, {})
            key_type = key_data.get("type", "normal") if isinstance(key_data, dict) else "normal"
            users.append({
                "user_id": uid,
                "key_type": key_type,
                "active_key": active_key
            })
    
    return jsonify(users)

@app.route('/api/admin/coupon', methods=['POST'])
def admin_create_coupon():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.json
    coupon_type = data.get("type", "premium")
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    
    db["coupons"][code] = {
        "type": coupon_type,
        "used_by": None,
        "created_by": db["keys"][req_key]["user"],
        "created_at": datetime.now().isoformat(),
        "permanent": True
    }
    save_db(db)
    
    return jsonify({"code": code, "type": coupon_type})

@app.route('/api/admin/broadcast', methods=['POST'])
def admin_broadcast():
    req_key = request.headers.get("Authorization")
    if not req_key:
        return jsonify({"error": "Unauthorized"}), 403
    
    db = load_db()
    if req_key not in db["keys"]:
        return jsonify({"error": "Invalid Key"}), 403
    
    if db["keys"][req_key].get("type") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.json
    message = data.get("message")
    
    if not message:
        return jsonify({"error": "Message required"}), 400
    
    success = 0
    failed = 0
    
    for user_id in db["users"].keys():
        try:
            bot.send_message(int(user_id), f"**📢 ANNOUNCEMENT FROM ADMIN**\n\n{message}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1
    
    return jsonify({"success": success, "failed": failed})

# ==========================================
# BOOTLOADER
# ==========================================
def serve_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                test = json.load(f)
            print(style_bold("Existing database found. Validating..."))
        except:
            print(style_bold("Corrupted database detected. Creating fresh database..."))
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
    
    print(style_bold("=" * 50))
    print(style_bold("EXU DEPLOY SYSTEM STARTING..."))
    print(style_bold("=" * 50))
    print(style_bold("Admin ID:") + f" {ADMIN_ID}")
    print(style_bold("Web URL:") + f" {WEB_URL}")
    print(style_bold("Bot Templates Dir:") + f" {BOT_TEMPLATES_DIR}")
    print(style_bold("Key Type:") + f" {style_bold('PERMANENT - Never Expires')}")
    print(style_bold("=" * 50))

    t = threading.Thread(target=serve_web)
    t.daemon = True
    t.start()

    print(style_bold("Flask server running"))
    print(style_bold("Telegram bot polling..."))
    bot.infinity_polling()
