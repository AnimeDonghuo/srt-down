import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "26826540"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

# Ensure required folders exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("API_ID, API_HASH, and BOT_TOKEN must be configured in environment variables.")
