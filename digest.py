import anthropic
import smtplib
import os
import re
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASS"]
TO_EMAIL          = os.environ.get("TO_EMAIL", GMAIL_USER)

# Watchlist — customise these tickers as you like
WATCHLIST = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "AMZN", "META", "BRK-B", "VTI", "GOOGL"]

# ── Step 1: Fetch real stock data via yfinance ────────────────────────────────
def fetch_stock_data() -> dict:
    import yfinance as yf
    result = {}
    for ticker in WATCHLIST:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist.empty:
                continue
            latest     = hist["Close"].iloc[-1]
            prev       = hist["Close"].iloc[-2] if len(hist) >= 2 else latest
            week_start = hist["Close"].iloc[0]
            result[ticker] = {
                "price":       round(latest, 2),
                "day_change":  round(((latest - prev) / prev) * 100, 2),
                "week_change": round(((latest - week_start) / week_start) * 100, 2),
            }
        except Exception as e:
            print(f"Warning: could not fetch {ticker}: {e}")
    return result


# ── Step 2: Fetch news digest via Claude with web search ─────────────────────
def fetch_news_digest() -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today  = datetime.now().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today}.

You are a sharp, concise morning briefing editor. Using web search, find the most important stories from the LAST 24 HOURS for each section:

**🤖 Artificial Intelligence**
3-4 bullets on the most important AI news (models, companies, policy, research). Each bullet 1-2 sentences with specific facts.

**🌍 Geopolitics**
3-4 bullets on key geopolitical developments (wars, diplomacy, elections, tensions). Each bullet 1-2 sentences with specific facts.

**💰 Finance & Markets**
3-4 bullets on macro finance news (Fed, inflation, economy, crypto, earnings). Each bullet 1-2 sentences with specific facts.

Keep under 350 words total. Be punchy and factual."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(text_parts).strip()


# ── Step 3: Ask Claude to analyse the real stock data ────────────────────────
def fetch_stock_analysis(stock_data: dict) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today  = datetime.now().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today}.

Here is real market data for a watchlist:
{json.dumps(stock_data, indent=2)}

Write a section called **📈 Market Pulse & Watchlist**

Start with 2 bullets:
- Overall market direction based on SPY/QQQ performance
- Biggest mover of the day and why it matters

Then pick 4-5 most interesting tickers and for each write one line:
TICKER ($price, day: X%, week: X%) — Why notable today. Long-term: one sentence thesis.

Frame as research ideas, not financial advice. Under 180 words total.
End with: ⚠️ For informational purposes only, not financial advice."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Step 4: Convert to HTML ───────────────────────────────────────────────────
def to_html(news: str, stocks: str, date_str: str) -> str:
    full  = news + "\n\n" + stocks
    lines = full.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<br>")
        elif line.startswith("**") and line.endswith("**"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            title = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            html_lines.append(f"<h3 style='color:#1a1a2e;margin:20px 0 8px;font-size:16px'>{title}</h3>")
        elif line.startswith("- ") or line.startswith("• "):
            if not in_list:
                html_lines.append("<ul style='padding-left:20px;margin:4px 0'>")
                in_list = True
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:])
            html_lines.append(f"<li style='margin-bottom:6px;line-height:1.6'>{content}</li>")
        elif line.startswith("💡") or line.startswith("⚠️"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            color  = "#f0f4ff" if line.startswith("💡") else "#fff8e1"
            border = "#4f6ef7" if line.startswith("💡") else "#f5a623"
            html_lines.append(f"<p style='background:{color};border-left:4px solid {border};padding:10px 14px;border-radius:4px;margin-top:12px;font-size:13px'>{line}</p>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"<p style='margin:4px 0;line-height:1.6'>{content}</p>")

    if in_list:
        html_lines.append("</ul>")

    body = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;max-width:620px;margin:0 auto;padding:24px;color:#222;background:#fafafa">
  <div style="background:#1a1a2e;color:#fff;padding:18px 24px;border-radius:8px;margin-bottom:24px">
    <h1 style="margin:0;font-size:22px">☀️ Morning Digest</h1>
    <p style="margin:4px 0 0;opacity:0.75;font-size:14px">{date_str}</p>
  </div>
  <div style="background:#fff;padding:20px 24px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
    {body}
  </div>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999;text-align:center">Powered by Claude · Delivered via GitHub Actions</p>
</body>
</html>"""


# ── Step 5: Send email ────────────────────────────────────────────────────────
def send_email(subject: str, html_body: str, plain_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body,  "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print(f"✅ Digest sent to {TO_EMAIL}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    print(f"🔍 Fetching morning digest for {date_str}...")

    print("📊 Fetching real stock data...")
    stock_data = fetch_stock_data()
    print(f"   Got data for: {list(stock_data.keys())}")

    print("📰 Fetching news digest...")
    news = fetch_news_digest()

    print("🧠 Analysing stocks with Claude...")
    stocks = fetch_stock_analysis(stock_data)

    html  = to_html(news, stocks, date_str)
    plain = news + "\n\n" + stocks
    subj  = f"☀️ Morning Digest · {date_str}"

    send_email(subj, html, plain)
