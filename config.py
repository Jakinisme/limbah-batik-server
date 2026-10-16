# config.py — backend EC. Angka rahasia dari environment (Hugging Face Secrets).
import os
from pathlib import Path

_SERVER = Path(__file__).resolve().parent

def _env(name, default=""):
    val = os.environ.get(name)
    return default if val is None or val.strip() == "" else val.strip()


# ---- HTTP (Hugging Face Spaces memakai 7860) ----
PORT = int(_env("PORT", "7860"))
HOST = _env("HOST", "0.0.0.0")

# ---- Firebase ----
FIREBASE_DATABASE_URL = _env(
    "FIREBASE_DATABASE_URL",
    "https://YOUR_PROJECT.firebaseio.com",
)
# Isi JSON service account utuh di secret FIREBASE_CREDENTIALS_JSON
# atau taruh file (jangan di-commit).
FIREBASE_CREDENTIALS_JSON = _env("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_CREDENTIALS_PATH = _env(
    "FIREBASE_CREDENTIALS_PATH",
    str(_SERVER / "serviceAccountKey.json"),
)

# ---- Telegram (kosongkan token = tidak kirim) ----
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "")
_chat = _env("TELEGRAM_CHAT_IDS", "")
TELEGRAM_CHAT_IDS = [c.strip() for c in _chat.split(",") if c.strip()]

# ---- Model (ikut folder server/models, mandiri dari PC) ----
MODELS_DIR = str(_SERVER / "models")
EC_MODEL_PATH = str(_SERVER / "models" / "ec_recommender.pkl")

# ---- Path RTDB ----
# TODO: konfirmasi nama field di node ini
PATH_SENSOR_WATER = _env("PATH_SENSOR_WATER", "/sensors/water/latest")
PATH_RECOMMEND_EC = _env("PATH_RECOMMEND_EC", "/recommendations/ec/latest")
PATH_HIST_RECOMMEND_EC = _env("PATH_HIST_RECOMMEND_EC", "/recommendations/ec/history")

PATH_SENSOR_ENERGY = "/sensors/energy/latest"
PATH_PRED_ENERGY = "/predictions/energy/latest"


def credentials_configured() -> bool:
    if FIREBASE_CREDENTIALS_JSON:
        return True
    p = Path(FIREBASE_CREDENTIALS_PATH)
    return p.is_file() and p.stat().st_size > 0
