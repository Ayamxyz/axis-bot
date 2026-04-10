"""
AXIS Notion Integration — v2
Uses direct Notion API calls (bypasses notion-client version issues)
Discovers actual property names before writing — handles any schema variation
"""

import os
import re
import time
import requests as req
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN               = os.getenv("NOTION_TOKEN")
NOTION_CLIENT_TRACKER_ID   = os.getenv("NOTION_CLIENT_TRACKER_ID")
NOTION_CONTENT_CALENDAR_ID = os.getenv("NOTION_CONTENT_CALENDAR_ID")
NOTION_SCHOLARSHIP_ID      = os.getenv("NOTION_SCHOLARSHIP_ID")
NOTION_TASK_MANAGER_ID     = os.getenv("NOTION_TASK_MANAGER_ID")
NOTION_CERT_ROADMAP_ID     = os.getenv("NOTION_CERT_ROADMAP_ID")

# Nigeria time — WAT is UTC+1
WAT      = timezone(timedelta(hours=1))
_now_wat = datetime.now(WAT)

today_iso = _now_wat.strftime("%Y-%m-%d")
today_fmt = _now_wat.strftime("%A, %d %B %Y")
tomorrow  = (_now_wat + timedelta(days=1)).strftime("%Y-%m-%d")
in_30d    = (_now_wat + timedelta(days=30)).strftime("%Y-%m-%d")

NOTION_VERSION = "2022-06-28"
BASE           = "https://api.notion.com/v1"


def hdrs():
    return {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION
    }


# ─────────────────────────────────────────
# CORE API CALLS
# ─────────────────────────────────────────
def get_client():
    """Verify token — returns True/False"""
    if not NOTION_TOKEN:
        print("  ⚠️  NOTION_TOKEN not in .env")
        return False
    try:
        r = req.get(f"{BASE}/users/me", headers=hdrs(), timeout=10)
        if r.status_code == 200:
            return True
        print(f"  ⚠️  Notion auth failed ({r.status_code})")
        return False
    except Exception as e:
        print(f"  ⚠️  Notion error: {e}")
        return False


def api_create(database_id, properties, emoji=None):
    body = {"parent": {"database_id": database_id}, "properties": properties}
    if emoji:
        body["icon"] = {"type": "emoji", "emoji": emoji}
    try:
        r = req.post(f"{BASE}/pages", headers=hdrs(), json=body, timeout=15)
        if r.status_code == 200:
            return r.json()
        msg = r.json().get("message", r.text[:200])
        print(f"    ⚠️  Notion create failed: {msg}")
        return None
    except Exception as e:
        print(f"    ⚠️  Notion create error: {e}")
        return None


def api_query(database_id, filter_body=None, page_size=10):
    body = {"page_size": page_size}
    if filter_body:
        body["filter"] = filter_body
    try:
        r = req.post(f"{BASE}/databases/{database_id}/query",
                     headers=hdrs(), json=body, timeout=15)
        if r.status_code == 200:
            return r.json().get("results", [])
        msg = r.json().get("message", r.text[:200])
        print(f"    ⚠️  Notion query failed: {msg}")
        return []
    except Exception as e:
        print(f"    ⚠️  Notion query error: {e}")
        return []


def api_schema(database_id):
    """Get actual property names from a database"""
    try:
        r = req.get(f"{BASE}/databases/{database_id}", headers=hdrs(), timeout=10)
        if r.status_code == 200:
            return r.json().get("properties", {})
        return {}
    except Exception:
        return {}


# ─────────────────────────────────────────
# PROPERTY BUILDERS
# ─────────────────────────────────────────
def p_title(v):    return {"title":        [{"text": {"content": str(v)[:2000]}}]}
def p_text(v):     return {"rich_text":    [{"text": {"content": str(v)[:2000]}}]}
def p_select(v):   return {"select":       {"name": str(v)}}
def p_mselect(vs): return {"multi_select": [{"name": str(v)} for v in vs]}
def p_date(v):     return {"date":         {"start": str(v)}}
def p_url(v):      return {"url": str(v)[:2000]} if v else {"url": None}


# ─────────────────────────────────────────
# SMART PROPERTY RESOLVER
# Maps expected names → actual names in DB
# ─────────────────────────────────────────
ALIASES = {
    "Client Name":          ["Client Name", "Name", "Title"],
    "Stage":                ["Stage", "Pipeline Stage", "Status"],
    "Platform":             ["Platform", "Source", "Channel", "Platforms"],
    "Last Contact":         ["Last Contact", "Last Contact Date", "Contact Date", "Date"],
    "Follow Up Date":       ["Follow Up Date", "Follow-up Date", "Next Contact", "Follow Up"],
    "Next Action":          ["Next Action", "Action", "Next Step"],
    "Link":                 ["Link", "URL", "Website"],
    "Company":              ["Company", "Business", "Organisation", "Organization"],
    "Notes":                ["Notes", "Description", "Details"],
    "Content Title":        ["Content Title", "Title", "Name"],
    "Pillar":               ["Pillar", "Content Pillar", "Category"],
    "Status":               ["Status", "Stage"],
    "Post Date":            ["Post Date", "Date", "Publish Date", "Scheduled Date"],
    "Draft":                ["Draft", "Content", "Body"],
    "Hook":                 ["Hook", "Subtitle"],
    "Agent":                ["Agent", "Assigned To"],
    "Programme Name":       ["Programme Name", "Program Name", "Name", "Title"],
    "Type":                 ["Type", "Category"],
    "Organisation":         ["Organisation", "Organization", "Org", "Provider"],
    "Funding":              ["Funding", "Funding Type", "Award Type"],
    "Application Deadline": ["Application Deadline", "Deadline", "Due Date", "Close Date"],
    "Application Opens":    ["Application Opens", "Opens", "Open Date"],
    "Eligibility Notes":    ["Eligibility Notes", "Eligibility", "Requirements"],
    "Task":                 ["Task", "Name", "Title"],
    "Category":             ["Category", "Type", "Area"],
    "Priority":             ["Priority", "Urgency"],
    "Due Date":             ["Due Date", "Deadline", "Date"],
}


def resolve(schema, desired):
    """Map desired {expected_name: value} to {actual_name: value}"""
    result  = {}
    lc_map  = {k.lower(): k for k in schema}
    for expected, value in desired.items():
        if expected in schema:
            result[expected] = value
            continue
        matched = False
        for alias in ALIASES.get(expected, []):
            if alias in schema:
                result[alias] = value
                matched = True
                break
            if alias.lower() in lc_map:
                result[lc_map[alias.lower()]] = value
                matched = True
                break
        if not matched and expected.lower() in lc_map:
            result[lc_map[expected.lower()]] = value
    return result


# ─────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────
def extract_deadline(text):
    for pattern in [r'\d{4}-\d{2}-\d{2}', r'\d{1,2}\s+\w+\s+\d{4}']:
        m = re.search(pattern, text)
        if m:
            for fmt in ["%Y-%m-%d", "%d %B %Y", "%B %d %Y", "%d %b %Y"]:
                try:
                    return datetime.strptime(m.group().strip(), fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


def extract_url(text):
    m = re.search(r'https?://[^\s\)\]]+', text)
    return m.group().rstrip('.,)') if m else None


def parse_opportunities(text):
    items, blocks = [], re.split(r'\*\d+\.', text)
    for block in blocks[1:]:
        lines = block.strip().split('\n')
        if not lines:
            continue
        tl    = lines[0].strip().replace('*', '')
        parts = tl.split(' — ')
        title = parts[0].strip()[:200]
        full  = '\n'.join(lines)
        url   = extract_url(full)
        budget = "Not listed"
        for line in lines:
            if 'Budget:' in line or 'budget:' in line:
                budget = line.replace('•', '').replace('Budget:', '').strip()[:100]
                break
        items.append({"title": title, "url": url,
                      "notes": f"Budget: {budget}\n\nFrom AXIS leads — {today_fmt}"})
    return items[:5]


def parse_scholarships(text):
    items, blocks = [], re.split(r'\*\d+\.', text)
    for block in blocks[1:]:
        lines = block.strip().split('\n')
        if not lines:
            continue
        tl    = lines[0].strip().replace('*', '')
        parts = tl.split(' — ')
        name  = parts[0].strip()[:200]
        org   = parts[1].strip()[:200] if len(parts) > 1 else ""
        full  = '\n'.join(lines)
        items.append({"name": name, "org": org,
                      "url": extract_url(full),
                      "deadline": extract_deadline(full),
                      "notes": full[:500]})
    return items[:3]


def parse_content_draft(text):
    """Extract LinkedIn draft — tries multiple patterns for robustness"""
    # Try standard format first
    patterns = [
        r'\*📌 LINKEDIN\*(.*?)(?=\*🐦|\*📸|\*👥|\*🎵|\*💬|\*📧|\Z)',
        r'📌 LINKEDIN[:\*]*(.*?)(?=🐦|📸|👥|🎵|💬|📧|\Z)',
        r'LINKEDIN[:\*\s]+(.*?)(?=TWITTER|X\/|INSTAGRAM|FACEBOOK|THREADS|TIKTOK|\Z)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            draft = m.group(1).strip()
            if len(draft) > 50:  # must have meaningful content
                return draft[:2000]
    # Fallback — return first 500 chars of the whole response
    return text[:500]


# ─────────────────────────────────────────
# WRITE FUNCTIONS
# ─────────────────────────────────────────
def add_client(name, url=None, notes=""):
    if not NOTION_CLIENT_TRACKER_ID:
        return
    schema = api_schema(NOTION_CLIENT_TRACKER_ID)
    if not schema:
        return
    fu = (_now_wat + timedelta(days=3)).strftime("%Y-%m-%d")
    desired = {
        "Client / Company": p_title(name),
        "Stage":          p_select("🧊 Cold"),
        "Last Contacted": p_date(today_iso),
        "Next Action Date": p_date(fu),
        "Next Action":    p_text("Send cold outreach message — see Slack #content"),
        "Notes":          p_text(notes[:500])
    }
    if url:
        desired["LinkedIn"] = p_url(url)
    props = resolve(schema, desired)
    if props:
        api_create(NOTION_CLIENT_TRACKER_ID, props, "🤝")


def add_content(title, draft):
    if not NOTION_CONTENT_CALENDAR_ID:
        return
    schema = api_schema(NOTION_CONTENT_CALENDAR_ID)
    if not schema:
        return
    desired = {
        "Post Title / Hook": p_title(title),
        "Status":        p_select("✍️ Drafting"),
        "Scheduled Date": p_date(today_iso),
        "Draft":         p_text(draft),
        "Agent":         p_select("WRITER")
    }
    props = resolve(schema, desired)
    if props:
        api_create(NOTION_CONTENT_CALENDAR_ID, props, "📣")


def add_scholarship(name, org="", url=None, deadline=None,
                    notes="", prog_type="Scholarship"):
    if not NOTION_SCHOLARSHIP_ID:
        return
    schema = api_schema(NOTION_SCHOLARSHIP_ID)
    if not schema:
        return
    desired = {
        "Opportunity Name": p_title(name),
        "Type":           p_select(prog_type),
        "Funding":        p_select("Fully Funded"),
        "Status":         p_select("🔍 Researching"),
        "Notes":          p_text(notes[:500])
    }
    if org:
        desired["Organiser / Funder"] = p_text(org)
    if url:
        desired["Application Link"] = p_url(url)
    if deadline:
        desired["Application Deadline"] = p_date(deadline)
    props = resolve(schema, desired)
    if props:
        api_create(NOTION_SCHOLARSHIP_ID, props,
                   "🎓" if prog_type == "Scholarship" else "🌍")


def add_task(task_name, category="Personal", priority="🟡 Medium",
             due_date=None, notes=""):
    if not NOTION_TASK_MANAGER_ID:
        return
    schema = api_schema(NOTION_TASK_MANAGER_ID)
    if not schema:
        return
    desired = {
        "Task":     p_title(task_name),
        "Category": p_select(category),
        "Priority": p_select(priority),
        "Status":   p_select("📥 Not Started"),
        "Notes":    p_text(notes[:500])
    }
    if due_date:
        desired["Due Date"] = p_date(due_date)
    props = resolve(schema, desired)
    if props:
        api_create(NOTION_TASK_MANAGER_ID, props, "✅")


# ─────────────────────────────────────────
# READ FUNCTIONS
# ─────────────────────────────────────────
def get_title(page, candidates):
    props = page.get("properties", {})
    for name in candidates:
        if name in props:
            arr = props[name].get("title", [])
            if arr:
                return arr[0].get("text", {}).get("content", "")
    return ""


def read_tasks_due():
    if not NOTION_TASK_MANAGER_ID:
        return []
    results = api_query(NOTION_TASK_MANAGER_ID, {
        "and": [
            {"property": "Status", "select": {"does_not_equal": "✅ Done"}},
            {"property": "Status", "select": {"does_not_equal": "🗑️ Cancelled"}},
            {"property": "Due Date", "date": {"before": tomorrow}}
        ]
    })
    tasks = []
    for page in results:
        props = page.get("properties", {})
        name  = get_title(page, ["Task", "Name", "Title"])
        du_p  = props.get("Due Date", props.get("Deadline", props.get("Date", {})))
        du    = (du_p.get("date") or {}).get("start", "") if du_p else ""
        pr_p  = props.get("Priority", {})
        pr    = (pr_p.get("select") or {}).get("name", "🟡 Medium") if pr_p else "🟡 Medium"
        ca_p  = props.get("Category", props.get("Type", {}))
        ca    = (ca_p.get("select") or {}).get("name", "") if ca_p else ""
        if name:
            tasks.append({"name": name, "due": du, "priority": pr,
                           "category": ca, "url": page.get("url", "")})
    return tasks


def read_client_followups():
    if not NOTION_CLIENT_TRACKER_ID:
        return []
    results = api_query(NOTION_CLIENT_TRACKER_ID, {
        "and": [
            {"property": "Stage", "select": {"does_not_equal": "✅ Closed Won"}},
            {"property": "Stage", "select": {"does_not_equal": "❌ Closed Lost"}},
            {"property": "Next Action Date", "date": {"before": tomorrow}}
        ]
    })
    clients = []
    for page in results:
        props = page.get("properties", {})
        name  = get_title(page, ["Client / Company", "Client Name", "Name", "Title"])
        st_p  = props.get("Stage", props.get("Status", {}))
        stage = (st_p.get("select") or {}).get("name", "") if st_p else ""
        fu_p  = props.get("Next Action Date",
                  props.get("Follow-up Date", props.get("Next Contact", {})))
        fu    = (fu_p.get("date") or {}).get("start", "") if fu_p else ""
        co_p  = props.get("Company", props.get("Business", {}))
        co_arr = (co_p.get("rich_text") or []) if co_p else []
        company = co_arr[0].get("text", {}).get("content", "") if co_arr else ""
        if name:
            clients.append({"name": name, "company": company,
                             "stage": stage, "follow_up": fu,
                             "url": page.get("url", "")})
    return clients


def read_scholarship_deadlines():
    if not NOTION_SCHOLARSHIP_ID:
        return []
    results = api_query(NOTION_SCHOLARSHIP_ID, {
        "and": [
            {"property": "Status", "select": {"does_not_equal": "📬 Submitted"}},
            {"property": "Status", "select": {"does_not_equal": "🎉 Awarded"}},
            {"property": "Application Deadline", "date": {"after": today_iso}},
            {"property": "Application Deadline", "date": {"before": in_30d}}
        ]
    })
    items = []
    for page in results:
        props = page.get("properties", {})
        name  = get_title(page, ["Opportunity Name", "Programme Name", "Name", "Title"])
        dl_p  = props.get("Application Deadline",
                  props.get("Deadline", props.get("Due Date", {})))
        dl    = (dl_p.get("date") or {}).get("start", "") if dl_p else ""
        ty_p  = props.get("Type", props.get("Category", {}))
        ptype = (ty_p.get("select") or {}).get("name", "") if ty_p else ""
        if name:
            items.append({"name": name, "deadline": dl,
                           "type": ptype, "url": page.get("url", "")})
    return items


def read_content_today():
    if not NOTION_CONTENT_CALENDAR_ID:
        return []
    results = api_query(NOTION_CONTENT_CALENDAR_ID, {
        "and": [
            {"property": "Status", "select": {"does_not_equal": "✅ Posted"}},
            {"property": "Scheduled Date", "date": {"on_or_after": today_iso}},
            {"property": "Scheduled Date", "date": {"before": tomorrow}}
        ]
    })
    items = []
    for page in results:
        props = page.get("properties", {})
        title = get_title(page, ["Post Title / Hook", "Content Title", "Title", "Name"])
        pl_p  = props.get("Platform", props.get("Platforms", {}))
        plats = [p.get("name", "") for p in
                 (pl_p.get("multi_select") or [])] if pl_p else []
        st_p  = props.get("Status", {})
        stat  = (st_p.get("select") or {}).get("name", "") if st_p else ""
        if title:
            items.append({"title": title, "platforms": plats,
                           "status": stat, "url": page.get("url", "")})
    return items


# ─────────────────────────────────────────
# MORNING BRIEFING
# ─────────────────────────────────────────
def build_notion_briefing(notion_connected):
    if not notion_connected:
        return ""
    sections = []

    tasks = read_tasks_due()
    if tasks:
        lines = []
        for t in tasks[:5]:
            flag = "🔴 OVERDUE" if t['due'] and t['due'] < today_iso else "⏰ DUE TODAY"
            lines.append(f"  {flag}: *{t['name']}* [{t['category']}]")
        sections.append("*📋 NOTION TASKS*\n" + "\n".join(lines))

    clients = read_client_followups()
    if clients:
        lines = []
        for c in clients[:5]:
            flag    = "🔴 OVERDUE" if c['follow_up'] and c['follow_up'] < today_iso else "⏰ TODAY"
            display = c['name'] + (f" — {c['company']}" if c['company'] else "")
            lines.append(f"  {flag}: *{display}* [{c['stage']}]")
        sections.append("*🤝 CLIENT FOLLOW-UPS*\n" + "\n".join(lines))

    schols = read_scholarship_deadlines()
    if schols:
        lines = []
        for s in schols[:5]:
            days_left = ""
            if s['deadline']:
                try:
                    delta     = (datetime.strptime(s['deadline'], "%Y-%m-%d") - datetime.now()).days
                    days_left = f" — *{delta} days left*"
                except ValueError:
                    pass
            lines.append(
                f"  📅 *{s['name']}* [{s['type']}]{days_left} — deadline: {s['deadline']}"
            )
        sections.append("*🎓 UPCOMING DEADLINES*\n" + "\n".join(lines))

    content = read_content_today()
    if content:
        lines = []
        for c in content[:3]:
            plats = ", ".join(c['platforms']) if c['platforms'] else "All platforms"
            lines.append(f"  📣 *{c['title']}* → {plats} [{c['status']}]")
        sections.append("*📅 CONTENT DUE TODAY*\n" + "\n".join(lines))

    if not sections:
        return ""

    return (
        "*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*\n"
        f"*📊 NOTION INTELLIGENCE — {today_fmt}*\n"
        "*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*\n"
        + "\n\n".join(sections)
        + "\n*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*"
    )


# ─────────────────────────────────────────
# SYNC WRAPPERS — called from run.py
# ─────────────────────────────────────────
def sync_opportunities(notion_connected, text):
    if not notion_connected or not text:
        return 0
    count = 0
    for item in parse_opportunities(text):
        add_client(name=item["title"], url=item.get("url"), notes=item.get("notes", ""))
        count += 1
        time.sleep(0.5)  # small delay between Notion writes to avoid rate limits
    return count


def sync_content(notion_connected, text):
    if not notion_connected or not text:
        return
    draft = parse_content_draft(text)
    m     = re.search(r'Core idea:\s*(.+)', text)
    title = m.group(1).strip()[:200] if m else f"Daily content — {today_fmt}"
    add_content(title=title, draft=draft)


def sync_scholarships(notion_connected, text):
    if not notion_connected or not text:
        return 0
    count = 0
    for item in parse_scholarships(text):
        add_scholarship(name=item["name"], org=item.get("org", ""),
                        url=item.get("url"), deadline=item.get("deadline"),
                        notes=item.get("notes", ""), prog_type="Scholarship")
        count += 1
        time.sleep(0.5)
    return count


def sync_leadership(notion_connected, text):
    if not notion_connected or not text:
        return 0
    count = 0
    for item in parse_scholarships(text):
        add_scholarship(name=item["name"], org=item.get("org", ""),
                        url=item.get("url"), deadline=item.get("deadline"),
                        notes=item.get("notes", ""), prog_type="Fellowship")
        count += 1
        time.sleep(0.5)
    return count


def sync_followup_tasks(notion_connected):
    if not notion_connected:
        return
    fu = (_now_wat + timedelta(days=3)).strftime("%Y-%m-%d")
    add_task(f"Follow up on outreach sent {today_fmt}",
             "💼 Client Work", "🔴 Critical", fu,
             "Check #followups for follow-up messages")
    add_task(f"Apply to 3+ opportunities — {today_fmt}",
             "💼 Client Work", "🔴 Critical", today_iso,
             "See Slack #opportunities for 20 leads")
    add_task(f"Post content on 2+ platforms — {today_fmt}",
             "📱 Content", "🟡 Medium", today_iso,
             "See Slack #content for all 8 platform drafts")


# ─────────────────────────────────────────
# CERTIFICATION ROADMAP — weekly Monday read
# ─────────────────────────────────────────
def read_certifications():
    """Read all active certifications from Certification Roadmap"""
    if not NOTION_CERT_ROADMAP_ID:
        return []
    results = api_query(
        NOTION_CERT_ROADMAP_ID,
        filter_body={
            "and": [
                {"property": "Status",
                 "select": {"does_not_equal": "✅ Completed"}},
                {"property": "Status",
                 "select": {"does_not_equal": "🏆 Certified"}}
            ]
        },
        page_size=20
    )
    certs = []
    for page in results:
        props    = page.get("properties", {})
        name     = get_title(page, ["Course / Certification", "Name", "Title"])
        stat_p   = props.get("Status", {})
        status   = (stat_p.get("select") or {}).get("name", "📥 Not Started") if stat_p else "📥 Not Started"
        prog_p   = props.get("Progress Percent", {})
        progress = prog_p.get("number") if prog_p else None
        prio_p   = props.get("Priority", {})
        priority = (prio_p.get("select") or {}).get("name", "") if prio_p else ""
        cat_p    = props.get("Category", {})
        category = (cat_p.get("select") or {}).get("name", "") if cat_p else ""
        tgt_p    = props.get("Target Completion", {})
        target   = (tgt_p.get("date") or {}).get("start", "") if tgt_p else ""
        why_p    = props.get("Why This Matters", {})
        why_arr  = (why_p.get("rich_text") or []) if why_p else []
        why      = why_arr[0].get("text", {}).get("content", "") if why_arr else ""
        if name:
            certs.append({
                "name": name,
                "status": status,
                "progress": progress,
                "priority": priority,
                "category": category,
                "target": target,
                "why": why,
                "url": page.get("url", "")
            })
    # Sort: In Progress first, then by priority
    priority_order = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Medium": 2, "🟢 Low": 3}
    status_order   = {"🔄 In Progress": 0, "📥 Not Started": 1, "⏸️ On Hold": 2}
    certs.sort(key=lambda c: (
        status_order.get(c["status"], 9),
        priority_order.get(c["priority"], 9)
    ))
    return certs


def build_cert_nudge(notion_connected):
    """Build Monday certification nudge — reads Certification Roadmap"""
    if not notion_connected:
        return ""

    certs = read_certifications()
    if not certs:
        return ""

    in_progress  = [c for c in certs if c["status"] == "🔄 In Progress"]
    not_started  = [c for c in certs if c["status"] == "📥 Not Started"]
    on_hold      = [c for c in certs if c["status"] == "⏸️ On Hold"]

    lines = []

    if in_progress:
        lines.append("*🔄 CURRENTLY IN PROGRESS:*")
        for c in in_progress:
            prog = f" — {c['progress']}% complete" if c['progress'] is not None else " — update your progress"
            tgt  = f" | target: {c['target']}" if c['target'] else ""
            lines.append(f"  → *{c['name']}* {prog}{tgt}")
            if c['why']:
                lines.append(f"    _{c['why'][:100]}_")

    if not_started:
        lines.append("\n*📥 NOT STARTED YET — pick one this week:*")
        for c in not_started[:4]:  # Show top 4
            prio = f" [{c['priority']}]" if c['priority'] else ""
            cat  = f" — {c['category']}" if c['category'] else ""
            lines.append(f"  → *{c['name']}*{prio}{cat}")
            if c['why']:
                lines.append(f"    _{c['why'][:100]}_")

    if on_hold:
        lines.append(f"\n*⏸️ ON HOLD ({len(on_hold)} courses)* — revisit when ready")

    # Primary action nudge
    if in_progress:
        focus = in_progress[0]
        prog  = f"{focus['progress']}%" if focus['progress'] is not None else "0%"
        action = f"  *This week:* Continue *{focus['name']}* — currently at {prog}"
    elif not_started:
        focus  = not_started[0]
        action = f"  *This week:* Start *{focus['name']}* — apply for financial aid if on Coursera"
    else:
        action = "  *This week:* Check your courses and update progress"

    total_active = len(in_progress) + len(not_started)

    return (
        "*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*\n"
        f"*📜 WEEKLY CERTIFICATION CHECK — {today_fmt}*\n"
        f"*{total_active} active courses · {len(in_progress)} in progress · {len(not_started)} not started*\n"
        "*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*\n"
        + "\n".join(lines) + "\n\n"
        + action + "\n"
        "*━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━*"
    )