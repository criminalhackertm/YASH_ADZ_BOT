import os, time, threading, logging
from datetime import datetime
from telebot import TeleBot, types
from config import BOT_TOKEN, OWNER_ID, PROMO_SUFFIX, FIRST_RUN_FLAG
from database import (
    load_main_data, save_main_data,
    save_promotion_text, get_promotion_texts,
    save_buttons_for_text, get_buttons_for_text,
    save_channels, get_channels, remove_channel,
    save_autopost_schedule, get_autopost_schedules, remove_schedule,
    save_autodelete_for_text, get_autodelete_for_text,
    add_pending, get_pending, replace_pending,
    add_stats, get_stats, clear_all_texts, clear_all_buttons
)

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment — add it in Choreo env vars.")

bot = TeleBot(BOT_TOKEN, parse_mode=None)
logging.basicConfig(level=logging.INFO)

# --- helpers & styling ---
PROMO_SUFFIX = PROMO_SUFFIX  # imported from config

def stylish(text):
    # small wrapper that returns same text (could add unicode style)
    return text

def owner_check(uid):
    return OWNER_ID is not None and uid == OWNER_ID

def build_markup(buttons):
    if not buttons:
        return None
    kb = types.InlineKeyboardMarkup()
    # default 2 buttons per row if many
    row = []
    for i, b in enumerate(buttons, start=1):
        try:
            btn = types.InlineKeyboardButton(b.get("text","BTN"), url=b.get("url","#"))
            row.append(btn)
            if len(row) >= 2:
                kb.row(*row); row=[]
        except:
            continue
    if row:
        kb.row(*row)
    return kb

def format_seconds(s):
    # show seconds nicely in hours/min/sec
    s = int(s)
    if s % 3600 == 0:
        return f"{s//3600} hour(s)"
    if s % 60 == 0:
        return f"{s//60} minute(s)"
    return f"{s} second(s)"

# --- background workers: pending delete & scheduled autopost ---
def pending_worker():
    while True:
        try:
            pend = get_pending()
            if not pend:
                time.sleep(3); continue
            ttl_map = {}  # per message deletion handled by stored send_time + stored autodelete
            now = datetime.utcnow().timestamp()
            new = []
            for r in pend:
                try:
                    send_time = datetime.fromisoformat(r["send_time"]).timestamp()
                except:
                    send_time = 0
                autodel = int(r.get("autodelete", 0) or 0)
                if autodel and (now - send_time) >= autodel:
                    try:
                        bot.delete_message(r["chat_id"], r["message_id"])
                        logging.info("Deleted %s @ %s", r["message_id"], r["chat_id"])
                    except Exception as e:
                        logging.debug("delete failed %s@%s -> %s", r["message_id"], r["chat_id"], e)
                else:
                    new.append(r)
            if len(new) != len(pend):
                replace_pending(new)
            time.sleep(5)
        except Exception:
            logging.exception("pending_worker crashed")
            time.sleep(5)

def schedule_worker():
    # checks schedules every 30s and triggers posts whose scheduled_time (HH:MM) matches current local time
    while True:
        try:
            schedules = get_autopost_schedules()  # list of dicts: {"id", "hhmm", "text_id", "buttons", "autodelete"}
            if not schedules:
                time.sleep(10); continue
            now_local = datetime.now()
            hm = now_local.strftime("%H:%M")
            today = now_local.strftime("%Y-%m-%d")
            for s in schedules:
                last_run = s.get("last_run_date")
                if s.get("hhmm") == hm and last_run != today:
                    # perform scheduled send
                    text_id = s.get("text_id")
                    texts = get_promotion_texts()
                    text_obj = next((t for t in texts if t["id"] == text_id), None)
                    if not text_obj:
                        continue
                    buttons = get_buttons_for_text(text_id)
                    for ch in get_channels():
                        try:
                            markup = build_markup(buttons)
                            target = f"@{ch}" if not str(ch).startswith("-100") else str(ch)
                            sent = bot.send_message(target, text_obj["text"] + PROMO_SUFFIX, reply_markup=markup)
                            if s.get("autodelete"):
                                add_pending(str(sent.chat.id), sent.message_id, datetime.utcnow().isoformat(), autodelete=s.get("autodelete"))
                        except Exception as e:
                            logging.warning("scheduled send failed %s -> %s", ch, e)
                        time.sleep(1.2)
                    # update last_run_date on schedule
                    s["last_run_date"] = today
                    save_autopost_schedule(s, update=True)
                    add_stats(autopost=1)
            time.sleep(30)
        except Exception:
            logging.exception("schedule_worker crashed")
            time.sleep(10)

# run background threads
threading.Thread(target=pending_worker, daemon=True).start()
threading.Thread(target=schedule_worker, daemon=True).start()

# --- first-run notify ---
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

threading.Thread(target=notify_owner_deploy, daemon=True).start()

# --- COMMANDS: owner-only guard wherever needed ---
@bot.message_handler(commands=['start'])
def cmd_start(m):
    if owner_check(m.from_user.id) and is_first_run():
        bot.reply_to(m, stylish("✅ *Bot Deployed Successfully!* You are OWNER. Use /help to manage."), parse_mode="Markdown")
        mark_first_run()
        return
    bot.reply_to(m, stylish("🟢 YASH ADZ BOT is running. Use /help"), parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def cmd_help(m):
    help_text = (
        "✨💠 𝙔𝘼𝙎𝙃 𝘼𝘿𝙕 𝘽𝙊𝙏 — 𝙊𝙬𝙣𝙚𝙧 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨 💠✨\n\n"
        "📌 𝘽𝙖𝙨𝙞𝙘 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨:\n• /start — Bot status check\n• /help — Show this help menu\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📝 𝙏𝙀𝙓𝙏 𝙈𝘼𝙉𝘼𝙂𝙀𝙈𝙀𝙉𝙏:\n• /settext — New promo text add\n• /listtext — Saved texts list\n• /cleartext — Remove selected text\n• /clearalltext — Remove all texts\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🔘 𝘽𝙐𝙏𝙏𝙊𝙉 𝙎𝙔𝙎𝙏𝙀𝙈:\n• /setbuttons — Add buttons for selected text\n• /listbuttons — Show button sets\n• /clearbuttons — Delete selected button set\n• /clearallbuttons — Remove all buttons\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📡 𝘾𝙃𝘼𝙉𝙉𝙀𝙇 𝙈𝘼𝙉𝘼𝙂𝙀𝙈𝙀𝙉𝙏:\n• /addchannel — Add channel (public/private)\n• /removechannel — Remove channel\n• /listchannels — Show all channels\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📢 𝘽𝙍𝙊𝘼𝘿𝘾𝘼𝙎𝙏 & 𝙋𝙍𝙀𝙑𝙄𝙀𝙒:\n• /preview — Preview selected text + buttons\n• /broadcast — Send promo to all channels\n(Manual broadcast ke baad auto-delete ka option aayega)\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⏰ 𝘼𝙐𝙏𝙊 𝙋𝙊𝙎𝙏 𝙎𝘾𝙃𝙀𝘿𝙐𝙇𝙀𝙍:\n• /schedule — Set exact time posting (HH:MM 24h)\n• /viewschedule — Show all scheduled posts\n• /clearschedule — Delete specific schedule\n• /clearallschedule — Delete all schedules\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🗑 𝘼𝙐𝙏𝙊 𝘿𝙀𝙇𝙀𝙏𝙀 (𝙋𝙊𝙎𝙏 𝙏𝙄𝙈𝙀):\n• Every broadcast / auto-post ke baad:\n   - Set Auto Delete Time (in sec/min/hr)\n   - Or Skip Auto Delete\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📊 𝙎𝙏𝘼𝙏𝙐𝙎:\n• /status — Show system stats\n\n"
        "━━━━━━━━━━━━━━━\n\n"
    )
    bot.reply_to(m, stylish(help_text), parse_mode="Markdown")

# --- TEXT MANAGEMENT: multi-text support ---
@bot.message_handler(commands=['settext'])
def cmd_settext(m):
    if not owner_check(m.from_user.id): return
    msg = bot.reply_to(m, "✍️ Send the promo text (it will be saved).")
    bot.register_next_step_handler(msg, _save_text_step)

def _save_text_step(m):
    try:
        # load current texts, create new id
        texts = get_promotion_texts()
        next_id = max([t["id"] for t in texts], default=0) + 1
        save_promotion_text(next_id, m.text)
        bot.reply_to(m, f"✅ Text saved as ID `{next_id}`.")
    except Exception as e:
        bot.reply_to(m, f"❌ Error saving text: {e}\nSolution: Retry /settext and send plain text (no large files).")

@bot.message_handler(commands=['listtext'])
def cmd_listtext(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts:
        return bot.reply_to(m, "No saved texts.")
    out = "📝 Saved Texts:\n"
    for t in texts:
        out += f"{t['id']}. {t['text'][:80].replace('\\n',' ')}\n"
    bot.reply_to(m, out)

@bot.message_handler(commands=['cleartext'])
def cmd_cleartext(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts:
        return bot.reply_to(m, "No texts to remove.")
    if len(texts) == 1:
        # single -> remove immediately
        tid = texts[0]["id"]
        save_promotion_text(tid, None, remove=True)
        return bot.reply_to(m, f"✅ Removed text ID {tid}.")
    # multiple -> ask which ID(s)
    msg = bot.reply_to(m, "Send ID(s) to remove separated by comma (e.g. `1,3`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, _cleartext_step)

def _cleartext_step(m):
    try:
        ids = [int(x.strip()) for x in m.text.split(",") if x.strip().isdigit()]
        removed = 0
        for tid in ids:
            if save_promotion_text(tid, None, remove=True):
                removed += 1
        bot.reply_to(m, f"✅ Removed {removed} text(s).")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}\nSolution: Send comma separated numeric IDs like `1,2`.")

@bot.message_handler(commands=['clearalltext'])
def cmd_clearalltext(m):
    if not owner_check(m.from_user.id): return
    clear_all_texts()
    bot.reply_to(m, "🧹 All texts removed.")

# --- BUTTONS per text ---
@bot.message_handler(commands=['setbuttons'])
def cmd_setbuttons(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts:
        return bot.reply_to(m, "No saved texts. Use /settext first.")
    msg = bot.reply_to(m, "Send target Text ID to attach buttons to:")
    bot.register_next_step_handler(msg, _setbuttons_choose_text)

def _setbuttons_choose_text(m):
    try:
        tid = int(m.text.strip())
        bot.reply_to(m, "Now send buttons line-by-line as `Name - https://link`")
        bot.register_next_step_handler(m, lambda mm: _save_buttons_for_text(tid, mm))
    except:
        bot.reply_to(m, "❌ Invalid ID. Solution: Check /listtext and reply numeric ID.")

def _save_buttons_for_text(tid, m):
    try:
        lines = [l for l in m.text.splitlines() if "-" in l]
        pairs = []
        for l in lines:
            name, url = l.split("-",1)
            pairs.append({"text": name.strip(), "url": url.strip()})
        save_buttons_for_text(tid, pairs)
        bot.reply_to(m, f"✅ {len(pairs)} button(s) saved for Text ID {tid}.")
    except Exception as e:
        bot.reply_to(m, f"❌ Error saving buttons: {e}")

@bot.message_handler(commands=['listbuttons'])
def cmd_listbuttons(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    out = ""
    for t in texts:
        btns = get_buttons_for_text(t["id"])
        out += f"Text {t['id']} — {len(btns)} button(s)\n"
    bot.reply_to(m, out or "No button sets.")

@bot.message_handler(commands=['clearbuttons'])
def cmd_clearbuttons(m):
    if not owner_check(m.from_user.id): return
    msg = bot.reply_to(m, "Send Text ID to clear buttons for (or `all`):")
    bot.register_next_step_handler(msg, _clearbuttons_step)

def _clearbuttons_step(m):
    txt = m.text.strip().lower()
    if txt == "all":
        clear_all_buttons(); return bot.reply_to(m, "✅ Cleared all button sets.")
    try:
        tid = int(txt)
        save_buttons_for_text(tid, [], remove=True)
        bot.reply_to(m, f"✅ Buttons cleared for Text ID {tid}.")
    except:
        bot.reply_to(m, "❌ Invalid input.")

# --- CHANNEL management ---
@bot.message_handler(commands=['addchannel'])
def cmd_addchannel(m):
    if not owner_check(m.from_user.id): return
    msg = bot.reply_to(m, "📡 Send channel username (without @) or -100ID:")
    bot.register_next_step_handler(msg, lambda mm: (save_channels(mm.text.replace("@","").strip()), bot.reply_to(mm, f"✅ Channel added: {mm.text.strip()}")))

@bot.message_handler(commands=['removechannel'])
def cmd_removechannel(m):
    if not owner_check(m.from_user.id): return
    msg = bot.reply_to(m, "📡 Send channel username (without @) or -100ID to remove:")
    bot.register_next_step_handler(msg, lambda mm: (remove_channel(mm.text.strip()) and bot.reply_to(mm, "✅ Removed.") or bot.reply_to(mm, "❌ Channel not found.")))

@bot.message_handler(commands=['listchannels'])
def cmd_listchannels(m):
    if not owner_check(m.from_user.id): return
    chs = get_channels()
    if not chs: return bot.reply_to(m, "No channels configured.")
    out = "📺 Channels:\n" + "\n".join([f"{i+1}. {c}" for i,c in enumerate(chs)])
    bot.reply_to(m, out)

# --- preview & broadcast ---
@bot.message_handler(commands=['preview'])
def cmd_preview(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts: return bot.reply_to(m, "No promo texts saved.")
    if len(texts) == 1:
        tid = texts[0]["id"]
    else:
        bot.reply_to(m, "Send Text ID to preview:")
        bot.register_next_step_handler(m, _preview_choose)
        return
    _do_preview(m.chat.id, tid, m)

def _preview_choose(m):
    try:
        tid = int(m.text.strip())
        _do_preview(m.chat.id, tid, m)
    except:
        bot.reply_to(m, "❌ Invalid ID.")

def _do_preview(chat_id, text_id, m_origin):
    text = next((t for t in get_promotion_texts() if t["id"]==text_id), None)
    if not text: return bot.reply_to(m_origin, "Text not found.")
    buttons = get_buttons_for_text(text_id)
    kb = build_markup(buttons)
    sent = bot.send_message(chat_id, "🔎 *Preview:*\n\n" + text["text"] + PROMO_SUFFIX, parse_mode="Markdown", reply_markup=kb)
    kb2 = types.InlineKeyboardMarkup()
    kb2.add(types.InlineKeyboardButton("✅ Send to all channels", callback_data=f"preview_send|{text_id}"))
    kb2.add(types.InlineKeyboardButton("❌ Cancel", callback_data="preview_cancel"))
    bot.send_message(chat_id, "Confirm:", reply_markup=kb2)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("preview_"))
def cb_preview(c):
    if not owner_check(c.from_user.id):
        bot.answer_callback_query(c.id, "Owner only.", show_alert=True); return
    if c.data == "preview_cancel":
        bot.answer_callback_query(c.id, "Cancelled"); bot.edit_message_text("❌ Preview cancelled.", c.message.chat.id, c.message.message_id)
        return
    # preview_send|<id>
    _, tid = c.data.split("|",1)
    tid = int(tid)
    bot.answer_callback_query(c.id, "Broadcast starting...")
    res = _do_broadcast_by_text(tid)
    bot.send_message(c.message.chat.id, f"✅ Broadcast finished. Sent: {res['sent']} Failed: {res['failed']}")

def _do_broadcast_by_text(text_id, m_origin=None):
    text_obj = next((t for t in get_promotion_texts() if t["id"]==text_id), None)
    if not text_obj:
        return {"ok":False,"sent":0,"failed":0,"msg":"no text"}
    buttons = get_buttons_for_text(text_id)
    sent = failed = 0
    for ch in get_channels():
        try:
            markup = build_markup(buttons)
            target = f"@{ch}" if not str(ch).startswith("-100") else str(ch)
            msg = bot.send_message(target, text_obj["text"] + PROMO_SUFFIX, reply_markup=markup)
            sent += 1
            # schedule delete if set
            autodel = get_autodelete_for_text(text_id)
            if autodel:
                add_pending(str(msg.chat.id), msg.message_id, datetime.utcnow().isoformat(), autodelete=autodel)
            time.sleep(1.2)
        except Exception as e:
            logging.warning("broadcast send failed %s -> %s", ch, e)
            failed += 1
    add_stats(broadcast=1, sent=sent, failed=failed)
    return {"ok":True,"sent":sent,"failed":failed}

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts: return bot.reply_to(m, "No texts to broadcast.")
    if len(texts) == 1:
        res = _do_broadcast_by_text(texts[0]["id"], m)
        return bot.reply_to(m, f"📢 Broadcast done. ✅ Sent: {res['sent']} ❌ Failed: {res['failed']}")
    bot.reply_to(m, "Which text ID to broadcast?"); bot.register_next_step_handler(m, _broadcast_choose)

def _broadcast_choose(m):
    try:
        tid = int(m.text.strip()); res = _do_broadcast_by_text(tid); bot.reply_to(m, f"📢 Broadcast done. ✅ Sent: {res['sent']} ❌ Failed: {res['failed']}")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

# --- scheduling: exact HH:MM entries (daily) ---
@bot.message_handler(commands=['schedule'])
def cmd_schedule(m):
    if not owner_check(m.from_user.id): return
    texts = get_promotion_texts()
    if not texts: return bot.reply_to(m, "No texts saved.")
    bot.reply_to(m, "Send schedule in format: `HH:MM | text_id | autodelete_seconds_or_0` (24h). Example:\n`22:00 | 2 | 3600`", parse_mode="Markdown")
    bot.register_next_step_handler(m, _save_schedule_step)

def _save_schedule_step(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        hhmm, tid_s, autodel_s = parts[0], parts[1], parts[2] if len(parts)>2 else "0"
        datetime.strptime(hhmm, "%H:%M")  # validate
        tid = int(tid_s)
        autodel = int(autodel_s)
        save_autopost_schedule(hhmm, tid, autodel)
        bot.reply_to(m, f"✅ Schedule saved: {hhmm} for Text ID {tid} (autodel {autodel}s)")
    except Exception as e:
        bot.reply_to(m, f"❌ Invalid format or error: {e}\nSolution: Use `HH:MM | text_id | autodelete_seconds`")

@bot.message_handler(commands=['viewschedule'])
def cmd_viewschedule(m):
    if not owner_check(m.from_user.id): return
    s = get_autopost_schedules()
    if not s: return bot.reply_to(m, "No schedules set.")
    out = "⏰ Schedules:\n"
    for i,sc in enumerate(s, start=1):
        out += f"{i}. {sc.get('hhmm')} -> TextID {sc.get('text_id')} (autodel {sc.get('autodelete',0)}s)\n"
    bot.reply_to(m, out)

@bot.message_handler(commands=['clearschedule'])
def cmd_clearschedule(m):
    if not owner_check(m.from_user.id): return
    msg = bot.reply_to(m, "Send schedule index to remove (from /viewschedule):")
    bot.register_next_step_handler(msg, lambda mm: (remove_schedule(int(mm.text.strip())), bot.reply_to(mm, "✅ Removed.")))

@bot.message_handler(commands=['clearallschedule'])
def cmd_clearallschedule(m):
    if not owner_check(m.from_user.id): return
    # remove all schedules
    save_autopost_schedule(None, None, None, clear_all=True)
    bot.reply_to(m, "✅ All schedules cleared.")

# --- status stylish ---
@bot.message_handler(commands=['status'])
def cmd_status(m):
    if not owner_check(m.from_user.id): return
    stats = get_stats()
    chs = get_channels()
    texts = get_promotion_texts()
    out = (
           "✨📊 *YASH ADZ BOT — System Status*\n\n"
        f"📡 Channels: {len(chs)}\n"
        f"📝 Saved texts: {len(texts)}\n"
        f"📤 Broadcasts sent: {stats.get('broadcasts',0)}\n"
        f"🔁 Autoposts: {stats.get('autoposts',0)}\n"
        f"✅ Sent: {stats.get('sent',0)}  ❌ Failed: {stats.get('failed',0)}\n"
        f"\n⚡ {PROMO_SUFFIX}"
    )
    bot.reply_to(m, stylish(out), parse_mode="Markdown")

# safe polling loop
def run_polling():
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=60)
        except Exception as e:
            logging.exception("polling crashed, restarting: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    run_polling()
