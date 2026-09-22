"""Prepare offline analytics artifacts. Use --force to deliberately retrain."""
import argparse
import json

from .data import Dataset
from .ml import ensure_artifacts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    dataset = Dataset()
    bundle = ensure_artifacts(dataset, force=args.force)
    print(json.dumps({"quality": dataset.quality(), "selected": bundle["selected"], "test": bundle["report"]["test"]}, indent=2))
