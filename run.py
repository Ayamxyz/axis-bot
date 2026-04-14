"""
AXIS — Ayam Samuel's Personal Brand System
Version 3.0 — Clean

7 Slack channels + Email + Google Sheets + Notion
"""

import os
import re
import time
import smtplib
import requests
import anthropic
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from notion_sync import (
    get_client,
    build_notion_briefing,
    build_cert_nudge,
    sync_opportunities,
    sync_content,
    sync_scholarships,
    sync_leadership,
    sync_followup_tasks
)

load_dotenv()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
KEY                    = os.getenv("ANTHROPIC_API_KEY")
BRIEFING_WEBHOOK       = os.getenv("BRIEFING_WEBHOOK")
JOBS_WEBHOOK           = os.getenv("JOBS_WEBHOOK")
CONTENT_WEBHOOK        = os.getenv("CONTENT_WEBHOOK")
FOLLOWUPS_WEBHOOK      = os.getenv("FOLLOWUPS_WEBHOOK")
SCHOLARSHIPS_WEBHOOK   = os.getenv("SCHOLARSHIPS_WEBHOOK")
LEADERSHIP_WEBHOOK     = os.getenv("LEADERSHIP_WEBHOOK")
CERTIFICATIONS_WEBHOOK = os.getenv("CERTIFICATIONS_WEBHOOK")
GMAIL_ADDRESS          = os.getenv("GMAIL_ADDRESS")
GMAIL_PASSWORD         = os.getenv("GMAIL_APP_PASSWORD")
SERVICE_ACCOUNT        = os.getenv("GOOGLE_SERVICE_ACCOUNT")
SHEET_ID               = os.getenv("GOOGLE_SHEET_ID")
NOTION_TOKEN           = os.getenv("NOTION_TOKEN")

# Nigeria time — WAT is UTC+1
WAT      = timezone(timedelta(hours=1))
_now_wat = datetime.now(WAT)

client = anthropic.Anthropic(api_key=KEY)
today  = _now_wat.strftime("%A, %d %B %Y")
now    = _now_wat.strftime("%Y-%m-%d %H:%M")
day    = _now_wat.strftime("%A")


# ─────────────────────────────────────────
# WRITING RULES — injected into every prompt
# ─────────────────────────────────────────
WRITING_RULES = """
WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown symbols.
- No divider lines of any kind. No ---, no ***, no ===, no long hyphens.
- No bold or italic markers. No > blockquote symbols.
- Do not begin with preamble such as "Here are", "Let me", "Certainly", or "I have found".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.
- Use short, clean sentences. British spelling throughout.

"""


# ─────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────
def clean_slack_output(text):
    """Strip all AI formatting artifacts from Slack output"""
    if not text:
        return text
    # Remove double asterisks **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # Remove single asterisks *text*
    text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
    # Remove remaining lone asterisks
    text = re.sub(r'(?<!\w)\*(?!\w)', '', text)
    # Remove long divider lines
    text = re.sub(r'[━─═\-]{4,}', '', text)
    # Remove markdown --- separators
    text = re.sub(r'(?m)^---+$', '', text)
    # Remove > blockquote markers
    text = re.sub(r'(?m)^>\s*', '', text)
    # Remove em dashes
    text = text.replace('—', '-').replace('–', '-')
    # Clean trailing spaces per line
    text = re.sub(r' +\n', '\n', text)
    # Max two consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def send_slack(webhook, text):
    if not webhook:
        print("  ⚠️  No webhook — skipping")
        return
    if not text or not text.strip():
        print("  ⚠️  Empty content — skipping")
        return
    text   = clean_slack_output(text)
    chunks = [text[i:i+2900] for i in range(0, len(text), 2900)]
    for chunk in chunks:
        r = requests.post(webhook, json={"text": chunk})
        status = "✅" if r.status_code == 200 else "❌"
        print(f"  {status} Slack sent ({len(chunk)} chars)")
        time.sleep(1)


def ask(prompt, label=""):
    print(f"  🤖 Generating {label}...")
    try:
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in r.content if hasattr(b, "text"))
        print(f"  ✅ Generated ({len(text)} chars)")
        return text.strip()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return ""


def ask_with_search(prompt, label=""):
    """Ask Claude with web search — gets real-time data"""
    print(f"  🌐 Generating {label} (with web search)...")
    try:
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(
            b.text for b in r.content
            if hasattr(b, "text") and b.type == "text"
        )
        searches = sum(1 for b in r.content
                       if hasattr(b, "type") and b.type == "tool_use")
        if searches:
            print(f"  🔍 {searches} web search(es) performed")
        if len(text.strip()) < 100:
            print("  ⚠️  Output too short — falling back to standard")
            return ask(prompt, label)
        print(f"  ✅ Generated ({len(text)} chars)")
        return text.strip()
    except Exception as e:
        print(f"  ❌ Web search failed: {e} — falling back")
        return ask(prompt, label)


def pause(seconds=90):
    print(f"  ⏳ Pausing {seconds}s...")
    time.sleep(seconds)


# ─────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────
def send_email(subject, html_body, plain_body=""):
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        print("  ⚠️  Gmail not configured — skipping")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"AXIS — Ayam Samuel <{GMAIL_ADDRESS}>"
        msg["To"]      = GMAIL_ADDRESS.replace("@", "+axis@")
        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS,
                            GMAIL_ADDRESS.replace("@", "+axis@"),
                            msg.as_string())
        print(f"  ✅ Email sent: {subject}")
    except Exception as e:
        print(f"  ❌ Email failed: {e}")


SECTION_META = {
    "NEWS BRIEFING":         {"icon": "🚀", "label": "Daily Intelligence"},
    "OPPORTUNITIES (1-10)":  {"icon": "🎯", "label": "Live Opportunities"},
    "OPPORTUNITIES (11-20)": {"icon": "🎯", "label": "More Opportunities"},
    "PLATFORM CONTENT":      {"icon": "📣", "label": "Content Drafts"},
    "OUTREACH TARGETS":      {"icon": "📨", "label": "Outreach Targets"},
    "FOLLOW-UP REMINDERS":   {"icon": "⏰", "label": "Follow Ups"},
    "SCHOLARSHIPS":          {"icon": "🎓", "label": "Scholarships"},
    "LEADERSHIP":            {"icon": "🌍", "label": "Leadership"},
    "CERTIFICATIONS":        {"icon": "📜", "label": "Certifications"},
}


def clean_for_email(text):
    """Strip all AI formatting, convert to clean HTML"""
    if not text:
        return ""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
    text = re.sub(r'_([^_\n]+)_', r'\1', text)
    text = re.sub(r'[━─═]{3,}', '', text)
    text = re.sub(r'(?m)^---+$', '', text)
    text = re.sub(r'(?m)^>\s*', '', text)
    text = text.replace('—', '-').replace('–', '-')
    text = re.sub(
        r'(https?://[^\s<>"]+)',
        r'<a href="\1" style="color:#555;text-decoration:underline;word-break:break-all;">\1</a>',
        text
    )
    text = text.replace('\n', '<br>')
    text = re.sub(r'(<br>){3,}', '<br><br>', text)
    return text.strip()


def build_section_card(label, content_text):
    meta    = SECTION_META.get(label, {"icon": "📌", "label": label})
    cleaned = clean_for_email(content_text)
    return f"""
    <div style="margin-bottom:32px;padding-bottom:32px;border-bottom:1px solid #e8e4de;">
      <p style="margin:0 0 10px;font-family:Arial,sans-serif;font-size:10px;
                 font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:#888888;">
        {meta['icon']}&nbsp;&nbsp;{meta['label']}
      </p>
      <div style="font-family:Georgia,serif;font-size:14px;line-height:1.8;color:#1a1a1a;">
        {cleaned}
      </div>
    </div>"""


def build_html_email(sections, labels):
    cards = ""
    for label, content_text in zip(labels, sections):
        if content_text and content_text.strip():
            cards += build_section_card(label, content_text)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AXIS — {today}</title>
</head>
<body style="margin:0;padding:0;background:#f0ece4;font-family:Georgia,serif;">

  <div style="max-width:600px;margin:40px auto;background:#ffffff;border-radius:4px;overflow:hidden;">

    <!-- Header -->
    <div style="background:#111111;padding:40px 48px 36px;">
      <p style="margin:0 0 6px;font-family:Arial,sans-serif;font-size:10px;
                 font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#777777;">
        Personal Brand System
      </p>
      <h1 style="margin:0 0 6px;font-family:Arial,sans-serif;font-size:30px;
                  font-weight:700;color:#ffffff;letter-spacing:-0.5px;">
        AXIS
      </h1>
      <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#777777;">
        {today}
      </p>
    </div>

    <!-- Body -->
    <div style="padding:40px 48px 12px;">
      {cards}
    </div>

    <!-- Checklist -->
    <div style="margin:0 48px 32px;padding:22px 26px;background:#f7f4f0;border-radius:4px;">
      <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:10px;
                 font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#888888;">
        Morning Actions
      </p>
      <p style="margin:0 0 7px;font-family:Arial,sans-serif;font-size:13px;color:#333333;line-height:1.6;">
        &#9744;&nbsp;&nbsp;Check Notion Task Manager for today
      </p>
      <p style="margin:0 0 7px;font-family:Arial,sans-serif;font-size:13px;color:#333333;line-height:1.6;">
        &#9744;&nbsp;&nbsp;Apply to 3 opportunities before noon
      </p>
      <p style="margin:0 0 7px;font-family:Arial,sans-serif;font-size:13px;color:#333333;line-height:1.6;">
        &#9744;&nbsp;&nbsp;Send 5 outreach messages
      </p>
      <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#333333;line-height:1.6;">
        &#9744;&nbsp;&nbsp;Post on 2 platforms
      </p>
    </div>

    <!-- Links -->
    <div style="padding:0 48px 32px;">
      <a href="https://ayamtek.xyz"
         style="font-family:Arial,sans-serif;font-size:12px;font-weight:700;
                color:#111111;text-decoration:none;border-bottom:1.5px solid #111111;
                padding-bottom:1px;margin-right:20px;">
        ayamtek.xyz
      </a>
      <a href="https://znap.link/ayamsamuel"
         style="font-family:Arial,sans-serif;font-size:12px;font-weight:700;
                color:#111111;text-decoration:none;border-bottom:1.5px solid #111111;
                padding-bottom:1px;">
        All Links
      </a>
    </div>

    <!-- Footer -->
    <div style="background:#111111;padding:24px 48px;">
      <p style="margin:0 0 3px;font-family:Arial,sans-serif;font-size:13px;
                 font-weight:700;color:#ffffff;">
        Ayam Samuel
      </p>
      <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:11px;color:#777777;">
        Managing Director, Ayamtek &nbsp;&middot;&nbsp; RN, RM &nbsp;&middot;&nbsp; @ayamsamuelxyz
      </p>
      <p style="margin:0;font-family:Arial,sans-serif;font-size:10px;color:#555555;">
        Generated by AXIS at {now} WAT &nbsp;&middot;&nbsp; ayamtek.xyz
      </p>
    </div>

  </div>

</body>
</html>"""


def send_full_email(sections, labels):
    print("\n📧 Sending email digest...")
    html_body  = build_html_email(sections, labels)
    plain_body = f"AXIS Daily Briefing — {today}\nGenerated: {now}\nOpen in a modern email client to view the full newsletter."
    send_email(f"AXIS Daily Briefing — {today}", html_body, plain_body)


# ─────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────
def get_sheet():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT, scopes=scopes)
        gc    = gspread.authorize(creds)
        return gc.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"  ❌ Sheets failed: {e}")
        return None


def build_sheet_map(sh):
    """Map both plain and icon-prefixed tab names to worksheet objects"""
    ws_map = {}
    for ws in sh.worksheets():
        ws_map[ws.title] = ws
        parts = ws.title.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) <= 2:
            base = parts[1].strip()
            if base not in ws_map:
                ws_map[base] = ws
    return ws_map


_sheet_map_cache = None

def get_sheet_map(sh):
    global _sheet_map_cache
    if _sheet_map_cache is None and sh:
        _sheet_map_cache = build_sheet_map(sh)
    return _sheet_map_cache or {}


def setup_sheets(sh):
    ws_map = get_sheet_map(sh)
    tabs = {
        "Opportunities":  ["Date", "Job Title", "Platform", "Budget", "Status",
                           "Application Sent", "Follow Up Date", "Link", "Notes"],
        "Scholarships":   ["Date", "Programme", "University", "Country", "Funding",
                           "Deadline", "Status", "Link", "Notes"],
        "Leadership":     ["Date", "Programme", "Organisation", "Type", "Cost",
                           "Deadline", "Status", "Link", "Notes"],
        "Certifications": ["Date", "Course", "Platform", "Cost", "Progress",
                           "Target Date", "Completed", "Link", "Notes"],
        "Content Log":    ["Date", "Platform", "Topic", "Posted", "Notes"],
        "Outreach Log":   ["Date", "Business", "Platform", "Message",
                           "Response", "Follow Up Date", "Notes"],
        "Follow Ups":     ["Original Date", "Contact", "Type",
                           "Message", "Due Date", "Status"],
        "Weekly Review":  ["Week", "Jobs Applied", "Content Posted",
                           "Outreach Sent", "Responses", "Projects Won", "Notes"]
    }
    for tab_name, headers in tabs.items():
        if tab_name not in ws_map:
            ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
            ws.append_row(headers)
            print(f"  ✅ Created tab: {tab_name}")


def log_row(sh, tab, row):
    try:
        ws_map = get_sheet_map(sh)
        if tab in ws_map:
            ws_map[tab].append_row(row)
        else:
            print(f"  ⚠️  Tab '{tab}' not found")
    except Exception as e:
        print(f"  ⚠️  Could not log to {tab}: {e}")


# ─────────────────────────────────────────
# SECTION 1 — DAILY NEWS BRIEFING
# ─────────────────────────────────────────
def run_briefing():
    print("\n📰 SECTION 1 — DAILY NEWS BRIEFING")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Write a sharp daily news briefing. One item per category. Be specific and factual.

Ayam is MD of Ayamtek Nigeria — websites, apps, automation, AI integrations. Registered Nurse (RN, RM). Target: MSc Health Data Science at LSHTM.

Cover exactly one development per category:

1. AI TOOLS AND AUTOMATION
Latest release or update from Claude, ChatGPT, Gemini, Make, Zapier or n8n.

2. WEB AND APP DEVELOPMENT
Framework update, no-code news, or major industry shift.

3. DIGITAL BUSINESS AND INTERNATIONAL CLIENTS
What businesses globally are spending on. What digital services are in demand.

4. AFRICAN TECH AND NIGERIA
Funding, startup activity, policy, or visibility news for African builders.

5. FRONTIER AI MODELS
Latest model release or research. Name the model, the lab, what changed.

6. HEALTH TECH AND DIGITAL HEALTH
AI in healthcare, health informatics, digital health policy, or health data science.

7. INFRASTRUCTURE AND CLOUD
Data centre news, cloud update, or major infrastructure deal.

8. NEW TOOL WORTH KNOWING
One specific tool launched this week. Name, what it does, link.

For each item: section number and name, headline in bold, two sentence summary, one sentence on why it matters to Ayam specifically.
Keep under 3000 characters total.""", "news briefing")

    send_slack(BRIEFING_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 2 — OPPORTUNITIES (1-10)
# ─────────────────────────────────────────
def run_opportunities_1(sh):
    print("\n🎯 SECTION 2 — OPPORTUNITIES BATCH 1 (1-10)")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 10 freelance contracts Ayam can apply to right now that match his exact skills.

Ayam's verified skills:
- Websites: WordPress, Webflow, Framer, HTML/CSS, landing pages
- Web apps: custom applications, dashboards, portals
- Automation: Zapier, Make.com, n8n
- AI integration: chatbots, Claude API, OpenAI API, AI-powered tools
- No-code/low-code: Bubble, Airtable, Notion integrations
- UI/UX design: Figma, wireframing, prototyping
- Mobile apps: cross-platform development
- Healthcare tech: clinical systems, health informatics
- IT consulting: digital strategy

Do not include: native iOS/Android only, data science engineering, DevOps, blockchain/Web3, video editing, SEO copywriting only.

Strict rules:
1. No expired listings. Today is {today}. Skip anything past its deadline.
2. Always state the deadline clearly.
3. At least 3 results must come from dailyremote.com.
4. Find real active listings only.

Search: dailyremote.com/remote-jobs/developer, dailyremote.com/remote-jobs/design, contra.com, peopleperhour.com, freelancer.com, himalayas.app, remotive.com, weworkremotely.com, flowroles.com

For each of the 10 list:
Number, job title, platform.
What the client needs.
Which of Ayam's skills it uses.
Budget (or "Not listed").
Deadline (exact date or "Open — apply now").
Fit score: High or Medium.
Direct URL to the job post.

Then write an exact 3-sentence application message Ayam can copy and send immediately. Make it human, personal, and specific to the role. No corporate language.""", "opportunities 1-10")

    send_slack(JOBS_WEBHOOK, text)
    if sh:
        log_row(sh, "Opportunities", [now, "Batch 1 — 10 leads", "Multiple",
                "$100+", "Not Applied", "No", "", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# SECTION 3 — OPPORTUNITIES (11-20)
# ─────────────────────────────────────────
def run_opportunities_2(sh):
    print("\n🎯 SECTION 3 — OPPORTUNITIES BATCH 2 (11-20)")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 10 more opportunities for Ayam — grants, accelerators, agency partnerships.

Ayam's skills: WordPress, Webflow, Framer, automation (Zapier, Make, n8n), AI integration, UI/UX (Figma), mobile apps, healthcare tech, IT consulting.

Do not include: native iOS/Android only, data science engineering, DevOps, blockchain, video editing, SEO copywriting.

Strict rules:
1. No expired opportunities. Today is {today}. Skip anything past its deadline.
2. Always show deadline prominently.
3. Only include things Ayam can genuinely do and apply to today.

Focus on:
1. Grants and funding open now for African tech founders
2. Accelerator programmes currently accepting applications
3. Agency white-label partnerships — subcontracting web and automation work
4. Healthcare organisations needing digital solutions
5. Businesses posting on LinkedIn or Twitter needing a developer now

For each of the 10 list:
Number, opportunity name, source.
Description of what is needed.
Which of Ayam's skills match.
Value (amount or grant size).
Deadline (exact date or "Open — no deadline").
Fit score: High or Medium.
Direct link.

Then write an exact 3-sentence pitch message Ayam copies immediately.""", "opportunities 11-20")

    send_slack(JOBS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 4 — PLATFORM CONTENT
# ─────────────────────────────────────────
def run_content(briefing, sh):
    print("\n📣 SECTION 4 — PLATFORM CONTENT")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's content strategist. Today is {today}.
{WRITING_RULES}
Write platform content for Ayam based on one idea from today's news.

Today's briefing context:
{briefing[:500]}

Ayam's voice:
- Honest, grounded, builder-minded, humble confidence
- Clear and direct. Simple English. Clean sentences.
- Never uses: game-changer, hustle, crushing it, synergy, unstoppable
- His edge: nurse turned tech builder who thinks in systems
- Positioning: MD of Ayamtek, Registered Nurse, future Health Data Science MSc candidate

Pick the single most relevant idea from today's briefing and write:

LINKEDIN (150-200 words)
Thoughtful, professional but human. Story angle. End with a question.

X TWITTER (under 280 characters)
Sharp and punchy. One strong take.

INSTAGRAM CAPTION (100-150 words)
Personal and warm. Strong first line. CTA at end. Five relevant hashtags on last line.

FACEBOOK (150-200 words)
Fuller, more personal version.

THREADS (2-3 sentences)
Casual, real, thinking out loud.

TIKTOK REELS SCRIPT
Opening hook (3 seconds). Three talking points. Clear CTA.

WHATSAPP STATUS (under 100 characters)
Personal and warm for close network.

SUBSTACK HOOK (50-75 words)
Opening paragraph for a newsletter issue. Deep and thoughtful.

Write in first person. Authentic. Label each platform clearly.""", "platform content")

    send_slack(CONTENT_WEBHOOK, text)
    if sh:
        for p in ["LinkedIn", "X/Twitter", "Instagram", "Facebook",
                  "Threads", "TikTok/Reels", "WhatsApp Status", "Substack"]:
            log_row(sh, "Content Log", [now, p, "See Slack #content", "No", ""])
    return text


# ─────────────────────────────────────────
# SECTION 5 — OUTREACH TARGETS
# ─────────────────────────────────────────
def run_outreach(sh):
    print("\n📨 SECTION 5 — OUTREACH TARGETS")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 5 specific businesses Ayam should cold message today.

Ayam runs Ayamtek — builds websites ($300 five-day website offer), web apps, automation systems, AI chatbots, WhatsApp automation, and booking systems.

Find businesses that genuinely need what Ayam builds:
- Small businesses with broken, outdated, or no website
- Health organisations with no digital presence
- Businesses posting about needing a developer
- Startups with funding but no proper website
- Nigerian businesses trying to reach international clients

For each of the 5 list:
Number, business name, where to find them.
The specific problem they have right now.
Exactly what Ayam pitches to them.
Direct URL or social handle.

Then write an exact cold message under 60 words. Sound like a human noticing something specific about their business, not a salesperson.""", "outreach targets")

    send_slack(CONTENT_WEBHOOK, text)
    if sh:
        fu = (_now_wat + timedelta(days=3)).strftime("%Y-%m-%d")
        for i in range(1, 6):
            log_row(sh, "Outreach Log", [now, f"Target {i} — see Slack",
                    "Various", "See Slack", "Pending", fu, ""])
    return text


# ─────────────────────────────────────────
# SECTION 6 — FOLLOW-UP REMINDERS
# ─────────────────────────────────────────
def run_followups():
    print("\n⏰ SECTION 6 — FOLLOW-UP REMINDERS")
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Write today's follow-up reminder templates and accountability check.

Follow-up rules:
3 days — gentle check-in
7 days — more direct
14 days — final attempt then close

Write three short templates:

Template 1 — 3-day follow-up:
Two sentences. Natural, not pushy. References the original message.

Template 2 — 7-day follow-up:
Two sentences. Slightly more direct. Adds a small new hook.

Template 3 — 14-day final:
Two sentences. Professional close. Leaves the door open.

Then write a short accountability check with five questions:
Did you apply to three or more opportunities yesterday?
Did you post content on at least two platforms?
Did you send five outreach messages?
Do you have any responses to follow up on?
Is your Google Sheets tracker updated?

End with one honest sentence about why following up matters more than applying.""", "follow-up reminders")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 7 — SCHOLARSHIPS
# ─────────────────────────────────────────
def run_scholarships(sh):
    print("\n🎓 SECTION 7 — SCHOLARSHIPS")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 5 fully funded scholarships for Ayam Samuel.

About Ayam:
- Nigerian citizen, Registered Nurse (RN, RM)
- MD of Ayamtek — digital solutions and AI systems
- Target degree: MSc Health Data Science, MSc Health Informatics, or MSc Digital Health and AI
- Target universities: LSHTM, University of Edinburgh, King's College London, TU Munich, Heidelberg, Johns Hopkins online
- Second class lower degree from University of Jos
- Strong profile: WHO Pandemic Accord Youth Advocate, former NUNSA National Senate President, tech company founder

Absolute rules:
- Fully funded only. Must cover all of: tuition fees, monthly living stipend, return flights, health insurance.
- If any component is missing, do not include it.
- No partial scholarships, no loans, no fee waivers only.
- Application must be free to submit.
- No expired scholarships. Today is {today}. Skip any whose deadline has passed.

Priority targets:
Chevening Scholarship, Commonwealth Scholarship, DAAD Scholarship, Mastercard Foundation Scholars, Gates Cambridge, Wellcome Trust, LSHTM bursaries.

For each scholarship list:
Number, scholarship name, funding organisation.
Deadline (exact date — never skip this).
When applications open.
What it covers: tuition, stipend, flights, insurance.
University and programme.
Key eligibility requirements and whether Ayam qualifies.
One sentence on why Ayam is a strong fit, referencing his WHO and NUNSA profile.
Direct application URL.""", "scholarships")

    send_slack(SCHOLARSHIPS_WEBHOOK, text)
    if sh:
        log_row(sh, "Scholarships", [now, "Daily batch", "Multiple",
                "Various", "Fully Funded", "See Slack", "Not Applied", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# SECTION 8 — LEADERSHIP
# ─────────────────────────────────────────
def run_leadership(sh):
    print("\n🌍 SECTION 8 — LEADERSHIP")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 8 leadership opportunities for Ayam Samuel.

About Ayam:
- Nigerian, registered nurse and tech entrepreneur
- MD of Ayamtek — AI and digital solutions
- Former National Senate President NUNSA
- WHO Pandemic Accord Youth Advocate
- Building at the intersection of health and technology

Critical rule: List free opportunities first. Ayam cannot afford paid events right now. Mark every item clearly as Free or Paid.

No expired opportunities. Today is {today}. Skip anything past its deadline.

Find across these categories:
1. Flagship fully funded fellowships: Mandela Washington Fellowship, Obama Foundation Leaders Africa, Archbishop Desmond Tutu Fellowship, Acumen Fellows, Atlas Corps, Commonwealth Youth Programme
2. Free online programmes: YALI Network, WEF Global Shapers, UN online programmes, African Leadership Academy
3. Free conferences and events: tech conferences with free or scholarship passes, health tech events with funded attendance, African innovation summits
4. Free marketing and business programmes: HubSpot Academy, Google Digital Garage, Meta Blueprint

For each of the 8 list:
Number, programme name, organisation.
Free or Paid — be explicit.
Deadline (exact date or "Rolling — apply anytime").
Type: Fellowship, Online Programme, Conference, or Workshop.
What you get — specific benefit.
Key eligibility requirements.
One sentence on why Ayam fits, referencing his WHO and NUNSA profile.
Direct URL.

List free opportunities first.""", "leadership")

    send_slack(LEADERSHIP_WEBHOOK, text)
    if sh:
        log_row(sh, "Leadership", [now, "Daily batch", "Multiple",
                "Fellowship/Programme", "Free/Funded",
                "See Slack", "Not Applied", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# SECTION 9 — CERTIFICATIONS (every day)
# ─────────────────────────────────────────
def run_certifications(sh):
    print("\n📜 SECTION 9 — CERTIFICATIONS")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Find 6 certification and learning opportunities for Ayam.

About Ayam:
- MD of Ayamtek — websites, apps, automation, AI systems
- Registered Nurse pursuing MSc Health Data Science
- Current skills: Webflow, WordPress, no-code, low-code, AI tools
- Target expertise: Health Tech, AI, Web Development, Data Science

Free certifications only unless exceptionally valuable. Mark each clearly as Free or Paid.

Priority order:
1. Health Data Science and Health Tech: IBM Data Science Certificate (Coursera, free with financial aid), Google Data Analytics (Coursera), WHO digital health courses (OpenWHO, always free), Stanford Digital Health (Coursera), HIMSS free webinars, health informatics on edX
2. Tech and AI: Google certificates, IBM AI Developer, Microsoft Azure AI Fundamentals study materials, Meta Blueprint, HubSpot
3. Web Development: Webflow Expert Certification (free exam), freeCodeCamp, Google Web Dev courses

Current focus reminder:
Primary: IBM Data Science Professional Certificate — Coursera (apply for financial aid)
Secondary: WHO OpenWHO digital health courses — always free
These two directly support the Health Data Science MSc application.

For each of the 6 list:
Number, certification name, platform.
Free or Paid (be explicit).
Deadline if time-limited, otherwise "Always available".
Estimated time to complete.
Why it matters — how it helps the Health Data Science MSc or Ayamtek.
How to get financial aid if on Coursera.
Direct enrolment link.""", "certifications")

    send_slack(CERTIFICATIONS_WEBHOOK, text)
    if sh:
        log_row(sh, "Certifications", [now, "Daily batch", "Multiple",
                "Free priority", "0%", "", "No", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# WEEKLY REVIEW (Sundays only)
# ─────────────────────────────────────────
def run_weekly_review(sh):
    if day != "Sunday":
        return ""
    print("\n📊 WEEKLY REVIEW — Sunday")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.
{WRITING_RULES}
Write Ayam's weekly review and planning session for the week ahead.

Structure it as follows:

This week in review:
Income and work — targets were: apply to 15 or more opportunities, send 35 outreach messages, win at least one project.
Content and brand — targets were: post on LinkedIn four or more times, post on X daily, engage for 30 minutes per day.
Scholarships and leadership — targets were: apply to two scholarships, register for one free leadership programme, progress the IBM Data Science Certificate.

Next week priorities:
1. Income — most urgent action.
2. Content — most important post.
3. Scholarship — deadline approaching.
4. Leadership — free programme to register for.
5. Certification — course to progress.

Long-term pipeline:
Mandela Washington Fellowship — opens October, due November. This week's prep task.
Chevening Scholarship — opens August, due October. This week's prep task.
LSHTM MSc Health Data Science — applications open September. This week's research task.
IBM Data Science Certificate — current progress reminder.

End with one honest, specific observation about what matters most this week.""", "weekly review")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    if sh:
        log_row(sh, "Weekly Review", [today, "0", "0", "0", "0", "0", ""])
    return text


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    print(f"""
╔════════════════════════════════════════════════╗
║   AXIS — Ayam Samuel's Personal Brand System   ║
║   {today:<44}║
║   7 channels · Email · Sheets · Notion         ║
╚════════════════════════════════════════════════╝
""")

    # Google Sheets
    print("📊 Connecting to Google Sheets...")
    sh = get_sheet()
    if sh:
        setup_sheets(sh)
        print("  ✅ Google Sheets connected")
    else:
        print("  ⚠️  Running without Google Sheets")

    # Notion
    print("\n📓 Connecting to Notion...")
    notion = get_client()
    if notion:
        print("  ✅ Notion connected")
        notion_brief = build_notion_briefing(True)
        if notion_brief:
            send_slack(BRIEFING_WEBHOOK, notion_brief)
            print("  ✅ Notion intelligence → #axis-briefing")
        else:
            print("  ℹ️  No pending Notion items today")
        if day == "Monday":
            cert_nudge = build_cert_nudge(True)
            if cert_nudge:
                send_slack(BRIEFING_WEBHOOK, cert_nudge)
                print("  ✅ Certification nudge → #axis-briefing")
    else:
        print("  ⚠️  Notion not connected — check NOTION_TOKEN in .env")
        notion = None

    sections = []
    labels   = []

    # Section 1 — News Briefing
    print("\n" + "─" * 50)
    s = run_briefing()
    sections.append(s); labels.append("NEWS BRIEFING")
    pause(90)

    # Section 2 — Opportunities 1-10
    s = run_opportunities_1(sh)
    sections.append(s); labels.append("OPPORTUNITIES (1-10)")
    if notion and s:
        count = sync_opportunities(notion, s)
        print(f"  📓 Notion: {count} leads → Client Tracker")
    pause(90)

    # Section 3 — Opportunities 11-20
    s = run_opportunities_2(sh)
    sections.append(s); labels.append("OPPORTUNITIES (11-20)")
    pause(90)

    # Section 4 — Platform Content
    s = run_content(sections[0], sh)
    sections.append(s); labels.append("PLATFORM CONTENT")
    if notion and s:
        sync_content(notion, s)
        print("  📓 Notion: Draft → Content Calendar")
    pause(90)

    # Section 5 — Outreach Targets
    s = run_outreach(sh)
    sections.append(s); labels.append("OUTREACH TARGETS")
    pause(90)

    # Section 6 — Follow-up Reminders
    s = run_followups()
    sections.append(s); labels.append("FOLLOW-UP REMINDERS")
    if notion:
        sync_followup_tasks(notion)
        print("  📓 Notion: 3 daily tasks → Task Manager")
    pause(90)

    # Section 7 — Scholarships
    s = run_scholarships(sh)
    sections.append(s); labels.append("SCHOLARSHIPS")
    if notion and s:
        count = sync_scholarships(notion, s)
        print(f"  📓 Notion: {count} scholarships → Scholarship Tracker")
    pause(90)

    # Section 8 — Leadership
    s = run_leadership(sh)
    sections.append(s); labels.append("LEADERSHIP")
    if notion and s:
        count = sync_leadership(notion, s)
        print(f"  📓 Notion: {count} fellowships → Scholarship Tracker")
    pause(90)

    # Section 9 — Certifications (every day)
    s = run_certifications(sh)
    sections.append(s); labels.append("CERTIFICATIONS")

    # Weekly Review (Sundays only)
    if day == "Sunday":
        pause(90)
        run_weekly_review(sh)

    # Email digest
    send_full_email(sections, labels)

    notion_status = "✅ Synced  → Notion databases" if notion else "⚠️  Notion → Not connected"
    print(f"""
╔════════════════════════════════════════════════╗
║   ✅ AXIS COMPLETE — {now:<26}║
╠════════════════════════════════════════════════╣
║   ✅ News briefing      → #axis-briefing       ║
║   ✅ Notion intelligence → #axis-briefing      ║
║   ✅ 20 opportunities   → #opportunities       ║
║   ✅ Platform content   → #content             ║
║   ✅ Outreach targets   → #content             ║
║   ✅ Follow-ups         → #followups           ║
║   ✅ Scholarships       → #scholarships        ║
║   ✅ Leadership         → #leadership          ║
║   ✅ Certifications     → #certifications      ║
║   ✅ Full digest        → Gmail (AXIS inbox)   ║
║   ✅ Logged             → Google Sheets        ║
║   {notion_status:<47}║
╠════════════════════════════════════════════════╣
║   YOUR MORNING ACTIONS:                        ║
║   → Check Notion Task Manager for today        ║
║   → Apply to 3 opportunities before noon       ║
║   → Send 5 outreach messages                   ║
║   → Post on 2 platforms                        ║
╚════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()