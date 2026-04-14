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

from datetime import datetime, timedelta, timezone

# Nigeria time — WAT is UTC+1
WAT = timezone(timedelta(hours=1))
_now_wat = datetime.now(WAT)

client = anthropic.Anthropic(api_key=KEY)
today  = _now_wat.strftime("%A, %d %B %Y")
now    = _now_wat.strftime("%Y-%m-%d %H:%M")
day    = _now_wat.strftime("%A")


# ─────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────
def clean_slack_output(text):
    """Strip all AI formatting artifacts from Slack output"""
    if not text:
        return text
    import re as _re
    # Remove double asterisks **text** first
    text = _re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # Remove single asterisks *text*
    text = _re.sub(r'\*([^*\n]+)\*', r'\1', text)
    # Remove remaining lone asterisks
    text = _re.sub(r'(?<!\w)\*(?!\w)', '', text)
    # Remove long divider lines (━ ─ = -)
    text = _re.sub(r'[━─═\-]{4,}', '', text)
    # Remove markdown --- separators
    text = _re.sub(r'(?m)^---+$', '', text)
    # Remove > blockquote markers
    text = _re.sub(r'(?m)^>\s*', '', text)
    # Remove em dashes and long hyphens
    text = text.replace('—', '-').replace('–', '-')
    # Clean trailing spaces per line
    text = _re.sub(r' +\n', '\n', text)
    # Max two consecutive blank lines
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def send_slack(webhook, text):
    if not webhook:
        print("  ⚠️  No webhook — skipping")
        return
    if not text or not text.strip():
        print("  ⚠️  Empty content — skipping Slack send")
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
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in r.content if hasattr(b, "text"))
        print(f"  ✅ Generated ({len(text)} chars)")
        return text.strip()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return ""


def ask_with_search(prompt, label=""):
    """Ask Claude with web search enabled — gets real-time data"""
    print(f"  🌐 Generating {label} (with web search)...")
    try:
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search"
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        # Extract all text blocks — web search returns mixed content types
        text = "".join(
            b.text for b in r.content
            if hasattr(b, "text") and b.type == "text"
        )
        searches = sum(
            1 for b in r.content
            if hasattr(b, "type") and b.type == "tool_use"
        )
        if searches:
            print(f"  🔍 Performed {searches} web search(es)")
        # If output is empty or too short, fall back to standard
        if len(text.strip()) < 100:
            print(f"  ⚠️  Web search output too short — falling back to standard")
            return ask(prompt, label)
        print(f"  ✅ Generated ({len(text)} chars)")
        return text.strip()
    except Exception as e:
        print(f"  ❌ Web search failed: {e} — falling back to standard")
        return ask(prompt, label)


def pause(seconds=90):
    print(f"  ⏳ Pausing {seconds}s for rate limit...")
    time.sleep(seconds)


def send_email(subject, html_body, plain_body=""):
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        print("  ⚠️  Gmail not configured — skipping")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"AXIS — Ayam Samuel <{GMAIL_ADDRESS}>"
        msg["To"]      = GMAIL_ADDRESS
        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
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


def build_sheet_map(sh):
    """Build a map of base_name → worksheet object, handling icon prefixes"""
    ws_map = {}
    for ws in sh.worksheets():
        ws_map[ws.title] = ws
        # Strip icon prefix — e.g. "🎯 Opportunities" → "Opportunities"
        parts = ws.title.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) <= 2:
            base = parts[1].strip()
            if base not in ws_map:
                ws_map[base] = ws
    return ws_map


def setup_sheets(sh):
    ws_map = build_sheet_map(sh)
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
        else:
            pass  # Tab already exists — do not recreate


# Cache the sheet map per run — only fetches worksheets once
_sheet_map_cache = None

def get_sheet_map(sh):
    """Get cached sheet map — only hits Google Sheets API once per run"""
    global _sheet_map_cache
    if _sheet_map_cache is None and sh:
        _sheet_map_cache = build_sheet_map(sh)
    return _sheet_map_cache or {}


def log_row(sh, tab, row):
    """Log a row using cached sheet map — no repeated API calls"""
    try:
        ws_map = get_sheet_map(sh)
        if tab in ws_map:
            ws_map[tab].append_row(row)
        else:
            print(f"  ⚠️  Tab '{tab}' not found — skipping log")
    except Exception as e:
        print(f"  ⚠️  Could not log to {tab}: {e}")


# ─────────────────────────────────────────
# SECTION 1 — DAILY NEWS BRIEFING
# ─────────────────────────────────────────
def run_briefing():
    print("\n📰 SECTION 1 — DAILY NEWS BRIEFING")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's personal chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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
Keep under 3000 characters total.

Start with:
""", "news briefing")

    send_slack(BRIEFING_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 2 — OPPORTUNITIES (1-10)
# ─────────────────────────────────────────
def run_opportunities_1(sh):
    print("\n🎯 SECTION 2 — OPPORTUNITIES BATCH 1 (1-10)")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


Find 10 freelance contracts Ayam can apply to RIGHT NOW that match his EXACT skills.

AYAM'S VERIFIED SKILLS — only show opportunities matching these:
✅ Websites: WordPress, Webflow, Framer, HTML/CSS, landing pages
✅ Web Apps: custom web applications, dashboards, portals
✅ Automation: Zapier, Make.com, n8n — workflow automation
✅ AI Integration: chatbots, Claude API, OpenAI API, AI-powered tools
✅ No-Code/Low-Code: Bubble, Glide, Airtable, Notion integrations
✅ UI/UX Design: Figma, wireframing, prototyping
✅ Mobile Apps: cross-platform mobile development
✅ IT Consulting: digital strategy, systems thinking
✅ Healthcare Tech: clinical systems, health informatics (bonus fit)

❌ DO NOT INCLUDE — Ayam CANNOT do these:
❌ Native iOS/Android (Swift, Kotlin) — not his stack
❌ Data Science / Machine Learning engineering
❌ DevOps, cloud infrastructure, AWS/Azure configuration
❌ Blockchain / Web3 / smart contracts
❌ Video editing, animation, motion graphics
❌ SEO copywriting, content writing
❌ Physical design (print, packaging, branding only)
❌ Anything requiring physical presence

⚠️ STRICT RULES:
1. NO expired opportunities — today is {today}. Deadline passed = skip it.
2. ALWAYS state the deadline — never leave it out
3. At least 3 results MUST come from dailyremote.com
4. Find REAL active listings — verify the URL exists

Search these platforms:
1. dailyremote.com/remote-jobs/developer — MUST include 3+ from here
2. dailyremote.com/remote-jobs/design — check this too
3. contra.com — web development and automation gigs
4. peopleperhour.com — Webflow, WordPress, automation
5. freelancer.com — web development posted this week
6. himalayas.app — web dev and no-code roles
7. remotive.com — developer and automation roles
8. weworkremotely.com — design and programming
9. flowroles.com — Webflow specific jobs

For each of the 10:
*[N]. [Job Title] — [Platform]*
• What: [exactly what client needs]
• Skills match: [which of Ayam's skills this uses — be specific]
• Budget: [amount or "Not listed"]
• Deadline: [specific date or "Open — apply now"]
• Fit score: [High / Medium — and why]
• Apply: [direct URL to the job post]

READY TO SEND APPLICATION:
[Exact 3-sentence message. Personal, specific, human — not corporate.
Reference the specific skill match.]


Start with:
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
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


Find 10 MORE opportunities for Ayam — grants, accelerators, partnerships.

AYAM'S VERIFIED SKILLS — only show opportunities matching these:
✅ Websites: WordPress, Webflow, Framer, landing pages
✅ Web Apps: custom web applications, dashboards, portals
✅ Automation: Zapier, Make.com, n8n
✅ AI Integration: chatbots, Claude API, AI-powered tools
✅ No-Code/Low-Code: Bubble, Airtable, Notion integrations
✅ UI/UX Design: Figma, wireframing
✅ Mobile Apps: cross-platform mobile development
✅ Healthcare Tech: clinical systems, health informatics
✅ IT Consulting: digital strategy for businesses

❌ DO NOT INCLUDE:
❌ Native iOS/Android only roles
❌ Data Science / ML engineering
❌ DevOps / cloud infrastructure
❌ Blockchain / Web3
❌ Video editing / motion graphics
❌ SEO / content writing only

⚠️ STRICT RULES:
1. NO expired opportunities — today is {today}. Deadline passed = skip completely.
2. ALWAYS show deadline prominently with ⏰
3. If rolling/open, say "Open — no deadline"
4. Only include things Ayam can actually do and apply to TODAY

This batch focuses on:
1. Grants and funding OPEN NOW for African tech founders
2. Accelerator programmes currently accepting applications
3. Agency white-label partnerships — web/automation subcontracting
4. Healthcare organisations needing digital solutions
5. Businesses posting on LinkedIn/Twitter needing a developer NOW

For each of the 10:
*[N]. [Opportunity] — [Source]*
• What: [specific description]
• Value: [$ amount or grant size]
• Deadline: [EXACT date — e.g. "30 April 2026" or "Open — no deadline" — NEVER skip]
• Fit: [one specific reason Ayam is right]
• Link: [direct URL]

PITCH MESSAGE:
[Exact 3-sentence pitch Ayam copies immediately. Personal, specific.]


Start with:
""", "opportunities 11-20")

    send_slack(JOBS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 4 — PLATFORM CONTENT
# ─────────────────────────────────────────
def run_content(briefing, sh):
    print("\n📣 SECTION 4 — PLATFORM CONTENT")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's content strategist. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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

LINKEDIN (150-200 words)
Thoughtful, professional but human. Story angle. End with question.

X / TWITTER (under 280 characters)
Sharp, punchy, one strong take.

INSTAGRAM CAPTION (100-150 words)
Personal, warm. Strong hook first. CTA at end. 5 hashtags on last line.

FACEBOOK (150-200 words)
Fuller, more personal version.

THREADS (2-3 sentences)
Casual, real, thinking out loud.

TIKTOK / REELS SCRIPT
Hook (3 seconds) + 3 talking points + CTA

WHATSAPP STATUS (under 100 characters)
Personal and warm.

SUBSTACK HOOK (50-75 words)
Opening paragraph. Deep and thoughtful.

Write in first person. Authentic. Never corporate.

""", "platform content")

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

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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


""", "outreach targets")

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

FOLLOW-UP RULES
3 days → gentle check-in
7 days → more direct
14 days → final attempt then close

Template 1 — 3-day follow-up:
[2 sentences. Natural, not pushy. References original message.]

Template 2 — 7-day follow-up:
[2 sentences. Slightly more direct. Adds small new hook.]

Template 3 — 14-day final message:
[2 sentences. Professional close. Leaves door open.]

Accountability check for today:
□ Applied to 3+ opportunities yesterday?
□ Posted content on at least 2 platforms?
□ Sent 5 outreach messages?
□ Any responses to follow up on?
□ Google Sheets tracker updated?

Note: 80% of contracts go to the person who followed up.
Not the person who applied first.


Start with:
""", "follow-up reminders")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    return text


# ─────────────────────────────────────────
# SECTION 7 — SCHOLARSHIPS
# ─────────────────────────────────────────
def run_scholarships(sh):
    print("\n🎓 SECTION 7 — SCHOLARSHIPS")
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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


Start with:
""", "scholarships")

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
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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
[N]. Programme Name — Organisation
• Cost: [🆓 FREE or 💰 PAID — be explicit]
• ⏰ DEADLINE: [EXACT DATE — e.g. "31 July 2026" or "Rolling — apply anytime"]
• Type: [Fellowship / Online / Conference / Workshop]
• What you get: [specific benefit — stipend amount, certificate, network]
• Eligibility: [key requirements]
• Why Ayam fits: [one sentence — reference his WHO/NUNSA/Ayamtek profile]
• Link: [direct URL]

Sort: FREE first, then funded, then paid.

""", "leadership")

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


    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today}.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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

Current focus reminder:
Primary: IBM Data Science Professional Certificate — Coursera
Secondary: WHO OpenWHO digital health courses — free
These directly support the Health Data Science MSc application.


""", "certifications")

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
    text = ask_with_search(f"""You are AXIS, Ayam Samuel's chief of staff. Today is {today} — Sunday.

WRITING RULES — follow strictly:
- Write in clean, plain British English. No asterisks. No markdown. No em dashes.
- No divider lines of any kind (no ---, no ===, no ***).
- No bold or italic markers.
- No AI preamble such as "Let me compile" or "Here are" or "Certainly".
- Go straight into the content. Start with the first item directly.
- Use numbered lists (1. 2. 3.) for multiple items, not bullet symbols.
- Separate sections with a single blank line only.
- Write as a sharp, informed human assistant — not a language model.


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


Start with:
""", "weekly review")

    send_slack(FOLLOWUPS_WEBHOOK, text)
    if sh:
        log_row(sh, "Weekly Review", [today, "0", "0", "0", "0", "0", ""])
    return text


# ─────────────────────────────────────────
# EMAIL — SECTION METADATA
# ─────────────────────────────────────────
SECTION_META = {
    "NEWS BRIEFING":        {"icon": "🚀", "colour": "#1A2E54", "label": "Daily Intelligence"},
    "OPPORTUNITIES (1-10)": {"icon": "🎯", "colour": "#1A2E54", "label": "Live Opportunities"},
    "OPPORTUNITIES (11-20)":{"icon": "🎯", "colour": "#1A2E54", "label": "More Opportunities"},
    "PLATFORM CONTENT":     {"icon": "📣", "colour": "#9EA1DC", "label": "Content Drafts"},
    "OUTREACH TARGETS":     {"icon": "📨", "colour": "#1A2E54", "label": "Outreach Targets"},
    "FOLLOW-UP REMINDERS":  {"icon": "⏰", "colour": "#C7A27F", "label": "Follow Ups"},
    "SCHOLARSHIPS":         {"icon": "🎓", "colour": "#1A2E54", "label": "Scholarships"},
    "LEADERSHIP":           {"icon": "🌍", "colour": "#9EA1DC", "label": "Leadership"},
    "CERTIFICATIONS":       {"icon": "📜", "colour": "#1A2E54", "label": "Certifications"},
}


def clean_for_email(text):
    """Convert text to clean readable HTML — strip all AI formatting"""
    if not text:
        return ""
    import re as _re
    # Strip all markdown formatting
    text = _re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = _re.sub(r'\*([^*\n]+)\*', r'\1', text)
    text = _re.sub(r'_([^_\n]+)_', r'\1', text)
    text = _re.sub(r'[━─═]{3,}', '', text)
    text = _re.sub(r'(?m)^---+$', '', text)
    text = _re.sub(r'(?m)^>\s*', '', text)
    text = text.replace('—', '-').replace('–', '-')
    # Make URLs clickable
    text = _re.sub(
        r'(https?://[^\s<>"]+)',
        r'<a href="\1" style="color:#555;text-decoration:underline;word-break:break-all;">\1</a>',
        text
    )
    text = text.replace('\n', '<br>')
    text = _re.sub(r'(<br>){3,}', '<br><br>', text)
    return text.strip()


def build_section_card(label, content):
    """Build one styled section card"""
    meta   = SECTION_META.get(label, {"icon": "📌", "colour": "#1A2E54", "label": label})
    cleaned = clean_for_email(content)
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
      <tr>
        <td style="background:#ffffff;border-radius:12px;overflow:hidden;
                   border-left:4px solid {meta['colour']};
                   box-shadow:0 2px 8px rgba(26,46,84,0.08);">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="background:{meta['colour']};padding:12px 22px;">
                <span style="font-family:Arial,sans-serif;font-size:12px;
                             font-weight:700;color:#F7F3ED;letter-spacing:1px;
                             text-transform:uppercase;">
                  {meta['icon']}&nbsp;&nbsp;{meta['label']}
                </span>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 22px 22px 22px;font-family:Arial,sans-serif;
                         font-size:14px;line-height:1.75;color:#0A0A0B;">
                {cleaned}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>"""


def build_html_email(sections, labels):
    """Build clean monochrome single-container HTML newsletter"""

    def make_section(label, content):
        meta    = SECTION_META.get(label, {"icon": "📌", "colour": "#1A2E54", "label": label})
        cleaned = clean_for_email(content)
        return f"""
        <div style="margin-bottom:32px;padding-bottom:32px;
                    border-bottom:1px solid #e8e5e0;">
          <p style="margin:0 0 10px;font-size:10px;font-weight:700;
                     letter-spacing:2.5px;text-transform:uppercase;color:#666;">
            {meta['icon']}&nbsp;&nbsp;{meta['label']}
          </p>
          <div style="font-size:14px;line-height:1.8;color:#1a1a1a;">
            {cleaned}
          </div>
        </div>"""

    sections_html = ""
    for label, content_text in zip(labels, sections):
        if content_text and content_text.strip():
            sections_html += make_section(label, content_text)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AXIS — {today}</title>
</head>
<body style="margin:0;padding:0;background:#f4f1ec;font-family:Georgia,serif;">

  <div style="max-width:600px;margin:40px auto;background:#ffffff;
              border-radius:4px;overflow:hidden;">

    <!-- Header -->
    <div style="background:#111111;padding:40px 48px 36px;">
      <p style="margin:0 0 6px;font-family:Arial,sans-serif;font-size:10px;
                 font-weight:700;letter-spacing:4px;text-transform:uppercase;
                 color:#888888;">
        Personal Brand System
      </p>
      <h1 style="margin:0 0 4px;font-family:Arial,sans-serif;font-size:28px;
                  font-weight:700;color:#ffffff;letter-spacing:-0.5px;">
        AXIS
      </h1>
      <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#888888;">
        {today}
      </p>
    </div>

    <!-- Body -->
    <div style="padding:40px 48px 8px;">
      {sections_html}
    </div>

    <!-- Checklist -->
    <div style="margin:0 48px 32px;padding:24px;background:#f9f7f4;border-radius:4px;">
      <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:10px;
                 font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#888;">
        Morning Actions
      </p>
      <p style="margin:0 0 6px;font-size:13px;font-family:Arial,sans-serif;
                 color:#333;line-height:1.6;">
        ☐ &nbsp;Check Notion Task Manager
      </p>
      <p style="margin:0 0 6px;font-size:13px;font-family:Arial,sans-serif;
                 color:#333;line-height:1.6;">
        ☐ &nbsp;Apply to 3 opportunities before noon
      </p>
      <p style="margin:0 0 6px;font-size:13px;font-family:Arial,sans-serif;
                 color:#333;line-height:1.6;">
        ☐ &nbsp;Send 5 outreach messages
      </p>
      <p style="margin:0;font-size:13px;font-family:Arial,sans-serif;
                 color:#333;line-height:1.6;">
        ☐ &nbsp;Post on 2 platforms
      </p>
    </div>

    <!-- Links -->
    <div style="padding:0 48px 32px;text-align:left;">
      <a href="https://ayamtek.xyz"
         style="display:inline-block;margin-right:12px;font-family:Arial,sans-serif;
                font-size:12px;font-weight:700;color:#111111;text-decoration:none;
                border-bottom:2px solid #111111;padding-bottom:2px;">
        ayamtek.xyz
      </a>
      <a href="https://znap.link/ayamsamuel"
         style="display:inline-block;font-family:Arial,sans-serif;
                font-size:12px;font-weight:700;color:#111111;text-decoration:none;
                border-bottom:2px solid #111111;padding-bottom:2px;">
        All Links
      </a>
    </div>

    <!-- Footer -->
    <div style="background:#111111;padding:24px 48px;">
      <p style="margin:0 0 2px;font-family:Arial,sans-serif;font-size:13px;
                 font-weight:700;color:#ffffff;">
        Ayam Samuel
      </p>
      <p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:11px;color:#888888;">
        Managing Director, Ayamtek &nbsp;·&nbsp; RN, RM &nbsp;·&nbsp; @ayamsamuelxyz
      </p>
      <p style="margin:0;font-family:Arial,sans-serif;font-size:10px;color:#555555;">
        Generated by AXIS at {now} WAT &nbsp;·&nbsp; ayamtek.xyz
      </p>
    </div>

  </div>

</body>
</html>"""


# ─────────────────────────────────────────
# EMAIL DIGEST
# ─────────────────────────────────────────
def send_full_email(sections, labels):
    print("\n📧 SENDING EMAIL DIGEST")
    subject   = f"AXIS Daily Briefing — {today}"
    html_body = build_html_email(sections, labels)
    plain_body = f"AXIS Daily Briefing — {today}\nGenerated: {now}\nOpen in a modern email client to view the full newsletter."
    send_email(subject, html_body, plain_body)


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