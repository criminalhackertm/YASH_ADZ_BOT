# database.py
import json, os, threading
from config import DATA_FILE, PENDING_FILE, STATS_FILE

_lock = threading.Lock()

DEFAULT = {
    "promo_text": "",
    "buttons": [],        # list of {"text": "...", "url":"..."}
    "channels": [],       # list of channel usernames or -100IDs as strings
    "autopost_interval": 0,   # seconds, 0 = disabled
    "autopost_text": "",
    "autodelete": 0           # seconds, 0 = disabled
}

def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path, data):
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def load_main():
    d = _read_json(DATA_FILE, DEFAULT.copy())
    # ensure keys exist
    for k,v in DEFAULT.items():
        if k not in d:
            d[k] = v
    return d

def save_main(d):
    _write_json(DATA_FILE, d)

# Convenience high-level API used by main.py
def save_promotion_text(text):
    d = load_main()
    d["promo_text"] = text
    save_main(d)

def get_promotion_text():
    return load_main().get("promo_text", "")

def save_buttons(list_of_pairs):
    # accept list of [name,url] or list of {"text","url"}
    d = load_main()
    btns = []
    for item in list_of_pairs:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            btns.append({"text": str(item[0]), "url": str(item[1])})
        elif isinstance(item, dict) and "text" in item and "url" in item:
            btns.append({"text": str(item["text"]), "url": str(item["url"])})
    d["buttons"] = btns
    save_main(d)

def get_buttons():
    return load_main().get("buttons", [])

def save_channels(ch):
    # add channel (username without @) or -100ID as string
    d = load_main()
    chs = d.get("channels", [])
    if isinstance(ch, int):
        c = str(ch)
    else:
        c = str(ch).strip()
    if c and c not in chs:
        chs.append(c)
        d["channels"] = chs
        save_main(d)

def get_channels():
    return load_main().get("channels", [])

def remove_channel(ch):
    d = load_main()
    chs = d.get("channels", [])
    c = str(ch).strip()
    if c in chs:
        chs.remove(c)
        d["channels"] = chs
        save_main(d)
        return True
    return False

def save_autopost(interval_seconds, text=None):
    d = load_main()
    d["autopost_interval"] = int(interval_seconds) if interval_seconds else 0
    if text is not None:
        d["autopost_text"] = text
    save_main(d)

def get_autopost():
    d = load_main()
    return d.get("autopost_interval", 0), d.get("autopost_text", "")

def save_autodelete(seconds):
    d = load_main()
    d["autodelete"] = int(seconds) if seconds else 0
    save_main(d)

def get_autodelete():
    return load_main().get("autodelete", 0)

# pending messages (for deletion scheduling)
def add_pending(chat_id, message_id, send_time_iso):
    pend = _read_json(PENDING_FILE, [])
    pend.append({"chat_id": str(chat_id), "message_id": int(message_id), "send_time": send_time_iso})
    _write_json(PENDING_FILE, pend)

def get_pending():
    return _read_json(PENDING_FILE, [])

def replace_pending(new_list):
    _write_json(PENDING_FILE, new_list)

# stats
def add_stats(sent=0, failed=0, broadcast=0, autopost=0):
    s = _read_json(STATS_FILE, {"broadcasts":0,"autoposts":0,"sent":0,"failed":0})
    s["sent"] = s.get("sent",0) + sent
    s["failed"] = s.get("failed",0) + failed
    s["broadcasts"] = s.get("broadcasts",0) + broadcast
    s["autoposts"] = s.get("autoposts",0) + autopost
    _write_json(STATS_FILE, s)

def get_stats():
    return _read_json(STATS_FILE, {"broadcasts":0,"autoposts":0,"sent":0,"failed":0})