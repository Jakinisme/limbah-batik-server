"""
ec_config.py — satu tempat untuk semua angka prototipe EC (NIPRO 2026).

Aturan: angka tanpa sumber resmi ditandai TODO. Placeholder bukan baku mutu.
COD/BOD/warna/konduktivitas/TSS BUKAN input model (tidak ada sensor).
"""
from pathlib import Path
import numpy as np

# Di Space, file ini tinggal di folder server/ (ROOT = folder itu).
ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Hardware — diisi dari jawaban operator (2026-04-10), volume masih kosong
# ---------------------------------------------------------------------------
ELECTRODE_TYPE = 1          # 0=Al, 1=Fe. Konfirmasi operator: Fe
GAP_CM = 2.0                # cm. Konfirmasi operator: ~2 cm
REACTOR_MODE = "batch"      # konfirmasi operator: batch (bukan kontinyu)
BATCH_VOLUME_L = None       # TODO: operator belum menyatakan volume reaktor (L)

# Rentang yang bisa dihasilkan XL6009 + MCP41100. Konfirmasi operator: 12–20 V, step 1 V.
V_MIN, V_MAX, V_STEP = 12.0, 20.0, 1.0
V_GRID = np.arange(V_MIN, V_MAX + 1e-9, V_STEP)

# Kandidat sisa waktu (jam) untuk grid search forward model.
T_MIN_H, T_MAX_H, T_STEP_H = 0.25, 8.0, 0.25
T_GRID = np.arange(T_MIN_H, T_MAX_H + 1e-9, T_STEP_H)

# Receding horizon: satu blok pendek, lalu ukur ulang.
BLOCK_HOURS_MIN = 0.25      # 15 menit
BLOCK_HOURS_MAX = 0.50      # 30 menit
SETTLE_SECONDS = 90         # diam setelah EC sebelum baca sensor akhir (gelembung hilang)

# ---------------------------------------------------------------------------
# Sensor tegangan — BELUM DIPASANG / BELUM DIUKUR (konfirmasi operator)
# ---------------------------------------------------------------------------
VOLTAGE_DIVIDER_RATIO = None    # TODO: modul 0–25 V umumnya 5:1; isi setelah wiring
VOLTAGE_ADC_PIN = None          # TODO: pin ADC ESP32
# Catatan (bukan kalibrasi): ADC ESP32 ~3.3 V. Jika pembagi 5:1, Vin jenuh ~16.5 V
# sementara V_GRID sampai 20 V. Ukur ulang setelah wiring.
ADC_SATURATE_NOTE_VIN_V = 16.5

# TDS: DFRobot analog, rentang hobi 0–1000 ppm (konfirmasi operator)
TDS_SENSOR_MAX_PPM = 1000.0
# Turbidity analog: kalibrasi NTU belum ada
TURB_SENSOR_MAX_NTU = None      # TODO: kalibrasi lab (NTU vs tegangan sensor)

# ---------------------------------------------------------------------------
# Baku mutu / target gerbang rekomendasi
# ---------------------------------------------------------------------------
# COD 150 mg/L: terkonfirmasi dari sumber sekunder Pergub Jatim 72/2013 (tekstil).
# Bukan input model; dicatat hanya sebagai konteks regulasi.
COD_LIMIT_MGL = 150.0           # sumber sekunder; TODO lampiran resmi

# TODO: verifikasi langsung lampiran Pergub Jatim 72/2013 (tekstil)
PH_MIN, PH_MAX = 6.0, 9.0       # TODO belum verifikasi lampiran
TSS_LIMIT_MGL = None            # TODO: kemungkinan 50 mg/L; belum verifikasi; BUKAN input
TDS_MAX = None                  # batas TDS tidak ditemukan di sumber yang dicek

# Proxy kekeruhan untuk gerbang "lolos". PLACEHOLDER sampai kalibrasi TSS/COD lab.
# Rencana: TURB_MAX_NTU = TSS_limit_terverifikasi / (TSS_lab per NTU)
TURB_MAX_NTU = 50.0             # PLACEHOLDER
MARGIN = 0.9                    # kebijakan prototipe (10% lebih ketat), bukan teks regulasi
PH_INNER_MARGIN = 0.2           # pita dalam pH; kebijakan prototipe, bukan regulasi

USE_MONOTONIC = False           # jangan pakai constraint monotonik sampai data asli mendukung
# I_MAX hanya di generator Faraday sintetis (arus TIDAK diukur)
I_MAX_SYNTHETIC = 10.0
# Volume Faraday di generator jika BATCH_VOLUME_L masih None — PLACEHOLDER, bukan alat nyata
SYNTHETIC_VOLUME_L = 10.0       # TODO ganti setelah volume reaktor diketahui

# ---------------------------------------------------------------------------
# Data & model
# ---------------------------------------------------------------------------
DATA_PATH = str(ROOT / "ec_experiments.csv")          # HANYA data eksperimen asli
LITERATURE_PATH = str(ROOT / "batik_ec_literature.csv")  # validasi kurva; JANGAN di-train
MODEL_PATH = str(ROOT / "models" / "ec_recommender.pkl")
PRETRAIN_PATH = str(ROOT / "models" / "ec_pretrained_synthetic.pkl")

SENSOR_STATE = ["pH_init", "TDS_init", "turb_init_NTU", "temp_C"]
CONFIG_COLS = ["electrode_type", "gap_cm"]
CTRL_COLS = ["voltage_V", "duration_h"]
QUAL_X = SENSOR_STATE + CONFIG_COLS + CTRL_COLS
QUAL_Y = ["pH_final", "turb_final_NTU", "TDS_final"]
OOD_COLS = SENSOR_STATE + CONFIG_COLS  # deteksi input air di luar sebaran latih

REAL_SAMPLE_WEIGHT = 8.0
N_BOOTSTRAP = 5
N_EXPLORATION_SESSIONS = 25     # 20–30 sesi pertama: jitter tegangan
EXPLORATION_VOLT_DELTA = 2.0    # ±1–2 V, tetap di V_GRID
ISO_CONTAMINATION = 0.05
# Jika (q90−q10) turbidity lebih besar dari ini → anggap tidak yakin.
# TODO: kalibrasi setelah ada data asli; angka ini kebijakan prototipe.
UNCERTAIN_TURB_SPAN_NTU = 40.0

MODEL_VERSION_BASE = "ec-rh-v1"

EXPERIMENT_COLUMNS = [
    "session_id",
    "pH_init", "TDS_init", "turb_init_NTU", "temp_C",
    "electrode_type", "gap_cm", "voltage_V", "duration_h",
    "pH_final", "turb_final_NTU", "TDS_final",
    "sat_tds", "sat_turb", "sat_adc", "outlier_flag",
    "exploration", "is_synthetic", "notes",
]


def load_config_dict():
    """Snapshot angka yang boleh dicek tes unit (tanpa array numpy besar)."""
    return {
        "DATA_PATH": DATA_PATH,
        "ELECTRODE_TYPE": ELECTRODE_TYPE,
        "GAP_CM": GAP_CM,
        "REACTOR_MODE": REACTOR_MODE,
        "BATCH_VOLUME_L": BATCH_VOLUME_L,
        "V_MIN": V_MIN,
        "V_MAX": V_MAX,
        "V_STEP": V_STEP,
        "TURB_MAX_NTU": TURB_MAX_NTU,
        "TDS_MAX": TDS_MAX,
        "PH_MIN": PH_MIN,
        "PH_MAX": PH_MAX,
        "MARGIN": MARGIN,
        "SETTLE_SECONDS": SETTLE_SECONDS,
        "BLOCK_HOURS_MIN": BLOCK_HOURS_MIN,
        "BLOCK_HOURS_MAX": BLOCK_HOURS_MAX,
        "TDS_SENSOR_MAX_PPM": TDS_SENSOR_MAX_PPM,
        "USE_MONOTONIC": USE_MONOTONIC,
        "COD_LIMIT_MGL": COD_LIMIT_MGL,
        "TSS_LIMIT_MGL": TSS_LIMIT_MGL,
        "VOLTAGE_DIVIDER_RATIO": VOLTAGE_DIVIDER_RATIO,
        "VOLTAGE_ADC_PIN": VOLTAGE_ADC_PIN,
    }
