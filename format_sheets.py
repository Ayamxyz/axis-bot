"""
AXIS Google Sheets Formatter — Brand Edition
Follows @ayamsamuelxyz brand guide exactly:
  - Midnight Navy #1A2E54 — headers (light-mode accent law)
  - Periwinkle #9EA1DC — tab colours and accent border
  - Parchment #F7F3ED — row backgrounds
  - Obsidian #0A0A0B — all body text
  - Bronze #C7A27F — micro-highlight (Follow Ups tab only)
  - Sora — single font family throughout
"""

import os
import time
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
SHEET_ID        = os.getenv("GOOGLE_SHEET_ID")

# ─────────────────────────────────────────
# BRAND PALETTE
# ─────────────────────────────────────────
NAVY           = {"red": 0.102, "green": 0.180, "blue": 0.329}   # #1A2E54
PERIWINKLE     = {"red": 0.620, "green": 0.631, "blue": 0.863}   # #9EA1DC
PARCHMENT      = {"red": 0.969, "green": 0.953, "blue": 0.929}   # #F7F3ED
OBSIDIAN       = {"red": 0.039, "green": 0.039, "blue": 0.043}   # #0A0A0B
BRONZE         = {"red": 0.780, "green": 0.635, "blue": 0.498}   # #C7A27F
PARCHMENT_ALT  = {"red": 0.937, "green": 0.918, "blue": 0.894}   # slightly deeper parchment
PERIWINKLE_PALE= {"red": 0.906, "green": 0.910, "blue": 0.957}   # very soft periwinkle
NAVY_PALE      = {"red": 0.827, "green": 0.859, "blue": 0.918}   # light navy tint
BRONZE_PALE    = {"red": 0.961, "green": 0.918, "blue": 0.882}   # light bronze tint
GREEN_PALE     = {"red": 0.824, "green": 0.941, "blue": 0.863}   # soft green
RED_PALE       = {"red": 0.980, "green": 0.867, "blue": 0.867}   # soft red

STATUS_COLOURS = {
    "Won": GREEN_PALE, "Posted": GREEN_PALE, "Done": GREEN_PALE,
    "Accepted": GREEN_PALE, "Completed": GREEN_PALE, "Applied": GREEN_PALE,
    "Lost": RED_PALE, "Rejected": RED_PALE, "Blocked": RED_PALE,
    "Cancelled": RED_PALE, "Dropped": RED_PALE,
    "In Progress": PERIWINKLE_PALE, "Negotiating": PERIWINKLE_PALE,
    "Waiting": PERIWINKLE_PALE, "Essay Drafting": PERIWINKLE_PALE,
    "Submitted": PERIWINKLE_PALE,
    "Contacted": NAVY_PALE, "Proposal Sent": NAVY_PALE,
    "Ready to Post": NAVY_PALE, "Not Applied": NAVY_PALE, "Replied": NAVY_PALE,
    "Researching": BRONZE_PALE, "Draft": BRONZE_PALE,
    "Cold": PARCHMENT_ALT, "Not Started": PARCHMENT_ALT,
    "On Hold": PARCHMENT_ALT, "Idea": PARCHMENT_ALT,
}

SHEET_CONFIGS = {
    "Opportunities": {
        "tab_colour": NAVY,
        "icon": "🎯",
        "col_widths": [180, 140, 80, 100, 100, 110, 120, 200, 280, 110, 120, 200],
        "status_col": 4
    },
    "Scholarships": {
        "tab_colour": PERIWINKLE,
        "icon": "🎓",
        "col_widths": [180, 180, 160, 100, 110, 200, 130, 130, 200],
        "status_col": 6
    },
    "Leadership": {
        "tab_colour": NAVY,
        "icon": "🌍",
        "col_widths": [180, 160, 100, 80, 140, 130, 200, 200],
        "status_col": 6
    },
    "Certifications": {
        "tab_colour": PERIWINKLE,
        "icon": "📜",
        "col_widths": [200, 120, 140, 80, 100, 80, 110, 110, 200],
        "status_col": 4
    },
    "Content Log": {
        "tab_colour": NAVY,
        "icon": "📣",
        "col_widths": [160, 120, 200, 80, 200],
        "status_col": 3
    },
    "Outreach Log": {
        "tab_colour": PERIWINKLE,
        "icon": "📨",
        "col_widths": [160, 200, 120, 280, 160, 120, 200],
        "status_col": 4
    },
    "Follow Ups": {
        "tab_colour": BRONZE,
        "icon": "⏰",
        "col_widths": [130, 200, 100, 280, 120, 120],
        "status_col": 5
    },
    "Weekly Review": {
        "tab_colour": NAVY,
        "icon": "📊",
        "col_widths": [160, 120, 120, 120, 120, 120, 300],
        "status_col": None
    }
}


def connect():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT, scopes=scopes)
    gc      = gspread.authorize(creds)
    sh      = gc.open_by_key(SHEET_ID)
    service = build("sheets", "v4", credentials=creds)
    return sh, service


def border(style="SOLID", r=0.8, g=0.8, b=0.8):
    return {"style": style, "color": {"red": r, "green": g, "blue": b}}


def remove_banding(service, sheet_id):
    try:
        data = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        for sheet in data.get("sheets", []):
            if sheet["properties"]["sheetId"] == sheet_id:
                for band in sheet.get("bandedRanges", []):
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=SHEET_ID,
                        body={"requests": [{"deleteBanding": {
                            "bandedRangeId": band["bandedRangeId"]
                        }}]}
                    ).execute()
    except Exception:
        pass


def build_requests(sheet_id, config):
    col_widths = config["col_widths"]
    num_cols   = len(col_widths)
    tab_colour = config["tab_colour"]
    reqs       = []

    # Freeze header row
    reqs.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1}
            },
            "fields": "gridProperties.frozenRowCount"
        }
    })

    # Tab colour
    reqs.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "tabColor": tab_colour},
            "fields": "tabColor"
        }
    })

    # Header — Navy bg, Parchment text, Sora Bold 10pt, left-aligned
    reqs.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": 0, "endColumnIndex": num_cols
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": NAVY,
                    "textFormat": {
                        "foregroundColor": PARCHMENT,
                        "bold": True,
                        "fontSize": 10,
                        "fontFamily": "Sora"
                    },
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP"
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)"
        }
    })

    # Header row height 42px
    reqs.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 0, "endIndex": 1
            },
            "properties": {"pixelSize": 42},
            "fields": "pixelSize"
        }
    })

    # Data rows — Parchment bg, Obsidian text, Sora 9pt
    reqs.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1, "endRowIndex": 1000,
                "startColumnIndex": 0, "endColumnIndex": num_cols
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": PARCHMENT,
                    "textFormat": {
                        "foregroundColor": OBSIDIAN,
                        "fontSize": 9,
                        "fontFamily": "Sora",
                        "bold": False
                    },
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP"
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,wrapStrategy)"
        }
    })

    # Alternating row banding — Parchment / Parchment Alt only
    reqs.append({
        "addBanding": {
            "bandedRange": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1, "endRowIndex": 1000,
                    "startColumnIndex": 0, "endColumnIndex": num_cols
                },
                "rowProperties": {
                    "firstBandColor":  PARCHMENT,
                    "secondBandColor": PARCHMENT_ALT
                }
            }
        }
    })

    # First column — Navy text, Sora Bold (name/title emphasis)
    reqs.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1, "endRowIndex": 1000,
                "startColumnIndex": 0, "endColumnIndex": 1
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "foregroundColor": NAVY,
                        "bold": True,
                        "fontSize": 9,
                        "fontFamily": "Sora"
                    }
                }
            },
            "fields": "userEnteredFormat.textFormat"
        }
    })

    # Column widths
    for i, width in enumerate(col_widths):
        reqs.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": i, "endIndex": i + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })

    # Data row height 30px
    reqs.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 1, "endIndex": 1000
            },
            "properties": {"pixelSize": 30},
            "fields": "pixelSize"
        }
    })

    # Outer border — Navy medium, inner borders subtle grey
    reqs.append({
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0, "endRowIndex": 1000,
                "startColumnIndex": 0, "endColumnIndex": num_cols
            },
            "top":    border("SOLID_MEDIUM", 0.102, 0.180, 0.329),
            "left":   border("SOLID_MEDIUM", 0.102, 0.180, 0.329),
            "right":  border("SOLID_MEDIUM", 0.102, 0.180, 0.329),
            "bottom": border("SOLID", 0.85, 0.85, 0.85),
            "innerHorizontal": border("SOLID", 0.878, 0.878, 0.882),
            "innerVertical":   border("SOLID", 0.878, 0.878, 0.882)
        }
    })

    # Periwinkle accent line under header
    reqs.append({
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": 0, "endColumnIndex": num_cols
            },
            "bottom": border("SOLID_MEDIUM", 0.620, 0.631, 0.863)
        }
    })

    return reqs


def build_status_rules(sheet_id, status_col):
    rules = []
    for status_text, bg in STATUS_COLOURS.items():
        rules.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": status_col,
                        "endColumnIndex": status_col + 1
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": status_text}]
                        },
                        "format": {
                            "backgroundColor": bg,
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": OBSIDIAN
                            }
                        }
                    }
                },
                "index": 0
            }
        })
    return rules


def build_checkbox(sheet_id, col_index):
    """Add checkbox data validation to a column"""
    return [{
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": col_index,
                "endColumnIndex": col_index + 1
            },
            "rule": {
                "condition": {"type": "BOOLEAN"},
                "showCustomUi": True,
                "strict": True
            }
        }
    }]


# Checkbox columns per sheet — col index (0-based)
CHECKBOX_COLS = {
    "Content Log":    [3],   # Posted
    "Certifications": [7],   # Certificate Earned
    "Follow Ups":     [5],   # Status (done checkbox)
}


def build_ws_map(worksheets):
    ws_map = {}
    for ws in worksheets:
        ws_map[ws.title] = ws.id
        parts = ws.title.split(" ", 1)
        if len(parts) == 2:
            base = parts[1].strip()
            if base not in ws_map:
                ws_map[base] = ws.id
    return ws_map


def main():
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  AXIS Sheets Formatter — Brand Edition")
    print("  @ayamsamuelxyz brand guide applied")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    sh, service = connect()
    print(f"✅ Connected: {sh.title}\n")

    ws_map = build_ws_map(sh.worksheets())

    for sheet_name, config in SHEET_CONFIGS.items():
        icon = config["icon"]
        if sheet_name not in ws_map:
            print(f"  ⚠️  {icon} {sheet_name} — not found")
            continue

        sheet_id = ws_map[sheet_name]
        print(f"  {icon}  Formatting {sheet_name}...")

        remove_banding(service, sheet_id)
        time.sleep(0.5)

        reqs = build_requests(sheet_id, config)
        if config["status_col"] is not None:
            reqs += build_status_rules(sheet_id, config["status_col"])

        # Add checkboxes for relevant columns
        for col_idx in CHECKBOX_COLS.get(sheet_name, []):
            reqs += build_checkbox(sheet_id, col_idx)

        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": reqs}
            ).execute()
            print("     ✅ Done")
        except Exception as e:
            print(f"     ❌ Error: {e}")

        time.sleep(1.2)

    # Rename tabs with icons
    print("\n  Updating tab names...")
    icon_reqs = []
    for sheet_name, config in SHEET_CONFIGS.items():
        if sheet_name not in ws_map:
            continue
        new_name = f"{config['icon']} {sheet_name}"
        icon_reqs.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws_map[sheet_name],
                    "title": new_name
                },
                "fields": "title"
            }
        })
    if icon_reqs:
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": icon_reqs}
            ).execute()
            print("  ✅ Tab names updated")
        except Exception as e:
            print(f"  ⚠️  {e}")

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ COMPLETE — Brand guide applied

  #1A2E54  Navy       — all headers
  #9EA1DC  Periwinkle — accent border + tab colours
  #F7F3ED  Parchment  — row backgrounds
  #0A0A0B  Obsidian   — all body text
  #C7A27F  Bronze     — Follow Ups tab only
  Sora     Font       — throughout

View your sheet:
https://docs.google.com/spreadsheets/d/{SHEET_ID}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    main()
