import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # set in Render / Choreo environment
OWNER_ID = os.getenv("OWNER_ID")
if OWNER_ID:
    try:
        OWNER_ID = int(OWNER_ID)
    except:
        OWNER_ID = None

# Files used by database module
DATA_FILE = os.getenv("DATA_FILE", "yash_data.json")
PENDING_FILE = os.getenv("PENDING_FILE", "yash_pending.json")
STATS_FILE = os.getenv("STATS_FILE", "yash_stats.json")
FIRST_RUN_FLAG = os.getenv("FIRST_RUN_FLAG", "yash_first_run.flag")

# Promotion suffix (stylish)
PROMO_SUFFIX = os.getenv("PROMO_SUFFIX", "\n\n⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡")
