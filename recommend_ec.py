"""
recommend_ec.py
===============
Forward model (pH, TDS, turbidity, suhu, V, t) → kondisi setelah EC,
lalu grid search (V, t) di V_GRID/T_GRID, receding horizon 15–30 menit.

Output: hours, volt, reachable, model_version, timestamp, ...
Data sintetis → data_label SINTETIS (jangan diklaim akurat).
"""
from __future__ import annotations

from datetime import datetime, timezone
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler

import ec_config as C


def _hgb(quantile=None, max_iter=300):
    kw = dict(
        max_iter=max_iter,
        learning_rate=0.06,
        min_samples_leaf=10,
        random_state=42,
        early_stopping=False,
    )
    if quantile is not None:
        kw["loss"] = "quantile"
        kw["quantile"] = quantile
    if C.USE_MONOTONIC:
        raise RuntimeError("USE_MONOTONIC=True dilarang sampai data asli mendukungnya")
    return HistGradientBoostingRegressor(**kw)


def fit_forward_models(df: pd.DataFrame, sample_weight=None, max_iter=300):
    """Latih quantile 0.1/0.5/0.9 per target. Tanpa constraint monotonik."""
    models = {}
    X = df[C.QUAL_X]
    for y in C.QUAL_Y:
        models[y] = {}
        for q in (0.1, 0.5, 0.9):
            m = _hgb(quantile=q, max_iter=max_iter)
            m.fit(X, df[y], sample_weight=sample_weight)
            models[y][q] = m
    return models


def fit_ood_detector(df: pd.DataFrame):
    scaler = StandardScaler()
    Xs = scaler.fit_transform(df[C.OOD_COLS])
    iso = IsolationForest(
        contamination=C.ISO_CONTAMINATION,
        random_state=42,
        n_estimators=200,
    )
    iso.fit(Xs)
    return iso, scaler


def predict_quantiles(models, X: pd.DataFrame):
    out = {}
    for y in C.QUAL_Y:
        out[y] = {q: models[y][q].predict(X) for q in (0.1, 0.5, 0.9)}
    return out


def _passes(pH_lo, pH_hi, pH_med, turb_hi, tds_hi):
    pH_ok = (pH_lo >= C.PH_MIN + C.PH_INNER_MARGIN) and (pH_hi <= C.PH_MAX - C.PH_INNER_MARGIN)
    # jika interval pH menyempit aneh, tetap pakai median sebagai cadangan
    if not pH_ok:
        pH_ok = (C.PH_MIN + C.PH_INNER_MARGIN) <= pH_med <= (C.PH_MAX - C.PH_INNER_MARGIN)
    turb_ok = turb_hi <= C.TURB_MAX_NTU * C.MARGIN
    tds_ok = True
    if C.TDS_MAX is not None:
        tds_ok = tds_hi <= C.TDS_MAX * C.MARGIN
    return pH_ok and turb_ok and tds_ok


def _maybe_explore(volt, hours, n_real, rng):
    """20–30 sesi pertama: jitter ±1–2 V di V_GRID agar data punya variasi tegangan."""
    if hours <= 0 or n_real >= C.N_EXPLORATION_SESSIONS:
        return int(volt), False
    delta = int(rng.randint(-int(C.EXPLORATION_VOLT_DELTA), int(C.EXPLORATION_VOLT_DELTA) + 1))
    if delta == 0:
        delta = int(rng.choice([-1, 1]))
    return _clip_to_grid(volt + delta), True


def _conservative(reason: str, data_label: str, model_version: str, extra=None,
                  n_real=0, rng=None):
    hours = float(C.BLOCK_HOURS_MAX)
    volt = int(round(float(C.V_GRID.max())))
    exploration = False
    if rng is not None:
        volt, exploration = _maybe_explore(volt, hours, n_real, rng)
    out = {
        "reachable": False,
        "hours": hours,
        "volt": volt,
        "fallback": "conservative",
        "reason": reason,
        "data_label": data_label,
        "model_version": model_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exploration": exploration,
    }
    if extra:
        out.update(extra)
    return out


def _clip_to_grid(volt: float) -> int:
    v = float(np.clip(volt, C.V_GRID.min(), C.V_GRID.max()))
    idx = int(np.argmin(np.abs(C.V_GRID - v)))
    return int(round(float(C.V_GRID[idx])))


def _next_block_hours(t_star: float) -> float:
    if t_star <= 1e-6:
        return 0.0
    h = min(max(t_star, C.BLOCK_HOURS_MIN), C.BLOCK_HOURS_MAX)
    # rapatkan ke 15 atau 30 menit
    return C.BLOCK_HOURS_MIN if h <= (C.BLOCK_HOURS_MIN + C.BLOCK_HOURS_MAX) / 2 else C.BLOCK_HOURS_MAX


def recommend(bundle, pH, TDS, turb_NTU, temp_C,
              electrode_type=None, gap_cm=None,
              n_real_sessions=None, rng=None):
    """
    Rekomendasi blok berikutnya (receding horizon).
    hours = durasi blok 15/30 menit (bukan klaim sisa waktu total ke operator
            kecuali pred_remaining_h juga dikembalikan).
    """
    electrode_type = C.ELECTRODE_TYPE if electrode_type is None else electrode_type
    gap_cm = C.GAP_CM if gap_cm is None else gap_cm
    data_label = bundle.get("data_label", "SINTETIS")
    model_version = bundle.get("model_version", C.MODEL_VERSION_BASE)
    n_real = bundle.get("n_real_sessions", 0) if n_real_sessions is None else n_real_sessions
    rng = np.random.RandomState(None) if rng is None else rng

    extra_common = {
        "pred_turb_NTU": None,
        "pred_pH": None,
        "pred_TDS": None,
        "ood": False,
        "uncertain": False,
    }

    # OOD pada kondisi air sekarang (bukan pada V,t yang kita pilih)
    ood_row = pd.DataFrame([{
        "pH_init": pH, "TDS_init": TDS, "turb_init_NTU": turb_NTU, "temp_C": temp_C,
        "electrode_type": electrode_type, "gap_cm": gap_cm,
    }])[C.OOD_COLS]
    iso, scaler = bundle["iso"], bundle["iso_scaler"]
    Xs = scaler.transform(ood_row)
    ood_score = float(iso.decision_function(Xs)[0])
    ood_flag = int(iso.predict(Xs)[0]) == -1
    # jaring pengaman: |z| ekstrem vs sebaran latih (bukan baku mutu)
    if np.any(np.abs(Xs) > 8):
        ood_flag = True
    extra_common["ood"] = ood_flag
    extra_common["ood_score"] = round(ood_score, 4)

    if ood_flag:
        return _conservative("ood", data_label, model_version, extra_common, n_real=n_real, rng=rng)

    # sudah di dalam target proxy?
    already = _passes(pH, pH, pH, turb_NTU, TDS)
    if already:
        return {
            "reachable": True,
            "hours": 0.0,
            "volt": 0,
            "fallback": None,
            "reason": "already_in_target_proxy",
            "data_label": data_label,
            "model_version": model_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exploration": False,
            **extra_common,
            "pred_turb_NTU": round(float(turb_NTU), 1),
            "pred_pH": round(float(pH), 2),
            "pred_TDS": round(float(TDS), 1),
            "pred_remaining_h": 0.0,
        }

    VV, TT = np.meshgrid(C.V_GRID, C.T_GRID)
    g = pd.DataFrame({"voltage_V": VV.ravel(), "duration_h": TT.ravel()})
    for k, v in dict(
        pH_init=pH, TDS_init=TDS, turb_init_NTU=turb_NTU, temp_C=temp_C,
        electrode_type=electrode_type, gap_cm=gap_cm,
    ).items():
        g[k] = v
    qpred = predict_quantiles(bundle["models"], g[C.QUAL_X])
    g["pH_p50"] = qpred["pH_final"][0.5]
    g["pH_lo"] = qpred["pH_final"][0.1]
    g["pH_hi"] = qpred["pH_final"][0.9]
    g["turb_p50"] = qpred["turb_final_NTU"][0.5]
    g["turb_hi"] = qpred["turb_final_NTU"][0.9]
    g["turb_lo"] = qpred["turb_final_NTU"][0.1]
    g["tds_p50"] = qpred["TDS_final"][0.5]
    g["tds_hi"] = qpred["TDS_final"][0.9]
    g["energy_rel"] = g.voltage_V ** 2 * g.duration_h
    g["turb_span"] = g.turb_hi - g.turb_lo
    g["ok"] = [
        _passes(lo, hi, med, th, td)
        for lo, hi, med, th, td in zip(
            g.pH_lo, g.pH_hi, g.pH_p50, g.turb_hi, g.tds_hi
        )
    ]

    # ketidakpastian: jika semua kandidat lolos punya span kekeruhan besar
    ok = g[g.ok]
    if ok.empty:
        b = g.sort_values(["duration_h", "voltage_V"]).iloc[-1]
        why = []
        if b.turb_hi > C.TURB_MAX_NTU * C.MARGIN:
            why.append("turbidity")
        if not ((C.PH_MIN + C.PH_INNER_MARGIN) <= b.pH_p50 <= (C.PH_MAX - C.PH_INNER_MARGIN)):
            why.append("pH")
        extra_common.update(
            pred_turb_NTU=round(float(b.turb_p50), 1),
            pred_pH=round(float(b.pH_p50), 2),
            pred_TDS=round(float(b.tds_p50), 1),
            tidak_lolos=why,
            pred_remaining_h=round(float(b.duration_h), 2),
        )
        return _conservative(
            "unreachable_or_uncertain_grid", data_label, model_version, extra_common,
            n_real=n_real, rng=rng,
        )

    uncertain = bool(ok.turb_span.min() > C.UNCERTAIN_TURB_SPAN_NTU)
    if uncertain:
        extra_common["uncertain"] = True
        return _conservative(
            "wide_prediction_interval", data_label, model_version, extra_common,
            n_real=n_real, rng=rng,
        )

    b = ok.sort_values("energy_rel").iloc[0]
    t_star = float(b.duration_h)
    volt = _clip_to_grid(float(b.voltage_V))
    hours = _next_block_hours(t_star)
    volt, exploration = _maybe_explore(volt, hours, n_real, rng)

    return {
        "reachable": True,
        "hours": round(hours, 2),
        "volt": volt,
        "fallback": None,
        "reason": "grid_search",
        "data_label": data_label,
        "model_version": model_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exploration": exploration,
        "ood": False,
        "uncertain": False,
        "ood_score": extra_common["ood_score"],
        "pred_turb_NTU": round(float(b.turb_p50), 1),
        "pred_pH": round(float(b.pH_p50), 2),
        "pred_TDS": round(float(b.tds_p50), 1),
        "pred_remaining_h": round(t_star, 2),
        "energy_rel": round(float(b.energy_rel), 0),
    }


def load_bundle(path=None):
    path = path or C.MODEL_PATH
    with open(path, "rb") as f:
        return pickle.load(f)


def save_bundle(bundle, path=None):
    path = path or C.MODEL_PATH
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(bundle, f)
    return path


if __name__ == "__main__":
    from config import EC_MODEL_PATH
    bundle = load_bundle(EC_MODEL_PATH)
    print("data_label=", bundle.get("data_label"), "version=", bundle.get("model_version"))
    r = recommend(bundle, pH=9.2, TDS=600, turb_NTU=400, temp_C=30, rng=np.random.RandomState(0))
    print(r)
