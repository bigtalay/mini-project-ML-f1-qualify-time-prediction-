"""Export the same pre-qualifying feature table used by the API and notebook."""
import argparse
from pathlib import Path

from intelligence.data import DATA, Dataset


def prepare_modeling_table(data_dir=DATA, output_path=DATA / "processed/f1_model_features.csv"):
    dataset = Dataset(Path(data_dir))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.features.to_csv(output, index=False)
    return dataset.features, dataset.quality()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=DATA / "processed/f1_model_features.csv")
    args = parser.parse_args()
    frame, report = prepare_modeling_table(args.data, args.output)
    print(report)
    print(f"Prepared {len(frame)} driver/event rows -> {args.output}")
