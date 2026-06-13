"""Streamlit dashboard for LeasePulse Taipei."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
DEMAND_REPORT = Path("data/processed/demand_evidence_report.json")


st.set_page_config(
    page_title="LeasePulse Taipei",
    page_icon="🏠",
    layout="wide",
)

st.title("LeasePulse Taipei")
st.caption("Rental pricing intelligence for independent landlords in Greater Taipei")


@st.cache_data(ttl=60)
def fetch_json(path: str):
    response = requests.get(f"{API_BASE}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def load_demand_report() -> dict | None:
    if DEMAND_REPORT.exists():
        import json

        with DEMAND_REPORT.open(encoding="utf-8") as handle:
            return json.load(handle)
    return None


try:
    metrics = fetch_json("/metrics/districts")
    recommendations = fetch_json("/recommendations")
    clusters = fetch_json("/clusters")
except requests.RequestException:
    st.error(
        "Could not reach the API. Start it with `uvicorn api.main:app --reload` "
        "or run `./scripts/run_local.sh`."
    )
    st.stop()

metrics_df = pd.DataFrame(metrics)
recs_df = pd.DataFrame(recommendations)
clusters_df = pd.DataFrame(clusters)

col1, col2, col3, col4 = st.columns(4)
col1.metric("District segments tracked", metrics_df["district"].nunique())
col2.metric("Median sample size", int(metrics_df["sample_size"].median()))
col3.metric(
    "Avg confidence",
    f"{recs_df['confidence_score'].mean():.0%}" if not recs_df.empty else "N/A",
)
col4.metric("HW2 K-Means segments", len(clusters_df))

st.subheader("District rent bands (NTD per ping)")
if not metrics_df.empty:
    fig = px.bar(
        metrics_df,
        x="district",
        y="median_rent_per_ping",
        color="building_type",
        barmode="group",
        labels={"median_rent_per_ping": "Median rent / ping (NTD)"},
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Market segments (HW2 MapReduce K-Means)")
if not clusters_df.empty:
    st.dataframe(clusters_df, use_container_width=True)
    seg_fig = px.scatter(
        clusters_df,
        x="centroid_area_ping",
        y="centroid_rent_per_ping",
        size="sample_size",
        color="segment_label",
        labels={
            "centroid_area_ping": "Avg area (ping)",
            "centroid_rent_per_ping": "Avg rent / ping (NTD)",
        },
    )
    st.plotly_chart(seg_fig, use_container_width=True)
else:
    st.info("Run `python -m pipeline.processor` to build K-Means segments.")

st.subheader("Interactive rent quote")
with st.form("quote_form"):
    district = st.selectbox("District", sorted(metrics_df["district"].unique()))
    building_type = st.selectbox(
        "Building type",
        sorted(metrics_df["building_type"].unique()),
    )
    area_ping = st.number_input("Area (ping)", min_value=3.0, max_value=30.0, value=10.0)
    submitted = st.form_submit_button("Get recommendation")

if submitted:
    quote = fetch_json(
        f"/quote?district={district}&building_type={building_type}&area_ping={area_ping}"
    )
    st.success(
        f"Recommended monthly rent: **{quote['recommended_rent_low']:,} – "
        f"{quote['recommended_rent_high']:,} TWD** "
        f"(midpoint {quote['recommended_rent_mid']:,} TWD, "
        f"confidence {quote['confidence_score']:.0%})"
    )

st.subheader("Demand validation snapshot")
demand = load_demand_report()
if demand:
    left, right = st.columns(2)
    left.write("Survey highlights")
    left.json(demand["survey_summary"])
    right.write("Competitor benchmark")
    right.json(demand["competitor_summary"])
else:
    st.info("Run `python scripts/collect_demand_evidence.py` to generate demand evidence.")

st.subheader("Business model")
st.markdown(
    """
    - **Customer:** Independent landlords managing 2–15 units in Greater Taipei
    - **Free tier:** District snapshot dashboard
    - **Pro tier (NT$499/mo):** Custom quotes, vacancy-risk alerts, CSV export
    - **API tier (NT$999/mo):** Programmatic access for small property managers
    """
)
