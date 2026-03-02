import anthropic
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Config (loaded from environment variables) ──────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]        # your.email@gmail.com
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASS"]    # 16-char Gmail App Password
TO_EMAIL          = os.environ.get("TO_EMAIL", GMAIL_USER)  # defaults to sender

TOPICS = [
    "latest AI and artificial intelligence news today",
    "geopolitics and international relations news today",
    "global finance and markets news today",
]

# ── Step 1: Fetch & summarise news using Claude with web search ─────────────
def fetch_digest() -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today}.

You are a sharp, concise morning briefing editor. Using web search, find the 3-4 most important stories from the LAST 24 HOURS for each of these topics:
1. Artificial Intelligence (models, companies, policy, research)
2. Geopolitics (wars, diplomacy, elections, international tensions)
3. Finance & Markets (stocks, crypto, macro economy, central banks)

For each topic, write:
- A bold topic header
- 3-4 bullet points, each 1-2 sentences max
- Each bullet must be a real, specific story with key facts (numbers, names, countries)

Keep the entire digest under 400 words. Be punchy, factual, no fluff.
End with a one-line "💡 Big Picture" connecting a theme across the three areas if one exists."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from response (may include tool_use blocks)
    text_parts = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(text_parts).strip()


# ── Step 2: Convert plain text digest to clean HTML email ───────────────────
def to_html(digest: str, date_str: str) -> str:
    # Convert markdown-style bold (**text**) and bullets to HTML
    lines = digest.split("\n")
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
        elif line.startswith("**") and line.endswith("**"):
            html_lines.append(f"<h3 style='color:#1a1a2e;margin:18px 0 6px'>{line[2:-2]}</h3>")
        elif line.startswith("- ") or line.startswith("• "):
            content = line[2:]
            # Bold any **text** inside bullet
            import re
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            html_lines.append(f"<li style='margin-bottom:6px'>{content}</li>")
        elif line.startswith("💡"):
            html_lines.append(f"<p style='background:#f0f4ff;border-left:4px solid #4f6ef7;padding:10px 14px;border-radius:4px;margin-top:18px'>{line}</p>")
        else:
            import re
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"<p style='margin:4px 0'>{line}</p>")

    body = "\n".join(html_lines)

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;max-width:620px;margin:0 auto;padding:24px;color:#222">
  <div style="background:#1a1a2e;color:#fff;padding:18px 24px;border-radius:8px;margin-bottom:24px">
    <h1 style="margin:0;font-size:22px">☀️ Morning Digest</h1>
    <p style="margin:4px 0 0;opacity:0.75;font-size:14px">{date_str}</p>
  </div>
  <ul style="padding-left:20px;line-height:1.7">
  {body}
  </ul>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999;text-align:center">Powered by Claude · Delivered via GitHub Actions</p>
</body>
</html>
"""


# ── Step 3: Send email via Gmail SMTP ───────────────────────────────────────
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


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    print(f"🔍 Fetching morning digest for {date_str}...")

    digest = fetch_digest()
    print("📰 Digest ready:\n", digest[:300], "...\n")

    html  = to_html(digest, date_str)
    subj  = f"☀️ Morning Digest · {date_str}"

    send_email(subj, html, digest)
