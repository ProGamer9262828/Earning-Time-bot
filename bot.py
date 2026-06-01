import sqlite3
import random
import telebot
from telebot import types
from datetime import datetime, timedelta

# --- CONFIGURATION ---
BOT_TOKEN = "8473027179:AAF-9rouF_79QAZRNLIeDnHNgg3-VPeq1RQ"
ADMIN_ID = 8031127296

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY, per_invite REAL, min_withdraw REAL, 
                        bot_fund REAL, earn_more_link TEXT, mandatory_channels TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, 
                        referred_by INTEGER, is_verified INTEGER DEFAULT 0, last_bonus_time TEXT)''')
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

# --- KEYBOARDS ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🎉 Gift Code'), types.KeyboardButton('💰 Balance'))
    markup.add(types.KeyboardButton('👥 Refer & Earn'), types.KeyboardButton('💸 Withdraw'))
    markup.add(types.KeyboardButton('🎰 Bet & Earn'), types.KeyboardButton('🚀 Earn More'))
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    text_split = message.text.split()
    
    # Sabse pehle purane saare fansi hue states ko flush karke khatam karo
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referrer = int(text_split[1]) if (len(text_split) > 1 and text_split[1].isdigit()) else None
        if referrer == user_id:
            referrer = None

        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referrer))
        if referrer:
            cursor.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (referrer, user_id))
        conn.commit()
    else:
        # Agar user pehle se registered hai aur verified hai, toh seedha menu do
        if user[4] == 1:
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
        bot.send_message(message.chat.id, "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*", 
                         parse_mode='Markdown', reply_markup=markup)
    else:
        ask_verification(message.chat.id)

def ask_verification(chat_id):
    # Unverified banday ke screen se normal keyboard clear kar do taaki kachra click na ho
    hide_keyboard = types.ReplyKeyboardRemove()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🛡️ Click Here to Verify", callback_data="trigger_captcha"))
    bot.send_message(chat_id, "🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=markup, reply_to_message_id=None)

# --- CAPTCHA VALIDATION SYSTEM ---
def verify_captcha_answer(message, correct_ans):
    user_id = message.from_user.id
    text = message.text
    
    if text and text.startswith('/start'):
        start(message)
        return

    try:
        user_ans = int(text)
        if user_ans == correct_ans:
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
            
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
                    except:
                        pass
            
            conn.commit()
            conn.close()
            
            # CRITICAL FIX: Sahi answer par get_main_keyboard bhej rahe hain jisse buttons open honge!
            bot.send_message(message.chat.id, "✅ *Verified Successfully!*\n\nYou can use our bot now.", reply_markup=get_main_keyboard(), parse_mode='Markdown')
        else:
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            msg = bot.send_message(message.chat.id, f"❌ *Wrong Answer!* Try again carefully:\n👉 *{num1} + {num2} = ?*", parse_mode='Markdown')
            bot.register_next_step_handler(msg, verify_captcha_answer, (num1+num2))
    except (ValueError, TypeError):
        msg = bot.send_message(message.chat.id, "🔢 Please enter a numeric answer only:")
        bot.register_next_step_handler(msg, verify_captcha_answer, correct_ans)

# --- TEXT BUTTONS HANDLING ---
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
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
        ask_verification(message.chat.id)
        return

    balance = user_status[1]

    if text == '🎉 Gift Code':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧭 Daily Bonus", callback_data="daily_bonus"))
        markup.add(types.InlineKeyboardButton("🎁 Gift Code", callback_data="claim_gift_code"))
        bot.send_message(message.chat.id, "✨ *Choose One:*", parse_mode='Markdown', reply_markup=markup)

    elif text == '💰 Balance':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history"))
        markup.add(types.InlineKeyboardButton("💸 Bot Fund", callback_data="view_bot_fund"))
        bot.send_message(message.chat.id, f"💰 *Balance: ₹{balance:.2f}*\n\n🎉 Use 'Withdraw' Button to Withdraw The Balance!", 
                         parse_mode='Markdown', reply_markup=markup)

    elif text == '👥 Refer & Earn':
        cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
        per_invite = cursor.fetchone()[0]
        invite_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 My Invites", callback_data="my_invites"), 
                   types.InlineKeyboardButton("👥 Refer Tracker", callback_data="refer_tracker"))
        bot.send_message(message.chat.id, f"🎁 *Per Invite ₹{int(per_invite)} UPI Cash !!*\n\n"
                                          f"🎁 *Invite Link :* {invite_link}\n\n"
                                          f"_*Share Your Own Invite Link To Earn Unlimited Easy Cash! 💵*_", 
                         parse_mode='Markdown', reply_markup=markup)

    elif text == '💸 Withdraw':
        cursor.execute("SELECT min_withdraw FROM settings WHERE id = 1")
        min_w = cursor.fetchone()[0]
        if balance < min_w:
            bot.send_message(message.chat.id, f"🤑 *You need minimum {int(min_w)} in balance to withdraw*", parse_mode='Markdown')
        else:
            msg = bot.send_message(message.chat.id, "Please type the *Amount* you want to withdraw:", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_withdraw_amount, balance)

    elif text == '🎰 Bet & Earn':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎲 Ludo", callback_data="game_ludo"))
        markup.add(types.InlineKeyboardButton("🟢 Wingo 🔴", callback_data="game_wingo"))
        bot.send_message(message.chat.id, "🎰 *Welcome to Bet & Earn Arena!*\nWin Big Cash & Have Fun!\n\n🎮 *Choose Your Game :*", 
                         parse_mode='Markdown', reply_markup=markup)

    elif text == '🚀 Earn More':
        cursor.execute("SELECT earn_more_link FROM settings WHERE id = 1")
        link = cursor.fetchone()[0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Visit Now", url=link))
        bot.send_message(message.chat.id, "🚀 Click the button below to complete tasks and earn more cash!", reply_markup=markup)

    conn.close()

# --- WITHDRAW FLOW ---
def process_withdraw_amount(message, balance):
    if message.text and message.text.startswith('/start'):
        start(message)
        return
    try:
        amount = float(message.text)
        if amount > balance or amount <= 0:
            bot.send_message(message.chat.id, "❌ Invalid amount or insufficient balance.")
        else:
            msg = bot.send_message(message.chat.id, "Now type your valid *UPI ID* to receive payment:", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_withdraw_upi, amount)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter valid digits.")

def process_withdraw_upi(message, amount):
    if message.text and message.text.startswith('/start'):
        start(message)
        return
    user_id = message.from_user.id
    upi_id = message.text
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ *Withdrawal Request Submitted!* Status: Pending Admin Approval.", parse_mode='Markdown', reply_markup=get_main_keyboard())
    bot.send_message(ADMIN_ID, f"🔔 *New Withdrawal Alert!*\n\nUser ID: `{user_id}`\nAmount: ₹{amount}\nUPI ID: `{upi_id}`\n\nApprove via `/approve <ID>` command.", parse_mode='Markdown')

# --- INLINE CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    if call.data == "check_channels":
        bot.answer_callback_query(call.id)
        ask_verification(call.message.chat.id)

    elif call.data == "daily_bonus":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
        last_time_str = cursor.fetchone()[0]
        now = datetime.now()
        
        if last_time_str:
            last_time = datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
            if now < last_time + timedelta(hours=24):
                remaining = (last_time + timedelta(hours=24)) - now
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                bot.send_message(call.message.chat.id, f"⏳ Daily Bonus is locked! Try again after *{hours}h {minutes}m*.", parse_mode='Markdown')
                conn.close()
                return
                
        dice_roll = random.randint(1, 6)
        cursor.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", (dice_roll, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        bot.send_message(call.message.chat.id, f"🎲 *Dice Rolled!* You got number *{dice_roll}*.\n₹{dice_roll} added to your balance!", parse_mode='Markdown')

    elif call.data == "view_bot_fund":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        fund = cursor.fetchone()[0]
        bot.send_message(call.message.chat.id, f"🎁 *Total Fund Of The Bot >>* ₹1,00,000\n🟢 *Remaining Fund >>* ₹{fund:.2f}", parse_mode='Markdown')

    elif call.data == "w_history":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT amount, upi_id, status FROM withdraws WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        hist = cursor.fetchall()
        if not hist:
            bot.send_message(call.message.chat.id, "📝 No withdrawal records found.")
        else:
            msg = "📝 *Your Last 5 Withdrawals:*\n\n"
            for item in hist:
                msg += f"💰 Amount: ₹{item[0]} | UPI: `{item[1]}`\nStatus: *{item[2]}*\n\n"
            bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

    elif call.data == "my_invites":
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT COUNT(*), status FROM referrals WHERE referrer_id = ? GROUP BY status", (user_id,))
        rows = cursor.fetchall()
        msg = "🚀 *Your Invitation Summary Track Status:*\n\n"
        if not rows:
            msg += "No referral transactions recorded."
        for row in rows:
            msg += f"• {row[1]}: *{row[0]} users*\n"
        bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

    elif call.data == "game_ludo":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔴 Big (4, 5, 6)", callback_data="ludo_big"),
                   types.InlineKeyboardButton("🔵 Small (1, 2, 3)", callback_data="ludo_small"))
        bot.send_message(call.message.chat.id, "🎲 *LUDO DICE BETTING*\n\nIf You Win Increased Your Balance Double! (2x Return)\n\nSelect your predict bucket:", parse_mode='Markdown', reply_markup=markup)

    elif call.data in ["ludo_big", "ludo_small"]:
        bot.answer_callback_query(call.id)
        choice = "BIG" if call.data == "ludo_big" else "SMALL"
        msg = bot.send_message(call.message.chat.id, f"💬 Enter the amount you want to bet on *{choice}*:")
        bot.register_next_step_handler(msg, process_ludo_bet, choice)

    conn.close()

# --- LUDO GAME CALCULATION ---
def process_ludo_bet(message, choice):
    if message.text and message.text.startswith('/start'):
        start(message)
        return
    user_id = message.from_user.id
    try:
        bet_amount = float(message.text)
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        
        if bet_amount > balance or bet_amount <= 0:
            bot.send_message(message.chat.id, "❌ Invalid bet balance limit reached.")
            conn.close()
            return

        dice_out = random.randint(1, 6)
        result_bucket = "BIG" if dice_out in [4, 5, 6] else "SMALL"
        bot.send_message(message.chat.id, f"🎲 Rolling Dice... Result is: *{dice_out}* ({result_bucket})", parse_mode='Markdown')
        
        if choice == result_bucket:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet_amount, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (bet_amount,))
            bot.send_message(message.chat.id, f"🥳 *Whohoo! You Won!*\n₹{bet_amount * 2} credited successfully (Double mapping!).", parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet_amount, user_id))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund + ? WHERE id = 1", (bet_amount,))
            bot.send_message(message.chat.id, f"😭 *You Lost the Bet!*\n₹{bet_amount} cut down from wallet balances.", parse_mode='Markdown', reply_markup=get_main_keyboard())
            
        conn.commit()
        conn.close()
    except ValueError:
        bot.send_message(message.chat.id, "❌ Numerical values only.")

# --- ADMIN CONTROLS ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    msg = ("🛠️ *Welcome To Admin Panel Command Desk*\n\n"
           "`/approve <wd_id>` - Complete user transaction\n"
           "`/reject <wd_id>` - Return user money back to wallet")
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['approve'])
def admin_approve(message):
    if message.from_user.id != ADMIN_ID: return
    text_split = message.text.split()
    if len(text_split) > 1:
        wd_id = int(text_split[1])
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (wd_id,))
        req = cursor.fetchone()
        if req:
            cursor.execute("UPDATE withdraws SET status = 'Success' WHERE id = ?", (wd_id,))
            conn.commit()
            bot.send_message(req[0], "🥳 *Whohoo your Money transfer To Your UPI Wallet Keep Support ( Raka )* 🔥", parse_mode='Markdown')
            bot.send_message(message.chat.id, "✅ Payout approved successfully!")
        conn.close()

@bot.message_handler(commands=['reject'])
def admin_reject(message):
    if message.from_user.id != ADMIN_ID: return
    text_split = message.text.split()
    if len(text_split) > 1:
        wd_id = int(text_split[1])
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (wd_id,))
        req = cursor.fetchone()
        if req:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (req[1], req[0]))
            cursor.execute("UPDATE withdraws SET status = 'Rejected' WHERE id = ?", (wd_id,))
            conn.commit()
            bot.send_message(req[0], "❌ *Your withdrawal request was rejected.* Fund added back.")
            bot.send_message(message.chat.id, "❌ Request rejected. Balance restored.")
        conn.close()

# --- START BOT ---
bot.infinity_polling()
