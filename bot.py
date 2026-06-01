import sqlite3
import random
import json
import os
import telebot
from telebot import types
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string

# --- CONFIGURATION ---
BOT_TOKEN = "8473027179:AAF-9rouF_79QAZRNLIeDnHNgg3-VPeq1RQ"
ADMIN_ID = 8031127296
RAILWAY_DOMAIN = "https://earning-time-bot-production.up.railway.app" 

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
DB_FILE = 'bot_data.db'

# --- SAFE DATABASE UTILITIES WITH LOCK PROTECTION ---
def get_db_connection():
    # check_same_thread=False allows multi-threaded Flask/Telebot processing safely
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=20)
    conn.execute('PRAGMA journal_mode=WAL;')  # High performance concurrent read/writes
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY, per_invite REAL, min_withdraw REAL, 
                        bot_fund REAL, earn_more_link TEXT, mandatory_channels TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, 
                        referred_by INTEGER, device_token TEXT, is_verified INTEGER DEFAULT 0, last_bonus_time TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referee_id INTEGER, status TEXT DEFAULT 'Started (Unverified)')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS withdraws (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, upi_id TEXT, status TEXT DEFAULT 'Pending')''')
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings VALUES (1, 5.0, 20.0, 100000.0, 'https://t.me/your_channel', '[]')")
    conn.commit()
    conn.close()

init_db()

# --- HARDENED WEBAPP ENGINE (ADVANCED HARDWARE ANTI-CHEAT) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Authenticator Engine</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0b0e14; color: white; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background-color: #151a24; border-radius: 24px; padding: 40px 20px; text-align: center; width: 85%; max-width: 360px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #1f293d; }
        .icon-circle { width: 90px; height: 90px; border-radius: 50%; border: 3px solid #00e676; display: flex; justify-content: center; align-items: center; margin: 0 auto 25px auto; background: rgba(0, 230, 118, 0.1); animation: pulse 2s infinite; }
        .icon-circle::after { content: "✓"; font-size: 45px; color: #00e676; font-weight: bold; }
        h2 { color: #00e676; font-size: 24px; margin-bottom: 8px; font-weight: 700; }
        p { color: #90a4ae; font-size: 14px; line-height: 1.6; margin-bottom: 35px; }
        .btn { background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%); color: #0b0e14; border: none; padding: 16px; border-radius: 14px; font-size: 15px; font-weight: bold; width: 100%; cursor: pointer; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 5px 20px rgba(0, 230, 118, 0.4); transition: transform 0.2s; }
        .btn:active { transform: scale(0.98); }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.4); } 70% { box-shadow: 0 0 0 15px rgba(0, 230, 118, 0); } 100% { box-shadow: 0 0 0 0 rgba(0, 230, 118, 0); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon-circle"></div>
        <h2>Device Checked Successfully</h2>
        <p>Your hardware profile has been verified. You can now unlock the automated dashboard systems safely.</p>
        <button class="btn" onclick="secureSubmit()">Complete Onboarding</button>
    </div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.ready();
        
        function getHardwareFingerprint() {
            // Complex multi-layered hardware string generation
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            let debugInfo = "";
            if (gl) {
                const ext = gl.getExtension('WEBGL_debug_renderer_info');
                debugInfo = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "";
            }
            
            // Core unique components combinations
            const hardwareProfile = [
                navigator.hardwareConcurrency || 4,
                screen.colorDepth,
                screen.availWidth + "x" + screen.availHeight,
                new Date().getTimezoneOffset(),
                navigator.cookieEnabled,
                debugInfo,
                navigator.deviceMemory || "N/A"
            ].join("||");
            
            // Convert to secure pseudo-hash string
            return btoa(unescape(encodeURIComponent(hardwareProfile))).substring(0, 40);
        }
        
        function secureSubmit() {
            const dynamicToken = getHardwareFingerprint();
            const initRaw = tg.initDataUnsafe;
            
            const clientPayload = {
                status: "VERIFIED_OK",
                hw_token: dynamicToken,
                tg_user_id: initRaw.user ? initRaw.user.id : null
            };
            
            // Push real-time event back through Telegram socket pipeline
            tg.sendData(JSON.stringify(clientPayload));
            tg.close();
        }
    </script>
</body>
</html>
"""

@app.route('/verify_page')
def verify_page():
    return render_template_string(HTML_TEMPLATE)

@app.route('/')
def home():
    return "Bot Core Service Active"

# --- SYSTEM KEYBOARDS ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🎉 Gift Code'), types.KeyboardButton('💰 Balance'))
    markup.add(types.KeyboardButton('👥 Refer & Earn'), types.KeyboardButton('💸 Withdraw'))
    markup.add(types.KeyboardButton('🎰 Bet & Earn'), types.KeyboardButton('🚀 Earn More'))
    return markup

def get_verify_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    web_app_url = f"{RAILWAY_DOMAIN}/verify_page?user_id={chat_id}"
    markup.add(types.KeyboardButton('🛡️ Click Here to Verify', web_app=types.WebAppInfo(url=web_app_url)))
    return markup

# --- START COMMAND ROUTER ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    text_split = message.text.split()
    
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referrer = int(text_split[1]) if (len(text_split) > 1 and text_split[1].isdigit()) else None
        if referrer == user_id: referrer = None
        
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referrer))
        if referrer:
            cursor.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (referrer, user_id))
        conn.commit()
    else:
        if user[5] == 1:  # check if is_verified == 1
            bot.send_message(message.chat.id, "👋 Welcome back to the main lobby!", reply_markup=get_main_keyboard())
            conn.close()
            return
            
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels_str = cursor.fetchone()[0]
    try:
        channels = json.loads(channels_str) if channels_str else []
    except:
        channels = []
    conn.close()
    
    if channels:
        markup = types.InlineKeyboardMarkup()
        for index, ch in enumerate(channels, 1):
            markup.add(types.InlineKeyboardButton(text=f"↗️ Join Channel {index}", url=ch))
        markup.add(types.InlineKeyboardButton(text="✔️ Claim", callback_data="check_channels"))
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))

# --- WEB APP REAL-TIME RESPONSE INTERCEPTOR ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("status") == "VERIFIED_OK":
            hw_token = data.get("hw_token")
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # CRITICAL: Find if this hardware profile token exists on another user account
            cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (hw_token, user_id))
            duplicate_device = cursor.fetchone()
            
            # Check referral tracking links
            cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
            ref_by = cursor.fetchone()[0]
            
            if duplicate_device:
                # CRITICAL CORE LOGIC MATCH:
                # This device has already been bound to another account.
                # The current user can use the bot, but the person who referred them gets NO CREDIT.
                cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
                if ref_by:
                    cursor.execute("UPDATE referrals SET status = 'Failed: Same Device Flag' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try:
                        bot.send_message(ref_by, f"⚠️ *Referral Multi-Account Alert!*\n\nUser `{user_id}` has joined your link using an existing device asset. No referral credit issued.", parse_mode='Markdown')
                    except: pass
                
                conn.commit()
                conn.close()
                
                bot.send_message(message.chat.id, "⚠️ *Verification Alert !!*\n\nYour hardware signature matches another system asset. Access granted to bot functions but referral tracking is invalidated.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
                return
            
            # Fresh new device setup path
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (hw_token, user_id))
            
            if ref_by:
                cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
                per_invite, current_fund = cursor.fetchone()
                if current_fund >= per_invite:
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (per_invite, ref_by))
                    cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (per_invite,))
                    cursor.execute("UPDATE referrals SET status = 'Success & Verified' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try:
                        bot.send_message(ref_by, f"🔔 *New Successful Referral!*\nUser ID `{user_id}` has completed unique verification. ₹{per_invite} added to wallet!", parse_mode='Markdown')
                    except: pass
            
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ *Verified Successfully!*\n\nYou can use our bot now.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Engine Processing Fault: {str(e)}")

# --- TEXT MENU HANDLING ARCHITECTURE ---
@bot.message_handler(func=lambda msg: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified, balance FROM users WHERE user_id = ?", (user_id,))
    user_status = cursor.fetchone()
    
    if not user_status or user_status[0] == 0:
        conn.close()
        bot.send_message(message.chat.id, "🛡️ *Please complete your verification first:*", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))
        return

    balance = user_status[1]

    if text == '🎉 Gift Code':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧭 Daily Bonus", callback_data="daily_bonus"))
        bot.send_message(message.chat.id, "✨ *Choose One:*", parse_mode='Markdown', reply_markup=markup)
    elif text == '💰 Balance':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history"), types.InlineKeyboardButton("💸 Bot Fund", callback_data="view_bot_fund"))
        bot.send_message(message.chat.id, f"💰 *Balance: ₹{balance:.2f}*\n\n🎉 Use 'Withdraw' Button to Withdraw!", parse_mode='Markdown', reply_markup=markup)
    elif text == '👥 Refer & Earn':
        cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
        per_invite = cursor.fetchone()[0]
        invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 My Invites", callback_data="my_invites"))
        bot.send_message(message.chat.id, f"🎁 *Per Invite ₹{int(per_invite)} UPI Cash !!*\n\n🎁 *Invite Link :* {invite_link}", parse_mode='Markdown', reply_markup=markup)
    elif text == '💸 Withdraw':
        cursor.execute("SELECT min_withdraw FROM settings WHERE id = 1")
        min_w = cursor.fetchone()[0]
        if balance < min_w:
            bot.send_message(message.chat.id, f"🤑 *You need minimum {int(min_w)} in balance to withdraw*", parse_mode='Markdown')
        else:
            msg = bot.send_message(message.chat.id, "Please type the *Amount* you want to withdraw:")
            bot.register_next_step_handler(msg, process_withdraw_amount, balance)
    elif text == '🎰 Bet & Earn':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎲 Ludo", callback_data="game_ludo"))
        bot.send_message(message.chat.id, "🎰 *Choose Your Game :*", parse_mode='Markdown', reply_markup=markup)
    elif text == '🚀 Earn More':
        cursor.execute("SELECT earn_more_link FROM settings WHERE id = 1")
        link = cursor.fetchone()[0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Visit Now", url=link))
        bot.send_message(message.chat.id, "🚀 Click below to earn more cash!", reply_markup=markup)
    conn.close()

def process_withdraw_amount(message, balance):
    try:
        amount = float(message.text)
        if amount > balance or amount <= 0: 
            bot.send_message(message.chat.id, "❌ Invalid amount threshold setup. Request terminated.")
            return
        msg = bot.send_message(message.chat.id, "Now type your valid *UPI ID*:")
        bot.register_next_step_handler(msg, process_withdraw_upi, amount)
    except ValueError: 
        bot.send_message(message.chat.id, "❌ Numerical float point error. Please input integers only.")

def process_withdraw_upi(message, amount):
    user_id = message.from_user.id
    upi_id = message.text
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    current_balance = cursor.fetchone()[0]
    
    if amount > current_balance:
        bot.send_message(message.chat.id, "❌ Balance conflict: Double transaction processing blocked.")
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ *Withdrawal Request Submitted!*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    try:
        bot.send_message(ADMIN_ID, f"🔔 *New Withdrawal Alert!*\n\nUser ID: `{user_id}`\nAmount: ₹{amount}\nUPI ID: `{upi_id}`", parse_mode='Markdown')
    except: pass

# --- CALLBACK INTERACTORS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if call.data == "check_channels":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🛡 *Verify Yourself To Start Bot*", reply_markup=get_verify_keyboard(call.message.chat.id))
    elif call.data == "daily_bonus":
        bot.answer_callback_query(call.id)
        
        cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
        last_time_str = cursor.fetchone()[0]
        now = datetime.now()
        
        if last_time_str:
            last_time = datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
            if now - last_time < timedelta(days=1):
                rem_time = timedelta(days=1) - (now - last_time)
                hours, remainder = divmod(rem_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                bot.send_message(call.message.chat.id, f"⏳ *Daily Bonus claimed!* Please wait `{hours}h {minutes}m` to spin again.", parse_mode="Markdown")
                conn.close()
                return
                
        dice_roll = random.randint(1, 6)
        cursor.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", (dice_roll, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        bot.send_message(call.message.chat.id, f"🎲 *Dice Rolled!* You got ₹{dice_roll}!")
        
    elif call.data == "view_bot_fund":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        bot.send_message(call.message.chat.id, f"🟢 *Remaining Fund >>* ₹{cursor.fetchone()[0]:.2f}")
    elif call.data == "w_history":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📝 No recent records.")
    elif call.data == "my_invites":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🚀 Use Tracker to see analytics.")
    elif call.data == "game_ludo":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔴 Big", callback_data="ludo_big"), types.InlineKeyboardButton("🔵 Small", callback_data="ludo_small"))
        bot.send_message(call.message.chat.id, "🎲 Select Bucket:", reply_markup=markup)
    elif call.data in ["ludo_big", "ludo_small"]:
        bot.answer_callback_query(call.id)
        choice = "BIG" if call.data == "ludo_big" else "SMALL"
        msg = bot.send_message(call.message.chat.id, f"💬 Enter amount to bet on {choice}:")
        bot.register_next_step_handler(msg, process_ludo_bet, choice)
    conn.close()

def process_ludo_bet(message, choice):
    user_id = message.from_user.id
    try:
        bet_amount = float(message.text)
        if bet_amount <= 0:
            bot.send_message(message.chat.id, "❌ Invalid Bet Amount.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        
        if bet_amount > balance:
            bot.send_message(message.chat.id, "❌ Low Balance.")
            conn.close()
            return
            
        dice_out = random.randint(1, 6)
        res = "BIG" if dice_out in [4, 5, 6] else "SMALL"
        
        if choice == res:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet_amount, user_id))
            bot.send_message(message.chat.id, f"🎲 Result: {dice_out}. 🥳 *You Won! Balance Doubled!*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet_amount, user_id))
            bot.send_message(message.chat.id, f"🎲 Result: {dice_out}. 😭 *You Lost!*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        
        conn.commit()
        conn.close()
    except ValueError:
        bot.send_message(message.chat.id, "❌ Cancelled. Enter numerical values only.")

# --- DUAL WEB ENGINE LAUNCHER ---
if __name__ == '__main__':
    import threading
    threading.Thread(target=bot.infinity_polling, kwargs={"skip_pending": True}, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
