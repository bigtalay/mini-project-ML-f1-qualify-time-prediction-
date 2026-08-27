"""Streamlit UI for the trained qualifying-time predictor."""

from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from preprocessing import transform_features


MODEL_PATH = Path("artifacts/model_bundle.joblib")


def format_lap_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes}:{remaining:06.3f}"


st.set_page_config(page_title="F1 Qualifying Predictor", page_icon="🏎️", layout="wide")
st.title("F1 Qualifying Time Prediction")
st.caption("Trained on FastF1 qualifying, practice, and weather data from 2021-2022; evaluated on 2023.")

if not MODEL_PATH.exists():
    st.error("Model artifacts are not available yet.")
    st.code("docker compose run --rm pipeline", language="powershell")
    st.stop()

bundle = joblib.load(MODEL_PATH)
reference = bundle["reference"]
metrics = bundle["metrics"]

left, right = st.columns([2, 1])
with right:
    st.subheader("Evaluation")
    st.write(bundle["split_description"])
    st.dataframe(metrics, hide_index=True, use_container_width=True)
    st.info(f"Active model: {bundle['model_name']}")

with left:
    st.subheader("Race weekend inputs")
    category_left, category_right = st.columns(2)
    with category_left:
        driver = st.selectbox("Driver", reference["categories"]["Driver"])
        team = st.selectbox("Team", reference["categories"]["Team"])
    with category_right:
        circuit = st.selectbox("Circuit", reference["categories"]["Circuit"])
        year = st.selectbox("Season", reference["years"], index=len(reference["years"]) - 1)

    defaults = reference["numeric_defaults"]
    weather_left, weather_right = st.columns(2)
    with weather_left:
        air_temp = st.number_input("Air temperature (°C)", value=defaults["AirTemp"], step=0.1)
        track_temp = st.number_input("Track temperature (°C)", value=defaults["TrackTemp"], step=0.1)
        humidity = st.number_input("Humidity (%)", min_value=0.0, max_value=100.0, value=defaults["Humidity"], step=0.1)
        rainfall = st.number_input("Rainfall fraction (0-1)", min_value=0.0, max_value=1.0, value=min(max(defaults["Rainfall"], 0.0), 1.0), step=0.01)
    with weather_right:
        fp1 = st.number_input("FP1 best lap (seconds)", value=defaults["FP1_Time"], step=0.001, format="%.3f")
        fp2 = st.number_input("FP2 best lap (seconds)", value=defaults["FP2_Time"], step=0.001, format="%.3f")
        fp3 = st.number_input("FP3 best lap (seconds)", value=defaults["FP3_Time"], step=0.001, format="%.3f")

    if st.button("Predict qualifying time", type="primary", use_container_width=True):
        row = pd.DataFrame(
            [
                {
                    "Driver": driver,
                    "Team": team,
                    "Circuit": circuit,
                    "Year": year,
                    "AirTemp": air_temp,
                    "TrackTemp": track_temp,
                    "Humidity": humidity,
                    "Rainfall": rainfall,
                    "FP1_Time": fp1,
                    "FP2_Time": fp2,
                    "FP3_Time": fp3,
                }
            ]
        )
        transformed = transform_features(row, bundle["preprocessing"])
        prediction = float(bundle["model"].predict(transformed)[0])
        st.metric("Predicted qualifying lap", format_lap_time(prediction), f"{prediction:.3f} seconds")

st.divider()
st.caption("FastF1 is an unofficial project and is not associated with Formula 1 companies.")
