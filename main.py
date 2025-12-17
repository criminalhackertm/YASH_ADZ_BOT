import os, time, threading, logging
from datetime import datetime
from telebot import TeleBot, types
from config import BOT_TOKEN, OWNER_ID, PROMO_SUFFIX, DATA_FILE, PENDING_FILE, STATS_FILE, FIRST_RUN_FLAG
import database

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment (Render / Choreo settings).")

bot = TeleBot(BOT_TOKEN, parse_mode="Markdown")
logging.basicConfig(level=logging.INFO)

# ---- helpers ----
def owner_check(uid):
    return OWNER_ID is not None and uid == OWNER_ID

def build_markup_from_rows(rows):
    if not rows: return None
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        buttons = []
        for b in r:
            buttons.append(types.InlineKeyboardButton(b.get("text","Btn"), url=b.get("url","#")))
        kb.add(*buttons)
    return kb

def iso_now():
    return datetime.utcnow().isoformat()

# ---- Background workers: pending delete & schedule dispatcher ----
def pending_worker():
    while True:
        try:
            cfg = database.load_main(DATA_FILE)
            ttl = None
            # pending list
            pend = cfg.get("pending",[])
            new = []
            now = datetime.utcnow().timestamp()
            # get autodelete default? we will use individual schedule auto_delete if set
            for rec in pend:
                try:
                    send_time = datetime.fromisoformat(rec.get("send_time")).timestamp()
                except:
                    send_time = 0
                # If a TTL value exists in rec['ttl'] use it else skip
                ttl_val = rec.get("ttl",0)
                if ttl_val and (now - send_time) >= ttl_val:
                    try:
                        bot.delete_message(rec["chat_id"], rec["message_id"])
                        logging.info("Deleted msg %s@%s", rec["message_id"], rec["chat_id"])
                    except Exception as e:
                        logging.debug("delete failed %s", e)
                else:
                    new.append(rec)
            if len(new)!=len(pend):
                cfg["pending"] = new
                database.save_main(DATA_FILE, cfg)
            time.sleep(4)
        except Exception:
            logging.exception("pending_worker crash")
            time.sleep(5)

def schedule_worker():
    while True:
        try:
            cfg = database.load_main(DATA_FILE)
            scheds = cfg.get("schedules",[])
            if not scheds:
                time.sleep(5); continue
            now_local = datetime.now()
            hm = now_local.strftime("%H:%M")
            today = now_local.strftime("%Y-%m-%d")
            for s in scheds:
                last = s.get("last_sent_date")
                if s.get("time")==hm and last != today:
                    # perform scheduled send
                    text_obj = database.get_text(DATA_FILE, s["text_id"])
                    if not text_obj: continue
                    txt = text_obj["text"] + PROMO_SUFFIX
                    bset = database.get_button_set(DATA_FILE, text_obj.get("buttons_id"))
                    kb = build_markup_from_rows(bset["rows"]) if bset else None
                    sent=failed=0
                    for ch in cfg.get("channels",[]):
                        try:
                            target = f"@{ch}" if not str(ch).startswith("-100") else str(ch)
                            msg = bot.send_message(target, txt, reply_markup=kb, disable_web_page_preview=True)
                            sent += 1
                            # schedule delete for this message if schedule has auto_delete
                            if s.get("auto_delete"):
                                database.add_pending(DATA_FILE, str(msg.chat.id), msg.message_id, iso_now())
                                # add ttl in last pending entry
                                pend = database.get_pending(DATA_FILE)
                                if pend: pend[-1]["ttl"] = s.get("auto_delete")
                                database.replace_pending(DATA_FILE, pend)
                        except Exception as e:
                            logging.warning("schedule send fail %s -> %s", ch, e); failed+=1
                        time.sleep(1.2)
                    database.add_stats(DATA_FILE, sent=sent, failed=failed, autopost=1)
                    s["last_sent_date"] = today
                    database.save_main(DATA_FILE, cfg)
            time.sleep(50)
        except Exception:
            logging.exception("schedule_worker crash")
            time.sleep(10)

threading.Thread(target=pending_worker, daemon=True).start()
threading.Thread(target=schedule_worker, daemon=True).start()

# ---- first-run notify ----
def is_first_run():
    return not os.path.exists(FIRST_RUN_FLAG)
def mark_first_run():
    with open(FIRST_RUN_FLAG,"w") as f: f.write("deployed")
def notify_owner_deploy():
    try:
        if is_first_run() and OWNER_ID:
            bot.send_message(OWNER_ID, "🚀 *YASH ADZ BOT Deployed Successfully!* Bot is now live.", parse_mode="Markdown")
            mark_first_run()
    except Exception as e:
        logging.warning("notify failed: %s", e)
threading.Thread(target=notify_owner_deploy, daemon=True).start()

# ---- COMMANDS: owner-only and general ----
HELP_TEXT = (
"✨💠 𝙔𝘼𝙎𝙃 𝘼𝘿𝙕 𝘽𝙊𝙏 — 𝙊𝙬𝙣𝙚𝙧 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨 💠✨\n\n"
"📌 𝘽𝙖𝙨𝙞𝙘 𝘾𝙤𝙢𝙢𝙖𝙣𝙙𝙨:\n• /start — Bot status check\n• /help — Show this help menu\n\n"
"━━━━━━━━━━━━━━━\n\n"
"📝 𝙏𝙀𝙓𝙏 𝙈𝘼𝙉𝘼𝙂𝙀𝙈𝙀𝙉𝙏:\n• /settext — New promo text add\n• /listtext — Saved texts list\n• /cleartext — Remove selected text\n• /clearalltext — Remove all texts\n\n"
"━━━━━━━━━━━━━━━\n\n"
"🔘 𝘽𝙐𝙏𝙏𝙊𝙉 𝙎𝙔𝙎𝙏𝙀𝙈:\n• /setbuttons — Add buttons for selected text\n• /listbuttons — Show button sets\n• /clearbuttons — Delete selected button set\n• /clearallbuttons — Remove all buttons\n\n"
"━━━━━━━━━━━━━━━\n\n"
"📡 𝘾𝙃𝘼𝙉𝙉𝙀𝙇 𝙈𝘼𝙉𝘼𝙂𝙀𝙈𝙀𝙉𝙏:\n• /addchannel — Add channel (public/private)\n• /removechannel — Remove channel\n• /listchannels — Show all channels\n\n"
"━━━━━━━━━━━━━━━\n\n"
"📢 𝘽𝙍𝙊𝘼𝘿𝘾𝘼𝙎𝙏 & 𝙋𝙍𝙀𝙑𝙄𝙀𝙒:\n• /preview — Preview selected text + buttons\n• /broadcast — Send promo to all channels\n  (Manual broadcast ke baad auto-delete ka option aayega)\n\n"
"━━━━━━━━━━━━━━━\n\n"
"⏰ 𝘼𝙐𝙏𝙊 𝙋𝙊𝙎𝙏 𝙎𝘾𝙃𝙀𝘿𝙐𝙇𝙀𝙍:\n• /schedule — Set exact time posting (HH:MM 24h)\n• /viewschedule — Show all scheduled posts\n• /clearschedule — Delete specific schedule\n• /clearallschedule — Delete all schedules\n\n"
"━━━━━━━━━━━━━━━\n\n"
"🗑 𝘼𝙐𝙏𝙊 𝘿𝙀𝙇𝙀𝙏𝙀 (𝙋𝙊𝙎𝙏 𝙏𝙄𝙈𝙀):\n• Every broadcast / auto-post ke baad:\n   - Set Auto Delete Time (in sec/min/hr)\n   - Or Skip Auto Delete\n\n"
"━━━━━━━━━━━━━━━\n\n"
"📊 𝙎𝙏𝘼𝙏𝙐𝙎:\n• /status — Show system stats\n\n"
"━━━━━━━━━━━━━━━\n꧁▪️ @YashXNetwork ࿐"
)

@bot.message_handler(commands=['start'])
def cmd_start(m):
    if owner_check(m.from_user.id) and is_first_run():
        bot.reply_to(m, "✅ *Bot Deployed Successfully!* You are OWNER. Use /help to manage.", parse_mode="Markdown")
        mark_first_run()
        return
    bot.reply_to(m, "🟢 YASH ADZ BOT is running. Use /help", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def cmd_help(m):
    bot.reply_to(m, HELP_TEXT, parse_mode="Markdown")

# Set text
@bot.message_handler(commands=['settext'])
def cmd_settext(m):
    if not owner_check(m.from_user.id): return
    sent = bot.reply_to(m, "✍️ Send the promotion text. (Will save exactly as you send — clickable links preserved)")
    bot.register_next_step_handler(sent, lambda mm: (database.add_text(DATA_FILE, mm.text), bot.reply_to(mm, "✅ Text saved.")))

@bot.message_handler(commands=['listtext'])
def cmd_listtext(m):
    if not owner_check(m.from_user.id): return
    texts = database.list_texts(DATA_FILE)
    if not texts: return bot.reply_to(m, "No saved texts.")
    out = "📝 Saved Texts:\n"
    for t in texts:
        out += f"{t['id']}. {t['text'][:80]}...\n"
    bot.reply_to(m, out)

@bot.message_handler(commands=['cleartext'])
def cmd_cleartext(m):
    if not owner_check(m.from_user.id): return
    texts = database.list_texts(DATA_FILE)
    if not texts: return bot.reply_to(m,"No texts to remove.")
    kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for t in texts:
        kb.add(str(t['id']))
    kb.add("Cancel")
    bot.reply_to(m, "Send the number of text to remove (or Cancel):", reply_markup=kb)
    bot.register_next_step_handler(m, lambda mm: handle_cleartext(mm))

def handle_cleartext(m):
    if m.text=="Cancel": return bot.reply_to(m,"Cancelled.")
    try:
        tid = int(m.text.strip())
        database.remove_text(DATA_FILE, tid)
        bot.reply_to(m, f"✅ Removed text {tid}")
    except:
        bot.reply_to(m, "❌ Invalid selection.")

@bot.message_handler(commands=['clearalltext'])
def cmd_clearalltext(m):
    if not owner_check(m.from_user.id): return
    database.clear_all_texts(DATA_FILE)
    bot.reply_to(m,"✅ All texts removed.")

# Buttons
@bot.message_handler(commands=['setbuttons'])
def cmd_setbuttons(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "🔘 How many rows of buttons? (send number e.g. 2)")
    bot.register_next_step_handler(m, lambda mm: handle_rows_count(mm))

def handle_rows_count(m):
    try:
        rows = int(m.text.strip())
        if rows<=0: raise ValueError
        steps = []
        # collect row counts
        bot.reply_to(m, "Now send counts per row separated by space. Example for 2 rows: '1 3'")
        bot.register_next_step_handler(m, lambda mm: collect_counts(mm, rows))
    except:
        bot.reply_to(m,"❌ Invalid number. Cancel and retry with /setbuttons.")

def collect_counts(m, rows):
    parts = m.text.strip().split()
    if len(parts)!=rows:
        return bot.reply_to(m,"❌ Count mismatch. Restart /setbuttons.")
    try:
        counts = [int(p) for p in parts]
    except:
        return bot.reply_to(m,"❌ Invalid counts.")
    # now request button names & links row by row
    state = {"rows":[], "row_index":0, "counts":counts}
    bot.reply_to(m, f"Start sending buttons for row 1. Format per button:\nName - https://link")
    bot.register_next_step_handler(m, lambda mm: collect_buttons_row(mm, state))

def collect_buttons_row(m, state):
    # accumulate current row
    try:
        expected = state["counts"][state["row_index"]]
        lines = m.text.splitlines()
        all_pairs=[]
        for line in lines:
            if "-" in line:
                n,l = line.split("-",1); all_pairs.append({"text":n.strip(),"url":l.strip()})
        if len(all_pairs)!=expected:
            return bot.reply_to(m, f"❌ Expected {expected} buttons for row {state['row_index']+1}. Send exactly {expected} lines.")
        state["rows"].append(all_pairs)
        state["row_index"] += 1
        if state["row_index"] < len(state["counts"]):
            bot.reply_to(m, f"Now send buttons for row {state['row_index']+1}")
            bot.register_next_step_handler(m, lambda mm: collect_buttons_row(mm, state))
        else:
            # final: ask for set name
            bot.reply_to(m, "✅ All rows captured. Send a name for this button set:")
            bot.register_next_step_handler(m, lambda mm: finish_button_set(mm, state))
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

def finish_button_set(m, state):
    name = m.text.strip()
    bid = database.add_button_set(DATA_FILE, name, state["rows"])
    bot.reply_to(m, f"✅ Button set saved (id {bid}).")

@bot.message_handler(commands=['listbuttons'])
def cmd_listbuttons(m):
    if not owner_check(m.from_user.id): return
    bs = database.list_button_sets(DATA_FILE)
    if not bs: return bot.reply_to(m, "No button sets.")
    out = "🔘 Button Sets:\n"
    for b in bs:
        out += f"{b['id']}. {b['name']} (rows {len(b['rows'])})\n"
    bot.reply_to(m, out)

@bot.message_handler(commands=['clearbuttons'])
def cmd_clearbuttons(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "Send button set ID to remove or 'all' to remove all:")
    bot.register_next_step_handler(m, lambda mm: handle_clearbuttons(mm))

def handle_clearbuttons(m):
    txt = m.text.strip()
    if txt.lower()=="all":
        database.clear_all_buttons(DATA_FILE)
        return bot.reply_to(m,"✅ All button sets removed.")
    try:
        bid = int(txt); database.remove_button_set(DATA_FILE, bid); bot.reply_to(m,f"✅ Removed button set {bid}")
    except:
        bot.reply_to(m,"❌ Invalid input.")

# Channels
@bot.message_handler(commands=['addchannel'])
def cmd_addchannel(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "📡 Send channel username (without @) or -100ID:")
    bot.register_next_step_handler(m, lambda mm: handle_addchannel(mm))

def handle_addchannel(m):
    ch = m.text.strip().replace("@","")
    ok = database.add_channel(DATA_FILE, ch)
    if ok: bot.reply_to(m, f"✅ Channel added: @{ch}")
    else: bot.reply_to(m, "❌ Channel already exists.")

@bot.message_handler(commands=['removechannel'])
def cmd_removechannel(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "Send channel username (without @) or -100ID to remove:")
    bot.register_next_step_handler(m, lambda mm: handle_removechannel(mm))

def handle_removechannel(m):
    ch = m.text.strip().replace("@","")
    ok = database.remove_channel(DATA_FILE, ch)
    if ok: bot.reply_to(m, f"✅ Channel removed: {ch}")
    else: bot.reply_to(m, "❌ Channel not found.")

@bot.message_handler(commands=['listchannels'])
def cmd_listchannels(m):
    if not owner_check(m.from_user.id): return
    chs = database.list_channels(DATA_FILE)
    if not chs: return bot.reply_to(m,"No channels configured.")
    out="📺 Channels:\n"+ "\n".join([f"{i+1}. {c}" for i,c in enumerate(chs)])
    bot.reply_to(m, out)

# Preview / broadcast
@bot.message_handler(commands=['preview'])
def cmd_preview(m):
    if not owner_check(m.from_user.id): return
    texts = database.list_texts(DATA_FILE)
    if not texts: return bot.reply_to(m,"No texts saved.")
    if len(texts)==1:
        t = texts[0]
        bset = database.get_button_set(DATA_FILE, t.get("buttons_id"))
        kb = build_markup_from_rows(bset["rows"]) if bset else None
        bot.send_message(m.chat.id, "🔎 *Preview*\n\n"+t["text"]+PROMO_SUFFIX, parse_mode="Markdown", reply_markup=kb)
        bot.reply_to(m, "Use /broadcast to send to all channels.")
        return
    # ask which text
    kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for t in texts: kb.add(str(t["id"]))
    kb.add("Cancel")
    bot.reply_to(m, "Which text to preview? Choose number:", reply_markup=kb)
    bot.register_next_step_handler(m, lambda mm: handle_preview_choice(mm))

def handle_preview_choice(m):
    if m.text=="Cancel": return bot.reply_to(m,"Cancelled.")
    try:
        tid = int(m.text.strip())
        t = database.get_text(DATA_FILE, tid)
        if not t: return bot.reply_to(m,"Not found.")
        bset = database.get_button_set(DATA_FILE, t.get("buttons_id"))
        kb = build_markup_from_rows(bset["rows"]) if bset else None
        bot.send_message(m.chat.id, "🔎 *Preview*\n\n"+t["text"]+PROMO_SUFFIX, parse_mode="Markdown", reply_markup=kb)
        # ask to send now
        kb2 = types.InlineKeyboardMarkup()
        kb2.add(types.InlineKeyboardButton("✅ Send to all", callback_data=f"preview_send|{tid}"))
        kb2.add(types.InlineKeyboardButton("❌ Cancel", callback_data="preview_cancel"))
        bot.send_message(m.chat.id, "Confirm:", reply_markup=kb2)
    except:
        bot.reply_to(m,"Invalid choice.")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("preview_send"))
def cb_preview_send(c):
    if not owner_check(c.from_user.id): return bot.answer_callback_query(c.id,"Owner only")
    tid = int(c.data.split("|",1)[1])
    res = do_broadcast(text_id=tid)
    bot.send_message(c.message.chat.id, f"✅ Broadcast finished. Sent: {res['sent']} Failed: {res['failed']}")

def do_broadcast(text_id=None, custom_text=None, custom_buttons=None, target_channels=None, delete_ttl=None):
    cfg = database.load_main(DATA_FILE)
    chs = target_channels if target_channels is not None else cfg.get("channels",[])
    if not chs:
        return {"ok":False,"msg":"no channels","sent":0,"failed":len(chs)}
    if custom_text:
        txt = custom_text + PROMO_SUFFIX
    else:
        t = database.get_text(DATA_FILE, text_id) if text_id else None
        if not t: return {"ok":False,"msg":"no text"}
        txt = t["text"] + PROMO_SUFFIX
        bset = database.get_button_set(DATA_FILE, t.get("buttons_id"))
    kb = None
    if custom_buttons:
        kb = build_markup_from_rows(custom_buttons)
    else:
        if not custom_text:
            kb = build_markup_from_rows(bset["rows"]) if bset else None

    sent=failed=0
    for ch in chs:
        try:
            target = f"@{ch}" if not str(ch).startswith("-100") else str(ch)
            msg = bot.send_message(target, txt, disable_web_page_preview=True, reply_markup=kb)
            sent += 1
            if delete_ttl and int(delete_ttl)>0:
                database.add_pending(DATA_FILE, str(msg.chat.id), msg.message_id, iso_now())
                pend = database.get_pending(DATA_FILE)
                if pend: pend[-1]["ttl"] = int(delete_ttl)
                database.replace_pending(DATA_FILE, pend)
        except Exception as e:
            logging.warning("broadcast fail %s -> %s", ch, e); failed+=1
        time.sleep(1.2)
    database.add_stats(DATA_FILE, sent=sent, failed=failed, broadcast=1)
    return {"ok":True,"sent":sent,"failed":failed}

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(m):
    if not owner_check(m.from_user.id): return
    texts = database.list_texts(DATA_FILE)
    if not texts: return bot.reply_to(m,"No texts saved.")
    if len(texts)==1:
        # direct broadcast using single saved text
        bot.reply_to(m, "⏳ Sending saved text to all channels...")
        res = do_broadcast(text_id=texts[0]["id"])
        bot.reply_to(m, f"📢 Broadcast done. Sent: {res['sent']} Failed: {res['failed']}")
        return
    # multiple texts -> ask which
    kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for t in texts: kb.add(str(t["id"]))
    kb.add("Cancel")
    bot.reply_to(m, "Which text number to broadcast? (or Cancel)", reply_markup=kb)
    bot.register_next_step_handler(m, lambda mm: handle_broadcast_choice(mm))

def handle_broadcast_choice(m):
    if m.text=="Cancel": return bot.reply_to(m,"Cancelled.")
    try:
        tid = int(m.text.strip())
        # ask auto-delete option for this broadcast
        bot.reply_to(m, "Send auto-delete in seconds after which posts will be deleted (0 = keep):")
        bot.register_next_step_handler(m, lambda mm: finalize_broadcast(mm, tid))
    except:
        bot.reply_to(m,"Invalid selection.")

def finalize_broadcast(m, tid):
    try:
        ttl = int(m.text.strip())
    except:
        ttl = 0
    bot.reply_to(m, "⏳ Broadcasting...")
    res = do_broadcast(text_id=tid, delete_ttl=ttl)
    bot.reply_to(m, f"📢 Broadcast done. Sent: {res['sent']} Failed: {res['failed']}")

# schedule commands
@bot.message_handler(commands=['schedule'])
def cmd_schedule(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "✍️ Send schedule in format: TEXT_ID HH:MM AUTO_DELETE_SEC\nExample: 1 22:00 3600")
    bot.register_next_step_handler(m, lambda mm: handle_schedule(mm))

def handle_schedule(m):
    try:
        parts = m.text.strip().split()
        tid = int(parts[0]); hhmm = parts[1]; ttl = int(parts[2]) if len(parts)>2 else 0
        database.add_schedule(DATA_FILE, tid, hhmm, ttl)
        bot.reply_to(m, f"✅ Scheduled text {tid} at {hhmm} with delete {ttl}s")
    except Exception as e:
        bot.reply_to(m, "❌ Invalid format. Use: TEXT_ID HH:MM AUTO_DELETE_SEC")
@bot.message_handler(commands=['viewschedule'])
def cmd_viewschedule(m):
    if not owner_check(m.from_user.id): return
    scheds = database.list_schedules(DATA_FILE)
    if not scheds: return bot.reply_to(m,"No schedules.")
    out = "⏰ Schedules:\n"
    for s in scheds:
        out += f"{s['id']}. Text {s['text_id']} at {s['time']} del {s.get('auto_delete',0)}s\n"
    bot.reply_to(m, out)

@bot.message_handler(commands=['clearschedule'])
def cmd_clearschedule(m):
    if not owner_check(m.from_user.id): return
    bot.reply_to(m, "Send schedule ID to remove:")
    bot.register_next_step_handler(m, lambda mm: handle_clearschedule(mm))

def handle_clearschedule(m):
    try:
        sid = int(m.text.strip()); database.remove_schedule(DATA_FILE, sid); bot.reply_to(m,"✅ Removed.")
    except:
        bot.reply_to(m,"❌ Invalid id.")

@bot.message_handler(commands=['clearallschedule'])
def cmd_clearallschedule(m):
    if not owner_check(m.from_user.id): return
    database.clear_all_schedules(DATA_FILE); bot.reply_to(m,"✅ All schedules removed.")

# status
@bot.message_handler(commands=['status'])
def cmd_status(m):
    if not owner_check(m.from_user.id): return
    stats = database.get_stats(DATA_FILE)
    chs = database.list_channels(DATA_FILE)
    out = (
        "📊 *YASH ADZ BOT STATUS*\n\n"
        f"Channels: `{len(chs)}`\n"
        f"Broadcasts: `{stats.get('broadcasts',0)}`\n"
        f"Sent: `{stats.get('sent',0)}` Failed: `{stats.get('failed',0)}`\n"
    )
    bot.reply_to(m, out, parse_mode="Markdown")

# clear buttons / clearallbuttons handled earlier
# graceful polling loop
def run_polling():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            logging.exception("polling crashed, restarting: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    run_polling()
