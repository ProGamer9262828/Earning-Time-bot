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

# --- DB CONNECTION ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
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

# --- HELPER: CHECK IF USER JOINED CHANNELS ---
def is_user_joined_all(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels_str = cursor.fetchone()[0]
    conn.close()
    
    try:
        channels = json.loads(channels_str) if channels_str else []
    except:
        channels = []
        
    if not channels:
        return True

    for ch in channels:
        # Agar link format me hai, to username extract karne ki koshish karein
        chat_target = ch.replace("https://t.me/", "@") if "t.me" in ch else ch
        try:
            member = bot.get_chat_member(chat_target, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            # Agar bot admin nahi hai ya private channel hai, toh user ko safe rakhne ke liye bypass na rokein
            continue
    return True

# --- ANTI-CHEAT WEBAPP ENGINE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Verification</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0b0e14; color: white; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .container { background-color: #151a24; border-radius: 24px; padding: 40px 20px; text-align: center; width: 85%; max-width: 360px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); border: 1px solid #1f293d; }
        .spinner { width: 80px; height: 80px; border: 4px solid rgba(255, 255, 255, 0.1); border-top: 4px solid #00b0ff; border-radius: 50%; margin: 0 auto 30px auto; animation: spin 1s linear infinite; }
        .icon-box { width: 90px; height: 90px; border-radius: 50%; display: none; justify-content: center; align-items: center; margin: 0 auto 25px auto; transform: scale(0.5); animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }
        .success-icon { border: 3px solid #00e676; background: rgba(0, 230, 118, 0.1); box-shadow: 0 0 20px rgba(0, 230, 118, 0.2); }
        .success-icon::after { content: "✓"; font-size: 45px; color: #00e676; font-weight: bold; }
        .danger-icon { border: 3px solid #ff1744; background: rgba(255, 23, 68, 0.1); box-shadow: 0 0 20px rgba(255, 23, 68, 0.2); }
        .danger-icon::after { content: "✕"; font-size: 40px; color: #ff1744; font-weight: bold; }
        h2 { color: #ffffff; font-size: 22px; margin-bottom: 12px; font-weight: 700; }
        p { color: #90a4ae; font-size: 14px; line-height: 1.6; margin-bottom: 35px; min-height: 45px; }
        .btn { background: linear-gradient(135deg, #78909c 0%, #455a64 100%); color: #ffffff; border: none; padding: 16px; border-radius: 14px; font-size: 15px; font-weight: bold; width: 100%; cursor: not-allowed; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.6; pointer-events: none; transition: all 0.3s ease; }
        .btn.active-success { background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%); color: #0b0e14; cursor: pointer; opacity: 1; pointer-events: auto; box-shadow: 0 5px 20px rgba(0, 230, 118, 0.4); }
        .btn.active-danger { background: linear-gradient(135deg, #ff1744 0%, #ff9100 100%); color: #ffffff; cursor: pointer; opacity: 1; pointer-events: auto; box-shadow: 0 5px 20px rgba(255, 23, 68, 0.4); }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes popIn { 100% { transform: scale(1); } }
    </style>
</head>
<body>
    <div class="container">
        <div id="loader" class="spinner"></div>
        <div id="statusIcon" class="icon-box"></div>
        <h2 id="mainHeading">Device Checking...</h2>
        <p id="subText">Please wait 3-5 seconds while we verify your hardware identity configurations...</p>
        <button id="actionBtn" class="btn" onclick="secureSubmit()">Processing...</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.ready();

        const urlParams = new URLSearchParams(window.location.search);
        const tgUserId = urlParams.get('user_id');

        function getHardwareFingerprint() {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            let debugInfo = "";
            if (gl) {
                const ext = gl.getExtension('WEBGL_debug_renderer_info');
                debugInfo = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "";
            }
            const profile = [
                navigator.hardwareConcurrency || 4,
                screen.colorDepth,
                screen.availWidth + "x" + screen.availHeight,
                new Date().getTimezoneOffset(),
                debugInfo,
                navigator.deviceMemory || "N/A"
            ].join("||");
            return btoa(unescape(encodeURIComponent(profile))).substring(0, 32);
        }

        const hwToken = getHardwareFingerprint();
        
        setTimeout(() => {
            document.getElementById('mainHeading').innerText = "Analyzing Telemetry...";
            document.getElementById('subText').innerText = "Checking device duplications and anti-bypass system registry...";
        }, 1500);

        setTimeout(() => {
            fetch(`/api/check_device?hw_token=${hwToken}&user_id=${tgUserId}`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById('loader').style.display = "none";
                    const iconEl = document.getElementById('statusIcon');
                    const btnEl = document.getElementById('actionBtn');
                    iconEl.style.display = "flex";

                    if(data.is_duplicate) {
                        iconEl.classList.add('danger-icon');
                        document.getElementById('mainHeading').innerText = "Same Device Detected";
                        document.getElementById('mainHeading').style.color = "#ff1744";
                        document.getElementById('subText').innerText = "This device is already registered with another account. Referral system bypassed.";
                        btnEl.innerText = "Continue to Bot";
                        btnEl.className = "btn active-danger";
                        btnEl.setAttribute('data-status', 'VERIFIED_SAME_DEVICE');
                    } else {
                        iconEl.classList.add('success-icon');
                        document.getElementById('mainHeading').innerText = "Device Checked Successfully";
                        document.getElementById('mainHeading').style.color = "#00e676";
                        document.getElementById('subText').innerText = "Your hardware profile is fully verified as unique. System access allowed safely.";
                        btnEl.innerText = "Continue to Bot";
                        btnEl.className = "btn active-success";
                        btnEl.setAttribute('data-status', 'VERIFIED_OK');
                    }
                }).catch(() => {
                    document.getElementById('loader').style.display = "none";
                    document.getElementById('statusIcon').style.display = "flex";
                    document.getElementById('statusIcon').classList.add('success-icon');
                    document.getElementById('mainHeading').innerText = "Device Checked Successfully";
                    document.getElementById('actionBtn').className = "btn active-success";
                    document.getElementById('actionBtn').innerText = "Continue to Bot";
                });
        }, 3500);

        function secureSubmit() {
            const btnEl = document.getElementById('actionBtn');
            const finalStatus = btnEl.getAttribute('data-status') || "VERIFIED_OK";
            const clientPayload = {
                status: finalStatus,
                hw_token: hwToken
            };
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

@app.route('/api/check_device')
def check_device():
    hw_token = request.args.get('hw_token', '')
    user_id = request.args.get('user_id', '')
    if not hw_token or not user_id or user_id in ["null", "None", ""]:
        return {"is_duplicate": False}
    try:
        current_uid = int(user_id)
    except ValueError:
        return {"is_duplicate": False}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (hw_token, current_uid))
    duplicate = cursor.fetchone()
    conn.close()
    if duplicate:
        return {"is_duplicate": True}
    return {"is_duplicate": False}

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

# --- START ROUTER WITH FIXED CHANNEL KEYBOARD ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    text_split = message.text.split()
    
    try:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    except:
        pass
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referrer = int(text_split[1]) if (len(text_split) > 1 and text_split[1].isdigit()) else None
        if referrer == user_id: referrer = None
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referrer))
        if referrer:
            cursor.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (referrer, user_id))
        conn.commit()
        is_verified = 0
    else:
        is_verified = user[0]
        
    if is_verified == 1: 
        conn.close()
        bot.send_message(message.chat.id, "👋 Welcome back to the main lobby!", reply_markup=get_main_keyboard())
        return
            
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels_str = cursor.fetchone()[0]
    try:
        channels = json.loads(channels_str) if channels_str else []
    except:
        channels = []
    conn.close()
    
    # Check if already joined channels to skip directly to verification
    if channels and not is_user_joined_all(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, ch in enumerate(channels, 1):
            btn_url = ch if ch.startswith("http") else f"https://t.me/{ch.replace('@', '')}"
            markup.add(types.InlineKeyboardButton(text=f"↗️ Join Channel {index}", url=btn_url))
        markup.add(types.InlineKeyboardButton(text="✔️ Checked / Joined ✅", callback_data="check_channels"))
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click 'Checked / Joined' Button*", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))

# --- PLATFORM TELEMETRY PIPELINE ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        incoming_status = data.get("status")
        hw_token = data.get("hw_token")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
        ref_by = cursor.fetchone()[0]
        
        if incoming_status == "VERIFIED_SAME_DEVICE":
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (hw_token, user_id))
            if ref_by:
                cursor.execute("UPDATE referrals SET status = 'Failed: Same Device Flag' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                try:
                    bot.send_message(ref_by, f"⚠️ *Referral Failed (Same Device)!*\n\nUser `{user_id}` ne click kiya par device duplicate mila, isliye referral point skip kar diya gaya.", parse_mode='Markdown')
                except: pass
            
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "⚠️ *Same Device Detected!*\n\nAapka device pehle se use ho chuka hai. Aap bot use kar sakte hain par jiske link se aapne join kiya hai, unka referral count nahi hoga.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
            return
            
        if incoming_status == "VERIFIED_OK":
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (hw_token, user_id))
            if ref_by:
                cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
                per_invite, current_fund = cursor.fetchone()
                if current_fund >= per_invite:
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (per_invite, ref_by))
                    cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (per_invite,))
                    cursor.execute("UPDATE referrals SET status = 'Success & Verified' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try:
                        bot.send_message(ref_by, f"🔔 *New Unique Referral!*\nUser ID `{user_id}` verified uniquely. ₹{per_invite} added!", parse_mode='Markdown')
                    except: pass
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ *Device Checked Successfully!*\n\nWelcome! Aap ab bot use kar sakte hain.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Engine Fault: {str(e)}")

# --- INLINE CALL ROUTER WITH VERIFICATION CHECK ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if call.data == "check_channels":
        bot.answer_callback_query(call.id)
        if is_user_joined_all(user_id):
            bot.send_message(call.message.chat.id, "🛡️ *Channels Verified Successfully!* Now click below to open Real Hardware Scan:", parse_mode="Markdown", reply_markup=get_verify_keyboard(user_id))
        else:
            bot.send_message(call.message.chat.id, "❌ *Aapne abhi saare channels join nahi kiye hain!* Kripya pehle upar diye gaye channels join karein.", parse_mode="Markdown")
            
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

# --- HANDLER WITH STRICT VERIFICATION CHECK ---
@bot.message_handler(func=lambda msg: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text
    
    if text.startswith('/start'):
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified, balance FROM users WHERE user_id = ?", (user_id,))
    user_status = cursor.fetchone()
    
    if not user_status or user_status[0] == 0:
        conn.close()
        # Direct redirect back to channel flow if not even verified
        start(message)
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
            bot.send_message(message.chat.id, "❌ Invalid amount setup. Request terminated.")
            return
        msg = bot.send_message(message.chat.id, "Now type your valid *UPI ID*:")
        bot.register_next_step_handler(msg, process_withdraw_upi, amount)
    except ValueError: 
        bot.send_message(message.chat.id, "❌ Please enter valid numbers only.")

def process_withdraw_upi(message, amount):
    user_id = message.from_user.id
    upi_id = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    current_balance = cursor.fetchone()[0]
    if amount > current_balance:
        bot.send_message(message.chat.id, "❌ Balance mismatch.")
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

if __name__ == '__main__':
    import threading
    threading.Thread(target=bot.infinity_polling, kwargs={"skip_pending": True}, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
