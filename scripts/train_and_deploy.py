#!/usr/bin/env python3
"""End-to-end training and deployment pipeline for the ATLAS FIR classifier.

Takes a labelled FIR CSV on the host, trains MuRIL inside the backend
container, verifies the checkpoint, and reloads the backend — all in one
command.

Usage
-----
    # Train on a labelled CSV you already have
    python scripts/train_and_deploy.py --data_path data/my_firs.csv

    # Train on auto-generated synthetic data (no CSV needed)
    python scripts/train_and_deploy.py --synthetic --samples_per_class 30

    # Full custom run
    python scripts/train_and_deploy.py \\
        --data_path data/my_firs.csv \\
        --epochs 5 \\
        --batch_size 2 \\
        --max_length 128 \\
        --output_dir backend/models/atlas_classifier_v2 \\
        --container atlas_platform-backend-1

Required CSV columns: text, category
Optional columns:      language, district

Categories (11): assault, cybercrime, dacoity_robbery, domestic_violence,
                 fraud, kidnapping, murder, narcotics, other, rape_sexoff, theft
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_CONTAINER   = "atlas_platform-backend-1"
DEFAULT_OUTPUT_DIR  = "backend/models/atlas_classifier_v1"
CONTAINER_DATA_PATH = "/data/training_input.csv"
CONTAINER_OUT_DIR   = None   # derived from --output_dir below
API_BASE            = "http://localhost:8000"
COMPOSE_FILE        = "docker-compose.yml"


# ── helpers ───────────────────────────────────────────────────────────────────

def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess, streaming stdout/stderr to the console unless capture=True."""
    log.debug("$ %s", " ".join(str(c) for c in cmd))
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def docker_exec(container: str, sh_cmd: str, *, check: bool = True, capture: bool = False):
    return run(["docker", "exec", container, "sh", "-c", sh_cmd], check=check, capture=capture)


def container_running(container: str) -> bool:
    result = run(
        ["docker", "inspect", "--format", "{{.State.Running}}", container],
        check=False, capture=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def validate_csv(path: Path) -> int:
    """Check required columns exist and return row count."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [c for c in ("text", "category") if c not in headers]
        if missing:
            log.error("CSV is missing required columns: %s", missing)
            log.error("Found columns: %s", headers)
            sys.exit(1)
        rows = sum(1 for _ in reader)
    log.info("CSV validated — %d rows, columns: %s", rows, headers)
    return rows


def wait_for_backend(base: str, timeout: int = 120) -> bool:
    """Poll the health endpoint until the backend responds or timeout."""
    url = f"{base}/api/v1/health"
    deadline = time.time() + timeout
    log.info("Waiting for backend at %s …", url)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


# ── pipeline stages ───────────────────────────────────────────────────────────

def stage_check_container(container: str) -> None:
    log.info("[1/6] Checking container '%s' is running …", container)
    if not container_running(container):
        log.error("Container '%s' is not running.", container)
        log.error("Start it with:  docker compose up -d backend")
        sys.exit(1)
    log.info("      Container is running ✓")


def stage_check_base_model(container: str) -> None:
    log.info("[2/6] Checking base model is available …")
    result = docker_exec(
        container,
        "test -f /app/models/hf_cache/muril-base-cased/config.json && echo OK || echo MISSING",
        capture=True,
    )
    if result.stdout.strip() != "OK":
        log.error("Base model not found at /app/models/hf_cache/muril-base-cased/")
        log.error("Run the one-time download first:")
        log.error("  pip install huggingface_hub")
        log.error("  python scripts/download_base_model.py")
        sys.exit(1)
    log.info("      Base model (MuRIL) found ✓")


def stage_prepare_data(
    container: str,
    data_path: Path | None,
    synthetic: bool,
    samples_per_class: int,
) -> int:
    """Copy CSV into container (or generate synthetic data) and return row count."""
    log.info("[3/6] Preparing training data …")

    docker_exec(container, "mkdir -p /data")

    if synthetic:
        log.info("      Generating synthetic data (%d samples/class × 11 classes) …", samples_per_class)
        docker_exec(
            container,
            f"python scripts/generate_synthetic_training_data.py "
            f"--output_dir /data --samples_per_class {samples_per_class}",
        )
        # rename to our standard container path
        docker_exec(container, f"cp /data/synthetic_fir_training.csv {CONTAINER_DATA_PATH}")
        result = docker_exec(container, f"wc -l {CONTAINER_DATA_PATH}", capture=True)
        row_count = max(0, int(result.stdout.split()[0]) - 1)  # subtract header
        log.info("      Generated %d training rows ✓", row_count)
        return row_count

    # Copy host CSV into container
    log.info("      Copying %s → container:%s", data_path, CONTAINER_DATA_PATH)
    run(["docker", "cp", str(data_path), f"{container}:{CONTAINER_DATA_PATH}"])
    row_count = validate_csv(data_path)
    log.info("      Data copied ✓  (%d rows)", row_count)
    return row_count


def stage_train(
    container: str,
    container_out_dir: str,
    epochs: int,
    batch_size: int,
    max_length: int,
    max_samples: int | None,
    no_class_weights: bool,
    lr: float,
) -> None:
    log.info("[4/6] Starting training …")
    log.info("      epochs=%d  batch_size=%d  max_length=%d  lr=%s",
             epochs, batch_size, max_length, lr)

    cmd_parts = [
        "python -m app.ml.train",
        f"--data_path {CONTAINER_DATA_PATH}",
        f"--output_dir {container_out_dir}",
        f"--epochs {epochs}",
        f"--batch_size {batch_size}",
        f"--max_length {max_length}",
        f"--lr {lr}",
        "--cpu_mode",
    ]
    if max_samples:
        cmd_parts.append(f"--max_samples {max_samples}")
    if no_class_weights:
        cmd_parts.append("--no_class_weights")

    train_cmd = " ".join(cmd_parts) + " 2>&1"
    log.info("      Command: %s", train_cmd)

    try:
        docker_exec(container, train_cmd)
    except subprocess.CalledProcessError:
        log.error("Training command exited with non-zero status.")
        log.error("Re-run with:  docker exec %s sh -c \"%s\"", container, train_cmd)
        sys.exit(1)

    log.info("      Training complete ✓")


def stage_verify_checkpoint(container: str, container_out_dir: str, host_out_dir: Path) -> dict:
    log.info("[5/6] Verifying checkpoint …")

    result = docker_exec(
        container,
        f"cat {container_out_dir}/evaluation_metrics.json",
        check=False, capture=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        log.error("evaluation_metrics.json not found — training may have crashed.")
        log.error("Check logs with:")
        log.error("  docker exec %s cat /tmp/train.log", container)
        sys.exit(1)

    try:
        metrics = json.loads(result.stdout)
    except json.JSONDecodeError:
        log.error("evaluation_metrics.json is corrupt: %s", result.stdout)
        sys.exit(1)

    val_f1 = metrics.get("best_val_f1", 0.0)
    test_acc = metrics.get("test_accuracy", 0.0)
    model_ver = metrics.get("model_version", "unknown")

    log.info("      model_version : %s", model_ver)
    log.info("      best_val_f1   : %.4f", val_f1)
    log.info("      test_accuracy : %.4f", test_acc)

    if val_f1 == 0.0 and test_acc == 0.0:
        log.warning("      Metrics are both 0.0 — model may not have learned.")
        log.warning("      Consider more data (--samples_per_class 50) or more epochs (--epochs 5).")
    else:
        log.info("      Checkpoint verified ✓")

    # Write a local copy of metrics to host output dir for reference
    host_out_dir.mkdir(parents=True, exist_ok=True)
    metrics_copy = host_out_dir / "last_training_metrics.json"
    metrics_copy.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    log.info("      Metrics saved locally → %s", metrics_copy)

    return metrics


def stage_deploy(container: str) -> None:
    log.info("[6/6] Reloading backend …")

    # check if docker compose is available
    compose_result = run(["docker", "compose", "version"], check=False, capture=True)
    if compose_result.returncode != 0:
        log.warning("docker compose not available — restart the backend manually:")
        log.warning("  docker compose restart backend")
        return

    if not Path(COMPOSE_FILE).exists():
        log.warning("%s not found in current directory.", COMPOSE_FILE)
        log.warning("Run from repo root, or restart manually: docker compose restart backend")
        return

    run(["docker", "compose", "restart", "backend"])
    log.info("      Backend restarting …")

    if wait_for_backend(API_BASE, timeout=90):
        log.info("      Backend is healthy ✓")
        # Confirm the new checkpoint is loaded
        try:
            with urllib.request.urlopen(f"{API_BASE}/api/v1/predict/model-info", timeout=10) as resp:
                info = json.loads(resp.read())
            log.info("      Active model  : %s", info.get("model_version", "unknown"))
            log.info("      Active F1     : %s", info.get("best_f1", "n/a"))
        except Exception as exc:
            log.warning("      Could not read model-info endpoint: %s", exc)
    else:
        log.warning("      Backend did not become healthy within 90 s.")
        log.warning("      Check with:  docker compose logs backend")


# ── entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the ATLAS FIR classifier and redeploy the backend.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Data source (mutually exclusive)
    data_group = parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument(
        "--data_path",
        type=Path,
        metavar="CSV",
        help="Path to a labelled FIR CSV on the host (columns: text, category).",
    )
    data_group.add_argument(
        "--synthetic",
        action="store_true",
        help="Generate synthetic training data inside the container instead of using a CSV.",
    )

    # Synthetic data options
    parser.add_argument(
        "--samples_per_class", type=int, default=30,
        help="Rows per crime category when --synthetic is used.",
    )

    # Training options
    parser.add_argument("--epochs",      type=int,   default=3,    help="Training epochs.")
    parser.add_argument("--batch_size",  type=int,   default=2,    help="Per-device batch size.")
    parser.add_argument("--max_length",  type=int,   default=128,  help="Tokeniser max length.")
    parser.add_argument("--lr",          type=float, default=2e-5, help="Learning rate.")
    parser.add_argument(
        "--max_samples", type=int, default=None,
        help="Cap training rows (useful for smoke tests — e.g. 50).",
    )
    parser.add_argument(
        "--no_class_weights", action="store_true",
        help="Disable inverse-frequency class weighting.",
    )

    # Infrastructure options
    parser.add_argument(
        "--output_dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR),
        help="Host path for the checkpoint (relative to repo root).",
    )
    parser.add_argument(
        "--container", default=DEFAULT_CONTAINER,
        help="Docker container name for the ATLAS backend.",
    )
    parser.add_argument(
        "--skip_deploy", action="store_true",
        help="Skip the backend restart after training.",
    )

    args = parser.parse_args()

    # Validate host CSV before doing anything else
    if args.data_path:
        if not args.data_path.exists():
            log.error("File not found: %s", args.data_path)
            sys.exit(1)
        validate_csv(args.data_path)

    # Derive the container-internal output path from the host path
    # host:  backend/models/atlas_classifier_v1
    # mount: ./backend/models -> /app/models
    # so:    /app/models/atlas_classifier_v1
    rel = args.output_dir
    try:
        # strip the leading "backend/models/" portion
        rel_inside = rel.relative_to("backend/models")
        container_out_dir = f"/app/models/{rel_inside}"
    except ValueError:
        # fallback: just use the path as-is if it doesn't start with backend/models
        container_out_dir = f"/app/models/{rel.name}"

    log.info("=" * 60)
    log.info("ATLAS Training & Deploy Pipeline")
    log.info("  data source   : %s",
             str(args.data_path) if args.data_path else f"synthetic ({args.samples_per_class}/class)")
    log.info("  output_dir    : %s  (container: %s)", args.output_dir, container_out_dir)
    log.info("  epochs=%d  batch=%d  lr=%s  max_length=%d",
             args.epochs, args.batch_size, args.lr, args.max_length)
    log.info("=" * 60)

    stage_check_container(args.container)
    stage_check_base_model(args.container)
    stage_prepare_data(args.container, args.data_path, args.synthetic, args.samples_per_class)
    stage_train(
        args.container,
        container_out_dir,
        args.epochs,
        args.batch_size,
        args.max_length,
        args.max_samples,
        args.no_class_weights,
        args.lr,
    )
    metrics = stage_verify_checkpoint(args.container, container_out_dir, args.output_dir)

    if not args.skip_deploy:
        stage_deploy(args.container)
    else:
        log.info("[6/6] Skipped (--skip_deploy)")

    log.info("=" * 60)
    log.info("Done.")
    log.info("  model_version : %s", metrics.get("model_version"))
    log.info("  best_val_f1   : %.4f", metrics.get("best_val_f1", 0))
    log.info("  test_accuracy : %.4f", metrics.get("test_accuracy", 0))
    log.info("  checkpoint    : %s", args.output_dir)
    if not args.skip_deploy:
        log.info("  predict API   : %s/api/v1/predict/classify", API_BASE)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
