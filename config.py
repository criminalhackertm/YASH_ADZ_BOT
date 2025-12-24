import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

TIMEZONE = "Asia/Kolkata"

DATA_FILE = "data.json"

PROMO_SUFFIX = "\n\n⚡ Ｐｏｗｅｒｅｄ Ｂｙ — @YashXNetwork ⚡"
