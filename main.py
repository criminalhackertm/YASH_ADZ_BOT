# main.py
import os, time, threading, logging
from datetime import datetime
from telebot import TeleBot, types
from config import BOT_TOKEN, OWNER_ID, PROMO_SUFFIX, FIRST_RUN_FLAG
from database import (
    save_promotion_text, get_promotion_text,
    save_buttons, get_buttons,
    save_channels, get_channels, remove_channel,
    save_autopost, get_autopost,
    save_autodelete, get_autodelete,
    add_pending, get_pending, replace_pending,
    add_stats, get_stats
)

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment (Choreo settings).")

bot = TeleBot(BOT_TOKEN, parse_mode=None)
logging.basicConfig(level=logging.INFO)

# ----- helper functions -----
def owner_check(uid):
    return OWNER_ID is not None and uid == OWNER_ID

def build_markup(buttons):
    if not buttons:
        return None
    kb = types.InlineKeyboardMarkup()
    # default one-button-per-row; you can later modify per-row layout easily
    for b in buttons:
        try:
            kb.add(types.InlineKeyboardButton(b.get("text","Button"), url=b.get("url","#")))
        except:
            continue
    return kb

def schedule_delete(chat_id, msg_id):
    # add to pending list (background worker will delete when time reached)
    add_pending(chat_id, msg_id, datetime.utcnow().isoformat())

def try_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
        return True
    except Exception as e:
        logging.debug("delete failed %s@%s -> %s", msg_id, chat_id, e)
        return False

# ----- background workers -----
def pending_worker():
    while True:
        try:
            ttl = get_autodelete()
            pend = get_pending()
            if not pend:
                time.sleep(3)
                continue
            now = datetime.utcnow().timestamp()
            new = []
            deleted_count = 0
            for r in pend:
                try:
                    send_time = datetime.fromisoformat(r["send_time"]).timestamp()
                except:
                    send_time = 0
                age = now - send_time
                if ttl and age >= ttl:
                    # try delete
                    if try_delete(r["chat_id"], r["message_id"]):
                        deleted_count += 1
                else:
                    new.append(r)
            if len(new) != len(pend):
                replace_pending(new)
            time.sleep(3)
        except Exception:
            logging.exception("pending_worker crashed")
            time.sleep(5)

def autopost_worker():
    while True:
        try:
            interval, text = get_autopost()
            if interval and int(interval) > 0:
                # send text + buttons to all channels
                buttons = get_buttons()
                chs = get_channels()
                sent = failed = 0
                for ch in chs:
                    try:
                        markup = build_markup(buttons)
                        msg = bot.send_message(f"@{ch}" if not str(ch).startswith("-100") else str(ch), text + PROMO_SUFFIX, reply_markup=markup)
                        sent += 1
                        # schedule deletion
                        if get_autodelete():
                            schedule_delete(str(msg.chat.id), msg.message_id)
                    except Exception as e:
                        logging.warning("autopost send failed %s -> %s", ch, e)
                        failed += 1
                    time.sleep(1.2)
                add_stats(sent=sent, failed=failed, autopost=1)
                logging.info("Autopost done: sent=%s failed=%s", sent, failed)
                time.sleep(int(interval))
            else:
                time.sleep(3)
        except Exception:
            logging.exception("autopost_worker crashed")
            time.sleep(5)

# start workers
threading.Thread(target=pending_worker, daemon=True).start()
threading.Thread(target=autopost_worker, daemon=True).start()

# ----- first run notify (owner only) -----
def is_first_run():
    return not os.path.exists(FIRST_RUN_FLAG)

def mark_first_run():
    with open(FIRST_RUN_FLAG, "w") as f:
        f.write("deployed")

def notify_owner_deploy():
    try:
        if is_first_run() and OWNER_ID:
            bot.send_message(OWNER_ID, "🚀 *YASH ADZ BOT Deployed Successfully!* Bot is now live.", parse_mode="Markdown")
            mark_first_run()
    except Exception as e:
        logging.warning("notify failed: %s", e)

# call notify on startup (non-blocking)
threading.Thread(target=notify_owner_deploy, daemon=True).start()

# ----- COMMANDS -----
@bot.message_handler(commands=['start'])
def cmd_start(m):
    if owner_check(m.from_user.id) and is_first_run():
        bot.reply_to(m, "✅ *Bot Deployed Successfully!* You are OWNER. Use /help to manage.", parse_mode="Markdown")
        mark_first_run()
        return
    bot.reply_to(m, "🟢 YASH ADZ BOT is running. Use /help", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def cmd_help(m):
    text = (
        "*YASH ADZ BOT — Commands*\n\n"
        "/start — check status\n"
        "/help — this help menu\n\n"
        "OWNER (only) commands:\n"
        "/settext — set promotion text (bot will ask)\n"
        "/setbuttons — set buttons (line per button: Name - https://link)\n"
        "/addchannel — add channel (username or -100ID)\n"
        "/removechannel — remove channel\n"
        "/listchannels — list saved channels\n"
        "/broadcast — manual broadcast (sends saved text+buttons)\n"
        "/preview — preview saved promo and send now\n"
        "/autopost_on — enable autopost (bot will ask interval seconds and text)\n"
        "/autopost_off — disable autopost\n"
        "/autodelete_on — enable auto-delete (bot will ask seconds)\n"
        "/autodelete_off — disable auto-delete\n"
        "/status — show status & stats\n"
    )
    bot.reply_to(m, text, parse_mode="Markdown")

# set text
@bot.message_handler(commands=['settext'])
def cmd_settext(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "✍️ Send the promotion text (it will be saved):")
    bot.register_next_step_handler(msg, lambda mm: (save_promotion_text(mm.text), bot.reply_to(mm, "✅ Promotion text saved!")))

# set buttons
@bot.message_handler(commands=['setbuttons'])
def cmd_setbuttons(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "🔘 Send buttons line-by-line as:\nButton Name - https://link")
    bot.register_next_step_handler(msg, _handle_buttons_save)

def _handle_buttons_save(m):
    try:
        lines = m.text.splitlines()
        pairs = []
        for l in lines:
            if "-" in l:
                name, url = l.split("-",1)
                pairs.append([name.strip(), url.strip()])
        save_buttons(pairs)
        bot.reply_to(m, f"✅ {len(pairs)} button(s) saved.")
    except Exception as e:
        bot.reply_to(m, f"❌ Error saving buttons: {e}")

# add channel
@bot.message_handler(commands=['addchannel'])
def cmd_addchannel(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "📡 Send channel username (without @) or -100ID:")
    bot.register_next_step_handler(msg, lambda mm: (save_channels(mm.text.replace("@","").strip()), bot.reply_to(mm, f"✅ Channel added: {mm.text.strip()}")))

# remove channel
@bot.message_handler(commands=['removechannel'])
def cmd_removechannel(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "📡 Send channel username (without @) or -100ID to remove:")
    bot.register_next_step_handler(msg, lambda mm: (bot.reply_to(mm, "✅ Removed." ) if remove_channel(mm.text.strip()) else bot.reply_to(mm, "❌ Channel not found.")))

@bot.message_handler(commands=['listchannels'])
def cmd_listchannels(m):
    if not owner_check(m.from_user.id):
        return
    chs = get_channels()
    if not chs:
        bot.reply_to(m, "No channels configured.")
        return
    out = "📺 Channels:\n" + "\n".join([f"{i+1}. {c}" for i,c in enumerate(chs)])
    bot.reply_to(m, out)

# preview
@bot.message_handler(commands=['preview'])
def cmd_preview(m):
    if not owner_check(m.from_user.id):
        return
    text = get_promotion_text()
    buttons = get_buttons()
    if not text:
        return bot.reply_to(m, "❌ No promo text saved. Use /settext first.")
    kb = build_markup(buttons)
    sent = bot.send_message(m.chat.id, "🔎 *Preview of saved promotion:*\n\n" + text + PROMO_SUFFIX, parse_mode="Markdown", reply_markup=kb)
    # offer confirm/cancel
    kb2 = types.InlineKeyboardMarkup()
    kb2.add(types.InlineKeyboardButton("✅ Send to all channels", callback_data="preview_send"))
    kb2.add(types.InlineKeyboardButton("❌ Cancel", callback_data="preview_cancel"))
    bot.send_message(m.chat.id, "Confirm action:", reply_markup=kb2)

@bot.callback_query_handler(func=lambda c: c.data in ("preview_send","preview_cancel"))
def cb_preview(c):
    if not owner_check(c.from_user.id):
        bot.answer_callback_query(c.id, "Owner only", show_alert=True); return
    if c.data == "preview_cancel":
        bot.answer_callback_query(c.id, "Cancelled")
        bot.edit_message_text("❌ Preview cancelled.", c.message.chat.id, c.message.message_id)
        return
    bot.answer_callback_query(c.id, "Broadcast starting...")
    res = _do_broadcast()
    bot.send_message(c.message.chat.id, f"✅ Broadcast finished. Sent: {res['sent']} Failed: {res['failed']}")

# broadcast
def _do_broadcast():
    text = get_promotion_text()
    buttons = get_buttons()
    chs = get_channels()
    sent = failed = 0
    if not text:
        return {"ok":False, "msg":"No promo text", "sent":0, "failed":0}
    for ch in chs:
        try:
            markup = build_markup(buttons)
            msg = bot.send_message(f"@{ch}" if not str(ch).startswith("-100") else str(ch), text + PROMO_SUFFIX, reply_markup=markup)
            sent += 1
            if get_autodelete():
                schedule_id = str(msg.chat.id)
                schedule_delete(schedule_id, msg.message_id)
            time.sleep(1.2)
        except Exception as e:
            logging.warning("broadcast send failed %s -> %s", ch, e)
            failed += 1
    add_stats(sent=sent, failed=failed, broadcast=1)
    return {"ok":True, "sent":sent, "failed":failed}

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(m):
    if not owner_check(m.from_user.id):
        return
    bot.reply_to(m, "⏳ Broadcasting to all configured channels...")
    res = _do_broadcast()
    bot.reply_to(m, f"📢 Broadcast completed. ✅ Sent: {res['sent']} ❌ Failed: {res['failed']}")

# autopost on
@bot.message_handler(commands=['autopost_on'])
def cmd_autopost_on(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "⏱ Send autopost interval in seconds (e.g. 3600) or 0 to cancel:")
    bot.register_next_step_handler(msg, _save_autopost_step)

def _save_autopost_step(m):
    try:
        t = int(m.text.strip())
        # ask for autopost text if enabling
        if t > 0:
            bot.reply_to(m, "✍️ Send the autopost text (this will be posted every interval):")
            bot.register_next_step_handler(m, lambda mm: (save_autopost(t, mm.text), bot.reply_to(mm, f"✅ Autopost enabled every {t} sec.")))
        else:
            save_autopost(0, "")
            bot.reply_to(m, "❌ Autopost disabled.")
    except:
        bot.reply_to(m, "❌ Invalid number.")

@bot.message_handler(commands=['autopost_off'])
def cmd_autopost_off(m):
    if not owner_check(m.from_user.id):
        return
    save_autopost(0, "")
    bot.reply_to(m, "✅ Autopost turned OFF.")

# autodelete on
@bot.message_handler(commands=['autodelete_on'])
def cmd_autodel_on(m):
    if not owner_check(m.from_user.id):
        return
    msg = bot.reply_to(m, "🗑 Enter auto-delete time in seconds (e.g. 60):")
    bot.register_next_step_handler(msg, _save_autodel_step)

def _save_autodel_step(m):
    try:
        t = int(m.text.strip())
        save_autodelete(t)
        bot.reply_to(m, f"✅ Auto-delete set to {t} seconds.")
    except:
        bot.reply_to(m, "❌ Invalid input.")

@bot.message_handler(commands=['autodelete_off'])
def cmd_autodel_off(m):
    if not owner_check(m.from_user.id):
        return
    save_autodelete(0)
    bot.reply_to(m, "✅ Auto-delete disabled.")

# status
@bot.message_handler(commands=['status'])
def cmd_status(m):
    if not owner_check(m.from_user.id):
        return
    interval, autopost_text = get_autopost()
    stats = get_stats()
    chs = get_channels()
    bot.reply_to(m,
        f"📡 *YASH ADZ BOT STATUS*\n\n"
        f"AutoPost Interval: `{interval}` sec\n"
        f"AutoDelete: `{get_autodelete()}` sec\n"
        f"Channels loaded: `{len(chs)}`\n"
        f"Stats — Broadcasts: {stats.get('broadcasts',0)}, Sent: {stats.get('sent',0)}, Failed: {stats.get('failed',0)}\n",
        parse_mode="Markdown"
    )

# safe polling loop
def run_polling():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            logging.exception("polling crashed, restarting: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    run_polling()