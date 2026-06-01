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

# --- DATABASE ENGINE ---
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

# --- WEB APP RECEPTION INTERFACE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        const tg = window.Telegram.WebApp; tg.expand();
        function sendDataToBot() {
            const fingerprint = navigator.userAgent + "_" + screen.width + "x" + screen.height;
            tg.sendData(JSON.stringify({ status: "VERIFIED_OK", device: fingerprint }));
            tg.close();
        }
    </script>
</body>
</html>
"""

@app.route('/verify_page')
def verify_page(): return render_template_string(HTML_TEMPLATE)
@app.route('/')
def home(): return "Bot Web Stack Running!"

# --- TELEGRAM KEYBOARDS (EXACT 6 BUTTONS ONLY) ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🎉 Gift Code'), types.KeyboardButton('💰 Balance'))
    markup.add(types.KeyboardButton('👥 Refer & Earn'), types.KeyboardButton('💸 Withdraw'))
    markup.add(types.KeyboardButton('🎰 Bet & Earn'), types.KeyboardButton('🚀 Earn More'))
    return markup

def get_verify_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    url = f"{RAILWAY_DOMAIN}/verify_page?user_id={chat_id}"
    markup.add(types.KeyboardButton('🛡️ Click Here to Verify', web_app=types.WebAppInfo(url=url)))
    return markup

# --- CORE USER FLOW ---
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
            cursor.execute("INSERT INTO referrals (referrer_id, referee_id, status) VALUES (?, ?, 'Started (Unverified)')", (referrer, user_id))
        conn.commit()
    else:
        if user[5] == 1:
            bot.send_message(message.chat.id, "👋 Welcome back to the main dashboard!", reply_markup=get_main_keyboard())
            conn.close()
            return
            
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels = eval(cursor.fetchone()[0])
    conn.close()
    
    if channels:
        markup = types.InlineKeyboardMarkup()
        for idx, ch in enumerate(channels, 1):
            markup.add(types.InlineKeyboardButton(text=f"↗️ Join Channel {idx}", url=ch))
        markup.add(types.InlineKeyboardButton(text="✔️ Claim", callback_data="check_channels"))
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=get_verify_keyboard(message.chat.id))

# --- WEB APP RECEPTION + SAME DEVICE BLOCK ENGINE ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("status") == "VERIFIED_OK":
            device_token = data.get("device", f"DEV_{user_id}")
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            
            # Anti-Cheat Match check
            cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (device_token, user_id))
            duplicate = cursor.fetchone()
            if duplicate:
                bot.send_message(message.chat.id, "❌ *Same Device Detected!*\n\nMultiple accounts are restricted on this device. Verification Failed!", parse_mode='Markdown')
                conn.close()
                return
            
            cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (device_token, user_id))
            cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
            ref_by = cursor.fetchone()[0]
            
            if ref_by:
                cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
                per_invite, current_fund = cursor.fetchone()
                if current_fund >= per_invite:
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (per_invite, ref_by))
                    cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (per_invite,))
                    cursor.execute("UPDATE referrals SET status = 'Success' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
                    try:
                        bot.send_message(ref_by, f"🔔 *New Referral Success!*\nUser ID `{user_id}` verified. +₹{per_invite} added!", parse_mode='Markdown')
                    except: pass
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ *Verified Successfully!*\nYou can use our bot now.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    except: pass

# --- UI INTERFACE CORE BUTTON CLICKS ---
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
        bot.send_message(message.chat.id, "🛡️ Please complete your verification first:", reply_markup=get_verify_keyboard(message.chat.id))
        return

    balance = user_status[1]

    # 1. GIFT CODE (2 Options Only)
    if text == '🎉 Gift Code':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧭 Daily Bonus", callback_data="daily_bonus"), types.InlineKeyboardButton("🎁 Gift Code", callback_data="gift_code_prompt"))
        bot.send_message(message.chat.id, "✨ *Choose One:*", parse_mode='Markdown', reply_markup=markup)

    # 2. BALANCE (With history & global pool tracker)
    elif text == '💰 Balance':
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        bot_fund = cursor.fetchone()[0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history"), types.InlineKeyboardButton("💸 Bot Fund", callback_data="view_bot_fund"))
        bot.send_message(message.chat.id, f"💰 *Balance: ₹{balance:.2f}*\n\n🎉 Use 'Withdraw' Button to Withdraw The Balance!", parse_mode='Markdown', reply_markup=markup)

    # 3. REFER & EARN (No contest button - 2 Options left)
    elif text == '👥 Refer & Earn':
        cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
        per_invite = cursor.fetchone()[0]
        invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 My Invites", callback_data="my_invites"), types.InlineKeyboardButton("👥 Refer Tracker", callback_data="refer_tracker"))
        bot.send_message(message.chat.id, f"🎁 *Per Invite ₹{int(per_invite)} UPI Cash !!*\n\n🎁 *Invite Link :* {invite_link}\n\n_*Share Your Own Invite Link To Earn Unlimited Easy Cash! 💵*_", parse_mode='Markdown', reply_markup=markup)

    # 4. WITHDRAW SYSTEM FLOW
    elif text == '💸 Withdraw':
        cursor.execute("SELECT min_withdraw FROM settings WHERE id = 1")
        min_w = cursor.fetchone()[0]
        if balance < min_w:
            bot.send_message(message.chat.id, f"🤑 *You need minimum {int(min_w)} in balance to withdraw*", parse_mode='Markdown')
        else:
            msg = bot.send_message(message.chat.id, "Please type the *Amount* you want to withdraw:")
            bot.register_next_step_handler(msg, process_withdraw_amount, balance)

    # 5. BET & EARN ARENA (Ludo + Wingo Only)
    elif text == '🎰 Bet & Earn':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎲 Ludo", callback_data="game_ludo"), types.InlineKeyboardButton("🟢 Wingo 🔴", callback_data="game_wingo"))
        bot.send_message(message.chat.id, "🎰 *Welcome to Bet & Earn Arena!*\nWin Big Cash & Have Fun!\n\n🎮 *Choose Your Game :*", parse_mode='Markdown', reply_markup=markup)

    # 6. DYNAMIC EARN MORE
    elif text == '🚀 Earn More':
        cursor.execute("SELECT earn_more_link FROM settings WHERE id = 1")
        link = cursor.fetchone()[0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Visit Now", url=link))
        bot.send_message(message.chat.id, "🚀 Click the button below to complete tasks and earn more cash!", reply_markup=markup)
    conn.close()

# --- FINANCIAL WITHDRAWAL TRACK PROCESSING ---
def process_withdraw_amount(message, balance):
    try:
        amount = float(message.text)
        if amount > balance or amount <= 0: bot.send_message(message.chat.id, "❌ Invalid amount limit.")
        else:
            msg = bot.send_message(message.chat.id, "Now type your valid *UPI ID*:")
            bot.register_next_step_handler(msg, process_withdraw_upi, amount)
    except: bot.send_message(message.chat.id, "❌ Numbers digits only.")

def process_withdraw_upi(message, amount):
    user_id = message.from_user.id
    upi_id = message.text
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ *Withdrawal Request Submitted Successfully!*\nStatus: Pending Admin Approval.", parse_mode='Markdown', reply_markup=get_main_keyboard())
    bot.send_message(ADMIN_ID, f"🔔 *New Withdrawal Request!*\nUser: `{user_id}`\nAmount: ₹{amount}\nUPI: `{upi_id}`\nAction: `/approve {amount}` / `/reject`", parse_mode='Markdown')

# --- CALLBACK ROUTER DATA DECK ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    if call.data == "check_channels":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🛡️ *Verify Yourself To Start Bot*", reply_markup=get_verify_keyboard(call.message.chat.id))
    
    elif call.data == "daily_bonus":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
        last_t = cursor.fetchone()[0]
        now = datetime.now()
        if last_t and now < datetime.strptime(last_t, '%Y-%m-%d %H:%M:%S') + timedelta(hours=24):
            bot.send_message(call.message.chat.id, "⏳ Bonus locked! Available every 24 hours.")
            conn.close()
            return
        dice = random.randint(1, 6)
        cursor.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", (dice, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        bot.send_message(call.message.chat.id, f"🎲 *Dice Rolled!* You got number *{dice}* added to your balance!", parse_mode='Markdown')

    elif call.data == "view_bot_fund":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        bot.send_message(call.message.chat.id, f"🎁 *Total Fund Of The Bot >>* ₹1,00,000\n🟢 *Remaining Fund >>* ₹{cursor.fetchone()[0]:.2f}", parse_mode='Markdown')

    elif call.data == "w_history":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT amount, upi_id, status FROM withdraws WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        hist = cursor.fetchall()
        msg = "📝 *Your Withdrawal History:*\n\n" if hist else "📝 No withdrawal requests found."
        for row in hist: msg += f"🪙 Amount: ₹{row[0]} | UPI: `{row[1]}` | *{row[2]}*\n"
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

    elif call.data == "my_invites":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status='Success'", (user_id,))
        sc = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status!='Success'", (user_id,))
        un = cursor.fetchone()[0]
        bot.send_message(call.message.chat.id, f"🚀 *Your Analytics:*\nVerified Invites: `{sc}`\nLeft/Unverified: `{un}`", parse_mode='Markdown')

    elif call.data == "refer_tracker":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT referee_id, status FROM referrals WHERE referrer_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        rows = cursor.fetchall()
        msg = "👥 *Live Referral Track Info:*\n\n" if rows else "No records found."
        for r in rows: msg += f"• User `{r[0]}` -> Status: *{r[1]}*\n"
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

    # --- LUDO GAME BUTTON ENGINE ---
    elif call.data == "game_ludo":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔴 Big (4, 5, 6)", callback_data="l_big"), types.InlineKeyboardButton("🔵 Small (1, 2, 3)", callback_data="l_small"))
        bot.send_message(call.message.chat.id, "🎲 *LUDO ARENA*\nIf You Win Increased Your Balance Double (2x Payout)\n\nSelect variant:", parse_mode='Markdown', reply_markup=markup)

    elif call.data in ["l_big", "l_small"]:
        bot.answer_callback_query(call.id)
        choice = "BIG" if call.data == "l_big" else "SMALL"
        msg = bot.send_message(call.message.chat.id, f"💬 Enter bet amount for *{choice}*:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_ludo_calculation, choice)

    # --- WINGO COLOR MATH GAME ENGINE ---
    elif call.data == "game_wingo":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🟢 Green", callback_data="w_green"), types.InlineKeyboardButton("🔴 Red", callback_data="w_red"))
        bot.send_message(call.message.chat.id, "🟢 *WINGO ARENA* 🔴\nPredict color option to double your balance cash asset pool!", parse_mode='Markdown', reply_markup=markup)

    elif call.data in ["w_green", "w_red"]:
        bot.answer_callback_query(call.id)
        choice = "GREEN" if call.data == "w_green" else "RED"
        msg = bot.send_message(call.message.chat.id, f"💬 Enter bet amount for Wingo *{choice}*:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_wingo_calculation, choice)
    conn.close()

# --- GAME ENGINE CALCULATOR LOGICS ---
def process_ludo_calculation(message, choice):
    user_id = message.from_user.id
    try:
        bet = float(message.text)
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        if bet > bal or bet <= 0:
            bot.send_message(message.chat.id, "❌ Low balance limits.")
            conn.close()
            return
        
        dice = random.randint(1, 6)
        res = "BIG" if dice in [4, 5, 6] else "SMALL"
        bot.send_message(message.chat.id, f"🎲 Rolling... Result is *{dice}* ({res})", parse_mode='Markdown')
        
        if choice == res:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (bet,))
            bot.send_message(message.chat.id, f"🥳 *Whohoo! You Won!* Balance doubled: +₹{bet * 2}", reply_markup=get_main_keyboard())
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund + ? WHERE id = 1", (bet,))
            bot.send_message(message.chat.id, f"😭 *You Lost!* ₹{bet} shifted to bot fund.", reply_markup=get_main_keyboard())
        conn.commit()
        conn.close()
    except: pass

def process_wingo_calculation(message, choice):
    user_id = message.from_user.id
    try:
        bet = float(message.text)
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        if bet > bal or bet <= 0:
            bot.send_message(message.chat.id, "❌ Low balance limits.")
            conn.close()
            return
        
        res = random.choice(["GREEN", "RED"])
        bot.send_message(message.chat.id, f"🎰 Wingo Slot Stop! Result color is *{res}*", parse_mode='Markdown')
        
        if choice == res:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (bet,))
            bot.send_message(message.chat.id, f"🥳 *Whohoo! Color Matched!* Received +₹{bet * 2}", reply_markup=get_main_keyboard())
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund + ? WHERE id = 1", (bet,))
            bot.send_message(message.chat.id, f"😭 *You Lost!* Wingo deducted ₹{bet}.", reply_markup=get_main_keyboard())
        conn.commit()
        conn.close()
    except: pass

# --- CONTROL ADMIN CODES PANEL ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    msg = ("🛠️ *Admin Master Dashboard Panel*\n\n"
           "`/setinvite <val>` - Set per invite reward cash asset\n"
           "`/setminwd <val>` - Threshold limit withdrawal\n"
           "`/setfund <val>` - Core balance pool refill topup\n"
           "`/setlink <url>` - Set dynamice Target Earn More link channel\n"
           "`/broadcast <msg>` - Blast notification alert message to everyone\n"
           "`/approve <wd_id>` - Dispatch success asset payout trigger\n"
           "`/reject <wd_id>` - Roll back cash ledger logs data")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['setinvite', 'setminwd', 'setfund', 'setlink', 'broadcast', 'approve', 'reject'])
def handle_admin_commands(message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.text.split()[0]
    args = message.text.replace(cmd, "").strip()
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    if cmd == '/setinvite' and args:
        cursor.execute("UPDATE settings SET per_invite = ? WHERE id = 1", (float(args),))
        bot.send_message(message.chat.id, f"✅ Per Invite amount set to ₹{args}")
    elif cmd == '/setminwd' and args:
        cursor.execute("UPDATE settings SET min_withdraw = ? WHERE id = 1", (float(args),))
        bot.send_message(message.chat.id, f"✅ Min Withdraw target set to ₹{args}")
    elif cmd == '/setfund' and args:
        cursor.execute("UPDATE settings SET bot_fund = ? WHERE id = 1", (float(args),))
        bot.send_message(message.chat.id, f"✅ Bot Fund level shifted to ₹{args}")
    elif cmd == '/setlink' and args:
        cursor.execute("UPDATE settings SET earn_more_link = ? WHERE id = 1", (args,))
        bot.send_message(message.chat.id, f"✅ Earn More interface link updated!")
    elif cmd == '/broadcast' and args:
        cursor.execute("SELECT user_id FROM users")
        for u in cursor.fetchall():
            try: bot.send_message(u[0], f"📢 *Global Alert Notice:*\n\n{args}", parse_mode='Markdown')
            except: pass
        bot.send_message(message.chat.id, "✅ Broadcast message dispatched successfully to everyone!")
    elif cmd == '/approve' and args:
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (int(args),))
        r = cursor.fetchone()
        if r:
            cursor.execute("UPDATE withdraws SET status = 'Success' WHERE id = ?", (int(args),))
            bot.send_message(r[0], "🥳 *Whohoo your Money transfer To Your UPI Wallet Keep Support ( Raka )* 🔥", parse_mode='Markdown')
            bot.send_message(message.chat.id, "✅ Payout completed successfully!")
    elif cmd == '/reject' and args:
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (int(args),))
        r = cursor.fetchone()
        if r:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (r[1], r[0]))
            cursor.execute("UPDATE withdraws SET status = 'Rejected' WHERE id = ?", (int(args),))
            bot.send_message(r[0], "❌ *Your withdrawal request was rejected.* Assets returned.")
            bot.send_message(message.chat.id, "❌ Transaction logs updated as Rejected.")
            
    conn.commit()
    conn.close()

# --- WEB SERVER INTERFACE TRIGGER LISTENER ---
if __name__ == '__main__':
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
