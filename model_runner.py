"""
model_runner.py — inference EC dari 5 sensor di /sensors/water/latest.

Tidak memakai COD/BOD/warna/konduktivitas/TSS/arus sebagai input.
Tidak menghitung TDS_final dengan faktor hardcode.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
# Space mandiri: modul di folder yang sama. Repo lokal: cadangan root.
for p in (_HERE, _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np

import ec_config as C
from recommend_ec import load_bundle, recommend

from config import EC_MODEL_PATH

_FIELD_ALIASES = {
    "pH": ("pH", "ph", "pH_init"),
    "TDS": ("TDS", "TDS_mgL", "tds", "TDS_init"),
    "turbidity": ("turbidity", "turbidity_NTU", "turb_NTU", "turb_init_NTU"),
    "temp_C": ("temp_C", "temp", "temperature", "temp_water_C"),
    "voltage_V": ("voltage_V", "voltage", "volt"),
}


def _pick(payload: dict, names):
    for n in names:
        if n in payload and payload[n] is not None and payload[n] != "":
            return payload[n]
    return None


def parse_water_sensors(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("payload bukan dict")
    out = {}
    missing = []
    for key, names in _FIELD_ALIASES.items():
        val = _pick(payload, names)
        if val is None:
            missing.append(key)
        else:
            out[key] = float(val)
    if missing:
        raise ValueError(f"sensor wajib hilang: {missing}")
    return out


def load_models() -> dict:
    bundle = load_bundle(EC_MODEL_PATH)
    return {"ec": bundle}


# Field yang diteruskan apa adanya dari recommend() ke RTDB.
# Kunci pred_*/uncertain/ood_score sudah lama ditunggu dashboard
# (batik-dashboard/src/hooks/useRecommendationHistory.tsx) tapi sebelumnya dibuang.
_PASSTHROUGH = (
    "hours", "volt", "reachable", "model_version", "timestamp", "data_label",
    "reason", "fallback", "exploration", "ood", "ood_score", "uncertain",
    "pred_pH", "pred_TDS", "pred_turb_NTU", "pred_remaining_h", "energy_rel",
    "tidak_lolos",
)

# Echo sensor yang dipakai model, supaya node rekomendasi bisa diaudit
# langsung terhadap /sensors/water/latest (tanpa buka console server).
_MEASURED_ECHO = {
    "measured_pH": "pH",
    "measured_TDS": "TDS",
    "measured_turbidity_NTU": "turbidity",
    "measured_temp_C": "temp_C",
    "measured_voltage_V": "voltage_V",
}


def run_ec_recommendation(payload: dict, models: dict, rng=None) -> dict:
    s = parse_water_sensors(payload)
    bundle = models["ec"]
    rec = recommend(
        bundle,
        pH=s["pH"],
        TDS=s["TDS"],
        turb_NTU=s["turbidity"],
        temp_C=s["temp_C"],
        electrode_type=C.ELECTRODE_TYPE,
        gap_cm=C.GAP_CM,
        rng=rng if rng is not None else np.random.RandomState(),
    )
    out = {k: rec.get(k) for k in _PASSTHROUGH}
    # "volt" = TARGET tegangan elektroda (V_GRID + jitter eksplorasi), BUKAN hasil ukur.
    # target_volt ditambah sebagai nama eksplisit; "volt" tetap dikirim karena
    # firmware ESP (ml_gate.cpp:19) dan dashboard masih membacanya.
    out["target_volt"] = rec.get("volt")
    out.update({dst: s[src] for dst, src in _MEASURED_ECHO.items()})
    return out
