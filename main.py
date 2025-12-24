# ===============================
# YASH ADZ BOT — MAIN FILE
# ===============================

import asyncio
import traceback
from datetime import datetime
import pytz

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN, OWNER_ID, PROMO_SUFFIX, TIMEZONE
from database import load_db, save_db

# ===============================
# DATABASE INIT
# ===============================
DATA_FILE = "data.json"

DEFAULT_DB = {
    "texts": [],            # list[str]
    "buttons": [],          # list[list[{text, url}]]
    "channels": [],         # list[str or int]
}

db = load_db(DATA_FILE, DEFAULT_DB)
IST = pytz.timezone(TIMEZONE)

def save():
    save_db(DATA_FILE, db)

def is_owner(update: Update):
    return update.effective_user.id == OWNER_ID

# ===============================
# UI HELPERS
# ===============================
def styled(text: str):
    return (
        "✨💠 𝙔𝘼𝙎𝙃 𝘼𝘿𝙕 𝘽𝙊𝙏 💠✨\n\n"
        f"{text}\n\n"
        "⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡"
    )

def build_buttons(rows):
    if not rows:
        return None
    keyboard = []
    for row in rows:
        keyboard.append(
            [InlineKeyboardButton(b["text"], url=b["url"]) for b in row]
        )
    return InlineKeyboardMarkup(keyboard)

# ===============================
# START
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        styled("✅ Bot is **RUNNING 24/7**"),
        parse_mode="Markdown"
    )

# ===============================
# HELP
# ===============================
HELP_TEXT = """
✨💠 𝙔𝘼𝙎𝙃 𝘼𝘿𝙕 𝘽𝙊𝙏 — 𝙊𝙬𝙣𝙚𝙧 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨 💠✨

━━━━━━━━━━━━━━━
📌 BASIC
━━━━━━━━━━━━━━━
• /start — Bot status
• /help — Help menu
• /status — System status

━━━━━━━━━━━━━━━
📝 TEXT
━━━━━━━━━━━━━━━
• /settext — Save new promo text
• /listtext — View saved texts
• /cleartext — Delete selected text
• /clearalltext — Delete ALL texts

━━━━━━━━━━━━━━━
🔘 BUTTONS
━━━━━━━━━━━━━━━
• /setbuttons — Add row based buttons
• /editbuttons — Edit buttons
• /deletebutton — Delete selected button
• /deleteallbuttons — Remove ALL buttons

━━━━━━━━━━━━━━━
📡 CHANNELS
━━━━━━━━━━━━━━━
• /addchannel — Add channel
• /removechannel — Remove channel
• /listchannels — Show channels

━━━━━━━━━━━━━━━
📢 BROADCAST
━━━━━━━━━━━━━━━
• /broadcast — Send promo to ALL channels
• /send — Manual send (saved / custom)

━━━━━━━━━━━━━━━
⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡
"""

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

# ===============================
# TEXT SYSTEM
# ===============================
async def settext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    text = update.message.text.replace("/settext", "", 1).strip()
    if not text:
        await update.message.reply_text("❌ Send text with command")
        return
    db["texts"].append(text)
    save()
    await update.message.reply_text(f"✅ Text Saved (#{len(db['texts'])})")

async def listtext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not db["texts"]:
        await update.message.reply_text("❌ No texts saved")
        return
    msg = "📝 Saved Texts:\n\n"
    for i, t in enumerate(db["texts"], 1):
        msg += f"{i}. {t[:50]}...\n"
    await update.message.reply_text(msg)

async def cleartext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not db["texts"]:
        await update.message.reply_text("❌ No texts")
        return
    kb = [
        [InlineKeyboardButton(str(i+1), callback_data=f"deltext_{i}")]
        for i in range(len(db["texts"]))
    ]
    await update.message.reply_text(
        "Select text to delete:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def deltext_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    idx = int(q.data.split("_")[1])
    try:
        db["texts"].pop(idx)
        save()
        await q.edit_message_text("✅ Text Deleted")
    except:
        await q.edit_message_text("❌ Error")

async def clearalltext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    db["texts"].clear()
    save()
    await update.message.reply_text("✅ All texts removed")

# ===============================
# CHANNELS
# ===============================
async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    ch = update.message.text.replace("/addchannel", "", 1).strip()
    if not ch:
        await update.message.reply_text("❌ Send channel username or ID")
        return
    if ch not in db["channels"]:
        db["channels"].append(ch)
        save()
    await update.message.reply_text("✅ Channel Added")

async def removechannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    ch = update.message.text.replace("/removechannel", "", 1).strip()
    if ch in db["channels"]:
        db["channels"].remove(ch)
        save()
        await update.message.reply_text("✅ Channel Removed")
    else:
        await update.message.reply_text("❌ Channel not found")

async def listchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not db["channels"]:
        await update.message.reply_text("❌ No channels")
        return
    await update.message.reply_text("\n".join(db["channels"]))

# ===============================
# BROADCAST
# ===============================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not db["texts"]:
        await update.message.reply_text("❌ No text saved")
        return

    text = db["texts"][0] + "\n\n" + PROMO_SUFFIX
    sent = 0

    for ch in db["channels"]:
        try:
            await context.bot.send_message(
                chat_id=ch,
                text=text,
                parse_mode="HTML"
            )
            sent += 1
        except:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent} channels")

# ===============================
# STATUS
# ===============================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
    msg = f"""
📊 STATUS

📝 Texts: {len(db['texts'])}
🔘 Buttons: {len(db['buttons'])}
📡 Channels: {len(db['channels'])}

🕒 Time: {now}
"""
    await update.message.reply_text(styled(msg))

# ===============================
# ERROR HANDLER
# ===============================
async def error_handler(update, context):
    err = traceback.format_exc()
    await context.bot.send_message(
        OWNER_ID,
        f"🚨 BOT ERROR\n\n<pre>{err}</pre>",
        parse_mode="HTML"
    )

# ===============================
# APP INIT
# ===============================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("status", status))

app.add_handler(CommandHandler("settext", settext))
app.add_handler(CommandHandler("listtext", listtext))
app.add_handler(CommandHandler("cleartext", cleartext))
app.add_handler(CommandHandler("clearalltext", clearalltext))

app.add_handler(CommandHandler("addchannel", addchannel))
app.add_handler(CommandHandler("removechannel", removechannel))
app.add_handler(CommandHandler("listchannels", listchannels))

app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(deltext_cb, pattern="^deltext_"))

app.add_error_handler(error_handler)

print("🔥 YASH ADZ BOT STARTED")
app.run_polling()
