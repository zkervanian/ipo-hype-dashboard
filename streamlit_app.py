# ipo_hype_mvp.py
# Run: python ipo_hype_mvp.py
import sqlite3
import time
import math
from datetime import datetime, timedelta
import requests
from collections import defaultdict
import random

# ---------- Config ----------
WINDOW_MINUTES = 60
DB = "ipo_hype.db"

# ---------- Utilities ----------
def ensure_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, ticker TEXT, expected_date TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS social_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, author_id TEXT, author_followers INTEGER,
        text TEXT, created_at TEXT, ipo_id INTEGER, likes INTEGER, shares INTEGER, comments INTEGER,
        sentiment REAL, bot_score REAL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS hype_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ipo_id INTEGER, window_start TEXT, window_end TEXT,
        volume INTEGER, avg_sentiment REAL, influencer_score REAL, engagement_score REAL,
        bot_penalty REAL, hype_score REAL, created_at TEXT
    )""")
    conn.commit()
    conn.close()

# ---------- Simple sentiment (placeholder) ----------
def simple_sentiment(text):
    # placeholder: rudimentary sentiment by counting words. Replace with model (VADER or transformer)
    pos = sum(1 for w in text.lower().split() if w in ("good","great","awesome","up","bull","love","moon"))
    neg = sum(1 for w in text.lower().split() if w in ("bad","terrible","down","sell","scam","bear"))
    score = (pos - neg) / max(1, pos + neg)
    return score

# ---------- Bot score (placeholder) ----------
def simple_bot_score(author_followers, account_age_days=365, posts_per_day=1):
    score = 0.0
    if author_followers < 50: score += 0.4
    if posts_per_day > 50: score += 0.4
    if account_age_days < 30: score += 0.2
    return min(1.0, score)

# ---------- Ingestion (MVP: generate synthetic social posts) ----------
def ingest_dummy_posts(ipo):
    # Replace with API calls: X, Reddit, StockTwits, etc.
    texts = [
        f"{ipo['ticker']} looks great, I'm bullish!",
        f"Heard {ipo['company']} IPO next week. pump?",
        f"Stay away from {ipo['ticker']} scam.",
        f"{ipo['company']} S-1 filed. news article: ...",
    ]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for i in range(random.randint(10,40)):
        text = random.choice(texts)
        followers = random.choice([10,50,200,5000,20000])
        sent = simple_sentiment(text)
        bot = simple_bot_score(followers, account_age_days=random.choice([10,100,500]), posts_per_day=random.choice([1,5,100]))
        likes = random.randint(0,500)
        shares = random.randint(0,200)
        comments = random.randint(0,100)
        created_at = datetime.utcnow().isoformat()
        c.execute("""INSERT INTO social_posts(platform, author_id, author_followers, text, created_at, ipo_id, likes, shares, comments, sentiment, bot_score)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  ("dummy", f"user_{random.randint(1,10000)}", followers, text, created_at, ipo['id'], likes, shares, comments, sent, bot))
    conn.commit()
    conn.close()

# ---------- Hype calculation ----------
def compute_hype_for_ipo(ipo_id, window_minutes=WINDOW_MINUTES):
    now = datetime.utcnow()
    start = now - timedelta(minutes=window_minutes)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT likes, shares, comments, author_followers, sentiment, bot_score FROM social_posts WHERE ipo_id=? AND created_at >= ?", (ipo_id, start.isoformat()))
    rows = c.fetchall()
    if not rows:
        conn.close()
        return None
    volume = len(rows)
    total_engagement = sum((r[0] + r[1] + r[2]) for r in rows)
    avg_sentiment = sum(r[4] for r in rows) / volume
    influencer_score = sum(math.sqrt(max(1,r[3])) for r in rows) / volume
    engagement_score = (math.log1p(total_engagement) / (1 + math.log1p(volume)))
    bot_penalty = sum(r[5] for r in rows) / volume

    # Normalize simple heuristics (quick min-max-ish scaling)
    norm_volume = min(1.0, math.log1p(volume)/5.0)  # adjust denominator by historical baseline
    norm_influencer = min(1.0, influencer_score/50.0)
    norm_engagement = min(1.0, engagement_score/10.0)
    positive_sentiment = max(0, avg_sentiment)
    news_signal = 0.0  # placeholder

    # weights (tune later)
    w1,w2,w3,w4,w5,w6 = 0.30,0.20,0.20,0.15,0.10,0.25
    raw = (w1*norm_volume + w2*norm_influencer + w3*norm_engagement + w4*positive_sentiment + w5*news_signal - w6*bot_penalty)
    hype = max(0.0, min(1.0, raw))
    nowstr = now.isoformat()
    c.execute("""INSERT INTO hype_scores(ipo_id, window_start, window_end, volume, avg_sentiment, influencer_score, engagement_score, bot_penalty, hype_score, created_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (ipo_id, start.isoformat(), now.isoformat(), volume, avg_sentiment, influencer_score, engagement_score, bot_penalty, hype, nowstr))
    conn.commit()
    conn.close()
    return hype

# ---------- Demo driver ----------
def demo_run():
    ensure_db()
    # create a demo IPO
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO ipos(company, ticker, expected_date, created_at) VALUES (?,?,?,?)",
              ("Acme Robotics", "ACMR", (datetime.utcnow()+timedelta(days=7)).date().isoformat(), datetime.utcnow().isoformat()))
    ipo_id = c.lastrowid
    conn.commit()
    conn.close()
    ipo = {'id': ipo_id, 'company': 'Acme Robotics', 'ticker': 'ACMR'}
    # ingest dummy posts
    ingest_dummy_posts(ipo)
    hype = compute_hype_for_ipo(ipo_id)
    print(f"IPO {ipo['ticker']} Hype Score (0-1): {hype}")

if __name__ == "__main__":
    demo_run()
