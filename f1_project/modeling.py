"""CLI compatibility entry point for the shared offline evaluation pipeline."""
import argparse
from pathlib import Path

from intelligence.data import Dataset
from intelligence.ml import ARTIFACTS, ensure_artifacts


def train_models(artifact_dir=ARTIFACTS, force=False):
    bundle = ensure_artifacts(Dataset(), Path(artifact_dir), force=force)
    print(bundle["report"])
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACTS)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    train_models(args.artifact_dir, args.force)
