# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ===============================
# TELEGRAM CONFIG
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Telegram Bot Token
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Your Telegram User ID (numeric)

# ===============================
# TIMEZONE CONFIG
# ===============================
TIMEZONE = "Asia/Kolkata"   # IST (24-hour format)

# ===============================
# FILE PATHS
# ===============================
DATA_FILE = "data.json"     # Main database file
LOG_FILE = "bot.log"        # Optional log file

# ===============================
# BRANDING / FOOTER
# ===============================
PROMO_SUFFIX = "\n\n⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡"

# ===============================
# SYSTEM SETTINGS
# ===============================
MAX_BUTTONS_PER_ROW = 5     # Telegram limit safety
MAX_ROWS = 10               # Max button rows allowed

# ===============================
# SAFETY CHECK
# ===============================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing! Set it in environment variables.")

if OWNER_ID == 0:
    raise RuntimeError("OWNER_ID is missing or invalid! Set it in environment variables.")
