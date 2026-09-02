import os
from dotenv import load_dotenv

# Ưu tiên load file .env nằm cùng thư mục backend của sprint1
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Cấu hình kết nối PostgreSQL
try:
    db_port = int(os.getenv("DB_PORT", 5432))
except ValueError:
    db_port = 5432

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "medical_db"),
    "user": os.getenv("DB_USER", "ai_agent"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": db_port
}

# Cấu hình Google Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

base_url = os.getenv(
    "GEMINI_URL",
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

if GEMINI_API_KEY and "key=" not in base_url:
    GEMINI_URL = f"{base_url}?key={GEMINI_API_KEY}"
else:
    GEMINI_URL = base_url

# Cảnh báo nếu thiếu API Key
if not GEMINI_API_KEY:
    print("[!] CANH BAO: Chua tim thay GEMINI_API_KEY trong file .env!")