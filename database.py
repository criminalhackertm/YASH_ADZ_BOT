import json, os, threading
from config import DATA_FILE, PENDING_FILE, STATS_FILE

lock = threading.Lock()

def read(path, default):
    if not os.path.exists(path): return default
    try:
        return json.load(open(path, "r"))
    except:
        return default

def write(path, data):
    with lock:
        json.dump(data, open(path, "w"), indent=2)


# ---------- PROMOTION TEXT ----------
def save_promotion_text(text):
    d = read(DATA_FILE, {})
    d["promo_text"] = text
    write(DATA_FILE, d)

def get_promotion_text():
    return read(DATA_FILE, {}).get("promo_text", "")


# ---------- BUTTONS ----------
def save_buttons(btn):
    d = read(DATA_FILE, {})
    d["buttons"] = btn
    write(DATA_FILE, d)

def get_buttons():
    return read(DATA_FILE, {}).get("buttons", [])


# ---------- CHANNELS ----------
def save_channels(ch):
    d = read(DATA_FILE, {})
    arr = d.get("channels", [])
    if ch not in arr:
        arr.append(ch)
    d["channels"] = arr
    write(DATA_FILE, d)

def remove_channel(ch):
    d = read(DATA_FILE, {})
    arr = d.get("channels", [])
    if ch in arr:
        arr.remove(ch)
        d["channels"] = arr
        write(DATA_FILE, d)
        return True
    return False

def get_channels():
    return read(DATA_FILE, {}).get("channels", [])


# ---------- AUTPOST ----------
def save_autopost(t, text):
    d = read(DATA_FILE, {})
    d["autopost"] = [t, text]
    write(DATA_FILE, d)

def get_autopost():
    return read(DATA_FILE, {}).get("autopost", [0, ""])


# ---------- AUTODELETE ----------
def save_autodelete(t):
    d = read(DATA_FILE, {})
    d["autodelete"] = t
    write(DATA_FILE, d)

def get_autodelete():
    return read(DATA_FILE, {}).get("autodelete", 0)


# ---------- PENDING DELETE ----------
def add_pending(chat_id, msg_id, time):
    arr = read(PENDING_FILE, [])
    arr.append({"chat_id": chat_id, "message_id": msg_id, "send_time": time})
    write(PENDING_FILE, arr)

def get_pending():
    return read(PENDING_FILE, [])

def replace_pending(new):
    write(PENDING_FILE, new)


# ---------- STATS ----------
def add_stats(sent=0, failed=0, broadcast=0, autopost=0):
    d = read(STATS_FILE, {})
    d["sent"] = d.get("sent", 0) + sent
    d["failed"] = d.get("failed", 0) + failed
    d["broadcasts"] = d.get("broadcasts", 0) + broadcast
    d["autoposts"] = d.get("autoposts", 0) + autopost
    write(STATS_FILE, d)

def get_stats():
    return read(STATS_FILE, {})