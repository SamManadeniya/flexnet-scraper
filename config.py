import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Prefer service role key for backend operations if provided; fallback to anon key
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
)

# Google Sheets Webhook
GOOGLE_SHEETS_WEBHOOK_URL = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "").strip()

# Scraper Settings
BASE_URL = "https://www.flexnet.co.jp"
SEARCH_URL = f"{BASE_URL}/search"
DEFAULT_CONCURRENCY = int(os.getenv("DEFAULT_CONCURRENCY", "5"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "0.4"))
TIMEOUT_SECONDS = float(os.getenv("TIMEOUT_SECONDS", "25"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# API Server Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Authentication & Security Settings (RFC 7518 256-bit compliant)
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "b39f7a81d4e04918e4726c92736184a51e5927b2a951c68f237190d7e48b59ac"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 days
