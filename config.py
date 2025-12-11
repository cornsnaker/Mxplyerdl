import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "12345678").split(",")]
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "abcdef1234567890")

# Paths
BIN_DIR = os.path.join(os.getcwd(), "bin")
NM3U8DL_PATH = os.path.join(BIN_DIR, "N_m3u8DL-RE")
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg")

# Database
DB_NAME = "bot_data.db"

# Constants
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
ORIGIN = "https://www.mxplayer.in"

# Max concurrent downloads per user
MAX_CONCURRENT_DOWNLOADS = 2
