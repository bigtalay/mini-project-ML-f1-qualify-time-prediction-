"""Optional legacy Streamlit view, using the same verified engine as the new web app."""
import streamlit as st
import pandas as pd

from intelligence.data import Dataset, PRACTICE
from intelligence.tyre_model import ensure_artifacts, scenario, build_features, row_sessions, KINDS

st.set_page_config(page_title="Weekend Intelligence / Legacy", layout="wide")
st.title("Weekend Intelligence — Legacy view")
st.caption("เว็บหลัก: http://localhost:8501 · โมเดลเวลา+ยาง · ประเมินย้อนหลังปี 2023 (เคยใช้วิเคราะห์แล้ว)")

@st.cache_resource
def load():
    dataset = Dataset()
    return dataset, ensure_artifacts(dataset)

data, bundle = load()
events = data.events.loc[data.events.year.eq(2023)]
event_id = st.selectbox("รายการแข่ง", events.event_id, format_func=lambda x: data.event(x)["name"])
features = build_features(data)
rows = features.loc[features.event_id.eq(event_id)]
driver = st.selectbox("นักขับ", rows.Driver)
row = rows.loc[rows.Driver.eq(driver)].iloc[0]
overrides = {}
tyres = row_sessions(row)
for column in PRACTICE:
    if pd.notna(row[column]):
        overrides[column] = st.number_input(column, min_value=.001, value=float(row[column]), step=.001, format="%.3f", key=f"{event_id}-{driver}-{column}")
        session = column.removesuffix("_Time")
        values = tyres[session]
        compound = values["compound"] if values["compound"] in KINDS else "UNKNOWN"
        values["compound"] = st.selectbox(f"{session} Compound", KINDS, index=KINDS.index(compound), key=f"{event_id}-{driver}-{session}-compound")
        values["tyre_life"] = st.number_input(f"{session} TyreLife (เว้นว่าง = training median)", min_value=0.0, value=values["tyre_life"], key=f"{event_id}-{driver}-{session}-age")
        values["time"] = overrides[column]
if st.button("ทดลอง scenario"):
    try:
        result = scenario(data, bundle, event_id, driver, overrides, {s: v for s, v in tyres.items() if v is not None})
        st.metric("เวลาที่ทำนาย (วินาที)", f"{result['prediction']:.3f}", f"{result['delta']:+.3f}")
        st.write(result)
    except ValueError as error:
        st.warning(str(error))
st.subheader("Retrospective evaluation / 2023")
st.dataframe(pd.DataFrame(bundle["report"]["test"]), hide_index=True)
st.caption("โมเดลถูกเลือกด้วย validation ปี 2022 ผล test อาจด้อยกว่า baseline; what-if ไม่ใช่ข้อสรุปเชิงสาเหตุ")
