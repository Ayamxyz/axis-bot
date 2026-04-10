"""
AXIS Notion Test Script
Run this to test Notion connection independently before running run.py
Tests: connection, read from each database, write a test entry to each
"""

from notion_sync import (
    get_client,
    api_schema,
    api_query,
    api_create,
    read_tasks_due,
    read_client_followups,
    read_scholarship_deadlines,
    read_content_today,
    add_client,
    add_content,
    add_scholarship,
    add_task,
    p_title,
    NOTION_CLIENT_TRACKER_ID,
    NOTION_CONTENT_CALENDAR_ID,
    NOTION_SCHOLARSHIP_ID,
    NOTION_TASK_MANAGER_ID,
    NOTION_CERT_ROADMAP_ID
)

SEP = "─" * 50

def test_connection():
    print(f"\n{SEP}")
    print("1. TESTING CONNECTION")
    print(SEP)
    result = get_client()
    if result:
        print("  ✅ Notion connected successfully")
    else:
        print("  ❌ Connection failed — check NOTION_TOKEN in .env")
    return result


def test_schema(label, db_id):
    print(f"\n  📋 Schema: {label}")
    if not db_id:
        print(f"    ⚠️  No ID set in .env for {label}")
        return {}
    schema = api_schema(db_id)
    if schema:
        print(f"    ✅ Found {len(schema)} properties:")
        for name, prop in schema.items():
            ptype = prop.get("type", "unknown")
            # Show select options if available
            if ptype == "select":
                opts = [o["name"] for o in prop.get("select", {}).get("options", [])]
                print(f"       • {name} ({ptype}): {opts}")
            elif ptype == "multi_select":
                opts = [o["name"] for o in prop.get("multi_select", {}).get("options", [])]
                print(f"       • {name} ({ptype}): {opts}")
            else:
                print(f"       • {name} ({ptype})")
    else:
        print(f"    ❌ Could not read schema — check database ID and integration permissions")
    return schema


def test_schemas():
    print(f"\n{SEP}")
    print("2. READING DATABASE SCHEMAS")
    print(SEP)
    test_schema("Client Tracker",          NOTION_CLIENT_TRACKER_ID)
    test_schema("Content Calendar",         NOTION_CONTENT_CALENDAR_ID)
    test_schema("Scholarship Tracker",      NOTION_SCHOLARSHIP_ID)
    test_schema("Task Manager",             NOTION_TASK_MANAGER_ID)
    test_schema("Certification Roadmap",    NOTION_CERT_ROADMAP_ID)


def test_reads():
    print(f"\n{SEP}")
    print("3. TESTING READS (morning intelligence)")
    print(SEP)

    print("\n  📋 Task Manager — overdue/due today:")
    tasks = read_tasks_due()
    if tasks:
        for t in tasks:
            print(f"    → {t['name']} [{t['due']}] [{t['priority']}]")
    else:
        print("    ℹ️  No tasks due — this is normal if database is empty")

    print("\n  🤝 Client Tracker — follow-ups due:")
    clients = read_client_followups()
    if clients:
        for c in clients:
            print(f"    → {c['name']} — {c['stage']} [follow up: {c['follow_up']}]")
    else:
        print("    ℹ️  No follow-ups due — normal if database is empty")

    print("\n  🎓 Scholarship Tracker — deadlines in 30 days:")
    schols = read_scholarship_deadlines()
    if schols:
        for s in schols:
            print(f"    → {s['name']} [{s['type']}] deadline: {s['deadline']}")
    else:
        print("    ℹ️  No upcoming deadlines — normal if database is empty")

    print("\n  📅 Content Calendar — scheduled today:")
    content = read_content_today()
    if content:
        for c in content:
            print(f"    → {c['title']} → {c['platforms']} [{c['status']}]")
    else:
        print("    ℹ️  Nothing scheduled today — normal if calendar is empty")


def test_writes():
    print(f"\n{SEP}")
    print("4. TESTING WRITES (one test entry per database)")
    print(SEP)
    print("  Writing test entries — check your Notion after this runs\n")

    print("  🤝 Client Tracker...")
    add_client(
        name="[TEST] Sample Lead — delete me",
        url="https://ayamtek.xyz",
        notes="Test entry from AXIS test script — safe to delete"
    )

    print("  📣 Content Calendar...")
    add_content(
        title="[TEST] Sample Draft — delete me",
        draft="This is a test content draft from AXIS. Safe to delete."
    )

    print("  🎓 Scholarship Tracker...")
    add_scholarship(
        name="[TEST] Sample Scholarship — delete me",
        org="Test Organisation",
        deadline="2026-12-31",
        notes="Test entry from AXIS test script — safe to delete",
        prog_type="Scholarship"
    )

    print("  ✅ Task Manager...")
    add_task(
        task_name="[TEST] Sample Task — delete me",
        category="Personal",
        priority="🟢 Low",
        due_date="2026-12-31",
        notes="Test entry from AXIS test script — safe to delete"
    )

    print("\n  Done. Open Notion and check each database for [TEST] entries.")
    print("  If you see them — writes are working perfectly.")
    print("  Delete the test entries after confirming.")


def main():
    print("\n" + "═" * 50)
    print("  AXIS NOTION TEST")
    print("  Tests connection, schema, reads and writes")
    print("═" * 50)

    # Step 1 — Connection
    connected = test_connection()
    if not connected:
        print("\n  ❌ Cannot continue — fix connection first")
        return

    # Step 2 — Schemas
    test_schemas()

    # Step 3 — Reads
    test_reads()

    # Step 4 — Writes
    print(f"\n{SEP}")
    answer = input("Run write tests? This adds [TEST] entries to Notion. (y/n): ").strip().lower()
    if answer == "y":
        test_writes()
    else:
        print("  Skipped write tests.")

    print(f"\n{'═' * 50}")
    print("  TEST COMPLETE")
    print("  If schemas show correctly and writes succeeded,")
    print("  Notion integration is ready for run.py")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
