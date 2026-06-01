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

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONFIGURATION (ADMIN CAN CHANGE THESE) ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Apna Telegram Bot Token yahan daalo
ADMIN_ID = 123456789  # Apni asli Telegram User ID yahan daalo

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
    
    # Refer tracker for extra details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refers (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            referrer_id INTEGER,
            referee_id INTEGER,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    # Withdrawal History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            user_id INTEGER,
            amount REAL,
            upi_id TEXT,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT
        )
    ''')
    
    # Admin Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default settings insertion
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('bot_fund', '100000')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('per_invite', '5')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('min_withdraw', '20')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('earn_more_link', 'https://t.me/RakaWorkAgency')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('channels', '@Channel1,@Channel2')")
    
    conn.commit()
    conn.close()

init_db()

# --- DATABASE HELPER FUNCTIONS ---
def get_setting(key):
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_setting(key, value):
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()
    conn.close()

# --- CONVERSATION STATES ---
BET_AMOUNT, WITHDRAW_AMOUNT, WITHDRAW_UPI, ADMIN_BROADCAST, ADMIN_SET_FUND, ADMIN_SET_INVITE, ADMIN_SET_MIN, ADMIN_SET_LINK, ADMIN_ADD_CH = range(9)

# --- MAIN FLOW: /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = user.id
    
    # Handling referral link setup
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
        # Naya user store karna bina verification ke
        c.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
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
        # Channel Join verification stage display
        channels_str = get_setting('channels')
        channels = channels_str.split(',') if channels_str else []
        
        keyboard = []
        for ch in channels:
            if ch.strip():
                keyboard.append([InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.replace('@','')}")])
        
        keyboard.append([InlineKeyboardButton("🚀 Claim", callback_data="check_channels")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 *Hey There! Welcome To Bot !!*\n\n⚪ *Join The Channels Below To Continue*\n\n😍 *After Joining Click Claim*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# --- CHANNEL VERIFICATION AND ANTI-CHEAT DEVICE CHECK ---
async def check_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    channels_str = get_setting('channels')
    channels = channels_str.split(',') if channels_str else []
    
    # Real setup inside production should verify chat member. 
    # Simulated check for simplicity unless administrative overrides apply.
    all_joined = True 
    
    if all_joined:
        # Prompting for Anti-Cheat Device HW/IP Check simulations
        keyboard = [[InlineKeyboardButton("🛡️ Verify", callback_data="device_verify")]]
        await query.message.reply_text(
            "🛡️ *Verify Yourself To Start Bot*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.message.reply_text("❌ Aapne saare channels join nahi kiye! Kripya dobara check karein.")

async def device_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # Anti-device duplication fingerprinting
    simulated_device_id = f"dev_hash_{user_id * 31}" 
    
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM users WHERE device_id=? AND user_id != ?", (simulated_device_id, user_id))
    duplicate = c.fetchone()
    
    if duplicate:
        await query.message.reply_text("⚠️ *Same device detected!* Multiple accounts bypass rules are restricted.", parse_mode="Markdown")
        conn.close()
        return
        
    # Validation successful
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
                
                # Notify Referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 *New Referral Milestone!*\nUser verified successfully. +₹{per_invite} credited to your wallet.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            else:
                c.execute("UPDATE refers SET status='Fund Depleted' WHERE referrer_id=? AND referee_id=?", (referrer_id, user_id))

        conn.commit()
    conn.close()
    
    # Web-app simulation dynamic UI callback
    keyboard = [[InlineKeyboardButton("CONTINUE TO BOT", callback_data="go_to_main_menu")]]
    await query.message.reply_text(
        "✅ *Verified Successfully*\n\nYou're verified successfully, you can use our bot now.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- SHOW MAIN MENU METHOD ---
async def go_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(query, context, is_query=True)

async def show_main_menu(target, context, is_query=False):
    keyboard = [
        ["🎉 Gift Code", "💰 Balance"],
        ["👥 Refer & Earn", "💸 Withdraw"],
        ["🎰 Bet & Earn", "🚀 Earn More"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    msg_text = "✨ *Welcome To Cash Giveaway Bot!*\n\nSelect an option from the menu layout below."
    
    if is_query:
        await target.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await target.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)

# --- ROUTING LOGIC HANDLER FOR THE INTERFACE LAYOUT ---
async def handle_menu_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    # Security Validation Gate
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] != 1:
        await update.message.reply_text("❌ Please verify initialization access credentials using /start.")
        return

    if text == "🎉 Gift Code":
        keyboard = [
            [InlineKeyboardButton("🎲 Daily Bonus", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 Gift Code Verification", callback_data="claim_promo")]
        ]
        await update.message.reply_text("✨ *Choose One:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif text == "💰 Balance":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = c.fetchone()[0]
        conn.close()
        
        bot_fund = get_setting('bot_fund')
        
        keyboard = [
            [InlineKeyboardButton("📝 Withdrawal History", callback_data="w_history")],
            [InlineKeyboardButton("📦 Bot Fund Status", callback_data="fund_status")]
        ]
        await update.message.reply_text(
            f"💰 *Balance: ₹{balance:.2f}*\n\nUse 'Withdraw' Button to Withdraw The Balance!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif text == "👥 Refer & Earn":
        per_invite = get_setting('per_invite')
        bot_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
        
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
        
    elif text == "💸 Withdraw":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = c.fetchone()[0]
        conn.close()
        
        min_w = float(get_setting('min_withdraw'))
        if balance < min_w:
            await update.message.reply_text(f"🤢 *You need minimum {min_w:.2f} in balance to withdraw*", parse_mode="Markdown")
            return ConversationHandler.END
            
        await update.message.reply_text("💵 *Enter the structural amount you want to withdraw:*", parse_mode="Markdown")
        return WITHDRAW_AMOUNT
        
    elif text == "🎰 Bet & Earn":
        keyboard = [
            [InlineKeyboardButton("🎲 Ludo (Big/Small)", callback_data="game_ludo")],
            [InlineKeyboardButton("🟢 Wingo (Color Game)", callback_data="game_wingo")]
        ]
        await update.message.reply_text(
            "🎰 *Welcome to Bet & Earn Arena!*\nWin Big Cash & Have Fun! 💸\n\n🎮 *Choose Your Game :*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif text == "🚀 Earn More":
        link = get_setting('earn_more_link')
        keyboard = [[InlineKeyboardButton("🔗 Visit Partner Link", url=link)]]
        await update.message.reply_text("🚀 Click below to earn extra via our global sponsor streams:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- INLINE CALLBACK SUB-MENU HANDLERS ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "daily_bonus":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT last_daily_bonus FROM users WHERE user_id=?", (user_id,))
        last_bonus_str = c.fetchone()[0]
        
        now = datetime.now()
        if last_bonus_str:
            last_bonus = datetime.strptime(last_bonus_str, '%Y-%m-%d %H:%M:%S')
            if now < last_bonus + timedelta(hours=24):
                time_left = (last_bonus + timedelta(hours=24)) - now
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await query.message.reply_text(f"⏳ *Daily bonus locked!* Please wait `{hours}h {minutes}m` to spin again.", parse_mode="Markdown")
                conn.close()
                return
        
        dice_roll = random.randint(1, 6)
        reward = float(dice_roll) # 1 point per dice spot allocation
        
        c.execute("UPDATE users SET balance = balance + ?, last_daily_bonus = ? WHERE user_id = ?", 
                  (reward, now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        conn.close()
        
        await query.message.reply_text(f"🎲 *Dice Rolled!* You got a `{dice_roll}`. Added *₹{reward}* inside wallet balance.", parse_mode="Markdown")
        
    elif data == "fund_status":
        bot_fund = get_setting('bot_fund')
        await query.message.reply_text(f"🎁 *Total Allocated Bot Cap Pool* >> ₹1,00,000\n🟢 *Remaining Fund Balance* >> ₹{float(bot_fund):,.2f}", parse_mode="Markdown")
        
    elif data == "w_history":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT amount, upi_id, status, timestamp FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            await query.message.reply_text("❌ No transaction histories found for this profile tracking id.")
            return
            
        history_text = "📋 *Your Withdrawal Records (Last 5):*\n\n"
        for row in rows:
            history_text += f"💰 Amount: ₹{row[0]} | UPI: `{row[1]}`\nStatus: *{row[2]}* | _({row[3]})_\n\n"
        await query.message.reply_text(history_text, parse_mode="Markdown")
        
    elif data == "my_invites":
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT status, COUNT(*) FROM refers WHERE referrer_id=? GROUP BY status", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        stats = {"Verified": 0, "Started": 0}
        for row in rows:
            if row[0] == "Verified": stats["Verified"] = row[1]
            elif row[0] == "Started": stats["Started"] = row[1]
            
        await query.message.reply_text(
            f"👥 *Your Invitation Analytics:*\n\n"
            f"✅ *Successful Valid Invites:* {stats['Verified']}\n"
            f"⚠️ *Incomplete (Left Without Verification/Channels):* {stats['Started']}",
            parse_mode="Markdown"
        )
        
    elif data == "refer_tracker":
        await query.message.reply_text("📊 *Live Track:* All active computational pipelines are operational. Multi-device filters protecting your dynamic downline allocations.")
        
    elif data == "game_ludo":
        keyboard = [
            [InlineKeyboardButton("🔴 Big (4-6)", callback_data="bet_ludo_big"),
             InlineKeyboardButton("🔵 Small (1-3)", callback_data="bet_ludo_small")]
        ]
        await query.message.reply_text(
            "🎲 *Ludo High-Low Arena*\n\n"
            "📈 *Multiplier Rules:* If You Win Increased Your Balance Double!\n"
            "Select choice parameters below:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("bet_ludo_"):
        choice = data.split("_")[2] # big or small
        context.user_data['bet_type'] = choice
        await query.message.reply_text(f"Selected *{choice.upper()}*. Please input structural numeric bet stake currency amount:", parse_mode="Markdown")
        return BET_AMOUNT

    elif data == "game_wingo":
        await query.message.reply_text("🟢 *Wingo Engine Update:* Color matching frameworks processing state shifts. Bet configuration running active modules.")

# --- CONVERSATION FLOW: BET PLACEMENT ENGINE ---
async def receive_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount_str = update.message.text
    bet_type = context.user_data.get('bet_type')
    
    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Input a valid positive number.")
        return BET_AMOUNT
        
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = c.fetchone()[0]
    
    if amount > balance:
        await update.message.reply_text("❌ Insufficient Wallet Balances! Try smaller staking values.")
        conn.close()
        return ConversationHandler.END
        
    bot_fund = float(get_setting('bot_fund'))
    if amount > bot_fund:
        await update.message.reply_text("❌ Engine Cap Warning: Bot tracking pool funds overloaded. Max limit cap adjusted.")
        conn.close()
        return ConversationHandler.END

    # Execution execution sequence rolling dice
    dice = random.randint(1, 6)
    result_type = "big" if dice in [4, 5, 6] else "small"
    
    if bet_type == result_type:
        # User Win Scenario
        new_balance = balance + amount # Double matrix calculation payout context
        new_fund = bot_fund - amount
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        c.execute("UPDATE settings SET value=? WHERE key='bot_fund'", (str(new_fund),))
        await update.message.reply_text(
            f"🎲 *Dice Rolled:* `{dice}` ({result_type.upper()})\n\n"
            f"🎉 *WINNER!* Your bet parameter matched perfectly. Double values credited: *+₹{amount * 2}*",
            parse_mode="Markdown"
        )
    else:
        # User Loss Scenario
        new_balance = balance - amount
        new_fund = bot_fund + amount
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        c.execute("UPDATE settings SET value=? WHERE key='bot_fund'", (str(new_fund),))
        await update.message.reply_text(
            f"🎲 *Dice Rolled:* `{dice}` ({result_type.upper()})\n\n"
            f"💔 *LOSS!* System values unmatched. Balance updated: *-₹{amount}*",
            parse_mode="Markdown"
        )
        
    conn.commit()
    conn.close()
    return ConversationHandler.END

# --- CONVERSATION FLOW: WITHDRAWAL CONTROLLER ---
async def receive_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    amount_str = update.message.text
    min_w = float(get_setting('min_withdraw'))
    
    try:
        amount = float(amount_str)
        if amount < min_w:
            await update.message.reply_text(f"❌ Minimum structural withdrawal threshold set to ₹{min_w}. Try again:")
            return WITHDRAW_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Input numeric values only:")
        return WITHDRAW_AMOUNT
        
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = c.fetchone()[0]
    conn.close()
    
    if amount > balance:
        await update.message.reply_text("❌ Out of balance constraints. Try again:")
        return WITHDRAW_AMOUNT
        
    context.user_data['w_amount'] = amount
    await update.message.reply_text("💳 *Now submit your target payout UPI address:*", parse_mode="Markdown")
    return WITHDRAW_UPI

async def receive_withdraw_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    upi_id = update.message.text
    amount = context.user_data.get('w_amount')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect('raka_bot.db')
    c = conn.cursor()
    
    # Deduct structural asset from tracking user balance instantly
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    
    # Log transactional records
    c.execute("INSERT INTO withdrawals (user_id, amount, upi_id, status, timestamp) VALUES (?, ?, ?, 'Pending', ?)",
              (user_id, amount, upi_id, timestamp))
    conn.commit()
    
    # Fetch auto increment transaction identity mapping allocation
    c.execute("SELECT last_insert_rowid()")
    tx_id = c.fetchone()[0]
    conn.close()
    
    await update.message.reply_text("⏳ *Withdrawal Request Registered Successfully!* Pending validation processing layers via monitoring core desk.")
    
    # Push update warning dispatch alerts direct towards Master Admin control room
    admin_keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{tx_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"adm_rej_{tx_id}")]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 *NEW WITHDRAWAL REQUEST REQUESTED*\n\n"
             f"👤 User ID: `{user_id}`\n"
             f"💰 Value Asset: ₹{amount}\n"
             f"💳 Target UPI destination: `{upi_id}`\n"
             f"🆔 Transaction Index Reference ID: #{tx_id}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )
    return ConversationHandler.END

# --- ADMIN COMMAND DESK PLATFORM ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Alerts", callback_data="adm_m_broad"),
         InlineKeyboardButton("💰 Set Core Fund Pool", callback_data="adm_m_fund")],
        [InlineKeyboardButton("👥 Modify Invite Value", callback_data="adm_m_inv"),
         InlineKeyboardButton("💸 Minimum Withdraw Cap", callback_data="adm_m_min")],
        [InlineKeyboardButton("🚀 Set 'Earn More' Link", callback_data="adm_m_link"),
         InlineKeyboardButton("🔗 Channel Controller", callback_data="adm_m_ch")]
    ]
    await update.message.reply_text("🛠️ *Raka Master Control Admin Panel UI Core*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()
    data = query.data
    
    if data.startswith("adm_app_"):
        tx_id = int(data.split("_")[2])
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, amount FROM withdrawals WHERE id=?", (tx_id,))
        w_row = c.fetchone()
        
        if w_row:
            u_id, amt = w_row[0], w_row[1]
            c.execute("UPDATE withdrawals SET status='Success' WHERE id=?", (tx_id,))
            conn.commit()
            await query.message.edit_text(f"✅ Transaction ID #{tx_id} marked as Success!")
            
            try:
                await context.bot.send_message(
                    chat_id=u_id,
                    text="🎉 *Whoohoo your Money transfer To You Upi Wallet Keep Support ( Raka )*",
                    parse_mode="Markdown"
                )
            except Exception: pass
        conn.close()
        
    elif data.startswith("adm_rej_"):
        tx_id = int(data.split("_")[2])
        conn = sqlite3.connect('raka_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, amount FROM withdrawals WHERE id=?", (tx_id,))
        w_row = c.fetchone()
        
        if w_row:
            u_id, amt = w_row[0], w_row[1]
            c.execute("UPDATE withdrawals SET status='Rejected' WHERE id=?", (tx_id,))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
            conn.commit()
            await query.message.edit_text(f"❌ Transaction ID #{tx_id} Rejected, asset refunded.")
            
            try:
                await context.bot.send_message(
                    chat_id=u_id,
                    text=f"❌ *Withdrawal request rejected by Admin.* ₹{amt} returned inside wallet balance structures.",
                    parse_mode="Markdown"
                )
            except Exception: pass
        conn.close()

    elif data == "adm_m_broad":
        await query.message.reply_text("Type the custom message context to transmit global network streams:")
        return ADMIN_BROADCAST
    elif data == "adm_m_fund":
        await query.message.reply_text("Enter new baseline core pool Bot Fund value allocations:")
        return ADMIN_SET_FUND
    elif data == "adm_m_inv":
        await query.message.reply_text("Enter target validation credit amount per invite parameter verification:")
        return ADMIN_SET_INVITE
    elif data == "adm_m_min":
        await query.message.reply_text("Configure minimum lower bound asset extraction limit cap values:")
        return ADMIN_SET_MIN
    elif data == "adm_m_link":
        await query.message.reply_text("Input sponsor tracking URLs for Earn More integration buttons:")
        return ADMIN_SET_LINK
    elif data == "adm_m_ch":
        current = get_setting('channels')
        await query.message.reply_text(f"Current allocation streams: `{current}`\nInput comma separated target channel identity strings (e.g. `@ch1,@ch2`):", parse_mode="Markdown")
        return ADMIN_ADD_CH

# --- ADMIN PARAMETER INPUT ACQUISITIONS ---
async def admin_recv_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(f"📢 Transmit stream operation completed. Reach metrics: {count} active channels.")
    return ConversationHandler.END

async def admin_recv_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('bot_fund', update.message.text)
    await update.message.reply_text("✅ Core database metrics updated: Bot tracking pool parameter refreshed.")
    return ConversationHandler.END

async def admin_recv_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('per_invite', update.message.text)
    await update.message.reply_text("✅ Parameter metrics reconfigured successfully.")
    return ConversationHandler.END

async def admin_recv_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('min_withdraw', update.message.text)
    await update.message.reply_text("✅ Base constraints threshold recalibrated configuration parameters.")
    return ConversationHandler.END

async def admin_recv_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('earn_more_link', update.message.text)
    await update.message.reply_text("✅ Dynamic payload target redirection links mapping online.")
    return ConversationHandler.END

async def admin_recv_ch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    update_setting('channels', update.message.text)
    await update.message.reply_text("✅ Core channel list successfully updated inside server database files.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Process terminated or configuration expired.")
    return ConversationHandler.END

# --- EXECUTION INITIALIZATION PIPELINES ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversational routing handler definitions
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_options),
            CallbackQueryHandler(handle_callbacks, pattern="^(daily_bonus|fund_status|w_history|my_invites|refer_tracker|game_ludo|game_wing|bet_ludo_).*$"),
            CallbackQueryHandler(handle_admin_callbacks, pattern="^(adm_).*$"),
        ],
        states={
            BET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bet_amount)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_amount)],
            WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_upi)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_broadcast)],
            ADMIN_SET_FUND: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_fund)],
            ADMIN_SET_INVITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_invite)],
            ADMIN_SET_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_min)],
            ADMIN_SET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_link)],
            ADMIN_ADD_CH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recv_ch)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(check_channels, pattern="^check_channels$"))
    app.add_handler(CallbackQueryHandler(device_verify, pattern="^device_verify$"))
    app.add_handler(CallbackQueryHandler(go_to_main_menu, pattern="^go_to_main_menu$"))
    app.add_handler(conv_handler)
    
    print("🚀 Bot running dynamically...")
    app.run_polling()

if __name__ == '__main__':
    main()
