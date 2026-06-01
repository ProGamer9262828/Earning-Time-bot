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

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
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

# --- WEB SERVER UI ROUTING (100% FIXED DATA PASS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profit Time Verification</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #0b0e14; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background-color: #151a24; border-radius: 24px; padding: 40px 20px; text-align: center; width: 85%; max-width: 360px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        .icon-circle { width: 100px; height: 100px; border-radius: 50%; border: 3px solid #00e676; display: flex; justify-content: center; align-items: center; margin: 0 auto 30px auto; background: rgba(0, 230, 118, 0.1); }
        .icon-circle::after { content: "✓"; font-size: 50px; color: #00e676; font-weight: bold; }
        h2 { color: #00e676; font-size: 26px; margin-bottom: 10px; }
        p { color: #90a4ae; font-size: 15px; line-height: 1.5; margin-bottom: 40px; }
        .btn { background-color: #00e676; color: #0b0e14; border: none; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; text-transform: uppercase; box-shadow: 0 5px 15px rgba(0, 230, 118, 0.3); }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon-circle"></div>
        <h2>Verified Successfully</h2>
        <p>You're verified successfully, you can use our bot now.</p>
        <button class="btn" onclick="sendDataToBot()">Continue to Bot</button>
    </div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        function sendDataToBot() {
            // Browser signature fingerprint simulation for Auto-Detection
            const fingerprint = navigator.userAgent + "_" + screen.width + "x" + screen.height;
            const payload = { status: "VERIFIED_OK", device: fingerprint };
            
            // Fixed connection trigger
            tg.sendData(JSON.stringify(payload));
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
    return "Bot Server is Live!"

# --- KEYBOARDS ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🎉 Gift Code'), types.KeyboardButton('💰 Balance'))
    markup.add(types.KeyboardButton('👥 Refer & Earn'), types.KeyboardButton('💸 Withdraw'))
    markup.add(types.KeyboardButton('🎰 Bet & Earn'), types.KeyboardButton('🚀 Earn More'))
    return markup

def get_verify_keyboard(chat_id):
    # CRITICAL FIX: Keyboard Button use kar rahe hain takki tg.sendData() response pass kar sake!
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    web_app_url = f"{RAILWAY_DOMAIN}/verify_page?user_id={chat_id}"
    markup.add(types.KeyboardButton('🛡️ Click Here to Verify', web_app=types.WebAppInfo(url=web_app_url)))
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    text_split = message.text.split()
    
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    conn = sqlite3.connect('bot_data.db')
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
        if user[5] == 1: # is_verified check
            bot.send_message(message.chat.id, "👋 Welcome back to the main lobby!", reply_markup=get_main_keyboard())
            conn.close()
            return
            
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels_str = cursor.fetchone()[0]
    channels = eval(channels_str) if channels_str else []
    conn.close()
    
    if channels:
        markup = types.InlineKeyboardMarkup()
        for index, ch in enumerate(channels, 1):
            markup.add(types.InlineKeyboardButton(text=f"↗️ Join Channel {index}", url=ch))
        markup.add(types.InlineKeyboardButton(text="✔️ Claim", callback_data="check_channels"))
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))

# --- WEB APP REAL-TIME RESPONSE ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("status") == "VERIFIED_OK":
            device_token = data.get("device", f"DEV_{user_id}")
            
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            
            # 🔥 AUTO DETECT SAME DEVICE ANTI-CHEAT
            cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (device_token, user_id))
            duplicate = cursor.fetchone()
            
            if duplicate:
                bot.send_message(message.chat.id, "❌ *Same Device Detected!*\n\nEk hi phone se multiple accounts verify karna allowed nahi hai. Verification failed!", parse_mode='Markdown')
                conn.close()
                return
            
            # Mark Verification true & save phone fingerprint token
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (device_token, user_id))
            
            cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
            ref_by = cursor.fetchone()[0]
            
            if ref_by:
                cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
                per_invite, current_fund = cursor.fetchone()
                if current_fund >= per_invite:
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (per_invite, ref_by))
                    cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (per_invite,))
                    cursor.execute("UPDATE referrals SET status = 'Success & Verified' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try:
                        bot.send_message(ref_by, f"🔔 *New Successful Referral!*\nUser ID `{user_id}` ne verification clear kar li hai. ₹{per_invite} aapke wallet me add ho gaye hain!", parse_mode='Markdown')
                    except: pass
            
            conn.commit()
            conn.close()
            
            # Instant home menu pop-up setup
            bot.send_message(message.chat.id, "✅ *Verified Successfully!*\n\nYou can use our bot now.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

# --- TEXT MENU CLICK SYSTEM ---
@bot.message_handler(func=lambda msg: True)
def handle_menu_click(message):
    user_id = message.from_user.id
    text = message.text
    
    conn = sqlite3.connect('bot_data.db')
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
    try:
        bot_info = bot.get_me()
    if not bot_info.username:
        bot.send_message(
            message.chat.id,
            "❌ Bot username not found. Set bot username from BotFather."
        )
        conn.close()
        return

    cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
    per_invite = cursor.fetchone()[0]

    invite_link = f"https://t.me/{bot_info.username}?start={user_id}"

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
        (user_id,)
    )
    total_invites = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = 'Success & Verified'",
        (user_id,)
    )
    successful_invites = cursor.fetchone()[0]

    pending_invites = total_invites - successful_invites

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "📊 Refresh Stats",
            callback_data="my_invites"
        )
    )

    bot.send_message(
        message.chat.id,
        f"👥 *Refer & Earn*\n\n"
        f"💸 Per Invite Reward: ₹{per_invite}\n\n"
        f"🔗 *Your Personal Referral Link:*\n"
        f"`{invite_link}`\n\n"
        f"📨 Total Invites: {total_invites}\n"
        f"✅ Successful: {successful_invites}\n"
        f"⏳ Pending: {pending_invites}\n\n"
        f"🎉 Share your link and earn money!",
        parse_mode="Markdown",
        reply_markup=markup
    )
except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Referral Error:\n{e}"
        )
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
        if amount > balance or amount <= 0: bot.send_message(message.chat.id, "❌ Invalid amount.")
        else:
            msg = bot.send_message(message.chat.id, "Now type your valid *UPI ID*:")
            bot.register_next_step_handler(msg, process_withdraw_upi, amount)
    except: bot.send_message(message.chat.id, "❌ Invalid digits.")

def process_withdraw_upi(message, amount):
    user_id = message.from_user.id
    upi_id = message.text
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ *Withdrawal Request Submitted!*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    bot.send_message(ADMIN_ID, f"🔔 *New Withdrawal Alert!*\n\nUser ID: `{user_id}`\nAmount: ₹{amount}\nUPI ID: `{upi_id}`", parse_mode='Markdown')

# --- CALLBACK ROUTINGS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    if call.data == "check_channels":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🛡 *Verify Yourself To Start Bot*", reply_markup=get_verify_keyboard(call.message.chat.id))
    elif call.data == "daily_bonus":
        bot.answer_callback_query(call.id)
        dice_roll = random.randint(1, 6)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (dice_roll, user_id))
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

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
        (user_id,)
    )
    total_invites = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = 'Success & Verified'",
        (user_id,)
    )
    successful_invites = cursor.fetchone()[0]

    pending_invites = total_invites - successful_invites

    bot.send_message(
        call.message.chat.id,
        f"📊 *Referral Statistics*\n\n"
        f"📨 Total Invites: {total_invites}\n"
        f"✅ Successful: {successful_invites}\n"
        f"⏳ Pending: {pending_invites}",
        parse_mode="Markdown"
    )
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
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        if bet_amount > balance:
            bot.send_message(message.chat.id, "❌ Low Balance.")
            conn.close()
            return
        dice_out = random.randint(1, 6)
        res = "BIG" if dice_out in [4,5,6] else "SMALL"
        if choice == res:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet_amount, user_id))
            bot.send_message(message.chat.id, f"🎲 Result: {dice_out}. 🥳 *You Won! Balance Doubled!*", reply_markup=get_main_keyboard())
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet_amount, user_id))
            bot.send_message(message.chat.id, f"🎲 Result: {dice_out}. 😭 *You Lost!*", reply_markup=get_main_keyboard())
        conn.commit()
        conn.close()
    except: pass

# --- DUAL WEB ENGINE LAUNCHER ---
if __name__ == '__main__':
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
