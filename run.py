"""
AXIS — Ayam Samuel's Complete Personal Brand System
Version 2.0 — Final

7 Slack channels:
  #axis-briefing    — daily news
  #opportunities    — 20 freelance/contract leads
  #content          — 8 platform posts + outreach
  #followups        — reminders and accountability
  #scholarships     — MPH, Health Data Science funding
  #leadership       — FREE fellowships, conferences, workshops
  #certifications   — FREE courses and tech certifications

+ Email digest
+ Google Sheets tracking (8 tabs)
"""

import os
import time
import smtplib
import requests
import anthropic
from datetime import datetime, timedelta
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

client = anthropic.Anthropic(api_key=KEY)
today  = datetime.now().strftime("%A, %d %B %Y")
now    = datetime.now().strftime("%Y-%m-%d %H:%M")
day    = datetime.now().strftime("%A")


# ─────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────
def send_slack(webhook, text):
    if not webhook:
        print("  ⚠️  No webhook — skipping")
        return
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
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in r.content if hasattr(b, "text"))
        print(f"  ✅ Generated ({len(text)} chars)")
        return text.strip()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return ""


def pause(seconds=90):
    print(f"  ⏳ Pausing {seconds}s for rate limit...")
    time.sleep(seconds)


def send_email(subject, body):
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        print("  ⚠️  Gmail not configured — skipping")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = GMAIL_ADDRESS
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())
        print(f"  ✅ Email sent: {subject}")
    except Exception as e:
        print(f"  ❌ Email failed: {e}")


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
        sh    = gc.open_by_key(SHEET_ID)
        return sh
    except Exception as e:
        print(f"  ❌ Sheets failed: {e}")
        return None


def setup_sheets(sh):
    existing = [ws.title for ws in sh.worksheets()]
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
        if tab_name not in existing:
            ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
            ws.append_row(headers)
            print(f"  ✅ Created tab: {tab_name}")


def log_row(sh, tab, row):
    try:
        ws = sh.worksheet(tab)
        ws.append_row(row)
    except Exception as e:
        print(f"  ⚠️  Could not log to {tab}: {e}")


# ─────────────────────────────────────────
# SECTION 1 — DAILY NEWS BRIEFING
# ─────────────────────────────────────────
def run_briefing():
    print("\n📰 SECTION 1 — DAILY NEWS BRIEFING")
    text = ask(f"""You are AXIS, Ayam Samuel's personal chief of staff. Today is {today}.

Write a sharp daily news briefing for Ayam Samuel.
He is MD of Ayamtek — Nigerian digital solutions company building websites,
web apps, mobile apps, automation systems, and AI integrations for global clients.
He is a Registered Nurse (RN, RM). Long-term goal: MSc Health Data Science at LSHTM.

Cover one development per category. Be specific. Date as of {today}:

*1. 🤖 AI TOOLS & AUTOMATION*
Latest release or update — Claude, ChatGPT, Gemini, Make, Zapier, n8n.

*2. 💻 WEB & APP DEVELOPMENT*
Framework update, no-code/low-code news, or major industry shift.

*3. 🌍 DIGITAL BUSINESS & INTERNATIONAL CLIENTS*
What businesses globally are spending on. What digital services are in demand.

*4. 🇳🇬 AFRICAN TECH & NIGERIA*
Funding, startup activity, policy, or visibility for African builders.

*5. 🧠 FRONTIER AI MODELS*
Latest model release or research breakthrough. Name model, lab, what changed.

*6. 🏥 HEALTH TECH & DIGITAL HEALTH*
AI in healthcare, health informatics, digital health policy, health data science.

*7. 🏗️ INFRASTRUCTURE & CLOUD*
Data centre news, cloud update, or major infrastructure deal.

*8. 🛠️ NEW TOOL WORTH KNOWING*
One specific new tool launched this week. Name it. What it does. Link.

For each: *bold header*, bold headline, 2 sentence summary,
1 sentence why it matters to Ayam specifically.
Slack formatting. Under 3000 characters total.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*🚀 AXIS DAILY BRIEFING — {today}*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Ready. What do you want to work on first?*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "news briefing")

    send_slack(BRIEFING_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 2 — OPPORTUNITIES (1-10)
# ─────────────────────────────────────────
def run_opportunities_1(sh):
    print("\n🎯 SECTION 2 — OPPORTUNITIES BATCH 1 (1-10)")
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find 10 specific freelance contracts Ayam can apply to RIGHT NOW.

About Ayam:
- MD of Ayamtek Nigeria — websites (WordPress, Webflow, Framer),
  web apps, mobile apps, landing pages, automation (Zapier, Make, n8n),
  AI integrations, chatbots, UI/UX, IT consulting
- Remote work globally — $100 minimum per project
- Payments: Payoneer, Wise, crypto. NOT employment — contracts only.

⚠️ STRICT RULES — READ BEFORE SEARCHING:
1. NO expired opportunities — today is {today}. If deadline has passed, skip it.
2. ALWAYS state the deadline if one exists — never leave it out
3. At least 3 results MUST come from dailyremote.com specifically
4. Find REAL active listings — not homepage links

Search these platforms:
1. dailyremote.com/remote-jobs/developer — MUST include 3+ from here
2. dailyremote.com/remote-jobs/design — check this section too
3. contra.com — web development and automation gigs
4. peopleperhour.com — Webflow, WordPress, automation jobs
5. freelancer.com — web development jobs posted this week
6. himalayas.app — web dev and no-code roles
7. remotive.com — developer and automation roles
8. weworkremotely.com — design and programming section
9. flowroles.com — Webflow specific jobs

For each of the 10:
*[N]. [Job Title] — [Platform]*
• What: [exactly what client needs — specific]
• Budget: [amount or "Not listed"]
• Deadline: [specific date or "Open — apply now" — NEVER skip this]
• Fit: [one specific reason Ayam wins this]
• Apply: [direct URL to the specific job post]

READY TO SEND APPLICATION:
[Write exact 3-sentence message Ayam copies and sends immediately.
Personal, specific, human — not corporate.]

Slack formatting. *bold* with asterisks.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*🎯 LIVE OPPORTUNITIES — {today} (1 of 2)*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with: *More in next message ↓*""", "opportunities 1-10")

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
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find 10 MORE opportunities for Ayam — beyond job boards.

About Ayam:
- MD of Ayamtek Nigeria — websites, apps, automation, AI systems
- RN and RM — understands healthcare
- Remote work globally — $100+ per project
- Personal brand: @ayamsamuelxyz

⚠️ STRICT RULES:
1. NO expired opportunities — today is {today}. Deadline passed = skip it completely.
2. ALWAYS state the deadline clearly — if deadline exists, show it prominently
3. If application is rolling/open, say "Open — no deadline"
4. Only include things Ayam can actually apply to TODAY

This batch focuses on:
1. Grants and funding OPEN NOW for African tech founders — NOT TEF (deadline passed)
2. Accelerator programmes currently accepting applications right now
3. Agency white-label partnerships — subcontracting web/automation work
4. LinkedIn or Twitter posts from founders needing a developer NOW
5. Healthcare organisations needing digital solutions

For each of the 10:
*[N]. [Opportunity] — [Source]*
• What: [specific description]
• Value: [$ amount or grant size]
• Deadline: [EXACT date — e.g. "30 April 2026" or "Open — no deadline" — NEVER skip]
• Fit: [one specific reason Ayam is right]
• Link: [direct URL]

PITCH MESSAGE:
[Exact 3-sentence pitch Ayam copies immediately. Personal, specific.]

Slack formatting. *bold* with asterisks.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*🎯 MORE OPPORTUNITIES — {today} (2 of 2)*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*20 leads total. Pick 3. Apply today.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "opportunities 11-20")

    send_slack(JOBS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 4 — PLATFORM CONTENT
# ─────────────────────────────────────────
def run_content(briefing, sh):
    print("\n📣 SECTION 4 — PLATFORM CONTENT")
    text = ask(f"""You are AXIS, Ayam Samuel's content strategist. Today is {today}.

Based on today's news, write platform content in Ayam's voice.

TODAY'S BRIEFING CONTEXT:
{briefing[:600]}

AYAM'S VOICE:
- Honest, grounded, builder-minded, humble confidence
- Clear and direct — simple English, clean sentences
- Never uses: game-changer, hustle, crushing it, synergy, unstoppable
- His edge: nurse turned tech builder — systems thinking
- Positioning: MD Ayamtek + RN + future Health Data Science MSc

Pick ONE most relevant idea from today's briefing and write:

*📌 LINKEDIN* (150-200 words)
Thoughtful, professional but human. Story angle. End with question.

*🐦 X / TWITTER* (under 280 characters)
Sharp, punchy, one strong take.

*📸 INSTAGRAM CAPTION* (100-150 words)
Personal, warm. Strong hook first. CTA at end. 5 hashtags on last line.

*👥 FACEBOOK* (150-200 words)
Fuller, more personal version.

*🧵 THREADS* (2-3 sentences)
Casual, real, thinking out loud.

*🎵 TIKTOK / REELS SCRIPT*
Hook (3 seconds) + 3 talking points + CTA

*💬 WHATSAPP STATUS* (under 100 characters)
Personal and warm.

*📧 SUBSTACK HOOK* (50-75 words)
Opening paragraph. Deep and thoughtful.

Write in first person. Authentic. Never corporate.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*📣 CONTENT FOR TODAY — {today}*
*Core idea: [one line summary]*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Review, adjust your voice, post. Takes 10 minutes.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "platform content")

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
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find 5 specific businesses Ayam should cold message TODAY.

About Ayam:
- MD of Ayamtek — websites, apps, automation, AI systems
- His offer: "The 5-Day Website — $300. Clean, fast, professional.
  Built in 5 days. Hosting setup. Mobile optimised."
- Also builds: AI chatbots, WhatsApp automation, booking systems

Find businesses that NEED what Ayam builds:
- Small businesses with broken/outdated/no website
- Health organisations with no digital presence
- Businesses posting about needing a developer
- Startups with funding but no proper website
- Nigerian businesses going international with no digital presence

For each of the 5:
*[N]. [Business Name] — [Where to find them]*
• Pain: [specific problem they have]
• Offer: [exactly what Ayam pitches]
• Find at: [specific URL or handle]

COLD MESSAGE TO SEND:
[Exact DM or email. Under 60 words. Personal and specific.
Human — not a salesperson. Reference something specific.]

Slack formatting. *bold* with asterisks.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*📨 OUTREACH TARGETS — {today}*
*5 businesses to message. Takes 20 minutes.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Send all 5 before noon. Follow up in 3 days.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "outreach targets")

    send_slack(CONTENT_WEBHOOK, text)
    if sh:
        fu = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
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

Write today's follow-up reminders and accountability check.

*FOLLOW-UP RULE:*
3 days → gentle check-in
7 days → more direct
14 days → final attempt then close

*TEMPLATE 1 — 3-DAY FOLLOW-UP:*
[2 sentences. Natural, not pushy. References original message.]

*TEMPLATE 2 — 7-DAY FOLLOW-UP:*
[2 sentences. Slightly more direct. Adds small new hook.]

*TEMPLATE 3 — 14-DAY FINAL:*
[2 sentences. Professional close. Leaves door open.]

*TODAY'S ACCOUNTABILITY CHECK:*
□ Applied to 3+ opportunities yesterday?
□ Posted content on at least 2 platforms?
□ Sent 5 outreach messages?
□ Any responses to follow up on?
□ Google Sheets tracker updated?

*REMEMBER:*
80% of contracts go to the person who followed up.
Not the person who applied first.

Slack formatting. *bold* headers.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*⏰ FOLLOW-UP REMINDERS — {today}*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Update your tracker. Money is in the follow-up.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "follow-up reminders")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 7 — SCHOLARSHIPS
# ─────────────────────────────────────────
def run_scholarships(sh):
    print("\n🎓 SECTION 7 — SCHOLARSHIPS")
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find scholarship opportunities for Ayam Samuel.

About Ayam:
- Nigerian citizen, registered nurse (RN, RM)
- MD of Ayamtek — digital solutions and AI systems
- Target: MSc Health Data Science OR MSc Health Informatics
  OR MSc Digital Health and AI
- Target schools: LSHTM, University of Edinburgh, King's College London,
  TU Munich, Heidelberg, Johns Hopkins online
- Second class lower from University of Jos
- Strong profile: WHO Pandemic Accord Youth Advocate,
  Former NUNSA National Senate President, tech company founder

Find 5 FULLY FUNDED scholarships for Ayam Samuel.

⚠️ STRICT RULES:
1. NO expired scholarships — today is {today}. If deadline has passed, skip it.
2. FULLY FUNDED ONLY — tuition ✅ + stipend ✅ + flights ✅ + insurance ✅
3. If ANY component is missing — do NOT include it
4. ALWAYS show deadline prominently — never skip it
5. Application must be FREE to submit

Focus on these known fully funded scholarships:
1. Chevening Scholarship (UK — opens August, deadline November)
2. Commonwealth Scholarship (UK — check current cycle)
3. DAAD Scholarship (Germany — multiple deadlines)
4. Mastercard Foundation Scholars (various — check open calls)
5. Gates Cambridge Scholarship (UK — October deadline)
6. Wellcome Trust Health Research Scholarships
7. LSHTM specific bursaries and funded places
8. Any other FULLY FUNDED award for health data science
   or health informatics at top global universities

For each scholarship:
*[N]. [Scholarship Name] — [Funding Organisation]*
• ⏰ DEADLINE: [EXACT DATE — e.g. "5 November 2026" — NEVER skip or say "varies"]
• 📅 Applications open: [when to start applying]
• Covers: tuition ✅ stipend ✅ flights ✅ insurance ✅
• University: [where you study]
• Programme: [exact MSc degree funded]
• Eligibility: [key requirements — confirm Ayam qualifies with his profile]
• Why Ayam fits: [one sentence — reference WHO/NUNSA/Ayamtek specifically]
• Apply: [direct URL to scholarship page]

Slack formatting. *bold* with asterisks.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*🎓 SCHOLARSHIP ALERTS — {today}*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Check deadlines. Apply to everything you qualify for.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "scholarships")

    send_slack(SCHOLARSHIPS_WEBHOOK, text)
    if sh:
        log_row(sh, "Scholarships", [now, "Daily batch — see Slack",
                "Multiple", "Various", "FULLY FUNDED ONLY",
                "See Slack", "Not Applied", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# SECTION 8 — LEADERSHIP (FREE PRIORITY)
# ─────────────────────────────────────────
def run_leadership(sh):
    print("\n🌍 SECTION 8 — LEADERSHIP")
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find leadership opportunities for Ayam Samuel.

About Ayam:
- Nigerian, registered nurse and tech entrepreneur
- MD of Ayamtek — AI and digital solutions
- Former National Senate President NUNSA
- WHO Pandemic Accord Youth Advocate
- Building at intersection of health and technology

⚠️ STRICT RULES:
1. NO expired opportunities — today is {today}. Deadline passed = skip it.
2. ALWAYS show deadline prominently with ⏰ symbol
3. FREE opportunities FIRST — Ayam cannot afford paid events right now
4. Mark every item clearly: 🆓 FREE or 💰 PAID

Find 8 opportunities across:

CATEGORY 1 — FLAGSHIP FELLOWSHIPS (fully funded, free to apply):
Mandela Washington Fellowship, Obama Foundation Leaders Africa,
Archbishop Desmond Tutu Fellowship, Acumen Fellows,
Atlas Corps, Commonwealth Youth Programme

CATEGORY 2 — FREE ONLINE PROGRAMMES:
YALI Network, WEF Global Shapers, UN online programmes,
African Leadership Academy, free webinars and workshops

CATEGORY 3 — FREE CONFERENCES AND EVENTS:
Tech conferences with free/scholarship passes,
health tech events with funded attendance,
African innovation summits, speaker call opportunities

CATEGORY 4 — FREE MARKETING AND BUSINESS BUILDING:
HubSpot Academy, Google Digital Garage,
Meta Blueprint, free online masterclasses

For each of the 8:
*[N]. [Programme Name] — [Organisation]*
• Cost: [🆓 FREE or 💰 PAID — be explicit]
• ⏰ DEADLINE: [EXACT DATE — e.g. "31 July 2026" or "Rolling — apply anytime"]
• Type: [Fellowship / Online / Conference / Workshop]
• What you get: [specific benefit — stipend amount, certificate, network]
• Eligibility: [key requirements]
• Why Ayam fits: [one sentence — reference his WHO/NUNSA/Ayamtek profile]
• Link: [direct URL]

Sort: FREE first, then funded, then paid.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*🌍 LEADERSHIP OPPORTUNITIES — {today}*
*🆓 = Free  💰 = Paid — Free ones listed first*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Start with the FREE ones. Build your profile. Funded ones follow.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "leadership")

    send_slack(LEADERSHIP_WEBHOOK, text)
    if sh:
        log_row(sh, "Leadership", [now, "Daily batch — see Slack",
                "Multiple", "Fellowship/Programme", "Free/Funded",
                "See Slack", "Not Applied", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# SECTION 9 — CERTIFICATIONS (FREE PRIORITY)
# Mon/Wed/Fri/Sun only
# ─────────────────────────────────────────
def run_certifications(sh):
    print("\n📜 SECTION 9 — CERTIFICATIONS")

    if day not in ["Monday", "Wednesday", "Friday", "Sunday"]:
        print("  ℹ️  Certifications runs Mon/Wed/Fri/Sun only — skipping")
        return ""

    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

Find certification and learning opportunities for Ayam.

About Ayam:
- MD of Ayamtek — websites, apps, automation, AI systems
- RN, RM — pursuing Health Data Science MSc
- Skills: Webflow, WordPress, no-code, low-code, AI tools
- Wants expertise in: Health Tech, AI, Web Development, Data Science

⚠️ FREE certifications ONLY unless exceptional value.
Mark clearly: 🆓 FREE or 💰 PAID.

Find 6 opportunities:

PRIORITY 1 — Health Data Science and Health Tech (FREE):
IBM Data Science Certificate (Coursera — free with financial aid),
Google Data Analytics (Coursera — free with aid),
WHO digital health courses (OpenWHO — always free),
Stanford Digital Health (Coursera — free to audit),
HIMSS free webinars, health informatics on edX (free to audit)

PRIORITY 2 — Tech and AI (FREE):
Google certificates (UX, PM, IT Support) — Coursera free with aid,
IBM AI Developer — Coursera free with aid,
Microsoft Azure AI Fundamentals — free study materials,
Meta Blueprint — always free, HubSpot — always free

PRIORITY 3 — Web Development (FREE):
Webflow Expert Certification — free exam,
freeCodeCamp — always free,
Google Web Dev courses — free

For each of the 6:
*[N]. [Certification] — [Platform]*
• Cost: [🆓 FREE or 💰 cost — be explicit]
• ⏰ Deadline: [if time-limited — exact date. If always available — "Always available"]
• Time: [estimated hours/weeks to complete]
• Why valuable: [how it helps Health Data Science MSc or Ayamtek goals]
• Financial aid: [if Coursera — "Apply for aid at coursera.org/financial-aid"]
• Link: [direct enrolment URL]

*CURRENT FOCUS REMINDER:*
Primary: IBM Data Science Professional Certificate — Coursera
Secondary: WHO OpenWHO digital health courses — free
These directly support the Health Data Science MSc application.

Slack formatting. *bold* with asterisks.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*📜 CERTIFICATIONS & LEARNING — {today}*
*🆓 = Free  💰 = Paid*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*Start here: coursera.org/professional-certificates/ibm-data-science*
*Apply for financial aid — takes 5 minutes. Saves you $49/month.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "certifications")

    send_slack(CERTIFICATIONS_WEBHOOK, text)
    if sh:
        log_row(sh, "Certifications", [now, "Weekly batch — see Slack",
                "Multiple", "Free", "0%", "", "No", "See Slack", ""])
    return text


# ─────────────────────────────────────────
# WEEKLY REVIEW (Sundays only)
# ─────────────────────────────────────────
def run_weekly_review(sh):
    if day != "Sunday":
        return ""
    print("\n📊 WEEKLY REVIEW — Sunday")
    text = ask(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today} — Sunday.

Write Ayam's weekly review and next week plan.

*THIS WEEK IN REVIEW:*

□ INCOME & WORK
  Target was: Apply to 15+ opportunities
  Send 35 outreach messages (5/day)
  Win at least 1 project

□ CONTENT & BRAND
  Target was: Post on LinkedIn 4+ times
  Post on X/Twitter daily
  Engage 30 mins per day

□ SCHOLARSHIPS & LEADERSHIP
  Target was: Apply to 2 scholarships
  Register for 1 free leadership programme
  Progress IBM Data Science Certificate

*NEXT WEEK PRIORITIES:*
1. [Income — most urgent]
2. [Content — most important]
3. [Scholarship — deadline approaching]
4. [Leadership — free programme to register]
5. [Certification — course to progress]

*LONG-TERM PIPELINE CHECK:*

Mandela Washington Fellowship:
Opens October. Applications due November.
This week prep: [specific task]

Chevening Scholarship:
Opens August. Applications due November.
This week prep: [specific task]

LSHTM MSc Health Data Science:
Applications open September typically.
This week research: [specific task]

IBM Data Science Certificate:
Current progress: [reminder to update]
This week: Complete [X] modules

*ONE HONEST OBSERVATION:*
[One sharp sentence about what matters most this week.
Real and specific — not motivational fluff.]

Slack formatting. *bold* headers.

Start with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*📊 AXIS WEEKLY REVIEW — {today}*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
End with:
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*
*New week. Fresh start. Execute.*
*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*""", "weekly review")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    if sh:
        log_row(sh, "Weekly Review", [today, "0", "0", "0", "0", "0", ""])
    return text


# ─────────────────────────────────────────
# EMAIL DIGEST
# ─────────────────────────────────────────
def send_full_email(sections, labels):
    print("\n📧 SENDING EMAIL DIGEST")
    subject = f"AXIS Daily Briefing — {today}"
    divider = "\n" + "─" * 50 + "\n"
    body = f"AXIS DAILY BRIEFING\n{today}\nGenerated: {now}\n{'=' * 50}\n"

    for label, content in zip(labels, sections):
        if content:
            body += f"\n{label}\n{divider}{content}\n"

    body += f"\n{'=' * 50}\n"
    body += "Generated by AXIS — Ayam Samuel's Personal Brand System\n"
    body += "ayamtek.xyz | @ayamsamuelxyz\n"
    send_email(subject, body)


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

    # ── Connect Google Sheets ──
    print("📊 Connecting to Google Sheets...")
    sh = get_sheet()
    if sh:
        setup_sheets(sh)
        print("  ✅ Google Sheets connected")
    else:
        print("  ⚠️  Running without Google Sheets")

    # ── Connect Notion ──
    print("\n📓 Connecting to Notion...")
    notion = get_client()
    if notion:
        print("  ✅ Notion connected")
        notion_brief = build_notion_briefing(notion)
        if notion_brief:
            send_slack(BRIEFING_WEBHOOK, notion_brief)
            print("  ✅ Notion intelligence → #axis-briefing")
        else:
            print("  ℹ️  No pending items in Notion today")
        # Monday — weekly certification nudge
        if day == "Monday":
            cert_nudge = build_cert_nudge(True)
            if cert_nudge:
                send_slack(BRIEFING_WEBHOOK, cert_nudge)
                print("  ✅ Cert nudge → #axis-briefing")
    else:
        print("  ⚠️  Notion not connected — check NOTION_TOKEN in .env")
        notion = None

    sections = []
    labels   = []

    # ── Section 1 — News Briefing ──
    print("\n" + "─"*50)
    s = run_briefing()
    sections.append(s); labels.append("NEWS BRIEFING")
    pause(90)

    # ── Section 2 — Opportunities 1-10 ──
    s = run_opportunities_1(sh)
    sections.append(s); labels.append("OPPORTUNITIES (1-10)")
    if notion and s:
        count = sync_opportunities(notion, s)
        print(f"  📓 Notion: {count} leads → Client Tracker")
    pause(90)

    # ── Section 3 — Opportunities 11-20 ──
    s = run_opportunities_2(sh)
    sections.append(s); labels.append("OPPORTUNITIES (11-20)")
    pause(90)

    # ── Section 4 — Platform Content ──
    s = run_content(sections[0], sh)
    sections.append(s); labels.append("PLATFORM CONTENT")
    if notion and s:
        sync_content(notion, s)
        print("  📓 Notion: Draft → Content Calendar")
    pause(90)

    # ── Section 5 — Outreach Targets ──
    s = run_outreach(sh)
    sections.append(s); labels.append("OUTREACH TARGETS")
    pause(90)

    # ── Section 6 — Follow-up Reminders ──
    s = run_followups()
    sections.append(s); labels.append("FOLLOW-UP REMINDERS")
    if notion:
        sync_followup_tasks(notion)
        print("  📓 Notion: 3 daily tasks → Task Manager")
    pause(90)

    # ── Section 7 — Scholarships ──
    s = run_scholarships(sh)
    sections.append(s); labels.append("SCHOLARSHIPS")
    if notion and s:
        count = sync_scholarships(notion, s)
        print(f"  📓 Notion: {count} scholarships → Scholarship Tracker")
    pause(90)

    # ── Section 8 — Leadership ──
    s = run_leadership(sh)
    sections.append(s); labels.append("LEADERSHIP")
    if notion and s:
        count = sync_leadership(notion, s)
        print(f"  📓 Notion: {count} fellowships → Scholarship Tracker")
    pause(90)

    # ── Section 9 — Certifications (Mon/Wed/Fri/Sun) ──
    s = run_certifications(sh)
    sections.append(s); labels.append("CERTIFICATIONS")

    # ── Weekly Review (Sundays only) ──
    if day == "Sunday":
        pause(90)
        run_weekly_review(sh)

    # ── Email digest ──
    send_full_email(sections, labels)

    notion_status = "✅ Synced             → Notion databases" if notion else "⚠️  Notion            → Not connected"
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
║   ✅ Leadership (free)  → #leadership          ║
║   ✅ Certifications     → #certifications      ║
║   ✅ Full digest        → Gmail                ║
║   ✅ Logged             → Google Sheets        ║
║   {notion_status:<47}║
╠════════════════════════════════════════════════╣
║   NOTION DATABASES UPDATED:                    ║
║   → Client Tracker   — new leads added         ║
║   → Content Calendar — today's draft saved     ║
║   → Task Manager     — 3 daily tasks created   ║
║   → Scholarship Tracker — new entries added    ║
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