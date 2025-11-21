# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")          # set in Choreo env
OWNER_ID = os.getenv("OWNER_ID")            # set in Choreo env (numeric)
try:
    OWNER_ID = int(OWNER_ID) if OWNER_ID is not None else None
except:
    OWNER_ID = None

# Optional small suffix appended automatically to promos (edit if you want)
PROMO_SUFFIX = os.getenv("PROMO_SUFFIX", "\n\n— Powered by @YashXNetwork")

# Data files
DATA_FILE = os.getenv("DATA_FILE", "yash_data.json")
PENDING_FILE = os.getenv("PENDING_FILE", "yash_pending.json")
STATS_FILE = os.getenv("STATS_FILE", "yash_stats.json")
FIRST_RUN_FLAG = os.getenv("FIRST_RUN_FLAG", "yash_first_run.flag")