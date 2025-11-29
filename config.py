import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

PROMO_SUFFIX = "\n\n— Powered by @YashXNetwork"

DATA_FILE = "yash_data.json"
PENDING_FILE = "yash_pending.json"
STATS_FILE = "yash_stats.json"