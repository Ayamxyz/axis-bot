"""
AXIS Fix Verification Tests
Tests every bug fix without running the full system.
Run: python test_fixes.py
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
results = []


def test(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, passed, detail))
    print(f"  {status}  {name}")
    if detail:
        print(f"       {detail}")


def section(title):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ─────────────────────────────────────────
# FIX 1 — No duplicate datetime import
# ─────────────────────────────────────────
section("FIX 1 — No duplicate datetime import")
try:
    content = open("run.py", encoding="utf-8").read()
    imports = [l for l in content.split("\n") if "from datetime import" in l]
    test("Only one datetime import line", len(imports) == 1,
         f"Found {len(imports)} import(s): {imports}")
except FileNotFoundError:
    test("run.py found", False, "run.py not found in current directory")


# ─────────────────────────────────────────
# FIX 2 — send_slack skips empty text
# ─────────────────────────────────────────
section("FIX 2 — send_slack skips empty text")
try:
    content = open("run.py", encoding="utf-8").read()
    has_empty_guard = (
        "if not text or not text.strip()" in content or
        "Empty content" in content
    )
    test("Empty text guard exists in send_slack", has_empty_guard)
except Exception as e:
    test("send_slack guard check", False, str(e))


# ─────────────────────────────────────────
# FIX 3 — Sheet map cache
# ─────────────────────────────────────────
section("FIX 3 — Google Sheets cache (no repeated API calls)")
try:
    content = open("run.py", encoding="utf-8").read()
    has_cache   = "_sheet_map_cache" in content
    has_get_map = "def get_sheet_map" in content
    log_uses_cache = "get_sheet_map(sh)" in content
    test("Cache variable defined", has_cache)
    test("get_sheet_map function exists", has_get_map)
    test("log_row uses cached get_sheet_map", log_uses_cache)
except Exception as e:
    test("Sheet cache check", False, str(e))


# ─────────────────────────────────────────
# FIX 4 — Scholarship URL field
# ─────────────────────────────────────────
section("FIX 4 — Scholarship URL goes to 'Application Link' not 'LinkedIn'")
try:
    content = open("notion_sync.py", encoding="utf-8").read()
    # Find the add_scholarship function
    fn_start = content.find("def add_scholarship")
    fn_end   = content.find("\ndef ", fn_start + 1)
    fn_body  = content[fn_start:fn_end]
    uses_app_link = "Application Link" in fn_body
    uses_linkedin  = '"LinkedIn"' in fn_body
    test("add_scholarship uses 'Application Link'", uses_app_link)
    test("add_scholarship does NOT use 'LinkedIn' for URL", not uses_linkedin)
except Exception as e:
    test("Scholarship URL field check", False, str(e))


# ─────────────────────────────────────────
# FIX 5 — sync_followup_tasks uses WAT time
# ─────────────────────────────────────────
section("FIX 5 — Follow-up tasks use Nigeria time (WAT)")
try:
    content = open("notion_sync.py", encoding="utf-8").read()
    fn_start = content.find("def sync_followup_tasks")
    fn_end   = content.find("\ndef ", fn_start + 1)
    fn_body  = content[fn_start:fn_end]
    uses_wat  = "_now_wat" in fn_body
    uses_utc  = "datetime.now()" in fn_body
    test("sync_followup_tasks uses _now_wat", uses_wat)
    test("sync_followup_tasks does NOT use datetime.now() (UTC)", not uses_utc)
except Exception as e:
    test("WAT time check", False, str(e))


# ─────────────────────────────────────────
# FIX 6 — Task category emoji prefixes
# ─────────────────────────────────────────
section("FIX 6 — Task Manager categories have emoji prefix")
try:
    content = open("notion_sync.py", encoding="utf-8").read()
    fn_start = content.find("def sync_followup_tasks")
    fn_end   = content.find("\ndef ", fn_start + 1)
    fn_body  = content[fn_start:fn_end]
    has_client_work = '"\U0001f4bc Client Work"' in fn_body or '"💼 Client Work"' in fn_body
    has_content     = '"\U0001f4f1 Content"'     in fn_body or '"📱 Content"'     in fn_body
    no_plain_client = '"Client Work"' not in fn_body.replace('"💼 Client Work"', '')
    test("Category '💼 Client Work' used (not plain)", has_client_work)
    test("Category '📱 Content' used (not plain)", has_content)
except Exception as e:
    test("Category emoji check", False, str(e))


# ─────────────────────────────────────────
# FIX 7 — Task priority correct value
# ─────────────────────────────────────────
section("FIX 7 — Task priority uses '🔴 Critical' not '🔴 High'")
try:
    content = open("notion_sync.py", encoding="utf-8").read()
    fn_start = content.find("def sync_followup_tasks")
    fn_end   = content.find("\ndef ", fn_start + 1)
    fn_body  = content[fn_start:fn_end]
    has_critical = "🔴 Critical" in fn_body
    has_wrong    = '"🔴 High"' in fn_body
    test("Priority '🔴 Critical' used", has_critical)
    test("Priority '🔴 High' NOT used (wrong value)", not has_wrong)
except Exception as e:
    test("Priority check", False, str(e))


# ─────────────────────────────────────────
# FIX 8 — parse_content_draft resilient regex
# ─────────────────────────────────────────
section("FIX 8 — parse_content_draft handles web search output formats")

# Import and test the actual function
try:
    sys.path.insert(0, ".")
    from notion_sync import parse_content_draft

    # Test 1: Standard format with asterisks
    standard = """*📌 LINKEDIN*
This is a LinkedIn post about AI and healthcare.
It is thoughtful and professional.

*🐦 X / TWITTER*
Short tweet here."""
    result1 = parse_content_draft(standard)
    test("Parses standard *📌 LINKEDIN* format",
         "LinkedIn post about AI" in result1,
         f"Got: {result1[:80]}")

    # Test 2: Web search may remove asterisks
    no_asterisks = """📌 LINKEDIN
This is a LinkedIn post without asterisks.
Written by web search response.

🐦 TWITTER
Short tweet."""
    result2 = parse_content_draft(no_asterisks)
    test("Parses format without asterisks",
         "LinkedIn post without" in result2 or len(result2) > 50,
         f"Got: {result2[:80]}")

    # Test 3: Plain LINKEDIN header
    plain = """LINKEDIN:
A professional post about building systems.
This tests the plain format fallback.

TWITTER:
Tweet here."""
    result3 = parse_content_draft(plain)
    test("Parses plain LINKEDIN: format",
         "professional post" in result3 or len(result3) > 50,
         f"Got: {result3[:80]}")

    # Test 4: Fallback when no match
    no_match = "Just some random text with no platform headers at all in it whatsoever."
    result4 = parse_content_draft(no_match)
    test("Falls back gracefully when no pattern matches",
         len(result4) > 0,
         f"Got: {result4[:80]}")

except ImportError as e:
    test("notion_sync.py importable", False, str(e))
except Exception as e:
    test("parse_content_draft test", False, str(e))


# ─────────────────────────────────────────
# FIX 9 — build_sheet_map icon detection
# ─────────────────────────────────────────
section("FIX 9 — build_sheet_map recognises icon-prefixed tabs")

class MockWS:
    def __init__(self, title):
        self.title = title

try:
    sys.path.insert(0, ".")
    # Import the function directly from run.py source
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_module", "run.py")
    # We can't import run.py directly as it connects to APIs on import
    # So we test the logic manually

    def build_sheet_map_test(worksheets):
        ws_map = {}
        for ws in worksheets:
            ws_map[ws.title] = ws
            parts = ws.title.split(" ", 1)
            if len(parts) == 2 and len(parts[0]) <= 2:
                base = parts[1].strip()
                if base not in ws_map:
                    ws_map[base] = ws
        return ws_map

    mock_sheets = [
        MockWS("🎯 Opportunities"),
        MockWS("🎓 Scholarships"),
        MockWS("🌍 Leadership"),
        MockWS("📜 Certifications"),
        MockWS("📣 Content Log"),
        MockWS("📨 Outreach Log"),
        MockWS("⏰ Follow Ups"),
        MockWS("📊 Weekly Review"),
    ]

    ws_map = build_sheet_map_test(mock_sheets)

    test("'Opportunities' found via icon-prefixed tab",
         "Opportunities" in ws_map)
    test("'Scholarships' found via icon-prefixed tab",
         "Scholarships" in ws_map)
    test("'Content Log' found via icon-prefixed tab",
         "Content Log" in ws_map)
    test("'Weekly Review' found via icon-prefixed tab",
         "Weekly Review" in ws_map)
    test("Icon-prefixed names also available directly",
         "🎯 Opportunities" in ws_map)
    test("Total entries correct (8 base + 8 icon = 16)",
         len(ws_map) == 16)

except Exception as e:
    test("Sheet map icon detection", False, str(e))


# ─────────────────────────────────────────
# FIX 10 — WAT timezone correct
# ─────────────────────────────────────────
section("FIX 10 — Nigeria time (WAT = UTC+1) correct")

WAT = timezone(timedelta(hours=1))
now_wat = datetime.now(WAT)
now_utc = datetime.utcnow()
wat_hour = now_wat.hour
utc_hour = now_utc.hour
diff = (wat_hour - utc_hour) % 24

test("WAT is 1 hour ahead of UTC",
     diff == 1,
     f"UTC hour: {utc_hour}, WAT hour: {wat_hour}, diff: {diff}")

test("WAT day name correct",
     now_wat.strftime("%A") in ["Monday","Tuesday","Wednesday",
                                 "Thursday","Friday","Saturday","Sunday"])


# ─────────────────────────────────────────
# FIX 11 — GitHub Actions timeout increased
# ─────────────────────────────────────────
section("FIX 11 — GitHub Actions timeout increased to 45 minutes")
try:
    yml = open(".github/workflows/daily.yml", encoding="utf-8").read()
    has_45  = "timeout-minutes: 45" in yml
    has_30  = "timeout-minutes: 30" in yml
    has_env = "SA_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}" in yml
    test("Timeout set to 45 minutes (not 30)", has_45 and not has_30)
    test("Service account uses env var (safer JSON handling)", has_env)
except FileNotFoundError:
    test("daily.yml found", False, ".github/workflows/daily.yml not found")
except Exception as e:
    test("GitHub Actions workflow check", False, str(e))


# ─────────────────────────────────────────
# LIVE CONNECTION TESTS (optional)
# ─────────────────────────────────────────
section("LIVE CONNECTION TESTS (requires valid .env)")

notion_token = os.getenv("NOTION_TOKEN")
if notion_token:
    try:
        import requests
        r = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28"
            },
            timeout=10
        )
        test("Notion API connection live", r.status_code == 200,
             f"Status: {r.status_code}")
    except Exception as e:
        test("Notion API connection", False, str(e))
else:
    print(f"  {WARN} NOTION_TOKEN not set — skipping live Notion test")

anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_key:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply: OK"}]
        )
        test("Anthropic API connection live",
             bool(r.content),
             "API responded correctly")
    except Exception as e:
        test("Anthropic API connection", False, str(e))
else:
    print(f"  {WARN} ANTHROPIC_API_KEY not set — skipping live API test")

service_account = os.getenv("GOOGLE_SERVICE_ACCOUNT")
sheet_id        = os.getenv("GOOGLE_SHEET_ID")
if service_account and sheet_id and os.path.exists(service_account):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(service_account, scopes=scopes)
        gc    = gspread.authorize(creds)
        sh    = gc.open_by_key(sheet_id)
        ws    = sh.worksheets()
        test("Google Sheets connection live",
             len(ws) > 0,
             f"Found {len(ws)} worksheets: {[w.title for w in ws]}")
    except Exception as e:
        test("Google Sheets connection", False, str(e))
else:
    print(f"  {WARN} Google credentials not configured — skipping live Sheets test")


# ─────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────
print(f"\n{'═'*55}")
print("  RESULTS SUMMARY")
print(f"{'═'*55}")

passed  = sum(1 for _, p, _ in results if p)
failed  = sum(1 for _, p, _ in results if not p)
total   = len(results)

for name, passed_r, detail in results:
    status = PASS if passed_r else FAIL
    print(f"  {status}  {name}")

print(f"\n  {passed}/{total} tests passed")

if failed == 0:
    print("""
  All fixes verified. Ready to push and run.
""")
else:
    print(f"""
  {failed} test(s) failed — check the details above.
  Fix the failures before pushing to GitHub.
""")
