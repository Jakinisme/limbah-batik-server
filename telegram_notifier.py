"""Telegram alerts untuk rekomendasi EC (tanpa COD/BOD/TSS/warna)."""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS


def _enabled() -> bool:
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    if not token or token.startswith("YOUR_"):
        return False
    return bool(TELEGRAM_CHAT_IDS)


def _send(chat_id: str, text: str, disable_notification: bool = False):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_notification": disable_notification,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[Telegram] Gagal kirim ke {chat_id}: {e}")


def broadcast(text: str, silent: bool = False):
    if not _enabled():
        return
    for cid in TELEGRAM_CHAT_IDS:
        _send(cid, text, disable_notification=silent)


def alert_rekomendasi(rec: dict):
    label = rec.get("data_label", "?")
    broadcast(
        f"<b>Rekomendasi EC</b>\n"
        f"hours: <code>{rec.get('hours')}</code>\n"
        f"volt: <code>{rec.get('volt')}</code>\n"
        f"reachable: <code>{rec.get('reachable')}</code>\n"
        f"version: <code>{rec.get('model_version')}</code>\n"
        f"ts: <code>{rec.get('timestamp')}</code>",
        silent=True,
    )


def alert_conservative(sensor: dict, rec: dict):
    broadcast(
        "⚠️ <b>Fallback konservatif</b>\n"
        f"alasan: <code>{rec.get('reason')}</code>\n"
        f"hours: <code>{rec.get('hours')}</code>  volt: <code>{rec.get('volt')}</code>\n"
        f"pH={sensor.get('pH', sensor.get('ph'))} "
        f"TDS={sensor.get('TDS', sensor.get('TDS_mgL'))} "
        f"turb={sensor.get('turbidity', sensor.get('turbidity_NTU'))}"
    )
