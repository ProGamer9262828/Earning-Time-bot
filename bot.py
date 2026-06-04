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

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY, per_invite REAL, min_withdraw REAL, 
                        bot_fund REAL, earn_more_link TEXT, mandatory_channels TEXT, verify_system TEXT DEFAULT 'on')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, 
                        referred_by INTEGER, device_token TEXT, is_verified INTEGER DEFAULT 0, last_bonus_time TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referee_id INTEGER, status TEXT DEFAULT 'Started (Unverified)')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS withdraws (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, upi_id TEXT, status TEXT DEFAULT 'Pending')''')
    
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings VALUES (1, 5.0, 20.0, 100000.0, 'https://t.me/your_channel', '[]', 'on')")
    conn.commit()
    conn.close()

init_db()

# --- ADMIN COMMANDS ---
@bot.message_handler(commands=['resetme'])
def cmd_reset_me(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_verified = 0, device_token = NULL WHERE user_id = ?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🔄 Aapka account testing ke liye reset ho gaya hai! Ab shuru se check kijiye.")

@bot.message_handler(commands=['setchannels'])
def cmd_set_channels(message):
    if message.from_user.id != ADMIN_ID: return
    text_split = message.text.split(maxsplit=1)
    if len(text_split) < 2:
        bot.reply_to(message, "ℹ️ Format: `/setchannels @chan1,@chan2` ya `/setchannels none`", parse_mode="Markdown")
        return
    
    input_val = text_split[1].strip()
    if input_val.lower() == "none":
        channels_list = []
        msg = "✅ Saare mandatory channels hata diye gaye hain!"
    else:
        raw_list = input_val.split(",")
        channels_list = []
        for ch in raw_list:
            ch_clean = ch.strip()
            if ch_clean:
                if "t.me/" in ch_clean:
                    ch_clean = "@" + ch_clean.split("t.me/")[1].replace("@", "")
                elif not ch_clean.startswith("@") and not ch_clean.lstrip('-').isdigit():
                    ch_clean = "@" + ch_clean
                channels_list.append(ch_clean)
        msg = f"✅ Mandatory channels updated: {', '.join(channels_list)}"
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET mandatory_channels = ? WHERE id = 1", (json.dumps(channels_list),))
    conn.commit()
    conn.close()
    bot.reply_to(message, msg)

@bot.message_handler(commands=['setverify'])
def cmd_set_verify(message):
    if message.from_user.id != ADMIN_ID: return
    text_split = message.text.split()
    if len(text_split) < 2 or text_split[1].lower() not in ['on', 'off']:
        bot.reply_to(message, "ℹ️ Format: `/setverify on` ya `/setverify off`")
        return
    
    status = text_split[1].lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET verify_system = ? WHERE id = 1", (status,))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"⚙️ Verification System: **{status.upper()}**", parse_mode="Markdown")

def get_clean_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    try: return json.loads(row[0]) if row and row[0] else []
    except: return []

def get_verify_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT verify_system FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "on"

def is_user_joined_all(user_id):
    channels = get_clean_channels()
    if not channels: return True
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ['left', 'kicked']: return False
        except: 
            return False
    return True

# --- HTML WEBAPP ENGINE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hardware Check</title><script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0b0e14; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background-color: #151a24; border-radius: 20px; padding: 30px; text-align: center; width: 85%; max-width: 340px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #1f293d; }
        .spinner { width: 60px; height: 60px; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid #00b0ff; border-radius: 50%; margin: 0 auto 20px auto; animation: spin 1s linear infinite; }
        h2 { font-size: 20px; margin-bottom: 10px; } p { color: #90a4ae; font-size: 13px; line-height: 1.5; margin-bottom: 25px; }
        .btn { background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%); color: #0b0e14; border: none; padding: 14px; border-radius: 12px; font-size: 14px; font-weight: bold; width: 100%; cursor: pointer; display:none; box-shadow: 0 4px 15px rgba(0, 230, 118, 0.3); }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div id="loader" class="spinner"></div>
        <h2 id="title">Device Hardware Checking...</h2>
        <p id="desc">Analyzing hardware identity configs to prevent system duplication bypass loops...</p>
        <button id="actionBtn" class="btn" onclick="secureSubmit()">CONTINUE TO BOT</button>
    </div>
    <script>
        const tg = window.Telegram.WebApp; tg.expand(); tg.ready();
        const uid = new URLSearchParams(window.location.search).get('user_id');
        function getFp() {
            const canvas = document.createElement('canvas'); const gl = canvas.getContext('webgl');
            let extInfo = gl ? (gl.getExtension('WEBGL_debug_renderer_info') ? gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL) : "") : "";
            return btoa([navigator.hardwareConcurrency||4, screen.colorDepth, extInfo, navigator.deviceMemory||"N/A"].join("||")).substring(0, 32);
        }
        const hwToken = getFp();
        setTimeout(() => {
            fetch(`/api/check_device?hw_token=${hwToken}&user_id=${uid}`)
                .then(res => res.json()).then(data => {
                    document.getElementById('loader').style.display = "none";
                    document.getElementById('actionBtn').style.display = "block";
                    if(data.is_duplicate) {
                        document.getElementById('title').innerText = "Same Device Detected";
                        document.getElementById('title').style.color = "#ff1744";
                        document.getElementById('actionBtn').setAttribute('data-status', 'VERIFIED_SAME_DEVICE');
                    } else {
                        document.getElementById('title').innerText = "Verification Successful";
                        document.getElementById('title').style.color = "#00e676";
                        document.getElementById('actionBtn').setAttribute('data-status', 'VERIFIED_OK');
                    }
                }).catch(() => { secureSubmit(); });
        }, 3000);
        function secureSubmit() {
            tg.sendData(JSON.stringify({ status: document.getElementById('actionBtn').getAttribute('data-status') || "VERIFIED_OK", hw_token: hwToken }));
            tg.close();
        }
    </script>
</body>
</html>
"""

@app.route('/verify_page')
def verify_page(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/check_device')
def check_device():
    hw = request.args.get('hw_token', '')
    uid = request.args.get('user_id', '')
    if not hw or not uid or uid in ["null", "None", ""]: return {"is_duplicate": False}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (hw, int(uid)))
    dup = cursor.fetchone()
    conn.close()
    return {"is_duplicate": bool(dup)}

@app.route('/')
def home(): return "Core Framework Active"

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🎉 Gift Code'), types.KeyboardButton('💰 Balance'))
    markup.add(types.KeyboardButton('👥 Refer & Earn'), types.KeyboardButton('💸 Withdraw'))
    markup.add(types.KeyboardButton('🎰 Bet & Earn'), types.KeyboardButton('🚀 Earn More'))
    return markup

def get_verify_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton('🛡️ Click Here to Verify', web_app=types.WebAppInfo(url=f"{RAILWAY_DOMAIN}/verify_page?user_id={chat_id}")))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    text_split = message.text.split()
    
    try: bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    except: pass
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        ref = int(text_split[1]) if (len(text_split) > 1 and text_split[1].isdigit()) else None
        if ref == user_id: ref = None
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, ref))
        if ref: cursor.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (ref, user_id))
        conn.commit()
        is_verified = 0
    else:
        is_verified = user[0]
    conn.close()
            
    # STEP 1: Pehle check karo ki user ne mandatory channels join kiye hain ya nahi
    channels = get_clean_channels()
    if channels and not is_user_joined_all(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, ch in enumerate(channels, 1):
            url = f"https://t.me/{ch.replace('@', '')}"
            markup.add(types.InlineKeyboardButton(text=f"↗️ Join Channel {index}", url=url))
        markup.add(types.InlineKeyboardButton(text="✔️ Checked / Joined ✅", callback_data="check_channels"))
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click 'Checked / Joined' Button*", parse_mode='Markdown', reply_markup=markup)
        return

    # STEP 2: Agar channel joined hain par user verified nahi hai, toh Hardware Verification dikhao
    if is_verified == 0 and get_verify_status() == "on":
        bot.send_message(message.chat.id, "🛡️ *Channels Checked!* Now verify your device hardware to get access:", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))
        return

    # STEP 3: Agar sab clear hai toh Direct Main Lobby open karo
    bot.send_message(message.chat.id, "👋 Welcome back to the main lobby!", reply_markup=get_main_keyboard())


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    try:
        if call.data == "check_channels":
            bot.answer_callback_query(call.id)
            # Jab user button click karega tab verification status check hoga
            if is_user_joined_all(user_id):
                if get_verify_status() == "on":
                    # Channel join karne ke just baad webapp verification button aayega
                    bot.send_message(call.message.chat.id, "🛡️ *Channels Verified!* Ab niche diye gaye button par click karke anti-cheat verification complete karein:", parse_mode="Markdown", reply_markup=get_verify_keyboard(user_id))
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    bot.send_message(call.message.chat.id, "✅ *Verified! Welcome to Lobby.*", reply_markup=get_main_keyboard())
            else:
                bot.send_message(call.message.chat.id, "❌ *Sabh channels join nahi kiya!* Pehle upar diye gaye saare channels join karein.")
            return
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error parsing: {str(e)}")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if call.data == "daily_bonus":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
        l_str = cursor.fetchone()[0]
        now = datetime.now()
        if l_str and (now - datetime.strptime(l_str, '%Y-%m-%d %H:%M:%S') < timedelta(days=1)):
            bot.send_message(call.message.chat.id, "⏳ *Daily Bonus claimed!* Wait 24 Hours.")
        else:
            dice = random.randint(1, 6)
            cursor.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", (dice, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
            conn.commit()
            bot.send_message(call.message.chat.id, f"🎲 *Rolled!* You got ₹{dice}!")
    elif call.data == "view_bot_fund":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        bot.send_message(call.message.chat.id, f"🟢 *Bot Fund:* ₹{cursor.fetchone()[0]:.2f}")
    elif call.data in ["w_history", "my_invites"]:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📝 Records are transparently logged.")
    elif call.data == "game_ludo":
        bot.answer_callback_query(call.id)
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🔴 Big", callback_data="ludo_big"), types.InlineKeyboardButton("🔵 Small", callback_data="ludo_small"))
        bot.send_message(call.message.chat.id, "🎲 Select Bucket:", reply_markup=m)
    elif call.data in ["ludo_big", "ludo_small"]:
        bot.answer_callback_query(call.id)
        ch = "BIG" if call.data == "ludo_big" else "SMALL"
        msg = bot.send_message(call.message.chat.id, f"💬 Enter amount to bet on {ch}:")
        bot.register_next_step_handler(msg, process_ludo_bet, ch)
    conn.close()

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        inc_status, hw = data.get("status"), data.get("hw_token")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
        ref_by = cursor.fetchone()[0]
        
        if inc_status == "VERIFIED_SAME_DEVICE":
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (hw, user_id))
            if ref_by: cursor.execute("UPDATE referrals SET status = 'Failed: Same Device Flag' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
            conn.commit()
            conn.close()
            # Verification clear hone ke baad hi lobby me entry
            bot.send_message(message.chat.id, "⚠️ *Same Device Detected!* Registration allowed without referral reward validation.", reply_markup=get_main_keyboard())
            return
            
        if inc_status == "VERIFIED_OK":
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (hw, user_id))
            if ref_by:
                cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
                pi, fund = cursor.fetchone()
                if fund >= pi:
                    cursor.execute("UPDATE users SET balance = balance + WHERE user_id = ?", (pi, ref_by))
                    cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (pi,))
                    cursor.execute("UPDATE referrals SET status = 'Success & Verified' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try: bot.send_message(ref_by, f"🔔 *New Referral Alert!* Earned ₹{pi}.")
                    except: pass
            conn.commit()
            conn.close()
            # Verification successful hone par final main lobby open
            bot.send_message(message.chat.id, "✅ *Device Verification Done!* Access Granted to Main Lobby.", reply_markup=get_main_keyboard())
    except: pass

@bot.message_handler(func=lambda msg: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text
    if text.startswith('/start'): return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified, balance FROM users WHERE user_id = ?", (user_id,))
    u_status = cursor.fetchone()
    
    # Security layer: Agar user unverified hai toh use menu access nahi milega, automatic /start standard rule trigger ho jayega
    if not u_status or u_status[0] == 0 or not is_user_joined_all(user_id):
        conn.close()
        start(message)
        return

    balance = u_status[1]
    if text == '🎉 Gift Code':
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🧭 Daily Bonus", callback_data="daily_bonus"))
        bot.send_message(message.chat.id, "✨ *Choose Option:*", parse_mode='Markdown', reply_markup=m)
    elif text == '💰 Balance':
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history"), types.InlineKeyboardButton("💸 Bot Fund", callback_data="view_bot_fund"))
        bot.send_message(message.chat.id, f"💰 *Balance: ₹{balance:.2f}*", parse_mode='Markdown', reply_markup=m)
    elif text == '👥 Refer & Earn':
        cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
        pi = cursor.fetchone()[0]
        bot.send_message(message.chat.id, f"🎁 *Per Invite ₹{int(pi)} UPI Cash!*\n\n🔗 Link: https://t.me/{bot.get_me().username}?start={user_id}", parse_mode='Markdown')
    elif text == '💸 Withdraw':
        cursor.execute("SELECT min_withdraw FROM settings WHERE id = 1")
        mw = cursor.fetchone()[0]
        if balance < mw: bot.send_message(message.chat.id, f"❌ *Min withdraw threshold is ₹{int(mw)}*", parse_mode='Markdown')
        else:
            msg = bot.send_message(message.chat.id, "Type the amount:")
            bot.register_next_step_handler(msg, process_withdraw_amount, balance)
    elif text == '🎰 Bet & Earn':
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🎲 Ludo Game", callback_data="game_ludo"))
        bot.send_message(message.chat.id, "🎰 *Games Lobby:*", parse_mode='Markdown', reply_markup=m)
    elif text == '🚀 Earn More':
        cursor.execute("SELECT earn_more_link FROM settings WHERE id = 1")
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🔗 Visit Now", url=cursor.fetchone()[0]))
        bot.send_message(message.chat.id, "🚀 Click to earn extra rewards!", reply_markup=m)
    conn.close()

def process_withdraw_amount(message, balance):
    try:
        amt = float(message.text)
        if amt > balance or amt <= 0: return
        msg = bot.send_message(message.chat.id, "Type your *UPI ID*:")
        bot.register_next_step_handler(msg, process_withdraw_upi, amt)
    except: pass

def process_withdraw_upi(message, amount):
    user_id = message.from_user.id
    upi = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    if amount > cursor.fetchone()[0]: conn.close(); return
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ *Withdrawal Request Submitted!*", reply_markup=get_main_keyboard())
    try: bot.send_message(ADMIN_ID, f"🔔 *Withdraw Alert!*\nUser: `{user_id}`\nAmount: ₹{amount}\nUPI: `{upi}`")
    except: pass

def process_ludo_bet(message, choice):
    user_id = message.from_user.id
    try:
        text = message.text
        if not text.isdigit(): return
        bet = float(text)
        if bet <= 0: return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        if bet > cursor.fetchone()[0]: conn.close(); return
        roll = random.randint(1, 6)
        res = "BIG" if roll in [4, 5, 6] else "SMALL"
        if choice == res:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, user_id))
            bot.send_message(message.chat.id, f"🎲 Roll: {roll}. 🥳 *You Won!*", reply_markup=get_main_keyboard())
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user_id))
            bot.send_message(message.chat.id, f"🎲 Roll: {roll}. 😭 *You Lost!*", reply_markup=get_main_keyboard())
        conn.commit()
        conn.close()
    except: pass

if __name__ == '__main__':
    import threading
    threading.Thread(target=bot.infinity_polling, kwargs={"skip_pending": True}, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)
