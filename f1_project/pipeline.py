"""Run raw extraction, data preparation, and model training end to end."""

from data_collection import collect_raw_dataset
from data_preparation import prepare_modeling_table
from modeling import train_models


if __name__ == "__main__":
    collect_raw_dataset()
    prepare_modeling_table()
    train_models()
