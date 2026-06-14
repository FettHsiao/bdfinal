"""Streamlit dashboard for LeasePulse Taipei."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    query = (
        f"district={quote(str(district))}"
        f"&building_type={quote(str(building_type))}"
        f"&area_ping={area_ping}"
    )
    quote = fetch_json(f"/quote?{query}")

    st.success(
        f"Recommended monthly rent band: **{quote['recommended_rent_low']:,} – "
        f"{quote['recommended_rent_high']:,} TWD**"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Conservative (P25)", f"{quote['recommended_rent_low']:,} TWD")
    c2.metric("Market median", f"{quote['recommended_rent_mid']:,} TWD")
    c3.metric("Aggressive (P75)", f"{quote['recommended_rent_high']:,} TWD")
    c4.metric("Confidence", f"{quote['confidence_score']:.0%}")

    left, right = st.columns([1.1, 1])
    with left:
        band_df = pd.DataFrame(
            [
                {
                    "Strategy": "Conservative (P25)",
                    "Monthly rent (TWD)": f"{quote['recommended_rent_low']:,}",
                    "Rent / ping (TWD)": f"{quote['rent_per_ping_low']:,.0f}",
                    "Annual rent (TWD)": f"{quote['annual_rent_estimate']['low_ntd']:,}",
                },
                {
                    "Strategy": "Market median",
                    "Monthly rent (TWD)": f"{quote['recommended_rent_mid']:,}",
                    "Rent / ping (TWD)": f"{quote['rent_per_ping_mid']:,.0f}",
                    "Annual rent (TWD)": f"{quote['annual_rent_estimate']['mid_ntd']:,}",
                },
                {
                    "Strategy": "Aggressive (P75)",
                    "Monthly rent (TWD)": f"{quote['recommended_rent_high']:,}",
                    "Rent / ping (TWD)": f"{quote['rent_per_ping_high']:,.0f}",
                    "Annual rent (TWD)": f"{quote['annual_rent_estimate']['high_ntd']:,}",
                },
            ]
        )
        st.markdown("**Pricing breakdown**")
        st.dataframe(band_df, use_container_width=True, hide_index=True)

        guidance = quote["pricing_guidance"]
        st.markdown("**How to read this quote**")
        for key in ("conservative", "market", "aggressive"):
            item = guidance[key]
            st.markdown(
                f"- **{item['label']}**: {item['monthly_rent_ntd']:,} TWD "
                f"({item['rent_per_ping_ntd']:,.0f} TWD/ping) — {item['note']}"
            )

    with right:
        fig = go.Figure(
            go.Bar(
                x=["P25", "Median", "P75"],
                y=[
                    quote["recommended_rent_low"],
                    quote["recommended_rent_mid"],
                    quote["recommended_rent_high"],
                ],
                marker_color=["#93c5fd", "#1f4e79", "#fca5a5"],
                text=[
                    f"{quote['recommended_rent_low']:,}",
                    f"{quote['recommended_rent_mid']:,}",
                    f"{quote['recommended_rent_high']:,}",
                ],
                textposition="outside",
            )
        )
        fig.update_layout(
            title=f"Monthly rent band — {quote['district']} / {area_ping} ping",
            yaxis_title="Monthly rent (TWD)",
            height=360,
            margin=dict(t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    meta1, meta2, meta3 = st.columns(3)
    meta1.info(f"Comparable sample size: **{quote['sample_size']}** transactions")
    meta2.info(
        "District median (all sizes): "
        f"**{int(quote['district_median_rent_ntd']):,} TWD/month**"
    )
    meta3.info(f"Data updated: **{quote['updated_at'][:10]}**")

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
