"""Salin ec_config, recommend_ec, dan pickle dari root repo ke folder server.

Jalankan dari root atau dari server/ sebelum upload ke Hugging Face:
    python server/sync_bundle.py
"""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = [
    (ROOT / "ec_config.py", HERE / "ec_config.py"),
    (ROOT / "recommend_ec.py", HERE / "recommend_ec.py"),
    (ROOT / "models" / "ec_recommender.pkl", HERE / "models" / "ec_recommender.pkl"),
    (ROOT / "models" / "ec_pretrained_synthetic.pkl", HERE / "models" / "ec_pretrained_synthetic.pkl"),
]


def main():
    (HERE / "models").mkdir(exist_ok=True)
    for src, dst in FILES:
        if not src.exists():
            print(f"skip (tidak ada): {src}")
            continue
        shutil.copy2(src, dst)
        print(f"ok {src.name} -> {dst}")


if __name__ == "__main__":
    main()
