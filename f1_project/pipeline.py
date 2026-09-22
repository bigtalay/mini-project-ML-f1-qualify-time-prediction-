"""Offline analytics pipeline. Collection is a separate, explicit maintenance command."""
from intelligence.data import Dataset
from intelligence.ml import ensure_artifacts

if __name__ == "__main__":
    dataset = Dataset()
    bundle = ensure_artifacts(dataset)
    print(dataset.quality())
    print(bundle["report"]["test"])
