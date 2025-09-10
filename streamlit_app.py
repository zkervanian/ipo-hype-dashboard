# streamlit_app.py
import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import altair as alt

# === CONFIG ===
# Replace with your actual API key if required
FINNHUB_API_KEY = "<YOUR_FINNHUB_API_KEY>"

def fetch_upcoming_ipos_finnhub(days=7):
    """
    Fetch upcoming IPOs via Finnhub API (free tier available).
    Default fetches IPOs in the next `days` days.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    future = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/calendar/ipo?"
        f"from={today}&to={future}&token={FINNHUB_API_KEY}"
    )
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Error fetching IPOs: {resp.status_code}")
        return pd.DataFrame()
    data = resp.json().get("ipoCalendar", [])
    return pd.DataFrame(data)

def main():
    st.set_page_config(page_title="IPO Hype Dashboard - Upcoming IPOs", layout="wide")
    st.title("IPO Hype Dashboard — Upcoming IPOs")

    days = st.sidebar.slider("Days ahead to fetch IPOs", 1, 30, 7)

    with st.spinner("Fetching upcoming IPOs..."):
        df = fetch_upcoming_ipos_finnhub(days=days)

    if df.empty:
        st.info("No upcoming IPOs found or API returned no data.")
        return

    # Display IPO table
    st.subheader(f"Upcoming IPOs (Next {days} days)")
    # Show key columns; adjust as needed
    display_cols = ["symbol", "name", "date", "exchange"]
    for col in display_cols:
        if col not in df.columns:
            df[col] = ""
    st.dataframe(df[display_cols])

    # Simple timeline chart — IPO count per day
    df["date"] = pd.to_datetime(df["date"])
    timeline = (
        df.groupby(df["date"].dt.date).size()
        .reset_index(name="count")
        .rename(columns={"date": "IPO Date"})
    )

    chart = alt.Chart(timeline).mark_bar().encode(
        x=alt.X("IPO Date:T"),
        y=alt.Y("count:Q", title="Number of IPOs"),
        tooltip=["IPO Date", "count"]
    )
    st.altair_chart(chart, use_container_width=True)

    # Auto-refresh every minute
    st.sidebar.write("This page auto-refreshes every 60 seconds.")
    time.sleep(60)
    st.experimental_rerun()

if __name__ == "__main__":
    main()
