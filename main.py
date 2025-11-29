import os, time, threading, logging
from datetime import datetime
from telebot import TeleBot, types
from config import BOT_TOKEN, OWNER_ID, PROMO_SUFFIX
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
    raise SystemExit("❌ BOT_TOKEN missing in Render → Environment Variables")

bot = TeleBot(BOT_TOKEN, parse_mode=None)
logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------
# HELPERS
# -----------------------------------------------------
def owner(uid):
    return uid == OWNER_ID

def build_markup(buttons):
    if not buttons: return None
    kb = types.InlineKeyboardMarkup()

    for b in buttons:
        try:
            kb.add(types.InlineKeyboardButton(b["text"], url=b["url"]))
        except:
            continue
    return kb

def schedule_delete(chat_id, msg_id):
    add_pending(chat_id, msg_id, datetime.utcnow().isoformat())

def try_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
        return True
    except:
        return False


# -----------------------------------------------------
# BACKGROUND WORKER — AUTO DELETE
# -----------------------------------------------------
def pending_worker():
    while True:
        try:
            ttl = get_autodelete()
            pend = get_pending()

            if not ttl or not pend:
                time.sleep(3)
                continue

            now = datetime.utcnow().timestamp()
            new_list = []

            for r in pend:
                t = datetime.fromisoformat(r["send_time"]).timestamp()
                if now - t >= ttl:
                    try_delete(r["chat_id"], r["message_id"])
                else:
                    new_list.append(r)

            replace_pending(new_list)
            time.sleep(3)

        except Exception as e:
            logging.exception("pending_worker crashed")
            time.sleep(5)


# -----------------------------------------------------
# BACKGROUND WORKER — AUTO POST
# -----------------------------------------------------
def autopost_worker():
    while True:
        try:
            interval, text = get_autopost()

            if interval > 0:
                buttons = get_buttons()
                channels = get_channels()

                sent = fail = 0
                for ch in channels:
                    try:
                        markup = build_markup(buttons)
                        msg = bot.send_message(
                            ch if str(ch).startswith("-100") else f"@{ch}",
                            text + PROMO_SUFFIX,
                            reply_markup=markup
                        )
                        sent += 1

                        if get_autodelete():
                            schedule_delete(msg.chat.id, msg.message_id)

                        time.sleep(1.2)
                    except:
                        fail += 1

                add_stats(sent=sent, failed=fail, autopost=1)
                time.sleep(interval)

            else:
                time.sleep(3)

        except Exception:
            logging.exception("autopost crashed")
            time.sleep(5)


# Start background threads
threading.Thread(target=pending_worker, daemon=True).start()
threading.Thread(target=autopost_worker, daemon=True).start()


# -----------------------------------------------------
# COMMANDS
# -----------------------------------------------------

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.reply_to(m, "✅ YASH ADZ BOT RUNNING!\nUse /help", parse_mode="Markdown")


@bot.message_handler(commands=['help'])
def help_cmd(m):
    bot.reply_to(m,
        "*YASH ADZ BOT COMMANDS*\n\n"
        "/settext – Save promotion text\n"
        "/setbuttons – Save buttons\n"
        "/addchannel – Add channel\n"
        "/removechannel – Remove channel\n"
        "/listchannels – List channels\n"
        "/broadcast – Manual send\n"
        "/preview – Preview promotion\n\n"
        "AUTO SYSTEM:\n"
        "/autopost_on – Enable autopost\n"
        "/autopost_off – Disable autopost\n"
        "/autodelete_on – Enable auto delete\n"
        "/autodelete_off – Disable auto delete\n"
        "/status – System status",
        parse_mode="Markdown"
    )


# SET TEXT
@bot.message_handler(commands=['settext'])
def settext(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Send promotion text:")
    bot.register_next_step_handler(msg, lambda mm: (save_promotion_text(mm.text), bot.reply_to(mm, "✔ Saved!")))


# SET BUTTONS
@bot.message_handler(commands=['setbuttons'])
def setbuttons(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Line-by-line:\nName - https://link")
    bot.register_next_step_handler(msg, _save_buttons)

def _save_buttons(m):
    arr = []
    for l in m.text.splitlines():
        if "-" in l:
            name, url = l.split("-", 1)
            arr.append({"text": name.strip(), "url": url.strip()})

    save_buttons(arr)
    bot.reply_to(m, f"✔ {len(arr)} Button(s) Saved!")


# ADD CHANNEL
@bot.message_handler(commands=['addchannel'])
def add_channel_cmd(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Send channel username or -100ID:")
    bot.register_next_step_handler(msg, lambda mm: (save_channels(mm.text.strip()), bot.reply_to(mm, "✔ Channel Added")))


# REMOVE CHANNEL
@bot.message_handler(commands=['removechannel'])
def remove_channel_cmd(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Send channel username to remove:")
    bot.register_next_step_handler(msg, lambda mm: bot.reply_to(mm, "✔ Removed" if remove_channel(mm.text.strip()) else "❌ Not found"))


# LIST
@bot.message_handler(commands=['listchannels'])
def listchannels(m):
    if not owner(m.from_user.id): return
    ch = get_channels()
    bot.reply_to(m, "📡 Saved Channels:\n" + "\n".join(ch))


# PREVIEW
@bot.message_handler(commands=['preview'])
def preview_cmd(m):
    if not owner(m.from_user.id): return
    text = get_promotion_text()
    if not text: return bot.reply_to(m, "❌ No text saved")

    kb = build_markup(get_buttons())
    bot.send_message(m.chat.id, "🔍 Preview:\n\n" + text + PROMO_SUFFIX, reply_markup=kb)


# BROADCAST
@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(m):
    if not owner(m.from_user.id): return

    text = get_promotion_text()
    if not text: return bot.reply_to(m, "❌ No text saved")

    buttons = get_buttons()
    channels = get_channels()

    sent = fail = 0

    for c in channels:
        try:
            kb = build_markup(buttons)
            msg = bot.send_message(
                c if str(c).startswith("-100") else f"@{c}",
                text + PROMO_SUFFIX,
                reply_markup=kb
            )
            sent += 1

            if get_autodelete():
                schedule_delete(msg.chat.id, msg.message_id)

            time.sleep(1.2)
        except:
            fail += 1

    bot.reply_to(m, f"📢 Broadcast Done\n✔ Sent: {sent}\n❌ Fail: {fail}")


# AUTOPost ON
@bot.message_handler(commands=['autopost_on'])
def autopost_on(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Send interval seconds (e.g., 3600):")
    bot.register_next_step_handler(msg, _save_autopost_1)

def _save_autopost_1(m):
    try:
        sec = int(m.text.strip())
        msg = bot.reply_to(m, "Send autopost text:")
        bot.register_next_step_handler(msg, lambda mm: (save_autopost(sec, mm.text), bot.reply_to(mm, "✔ Autopost Enabled")))
    except:
        bot.reply_to(m, "❌ Invalid")


# AUTOPost OFF
@bot.message_handler(commands=['autopost_off'])
def autopost_off(m):
    if not owner(m.from_user.id): return
    save_autopost(0, "")
    bot.reply_to(m, "✔ Autopost Disabled")


# AUTODELETE ON
@bot.message_handler(commands=['autodelete_on'])
def autodel_on(m):
    if not owner(m.from_user.id): return
    msg = bot.reply_to(m, "Enter delete time seconds:")
    bot.register_next_step_handler(msg, lambda mm: (save_autodelete(int(mm.text)), bot.reply_to(mm, "✔ Auto-delete active")))


# AUTODELETE OFF
@bot.message_handler(commands=['autodelete_off'])
def autodel_off(m):
    if not owner(m.from_user.id): return
    save_autodelete(0)
    bot.reply_to(m, "✔ Auto-delete disabled")


# STATUS
@bot.message_handler(commands=['status'])
def status_cmd(m):
    if not owner(m.from_user.id): return
    interval, text = get_autopost()
    stats = get_stats()
    bot.reply_to(
        m,
        f"📊 *BOT STATUS*\n\n"
        f"Autopost Interval: `{interval}` sec\n"
        f"Autodelete: `{get_autodelete()}` sec\n"
        f"Channels: {len(get_channels())}\n"
        f"Broadcasts: {stats.get('broadcasts',0)}\n"
        f"Sent: {stats.get('sent',0)}\n"
        f"Failed: {stats.get('failed',0)}",
        parse_mode="Markdown"
    )


def start():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            logging.error(e)
            time.sleep(5)

if __name__ == "__main__":
    start()