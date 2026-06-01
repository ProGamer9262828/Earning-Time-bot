import sqlite3
import random
from datetime import datetime, timedelta
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext

# --- EXCLUSIVE CONFIGURATION FIT ---
BOT_TOKEN = "8473027179:AAF-9rouF_79QAZRNLIeDnHNgg3-VPeq1RQ"
ADMIN_ID = 8031127296

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Global Admin Settings Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY,
                        per_invite REAL,
                        min_withdraw REAL,
                        bot_fund REAL,
                        earn_more_link TEXT,
                        mandatory_channels TEXT)''')
    
    # User Profile Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        balance REAL DEFAULT 0.0,
                        referred_by INTEGER,
                        device_token TEXT,
                        is_verified INTEGER DEFAULT 0,
                        last_bonus_time TEXT)''')
    
    # Referral Tracking Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER,
                        referee_id INTEGER,
                        status TEXT DEFAULT 'Started (Unverified)')''')
    
    # Withdraw Requests Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS withdraws (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        amount REAL,
                        upi_id TEXT,
                        status TEXT DEFAULT 'Pending')''')
    
    # Default values initialize if empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        # Default 5 INR per invite, 20 INR min withdraw, 1 Lakh starting fund
        cursor.execute("INSERT INTO settings VALUES (1, 5.0, 20.0, 100000.0, 'https://t.me/your_channel', '[]')")
    
    conn.commit()
    conn.close()

init_db()

# --- KEYBOARDS & NAVIGATION (Screenshot 19680.jpg) ---
def get_main_keyboard():
    # Removed "Payout Method", total 6 options + 1 Earn More
    keyboard = [
        ['🎉 Gift Code', '💰 Balance'],
        ['👥 Refer & Earn', '💸 Withdraw'],
        ['🎰 Bet & Earn', '🚀 Earn More']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START COMMAND (Screenshot 19678.jpg) ---
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # User registration if new
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referrer = int(args[0]) if (args and args[0].isdigit()) else None
        cursor.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referrer))
        if referrer:
            cursor.execute("INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)", (referrer, user_id))
        conn.commit()
    
    # Mandatory Channels Fetching from Admin Panel
    cursor.execute("SELECT mandatory_channels FROM settings WHERE id = 1")
    channels_str = cursor.fetchone()[0]
    channels = eval(channels_str) if channels_str else []
    conn.close()
    
    if channels:
        keyboard = []
        for index, ch in enumerate(channels, 1):
            keyboard.append([InlineKeyboardButton(f"↗️ Join Channel {index}", url=ch)])
        keyboard.append([InlineKeyboardButton("✔️ Claim", callback_data="check_channels")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*", 
                                  parse_mode='Markdown', reply_markup=reply_markup)
    else:
        ask_verification(update.message, context)

# --- CHANNELS CHECK & WEB VERIFICATION (Screenshot 19678.jpg & 19679.jpg) ---
def check_channels(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    ask_verification(query.message, context)

def ask_verification(message, context):
    user_id = message.chat_id
    # Simulation device routing link (Aap is link ko apne server panel se connect kar sakte hain)
    verify_url = f"https://yourdomain.com/verify?user_id={user_id}" 
    
    keyboard = [[InlineKeyboardButton("🛡️ Verify", url=verify_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message.reply_text("🛡️ *Verify Yourself To Start Bot*", parse_mode='Markdown', reply_markup=reply_markup)

# --- WEB PANEL SIMULATION CORE LOGIC (Anti-Cheat) ---
def complete_verification(user_id, client_device_fingerprint):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Anti-cheat duplicate login protection
    cursor.execute("SELECT user_id FROM users WHERE device_token = ? AND user_id != ?", (client_device_fingerprint, user_id))
    duplicate = cursor.fetchone()
    
    if duplicate:
        conn.close()
        return "Same device detected. Verification Failed! ❌"
    
    cursor.execute("UPDATE users SET is_verified = 1, device_token = ? WHERE user_id = ?", (client_device_fingerprint, user_id))
    
    # Process referral track instantly
    cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    ref_by = cursor.fetchone()[0]
    
    if ref_by:
        cursor.execute("SELECT per_invite, bot_fund FROM settings WHERE id = 1")
        per_invite, current_fund = cursor.fetchone()
        
        if current_fund >= per_invite:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (per_invite, ref_by))
            cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (per_invite,))
            cursor.execute("UPDATE referrals SET status = 'Success & Verified' WHERE referrer_id = ? AND referee_id = ?", (ref_by, user_id))
            
    conn.commit()
    conn.close()
    return "Verified Successfully! Click CONTINUE TO BOT."

# --- BOT MENU HANDLING FUNCTIONS ---
def handle_messages(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified, balance FROM users WHERE user_id = ?", (user_id,))
    user_status = cursor.fetchone()
    
    if not user_status or user_status[0] == 0:
        # User is testing dashboard without verification clearance
        update.message.reply_text("❌ Please complete your web verification first!")
        conn.close()
        return

    balance = user_status[1]

    # 1. GIFT CODE ACTION (Screenshot 19681.jpg)
    if text == '🎉 Gift Code':
        keyboard = [
            [InlineKeyboardButton("🧭 Daily Bonus", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 Gift Code", callback_data="claim_gift_code")]
        ]
        update.message.reply_text("✨ *Choose One:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # 2. BALANCE ACTION (Screenshot 19681.jpg)
    elif text == '💰 Balance':
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        bot_fund = cursor.fetchone()[0]
        
        keyboard = [
            [InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history")],
            [InlineKeyboardButton("💸 Bot Fund", callback_data="view_bot_fund")]
        ]
        update.message.reply_text(f"💰 *Balance: ₹{balance:.2f}*\n\n🎉 Use 'Withdraw' Button to Withdraw The Balance!", 
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # 3. REFER & EARN ACTION (Screenshot 19682.jpg)
    elif text == '👥 Refer & Earn':
        cursor.execute("SELECT per_invite FROM settings WHERE id = 1")
        per_invite = cursor.fetchone()[0]
        
        bot_username = context.bot.username
        invite_link = f"https://t.me/{bot_username}?start={user_id}"
        
        keyboard = [
            [InlineKeyboardButton("🚀 My Invites", callback_data="my_invites"), 
             InlineKeyboardButton("👥 Refer Tracker", callback_data="refer_tracker")]
        ]
        update.message.reply_text(f"🎁 *Per Invite ₹{int(per_invite)} UPI Cash !!*\n\n"
                                  f"🎁 *Invite Link :* {invite_link}\n\n"
                                  f"_*Share Your Own Invite Link To Earn Unlimited Easy Cash! 💵*_", 
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # 4. WITHDRAW ACTIONS
    elif text == '💸 Withdraw':
        cursor.execute("SELECT min_withdraw FROM settings WHERE id = 1")
        min_w = cursor.fetchone()[0]
        
        if balance < min_w:
            update.message.reply_text(f"🤑 *You need minimum {int(min_w)} in balance to withdraw*", parse_mode='Markdown')
        else:
            update.message.reply_text("Please type the *Amount* you want to withdraw:", parse_mode='Markdown')
            context.user_data['state'] = 'AWAITING_WITHDRAW_AMOUNT'

    # 5. BET & EARN ACTION (Screenshot 19683.jpg)
    elif text == '🎰 Bet & Earn':
        keyboard = [
            [InlineKeyboardButton("🎲 Ludo", callback_data="game_ludo")],
            [InlineKeyboardButton("🟢 Wingo 🔴", callback_data="game_wingo")]
        ]
        update.message.reply_text("🎰 *Welcome to Bet & Earn Arena!*\nWin Big Cash & Have Fun!\n\n🎮 *Choose Your Game :*", 
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # 6. DYNAMIC EARN MORE HANDLER
    elif text == '🚀 Earn More':
        cursor.execute("SELECT earn_more_link FROM settings WHERE id = 1")
        link = cursor.fetchone()[0]
        keyboard = [[InlineKeyboardButton("🔗 Visit Now", url=link)]]
        update.message.reply_text("🚀 Click the button below to complete tasks and earn more cash!", reply_markup=InlineKeyboardMarkup(keyboard))

    # STATE ROUTER MANAGEMENT
    elif context.user_data.get('state') == 'AWAITING_WITHDRAW_AMOUNT':
        try:
            amount = float(text)
            if amount > balance or amount <= 0:
                update.message.reply_text("❌ Invalid amount or insufficient balance.")
                context.user_data.clear()
            else:
                context.user_data['w_amount'] = amount
                update.message.reply_text("Now type your valid *UPI ID* to receive payment:", parse_mode='Markdown')
                context.user_data['state'] = 'AWAITING_UPI_ID'
        except ValueError:
            update.message.reply_text("❌ Please enter valid digits.")

    elif context.user_data.get('state') == 'AWAITING_UPI_ID':
        upi_id = text
        amount = context.user_data['w_amount']
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("INSERT INTO withdraws (user_id, amount, upi_id) VALUES (?, ?, ?)", (user_id, amount, upi_id))
        conn.commit()
        
        update.message.reply_text("✅ *Withdrawal Request Submitted!* Status: Pending Admin Approval.", parse_mode='Markdown', reply_markup=get_main_keyboard())
        
        # Fire Notification Alert to Admin Panel Directly
        context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 *New Withdrawal Alert!*\n\nUser ID: `{user_id}`\nAmount: ₹{amount}\nUPI ID: `{upi_id}`\n\nApprove execution via `/approve <ID>` command.", parse_mode='Markdown')
        context.user_data.clear()

    elif context.user_data.get('state') in ['LUDO_BET_BIG', 'LUDO_BET_SMALL']:
        try:
            bet_amount = float(text)
            if bet_amount > balance or bet_amount <= 0:
                update.message.reply_text("❌ Invalid bet balance limit reached.")
                context.user_data.clear()
                conn.close()
                return
                
            choice = "BIG" if context.user_data['state'] == 'LUDO_BET_BIG' else "SMALL"
            execute_ludo_dice_roll(update, context, user_id, bet_amount, choice)
        except ValueError:
            update.message.reply_text("❌ Numerical limits are only allowed.")
            
    conn.close()

# --- CALLBACKS & ROUTERS DECK ---
def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    query.answer()
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    if data == "daily_bonus":
        cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
        last_time_str = cursor.fetchone()[0]
        
        now = datetime.now()
        if last_time_str:
            last_time = datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
            if now < last_time + timedelta(hours=24):
                remaining = (last_time + timedelta(hours=24)) - now
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                query.message.reply_text(f"⏳ Daily Bonus is locked! Try again after *{hours}h {minutes}m*.", parse_mode='Markdown')
                conn.close()
                return
                
        dice_roll = random.randint(1, 6)
        cursor.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", 
                       (dice_roll, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        query.message.reply_text(f"🎲 *Dice Rolled!* You got number *{dice_roll}*.\n₹{dice_roll} added to your balance!", parse_mode='Markdown')

    elif data == "view_bot_fund":
        cursor.execute("SELECT bot_fund FROM settings WHERE id = 1")
        fund = cursor.fetchone()[0]
        query.message.reply_text(f"🎁 *Total Fund Of The Bot >>* ₹1,00,000\n🟢 *Remaining Fund >>* ₹{fund:.2f}", parse_mode='Markdown')

    elif data == "w_history":
        cursor.execute("SELECT amount, upi_id, status FROM withdraws WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        hist = cursor.fetchall()
        if not hist:
            query.message.reply_text("📝 No withdrawal records found.")
        else:
            msg = "📝 *Your Last 5 Withdrawals:*\n\n"
            for item in hist:
                msg += f"💰 Amount: ₹{item[0]} | UPI: `{item[1]}`\nStatus: *{item[2]}*\n\n"
            query.message.reply_text(msg, parse_mode='Markdown')

    elif data == "my_invites":
        cursor.execute("SELECT COUNT(*), status FROM referrals WHERE referrer_id = ? GROUP BY status", (user_id,))
        rows = cursor.fetchall()
        msg = "🚀 *Your Invitation Summary Track Status:*\n\n"
        if not rows:
            msg += "No referral transactions recorded."
        for row in rows:
            msg += f"• {row[1]}: *{row[0]} users*\n"
        query.message.reply_text(msg, parse_mode='Markdown')

    elif data == "game_ludo":
        keyboard = [
            [InlineKeyboardButton("🔴 Big (4, 5, 6)", callback_data="ludo_big"),
             InlineKeyboardButton("🔵 Small (1, 2, 3)", callback_data="ludo_small")]
        ]
        query.message.reply_text("🎲 *LUDO DICE BETTING*\n\nIf You Win Increased Your Balance Double! (2x Return)\n\nSelect your predict bucket:", 
                                 parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "ludo_big":
        query.message.reply_text("💬 Enter the amount you want to bet on *BIG*:")
        context.user_data['state'] = 'LUDO_BET_BIG'

    elif data == "ludo_small":
        query.message.reply_text("💬 Enter the amount you want to bet on *SMALL*:")
        context.user_data['state'] = 'LUDO_BET_SMALL'
        
    conn.close()

# --- LUDO BET MATH LOGIC ENGINE ---
def execute_ludo_dice_roll(update, context, user_id, bet_amount, choice):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    dice_out = random.randint(1, 6)
    result_bucket = "BIG" if dice_out in [4, 5, 6] else "SMALL"
    
    update.message.reply_text(f"🎲 Rolling Dice... Result is: *{dice_out}* ({result_bucket})", parse_mode='Markdown')
    
    if choice == result_bucket:
        # User Wins double balance adjustment (5 input turns to 10 total payout payload)
        win_net = bet_amount
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_net, user_id))
        cursor.execute("UPDATE settings SET bot_fund = bot_fund - ? WHERE id = 1", (win_net,))
        update.message.reply_text(f"🥳 *Whohoo! You Won!*\n₹{bet_amount * 2} credited successfully (Double mapping!).", parse_mode='Markdown')
    else:
        # User Loses amount moves to bot pool fund automatically
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet_amount, user_id))
        cursor.execute("UPDATE settings SET bot_fund = bot_fund + ? WHERE id = 1", (bet_amount,))
        update.message.reply_text(f"😭 *You Lost the Bet!*\n₹{bet_amount} cut down from wallet balances.", parse_mode='Markdown')
        
    conn.commit()
    conn.close()
    context.user_data.clear()

# --- CONTROL DESK ADMIN COMMAND CODES (EXCLUSIVE FOR ADMIN ID) ---
def admin_panel(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = ("🛠️ *Welcome To Admin Panel Command Desk*\n\n"
           "`/setinvite <val>` - Change invite asset payout\n"
           "`/setminwd <val>` - Change min withdraw floor value\n"
           "`/setfund <val>` - Refill core balance pool\n"
           "`/setlink <url>` - Set dynamic Earn More target url\n"
           "`/approve <wd_id>` - Complete user transaction\n"
           "`/reject <wd_id>` - Return user money back to wallet")
    update.message.reply_text(msg, parse_mode='Markdown')

def admin_set_invite(update: Update, context: CallbackContext):
    if update.effective_user.id == ADMIN_ID and context.args:
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET per_invite = ? WHERE id = 1", (float(context.args[0]),))
        conn.commit()
        conn.close()
        update.message.reply_text("✅ Target invite reward parameters shifted successfully!")

def admin_approve_withdrawal(update: Update, context: CallbackContext):
    if update.effective_user.id == ADMIN_ID and context.args:
        wd_id = int(context.args[0])
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (wd_id,))
        req = cursor.fetchone()
        
        if req:
            cursor.execute("UPDATE withdraws SET status = 'Success' WHERE id = ?", (wd_id,))
            conn.commit()
            context.bot.send_message(chat_id=req[0], text="🥳 *Whohoo your Money transfer To Your UPI Wallet Keep Support ( Raka )* 🔥", parse_mode='Markdown')
            update.message.reply_text("✅ Payout notification broadcast executed!")
        conn.close()

def admin_reject_withdrawal(update: Update, context: CallbackContext):
    if update.effective_user.id == ADMIN_ID and context.args:
        wd_id = int(context.args[0])
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM withdraws WHERE id = ?", (wd_id,))
        req = cursor.fetchone()
        
        if req:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (req[1], req[0]))
            cursor.execute("UPDATE withdraws SET status = 'Rejected' WHERE id = ?", (wd_id,))
            conn.commit()
            context.bot.send_message(chat_id=req[0], text="❌ *Your withdrawal request was rejected.* Fund added back to your balance.")
            update.message.reply_text("❌ Request marked as rejected. Balance restored safely.")
        conn.close()

# --- MAIN ENGINE CODES ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CommandHandler("setinvite", admin_set_invite))
    dp.add_handler(CommandHandler("approve", admin_approve_withdrawal))
    dp.add_handler(CommandHandler("reject", admin_reject_withdrawal))
    
    dp.add_handler(CallbackQueryHandler(handle_callbacks, pattern="^(daily_bonus|view_bot_fund|w_history|my_invites|game_ludo|ludo_big|ludo_small)$"))
    dp.add_handler(CallbackQueryHandler(check_channels, pattern="check_channels"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_messages))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
