"""Run data collection and model training end to end."""

from data_collection import collect_dataset
from modeling import train_models


if __name__ == "__main__":
    collect_dataset()
    train_models()
