import json, os, threading, uuid
from datetime import datetime
from config import DATA_FILE, PENDING_FILE, STATS_FILE

_lock = threading.Lock()

def _read(fn, default):
    if not os.path.exists(fn):
        return default
    try:
        with open(fn, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _write(fn, data):
    with _lock:
        with open(fn, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# main data structure:
# {
#   "texts": [{"id":1,"text":"..."}],
#   "buttons": {"1":[{"text":"A","url":"..."}], "2":[...]},
#   "channels": ["channel1","-100xxxxx"],
#   "schedules": [{"id":"uuid","hhmm":"22:00","text_id":2,"autodelete":3600,"last_run_date":null}],
#   "autodeletes": {"1":3600, "2":0}
# }
def load_main_data():
    return _read(DATA_FILE, {"texts":[],"buttons":{},"channels":[],"schedules":[],"autodeletes":{}})

def save_main_data(data):
    _write(DATA_FILE, data)

# texts
def save_promotion_text(tid, text, remove=False):
    d = load_main_data()
    if remove:
        d["texts"] = [t for t in d["texts"] if t["id"] != tid]
        # also remove buttons & autodelete mapping
        d["buttons"].pop(str(tid), None)
        d["autodeletes"].pop(str(tid), None)
        save_main_data(d)
        return True
    if text is None:
        return False
    # upsert
    exists = False
    for t in d["texts"]:
        if t["id"] == tid:
            t["text"] = text; exists=True; break
    if not exists:
        d["texts"].append({"id": tid, "text": text})
    save_main_data(d)
    return True

def get_promotion_texts():
    d = load_main_data()
    return d.get("texts", [])

def clear_all_texts():
    d = load_main_data()
    d["texts"] = []
    d["buttons"] = {}
    d["autodeletes"] = {}
    save_main_data(d)

# buttons
def save_buttons_for_text(tid, buttons, remove=False):
    d = load_main_data()
    key = str(tid)
    if remove:
        d["buttons"].pop(key, None); save_main_data(d); return True
    d["buttons"][key] = buttons or []
    save_main_data(d); return True

def get_buttons_for_text(tid):
    d = load_main_data()
    return d.get("buttons", {}).get(str(tid), [])

def clear_all_buttons():
    d = load_main_data(); d["buttons"] = {}; save_main_data(d)

# channels
def save_channels(ch):
    d = load_main_data()
    chs = d.get("channels", [])
    if ch not in chs:
        chs.append(ch); d["channels"] = chs; save_main_data(d)

def get_channels():
    d = load_main_data()
    return d.get("channels", [])

def remove_channel(ch):
    d = load_main_data()
    if ch in d.get("channels", []):
        d["channels"].remove(ch); save_main_data(d); return True
    return False

# schedules (autopost exact time daily)
def save_autopost_schedule(hhmm, text_id, autodelete=0, update=False, clear_all=False):
    d = load_main_data()
    if clear_all:
        d["schedules"] = []; save_main_data(d); return True
    if update and isinstance(hhmm, dict):
        # update schedule dict provided
        schedules = d.get("schedules", [])
        for i, s in enumerate(schedules):
            if s.get("id") == hhmm.get("id"):
                schedules[i] = hhmm; d["schedules"] = schedules; save_main_data(d); return True
    if hhmm is None:
        return False
    entry = {"id": str(uuid.uuid4()), "hhmm": hhmm, "text_id": int(text_id), "autodelete": int(autodelete), "last_run_date": None}
    d.setdefault("schedules", []).append(entry)
    save_main_data(d)
    return True

def get_autopost_schedules():
    d = load_main_data()
    return d.get("schedules", [])

def remove_schedule(index):
    d = load_main_data()
    arr = d.get("schedules", [])
    if 0 <= index-1 < len(arr):
        arr.pop(index-1); d["schedules"] = arr; save_main_data(d); return True
    return False

# per-text autodelete
def save_autodelete_for_text(tid, seconds):
    d = load_main_data()
    d.setdefault("autodeletes", {})[str(tid)] = int(seconds)
    save_main_data(d)

def get_autodelete_for_text(tid):
    d = load_main_data()
    return int(d.get("autodeletes", {}).get(str(tid), 0) or 0)

# pending deletes (list of {"chat_id","message_id","send_time","autodelete"})
def add_pending(chat_id, message_id, send_time_iso, autodelete=0):
    p = _read(PENDING_FILE, [])
    p.append({"chat_id": str(chat_id), "message_id": int(message_id), "send_time": send_time_iso, "autodelete": int(autodelete)})
    _write(PENDING_FILE, p)

def get_pending():
    return _read(PENDING_FILE, [])

def replace_pending(new):
    _write(PENDING_FILE, new)

# stats
def add_stats(broadcast=0, autopost=0, sent=0, failed=0):
    s = _read(STATS_FILE, {"broadcasts":0,"autoposts":0,"sent":0,"failed":0})
    s["broadcasts"] = s.get("broadcasts",0) + int(broadcast)
    s["autoposts"] = s.get("autoposts",0) + int(autopost)
    s["sent"] = s.get("sent",0) + int(sent)
    s["failed"] = s.get("failed",0) + int(failed)
    _write(STATS_FILE, s)

def get_stats():
    return _read(STATS_FILE, {"broadcasts":0,"autoposts":0,"sent":0,"failed":0})
