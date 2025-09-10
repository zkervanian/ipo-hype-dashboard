# streamlit_ipo_hype_dashboard.py
# Streamlit dashboard for IPO Hype Scores
# Reads sqlite DB 'ipo_hype.db' (created by the prototype). If missing, the app will create a demo DB with sample data.

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import altair as alt
import math

DB_PATH = "ipo_hype.db"

# -------------------- DB utilities --------------------

def get_conn(path=DB_PATH):
    return sqlite3.connect(path, check_same_thread=False)


def ensure_demo_db(conn):
    """Creates schema and inserts demo data if tables are missing or empty."""
    c = conn.cursor()
    # Create tables if not exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, ticker TEXT, expected_date TEXT, created_at TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS social_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, author_id TEXT, author_followers INTEGER,
        text TEXT, created_at TEXT, ipo_id INTEGER, likes INTEGER, shares INTEGER, comments INTEGER,
        sentiment REAL, bot_score REAL
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS hype_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ipo_id INTEGER, window_start TEXT, window_end TEXT,
        volume INTEGER, avg_sentiment REAL, influencer_score REAL, engagement_score REAL,
        bot_penalty REAL, hype_score REAL, created_at TEXT
    )""")
    conn.commit()

    # If no IPOs, insert demo IPO and posts
    ipos_df = pd.read_sql_query("SELECT * FROM ipos LIMIT 1", conn)
    if ipos_df.empty:
        now = datetime.utcnow()
        c.execute("INSERT INTO ipos(company, ticker, expected_date, created_at) VALUES (?,?,?,?)",
                  ("Acme Robotics", "ACMR", (now + timedelta(days=7)).date().isoformat(), now.isoformat()))
        ipo_id = c.lastrowid

        # create synthetic hype score rows
        import random
        for h in range(48):
            window_end = now - timedelta(hours=47-h)
            window_start = window_end - timedelta(hours=1)
            volume = random.randint(2,40)
            avg_sentiment = random.uniform(-0.3, 0.9)
            influencer_score = random.uniform(1, 60)
            engagement_score = random.uniform(0.1, 10)
            bot_penalty = random.uniform(0.0, 0.6)
            hype_score = max(0.0, min(1.0, 0.3*min(1, math.log1p(volume)/5.0) + 0.2*(influencer_score/50.0) + 0.2*(engagement_score/10.0) + 0.15*max(0,avg_sentiment) - 0.25*bot_penalty))
            c.execute("""
            INSERT INTO hype_scores(ipo_id, window_start, window_end, volume, avg_sentiment, influencer_score, engagement_score, bot_penalty, hype_score, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (ipo_id, window_start.isoformat(), window_end.isoformat(), volume, avg_sentiment, influencer_score, engagement_score, bot_penalty, hype_score, window_end.isoformat()))

        conn.commit()


# -------------------- Simple analysis utilities --------------------

def zscore_normalization(series):
    if series.std() == 0:
        return pd.Series([50.0]*len(series), index=series.index)
    z = (series - series.mean()) / series.std()
    scaled = 50 + 10*z  # center at 50, scale by std dev
    return scaled.clip(0,100)


# -------------------- Data loading --------------------

def load_ipos(conn):
    return pd.read_sql_query("SELECT * FROM ipos ORDER BY created_at DESC", conn)


def load_hype_scores(conn, ipo_id=None, since_days=7):
    q = "SELECT * FROM hype_scores"
    params = []
    if ipo_id is not None:
        q += " WHERE ipo_id = ?"
        params.append(ipo_id)
    q += " ORDER BY window_end ASC"
    df = pd.read_sql_query(q, conn, params=params)
    if not df.empty:
        df['window_end'] = pd.to_datetime(df['window_end'])
        df['window_start'] = pd.to_datetime(df['window_start'])
    return df


# -------------------- Streamlit UI --------------------

def main():
    st.set_page_config(page_title="IPO Hype Dashboard", layout="wide")
    st.title("IPO Hype Dashboard")

    conn = get_conn()
    ensure_demo_db(conn)

    # Sidebar controls
    st.sidebar.header("Filters")
    ipos_df = load_ipos(conn)
    ipo_map = {f"{r['company']} ({r['ticker']})": int(r['id']) for _, r in ipos_df.iterrows()} if not ipos_df.empty else {}
    ipo_choice = st.sidebar.selectbox("Select IPO", options=["All"] + list(ipo_map.keys()))
    date_range_days = st.sidebar.slider("Show last N days", min_value=1, max_value=30, value=7)

    # Main layout
    st.subheader("Hype Score Timeline (0-100, z-score normalized)")
    if ipo_choice == "All":
        hs_df = load_hype_scores(conn)
    else:
        hs_df = load_hype_scores(conn, ipo_id=ipo_map[ipo_choice])

    if hs_df.empty:
        st.info("No hype scores found.")
    else:
        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=date_range_days)
        hs_df = hs_df[hs_df['window_end'] >= cutoff]

        if hs_df.empty:
            st.info("No data in selected date range.")
        else:
            # Convert hype_score (0-1) to 0-100, then normalize with z-score baseline
            hs_df['hype_raw'] = hs_df['hype_score'] * 100
            hs_df['hype_norm'] = zscore_normalization(hs_df['hype_raw'])

            if ipo_choice == "All":
                chart_df = hs_df.groupby('window_end').hype_norm.mean().reset_index()
                chart_df.rename(columns={'hype_norm': 'HypeScore'}, inplace=True)
            else:
                chart_df = hs_df[['window_end','hype_norm']].rename(columns={'hype_norm':'HypeScore'})

            line = alt.Chart(chart_df).mark_line(point=True).encode(
                x=alt.X('window_end:T', title='Time'),
                y=alt.Y('HypeScore:Q', title='Hype Score (0-100, z-score)'),
                tooltip=[alt.Tooltip('window_end:T', title='Time'), alt.Tooltip('HypeScore:Q', title='Score')]
            ).interactive()

            st.altair_chart(line, use_container_width=True)

            # Latest metrics
            latest = hs_df.sort_values('window_end').iloc[-1]
            col_a, col_b = st.columns(2)
            col_a.metric("Latest Raw Hype", f"{latest['hype_raw']:.1f}")
            col_b.metric("Normalized Hype", f"{latest['hype_norm']:.1f}")

    conn.close()


if __name__ == '__main__':
    main()
