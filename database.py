import json, os, threading, time
from datetime import datetime

_lock = threading.Lock()

def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _write_json(path, data):
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# ---- default structure ----
DEFAULT = {
    "texts": [],     # list of {"id":1,"text":"...","buttons_id":None}
    "buttons": [],   # list of {"id":1,"name":"set1","rows":[ [ {"text":"A","url":"..."} ], [ ... ] ] }
    "channels": [],  # list of channel identifiers like "@name" or "-100123..."
    "schedules": [], # list of {"id":1,"text_id":X,"time":"HH:MM","auto_delete":0}
    "pending": [],   # list of {"chat_id":str,"message_id":int,"send_time":"iso"}
    "stats": {"broadcasts":0,"autoposts":0,"sent":0,"failed":0}
}

def ensure_file(path):
    if not os.path.exists(path):
        _write_json(path, DEFAULT)

# High level helpers (using path strings passed by caller)
def load_main(path):
    ensure_file(path)
    return _read_json(path, DEFAULT.copy())

def save_main(path, data):
    _write_json(path, data)

# Text helpers
def add_text(path, text):
    data = load_main(path)
    nid = max([t["id"] for t in data["texts"]], default=0)+1
    data["texts"].append({"id":nid,"text":text,"buttons_id":None})
    save_main(path, data)
    return nid

def list_texts(path):
    data = load_main(path)
    return data["texts"]

def get_text(path, tid):
    data = load_main(path)
    for t in data["texts"]:
        if t["id"]==tid: return t
    return None

def remove_text(path, tid):
    data = load_main(path)
    data["texts"] = [t for t in data["texts"] if t["id"]!=tid]
    save_main(path, data)
    return True

def clear_all_texts(path):
    data = load_main(path)
    data["texts"] = []
    save_main(path, data)

def set_text_buttons(path, tid, bid):
    data = load_main(path)
    for t in data["texts"]:
        if t["id"]==tid:
            t["buttons_id"] = bid
    save_main(path, data)

# Button helpers
def add_button_set(path, name, rows):
    data = load_main(path)
    nid = max([b["id"] for b in data["buttons"]], default=0)+1
    data["buttons"].append({"id":nid,"name":name,"rows":rows})
    save_main(path, data)
    return nid

def list_button_sets(path):
    data = load_main(path); return data["buttons"]

def get_button_set(path, bid):
    data = load_main(path)
    for b in data["buttons"]:
        if b["id"]==bid: return b
    return None

def remove_button_set(path, bid):
    data = load_main(path)
    data["buttons"] = [b for b in data["buttons"] if b["id"]!=bid]
    # clear references
    for t in data["texts"]:
        if t.get("buttons_id")==bid: t["buttons_id"]=None
    save_main(path, data)

def clear_all_buttons(path):
    data = load_main(path)
    data["buttons"] = []
    for t in data["texts"]:
        t["buttons_id"]=None
    save_main(path, data)

# Channel helpers
def add_channel(path, ch):
    data = load_main(path)
    if ch not in data["channels"]:
        data["channels"].append(ch)
        save_main(path, data)
        return True
    return False

def remove_channel(path, ch):
    data = load_main(path)
    if ch in data["channels"]:
        data["channels"].remove(ch)
        save_main(path, data)
        return True
    return False

def list_channels(path):
    data = load_main(path)
    return data["channels"]

def clear_all_channels(path):
    data = load_main(path); data["channels"] = []; save_main(path,data)

# Schedule helpers (time in "HH:MM")
def add_schedule(path, text_id, hhmm, auto_delete=0):
    data = load_main(path)
    sid = max([s["id"] for s in data["schedules"]], default=0)+1
    data["schedules"].append({"id":sid,"text_id":text_id,"time":hhmm,"auto_delete":auto_delete})
    save_main(path, data)
    return sid

def list_schedules(path):
    data = load_main(path); return data["schedules"]

def remove_schedule(path, sid):
    data = load_main(path)
    data["schedules"] = [s for s in data["schedules"] if s["id"]!=sid]
    save_main(path, data)

def clear_all_schedules(path):
    data = load_main(path); data["schedules"]=[]; save_main(path,data)

# Pending delete / stats
def add_pending(path, chat_id, msg_id, send_time_iso):
    data = load_main(path)
    data["pending"].append({"chat_id":str(chat_id),"message_id":int(msg_id),"send_time":send_time_iso})
    save_main(path, data)

def get_pending(path):
    data = load_main(path)
    return data.get("pending",[])

def replace_pending(path, newlist):
    data = load_main(path)
    data["pending"] = newlist
    save_main(path, data)

def add_stats(path, sent=0, failed=0, broadcast=0, autopost=0):
    data = load_main(path)
    st = data.get("stats",{"broadcasts":0,"autoposts":0,"sent":0,"failed":0})
    st["sent"] = st.get("sent",0) + sent
    st["failed"] = st.get("failed",0) + failed
    st["broadcasts"] = st.get("broadcasts",0) + broadcast
    st["autoposts"] = st.get("autoposts",0) + autopost
    data["stats"] = st
    save_main(path, data)

def get_stats(path):
    return load_main(path).get("stats",{"broadcasts":0,"autoposts":0,"sent":0,"failed":0})
