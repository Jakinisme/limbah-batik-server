"""
main.py — listener limbah: 5 sensor -> rekomendasi EC.

Dipakai lokal (`python main.py`) dan oleh app.py di Hugging Face Space.
"""
import logging
import time
from datetime import datetime, timezone

import firebase_client as fb
import model_runner as mr
import telegram_notifier as tg
from config import (
    EC_MODEL_PATH,
    PATH_HIST_RECOMMEND_EC,
    PATH_RECOMMEND_EC,
    PATH_SENSOR_WATER,
    credentials_configured,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

_models = None
STATUS = {
    "listener": "stopped",
    "firebase": False,
    "model_loaded": False,
    "model_path": EC_MODEL_PATH,
    "model_version": None,
    "data_label": None,
    "last_rec": None,
    "last_error": None,
    "last_event_at": None,
    "started_at": None,
}


def on_water(event):
    # firebase_admin memanggil callback ini tanpa try/except (firebase_admin/db.py
    # _start_listen). Exception yang lolos mematikan thread listener diam-diam,
    # jadi bungkus seluruh isi callback dan tandai statusnya.
    try:
        _handle_water(event)
    except Exception as exc:
        STATUS["listener"] = "error"
        STATUS["last_error"] = f"on_water: {exc}"
        STATUS["last_event_at"] = datetime.now(timezone.utc).isoformat()
        log.exception("[Water] callback gagal - listener Firebase berhenti mendengar")


def _handle_water(event):
    if not event.data or not isinstance(event.data, dict):
        return
    payload = event.data
    log.info(
        "[Water] pH=%s TDS=%s turb=%s T=%s V=%s",
        payload.get("pH", payload.get("ph")),
        payload.get("TDS", payload.get("TDS_mgL")),
        payload.get("turbidity", payload.get("turbidity_NTU")),
        payload.get("temp_C", payload.get("temp")),
        payload.get("voltage_V", payload.get("voltage")),
    )
    try:
        rec = mr.run_ec_recommendation(payload, _models)
    except Exception as exc:
        log.error("[Water] Inference error: %s", exc)
        STATUS["last_error"] = str(exc)
        STATUS["last_event_at"] = datetime.now(timezone.utc).isoformat()
        return

    fb.write(PATH_RECOMMEND_EC, rec)
    fb.push(PATH_HIST_RECOMMEND_EC, rec)
    STATUS["last_rec"] = rec
    STATUS["last_error"] = None
    STATUS["last_event_at"] = datetime.now(timezone.utc).isoformat()
    log.info(
        "[Water] -> hours=%s volt=%s reachable=%s version=%s label=%s",
        rec["hours"], rec["volt"], rec["reachable"], rec["model_version"], rec.get("data_label"),
    )
    if rec.get("data_label") == "ASLI":
        log.warning("[Water] Output model ASLI")
    if rec.get("ood") or rec.get("fallback") == "conservative":
        tg.alert_conservative(payload, rec)
    else:
        tg.alert_rekomendasi(rec)


def start_backend():
    """Load model + pasang listener. Tidak memblokir (listener di thread Firebase)."""
    global _models
    STATUS["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        log.info("Loading model EC dari %s", EC_MODEL_PATH)
        _models = mr.load_models()
        bundle = _models["ec"]
        STATUS["model_loaded"] = True
        STATUS["model_version"] = bundle.get("model_version")
        STATUS["data_label"] = bundle.get("data_label")
        log.info("Model siap version=%s label=%s", STATUS["model_version"], STATUS["data_label"])
    except Exception as exc:
        STATUS["listener"] = "error"
        STATUS["last_error"] = f"gagal load model: {exc}"
        log.exception("Gagal load model")
        return STATUS

    if not credentials_configured():
        STATUS["listener"] = "waiting_credentials"
        STATUS["last_error"] = (
            "Firebase belum dikonfigurasi. Isi secret FIREBASE_DATABASE_URL "
            "dan FIREBASE_CREDENTIALS_JSON di Hugging Face Space."
        )
        log.error(STATUS["last_error"])
        return STATUS

    try:
        fb.init()
        STATUS["firebase"] = True
        log.info("Listening %s", PATH_SENSOR_WATER)
        fb.listen(PATH_SENSOR_WATER, on_water)
        STATUS["listener"] = "running"
        STATUS["last_error"] = None
    except Exception as exc:
        STATUS["listener"] = "error"
        STATUS["last_error"] = f"firebase: {exc}"
        log.exception("Gagal Firebase")
    return STATUS


if __name__ == "__main__":
    log.info("Backend EC limbah batik - START")
    start_backend()
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Backend dihentikan.")
