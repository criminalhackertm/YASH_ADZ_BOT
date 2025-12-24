# database.py
import json
import os
import threading

_lock = threading.Lock()

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

# =========================
# MAIN DB LOAD / SAVE
# =========================
def load_db(path, default):
    data = _read_json(path, default)
    # ensure all keys exist
    for k, v in default.items():
        if k not in data:
            data[k] = v
    return data

def save_db(path, data):
    _write_json(path, data)

# =========================
# TEXT SYSTEM
# =========================
def add_text(db, text):
    db["texts"].append(text)

def get_texts(db):
    return db["texts"]

def delete_text(db, index):
    try:
        db["texts"].pop(index)
        return True
    except:
        return False

def clear_all_texts(db):
    db["texts"].clear()

# =========================
# BUTTON SYSTEM
# buttons structure:
# db["buttons"] = {
#   text_index: [
#       [ { "text": "A", "url": "https://..." }, ... ],  # row 1
#       [ { "text": "B", "url": "https://..." } ]       # row 2
#   ]
# }
# =========================
def set_buttons(db, text_index, rows):
    db["buttons"][str(text_index)] = rows

def get_buttons(db, text_index):
    return db["buttons"].get(str(text_index), [])

def delete_buttons(db, text_index):
    if str(text_index) in db["buttons"]:
        del db["buttons"][str(text_index)]
        return True
    return False

def clear_all_buttons(db):
    db["buttons"].clear()

# =========================
# CHANNEL SYSTEM
# =========================
def add_channel(db, channel):
    if channel not in db["channels"]:
        db["channels"].append(channel)

def remove_channel(db, channel):
    if channel in db["channels"]:
        db["channels"].remove(channel)
        return True
    return False

def get_channels(db):
    return db["channels"]

# =========================
# SCHEDULER SYSTEM
# schedule item:
# {
#   "time": "22:00",
#   "text_index": 0,
#   "autodelete": 3600
# }
# =========================
def add_schedule(db, item):
    db["schedules"].append(item)

def get_schedules(db):
    return db["schedules"]

def delete_schedule(db, index):
    try:
        db["schedules"].pop(index)
        return True
    except:
        return False

def clear_all_schedules(db):
    db["schedules"].clear()
