"""firebase_client.py — wrapper Firebase Admin SDK."""
import json
import os

import firebase_admin
from firebase_admin import credentials, db

from config import (
    FIREBASE_CREDENTIALS_JSON,
    FIREBASE_CREDENTIALS_PATH,
    FIREBASE_DATABASE_URL,
)


def _credential():
    if FIREBASE_CREDENTIALS_JSON:
        info = json.loads(FIREBASE_CREDENTIALS_JSON)
        return credentials.Certificate(info)
    path = FIREBASE_CREDENTIALS_PATH
    if path and os.path.isfile(path):
        return credentials.Certificate(path)
    raise FileNotFoundError(
        "Firebase credentials tidak ada. Set secret FIREBASE_CREDENTIALS_JSON "
        "atau file serviceAccountKey.json."
    )


def init():
    if firebase_admin._apps:
        return
    cred = _credential()
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DATABASE_URL})
    print(f"[Firebase] Terhubung -> {FIREBASE_DATABASE_URL}")


def listen(path: str, callback):
    ref = db.reference(path)
    ref.listen(callback)
    return ref


def read(path: str):
    return db.reference(path).get()


def write(path: str, data: dict):
    db.reference(path).set(data)


def push(path: str, data: dict) -> str:
    return db.reference(path).push(data).key
