#!/usr/bin/env python3
"""
scripts/download_models.py

Run once during Railway build (or local setup) to download models
into the repository's models/ directory.

    python scripts/download_models.py

What this downloads
-------------------
1. BGE-small-en-v1.5 ONNX model + tokenizer   (~43 MB total)
   → models/bge-small/onnx/model.onnx
   → models/bge-small/tokenizer.json
   → models/bge-small/tokenizer_config.json

2. spaCy en_core_web_sm                         (~12 MB)
   (installed as a package, not a file download)

Total cold-start resident memory (both loaded):  ~55 MB
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"


def download_bge_onnx() -> None:
    print("── BGE-small-en-v1.5 (ONNX) ──────────────────────────────")
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError:
        print("  Installing huggingface_hub …")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub", "-q"])
        from huggingface_hub import hf_hub_download

    out_dir = MODELS_DIR / "bge-small"
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_dir = out_dir / "onnx"
    onnx_dir.mkdir(exist_ok=True)

    # ONNX model weights
    print("  Downloading onnx/model.onnx …")
    hf_hub_download(
        repo_id="BAAI/bge-small-en-v1.5",
        filename="onnx/model.onnx",
        local_dir=str(out_dir),
    )

    # Tokenizer files (needed by the local tokenizers library fallback)
    for fname in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"):
        print(f"  Downloading {fname} …")
        try:
            hf_hub_download(
                repo_id="BAAI/bge-small-en-v1.5",
                filename=fname,
                local_dir=str(out_dir),
            )
        except Exception as e:
            print(f"    ⚠  Could not download {fname}: {e}")

    print(f"  ✓ Saved to {out_dir}\n")


def download_spacy() -> None:
    print("── spaCy en_core_web_sm ────────────────────────────────────")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  ✓ en_core_web_sm installed\n")
    else:
        print(f"  ✗ spaCy download failed:\n{result.stderr}")
        sys.exit(1)


def verify() -> None:
    print("── Verification ────────────────────────────────────────────")
    errors = []

    onnx_path = MODELS_DIR / "bge-small" / "onnx" / "model.onnx"
    if onnx_path.exists():
        size_mb = onnx_path.stat().st_size / 1024 / 1024
        print(f"  ✓ BGE ONNX model  ({size_mb:.1f} MB)")
    else:
        errors.append(f"  ✗ BGE ONNX model not found at {onnx_path}")

    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print(f"  ✓ spaCy en_core_web_sm loaded")
    except Exception as e:
        errors.append(f"  ✗ spaCy load failed: {e}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("\n  All models ready. ✓")


if __name__ == "__main__":
    download_bge_onnx()
    download_spacy()
    verify()