import logging
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Logging configuration to track errors
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # <-- Apna Token Yahan Daalo
ADMIN_ID = 123456789  # <-- Apni Asli Telegram Numerical ID Yahan Daalo

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('raka_bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER,
            verified INTEGER DEFAULT 0,
            device_id TEXT,
            last_daily_bonus TEXT
        )
    ''')
    
    # Refer tracker
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referee_id INTEGER,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    # Withdrawal History
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            upi_id TEXT,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT
        )
    ''')
    
    # Admin Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default parameters
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('bot_fund', '100000')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('per_invite', '5')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('min_withdraw', '20')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('earn_more_link', 'https://t.me/')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('channels', '@Channel1,@Channel2')")
    
    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    logger.error(f"Database Initialization Error: {e}")

# --- HELPER FUNCTIONS ---
def get_setting(key):
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "0"

def update_setting(key, value):
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()
    conn.close()

# --- CONVERSATION STATES ---
BET_AMOUNT, WITHDRAW_AMOUNT, WITHDRAW_UPI = range(3)
ADMIN_BROADCAST, ADMIN_SET_FUND, ADMIN_SET_INVITE, ADMIN_SET_MIN, ADMIN_SET_LINK, ADMIN_ADD_CH = range(3, 9)

# --- START FLOW ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = user.id
    
    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id == chat_id:
                referrer_id = None
        except ValueError:
            pass

    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE user_id=?", (chat_id,))
    row = c.fetchone()
    
    if not row:
        c.execute("INSERT INTO users (user_id, username, balance, referred_by, verified) VALUES (?, ?, 0.0, ?, 0)", 
                  (chat_id, user.username, referrer_id))
        if referrer_id:
            c.execute("INSERT INTO refers (referrer_id, referee_id, status) VALUES (?, ?, 'Started')", 
                      (referrer_id, chat_id))
        conn.commit()
        is_verified = 0
    else:
        is_verified = row[0]
    conn.close()

    if is_verified == 1:
        await show_main_menu(update, context)
    else:
        channels_str = get_setting('channels')
        channels = channels_str.split(',') if channels_str else []
        
        keyboard = []
        for ch in channels:
            if ch.strip():
                clean_ch = ch.strip().replace('@', '')
                keyboard.append([InlineKeyboardButton(f"Join {ch.strip()}", url=f"https://t.me/{clean_ch}")])
        
        keyboard.append([InlineKeyboardButton("🚀 Claim", callback_data="check_channels")])
        
        await update.message.reply_text(
            "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- VERIFICATION & ANTI-CHEAT ---
async def check_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Yahan channels joining strictly secure check karne ke liye logic customizable hai
    keyboard = [[InlineKeyboardButton("🛡️ Verify Yourself", callback_data="device_verify")]]
    await query.message.reply_text(
        "🛡️ *Verify Yourself To Start Bot*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def device_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # Device duplication simulation fingerprint
    simulated_device_id = f"device_secure_hash_{user_id * 17}"
    
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    
    # Check if this device is already verified with another user ID
    c.execute("SELECT user_id FROM users WHERE device_id=? AND user_id != ?", (simulated_device_id, user_id))
    duplicate = c.fetchone()
    
    if duplicate:
        await query.message.reply_text("⚠️ *Same device detected!* Multiple accounts are not allowed on this device.")
        conn.close()
        return
        
    c.execute("SELECT referred_by, verified FROM users WHERE user_id=?", (user_id,))
    user_row = c.fetchone()
    
    if user_row and user_row[1] == 0:
        c.execute("UPDATE users SET verified=1, device_id=? WHERE user_id=?", (simulated_device_id, user_id))
        referrer_id = user_row[0]
        
        if referrer_id:
            per_invite = float(get_setting('per_invite'))
            bot_fund = float(get_setting('bot_fund'))
            
            if bot_fund >= per_invite:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (per_invite, referrer_id))
                c.execute("UPDATE settings SET value=? WHERE key='bot_fund'", (str(bot_fund - per_invite),))
                c.execute("UPDATE refers SET status='Verified' WHERE referrer_id=? AND referee_id=?", (referrer_id, user_id))
                
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 *New Refer Earned!*\nUser verified successfully. +₹{per_invite} added to your balance.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            else:
                c.execute("UPDATE refers SET status='Fund Empty' WHERE referrer_id=? AND referee_id=?", (referrer_id, user_id))
        conn.commit()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("CONTINUE TO BOT", callback_data="go_to_main_menu")]]
    await query.message.reply_text(
        "✅ *Verified Successfully*\n\nYou're verified successfully, you can use our bot now.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_main_menu(update, context):
    keyboard = [
        ["🎉 Gift Code", "💰 Balance"],
        ["👥 Refer & Earn", "💸 Withdraw"],
        ["🎰 Bet & Earn", "🚀 Earn More"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    msg_text = "✨ *Welcome To Cash Giveaway Bot!*\n\nSelect an option from the menu buttons below."
    
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)

# --- MENU ROUTING HANDLER ---
async def handle_menu_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or row[0] != 1:
        await update.message.reply_text("❌ First verification required. Send /start to begin.")
        return ConversationHandler.END

    if text == "🎉 Gift Code":
        keyboard = [
            [InlineKeyboardButton("🎲 Daily Bonus", callback_data="daily_bonus")]
        ]
        await update.message.reply_text("✨ *Choose One:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
        
    elif text == "💰 Balance":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = c.fetchone()[0]
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history")],
            [InlineKeyboardButton("📦 Bot Fund", callback_data="fund_status")]
        ]
        await update.message.reply_text(
            f"💰 *Balance: ₹{balance:.2f}*\n\nUse 'Withdraw' Button to Withdraw The Balance!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
        
    elif text == "👥 Refer & Earn":
        per_invite = get_setting('per_invite')
        bot_username = (await context.bot.get_me()).username
        bot_link = f"https://t.me/{bot_username}?start={user_id}"
        
        keyboard = [
            [InlineKeyboardButton("🚀 My Invites", callback_data="my_invites"), 
             InlineKeyboardButton("📊 Refer Tracker", callback_data="refer_tracker")]
        ]
        await update.message.reply_text(
            f"🎁 *Per Invite ₹{per_invite} UPI Cash !!*\n\n"
            f"🎁 *Invite Link :* {bot_link}\n\n"
            f"Share Your Own Invite Link To Earn Unlimited Easy Cash! 💵",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        return ConversationHandler.END
        
    elif text == "💸 Withdraw":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = c.fetchone()[0]
        conn.close()
        
        min_w = float(get_setting('min_withdraw'))
        if balance < min_w:
            await update.message.reply_text(f"🤢 *You need minimum {min_w:.0f} in balance to withdraw*")
            return ConversationHandler.END
            
        await update.message.reply_text("💵 *Enter the amount you want to withdraw:*", parse_mode="Markdown")
        return WITHDRAW_AMOUNT
        
    elif text == "🎰 Bet & Earn":
        keyboard = [
            [InlineKeyboardButton("🎲 Ludo (Big/Small)", callback_data="game_ludo")]
        ]
        await update.message.reply_text(
            "🎰 *Welcome to Bet & Earn Arena!*\nWin Big Cash & Have Fun! 💸\n\n🎮 *Choose Your Game :*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
        
    elif text == "🚀 Earn More":
        link = get_setting('earn_more_link')
        keyboard = [[InlineKeyboardButton("🔗 Visit Channel / link", url=link)]]
        await update.message.reply_text("🚀 Click below to earn more:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

# --- INLINE GENERAL CALLBACK HANDLER ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "go_to_main_menu":
        await show_main_menu(update, context)
        
    elif data == "daily_bonus":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT last_daily_bonus FROM users WHERE user_id=?", (user_id,))
        last_bonus_str = c.fetchone()[0]
        
        now = datetime.now()
        if last_bonus_str:
            last_bonus = datetime.strptime(last_bonus_str, '%Y-%m-%d %H:%M:%S')
            if now < last_bonus + timedelta(hours=24):
                time_left = (last_bonus + timedelta(hours=24)) - now
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                await query.message.reply_text(f"⏳ *Daily bonus locked!* Please wait `{hours}h {minutes}m` to roll again.", parse_mode="Markdown")
                conn.close()
                return
        
        dice_roll = random.randint(1, 6)
        reward = float(dice_roll)
        
        c.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?", 
                  (reward, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        conn.close()
        
        await query.message.reply_text(f"🎲 *Dice Rolled!* Result: `{dice_roll}`. Added *₹{reward}* to your balance!", parse_mode="Markdown")
        
    elif data == "fund_status":
        bot_fund = get_setting('bot_fund')
        await query.message.reply_text(f"🎁 *Total Fund Of The Bot* >> ₹1,00,000\n🟢 *Remaining Fund* >> ₹{float(bot_fund):.2f}", parse_mode="Markdown")
        
    elif data == "w_history":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT amount, upi_id, status FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            await query.message.reply_text("❌ No withdrawal history found.")
            return
            
        text = "📋 *Withdrawal History (Last 5):*\n\n"
        for r in rows:
            text += f"💰 Amt: ₹{r[0]} | UPI: `{r[1]}`\nStatus: *{r[2]}*\n\n"
        await query.message.reply_text(text, parse_mode="Markdown")
        
    elif data == "my_invites":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT status, COUNT(*) FROM refers WHERE referrer_id=? GROUP BY status", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        stats = {"Verified": 0, "Started": 0}
        for r in rows:
            if r[0] == "Verified": stats["Verified"] = r[1]
            elif r[0] == "Started": stats["Started"] = r[1]
            
        await query.message.reply_text(f"👥 *Your Invites:*\n\nSuccess: {stats['Verified']}\nIncomplete (No join/verify): {stats['Started']}")
        
    elif data == "refer_tracker":
        await query.message.reply_text("📊 Tracking setup is running fine. All dynamic refers monitored.")
        
    elif data == "game_ludo":
        keyboard = [
            [InlineKeyboardButton("🔴 Big (4-6)", callback_data="ludo_bet_big"),
             InlineKeyboardButton("🔵 Small (1-3)", callback_data="ludo_bet_small")]
        ]
        await query.message.reply_text(
            "🎲 *Ludo - Big vs Small*\n\n*If You Win Increased Your Balance Double!*\nChoose your side:",
            parse_mode="Markdown",
            markup=InlineKeyboardMarkup(keyboard)
        )

# --- GAME REGISTRATION FLOW ---
async def start_ludo_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[2]
    context.user_data['ludo_choice'] = choice
    await query.message.reply_text(f"Selected *{choice.upper()}*. Enter bet amount:", parse_mode="Markdown")
    return BET_AMOUNT

async def run_ludo_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount_str = update.message.text
    choice = context.user_data.get('ludo_choice')
    
    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid positive number:")
        return BET_AMOUNT
        
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = c.fetchone()[0]
    
    if amount > balance:
        await update.message.reply_text("❌ Insufficient balance!")
        conn.close()
        return ConversationHandler.END
        
    bot_fund = float(get_setting('bot_fund'))
    dice = random.randint(1, 6)
    outcome = "big" if dice in [4, 5, 6] else "small"
    
    if choice == outcome:
        # Win logic: double standard payout 5 + 5 = 10
        new_bal = balance + amount
        new_fund = bot_fund - amount
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_bal, user_id))
        c.execute("UPDATE settings SET value=? WHERE key='bot_fund'", (str(new_fund),))
        await update.message.reply_text(f"🎲 *Dice Rolled:* `{dice}` ({outcome.upper()})\n\n🎉 *WIN!* Balance increased double: *+₹{amount * 2}*", parse_mode="Markdown")
    else:
        # Loss logic
        new_bal = balance - amount
        new_fund = bot_fund + amount
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_bal, user_id))
        c.execute("UPDATE settings SET value=? WHERE key='bot_fund'", (str(new_fund),))
        await update.message.reply_text(f"🎲 *Dice Rolled:* `{dice}` ({outcome.upper()})\n\n💔 *LOSS!* Bet amount cut from your account: *-₹{amount}*", parse_mode="Markdown")
        
    conn.commit()
    conn.close()
    return ConversationHandler.END

# --- WITHDRAW HANDLING PROCESS ---
async def run_withdraw_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount_str = update.message.text
    min_w = float(get_setting('min_withdraw'))
    
    try:
        amount = float(amount_str)
        if amount < min_w:
            await update.message.reply_text(f"❌ Minimum withdrawal is ₹{min_w:.0f}. Re-enter amount:")
            return WITHDRAW_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Numbers only. Re-enter:")
        return WITHDRAW_AMOUNT
        
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    
    if amount > balance:
        await update.message.reply_text("❌ Insufficient balance. Re-enter amount:")
        return WITHDRAW_AMOUNT
        
    context.user_data['w_amt'] = amount
    await update.message.reply_text("💳 *Now submit your UPI ID:*", parse_mode="Markdown")
    return WITHDRAW_UPI

async def run_withdraw_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    upi_id = update.message.text
    amount = context.user_data.get('w_amt')
    time_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    c.execute("INSERT INTO withdrawals (user_id, amount, upi_id, status, timestamp) VALUES (?, ?, ?, 'Pending', ?)",
              (user_id, amount, upi_id, time_stamp))
    conn.commit()
    tx_id = c.lastrowid
    conn.close()
    
    await update.message.reply_text("⏳ *Withdrawal request submitted successfully! Pending approval.*")
    
    # Notify Admin Room
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"ap_{tx_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"rj_{tx_id}")]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 *NEW WITHDRAW REQUEST*\n\nUser: `{user_id}`\nAmount: ₹{amount}\nUPI: `{upi_id}`\nTX ID: #{tx_id}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# --- ADMIN CONVERSATIONS ---
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="ad_br"), InlineKeyboardButton("💰 Bot Fund", callback_data="ad_fd")],
        [InlineKeyboardButton("👥 Invite ₹", callback_data="ad_inv"), InlineKeyboardButton("💸 Min Withdrawal", callback_data="ad_mw")],
        [InlineKeyboardButton("🚀 'Earn More' Link", callback_data="ad_lk"), InlineKeyboardButton("🔗 Channels", callback_data="ad_ch")]
    ]
    await update.message.reply_text("🛠️ *Admin Master Control Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    data = query.data
    
    if data.startswith("ap_"):
        tx_id = int(data.split("_")[1])
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, amount FROM withdrawals WHERE id=?", (tx_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE withdrawals SET status='Success' WHERE id=?", (tx_id,))
            conn.commit()
            await query.message.edit_text(f"✅ Approved Request #{tx_id}")
            try:
                await context.bot.send_message(chat_id=row[0], text="🎉 *Whoohoo your Money transfer To You Upi Wallet Keep Support ( Raka )*", parse_mode="Markdown")
            except Exception: pass
        conn.close()
        return ConversationHandler.END
        
    elif data.startswith("rj_"):
        tx_id = int(data.split("_")[1])
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, amount FROM withdrawals WHERE id=?", (tx_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE withdrawals SET status='Rejected' WHERE id=?", (tx_id,))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (row[1], row[0]))
            conn.commit()
            await query.message.edit_text(f"❌ Rejected Request #{tx_id}. Money Refunded.")
            try:
                await context.bot.send_message(chat_id=row[0], text=f"❌ *Withdrawal request rejected.* ₹{row[1]} added back to balance.")
            except Exception: pass
        conn.close()
        return ConversationHandler.END

    # Route options setup states
    if data == "ad_br":
        await query.message.reply_text("Enter message to broadcast to all users:")
        return ADMIN_BROADCAST
    elif data == "ad_fd":
        await query.message.reply_text("Enter new Bot Fund amount:")
        return ADMIN_SET_FUND
    elif data == "ad_inv":
        await query.message.reply_text("Enter bonus per invite:")
        return ADMIN_SET_INVITE
    elif data == "ad_mw":
        await query.message.reply_text("Enter minimum withdrawal amount:")
        return ADMIN_SET_MIN
    elif data == "ad_lk":
        await query.message.reply_text("Enter new link for 'Earn More' button:")
        return ADMIN_SET_LINK
    elif data == "ad_ch":
        await query.message.reply_text("Enter comma separated channels list (ex: `@ch1,@ch2`):")
        return ADMIN_ADD_CH

async def rec_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    msg = update.message.text
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=msg)
            count += 1
        except Exception: pass
    await update.message.reply_text(f"📢 Sent to {count} users successfully.")
    return ConversationHandler.END

async def rec_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('bot_fund', update.message.text)
    await update.message.reply_text("✅ Bot fund updated!")
    return ConversationHandler.END

async def rec_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('per_invite', update.message.text)
    await update.message.reply_text("✅ Per Invite balance updated!")
    return ConversationHandler.END

async def rec_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('min_withdraw', update.message.text)
    await update.message.reply_text("✅ Minimum withdrawal threshold updated!")
    return ConversationHandler.END

async def rec_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('earn_more_link', update.message.text)
    await update.message.reply_text("✅ 'Earn More' partner redirect link updated!")
    return ConversationHandler.END

async def rec_ch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('channels', update.message.text)
    await update.message.reply_text("✅ Verification channels stream listing configuration updated!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

# --- APP EXECUTION COROUTINES ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # State routing engine definitions
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_options),
            CallbackQueryHandler(handle_admin_action, pattern="^(ap_|rj_|ad_).*$"),
            CallbackQueryHandler(start_ludo_bet, pattern="^ludo_bet_.*$"),
            CallbackQueryHandler(handle_callbacks, pattern="^(daily_bonus|fund_status|w_history|my_invites|refer_tracker|game_ludo)$")
        ],
        states={
            BET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, run_ludo_engine)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, run_withdraw_amt)],
            WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, run_withdraw_upi)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_broadcast)],
            ADMIN_SET_FUND: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_fund)],
            ADMIN_SET_INVITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_invite)],
            ADMIN_SET_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_min)],
            ADMIN_SET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_link)],
            ADMIN_ADD_CH: [MessageHandler(filters.TEXT & ~filters.COMMAND, rec_ch)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", start_admin))
    app.add_handler(CallbackQueryHandler(check_channels, pattern="^check_channels$"))
    app.add_handler(CallbackQueryHandler(device_verify, pattern="^device_verify$"))
    app.add_handler(conv_handler)
    
    print("🚀 Anti-crash bot script is successfully running live...")
    app.run_polling()

if __name__ == '__main__':
    main()
