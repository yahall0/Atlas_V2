"""Download the MuRIL base model to backend/models/hf_cache/muril-base-cased.

Run this ONCE on the host before `docker compose up`.  After this, the
container runs with TRANSFORMERS_OFFLINE=1 and never contacts HuggingFace.

Usage
-----
    python scripts/download_base_model.py

Requirements (host, not container):
    pip install huggingface_hub
"""

from __future__ import annotations

import sys
from pathlib import Path

MODEL_ID = "google/muril-base-cased"
# Saved next to backend/models/ which is bind-mounted into the container
SAVE_DIR = Path(__file__).parent.parent / "backend" / "models" / "hf_cache" / "muril-base-cased"


def main() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub not installed on host.")
        print("Run: pip install huggingface_hub")
        sys.exit(1)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_ID} → {SAVE_DIR}")
    print("(This is a ~900 MB download — runs once, then fully offline.)\n")

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(SAVE_DIR),
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
    )
    print(f"\n✓ Model downloaded to {SAVE_DIR}")

    print("\nNext steps:")
    print("  1. docker compose build backend")
    print("  2. docker compose up -d backend")
    print("  3. docker exec atlas_platform-backend-1 mkdir -p /data")
    print("  4. docker cp scripts\\data\\synthetic_fir_training.csv atlas_platform-backend-1:/data/synthetic_fir_training.csv")
    print("  5. docker exec atlas_platform-backend-1 python -m app.ml.train \\")
    print("       --data_path /data/synthetic_fir_training.csv \\")
    print("       --output_dir /app/models/atlas_classifier_v1 \\")
    print("       --epochs 3 --batch_size 8 --cpu_mode")


if __name__ == "__main__":
    main()
