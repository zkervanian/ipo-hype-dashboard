# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

st.set_page_config(page_title="IPO Hype Dashboard", layout="wide")
st.title("🚀 IPO Hype Dashboard (Demo)")

# --- Generate simple fake data ---
np.random.seed(42)
dates = pd.date_range(datetime.now() - timedelta(days=7), periods=50, freq="4H")
data = pd.DataFrame({
    "time": dates,
    "ipo": np.random.choice(["Acme Robotics (ACMR)", "FinTechNow (FTNW)", "BioFuture (BIOF)"], size=len(dates)),
    "hype_score": np.clip(np.random.normal(loc=50, scale=15, size=len(dates)), 0, 100)
})

# --- Sidebar ---
ipo_choice = st.sidebar.selectbox("Select IPO", ["All"] + sorted(data["ipo"].unique()))

if ipo_choice != "All":
    df_plot = data[data["ipo"] == ipo_choice]
else:
    df_plot = data.groupby("time")["hype_score"].mean().reset_index()
    df_plot["ipo"] = "All"

# --- Chart ---
chart = alt.Chart(df_plot).mark_line(point=True).encode(
    x="time:T",
    y=alt.Y("hype_score:Q", title="Hype Score (0–100)"),
    color="ipo:N",
    tooltip=["time:T", "ipo:N", "hype_score:Q"]
).interactive()

st.altair_chart(chart, use_container_width=True)

# --- Latest metric ---
latest = df_plot.sort_values("time").iloc[-1]
st.metric("Latest Hype Score", f"{latest['hype_score']:.1f}")

