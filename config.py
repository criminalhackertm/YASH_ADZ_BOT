import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
if OWNER_ID:
    try:
        OWNER_ID = int(OWNER_ID)
    except:
        OWNER_ID = None

# files & flags
DATA_FILE = "yash_data.json"
PENDING_FILE = "yash_pending.json"
STATS_FILE = "yash_stats.json"
FIRST_RUN_FLAG = "yash_first_run.flag"

# promo suffix (stylish)
PROMO_SUFFIX = """
⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡
"""
