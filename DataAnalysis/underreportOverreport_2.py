
"""
PPD vs DS comparison with per-cell verdicts, with robust app-name normalization.

Output Excel has two sheets:
  1) "PPD_DS_by_operation" – matrix: appname | Operation | [Category -> (PPD, DS)]...
  2) "Verdicts"            – tall table: appname | Operation | Category | PPD | DS | verdict

Verdict mapping:
  PPD=1, DS=1 -> AGREE_present
  PPD=0, DS=0 -> AGREE_absent
  PPD=1, DS=0 -> UNDER
  PPD=0, DS=1 -> OVER

Requires:
  pip install xlsxwriter
"""

PPD_JSON_PATH = r"privacy_PolicyData_Json Path"
DS_JSON_PATH  = r"DataSafetylabel data path"
OUTPUT_XLSX   = r"./outputfile.xlsx"

import json
import os
import sys
import re
import unicodedata

try:
    import xlsxwriter
except ImportError:
    print("ERROR: xlsxwriter is required. Install with: pip install xlsxwriter")
    sys.exit(1)


try:
    import category_mapping2 as cm   
except Exception as e:
    print("ERROR: Could not import mapping module. Make sure it’s in the same folder (or on PYTHONPATH).")
    print(f"Details: {e}")
    sys.exit(1)


DISPLAY_LABELS = [
    "Location","Personal info","Financial info","Health and fitness","Messages","Photos and videos",
    "Audio","Files and docs","Calendar","Contacts","App activity","Web browsing",
    "App info and performance","Device or other IDs",
]
LABEL_TO_KEY = {
    "Location": "location",
    "Personal info": "personal_info",
    "Financial info": "financial_info",
    "Health and fitness": "health_fitness",
    "Messages": "messages",
    "Photos and videos": "photos_videos",
    "Audio": "audio",
    "Files and docs": "files_docs",
    "Calendar": "calendar",
    "Contacts": "contacts",
    "App activity": "app_activity",
    "Web browsing": "web_browsing",
    "App info and performance": "app_info_perf",
    "Device or other IDs": "device_or_other_ids",
}
DISPLAY_ORDER = [(label, LABEL_TO_KEY[label]) for label in DISPLAY_LABELS if LABEL_TO_KEY[label] in cm.GOOGLE_SCHEMA]


_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE    = re.compile(r"\s+")

def strip_emoji(text: str) -> str:
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in {"So"} and not (0x1F300 <= ord(ch) <= 0x1FAFF)
    )

def normalize_app_name(name: str) -> str:
    """
    Normalize app names so punctuation/emoji/case/sep differences don't matter.
    Examples that all match:
      "Audiomack_ Music Downloader"
      "Audiomack: Music Downloader"
      "audiomack music downloader"
    """
    if not isinstance(name, str):
        name = str(name or "")
    s = unicodedata.normalize("NFKC", name).lower().strip()
    s = s.replace("_", " ").replace(":", " ").replace("-", " ").replace("·", " ")
    s = re.sub(r"\s*&\s*", " and ", s)
    s = s.replace("®", " ").replace("™", " ").replace("©", " ")
    s = strip_emoji(s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s

def title_like(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split())


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_policy_entries(dst: dict, src: dict) -> dict:
    """
    dst/src like: {"shared":[...], "collected":[...]}
    Merge lists by union while preserving original order where possible.
    """
    for op in ("shared", "collected"):
        dst.setdefault(op, [])
        seen = set(dst[op])
        for item in (src.get(op, []) or []):
            if item not in seen:
                dst[op].append(item)
                seen.add(item)
    return dst

def merge_ds_entries(dst: dict, src: dict) -> dict:
    """
    dst/src are raw DS app objects (with "Data shared" / "Data collected" blocks).
    Shallow-merge keys and union inner dict keys.
    """
    for k in src.keys():
        if k not in dst or not isinstance(dst[k], dict) or not isinstance(src[k], dict):
            dst[k] = src[k]
        else:
            for cat, val in src[k].items():
                if cat not in dst[k]:
                    dst[k][cat] = val
                else:
                    
                    pass
    return dst

def index_and_merge_by_normalized_name(raw_map: dict, is_policy: bool):
    """
    Build normalized index:
      norm_name -> {"display_names": set([...]), "data": merged_entry}
    """
    idx = {}
    for original_name, payload in (raw_map or {}).items():
        norm = normalize_app_name(original_name)
        if norm not in idx:
            idx[norm] = {"display_names": set(), "data": {}}
        idx[norm]["display_names"].add(original_name)
        if is_policy:
            idx[norm]["data"] = merge_policy_entries(idx[norm]["data"], payload or {})
        else:
            idx[norm]["data"] = merge_ds_entries(idx[norm]["data"], payload or {})
    return idx


def compute_rows(policy_summary_raw: dict, data_safety_raw: dict):
    """
    Build rows for the matrix and for verdicts with normalized name matching.

    Returns:
      rows_matrix: list of (display_appname, operation, ppd_map, ds_map)
      rows_verdicts: list of (display_appname, operation, category_label, top_key, ppd, ds, verdict)
    """
    rows_matrix = []
    rows_verdicts = []

    def verdict(ppd: int, ds: int) -> str:
        if ppd == 1 and ds == 1: return "AGREE_present"
        if ppd == 0 and ds == 0: return "AGREE_absent"
        if ppd == 1 and ds == 0: return "UNDER"
        if ppd == 0 and ds == 1: return "OVER"
        return ""

    # Normalize + merge both maps
    pol_idx = index_and_merge_by_normalized_name(policy_summary_raw, is_policy=True)
    ds_idx  = index_and_merge_by_normalized_name(data_safety_raw,  is_policy=False)

    # # Union of all normalized names
    # all_norm_names = set(pol_idx.keys()) | set(ds_idx.keys())

    # Only apps with matching normalized names in both files
    all_norm_names = set(pol_idx.keys()) & set(ds_idx.keys())


    for norm in all_norm_names:
        pol_entry = pol_idx.get(norm, {})
        ds_entry  = ds_idx.get(norm, {})

        # Choose display name: prefer DS name (closer to Play listing), else policy name, else normalized Title Case
        ds_names  = ds_entry.get("display_names", set())
        pol_names = pol_entry.get("display_names", set())
        if ds_names:
            display_appname = sorted(ds_names, key=lambda s: (len(s), s.lower()))[0]
        elif pol_names:
            display_appname = sorted(pol_names, key=lambda s: (len(s), s.lower()))[0]
        else:
            display_appname = title_like(norm)

        # Get data objects
        pol_data = pol_entry.get("data", {}) or {}
        ds_data  = ds_entry.get("data", {}) or {}

        # Parse via your mapping module
        mapped, _, _ = cm.parse_policy_items_with_trace(pol_data)
        ds_sections = cm.parse_label_sections(ds_data)

        for operation in ("shared", "collected"):
            ppd_map = {k: 0 for k in cm.GOOGLE_SCHEMA.keys()}
            ds_map  = {k: 0 for k in cm.GOOGLE_SCHEMA.keys()}

            for top_key in (mapped.get(operation, {}) or {}).keys():
                ppd_map[top_key] = 1
            for top_key in (ds_sections.get(operation, {}) or {}).keys():
                ds_map[top_key] = 1

            rows_matrix.append((display_appname, operation, ppd_map, ds_map))

            # per-category verdicts
            for label, top_key in DISPLAY_ORDER:
                p = ppd_map.get(top_key, 0)
                d = ds_map.get(top_key, 0)
                rows_verdicts.append((display_appname, operation, label, top_key, p, d, verdict(p, d)))

    return rows_matrix, rows_verdicts

# -----------------------------
# Excel writer
# -----------------------------
def write_excel(rows_matrix, rows_verdicts, out_xlsx: str):
    wb = xlsxwriter.Workbook(out_xlsx)

    # ===== Sheet 1: Matrix =====
    ws1 = wb.add_worksheet("PPD_DS_by_operation")
    fmt_center   = wb.add_format({"align": "center", "valign": "vcenter", "border": 1})
    fmt_header   = wb.add_format({"align": "center", "valign": "vcenter", "bold": True, "border": 1})
    fmt_category = wb.add_format({"align": "center", "valign": "vcenter", "bold": True, "bg_color": "#F0F0F0", "border": 1})

    # Headers
    ws1.merge_range(0, 0, 1, 0, "appname", fmt_header)
    ws1.merge_range(0, 1, 1, 1, "Operation", fmt_header)
    col = 2
    for label, _top in DISPLAY_ORDER:
        ws1.merge_range(0, col, 0, col+1, label, fmt_category)
        ws1.write(1, col,   "PPD", fmt_header)
        ws1.write(1, col+1, "DS",  fmt_header)
        col += 2

    # Data
    row_idx = 2
    for app, operation, ppd_map, ds_map in sorted(rows_matrix, key=lambda r: (str(r[0]).lower(), 0 if r[1]=="shared" else 1)):
        ws1.write(row_idx, 0, app, fmt_center)
        ws1.write(row_idx, 1, operation, fmt_center)
        col = 2
        for _label, top_key in DISPLAY_ORDER:
            ws1.write(row_idx, col,   ppd_map.get(top_key, 0), fmt_center)
            ws1.write(row_idx, col+1, ds_map.get(top_key, 0), fmt_center)
            col += 2
        row_idx += 1

    ws1.set_column(0, 0, 36)
    ws1.set_column(1, 1, 12)
    for i in range(2, 2 + len(DISPLAY_ORDER) * 2):
        ws1.set_column(i, i, 14)

    # ===== Sheet 2: Verdicts =====
    ws2 = wb.add_worksheet("Verdicts")
    fmt_header2 = wb.add_format({"align": "center", "valign": "vcenter", "bold": True, "border": 1})
    headers = ["appname", "Operation", "Category", "PPD", "DS", "verdict"]
    for c, h in enumerate(headers):
        ws2.write(0, c, h, fmt_header2)

    row_idx = 1
    for app, operation, label, _top, p, d, v in sorted(
        rows_verdicts, key=lambda r: (str(r[0]).lower(), 0 if r[1]=="shared" else 1, r[2])
    ):
        ws2.write(row_idx, 0, app)
        ws2.write(row_idx, 1, operation)
        ws2.write(row_idx, 2, label)
        ws2.write_number(row_idx, 3, int(p))
        ws2.write_number(row_idx, 4, int(d))
        ws2.write(row_idx, 5, v)
        row_idx += 1

    ws2.set_column(0, 0, 36)
    ws2.set_column(1, 1, 12)
    ws2.set_column(2, 2, 22)
    ws2.set_column(3, 5, 16)

    wb.close()
    print(f"Saved: {out_xlsx}")


def main():
    policy_summary = load_json(PPD_JSON_PATH)
    data_safety    = load_json(DS_JSON_PATH)
    rows_matrix, rows_verdicts = compute_rows(policy_summary, data_safety)
    write_excel(rows_matrix, rows_verdicts, OUTPUT_XLSX)

if __name__ == "__main__":
    main()
