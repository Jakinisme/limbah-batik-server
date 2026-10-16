---
title: NIPRO EC Backend
emoji: 💧
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Backend elektrokoagulasi NIPRO 2026

Folder ini **mandiri**: kode inference + `models/ec_recommender.pkl`.
Tidak perlu environment PC lokal.

Alur: ESP32 menulis 5 sensor ke Firebase `/sensors/water/latest` → Space ini
menghitung rekomendasi EC → menulis `/recommendations/ec/latest`.

Node rekomendasi berisi seluruh output model (tidak lagi dipotong whitelist):

```
{hours, volt, target_volt, reachable, model_version, timestamp, data_label, reason,
 fallback, exploration, ood, ood_score, uncertain,
 pred_pH, pred_TDS, pred_turb_NTU, pred_remaining_h, energy_rel, tidak_lolos,
 measured_pH, measured_TDS, measured_turbidity_NTU, measured_temp_C, measured_voltage_V}
```

- `volt` = **target** tegangan elektroda (V_GRID + jitter eksplorasi), bukan hasil ukur.
  `target_volt` adalah nama eksplisitnya; `volt` tetap dikirim karena firmware ESP
  (`esp/src/core/ml_gate.cpp`) dan dashboard masih membacanya.
- `measured_*` = echo sensor yang dipakai model, supaya node ini bisa diaudit langsung
  terhadap `/sensors/water/latest`.
- `pred_*` bernilai `null` saat model menolak (`reason=ood`) — itu penolakan, bukan nol.

Model saat ini berlabel **SINTETIS**. Jangan diklaim akurat.

## Isi yang diunggah ke Space

Unggah **isi folder `server/`** (bukan seluruh repo), termasuk `models/`.

```
Dockerfile
README.md
requirements.txt
app.py
main.py
config.py
model_runner.py
firebase_client.py
telegram_notifier.py
ec_config.py
recommend_ec.py
models/ec_recommender.pkl
```

Jangan unggah `serviceAccountKey.json`.

Sebelum upload, dari PC (opsional, kalau baru retraining):

```text
python server/sync_bundle.py
```

## Buat Space di Hugging Face

1. [huggingface.co/new-space](https://huggingface.co/new-space)
2. SDK: **Docker**
3. Hardware: CPU. Untuk **24 jam tanpa tidur**, di Settings Space aktifkan
   hardware yang tidak sleep (paket berbayar / persistent). Space CPU gratis
   **bisa tidur** saat tidak ada pengunjung — listener Firebase ikut mati.
4. Unggah semua file di folder ini, atau `git push` repo Space yang isinya folder ini.

## Secrets (Settings → Variables and secrets)

Wajib:

| Nama | Isi |
|---|---|
| `FIREBASE_DATABASE_URL` | `https://NAMA-PROYEK-default-rtdb.REGION.firebasedatabase.app` |
| `FIREBASE_CREDENTIALS_JSON` | Isi utuh file service account JSON (satu baris / utuh) |

Opsional:

| Nama | Isi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token BotFather |
| `TELEGRAM_CHAT_IDS` | chat id, pisah koma kalau lebih dari satu |
| `PATH_SENSOR_WATER` | default `/sensors/water/latest` |
| `PATH_RECOMMEND_EC` | default `/recommendations/ec/latest` |

Firebase: service account butuh akses Realtime Database.

## Cek hidup

Setelah Building selesai, buka URL Space. Harus terlihat `Listener: running`.
JSON: `https://NAMA-SPACE.hf.space/health`

Kalau `waiting_credentials`, secret belum kebaca — restart Space setelah save secret.

## Lokal (tes)

```text
cd server
pip install -r requirements.txt
set FIREBASE_DATABASE_URL=...
set FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
python app.py
```

Buka http://127.0.0.1:7860/
